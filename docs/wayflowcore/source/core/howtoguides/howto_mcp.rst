.. _top-howtomcp:

======================================
How to connect MCP tools to Assistants
======================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_mcp.py
        :link-alt: MCP how-to script

        Python script/notebook for this guide.


.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Tools <../api/tools>`
    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

`Model Context Protocol <https://modelcontextprotocol.io/introduction>`_ (MCP) is an open protocol that standardizes how applications provide context to LLMs.
You can use an MCP server to provide a consistent tool interface to your agents and flows, without having to create custom adapters for different APIs.

.. tip::

    See the `Oracle MCP Server Repository <https://github.com/oracle/mcp>`_ to explore examples
    of reference implementations of MCP servers for managing and interacting with Oracle products.


In this guide, you will learn how to:

* Create a simple MCP Server (in a separate Python file)
* Connect an Agent to an MCP Server (including how to export/load via Agent Spec, and run it)
* Connect a Flow to an MCP Server (including export/load/run)

.. important::

    This guide does not aim at explaining how to make secure MCP servers, but instead mainly aims at showing how to connect to one.
    You should ensure that your MCP server configurations are secure, and only connect to trusted external MCP servers.


Prerequisite: Setup a simple MCP Server
=======================================

First, let’s see how to create and start a simple MCP server exposing a couple of tools.

.. note::
    You should copy the following server code and run it in a separate Python process.

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##Create_a_MCP_Server
    :end-before: # .. end-##Create_a_MCP_Server

This MCP server exposes two example tools: ``get_user_session`` and ``get_payslips``.
Once started, it will be available at (by default): ``http://localhost:8080/sse``.


.. note::
    When choosing a transport for MCP:

    - Use :ref:`Stdio <stdiotransport>` when launching and communicating with an MCP server as a local subprocess on the same machine as the client.
    - Use :ref:`Streamable HTTP <streamablehttpmtlstransport>` when connecting to a remote MCP server.

    For more information, visit https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio


Connecting an Agent to the MCP Server
=====================================

You can now connect an agent to this running MCP server.


Add imports and configure an LLM
--------------------------------

Start by importing the necessary packages for this guide:

.. literalinclude:: ../code_examples/howto_mcp.py
   :language: python
   :start-after: .. start-##_Imports_for_this_guide
   :end-before: .. end-##_Imports_for_this_guide

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Build the Agent
---------------

:ref:`Agents <agent>` can connect to MCP tools by either using a :ref:`MCPToolBox <mcptoolbox>` or a :ref:`MCPTool <mcptool>`.
Here you will use the toolbox (see the section on Flows to see how to use the ``MCPTool``).

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Connecting_an_agent_to_the_MCP_server
    :end-before: # .. end-##_Connecting_an_agent_to_the_MCP_server

Specify the :ref:`transport <clienttransport>` to use to handle the connection to the server and create the toolbox.
You can then equip an agent with the toolbox similarly to tools.

.. note::
   ``enable_mcp_without_auth()`` disables authorization for local/testing only—do not use in production.


Running the Agent
-----------------

You can now run the agent in a simple conversation:

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Running_the_agent
    :end-before: # .. end-##_Running_the_agent

Alternatively, run the agent interactively in a command-line loop:

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Running_with_an_execution_loop
    :end-before: # .. end-##_Running_with_an_execution_loop

.. note::

    WayFlow maintains MCP Client sessions between calls, which means that the client
    does not need to re-authenticate at every call. After establishing a secure connection,
    MCP servers can safely perform session recognition (e.g. for retrieving user information)


Connecting a Flow to the MCP Server
===================================

You can also use MCP tools in a :ref:`Flow <flow>` by using the :ref:`MCPTool <mcptool>` in a :ref:`ToolExecutionStep <toolexecutionstep>`.

Build the Flow
--------------

Create the flow using the MCP tool:

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Connecting_a_flow_to_the_MCP_server
    :end-before: # .. end-##_Connecting_a_flow_to_the_MCP_server

Here you specify the client transport as with the MCP ToolBox, as well as the name of the specific tool
you want to use. Additionally, you can override the tool description (exposed by the MCP server) by
specifying the ``description`` parameter.

.. tip::

    Use the ``_validate_tool_exist_on_server`` parameter to validate whether the tool is available or not
    at instantiation time.

Running the Flow
----------------

Execute the flow as follows:

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Running_the_flow
    :end-before: # .. end-##_Running_the_flow



Advanced use: Use OAuth in MCP Tools
====================================

MCP Tools and ToolBoxes support auth using the official
`OAuth flow from MCP <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization>`_,

To enable auth simply provide an Auth configuration to a MCP Client Transport (SSE or StreamableHTTP).

.. code-block:: python

    import webbrowser
    from wayflowcore.mcp import MCPOAuthConfigFactory

    oauth_callback_port = 8001 # depends on your MCP server configuration
    auth = MCPOAuthConfigFactory.with_dynamic_discovery(
        redirect_uri=f"http://localhost:{oauth_callback_port}/callback"
    )
    client_transport = SSETransport(url=sse_mcp_server_oauth, auth=auth)

    tool = MCPTool(
        name="generate_random_string",
        description="1234567",
        client_transport=client_transport,
        _validate_server_exists=False,
        _validate_tool_exist_on_server=False,
        input_descriptors=[],
    )

    agent = Agent(llm=llm, tools=[tool])

.. important::

    You must disable MCPTool verification at instantiation when using OAuth.

Then when runing the assistant, when authorization is required an execution status
is returned with the authorization url. The client is responsible for obtaining the
auth code and state and submit it back to the execution loop, which will complete the
OAuth flow. Once the OAuth flow is completed, the conversation can be resumed with the
now authenticated MCP Client sessions.

.. code-block:: python

    from wayflowcore.auth.auth import AuthChallengeResult
    from wayflowcore.executors.executionstatus import AuthChallengeRequestStatus

    conv = agent.start_conversation()
    conv.append_user_message("Call the tool please")
    status = conv.execute()

    assert isinstance(status, AuthChallengeRequestStatus)
    authorization_url = status.auth_request.authorization_url

    # The client app must consume the authorization url, fetch the code/state
    # and submit it back to complete the OAuth flow.
    webbrowser.open(authorization_url)
    auth_code, auth_state = ...

    # The auth callback are submitted, which completes the auth flow
    status.submit_result(AuthChallengeResult(code=auth_code, state=auth_state))

    # The conversation is resumed, and return the expected result
    status = conv.execute()


**API Reference:** :ref:`OAuthClientConfig <oauthclientconfig>`

OAuth works with MCP Tools and ToolBoxes, in agents, flows and multi-agent patterns.

.. note::

    Note that MCP client sessions are reused in a single conversation, which means that you
    will not have to re-perform the OAuth flow at every request.


Advanced use: Complex types in MCP tools
========================================


WayFlow supports MCP tools with non-string outputs, such as:

- List of string
- Dictionary with key and values of string type

From the MCP server-side, you may need to enable the ``structured_output`` parameter
of your MCP server (depends on the implementation).


.. code-block:: python

    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        host=host,
        port=port,
    )

    @server.tool(description="Tool that generates a dictionary", structured_output=True)
    def generate_dict() -> dict[str, str]:
        return {"key": "value"}

    @server.tool(description="Tool that generates a list", structured_output=True)
    def generate_list() -> list[str]:
        return ["value1", "value2"]


On the WayFlow side, the input and output descriptors can be automatically inferred.

.. code-block:: python

    generate_dict_tool = MCPTool(
        name="generate_dict",
        description="Tool that generates a dictionary",
        client_transport=mcp_client,
        # output_descriptors=[DictProperty(name="generate_dictOutput")], # this will be automatically inferred
    )

    generate_list_tool = MCPTool(
        name="generate_list",
        description="Tool that generates a list",
        client_transport=mcp_client,
        # output_descriptors=[ListProperty(name="generate_listOutput")], # this will be automatically inferred
    )


You can then use those tools in a :ref:`Flow <flow>` to natively support the manipulation of complex data types with MCP tools.

You can also use Pydantic models to change the tool output names. Note that in this advanced use,
you must wrap the outputs in a `result` field as expected by MCP when using non-dict types.
This also enables the use of multi-output in tools by using tuples.


.. code-block:: python

    from typing import Annotated
    from pydantic import BaseModel, RootModel, Field

    class GenerateTupleOut(BaseModel, title="tool_output"):
        result: tuple[
            Annotated[str, Field(title="str_output")],
            Annotated[bool, Field(title="bool_output")]
        ]
        # /!\ this needs to be named `result`

    class GenerateListOut(BaseModel, title="tool_output"):
        result: list[str] # /!\ this needs to be named `result`

    class GenerateDictOut(RootModel[dict[str, str]], title="tool_output"):
        pass

    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        host=host,
        port=port,
    )

    @server.tool(description="Tool that generates a dictionary", structured_output=True)
    def generate_dict() -> GenerateDictOut:
        return GenerateDictOut({"key": "value"})

    @server.tool(description="Tool that generates a list", structured_output=True)
    def generate_list() -> GenerateListOut:
        return GenerateListOut(result=["value1", "value2"])

    @server.tool(description="Tool that returns multiple outputs", structured_output=True)
    def generate_tuple(inputs: list[str]) -> GenerateTupleOut:
        value = "; ".join(inputs)
        return GenerateTupleOut(result=("value", True))


You can then match the output descriptors on the WayFlow side.

.. code-block:: python

    generate_dict_tool = MCPTool(
        name="generate_dict",
        description="Tool that generates a dictionary",
        client_transport=mcp_client,
        output_descriptors=[DictProperty(name="tool_output")],
    )

    generate_list_tool = MCPTool(
        name="generate_list",
        description="Tool that generates a list",
        client_transport=mcp_client,
        output_descriptors=[ListProperty(name="tool_output")],
    )

    generate_tuple_tool = MCPTool(
        name="generate_tuple",
        description="Tool that returns multiple outputs",
        client_transport=mcp_client,
        input_descriptors=[ListProperty(name="inputs")],
        output_descriptors=[StringProperty(name="str_output"), BooleanProperty(name="bool_output")],
    )

When specified, the input/output descriptors of the MCP tool will be validated against the schema fetched from the MCP server.


.. note::

    MCPToolBox are not compatible with complex output types.
    Tools from MCPToolBox will always return string values.


Exporting/Loading with Agent Spec
=================================

You can export the assistant from this tutorial to Agent Spec:

.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Export_config_to_Agent_Spec
    :end-before: # .. end-##_Export_config_to_Agent_Spec



Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

    .. tabs::

        .. tab:: Agent Configuration

            .. tabs::

                .. tab:: JSON

                    .. literalinclude:: ../config_examples/howto_mcp_agent.json
                        :language: json

                .. tab:: YAML

                    .. literalinclude:: ../config_examples/howto_mcp_agent.yaml
                        :language: yaml

        .. tab:: Flow Configuration

            .. tabs::

                .. tab:: JSON

                    .. literalinclude:: ../config_examples/howto_mcp_flow.json
                        :language: json

                .. tab:: YAML

                    .. literalinclude:: ../config_examples/howto_mcp_flow.yaml
                        :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_mcp.py
    :language: python
    :start-after: # .. start-##_Load_Agent_Spec_config
    :end-before: # .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginMCPToolBox``
    - ``ExtendedToolNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next Steps
==========

Having learned how to integrate MCP servers in WayFlow, you may now proceed to:

- :doc:`How to Enable Tool Output Streaming <howto_tooloutputstreaming>`
- :doc:`How to Add User Confirmation to Tool Call Requests <howto_userconfirmation>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`

Full code
=========

Click on the card at the :ref:`top of this page <top-howtomcp>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_mcp.py
    :language: python
    :linenos:
