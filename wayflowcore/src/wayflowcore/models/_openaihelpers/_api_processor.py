# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, Dict, Optional

from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import Message
from wayflowcore.tokenusage import TokenUsage
from wayflowcore.tools import Tool

from .._requesthelpers import TaggedMessageChunkTypeWithTokenUsage
from ..llmgenerationconfig import LlmGenerationConfig
from ..llmmodel import Prompt
from ._utils import _build_request_url, _remove_optional_from_signature

if TYPE_CHECKING:
    from wayflowcore.models import OpenAIAPIType


logger = logging.getLogger(__name__)


class _APIProcessor(ABC):
    def __init__(self, model_id: str, base_url: str, api_type: "OpenAIAPIType"):
        self.base_url = base_url
        self.model_id = model_id
        self.api_type = api_type

    @abstractmethod
    def _extract_usage(self, response_data: Dict[str, Any]) -> Optional[TokenUsage]:
        """Extract Token Usage information from the response"""

    def _generate_request_params(self, prompt: "Prompt", stream: bool) -> Dict[str, Any]:
        """Generate Request Parameters for the API type"""
        url = _build_request_url(base_url=self.base_url, api_type=self.api_type)

        json_obj = {
            "model": self.model_id,
            "store": False,
            "stream": stream,
            **self._convert_prompt(prompt),
            **self._convert_generation_params(prompt.generation_config),
        }

        json_obj = self._generate_api_specific_request_params(json_obj, stream)

        return dict(
            url=url,
            json=json_obj,
        )

    def _get_prompt_cache_key_from_prompt(self, prompt: Prompt) -> str:

        prompt_cache_key: str = IdGenerator.get_or_generate_id()

        if prompt.messages[-1]._prompt_cache_key:
            # Use previous prompt cache key to increase likelihood of hitting prompt cache
            prompt_cache_key = prompt.messages[-1]._prompt_cache_key

        return prompt_cache_key

    def _generate_api_specific_request_params(
        self, json_obj: Dict[str, Any], stream: bool
    ) -> Dict[str, Any]:
        """Generate API Specific Request Parameters"""
        return json_obj

    @abstractmethod
    def _convert_openai_response_into_message(self, response: Any) -> "Message":
        """Convert OpenAI response to WayFlow Message"""

    async def _tagged_chunk_iterator_from_stream_of_openai_compatible_json(
        self,
        json_object_iterable: AsyncIterable[Any],
        post_processing: Optional[Callable[["Message"], "Message"]] = None,
    ) -> AsyncIterable[TaggedMessageChunkTypeWithTokenUsage]:
        """Iterator for streaming chunks"""
        if False:
            yield  # This makes this method recognized as an async generator for typing
        raise NotImplementedError()

    async def _json_iterator_from_stream_of_api_str(
        self,
        line_iterator: AsyncIterable[str],
    ) -> AsyncIterable[Dict[str, Any]]:
        "JSON Iterator for streaming responses"
        if False:
            yield  # This makes this method recognized as an async generator for typing
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def _tool_to_openai_function_dict(tool: Tool) -> Dict[str, Any]:
        """Function calling as defined in: https://platform.openai.com/docs/guides/function-calling"""

    @staticmethod
    def _get_tool_parameters(tool: Tool) -> Dict[str, Any]:
        if any(tool.parameters):
            return {
                "type": "object",
                "properties": {
                    t_name: _remove_optional_from_signature(t)
                    for t_name, t in tool.parameters.items()
                },
                "required": [
                    param_name
                    for param_name, param_info in tool.parameters.items()
                    if "default" not in param_info
                ],
            }
        else:
            return {}

    @abstractmethod
    def _convert_prompt(self, prompt: "Prompt") -> Dict[str, Any]:
        """Convert a prompt to OpenAI-Compatible Format"""

    @abstractmethod
    def _convert_generation_params(
        self, generation_config: Optional[LlmGenerationConfig]
    ) -> Dict[str, Any]:
        """Convert Generation parameters to OpenAI-Compatible Format"""
