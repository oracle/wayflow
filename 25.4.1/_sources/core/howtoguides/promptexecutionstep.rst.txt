============================================
How to Do Structured LLM Generation in Flows
============================================

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

WayFlow enables to leverage LLMs to generate text and structured outputs.
This guide will show you how to:

- use the :ref:`PromptExecutionStep <PromptExecutionStep>` to generate text using an LLM
- use the :ref:`PromptExecutionStep <PromptExecutionStep>` to generate structured outputs
- use the :ref:`AgentExecutionStep <AgentExecutionStep>` to generate structured outputs using an agent


Basic implementation
====================

In this how-to guide, you will learn how to do a structured LLM generation with Flows.

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Assuming you want to summarize this article:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-article:
    :end-before: .. end-article

WayFlow offers the :ref:`PromptExecutionStep <PromptExecutionStep>` for this type of queries.
Use the code below to generate a 10-words summary:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-prompt:
    :end-before: .. end-prompt

.. note::

  In the prompt, ``article`` is a Jinja2 syntax to specify a placeholder for a variable, which will appear as an input for the step.
  If you use ``{{var_name}}``, the variable named ``var_name`` will be of type ``StringProperty``.
  If you specify anything else Jinja2 compatible (for loops, filters, and so on), it will be of type ``AnyProperty``.

Now execute the flow:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-execute:
    :end-before: .. end-execute

As expected, your flow has generated the article summary!

Structured generation with Flows
================================

In many cases, generating raw text within a flow is not very useful, as it is difficult to leverage in later steps.
Instead, you might want to generate attributes that follow a particular schema. The ``PromptExecutionStep`` class enables this through the `output_descriptors` parameter.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-structured:
    :end-before: .. end-structured


Complex JSON objects
====================

Sometimes, you might need to generate an object that follows a specific JSON Schema.
You can do that by using an output descriptor of type ``ObjectProperty``, or directly converting your JSON Schema into a descriptor:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-complex:
    :end-before: .. end-complex


Structured generation with Agents
=================================

In certain scenarios, you might need to invoke additional tools within your flow.
You can instruct the agent to generate specific outputs, and use them in the ``AgentExecutionStep`` class to perform structured generation.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-agent:
    :end-before: .. end-agent

Recap
=====

In this guide, you learned how to incorporate LLMs into flows using the :ref:`PromptExecutionStep <PromptExecutionStep>` class to:

- generate raw text
- produce structured output
- generate structured generation using the agent and :ref:`AgentExecutionStep <AgentExecutionStep>`

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-article:
        :end-before: .. end-article

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-llm:
        :end-before: .. end-llm

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-prompt:
        :end-before: .. end-prompt

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-execute:
        :end-before: .. end-execute

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-structured:
        :end-before: .. end-structured

    .. literalinclude:: ../code_examples/howto_promptexecutionstep.py
        :language: python
        :start-after: .. start-agent:
        :end-before: .. end-agent


Next steps
==========

Having learned how to perform structured generation in WayFlow, you may now proceed to:

- :doc:`Config Generation <generation_config>` to change LLM generation parameters.
- :doc:`Catching Exceptions <catching_exceptions>` to ensure robustness of the generated outputs.
