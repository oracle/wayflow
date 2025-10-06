# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
from typing import Any, Dict, Optional

from wayflowcore._metadata import MetadataType

from .llmgenerationconfig import LlmGenerationConfig
from .openaicompatiblemodel import OpenAICompatibleModel

OPEN_API_KEY = "OPENAI_API_KEY"


class OpenAIModel(OpenAICompatibleModel):
    def __init__(
        self,
        model_id: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        generation_config: Optional[LlmGenerationConfig] = None,
        proxy: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Model powered by OpenAI.

        Parameters
        ----------
        model_id:
            Name of the model to use
        api_key:
            API key for the OpenAI endpoint. Overrides existing ``OPENAI_API_KEY`` environment variable.
        generation_config:
            default parameters for text generation with this model
        proxy:
            proxy to access the remote model under VPN
        id:
            ID of the component.
        name:
            Name of the component.
        description:
            Description of the component.

        .. important::
            When running under Oracle VPN, the connection to the OCIGenAI service requires to run the model without any proxy.
            Therefore, make sure not to have any of ``http_proxy`` or ``HTTP_PROXY`` environment variables setup,
            or unset them with ``unset http_proxy HTTP_PROXY``. Please also ensure that the ``OPENAI_API_KEY`` is set beforehand
            to access this model. A list of available OpenAI models can be found at the following
            link: `OpenAI Models <https://platform.openai.com/docs/models>`_

        Examples
        --------
        >>> from wayflowcore.models import LlmModelFactory
        >>> OPENAI_CONFIG = {
        ...     "model_type": "openai",
        ...     "model_id": "gpt-4o-mini",
        ... }
        >>> llm = LlmModelFactory.from_config(OPENAI_CONFIG)  # doctest: +SKIP

        Notes
        -----
        When running with Oracle VPN, you need to specify a https proxy, either globally or at the model level:

        >>> OPENAI_CONFIG = {
        ...    "model_type": "openai",
        ...    "model_id": "gpt-4o-mini",
        ...    "proxy": "<PROXY_ADDRESS>",
        ... }  # doctest: +SKIP
        """

        if api_key is None and OPEN_API_KEY not in os.environ:
            raise ValueError(f'Missing "{OPEN_API_KEY}" environment variable or input `api_key`')

        self.proxy = proxy
        super().__init__(
            model_id=model_id,
            base_url="https://api.openai.com",
            proxy=proxy,
            api_key=api_key or os.environ[OPEN_API_KEY],
            generation_config=generation_config,
            supports_structured_generation=True,
            supports_tool_calling=True,
            id=id,
            __metadata_info__=__metadata_info__,
            name=name,
            description=description,
        )

    def _get_headers(self) -> Dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @property
    def config(self) -> Dict[str, Any]:
        # proxy and api_key parameters are not serialized on purpose
        return {
            "model_type": "openai",
            "model_id": self.model_id,
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
        }
