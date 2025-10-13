# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.formatting import generate_tool_id
from wayflowcore.events.event import ToolExecutionResultEvent, ToolExecutionStartEvent
from wayflowcore.events.eventlistener import record_event
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import ClientTool, Tool, ToolRequest
from wayflowcore.tools.servertools import ServerTool, _convert_previously_supported_tool_if_needed
from wayflowcore.tools.tools import TOOL_OUTPUT_NAME, ToolResult
from wayflowcore.tracing.span import ToolExecutionSpan

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)


class ToolExecutionStep(Step):
    """Step to execute a WayFlow tool. This step does not require the use of LLMs."""

    TOOL_OUTPUT = TOOL_OUTPUT_NAME
    """str: Output key for the result obtained from executing the tool."""
    TOOL_REQUEST_UUID = "tool_request_uuid"
    """str: Output key for uuid of the tool request (useful when using ``ClientTool``)"""

    def __init__(
        self,
        tool: Tool,
        raise_exceptions: bool = True,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
        name: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):
        """
        Note
        ----

        A step has input and output descriptors, describing what values the step requires to run and what values it produces.

        **Input descriptors**

        By default, when ``input_descriptors`` is set to ``None``, the input descriptors will be inferred from
        the arguments of the tool, with one input descriptor per argument.

        **Output descriptors**

        By default, when ``output_descriptors`` is set to ``None``, this step will have the same output descriptors
        as the tool. By default, if the tool has a single output, the name will be ``ToolExecutionStep.TOOL_OUTPUT``,
        of the same type as the return type of the tool, which represents the result returned by the tool.

        If you provide a list of output descriptors, each descriptor passed will override the automatically
        detected one, in particular using the new type instead of the detected one.
        If some of them are missing, an error will be thrown at instantiation of the step.

        If you provide input descriptors for non-autodetected variables, a warning will be emitted, and
        they won't be used during the execution of the step.

        Parameters
        ----------
        tool:
            The tool to be executed.
        raise_exceptions:
            Whether to raise or not exceptions raised by the tool. If ``False``, it will put the error message as the result
            of the tool if the tool output type is string.
        input_descriptors:
            Input descriptors of the step. ``None`` means the step will resolve the input descriptors automatically using its static configuration in a best effort manner.

        output_descriptors:
            Output descriptors of the step. ``None`` means the step will resolve them automatically using its static
            configuration in a best effort manner.

        name:
            Name of the step.

        input_mapping:
            Mapping between the name of the inputs this step expects and the name to get it from in the conversation input/output dictionary.

        output_mapping:
            Mapping between the name of the outputs this step expects and the name to get it from in the conversation input/output dictionary.

        Examples
        --------
        >>> from wayflowcore.flowhelpers import create_single_step_flow
        >>> from wayflowcore.steps import ToolExecutionStep
        >>> from wayflowcore.tools import ServerTool
        >>> from wayflowcore.property import FloatProperty
        >>>
        >>> square_root_tool = ServerTool(
        ...     name="compute_square_root",
        ...     description="Computes the square root of a number",
        ...     input_descriptors=[FloatProperty(name="x", description="The number to use")],
        ...     func=lambda x: x**0.5,
        ...     output_descriptors=[FloatProperty()]
        ... )
        >>> step = ToolExecutionStep(tool=square_root_tool)
        >>> assistant = create_single_step_flow(step)
        >>> conversation = assistant.start_conversation(inputs={"x": 123456789.0})
        >>> status = conversation.execute()
        >>> print(status.output_values)
        {'tool_output': 11111.111060555555}

        """
        self.tool: Tool = _convert_previously_supported_tool_if_needed(tool)
        self._is_client_tool = isinstance(self.tool, ClientTool)
        self._is_server_tool = isinstance(self.tool, ServerTool)
        self.raise_exceptions = raise_exceptions

        super().__init__(
            step_static_configuration=dict(
                tool=tool,
                raise_exceptions=raise_exceptions,
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
        return {"tool": Tool, "raise_exceptions": bool}

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        tool = self.tool
        if isinstance(tool, ClientTool):
            return self._handle_client_tool(tool, conversation, inputs)
        elif isinstance(tool, ServerTool):
            return await self._handle_server_tool(tool, conversation, inputs)
        else:
            raise ValueError(f"Unsupported tool type: {self.tool.__class__.__name__}")

    @property
    def might_yield(self) -> bool:
        # The tool execution yields if its tool is a client tool **because** in this case it will
        # give tool execution instructions to the client and wait for the tool results.
        return self._is_client_tool

    @property
    def supports_dict_io_with_non_str_keys(self) -> bool:
        return True

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(
        cls,
        tool: Tool,
        raise_exceptions: bool,
    ) -> List[Property]:
        tool = _convert_previously_supported_tool_if_needed(tool)
        return tool.input_descriptors

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(
        cls,
        tool: Tool,
        raise_exceptions: bool,
    ) -> List[Property]:
        tool = _convert_previously_supported_tool_if_needed(tool)
        return tool.output_descriptors

    def _handle_client_tool(
        self,
        tool: ClientTool,
        conversation: "FlowConversation",
        inputs: Dict[str, Any],
    ) -> StepResult:
        # The ToolExecutionStep uses an internal context to store a tool_request_uuid. This is
        # helpful because it allows for the step to know whether it is invoked in order to create
        # a TOOL_REQUEST message or whether it is invoked a second time in order to read the tool's
        # output from a TOOL_RESULT message.
        tool_request_uuid = conversation._get_internal_context_value_for_step(
            self,
            ToolExecutionStep.TOOL_REQUEST_UUID,
        )
        if tool_request_uuid is None:
            # initial call, we will ask the user
            tool_request_uuid = self._append_tool_request_message(conversation, inputs)
            record_event(
                ToolExecutionStartEvent(
                    tool=tool,
                    tool_request=ToolRequest(
                        name=tool.name,
                        tool_request_id=tool_request_uuid,
                        args=inputs,
                    ),
                )
            )
            return StepResult(
                outputs={}, branch_name=self.BRANCH_SELF, step_type=StepExecutionStatus.YIELDING
            )

        tool_output = self._get_tool_output_from_tool_result_message(
            conversation, tool_request_uuid
        )
        conversation._put_internal_context_key_value_for_step(
            self, ToolExecutionStep.TOOL_REQUEST_UUID, None
        )
        record_event(
            ToolExecutionResultEvent(
                tool=tool,
                tool_result=ToolResult(
                    tool_request_id=tool_request_uuid,
                    content=tool_output,
                ),
            )
        )
        return StepResult(
            outputs=self._convert_tool_output_into_output_dict(
                tool=tool,
                tool_output=tool_output,
            )
        )

    async def _handle_server_tool(
        self,
        tool: ServerTool,
        conversation: "FlowConversation",
        inputs: Dict[str, Any],
    ) -> StepResult:
        tool._bind_parent_conversation_if_applicable(conversation)
        tool_request_id = generate_tool_id()
        with ToolExecutionSpan(
            tool=tool,
            tool_request=ToolRequest(
                name=tool.name,
                args=inputs,
                tool_request_id=tool_request_id,
            ),
        ) as span:
            tool_output = await self._execute_tool(tool, inputs)
            span.record_end_span_event(
                output=tool_output,
            )
        return StepResult(
            outputs=self._convert_tool_output_into_output_dict(
                tool=tool,
                tool_output=tool_output,
            )
        )

    async def _execute_tool(self, tool: ServerTool, inputs: Dict[str, Any]) -> Any:
        try:
            tool_output = await tool.run_async(**inputs)
        except Exception as e:
            if self.raise_exceptions:
                raise e
            else:
                tool_output = str(e)
        return tool_output

    def _convert_tool_output_into_output_dict(
        self, tool: Tool, tool_output: Any
    ) -> Dict[str, type]:
        outputs = {}
        if len(tool.output_descriptors) == 1:
            # tool output is the value that should be returned
            outputs = {self._internal_output_descriptors[0].name: tool_output}
        elif len(tool.output_descriptors) > 1:
            # tool output is a dict containing all values
            if not isinstance(tool_output, dict):
                raise ValueError(
                    f"The tool has several outputs, it should return a dictionary, but it returned: {tool_output} of type: {type(tool_output)}"
                )

            if not all(
                tool_descriptor.name in tool_output for tool_descriptor in tool.output_descriptors
            ):
                raise ValueError(
                    f"The tool did not return all expected outputs: It is configured with these output descriptors:"
                    f"{tool.output_descriptors}\n but returned these outputs: {tool_output}.\n"
                    f"Missing outputs are: {[tool_descriptor.name for tool_descriptor in tool.output_descriptors if tool_descriptor.name not in tool_output]}"
                )

            outputs = {
                descriptor.name: tool_output[descriptor.name]
                for descriptor in self._internal_output_descriptors
            }
        return outputs

    def _append_tool_request_message(
        self, conversation: "FlowConversation", inputs: Dict[str, Any]
    ) -> str:
        tool_request_uuid = generate_tool_id()
        conversation._put_internal_context_key_value_for_step(
            self, ToolExecutionStep.TOOL_REQUEST_UUID, tool_request_uuid
        )
        conversation.append_message(
            Message(
                tool_requests=[
                    ToolRequest(
                        name=self.tool.name,
                        args=inputs,
                        tool_request_id=tool_request_uuid,
                    )
                ],
                role="user",
            )
        )

        return tool_request_uuid

    def _get_tool_output_from_tool_result_message(
        self, conversation: "FlowConversation", tool_request_uuid: str
    ) -> Any:
        try:
            tool_result_content = next(
                message.tool_result.content
                for message in reversed(conversation.get_messages())
                if message.message_type == MessageType.TOOL_RESULT
                if (
                    message.tool_result is not None
                    and message.tool_result.tool_request_id == tool_request_uuid
                )
            )
        except StopIteration:
            messages_as_str = "\n".join(str(m) for m in conversation.get_messages())
            raise ValueError(
                f"The ToolExecutionStep was expecting a tool result message with id "
                f"{tool_request_uuid}, but did not find any: {messages_as_str}"
            )
        return tool_result_content

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {self.tool.id: self.tool}
