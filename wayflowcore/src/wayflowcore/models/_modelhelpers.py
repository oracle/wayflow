# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import re
import warnings
from copy import copy
from enum import Enum
from json import JSONDecodeError
from typing import TypeVar

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmGenerationConfig, LlmModel, Prompt
from wayflowcore.property import IntegerProperty, ObjectProperty, StringProperty, logger
from wayflowcore.tools import Tool

_APIType = TypeVar("_APIType", bound=Enum)
_GPT_MODEL_VERSION_PATTERN = re.compile(r"(?<![a-z0-9])gpt-(\d+)(?:\.(\d+))?", re.IGNORECASE)


def _is_gpt_54_or_later(model_id: str) -> bool:
    match = _GPT_MODEL_VERSION_PATTERN.search(model_id)
    return match is not None and (int(match[1]), int(match[2] or 0)) >= (5, 4)


def _prepare_gpt_chat_prompt(
    prompt: Prompt, model_id: str, chat_api_type: _APIType, responses_api_type: _APIType
) -> tuple[Prompt, _APIType]:
    """Adapt GPT-5.4+ chat requests without modifying the prompt or model configuration."""
    config = prompt.generation_config
    if not _is_gpt_54_or_later(model_id) or config is None:
        return prompt, chat_api_type

    effort = config.extra_args.get("reasoning_effort")
    if effort is None:
        return prompt, chat_api_type

    use_responses = bool(prompt.tools) and str(effort).casefold() != "none"
    if not isinstance(effort, str):
        if use_responses:
            raise ValueError("`reasoning_effort` must be a string for the Responses API.")
        return prompt, chat_api_type

    extra_args = dict(config.extra_args)
    if use_responses:
        extra_args.pop("reasoning_effort")
        reasoning = extra_args.get("reasoning")
        if reasoning is not None and not isinstance(reasoning, dict):
            raise ValueError("`reasoning` must be a dictionary for the Responses API.")
        extra_args["reasoning"] = {**(reasoning or {}), "effort": effort.lower()}
        warnings.warn(
            f"Model {model_id!r} is switching from {chat_api_type} to {responses_api_type} "
            "because chat completions does not support function tools with a non-NONE "
            "reasoning_effort.",
            UserWarning,
            stacklevel=3,
        )
    else:
        if effort == effort.lower():
            return prompt, chat_api_type
        extra_args["reasoning_effort"] = effort.lower()

    adapted_config = copy(config)
    adapted_config.extra_args = extra_args
    return (
        prompt.copy(generation_config=adapted_config),
        responses_api_type if use_responses else chat_api_type,
    )


def _fetch_structured_generation_support(llm: "LlmModel") -> bool:
    from wayflowcore.messagelist import Message, MessageType

    _structured_generation_support_prompt = Prompt(
        messages=[Message(content="Please submit the year: 2025", message_type=MessageType.USER)],
        generation_config=LlmGenerationConfig(max_tokens=100),
        response_format=ObjectProperty(name="result", properties={"year": IntegerProperty()}),
    )

    async def generate_impl() -> bool:
        completion = await llm._generate_impl(prompt=_structured_generation_support_prompt)
        result = json.loads(completion.message.content)

        result_is_formatted = isinstance(result, dict) and isinstance(result.get("year", None), int)
        if result_is_formatted:
            logger.debug(f"Response format is supported by model {llm}")
        else:
            logger.debug(f"Response format is not supported by model {llm}")
        return result_is_formatted

    try:
        return run_async_in_sync(generate_impl)
    except TypeError as e:
        logger.debug(f"Response format is not supported by model {llm}: {e}")
    except JSONDecodeError as e:
        logger.debug(f"Response format is not supported by model {llm}: {e}")
    except Exception as e:
        if "API streaming request failed after retries" not in str(e):
            raise e
        logger.debug(f"Response format is not supported by model {llm}: {e}")
    return False


def _fetch_tool_calling_support(llm: "LlmModel") -> bool:

    _tool_calling_support_prompt = Prompt(
        messages=[Message(content="Find the weather in Zurich", message_type=MessageType.USER)],
        generation_config=LlmGenerationConfig(max_tokens=100),
        tools=[
            Tool(
                name="get_weather",
                description="get the weather in a city",
                input_descriptors=[StringProperty(name="zurich")],
            )
        ],
    )

    async def generate_impl() -> bool:
        completion = await llm._generate_impl(prompt=_tool_calling_support_prompt)
        result_contains_tool_calls = completion.message.tool_requests is not None
        if result_contains_tool_calls:
            logger.debug(f"Tool calls are supported by model {llm}: {completion}")
        else:
            logger.debug(f"Tool calls are not supported by model {llm}: {completion}")
        return result_contains_tool_calls

    try:
        return run_async_in_sync(generate_impl)
    except TypeError as e:
        logger.debug(f"Response format is not supported by model {llm}: {e}")
    except Exception as e:
        logger.debug(f"Response format is not supported by model {llm}: {e}")
        if "API streaming request failed after retries" not in str(e):
            raise e
    return False


def _is_gemma_model(model_id: str) -> bool:
    return "gemma" in model_id.lower()


def _is_native_tool_calling_gemma_model(model_id: str) -> bool:
    # Match versioned Gemma names like `gemma-4-27b-it`, while avoiding compact
    # or size-only names like `gemma4` and `gemma-7b-it`.
    # Here, we assume all Gemma models from version 4 support native tool-calling
    version_match = re.search(r"(?:^|[/_:.-])gemma-([0-9]+)(?=[/_:.-]|$)", model_id.lower())
    if version_match is None:
        return False
    return int(version_match.group(1)) >= 4


def _supports_tool_role(model_id: str) -> bool:
    if _is_gemma_model(model_id):
        return _is_native_tool_calling_gemma_model(model_id)
    return True


def _is_llama_legacy_model(model_id: str) -> bool:
    return "llama" in model_id.lower() and "3." in model_id
