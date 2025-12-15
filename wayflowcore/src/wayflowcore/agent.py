# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import logging
import warnings
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Sequence, Set, Tuple, Union

from wayflowcore._metadata import MetadataType
from wayflowcore._utils._templating_helpers import get_variables_names_and_types_from_template
from wayflowcore.componentwithio import ComponentWithInputsOutputs
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors._executor import ConversationExecutor
from wayflowcore.idgeneration import IdGenerator
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.property import Property, _cast_value_into, _empty_default
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.tools import DescribedAgent, DescribedFlow, Tool, ToolBox
from wayflowcore.tools.servertools import _convert_previously_supported_tools_if_needed
from wayflowcore.transforms import MessageTransform

if TYPE_CHECKING:
    from wayflowcore.contextproviders import ContextProvider
    from wayflowcore.executors._agentconversation import AgentConversation
    from wayflowcore.flow import Flow
    from wayflowcore.ociagent import OciAgent


logger = logging.getLogger(__name__)


class CallerInputMode(Enum):
    """Mode into which the caller of an Agent/AgentExecutionStep sets the Agent."""

    NEVER = "never"  # doc: The agent cannot ask questions and needs to do it by itself
    ALWAYS = "always"  # doc: The agent is allowed to ask the user for more information if needed


NOT_SET_INITIAL_MESSAGE = "N/A"
DEFAULT_INITIAL_MESSAGE = "Hi! How can I help you?"


