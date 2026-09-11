.. _top-howtoasync:

=============================
How to Use Asynchronous APIs
=============================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_async.py
        :link-alt: Asynchronous APIs how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLMs <../api/llmmodels>`
    - :doc:`Agent <../api/agent>`
    - :doc:`Flows <../api/flows>`

Why async matters
=================

Asynchronous (async) programming in Python lets you start operations that wait on I/O (network, disk, etc.)
without blocking the main thread, enabling high concurrency with a single event loop.
Async is ideal for I/O-bound workloads (LLM calls, HTTP requests, databases) and less useful for CPU-bound tasks,
which should run in worker threads or processes to avoid blocking the event loop.

WayFlow provides asynchronous APIs across models (e.g., ``generate_async``), conversations (``execute_async``),
agents, and flows so you can compose concurrent, high-throughput pipelines using libraries such as ``anyio``.
Use async in the following cases:

- Many parallel LLM requests
- Agents calling several tools that perform remote I/O
- Flows coordinating multiple steps concurrently


Basic implementation
====================

This section shows how to:

1. Use an LLM asynchronously
2. Execute an agent and a flow asynchronously
3. Define tools properly for CPU-bound vs I/O-bound tasks
4. Run many agents concurrently with ``anyio``
5. Understand when to still use synchronous APIs


For this tutorial, we will use a LLM. WayFlow supports several LLM API
providers, select a LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Using asynchronous APIs
-----------------------

From synchronous code, wrap the coroutine with ``anyio.run(...)`` to execute it in an event loop without blocking.
Inside an ``async def`` function, you would instead write ``await ...``.
This pattern lets you fire off many I/O-bound calls concurrently and get much higher throughput than sync code.
For example, with an ``LlmModel``:

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Single_async_generation
    :end-before: .. end-##_Single_async_generation

Execute an Agent asynchronously
-------------------------------

In async pipelines, you can now use ``execute_async`` to avoid head-of-line blocking.

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Async_Agent_execution
    :end-before: .. end-##_Async_Agent_execution

Execute a Flow asynchronously
-----------------------------

Similarly, you can now run ``Flows`` asynchronously:

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Async_Flow_execution
    :end-before: .. end-##_Async_Flow_execution

Async tools vs sync tools
-------------------------

:ref:`ServerTool <ServerTool>` 's callable can be synchronous or asynchronous. The ``tool`` decorator
can therefore be applied to both synchronous and asynchronous functionx.

Use ``async`` tools for I/O-bound operations (HTTP calls, databases, storage) so they compose naturally
with the event loop. Keep CPU-bound work in synchronous functions, so that WayFlow automatically
runs them in worker threads in order to not block the event loop.

.. tip::
   Avoid putting heavy CPU work inside an ``async def`` tool. If you must compute in an async context,
   offload to a thread or keep it as a synchronous tool so WayFlow can schedule it efficiently.

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Define_tools_async_vs_sync
    :end-before: .. end-##_Define_tools_async_vs_sync

Use tools in an async Agent
---------------------------

Combine tools with an agent and run it asynchronously.

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Agent_with_async_tools
    :end-before: .. end-##_Agent_with_async_tools

Run many Agents concurrently
----------------------------

To scale throughput, use ``anyio.create_task_group()`` to start many agent runs concurrently.
Each task awaits its own ``execute_async`` call; the event loop interleaves I/O so all runs make progress.
You can bound concurrency by using semaphores if your backend has rate limits.

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Run_agents_concurrently
    :end-before: .. end-##_Run_agents_concurrently

Synchronous APIs in synchronous contexts
----------------------------------------

Synchronous APIs remain useful in simple scripts and batch jobs. Prefer them only when you are not inside
an event loop. If you call ``execute()`` or other sync APIs from async code, you risk blocking the loop;
WayFlow emits a warning and tells you which async method to use instead (for example, ``execute_async``).

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Synchronous_usage
    :end-before: .. end-##_Synchronous_usage

Agent Spec Exporting/Loading
============================

You can export the agent configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_async.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_async.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_async.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_tracing.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config


Next steps
==========

Having learned how to use the asynchronous APIs, you may now proceed to:

- :doc:`Use Agents in Flows <howto_agents_in_flows>`
- :doc:`Do Structured LLM Generation in Flows <howto_promptexecutionstep>`
- :doc:`Build Assistants with WayFlow Tools <howto_build_assistants_with_tools>`


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoasync>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_async.py
    :language: python
    :linenos:
