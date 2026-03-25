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

- Create a :ref:`Server Tool <servertool>` that streams output chunks;
- Consume tool chunk events with an :ref:`Event Listener <eventlistener>`.


Tool output streaming for Server Tools
======================================

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


.. note::

   **What is tool output streaming:**
   Tool output streaming lets a tool produce **intermediate outputs** while it is still running,
   instead of waiting until the execution completes to return a single final result.
   When streaming is enabled, WayFlow emits chunk events as the tool makes progress (this is emitted as
   :ref:`ToolExecutionStreamingChunkReceivedEvent <toolexecutionstreamingchunkreceivedevent>`).
   This enables UIs and listeners to display partial results in near real time.
   The tool's **final output is the last value produced** (i.e., the completed tool result);
   earlier values are treated as streamed chunks emitted during execution.

You can enable tool output streaming by creating an async generator
(i.e., an async callable yielding items with ``yield`` instead of ``return``).

When running the async tool callable, yielded items are streamed via the event
:ref:`ToolExecutionStreamingChunkReceivedEvent <toolexecutionstreamingchunkreceivedevent>`.

The last yielded item is treated as the final tool result **and is not streamed.**

Here is a simple example using the :ref:`@tool decorator <tooldecorator>`:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Define_simple_streaming_tool
   :end-before: .. end-##_Define_simple_streaming_tool


You can then define an :ref:`EventListener <eventlistener>` to observe the streamed chunks:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Define_simple_stream_listener
   :end-before: .. end-##_Define_simple_stream_listener


Finally, register a listener before running your Agent/Flow:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Run_agent_with_stream_listener
   :end-before: .. end-##_Run_agent_with_stream_listener


.. _streaming-server-tools-with-artifacts:

Streaming server tools with artifacts
-------------------------------------

.. note::

   Streaming server tools can also return artifacts.
   When the tool is configured with ``output_type=ToolOutputType.CONTENT_AND_ARTIFACT``,
   each yielded item may be either ``content`` or ``(content, artifacts)``.
   Earlier yielded artifacts are exposed on
   :ref:`ToolExecutionStreamingChunkReceivedEvent <toolexecutionstreamingchunkreceivedevent>`
   through ``event.artifacts``.
   Only artifacts returned by the final yielded item are exposed on the final
   :ref:`ToolExecutionResultEvent <toolexecutionresultevent>` and in-memory tool result
   messages.

Here is an artifact-enabled streaming tool using the :ref:`@tool decorator <tooldecorator>`:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Define_streaming_tool_with_artifacts
   :end-before: .. end-##_Define_streaming_tool_with_artifacts


Use a listener like this to observe both streamed chunk artifacts and final result artifacts:

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Define_artifact_stream_listener
   :end-before: .. end-##_Define_artifact_stream_listener


Tool output streaming for MCP Tools
===================================

You can also enable tool output streaming when using MCP tools by wrapping your server-side async callable
with the :ref:`@mcp_streaming_tool <mcpstreamingtool>` decorator.

.. note::

   Wrapping the callable allows to automatically handle the streaming by using the progress
   notification feature from MCP. This feature only works in async code, so you need to write an
   async callable to use the output streaming feature for MCP tools.

   ``mcp_streaming_tool`` also supports ``output_type=ToolOutputType.CONTENT_AND_ARTIFACT``.
   In that mode, each yielded value may be ``content`` or ``(content, artifacts)``.
   Earlier yielded artifacts are exposed on chunk events, while only artifacts from the
   final yielded value populate ``ToolExecutionResultEvent.tool_result.artifacts``.

Here is an example using the official MCP SDK:

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
       all_sentences = [f"{topic} part {i}" for i in range(2)]
       for i in range(2):
           await anyio.sleep(0.2)  # simulate work
           yield all_sentences[i]
       yield ". ".join(all_sentences)

   server.run(transport="streamable-http")


When using other MCP libraries (e.g., https://gofastmcp.com/), you need to
provide the context class when using the ``mcp_streaming_tool`` wrapper.

.. code-block:: python

   from fastmcp import FastMCP, Context

   server = FastMCP(
      name="Example MCP Server",
      instructions="A MCP Server.",
   )

   async def my_tool() -> AsyncGenerator[str, None]:
      contents = [f"This is the sentence N°{i}" for i in range(5)]
      for chunk in contents:
            yield chunk  # streamed chunks
            await anyio.sleep(0.2)

      yield ". ".join(contents)  # final result

   streaming_tool = mcp_streaming_tool(my_tool, context_cls=Context)
   server.tool(description="...")(streaming_tool)



From the client-side, you can consume the MCP tool and observe the streamed chunks
using an event listener as shown above with server tools.

Final MCP tool artifacts, when present, are available on
``ToolExecutionResultEvent.tool_result.artifacts`` and on in-memory tool result messages.
To consume those artifacts, the local :ref:`MCPTool <mcptool>` (or toolbox tool signature)
must explicitly set ``output_type=ToolOutputType.CONTENT_AND_ARTIFACT``. Remote metadata is
used only for validation warnings.

.. literalinclude:: ../code_examples/howto_tooloutputstreaming.py
   :language: python
   :start-after: .. start-##_Run_mcp_streaming_tool
   :end-before: .. end-##_Run_mcp_streaming_tool


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
- Return artifacts together with the final streamed tool result
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
