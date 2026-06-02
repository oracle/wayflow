.. _top-tracing:

================================
How to Enable Tracing in WayFlow
================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_tracing.py
        :link-alt: Tracing how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

  This guide assumes familiarity with:

  - :doc:`Using agents <agents>`


Tracing is a crucial aspect of any application, allowing developers to monitor and analyze the behavior of their system.
In the context of an agentic framework like WayFlow, tracing allows you to understand the interactions between agents,
tools, and other components.

In this guide, you will learn how to:

- Create a :ref:`SpanExporter <SpanExporter>`
- Set up tracing in WayFlow
- Save your traces in a file

What is Tracing?
================

Tracing refers to the process of collecting and analyzing data about the execution of a program or system.
This data can include information about function calls, variable assignments, and other events that occur during execution.
By analyzing this data, developers can identify performance bottlenecks, debug issues, and optimize their system for better performance.

Why is Tracing Important?
=========================

Tracing is essential for several reasons:

*   **Debugging**: Tracing helps developers identify and diagnose issues in their agents.
    By analyzing the trace data, they can pinpoint the exact location and cause of errors.
*   **Performance Optimization**: Tracing provides insights into the performance characteristics of an agent, enabling
    developers to identify bottlenecks and optimize their architectures for better efficiency.
*   **Monitoring**: Tracing allows developers to monitor the behavior of their agents in real-time, enabling them
    to detect anomalies and respond promptly to issues.


Basic implementation
====================

To set up tracing in WayFlow, you need to provide an implementation of the :ref:`SpanProcessor <SpanProcessor>`
and :ref:`SpanExporter <SpanExporter>` classes.

A :ref:`SpanProcessor <SpanProcessor>` is a common concept in the observability world.
It is a component in the tracing pipeline responsible for receiving and processing spans as they are
created and completed by the application.
:ref:`SpanProcessor <SpanProcessor>` sit between the tracing backend and the exporter, allowing developers
to implement logic such as batching, filtering, modification, or immediate export of :ref:`Spans <Span>`.
When a :ref:`Span <Span>` ends, the :ref:`SpanProcessor <SpanProcessor>` determines what happens to it next,
whether it’s sent off immediately, or collected for more efficient periodic export (e.g., doing batching).
This flexible mechanism enables customization of trace data handling before it's ultimately exported to backend observability systems.

A :ref:`SpanExporter <SpanExporter>` is a component that is responsible for sending finished spans, along with their
collected trace data, from the application to an external backend or observability system for storage and analysis.
The exporter receives spans from the :ref:`SpanProcessor <SpanProcessor>` and translates them into the appropriate format
for the target system, such as `LangFuse <https://langfuse.com>`_,
`LangSmith <https://www.langchain.com/langsmith>`_, or
`OCI APM <https://www.oracle.com/nl/manageability/application-performance-monitoring/>`_.
Exporters encapsulate the logic required to connect, serialize, and transmit data, allowing OpenTelemetry
to support a wide range of backends through a consistent, pluggable interface.
This mechanism enables seamless integration of collected trace data with various monitoring and tracing platforms.

In the following sections you will learn how to implement a combination of SpanProcessor and SpanExporter
that can export traces to a file.

SpanProcessor and SpanExporter
------------------------------

.. danger::
  Several security concerns arise when implementing SpanProcessors and SpanExporters, which include,
  but they are not limited to, the security of the network used to export traces, and the sensitivity of the
  information exported. Please refer to our :doc:`Security Guidelines <../security>` for more information.

As partially anticipated in the previous section, the most simple implementation of a :ref:`SpanProcessor <SpanProcessor>`
is the one that exports the received :ref:`Span <Span>` as-is, without any modification, as soon as the :ref:`Span <Span>` is closed.
This implementation is provided by ``wayflowcore``, and it is called :ref:`SimpleSpanProcessor <SimpleSpanProcessor>`.
You will use an instance of this :ref:`SpanProcessor <SpanProcessor>` in this guide.

For what concerns the :ref:`SpanExporter <SpanExporter>`, you can implement a version of it that just prints
the information contained in the :ref:`Spans <Span>` to a file at a given path.
The implementation can focus on the `export` method, that opens the file in `append` mode, and it prints in it
the content of the :ref:`Spans <Span>` retrieved through the `to_tracing_info` method.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Span_Exporter_Setup
    :end-before: .. end-##_Span_Exporter_Setup

You can now combine :ref:`SimpleSpanProcessor <SimpleSpanProcessor>` with the `FileSpanExporter` you just implemented
to set up the basic components that will let you export traces to the desired file.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Tracing_Basics
    :end-before: .. end-##_Tracing_Basics

Tracking an agent
-----------------

Now that you have everything you need to process and export traces, you can work on your agent.

In this example, you are going to build a simple calculator agent with four tools, one for each of the basic operations:
addition, subtraction, multiplication, division.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Build_Calculator_Agent
    :end-before: .. end-##_Build_Calculator_Agent

We now run your agent enabling traces, and using the ``FileSpanExporter`` in order to export the traces in a file.
To do that, just wrap the execution loop of our agent in a :ref:`Trace <Trace>` context manager.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Agent_Execution_With_Tracing
    :end-before: .. end-##_Agent_Execution_With_Tracing

You can now run our code and inspect the traces saved in your file.

Emitting Agent Spec Traces
==========================

Open Agent Specification Tracing (short: Agent Spec Tracing) is an extension of
Agent Spec that standardizes how agent and flow executions emit traces.
It defines a unified, implementation-agnostic semantic for, Events, Spans, Traces, and SpanProcessors, with
the same semantic presented for WayFlow in this guide.

WayFlow offers an ``EventListener`` called :ref:`AgentSpecEventListener <agentspeceventlistener>` that
makes WayFlow components emit traces according to the Agent Spec Tracing standard.
Here's an example of how to use it in your code.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Enable_Agent_Spec_Tracing
    :end-before: .. end-##_Enable_Agent_Spec_Tracing


Agent Spec Exporting/Loading
============================

You can export the agent configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_tracing.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_tracing.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginPromptTemplate``
    - ``PluginRemoveEmptyNonUserMessageTransform``
    - ``ExtendedAgent``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`

Using OpenTelemetry SpanProcessors
==================================

`OpenTelemetry <https://opentelemetry.io>`_ is an open-source observability framework that provides standardized APIs and
libraries to collect, process, and export telemetry data from distributed systems.
This standard is agnostic with respect to the domain of application, so it can be easily
adopted also for tracing in agentic frameworks.

Tracing in WayFlow is largely inspired by the OpenTelemetry standard, therefore most of the
concepts and APIs overlap.
For this reason, ``wayflowcore`` offers the implementation of two ``SpanProcessors`` that follow
the OpenTelemetry standard:

- :ref:`OtelSimpleSpanProcessor <otelsimplespanprocessor>`: A span processor that exports spans one by one
- :ref:`OtelBatchSpanProcessor <otelbatchspanprocessor>`: A span processor that exports spans in batches

These span processors wrap the OpenTelemetry implementation, transform WayFlow spans into OpenTelemetry ones,
and emulate the expected behavior of the processor.
Moreover, they allow using OpenTelemetry compatible ``SpanExporter``, like, for example,
those offered by the `OpenTelemetry Exporters library <https://opentelemetry-python.readthedocs.io/en/latest/exporter/index.html>`_.

Next steps
==========

Now that you've learned tracing in WayFlow, you might want to apply it in other scenarios:

- :doc:`How to Build a Swarm of Agents <howto_swarm>`
- :doc:`How to Build Multi-Agent Assistants <howto_multiagent>`


Full code
=========

Click on the card at the :ref:`top of this page <top-tracing>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_tracing.py
    :language: python
    :linenos:
