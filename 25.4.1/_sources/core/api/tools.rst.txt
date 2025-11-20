Tools
=====

This page presents all APIs and classes related to tools in WayFlow


.. |agentspec-icon| image:: ../../_static/icons/agentspec-icon.svg
   :width: 100px

.. grid:: 1

    .. grid-item-card:: |agentspec-icon|
        :link: https://oracle.github.io/agent-spec/api/tools.html
        :link-alt: Agent Spec - Tools API Reference

        Visit the Agent Spec API Documentation to learn more about LLMs Components.


.. tip::

    Click the button above ↑ to visit the `Agent Spec Documentation <https://oracle.github.io/agent-spec/index.html>`_




Client Tool
-----------

.. _clienttool:
.. autoclass:: wayflowcore.tools.clienttools.ClientTool

Server Tool
-----------

.. _servertool:
.. autoclass:: wayflowcore.tools.servertools.ServerTool

Remote Tool
-----------

.. _remotetool:
.. autoclass:: wayflowcore.tools.remotetools.RemoteTool

MCP Tool
--------

`Model Context Protocol <https://modelcontextprotocol.io/introduction>`_ (MCP) is an open protocol that standardizes how applications provide context to LLMs.

.. _mcptool:
.. autoclass:: wayflowcore.mcp.MCPTool

.. _mcptoolbox:
.. autoclass:: wayflowcore.mcp.MCPToolBox

.. _sessionparameters:
.. autoclass:: wayflowcore.mcp.SessionParameters
    :exclude-members: to_dict

.. _enablemcpwithoutauth:
.. autofunction:: wayflowcore.mcp.enable_mcp_without_auth

.. _clienttransport:
.. autoclass:: wayflowcore.mcp.ClientTransport

.. _stdiotransport:
.. autoclass:: wayflowcore.mcp.StdioTransport

.. _ssetransport:
.. autoclass:: wayflowcore.mcp.SSETransport

.. _ssemtlstransport:
.. autoclass:: wayflowcore.mcp.SSEmTLSTransport

.. _streamablehttptransport:
.. autoclass:: wayflowcore.mcp.StreamableHTTPTransport

.. _streamablehttpmtlstransport:
.. autoclass:: wayflowcore.mcp.StreamableHTTPmTLSTransport


Tool decorator
--------------

.. _tooldecorator:
.. autofunction:: wayflowcore.tools.toolhelpers.tool

Tool-related Classes
--------------------

.. _toolrequest:
.. autoclass:: wayflowcore.tools.tools.ToolRequest

.. _toolresult:
.. autoclass:: wayflowcore.tools.tools.ToolResult
