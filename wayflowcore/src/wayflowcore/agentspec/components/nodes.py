# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from copy import deepcopy
from typing import Any, ClassVar, Dict, List, Literal, Optional, Set, Type, Union, cast

from pyagentspec.agent import Agent
from pyagentspec.component import SerializeAsEnum
from pyagentspec.flows.flow import Flow
from pyagentspec.flows.nodes import (
    AgentNode,
    EndNode,
    InputMessageNode,
    LlmNode,
    OutputMessageNode,
    ToolNode,
)
from pyagentspec.llms import LlmConfig
from pyagentspec.property import (
    BooleanProperty,
    FloatProperty,
    IntegerProperty,
    ListProperty,
    Property,
    StringProperty,
    json_schemas_have_same_type,
    properties_have_same_type,
)
from pyagentspec.templating import get_placeholder_properties_from_string
from pyagentspec.validation_helpers import model_validator_with_error_accumulation
from pydantic import ConfigDict, Field, SerializeAsAny
from typing_extensions import Self

from wayflowcore.agentspec.components._pydantic_plugins import (
    PydanticComponentDeserializationPlugin,
    PydanticComponentSerializationPlugin,
)
from wayflowcore.agentspec.components._utils import (
    get_placeholder_properties_from_string_with_jinja_loops,
)
from wayflowcore.agentspec.components.messagelist import PluginMessageType  # type: ignore
from wayflowcore.agentspec.components.template import PluginPromptTemplate
from wayflowcore.steps.agentexecutionstep import CallerInputMode  # type: ignore
from wayflowcore.steps.choiceselectionstep import _DEFAULT_CHOICE_SELECTION_TEMPLATE
from wayflowcore.steps.getchathistorystep import (
    _DEFAULT_OUTPUT_TEMPLATE as _GETCHATHISTORY_DEFAULT_OUTPUT_TEMPLATE,
)
from wayflowcore.steps.getchathistorystep import MessageSlice as PluginMessageSlice
from wayflowcore.variable import VariableWriteOperation as PluginVariableWriteOperation

from .node import ExtendedNode
from .outputparser import PluginRegexPattern


class PluginCatchExceptionNode(ExtendedNode):
    """Executes a ``Flow`` inside a step and catches specific potential exceptions.
    If no exception is caught, it will transition to the branches of its subflow.
    If an exception is caught, it will transition to some specific exception branch has configured in this step.
    """

    flow: SerializeAsAny[Flow]
    """The flow to run and catch exceptions from."""
    except_on: Optional[Dict[str, str]] = None
    """Names of exceptions to catch and their associated branches."""
    catch_all_exceptions: bool = False
    """Whether to catch any exception and redirect to the default exception branch."""

    EXCEPTION_NAME_OUTPUT_NAME: ClassVar[str] = "exception_name"
    """Variable containing the name of the caught exception."""
    EXCEPTION_PAYLOAD_OUTPUT_NAME: ClassVar[str] = "exception_payload_name"
    """Variable containing the exception payload. Does not contain any higher-level stacktrace
    information than the wayflowcore stacktraces."""
    DEFAULT_EXCEPTION_BRANCH: ClassVar[str] = "default_exception_branch"
    """Name of the branch where the step will transition if ``catch_all_exceptions`` is ``True``
    and an exception was caught."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if hasattr(self, "flow"):
            return self.flow.inputs or []
        return []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        outputs: List[Property] = []
        if hasattr(self, "flow"):
            outputs.extend(self.flow.outputs or [])
        return outputs + [
            Property(
                json_schema={
                    "title": self.EXCEPTION_NAME_OUTPUT_NAME,
                    "type": "string",
                    "default": "",
                }
            ),
            Property(
                json_schema={
                    "title": self.EXCEPTION_PAYLOAD_OUTPUT_NAME,
                    "type": "string",
                    "default": "",
                }
            ),
        ]

    def _get_inferred_branches(self) -> List[str]:
        branches = []
        if hasattr(self, "flow"):
            end_nodes = sorted(
                list({node.branch_name for node in self.flow.nodes if isinstance(node, EndNode)})
            )
            branches = end_nodes if end_nodes else super()._get_inferred_branches()
        if hasattr(self, "catch_all_exceptions") and self.catch_all_exceptions:
            branches.append(self.DEFAULT_EXCEPTION_BRANCH)
        if hasattr(self, "except_on") and self.except_on is not None:
            branches.extend(self.except_on.values())
        return branches


class PluginExtractNode(ExtendedNode):
    """Node to extract information from a raw json text."""

    output_values: Dict[str, str]
    """The keys are output names of this step. The values are the jq formulas
    to extract them from the json detected"""

    TEXT: ClassVar[str] = "text"
    """Input key for the raw json text to be parsed."""

    llm_config: Optional[SerializeAsAny[LlmConfig]] = None
    """LLM to use to rephrase the message. Only required if ``retry=True``."""

    retry: bool = False
    """Whether to reprompt a LLM to fix the error or not"""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return [StringProperty(title=PluginExtractNode.TEXT)]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "output_values"):
            return []
        return [Property(json_schema={"title": title}) for title in self.output_values.keys()]


def _get_json_schema_of_read_variable(
    variable: Property, title: str | None = None
) -> Dict[str, Any]:
    json_schema = deepcopy(variable.json_schema)

    if title is not None:
        json_schema["title"] = title

    return json_schema


def _get_json_schema_of_write_variable(
    variable: Property, operation: PluginVariableWriteOperation, title: str | None = None
) -> Dict[str, Any]:
    json_schema = {}
    if operation == PluginVariableWriteOperation.INSERT:
        if variable.type == "array":
            json_schema = deepcopy(variable.json_schema["items"])
            json_schema["description"] = json_schema.get(
                "description", f"{variable.description} (single element)"
            )
        else:
            raise TypeError(
                f"Can only apply insert write operation to lists, not to {variable.type}"
            )
    else:
        json_schema = deepcopy(variable.json_schema)

    if title is not None:
        json_schema["title"] = title

    return json_schema


class PluginReadVariableNode(ExtendedNode):
    variable: Property
    """The variable (which is a Property in AgentSpec) that this node will read."""

    VALUE: ClassVar[str] = "value"
    """str: Output key for the read value from the ``PluginReadVariableNode``."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "variable"):
            return []

        return [
            Property(
                json_schema=_get_json_schema_of_read_variable(
                    self.variable,
                    title=PluginReadVariableNode.VALUE,
                )
            )
        ]


class PluginVariableNode(ExtendedNode):
    write_variables: List[Property] = Field(default_factory=list)
    """The variables (which are a Property in AgentSpec) that this node will write."""

    read_variables: List[Property] = Field(default_factory=list)
    """The variables (which are a Property in AgentSpec) that this node will read."""

    write_operations: Dict[str, SerializeAsEnum[PluginVariableWriteOperation]] = Field(
        default_factory=dict
    )
    """The type of write operations to perform on write variables."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if not hasattr(self, "write_variables") or not hasattr(self, "write_operations"):
            return []

        if {wv.title for wv in self.write_variables} != set(self.write_operations.keys()):
            raise ValueError(
                "An operation must be defined in `write_operations` for all of the "
                "variables in `write_variables`, and it must not defined for "
                "any other variables."
            )

        return [
            Property(
                json_schema=_get_json_schema_of_write_variable(
                    variable=write_variable,
                    operation=self.write_operations[write_variable.title],
                    title=write_variable.title,
                )
            )
            for write_variable in self.write_variables
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "read_variables"):
            return []

        return [
            Property(
                json_schema=_get_json_schema_of_read_variable(
                    variable=read_variable,
                    title=read_variable.title,
                )
            )
            for read_variable in self.read_variables
        ]


class PluginWriteVariableNode(ExtendedNode):
    variable: Property
    """The variable (which is a Property in AgentSpec) that this node will write."""

    operation: SerializeAsEnum[PluginVariableWriteOperation] = (
        PluginVariableWriteOperation.OVERWRITE
    )
    """The type of write operation to perform"""

    VALUE: ClassVar[str] = "value"
    """str: Input key for the value to write for the ``PluginWriteVariableNode``."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if not hasattr(self, "variable") or not hasattr(self, "operation"):
            return []

        return [
            Property(
                json_schema=_get_json_schema_of_write_variable(
                    variable=self.variable,
                    operation=self.operation,
                    title=self.VALUE,
                )
            )
        ]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return []


