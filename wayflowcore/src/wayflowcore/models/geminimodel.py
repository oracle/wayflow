# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import logging
import os

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, List, Optional

import litellm
from litellm.types.utils import (
    ChatCompletionDeltaToolCall,
    ChatCompletionMessageToolCall,
    CompletionTokensDetailsWrapper,
)
from litellm.types.utils import Message as LiteLLMMessage
from litellm.types.utils import (
    ModelResponse,
    ModelResponseStream,
    PromptTokensDetailsWrapper,
    Usage,
)
from pydantic import BaseModel

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.formatting import stringify
from wayflowcore.conversation import Conversation
from wayflowcore.idgeneration import IdGenerator
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

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message

logger = logging.getLogger(__name__)

GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
GEMINI_AI_STUDIO_MODEL_PREFIX = "gemini/"
GEMINI_VERTEX_AI_MODEL_PREFIX = "vertex_ai/"

LiteLLMToolCallType = ChatCompletionDeltaToolCall | ChatCompletionMessageToolCall


def _provider_specific_fields_from_litellm_object(
    obj: Any,
) -> Optional[Dict[str, Any]]:
    """Return a copy of LiteLLM provider-specific fields when present."""
    provider_specific_fields = getattr(obj, "provider_specific_fields", None)
    if isinstance(provider_specific_fields, dict):
        return dict(provider_specific_fields)
    return None


def _tool_call_extra_content_from_litellm_object(
    tool_call: LiteLLMToolCallType,
) -> Optional[Dict[str, Any]]:
    """Return Gemini tool-call metadata from either the tool call or its nested function."""
    provider_specific_fields = _provider_specific_fields_from_litellm_object(tool_call)
    if provider_specific_fields is not None:
        return provider_specific_fields

    return _provider_specific_fields_from_litellm_object(getattr(tool_call, "function", None))


def _convert_litellm_tool_calls_to_tool_requests(
    tool_calls: Iterable[LiteLLMToolCallType],
) -> List[ToolRequest]:
    """Convert LiteLLM Gemini tool calls into WayFlow ToolRequests.

    GeminiModel is Gemini-only and expects LiteLLM to return OpenAI-style tool-call objects.
    This function intentionally raises if the shape is unexpected.
    """

    tool_requests: List[ToolRequest] = []
    for tc in tool_calls:
        if not isinstance(tc, (ChatCompletionDeltaToolCall, ChatCompletionMessageToolCall)):
            raise TypeError(
                f"Unexpected tool call type {type(tc).__name__}; "
                "expected ChatCompletionDeltaToolCall or ChatCompletionMessageToolCall."
            )

        if not isinstance(tc.id, str) or not tc.id:
            raise ValueError(f"Invalid tool call id: {tc.id!r}")
        if tc.type not in (None, "function"):
            raise ValueError(f"Unsupported tool call type: {tc.type!r}")

        name = tc.function.name
        arguments = tc.function.arguments

        if not isinstance(name, str) or not name:
            raise ValueError(f"Invalid tool call name: {name!r}")
        if not isinstance(arguments, str) or not arguments:
            raise ValueError(f"Invalid tool call arguments: {arguments!r}")

        tool_requests.append(
            ToolRequest(
                name=name,
                args=_safe_json_loads(arguments),
                tool_request_id=tc.id,
                _extra_content=_tool_call_extra_content_from_litellm_object(tc),
            )
        )

    return tool_requests


def _convert_litellm_tool_deltas_to_tool_requests(
    tool_deltas: Iterable[ChatCompletionDeltaToolCall],
) -> List[ToolRequest]:
    """Reconstruct complete tool calls from streamed LiteLLM tool-call deltas."""
    tool_requests_dict: Dict[int, Dict[str, Any]] = {}
    next_index = 0

    for delta in tool_deltas:
        if not isinstance(delta, ChatCompletionDeltaToolCall):
            raise TypeError(
                f"Unexpected tool call type {type(delta).__name__}; expected "
                "ChatCompletionDeltaToolCall."
            )

        index = delta.index if isinstance(delta.index, int) else None
        if index is None:
            function = delta.function
            if function.name and function.arguments:
                index = next_index
                next_index += 1
            else:
                raise ValueError(f"Invalid streamed tool call delta without index: {delta!r}")

        if index not in tool_requests_dict:
            tool_requests_dict[index] = {
                "name": "",
                "args": "",
                "tool_request_id": delta.id or IdGenerator.get_or_generate_id(),
                "_extra_content": None,
            }

        current_tool_request = tool_requests_dict[index]
        if delta.id:
            current_tool_request["tool_request_id"] = delta.id
        if delta.function.name:
            current_tool_request["name"] += delta.function.name
        if delta.function.arguments:
            current_tool_request["args"] += delta.function.arguments

        extra_content = _tool_call_extra_content_from_litellm_object(delta)
        if extra_content is not None:
            current_tool_request["_extra_content"] = extra_content

    return [
        ToolRequest(
            name=tool_request["name"],
            args=_safe_json_loads(tool_request["args"]),
            tool_request_id=tool_request["tool_request_id"],
            _extra_content=tool_request["_extra_content"],
        )
        for tool_request in tool_requests_dict.values()
    ]


