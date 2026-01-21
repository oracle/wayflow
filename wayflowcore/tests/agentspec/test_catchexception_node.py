# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import pytest
from pyagentspec.flows.edges import ControlFlowEdge as SpecControlFlowEdge
from pyagentspec.flows.edges import DataFlowEdge as SpecDataFlowEdge
from pyagentspec.flows.flow import Flow as SpecFlow
from pyagentspec.flows.node import Node
from pyagentspec.flows.nodes import CatchExceptionNode, EndNode, StartNode, ToolNode
from pyagentspec.property import IntegerProperty, NullProperty, StringProperty, UnionProperty
from pyagentspec.tools import ServerTool as SpecServerTool

from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader
from wayflowcore.agentspec.components import PluginCatchExceptionNode
from wayflowcore.controlconnection import ControlFlowEdge as RuntimeControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge as RuntimeDataFlowEdge
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow as RuntimeFlow

# from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.property import StringProperty as RuntimeStringProperty
from wayflowcore.steps import CatchExceptionStep, OutputMessageStep, ToolExecutionStep
from wayflowcore.steps.step import Step
from wayflowcore.tools import tool


@pytest.fixture
def spec_flow_with_catchexception() -> SpecFlow:
    inp = IntegerProperty(title="x")
    subflow_output = StringProperty(title="tool_output", default="")
    flaky_tool = SpecServerTool(
        name="flaky_tool",
        description="Raises for negative inputs",
        inputs=[inp],
        outputs=[subflow_output],
    )
    sub_start = StartNode(name="sub_start", inputs=[inp])
    tool_node = ToolNode(name="flaky_node", tool=flaky_tool)
    sub_end = EndNode(name="sub_end", outputs=[subflow_output])

    subflow = SpecFlow(
        name="flaky_subflow",
        start_node=sub_start,
        nodes=[sub_start, tool_node, sub_end],
        control_flow_connections=[
            SpecControlFlowEdge(name="s2t", from_node=sub_start, to_node=tool_node),
            SpecControlFlowEdge(name="t2e", from_node=tool_node, to_node=sub_end),
        ],
        data_flow_connections=[
            SpecDataFlowEdge(
                name="in",
                source_node=sub_start,
                source_output=inp.title,
                destination_node=tool_node,
                destination_input=inp.title,
            ),
            SpecDataFlowEdge(
                name="out",
                source_node=tool_node,
                source_output=subflow_output.title,
                destination_node=sub_end,
                destination_input=subflow_output.title,
            ),
        ],
        inputs=[inp],
        outputs=[subflow_output],
    )

    catch = CatchExceptionNode(name="catch_step", subflow=subflow)

    start = StartNode(name="start", inputs=[inp])
    error_info = UnionProperty(
        title="error_info",
        any_of=[StringProperty(title="error_info"), NullProperty(title="error_info")],
        default=None,
    )
    success_end = EndNode(name="success_end", outputs=[subflow_output, error_info])
    error_end = EndNode(name="error_end", outputs=[subflow_output, error_info], branch_name="ERROR")

    return SpecFlow(
        name="outer",
        start_node=start,
        nodes=[start, catch, success_end, error_end],
        control_flow_connections=[
            SpecControlFlowEdge(name="s2c", from_node=start, to_node=catch),
            SpecControlFlowEdge(name="c2e", from_node=catch, to_node=success_end),
            SpecControlFlowEdge(
                name="caught_to_error",
                from_node=catch,
                from_branch=CatchExceptionNode.CAUGHT_EXCEPTION_BRANCH,
                to_node=error_end,
            ),
        ],
        data_flow_connections=[
            SpecDataFlowEdge(
                name="in",
                source_node=start,
                source_output=inp.title,
                destination_node=catch,
                destination_input=inp.title,
            ),
            SpecDataFlowEdge(
                name="out",
                source_node=catch,
                source_output=subflow_output.title,
                destination_node=success_end,
                destination_input=subflow_output.title,
            ),
            SpecDataFlowEdge(
                name="exception_to_error",
                source_node=catch,
                source_output="caught_exception_info",
                destination_node=error_end,
                destination_input=error_info.title,
            ),
        ],
        inputs=[inp],
        outputs=[subflow_output, error_info],
    )


@tool(description_mode="only_docstring")
def flaky_tool(x: int) -> str:
    """Raises for negative inputs."""
    if x < 0:
        raise ValueError("x must be non-negative")
    return "ok"


@pytest.fixture
def flaky_wayflow_subflow() -> RuntimeFlow:
    tool_step = ToolExecutionStep(
        name="flaky",
        tool=flaky_tool,
        raise_exceptions=True,
        output_descriptors=[
            RuntimeStringProperty(name=ToolExecutionStep.TOOL_OUTPUT, default_value="no_output")
        ],
    )
    return RuntimeFlow.from_steps([tool_step])


@pytest.fixture
def runtime_flow_catching_all_exceptions(flaky_wayflow_subflow: SpecFlow) -> RuntimeFlow:
    tool_node_with_catch = CatchExceptionStep(
        name="catch_step", flow=flaky_wayflow_subflow, catch_all_exceptions=True
    )
    tool_sucess_output = OutputMessageStep(
        name="success_output_step",
        message_template="Tool succeeded without exceptions.",
    )
    tool_failure_output_step = OutputMessageStep(
        name="failure_output_step",
        message_template="Tool failed with ValueError: {{tool_error}}",
    )
    return RuntimeFlow(
        name="flow_catch_all_exceptions",
        begin_step=tool_node_with_catch,
        control_flow_edges=[
            RuntimeControlFlowEdge(
                source_step=tool_node_with_catch,
                destination_step=tool_sucess_output,
                source_branch=CatchExceptionStep.BRANCH_NEXT,
            ),
            RuntimeControlFlowEdge(
                source_step=tool_node_with_catch,
                destination_step=tool_failure_output_step,
                source_branch=CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
                # ^ This is the branch taken when any exception is raised
            ),
            RuntimeControlFlowEdge(source_step=tool_sucess_output, destination_step=None),
            RuntimeControlFlowEdge(source_step=tool_failure_output_step, destination_step=None),
        ],
        data_flow_edges=[
            RuntimeDataFlowEdge(
                tool_node_with_catch,
                CatchExceptionStep.EXCEPTION_PAYLOAD_OUTPUT_NAME,
                tool_failure_output_step,
                "tool_error",
            ),
        ],
    )


def test_runtime_flow_catching_all_exceptions_runs_as_expected(
    runtime_flow_catching_all_exceptions: RuntimeFlow,
) -> None:
    flow = runtime_flow_catching_all_exceptions
    # flaky case
    conv = flow.start_conversation({"x": -5})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "exception_name": "ValueError",
        "tool_output": "no_output",  # default value
        "output_message": "Tool failed with ValueError: x must be non-negative",
        "exception_payload_name": "x must be non-negative",
    }

    # non-flaky case
    conv2 = flow.start_conversation({"x": 5})
    status = conv2.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "exception_payload_name": "",
        "tool_output": "ok",
        "output_message": "Tool succeeded without exceptions.",
        "exception_name": "",
    }


def test_wayflow_flow_catching_all_exceptions_properly_converts_to_agentspec(
    runtime_flow_catching_all_exceptions: RuntimeFlow,
) -> None:
    spec_flow: SpecFlow = AgentSpecExporter().to_component(runtime_flow_catching_all_exceptions)

    # 1. there should be two output message nodes
    node_titles = {n.name for n in spec_flow.nodes}
    assert "success_output_step" in node_titles
    assert "failure_output_step" in node_titles

    # 2. the flow should use the native CatchExceptionNode
    catch_node = next((n for n in spec_flow.nodes if n.name == "catch_step"), None)
    assert (catch_node is not None) and isinstance(catch_node, CatchExceptionNode)

    # 3. check for correct control flow edge connection
    control_flow_edges = {
        (c.from_node.name, c.to_node.name, c.from_branch)
        for c in spec_flow.control_flow_connections
    }
    assert (
        "catch_step",
        "success_output_step",
        Node.DEFAULT_NEXT_BRANCH,
    ) in control_flow_edges or ("catch_step", "success_output_step", None) in control_flow_edges
    assert (
        "catch_step",
        "failure_output_step",
        CatchExceptionNode.CAUGHT_EXCEPTION_BRANCH,
    ) in control_flow_edges

    # 4. check for correct data flow edge connection
    data_flow_edges = {
        (d.source_node.name, d.source_output, d.destination_node.name, d.destination_input)
        for d in spec_flow.data_flow_connections
    }
    assert (
        "catch_step",
        CatchExceptionNode.DEFAULT_EXCEPTION_INFO_VALUE,
        "failure_output_step",
        "tool_error",
    ) in data_flow_edges

    # 5. check for input/output
    spec_flow_input_titles = {p.title for p in spec_flow.inputs}
    spec_flow_output_titles = {p.title for p in spec_flow.outputs}

    assert spec_flow_input_titles == {"x"}

    # check that the exception name has been removed
    assert CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME not in spec_flow_output_titles
    # check that the exception payload has been renamed
    assert CatchExceptionStep.EXCEPTION_PAYLOAD_OUTPUT_NAME not in spec_flow_output_titles
    assert CatchExceptionNode.DEFAULT_EXCEPTION_INFO_VALUE in spec_flow_output_titles


@pytest.fixture
def runtime_flow_catching_specific_exceptions(flaky_wayflow_subflow: RuntimeFlow) -> RuntimeFlow:
    tool_node_with_catch = CatchExceptionStep(
        name="catch_step",
        flow=flaky_wayflow_subflow,
        except_on={ValueError.__name__: "value_error_branch"},
    )
    tool_sucess_output = OutputMessageStep(
        name="success_output_step",
        message_template="Tool succeeded without exceptions.",
    )
    tool_failure_output_step = OutputMessageStep(
        name="failure_output_step",
        message_template="Tool failed with ValueError: {{tool_error}}",
    )
    return RuntimeFlow(
        name="flow_catch_value_error",
        begin_step=tool_node_with_catch,
        control_flow_edges=[
            RuntimeControlFlowEdge(
                source_step=tool_node_with_catch,
                destination_step=tool_sucess_output,
                source_branch=CatchExceptionStep.BRANCH_NEXT,
            ),
            RuntimeControlFlowEdge(
                source_step=tool_node_with_catch,
                destination_step=tool_failure_output_step,
                source_branch="value_error_branch",
            ),
            RuntimeControlFlowEdge(source_step=tool_sucess_output, destination_step=None),
            RuntimeControlFlowEdge(source_step=tool_failure_output_step, destination_step=None),
        ],
        data_flow_edges=[
            RuntimeDataFlowEdge(
                tool_node_with_catch,
                CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME,
                tool_failure_output_step,
                "tool_error",
            ),
        ],
    )


def test_runtime_flow_catching_specific_exceptions_runs_as_expected(
    runtime_flow_catching_specific_exceptions: RuntimeFlow,
) -> None:
    flow = runtime_flow_catching_specific_exceptions

    # flaky case
    conv = flow.start_conversation({"x": -1})
    status = conv.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "exception_name": "ValueError",
        "tool_output": "no_output",
        "exception_payload_name": "x must be non-negative",
        "output_message": "Tool failed with ValueError: ValueError",
    }

    # non-flaky case
    conv2 = flow.start_conversation({"x": 10})
    status = conv2.execute()
    assert isinstance(status, FinishedStatus)
    assert status.output_values == {
        "exception_payload_name": "",
        "tool_output": "ok",
        "exception_name": "",
        "output_message": "Tool succeeded without exceptions.",
    }


def test_wayflow_flow_catching_specific_exceptions_properly_converts_to_agentspec(
    runtime_flow_catching_specific_exceptions: RuntimeFlow,
) -> None:
    spec_flow: SpecFlow = AgentSpecExporter().to_component(
        runtime_flow_catching_specific_exceptions
    )

    # 1. there should be two output message nodes
    node_titles = {n.name for n in spec_flow.nodes}
    assert "success_output_step" in node_titles
    assert "failure_output_step" in node_titles

    # 2. the flow should use the native CatchExceptionNode
    catch_node = next((n for n in spec_flow.nodes if n.name == "catch_step"), None)
    assert (catch_node is not None) and isinstance(catch_node, PluginCatchExceptionNode)

    # 3. check for correct control flow edge connection
    control_flow_edges = {
        (c.from_node.name, c.to_node.name, c.from_branch)
        for c in spec_flow.control_flow_connections
    }
    assert (
        "catch_step",
        "success_output_step",
        Node.DEFAULT_NEXT_BRANCH,
    ) in control_flow_edges or ("catch_step", "success_output_step", None) in control_flow_edges
    assert ("catch_step", "failure_output_step", "value_error_branch") in control_flow_edges

    # 4. check for correct data flow edge connection
    data_flow_edges = {
        (d.source_node.name, d.source_output, d.destination_node.name, d.destination_input)
        for d in spec_flow.data_flow_connections
    }
    assert (
        "catch_step",
        PluginCatchExceptionNode.EXCEPTION_NAME_OUTPUT_NAME,
        "failure_output_step",
        "tool_error",
    ) in data_flow_edges

    # 5. check for input/output
    spec_flow_input_titles = {p.title for p in spec_flow.inputs}
    spec_flow_output_titles = {p.title for p in spec_flow.outputs}

    assert spec_flow_input_titles == {"x"}

    assert PluginCatchExceptionNode.EXCEPTION_NAME_OUTPUT_NAME in spec_flow_output_titles
    assert PluginCatchExceptionNode.EXCEPTION_PAYLOAD_OUTPUT_NAME in spec_flow_output_titles


def test_agentspec_flow_properly_converts_to_wayflow(
    spec_flow_with_catchexception: RuntimeFlow,
) -> None:
    runtime_flow: RuntimeFlow = AgentSpecLoader({"flaky_tool": flaky_tool}).load_component(
        spec_flow_with_catchexception
    )

    # check for correct control flow edge connection
    control_flow_edges = {
        (c.source_step.name, c.destination_step.name, c.source_branch)
        for c in runtime_flow.control_flow_edges
    }
    assert ("catch_step", "success_end", Step.BRANCH_NEXT) in control_flow_edges or (
        "catch_step",
        "success_end",
        None,
    ) in control_flow_edges
    assert (
        "catch_step",
        "error_end",
        CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
    ) in control_flow_edges

    # check for correct data flow edge connection
    data_flow_edges = {
        (d.source_step.name, d.source_output, d.destination_step.name, d.destination_input)
        for d in runtime_flow.data_flow_edges
    }
    assert (
        "catch_step",
        CatchExceptionNode.DEFAULT_EXCEPTION_INFO_VALUE,
        "error_end",
        "error_info",
    ) in data_flow_edges

    # 5. check for input/output
    spec_flow_input_titles = {p.name for p in runtime_flow.input_descriptors}
    spec_flow_output_titles = {p.name for p in runtime_flow.output_descriptors}

    assert spec_flow_input_titles == {"x"}
    assert "error_info" in spec_flow_output_titles
