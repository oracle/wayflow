.. _top-toolartifacts:

================================
How to Use Tool Output Artifacts
================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_tool_artifacts.py
        :link-alt: Tool artifacts how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    - Familiarity with WayFlow Agents, Flows, and Tools
    - Basic understanding of WayFlow events


In this guide you will:

- Create a :ref:`Server Tool <servertool>` that returns both model-visible content and user-visible artifacts;
- Capture artifacts from :ref:`ToolExecutionResultEvent <toolexecutionresultevent>`;
- Access artifacts from in-memory tool result messages and from flow event listeners.


Imports and LLM configuration
=============================

The examples in this guide use the following imports:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Imports_for_this_guide
   :end-before: .. end-##_Imports_for_this_guide

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Tool artifacts for Server Tools
===============================


.. note::

   **What are tool artifacts:**
   Tool outputs in ``ToolResult.content`` are expected to remain LLM-friendly.
   ``ToolResult.artifacts`` lets a tool additionally attach one or more richer payloads for
   application or UI consumption.
   Artifacts are available only at runtime, are never added to model context, and are dropped
   during serialization.

To enable artifacts, configure the tool with
``output_type=ToolOutputType.CONTENT_AND_ARTIFACT`` and return a 2-tuple of
``(content, artifacts)``.
You can annotate the callable with ``ReturnArtifact[T]`` for a mypy-friendly
return type while keeping the tool schema focused on the model-visible content.

For server tools, several artifacts are typically returned as a named dictionary,
for example ``{"log.txt": "full log", "report.json": {"mime_type": "application/json", "data": "{...}"}}``.

Here is an example using the :ref:`@tool decorator <tooldecorator>`:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Define_tool_with_artifacts
   :end-before: .. end-##_Define_tool_with_artifacts

If you need to attach several artifacts, return a named mapping:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Define_tool_with_multiple_artifacts
   :end-before: .. end-##_Define_tool_with_multiple_artifacts

WayFlow normalizes those mapped artifacts at runtime and preserves the mapping keys as
artifact names:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Access_multiple_artifacts_from_flow
   :end-before: .. end-##_Access_multiple_artifacts_from_flow

.. seealso::

   If your tool also streams intermediate chunks, see
   :ref:`Streaming server tools with artifacts <streaming-server-tools-with-artifacts>`
   in the :doc:`Tool Output Streaming guide <howto_tooloutputstreaming>`.


Capture artifacts from events
=============================

Artifacts are available at runtime on :ref:`ToolExecutionResultEvent <toolexecutionresultevent>`.
You can capture them with an :ref:`EventListener <eventlistener>`:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Define_event_listener
   :end-before: .. end-##_Define_event_listener


Access artifacts from agent conversations
=========================================

Build the agent as usual:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Build_the_agent
   :end-before: .. end-##_Build_the_agent

After the tool runs, the matching tool result message exposes the normalized artifacts in memory:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Access_artifacts_from_agent_conversation
   :end-before: .. end-##_Access_artifacts_from_agent_conversation


Access artifacts from flows
===========================

Flows do not materialize tool artifacts into conversation messages. For flows,
consume artifacts via event listeners:

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Access_artifacts_from_flow
   :end-before: .. end-##_Access_artifacts_from_flow


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Export_config_to_Agent_Spec
   :end-before: .. end-##_Export_config_to_Agent_Spec

.. note::

   The exported Agent Spec preserves the tool's ``output_type`` through metadata.
   Runtime artifact payloads themselves are never serialized.

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_tool_artifacts.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_tool_artifacts.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_tool_artifacts.py
   :language: python
   :start-after: .. start-##_Load_Agent_Spec_config
   :end-before: .. end-##_Load_Agent_Spec_config


Recap
=====

In this guide, you learned how to:

- Return compact tool content together with rich user-visible artifacts
- Capture artifacts from ``ToolExecutionResultEvent``
- Read artifacts from agent tool result messages and from flow listeners


Next steps
==========

Having learned how to return tool artifacts, you may now proceed to:

- :doc:`Enable Tool Output Streaming <howto_tooloutputstreaming>` to surface incremental tool chunks during execution.
- :doc:`Use the Event System <howto_event_system>` to build custom listeners and runtime integrations.


Full code
=========

Click on the card at the :ref:`top of this page <top-toolartifacts>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_tool_artifacts.py
   :language: python
   :linenos:
