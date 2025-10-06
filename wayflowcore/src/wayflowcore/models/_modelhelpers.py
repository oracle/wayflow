# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
import json
from json import JSONDecodeError

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmGenerationConfig, LlmModel, Prompt
from wayflowcore.property import IntegerProperty, ObjectProperty, StringProperty, logger
from wayflowcore.tools import Tool


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