@dataclass
class Agent(ConversationalComponent, SerializableDataclassMixin, SerializableObject):

    NOT_SET_INITIAL_MESSAGE: ClassVar[str] = NOT_SET_INITIAL_MESSAGE
    """str: Placeholder for non-explicitly set initial message."""

    DEFAULT_INITIAL_MESSAGE: ClassVar[str] = DEFAULT_INITIAL_MESSAGE
    """str: Message the agent will post if no previous user message to welcome them."""

    llm: LlmModel
    """LLM used for the react agent"""

    tools: Sequence[Union[Tool, ToolBox]]
    """Tools the agent has access to"""
    flows: List["Flow"]
    """Flows the agent has access to"""
    agents: List[Union["Agent", "OciAgent"]]
    """Sub-agents the agent has access to"""

    custom_instruction: Optional[str]
    """Additional instructions to put in the agent system prompt"""
    max_iterations: int
    """Maximum number of iterations the agent can loop before returning to the user"""
    context_providers: List["ContextProvider"]
    """Context providers for variables present in the custom instructions of the agent"""
    can_finish_conversation: bool
    """Whether the agent can just exist the conversation when thinks it is done helping the user"""
    raise_exceptions: bool
    """Whether exceptions from sub-executions (tool, sub-agent, or sub-flow execution) are raised or not."""
    initial_message: Optional[str]
    """Initial hardcoded message the agent might post if it doesn't have any user message in the conversation"""
    caller_input_mode: CallerInputMode
    """Whether the agent can ask the user for additional information or needs to just deal with the task itself"""

    agent_template: PromptTemplate

    _add_talk_to_user_tool: bool
    """Whether to add a tool for the agent to talk to the user or not"""

    _used_provided_input_descriptors: List[Property]
    """Inputs provided by the user. Saved separately because input_descriptors are updated based on other attributes"""

    output_descriptors: List[Property]
    """Output descriptors of the agent"""
    input_descriptors: List[Property]
    """Input descriptors of the agent. Can be updated based on other agent attributes"""

    # the following attributes are computed based on the previous attributes values, so whenever
    # some of the above attributes are changed, these need to be re-computed using `_update_internal_state`
    _all_variables: List[str]
    """Names of the variables needed to format the agent system prompt"""
    _all_static_tools: List[Tool]
    """List of all tools & flows as tools & agents as tools the agent has access to"""

    name: str
    description: Optional[str]
    id: str
    """Id of the agent, needed to deal with message visibility"""

    __metadata_info__: MetadataType

    def __init__(
        self,
        llm: "LlmModel",
        tools: Optional[Sequence[Union[Tool, ToolBox]]] = None,
        flows: Optional[List["Flow"]] = None,
        agents: Optional[List[Union["Agent", "OciAgent"]]] = None,
        custom_instruction: Optional[str] = None,
        agent_id: Optional[str] = None,
        id: Optional[str] = None,
        max_iterations: int = 10,
        context_providers: Optional[List["ContextProvider"]] = None,
        can_finish_conversation: bool = False,
        raise_exceptions: bool = False,
        initial_message: Optional[str] = NOT_SET_INITIAL_MESSAGE,
        caller_input_mode: CallerInputMode = CallerInputMode.ALWAYS,
        input_descriptors: Optional[List["Property"]] = None,
        output_descriptors: Optional[List["Property"]] = None,
        name: Optional[str] = None,
        description: str = "",
        agent_template: Optional[PromptTemplate] = None,
        transforms: Optional[List[MessageTransform]] = None,
        _add_talk_to_user_tool: bool = True,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Agent that can handle a conversation with a user, interact with external tools
        and follow interaction flows.

        Note
        ----

        An ``Agent`` has input and output descriptors, describing what values the agent requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input_descriptors will be automatically inferred
        from the ``custom_instruction`` template of the ``Agent``, with one input descriptor per variable in the template,
        trying to detect the type of the variable based on how it is used in the template.
        See :ref:`TemplateRenderingStep <TemplateRenderingStep>` for concrete examples on how descriptors are
        extracted from text prompts.

        If you provide a list of input descriptors, each provided descriptor will automatically override the detected one,
        in particular using the new type instead of the detected one. If some of them are missing,
        the Agent's execution is not guaranteed to succeed.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        **Output descriptors**

        By default, when ``output_descriptors`` is set to ``None``, the ``Agent`` won't have any output descriptors,
        which means that it can only ask question to the user by yielding.

        If you provide a list of output descriptors, the ``Agent`` will be prompted to gather and output
        values that will match the expected output descriptors, which means it can either yield to the user or
        finish the conversation by outputting the output values. If the ``Agent`` is not able to generate them,
        the values will be filled with their default values if they are specified, or the default values
        of their respective types, after the maximum amount of iterations of the ``Agent`` is reached.


        Parameters
        ----------
        llm:
            Model to use for the agent executor (which chooses the next action to do).
        tools:
            List of tools available for the agent.
        flows:
            List of flows available for the agent.
        agents:
            Other agents that the agent can call (expert agents).

            .. warning::
                The use of expert agents is currently in beta and may undergo significant changes.
                The API and behaviour are not guaranteed to be stable and may change in future versions.

        custom_instruction:
            Custom instruction for the agent that will be passed in the system prompt.
            You need to include the context and what the agent is supposed to help the
            user with. This can contain variables in the jinja syntax, and their context
            providers need to be passed in the `context_providers` parameter.
        max_iterations:
            Maximum number of calls to the agent executor before yielding back to the user.
        context_providers:
            Context providers for jinja variables in the custom_instruction.
        can_finish_conversation
            Whether the agent can decide to end the conversation or not.
        raise_exceptions
            Whether exceptions from sub-executions (tool, sub-agent, or sub-flow execution) are raised or not.
        initial_message:
            Initial message the agent will post if no previous user message. It must be None for `CallerInputMode.NEVER`
            If None for `CallerInputMode.ALWAYS`, the LLM will generate it given the `custom_instruction`. Default to
            `Agent.DEFAULT_INITIAL_MESSAGE` for `CallerInputMode.ALWAYS` and None for `CallerInputMode.NEVER`.
        caller_input_mode:
            Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
            If set to NEVER, the agent won't be able to yield.
        input_descriptors:
            Input descriptors of the agent. ``None`` means the agent will resolve the input descriptors automatically in a best effort manner.

            .. note::

                In some cases, the static configuration might not be enough to infer them properly, so this argument allows to override them.

                If ``input_descriptors`` are specified, they will override the resolved descriptors but will be matched
                by ``name`` against them to check that types can be casted from one another, raising an error if they can't.
                If some expected descriptors are missing from the ``input_descriptors`` (i.e. you forgot to specify one),
                a warning will be raised and the agent is not guaranteed to work properly.
        output_descriptors:
            Outputs that the agent is expected to generate.

            .. warning::

                If not ``None``, it will change the agent's behavior and the agent will be prompted to output values for
                all outputs. The ``Agent`` will be able to submit values when it sees fit to finish the conversation.
                The outputs are mandatory if no default value is provided (the agent will have to submit a value for
                it to finish the conversation, and will be re-prompted to do so if it does not provide a value for it)
                but optional if a default value is passed (it will use the default value if the LLM doesn't generate
                a value for it.

        name:
            name of the agent, used for composition
        description:
            description of the agent, used for composition
        id:
            ID of the agent
        agent_template:
            Specific agent template for more advanced prompting techniques. It will be overloaded with the current
            agent ``tools``, and can have placeholders:
            * ``custom_instruction`` placeholder for the ``custom_instruction`` parameter.
        transforms:
            List of MessageTransform objets to run in order on each conversation before passing to the LLM.
        Examples
        --------
        >>> from wayflowcore.agent import Agent
        >>> agent = Agent(llm=llm)
        >>> conversation = agent.start_conversation()
        >>> conversation.append_user_message("I need help regarding my sql query")
        >>> status = conversation.execute()
        >>> agent_answer = conversation.get_last_message().content
        >>> # I'd be happy to help with your SQL query
        """

        # We use the guidelines from https://docs.python.org/3/howto/logging.html#when-to-use-logging
        # for when to use warnings.warn vs logger.warning:
        # - use warnings.warn() if the issue is avoidable and the client application should be modified to eliminate the warning
        # - use logging.warning() if there is nothing the client application can do about the situation, but the event should still be noted
        if agents:
            warnings.warn(
                "The use of expert agents is currently in beta and may undergo significant changes. "
                "The API and behaviour are not guaranteed to be stable and may change in future versions.",
                category=FutureWarning,
            )
            agents = [_convert_described_agent_into_named_agent(agent) for agent in agents]
            self._validate_agent_can_be_used_in_composition(agents)

        if flows is not None:
            flows = [_convert_described_flow_into_named_flow(flow) for flow in flows]
            self._validate_flow_can_be_used_in_composition(flows)

        if caller_input_mode not in [CallerInputMode.ALWAYS, CallerInputMode.NEVER]:
            raise ValueError(
                f"`caller_input_mode` value {caller_input_mode} is not within the domain of `CallerInputMode`."
            )

        if initial_message == NOT_SET_INITIAL_MESSAGE:
            if caller_input_mode == CallerInputMode.ALWAYS:
                initial_message = DEFAULT_INITIAL_MESSAGE
            elif caller_input_mode == CallerInputMode.NEVER:
                initial_message = None
            else:
                raise NotImplementedError(
                    f"The case of not explicitly setting the `initial message` with caller_input_mode = {caller_input_mode} is not supported. This is probably a problem from our side. Please try to proceed with explicitly setting a value for `initial_message`."
                )

        if output_descriptors is not None and len(
            set(descriptor.name for descriptor in output_descriptors)
        ) < len(output_descriptors):
            raise ValueError(
                f"Detected name conflicts in outputs of the Agent. Please ensure output names are unique: {output_descriptors}"
            )

        if caller_input_mode == CallerInputMode.NEVER and initial_message is not None:
            raise ValueError(
                "The caller input mode for the agent is set to `CallerInputMode.NEVER`, which does not allow setting an initial message."
            )

        if (
            caller_input_mode == CallerInputMode.NEVER
            and tools is not None
            and len(tools) > 0
            and max_iterations <= 1
        ):
            warnings.warn(
                "Maximum number of iterations is set to one for the Agent. The agent will be not able to call the tools and report the result.",
                UserWarning,
            )

        self.llm = llm

        self.tools = _convert_previously_supported_tools_if_needed(tools) or []
        self.flows = flows or []
        self.agents = agents or []

        self.custom_instruction = custom_instruction
        self.max_iterations = max_iterations
        self.context_providers = context_providers or []
        self.can_finish_conversation = can_finish_conversation
        self.raise_exceptions = raise_exceptions
        self.initial_message = initial_message
        self.caller_input_mode = caller_input_mode
        self._add_talk_to_user_tool = _add_talk_to_user_tool

        self.transforms = transforms or []
        agent_template = agent_template or llm.agent_template
        for transform in self.transforms:
            agent_template = agent_template.with_additional_post_rendering_transform(transform)
        self.agent_template = agent_template

        self._used_provided_input_descriptors = input_descriptors or []
        self._tools: List[Tool] = []
        self._toolboxes: List[ToolBox] = []

        from wayflowcore.executors._agentconversation import AgentConversation
        from wayflowcore.executors._agentexecutor import AgentConversationExecutor

        super().__init__(
            name=IdGenerator.get_or_generate_name(name, prefix="agent_", length=8),
            description=description,
            id=id or agent_id,
            input_descriptors=[*self._used_provided_input_descriptors],
            output_descriptors=output_descriptors or [],
            runner=AgentConversationExecutor,
            conversation_class=AgentConversation,
            __metadata_info__=__metadata_info__,
        )

        self._all_static_tools = []
        self._all_variables = []
        self._update_internal_state()

    @property
    def agent_id(self) -> str:
        return self.id

    @staticmethod
    def _validate_agent_can_be_used_in_composition(
        agents: List[Union["Agent", "OciAgent"]],
    ) -> None:
        for agent in agents:
            if IdGenerator.is_auto_generated(agent.name):
                raise ValueError(
                    "An agent seems to have an auto-generated name. To use an agent in another agent, you should "
                    f"specify a correct sub-agent name to help the agent in calling it appropriately: {agent}"
                )
            if agent.description == "":
                warnings.warn(f"Agent should have a description but was empty: {agent}")

    @staticmethod
    def _validate_flow_can_be_used_in_composition(flows: List["Flow"]) -> None:
        for flow in flows:
            if IdGenerator.is_auto_generated(flow.name):
                raise ValueError(
                    "A flow seems to have an auto-generated name. To use a flow in an agent, you should "
                    f"specify a correct sub-flow name to help the agent in calling it appropriately: {flow}"
                )
            if flow.description == "":
                warnings.warn(f"Flow should have a description but was empty: {flow}")

    def start_conversation(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        messages: Union[None, str, "Message", List["Message"], "MessageList"] = None,
        conversation_id: Optional[str] = None,
    ) -> "AgentConversation":
        """
        Initializes a conversation with the agent.

        Parameters
        ----------
        inputs:
            This argument is not used.
            It is included for compatibility with the Flow class.
        messages:
            Message list to which the agent will participate
        conversation_id:
            Conversation id of the parent conversation.

        Returns
        -------
        Conversation:
            The conversation object of the agent.
        """
        from wayflowcore.events.event import ConversationCreatedEvent
        from wayflowcore.events.eventlistener import record_event
        from wayflowcore.executors._agentconversation import AgentConversation

        if not isinstance(messages, MessageList):
            messages = MessageList.from_messages(messages=messages)

        required_input_names = [
            input_descriptor.name
            for input_descriptor in self.input_descriptors
            if input_descriptor.default_value is _empty_default
        ]

        if len(self.input_descriptors) > 0:
            if inputs is None:
                if required_input_names:
                    raise ValueError(
                        f"Agent requires inputs (`{required_input_names}`), but you did not pass any."
                    )
                else:
                    # We don't have inputs, but all the input descriptors have defaults
                    inputs = {}
            for input_value_description in self.input_descriptors:
                # We retrieve inputs when available, otherwise get defaults if defined, if not defined, raise
                if input_value_description.name in inputs:
                    input_value = inputs[input_value_description.name]
                elif input_value_description.default_value is not _empty_default:
                    input_value = input_value_description.default_value
                else:
                    raise ValueError(
                        f"The agent requires an input `{input_value_description.name}`, but it was not passed in the input dictionary: `{inputs}`"
                    )

                try:
                    casted_input_value = _cast_value_into(input_value, input_value_description)
                    inputs[input_value_description.name] = casted_input_value
                except Exception as e:
                    raise TypeError(
                        f"Input value `{input_value_description.name}` should be of type {input_value_description} but was: {input_value}"
                    )

        record_event(
            ConversationCreatedEvent(
                conversational_component=self,
                inputs=inputs,
                messages=messages,
                conversation_id=conversation_id,
                nesting_level=None,
            )
        )

        from wayflowcore.executors._agentexecutor import AgentConversationExecutionState

        return AgentConversation(
            component=self,
            message_list=messages,
            conversation_id=IdGenerator.get_or_generate_id(conversation_id),
            inputs=inputs or {},
            name="agent_conversation",
            state=AgentConversationExecutionState(),
            status=None,
            __metadata_info__={},
        )

    @property
    def llms(self) -> List["LlmModel"]:
        return [self.llm] if self.llm else []

    @property
    def executor(self) -> ConversationExecutor:
        return self.runner()

    def clone(self, name: str, description: str) -> "Agent":
        """Clones an agent with a different name and description"""
        return Agent(
            llm=self.llm,
            agent_id=self.agent_id,
            tools=self.tools,
            flows=self.flows,
            agents=self.agents,
            context_providers=self.context_providers,
            custom_instruction=self.custom_instruction,
            max_iterations=self.max_iterations,
            can_finish_conversation=self.can_finish_conversation,
            initial_message=self.initial_message,
            caller_input_mode=self.caller_input_mode,
            output_descriptors=self.output_descriptors,
            input_descriptors=self.input_descriptors,
            name=name,
            description=description,
            __metadata_info__=self.__metadata_info__,
        )

    @property
    def config(self) -> "Agent":
        # backward compatibility
        return self

    def _update_internal_state(self) -> None:
        """Updates the internal state of the Agent executor based on its attributes that are init attributes"""
        if (
            # When the user does not specify an agent_template, we default to the LLM's agent template.
            # So here we check if the user set one or we are using the default.
            self.agent_template == self.llm.agent_template
            and self.initial_message is None
            and self.custom_instruction is None
        ):
            raise ValueError(
                "Initial message and agent template were set to None, so the Agent requires a custom instruction, but it was None"
            )

        self._tools, self._toolboxes = _extract_toolboxes_from_tool_sequence(self.tools or [])

        # need to be done in order
        self._all_static_tools = Agent._compute_all_agent_tools(
            tools=self._tools,
            flows=self.flows,
            agents=self.agents,
            can_finish_conversation=self.can_finish_conversation,
            output_descriptors=self.output_descriptors,
            caller_input_mode=self.caller_input_mode,
            add_talk_to_user_tool=self._add_talk_to_user_tool,
        )

        self.input_descriptors, self._all_variables = Agent.compute_agent_inputs(
            custom_instruction=self.custom_instruction,
            context_providers=self.context_providers,
            user_specified_input_descriptors=self._used_provided_input_descriptors,
            agent_template=self.agent_template,
        )

    @staticmethod
    def _compute_all_agent_tools(
        tools: List[Tool],
        flows: List["Flow"],
        agents: List[Union["Agent", "OciAgent"]],
        can_finish_conversation: bool,
        output_descriptors: List[Property],
        caller_input_mode: CallerInputMode,
        add_talk_to_user_tool: bool,
    ) -> List[Tool]:
        from wayflowcore.executors._agentexecutor import (
            _TALK_TO_USER_TOOL_NAME,
            _agent_as_client_tool,
            _get_end_conversation_tool,
            _make_submit_output_tool,
            _make_talk_to_user_tool,
        )

        flow_tools = [flow.as_client_tool() for flow in flows]
        agent_tools = [_agent_as_client_tool(agent) for agent in agents]
        all_tools = tools + flow_tools + agent_tools

        if len(set(t.name for t in agent_tools)) < (
            len(agent_names := [agent.name for agent in agents])
        ):
            raise ValueError(
                f"Sub-agent name collision: names must differ by more than whitespace, punctuation, casing, or special characters. Names of provided agents: {agent_names}"
            )
        if len(set(t.name for t in flow_tools)) < (
            len(flow_names := [flow.name for flow in flows])
        ):
            raise ValueError(
                f"Sub-flow name collision: names must differ by more than whitespace, punctuation, casing, or special characters. Names of provided flows: {flow_names}"
            )

        if can_finish_conversation and len(output_descriptors) == 0:
            exit_tool = _get_end_conversation_tool()
            if any(exit_tool.name == tool.name for tool in all_tools):
                raise ValueError(
                    f"A tool name is conflicting with the agent exit tool. Please rename this tool: {exit_tool.name}"
                )
            all_tools += [exit_tool]

        if caller_input_mode == CallerInputMode.NEVER and _TALK_TO_USER_TOOL_NAME in (
            _all_tool_names := [tool_.name for tool_ in all_tools]
        ):
            raise ValueError(
                f"Caller input mode is set to 'NEVER' but found a tool with name {_TALK_TO_USER_TOOL_NAME}. "
                f"Make sure to not pass any tool with this name. List of tool names was: {_all_tool_names}"
            )

        if (
            caller_input_mode == CallerInputMode.ALWAYS
            and len(all_tools) > 0
            and add_talk_to_user_tool
        ):
            all_tools += [_make_talk_to_user_tool()]

        if len(output_descriptors) > 0:
            all_tools += [
                _make_submit_output_tool(
                    caller_input_mode=caller_input_mode, outputs=output_descriptors
                )
            ]

        all_names = [e.name for e in all_tools]
        name_counts = Counter(all_names)
        reused_names = [name for name, name_count in name_counts.items() if name_count > 1]
        if any(reused_names):
            raise ValueError(
                f"Found overlapping names (after normalization) for agents, flows, and/or tools: {reused_names}. Rename flows/agents/tools so normalized names are unique."
            )

        return all_tools

    @staticmethod
    def compute_agent_inputs(
        custom_instruction: Optional[str],
        context_providers: List["ContextProvider"],
        user_specified_input_descriptors: List[Property],
        agent_template: PromptTemplate,
    ) -> Tuple[List[Property], List[str]]:
        template_inputs = agent_template.input_descriptors or []
        all_input_variables = [
            p
            for p in template_inputs
            if p.name
            not in {
                PromptTemplate.CHAT_HISTORY_PLACEHOLDER_NAME,  # placeholder of chat history
                PromptTemplate.TOOL_PLACEHOLDER_NAME,  # placeholder for tools
                "custom_instruction",  # placeholder for agent instructions
                "__PLAN__",  # placeholder for plan
            }
        ]
        if custom_instruction is not None:
            all_input_variables.extend(
                get_variables_names_and_types_from_template(custom_instruction)
            )

        available_contextual_variable_names = {
            property_.name
            for context_provider in context_providers
            for property_ in context_provider.get_output_descriptors()
        }
        agent_inputs = [
            property_
            for property_ in all_input_variables
            if property_.name not in available_contextual_variable_names
        ]
        if len(agent_inputs) > 0:
            logger.debug(f"Agent will have several inputs: {agent_inputs}")
        return ComponentWithInputsOutputs._resolve_input_descriptors(
            specified_descriptors=user_specified_input_descriptors, default_descriptors=agent_inputs
        ), list(property_.name for property_ in set(all_input_variables))

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        all_tools = {tool.id: tool for tool in self._tools}

        if recursive:
            for agent in self.agents:
                all_tools.update(
                    agent._referenced_tools_dict(recursive=True, visited_set=visited_set)
                )

            for flow in self.flows:
                all_tools.update(
                    flow._referenced_tools_dict(recursive=True, visited_set=visited_set)
                )

            if self.agent_template.tools is not None:
                for tool in self.agent_template.tools:
                    all_tools[tool.id] = tool

        return all_tools

    @property
    def might_yield(self) -> bool:
        might_ask_question_to_user = self.caller_input_mode != CallerInputMode.NEVER
        has_yielding_tools = any(tool.might_yield for tool in self.tools)
        has_yielding_flows = any(flow.might_yield for flow in self.flows)
        return might_ask_question_to_user or has_yielding_tools or has_yielding_flows


class _MutatedAgent:
    def __init__(
        self,
        agent: Agent,
        attributes: Dict[str, Any],
    ):
        self.agent = agent
        self.attributes = attributes
        self.old_config: Dict[str, Any] = {}

    def __enter__(self) -> Agent:
        self.old_config.clear()
        for attribute_name, attribute_value in self.attributes.items():
            self.old_config[attribute_name] = getattr(self.agent, attribute_name)
            setattr(self.agent, attribute_name, attribute_value)
        self.agent._update_internal_state()

        return self.agent

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        attribute_names = list(self.old_config.keys())
        for attribute_name in attribute_names:
            setattr(self.agent, attribute_name, self.old_config.pop(attribute_name))
        self.agent._update_internal_state()


def _convert_described_agent_into_named_agent(
    described_agent: Union[DescribedAgent, Agent, "OciAgent"],
) -> Union[Agent, "OciAgent"]:
    from wayflowcore.ociagent import OciAgent

    if isinstance(described_agent, (Agent, OciAgent)):
        return described_agent

    # modifying in place might lead to issues, so we copy
    return described_agent.agent.clone(
        name=described_agent.name,
        description=described_agent.description,
    )


def _convert_described_flow_into_named_flow(described_flow: Union[DescribedFlow, "Flow"]) -> "Flow":
    from wayflowcore.flow import Flow

    if isinstance(described_flow, Flow):
        return described_flow

    # modifying in place might lead to issues, so we copy
    new_flow = described_flow.flow.clone(
        name=described_flow.name,
        description=described_flow.description,
    )

    if described_flow.output is not None:
        new_flow.output_descriptors_dict = {
            described_flow.output: new_flow.output_descriptors_dict[described_flow.output]
        }
        new_flow.output_descriptors = [new_flow.output_descriptors_dict[described_flow.output]]
    return new_flow


def _extract_toolboxes_from_tool_sequence(
    tools: Sequence[Union[Tool, ToolBox]],
) -> Tuple[List[Tool], List[ToolBox]]:
    all_tools: List[Tool] = []
    all_toolboxes: List[ToolBox] = []
    for tool in tools:
        if isinstance(tool, ToolBox):
            all_toolboxes.append(tool)
        else:
            all_tools.append(tool)  # tool validation is done after
    return all_tools, all_toolboxes
