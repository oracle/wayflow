# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
import os
from contextlib import aclosing
from typing import TYPE_CHECKING, Any, AsyncIterable, AsyncIterator, Dict, Optional

from wayflowcore._metadata import MetadataType

from ._openaihelpers import _APIProcessor, _ChatCompletionsAPIProcessor, _ResponsesAPIProcessor
from ._requesthelpers import (
    TaggedMessageChunkTypeWithTokenUsage,
    _RetryStrategy,
    request_post_with_retries,
    request_streaming_post_with_retries,
)
from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import LlmCompletion, LlmModel, Prompt
from .openaiapitype import OpenAIAPIType

if TYPE_CHECKING:
    from wayflowcore.messagelist import Message


logger = logging.getLogger(__name__)

EMPTY_API_KEY = "<[EMPTY#KEY]>"
OPEN_API_KEY = "OPENAI_API_KEY"

_openai_api_type_to_processor_map = {
    OpenAIAPIType.CHAT_COMPLETIONS: _ChatCompletionsAPIProcessor,
    OpenAIAPIType.RESPONSES: _ResponsesAPIProcessor,
}


class OpenAICompatibleModel(LlmModel):
    def __init__(
        self,
        model_id: str,
        base_url: str,
        proxy: Optional[str] = None,
        api_key: Optional[str] = None,
        generation_config: Optional[LlmGenerationConfig] = None,
        supports_structured_generation: Optional[bool] = True,
        supports_tool_calling: Optional[bool] = True,
        api_type: OpenAIAPIType = OpenAIAPIType.CHAT_COMPLETIONS,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Model to use remote LLM endpoints that use OpenAI-compatible chat APIs.

        Parameters
        ----------
        model_id:
            Name of the model to use
        base_url:
            Hostname and port of the vllm server where the model is hosted. If you specify a url
            ending with `/completions` or `/responses` it will be used as-is, otherwise the url path
            `v1/chat/completions` or `v1/responses` will be appended to the base url depending on the API
            type specified.
        proxy:
            Proxy to use to connect to the remote LLM endpoint
        api_key:
            API key to use for the request if needed. It will be formatted in the OpenAI format.
            (as "Bearer API_KEY" in the request header)
            If not provided, will attempt to read from the environment variable OPENAI_API_KEY
        generation_config:
            default parameters for text generation with this model
        supports_structured_generation:
            Whether the model supports structured generation or not. When set to `None`,
            the model will be prompted with a response format and it will check it can use
            structured generation.
        supports_tool_calling:
            Whether the model supports tool calling or not. When set to `None`,
            the model will be prompted with a tool and it will check it can use
            the tool.
        api_type:
            OpenAI API type to use. Currently supports Responses and Chat Completions API.
            Uses Chat Completions API if not specified
        id:
            ID of the component.
        name:
            Name of the component.
        description:
            Description of the component.

        Examples
        --------
        >>> from wayflowcore.models import OpenAICompatibleModel
        >>> llm = OpenAICompatibleModel(
        ...     model_id="<MODEL_NAME>",
        ...     base_url="<ENDPOINT_URL>",
        ...     api_key="<API_KEY_FOR_REMOTE_ENDPOINT>",
        ... )

        """
        self.base_url = base_url
        self.proxy = proxy
        self.api_key = _resolve_api_key(api_key)
        self.api_type = api_type

        self._retry_strategy = _RetryStrategy()
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

        self._setup_api_processor(api_type)

    async def _generate_impl(
        self,
        prompt: "Prompt",
    ) -> LlmCompletion:
        prompt = self._pre_process(prompt)
        request_params = self.api_processor._generate_request_params(prompt, stream=False)
        request_params["headers"] = self._get_headers()
        response_data = await self._post(
            request_params=request_params, retry_strategy=self._retry_strategy, proxy=self.proxy
        )
        logger.debug(f"Raw LLM answer: %s", response_data)
        message = self.api_processor._convert_openai_response_into_message(response_data)
        message = self._post_process(message)
        message = prompt.parse_output(message)
        return LlmCompletion(
            message=message, token_usage=self.api_processor._extract_usage(response_data)
        )

    async def _stream_generate_impl(
        self, prompt: "Prompt"
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        prompt = self._pre_process(prompt)
        request_args = self.api_processor._generate_request_params(prompt, stream=True)
        request_args["headers"] = self._get_headers()

        def final_message_post_processing(message: "Message") -> "Message":
            return prompt.parse_output(self._post_process(message))

        json_stream = self._post_stream(
            request_args,
            retry_strategy=self._retry_strategy,
            proxy=self.proxy,
            api_processor=self.api_processor,
        )

        async for (
            chunk
        ) in self.api_processor._tagged_chunk_iterator_from_stream_of_openai_compatible_json(
            json_object_iterable=json_stream,
            post_processing=final_message_post_processing,
        ):
            yield chunk

    def _pre_process(self, prompt: "Prompt") -> "Prompt":
        return prompt

    def _post_process(self, message: "Message") -> "Message":
        return message

    def _get_headers(self) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key is not None:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _setup_api_processor(self, api_type: OpenAIAPIType) -> None:

        self.api_processor: _APIProcessor
        model_cls = _openai_api_type_to_processor_map[api_type]
        self.api_processor = model_cls(self.model_id, self.base_url, api_type)

    @staticmethod
    async def _post(
        request_params: Dict[str, Any], retry_strategy: _RetryStrategy, proxy: Optional[str]
    ) -> Dict[str, Any]:
        logger.debug(f"Request to remote endpoint: {request_params}")
        response = await request_post_with_retries(request_params, retry_strategy, proxy)
        logger.debug(f"Raw remote endpoint response: {response}")
        return response

    @staticmethod
    async def _post_stream(
        request_params: Dict[str, Any],
        retry_strategy: _RetryStrategy,
        proxy: Optional[str],
        api_processor: _APIProcessor,
    ) -> AsyncIterator[Dict[str, Any]]:
        logger.debug(f"Streaming request to remote endpoint: {request_params}")
        line_iterator = request_streaming_post_with_retries(
            request_params, retry_strategy=retry_strategy, proxy=proxy
        )
        # ensure the generator is closed at the end
        async with aclosing(line_iterator):
            async for chunk in api_processor._json_iterator_from_stream_of_api_str(line_iterator):
                yield chunk

    @property
    def config(self) -> Dict[str, Any]:
        if self.api_key is not None:
            logger.warning(
                f"API was configured on {self} but it will not be serialized in the config"
            )
        return {
            "model_type": "openaicompatible",
            "model_id": self.model_id,
            "base_url": self.base_url,
            "proxy": self.proxy,
            "supports_structured_generation": self.supports_structured_generation,
            "supports_tool_calling": self.supports_tool_calling,
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
        }

    def _generate_request_params(self, prompt: "Prompt", stream: bool) -> Dict[str, Any]:
        """Generate Request Parameters for the API type"""
        return self.api_processor._generate_request_params(prompt, stream=stream)


def _resolve_api_key(provided_api_key: Optional[str]) -> Optional[str]:
    env_api_key = os.getenv(OPEN_API_KEY)
    if provided_api_key == EMPTY_API_KEY:
        # Placeholder provided: use env var if available; otherwise None. No warning.
        api_key = env_api_key or None
    elif provided_api_key:
        # Explicit api_key provided: prioritize it (do nothing).
        api_key = provided_api_key
    else:
        # api_key not provided: fall back to env var, warn if still missing.
        api_key = env_api_key or None
        if not api_key:
            logger.warning(
                "No api_key provided. It might be OK if it is not necessary to access the model. If however the access requires it, either specify the api_key parameter, or set the OPENAI_API_KEY environment variable."
            )
    return api_key
