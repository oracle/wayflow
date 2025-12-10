# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from ._requesthelpers import (
    StreamChunkType,
    TaggedMessageChunkType,
    TaggedMessageChunkTypeWithTokenUsage,
)
from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import LlmCompletion, LlmModel, Prompt
from .llmmodelfactory import LlmModelFactory
from .ociclientconfig import (
    OCIClientConfig,
    OCIClientConfigWithApiKey,
    OCIClientConfigWithInstancePrincipal,
    OCIClientConfigWithResourcePrincipal,
    OCIClientConfigWithSecurityToken,
    OCIClientConfigWithUserAuthentication,
    OCIUserAuthenticationConfig,
)
from .ocigenaimodel import OCIGenAIModel
from .ollamamodel import OllamaModel
from .openaiapitype import OpenAIAPIType
from .openaicompatiblemodel import OpenAICompatibleModel
from .openaimodel import OpenAIModel
from .vllmmodel import VllmModel

__all__ = [
    "LlmCompletion",
    "LlmGenerationConfig",
    "LlmModel",
    "LlmModelFactory",
    "OCIGenAIModel",
    "OllamaModel",
    "OpenAICompatibleModel",
    "OpenAIAPIType",
    "OpenAIModel",
    "Prompt",
    "StreamChunkType",
    "VllmModel",
    "TaggedMessageChunkType",
    "TaggedMessageChunkTypeWithTokenUsage",
    "OCIClientConfigWithApiKey",
    "OCIClientConfigWithSecurityToken",
    "OCIClientConfigWithInstancePrincipal",
    "OCIClientConfigWithResourcePrincipal",
    "OCIClientConfigWithUserAuthentication",
    "OCIUserAuthenticationConfig",
    "OCIClientConfig",
]
