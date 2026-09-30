# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import re
import warnings
from copy import copy
from typing import Any, Dict, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.retrypolicy import RetryPolicy
from wayflowcore.serialization.serializer import serialize_to_dict

from .llmgenerationconfig import LlmGenerationConfig
from .llmmodel import Prompt
from .openaiapitype import OpenAIAPIType
from .openaicompatiblemodel import OPEN_API_KEY, OpenAICompatibleModel

_GPT_MODEL_VERSION_PATTERN = re.compile(r"(?<![a-z0-9])gpt-(\d+)(?:\.(\d+))?", re.IGNORECASE)


def _is_gpt_54_or_later(model_id: str) -> bool:
    match = _GPT_MODEL_VERSION_PATTERN.search(model_id)
    if match is None:
        return False
    version = (int(match.group(1)), int(match.group(2) or 0))
    return version >= (5, 4)


class OpenAIModel(OpenAICompatibleModel):
    def __init__(
        self,
        model_id: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        generation_config: Optional[LlmGenerationConfig] = None,
        proxy: Optional[str] = None,
        api_type: OpenAIAPIType = OpenAIAPIType.CHAT_COMPLETIONS,
        retry_policy: Optional[RetryPolicy] = None,
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
        api_type:
            OpenAI API type to use. Currently supports Responses and Chat Completions API.
            Uses Completions API if not specified
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
            api_key=api_key if api_key is not None else os.environ[OPEN_API_KEY],
            generation_config=generation_config,
            supports_structured_generation=True,
            supports_tool_calling=True,
            api_type=api_type,
            retry_policy=retry_policy,
            id=id,
            __metadata_info__=__metadata_info__,
            name=name,
            description=description,
        )

    def _prepare_prompt_and_api_processor(self, prompt: Prompt) -> tuple[Prompt, Any]:
        """Use Responses for tool calls with reasoning effort unsupported by Chat Completions.

        Tool availability is prompt-specific, so select the API processor per request rather than
        changing the model's configured API type. This also keeps concurrent requests isolated.
        """
        if self.api_type != OpenAIAPIType.CHAT_COMPLETIONS or not _is_gpt_54_or_later(
            self.model_id
        ):
            return super()._prepare_prompt_and_api_processor(prompt)

        generation_config = prompt.generation_config
        if generation_config is None:
            return super()._prepare_prompt_and_api_processor(prompt)

        reasoning_effort = generation_config.extra_args.get("reasoning_effort")
        if reasoning_effort is None:
            return super()._prepare_prompt_and_api_processor(prompt)
        if not isinstance(reasoning_effort, str):
            if not prompt.tools or str(reasoning_effort).casefold() == "none":
                return super()._prepare_prompt_and_api_processor(prompt)
            raise ValueError(
                "`reasoning_effort` must be a string when switching to the OpenAI Responses API."
            )

        normalized_effort = reasoning_effort.lower()
        if not prompt.tools or normalized_effort == "none":
            if reasoning_effort == normalized_effort:
                return super()._prepare_prompt_and_api_processor(prompt)

            normalized_generation_config = copy(generation_config)
            normalized_extra_args = dict(generation_config.extra_args)
            normalized_extra_args["reasoning_effort"] = normalized_effort
            normalized_generation_config.extra_args = normalized_extra_args
            return (
                prompt.copy(generation_config=normalized_generation_config),
                self.api_processor,
            )

        # The Chat Completions and Responses APIs use different field names. Copy the config so
        # preparing this request doesn't mutate a caller-owned Prompt or model default.
        responses_generation_config = copy(generation_config)
        responses_extra_args = dict(generation_config.extra_args)
        responses_extra_args.pop("reasoning_effort")
        reasoning = responses_extra_args.get("reasoning")
        if reasoning is None:
            reasoning = {}
        elif isinstance(reasoning, dict):
            reasoning = dict(reasoning)
        else:
            raise ValueError("`reasoning` must be a dictionary for the OpenAI Responses API.")
        reasoning["effort"] = normalized_effort
        responses_extra_args["reasoning"] = reasoning
        responses_generation_config.extra_args = responses_extra_args
        prompt = prompt.copy(generation_config=responses_generation_config)

        warnings.warn(
            f"Model {self.model_id!r} is switching from {OpenAIAPIType.CHAT_COMPLETIONS} to "
            f"{OpenAIAPIType.RESPONSES} because Chat Completions does not support function "
            "tools with a non-NONE reasoning_effort.",
            UserWarning,
            stacklevel=2,
        )
        return prompt, self._create_api_processor(OpenAIAPIType.RESPONSES)

    @property
    def config(self) -> Dict[str, Any]:
        # proxy and api_key parameters are not serialized on purpose
        return {
            "model_type": "openai",
            "model_id": self.model_id,
            "retry_policy": (
                serialize_to_dict(self.retry_policy) if self.retry_policy is not None else None
            ),
            "generation_config": (
                self.generation_config.to_dict() if self.generation_config is not None else None
            ),
        }
