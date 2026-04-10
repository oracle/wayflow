# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import os
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, List, Optional, cast

from pydantic import BaseModel

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import AsyncContext, get_execution_context
from wayflowcore._utils.lazy_loader import LazyLoader
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.tokenusage import TokenUsage

from ._openaihelpers import _ChatCompletionsAPIProcessor
from ._openaihelpers._utils import _prepare_openai_compatible_json_schema
from ._requesthelpers import (
    StreamChunkType,
    TaggedMessageChunkType,
    TaggedMessageChunkTypeWithTokenUsage,
)
from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import LlmCompletion, LlmModel, Prompt
from .openaiapitype import OpenAIAPIType

if TYPE_CHECKING:
    # Mirror the OCI model import pattern: GeminiModel is re-exported from
    # wayflowcore.models, but importing that package should not eagerly import
    # LiteLLM. Keep the runtime path behind LazyLoader.
    import litellm

    from wayflowcore.conversation import Conversation
    from wayflowcore.tools import ToolRequest
else:
    litellm = LazyLoader("litellm")


logger = logging.getLogger(__name__)


class GeminiApiKeyAuth(BaseModel):
    api_key: Optional[str] = None


class GeminiCloudAuth(BaseModel):
    project_id: Optional[str] = None
    location: str = "global"
    vertex_credentials: str | Dict[str, Any] | None = None


def _litellm_object_to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped_value = value.model_dump(exclude_none=True)
        except TypeError:
            dumped_value = value.model_dump()
        if isinstance(dumped_value, dict):
            return dumped_value
    if hasattr(value, "dict"):
        try:
            dumped_value = value.dict(exclude_none=True)
        except TypeError:
            dumped_value = value.dict()
        if isinstance(dumped_value, dict):
            return dumped_value
    raise TypeError(
        "Unexpected LiteLLM payload type. Expected a dict or LiteLLM object convertible to dict."
    )


def _rename_message_and_tool_call_field(
    *, message_payload: Dict[str, Any], source_key: str, target_key: str
) -> Dict[str, Any]:
    for mapping in [message_payload, *(message_payload.get("tool_calls") or [])]:
        if source_key in mapping:
            source_value = mapping.pop(source_key)
            if target_key not in mapping:
                mapping[target_key] = source_value
    return message_payload


class GeminiModel(LlmModel):
    """Run Gemini models through LiteLLM using Google AI Studio or Vertex AI auth."""

    def __init__(
        self,
        model_id: str,
        auth: GeminiApiKeyAuth | GeminiCloudAuth,
        proxy: Optional[str] = None,
        generation_config: Optional[LlmGenerationConfig] = None,
        supports_structured_generation: Optional[bool] = True,
        supports_tool_calling: Optional[bool] = True,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        self.auth = auth
        self.proxy = proxy
        self._processor = _ChatCompletionsAPIProcessor(
            model_id=model_id,
            base_url="",
            api_type=OpenAIAPIType.CHAT_COMPLETIONS,
        )
        super().__init__(
            model_id=model_id,
            generation_config=generation_config,
            supports_structured_generation=supports_structured_generation,
            supports_tool_calling=supports_tool_calling,
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )

    def generate(
        self, prompt: "Prompt | str", _conversation: Optional["Conversation"] = None
    ) -> LlmCompletion:
        # Outside a plain sync context, defer to the base class so it can bridge
        # through generate_async instead of forcing a nested sync LiteLLM call.
        # That still comes back into GeminiModel._generate_impl(), so Gemini is
        # still executed through LiteLLM, just via litellm.acompletion.
        if get_execution_context() is not AsyncContext.SYNC:
            return super().generate(prompt, _conversation)

        from wayflowcore.tracing.span import LlmGenerationSpan

        prompt = self._prepare_prompt_sync(prompt)
        self._check_supports_prompt(prompt)

        with LlmGenerationSpan(
            llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
        ) as span:
            logger.debug("LLM generating: %s", prompt)
            response = litellm.completion(**self._build_litellm_request(prompt, stream=False))
            completion = self._completion_from_response(prompt, response)
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
        # Outside a plain sync context, let the base class bridge from the async
        # streaming implementation instead of consuming LiteLLM's sync stream.
        # That bridge still ends up in GeminiModel._stream_generate_impl(), so
        # Gemini is still streamed through LiteLLM via litellm.acompletion.
        if get_execution_context() is not AsyncContext.SYNC:
            yield from super().stream_generate(prompt, _conversation)
            return

        from wayflowcore.tracing.span import LlmGenerationSpan

        prompt = self._prepare_prompt_sync(prompt)
        self._check_supports_prompt(prompt)

        with LlmGenerationSpan(
            llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
        ) as span:
            logger.debug("LLM generating (stream): %s", prompt)
            stream = litellm.completion(**self._build_litellm_request(prompt, stream=True))

            yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT)

            # Wayflow streams text chunks incrementally, but still needs one final
            # Message on END_CHUNK. Gemini/LiteLLM can surface text, tool calls,
            # provider fields, and usage on different chunks, so we accumulate
            # them here and assemble the final Message at the end.
            stream_state = {
                "text": "",
                "tool_deltas": [],
                "message_extra_content": None,
                "token_usage": None,
            }
            try:
                for chunk in stream:
                    text_delta = self._ingest_litellm_stream_chunk(stream_state, chunk)
                    if text_delta:
                        yield StreamChunkType.TEXT_CHUNK, Message(
                            content=text_delta, message_type=MessageType.AGENT
                        )

                final_message = prompt.parse_output(
                    self._stream_state_to_wayflow_message(stream_state)
                )
                completion = LlmCompletion(
                    message=final_message,
                    token_usage=cast(Optional[TokenUsage], stream_state["token_usage"]),
                )
                self._update_token_usage(
                    conversation=_conversation, prompt=prompt, completion=completion
                )
                span.record_end_span_event(completion=completion)

                yield StreamChunkType.END_CHUNK, final_message
            finally:
                completion_stream = stream.completion_stream
                if completion_stream is not None:
                    completion_stream.response_iterator.close()
                    completion_stream.streaming_response.close()

    async def _generate_impl(self, prompt: Prompt) -> LlmCompletion:
        response = await litellm.acompletion(**self._build_litellm_request(prompt, stream=False))
        return self._completion_from_response(prompt, response)

    async def _stream_generate_impl(
        self, prompt: Prompt
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        stream = await litellm.acompletion(**self._build_litellm_request(prompt, stream=True))

        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None

        # Async streaming uses the same accumulation strategy as the sync path:
        # collect partial LiteLLM chunks until we can emit the final Message.
        stream_state = {
            "text": "",
            "tool_deltas": [],
            "message_extra_content": None,
            "token_usage": None,
        }
        try:
            async for chunk in stream:
                text_delta = self._ingest_litellm_stream_chunk(stream_state, chunk)
                if text_delta:
                    yield (
                        StreamChunkType.TEXT_CHUNK,
                        Message(content=text_delta, message_type=MessageType.AGENT),
                        None,
                    )

            final_message = prompt.parse_output(self._stream_state_to_wayflow_message(stream_state))
            yield (
                StreamChunkType.END_CHUNK,
                final_message,
                cast(Optional[TokenUsage], stream_state["token_usage"]),
            )
        finally:
            completion_stream = stream.completion_stream
            if completion_stream is not None:
                await completion_stream.async_response_iterator.aclose()
                await completion_stream.streaming_response.aclose()

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "model_type": "gemini",
            "model_id": self.model_id,
            "proxy": self.proxy,
            "supports_structured_generation": self.supports_structured_generation,
            "supports_tool_calling": self.supports_tool_calling,
            "auth": self._serialize_auth_config(self.auth),
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
        }

    def _prepare_prompt_sync(self, prompt: "Prompt | str") -> Prompt:
        if not isinstance(prompt, Prompt):
            from wayflowcore.templates import PromptTemplate

            prompt = PromptTemplate.from_string(prompt).format()
        if prompt.generation_config is None:
            prompt = prompt.copy(generation_config=self.generation_config)
        return prompt

    def _completion_from_response(self, prompt: Prompt, response: Any) -> LlmCompletion:
        response_dict = _litellm_object_to_dict(response)
        choices = response_dict.get("choices") or []
        if len(choices) > 1:
            raise NotImplementedError("Provider does not support multiple completions")
        choices[0]["message"] = _rename_message_and_tool_call_field(
            message_payload=choices[0]["message"],
            source_key="provider_specific_fields",
            target_key="extra_content",
        )
        message = prompt.parse_output(
            self._processor._convert_openai_response_into_message(response_dict)
        )
        return LlmCompletion(
            message=message,
            token_usage=self._litellm_usage_to_wayflow_token_usage(response),
        )

    def _serialize_auth_config(self, auth: GeminiApiKeyAuth | GeminiCloudAuth) -> Dict[str, Any]:
        if isinstance(auth, GeminiApiKeyAuth):
            if auth.api_key is not None:
                logger.warning(
                    "API key was configured on %s but it will not be serialized in the config",
                    self,
                )
            return {"type": "api_key"}

        auth_config = {
            "type": "cloud",
            "project_id": auth.project_id,
            "location": auth.location,
        }
        if auth.vertex_credentials is not None:
            logger.warning(
                "Vertex credentials were configured on %s but they will not be serialized in the config",
                self,
            )
        return auth_config

    def _build_litellm_request(self, prompt: Prompt, stream: bool) -> Dict[str, Any]:
        generation_kwargs = self._processor._convert_generation_params(prompt.generation_config)
        if "max_completion_tokens" in generation_kwargs:
            generation_kwargs["max_tokens"] = generation_kwargs.pop("max_completion_tokens")

        model_id = self.model_id
        if not model_id.startswith(("gemini/", "vertex_ai/")):
            model_id = (
                f"vertex_ai/{model_id}"
                if isinstance(self.auth, GeminiCloudAuth)
                else f"gemini/{model_id}"
            )

        request: Dict[str, Any] = {
            "model": model_id,
            "messages": [
                _rename_message_and_tool_call_field(
                    message_payload=converted_message,
                    source_key="extra_content",
                    target_key="provider_specific_fields",
                )
                for message in prompt.messages
                for converted_message in self._processor._convert_message_into_openai_message_dict(
                    message,
                    supports_tool_role=True,
                )
            ],
            "stream": stream,
            **generation_kwargs,
        }

        if prompt.tools is not None:
            request["tools"] = [tool.to_openai_format() for tool in prompt.tools]
        if prompt.response_format is not None:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": _prepare_openai_compatible_json_schema(prompt.response_format),
            }
        if self.proxy is not None:
            request["proxy"] = self.proxy

        if isinstance(self.auth, GeminiApiKeyAuth):
            api_key = self.auth.api_key or os.getenv("GEMINI_API_KEY")
            if api_key is not None:
                request["api_key"] = api_key
        else:
            if self.auth.project_id is not None:
                request["vertex_project"] = self.auth.project_id
            request["vertex_location"] = self.auth.location
            if self.auth.vertex_credentials is not None:
                request["vertex_credentials"] = self._load_vertex_credentials(
                    self.auth.vertex_credentials
                )

        return request

    @staticmethod
    def _ingest_litellm_stream_chunk(stream_state: Dict[str, Any], chunk: Any) -> str:
        # Fold one LiteLLM chunk into the running Wayflow stream state.
        # Gemini may emit text, tool calls, thought-signature metadata, and usage
        # on different chunks, while Wayflow expects a single final Message.
        normalized_chunk = _litellm_object_to_dict(chunk)
        choices = normalized_chunk.get("choices") or []
        if len(choices) > 1:
            raise NotImplementedError("Provider does not support multiple completions")
        choice = choices[0] if choices else {}
        delta = _rename_message_and_tool_call_field(
            message_payload=choice.get("delta") or {},
            source_key="provider_specific_fields",
            target_key="extra_content",
        )
        stream_state["tool_deltas"].extend(delta.get("tool_calls") or [])

        # Thought signatures can arrive on a later chunk, sometimes without text,
        # so keep the latest non-empty provider fields we see.
        message_extra_content = delta.get("extra_content")
        if message_extra_content:
            stream_state["message_extra_content"] = message_extra_content

        content = delta.get("content")
        text_delta = content if isinstance(content, str) else ""
        stream_state["text"] += text_delta

        token_usage = GeminiModel._litellm_usage_to_wayflow_token_usage(normalized_chunk)
        if token_usage is not None:
            stream_state["token_usage"] = token_usage

        return text_delta

    def _stream_state_to_wayflow_message(self, stream_state: Dict[str, Any]) -> Message:
        tool_requests: Optional[List["ToolRequest"]] = None
        if stream_state["tool_deltas"]:
            tool_requests = self._processor._convert_tool_deltas_into_tool_requests(
                stream_state["tool_deltas"]
            )
        return Message(
            content=stream_state["text"],
            tool_requests=tool_requests,
            message_type=MessageType.AGENT if tool_requests is None else MessageType.TOOL_REQUEST,
            _extra_content=stream_state["message_extra_content"],
        )

    @staticmethod
    def _litellm_usage_to_wayflow_token_usage(value: Any) -> Optional[TokenUsage]:
        usage = _litellm_object_to_dict(value)
        if isinstance(usage, dict) and "usage" in usage:
            usage = usage["usage"]
        if not isinstance(usage, dict):
            return None

        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = (
            int(prompt_details.get("cached_tokens") or 0) if isinstance(prompt_details, dict) else 0
        )

        completion_details = usage.get("completion_tokens_details") or {}
        reasoning_tokens = (
            int(completion_details.get("reasoning_tokens") or 0)
            if isinstance(completion_details, dict)
            else 0
        )

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            exact_count=True,
        )

    @staticmethod
    def _load_vertex_credentials(vertex_credentials: str | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(vertex_credentials, dict):
            return GeminiModel._normalize_vertex_credentials(vertex_credentials)
        if not isinstance(vertex_credentials, str):
            raise ValueError(
                "Expected vertex_credentials to be a dict, JSON string, or path to a JSON credentials file."
            )

        try:
            parsed_credentials = json.loads(vertex_credentials)
        except json.JSONDecodeError:
            parsed_credentials = None

        if isinstance(parsed_credentials, dict):
            return GeminiModel._normalize_vertex_credentials(parsed_credentials)
        if parsed_credentials is not None:
            raise ValueError("Expected vertex_credentials JSON to decode to an object.")

        try:
            with open(os.path.expanduser(vertex_credentials), "r") as file:
                file_credentials = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "Expected vertex_credentials to be a JSON string/object or a path to a JSON credentials file."
            ) from exc

        if not isinstance(file_credentials, dict):
            raise ValueError("Expected vertex_credentials file to contain a JSON object.")
        return GeminiModel._normalize_vertex_credentials(file_credentials)

    @staticmethod
    def _normalize_vertex_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
        normalized_credentials = dict(credentials)
        private_key = normalized_credentials.get("private_key")
        if isinstance(private_key, str):
            normalized_credentials["private_key"] = private_key.replace("\\n", "\n")
        return normalized_credentials
