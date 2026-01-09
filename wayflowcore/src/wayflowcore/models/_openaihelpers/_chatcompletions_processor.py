# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
from typing import Any, AsyncIterable, Callable, Dict, List, Optional, TypedDict

from wayflowcore._utils.formatting import stringify
from wayflowcore.messagelist import ImageContent, Message, TextContent
from wayflowcore.tokenusage import TokenUsage
from wayflowcore.tools import Tool, ToolRequest
from wayflowcore.tools.tools import ExtraContentT

from .._requesthelpers import StreamChunkType, TaggedMessageChunkTypeWithTokenUsage
from ..llmgenerationconfig import LlmGenerationConfig
from ..llmmodel import Prompt
from ._api_processor import _APIProcessor
from ._utils import _prepare_openai_compatible_json_schema, _safe_json_loads

logger = logging.getLogger(__name__)


class OpenAIToolRequestAsDictT(TypedDict, total=True):
    tool_request_id: str
    name: str
    args: str
    _extra_content: Optional[ExtraContentT]


class _ChatCompletionsAPIProcessor(_APIProcessor):

    @staticmethod
    def _tool_to_openai_function_dict(tool: Tool) -> Dict[str, Any]:
        openai_function_dict: Dict[str, Any] = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
            },
        }
        openai_function_dict["function"]["parameters"] = _APIProcessor._get_tool_parameters(tool)

        return openai_function_dict

    def _generate_api_specific_request_params(
        self, json_obj: Dict[str, Any], stream: bool
    ) -> Dict[str, Any]:

        if stream:
            json_obj["stream_options"] = dict(include_usage=True)

        if not self._is_openai_endpoint():
            # Some OpenAI Compatible APIs (e.g., VLLM) will choose to ignore this parameter if it is
            # not supported, whereas others (e.g., Gemini) will return an error.
            json_obj.pop("store")

        return json_obj

    def _convert_message_into_openai_message_dict(
        self, m: "Message", supports_tool_role: bool
    ) -> List[Dict[str, Any]]:
        if m.tool_requests:
            if any(not isinstance(content, TextContent) for content in m.contents):
                raise ValueError(
                    "Invalid tool request. A tool request message should only contain text contents"
                )
            converted_message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.tool_request_id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                        **(
                            {"extra_content": tc._extra_content}
                            if tc._extra_content is not None
                            else {}
                        ),
                    }
                    for tc in (m.tool_requests or [])
                ],
            }
            if m.content:
                converted_message["content"] = m.content
            return [converted_message]
        elif m.tool_result:
            if len(m.contents):
                raise ValueError(
                    "Invalid tool result. Tool results should not contain any message content"
                )

            return [
                {
                    "role": "tool" if supports_tool_role else "user",
                    "tool_call_id": m.tool_result.tool_request_id,
                    "content": stringify(m.tool_result.content),
                }
            ]
        else:
            role = m.role
            all_contents = []

            for content in m.contents:
                if isinstance(content, ImageContent):
                    all_contents.append(
                        {"type": "image_url", "image_url": {"url": content.base64_content}}
                    )
                elif isinstance(content, TextContent):
                    all_contents.append({"type": "text", "text": content.content})
                else:
                    raise RuntimeError(f"Unsupported content type: {content.__class__.__name__}")

            return [{"role": role, "content": all_contents if len(all_contents) else ""}]

    def _convert_prompt(self, prompt: "Prompt", supports_tool_role: bool) -> Dict[str, Any]:
        payload_arguments: Dict[str, Any] = {
            "messages": [
                m
                for message in prompt.messages
                for m in self._convert_message_into_openai_message_dict(message, supports_tool_role)
            ],
            "prompt_cache_key": self._get_prompt_cache_key_from_prompt(prompt),
        }

        if prompt.tools is not None:
            payload_arguments["tools"] = [t.to_openai_format() for t in prompt.tools]
        if prompt.response_format is not None:
            payload_arguments["response_format"] = {
                "type": "json_schema",
                "json_schema": _prepare_openai_compatible_json_schema(prompt.response_format),
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
            kwargs["max_completion_tokens"] = generation_config.max_tokens
        if generation_config.stop is not None:
            kwargs["stop"] = generation_config.stop
        if generation_config.frequency_penalty is not None:
            kwargs["frequency_penalty"] = generation_config.frequency_penalty
        if generation_config.extra_args:
            kwargs.update(generation_config.extra_args)
        return kwargs

    def _convert_openai_response_into_message(self, response: Any) -> "Message":
        extracted_message = response["choices"][0]["message"]
        if len(extracted_message.get("tool_calls") or []) > 0:
            message = Message(
                tool_requests=[
                    ToolRequest(
                        name=tc["function"]["name"],
                        args=_safe_json_loads(tc["function"]["arguments"]),
                        tool_request_id=tc["id"],
                        _extra_content=tc.get("extra_content"),
                    )
                    for tc in extracted_message["tool_calls"]
                ],
                role="assistant",
            )
        else:
            # content might be empty when certain models (like gemini) decide
            # to finish the conversation
            content = extracted_message.get("content", "")
            message = Message(
                role="assistant",
                contents=[TextContent(content=content)],
                _extra_content=extracted_message.get("extra_content"),
            )
        return message

    def _extract_usage(self, response_data: Dict[str, Any]) -> Optional[TokenUsage]:
        if "usage" not in response_data:
            return None

        response = response_data["usage"]
        cached_tokens = 0
        if "prompt_tokens_details" in response and "cached_tokens" in (
            response["prompt_tokens_details"] or []
        ):
            cached_tokens = response["prompt_tokens_details"]["cached_tokens"]
        return TokenUsage(
            input_tokens=response["prompt_tokens"],
            output_tokens=response["completion_tokens"],
            total_tokens=response["total_tokens"],
            cached_tokens=cached_tokens,
            exact_count=True,
        )

    async def _json_iterator_from_stream_of_api_str(
        self,
        line_iterator: AsyncIterable[str],
    ) -> AsyncIterable[Dict[str, Any]]:
        """
        Transforms an iterator of lines (following the `completions` API
        https://platform.openai.com/docs/api-reference/completions/create#completions_create-stream
        into an iterator of json objects.
        """
        async for line in line_iterator:
            if not line:
                continue

            if not line.startswith("data:"):
                logger.info("Received unexpected chunk from remote: %r", line)
                continue

            content = line.lstrip("data: ")

            if content == "[DONE]":
                break

            if content == "":
                continue

            yield json.loads(content)

    async def _tagged_chunk_iterator_from_stream_of_openai_compatible_json(
        self,
        json_object_iterable: AsyncIterable[Any],
        post_processing: Optional[Callable[["Message"], "Message"]] = None,
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        """Using API: https://platform.openai.com/docs/api-reference/chat-streaming/streaming"""

        from wayflowcore.messagelist import Message, MessageType

        # start the stream
        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None

        text = ""
        tool_deltas = []
        token_usage: Optional[TokenUsage] = None
        async for json_object in json_object_iterable:
            text_delta = ""
            for chunk in json_object["choices"]:
                delta = chunk["delta"]
                if "tool_calls" in delta:
                    tool_deltas.extend(delta["tool_calls"])
                if "content" in delta and delta["content"] is not None:
                    text_delta = delta["content"]
                    text += text_delta

            if "usage" in json_object and json_object["usage"] is not None:
                raw_usage = json_object["usage"]
                token_usage = self._extract_usage(raw_usage)
            yield StreamChunkType.TEXT_CHUNK, Message(
                content=text_delta, message_type=MessageType.AGENT
            ), None

        if len(tool_deltas) > 0:
            message_type = MessageType.TOOL_REQUEST
            tool_calls = self._convert_tool_deltas_into_tool_requests(tool_deltas)
        else:
            message_type = MessageType.AGENT
            tool_calls = None

        message = Message(content=text, message_type=message_type, tool_requests=tool_calls)
        if post_processing is not None:
            message = post_processing(message)
        yield StreamChunkType.END_CHUNK, message, token_usage

    def _convert_tool_deltas_into_tool_requests(self, tool_deltas: List[Any]) -> List[ToolRequest]:
        """Gets tool deltas and return list of proper tool calls"""
        tool_requests_dict: Dict[int, OpenAIToolRequestAsDictT] = {}
        for delta in tool_deltas:
            index = delta["index"]
            if index not in tool_requests_dict:
                tool_requests_dict[index] = {
                    "name": "",
                    "args": "",
                    "tool_request_id": "",
                    "_extra_content": None,
                }
            if "id" in delta:
                tool_requests_dict[index]["tool_request_id"] = delta["id"]
            if "function" in delta:
                func = delta["function"]
                if "name" in func:
                    tool_requests_dict[index]["name"] += func["name"]
                if "arguments" in func:
                    tool_requests_dict[index]["args"] += func["arguments"]
            if "extra_content" in delta:
                tool_requests_dict[index]["_extra_content"] = delta["extra_content"]
        return [
            ToolRequest(
                name=s["name"],
                tool_request_id=s["tool_request_id"],
                args=_safe_json_loads(s["args"]),
                _extra_content=s.get("_extra_content"),
            )
            for s in tool_requests_dict.values()
        ]
