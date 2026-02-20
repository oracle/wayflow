# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import logging
import os
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, Iterator, List, Optional

import litellm
from litellm.types.utils import ModelResponse, ModelResponseStream
from pydantic import BaseModel

from wayflowcore._metadata import MetadataType
from wayflowcore.conversation import Conversation
from wayflowcore.messagelist import ImageContent, Message, MessageType, TextContent
from wayflowcore.tokenusage import TokenUsage
from wayflowcore.tools import ToolRequest

from ._openaihelpers._utils import _prepare_openai_compatible_json_schema, _safe_json_loads
from ._requesthelpers import (
    StreamChunkType,
    TaggedMessageChunkType,
    TaggedMessageChunkTypeWithTokenUsage,
)
from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import LlmCompletion, LlmModel, Prompt


def _convert_tool_call_deltas_into_tool_requests(tool_deltas: List[Any]) -> List[ToolRequest]:
    tool_requests: List[ToolRequest] = []
    for tool_call in tool_deltas:
        function = tool_call.function
        name = function.name
        arguments = function.arguments

        if not isinstance(name, str) or not isinstance(arguments, str):
            # Be defensive: provider may send partial deltas.
            continue

        tool_requests.append(
            ToolRequest(
                name=name,
                args=_safe_json_loads(arguments),
                tool_request_id=str(tool_call.id or ""),
            )
        )

    return tool_requests


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from wayflowcore.messagelist import Message

GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"


class GeminiAuth(BaseModel):
    pass


class GeminiApiKeyAuth(GeminiAuth):
    api_key: Optional[str] = None
    """API key to use. If None, will try to load it from the env variable GEMINI_API_KEY"""


class GeminiCloudAuth(GeminiAuth):
    project_id: Optional[str] = None
    location: str = "us-central1"
    vertex_credentials: str | None = None
    """JSON dictionary or path to file containing the google cloud config"""


