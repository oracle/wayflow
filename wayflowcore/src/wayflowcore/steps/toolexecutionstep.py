# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.formatting import generate_tool_id
from wayflowcore.events.event import (
    ToolConfirmationRequestEndEvent,
    ToolConfirmationRequestStartEvent,
)
from wayflowcore.events.eventlistener import record_event
from wayflowcore.exceptions import AuthInterrupt
from wayflowcore.executors.executionstatus import ToolExecutionConfirmationStatus
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepExecutionStatus, StepResult
from wayflowcore.tools import ClientTool, ToolRequest
from wayflowcore.tools.servertools import ServerTool, _convert_previously_supported_tool_if_needed
from wayflowcore.tools.tools import TOOL_OUTPUT_NAME, Tool, ToolResult

if TYPE_CHECKING:
    from wayflowcore.executors._flowconversation import FlowConversation

logger = logging.getLogger(__name__)

_TOOL_REJECTION_REASON = "Tool Request for tool {tool} denied due to reason: {reason}"


class ToolExecutionStep(Step):
    """Step to execute a WayFlow tool. This step does not require the use of LLMs."""

    TOOL_OUTPUT = TOOL_OUTPUT_NAME
    """str: Output key for the result obtained from executing the tool."""
    TOOL_REQUEST = "tool_request"
    """str: ToolRequest for uuid of the tool request (useful when using tools requiring confirmation)"""

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

    def _get_or_create_tool_request(
        self, inputs: Dict[str, Any], conversation: "FlowConversation"
    ) -> Tuple["ToolRequest", bool]:
        """
        Create/get ToolRequest and manage UUID state
        """
        tool_request: Optional[ToolRequest]
        tool_request = conversation._get_internal_context_value_for_step(
            self,
            ToolExecutionStep.TOOL_REQUEST,
        )
        if tool_request is None:
            new_uuid = generate_tool_id()
            new_tool_request = ToolRequest(
                name=self.tool.name, args=inputs, tool_request_id=new_uuid
            )
            conversation._put_internal_context_key_value_for_step(
                self, ToolExecutionStep.TOOL_REQUEST, new_tool_request
            )
            return new_tool_request, False
        else:
            return tool_request, True

    async def _invoke_step_async(
        self,
        inputs: Dict[str, Any],
        conversation: "FlowConversation",
    ) -> StepResult:
        from wayflowcore.events.event import ToolExecutionStartEvent

        tool_request, tool_request_exists = self._get_or_create_tool_request(inputs, conversation)

        # 1. If confirmation required and not yet started, queue a confirmation request
        if self.tool.requires_confirmation and not tool_request_exists:
            tool_request._requires_confirmation = True
            record_event(
                ToolConfirmationRequestStartEvent(
                    tool=self.tool,
                    tool_request=tool_request,
                )
            )
            return StepResult(
                outputs={
                    "__execution_status__": ToolExecutionConfirmationStatus(
                        tool_requests=[tool_request], _conversation_id=conversation.id
                    )
                },
                branch_name=self.BRANCH_SELF,
                step_type=StepExecutionStatus.YIELDING,
            )

        # 2. If confirmation needed, check confirmation result
        tool_result: Optional[ToolResult]
        if self.tool.requires_confirmation:
            record_event(
                ToolConfirmationRequestEndEvent(
                    tool=self.tool,
                    tool_request=tool_request,
                )
            )
            if tool_request._tool_execution_confirmed is None:
                raise ValueError(
                    "Missing tool confirmation, "
                    "please make sure to either confirm or reject the tool execution before resuming the conversation."
                )

            if not tool_request._tool_execution_confirmed:
                # User rejected execution
                if self.raise_exceptions:
                    raise ValueError(
                        "Tool Execution was rejected by the user. "
                        "This error is being raised because flow outputs need to be structured and rejecting tool execution could break the flow. "
                        "Set raise_exceptions=False to set the rejection reason as the tool output"
                    )
                tool_output = _TOOL_REJECTION_REASON.format(
                    tool=self.tool, reason=tool_request._tool_rejection_reason
                )
                tool_result = ToolResult(
                    content=tool_output, tool_request_id=tool_request.tool_request_id
                )
            else:
                tool_result = await self.tool._run(
                    conversation, tool_request, raise_exceptions=self.raise_exceptions
                )
        else:
            # Tool does not require confirmation
            tool_result = await self.tool._run(
                conversation, tool_request, raise_exceptions=self.raise_exceptions
            )

        # 3. If tool_result is None, manage message requesting tool result and yield
        if tool_result is None:
            # Must have a current tool request on yield
            current_tool_request = conversation._get_internal_context_value_for_step(
                self,
                ToolExecutionStep.TOOL_REQUEST,
            )
            if current_tool_request is None:
                raise ValueError(
                    "Current Conversation Tool Request should not be None for return ToolRequest"
                )
            # Double-check (should not usually trigger in normal flow)
            existing_req = any(
                m.message_type == MessageType.TOOL_REQUEST
                and m.tool_requests is not None
                and any(
                    request.tool_request_id == tool_request.tool_request_id
                    for request in m.tool_requests
                )
                for m in reversed(conversation.get_messages())
            )
            # If this condition is true, then we have already added a tool request to the messages before.
            # This means the user has not answered the tool request, so we raise an error.
            # If the condition is False, we append a tool request to the conversation
            if existing_req:
                messages_as_str = "\n".join(str(m) for m in conversation.get_messages())
                raise ValueError(
                    f"The ToolExecutionStep was expecting a tool result message with id "
                    f"{tool_request.tool_request_id} for the corresponding tool request, but did not find any: {messages_as_str}"
                )
            conversation.message_list.append_message(
                Message(
                    tool_requests=[current_tool_request],
                    role="assistant",
                )
            )
            record_event(
                ToolExecutionStartEvent(
                    tool=self.tool,
                    tool_request=current_tool_request,
                )
            )
            return StepResult(
                outputs={},
                branch_name=self.BRANCH_SELF,
                step_type=StepExecutionStatus.YIELDING,
            )

        # 4. If tool_result is an Exception
        if isinstance(tool_result.content, Exception):
            if isinstance(tool_result.content, AuthInterrupt):
                # e.g. for MCP Auth
                return StepResult(
                    outputs={"__execution_status__": tool_result.content.status},
                    branch_name=self.BRANCH_SELF,
                    step_type=StepExecutionStatus.YIELDING,
                )
            elif self.raise_exceptions:
                raise tool_result.content
            else:
                tool_result = ToolResult(
                    content=str(tool_result.content), tool_request_id=tool_result.tool_request_id
                )

        # Note: At this point no exception will be passed to this method
        tool_output = self.tool._check_tool_outputs_copyable(
            tool_result.content, self.raise_exceptions
        )
        tool_result = ToolResult(content=tool_output, tool_request_id=tool_result.tool_request_id)

        # 6. Normal terminal output path: clear tool request, return structured output
        conversation._put_internal_context_key_value_for_step(
            self, ToolExecutionStep.TOOL_REQUEST, None
        )
        return StepResult(
            outputs=self._convert_tool_output_into_output_dict(
                tool=self.tool,
                tool_output=tool_result.content,
            )
        )

    @property
    def might_yield(self) -> bool:
        # The tool execution yields if its tool is a client tool **because** in this case it will
        # give tool execution instructions to the client and wait for the tool results.
        # The tool execution will also yield if the server tool requires confirmation of the user to run
        return self.tool.might_yield

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

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {self.tool.id: self.tool}
