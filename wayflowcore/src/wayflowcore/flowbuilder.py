# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Literal, Optional, overload

from wayflowcore.agentspec import AgentSpecExporter
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import Property
from wayflowcore.steps import BranchingStep, CompleteStep, StartStep
from wayflowcore.steps.step import Step

DEFAULT_FLOW_NAME = "Flow"


class FlowBuilder:
    """A builder for constructing WayFlow Flows."""

    _begin_step: Step | None

    def __init__(self) -> None:
        self.steps: dict[str, Step] = {}
        self.control_flow_connections: list[ControlFlowEdge] = []
        self.data_flow_connections: list[DataFlowEdge] = []
        self._conditional_edge_counter = 1
        self._end_step_counter = 1
        self._begin_step = None
        self._output_descriptors: list[Property] | None = None

    def add_step(self, step: Step) -> "FlowBuilder":
        """
        Add a new step to the Flow.

        Parameters
        ----------
        step:
            Step to add to the Flow.
        """
        name = step.name
        if name in self.steps:
            raise ValueError(f"Step with name '{name}' already exists")
        self.steps[name] = step
        return self

    def add_edge(
        self,
        source_step: list[Step | str] | Step | str,
        dest_step: Optional[Step | str],
        from_branch: list[str | None] | str | None = None,
        edge_name: str | None = None,
    ) -> "FlowBuilder":
        """
        Add a control flow edge to the Flow.

        Parameters
        ----------
        source_step:
            Single step/name (creates 1 edge) or list of steps/names (creates N edges)
            which constitute the start of the control flow edge(s).
        dest_step:
            Step/name that constitutes the end of the control flow edge(s). Pass ``None`` to finish the flow
            from the source step(s).
        from_branch:
            Optional source branch name(s) to use in the control flow edge(s).
            When a list, must be of the same length as the list of ``source_step``.
        edge_name:
            Name for the edge. Defaults to f"control_edge_{source_step.name}_{dest_step.name}_{from_branch}".
        """
        start_step_list = source_step if isinstance(source_step, list) else [source_step]
        from_branch_list = from_branch if isinstance(from_branch, list) else [from_branch]

        if len(start_step_list) != len(from_branch_list):
            raise ValueError("source_step and from_branch must have the same length")

        destination_step = (
            None
            if dest_step is None or dest_step == "None"
            else self._get_step(dest_step, prefix_err_msg="End step")
        )

        for start_key_, from_branch_ in zip(start_step_list, from_branch_list):
            source_step_ = self._get_step(start_key_, prefix_err_msg="Start step")
            source_branch = from_branch_ if from_branch_ is not None else source_step_.BRANCH_NEXT
            dest_name = destination_step.name if destination_step else "END"
            self.control_flow_connections.append(
                ControlFlowEdge(
                    source_step=source_step_,
                    destination_step=destination_step,
                    source_branch=source_branch,
                    name=edge_name
                    or f"control_edge_{source_step_.name}_{dest_name}_{source_branch}",
                )
            )
        return self

    def add_data_edge(
        self,
        source_step: Step | str,
        dest_step: Step | str,
        data_name: str | tuple[str, str],
        edge_name: str | None = None,
    ) -> "FlowBuilder":
        """
        Add a data flow edge to the Flow.

        Parameters
        ----------
        source_step:
            Step/name which constitutes the start/source of the data flow edge.
        dest_step:
            Step/name that constitutes the end/destination of the data flow edge.
        data_name:
            Name of the data property to propagate between the two steps, either
            str when the name is shared, or tuple (source_output, destination_input)
            when the names are different.
        edge_name:
            Name for the edge. Defaults to "data_flow_edge"
        """

        source_step_ = self._get_step(source_step, prefix_err_msg="Source step")
        dest_step_ = self._get_step(dest_step, prefix_err_msg="Destination step")

        # Validate data_name
        if isinstance(data_name, tuple):
            if len(data_name) != 2 or not all(isinstance(x, str) for x in data_name):
                raise ValueError("data_name tuple must be (str, str)")
            source_output, dest_input = data_name
        elif isinstance(data_name, str):
            source_output, dest_input = data_name, data_name
        else:
            raise ValueError("data_name must be str or tuple[str, str]")

        self.data_flow_connections.append(
            DataFlowEdge(
                name=edge_name or "data_flow_edge",
                source_step=source_step_,
                source_output=source_output,
                destination_step=dest_step_,
                destination_input=dest_input,
            )
        )
        return self

    def add_sequence(self, steps: list[Step]) -> "FlowBuilder":
        """
        Add a sequence of steps to the Flow and automatically
        creates control flow edges between them.

        Parameters
        ----------
        steps:
            List of steps to add to the Flow.
        """
        # Add all steps first (allows mixing with other builder calls)
        for step_ in steps:
            self.add_step(step_)

        # Then wire control flow edges between consecutive steps
        if len(steps) > 1:
            for left, right in zip(steps[:-1], steps[1:]):
                self.add_edge(left, right)

        return self

    def add_conditional(
        self,
        source_step: Step | str,
        source_value: str | tuple[Step | str, str],
        destination_map: dict[str, Step | str],
        default_destination: Step | str,
        branching_step_name: str | None = None,
    ) -> "FlowBuilder":
        """
        Add a condition/branching to the Flow.

        Parameters
        ----------
        source_step:
            Step/name from which to start the branching from.
        source_value:
            Which value to use to perform the branching condition. If str, uses the `source_step`.
            If `tuple[Step | str, str]`, uses the specified step and output name.
        destination_map:
            Dictionary which specifies which step to transition to for given input values.
        default_destination:
            Step/name where to transition to if no matching value/transition is found
            in the `destination_map`.
        branching_step_name:
            Optional name for the branching step. Uses automatically generated auto-incrementing
            names if not providing.

        Example
        -------
        >>> from wayflowcore.flowbuilder import FlowBuilder
        >>> from wayflowcore.steps import OutputMessageStep
        >>>
        >>> flow = (
        ...     FlowBuilder()
        ...     .add_step(OutputMessageStep(name="source_step", message_template="{{ value }}"))
        ...     .add_step(OutputMessageStep(name="fail_step", message_template="FAIL"))
        ...     .add_step(OutputMessageStep(name="success_step", message_template="SUCCESS"))
        ...     .add_conditional("source_step", OutputMessageStep.OUTPUT,
        ...                      {"success": "success_step", "fail": "fail_step"},
        ...                      default_destination="fail_step"
        ...     )
        ...     .set_entry_point("source_step")
        ...     .set_finish_points(["fail_step", "success_step"])
        ...     .build()
        ... )

        """
        if branching_step_name:
            conditional_step_name = branching_step_name
        else:
            conditional_step_name = f"BranchingStep_{self._conditional_edge_counter}"
            self._conditional_edge_counter += 1

        destination_map_str = {
            k: (n.name if isinstance(n, Step) else n) for k, n in destination_map.items()
        }
        # In WayFlow: BranchingStep maps input value -> branch label; we use destination step names as branch labels
        self.add_step(
            BranchingStep(
                name=conditional_step_name,
                branch_name_mapping=destination_map_str,
            )
        )

        # Prevent user from colliding with default branch name
        if BranchingStep.BRANCH_DEFAULT in destination_map_str.values():
            raise ValueError(
                f"destination_map cannot contain reserved branch label '{BranchingStep.BRANCH_DEFAULT}'. "
                "Please use `default_destination` instead."
            )

        # adding control flow edges
        self.add_edge(source_step, conditional_step_name)
        for destination_step_name in destination_map_str.values():
            self.add_edge(conditional_step_name, destination_step_name, destination_step_name)

        self.add_edge(conditional_step_name, default_destination, BranchingStep.BRANCH_DEFAULT)

        # adding data flow edge for the input to the branching step
        if source_value:
            source_step_ = source_step if not isinstance(source_value, tuple) else source_value[0]
            source_value_ = source_value if not isinstance(source_value, tuple) else source_value[1]
            self.add_data_edge(
                source_step_,
                conditional_step_name,
                (source_value_, BranchingStep.NEXT_BRANCH_NAME),
            )
        return self

    def set_entry_point(
        self, step: Step | str, input_descriptors: list[Property] | None = None
    ) -> "FlowBuilder":
        """
        Sets the first step to execute in the Flow.

        Parameters
        ----------
        step:
            Step/name that will first be run in the Flow.
        input_descriptors:
            Optional list of inputs for the flow. If `None`, auto-detects as the list of
            inputs that are not generated at some point in the execution of the flow.
        """
        if self._begin_step is not None:
            raise ValueError("Entry point already set; set_entry_point cannot be called twice")

        if input_descriptors is None:
            # No explicit start step; directly set the begin step
            # Ensure target exists to fail fast
            self._begin_step = self._get_step(step, prefix_err_msg="Start step")
        else:
            start_step_name = Flow._DEFAULT_STARTSTEP_NAME
            start_step = StartStep(name=start_step_name, input_descriptors=input_descriptors)
            self.add_step(start_step)
            self._begin_step = start_step
            self.add_edge(start_step_name, step)
        return self

    def set_finish_points(
        self,
        step: list[Step | str] | Step | str,
        output_descriptors: list[Property] | None = None,
    ) -> "FlowBuilder":
        """
        Specifies the potential points of completion of the Flow.

        Parameters
        ----------
        step:
            Step/name or list of steps/names which are terminal steps in the Flow.
        output_descriptors:
            Optional list of outputs for the flow. If `None`, auto-detects as the
            intersection of all the outputs generated by any step in any execution
            branch of the flow.

        """
        source_step_list = step if isinstance(step, list) else [step]
        self._output_descriptors = output_descriptors

        for source_key in source_step_list:
            end_step_name = f"CompleteStep_{self._end_step_counter}"
            self._end_step_counter += 1
            self.add_step(CompleteStep(name=end_step_name))
            self.add_edge(source_key, end_step_name)
        return self

    def build(self, name: str = DEFAULT_FLOW_NAME, description: str = "") -> Flow:
        """
        Build the Flow.

        Will raise errors if encountering any while building the Flow.

        Examples
        --------

        >>> from wayflowcore.flowbuilder import FlowBuilder
        >>> from wayflowcore.steps import OutputMessageStep
        >>>
        >>> n1 = OutputMessageStep(name="n1", message_template="Hello")
        >>> n2 = OutputMessageStep(name="n2", message_template="World")
        >>>
        >>> flow = (
        ...     FlowBuilder()
        ...     .add_sequence([n1, n2])
        ...     .set_entry_point(n1)
        ...     .set_finish_points(n2)
        ...     .build()
        ... )

        """
        # Determine start step: prefer explicitly set via set_entry_point,
        # otherwise accept a single StartStep added manually.
        if self._begin_step is not None:
            start_step_obj = self._begin_step
        else:
            start_steps = [s for s in self.steps.values() if isinstance(s, StartStep)]
            if len(start_steps) == 1:
                start_step_obj = start_steps[0]
            else:
                # Either none or ambiguous; require explicit entry point
                raise ValueError("Missing start step")

        # Build the WayFlow Flow instance
        return Flow(
            begin_step=start_step_obj,
            steps=list(self.steps.values()),
            control_flow_edges=self.control_flow_connections,
            data_flow_edges=self.data_flow_connections,
            name=name,
            description=description,
            output_descriptors=self._output_descriptors,
        )

    def build_agent_spec(
        self, name: str = DEFAULT_FLOW_NAME, serialize_as: Literal["JSON", "YAML"] = "JSON"
    ) -> str:
        """
        Build the Flow and return its Agent Spec JSON or YAML configuration.

        Will raise errors if encountering any while building the Flow.
        """
        flow = self.build(name)
        if serialize_as == "JSON":
            return AgentSpecExporter().to_json(flow)
        elif serialize_as == "YAML":
            return AgentSpecExporter().to_yaml(flow)
        else:
            raise ValueError(
                f"Incorrect serialization format {serialize_as}. "
                "Allowed values are 'JSON' and 'YAML'"
            )

    @overload
    @classmethod
    def build_linear_flow(
        cls,
        steps: list[Step],
        name: str = DEFAULT_FLOW_NAME,
        serialize_as: Literal[None] = None,
        data_flow_edges: list[DataFlowEdge] | None = None,
        input_descriptors: list[Property] | None = None,
        output_descriptors: list[Property] | None = None,
    ) -> Flow: ...

    @overload
    @classmethod
    def build_linear_flow(
        cls,
        steps: list[Step],
        name: str = DEFAULT_FLOW_NAME,
        serialize_as: Literal["JSON", "YAML"] = "JSON",
        data_flow_edges: list[DataFlowEdge] | None = None,
        input_descriptors: list[Property] | None = None,
        output_descriptors: list[Property] | None = None,
    ) -> str: ...

    @classmethod
    def build_linear_flow(
        cls,
        steps: list[Step],
        name: str = DEFAULT_FLOW_NAME,
        serialize_as: Literal["JSON", "YAML"] | None = None,
        data_flow_edges: list[DataFlowEdge] | None = None,
        input_descriptors: list[Property] | None = None,
        output_descriptors: list[Property] | None = None,
    ) -> Flow | str:
        """
        Build a linear flow from a list of steps.

        Parameters
        ----------
        steps:
            List of steps to use to create the linear/sequential Flow.
        serialize_as:
            Format for the returned object. If `None`, returns a WayFlow `Flow`.
            Otherwise, returns its Agent Spec configuration as JSON/YAML.
        data_flow_edges:
            Optional list of data flow edges.
        input_descriptors:
            Optional list of inputs for the flow. If `None`, auto-detects as the list of
            inputs that are not generated at some point in the execution of the flow.
        output_descriptors:
            Optional list of outputs for the flow. If `None`, auto-detects as the
            intersection of all the outputs generated by any step in any execution
            branch of the flow.

        """
        flow = Flow.from_steps(
            name=name,
            steps=steps,
            data_flow_edges=data_flow_edges,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
        )
        if serialize_as == "JSON":
            return AgentSpecExporter().to_json(flow)
        elif serialize_as == "YAML":
            return AgentSpecExporter().to_yaml(flow)
        else:
            return flow

    def _get_step(self, step_or_name: Step | str, prefix_err_msg: str = "Step with name") -> Step:
        step_name = step_or_name.name if isinstance(step_or_name, Step) else step_or_name

        if step_name not in self.steps:
            raise ValueError(f"{prefix_err_msg} '{step_name}' not found")

        return self.steps[step_name]

    def _get_step_name(
        self, step_or_name: Step | str, prefix_err_msg: str = "Step with name"
    ) -> str:
        if isinstance(step_or_name, str):
            return step_or_name

        return self._get_step(step_or_name, prefix_err_msg).name
