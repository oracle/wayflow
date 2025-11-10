.. _top-howtomanagerworkers:

========================================
How to Build a Manager-Workers of Agents
========================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_managerworkers.py
        :link-alt: ManagerWorkers how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Agents <../tutorials/basic_agent>`.

With the advent of increasingly powerful Large Language Models (LLMs), multi-agent systems are becoming more relevant
and are expected to be particularly valuable in scenarios requiring high-levels of autonomy and/or processing
of diverse sources of information.

There are various types of multi-agent systems, each serving different purposes and applications.
Some notable examples include hierarchical structures, agent swarms, and mixtures of agents.

This guide demonstrates an example of a hierarchical multi-agent system (also known as manager-workers pattern) and will show you how to:

- Build expert agents equipped with tools and a manager agent;
- Test the expert agents individually;
- Build a ManagerWorkers using the defined agents;
- Execute the ManagerWorkers of agents;

.. image:: ../_static/howto/howto_multiagent.svg
    :align: center
    :scale: 70%
    :alt: Example of a multi-agent system

**Diagram:** Multi-agent system shown in this how-to guide, comprising a manager agent
(customer service agent) and two expert agents equipped with tools (refund specialist
and satisfaction surveyor).

.. seealso::

    To access short code snippets demonstrating how to use other agentic patterns in WayFlow,
    refer to the :doc:`Reference Sheet <../misc/reference_sheet>`.


To follow this guide, you need an LLM. WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Building and testing expert Agents
==================================

In this guide you will use the following helper function to print
messages:

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Helper_method_for_printing_conversation_messages
    :end-before: .. end-##_Helper_method_for_printing_conversation_messages

API Reference: :ref:`MessageType <messagetype>`

Refund specialist agent
-----------------------

The refund specialist agent is equipped with two tools.

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Specialist_tools
    :end-before: .. end-##_Specialist_tools

API Reference: :ref:`tool <tooldecorator>`

The first tool is used to check whether a given order is eligible for a refund,
while the second is used to process the specific refund.

System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Specialist_prompt
    :end-before: .. end-##_Specialist_prompt

.. important::

    The quality of the system prompt is paramount to ensuring proper behaviour of the multi-agent
    system, because slight deviations in the behaviour can lead to cascading
    unintended effects as the number of agents scales up.

Building the Agent
^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Specialist_agent
    :end-before: .. end-##_Specialist_agent

API Reference: :ref:`Agent <agent>`

Testing the Agent
^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Specialist_test
    :end-before: .. end-##_Specialist_test

Test the agents individually to ensure they perform as expected.


Statisfaction surveyor agent
----------------------------

Tools
^^^^^

The statisfaction surveyor agent is equipped with one tool.

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Surveyor_tools
    :end-before: .. end-##_Surveyor_tools


The ``record_survey_response`` tool is simulating the recording of
user feedback data.


System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Surveyor_prompt
    :end-before: .. end-##_Surveyor_prompt


Building the Agent
^^^^^^^^^^^^^^^^^^


.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Surveyor_agent
    :end-before: .. end-##_Surveyor_agent


Testing the Agent
^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Surveyor_test
    :end-before: .. end-##_Surveyor_test


Again, the expert agent behaves as intended.

Manager Agent
-------------

In the our built-in ManagerWorkers component, we allow passing an Agent
as the group manager. Therefore, we just need to define an agent as usual.

In this example, our manager agent will be a Customer Service Manager.

System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Manager_prompt
    :end-before: .. end-##_Manager_prompt

Building the manager Agent
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Manager_agent
    :end-before: .. end-##_Manager_agent


Building and testing ManagerWorkers of Agents
=============================================

Building the ManagerWorkers of Agents
-------------------------------------


.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Managerworkers_pattern
    :end-before: .. end-##_Managerworkers_pattern

API Reference: :ref:`ManagerWorkers <managerworkers>`

The ManagerWorkers has two main parameters:

- ``group_manager``
  This can be either an Agent or an LLM.

  - If an LLM is provided, a manager agent will automatically be created using that LLM along with the default ``custom_instruction`` for group managers.
  - In this example, we explicitly pass an Agent (the *Customer Service Manager Agent*) so we can use our own defined ``custom_instruction``.

- ``workers`` - List of Agents
  These agents serve as the workers within the group and are coordinated by the manager agent.

  - Worker agents cannot interact with the end user directly.
  - When invoked, each worker can leverage its equipped tools to complete the assigned task and report the result back to the group manager.

Executing the ManagerWorkers
----------------------------

The power of mult-agent systems is their high adaptiveness.
In the following example, it is demonstrated how the manager can decide
not to call the expert agents for simple user queries.


.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Managerworkers_answers_without_expert
    :end-before: .. end-##_Managerworkers_answers_without_expert

However, the manager is explicitly prompted to assign to the specialized agents for more complex tasks.
This is demonstrated in the following example.

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Managerworkers_answers_with_expert
    :end-before: .. end-##_Managerworkers_answers_with_expert


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_managerworkers.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_managerworkers.yaml
            :language: yaml

You can load it back using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_managerworkers.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

Next steps
==========

Now that you have learned how to define a ManagerWorkers, you may proceed to :doc:`Build a Swarm of Agents <howto_swarm>`.

Full code
=========

Click on the card at the :ref:`top of this page <top-howtomanagerworkers>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_managerworkers.py
    :language: python
    :linenos:
