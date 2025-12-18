.. _top-howtoswarm:

==============================
How to Build a Swarm of Agents
==============================


.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_swarm.py
        :link-alt: Swarm how-to script

        Python script/notebook for this guide.



.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Agents <../tutorials/basic_agent>`.

The Swarm pattern is a type of agentic pattern that takes inspiration from `Swarm intelligence <https://en.wikipedia.org/wiki/Swarm_intelligence>`_,
a phenomenon commonly seen in ant colonies, bee hives, and bird flocks, where coordinated behavior emerges from many simple actors rather than a central controller.
In this agentic pattern, each agent is assigned a specific responsibility and can delegate tasks to other specialized agents to improve overall performance.


**When to use the Swarm pattern?**

Compared to using a :doc:`hierarchical multi-agent pattern <howto_multiagent>`, the communication in :ref:`Swarm <swarm>` pattern reduces the number of LLM calls
as showcased in the diagram below.

.. image:: ../_static/howto/hierarchical_vs_swarm.svg
   :align: center
   :scale: 70%
   :alt: How the Swarm pattern compares to hierarchical multi-agent pattern



In the **hierarchical pattern**, a route User → Agent K → User will require:

1. All intermediate agent to call the correct sub-agent to go down to the Agent K.
2. The Agent K to generate its answer.
3. All intermediate agents to relay the answer back to the user.

In the **swarm pattern**, a route User → Agent K → User will require:

1. The first agent to call or handoff the conversation the Agent K (provided that the developer allows the connection between the two agents).
2. The Agent K to generate its answer.
3. The first agent to relay the answer (only when NOT using handoff; with handoff the Agent K **replaces** the first agent and is thus directly communicating with the human user)

-------


This guide presents an example of a simple Swarm of agents applied to a medical use case.

.. image:: ../_static/howto/swarm_example.svg
   :align: center
   :scale: 90%
   :alt: Example of a Swarm agent pattern for medical application

This guide will walk you through the following steps:

1. Defining agents equipped with tools
2. Assembling a Swarm using the defined agents
3. Executing the Swarm of agents

It also covers how to enable ``handoff`` when building the ``Swarm``.


.. warning::

    The ``Swarm`` agentic pattern is currently in beta (e.g., it cannot yet be used in a ``Flow``).
    Its API and behavior are not guaranteed to be stable and may evolve in future versions.

For more information about ``Swarm`` and other agentic patterns in WayFlow, contact the AgentSpec development team.



Basic implementation
====================

First import what is needed for this guide:

.. literalinclude:: ../code_examples/howto_swarm.py
   :language: python
   :linenos:
   :start-after: .. start-##_Imports_for_this_guide
   :end-before: .. end-##_Imports_for_this_guide


To follow this guide, you will need access to a large language model (LLM).
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

In this section, you will define the agents that will later be used to build the Swarm of agents.




Creating the tools
------------------

The Swarm in this example consists of three :ref:`Agents <agent>`, each equipped with a single :ref:`Tool <tooldecorator>`.

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Creating_the_tools
    :end-before: .. end-##_Creating_the_tools

**API Reference:** :ref:`tool <tooldecorator>`


Defining the agents
-------------------

The three agents need to be given the following elements:

* A name
* A description
* A system prompt (the instruction to give to the LLM to solve a given task)
* A LLM
* Some optional tools


General Practitioner Agent
^^^^^^^^^^^^^^^^^^^^^^^^^^

The first agent the user interacts with is the General Practitioner Agent.

This agent is equipped with the symptoms checker tool, and can interact with the **Pharmacist Agent**
as well as the **Dermatologist Agent**.


.. collapse:: Prompt for the General Practitioner Agent

    .. literalinclude:: ../code_examples/howto_swarm.py
        :language: python
        :start-after: .. start-##_Prompt_for_the_General_Practitioner_Agent
        :end-before: .. end-##_Prompt_for_the_General_Practitioner_Agent


The General Practitioner Agent can be configured as follows:

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Define_the_General_Practitioner_Agent
    :end-before: .. end-##_Define_the_General_Practitioner_Agent



Pharmacist Agent
^^^^^^^^^^^^^^^^

The Pharmacist Agent is equipped with the tool to obtain medication information.
This agent cannot initiate a discussion with the other agents in the Swarm.

.. collapse:: Prompt for the Pharmacist Agent

    .. literalinclude:: ../code_examples/howto_swarm.py
        :language: python
        :start-after: .. start-##_Prompt_for_the_Pharmacist_Agent
        :end-before: .. end-##_Prompt_for_the_Pharmacist_Agent


.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Define_the_Pharmacist_Agent
    :end-before: .. end-##_Define_the_Pharmacist_Agent



Dermatologist Agent
^^^^^^^^^^^^^^^^^^^

The final agent in the Swarm is the Dermatologist agent which is equipped with a tool to query a skin condition knowledge base.
This agent can initiate a discussion with the **Pharmacist Agent**.


.. collapse:: Prompt for the Dermatologist Agent

    .. literalinclude:: ../code_examples/howto_swarm.py
        :language: python
        :start-after: .. start-##_Prompt_for_the_Dermatologist_Agent
        :end-before: .. end-##_Prompt_for_the_Dermatologist_Agent


.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Define_the_Dermatologist_Agent
    :end-before: .. end-##_Define_the_Dermatologist_Agent


Creating the Swarm
------------------

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Creating_the_Swarm
    :end-before: .. end-##_Creating_the_Swarm

**API Reference:** :ref:`Swarm <swarm>`

The Swarm has two main parameters:

- The ``first_agent`` — the initial agent the user interacts with (in this example, the General Practitioner Agent).
- A list of relationships between agents.

The ``relationships`` parameter defines the communication edges between agents.
Each relationship is expressed as a tuple of Caller Agent → Recipient Agent, indicating that the caller is permitted to delegate work to the recipient.

These relationships apply to both types of delegation supported by the Swarm:

- They determine which agents may contact another agent using the send-message tool.
- They also define which pairs of agents are eligible for a handoff, meaning the full user–agent conversation can be transferred from the caller to the recipient.

In this example, the General Practitioner Doctor Agent can delegate to both the Pharmacist and the Dermatologist.
The Dermatologist can also delegate with the Pharmacist.

When invoked, each agent can either respond to its caller (a human user or another agent) or choose to initiate a discussion with
another agent if they are given the capability to do so.

Executing the Swarm
-------------------

Now that the Swarm is defined, you can execute it using an example user query.

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Running_the_Swarm
    :end-before: .. end-##_Running_the_Swarm

We recommend to implement an :ref:`execution loop <refsheet_executionloop>` to execute the ``Swarm``, such as the following:


.. literalinclude:: ../code_examples/howto_swarm.py
   :language: python
   :linenos:
   :start-after: .. start-##_Running_with_the_execution_loop
   :end-before: .. end-##_Running_with_the_execution_loop


Advanced usage
==============

Different handoff modes in Swarm
--------------------------------

One of the key benefits of Swarm is its handoff mechanism. When enabled, an agent can hand off its conversation — that is, transfer the entire message history between it and the human user — to another agent within the Swarm.

The handoff mechanism helps reduce response latency.
Normally, when agents talk to each other, the "distance" between the human user and the final answering agent increases, because messages must travel through multiple agents.
Handoff avoids this by directly transferring the conversation to another agent: while the agent changes, the user's distance to the active agent stays the same.

Swarm provides three handoff modes:

- ``HandoffMode.NEVER``
  Disables the handoff mechanism. Agents can still communicate with each other, but cannot transfer the entire user conversation to another agent.
  In this mode, the  ``first_agent`` is the only agent that can directly interact with the human user.

- ``HandoffMode.OPTIONAL`` (default)
  Agents may perform a handoff when it is beneficial.
  A handoff is performed only when the receiving agent is able to take over and independently address the user’s request.
  This strikes a balance between multi-agent collaboration and minimizing overhead.

- ``HandoffMode.ALWAYS``
  Agents must use the handoff mechanism whenever delegating work to another agent. Direct *send-message* tools between agents are disabled in this mode.
  This mode is useful when most user requests are best handled by a single expert agent rather than through multi-agent collaboration.


To set the handoff mode, simply use :ref:`HandoffMode <handoffmode>` and select the desired mode.

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Enabling_handoff_in_the_Swarm
    :end-before: .. end-##_Enabling_handoff_in_the_Swarm

**API Reference:** :ref:`HandoffMode <handoffmode>`

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_swarm.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_swarm.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_swarm.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

Next steps
==========

Now that you have learned how to define a Swarm, you may proceed to :doc:`How to Build Multi-Agent System <howto_multiagent>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoswarm>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_swarm.py
    :language: python
    :linenos:
