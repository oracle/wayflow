==============================================
How to Build a Hierarchical Multi-Agent System
==============================================


.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Agents <../tutorials/basic_agent>`.


With the advent of increasingly powerful Large Language Models (LLMs), multi-agent systems are becoming more relevant
and are expected to be particularly valuable in scenarios requiring high-levels of autonomy and/or processing
of diverse sources of information.

There are various types of multi-agent systems, each serving different purposes and applications.
Some notable examples include hierarchical structures, agent swarms, and mixtures of agents.

This guide demonstrates an example of a hierarchical multi-agent system (also known as manager-worker pattern) and will show you how to:

- Build expert agents equipped with tools;
- Test the expert agents individually;
- Build and test a hierarchical multi-agent assistant.

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

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-helpermethod:
    :end-before: .. end-helpermethod

API Reference: :ref:`MessageType <messagetype>`


Refund specialist agent
-----------------------

Tools
^^^^^

The refund specialist agent is equipped with two tools.

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-specialisttools:
    :end-before: .. end-specialisttools

API Reference: :ref:`tool <tooldecorator>`

The first tool is used to check whether a given order is eligible for a refund,
while the second is used to process the specific refund.


System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-specialistprompt:
    :end-before: .. end-specialistprompt

.. important::

    The quality of the system prompt is paramount to ensuring proper behaviour of the multi-agent
    system, because slight deviations in the behaviour can lead to cascading
    unintended effects as the number of agents scales up.


Building the Agent
^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-specialistagent:
    :end-before: .. end-specialistagent

API Reference: :ref:`Agent <agent>`


Testing the Agent
^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-specialisttest:
    :end-before: .. end-specialisttest

Test the agents individually to ensure they perform as expected.


Statisfaction surveyor agent
----------------------------

Tools
^^^^^

The statisfaction surveyor agent is equipped with one tool.

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-surveyortools:
    :end-before: .. end-surveyortools


The ``record_survey_response`` tool is simulating the recording of
user feedback data.


System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-surveyorprompt:
    :end-before: .. end-surveyorprompt


Building the Agent
^^^^^^^^^^^^^^^^^^


.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-surveyoragent:
    :end-before: .. end-surveyoragent


Testing the Agent
^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-surveyortest:
    :end-before: .. end-surveyortest


Again, the expert agent behaves as intended.


Building and testing the multi-agent assistant
==============================================


Manager Agent
-------------

In WayFlow, a hierarchical multi-agent system can simply be created as
an agent equipped with expert agents (the ones defined earlier).

This agent is also known as **manager** or **router** agent.

System prompt
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-managerprompt:
    :end-before: .. end-managerprompt

Building the manager Agent
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-manageragent:
    :end-before: .. end-manageragent


Testing the multi-agent system
------------------------------

The power of mult-agent systems is their high adaptiveness.
In the following example, it is demonstrated how the manager can decide
not to call the expert agents for simple user queries.


.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-managertest_noexpert:
    :end-before: .. end-managertest_noexpert


However, the manager is explicitly prompted to delegate to the specialized agents for more complex tasks.
This is demonstrated in the following example.


.. literalinclude:: ../code_examples/howto_multiagent.py
    :language: python
    :start-after: .. start-managertest_withexpert:
    :end-before: .. end-managertest_withexpert



Recap
=====

In this guide, you learned how to build a multi-agent system
consisting of a manager agent and two expert sub-agents.

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-helpermethod:
        :end-before: .. end-helpermethod

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-specialisttools:
        :end-before: .. end-specialisttools

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-specialistprompt:
        :end-before: .. end-specialistprompt

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-specialistagent:
        :end-before: .. end-specialistagent

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-specialisttest:
        :end-before: .. end-specialisttest

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-surveyortools:
        :end-before: .. end-surveyortools

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-surveyorprompt:
        :end-before: .. end-surveyorprompt

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-surveyoragent:
        :end-before: .. end-surveyoragent

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-surveyortest:
        :end-before: .. end-surveyortest

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-managerprompt:
        :end-before: .. end-managerprompt

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-manageragent:
        :end-before: .. end-manageragent

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-managertest_noexpert:
        :end-before: .. end-managertest_noexpert

    .. literalinclude:: ../code_examples/howto_multiagent.py
        :language: python
        :start-after: .. start-managertest_withexpert:
        :end-before: .. end-managertest_withexpert


Next steps
==========

Having learned how to build a multi-agent system in WayFlow, you may now proceed to :doc:`How to Use Agents in Flows <create_a_tool_from_a_flow>`.
