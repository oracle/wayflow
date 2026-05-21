.. _top-howtoa2aserving:

=========================================
How to Serve Assistants with A2A Protocol
=========================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_a2a_serving.py
        :link-alt: A2A Agent how-to script

        Python script/notebook for this guide.

`A2A Protocol <https://a2a-protocol.org/latest/>`_ is an open standard that defines how two agents can communicate
with each other. It covers both the serving and consumption aspects of agent interaction.

This guide will show you how to serve a WayFlow assistant using this protocol either through the :ref:`A2AServer <a2aserver>` or from the command line.

Basic implementation
====================

With the provided ``A2AServer``, you can:

- Serve any conversational component in WayFlow, including :ref:`Agent <agent>`, :ref:`Flow <flow>`, :ref:`ManagerWorkers <managerworkers>`, and :ref:`Swarm <swarm>`.
- Serve from a serialized AgentSpec JSON/YAML string
- Serve from a path to an AgentSpec config file.

In this guide, we start with serving a simple math agent equipped with a multiplication tool.

To define the agent, you will need access to a large language model (LLM).
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Creating the agent
------------------

.. literalinclude:: ../code_examples/howto_a2a_serving.py
    :language: python
    :start-after: .. start-##_Create_the_agent
    :end-before: .. end-##_Create_the_agent

**API Reference:** :ref:`tool <tooldecorator>`, :ref:`Agent <agent>`

We recommend setting ``can_finish_conversation=True`` because, in A2A, each user request is treated as a `Task <https://a2a-protocol.org/latest/topics/life-of-a-task/>`_ that should complete once the request is processed.
Enabling this option allows the agent to return a *completed* status to clearly indicate that the task has finished.

Serving the agent with ``A2AServer``
------------------------------------

.. literalinclude:: ../code_examples/howto_a2a_serving.py
    :language: python
    :start-after: .. start-##_Serve_the_agent
    :end-before: .. end-##_Serve_the_agent

**API Reference:** :ref:`A2AServer <a2aserver>`

You must specify the public URL where the agent will be reachable.
This URL is used to specify the agent's address in the Agent Card.

When doing ``server.run``, the agent will be served at the specified ``host`` and ``port``.
The server exposes the following standard A2A endpoints:

- ``/message/send``: for sending message requests
- ``/tasks/get``: for getting the information of a task
- ``/.well-known/agent-card.json``: for getting the agent card

By default, when a client sends a message request, the server responds that the task has been submitted.
The client must then poll ``/tasks/get`` using the returned ``task_id``.

If the client prefers to block and wait for the final response, it can set ``blocking=True`` when sending the message request.

Serving the agent via CLI
-------------------------

You can also serve an agent using its serialized AgentSpec configuration directly from the CLI:

.. code-block:: bash

    wayflow serve \
      --api a2a \
      --agent-config agent.json \
      --tool-registry <path to a Python module exposing a `tool_registry` dictionary for agent server tools>

Since the agent uses a tool, you must pass the ``tool_registry``.
See the :ref:`API reference <cliwayflowreference>` for a complete description of all arguments.

Advanced usage
==============

Storage configuration
---------------------

By default, ``InMemoryDatastore`` is used.
This is suitable for testing or local development, but not production.
For production, configure a persistent datastore through :ref:`ServerStorageConfig <serverstorageconfig>`.

We support the following types of datastores:

- ``InMemoryDatastore`` (not persistent)
- ``OracleDatastore`` (persistent)
- ``PostGresDatastore`` (persistent)

Serving other WayFlow components
--------------------------------

We support serving all conversational components in WayFlow.

For Flows:

- Only Flows that *yield* are supported—that is, Flows containing :ref:`InputMessageStep <inputmessagestep>` or :ref:`AgentExecutionStep <agentexecutionstep>`.
- A Flow should include an :ref:`OutputMessageStep <outputmessagestep>` so that its final result can be returned to the client as a message.

Below is example Flow that is valid for serving, along with how it can be served:

.. literalinclude:: ../code_examples/howto_a2a_serving.py
    :language: python
    :start-after: .. start-##_Serve_a_flow
    :end-before: .. end-##_Serve_a_flow

**API Reference:** :ref:`Flow <flow>`, :ref:`InputMessageStep <inputmessagestep>`, :ref:`AgentExecutionStep <agentexecutionstep>`, :ref:`OutputMessageStep <outputmessagestep>`

Next steps
==========

Now that you have learned how to serve WayFlow assistants using A2A protocol, you may proceed to :doc:`How to Build A2A Agents <howto_a2aagent>` to learn how consume an A2A-served agent.

Full code
=========

Click on the card at the :ref:`top of this page <top-howtoa2aserving>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_a2a_serving.py
    :language: python
    :linenos:
