# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import inspect
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Union,
    cast,
    overload,
)

from deprecated import deprecated
from pydantic import PydanticSchemaGenerationError, create_model

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.async_helpers import (
    is_coroutine_function,
    run_async_in_sync,
    run_sync_in_process,
    run_sync_in_thread,
)
from wayflowcore.executors.executionstatus import (
    FinishedStatus,
    ToolExecutionConfirmationStatus,
    ToolRequestStatus,
    UserMessageRequestStatus,
)
from wayflowcore.executors.interrupts import ExecutionInterrupt, InterruptedExecutionStatus
from wayflowcore.property import JsonSchemaParam, Property

from .flowbasedtools import DescribedFlow
from .toolbox import ToolBox
from .tools import Tool, _make_tool_key

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.executors._flowconversation import FlowConversation
    from wayflowcore.flow import Flow
    from wayflowcore.steps.step import Step


logger = logging.getLogger(__name__)


def _get_params_with_none_default_value_from_callable(func: Callable[[Any], Any]) -> Set[str]:
    has_none_default_set = set()
    func_signature = inspect.signature(func)
    func_parameters = func_signature.parameters
    for param_name, param in func_parameters.items():
        if param.default is None:
            has_none_default_set.add(param_name)
    return has_none_default_set


def transform_python_type_into_json_schema(python_type: type) -> JsonSchemaParam:
    try:
        # https://docs.pydantic.dev/latest/concepts/models/#dynamic-model-creation
        CustomModel = create_model("CustomModel", data=(python_type, ...))
        json_schema: JsonSchemaParam = CustomModel.model_json_schema()["properties"]["data"]
        del json_schema["title"]  # was added because of the name of the variable above
        return json_schema
    except PydanticSchemaGenerationError:
        return {}


LangchainToolTypeT = Any


def find_output_schema_from_langchain_tool(
    tool: LangchainToolTypeT,
) -> JsonSchemaParam:
    output_schema: Dict[str, Any] = {}
    try:
        output_schema = tool.output_schema.schema()
    except PydanticSchemaGenerationError:
        pass
    # langchain adds a title, we don't want it by default
    output_schema.pop("title", None)
    if "type" not in output_schema and hasattr(tool.func, "__annotations__"):
        return_annotation = tool.func.__annotations__.get("return")
        if return_annotation is not None:
            output_schema.update(
                transform_python_type_into_json_schema(return_annotation),
            )

    return cast(JsonSchemaParam, output_schema)


def find_json_schema_from_annotation(param_data: type) -> JsonSchemaParam:
    return transform_python_type_into_json_schema(param_data)


class ServerTool(Tool):
    """
    Contains the description and callable of a tool, including its name, documentation and schema of its
    arguments. This tool is executed on the server side, with the provided callable.

    Attributes
    ----------
    name:
        name of the tool
    description:
        description of the tool
    input_descriptors:
        list of properties describing the inputs of the tool.
    output_descriptors:
        list of properties describing the outputs of the tool.

        If there is a single output descriptor, the tool needs to just return the value.
        If there are several output descriptors, the tool needs to return a dict of all expected values.

        If no output descriptor is passed, or if a single output descriptor is passed without a name, the output will
        be automatically be named ``Tool.DEFAULT_TOOL_NAME``.
    func: Callable
        tool callable
    requires_confirmation: bool
        Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus during execution.

    Examples
    --------
    >>> from wayflowcore.tools import ServerTool
    >>> from wayflowcore.property import FloatProperty

    >>> def add_tool(arg1, arg2):
    ...    return arg1 + arg2

    >>> addition_client_tool = ServerTool(
    ...     name="add_tool",
    ...     description="Simply adds two numbers",
    ...     input_descriptors=[
    ...         FloatProperty(name="a", description="the first number", default_value= 0.0),
    ...         FloatProperty(name="b", description="the second number"),
    ...     ],
    ...     output_descriptors=[FloatProperty()],
    ...     func=add_tool,
    ... )

    You can also write tools with several outputs. Make sure the tool returns a dict with the appropriate names
    and types, and specify the ``output_descriptors``:

    >>> from typing import Any, Dict
    >>> from wayflowcore.property import StringProperty, IntegerProperty
    >>> def some_func(a: int, b: str) -> Dict[str, Any]:
    ...     return {'renamed_a': a, 'renamed_b': b} # keys and types of values need to correspond to output_descriptors
    >>> tool = ServerTool(
    ...     name='my_tool',
    ...     description='some description',
    ...     input_descriptors=[
    ...         IntegerProperty(name='a'),
    ...         StringProperty(name='b'),
    ...     ],
    ...     output_descriptors=[
    ...         IntegerProperty(name='renamed_a'),
    ...         StringProperty(name='renamed_b'),
    ...     ],
    ...     func=some_func,
    ... )


    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        parameters: Optional[Dict[str, JsonSchemaParam]] = None,
        output: Optional[JsonSchemaParam] = None,
        id: Optional[str] = None,
        _cpu_bounded: bool = False,
        __metadata_info__: Optional[MetadataType] = None,
        requires_confirmation: bool = False,
    ):
        # _cpu_bounded:
        #   Whether the tool can be ran in a separate process (for cpu-bound
        #   functions with no outside variable access) or not, in which case it's ran
        #   in a separate thread.
        if not callable(func):
            raise ValueError(f"Should pass a callable `func` but was: {func!r}")

        self.func = func
        self._cpu_bounded = _cpu_bounded
        super().__init__(
            name=name,
            description=description,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            parameters=parameters,
            output=output,
            id=id,
            __metadata_info__=__metadata_info__,
            requires_confirmation=requires_confirmation,
        )

    async def run_async(self, *args: Any, **kwargs: Any) -> Any:
        """
        Runs the tool in an asynchronous manner, no matter the
        synchronous or asynchronous aspect of its `func` attribute.
        If `func` is synchronous, it will run in an anyio worker thread.
        """
        if is_coroutine_function(self.func):
            return await self.func(*args, **kwargs)
        else:
            # wrap to handle named arguments
            def _wrap() -> Any:
                return self.func(*args, **kwargs)

            if self._cpu_bounded:
                return await run_sync_in_process(_wrap)
            else:
                return await run_sync_in_thread(_wrap)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Runs the tool in a synchronous manner, no matter the
        synchronous or asynchronous aspect of its `func` attribute.
        """
        if not is_coroutine_function(self.func):
            return self.func(*args, **kwargs)
        else:
            # wrap to handle named arguments
            async def _wrap() -> Any:
                return await self.func(*args, **kwargs)

            return run_async_in_sync(_wrap)

    @classmethod
    def from_langchain(cls, tool: LangchainToolTypeT) -> "ServerTool":
        """
        Converts a usual Langchain tool into a server-side tool that will be executed on the server.

        Parameters
        ----------
        tool:
            langchain tool to convert
        """
        if tool.func is None:
            raise ValueError("The langchain tool must have a func but was None")

        # fixing a langchain bug: a None default value means the argument is required for Langchain
        # we fix this by checking whether the default is None, and if yes set the json schema parameter
        # default to None
        has_none_default_parameter_set = _get_params_with_none_default_value_from_callable(
            tool.func
        )

        tool_parameters = tool.args
        for tool_name, tool_json_schema in tool_parameters.items():
            if tool_name in has_none_default_parameter_set:
                tool_json_schema["default"] = None

        return ServerTool(
            name=tool.name,
            description=tool.description,
            parameters=tool_parameters,
            func=tool.func,
            output=find_output_schema_from_langchain_tool(tool),
        )

    @classmethod
    def from_flow(
        cls,
        flow: "Flow",
        flow_name: str,
        flow_description: str,
        flow_output: Optional[Union[List[str], str]] = None,
    ) -> "ServerTool":
        """
        Converts a flow into a server-side tool that will be executed on the server.

        Parameters
        ----------
        flow:
            The flow to be executed as the tool
        flow_name:
            The name given to the flow to be used as the tool name
        flow_description:
            The description to be used as description of the tool
        flow_output:
            Optional list of flow outputs to collect. By default will collect all flow outputs,
            otherwise will only collect the outputs which names are specified in this argument.

        Raises
        ------
        ValueError
            If the input flow is a potentially-yielding flow (conversion to ``ServerTool`` is not
            supported).
        """
        if flow.might_yield:
            raise ValueError(f"The flow '{flow_name}' might yield. It cannot be used as a tool.")
        if flow_output is not None:
            flow_outputs = flow_output if isinstance(flow_output, list) else [flow_output]
            for flow_output in flow_outputs:
                if flow_output not in flow.output_descriptors_dict:
                    raise ValueError(
                        f"The flow or step '{flow_name}' does not have an output named '{flow_output}'"
                    )
            output_descriptors = [
                descriptor
                for descriptor in flow.output_descriptors
                if descriptor.name in flow_outputs
            ]
        else:
            output_descriptors = flow.output_descriptors
            flow_outputs = None
        func = _FlowAsToolCallable(flow, flow_outputs)
        return ServerTool(
            name=flow_name,
            description=flow_description,
            input_descriptors=flow.input_descriptors,
            output_descriptors=output_descriptors,
            func=func,
        )

    @classmethod
    def from_step(
        cls,
        step: "Step",
        step_name: str,
        step_description: str,
        step_output: Optional[Union[str, List[str]]] = None,
    ) -> "ServerTool":
        """
        Converts a step into a server-side tool that will be executed on the server.

        Parameters
        ----------
        step:
            The step to be executed as the tool
        step_name:
            The name given to the step to be used as the tool name
        step_description:
            The description to be used as description of the tool
        step_output:
            Optional list of flow outputs to collect. By default will collect all flow outputs,
            otherwise will only collect the outputs which names are specified in this argument.

        Raises
        ------
        ValueError
            If the input step is a potentially-yielding step (conversion to ``ServerTool`` is not
            supported).
        """
        from wayflowcore.flowhelpers import create_single_step_flow

        if step.might_yield:
            raise ValueError(f"The step '{step_name}' might yield. It cannot be used as a tool.")

        return cls.from_flow(
            create_single_step_flow(step),
            step_name,
            step_description,
            step_output,
        )

    @classmethod
    def from_any(
        cls,
        tool: Union[
            "ServerTool",
            "Flow",
            "Step",
            DescribedFlow,
            LangchainToolTypeT,
        ],
        **kwargs: Any,
    ) -> "ServerTool":
        from wayflowcore.flow import Flow
        from wayflowcore.steps.step import Step

        if isinstance(tool, ServerTool):
            return tool
        elif isinstance(tool, Flow):
            return cls.from_flow(tool, **kwargs)
        elif isinstance(tool, Step):
            return cls.from_step(tool, **kwargs)
        elif isinstance(tool, DescribedFlow):
            return cls.from_flow(
                tool.flow,
                tool.name,
                tool.description,
                tool.output,
            )
        else:
            try:
                return cls.from_langchain(tool)
            except Exception as e:
                raise ValueError(
                    f"Conversion from `{tool.__class__.__name__}` to `ServerTool` not supported. Supported types: "
                    f"LangchainStructuredTool, LangchainTool, Flow, Step. Encountered error: {e}"
                )

    def _bind_parent_conversation_if_applicable(self, parent_conversation: "Conversation") -> None:
        if isinstance(self.func, _FlowAsToolCallable):
            self.func._parent_conversation = parent_conversation
        else:
            pass  # No need to bind the conversation for callables that are not flows


class _FlowAsToolCallable:
    """A stateful callable for flows that can be bound to a conversation"""

    def __init__(self, flow: "Flow", flow_outputs: Optional[List[str]]):
        self.flow = flow
        self.flow_outputs = flow_outputs
        self._parent_conversation: Optional["Conversation"] = None

    # Types of this callable will depend on the tool and are defined by `server_tool.parameters`
    # and `server_tool.output`
    async def __func__(self, **inputs: Any) -> Any:
        return await self.__call__(**inputs)

    async def __call__(self, **inputs: Any) -> Any:
        conversation: "FlowConversation"
        interrupts: Optional[List["ExecutionInterrupt"]] = None
        if self._parent_conversation is None:
            conversation = self.flow.start_conversation(inputs)
            interrupts = []
        else:
            conversation = self.flow.start_conversation(
                inputs=inputs,
                messages=self._parent_conversation.message_list,
            )
            interrupts = self._parent_conversation._get_interrupts()

        status = await conversation.execute_async(execution_interrupts=interrupts)
        # Removes the bounded conversation such that we avoid calling the tool again on this same
        # parent conversation.
        self._parent_conversation = None

        if isinstance(
            status, (UserMessageRequestStatus, ToolRequestStatus, ToolExecutionConfirmationStatus)
        ):
            raise ValueError(
                "A server tool was configured with a flow that yield. This is not allowed."
            )
        if isinstance(status, InterruptedExecutionStatus):
            raise ValueError(
                f"Execution of the tool failed because of an interruption with reason: "
                f"'{status.reason}'"
            )
        if not isinstance(status, FinishedStatus):
            raise ValueError(
                f"The execution of the flow as tool completed with an unsupported status: "
                f"'{status}'"
            )
        if self.flow_outputs is None:
            return status.output_values
        elif len(self.flow_outputs) == 0:
            return None
        elif len(self.flow_outputs) == 1:
            return status.output_values[self.flow_outputs[0]]
        else:
            return {
                flow_output: status.output_values[flow_output] for flow_output in self.flow_outputs
            }


@deprecated(
    "You passed some legacy tools to the wayflowcore APIs (one of LangchainStructuredTool, LangchainTool, "
    "Flow, Step). To benefit from the latest improvements, please first convert "
    "your legacy tools using the provided functions (available as class methods of `ServerTool`) and pass them"
    "to the wayflowcore APIs."
)
def _convert_previously_supported_tool_into_server_tool(
    tool: Union["Flow", "Step", LangchainToolTypeT],
) -> "ServerTool":
    return ServerTool.from_any(tool)


@overload
def _convert_previously_supported_tools_if_needed(tools: None) -> None: ...


@overload
def _convert_previously_supported_tools_if_needed(
    tools: Sequence[
        Union[
            LangchainToolTypeT,
            "Flow",
            "Step",
            Tool,
        ]
    ],
) -> List[Tool]: ...


def _convert_previously_supported_tools_if_needed(
    tools: Optional[
        Sequence[
            Union[
                LangchainToolTypeT,
                "Flow",
                "Step",
                Tool,
                "ToolBox",
            ]
        ]
    ],
) -> Optional[Sequence[Union[Tool, ToolBox]]]:
    if tools is None:
        return None
    return [
        (
            _convert_previously_supported_tool_into_server_tool(t)
            if not isinstance(t, (Tool, ToolBox))
            else t
        )
        for t in tools
    ]


def _convert_previously_supported_tool_if_needed(
    tool: Union[
        LangchainToolTypeT,
        "Flow",
        "Step",
        Tool,
    ],
) -> Tool:
    return _convert_previously_supported_tools_if_needed([tool])[0]


def register_server_tool(
    tool: ServerTool, registered_tools: Dict[str, ServerTool]
) -> Dict[str, ServerTool]:
    if not isinstance(tool, ServerTool):
        raise TypeError(f"Tool {tool} is not a `ServerTool`")
    registered_tools[_make_tool_key(tool.name, registered_tools)] = tool
    logger.info("Registered Server Tool: %s", tool.name)
    return registered_tools
