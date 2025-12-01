# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
from typing import Any, AsyncIterable, Callable, Dict, List, Optional

from wayflowcore._utils.formatting import stringify
from wayflowcore.messagelist import (
    ImageContent,
    Message,
    MessageContent,
    TextContent,
    _ReasoningContent,
)
from wayflowcore.tokenusage import TokenUsage
from wayflowcore.tools import Tool, ToolRequest

from .._requesthelpers import StreamChunkType, TaggedMessageChunkTypeWithTokenUsage
from ..llmgenerationconfig import LlmGenerationConfig
from ..llmmodel import Prompt
from ._api_processor import _APIProcessor
from ._utils import _prepare_openai_compatible_json_schema

logger = logging.getLogger(__name__)


class _ResponsesAPIProcessor(_APIProcessor):
    @staticmethod
    def _tool_to_openai_function_dict(tool: Tool) -> Dict[str, Any]:
        openai_function_dict: Dict[str, Any] = {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
        }
        openai_function_dict["parameters"] = _APIProcessor._get_tool_parameters(tool)
        return openai_function_dict

    def _convert_message_with_tool_requests_into_openai_message(
        self, m: Message
    ) -> List[Dict[str, Any]]:
        if any(not isinstance(content, TextContent) for content in m.contents):
            raise ValueError(
                "Invalid tool request. A tool request message should only contain text contents"
            )

        output_message: List[Dict[str, Any]] = []

        if m._reasoning_content:
            output_message.append(m._reasoning_content)

        if m.content:
            output_message.append(
                {
                    "content": m.content,
                    "role": "assistant",
                }
            )

        for tc in m.tool_requests or []:
            output_message.append(
                {
                    "type": "function_call",
                    "name": tc.name,
                    "arguments": json.dumps(tc.args),
                    "call_id": tc.tool_request_id,
                }
            )

        return output_message

    def _convert_message_with_tool_result_into_openai_message(
        self, m: Message
    ) -> List[Dict[str, Any]]:
        if len(m.contents):
            raise ValueError(
                "Invalid tool result. Tool results should not contain any message content"
            )

        if not m.tool_result:
            raise ValueError(
                "Internal Errror: Expected Message to have a Tool Result for converting to OpenAI-Responses Compatible Dictionary"
            )

        return [
            {
                "type": "function_call_output",
                "call_id": m.tool_result.tool_request_id,
                "output": stringify(m.tool_result.content),
            }
        ]

    def _convert_message_with_content_into_openai_message(self, m: Message) -> List[Dict[str, Any]]:
        role = m.role
        all_contents = []

        for content in m.contents:
            if isinstance(content, ImageContent):
                all_contents.append(
                    {"type": "input_image", "image_url": content.base64_content, "detail": "auto"}
                )
            elif isinstance(content, TextContent):
                all_contents.append({"type": "input_text", "text": content.content})
            else:
                raise RuntimeError(f"Unsupported content type: {content.__class__.__name__}")

        openai_dict: Dict[str, Any] = dict(role=role, type="message")

        if len(all_contents) == 1 and all_contents[0]["type"] == "input_text":
            openai_dict["content"] = all_contents[0]["text"]
        elif len(all_contents) == 0:
            openai_dict["content"] = ""
        else:
            openai_dict["content"] = all_contents

        if role == "assistant" and m._reasoning_content:
            return [m._reasoning_content, openai_dict]
        else:
            return [openai_dict]

    def _convert_message_into_openai_message_dict(self, m: Message) -> List[Dict[str, Any]]:
        """
        Convert a WayFlow ``Message`` object into a list of dictionaries compatible with the OpenAI Responses API.

        This transformation supports text, image, and tool call/result messages, and produces output in the format described by:
        https://platform.openai.com/docs/api-reference/responses/create#responses_create-input

        Parameters
        ----------
        m : Message
            The WayFlow message instance to convert.

        Returns
        -------
        List[Dict[str, Any]]
            A list of dictionaries formatted for OpenAI's Responses API.

        Example
        -------
        .. code-block:: python

            from wayflowcore.messagelist import Message, TextContent, ImageContent
            from wayflowcore.models._openaihelpers._responses_processor import _ResponsesAPIProcessor

            # Construct a multimodal user message with text and image content
            message = Message(
                role="user",
                contents=[
                    TextContent("What is in this image?"),
                    ImageContent(base64_content="image-base64")
                ]
            )

            # Initialize processor and convert
            processor = _ResponsesAPIProcessor()
            result = processor._convert_message_into_openai_message_dict(message)
            print(result)

        Output
        ------
        .. code-block:: python

            [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "What is in this image?"},
                        {"type": "input_image", "image_url": "image-base64"}
                    ],
                }
            ]

        """
        if m.tool_requests:
            return self._convert_message_with_tool_requests_into_openai_message(m)
        elif m.tool_result:
            return self._convert_message_with_tool_result_into_openai_message(m)
        else:
            return self._convert_message_with_content_into_openai_message(m)

    def _convert_prompt(self, prompt: "Prompt") -> Dict[str, Any]:
        payload_arguments: Dict[str, Any] = {
            "input": [
                m
                for message in prompt.messages
                for m in self._convert_message_into_openai_message_dict(message)
            ],
        }

        payload_arguments["prompt_cache_key"] = self._get_prompt_cache_key_from_prompt(prompt)

        if prompt.tools is not None:
            payload_arguments["tools"] = [
                t.to_openai_format(api_type=self.api_type) for t in prompt.tools
            ]
        if prompt.response_format is not None:
            payload_arguments["text"] = {
                "format": {
                    "type": "json_schema",
                    **_prepare_openai_compatible_json_schema(prompt.response_format),
                },
            }
        return payload_arguments

    def _convert_generation_params(
        self, generation_config: Optional[LlmGenerationConfig]
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if generation_config is None:
            return kwargs
        if generation_config.top_p is not None:
            kwargs["top_p"] = generation_config.top_p
        if generation_config.temperature is not None:
            kwargs["temperature"] = generation_config.temperature
        if generation_config.max_tokens is not None:
            kwargs["max_output_tokens"] = generation_config.max_tokens
        if generation_config.extra_args:
            if "reasoning" in generation_config.extra_args:
                kwargs["include"] = [
                    "reasoning.encrypted_content"
                ]  # Pass reasoning traces if user has configured the reasoning parameter

                if "summary" not in generation_config.extra_args["reasoning"]:
                    generation_config.extra_args["reasoning"]["summary"] = "auto"

            kwargs.update(generation_config.extra_args)

        return kwargs

    def _convert_openai_response_into_message(self, response: Any) -> "Message":
        from wayflowcore.messagelist import Message

        current_tool_requests: List[ToolRequest] = []
        output_contents: List[MessageContent] = []
        reasoning_content: Optional[_ReasoningContent] = None
        prompt_cache_key = None

        if "incomplete_details" in response and response["incomplete_details"]:
            raise ValueError(
                f"LLM generation incomplete due to reason: {response['incomplete_details']}"
            )

        for item in response["output"]:
            if item["type"] == "function_call":
                current_tool_requests.append(
                    ToolRequest(
                        name=item["name"],
                        args=json.loads(item["arguments"]),
                        tool_request_id=item["call_id"],
                    )
                )

            elif item["type"] == "message":
                if len(item["content"]) > 1:
                    raise NotImplementedError(
                        "Cannot currently handle multiple content parts in Responses API response object of type: message."
                    )

                if item["content"][0]["type"] == "output_text":
                    output_contents.append(TextContent(item["content"][0]["text"]))

            elif item["type"] == "image_generation_call" and item["result"]:
                output_contents.append(ImageContent(base64_content=item["result"]))

            elif item["type"] == "reasoning" and self._reasoning_has_content(item):
                reasoning_content = item.copy()

        tool_requests: Optional[List[ToolRequest]] = current_tool_requests
        if not len(current_tool_requests):
            tool_requests = None

        if "prompt_cache_key" in response:
            prompt_cache_key = response["prompt_cache_key"]

        message = Message(
            contents=output_contents,
            tool_requests=tool_requests,
            role="assistant",
            _reasoning_content=reasoning_content,
            _prompt_cache_key=prompt_cache_key,
        )

        return message

    def _extract_usage(self, response_data: Dict[str, Any]) -> Optional[TokenUsage]:
        if "usage" not in response_data:
            return None

        response = response_data["usage"]
        cached_tokens = 0
        if "input_tokens_details" in response and "cached_tokens" in (
            response["input_tokens_details"] or []
        ):
            cached_tokens = response["input_tokens_details"]["cached_tokens"]

        reasoning_tokens = 0
        if "output_tokens_details" in response and "reasoning_tokens" in (
            response["output_tokens_details"] or []
        ):
            reasoning_tokens = response["output_tokens_details"]["reasoning_tokens"]

        return TokenUsage(
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            total_tokens=response["total_tokens"],
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            exact_count=True,
        )

    async def _tagged_chunk_iterator_from_stream_of_openai_compatible_json(
        self,
        json_object_iterable: AsyncIterable[Any],
        post_processing: Optional[Callable[["Message"], "Message"]] = None,
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        """Using API: https://platform.openai.com/docs/api-reference/responses-streaming/response"""
        from wayflowcore.messagelist import Message, MessageType

        # start the stream
        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None

        text = ""
        final_output_text = None
        tool_calls = []
        token_usage: Optional[TokenUsage] = None
        reasoning_content: Optional[_ReasoningContent] = None
        prompt_cache_key = None
        image_content = []

        async for json_object in json_object_iterable:
            text_delta = ""

            if "response" in json_object and "prompt_cache_key" in json_object["response"]:
                prompt_cache_key = json_object["response"]["prompt_cache_key"]

            if json_object["type"] == "response.failed":
                raise ValueError(
                    f"Streaming failed due to reason: {json_object['response']['error']}"
                )

            if json_object["type"] == "response.incomplete":
                raise ValueError(
                    f"Streaming incomplete due to reason: {json_object['response']['incomplete_details']}"
                )

            if json_object["type"] == "response.output_item.done":
                if json_object["item"]["type"] == "reasoning":
                    if self._reasoning_has_content(
                        json_object["item"]
                    ):  # Only add reasoning content in the message if the API returns any reasoning content. Otherwise gives error with OpenAI API
                        reasoning_content = json_object["item"]

                if (
                    json_object["item"]["type"] == "image_generation_call"
                    and json_object["item"]["result"]
                ):
                    image_content.append(json_object["item"]["result"])

                if json_object["item"]["type"] == "function_call":
                    tool_calls.append(json_object["item"])

            if json_object["type"] == "response.output_text.delta":
                text_delta = json_object["delta"]

            if json_object["type"] == "response.completed":
                for output in json_object["response"]["output"]:
                    if output["type"] == "message":
                        try:
                            # Workaround: vLLM somtimes returns tool call arguments as a text rather than using the "function_call" message type in Responses API.
                            # Thus, we try to convert the output text to a tool call. If this fails, we simply assume the output text to be the final response returned by the model.
                            tool_req = self._convert_vllm_tool_call(output)
                            tool_calls.append(tool_req)
                        except:
                            if "content" in output:
                                content = output["content"][0]
                                if content["type"] == "output_text":
                                    final_output_text = content["text"]

                                if content["type"] == "refusal":
                                    final_output_text = content["refusal"]

            if (
                "response" in json_object
                and "usage" in json_object["response"]
                and json_object["response"]["usage"] is not None
            ):
                raw_usage = json_object["response"]["usage"]
                token_usage = self._extract_usage(raw_usage)

            text += text_delta

            if len(text_delta):
                yield StreamChunkType.TEXT_CHUNK, Message(
                    content=text_delta, role="assistant"
                ), None

        tool_requests: Optional[List[ToolRequest]]
        if len(tool_calls) > 0:
            tool_requests = self._convert_tool_calls_into_tool_requests(tool_calls)
        else:
            tool_requests = None

        if final_output_text is not None:
            text = final_output_text  # We use final generated output_text if we miss any text delta during streaming

        if len(image_content):
            message_contents: List[MessageContent] = [TextContent(text)]
            for image in image_content:
                message_contents.append(ImageContent(base64_content=image))

            message = Message(
                contents=message_contents,
                role="assistant",
                tool_requests=tool_requests,
                _reasoning_content=reasoning_content,
                _prompt_cache_key=prompt_cache_key,
            )
        else:
            message = Message(
                content=text,
                role="assistant",
                tool_requests=tool_requests,
                _reasoning_content=reasoning_content,
                _prompt_cache_key=prompt_cache_key,
            )

        if post_processing is not None:
            message = post_processing(message)

        yield StreamChunkType.END_CHUNK, message, token_usage

    def _reasoning_has_content(self, reasoning_object: _ReasoningContent) -> bool:
        if "summary" in reasoning_object and len(reasoning_object["summary"]):
            return True
        elif "content" in reasoning_object and len(reasoning_object["content"]):
            return True
        return False

    def _convert_tool_calls_into_tool_requests(
        self, tool_calls: List[Any]
    ) -> Optional[List[ToolRequest]]:
        """Gets tool calls and return list of proper tool requests"""
        tool_requests = []
        for req in tool_calls:
            if isinstance(req, ToolRequest):
                tool_requests.append(req)
                continue

            tool_requests.append(
                ToolRequest(
                    name=req["name"],
                    tool_request_id=req["call_id"],
                    args=json.loads(req["arguments"]),
                )
            )

        if len(tool_requests) == 0:
            return None
        return tool_requests

    def _convert_vllm_tool_call(self, json_output: Dict[str, Any]) -> ToolRequest:
        """Tries to convert vLLM output text to tool calls"""

        function_inputs = json.loads(json_output["content"][0]["text"])
        return ToolRequest(
            name=function_inputs["name"],
            args=function_inputs["parameters"],
            tool_request_id=json_output["id"],
        )

    async def _json_iterator_from_stream_of_api_str(
        self,
        line_iterator: AsyncIterable[str],
    ) -> AsyncIterable[Dict[str, Any]]:
        """
        Transforms an iterator of lines (following the `responses` API
        https://platform.openai.com/docs/guides/streaming-responses?api-mode=responses
        into an iterator of json objects.
        """
        async for line in line_iterator:
            if not line:
                continue

            if line.startswith("data:"):
                content = line.lstrip("data:")

            # The "event" line has the format "event: 'type_of_streaming_event'"
            # There is no data in it, hence we can skip this line
            elif line.startswith("event:"):
                continue
            else:
                logger.info("Received unexpected chunk from remote: %r", line)
                continue

            content = content.strip()
            if content == "[DONE]":
                break

            if content == "":
                continue

            yield json.loads(content)
