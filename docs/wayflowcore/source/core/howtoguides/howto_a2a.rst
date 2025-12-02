.. _top-howtoa2a:

=============================================
How to use Serve and Consume Agents using A2A
=============================================

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

This guide provides a step-by-step walkthrough on how to use the `Agent-to-Agent (A2A) protocol <https://a2a-protocol.org/latest/>` within Wayflow, covering both the serving and consuming roles from start to finish.
The A2A protocol allows agents to seamlessly communicate and delegate tasks to one another.

We'll demonstrate its functionality by creating two agents: one responsible for checking if a number is prime and another for generating random numbers. These agents will interact under the coordination of a manager agent.
Through this example, we'll highlight how the A2A protocol enables easy integration of specialized agents independent on how its implemented, allowing for flexible, plug-and-play capabilities across different tasks.

Server Setup for Agents
=======================

In this section, we set up servers for two agents: a ``prime_agent`` for checking prime numbers and a ``sample_agent`` for generating random numbers.

Prime Agent Server
------------------

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Server_Setup_Prime_Agent
   :end-before: .. end-##_Server_Setup_Prime_Agent

Sample Agent Server
-------------------

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

Client Setup for A2A Agents
===========================

On the client side, we create A2A agents that connect to the respective servers.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Client_Setup
   :end-before: .. end-##_Client_Setup

Manager Agent Setup
===================

A manager agent is created to coordinate tasks between the sample and prime agents.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_Manager_Setup
   :end-before: .. end-##_Manager_Setup

Executing Tasks with ManagerWorkers
===================================

Finally, we use the :ref:`ManagerWorkers <managerworkers>` to execute a conversation where the manager agent delegates tasks to the appropriate agents.

.. literalinclude:: ../code_examples/howto_a2a.py
   :language: python
   :start-after: .. start-##_ManagerWorkers_Execution
   :end-before: .. end-##_ManagerWorkers_Execution

Next steps
==========

This guide provided a complete example of implementing the A2A protocol in Wayflow. By setting up servers for specialized agents and coordinating their interactions through a manager agent, you can create powerful distributed systems where tasks are delegated efficiently.

For more and fine grained details on serving agents with A2A, refer to :doc:`A2A Serving <howto_a2a_serving>` and on using A2A agents, refer to :doc:`A2A Consuming <howto_a2aagent>`.

Full code
=========

Click on the card at the :ref:`top of this page <top-howtoa2a>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_a2a.py
    :language: python
    :linenos:
