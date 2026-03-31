# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import os
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, List, Optional

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from pydantic import BaseModel

from wayflowcore._metadata import MetadataType
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
    from wayflowcore.conversation import Conversation
    from wayflowcore.tools import ToolRequest


logger = logging.getLogger(__name__)

GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
GEMINI_AI_STUDIO_MODEL_PREFIX = "gemini/"
GEMINI_VERTEX_AI_MODEL_PREFIX = "vertex_ai/"

_STREAM_PROCESSOR = _ChatCompletionsAPIProcessor(
    model_id="gemini",
    base_url="",
    api_type=OpenAIAPIType.CHAT_COMPLETIONS,
)


class GeminiApiKeyAuth(BaseModel):
    api_key: Optional[str] = None


class GeminiCloudAuth(BaseModel):
    project_id: Optional[str] = None
    location: str = "global"
    vertex_credentials: str | Dict[str, Any] | None = None


def get_litellm_gemini_model_id(model_id: str, auth: GeminiApiKeyAuth | GeminiCloudAuth) -> str:
    if model_id.startswith((GEMINI_AI_STUDIO_MODEL_PREFIX, GEMINI_VERTEX_AI_MODEL_PREFIX)):
        return model_id
    if isinstance(auth, GeminiCloudAuth):
        return f"{GEMINI_VERTEX_AI_MODEL_PREFIX}{model_id}"
    return f"{GEMINI_AI_STUDIO_MODEL_PREFIX}{model_id}"


