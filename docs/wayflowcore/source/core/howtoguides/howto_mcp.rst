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


Exporting/Loading with Agent Spec
---------------------------------

You can export the flow configuration to Agent Spec YAML:

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

- :doc:`Agents in Flows <howto_agents_in_flows>`
- :doc:`How to Add User Confirmation to Tool Call Requests <howto_userconfirmation>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`

Full code
=========

Click on the card at the :ref:`top of this page <top-howtomcp>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_mcp.py
    :language: python
    :linenos:
