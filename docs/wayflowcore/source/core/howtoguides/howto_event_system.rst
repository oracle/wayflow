.. _top-event-system:

===========================
How to Use the Event System
===========================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../code_examples/howto_event_system.py
        :link-alt: Event System how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

  This guide assumes familiarity with:

  - :doc:`Using agents <agents>`

The event system in WayFlow provides a powerful framework for monitoring and debugging agents and flows.
By capturing detailed runtime data through structured events, it offers deep insights into interactions between agents, flows, tools, and LLMs.

This guide introduces the core concepts of the event system, describes available event types and listeners, and provides practical examples for effective implementation.

At its heart, WayFlow's event system records and communicates key occurrences during an execution. Each event is a structured data object that captures details of a specific action or state change, such as starting a conversation, executing a tool, or generating an LLM response. Events include metadata like unique identifiers, timestamps, and relevant contextual information.

The system follows a publish-subscribe model: events are published as they occur, and components called listeners subscribe to receive and react to them. This separation of event generation and handling allows developers to add custom behaviors or logging without altering the core logic of agents or flows.

Basic Implementation
====================

To use the event system effectively, you need to understand its two main components: `Events` and `EventListeners`.

`Events` are data structures that represent occurrences within WayFlow, organized into different types for various scenarios.
`EventListeners` are components that react to these published events.

Let's explore this with two practical examples:

Example 1: Computing LLM Token Usage
====================================

A key use of the event system is tracking resource consumption, such as monitoring token usage during LLM interactions.
Since token usage affects operational costs, this data can inform prompt and model optimization.
By subscribing to LLM response events, developers can aggregate and analyze token usage across a conversation.

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_TokenUsage
    :end-before: .. end-##_TokenUsage

In this example, `TokenUsageListener` is a custom listener that calculates total token usage by summing the tokens reported in each :ref:`LlmGenerationResponseEvent <LlmGenerationResponseEvent>`.

Example 2: Tracking Tool Calls
==============================

Another useful application is monitoring tool invocations within an agentic workflow.
Understanding which tools are used and their frequency helps developers evaluate the effectiveness of their toolset and identify opportunities for improvement.
By listening to tool execution events, you can log each call and track usage patterns.

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_Tool_Call_Listener
    :end-before: .. end-##_Tool_Call_Listener

This snippet illustrates how to create a `ToolCallListener` to track tool invocations using :ref:`ToolExecutionStartEvent <toolexecutionstartevent>`.

With both listeners implemented, let's apply them in a conversation with an :ref:`Agent <Agent>`.

For LLMs, WayFlow supports multiple API providers. Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Now, let's set up an agent:

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_Agent
    :end-before: .. end-##_Agent

Using the agent in a conversation:

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_Conversation
    :end-before: .. end-##_Conversation

Both listeners are registered within a context manager using :ref:`register_event_listeners <registereventlisteners>` during agent execution, ensuring they capture all relevant events.

Beyond the events highlighted here, WayFlow offers a wide range of events for detailed monitoring. See :ref:`Events <events>` for more information.  You can implement custom `EventListeners` for these events as shown in the examples above.

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_event_system.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_event_system.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

Next Steps
==========

After exploring the event system in WayFlow, consider learning more about related features to further enhance your agentic applications:

- :doc:`How to Enable Tracing in WayFlow <howto_tracing>`
- :doc:`How to Build a Swarm of Agents <howto_swarm>`

Full Code
=========

Click on the card at the :ref:`top of this page <top-event-system>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../code_examples/howto_event_system.py
    :language: python
    :linenos:
