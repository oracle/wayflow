.. _top-tooloutputstreaming:

===================================
How to Enable Tool Output Streaming
===================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_tooloutputstreaming.py
        :link-alt: Tool Output Streaming how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    - Familiarity with WayFlow Agents and Tools
    - Basic understanding of async functions in Python


In this guide you will:

- Create an async-generator Server Tool that streams output chunks
- Consume tool chunk events with an EventListener
- Configure an Agent to use the streaming tool
- Learn how to increase or disable the chunk cap


Tool output streaming for Server Tools
======================================

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Minimal example
---------------

The simplest way to stream tool output is to return an ``AsyncGenerator`` from the tool implementation. All yielded items except the last are streamed via ``ToolExecutionStreamingChunkReceived``. The last yielded item is treated as the final tool result.

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Define_streaming_tool_and_listener
   :end-before: .. end-##_Define_streaming_tool_and_listener

To observe streamed chunks, register a listener before running your Agent/Flow:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Run_agent_with_stream_listener
   :end-before: .. end-##_Run_agent_with_stream_listener


Tool output streaming for MCP Tools
===================================

Below is the server-side snippet for a streaming MCP tool using the adapter decorator. Run it in a separate process.

.. code-block:: python

   import anyio
   from typing import AsyncGenerator
   from mcp.server.fastmcp import FastMCP
   from wayflowcore.mcp.mcphelpers import mcp_streaming_tool

   server = FastMCP(
       name="Example MCP Server",
       instructions="A MCP Server.",
   )

   @server.tool(description="Stream intermediate outputs, then yield the final result.")
   @mcp_streaming_tool
   async def my_streaming_tool(topic: str) -> AsyncGenerator[str, None]:
       for i in range(2):
           await anyio.sleep(0.2)
           yield f"{topic} part {i}"
       yield f"{topic} FINAL"

       return server

   server.run(transport="streamable-http")

And the client side (assistant/flow).

.. code-block:: python

   from wayflowcore.mcp import MCPTool, MCPToolBox, SSETransport, enable_mcp_without_auth
   from wayflowcore.flow import Flow
   from wayflowcore.steps import ToolExecutionStep

   enable_mcp_without_auth()  # for local dev only
   mcp_client = SSETransport(url="http://localhost:8080/sse")

   # Option A: connect toolbox exposing all server tools to an Agent
   mcp_toolbox = MCPToolBox(client_transport=mcp_client)
   # assistant = Agent(llm=llm, tools=[mcp_toolbox])

   # Option B: connect a single tool to a Flow
   MCP_TOOL_NAME = "my_streaming_tool"
   mcp_tool = MCPTool(
       name=MCP_TOOL_NAME,
       client_transport=mcp_client,
   )

   assistant = Flow.from_steps([
       ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
   ])

   # Use the same ToolExecutionStreamingChunkReceived listener as above

.. seealso::

   For more information read the :doc:`Guide on using MCP Tools <howto_mcp>`

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Export_config_to_Agent_Spec
   :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_tooloutputstreaming.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_tooloutputstreaming.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Load_Agent_Spec_config
   :end-before: .. end-##_Load_Agent_Spec_config

Recap
=====

In this guide, you learned how to:

- Implement streaming Server Tools using async generators
- Listen to tool chunk events and correlate them with executions
- Adjust the streaming cap (including unlimited)


Next steps
==========

Having learned how to stream tool outputs and consume chunk events, you may now proceed to:

- :doc:`Build Assistants with Tools <howto_build_assistants_with_tools>` to design richer tool-enabled agents and flows.
- :doc:`Use the Event System <howto_event_system>` to implement custom listeners, tracing, and monitoring.


Full code
=========

Click on the card at the :ref:`top of this page <top-tooloutputstreaming>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_tooloutputstreaming.py
   :language: python
   :linenos:
