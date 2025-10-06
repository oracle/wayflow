# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.


from pyagentspec import Component
from pyagentspec.component import SerializeAsEnum
from pyagentspec.llms.ociclientconfig import OciClientConfig
from pydantic import SerializeAsAny

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.models.ocigenaimodel import ServingMode


class PluginEmbeddingConfig(Component, abstract=True):
    """Embedding models are components that can transform text into float vectors, to be used later
    for retrieval for example."""


class PluginOciGenAiEmbeddingConfig(PluginEmbeddingConfig):
    """
    Class to configure a connection to a OCI GenAI hosted embedding model.

    Requires to specify the model id, compartment id and the client configuration to the OCI GenAI service.
    """

    model_id: str
    """ID of the model to use"""
    compartment_id: str
    """ID of the compartment to use"""
    client_config: SerializeAsAny[OciClientConfig]
    """Client configuration to connect to the Oci GenAI service"""
    serving_mode: SerializeAsEnum[ServingMode] = ServingMode.ON_DEMAND
    """The serving mode of this remote Oci GenAI embedding model"""


class PluginOpenAiCompatibleEmbeddingConfig(PluginEmbeddingConfig):
    """
    Class to configure a connection to an openai-compatible remotely hosted embedding model.

    Requires to specify the url at which the instance is running.
    """

    url: str
    """Url of the model deployment"""
    model_id: str
    """ID of the model to use"""


class PluginOllamaEmbeddingConfig(PluginOpenAiCompatibleEmbeddingConfig):
    """
    Class to configure a connection to a local embedding model ran with Ollama.

    Requires to specify the url and port at which the model is running.
    """


class PluginOpenAiEmbeddingConfig(PluginEmbeddingConfig):
    """
    Class to configure a connection to a OpenAI embedding model.

    Requires to specify the name of the model to use.
    """

    model_id: str
    """ID of the model to use"""


class PluginVllmEmbeddingConfig(PluginOpenAiCompatibleEmbeddingConfig):
    """
    Class to configure a connection to a vLLM-hosted embedding model.

    Requires to specify the url at which the instance is running.
    """


EMBEDDINGMODEL_PLUGIN_NAME = "EmbeddingModelPlugin"

embeddingmodel_serialization_plugin = PydanticComponentSerializationPlugin(
    name=EMBEDDINGMODEL_PLUGIN_NAME,
    component_types_and_models={
        PluginOciGenAiEmbeddingConfig.__name__: PluginOciGenAiEmbeddingConfig,
        PluginOllamaEmbeddingConfig.__name__: PluginOllamaEmbeddingConfig,
        PluginOpenAiEmbeddingConfig.__name__: PluginOpenAiEmbeddingConfig,
        PluginVllmEmbeddingConfig.__name__: PluginVllmEmbeddingConfig,
        PluginOpenAiCompatibleEmbeddingConfig.__name__: PluginOpenAiCompatibleEmbeddingConfig,
    },
)
embeddingmodel_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=EMBEDDINGMODEL_PLUGIN_NAME,
    component_types_and_models={
        PluginOciGenAiEmbeddingConfig.__name__: PluginOciGenAiEmbeddingConfig,
        PluginOllamaEmbeddingConfig.__name__: PluginOllamaEmbeddingConfig,
        PluginOpenAiEmbeddingConfig.__name__: PluginOpenAiEmbeddingConfig,
        PluginVllmEmbeddingConfig.__name__: PluginVllmEmbeddingConfig,
        PluginOpenAiCompatibleEmbeddingConfig.__name__: PluginOpenAiCompatibleEmbeddingConfig,
    },
)
