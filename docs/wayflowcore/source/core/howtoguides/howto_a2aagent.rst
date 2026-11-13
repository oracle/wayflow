.. _top-howtoa2aagent:

=====================
How to Use A2A Agents
=====================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_a2aagent.py
        :link-alt: A2A Agent how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`

`A2A Protocol <https://a2a-protocol.org/latest/>`_ is an open standard that defines how two agents can communicate with each other. It covers both the serving and consumption aspects of agent interaction.
This step-by-step guide demonstrates how to use the protocol in WayFlow in different ways, focusing on consuming hosted agents.
For serving using A2A, refer :doc:`A2A Serving <howto_a2a_serving>`.

A2A Agents
==========

In this section, you will learn how to connect to a remote agent using this protocol with the :ref:`A2AAgent <a2aagent>`.

Basic Usage
-----------

To get started with an A2A agent, you need the URL of the remote server agent you wish to connect to. Once you have this information, creating your A2A agent is straightforward and can be done in just a few lines of code:

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Creating_the_agent
    :end-before: .. end-##_Creating_the_agent

Then, use the agent as shown below:

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Running_the_agent
    :end-before: .. end-##_Running_the_agent

Agent Spec Exporting/Loading
----------------------------

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec1
    :end-before: .. end-##_Export_config_to_Agent_Spec1

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_a2aagent_1.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_a2aagent_1.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config1
    :end-before: .. end-##_Load_Agent_Spec_config1

Manager Workers with A2A Agents
===============================

While each agent has limited standalone capabilities, combining them unlocks powerful workflows.
Using :ref:`ManagerWorkers <managerworkers>`, you can implement a manager agent that efficiently coordinates tasks between different specialized agents.
This modular, scalable architecture allows each agent to focus on specific tasks, increasing overall system capability and flexibility.

In this example, you'll create two A2A agents: one for checking if numbers are prime, and another for generating random numbers.
A manager agent will coordinate their interactions, demonstrating the plug-and-play flexibility offered by the protocol for integrating specialized agents, regardless of their implementation details.

Setting up the Agents
---------------------

In this section, you'll set up servers for two agents: ``prime_agent`` checks if numbers are prime, and ``sample_agent`` generates random numbers.

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_Server_Setup_Prime_Agent
   :end-before: .. end-##_Server_Setup_Prime_Agent

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_Server_Setup_Sample_Agent
   :end-before: .. end-##_Server_Setup_Sample_Agent

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_Server_Startup_Logic
   :end-before: .. end-##_Server_Startup_Logic

For further details, see :ref:`A2AServer <a2aserver>`.

On the client side, create ``A2AAgent`` instances to connect to the servers started above.

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_Client_Setup
   :end-before: .. end-##_Client_Setup

Now you can use these agents in :ref:`ManagerWorkers <managerworkers>` setup.

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_Manager_Setup
   :end-before: .. end-##_Manager_Setup

Executing Tasks
---------------

Now, you can execute a conversation in which the manager agent delegates tasks to the most appropriate agent based on their capabilities.
This demonstrates how ManagerWorkers can be used to orchestrate complex interactions seamlessly.

.. literalinclude:: ../code_examples/howto_a2aagent.py
   :language: python
   :start-after: .. start-##_ManagerWorkers_Execution
   :end-before: .. end-##_ManagerWorkers_Execution

Agent Spec Exporting/Loading
----------------------------

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec2
    :end-before: .. end-##_Export_config_to_Agent_Spec2

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_a2aagent_2.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_a2aagent_2.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_a2aagent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config2
    :end-before: .. end-##_Load_Agent_Spec_config2

Next Steps
==========

This guide covered the basics of using A2A agents and coordinating interactions through manager workers in WayFlow.

Full Code
=========

Click on the card at the :ref:`top of this page <top-howtoa2aagent>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_a2aagent.py
    :language: python
    :linenos:
