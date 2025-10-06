# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
from pathlib import Path

import pytest

from wayflowcore.agent import Agent
from wayflowcore.contextproviders import (
    ContextProvider,
    FlowContextProvider,
    ToolContextProvider,
    get_default_context_providers,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization import autodeserialize, deserialize, serialize

CONFIGS_DIR = Path(os.path.dirname(__file__)).parent / "configs"


@pytest.fixture
def flow_context_provider_config():
    with open(CONFIGS_DIR / "flow_context_provider.yaml") as config_file:
        serialized_contextprovider = config_file.read()
    return serialized_contextprovider


def test_can_serialize_all_default_context_providers() -> None:
    context_providers = get_default_context_providers()
    for cp in context_providers.values():
        serialized_cp = serialize(cp)
        assert "_component_type: ContextProvider" in serialized_cp
        assert "output_descriptions" not in serialized_cp


def test_can_deserialize_all_serialized_default_context_providers() -> None:
    context_providers = get_default_context_providers()
    for cp in context_providers.values():
        new_cp = deserialize(ContextProvider, serialize(cp))
        assert isinstance(new_cp, type(cp))


def test_can_autodeserialize_all_serialized_default_context_providers() -> None:
    context_providers = get_default_context_providers()
    for cp in context_providers.values():
        new_cp = autodeserialize(serialize(cp))
        assert isinstance(new_cp, type(cp))


def test_deserializing_non_supported_context_provider_type_raises() -> None:
    unsupported_serialized_context_provider = """
      _component_type: ContextProvider
      context_provider_type: not-supported
      context_provider_args: {}
    """

    with pytest.raises(
        ValueError,
        match="The context provider type not-supported is not supported for deserialization",
    ):
        deserialize(ContextProvider, unsupported_serialized_context_provider)


def test_serialized_flow_context_provider_can_be_deserialized(flow_context_provider_config) -> None:
    context_provider = deserialize(ContextProvider, flow_context_provider_config)
    assert isinstance(context_provider, FlowContextProvider)
    assert isinstance(context_provider.flow, Flow)
    assert [
        vd.name for vd in context_provider.get_output_descriptors()
    ] == context_provider.flow_output_names
    assert set(context_provider.flow.steps.keys()) == {
        Flow._DEFAULT_STARTSTEP_NAME,
        "place_output_step",
        "time_output_step",
    }


@pytest.fixture
def contextual_flow() -> Flow:
    from wayflowcore.steps import OutputMessageStep

    return Flow.from_steps(
        [
            OutputMessageStep(
                message_template="The current time is 2pm.",
                output_mapping={OutputMessageStep.OUTPUT: "time_output_io"},
            ),
            OutputMessageStep(
                message_template="The current place is Zurich.",
            ),
        ]
    )


def test_flow_with_flow_context_provider_can_be_serde(contextual_flow: Flow) -> None:
    from wayflowcore.steps import OutputMessageStep

    flow_cp = FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
    main_flow = create_single_step_flow(
        step=OutputMessageStep(
            message_template="Context Time: {{ time_output_io }}",
            output_mapping={OutputMessageStep.OUTPUT: "$display_io"},
        ),
        context_providers=[flow_cp],
    )

    new_flow: Flow = deserialize(Flow, serialize(main_flow))

    assert isinstance(new_flow, Flow)

    assert isinstance(new_flow, Flow)
    assert len(new_flow.context_providers) == 1
    assert isinstance(new_flow.context_providers[0], FlowContextProvider)
    assert new_flow.context_providers[0].flow_output_names == flow_cp.flow_output_names
    assert main_flow.output_descriptors_dict == new_flow.output_descriptors_dict


def test_flexassistant_with_flow_context_provider_can_be_serde(
    contextual_flow: Flow, remotely_hosted_llm: VllmModel
) -> None:
    pass

    flow_cp = FlowContextProvider(contextual_flow, flow_output_names=["time_output_io"])
    assistant = Agent(
        llm=remotely_hosted_llm,
        custom_instruction="The current time is: {{ time_output_io }}",
        context_providers=[flow_cp],
    )
    new_assistant = deserialize(Agent, serialize(assistant))
    assert isinstance(new_assistant, Agent)
    assert len(new_assistant.context_providers) == 1
    assert isinstance(new_assistant.context_providers[0], FlowContextProvider)
    assert new_assistant.context_providers[0].get_output_descriptors()[0].name == "time_output_io"


def test_tool_context_provider_can_be_serde() -> None:
    from wayflowcore.serialization.context import DeserializationContext
    from wayflowcore.steps import OutputMessageStep
    from wayflowcore.tools import ServerTool

    def current_time() -> str:
        from datetime import datetime

        return str(datetime.now())

    tool = ServerTool(
        name="Current time",
        description="Tool that returns time",
        parameters={},
        output={"type": "string"},
        func=current_time,
    )

    context_provider = ToolContextProvider(tool=tool, output_name="time_output_io")

    main_flow = create_single_step_flow(
        step=OutputMessageStep(
            message_template="Context Time: {{ time_output_io }}",
        ),
        context_providers=[context_provider],
    )

    deser_context = DeserializationContext()
    deser_context.registered_tools = {tool.name: tool}
    new_flow: Flow = deserialize(
        Flow,
        serialize(main_flow),
        deserialization_context=deser_context,
    )

    assert isinstance(new_flow, Flow)
    assert len(new_flow.context_providers) == 1
    assert isinstance(new_flow.context_providers[0], ToolContextProvider)
    assert new_flow.context_providers[0].output_name == context_provider.output_name
    assert new_flow.context_providers[0].tool.name == context_provider.tool.name
    assert new_flow.context_providers[0].tool.description == context_provider.tool.description
    assert new_flow.context_providers[0].tool.parameters == context_provider.tool.parameters
    assert new_flow.context_providers[0].tool.output == context_provider.tool.output
    assert new_flow.context_providers[0].id == context_provider.id
