WayFlow
=======

*Robust AI-powered assistants for task automation and enhanced user experiences.*

**WayFlow** is a powerful, intuitive Python library for building advanced AI-powered assistants.
It offers a standard library of modular building blocks to streamline the creation of both
workflow-based and agent-style assistants, encourages reusability and speeds up the development process.

With WayFlow you can build both structured :ref:`Flows <flow>` and autonomous :ref:`Agents <agent>`, giving you complete
flexibility and allowing you to choose the paradigm that best fits your use case.

.. rubric:: Why WayFlow?

WayFlow has several advantages over other existing open-source frameworks:

* **Flexibility**: WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.
* **Interoperability**: WayFlow works with LLMs from many different vendors and supports an open approach to integration.
* **Reusability**: Build reusable and composable components to enable rapid development of AI Assistants.
* **Extensibility**: WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.
* **Openness**: We want to build a community and welcome contributions from diverse teams looking to take the next step in open-source AI Agents.

.. rubric:: Quick start

To install WayFlow from PyPI:

.. only:: stable

   To install ``wayflowcore`` (on Python 3.10), use the following command to install it from PyPI:

   .. code-block:: bash
      :substitutions:

      pip install "|package_name|==|stable_release|"

.. only:: dev

   To install ``wayflowcore`` (on Python 3.10), use the following command to install it from source:

   .. code-block:: bash
      :substitutions:

      bash install-dev.sh

For full details on installation including what Python versions and platforms are supported please see our :doc:`installation guide<installation>`.

With WayFlow installed, you can now try it out.

WayFlow supports several LLM API providers. First choose an LLM from one of the options below:

.. include:: _components/llm_config_tabs.rst

Then create an agent and have a conversation with it, as shown in the code below:

.. literalinclude:: code_examples/quickstart.py
   :language: python
   :start-after: .. full-code:
   :end-before: .. end-full-code

.. tip::
   **Self Hosted Models**: If you are interested in using locally hosted models, please see our guide on using them with WayFlow, :doc:`How to install Ollama <howtoguides/installing_ollama>`.


.. rubric:: Next Steps

#. **Familiarize yourself with the basics - Tutorials**

   * Start with the :doc:`Tutorial building a simple conversational assistant with Agents <tutorials/basic_agent>`.
   * Step through the :doc:`Tutorial building a simple conversational assistant with Flows <tutorials/basic_flow>`.
   * And then do the :doc:`Tutorial building a simple code review assistant <tutorials/usecase_prbot>`.

#. **Ways to use WayFlow to solve common tasks - How-to Guides**

   The :doc:`how-to guides <howtoguides/index>` show you how to achieve common tasks and use-cases using WayFlow.
   They cover topics such as:

   * :doc:`How to create conditional transitions in Flows <howtoguides/conditional_flows>`.
   * :doc:`How to build assistants with Tools <howtoguides/howto_build_assistants_with_tools>`.
   * :doc:`How to catch exceptions in flows <howtoguides/catching_exceptions>`.
   * :doc:`How to use Agents in Flows <howtoguides/howto_agents_in_flows>`.
   * :doc:`How to connect assistants to data <howtoguides/howto_datastores>`.

#. **Explore the API documentation**

   Dive deeper into the :doc:`API documentation <api/index>` to learn about the various classes, methods, and functions available in the
   library.

.. rubric:: Dive Deeper

.. rubric:: Security

LLM-based assistants and LLM-based flows require careful security assessments before deployment.
Please see our :doc:`Security considerations page <security>` to learn more.

.. rubric:: Frequently Asked Questions

Look through our :doc:`Frequently Asked Questions <faqs>`.

.. toctree::
   :hidden:

   Changelog <changelog>
   Installation <installation>


.. toctree::
   :hidden:
   :caption: Essentials

   Tutorials & Use Cases <tutorials/index>
   How-to Guides <howtoguides/index>
   Conceptual Guides <conceptual_guides/data_flow_edges>
   API Reference <api/index>

.. toctree::
   :hidden:
   :caption: Resources

   Reference Sheet <misc/reference_sheet>
   Glossary <misc/glossary>
   Security Considerations <security>
   For Contributors <contributing>
   Frequently Asked Questions <faqs>
