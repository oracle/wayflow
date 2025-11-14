# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import copy
import datetime
import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union
from unittest import mock

import httpx
import pytest

from wayflowcore.executors._agentexecutor import _get_end_conversation_tool
from wayflowcore.messagelist import ImageContent, Message, MessageType, TextContent
from wayflowcore.models import StreamChunkType
from wayflowcore.models._requesthelpers import _RetryStrategy
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import LlmModel, Prompt
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.models.ollamamodel import OllamaModel
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.property import (
    ObjectProperty,
    StringProperty,
    _output_properties_to_response_format_property,
)
from wayflowcore.templates import REACT_CHAT_TEMPLATE, PromptTemplate
from wayflowcore.tools import Tool, ToolRequest, ToolResult, tool

from ..conftest import (
    COHERE_OCI_API_KEY_CONFIG,
    GEMMA_CONFIG,
    GROK_OCI_API_KEY_CONFIG,
    LLAMA_4_OCI_API_KEY_CONFIG,
    LLAMA_OCI_API_KEY_CONFIG,
    OCI_REASONING_MODEL_API_KEY_CONFIG,
    OLLAMA_MODEL_CONFIG,
    OPENAI_COMPATIBLE_MODEL_CONFIG,
    OPENAI_CONFIG,
    OPENAI_REASONING_CONFIG,
    VLLM_MODEL_CONFIG,
)
from ..testhelpers.dummy import DummyModel
from ..testhelpers.patching import patch_openai_compatible_llm
from ..testhelpers.testhelpers import retry_test

TEXT_GENERATION_PROMPT = "the capital of Switzerland is"
CHAT_TEXT_PROMPT = [
    Message(message_type=MessageType.USER, content="what is the capital of Switzerland?"),
]
CHAT_PROMPT = [
    Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
    Message(message_type=MessageType.USER, content="are you ready?"),
    Message(message_type=MessageType.AGENT, content="yes"),
    Message(message_type=MessageType.USER, content="what is the capital of Switzerland?"),
]
UNORDERED_CHAT_PROMPT = [
    Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
    Message(message_type=MessageType.SYSTEM, content="remember: answer the user question"),
    Message(message_type=MessageType.AGENT, content="yes, ok"),
    Message(message_type=MessageType.AGENT, content="can you repeat?"),
    Message(message_type=MessageType.USER, content="what is the capital of Switzerland?"),
]
CHAT_PROMPT_WITH_TOOLS = [
    Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
    Message(message_type=MessageType.USER, content="In what city is my company 'OHOH' based?"),
    Message(
        message_type=MessageType.TOOL_REQUEST,
        content="I'll use the get_company_location with the user's company",
        tool_requests=[
            ToolRequest(
                name="get_location",
                args={"company_name": "OHOH", "useless6": "", "useless8": 0},
                tool_request_id="tc1",
            )
        ],
    ),
    Message(
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(tool_request_id="tc1", content="zurich"),
    ),
    Message(message_type=MessageType.AGENT, content="'OHOH' is based in Zurich"),
    Message(message_type=MessageType.USER, content="And in what city is my company 'AHAH' based?"),
    Message(
        message_type=MessageType.TOOL_REQUEST,
        content="I'll use the get_company_location with the user's company",
        tool_requests=[
            ToolRequest(
                name="get_location",
                args={"company_name": "AHAH", "useless6": "", "useless8": 0},
                tool_request_id="tc2",
            )
        ],
    ),
    Message(
        message_type=MessageType.TOOL_RESULT,
        tool_result=ToolResult(tool_request_id="tc2", content="bern"),
    ),
]
CHAT_PROMPT_BEFORE_TOOL_CALL = [
    Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
    Message(message_type=MessageType.USER, content="In what city is my company 'OHOH' based?"),
]

CHAT_PROMPT_STANDALONE_SYSTEM_MESSAGE = [
    Message(message_type=MessageType.SYSTEM, content="greet the user with a welcome message"),
]

DUMMY_CONFIG = {
    "model_type": "dummy",
    "next_output": {
        "what is the capital of Switzerland?": Message(
            content="the capital of Switzerland is Bern",
            message_type=MessageType.AGENT,
        ),
        "bern": Message(
            content="the capital of Switzerland is Bern", message_type=MessageType.AGENT
        ),
        "In what city is my company 'OHOH' based?": Message(
            message_type=MessageType.TOOL_REQUEST,
            content="I'll use the get_company_location with the user's company",
            tool_requests=[ToolRequest("get_location", {"company_name": "OHOH"}, "tc1")],
        ),
        "the capital of Switzerland is": " bern",  # text since it's text completion
    },
}

INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL = os.environ.get("INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL")
if not INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL:
    raise Exception("INSTANCE_PRINCIPAL_ENDPOINT_BASE_URL is not set in the environment")


@tool
def get_location(
    company_name: Annotated[str, "Name of the company to search the location for"],
    useless6: Annotated[str, "this argument needs to be specified, Use empty string"],
    useless8: Annotated[int, "this argument needs to be specified. Use 0"],
    useless1: Annotated[int, "unused"] = 0,
    useless2: Annotated[float, "unused"] = 0.0,
    useless3: Annotated[bool, "unused"] = False,
    useless4: Annotated[List[str], "unused"] = [],
    useless5: Annotated[Dict[str, str], "unused"] = {},
    useless7: Annotated[int, "unused"] = 0,
) -> str:
    """Search the location of a given company"""
    return "bern"


SERVER_TOOLS = [get_location]


def stream_and_return_final_result(
    llm_config: Dict[str, str],
    chat_history: List[Message],
    tools: Optional[List[Tool]] = None,
) -> Message:
    llm = initialize_model(llm_config)
    prompt = llm.chat_template.with_tools(tools).format(inputs=dict(__CHAT_HISTORY__=chat_history))

    stream = llm.stream_generate(prompt=prompt)
    res_content = ""
    final_res = None
    for chunk_type, chunk in stream:
        if chunk_type == StreamChunkType.TEXT_CHUNK:
            res_content += chunk.content
        elif chunk_type == StreamChunkType.END_CHUNK:
            final_res = chunk
        elif chunk_type == StreamChunkType.START_CHUNK:
            res_content += chunk.content
        else:
            pass
    assert (
        final_res.content in res_content
    ), "Final chunk didn't return same content as what was streamed."
    check_counted_tokens(llm)
    return final_res


def assert_str_contains_bern(text: str) -> None:
    assert isinstance(text, str)
    assert "bern" in text.lower()


def check_message_contains_bern(message: Message) -> None:
    assert isinstance(message, Message)
    assert len(message.contents) == 1
    assert isinstance(message.contents[0], TextContent)

    assert isinstance(message.contents[0].content, str)
    assert "bern" in message.contents[0].content.lower()


def check_message_contains_tool_call(message: Message) -> None:
    assert isinstance(message, Message)
    assert message.tool_requests is not None
    assert len(message.tool_requests) > 0
    assert message.tool_requests[0].name == "get_location"
    assert message.tool_requests[0].args["company_name"].lower() == "ohoh"
    assert "useless6" in message.tool_requests[0].args
    assert "useless8" in message.tool_requests[0].args


def check_counted_tokens(llm: LlmModel) -> None:
    assert llm.token_usage_standalone.input_tokens > 0
    assert llm.token_usage_standalone.output_tokens > 0


def copy_config_and_set_tool_calling_method(
    config: Dict[str, Any], tool_calling_method: str
) -> Dict[str, Any]:
    config_copy = deepcopy(config)
    config_copy["_tool_calling_method"] = tool_calling_method
    return config_copy


def find_all_vision_models():
    available_models: List[Tuple[str, Dict[str, Any]]] = []
    if "OPENAI_API_KEY" in os.environ:
        available_models.append(("openai", OPENAI_CONFIG))
    if "OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ:
        available_models.append(("llama_4_oci", LLAMA_4_OCI_API_KEY_CONFIG))  # llama 4 oci
    available_models.append(("gemma_model", GEMMA_CONFIG))

    ids, arg_values = zip(*available_models)
    return {
        "argvalues": arg_values,
        "ids": ids,
    }


def find_all_available_models(
    with_dummy: bool = False,
    with_tool_calling_modes: bool = False,
    with_stop_parameter: bool = True,
) -> Dict:
    available_models: List[Tuple[str, Dict[str, Any]]] = []

    available_models.append(("vllm_llama", VLLM_MODEL_CONFIG))  # default vllm
    # default vllm with openai-compatible wrapper
    available_models.append(("openaicompatible_llama", OPENAI_COMPATIBLE_MODEL_CONFIG))
    available_models.append(("ollama", OLLAMA_MODEL_CONFIG))  # default ollama
    if with_dummy:
        available_models.append(("dummy", DUMMY_CONFIG))
    if "OPENAI_API_KEY" in os.environ:
        available_models.append(("openai", OPENAI_CONFIG))
    if "OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ:
        available_models.append(("cohere_oci", COHERE_OCI_API_KEY_CONFIG))  # cohere oci
        available_models.append(("llama_oci", LLAMA_OCI_API_KEY_CONFIG))  # llama oci
        if not with_stop_parameter:
            available_models.append(("grok_oci", GROK_OCI_API_KEY_CONFIG))  # grok oci

    if with_tool_calling_modes:
        available_models.append(
            ("vllm_react", copy_config_and_set_tool_calling_method(VLLM_MODEL_CONFIG, "REACT"))
        )
        available_models.append(
            ("vllm_native", copy_config_and_set_tool_calling_method(VLLM_MODEL_CONFIG, "NATIVE"))
        )

        if "openai" in {model_name for model_name, _ in available_models}:
            available_models.append(
                ("openai_react", copy_config_and_set_tool_calling_method(OPENAI_CONFIG, "REACT"))
            )

        if "llama_oci" in {model_name for model_name, _ in available_models}:
            available_models.append(
                (
                    "llama_oci_react",
                    copy_config_and_set_tool_calling_method(LLAMA_OCI_API_KEY_CONFIG, "REACT"),
                )
            )
            available_models.append(
                (
                    "llama_oci_native",
                    copy_config_and_set_tool_calling_method(LLAMA_OCI_API_KEY_CONFIG, "NATIVE"),
                )
            )

    ids, arg_values = zip(*available_models)
    return {
        "argvalues": arg_values,
        "ids": ids,
    }


def find_all_available_reasoning_models() -> Dict:
    available_models: List[Tuple[str, Dict[str, Any]]] = []
    if "OPENAI_API_KEY" in os.environ:
        available_models.append(("openai", OPENAI_REASONING_CONFIG))  # llama oci
    if "OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ:
        available_models.append(("oci_reasoning", OCI_REASONING_MODEL_API_KEY_CONFIG))
    ids, arg_values = zip(*available_models) if available_models else ([], [])
    return {
        "argvalues": arg_values,
        "ids": ids,
    }


# it will run different amount of tests depending on the machine and
# the environment it runs on, in order to catch bugs as soon as possible
with_all_llm_configs = pytest.mark.parametrize("llm_config", **find_all_available_models())

with_all_vision_llm_configs = pytest.mark.parametrize("llm_config", **find_all_vision_models())


with_all_llm_configs_and_dummy = pytest.mark.parametrize(
    "llm_config", **find_all_available_models(with_dummy=True)
)
with_all_llm_configs_with_stop_parameter = pytest.mark.parametrize(
    "llm_config", **find_all_available_models(with_stop_parameter=True)
)
with_all_llm_tool_calling_configs = pytest.mark.parametrize(
    "llm_config", **find_all_available_models(with_tool_calling_modes=True)
)
with_all_reasoning_models = pytest.mark.parametrize(
    "llm_config", **find_all_available_reasoning_models()
)
with_all_prompts = pytest.mark.parametrize(
    argnames="prompt",
    argvalues=[CHAT_TEXT_PROMPT, CHAT_PROMPT, UNORDERED_CHAT_PROMPT],
    ids=["chat_text_prompt", "chat_prompt", "unordered_chat_prompt"],
)


def initialize_model(llm_config: Dict[str, str]):
    if llm_config["model_type"] == "dummy":
        llm = DummyModel()
        llm.set_next_output(llm_config["next_output"])
    else:
        llm = LlmModelFactory.from_config(llm_config)
    return llm


@with_all_llm_configs_and_dummy
@with_all_prompts
@retry_test(max_attempts=2)
def test_model_chat(llm_config: Dict[str, str], prompt: List[Message]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-05-22
    Average success time:  0.42 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm = initialize_model(llm_config)
    res = llm.generate(prompt=Prompt(prompt))
    check_message_contains_bern(res.message)
    check_counted_tokens(llm)


@with_all_llm_configs_with_stop_parameter
@retry_test(max_attempts=2)
def test_model_with_stop_parameter(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-05-22
    Average success time:  0.42 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm = initialize_model(llm_config)
    prompt = Prompt(
        messages=[Message(content="please count from 1 to 10")],
        generation_config=LlmGenerationConfig(stop=["2"]),
    )
    res = llm.generate(prompt).message
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    assert "2" not in res.contents[0].content


@with_all_llm_configs
@retry_test(max_attempts=2)
def test_model_without_stop_parameter(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-05-22
    Average success time:  0.42 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm = initialize_model(llm_config)
    prompt = Prompt(
        messages=[Message(content="please count from 1 to 10")],
    )
    res = llm.generate(prompt).message
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    assert "2" in res.contents[0].content


@with_all_llm_configs_and_dummy
@with_all_prompts
@retry_test(max_attempts=2)
def test_model_chat_stream(llm_config: Dict[str, str], prompt: List[Message]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-05-22
    Average success time:  0.42 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm_prompt = Prompt(messages=prompt)
    res = stream_and_return_final_result(llm_config=llm_config, chat_history=prompt)
    check_message_contains_bern(res)


@with_all_llm_tool_calling_configs
@retry_test(max_attempts=7, wait_between_tries=1)
def test_model_chat_with_tools(llm_config: Dict[str, str], request) -> None:
    """
    vllm_llama
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  0.50 seconds per successful attempt
    Average failure time:  0.82 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    ollama
    Failure rate:          11 out of 20
    Observed on:           2025-05-06
    Average success time:  0.56 seconds per successful attempt
    Average failure time:  0.70 seconds per failed attempt
    Max attempt:           16
    Justification:         (0.55 ** 16) ~= 6.1 / 100'000
    SKIPPED

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.65 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  3.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  4.72 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    vllm_react
    Failure rate:          4 out of 20
    Observed on:           2025-05-06
    Average success time:  0.49 seconds per successful attempt
    Average failure time:  1.00 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.23 ** 7) ~= 3.1 / 100'000

    vllm_native
    Failure rate:          20 out of 20
    Observed on:           2025-05-06
    Average success time:  No time measurement
    Average failure time:  0.71 seconds per failed attempt
    Max attempt:           198
    Justification:         (0.95 ** 198) ~= 10.0 / 100'000

    openai_react
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_react
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  3.87 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_native
    Failure rate:          2 out of 20
    Observed on:           2025-05-08
    Average success time:  11.09 seconds per successful attempt
    Average failure time:  6.21 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.14 ** 5) ~= 4.7 / 100'000
    """
    llm = initialize_model(llm_config)
    if "vllm_native" in request.node.name or "ollama" in request.node.name:
        pytest.skip("Too flaky")
    prompt = llm.chat_template.with_tools(SERVER_TOOLS).format(
        inputs=dict(__CHAT_HISTORY__=CHAT_PROMPT_WITH_TOOLS)
    )
    res = llm.generate(prompt).message
    check_message_contains_bern(res)
    check_counted_tokens(llm)


@with_all_llm_tool_calling_configs
@retry_test(max_attempts=7, wait_between_tries=0)
def test_model_chat_with_tools_stream(llm_config: Dict[str, str], request) -> None:
    """
    vllm_llama
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.51 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ollama
    Failure rate:          4 out of 20
    Observed on:           2025-05-06
    Average success time:  0.55 seconds per successful attempt
    Average failure time:  0.69 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.23 ** 7) ~= 3.1 / 100'000

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.60 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  4.04 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  3.91 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    vllm_react
    Failure rate:          2 out of 20
    Observed on:           2025-05-06
    Average success time:  0.50 seconds per successful attempt
    Average failure time:  0.92 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.14 ** 5) ~= 4.7 / 100'000

    vllm_native
    Failure rate:          17 out of 20
    Observed on:           2025-05-06
    Average success time:  0.55 seconds per successful attempt
    Average failure time:  0.69 seconds per failed attempt
    Max attempt:           46
    Justification:         (0.82 ** 46) ~= 9.8 / 100'000

    openai_react
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.37 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_react
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  3.04 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_native
    Failure rate:          1 out of 20
    Observed on:           2025-05-09
    Average success time:  2.92 seconds per successful attempt
    Average failure time:  3.91 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """
    if any(x in request.node.name for x in ["vllm_native"]):
        pytest.skip("Too flaky")
    res = stream_and_return_final_result(
        llm_config=llm_config, chat_history=CHAT_PROMPT_WITH_TOOLS, tools=SERVER_TOOLS
    )
    check_message_contains_bern(res)


@with_all_llm_configs_and_dummy
@retry_test(max_attempts=2)
def test_model_text_generation(llm_config: Dict[str, str]) -> None:
    """
    Failure rate:          0 out of 100
    Observed on:           2025-05-22
    Average success time:  0.42 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           2
    Justification:         (0.01 ** 2) ~= 9.6 / 100'000
    """
    llm = initialize_model(llm_config)
    res = llm.generate(prompt=TEXT_GENERATION_PROMPT).message
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    assert_str_contains_bern(res.contents[0].content)


@with_all_reasoning_models
def test_reasoning_model_text_generation(llm_config) -> None:
    llm = initialize_model(llm_config)
    res = llm.generate(prompt=TEXT_GENERATION_PROMPT).message
    assert_str_contains_bern(res.content)


@with_all_llm_configs
def test_model_text_generation_from_standalone_system_message(llm_config: Dict[str, str]) -> None:
    llm = initialize_model(llm_config)
    prompt = PromptTemplate(messages=CHAT_PROMPT_STANDALONE_SYSTEM_MESSAGE).format()
    res_msg = llm.generate(prompt=prompt).message
    assert len(res_msg.contents) == 1
    assert isinstance(res_msg.contents[0], TextContent)
    assert isinstance(res_msg.contents[0].content, str)
    assert len(res_msg.contents[0].content.strip()) > 0


@with_all_llm_configs
def test_model_text_generation_from_standalone_system_message_stream(
    llm_config: Dict[str, str],
) -> None:
    res = stream_and_return_final_result(
        llm_config=llm_config, chat_history=CHAT_PROMPT_STANDALONE_SYSTEM_MESSAGE
    )
    assert isinstance(res, Message)
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    assert isinstance(res.contents[0].content, str)
    assert len(res.contents[0].content.strip()) > 0


def test_model_factory_and_direct_instantiation_are_equivalent():
    """Test that initializing a model directly or through the factory is
    the same wrt the resulting generation_config.

    Previous inconsistent behaviour is documented.
    """
    initialized_model = VllmModel(
        host_port=VLLM_MODEL_CONFIG["host_port"], model_id=VLLM_MODEL_CONFIG["model_id"]
    )
    config_without_generation_config = copy.deepcopy(VLLM_MODEL_CONFIG)
    config_without_generation_config.pop("generation_config")
    model_from_factory = LlmModelFactory.from_config(config_without_generation_config)
    assert initialized_model.generation_config == model_from_factory.generation_config


@with_all_llm_tool_calling_configs
@retry_test(max_attempts=7, wait_between_tries=1)
def test_can_generate_tool_call(llm_config) -> None:
    """
    vllm_llama
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  0.90 seconds per successful attempt
    Average failure time:  1.18 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    ollama
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.90 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.83 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  4.76 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  6.01 seconds per successful attempt
    Average failure time:  6.35 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    vllm_react
    Failure rate:          4 out of 20
    Observed on:           2025-05-06
    Average success time:  1.18 seconds per successful attempt
    Average failure time:  0.95 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.23 ** 7) ~= 3.1 / 100'000

    vllm_native
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.62 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    openai_react
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  2.66 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_react
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  7.99 seconds per successful attempt
    Average failure time:  13.99 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    llama_oci_native
    Failure rate:          0 out of 20
    Observed on:           2025-05-08
    Average success time:  3.91 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    llm = LlmModelFactory.from_config(llm_config)
    prompt = llm.chat_template.with_tools(SERVER_TOOLS).format(
        inputs=dict(__CHAT_HISTORY__=CHAT_PROMPT_BEFORE_TOOL_CALL)
    )
    res = llm.generate(prompt).message
    check_message_contains_tool_call(res)
    check_counted_tokens(llm)


@with_all_llm_tool_calling_configs
@retry_test(max_attempts=7, wait_between_tries=1)
def test_can_generate_tool_call_stream(llm_config, request) -> None:
    """
    vllm_llama
    Failure rate:          1 out of 40
    Observed on:           2025-05-06
    Average success time:  0.86 seconds per successful attempt
    Average failure time:  0.93 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.05 ** 4) ~= 0.5 / 100'000

    ollama
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  0.74 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    openai
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  1.93 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    cohere_oci
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  4.62 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    llama_oci
    Failure rate:          3 out of 40
    Observed on:           2025-05-06
    Average success time:  5.20 seconds per successful attempt
    Average failure time:  9.07 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.10 ** 4) ~= 8.2 / 100'000

    vllm_react
    Failure rate:          10 out of 40
    Observed on:           2025-05-06
    Average success time:  1.14 seconds per successful attempt
    Average failure time:  1.24 seconds per failed attempt
    Max attempt:           7
    Justification:         (0.26 ** 7) ~= 8.5 / 100'000

    vllm_native
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  0.64 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    openai_react
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  2.89 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    llama_oci_react
    Failure rate:          0 out of 40
    Observed on:           2025-05-06
    Average success time:  8.08 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.02 ** 3) ~= 1.3 / 100'000

    llama_oci_native
    Failure rate:          3 out of 20
    Observed on:           2025-05-09
    Average success time:  3.71 seconds per successful attempt
    Average failure time:  4.50 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.18 ** 6) ~= 3.6 / 100'000
    """
    res = stream_and_return_final_result(
        llm_config=llm_config, chat_history=CHAT_PROMPT_BEFORE_TOOL_CALL, tools=SERVER_TOOLS
    )
    check_message_contains_tool_call(res)


@with_all_llm_tool_calling_configs
def test_model_cannot_generate_tool_call_without_tool(llm_config: Dict[str, str]) -> None:
    llm = LlmModelFactory.from_config(llm_config)
    prompt = llm.chat_template.with_tools(None).format(
        inputs=dict(__CHAT_HISTORY__=CHAT_PROMPT_BEFORE_TOOL_CALL)
    )
    res = llm.generate(prompt).message
    assert isinstance(res, Message)
    assert res.tool_requests is None


@pytest.mark.parametrize(
    "llm_config",
    [
        VLLM_MODEL_CONFIG,
        copy_config_and_set_tool_calling_method(VLLM_MODEL_CONFIG, "NATIVE"),
        copy_config_and_set_tool_calling_method(VLLM_MODEL_CONFIG, "REACT"),
    ],
    ids=["vllm_llama", "vllm_native", "vllm_react"],
)
@retry_test(max_attempts=5, wait_between_tries=1)
def test_can_generate_ambiguous_tool_call(llm_config) -> None:
    """
    vllm_llama
    Failure rate:          2 out of 20
    Observed on:           2025-05-06
    Average success time:  0.62 seconds per successful attempt
    Average failure time:  0.56 seconds per failed attempt
    Max attempt:           5
    Justification:         (0.14 ** 5) ~= 4.7 / 100'000

    vllm_native
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.61 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    vllm_react
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  0.88 seconds per successful attempt
    Average failure time:  1.17 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """

    # tool name is not accurate to make sure the LLM has access to the documentation
    @tool
    def diner_forecast(
        city: Annotated[str, "name of the city. Needs to be in lowercase"],
        type: Annotated[
            Literal["4", "5"],
            "type of the city. Only possible values are '4' if a swiss city, '5' otherwise",
        ],
    ) -> str:
        """Function to get a city nickname."""
        if type not in ["4", "5"]:
            raise ValueError(f"Something went wrong, type is {type!r}")
        if city.lower() != city:
            raise ValueError(f"Something went wrong, city is {city!r}")
        return "big small apple"

    @tool
    def do_something_with_city(city: Annotated[str, "is not used"]) -> str:
        """Useless function. Don't call it"""
        raise NotImplementedError()

    messages = [
        Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
        Message(message_type=MessageType.USER, content="What is the nickname of Schlieren?"),
    ]
    llm = LlmModelFactory.from_config(llm_config)
    prompt = llm.chat_template.with_tools([diner_forecast, do_something_with_city]).format(
        inputs=dict(__CHAT_HISTORY__=messages)
    )
    message = llm.generate(prompt).message
    assert isinstance(message, Message)
    assert message.tool_requests is not None
    assert len(message.tool_requests) > 0
    assert "diner_forecast" == message.tool_requests[0].name
    assert diner_forecast.run(**message.tool_requests[0].args) == "big small apple"
    check_counted_tokens(llm)


@pytest.mark.parametrize(
    "llm_output,expected_tool_calls",
    [
        (
            """## Thought: I'll use the get_company_location with the user's company",
## Action:
```
{
    "name": "get_location",
    "parameters": {"company_name": "OHOH"}
}
```
""",
            [{"name": "get_location", "args": {"company_name": "OHOH"}}],
        ),
        (
            """## Thought: I'll use the get_company_location with the user's company
## Action:
```
{
    "name": "get_location",
    "parameters": {"company_name": "OHOH"}
},
{
    "name": "get_location",
    "parameters": {"company_name": "OHOH"}
}
```
""",
            [
                {"name": "get_location", "args": {"company_name": "OHOH"}},
                {"name": "get_location", "args": {"company_name": "OHOH"}},
            ],
        ),
        (
            """## Thought: I'll use the get_company_location with the user's company
## Action:
```
[{
    "name": "get_location",
    "parameters": {"company_name": "OHOH"}
},{
    "name": "get_location",
    "parameters": {"company_name" "OHOH"}
}]
```
""",
            [
                {"name": "get_location", "args": {"company_name": "OHOH"}},
                {"name": "get_location", "args": {"company_name": "OHOH"}},
            ],
        ),
    ],
)
def test_react_model_can_parse_several_tool_call(
    llm_output: str,
    expected_tool_calls: List[Dict[str, Union[Dict[str, str], str]]],
    remotely_hosted_llm: VllmModel,
) -> None:

    remotely_hosted_llm.chat_template = REACT_CHAT_TEMPLATE
    with patch_openai_compatible_llm(remotely_hosted_llm, llm_output):
        CHAT_PROMPT_BEFORE_TOOL_CALL = [
            Message(message_type=MessageType.SYSTEM, content="answer the user's questions"),
            Message(
                message_type=MessageType.USER, content="In what city is my company 'OHOH' based?"
            ),
        ]
        prompt = remotely_hosted_llm.chat_template.format(
            inputs=dict(__CHAT_HISTORY__=CHAT_PROMPT_BEFORE_TOOL_CALL)
        )
        res = remotely_hosted_llm.generate(prompt).message
        observed_tool_calls = [{"name": tr.name, "args": tr.args} for tr in res.tool_requests]
        assert observed_tool_calls == expected_tool_calls


@with_all_llm_configs
@retry_test(max_attempts=6, wait_between_tries=1)
def test_structured_generation(llm_config, request):
    """
    vllm_llama
    Failure rate:          3 out of 20
    Observed on:           2025-05-06
    Average success time:  0.58 seconds per successful attempt
    Average failure time:  0.71 seconds per failed attempt
    Max attempt:           6
    Justification:         (0.18 ** 6) ~= 3.6 / 100'000

    ollama
    Failure rate:          1 out of 20
    Observed on:           2025-05-06
    Average success time:  0.54 seconds per successful attempt
    Average failure time:  4.06 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.29 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    NOT SUPPORTED

    llama_oci
    NOT SUPPORTED
    """
    if any(x in request.node.name for x in ["cohere_oci", "llama_oci"]):
        pytest.skip("Not supported")
    llm = LlmModelFactory.from_config(llm_config)

    name_output = StringProperty(
        name="last_name",
        description="Extract and output only the last name of the person",
    )
    response_format = _output_properties_to_response_format_property([name_output])
    prompt = Prompt(
        messages=[
            Message(
                content="My first name is Safra and my last name is Catz",
                message_type=MessageType.USER,
            )
        ],
        response_format=response_format,
    )
    res = llm.generate(prompt).message
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    result = json.loads(res.contents[0].content)
    assert "last_name" in result
    assert result["last_name"] == "Catz"


@with_all_llm_configs
@retry_test(max_attempts=3, wait_between_tries=1)
def test_structured_generation_with_multiple_outputs(llm_config, request):
    """
    vllm_llama
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    ollama
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  0.54 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-06
    Average success time:  1.53 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    NOT SUPPORTED

    llama_oci
    NOT SUPPORTED
    """
    if any(x in request.node.name for x in ["cohere_oci", "llama_oci"]):
        pytest.skip("Not supported")
    llm = LlmModelFactory.from_config(llm_config)

    last_name_output = StringProperty(
        name="last_name",
        description="Extract and output only the last name of the person",
    )
    first_name_output = StringProperty(
        name="first_name",
        description="Extract and output only the first name of the person",
    )
    prompt = Prompt(
        messages=[
            Message(
                content="You need to output the first name and last name of the user. Here is her message: "
                "My first name is Safra and my last name is Catz",
                message_type=MessageType.USER,
            ),
        ],
        response_format=_output_properties_to_response_format_property(
            [last_name_output, first_name_output]
        ),
    )
    res = llm.generate(prompt).message
    assert len(res.contents) == 1
    assert isinstance(res.contents[0], TextContent)
    result = json.loads(res.contents[0].content)
    assert "last_name" in result
    assert result["last_name"] == "Catz"
    assert "first_name" in result
    assert result["first_name"] == "Safra"


@with_all_llm_configs
def test_chat_generate_works_with_empty_outputs_list(llm_config):
    llm = LlmModelFactory.from_config(llm_config)
    res = llm.generate(
        Prompt(messages=[Message(content="I'm Safra A. Catz", message_type=MessageType.USER)])
    )
    assert res is not None


# Cannot use the usual decorator because not all models support the seed
@pytest.mark.parametrize(
    "llm_config",
    [VLLM_MODEL_CONFIG, OPENAI_COMPATIBLE_MODEL_CONFIG]
    + ([OPENAI_CONFIG] if "OPENAI_API_KEY" in os.environ else [])
    + (
        [LLAMA_OCI_API_KEY_CONFIG]
        if "OCI_GENAI_API_KEY_CONFIG" in os.environ and "OCI_GENAI_API_KEY_PEM" in os.environ
        else []
    ),
)
@retry_test(max_attempts=3)
def test_extra_args_are_used_by_models(llm_config):
    """
    Failure rate:          0 out of 30
    Observed on:           2025-09-09
    Average success time:  2.60 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 3.1 / 100'000
    """
    # We set the seed, and we check that the outputs are the same
    llm_config = deepcopy(llm_config)
    llm_config["generation_config"]["temperature"] = 0.5
    llm_config["generation_config"]["seed"] = 1
    llm = LlmModelFactory.from_config(llm_config)
    prompt = Prompt(messages=[Message(content="What time is it?", message_type=MessageType.USER)])
    first_res = llm.generate(prompt)
    second_res = llm.generate(prompt)
    assert first_res.message.content == second_res.message.content


@retry_test(max_attempts=3)
def test_thinking_model_works_with_tools(oci_reasoning_model):
    """
    Failure rate:          0 out of 20
    Observed on:           2025-05-09
    Average success time:  3.63 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    prompt = Prompt(messages=CHAT_PROMPT_WITH_TOOLS, tools=SERVER_TOOLS)
    res = oci_reasoning_model.generate(prompt).message
    check_message_contains_bern(res)
    check_counted_tokens(oci_reasoning_model)


def test_thinking_model_doesnt_work_with_too_little_tokens(oci_reasoning_model):
    # not flaky, 10 tokens is not enough reasoning tokens for reasoning models
    prompt = Prompt(
        messages=CHAT_PROMPT_WITH_TOOLS,
        tools=SERVER_TOOLS,
        generation_config=LlmGenerationConfig(max_tokens=10),
    )
    res = oci_reasoning_model.generate(prompt).message
    assert "bern" not in res.content
    check_counted_tokens(oci_reasoning_model)


@with_all_llm_tool_calling_configs
@retry_test(max_attempts=4)
def test_model_can_end_conversation(llm_config):
    """Tests the resolution, where we found OCI models
    unable to call the built-in end_conversation tool because of a tool
    conversion issue.

    vllm_llama
    Failure rate:          0 out of 20
    Observed on:           2025-05-13
    Average success time:  0.68 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    openai
    Failure rate:          0 out of 20
    Observed on:           2025-05-13
    Average success time:  1.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    cohere_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-13
    Average success time:  3.86 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci
    Failure rate:          0 out of 20
    Observed on:           2025-05-13
    Average success time:  2.95 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_native
    Failure rate:          1 out of 20
    Observed on:           2025-05-13
    Average success time:  2.93 seconds per successful attempt
    Average failure time:  4.18 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000
    """
    if llm_config.get("_tool_calling_method") == "REACT":
        pytest.skip(
            "ReACT tool calling will lead the model to output a thought instead of a tool call. "
            "Testing native tool calling support is sufficient for this test."
        )

    model = LlmModelFactory.from_config(llm_config)
    finish_conversation_messages = [
        Message(
            message_type=MessageType.SYSTEM,
            content="No matter what the user asks, always finish this conversation with the provided tool. Do not think, just call the tool.",
        ),
        Message(message_type=MessageType.USER, content="Please end this conversation"),
    ]
    end_conversation_tool = _get_end_conversation_tool()
    prompt = model.chat_template.with_tools([end_conversation_tool]).format(
        inputs=dict(__CHAT_HISTORY__=finish_conversation_messages)
    )
    res = model.generate(prompt).message
    assert res.message_type == MessageType.TOOL_REQUEST
    assert len(res.tool_requests) == 1
    assert res.tool_requests[0].name == end_conversation_tool.name


@pytest.mark.anyio
async def test_call_model_inside_coroutine(remotely_hosted_llm, test_with_llm_fixture):
    async def async_llm_call():
        res = remotely_hosted_llm.generate("what is the capital of switzerland?")
        assert len(res.message.contents) == 1
        assert isinstance(res.message.contents[0], TextContent)
        assert len(res.message.contents[0].content) > 0

    with pytest.warns(
        UserWarning, match="You are calling an asynchronous method in a synchronous method"
    ):
        await async_llm_call()


@pytest.mark.anyio
async def test_async_call_model_inside_coroutine(remotely_hosted_llm):
    res = await remotely_hosted_llm.generate_async("what is the capital of switzerland?")
    assert len(res.message.contents) == 1
    assert isinstance(res.message.contents[0], TextContent)
    assert len(res.message.contents[0].content) > 0


@with_all_llm_configs
@retry_test(max_attempts=4, wait_between_tries=1)
def test_generate_works_with_frequency_penalty(llm_config):
    """
    vllm_llama
    Failure rate:          0 out of 10
    Observed on:           2025-06-04
    Average success time:  4.41 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    ollama
    Failure rate:          0 out of 10
    Observed on:           2025-06-04
    Average success time:  1.23 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    openai
    Not evaluated

    cohere_oci
    Failure rate:          0 out of 10
    Observed on:           2025-06-04
    Average success time:  0.00 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    llama_oci
    Failure rate:          0 out of 10
    Observed on:           2025-06-04
    Average success time:  19.47 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    # Cohere test with this parameter is undeterministic. So we don't run llm inference.
    # We only check if the parameters are properly set
    cohere_model_detected = "cohere" in llm_config.get("model_id", "")

    llm_config = deepcopy(llm_config)
    if "generation_config" in llm_config:
        generation_cfg = llm_config["generation_config"]
    else:
        generation_cfg = llm_config.get("generation_args", {})
    generation_cfg["temperature"] = 0
    generation_cfg["top_p"] = 1
    llm_config["generation_config"] = generation_cfg
    generation_cfg["max_tokens"] = 512

    llm_no_penalty = LlmModelFactory.from_config(deepcopy(llm_config))
    assert llm_no_penalty.generation_config.frequency_penalty is None

    with pytest.raises(ValueError, match="The frequency penalty should be between -2 and 2"):
        generation_cfg["frequency_penalty"] = -3
        llm_penalty = LlmModelFactory.from_config(llm_config)
    with pytest.raises(ValueError, match="The frequency penalty should be between -2 and 2"):
        generation_cfg["frequency_penalty"] = 3
        llm_penalty = LlmModelFactory.from_config(llm_config)

    generation_cfg["frequency_penalty"] = 2
    llm_penalty = LlmModelFactory.from_config(llm_config)

    assert llm_no_penalty.generation_config.temperature == 0
    if cohere_model_detected:
        assert llm_penalty.generation_config.frequency_penalty == 1
        with pytest.raises(
            ValueError, match="Cohere Models do not support negative frequency penalties"
        ):
            generation_cfg["frequency_penalty"] = -0.5
            llm_penalty = LlmModelFactory.from_config(llm_config)
    else:
        assert llm_penalty.generation_config.frequency_penalty == 2
        test = 'Repeat the word "banana"  many times.'
        gen_str_no_penalty = llm_no_penalty.generate(test).message.content.lower()
        gen_str_penalty = llm_penalty.generate(test).message.content.lower()

        gen_cnt_no_penalty = gen_str_no_penalty.count("banana")

        gen_cnt_penalty = gen_str_penalty.count("banana")
        assert gen_cnt_no_penalty > gen_cnt_penalty


@pytest.mark.parametrize("timeout", [0.0001, httpx.Timeout(timeout=0.0001)])
def test_configure_timeout_works(timeout):
    llm = LlmModelFactory.from_config(VLLM_MODEL_CONFIG)
    llm._retry_strategy = _RetryStrategy(timeout=timeout, max_retries=0)
    with pytest.raises(
        Exception, match="API request failed after retries due to network error: ConnectTimeout"
    ):
        llm.generate("hello")


@retry_test(max_attempts=4)
def test_llm_streaming_gap_detected(remotely_hosted_llm):
    """
    Failure rate:          0 out of 10
    Observed on:           2025-08-01
    Average success time:  3.68 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000
    """
    streamed_times = []
    for chunk_type, message in remotely_hosted_llm.stream_generate(
        "List 50 animals, one per line."
    ):
        if chunk_type == StreamChunkType.START_CHUNK:
            # ignore initial chunk type that is streamed before the request
            continue
        streamed_times.append(datetime.datetime.now())

    assert (
        len(streamed_times) >= 3
    ), f"Expected at least 3 streaming chunks, got {len(streamed_times)}"
    duration = streamed_times[-1] - streamed_times[0]
    assert duration > datetime.timedelta(
        seconds=0.5
    ), f"First and last chunks were generated too close"


@retry_test(max_attempts=4)
@with_all_vision_llm_configs
def test_image_content_model(llm_config):
    """
    Test that the model can process a message with ImageContent,
    specifically querying the color of a logo in the image, expecting 'yellow' in the response.

    llama4_oci
    Failure rate:          0 out of 10
    Observed on:           2025-07-11
    Average success time:  1.52 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           4
    Justification:         (0.08 ** 4) ~= 4.8 / 100'000

    gemma_model
    Failure rate:          0 out of 10
    Observed on:           2025-07-11
    Average success time:  1.35 seconds per successful attempt
    """

    remotely_hosted_llm = LlmModelFactory.from_config(llm_config)
    # Test 1: Image + Text content (querying logo color)
    image_path = Path(__file__).parent.parent / "configs/test_data/image.png"
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_content = ImageContent.from_bytes(bytes_content=image_bytes, format="png")
    text_content = TextContent(content="What color is the logo?")
    image_message = Message(contents=[image_content, text_content], role="user")
    image_prompt = Prompt(messages=[image_message])

    result = remotely_hosted_llm.generate(image_prompt)
    result_string = result.message.content.lower()
    assert ("yellow" in result_string) or ("gold" in result_string)


@with_all_llm_configs
def test_unsupported_content_type(llm_config):
    """Test that an unsupported content type raises a RuntimeError in OpenAI compatible models."""
    llm = LlmModelFactory.from_config(llm_config)

    class UnsupportedContent:
        pass

    message = Message(role="user", contents=[UnsupportedContent()])
    prompt = Prompt(messages=[message])

    with pytest.raises(
        RuntimeError,
        match=r"(Unsupported content|Cohere models only support text messages as input)",
    ):
        llm.generate(prompt)


@pytest.mark.parametrize("llm_config", **find_all_available_models(with_stop_parameter=False))
def test_all_parameter_configs_set_works(llm_config):
    llm = LlmModelFactory.from_config(llm_config)
    result = llm.generate(
        prompt=Prompt(
            messages=[Message(content="2+2=", role="user")],
            generation_config=LlmGenerationConfig(
                top_p=0.95,
                temperature=0.5,
                max_tokens=10,
                stop=["4"],
                frequency_penalty=0.5,
            ),
        ),
    )


@retry_test(max_attempts=4)
def test_structured_generation_uses_default(remotely_hosted_llm, caplog):
    """
    Failure rate:          2 out of 40
    Observed on:           2025-11-04
    Average success time:  0.60 seconds per successful attempt
    Average failure time:  5.70 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.07 ** 4) ~= 2.6 / 100'000
    """
    prompt = Prompt(
        messages=[Message(content="Analyse the stacktrace:\n\nno error")],
        response_format=ObjectProperty(
            name="person",
            properties={
                "type": StringProperty(
                    description="ERROR if there is an error, OK if no error, WARNING if there is a warning"
                ),
                "error": StringProperty(
                    default_value="no_error", description="optional, only specify if none"
                ),
            },
        ),
    )

    with caplog.at_level(logging.INFO):
        result_as_str = remotely_hosted_llm.generate(prompt)
    result = json.loads(result_as_str.message.content)

    assert any(
        "The LLM cannot access the default value of the property `error=no_error`." in r.message
        for r in caplog.records
    )


@retry_test(max_attempts=3)
@pytest.mark.parametrize(
    "llm_fixture_name",
    ["remotely_hosted_llm", "llama_oci_llm", "grok_oci_llm", "cohere_llm", "gpt_llm"],
)
def test_structured_generation_with_enum(request, llm_fixture_name):
    """
    remotely_hosted_llm
    Failure rate:          0 out of 20
    Observed on:           2025-09-18
    Average success time:  0.96 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    llama_oci_llm
    Failure rate:          0 out of 20
    Observed on:           2025-09-18
    Average success time:  9.70 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    grok_oci_llm
    Failure rate:          1 out of 20
    Observed on:           2025-09-18
    Average success time:  7.45 seconds per successful attempt
    Average failure time:  5.69 seconds per failed attempt
    Max attempt:           4
    Justification:         (0.09 ** 4) ~= 6.8 / 100'000

    cohere_llm
    Failure rate:          0 out of 20
    Observed on:           2025-09-18
    Average success time:  1.62 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000

    gpt_llm
    Failure rate:          0 out of 20
    Observed on:           2025-09-18
    Average success time:  2.12 seconds per successful attempt
    Average failure time:  No time measurement
    Max attempt:           3
    Justification:         (0.05 ** 3) ~= 9.4 / 100'000
    """
    llm = request.getfixturevalue(llm_fixture_name)
    text = dedent(
        """
        Here is some text, extract some information about it:
        Sea turtles are animals living most of their lives in the ocean, in the deep waters. They are in danger, and are lonely animals.
        """
    )
    habitat_enum = ("WATER", "FOREST", "DESERT", "MOUNTAINS")
    state_enum = ("NA", "IN_DANGER", "EXTINCTION")
    life_enum = ("ALONE", "FAMILY", "HERD")
    response_format = ObjectProperty(
        name="animal",
        properties={
            "name": StringProperty(description="name of the animal in lower letters"),
            "habitat": StringProperty(enum=habitat_enum),
            "state": StringProperty(enum=state_enum),
            "life": StringProperty(enum=life_enum),
        },
    )
    prompt = Prompt(messages=[Message(content=text, role="user")], response_format=response_format)
    completion = llm.generate(prompt)
    content = completion.message.content
    json_content = json.loads(content)
    assert json_content.pop("name")
    assert json_content.pop("habitat") in habitat_enum
    assert json_content.pop("state") in state_enum
    assert json_content.pop("life") in life_enum


@pytest.mark.parametrize("model_cls", [VllmModel, OllamaModel])
@pytest.mark.parametrize(
    "base_url, expected",
    [
        ("https://www.example.com/v1/", "https://www.example.com/v1/chat/completions"),
        (
            "https://www.example.com/v1/chat/completions",
            "https://www.example.com/v1/chat/completions",
        ),
        ("http://www.example.com", "http://www.example.com/v1/chat/completions"),
        ("www.example.com/v1", "http://www.example.com/v1/chat/completions"),
        ("127.0.0.1:8080", "http://127.0.0.1:8080/v1/chat/completions"),
    ],
    ids=["https", "https-full", "http", "no-scheme/v1", "localhost"],
)
def test_vllm_ollama_with_correct_url(model_cls, base_url, expected):
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    payload = model_cls(model_id="my.model-id", host_port=base_url)._generate_request_params(prompt)
    assert payload["url"] == expected
    if os.environ.get("OPENAI_API_KEY") is None:
        assert payload.get("headers", {}).get("Authorization") is None  # no api_key was specified


@pytest.mark.parametrize("model_cls", [VllmModel, OllamaModel])
@mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-034-MOCKED_KEY"})
def test_vllm_ollama_with_api_key(model_cls):
    prompt = Prompt(messages=[Message(role="user", content="hello")])
    payload = model_cls(
        model_id="my.model-id", host_port="localhost:80000"
    )._generate_request_params(prompt)
    assert payload.get("headers", {}).get("Authorization") == "Bearer sk-034-MOCKED_KEY"
