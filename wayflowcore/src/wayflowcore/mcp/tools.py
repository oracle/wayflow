# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import copy
import logging
from dataclasses import InitVar, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from mcp import ClientSession

from wayflowcore._metadata import MetadataType
from wayflowcore.component import DataclassComponent
from wayflowcore.mcp._session_persistence import get_mcp_async_runtime
from wayflowcore.mcp.clienttransport import ClientTransport, _raise_if_missing
from wayflowcore.mcp.mcphelpers import (
    _get_tool_on_server,
    _invoke_mcp_tool_call_async,
    _validate_auth,
    get_server_tools_from_mcp_server,
)
from wayflowcore.property import Property
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import SerializableDataclassMixin, SerializableObject
from wayflowcore.tools.servertools import ServerTool
from wayflowcore.tools.toolbox import ToolBox
from wayflowcore.tools.tools import Tool

logger = logging.getLogger(__name__)


@dataclass
class MCPTool(ServerTool, SerializableDataclassMixin, SerializableObject):
    """Class to represent a MCP tool exposed by a MCP server to a ServerTool.

    .. seealso::

        :ref:`How to connect MCP tools to Assistants <top-howtomcp>`

    """

    client_transport: ClientTransport
    """Transport to use for establishing and managing connections to the MCP server."""

    def __init__(
        self,
        name: str,
        client_transport: ClientTransport,
        description: Optional[str] = None,
        input_descriptors: Optional[List[Property]] = None,
        output_descriptors: Optional[List[Property]] = None,
        _validate_server_exists: bool = True,
        _validate_tool_exist_on_server: bool = True,
        __metadata_info__: Optional[MetadataType] = None,
        id: Optional[str] = None,
        requires_confirmation: bool = False,
    ):
        self.client_transport = client_transport
        _validate_auth(self.client_transport)

        if _validate_server_exists and _validate_tool_exist_on_server:
            mcp_runtime = get_mcp_async_runtime()
            # 1. Ensure session is created (from the portal)
            session = mcp_runtime.get_or_create_session(self.client_transport)
            # 2. Perform the call (from the portal)
            tool = mcp_runtime.call(_get_tool_on_server, session, name, self.client_transport)

            if description is None:
                description = tool.description

            if input_descriptors is None:
                input_descriptors = tool.input_descriptors
            elif input_descriptors != tool.input_descriptors:
                logger.warning(
                    "The input descriptors exposed by the remote MCP server do not match the locally defined input descriptors for tool `%s`:\nLocal input descriptors: %s\nRemote input descriptors: %s",
                    name,
                    input_descriptors,
                    tool.input_descriptors,
                )

            if output_descriptors is None:
                output_descriptors = tool.output_descriptors
            elif output_descriptors != tool.output_descriptors:
                logger.warning(
                    "The output descriptors exposed by the remote MCP server do not match the locally defined output descriptors for tool `%s`:\nLocal output descriptors: %s\nRemote output descriptors: %s",
                    name,
                    output_descriptors,
                    tool.output_descriptors,
                )

        if description is None or input_descriptors is None:
            raise ValueError(
                f"For the tool to be usable, it should have a description and input_descriptors, but got: {description} and {input_descriptors}"
            )

        async def wrapped_async(**kwargs: Any) -> Any:
            raise RuntimeError("Should not be called")

        super().__init__(
            name=name,
            description=description or "",
            input_descriptors=input_descriptors,
            output_descriptors=output_descriptors,
            func=wrapped_async,
            id=id,
            __metadata_info__=__metadata_info__,
            requires_confirmation=requires_confirmation,
        )

    async def run_async(self, *args: Any, **kwargs: Any) -> Any:
        """Runs the MCP tool in an asynchronous manner."""
        mcp_runtime = get_mcp_async_runtime()
        # 1. Ensure session is created (from the portal)
        session = mcp_runtime.get_or_create_session(self.client_transport)
        # 2. Perform the call (from the portal)
        res = await mcp_runtime.call_async(
            _invoke_mcp_tool_call_async, session, self.name, kwargs, self.output_descriptors
        )
        return res

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Runs the MCP tool in a synchronous manner."""
        mcp_runtime = get_mcp_async_runtime()
        # 1. Ensure session is created (from the portal)
        session = mcp_runtime.get_or_create_session(self.client_transport)
        # 2. Perform the call (from the portal)
        res = mcp_runtime.call(
            _invoke_mcp_tool_call_async, session, self.name, kwargs, self.output_descriptors
        )
        return res

    def _serialize_to_dict(self, serialization_context: "SerializationContext") -> Dict[str, Any]:
        from wayflowcore.serialization.serializer import serialize_any_to_dict

        return {
            attr_name: serialize_any_to_dict(getattr(self, attr_name), serialization_context)
            for attr_name in [
                "name",
                "description",
                "input_descriptors",
                "output_descriptors",
                "client_transport",
                "requires_confirmation",
            ]
        }

    @classmethod
    def _deserialize_from_dict(
        cls, input_dict: Dict[str, Any], deserialization_context: "DeserializationContext"
    ) -> "SerializableObject":
        from wayflowcore.serialization.serializer import autodeserialize_any_from_dict

        return MCPTool(
            **{
                attr_name: autodeserialize_any_from_dict(
                    input_dict[attr_name], deserialization_context
                )
                for attr_name in [
                    "name",
                    "description",
                    "input_descriptors",
                    "output_descriptors",
                    "client_transport",
                    "requires_confirmation",
                ]
            },
            # deserialization should not require to be able to reach the server
            _validate_server_exists=False,
        )


@dataclass
class MCPToolBox(ToolBox, DataclassComponent):
    """Class to dynamically expose a list of tools from a MCP Server."""

    client_transport: ClientTransport = field(default_factory=_raise_if_missing("client_transport"))  # type: ignore
    """Transport to use for establishing and managing connections to the MCP server."""

    tool_filter: Optional[List[Union[str, Tool]]] = None
    """
    Optional filter to select specific tools.

    If None, exposes all tools from the MCP server.

    * Specifying a tool name (``str``) indicates that a tool of the given name is expected from the MCP server.
    * Specifying a tool signature (``Tool``) validate the presence and signature of the specified tool in the MCP Server.
        * The name of the MCP tool should match the name of the tool from the MCP Server.
        * Specifying a non-empty description will override the remote tool description.
        * Input descriptors can be provided with description of each input. The names and types should match the remote tool schema.
    """

    _validate_mcp_client_transport: InitVar[bool] = field(default=True, compare=False)

    def __post_init__(self, _validate_mcp_client_transport: bool) -> None:
        if _validate_mcp_client_transport:
            _validate_auth(self.client_transport)

    async def _get_tools_async_impl(self, session: ClientSession) -> Sequence[ServerTool]:
        expected_signatures_by_name: Dict[str, Optional[Tool]] = {}
        for tool_ in self.tool_filter or []:
            if isinstance(tool_, str):  # tool_ is a tool name
                expected_signatures_by_name[tool_] = None
            elif isinstance(tool_, Tool):  # tool_ is a MCP tool signature
                expected_signatures_by_name[tool_.name] = tool_
            else:
                raise ValueError(
                    f"Invalid tool filter. Should be `str` or `Tool`, was {type(tool_)}"
                )

        server_tools = await get_server_tools_from_mcp_server(
            session=session,
            expected_signatures_by_name=expected_signatures_by_name,
            client_transport=self.client_transport,
        )

        for server_tool in server_tools:
            if self.requires_confirmation and not server_tool.requires_confirmation:
                server_tool = copy.deepcopy(server_tool)
                server_tool.requires_confirmation = True

        return server_tools

    async def get_tools_async(self) -> Sequence[ServerTool]:
        mcp_runtime = get_mcp_async_runtime()
        # 1. Ensure session is created (from the portal)
        session = mcp_runtime.get_or_create_session(self.client_transport)
        # 2. Perform the call (from the portal)
        return await mcp_runtime.call_async(self._get_tools_async_impl, session)

    def get_tools(self) -> Sequence[ServerTool]:
        """
        Return the list of tools exposed by the ``MCPToolBox``.

        Will be called at every iteration in the execution loop
        of agentic components.
        """
        mcp_runtime = get_mcp_async_runtime()
        # 1. Ensure session is created (from the portal)
        session = mcp_runtime.get_or_create_session(self.client_transport)
        # 2. Perform the call (from the portal)
        return mcp_runtime.call(self._get_tools_async_impl, session)
