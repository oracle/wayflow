# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import re
import warnings
from copy import copy
from json import JSONDecodeError
from threading import Lock

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmGenerationConfig, LlmModel, Prompt
from wayflowcore.property import IntegerProperty, ObjectProperty, StringProperty, logger
from wayflowcore.tools import Tool

_GPT_MODEL_VERSION_PATTERN = re.compile(r"(?<![a-z0-9])gpt-(\d+)(?:\.(\d+))?", re.IGNORECASE)
_gpt_responses_warning_emitted = False
_gpt_responses_warning_lock = Lock()


def _is_gpt_54_or_later(model_id: str) -> bool:
    match = _GPT_MODEL_VERSION_PATTERN.search(model_id)
    return match is not None and (int(match[1]), int(match[2] or 0)) >= (5, 4)


def _normalize_openai_reasoning_effort(effort: str) -> str:
    """OpenAI-compatible APIs use lowercase reasoning-effort values."""
    return effort.lower()


def _requires_gpt_responses_api(prompt: Prompt, model_id: str) -> bool:
    """Check whether GPT-5.4+ tools require Responses and warn about the fallback."""
    global _gpt_responses_warning_emitted
    config = prompt.generation_config
    if not _is_gpt_54_or_later(model_id) or not prompt.tools or config is None:
        return False

    effort = config.extra_args.get("reasoning_effort")
    if effort is None:
        return False

    if not isinstance(effort, str):
        raise ValueError("`reasoning_effort` must be a string for the Responses API.")
    if _normalize_openai_reasoning_effort(effort) == "none":
        return False
    with _gpt_responses_warning_lock:
        if _gpt_responses_warning_emitted:
            return True
        # OCI authentication changes warning filters, resetting Python's suppression.
        _gpt_responses_warning_emitted = True
    warnings.warn(
        f"Model {model_id!r} is switching to the Responses API because Chat Completions "
        "does not support tools with non-none reasoning effort.",
        UserWarning,
        stacklevel=3,
    )
    return True


def _convert_chat_reasoning_to_responses(
    generation_config: LlmGenerationConfig,
) -> LlmGenerationConfig:
    """Copy a config with Chat Completions reasoning converted to Responses format."""
    extra_args = dict(generation_config.extra_args)
    effort = extra_args.pop("reasoning_effort")
    reasoning = extra_args.get("reasoning")
    if reasoning is not None and not isinstance(reasoning, dict):
        raise ValueError("`reasoning` must be a dictionary for the Responses API.")
    extra_args["reasoning"] = {
        **(reasoning or {}),
        "effort": _normalize_openai_reasoning_effort(effort),
    }
    adapted_config = copy(generation_config)
    adapted_config.extra_args = extra_args
    return adapted_config


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