@dataclass
class _LiteLLMStreamAccumulator:
    accumulated_text: str = ""
    tool_calls: List[ChatCompletionDeltaToolCall] = field(default_factory=list)
    token_usage: Optional[TokenUsage] = None

    def ingest_chunk(self, model: "GeminiModel", chunk: Any) -> str:
        if not isinstance(chunk, ModelResponseStream):
            raise TypeError(
                f"Unexpected streaming chunk type {type(chunk).__name__}; expected "
                "ModelResponseStream."
            )

        delta = chunk.choices[0].delta
        if delta is None:
            return ""

        tool_calls = delta.tool_calls
        if tool_calls:
            for tc in tool_calls:
                if not isinstance(tc, ChatCompletionDeltaToolCall):
                    raise TypeError(
                        f"Unexpected tool call type {type(tc).__name__}; expected "
                        "ChatCompletionDeltaToolCall."
                    )
            self.tool_calls.extend(tool_calls)

        text_delta = delta.content or ""
        if text_delta:
            self.accumulated_text += text_delta

        self.token_usage = self.token_usage or model._litellm_usage_to_token_usage(chunk)
        return text_delta

    def build_final_message(self) -> Message:
        if self.tool_calls:
            return Message(
                content=self.accumulated_text,
                tool_requests=_convert_litellm_tool_deltas_to_tool_requests(self.tool_calls),
            )
        return Message(content=self.accumulated_text, message_type=MessageType.AGENT)


class GeminiApiKeyAuth(BaseModel):
    """Authentication settings for Gemini through Google AI Studio."""

    api_key: Optional[str] = None
    """API key to use. If None, will try to load it from the env variable GEMINI_API_KEY"""


class GeminiCloudAuth(BaseModel):
    """Authentication settings for Gemini through Google Vertex AI."""

    project_id: Optional[str] = None
    """Optional Google Cloud project identifier.

    This may still need to be set explicitly when LiteLLM/Google auth cannot
    infer the project from Application Default Credentials (ADC) or other local
    Google Cloud configuration.
    """
    location: str = "global"
    """Vertex AI region/location."""
    vertex_credentials: str | Dict[str, Any] | None = None
    """Optional JSON string/object or path to a file containing Google Cloud credentials.

    When unset, LiteLLM/Google auth may rely on Application Default Credentials (ADC), such as
    ``GOOGLE_APPLICATION_CREDENTIALS``, credentials configured via
    ``gcloud auth application-default login``, or an attached service account.
    Even then, ``project_id`` may still need to be provided separately if it
    cannot be resolved from the environment.
    """


def get_litellm_gemini_model_id(model_id: str, auth: GeminiApiKeyAuth | GeminiCloudAuth) -> str:
    """Return the LiteLLM Gemini model identifier inferred from the auth mode when needed."""
    if model_id.startswith((GEMINI_AI_STUDIO_MODEL_PREFIX, GEMINI_VERTEX_AI_MODEL_PREFIX)):
        return model_id
    provider_prefix = (
        GEMINI_VERTEX_AI_MODEL_PREFIX
        if isinstance(auth, GeminiCloudAuth)
        else GEMINI_AI_STUDIO_MODEL_PREFIX
    )
    return f"{provider_prefix}{model_id}"


class GeminiModel(LlmModel):
    """Run Gemini models through LiteLLM using Google AI Studio or Vertex AI auth."""

    def __init__(
        self,
        model_id: str,
        auth: GeminiApiKeyAuth | GeminiCloudAuth,
        # networking
        proxy: str | None = None,
        # defaults
        generation_config: "LlmGenerationConfig | None" = None,
        supports_structured_generation: Optional[bool] = True,
        supports_tool_calling: Optional[bool] = True,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Generic model to connect to Gemini via Google AI Studio or Vertex AI.
        Implementation note: use litellm.completion and litellm.acompletion as the way to
        actually make the API calls.

        Parameters
        ----------
        model_id:
            Gemini model name as exposed by the selected service (for example
            ``gemini-2.5-pro``). Use the name listed by Google AI Studio when
            authenticating with ``GeminiApiKeyAuth``, and the name listed by
            Vertex AI when authenticating with ``GeminiCloudAuth``.
        auth:
            Required authentication configuration. Use ``GeminiApiKeyAuth()`` to let
            AI Studio load ``GEMINI_API_KEY`` from the environment, or
            ``GeminiCloudAuth(...)`` for Vertex AI. For Vertex AI, explicit credentials
            are optional when Application Default Credentials are already configured,
            but ``project_id`` may still need to be supplied explicitly if ADC does
            not include a default project.
        proxy:
            Optional proxy URL if required.
        ...
        """
        self.auth: GeminiApiKeyAuth | GeminiCloudAuth = auth
        self.proxy = proxy

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

        with LlmGenerationSpan(
            llm=self, prompt=prompt, name=f"LlmGeneration[{self._get_display_name()}]"
        ) as span:
            logger.debug("LLM generating (stream): %s", prompt)
            request = self._build_litellm_request(prompt, stream=True)
            stream = litellm.completion(**request)

            yield StreamChunkType.START_CHUNK, Message(content="", message_type=MessageType.AGENT)

            accumulator = _LiteLLMStreamAccumulator()
            for chunk in stream:
                text_delta = accumulator.ingest_chunk(self, chunk)
                if text_delta:
                    yield StreamChunkType.TEXT_CHUNK, Message(
                        content=text_delta, message_type=MessageType.AGENT
                    )

            final_message = prompt.parse_output(accumulator.build_final_message())
            completion = LlmCompletion(message=final_message, token_usage=accumulator.token_usage)
            self._update_token_usage(
                conversation=_conversation, prompt=prompt, completion=completion
            )
            span.record_end_span_event(completion=completion)

            yield StreamChunkType.END_CHUNK, final_message

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

        accumulator = _LiteLLMStreamAccumulator()
        async for chunk in stream:
            delta_text = accumulator.ingest_chunk(self, chunk)
            if delta_text:
                yield (
                    StreamChunkType.TEXT_CHUNK,
                    Message(content=delta_text, message_type=MessageType.AGENT),
                    None,
                )

        final_message = prompt.parse_output(accumulator.build_final_message())
        yield StreamChunkType.END_CHUNK, final_message, accumulator.token_usage

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
        }

    def _serialize_auth_config(self, auth: GeminiApiKeyAuth | GeminiCloudAuth) -> Dict[str, Any]:
        if isinstance(auth, GeminiApiKeyAuth):
            if auth.api_key is not None:
                logger.warning(
                    "API key was configured on %s but it will not be serialized in the config",
                    self,
                )
            return {"type": "api_key"}
        if isinstance(auth, GeminiCloudAuth):
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
        return {"type": "unknown"}

    def _build_litellm_request(self, prompt: Prompt, stream: bool) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": get_litellm_gemini_model_id(self.model_id, self.auth),
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
                vertex_credentials = self.auth.vertex_credentials
                if isinstance(vertex_credentials, dict):
                    request["vertex_credentials"] = self._normalize_vertex_credentials(
                        vertex_credentials
                    )
                elif os.path.exists(vertex_credentials):
                    with open(vertex_credentials, "r") as f:
                        request["vertex_credentials"] = self._normalize_vertex_credentials(
                            json.load(f)
                        )
                else:
                    try:
                        request["vertex_credentials"] = self._normalize_vertex_credentials(
                            json.loads(vertex_credentials)
                        )
                    except json.JSONDecodeError:
                        raise ValueError(
                            f"Expected vertex_credentials to be a JSON string or a path to the Vertex AI credentials but got type {type(self.auth.vertex_credentials)} instead"
                        )
            if self.auth.project_id is not None:
                request["vertex_project"] = self.auth.project_id
            request["vertex_location"] = self.auth.location

        return request

    @staticmethod
    def _normalize_vertex_credentials(credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize inline Vertex credentials before sending them to LiteLLM."""
        normalized_credentials = dict(credentials)
        private_key = normalized_credentials.get("private_key")
        if isinstance(private_key, str):
            normalized_credentials["private_key"] = private_key.replace("\\n", "\n")
        return normalized_credentials

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
        return [
            converted_message
            for message in prompt.messages
            for converted_message in self._message_to_litellm_message_dicts(message)
        ]

    def _message_to_litellm_message_dicts(self, message: Message) -> List[Dict[str, Any]]:
        if message.tool_requests:
            if any(not isinstance(content, TextContent) for content in message.contents):
                raise ValueError(
                    "Invalid tool request. A tool request message should only contain text contents"
                )

            converted_message: Dict[str, Any] = {
                "role": "assistant",
                "tool_calls": [
                    self._tool_request_to_litellm_tool_call_dict(tool_request)
                    for tool_request in message.tool_requests
                ],
            }
            if message.content:
                converted_message["content"] = message.content
            return [converted_message]

        if message.tool_result:
            if len(message.contents):
                raise ValueError(
                    "Invalid tool result. Tool results should not contain any message content"
                )

            return [
                {
                    "role": "tool",
                    "tool_call_id": message.tool_result.tool_request_id,
                    "content": stringify(message.tool_result.content),
                }
            ]

        converted_message = {
            "role": message.role,
            "content": self._message_contents_to_litellm_content(message),
        }
        if isinstance(message._extra_content, dict) and message._extra_content:
            converted_message["provider_specific_fields"] = dict(message._extra_content)
        return [converted_message]

    def _message_contents_to_litellm_content(self, message: Message) -> List[Dict[str, Any]] | str:
        contents: List[Dict[str, Any]] = []
        for content in message.contents:
            if isinstance(content, TextContent):
                contents.append({"type": "text", "text": content.content})
            elif isinstance(content, ImageContent):
                contents.append({"type": "image_url", "image_url": {"url": content.base64_content}})
            else:
                raise RuntimeError(f"Unsupported content type: {content.__class__.__name__}")
        return contents if contents else ""

    def _tool_request_to_litellm_tool_call_dict(self, tool_request: ToolRequest) -> Dict[str, Any]:
        function_dict: Dict[str, Any] = {
            "name": tool_request.name,
            "arguments": json.dumps(tool_request.args),
        }
        tool_call_dict: Dict[str, Any] = {
            "id": tool_request.tool_request_id,
            "type": "function",
            "function": function_dict,
        }

        if isinstance(tool_request._extra_content, dict) and tool_request._extra_content:
            tool_call_dict["provider_specific_fields"] = dict(tool_request._extra_content)

        return tool_call_dict

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

        msg_raw = choice0.message
        if not isinstance(msg_raw, LiteLLMMessage):
            raise TypeError(
                "GeminiModel expected a LiteLLM Message in non-streaming responses, got "
                f"{type(msg_raw).__name__}"
            )
        msg = msg_raw

        tool_calls = msg.tool_calls

        if tool_calls:
            tool_requests = _convert_litellm_tool_calls_to_tool_requests(tool_calls)
            if not tool_requests:
                raise ValueError("GeminiModel got tool calls but could not parse any tool requests")
            return Message(tool_requests=tool_requests)

        extra_content = _provider_specific_fields_from_litellm_object(msg)
        content = msg.content or ""
        return Message(role="assistant", content=content, _extra_content=extra_content)

    def _litellm_usage_to_token_usage(self, response: Any) -> Optional[TokenUsage]:
        usage_raw: Any
        if isinstance(response, dict):
            usage_raw = response.get("usage")
        else:
            # LiteLLM's `ModelResponse` / `ModelResponseStream` are pydantic models where
            # `usage` is not always present (especially in streaming chunks).
            if not hasattr(response, "usage"):
                return None
            usage_raw = response.usage

        if usage_raw is None:
            return None

        if isinstance(usage_raw, Usage):
            usage = usage_raw
        elif isinstance(usage_raw, dict):
            usage = Usage(**usage_raw)
        else:
            raise TypeError(
                "GeminiModel expected LiteLLM usage to be a Usage or dict, got "
                f"{type(usage_raw).__name__}"
            )

        cached_tokens = 0
        prompt_details_raw = usage.prompt_tokens_details
        if prompt_details_raw is not None:
            if isinstance(prompt_details_raw, PromptTokensDetailsWrapper):
                cached_raw = prompt_details_raw.cached_tokens
            elif isinstance(prompt_details_raw, dict):
                cached_raw = prompt_details_raw.get("cached_tokens")
            else:
                raise TypeError(
                    "GeminiModel expected prompt_tokens_details to be a PromptTokensDetailsWrapper "
                    f"or dict, got {type(prompt_details_raw).__name__}"
                )
            if isinstance(cached_raw, int):
                cached_tokens = cached_raw

        reasoning_tokens = 0
        completion_details_raw = usage.completion_tokens_details
        if completion_details_raw is not None:
            if isinstance(completion_details_raw, CompletionTokensDetailsWrapper):
                reasoning_raw = completion_details_raw.reasoning_tokens
            elif isinstance(completion_details_raw, dict):
                reasoning_raw = completion_details_raw.get("reasoning_tokens")
            else:
                raise TypeError(
                    "GeminiModel expected completion_tokens_details to be a "
                    "CompletionTokensDetailsWrapper or dict, got "
                    f"{type(completion_details_raw).__name__}"
                )
            if isinstance(reasoning_raw, int):
                reasoning_tokens = reasoning_raw

        input_tokens = int(usage.prompt_tokens or 0)
        output_tokens = int(usage.completion_tokens or 0)
        total_tokens = int(usage.total_tokens or (input_tokens + output_tokens))

        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            exact_count=True,
        )
