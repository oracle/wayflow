# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore._metadata import MetadataType

from .llmgenerationconfig import LlmGenerationConfig
from .openaiapitype import OpenAIAPIType
from .openaicompatiblemodel import EMPTY_API_KEY, OpenAICompatibleModel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from wayflowcore.templates import PromptTemplate


class VllmModel(OpenAICompatibleModel):
    def __init__(
        self,
        model_id: str,
        host_port: str,
        proxy: Optional[str] = None,
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
        Model powered by a model hosted with VLLM server.

        Parameters
        ----------
        model_id:
            Name of the model to use
        host_port:
            Hostname and port of the vllm server where the model is hosted
        proxy:
            Proxy to use to connect to the remote LLM endpoint
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
            Uses Completions API if not specified.
            As of November 2025, Reponses support with VLLM is limited for certain models.
            Responses API has been tested on vLLM with OpenAI GPT-OSS.
        id:
            ID of the component.
        name:
            Name of the component.
        description:
            Description of the component.

        Examples
        --------
        >>> from wayflowcore.models import LlmModelFactory
        >>> VLLM_CONFIG = {
        ...     "model_type": "vllm",
        ...     "host_port": "<HOSTNAME>",
        ...     "model_id": "<MODEL_NAME>",
        ... }
        >>> llm = LlmModelFactory.from_config(VLLM_CONFIG)

        Notes
        -----
        Usually, VLLM models do not support tool calling. To enable this, we prepend and append some specific REACT
        prompts and format tools with the REACT prompting template when:

        * the model should use tools
        * the list of message contains some tool_requests or tool_results

        Be aware of that when you generate with tools or tool calls. To disable this behaviour, set `use_tools` to False
        and make sure the prompt doesn't contain tool_call and tool_result messages.
        See https://arxiv.org/abs/2210.03629 for learning more about the REACT prompting techniques.

        Notes
        -----
        When running under Oracle VPN, the connection to the OCIGenAI service requires to run the model without any proxy.
        Therefore, make sure not to have any of `http_proxy` or `HTTP_PROXY` environment variables setup, or unset them with `unset http_proxy HTTP_PROXY`
        """
        self.host_port = host_port
        super().__init__(
            base_url=host_port,
            model_id=model_id,
            proxy=proxy,
            api_key=EMPTY_API_KEY,
            generation_config=generation_config,
            supports_structured_generation=supports_structured_generation,
            supports_tool_calling=supports_tool_calling,
            api_type=api_type,
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "model_type": "vllm",
            "model_id": self.model_id,
            "host_port": self.host_port,
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
        }

    @property
    def default_chat_template(self) -> "PromptTemplate":
        from wayflowcore.templates import LLAMA_CHAT_TEMPLATE

        return LLAMA_CHAT_TEMPLATE

    @property
    def default_agent_template(self) -> "PromptTemplate":
        from wayflowcore.templates import LLAMA_AGENT_TEMPLATE, NATIVE_AGENT_TEMPLATE

        if "llama" in self.model_id.lower() and "3." in self.model_id:
            # llama3.x works better with custom template
            return LLAMA_AGENT_TEMPLATE
        return NATIVE_AGENT_TEMPLATE
