.. _core_basic_agent:

===================================================
Build a Simple Conversational Assistant with Agents
===================================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/tutorial_agent.py
        :link-alt: Agent tutorial script

        Python script/notebook for this tutorial.


.. admonition:: Prerequisites

   This guide does not assume any prior knowledge about WayFlow. However, it assumes the reader has a basic knowledge of LLMs.

   You will need a working installation of WayFlow - see :doc:`Installation <../installation>`.

Learning Goals
--------------

In this first tutorial you will develop a simple HR chatbot Assistant that uses a :doc:`Tool <../api/tools>` to search an
HR database to answer the employee's HR-related question.

The HR system will be represented by a set of dummy data that we will
be made available to the agent. The agent will use this dummy data to answer your questions and if it is asked a question that can not
be answered from the dummy data, then it will say so.

By completing this tutorial, you will:

#. Get a feel for how WayFlow works by creating a simple conversational assistant.
#. Learn the basics of using an :ref:`Agent <agent>` to build an assistant.

.. _primer_on_agents:

A primer on Agents
==================

**Assistants** created using WayFlow are AI-powered assistants designed to solve tasks in a (semi-)autonomous and intelligent manner.
WayFlow supports two main types of assistants:

- :ref:`Flows <flow>` - Used for assistants that follow a predefined process to complete tasks. A Flow consists of individual **steps** connected to form a logical sequence of actions. Each step in a Flow serves a specific function, similar to functions in programming.
- :ref:`Agents <agent>` - Used to create conversational agents that can autonomously plan, think, act, and execute tools in a flexible manner.

Additionally, WayFlow provides :ref:`Tools <clienttool>`, which are wrappers around external APIs.
Assistants can use these tools to retrieve relevant data and information necessary for completing tasks.

.. tip::
   **When to use a Flow and when an Agent?** \
   Flows are useful to model business processes with clear requirements, as these assistants provide a high level of
   control over their behavior. On the other hand, Agents are not easy to control, but they can be useful in ambiguous
   environments that necessitate flexibility and creativity.

In this tutorial, you will use the Agent, which is a general-purpose assistant that can interact with users, leverage LLMs, and execute tools to complete tasks.

.. note::

   To learn more about building assistants with Flows, check out Build a Simple Fixed-flow Assistant with Flows :doc:`basic_flow`.

Building the Agent
==================

The process for building a simple Agent will be composed of the following elements:

#. Set up the coding environment by importing the necessary modules and configuring the LLMs.
#. Specify the Agents' instructions.
#. Create the Agent.

Imports and LLM configuration
=============================

First import what is needed for this tutorial:

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Imports_for_this_guide
   :end-before: .. end-##_Imports_for_this_guide

WayFlow supports several LLM API providers. First choose an LLM from one of the options below:

.. include:: ../_components/llm_config_tabs.rst

.. note::
   API keys should never be stored in code. Use environment variables and/or tools such as `python-dotenv <https://pypi.org/project/python-dotenv/>`_
   instead.



Creating a tool for the Agent
=============================

The agent shown in this tutorial is equipped with a tool ``search_hr_database``, which -as the name indicates-
will enable the assistant to search a (ficticious) HR database.

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Defining_a_tool_for_the_agent
   :end-before: .. end-##_Defining_a_tool_for_the_agent


Here, the tool returns some dummy data about two fictitious employees, `John Smith` and `Mary Jones`. The dummy data
returned contains details of the salary and benefits for each of these employees. The agent will use this dummy data
to answer the user's salary queries.



Specifying the agent instructions
=================================

.. _createagent_instructions:

Next, give the agent instructions on how to approach the task. The instructions are shown below.

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Specifying_the_agent_instructions
   :end-before: .. end-##_Specifying_the_agent_instructions

The LLM is provided with these instructions to guide it in solving the task. In this context, the LLM acts as an HR assistant.

.. note::
   For advanced LLM users, these instructions correspond to the system prompt.
   The underlying LLM is used as a multi-turn chat model, with these instructions serving as the initial system prompt.

.. hint::
   **How do I write good instructions?** \
   Good instructions for an LLM should include the following elements:

   #. A persona description defining the role of the agent.
   #. A short description of the task to be solved.
   #. A detailed description of the task. More precise descriptions lead to more consistent results.
   #. Instructions on how the output should be formatted.



Creating the Agent
==================

Now that the tool is created and the instructions are written, you can then create the :ref:`Agent <agent>`.

The code for the agent is shown below.

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Creating_the_agent
   :end-before: .. end-##_Creating_the_agent

The :ref:`Agent <agent>` interacts with the user through conversations. During each turn, it may choose to respond to the user, execute tools or flows, or consult expert agents.

This completes your first Agent!

Running the Agent
=================

Finally, run your agent using a simple turn-based conversation flow until the conversation concludes.
You can execute the assistant by implementing a finite conversation sequence, or a conversation loop.

In the given example conversation loop, the agent's output is displayed to you, and when additional information
is needed, you will be prompted for input.
The script reads your input and responds accordingly, requiring it to be run in an "interactive" manner.

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Running_the_agent
   :end-before: .. end-##_Running_the_agent

Before we run the assistant, what are some questions that you could ask it? The following questions can be answered form
the dummy HR data and are a good starting point.

#. `What is the salary for John Smith?`
#. `Does John Smith earn more that Mary Jones?`
#. `How much annual leave does John Smith get?`

But, we can also ask the assistant questions that it shouldn't be able to answer, because it hasn't been given any data that is relevant to the question:

#. `How much does Jones Jones earn?`
#. `What is Mary Jones favorite color?`

So with some questions ready you can now run the assistant. Run the code below to run the assistant. To quit the assistant type, `Done.`

.. literalinclude:: ../code_examples/tutorial_agent.py
   :language: python
   :linenos:
   :start-after: .. start-##_Running_with_the_execution_loop
   :end-before: .. end-##_Running_with_the_execution_loop



Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/tutorial_agent.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/tutorial_agent.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/tutorial_agent.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/tutorial_agent.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


Next steps
==========

You have successfully learned how to build a conversational assistant using WayFlow :ref:`Agent <agent>`.
With the basics covered, you can now start building more complex assistants.

To continue learning, check out:

- :ref:`API reference <api>`.
- :ref:`How-to guides <how-to_guides>`



Full code
=========

Click on the card at the :ref:`top of this page <core_basic_agent>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/tutorial_agent.py
   :language: python
   :linenos:
