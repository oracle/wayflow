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

WayFlow enables you to leverage LLMs to generate text and structured outputs.
This guide will show you how to:

- use the :ref:`PromptExecutionStep <PromptExecutionStep>` to generate text using an LLM
- use the :ref:`PromptExecutionStep <PromptExecutionStep>` to generate structured outputs
- use the :ref:`AgentExecutionStep <AgentExecutionStep>` to generate structured outputs using an agent


Basic implementation
====================

In this how-to guide, you will learn how to perform structured LLM generation with Flows.

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Assuming you want to summarize this article:

.. literalinclude:: ../code_examples/howto_promptexecutionstep.py
    :language: python
    :start-after: .. start-##_Define_the_article
    :end-before: .. end-##_Define_the_article

WayFlow offers the :ref:`PromptExecutionStep <PromptExecutionStep>` for this type of query.
Use the code below to generate a 10-word summary:

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

How to write secure prompts with Jinja templating
=================================================

.. _securejinjatemplating:

`Jinja2 <https://jinja.palletsprojects.com/en/stable/intro/>`_ is a fast and flexible templating engine for Python,
enabling dynamic generation of text-based formats by combining templates with data.

However, enabling all Jinja templating capabilities poses some security challenges.
For this reason, WayFlow relies on a stricter implementation of the Jinja2's SandboxedEnvironment for higher security.
Every callable is considered unsafe, and every attribute and item access is prevented, except for:

* The attributes ``index0``, ``index``, ``first``, ``last``, ``length`` of the ``jinja2.runtime.LoopContext``;
* The entries of a Python dictionary (only native type is accepted);
* The items of a Python list (only native type is accepted).

You should never write a template that includes a function call, or access to any internal attribute or element of
an arbitrary variable: that is considered unsafe, and it will raise a ``SecurityException``.

Moreover, WayFlow performs additional checks on the inputs provided for rendering.
In particular, only elements and sub-elements that are of basic Python types
(``str``, ``int``, ``float``, ``bool``, ``list``, ``dict``, ``tuple``, ``set``, ``NoneType``) are accepted.
In any other case, a ``SecurityException`` is raised.

What you can write
------------------

Here's a set of common patterns that are accepted by WayFlow's restricted Jinja templating.

Templates that access variables of base Python types:

  .. code-block:: python

    my_var: str = "simple string"
    template = "{{ my_var }}"
    # Expected outcome: "simple string"

Templates that access elements of a list of base Python types:

  .. code-block:: python

    my_var: list[str] = ["simple string"]
    template = "{{ my_var[0] }}"
    # Expected outcome: "simple string"

Templates that access dictionary entries of base Python types:

  .. code-block:: python

    my_var: dict[str, str] = {"k1": "simple string"}
    template = "{{ my_var['k1'] }}"
    # Expected outcome: "simple string"

    my_var: dict[str, str] = {"k1": "simple string"}
    template = "{{ my_var.k1 }}"
    # Expected outcome: "simple string"

Builtin functions of Jinja, like ``length`` or ``format``:

  .. code-block:: python

    my_var: list[str] = ["simple string"]
    template = "{{ my_var | length }}"
    # Expected outcome: "1"

Simple expressions:

  .. code-block:: python

    template = "{{ 7*7 }}"
    # Expected outcome: "49"

``For`` loops, optionally accessing the ``LoopContext``:

  .. code-block:: python

    my_var: list[int] = [1, 2, 3]
    template = "{% for e in my_var %}{{e}}{{ ', ' if not loop.last }}{% endfor %}"
    # Expected outcome: "1, 2, 3"

``If`` conditions:

  .. code-block:: python

    my_var: int = 4
    template = "{% if my_var % 2 == 0 %}even{% else %}odd{% endif %}"
    # Expected outcome: "even"

Our general recommendation is to avoid complex logic in templates, and to pre-process the data you want to render instead.
For example, in case of complex objects, in order to comply with restrictions above, you should conveniently
transform them recursively into a dictionary of entries of basic Python types (see list of accepted types above).

What you cannot write
---------------------

Here's a set of common patterns that are **NOT** accepted by WayFlow's restricted Jinja templating.

Templates that access arbitrary objects:

  .. code-block:: python

    my_var: MyComplexObject = MyComplexObject()
    template = "{{ my_var }}"
    # Expected outcome: SecurityException

Templates that access attributes of arbitrary objects:

  .. code-block:: python

    my_var: MyComplexObject = MyComplexObject(attribute="my string")
    template = "{{ my_var.attribute }}"
    # Expected outcome: SecurityException

Templates that access internals of any type and object:

  .. code-block:: python

    my_var: dict = {"k1": "my string"}
    template = "{{ my_var.__init__ }}"
    # Expected outcome: SecurityException

Templates that access non-existing keys of a dictionary:

  .. code-block:: python

    my_var: dict = {"k1": "my string"}
    template = "{{ my_var['non-existing-key'] }}"
    # Expected outcome: SecurityException

Templates that access keys of a dictionary of type different from ``int`` or ``str``:

  .. code-block:: python

    my_var: dict = {("complex", "key"): "my string"}
    template = "{{ my_var[('complex', 'key')] }}"
    # Expected outcome: SecurityException

Templates that access callables:

  .. code-block:: python

    my_var: Callable = lambda x: f"my value {x}"
    template = "{{ my_var(2) }}"
    # Expected outcome: SecurityException

    my_var: list = [1, 2, 3]
    template = "{{ len(my_var) }}"
    # Expected outcome: SecurityException

    my_var: MyComplexObject = MyComplexObject()
    template = "{{ my_var.to_string() }}"
    # Expected outcome: SecurityException


For more information, please check our :doc:`Security considerations page <../security>`.

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
- perform structured generation using the agent and :ref:`AgentExecutionStep <AgentExecutionStep>`


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
