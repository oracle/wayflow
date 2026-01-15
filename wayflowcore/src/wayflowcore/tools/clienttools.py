# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from wayflowcore._metadata import MetadataType
from wayflowcore.property import JsonSchemaParam, Property

from .tools import SupportedToolTypesT, Tool

if TYPE_CHECKING:
    from wayflowcore.conversation import Conversation
    from wayflowcore.tools.tools import ToolRequest, ToolResult


logger = logging.getLogger(__name__)


class ClientTool(Tool):
    """
    Contains the description of a tool, including its name, documentation and schema of its
    arguments. Instead of being run in the server, calling this tool will actually
    yield to the client for them to compute the result, and post it back to continue
    execution.

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

    requires_confirmation: bool
        Flag to make tool require confirmation before execution. Yields a ToolExecutionConfirmationStatus during execution.
        If tool use is confirmed, then a ToolRequestStatus is raised to ask the client to execute the tool and provide the outputs.

    Examples
    --------
    >>> from wayflowcore.tools import ClientTool
    >>> from wayflowcore.property import FloatProperty
    >>> addition_client_tool = ClientTool(
    ...    name="add_numbers",
    ...    description="Simply adds two numbers",
    ...    input_descriptors=[
    ...         FloatProperty(name="a", description="the first number", default_value=0),
    ...         FloatProperty(name="b", description="the second number"),
    ...    ],
    ... )

    """

    def __init__(
        self,
        name: str,
        description: str,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        parameters: Optional[Dict[str, JsonSchemaParam]] = None,
        output: Optional[JsonSchemaParam] = None,
        requires_confirmation: bool = False,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ):

        super().__init__(
            name=name,
            description=description,
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            parameters=parameters,
            output=output,
            requires_confirmation=requires_confirmation,
            id=id,
            __metadata_info__=__metadata_info__,
        )

    @property
    def _tool_type(self) -> SupportedToolTypesT:
        return "client"

    @property
    def might_yield(self) -> bool:
        """
        Indicates that the client tool might yield (it always does).
        """
        return True

    async def _run(
        self,
        conversation: "Conversation",
        tool_request: "ToolRequest",
        append_message: bool = False,
        raise_exceptions: bool = False,
    ) -> Optional["ToolResult"]:
        from wayflowcore.events import record_event
        from wayflowcore.events.event import ToolExecutionResultEvent
        from wayflowcore.messagelist import MessageType

        if tool_request is None:
            raise ValueError(
                "Internal Error: Expected tool request for client tool to not be None before calling _run"
            )

        if append_message:
            logger.warning(
                "ClientTool `_run` method got append_message=True, this argument will be ignored."
            )
        if raise_exceptions:
            logger.warning(
                "ClientTool `_run` method got raise_exceptions=True, this argument will be ignored."
            )

        # Tool Request does not exist, so we return None such that we can append tool request to messages in the executor
        if not any(
            m.message_type == MessageType.TOOL_REQUEST
            and m.tool_requests is not None
            and any(
                request.tool_request_id == tool_request.tool_request_id
                for request in m.tool_requests
            )
            for m in reversed(conversation.message_list.get_messages())
        ):
            return None

        try:
            tool_result = next(
                message.tool_result
                for message in reversed(conversation.message_list.messages)
                if (
                    message.tool_result is not None
                    and message.tool_result.tool_request_id == tool_request.tool_request_id
                )
            )

            self._add_defaults_to_tool_outputs(tool_result.content)

            record_event(
                ToolExecutionResultEvent(
                    tool=self,
                    tool_result=tool_result,
                )
            )
            return tool_result

        except StopIteration:
            # client hasn't answered tool request yet, will raise an error if in a Flow
            return None
