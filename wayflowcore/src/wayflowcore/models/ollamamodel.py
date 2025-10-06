# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.messagelist import Message, MessageType, TextContent

from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import Prompt
from .openaicompatiblemodel import OpenAICompatibleModel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from wayflowcore.templates import PromptTemplate


def _filter_ollama_header_tokens(content: str) -> str:
    # TODO: Investigate Langchain/Ollama header token issues when using Llama models
    return content.replace("<|start_header_id|>assistant<|end_header_id|>", "")


DEFAULT_OLLAMA_HOST_PORT = "localhost:11434"


class OllamaModel(OpenAICompatibleModel):
    def __init__(
        self,
        model_id: str,
        host_port: str = DEFAULT_OLLAMA_HOST_PORT,
        proxy: Optional[str] = None,
        generation_config: Optional[LlmGenerationConfig] = None,
        supports_structured_generation: Optional[bool] = True,
        supports_tool_calling: Optional[bool] = True,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Model powered by a locally hosted Ollama server.

        Parameters
        ----------
        model_id:
            Name of the model to use. List of model names can be found here:
            https://ollama.com/search
        host_port:
            Hostname and port of the vllm server where the model is hosted.
            By default Ollama binds port 11434.
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
        id:
            ID of the component.
        name:
            Name of the component.
        description:
            Description of the component.

        Examples
        --------
        >>> from wayflowcore.models import LlmModelFactory
        >>> OLLAMA_CONFIG = {
        ...     "model_type": "ollama",
        ...     "model_id": "<MODEL_NAME>",
        ... }
        >>> llm = LlmModelFactory.from_config(OLLAMA_CONFIG)

        Notes
        -----
        As of November 2024, Ollama does not support tool calling with token streaming. To enable this functionality,
        we prepend and append some specific REACT prompts and format tools with the REACT prompting template when:

        * the model should use tools
        * the list of message contains some tool_requests or tool_results

        Be aware of that when you generate with tools or tool calls. To disable this behaviour, set `use_tools` to False
        and make sure the prompt doesn't contain tool_call and tool_result messages.
        See https://arxiv.org/abs/2210.03629 for learning more about the REACT prompting techniques.

        """
        if host_port != DEFAULT_OLLAMA_HOST_PORT:
            logger.info("Will be using host port `%s` for Ollama model", host_port)
        self.host_port = host_port
        super().__init__(
            model_id=model_id,
            base_url=host_port,
            proxy=proxy,
            generation_config=generation_config,
            supports_tool_calling=supports_tool_calling,
            supports_structured_generation=supports_structured_generation,
            __metadata_info__=__metadata_info__,
            id=id,
            name=name,
            description=description,
        )

    def _pre_process(self, prompt: Prompt) -> Prompt:
        # Ollama will not generate a message if the message prompt only contains a message of type System.
        # It works if an empty Agent message is given additionally.
        # Bug Ticket: Fix ollama not generating output when only a system message is supplied
        if len(prompt.messages) == 1 and prompt.messages[0].message_type == MessageType.SYSTEM:
            prompt.messages += [Message(content="", message_type=MessageType.AGENT)]

        return super()._pre_process(prompt)

    def _post_process(self, message: "Message") -> "Message":
        for content in message.contents:
            if isinstance(content, TextContent):
                content.content = _filter_ollama_header_tokens(content.content)
        return message

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "model_type": "ollama",
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
        from wayflowcore.templates import LLAMA_AGENT_TEMPLATE

        return LLAMA_AGENT_TEMPLATE
