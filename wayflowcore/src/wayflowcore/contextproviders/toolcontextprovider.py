# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from wayflowcore._metadata import MetadataType
from wayflowcore._utils.formatting import generate_tool_id
from wayflowcore.property import Property
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.tools import Tool, ToolRequest

from .contextprovider import ContextProvider

if TYPE_CHECKING:
    from wayflowcore.conversation import ContextProviderType, Conversation


class ToolContextProvider(ContextProvider):
    def __init__(
        self,
        tool: ServerTool,
        output_name: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        id: Optional[str] = None,
        __metadata_info__: Optional[MetadataType] = None,
    ) -> None:
        """
        Context provider to wrap a tool execution.

        Parameters
        ----------
        tool:
            The tool to be called as part of this context provider
        output_name:
            The name of the output of this context provider.
            If None is given, the name of the tool followed by `_output` is used.
        name:
            The name of the context provider

        Examples
        --------
        >>> from time import time
        >>> from wayflowcore.controlconnection import ControlFlowEdge
        >>> from wayflowcore.contextproviders import ToolContextProvider
        >>> from wayflowcore.flow import Flow
        >>> from wayflowcore.steps import OutputMessageStep
        >>> from wayflowcore.tools import tool
        >>>
        >>> @tool(description_mode='only_docstring')
        ... def current_time() -> str:
        ...     '''Tool that returns time'''
        ...     from time import time
        ...     return str(time())
        >>>
        >>> context_provider = ToolContextProvider(tool=current_time, output_name="time_output_io", name="tool_step")
        >>> display_first_step_time = OutputMessageStep(message_template="{{ time_output_io }}", name="display_first_step_time")
        >>>
        >>> display_second_step_time = OutputMessageStep(
        ...     message_template="{{ time_output_io }}", name="display_second_step_time"
        ... )
        >>> flow = Flow(
        ...     begin_step=display_first_step_time,
        ...     control_flow_edges=[
        ...         ControlFlowEdge(
        ...             source_step=display_first_step_time,
        ...             destination_step=display_second_step_time,
        ...         ),
        ...         ControlFlowEdge(source_step=display_second_step_time, destination_step=None),
        ...     ],
        ...     context_providers=[context_provider],
        ... )

        """
        if not isinstance(tool, ServerTool):
            raise ValueError(
                f"Unsupported type of tool provided. "
                f"Only ServerTools are supported, given `{type(tool)}` instead."
            )
        if any("default" not in tool_parameter for tool_parameter in tool.parameters.values()):
            raise ValueError(
                f"Unsupported tool provided. "
                f"Only ServerTools that do not have parameters without default values are allowed."
            )

        self.tool = tool
        self.output_name = output_name or f"{tool.name}_output"
        self._output_descriptors = [
            Property.from_json_schema(
                schema=tool.output,
                name=self.output_name,
                description=f"Output of the tool `{tool.name}` executed as part of the context provider",
            )
        ]
        super().__init__(
            name=name, id=id, description=description, __metadata_info__=__metadata_info__
        )

    async def call_async(self, conversation: "Conversation") -> Any:
        from wayflowcore.tracing.span import ContextProviderExecutionSpan, ToolExecutionSpan

        with ContextProviderExecutionSpan(context_provider=self) as context_provider_span:
            self.tool._bind_parent_conversation_if_applicable(conversation)
            tool_request_id = generate_tool_id()
            with ToolExecutionSpan(
                tool=self.tool,
                tool_request=ToolRequest(
                    name=self.tool.name,
                    args={},
                    tool_request_id=tool_request_id,
                ),
            ) as tool_span:
                tool_output = await self.tool.run_async()
                tool_span.record_end_span_event(
                    output=tool_output,
                )
            context_provider_span.record_end_span_event(
                output=tool_output,
            )
            return tool_output

    def get_output_descriptors(self) -> List["Property"]:
        return self._output_descriptors

    @classmethod
    def get_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        return {
            "tool": Tool,
            "output_name": Optional[str],  # type: ignore
        }

    def _referenced_tools_dict_inner(
        self, recursive: bool, visited_set: Set[str]
    ) -> Dict[str, "Tool"]:
        return {self.tool.id: self.tool}


def _convert_context_provider_dict_to_tool_provider(
    context_provider_dict: Dict[str, "ContextProviderType"],
) -> List[ContextProvider]:
    return [
        ToolContextProvider(
            tool=ServerTool(
                name="context_provider_tool",
                description="",
                input_descriptors=[],
                func=lambda: context_provider_func(None),  # type: ignore
            ),
            output_name=value_name,
        )
        for value_name, context_provider_func in context_provider_dict.items()
    ]
