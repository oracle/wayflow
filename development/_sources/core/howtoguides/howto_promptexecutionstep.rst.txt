.. _top-howtopromptexecutionstep:

============================================
How to Do Structured LLM Generation in Flows
============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_promptexecutionstep.py
        :link-alt: Prompt execution step how-to script

        Python script/notebook for this guide.

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
    :start-after: .. start-##_Define_the_article
    :end-before: .. end-##_Define_the_article

WayFlow offers the :ref:`PromptExecutionStep <PromptExecutionStep>` for this type of queries.
Use the code below to generate a 10-words summary:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Create_the_flow_using_the_prompt_execution_step
    :end-before: .. end-##_Create_the_flow_using_the_prompt_execution_step

.. note::

  In the prompt, ``article`` is a Jinja2 syntax to specify a placeholder for a variable, which will appear as an input for the step.
  If you use ``{{var_name}}``, the variable named ``var_name`` will be of type ``StringProperty``.
  If you specify anything else Jinja2 compatible (for loops, filters, and so on), it will be of type ``AnyProperty``.

Now execute the flow:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Run_the_flow_to_get_the_summary
    :end-before: .. end-##_Run_the_flow_to_get_the_summary

As expected, your flow has generated the article summary!

Structured generation with Flows
================================

In many cases, generating raw text within a flow is not very useful, as it is difficult to leverage in later steps.
Instead, you might want to generate attributes that follow a particular schema.
The ``PromptExecutionStep`` class enables this through the `output_descriptors` parameter.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Use_structured_generation_to_extract_formatted_information
    :end-before: .. end-##_Use_structured_generation_to_extract_formatted_information


Complex JSON objects
====================

Sometimes, you might need to generate an object that follows a specific JSON Schema.
You can do that by using an output descriptor of type ``ObjectProperty``, or directly converting your JSON Schema into a descriptor:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Use_structured_generation_with_JSON_schema
    :end-before: .. end-##_Use_structured_generation_with_JSON_schema


Structured generation with Agents
=================================

In certain scenarios, you might need an agent to generate well-formatted outputs within your flow.
You can instruct the agent to generate them, and use it in the ``AgentExecutionStep`` class to perform structured generation.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Use_structured_generation_with_Agents_in_flows
    :end-before: .. end-##_Use_structured_generation_with_Agents_in_flows

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
   :language: python
   :start-after: .. start-##_Export_config_to_Agent_Spec
   :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_promptexecutionstep.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_promptexecutionstep.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
   :language: python
   :start-after: .. start-##_Load_Agent_Spec_config
   :end-before: .. end-##_Load_Agent_Spec_config

Recap
=====

In this guide, you learned how to incorporate LLMs into flows to:

- generate raw text
- produce structured output
- generate structured generation using the agent and :ref:`AgentExecutionStep <AgentExecutionStep>`


Next steps
==========

Having learned how to perform structured generation in WayFlow, you may now proceed to:

- :doc:`Config Generation <generation_config>` to change LLM generation parameters.
- :doc:`Catching Exceptions <catching_exceptions>` to ensure robustness of the generated outputs.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtopromptexecutionstep>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_promptexecutionstep.py
   :language: python
   :linenos:
