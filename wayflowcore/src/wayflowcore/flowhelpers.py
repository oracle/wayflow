# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Any, Dict, List, Optional, Tuple, Union

from wayflowcore.contextproviders import ContextProvider
from wayflowcore.conversation import ContextProviderType, Conversation
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import ExecutionStatus, FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step
from wayflowcore.tools import ServerTool
from wayflowcore.variable import Variable


def run_step_and_return_outputs(
    step: Step,
    inputs: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Message]] = None,
    context_providers: Optional[List[ContextProvider]] = None,
) -> Dict[str, Any]:
    """Helper function to run a step with some inputs and return the outputs of the step.

    Parameters
    ----------
    step:
        Step to run
    inputs:
        Inputs for the step. Need to contain all expected inputs of the step. Their names and types
        can be checked using ``step.input_descriptors``.
    messages:
        List of previous messages
    user_input:
        Initial message from the user

    Examples
    --------

    >>> from wayflowcore.steps import PromptExecutionStep
    >>> from wayflowcore.flowhelpers import run_step_and_return_outputs
    >>> step = PromptExecutionStep(
    ...     llm=llm,
    ...     prompt_template="What is the capital of {{country}}?"
    ... )
    >>> outputs = run_step_and_return_outputs(step, inputs={'country': 'Switzerland'})
    >>> # {"output": "the capital of Switzerland is Bern"}

    """
    flow = Flow.from_steps([step], context_providers=context_providers)
    return run_flow_and_return_outputs(flow, inputs, messages=messages)


async def run_step_and_return_outputs_async(
    step: Step, inputs: Dict[str, Any] | None = None
) -> Dict[str, Any]:

    flow = create_single_step_flow(step)
    conversation = flow.start_conversation(inputs or {})
    status = await conversation.execute_async()
    if not isinstance(status, FinishedStatus):
        raise RuntimeError("The flow execution did not complete as expected.")
    return status.output_values 


def run_flow_and_return_outputs(
    flow: Flow,
    inputs: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Message]] = None,
) -> Dict[str, Any]:
    """
    Runs a `Flow` until completion and returns the outputs of the flow. It should not use any `ClientTool` nor `Agent`.

    Parameters
    ----------
    flow:
        Flow to run
    inputs:
        Inputs for the flow. Need to contain all expected inputs of the flow. Their names and types
        can be checked using ``flow.input_descriptors``.
    messages:
        Initial messages of the conversation

    Examples
    --------

    >>> from wayflowcore.steps import PromptExecutionStep, BranchingStep, OutputMessageStep
    >>> from wayflowcore.controlconnection import ControlFlowEdge
    >>> from wayflowcore.flow import Flow
    >>> from wayflowcore.flowhelpers import run_flow_and_return_outputs
    >>> generation_step = PromptExecutionStep(
    ...     llm=llm,
    ...     prompt_template="What is the capital of {{country}}? Only answer by the name of city, and the name of the city only.",
    ...     name='generation',
    ... )
    >>> branching_step = BranchingStep(
    ...     branch_name_mapping={'bern': 'success'}, name='branching'
    ... )
    >>> success_step = OutputMessageStep('Well done, llama!', name='success')
    >>> failure_step = OutputMessageStep("That's not it...", name='failure')
    >>> flow = Flow(
    ...     begin_step=generation_step,
    ...     control_flow_edges=[
    ...         ControlFlowEdge(source_step=generation_step, destination_step=branching_step),
    ...         ControlFlowEdge(source_step=branching_step, destination_step=success_step, source_branch='success'),
    ...         ControlFlowEdge(source_step=branching_step, destination_step=failure_step, source_branch=branching_step.BRANCH_DEFAULT),
    ...         ControlFlowEdge(source_step=success_step, destination_step=None),
    ...         ControlFlowEdge(source_step=failure_step, destination_step=None),
    ...     ],
    ... )
    >>> outputs = run_flow_and_return_outputs(flow, inputs={'country': 'Switzerland'})

    """
    status = _run_flow_and_return_status(flow, inputs, messages)
    if not isinstance(status, FinishedStatus):
        raise RuntimeError("The flow execution did not complete as expected.")
    return status.output_values


def create_single_step_flow(
    step: Step,
    step_name: str = "single_step",
    context_providers: Optional[
        Union[Dict[Property, ContextProviderType], List[ContextProvider]]
    ] = None,
    data_flow_edges: Optional[List[DataFlowEdge]] = None,
    variables: Optional[List["Variable"]] = None,
    flow_name: Optional[str] = None,
    flow_description: str = "",
) -> Flow:
    """Create a flow that consist of one step only

    Parameters
    ----------
    step:
        the step that this flow should consist of
    step_name:
        the name of the single step
    context_providers:
        context providers that should be available to the assistant
    data_flow_edges:
        list of data flow edges
    variables:
        list of variables of the flow
    flow_name:
        optional name of the flow
    flow_description:
        optional description of the flow
    """
    if isinstance(context_providers, dict):
        from wayflowcore.contextproviders import ToolContextProvider

        context_providers = [
            ToolContextProvider(
                tool=ServerTool(
                    func=func,
                    name="",
                    description="",
                    input_descriptors=[],
                    output_descriptors=[prop_],
                )
            )
            for prop_, func in context_providers.items()
        ]
    return Flow.from_steps(
        steps=[step],
        step_names=[step_name],
        context_providers=context_providers,
        data_flow_edges=data_flow_edges,
        variables=variables,
        name=flow_name,
        description=flow_description,
    )


def _run_single_step_to_finish(
    step: Step,
    inputs: Optional[Dict[str, Any]] = None,
    user_input: str = "",
    messages: Optional[List[Message]] = None,
    context_providers: Optional[
        Union[Dict[Property, ContextProviderType], List[ContextProvider]]
    ] = None,
) -> Dict[str, Any]:
    conv, status = _run_single_step_and_return_conv_and_status(
        step, inputs, user_input, messages, context_providers
    )
    if not isinstance(status, FinishedStatus):
        raise RuntimeError("The flow execution did not complete as expected.")
    return status.output_values


def run_single_step(
    step: Step,
    inputs: Optional[Dict[str, Any]] = None,
    user_input: str = "",
    messages: Optional[List[Message]] = None,
    context_providers: Optional[
        Union[Dict[Property, ContextProviderType], List[ContextProvider]]
    ] = None,
) -> Tuple["Conversation", List[Message]]:
    """Run a single step given some input parameters.

    Parameters
    ----------
    step
        the step to run
    inputs
        the inputs to provide to the assistant
    user_input
        the input from the user
    messages
        the list of previous messages
    context_providers
        context providers that should be available to the assistant

    Returns
    -------
        the resulting conversation and the new list of messages
    """
    conv, status = _run_single_step_and_return_conv_and_status(
        step, inputs, user_input, messages, context_providers
    )
    return conv, conv.get_messages()


def _run_flow_and_return_status(
    flow: Flow,
    inputs: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Message]] = None,
) -> ExecutionStatus:
    return flow.start_conversation(
        inputs=inputs or {},
        messages=messages,
    ).execute()


def _run_single_step_and_return_conv_and_status(
    step: Step,
    inputs: Optional[Dict[str, Any]] = None,
    user_input: str = "",
    messages: Optional[List[Message]] = None,
    context_providers: Optional[
        Union[Dict[Property, ContextProviderType], List[ContextProvider]]
    ] = None,
) -> Tuple["Conversation", ExecutionStatus]:
    message_list = MessageList.from_messages(messages or [])
    inputs = inputs or {}
    context_providers = context_providers or []
    assistant = create_single_step_flow(step, "step", context_providers)
    conversation = assistant.start_conversation(inputs, messages=message_list)
    if user_input is not None and user_input != "":
        conversation.append_message(Message(content=user_input, message_type=MessageType.USER))
    status = conversation.execute()
    return conversation, status
