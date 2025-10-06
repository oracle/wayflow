# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import warnings
from copy import deepcopy
from typing import Any, Dict, Type

from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import LlmModel
from .ocigenaimodel import ModelProvider


class LlmModelFactory:
    """Factory class that creates ``LlmModel`` instances from configuration dictionaries.

    Supports vLLM, Ollama, OpenAI and OCIGenAI models.
    """

    @staticmethod
    def from_config(model_config: Dict[str, Any]) -> LlmModel:
        config_copy = deepcopy(model_config)
        model_type = config_copy.pop("model_type")

        from .ociclientconfig import OCIClientConfig
        from .ocigenaimodel import OCIGenAIModel, ServingMode
        from .ollamamodel import OllamaModel
        from .openaicompatiblemodel import OpenAICompatibleModel
        from .openaimodel import OpenAIModel
        from .vllmmodel import VllmModel

        if "generation_args" in config_copy:
            # preserve legacy configs
            generation_config = config_copy.pop("generation_args")
            config_copy["generation_config"] = generation_config

        if "generation_config" in config_copy and config_copy["generation_config"] is not None:
            config_copy["generation_config"] = LlmGenerationConfig.from_dict(
                config_copy["generation_config"]
            )

        if "model_args" in config_copy:
            warnings.warn("Deprecated model_args. Use the wayflowcore model arguments")
            config_copy.pop("model_args")

        if model_type == "ocigenai":
            if "client_config" in config_copy:
                client_config_obj = config_copy["client_config"]
                if isinstance(client_config_obj, dict):
                    config_copy["client_config"] = OCIClientConfig.from_dict(client_config_obj)
                elif not isinstance(client_config_obj, OCIClientConfig):
                    raise TypeError(
                        f"'client_config' should be either a dictionary or an OCIClientConfig object. "
                        f"Got type {type(client_config_obj)} instead."
                    )
            if "serving_mode" in config_copy:
                config_copy["serving_mode"] = ServingMode(config_copy["serving_mode"])
            if "provider" in config_copy:
                config_copy["provider"] = ModelProvider(config_copy["provider"])

        config_copy.pop("_component_type", None)
        config_copy.pop("_referenced_objects", None)
        override_tool_calling_default_method = config_copy.pop("_tool_calling_method", None)

        model_type_to_model_class_dict: Dict[str, Type[LlmModel]] = {
            "vllm": VllmModel,
            "ollama": OllamaModel,
            "openai": OpenAIModel,
            "openaicompatible": OpenAICompatibleModel,
            "ocigenai": OCIGenAIModel,
        }
        model_cls = model_type_to_model_class_dict.get(model_type, None)
        if model_cls is None:
            raise ValueError(f"Unknown type of model: {model_type}")

        model = model_cls(**config_copy)

        if override_tool_calling_default_method is not None:
            from wayflowcore.templates import (
                LLAMA_AGENT_TEMPLATE,
                NATIVE_AGENT_TEMPLATE,
                REACT_AGENT_TEMPLATE,
            )

            if override_tool_calling_default_method == "LLAMA":
                model.agent_template = LLAMA_AGENT_TEMPLATE
            elif override_tool_calling_default_method == "REACT":
                model.agent_template = REACT_AGENT_TEMPLATE
            elif override_tool_calling_default_method == "NATIVE":
                model.agent_template = NATIVE_AGENT_TEMPLATE
            else:
                raise ValueError(f"Not supported {override_tool_calling_default_method}")
        return model
