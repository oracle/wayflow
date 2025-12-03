.. _top-howtoa2a:

==================================
How to use A2A with ManagerWorkers
==================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_a2a.py
        :link-alt: A2A servers and clients how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`LLM configuration <../howtoguides/llm_from_different_providers>`
    - :doc:`Using agents <agents>`

This step-by-step guide demonstrates how to use the `Agent-to-Agent (A2A) protocol <https://a2a-protocol.org/latest/>`_ in Wayflow for both serving and consuming agents.

The A2A protocol enables agents to communicate and delegate tasks seamlessly. In this example, you'll create two agents: one for checking if numbers are prime, and another for generating random numbers.
A manager agent will coordinate their interactions, demonstrating the plug-and-play flexibility offered by the protocol for integrating specialized agents, regardless of their implementation details.

Server Setup for A2A
====================

In this section, you'll set up servers for two agents: ``prime_agent`` checks if numbers are prime, and ``sample_agent`` generates random numbers.

Setting up the Agents
---------------------

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Server_Setup_Prime_Agent
   :end-before: .. end-##_Server_Setup_Prime_Agent

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Server_Setup_Sample_Agent
   :end-before: .. end-##_Server_Setup_Sample_Agent

Starting the Servers
--------------------

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Server_Startup_Logic
   :end-before: .. end-##_Server_Startup_Logic

For further details, see :ref:`A2AServer <a2aserver>`.

Client Setup for A2A
====================

On the client side, create ``A2AAgent`` instances to connect to the servers started above.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Client_Setup
   :end-before: .. end-##_Client_Setup

See also :ref:`A2AAgent <a2aagent>` for more information.

Manager Agent Setup
===================

While each agent has limited standalone capability, combining them unlocks powerful workflows.
Using :ref:`ManagerWorkers <managerworkers>`, you can implement a manager agent that efficiently coordinates tasks between the sample and prime agents.
This modular, scalable architecture allows each agent to specialize, increasing system capability and flexibility.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Manager_Setup
   :end-before: .. end-##_Manager_Setup

Executing Tasks with ManagerWorkers
===================================

Now, execute a conversation in which the manager agent delegates tasks to the most appropriate agent.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_ManagerWorkers_Execution
   :end-before: .. end-##_ManagerWorkers_Execution

Next steps
==========

This guide demonstrated end-to-end implementation of the A2A protocol: setting up agent servers and coordinating interactions through a manager agent to create distributed systems with effective task delegation.

For more details:

- On serving with A2A, see :doc:`A2A Serving <howto_a2a_serving>`
- On using A2A agents, see :doc:`A2A Consuming <howto_a2aagent>`

Full code
=========

Click on the card at the :ref:`top of this page <top-howtoa2a>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_a2a.py
    :language: python
    :linenos:
