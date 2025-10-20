# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Optional, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmModel, VllmModel
from wayflowcore.property import (
    AnyProperty,
    BooleanProperty,
    IntegerProperty,
    ListProperty,
    Property,
    StringProperty,
)
from wayflowcore.steps import InputMessageStep, ToolExecutionStep
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import DescribedFlow, tool

from ..testhelpers.dummy import DummyModel


def _map_value_to_type(value: Union[List[str], str]) -> Property:
    if isinstance(value, list):
        return (
            ListProperty(item_type=_map_value_to_type(value[0]))
            if len(value) > 0
            else ListProperty(item_type=AnyProperty())
        )
    if isinstance(value, str):
        return StringProperty()
    if isinstance(value, int):
        return IntegerProperty()
    if isinstance(value, bool):
        return BooleanProperty()
    raise ValueError(f"No type for {value}")


class _AddCustomValuesToContextStep(Step):
    def __init__(self, expected_outputs: Dict[str, Any]) -> None:
        super().__init__(
            input_mapping=None,
            output_mapping=None,
            __metadata_info__=None,
            step_static_configuration=dict(
                expected_outputs=expected_outputs,
            ),
            input_descriptors=None,
            output_descriptors=None,
        )
        self.expected_outputs = expected_outputs

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        return {"expected_outputs": str}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        expected_outputs: Dict[str, Any],
    ) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        expected_outputs: Dict[str, Any],
    ) -> List[Property]:
        return [
            _map_value_to_type(value).copy(name=key, description=key)
            for key, value in expected_outputs.items()
        ]

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: FlowConversation,
    ) -> StepResult:

        return StepResult(outputs=self.expected_outputs)


class _InputOutputSpecifiedStep(Step):
    def __init__(
        self,
        inputs: Optional[List[Union[str, Property]]] = None,
        outputs: Optional[List[Union[str, Property]]] = None,
        output_values: Optional[Dict[str, Any]] = None,
        branch_out: Optional[List[Optional[str]]] = None,
        input_mapping: Dict[str, str] = None,
        output_mapping: Dict[str, str] = None,
    ) -> None:
        if inputs is None:
            inputs = []
        if outputs is None:
            outputs = []
        if output_values is None:
            output_values = dict()
        super().__init__(
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(
                inputs=inputs,
                outputs=outputs,
                output_values=output_values,
                branch_out=branch_out,
            ),
            input_descriptors=None,
            output_descriptors=None,
            __metadata_info__=None,
        )
        self.branch_out = branch_out
        self.inputs = inputs
        self.outputs = outputs
        self.output_values = output_values

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "inputs": str,
            "outputs": str,
            "output_values": str,
            "branch_out": str,
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        inputs: List[Union[str, Property]],
        outputs: List[Union[str, Property]],
        output_values: Dict[str, Any],
        branch_out: Optional[List[Optional[str]]],
    ) -> List[Property]:
        return [
            (StringProperty(name=x, description=x) if isinstance(x, str) else x) for x in inputs
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        inputs: List[Union[str, Property]],
        outputs: List[Union[str, Property]],
        output_values: Dict[str, Any],
        branch_out: Optional[List[Optional[str]]],
    ) -> List[Property]:
        return [
            (StringProperty(name=x, description=x) if isinstance(x, str) else x) for x in outputs
        ]

    @classmethod
    def _compute_internal_branches_from_static_config(
        cls,
        inputs: List[Union[str, Property]],
        outputs: List[Union[str, Property]],
        output_values: Dict[str, Any],
        branch_out: Optional[List[Optional[str]]],
    ) -> List[str]:
        # We always have a single next step, but we don't know which just based on config
        # it is set in the flow transitions
        return [cls.BRANCH_NEXT] if branch_out is None else branch_out

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: FlowConversation,
    ) -> StepResult:

        next_step_name = (
            next(
                m.content
                for m in conversation.get_messages()[::1]
                if m.message_type == MessageType.USER
            )
            if self.branch_out is not None
            else self.BRANCH_NEXT
        )

        return StepResult(
            outputs={
                k.name: self.output_values.get(k.name, k.name) for k in self.output_descriptors
            },
            branch_name=next_step_name,
            step_type=StepExecutionStatus.PASSTHROUGH,
        )


class FakeStep(Step):
    def __init__(
        self,
        llm: Optional[LlmModel] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        super().__init__(
            llm=llm,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            step_static_configuration=dict(llm=llm),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            __metadata_info__=__metadata_info__,
        )

    # override
    @property
    def might_yield(self) -> bool:
        """
        Indicates that this step might yield (it always does).
        """
        return True

    def _invoke_step(
        self,
        inputs: Dict[str, str],
        conversation: FlowConversation,
    ) -> StepResult:
        conversation.append_message(Message(content=str(inputs)))
        outputs = {"output_1": "o1", "output_2": "o2"}
        return StepResult(outputs, self.BRANCH_SELF, StepExecutionStatus.YIELDING)

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {"llm": Optional[LlmModel]}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls, llm: Optional[LlmModel]
    ) -> List[Property]:
        return [
            StringProperty("input_1"),
            StringProperty("input_2"),
            StringProperty("input_3", default_value="default_value"),
        ]

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls, llm: Optional[LlmModel]
    ) -> List[Property]:
        return [
            StringProperty("output_1"),
            StringProperty("output_2"),
        ]


def create_naming_flow(llms: Optional[Union[List[VllmModel], List[DummyModel]]]) -> DescribedFlow:

    @tool(description_mode="only_docstring")
    def register_name(name: str) -> str:
        """Registers a given name"""
        return str({"dashboard_name": name})

    USER_INPUT = "user_input"
    REGISTERING_NAME = "registering_name"
    naming_flow = Flow.from_steps(
        steps=[
            InputMessageStep("Please choose a name for the dashboard"),
            ToolExecutionStep(
                tool=register_name,
                input_mapping={"name": InputMessageStep.USER_PROVIDED_INPUT},
            ),
        ]
    )

    return DescribedFlow(
        flow=naming_flow,
        name="naming_tool",
        description="A naming tool. It needs to be called to define any dashboard name. No inputs. Returns the chosen name for the dashboard",
        output="tool_output",
    )


def create_forecasting_flow(
    llms: Optional[Union[List[VllmModel], List[DummyModel]]],
) -> DescribedFlow:

    @tool(description_mode="only_docstring")
    def forecast_data(horizon: str = "5") -> str:
        """Forecast data given a horizon (in number of days between 1 and 7)"""
        data = [27, 28, 24, 21, 25, 29, 24][: int(horizon)]
        return f"{data}"

    input_step = InputMessageStep("Please choose a forecasting horizon (in weeks, between 1 and 7)")
    tool_step = ToolExecutionStep(
        tool=forecast_data,
        input_mapping={"horizon": InputMessageStep.USER_PROVIDED_INPUT},
    )
    dsa_flow = Flow(
        begin_step=input_step,
        steps={
            "user_input": input_step,
            "forecasting_data": tool_step,
        },
        control_flow_edges=[
            ControlFlowEdge(source_step=input_step, destination_step=tool_step),
            ControlFlowEdge(source_step=tool_step, destination_step=None),
        ],
    )

    return DescribedFlow(
        flow=dsa_flow,
        name="forecasting_tool",
        description="A tool to forecast weather data. No inputs",
        output="tool_output",
    )
