# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union

from wayflowcore._metadata import MetadataType
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.conversationalcomponent import _mutate
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
)
from wayflowcore.executors.interrupts.executioninterrupt import InterruptedExecutionStatus
from wayflowcore.ociagent import OciAgent
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.swarm import Swarm
from wayflowcore.tools import Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)


class AgentExecutionStep(Step):

    _output_descriptors_change_step_behavior = True
    # it changes the behavior of the underlying agent by asking it to generate these outputs

    def __init__(
        self,
        agent: Union[Agent, OciAgent, Swarm],
        caller_input_mode: Optional[CallerInputMode] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
        _share_conversation: bool = True,
    ):
        """
        Step that executes an agent. If given some outputs, it will ask the agent to return these outputs.
        Otherwise, it will never exit the step and allows the user to ask questions to the agent.

        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input_descriptors will be automatically inferred
        from the ``custom_instruction`` template of the ``Agent``, with one input descriptor per variable in the template,
        trying to detect the type of the variable based on how it is used in the template.
        See :ref:`TemplateRenderingStep <TemplateRenderingStep>` for concrete examples on how descriptors are
        extracted from text prompts.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one. If some of them are missing,
        an error will be thrown at the instantiation of the ``Agent``.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        **Output descriptors**

        By default, when ``output_descriptors`` is set to ``None``, the step will have the same output descriptors
        as its ``Agent``. See :ref:`Agent <Agent>` to learn more about how their output descriptors are computed.

        If you provide a list of output descriptors, the step will prompt the ``Agent`` to gather and output
        values that will match the expected output descriptors, which means it can either yield to the user or
        finish the conversation by outputting the output values. If the ``Agent`` is not able to generate them,
        the values will be filled with their default values if they are specified, or the default values
        of their respective types, after the maximum amount of iterations of the ``Agent`` is reached.

        Parameters
        ----------
        agent:
            Agent that will be used in the step
        caller_input_mode:
            Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
            If set to NEVER, the step won't be able to yield. Defaults to ``None``, which means it will use the ``call_input_mode``
            of the underlying agent.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

            .. warning::

                Changing this will change the behavior of the step. If not ``None``, the ``Agent`` will be prompted
                to generate the expected outputs and the step will only return when the ``Agent`` submits values for
                all these outputs.
        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.


        See Also
        --------
        :class:`~wayflowcore.agent.Agent` : the agent class that will be run inside this step.

        Notes
        -----
        Here are some guidelines to ensure the best performance of this step:

        1. ``custom_instruction`` of the `Agent`: specify in it what the task is about. Don't use phrasing of style "You are a helpful assistant ..." because our tool calling template contains it. Only specify relevant information for your use-case

        2. ``caller_input_mode``: if ``NEVER``, you might improve performance by reminding the model to only output a single function at a time and not to talk to the user

        Examples
        --------
        To run this example, you need to install ``duckduckgosearch`` with ``pip install duckduckgo-search``

        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.agent import Agent
        >>> from wayflowcore.property import (
        ...     IntegerProperty,
        ...     Property,
        ...     StringProperty,
        ... )
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import InputMessageStep
        >>> from wayflowcore.steps.agentexecutionstep import AgentExecutionStep, CallerInputMode
        >>> from langchain_community.tools import DuckDuckGoSearchRun  # doctest: +SKIP
        >>> search_tool = DuckDuckGoSearchRun().as_tool()  # doctest: +SKIP
        >>> agent = Agent(
        ...     llm=llm,
        ...     custom_instruction=(
        ...         "Your task is to gather the required information for the user: "
        ...         "creation_date, name, CEO, country"
        ...     ),
        ...     tools=[search_tool],
        ... )  # doctest: +SKIP
        >>> flow = Flow.from_steps([
        ...     InputMessageStep("Which company are you interested in?"),
        ...     AgentExecutionStep(
        ...         agent=agent,
        ...         caller_input_mode=CallerInputMode.NEVER,
        ...         output_descriptors=[
        ...             IntegerProperty(
        ...                 name='creation_date',
        ...                 description='year when the company was founded',
        ...                 default_value=-1,
        ...             ),
        ...             StringProperty(
        ...                 name='name',
        ...                 description='official name of the company',
        ...                 default_value='',
        ...             ),
        ...             StringProperty(
        ...                 name='CEO',
        ...                 description='name of the CEO of the company',
        ...                 default_value='',
        ...             ),
        ...             StringProperty(
        ...                 name='country',
        ...                 description='country where the headquarters are based',
        ...                 default_value='',
        ...             )
        ...         ]
        ...     )
        ... ])  # doctest: +SKIP
        >>> conv = flow.start_conversation()  # doctest: +SKIP
        >>> status = conv.execute()  # doctest: +SKIP
        >>> conv.append_user_message('Oracle')  # doctest: +SKIP
        >>> status = conv.execute()  # doctest: +SKIP
        >>> # status.output_values
        >>> # {'name': 'Oracle', 'creation_date': 1977, 'CEO': 'Safra A. Catz', 'country': 'US'}

        """
        if caller_input_mode == CallerInputMode.NEVER and (
            output_descriptors is None or len(output_descriptors) == 0
        ):
            raise ValueError(
                "caller_input_mode=CallerInputMode.NEVER requires outputs to have an exiting criteria."
            )

        self.caller_input_mode = caller_input_mode
        self.agent = agent
        self._share_conversation = _share_conversation
        """Whether the calling flow shares its messages with the Agent or not."""

        if not isinstance(self.agent, (Agent, Swarm)):
            if output_descriptors is not None and len(output_descriptors) > 0:
                raise ValueError(
                    f"Only `Agent` and `Swarm` in `AgentExecutionStep` supports setting outputs, but you used: `{self.agent}` for {output_descriptors}. Please use an `Agent` or a `Swarm` or set the outputs to `None`"
                )
            if caller_input_mode != CallerInputMode.ALWAYS:
                raise ValueError(
                    f"Only `Agent` and `Swarm` in `AgentExecutionStep` supports setting a caller input mode, but you used: `{self.agent}` for {caller_input_mode}. Please use an `Agent` or a `Swarm` or set the outputs to `None`"
                )

        super().__init__(
            llm=self.agent.llm if isinstance(self.agent, Agent) else None,
            step_static_configuration=dict(
                agent=agent,
                caller_input_mode=caller_input_mode,
            ),
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            input_mapping=input_mapping,
            output_mapping=output_mapping,
            name=name,
            __metadata_info__=__metadata_info__,
        )

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {
            "agent": Agent,
            "caller_input_mode": Optional[CallerInputMode],
        }

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        agent: "Agent",
        output_descriptors: Optional[List[Property]],
        caller_input_mode: CallerInputMode,
    ) -> List[Property]:
        # no need to mutate the agent, we don't touch the inputs
        return agent.input_descriptors

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        agent: "Agent",
        output_descriptors: Optional[List[Property]],
        caller_input_mode: CallerInputMode,
    ) -> List[Property]:
        # we need to mutate the agent to give it the proper outputs
        if output_descriptors is not None:
            return output_descriptors
        return agent.output_descriptors

    # override
    @property
    def might_yield(self) -> bool:
        if isinstance(self.agent, Agent):
            return self.agent.might_yield or self.caller_input_mode == CallerInputMode.ALWAYS
        elif isinstance(self.agent, Swarm):
            # Swarm's caller_input_mode enforces whether the agent is conversational or not
            return (
                self.agent.caller_input_mode == CallerInputMode.ALWAYS
                or self.caller_input_mode == CallerInputMode.ALWAYS
            )
        elif isinstance(self.agent, OciAgent):
            return True
        else:
            raise NotImplementedError(f"{self.agent} not supported in the agent execution step.")

    def _get_or_create_agent_subconversation(
        self,
        sub_conversation_id: str,
        caller_conv: "FlowConversation",
        inputs: Dict[str, Any],
    ) -> "Conversation":
        from wayflowcore.messagelist import MessageList

        agent_sub_conversation = caller_conv._get_current_sub_conversation(
            self, sub_conversation_id
        )
        if agent_sub_conversation is not None:
            return agent_sub_conversation

        init_messages = (
            caller_conv.message_list if self._share_conversation else MessageList.from_messages([])
        )
        agent_sub_conversation = self.agent.start_conversation(
            inputs=inputs, messages=init_messages
        )

        return agent_sub_conversation

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        from wayflowcore.executors._flowexecutor import FlowConversationExecutor

        SUB_CONVERSATION_ID = (
            f"agent_sub_conversation_{self.name}" + FlowConversationExecutor._SUB_CONVERSATION_KEY
        )
        agent_sub_conversation = self._get_or_create_agent_subconversation(
            sub_conversation_id=SUB_CONVERSATION_ID, caller_conv=conversation, inputs=inputs
        )
        conversation._update_sub_conversation(self, agent_sub_conversation, SUB_CONVERSATION_ID)

        mutated_agent_parameters: Dict[str, Any] = {
            "output_descriptors": self._internal_output_descriptors,
        }
        if self.caller_input_mode is not None:
            mutated_agent_parameters["caller_input_mode"] = self.caller_input_mode

        if isinstance(self.agent, (Agent, Swarm)):
            context_manager = _mutate(
                component=self.agent,
                attributes=mutated_agent_parameters,
            )
        else:
            # ignoring the type because mypy doesn't recognize nullcontext as a proper context manager to typing fails
            context_manager = contextlib.nullcontext()  # type: ignore

        with context_manager:
            status = await agent_sub_conversation.execute_async()

        logger.debug(f"Agent of AgentExecutionStep returned status: {status}")

        if isinstance(
            status, (InterruptedExecutionStatus, ToolRequestStatus, ToolExecutionConfirmationStatus)
        ):
            return StepResult(
                outputs={"__execution_status__": status},
                branch_name=self.BRANCH_SELF,
                step_type=(
                    StepExecutionStatus.INTERRUPTED
                    if isinstance(status, InterruptedExecutionStatus)
                    else StepExecutionStatus.YIELDING
                ),
            )
        if not isinstance(status, FinishedStatus):
            return StepResult(
                outputs={"__execution_status__": status},
                branch_name=self.BRANCH_SELF,
                step_type=StepExecutionStatus.YIELDING,
            )

        conversation._cleanup_sub_conversation(self, SUB_CONVERSATION_ID)

        return StepResult(outputs=status.output_values)

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {}

        if recursive:
            all_tools.update(
                self.agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
            )

        return all_tools
