# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import (
    SerializableDataclass,
    autodeserialize_any_from_dict,
    serialize_any_to_dict,
)


@dataclass
class LlmGenerationConfig(SerializableDataclass):
    """
    Parameters for LLM generation

    Parameters
    ----------
    max_tokens:
        Maximum number of tokens to generate as output.
    temperature:
        What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random,
        while lower values like 0.2 will make it more focused and deterministic.
        We generally recommend altering this or ``top_p`` but not both.
    top_p:
        An alternative to sampling with temperature, called nucleus sampling, where the model considers the results
        of the tokens with top_p probability mass. So 0.1 means only the tokens comprising the top 10% probability
        mass are considered.
        We generally recommend altering this or temperature but not both.
    stop:
        List of stop words to indicate the LLM to stop generating when encountering one of these words. This helps
        reducing hallucinations, when using templates like ReAct. Some reasoning models (o3, o4-mini...) might
        not support it.
    frequency_penalty:
        float between -2.0 and 2.0 that penalizes new tokens based on their frequency in the generated text so far.
        Values > 0 encourage the model to use new tokens, while values < 0 encourage the model to repeat tokens.

    extra_args:
        dictionary of extra arguments that can be used by specific model providers

        For OpenAI Responses API:

        max_tool_calls:
            The maximum number of total calls to built-in tools that can be processed in a response.
            This maximum number applies across all built-in tool calls, not per individual tool.
            Any further attempts to call a tool by the model will be ignored.

        reasoning:
            gpt-5 and o-series models only.

            If the config contains "reasoning", adds the "reasoning.encrypted_content" key in "include" automatically to preserve reasoning traces.
            (https://platform.openai.com/docs/api-reference/responses/create#responses_create-include)

            effort:
                Constrains effort on reasoning for reasoning models. Currently supported values are "minimal", "low", "medium", and "high".
                Reducing reasoning effort can result in faster responses and fewer tokens used on reasoning in a response.

            summary:
                A summary of the reasoning performed by the model. This can be useful for debugging and understanding the model's reasoning process. One of "auto", "concise", or "detailed".
                If the config contains "reasoning" and the "summary" parameter is not set, defaults to "auto".


        The full list of parameters for Responses API can be found here:
        https://platform.openai.com/docs/api-reference/responses/create

        .. note::
            The extra parameters should never include sensitive information.

    """

    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    frequency_penalty: Optional[float] = None
    extra_args: Dict[str, Any] = field(default_factory=dict)
    # might be an issue in the future if you want not to pass some parameter and there is a default config
    # if needed, defaults would be `Empty` and then None means `not specified` rather than `don't use`

    def __post_init__(self) -> None:
        # We check if among the extra args there are known fields
        known_fields: Set[str] = {"max_tokens", "temperature", "top_p", "stop", "frequency_penalty"}
        for extra_arg_key in known_fields:
            # If we find one, we remove it from extra args, and we set the proper field with the value (if it's not set)
            # If the field is already set (i.e., not None), we just ignore the value in extra_args and raise a warning
            if extra_arg_key in self.extra_args:
                extra_arg_value = self.extra_args.pop(extra_arg_key)
                if getattr(self, extra_arg_key) is None:
                    setattr(self, extra_arg_key, extra_arg_value)
                else:
                    warnings.warn(
                        f"The parameter `{extra_arg_key}` provided in the `extra_args` is already set "
                        f"in the corresponding field. The extra_arg entry will be ignored."
                    )
        if not (self.frequency_penalty is None or (-2 <= self.frequency_penalty <= 2)):
            raise ValueError("The frequency penalty should be between -2 and 2")

    def to_dict(self) -> Dict[str, Any]:
        config_dict: Dict[str, Union[int, float, List[str], Dict[str, Any]]] = {}
        if self.max_tokens is not None:
            config_dict["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            config_dict["temperature"] = self.temperature
        if self.top_p is not None:
            config_dict["top_p"] = self.top_p
        if self.stop is not None:
            config_dict["stop"] = self.stop
        if self.frequency_penalty is not None:
            config_dict["frequency_penalty"] = self.frequency_penalty
        if self.extra_args:
            for extra_arg_key, extra_arg_value in self.extra_args.items():
                config_dict[extra_arg_key] = serialize_any_to_dict(
                    extra_arg_value, SerializationContext(root=self)
                )
        return config_dict

    @staticmethod
    def from_dict(config: Dict[str, Any]) -> "LlmGenerationConfig":

        max_tokens = config.pop("max_tokens", config.pop("max_new_tokens", None))
        if max_tokens is not None:
            max_tokens = int(max_tokens)

        temperature = config.pop("temperature", None)
        if temperature is not None:
            temperature = float(temperature)

        top_p = config.pop("top_p", None)
        if top_p is not None:
            top_p = float(top_p)

        frequency_penalty = config.pop("frequency_penalty", None)
        if frequency_penalty is not None:
            frequency_penalty = float(frequency_penalty)

        stop = config.pop("stop", None)

        extra_args: Dict[str, Any] = {}
        for extra_arg_key, extra_arg_value in config.items():
            extra_args[extra_arg_key] = autodeserialize_any_from_dict(
                extra_arg_value, DeserializationContext()
            )

        return LlmGenerationConfig(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            frequency_penalty=frequency_penalty,
            extra_args=extra_args,
        )

    def merge_config(
        self, overriding_config: Optional["LlmGenerationConfig"]
    ) -> "LlmGenerationConfig":
        if overriding_config is None:
            return self
        self_dict = self.to_dict()
        for attr_name, attr_value in overriding_config.to_dict().items():
            if attr_value is not None:
                self_dict[attr_name] = attr_value
        return LlmGenerationConfig.from_dict(self_dict)