class ExtendedLlmNode(ExtendedNode, LlmNode):
    """Extended version of the Agent Spec LlmNode. Supports prompt templates and streaming."""

    prompt_template_object: Optional[PluginPromptTemplate] = None
    """Prompt template object. Either use `prompt_template` or `prompt_template_object`."""

    send_message: bool = False
    """Determines whether to send the generated content to the current message list or not.
    By default, the content is only exposed as an output.
    """

    OUTPUT: ClassVar[str] = "output"
    """Output key for the output generated by the LLM, matching the Reference Runtime default value."""

    @model_validator_with_error_accumulation
    def check_either_prompt_str_or_object_is_used(self) -> Self:
        if (not self.prompt_template and not self.prompt_template_object) or (
            self.prompt_template and self.prompt_template_object
        ):
            raise ValueError("Use either the `prompt_template` or `prompt_template_object`.")
        return self

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if (
            hasattr(self, "prompt_template_object")
            and self.prompt_template_object
            and self.prompt_template_object.inputs
        ):
            return self.prompt_template_object.inputs
        elif hasattr(self, "prompt_template"):
            return get_placeholder_properties_from_string(self.prompt_template)
        else:
            return []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if (
            hasattr(self, "prompt_template_object") and self.prompt_template_object
        ) and self.prompt_template_object.response_format:
            return [self.prompt_template_object.response_format]
        return [
            StringProperty(
                title=self.OUTPUT,
                description="the generated text",
            )
        ]


class PluginInputMessageNode(ExtendedNode, InputMessageNode):
    """Node to get an input from the conversation with the user.

    The input step prints a message to the user, asks for an answer and returns it as
    an output of the step. It places both messages in the messages list so that it is
    possible to visualize the conversation, but also returns the user input as an output."""

    message_template: Optional[str]
    """The message template to use to ask for more information to the user, in jinja format."""
    rephrase: bool = False
    """Whether to rephrase the message. Requires ``llm`` to be set."""
    llm_config: Optional[SerializeAsAny[LlmConfig]] = None
    """LLM to use to rephrase the message. Only required if ``rephrase=True``."""

    USER_PROVIDED_INPUT: ClassVar[str] = "user_provided_input"
    """Output key for the input text provided by the user."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return get_placeholder_properties_from_string_with_jinja_loops(
            getattr(self, "message_template", "") or ""  # message_template could be None
        )

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        output_title = self.outputs[0].title if self.outputs else self.USER_PROVIDED_INPUT
        return [
            Property(json_schema={"title": output_title, "type": "string"})
        ]  # TODO support passing descriptions


class PluginOutputMessageNode(ExtendedNode, OutputMessageNode):
    """Node to output a message to the chat history."""

    message_type: SerializeAsEnum[PluginMessageType] = PluginMessageType.AGENT
    """Message type of the message added to the message history."""
    rephrase: bool = False
    """Whether to rephrase the message. Requires ``llm`` to be set."""
    llm_config: Optional[SerializeAsAny[LlmConfig]] = None
    """LLM to use to rephrase the message. Only required if ``rephrase=True``."""
    expose_message_as_output: bool = True
    """Whether the message generated by this step should appear among the output descriptors"""

    OUTPUT: ClassVar[str] = "output_message"
    """Output key for the output message generated by the ``PluginOutputMessageNode``."""

    # override the base attribute to add the alias for backward compatibility
    message: str = Field(alias="message_template")
    model_config = ConfigDict(populate_by_name=True)

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return get_placeholder_properties_from_string_with_jinja_loops(getattr(self, "message", ""))

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        output_title = self.outputs[0].title if self.outputs else self.OUTPUT
        return (
            [Property(json_schema={"title": output_title, "type": "string"})]
            if self.expose_message_as_output
            else []
        )


# /!\ The inheritance order for the class `ExtendedToolNode` is important such that
# `ExtendedNode._get_inferred_inputs` is used and not `ToolNode._get_inferred_inputs`
# You can learn about Method Resolution Order here: https://docs.python.org/3/howto/mro.html
class ExtendedToolNode(ExtendedNode, ToolNode):
    """Extension of the Agent Spec ToolNode. Supports silencing exceptions raised by tools."""

    raise_exceptions: bool
    """Whether to raise or not exceptions raised by the tool. If ``False``, it will put the error message
       as the result of the tool if the tool output type is string."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return (self.tool.inputs or []) if hasattr(self, "tool") else []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return (self.tool.outputs or []) if hasattr(self, "tool") else []


class ExtendedMapNode(ExtendedNode):
    """Extension of the Agent Spec MapNode. Supports parallel execution and input extraction."""

    flow: Flow
    """Flow that is being executed with each iteration of the input."""
    unpack_input: Dict[str, str] = Field(default_factory=dict)
    """Mapping to specify how to unpack when each iter item is a ``dict``
    and we need to map its element to the inside flow inputs."""
    parallel_execution: bool = False
    """Executes the mapping operation in parallel. Cannot be set to true if the internal flow can yield.
    This feature is in beta, be aware that flows might have side effects on one another.
    Each thread will use a different IO dict, but they will all share the same message list."""
    max_workers: Optional[int] = None
    """The number of workers to use in case of parallel execution."""

    ITERATED_INPUT: ClassVar[str] = "iterated_input"
    """Input key for the iterable to use the ``MapStep`` on."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        unpack_input = getattr(self, "unpack_input", {})
        if not unpack_input:
            return []
        iterated_input_names = set(unpack_input.keys())

        # inputs that are not iterated
        flow_inputs = getattr(self.flow, "inputs", []) if hasattr(self, "flow") else []
        resolved_inputs = {
            property_.title: property_.model_copy(update={"title": property_.title})
            for property_ in flow_inputs
            if property_.title not in iterated_input_names
        }

        # can take the inside flow var type
        inside_var_name = next(iter(unpack_input))
        item_value_type = next(
            property_ for property_ in flow_inputs if property_.title == inside_var_name
        )

        resolved_inputs[self.ITERATED_INPUT] = ListProperty(
            title=self.ITERATED_INPUT,
            description="iterated input for the map step",
            item_type=item_value_type,
        )
        return list(resolved_inputs.values())

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return self.outputs or []


class PluginRegexNode(ExtendedNode):
    """Node to extract information from a raw text using a regular expression (regex)."""

    regex_pattern: Union[PluginRegexPattern, str]
    """Specify the regex pattern for searching in the input text."""

    return_first_match_only: bool = True
    """Whether to return only the first match. If set to False the step output will be a list."""

    DEFAULT_INPUT_KEY: ClassVar[str] = "text"
    """Input key for the name to transition to next."""

    DEFAULT_OUTPUT_KEY: ClassVar[str] = "output"
    """Input key for the name to transition to next."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return [StringProperty(title=PluginRegexNode.DEFAULT_INPUT_KEY)]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if self.return_first_match_only:
            return [StringProperty(title=PluginRegexNode.DEFAULT_OUTPUT_KEY)]
        else:
            return [
                ListProperty(
                    item_type=StringProperty(title=f"{PluginRegexNode.DEFAULT_OUTPUT_KEY}_item"),
                    title=PluginRegexNode.DEFAULT_OUTPUT_KEY,
                )
            ]


class PluginTemplateNode(ExtendedNode):
    """Node to render a template given some inputs."""

    template: str
    """The template to be rendered when this node is executed"""

    OUTPUT: ClassVar[Literal["output"]] = "output"
    """Output key for the rendered template."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return get_placeholder_properties_from_string_with_jinja_loops(
            getattr(self, "template", "")
        )

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return [StringProperty(title=PluginTemplateNode.OUTPUT)]


class PluginChoiceNode(ExtendedNode):
    """
    Node that decides what next step to go to (control flow change) based on an input and description
    of the next steps, powered by a LLM. If the next step named as an explicit mapping to some existing value,
    please use the ``BranchingNode``, which is similar to this step but doesn't use any LLM.

    It outputs the selected choice index so that it can be consumed by downstream nodes if they need it,
    as well as the full text given back by the LLM.
    """

    llm_config: LlmConfig
    """LLM configuration that is used to determine the choice of next step"""

    next_branches: List[List[str]]
    """
    List of lists containing the name and a description for each possible branch. It must follow
    the format ``[branch_name, branch_description]`` or
    ``[branch_name, branch_description, branch_display_name]``. In this second case, only the
    displayed_step_name will be passed in the prompt for making the branching choice.
    """

    prompt_template: str = ""
    """
    Prompt template to be used to have the LLM determine the next step to transition to. Defaults
    to ``PluginChoiceNode.DEFAULT_CHOICE_SELECTION_TEMPLATE``.
    """

    num_tokens: int = 7
    """Upper limit on the number of tokens that can be generated by the LLM."""

    INPUT: ClassVar[str] = "input"
    """Input key for the input to be used to determine the next step to transition to."""

    SELECTED_CHOICE: ClassVar[str] = "selected_choice"
    """Output key for the raw next step decision generated by the LLM."""

    LLM_OUTPUT: ClassVar[str] = "llm_output"
    """Output key for the final next step decision after parsing the LLM decision."""

    DEFAULT_CHOICE_SELECTION_TEMPLATE: ClassVar[str] = _DEFAULT_CHOICE_SELECTION_TEMPLATE
    """Default prompt template to be used by the LLM to determine the next step to transition to."""

    BRANCH_DEFAULT: ClassVar[str] = "default"
    """Name of the branch taken in case the LLM is not able to choose a next step"""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return [StringProperty(title=PluginChoiceNode.INPUT)]

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return [
            StringProperty(
                title=PluginChoiceNode.SELECTED_CHOICE,
                description="the selected choice",
                default=PluginChoiceNode.BRANCH_DEFAULT,
            ),
            StringProperty(
                title=PluginChoiceNode.LLM_OUTPUT,
                description="the output from the LLM potentially containing an explanation as to why the selected choice has been chosen",
            ),
        ]

    def _get_inferred_branches(self) -> List[str]:
        return [
            *set(branch_name for branch_name, *_ in getattr(self, "next_branches", [])),
            PluginChoiceNode.BRANCH_DEFAULT,
        ]


class PluginConstantValuesNode(ExtendedNode):
    """Step to provide constant values."""

    constant_values: Dict[str, Any]
    """Dictionary mapping names to constant values."""

    @staticmethod
    def _infer_type(value: str) -> Type[Property]:
        """Infer the type of the configuration value."""
        if isinstance(value, bool):
            # isinstance(True, int) will return true, so we need to have bool at the top
            return BooleanProperty
        elif isinstance(value, int):
            return IntegerProperty
        elif isinstance(value, float):
            return FloatProperty
        elif isinstance(value, str):
            return StringProperty
        else:
            raise ValueError(f"Value of type {type(value)} not supported in ConstantValuesStep.")

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "constant_values"):
            return []

        outputs = getattr(self, "outputs", None)
        if outputs:
            return cast(list[Property], outputs)
        else:
            outputs = []
            for name, constant in self.constant_values.items():
                if not isinstance(name, str):
                    raise ValueError(
                        f"Name of values in the PluginConstantValuesNode must be string, "
                        f"received value with name {name} of type {type(name)}"
                    )
                property_class = PluginConstantValuesNode._infer_type(constant)
                outputs.append(
                    property_class(
                        title=name,
                        description=f"constant value with name {name}",
                    )
                )
            return outputs


class PluginGetChatHistoryNode(ExtendedNode):
    "Step to get messages from the messages list e.g. last 4 messages and return it as output."

    CHAT_HISTORY: ClassVar[str] = "chat_history"
    """Output key for the chat history collected by the ``GetChatHistoryStep``."""
    DEFAULT_OUTPUT_TEMPLATE: ClassVar[str] = _GETCHATHISTORY_DEFAULT_OUTPUT_TEMPLATE
    """Default output template to be used to format the chat history."""

    n: int = 10
    which_messages: PluginMessageSlice = PluginMessageSlice.LAST_MESSAGES
    offset: int = 0
    message_types: Optional[List[PluginMessageType]] = Field(
        default_factory=lambda: [PluginMessageType.USER, PluginMessageType.AGENT]
    )
    output_template: Optional[str] = ""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if not hasattr(self, "output_template"):
            return []

        if self.output_template is None:
            return []

        inputs = [
            prop_
            for prop_ in get_placeholder_properties_from_string(self.output_template)
            if prop_.title != self.CHAT_HISTORY
        ]
        return inputs

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "output_template"):
            return []

        if self.output_template is None:
            output_type = "array"
            description = "the list of chat messages extracted from the messages list"
        else:
            output_type = "string"
            description = "the chat history extracted from the messages list, formatted as a string"

        return [
            Property(
                json_schema=dict(title=self.CHAT_HISTORY, description=description, type=output_type)
            )
        ]


class PluginRetryNode(ExtendedNode):
    """Step that can be used to execute a given ``Flow`` and retries if a success condition is not met."""

    NUM_RETRIES_VAR: ClassVar[str] = "retry_step_num_retries"
    """Output key for the number of retries the retry step took to succeed or exit."""
    SUCCESS_VAR: ClassVar[str] = "retry_step_success"
    """Output key for whether the retry step succeeded in the end or not."""
    MAX_RETRY: ClassVar[int] = 20
    """Global upper limit on the number of retries for the ``RetryStep``."""

    BRANCH_FAILURE: ClassVar[str] = "failure"
    """Name of the branch taken in case the condition is still not met after the maximum number of trials"""

    flow: SerializeAsAny[Flow]
    """Flow to run in the retry node."""
    success_condition: str
    """Name of the variable in the flow that defines success. The success is evaluated
    with ``bool(flow_output[success_condition])``"""
    max_num_trials: int = 5
    """Maximum number of times to retry the flow execution. Defaults to 5.
    ``max_num_trials`` should not exceed ``MAX_RETRY`` retries"""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        if not hasattr(self, "flow"):
            return []
        return self.flow.inputs or []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        if not hasattr(self, "flow"):
            return []

        outputs = [
            o
            for o in (self.flow.outputs or [])
            if o.title != getattr(self, "success_condition", None)
        ]
        return outputs + [
            IntegerProperty(
                title=self.NUM_RETRIES_VAR,
                description="Number of retries the retry step took to succeed or exit",
            ),
            BooleanProperty(
                title=self.SUCCESS_VAR,
                description="Whether the retry step succeeded in the end or not",
            ),
        ]

    def _get_inferred_branches(self) -> List[str]:
        branches = [PluginRetryNode.BRANCH_FAILURE]
        if hasattr(self, "flow"):
            end_nodes = sorted(
                list({node.branch_name for node in self.flow.nodes if isinstance(node, EndNode)})
            )
            branches += end_nodes if end_nodes else super()._get_inferred_branches()
        return branches


class ExtendedAgentNode(ExtendedNode, AgentNode):
    """Extension of the Agent Spec AgentNode. Supports overwriting agent's outputs and caller input mode."""

    caller_input_mode: Optional[SerializeAsEnum[CallerInputMode]] = None
    """Whether the agent is allowed to ask the user questions (CallerInputMode.ALWAYS) or not (CallerInputMode.NEVER).
       If set to NEVER, the step won't be able to yield. Defaults to ``None``, which means it will use the ``caller_input_mode``
       of the underlying agent."""

    def model_post_init(self, __context: Any) -> None:
        """Override of the method used by Component as post-init."""
        if self.caller_input_mode is None and hasattr(self, "agent"):
            self.caller_input_mode = getattr(
                self.agent, "caller_input_mode", CallerInputMode.ALWAYS
            )
        super().model_post_init(__context)

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        return (self.agent.inputs or []) if hasattr(self, "agent") else []

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        outputs: Optional[List[Property]] = getattr(self, "outputs", None)
        agent: Optional[Agent] = getattr(self, "agent", None)
        return (
            outputs if outputs is not None else (agent.outputs or []) if agent is not None else []
        )


class ExtendedParallelFlowNode(ExtendedNode):
    """Execute different flows in parallel."""

    flows: List[SerializeAsAny[Flow]]
    """Sub-flows to run in parallel"""
    max_workers: Optional[int] = None
    """The number of workers to use in case of parallel execution."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        inputs_dict: Dict[str, Property] = {}
        for flow in getattr(self, "flows", []):
            for input_ in flow.inputs or []:
                if input_.title not in inputs_dict:
                    inputs_dict[input_.title] = input_
                else:
                    previous_input_descriptor = inputs_dict[input_.title]
                    # Inputs with the same name must have the same type
                    if not json_schemas_have_same_type(
                        input_.json_schema,
                        previous_input_descriptor.json_schema,
                    ):
                        raise ValueError(
                            f"Two subflows in ExtendedParallelFlowNode have an input descriptor "
                            f"with the same name but different types:\n"
                            f"1) {input_}\n2) {previous_input_descriptor}"
                        )
        return list(inputs_dict.values())

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        outputs_dict: Dict[str, Property] = {}
        for flow in getattr(self, "flows", []):
            for output in flow.outputs or []:
                if output.title not in outputs_dict:
                    outputs_dict[output.title] = output
                else:
                    raise ValueError(
                        f"Found two outputs with the same title `{output.title}` in ExtendedParallelFlowNode subflows."
                    )
        return list(outputs_dict.values())

    @model_validator_with_error_accumulation
    def _validate_inputs_with_same_name_and_different_type_do_not_exist(self) -> Self:
        """Check that there aren't inputs with the same name and different type"""
        union_of_inputs: Dict[str, Property] = dict()
        for input_property in getattr(self, "inputs", []):
            if input_property.title not in union_of_inputs:
                union_of_inputs[input_property.title] = input_property
            elif not properties_have_same_type(
                input_property, union_of_inputs[input_property.title]
            ):
                raise ValueError(
                    f"Two subflows of ExtendedParallelFlowNode `{getattr(self, 'name', '')}` have inputs with "
                    f"the same name `{input_property.title}`, but different types:\n"
                    f"{union_of_inputs[input_property.title].json_schema}\n"
                    f"{input_property.json_schema}\n"
                )
        return self

    @model_validator_with_error_accumulation
    def _validate_outputs_with_same_name_do_not_exist(self) -> Self:
        """Check that there aren't outputs with the same name"""
        union_of_outputs: Set[str] = set()
        for output_property in getattr(self, "outputs", []):
            if output_property.title in union_of_outputs:
                raise ValueError(
                    f"Two subflows of ExtendedParallelFlowNode `{getattr(self, 'name', '')}` have outputs with "
                    f"the same name `{output_property.title}`."
                )
            union_of_outputs.add(output_property.title)
        return self


class ExtendedParallelMapNode(ExtendedNode):
    """Extension of the Agent Spec ParallelMapNode. Enforces parallel execution."""

    flow: Flow
    """Flow that is being executed with each iteration of the input."""
    unpack_input: Dict[str, str] = Field(default_factory=dict)
    """Mapping to specify how to unpack when each iter item is a ``dict``
    and we need to map its element to the inside flow inputs."""
    max_workers: Optional[int] = None
    """The number of workers to use in case of parallel execution."""

    ITERATED_INPUT: ClassVar[str] = "iterated_input"
    """Input key for the iterable to use the ``MapStep`` on."""

    def _get_non_mapped_inferred_inputs(self) -> List[Property]:
        unpack_input = getattr(self, "unpack_input", {})
        if not unpack_input:
            return []
        iterated_input_names = set(unpack_input.keys())

        # inputs that are not iterated
        flow_inputs = getattr(self.flow, "inputs", []) if hasattr(self, "flow") else []
        resolved_inputs = {
            property_.title: property_.model_copy(update={"title": property_.title})
            for property_ in flow_inputs
            if property_.title not in iterated_input_names
        }

        # can take the inside flow var type
        inside_var_name = next(iter(unpack_input))
        item_value_type = next(
            property_ for property_ in flow_inputs if property_.title == inside_var_name
        )

        resolved_inputs[self.ITERATED_INPUT] = ListProperty(
            title=self.ITERATED_INPUT,
            description="iterated input for the map step",
            item_type=item_value_type,
        )
        return list(resolved_inputs.values())

    def _get_non_mapped_inferred_outputs(self) -> List[Property]:
        return getattr(self, "outputs", []) or []


NODES_PLUGIN_NAME = "NodesPlugin"

nodes_serialization_plugin = PydanticComponentSerializationPlugin(
    name=NODES_PLUGIN_NAME,
    component_types_and_models={
        PluginCatchExceptionNode.__name__: PluginCatchExceptionNode,
        PluginExtractNode.__name__: PluginExtractNode,
        PluginInputMessageNode.__name__: PluginInputMessageNode,
        PluginOutputMessageNode.__name__: PluginOutputMessageNode,
        ExtendedToolNode.__name__: ExtendedToolNode,
        ExtendedLlmNode.__name__: ExtendedLlmNode,
        ExtendedMapNode.__name__: ExtendedMapNode,
        ExtendedAgentNode.__name__: ExtendedAgentNode,
        PluginRegexNode.__name__: PluginRegexNode,
        PluginTemplateNode.__name__: PluginTemplateNode,
        PluginChoiceNode.__name__: PluginChoiceNode,
        PluginReadVariableNode.__name__: PluginReadVariableNode,
        PluginVariableNode.__name__: PluginVariableNode,
        PluginWriteVariableNode.__name__: PluginWriteVariableNode,
        PluginConstantValuesNode.__name__: PluginConstantValuesNode,
        PluginGetChatHistoryNode.__name__: PluginGetChatHistoryNode,
        PluginRetryNode.__name__: PluginRetryNode,
        ExtendedParallelFlowNode.__name__: ExtendedParallelFlowNode,
        ExtendedParallelMapNode.__name__: ExtendedParallelMapNode,
    },
)
nodes_deserialization_plugin = PydanticComponentDeserializationPlugin(
    name=NODES_PLUGIN_NAME,
    component_types_and_models={
        PluginCatchExceptionNode.__name__: PluginCatchExceptionNode,
        PluginExtractNode.__name__: PluginExtractNode,
        PluginInputMessageNode.__name__: PluginInputMessageNode,
        PluginOutputMessageNode.__name__: PluginOutputMessageNode,
        ExtendedToolNode.__name__: ExtendedToolNode,
        ExtendedLlmNode.__name__: ExtendedLlmNode,
        ExtendedMapNode.__name__: ExtendedMapNode,
        ExtendedAgentNode.__name__: ExtendedAgentNode,
        PluginRegexNode.__name__: PluginRegexNode,
        PluginTemplateNode.__name__: PluginTemplateNode,
        PluginChoiceNode.__name__: PluginChoiceNode,
        PluginReadVariableNode.__name__: PluginReadVariableNode,
        PluginVariableNode.__name__: PluginVariableNode,
        PluginWriteVariableNode.__name__: PluginWriteVariableNode,
        PluginConstantValuesNode.__name__: PluginConstantValuesNode,
        PluginGetChatHistoryNode.__name__: PluginGetChatHistoryNode,
        PluginRetryNode.__name__: PluginRetryNode,
        ExtendedParallelFlowNode.__name__: ExtendedParallelFlowNode,
        ExtendedParallelMapNode.__name__: ExtendedParallelMapNode,
    },
)
