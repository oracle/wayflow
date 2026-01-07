# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json

import pytest

from wayflowcore.flow import Flow
from wayflowcore.flowbuilder import FlowBuilder
from wayflowcore.steps import BranchingStep
from wayflowcore.steps.constantvaluesstep import ConstantValuesStep
from wayflowcore.steps.outputmessagestep import OutputMessageStep

_DEFAULT_STARTSTEP_NAME = Flow._DEFAULT_STARTSTEP_NAME


def test_build_simple_flow_with_single_step():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="s", message_template="Hello"))
    builder.set_entry_point("s")
    builder.set_finish_points("s")
    flow = builder.build()

    # Basic structure checks
    step_names = set(flow.steps.keys())
    assert _DEFAULT_STARTSTEP_NAME in step_names
    assert "s" in step_names
    # Should have: StartStep->s and s->None
    assert len(flow.control_flow_edges) == 2
    assert len(flow.data_flow_edges) == 0


def test_build_linear_flow_with_explicit_edge():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="s1", message_template="A"))
    builder.add_step(OutputMessageStep(name="s2", message_template="B"))
    builder.add_edge("s1", "s2")
    builder.set_entry_point("s1")
    builder.set_finish_points("s2")
    flow = builder.build()

    step_names = set(flow.steps.keys())
    assert {_DEFAULT_STARTSTEP_NAME, "s1", "s2", "CompleteStep_1"} == step_names
    # Edges: StartStep->s1, s1->s2, s2->None
    assert len(flow.control_flow_edges) == 3


def test_add_sequence_builds_linear_flow():
    builder = FlowBuilder()
    builder.add_sequence(
        [
            OutputMessageStep(name="s1", message_template="A"),
            OutputMessageStep(name="s2", message_template="B"),
        ]
    )
    builder.set_entry_point("s1")
    builder.set_finish_points("s2")
    flow = builder.build()

    step_names = set(flow.steps.keys())
    assert _DEFAULT_STARTSTEP_NAME in step_names
    assert "s1" in step_names
    assert "s2" in step_names


def test_build_spec_returns_valid_json():
    builder = FlowBuilder()
    builder.add_sequence(
        [
            OutputMessageStep(name="s1", message_template="A"),
            OutputMessageStep(name="s2", message_template="B"),
        ]
    )
    builder.set_entry_point("s1")
    builder.set_finish_points("s2")
    spec_json = builder.build_agent_spec()
    parsed = json.loads(spec_json)
    assert isinstance(parsed, dict)
    assert parsed.get("name") == "Flow"


def test_flow_with_conditional_transition():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="decider", message_template="{{ value }}"))
    builder.add_step(OutputMessageStep(name="fail", message_template="FAIL"))
    builder.add_step(OutputMessageStep(name="success", message_template="SUCCESS"))
    builder.add_conditional(
        "decider",
        OutputMessageStep.OUTPUT,
        {"success": "success", "fail": "fail"},
        default_destination="fail",
    )
    builder.set_entry_point("decider")
    builder.set_finish_points(["success", "fail"])
    flow = builder.build()

    # There should be a BranchingStep injected
    branch_steps = [s for s in flow.steps.values() if isinstance(s, BranchingStep)]
    assert len(branch_steps) == 1
    # Control edges include:
    # StartStep->decider, decider->branch, branch->success, branch->fail, branch->default(fail),
    # plus finish edges from success/fail (2)
    assert len(flow.control_flow_edges) == 7


def test_flow_with_data_connections():
    builder = FlowBuilder()
    builder.add_step(ConstantValuesStep(name="producer", constant_values={"generated_text": "hi"}))
    builder.add_step(OutputMessageStep(name="consumer1", message_template="{{ generated_text }}"))
    builder.add_step(OutputMessageStep(name="consumer2", message_template="{{ also_value }}"))
    builder.add_edge("producer", "consumer1")
    builder.add_edge("consumer1", "consumer2")

    builder.add_data_edge("producer", "consumer1", "generated_text")
    builder.add_data_edge("producer", "consumer2", ("generated_text", "also_value"))

    builder.set_entry_point("producer")
    builder.set_finish_points(["consumer2"])  # linear chain with two data edges from producer
    flow = builder.build()

    assert len(flow.data_flow_edges) == 2
    data_edges = {
        (e.source_step.name, e.destination_step.name, e.source_output, e.destination_input)
        for e in flow.data_flow_edges
    }
    assert ("producer", "consumer1", "generated_text", "generated_text") in data_edges
    assert ("producer", "consumer2", "generated_text", "also_value") in data_edges


def test_add_edge_raises_when_end_step_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="a", message_template="x"))
    with pytest.raises(ValueError, match="End step 'b' not found"):
        builder.add_edge("a", "b")


def test_add_edge_raises_when_start_step_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="b", message_template="x"))
    with pytest.raises(ValueError, match="Start step 'a' not found"):
        builder.add_edge("a", "b")


def test_add_edge_raises_on_length_mismatch_between_starts_and_branches():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="a", message_template="x"))
    builder.add_step(OutputMessageStep(name="b", message_template="x"))
    # source_step has 2 entries; from_branch has 1
    with pytest.raises(ValueError, match="source_step and from_branch must have the same length"):
        builder.add_edge(source_step=["a", "a"], dest_step="b", from_branch=[None])


def test_add_step_raises_on_duplicate_name():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="dup", message_template="x"))
    with pytest.raises(ValueError, match="Step with name 'dup' already exists"):
        builder.add_step(OutputMessageStep(name="dup", message_template="y"))


def test_add_data_edge_raises_when_source_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="dst", message_template="{{ out }}"))
    with pytest.raises(ValueError, match="Source step 'src' not found"):
        builder.add_data_edge("src", "dst", "out")


def test_add_data_edge_raises_when_destination_missing():
    builder = FlowBuilder()
    builder.add_step(ConstantValuesStep(name="src", constant_values={"out": "x"}))
    with pytest.raises(ValueError, match="Destination step 'dst' not found"):
        builder.add_data_edge("src", "dst", "out")


def test_add_sequence_works_in_combination_with_add_step():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="x", message_template="x"))
    builder.add_sequence([OutputMessageStep(name="y", message_template="y")])
    builder.add_edge("x", "y")
    builder.set_entry_point("x")
    builder.set_finish_points("y")
    flow = builder.build()
    # Ensure there is an edge from x to y (plus start and finish)
    edges = {
        (e.source_step.name, (e.destination_step.name if e.destination_step else None))
        for e in flow.control_flow_edges
    }
    assert ("x", "y") in {(a, b) for (a, b) in edges if b is not None}


def test_build_raises_when_start_step_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="x", message_template="x"))
    with pytest.raises(ValueError, match="Missing start step"):
        builder.build()


def test_set_entry_point_raises_when_target_step_missing():
    builder = FlowBuilder()
    # set_entry_point will try to add an edge StartStep->unknown and should raise via add_edge
    with pytest.raises(ValueError, match="Start step 'unknown' not found"):
        builder.set_entry_point("unknown")


def test_add_conditional_edges_raises_when_source_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="success", message_template="x"))
    with pytest.raises(ValueError, match="Start step 'llm' not found"):
        builder.add_conditional(
            "llm", "result", {"success": "success"}, default_destination="success"
        )


def test_add_conditional_edges_raises_when_destination_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="step", message_template="x"))
    # Destination 'missing' doesn't exist
    with pytest.raises(ValueError, match="End step 'missing' not found"):
        builder.add_conditional(
            "step", "result", {"missing": "missing"}, default_destination="missing"
        )


def test_add_conditional_with_tuple_source_value():
    # Build a small graph where the conditional takes value from another step
    builder = FlowBuilder()
    builder.add_step(ConstantValuesStep(name="producer", constant_values={"flag": "true"}))
    builder.add_step(OutputMessageStep(name="step", message_template="Hello"))
    builder.add_step(OutputMessageStep(name="false_branch", message_template="Hello"))
    builder.add_step(OutputMessageStep(name="true_branch", message_template="Hello"))
    builder.add_conditional(
        source_step="step",
        source_value=("producer", "flag"),
        destination_map={"true": "true_branch"},
        default_destination="false_branch",
    )
    builder.add_edge("producer", "step")
    builder.set_entry_point("producer")
    builder.set_finish_points(["true_branch", "false_branch"])  # alias method
    flow = builder.build()
    # Ensure data edge from producer to the branching step exists
    assert any(
        e.source_step.name == "producer" and isinstance(e.destination_step, BranchingStep)
        for e in flow.data_flow_edges
    )


def test_build_linear_flow_returns_flow_and_json():
    from wayflowcore.steps import OutputMessageStep

    s1 = OutputMessageStep(name="s1", message_template="A")
    s2 = OutputMessageStep(name="s2", message_template="B")

    # Flow object
    flow = FlowBuilder.build_linear_flow([s1, s2], name="MyFlow")
    assert flow.name == "MyFlow"
    assert set(flow.steps.keys()) >= {"s1", "s2"}

    # JSON spec
    spec_json = FlowBuilder.build_linear_flow([s1, s2], serialize_as="JSON")
    parsed = json.loads(spec_json)
    assert parsed.get("name") == "Flow"


def test_set_entry_point_cannot_be_called_twice():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="s", message_template="x"))
    builder.set_entry_point("s")
    with pytest.raises(ValueError, match="Entry point already set"):
        builder.set_entry_point("s")


def test_add_data_edge_validates_data_name_tuple_shape():
    builder = FlowBuilder()
    builder.add_step(ConstantValuesStep(name="src", constant_values={"out": "x"}))
    builder.add_step(OutputMessageStep(name="dst", message_template="{{ out }}"))
    # wrong length tuple
    with pytest.raises(ValueError, match="data_name tuple must be"):
        builder.add_data_edge("src", "dst", ("a", "b", "c"))
    # wrong types
    with pytest.raises(ValueError, match="data_name tuple must be"):
        builder.add_data_edge("src", "dst", (1, "b"))  # type: ignore


def test_add_data_edge_raises_when_step_instances_not_added():
    src = ConstantValuesStep(name="src", constant_values={"out": "x"})
    dst = OutputMessageStep(name="dst", message_template="{{ out }}")
    builder = FlowBuilder()
    # Add only destination
    builder.add_step(dst)
    with pytest.raises(ValueError, match="Source step 'src' not found"):
        builder.add_data_edge(src, dst, "out")
    # Now add source but not destination
    builder2 = FlowBuilder()
    builder2.add_step(src)
    with pytest.raises(ValueError, match="Destination step 'dst' not found"):
        builder2.add_data_edge(src, dst, "out")


def test_add_conditional_rejects_default_label_in_mapping():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="decider", message_template="{{ value }}"))
    builder.add_step(OutputMessageStep(name="A", message_template="A"))
    with pytest.raises(ValueError, match="reserved branch label"):
        builder.add_conditional(
            "decider",
            OutputMessageStep.OUTPUT,
            {"some_value": BranchingStep.BRANCH_DEFAULT},
            default_destination="A",
        )


def test_add_conditional_raises_when_default_destination_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="src", message_template="x"))
    builder.add_step(OutputMessageStep(name="ok", message_template="ok"))
    with pytest.raises(ValueError, match="End step 'missing' not found"):
        builder.add_conditional(
            "src", OutputMessageStep.OUTPUT, {"v": "ok"}, default_destination="missing"
        )


def test_add_conditional_raises_when_one_mapping_destination_missing():
    builder = FlowBuilder()
    builder.add_step(OutputMessageStep(name="src", message_template="x"))
    builder.add_step(OutputMessageStep(name="ok", message_template="ok"))
    with pytest.raises(ValueError, match="End step 'missing' not found"):
        builder.add_conditional(
            "src", OutputMessageStep.OUTPUT, {"v": "missing"}, default_destination="ok"
        )