class _GeminiLiteLLMAdapter:
    """Translate between WayFlow's internal message shape and LiteLLM Gemini payloads."""

    def __init__(self, processor: _ChatCompletionsAPIProcessor) -> None:
        self._processor = processor

    @staticmethod
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

    @classmethod
    def _rename_key_recursively(cls, value: Any, source_key: str, target_key: str) -> Any:
        if isinstance(value, dict):
            renamed: Dict[str, Any] = {}
            for key, item in value.items():
                renamed[target_key if key == source_key else key] = cls._rename_key_recursively(
                    item,
                    source_key,
                    target_key,
                )
            return renamed
        if isinstance(value, list):
            return [cls._rename_key_recursively(item, source_key, target_key) for item in value]
        return value

    @classmethod
    def wayflow_payload_to_litellm(cls, value: Any) -> Any:
        return cls._rename_key_recursively(value, "extra_content", "provider_specific_fields")

    @classmethod
    def litellm_payload_to_wayflow(cls, value: Any) -> Any:
        normalized = cls._rename_key_recursively(
            value,
            "provider_specific_fields",
            "extra_content",
        )
        if isinstance(normalized, dict):
            function_payload = normalized.get("function")
            if (
                isinstance(function_payload, dict)
                and "extra_content" in function_payload
                and "extra_content" not in normalized
            ):
                normalized["extra_content"] = function_payload.pop("extra_content")
        return normalized

    def generation_config_to_litellm_kwargs(
        self, generation_config: Optional[LlmGenerationConfig]
    ) -> Dict[str, Any]:
        generation_kwargs = self._processor._convert_generation_params(generation_config)
        if "max_completion_tokens" in generation_kwargs:
            generation_kwargs["max_tokens"] = generation_kwargs.pop("max_completion_tokens")
        return generation_kwargs

    def wayflow_prompt_to_litellm_messages(self, prompt: Prompt) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        for message in prompt.messages:
            converted_messages = self._processor._convert_message_into_openai_message_dict(
                message,
                supports_tool_role=True,
            )
            for converted_message in converted_messages:
                normalized_message = self.wayflow_payload_to_litellm(converted_message)
                if (
                    isinstance(message._extra_content, dict)
                    and message._extra_content
                    and "tool_calls" not in normalized_message
                    and "tool_call_id" not in normalized_message
                ):
                    normalized_message["provider_specific_fields"] = dict(message._extra_content)
                messages.append(normalized_message)
        return messages

    def litellm_response_to_wayflow_message(self, response: Any) -> Message:
        normalized_response = self.litellm_payload_to_wayflow(
            self._litellm_object_to_dict(response)
        )
        return self._processor._convert_openai_response_into_message(normalized_response)

    def litellm_usage_to_wayflow_token_usage(self, value: Any) -> Optional[TokenUsage]:
        usage = self._litellm_object_to_dict(value)
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
    def new_stream_state() -> Dict[str, Any]:
        return {
            "text": "",
            "tool_deltas": [],
            "token_usage": None,
        }

    def ingest_litellm_stream_chunk(self, stream_state: Dict[str, Any], chunk: Any) -> str:
        normalized_chunk = self.litellm_payload_to_wayflow(self._litellm_object_to_dict(chunk))

        text_delta = ""
        for choice in normalized_chunk.get("choices") or []:
            if not isinstance(choice, dict):
                continue

            delta = choice.get("delta") or {}
            if not isinstance(delta, dict):
                continue

            tool_calls = delta.get("tool_calls") or []
            if isinstance(tool_calls, list):
                stream_state["tool_deltas"].extend(
                    tool_call for tool_call in tool_calls if isinstance(tool_call, dict)
                )

            content = delta.get("content")
            if isinstance(content, str):
                text_delta += content

        stream_state["text"] += text_delta

        token_usage = self.litellm_usage_to_wayflow_token_usage(normalized_chunk)
        if token_usage is not None:
            stream_state["token_usage"] = token_usage

        return text_delta

    def stream_state_to_wayflow_message(self, stream_state: Dict[str, Any]) -> Message:
        tool_requests: Optional[List["ToolRequest"]] = None
        if stream_state["tool_deltas"]:
            tool_requests = _STREAM_PROCESSOR._convert_tool_deltas_into_tool_requests(
                stream_state["tool_deltas"]
            )
        return Message(
            content=stream_state["text"],
            tool_requests=tool_requests,
            message_type=MessageType.AGENT if tool_requests is None else MessageType.TOOL_REQUEST,
        )


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
        self._litellm_adapter = _GeminiLiteLLMAdapter(self._processor)
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
        from wayflowcore.tracing.span import LlmGenerationSpan

        prompt = self._prepare_prompt_sync(prompt)
        self._check_supports_prompt(prompt)

        with LlmGenerationSpan(
            llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
        ) as span:
            logger.debug("LLM generating (stream): %s", prompt)
            stream = litellm.completion(**self._build_litellm_request(prompt, stream=True))

            yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT)

            stream_state = self._litellm_adapter.new_stream_state()
            for chunk in stream:
                text_delta = self._litellm_adapter.ingest_litellm_stream_chunk(stream_state, chunk)
                if text_delta:
                    yield StreamChunkType.TEXT_CHUNK, Message(
                        content=text_delta, message_type=MessageType.AGENT
                    )

            final_message = prompt.parse_output(
                self._litellm_adapter.stream_state_to_wayflow_message(stream_state)
            )
            completion = LlmCompletion(
                message=final_message,
                token_usage=stream_state["token_usage"],
            )
            self._update_token_usage(
                conversation=_conversation, prompt=prompt, completion=completion
            )
            span.record_end_span_event(completion=completion)

            yield StreamChunkType.END_CHUNK, final_message

    async def _generate_impl(self, prompt: Prompt) -> LlmCompletion:
        response = await litellm.acompletion(**self._build_litellm_request(prompt, stream=False))
        return self._completion_from_response(prompt, response)

    async def _stream_generate_impl(
        self, prompt: Prompt
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        stream = await litellm.acompletion(**self._build_litellm_request(prompt, stream=True))

        yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT), None

        stream_state = self._litellm_adapter.new_stream_state()
        async for chunk in stream:
            text_delta = self._litellm_adapter.ingest_litellm_stream_chunk(stream_state, chunk)
            if text_delta:
                yield (
                    StreamChunkType.TEXT_CHUNK,
                    Message(content=text_delta, message_type=MessageType.AGENT),
                    None,
                )

        final_message = prompt.parse_output(
            self._litellm_adapter.stream_state_to_wayflow_message(stream_state)
        )
        yield StreamChunkType.END_CHUNK, final_message, stream_state["token_usage"]

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
        message = prompt.parse_output(
            self._litellm_adapter.litellm_response_to_wayflow_message(response)
        )
        return LlmCompletion(
            message=message,
            token_usage=self._litellm_adapter.litellm_usage_to_wayflow_token_usage(response),
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
        request: Dict[str, Any] = {
            "model": get_litellm_gemini_model_id(self.model_id, self.auth),
            "messages": self._litellm_adapter.wayflow_prompt_to_litellm_messages(prompt),
            "stream": stream,
            **self._litellm_adapter.generation_config_to_litellm_kwargs(prompt.generation_config),
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
            api_key = self.auth.api_key or os.getenv(GEMINI_API_KEY_ENV_VAR)
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
