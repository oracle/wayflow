# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import inspect
import random
import warnings
from typing import Annotated, Any, Dict, List, Optional, Type

import pytest

from wayflowcore import Agent, Flow
from wayflowcore.agent import CallerInputMode
from wayflowcore.datastore import Datastore
from wayflowcore.datastore.entity import Entity
from wayflowcore.datastore.inmemory import _INMEMORY_USER_WARNING, InMemoryDatastore
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.messagelist import MessageType
from wayflowcore.models import LlmModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.outputparser import RegexPattern
from wayflowcore.property import IntegerProperty, ListProperty, StringProperty
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps import (
    AgentExecutionStep,
    ChoiceSelectionStep,
    InputMessageStep,
    OutputMessageStep,
    ParallelFlowExecutionStep,
    RegexExtractionStep,
    RetryStep,
)
from wayflowcore.steps.choiceselectionstep import _DEFAULT_CHOICE_SELECTION_TEMPLATE
from wayflowcore.steps.datastoresteps import DatastoreListStep
from wayflowcore.steps.getchathistorystep import MessageSlice
from wayflowcore.steps.step import Step, _StepRegistry
from wayflowcore.tools import Tool, tool
from wayflowcore.variable import Variable, VariableWriteOperation

from ..conftest import get_single_step_flow

model_id, host_port = "zephyr-7b-beta", "LLAMA_API_ENDPOINT"
llm_assistant_model = VllmModel(
    host_port=host_port,
    model_id=model_id,
    generation_config=LlmGenerationConfig(max_tokens=1234),
)
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message=f"{_INMEMORY_USER_WARNING}*")
    datastore = InMemoryDatastore(
        schema={"Hello World": Entity(properties={"ID": IntegerProperty(default_value=0)})}
    )


@tool
def get_weather(location: Annotated[str, "The location to get the weather from"]) -> str:
    """Returns the weather in the provided location"""
    return random.choice(
        ["sunny", "rainy"]
    )  # nosec0004 # the reported issue by pybandit indicates use of non-cryptographic randomness; this randomness is only used to return a demo weather condition for tests


@pytest.fixture
def deserialization_context_with_tool():
    deserialization_context = DeserializationContext()
    deserialization_context.registered_tools["get_weather"] = get_weather
    return deserialization_context


DEFAULT_DESCRIPTOR_VALUES: Dict[str, object] = {
    str.__name__: "Hello World",
    int.__name__: 42,
    float.__name__: 42.0,
    bool.__name__: True,
    MessageType.__name__: MessageType.USER,
    MessageSlice.__name__: MessageSlice.LAST_MESSAGES,
    Optional.__name__: None,
    List.__name__: [],
    LlmModel.__name__: [llm_assistant_model],
    Tool.__name__: get_weather,
    Flow.__name__: get_single_step_flow(),
    Dict.__name__: {},
    Variable.__name__: Variable(
        name="var",
        type=ListProperty(item_type=StringProperty()),
        description="var",
        default_value=[],
    ),
    Datastore.__name__: datastore,
    CallerInputMode.__name__: CallerInputMode.ALWAYS,
    VariableWriteOperation.__name__: VariableWriteOperation.OVERWRITE,
}

DEFAULT_PARAMETER_VALUES: Dict[str, object] = {"llm": llm_assistant_model}

DEFAULT_CLASS_PARAMETER_VALUES: Dict[str, Dict[str, object]] = {
    ChoiceSelectionStep.__name__: {
        "next_steps": [],
        "prompt_template": _DEFAULT_CHOICE_SELECTION_TEMPLATE,
    },
    RetryStep.__name__: {
        "flow": create_single_step_flow(
            OutputMessageStep(
                message_template="Any message",
                output_mapping={OutputMessageStep.OUTPUT: "Hello World"},
            )
        ),
        "max_num_trials": 20,
    },
    AgentExecutionStep.__name__: {"agent": Agent(llm=llm_assistant_model)},
    DatastoreListStep.__name__: {"limit": 1},
    InputMessageStep.__name__: {"message_template": "Hello"},
    OutputMessageStep.__name__: {"message_type": MessageType.AGENT},
    RegexExtractionStep.__name__: {"regex_pattern": RegexPattern(pattern=".*")},
    ParallelFlowExecutionStep.__name__: {"flows": [get_single_step_flow()]},
}

# Add step class names in this list if they are not meant to be actually tested
step_cls_skiplist = [
    "Step",
    "CallableStep",
    "DoNothingStep",
    "ObjectStep",
    "AddCustomValuesToContextStep",
    "InputOutputSpecifiedStep",
    "FakeFailingStep",
    "FakeAdditionalStep",
    "PromptBenchmarkerPlaceholder",
    "_AssistantTesterExceptionStep",
]

# ignore abstract classes (e.g. Step) and private classes (_MY_STEP_HERE)
steps_to_check = [
    cls
    for cls in _StepRegistry._REGISTRY.values()
    if not inspect.isabstract(cls)
    and not cls.__name__.startswith("_")
    and not cls.__name__ in step_cls_skiplist
]


def create_init_arguments(step_cls: Type[Step]) -> Dict[str, Any]:
    init_arguments = {}
    for (
        config_name,
        config_descriptor,
    ) in step_cls._get_step_specific_static_configuration_descriptors().items():
        # 1. Check if there are specific parameters for the given Step class
        if (
            step_cls.__name__ in DEFAULT_CLASS_PARAMETER_VALUES
            and config_name in DEFAULT_CLASS_PARAMETER_VALUES[step_cls.__name__]
        ):
            init_arguments[config_name] = DEFAULT_CLASS_PARAMETER_VALUES[step_cls.__name__][
                config_name
            ]
        # 2. Check if there are specific values for the given parameter names
        elif config_name in DEFAULT_PARAMETER_VALUES:
            init_arguments[config_name] = DEFAULT_PARAMETER_VALUES[config_name]
        # 3. Use the default value from config descriptors
        elif config_descriptor.__name__ in DEFAULT_DESCRIPTOR_VALUES:
            init_arguments[config_name] = DEFAULT_DESCRIPTOR_VALUES[config_descriptor.__name__]
    init_arguments.update(
        dict(
            input_mapping=None,
            output_mapping=None,
            input_descriptors=None,
            output_descriptors=None,
        )
    )
    return init_arguments


@pytest.mark.filterwarnings(f"ignore:{_INMEMORY_USER_WARNING}:UserWarning")
@pytest.mark.parametrize("step_cls", steps_to_check)
def test_all_steps_can_be_serde_when_init_with_default_values(
    step_cls: Any, deserialization_context_with_tool
) -> None:
    config_descriptors: Dict[str, Any] = (
        step_cls._get_step_specific_static_configuration_descriptors()
    )
    init_arguments = create_init_arguments(step_cls)

    initialized_step = step_cls(**init_arguments)
    assert all(hasattr(initialized_step, config_name) for config_name in config_descriptors)
    serialized_step = serialize(initialized_step)
    deserialized_step = deserialize(
        Step, serialized_step, deserialization_context=deserialization_context_with_tool
    )
    assert initialized_step.__class__ == deserialized_step.__class__