class GeminiModel(LlmModel):
    def __init__(
        self,
        model_id: str,
        auth: Optional[GeminiAuth] = None,
        # networking
        proxy: str | None = None,
        # defaults
        generation_config: "LlmGenerationConfig | None" = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Generic model to connect to Gemini on Vertex AI using Google's Python SDKs.
        Implementation note: use litellm.completion and litellm.acompletion as the way to actually make the API calls.

        Parameters
        ----------
        model_id:
            Gemini model name (e.g., gemini-2.x...). Availability depends on GCP region/project.
        auth:
            Optional explicit google-auth credentials. Defaults to GeminiApiKeyAuth and loads from environment variable.
        proxy:
            Optional proxy URL if required.
        ...
        """
        self.auth: GeminiAuth = auth or GeminiApiKeyAuth()
        self.proxy = proxy

        super().__init__(
            model_id=model_id,
            generation_config=generation_config,
            supports_structured_generation=True,
            supports_tool_calling=True,
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )

    def generate(
        self, prompt: "Prompt | str", _conversation: Optional["Conversation"] = None
    ) -> LlmCompletion:
        from wayflowcore.templates import PromptTemplate
        from wayflowcore.tracing.span import LlmGenerationSpan

        if not isinstance(prompt, Prompt):
            prompt = PromptTemplate.from_string(prompt).format()

        if prompt.generation_config is None:
            prompt = prompt.copy(generation_config=self.generation_config)

        self._check_supports_prompt(prompt)

        with LlmGenerationSpan(
            llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
        ) as span:
            logger.debug("LLM generating: %s", prompt)
            request = self._build_litellm_request(prompt, stream=False)
            response = litellm.completion(**request)
            message = self._litellm_response_to_message(response)
            message = prompt.parse_output(message)
            completion = LlmCompletion(
                message=message, token_usage=self._litellm_usage_to_token_usage(response)
            )
            self._update_token_usage(
                conversation=_conversation, prompt=prompt, completion=completion
            )
            span.record_end_span_event(completion=completion)
            return completion

    def stream_generate(
        self,
        prompt: "Prompt | str",
        _conversation: Optional["Conversation"] = None,
    ) -> Iterable[TaggedMessageChunkType]:
        from wayflowcore.templates import PromptTemplate
        from wayflowcore.tracing.span import LlmGenerationSpan

        if not isinstance(prompt, Prompt):
            prompt = PromptTemplate.from_string(prompt).format()

        if prompt.generation_config is None:
            prompt = prompt.copy(generation_config=self.generation_config)

        self._check_supports_prompt(prompt)

        def _generator() -> Iterator[TaggedMessageChunkType]:
            with LlmGenerationSpan(
                llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
            ) as span:
                logger.debug("LLM generating (stream): %s", prompt)
                request = self._build_litellm_request(prompt, stream=True)
                stream = litellm.completion(**request)

                yield StreamChunkType.START_CHUNK, Message(
                    content="", message_type=MessageType.AGENT
                )

                accumulated_text = ""
                tool_deltas: List[Any] = []
                final_token_usage: Optional[TokenUsage] = None

                for chunk in stream:
                    if isinstance(chunk, dict):
                        model_chunk = litellm.ModelResponseStream(**chunk)
                    else:
                        model_chunk = chunk

                    if not isinstance(model_chunk, ModelResponseStream):
                        model_chunk = litellm.ModelResponseStream(**model_chunk)

                    choice0 = model_chunk.choices[0]
                    delta = choice0.delta
                    if delta is not None and delta.tool_calls:
                        tool_deltas.extend(delta.tool_calls)

                    text_delta = delta.content or ""
                    if text_delta:
                        accumulated_text += text_delta
                        yield StreamChunkType.TEXT_CHUNK, Message(
                            content=text_delta, message_type=MessageType.AGENT
                        )

                    if final_token_usage is None:
                        final_token_usage = self._litellm_usage_to_token_usage(model_chunk)

                if tool_deltas:
                    final_message = Message(
                        tool_requests=_convert_tool_call_deltas_into_tool_requests(tool_deltas)
                    )
                else:
                    final_message = Message(contents=[TextContent(content=accumulated_text)])
                final_message = prompt.parse_output(final_message)

                completion = LlmCompletion(message=final_message, token_usage=final_token_usage)
                self._update_token_usage(
                    conversation=_conversation, prompt=prompt, completion=completion
                )
                span.record_end_span_event(completion=completion)

                yield StreamChunkType.END_CHUNK, final_message

        return _generator()

    async def _generate_impl(self, prompt: Prompt) -> LlmCompletion:
        request = self._build_litellm_request(prompt, stream=False)
        response = await litellm.acompletion(**request)
        message = self._litellm_response_to_message(response)
        message = prompt.parse_output(message)
        return LlmCompletion(
            message=message,
            token_usage=self._litellm_usage_to_token_usage(response),
        )

    async def _stream_generate_impl(
        self, prompt: Prompt
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        request = self._build_litellm_request(prompt, stream=True)
        stream = await litellm.acompletion(**request)

        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None

        accumulated = ""
        final_token_usage: Optional[TokenUsage] = None
        tool_deltas: List[Any] = []
        async for chunk in stream:
            if isinstance(chunk, dict):
                chunk = litellm.ModelResponse(**chunk)

            choice0 = chunk.choices[0]
            delta_obj = getattr(choice0, "delta", None)
            delta_tool_calls = getattr(delta_obj, "tool_calls", None)
            if isinstance(delta_tool_calls, list) and delta_tool_calls:
                tool_deltas.extend(delta_tool_calls)

            delta_text = self._extract_stream_delta_text(chunk)
            if delta_text:
                accumulated += delta_text
                yield (
                    StreamChunkType.TEXT_CHUNK,
                    Message(content=delta_text, message_type=MessageType.AGENT),
                    None,
                )

            final_token_usage = final_token_usage or self._litellm_usage_to_token_usage(chunk)

        if tool_deltas:
            final_message = Message(
                tool_requests=_convert_tool_call_deltas_into_tool_requests(tool_deltas)
            )
        else:
            final_message = Message(content=accumulated, message_type=MessageType.AGENT)
        final_message = prompt.parse_output(final_message)
        yield StreamChunkType.END_CHUNK, final_message, final_token_usage

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "model_type": "gemini",
            "model_id": self.model_id,
            "proxy": self.proxy,
            "auth": self._serialize_auth_config(self.auth),
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
            "supports_structured_generation": self.supports_structured_generation,
            "supports_tool_calling": self.supports_tool_calling,
        }

    def _serialize_auth_config(self, auth: GeminiAuth) -> Dict[str, Any]:
        if isinstance(auth, GeminiApiKeyAuth):
            return {"type": "api_key"}
        if isinstance(auth, GeminiCloudAuth):
            return {
                "type": "cloud",
                "project_id": auth.project_id,
                "location": auth.location,
                "vertex_credentials": "**MASKED**" if auth.vertex_credentials else None,
            }
        return {"type": "unknown"}

    def _build_litellm_request(self, prompt: Prompt, stream: bool) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": self.model_id,
            "messages": self._prompt_to_litellm_messages(prompt),
            "stream": stream,
        }

        if self.proxy is not None:
            request["proxy"] = self.proxy

        if prompt.generation_config is not None:
            request.update(self._generation_config_to_litellm_kwargs(prompt.generation_config))

        if prompt.tools is not None:
            request["tools"] = [t.to_openai_format() for t in prompt.tools]

        if prompt.response_format is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": _prepare_openai_compatible_json_schema(prompt.response_format),
            }

        if isinstance(self.auth, GeminiApiKeyAuth):
            api_key = self.auth.api_key or os.getenv(GEMINI_API_KEY_ENV_VAR)
            if api_key is not None:
                request["api_key"] = api_key
        elif isinstance(self.auth, GeminiCloudAuth):
            if self.auth.vertex_credentials is not None:
                if os.path.exists(self.auth.vertex_credentials):
                    with open(self.auth.vertex_credentials, "r") as f:
                        request["vertex_credentials"] = json.load(f)
                else:
                    request["vertex_credentials"] = self.auth.vertex_credentials
            if self.auth.project_id is not None:
                request["vertex_project"] = self.auth.project_id
            request["vertex_location"] = self.auth.location

        return request

    def _generation_config_to_litellm_kwargs(
        self, generation_config: LlmGenerationConfig
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if generation_config.temperature is not None:
            kwargs["temperature"] = generation_config.temperature
        if generation_config.top_p is not None:
            kwargs["top_p"] = generation_config.top_p
        if generation_config.max_tokens is not None:
            kwargs["max_tokens"] = generation_config.max_tokens
        if generation_config.stop is not None:
            kwargs["stop"] = generation_config.stop
        if generation_config.frequency_penalty is not None:
            kwargs["frequency_penalty"] = generation_config.frequency_penalty
        if generation_config.extra_args:
            kwargs.update(generation_config.extra_args)
        return kwargs

    def _prompt_to_litellm_messages(self, prompt: Prompt) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        for message in prompt.messages:
            if message.tool_requests or message.tool_result:
                raise ValueError(
                    "GeminiModel expects native tool calling via prompt.tools; "
                    "tool request/result messages are not supported."
                )

            contents: List[Dict[str, Any]] = []
            for content in message.contents:
                if isinstance(content, TextContent):
                    contents.append({"type": "text", "text": content.content})
                elif isinstance(content, ImageContent):
                    contents.append(
                        {"type": "image_url", "image_url": {"url": content.base64_content}}
                    )
                else:
                    raise RuntimeError(f"Unsupported content type: {content.__class__.__name__}")

            messages.append({"role": message.role, "content": contents if contents else ""})
        return messages

    def _litellm_response_to_message(self, response: ModelResponse) -> "Message":
        choice0 = response.choices[0]
        # `ModelResponse.choices` is typed as `Choices | StreamingChoices` in LiteLLM.
        # Non-streaming completions should always return `Choices` (which has
        # `.message`), but mypy cannot prove that from the public type.
        if not hasattr(choice0, "message"):
            raise ValueError(
                "GeminiModel expected a non-streaming response with a message; "
                "got a streaming choice."
            )

        msg = choice0.message

        provider_specific_fields = getattr(msg, "provider_specific_fields", None)
        extra_content: Optional[Dict[str, Any]]
        if isinstance(provider_specific_fields, dict):
            extra_content = {"provider_specific_fields": provider_specific_fields}
        else:
            extra_content = None

        tool_calls = msg.tool_calls
        if tool_calls:
            tool_requests: List[ToolRequest] = []
            for tc in tool_calls:
                if not tc.function.name or not tc.id:
                    raise ValueError(
                        f"GeminiModel expected non-empty tool name or tool-call id but got: {tc.function.name}, {tc.id}"
                    )
                tool_requests.append(
                    ToolRequest(
                        name=tc.function.name,
                        args=_safe_json_loads(tc.function.arguments),
                        tool_request_id=tc.id,
                    )
                )

            return Message(tool_requests=tool_requests, _extra_content=extra_content)

        content = msg.content or ""
        return Message(contents=[TextContent(content=content)], _extra_content=extra_content)

    def _litellm_usage_to_token_usage(self, response: Any) -> Optional[TokenUsage]:
        if isinstance(response, dict):
            response = litellm.ModelResponse(**response)
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=getattr(usage, "prompt_tokens", 0),
            output_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
            reasoning_tokens=getattr(usage, "reasoning_tokens", 0) or 0,
            exact_count=True,
        )

    # Note: tool-call delta conversion is shared with other models.

    def _extract_stream_delta_text(self, chunk: Any) -> str:
        try:
            if isinstance(chunk, dict):
                chunk = litellm.ModelResponse(**chunk)
            choice0 = chunk.choices[0]
            delta = choice0.delta
            if delta is None:
                return ""
            return delta.content or ""
        except Exception:
            return ""
