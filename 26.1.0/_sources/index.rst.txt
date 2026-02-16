.. _landing_page:


WayFlow
=======

.. container:: gradient-background

  .. container:: description

      **Build robust AI-powered assistants for task automation and enhanced user experiences**

      WayFlow is a powerful, intuitive Python library for building advanced AI-powered assistants.
      It offers a standard library of modular building blocks to streamline the creation of both
      workflow-based and agent-style assistants, encourages reusability and speeds up the development process.

  .. container:: description-second link-style

      WayFlow is a reference runtime implementation for `Agent Spec <https://github.com/oracle/agent-spec/>`_, with native support for all Agent Spec Agents and Flows.

  .. container:: button-group

      :doc:`Get Started <core/installation>`
      :doc:`Documentation <core/index>`

  .. rubric:: Why WayFlow?
      :class: sub-title

  .. container:: benefits

      .. container:: benefit-card card-red

        .. image:: _static/img/flexibility.svg
            :class: benefit-icon
            :alt: Flexibility

        **Flexibility**
        WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.

      .. container:: benefit-card card-yellow

        .. image:: _static/img/interoperability.svg
            :class: benefit-icon
            :alt: Interoperability

        **Interoperability**
        WayFlow works with LLMs from many different vendors and supports an open approach to integration.

      .. container:: benefit-card card-blue

        .. image:: _static/img/reusability.svg
            :class: benefit-icon
            :alt: Reusability

        **Reusability**
        WayFlow enables you to build reusable and composable components for rapid development of AI assistants.

      .. container:: benefit-card card-yellow

        .. image:: _static/img/extensibility.svg
            :class: benefit-icon
            :alt: Extensibility

        **Extensibility**
        WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.

      .. container:: benefit-card card-blue

        .. image:: _static/img/opennes.svg
            :class: benefit-icon
            :alt: Openness

        **Openness**
        WayFlow is an open-source project, welcoming contributions from diverse teams looking to take AI agents to the next step.

.. container:: quickstart-container

    .. rubric:: Quick Start
        :class: sub-title

    .. only:: stable

       To install WayFlow on Python 3.10, use the following command to install it from the package index:

       .. container:: qs-content

           .. code-block:: bash
              :substitutions:

              pip install "|package_name|==|stable_release|"

    .. only:: dev

       To install WayFlow on Python 3.10, use the following command to install it from source:

       .. code-block:: bash
          :substitutions:

          bash install-dev.sh

    For complete installation instructions, including supported Python versions and platforms, see the :doc:`installation guide <core/installation>`.

    With WayFlow installed, you can now try it out.

    WayFlow supports several LLM API providers. Select an LLM from the options below:

    .. include:: core/_components/llm_config_tabs.rst

    Then create an agent and start a conversation, as shown in the example below:

    .. literalinclude:: core/code_examples/quickstart.py
       :language: python
       :start-after: .. full-code:
       :end-before: .. end-full-code

    .. tip::
       **Self-Hosted Models**: To use locally hosted models, see the guide on integrating them with WayFlow :doc:`Installing Ollama <core/howtoguides/installing_ollama>`.

.. container:: wnext-container

    .. rubric:: What's Next?
        :class: sub-title

    .. container:: wnext

      .. container:: wnext-card

        .. raw:: html

            <a href="core/tutorials/index.html" class="benefit-card-link">

      .. container:: wn-card-content card-blue

        .. image:: _static/img/tutorials.svg
            :class: benefit-icon
            :alt: How-to Guides

        **Tutorials**

        A series of tutorials that introduces key WayFlow concepts through practical, example-driven learning.

      .. raw:: html

          </a>

      .. container:: wnext-card

        .. raw:: html

            <a href="core/howtoguides/index.html" class="benefit-card-link">

      .. container:: wn-card-content card-blue

        .. image:: _static/img/examples.svg
            :class: benefit-icon
            :alt: How-to Guides

        **How-to Guides**

        Goal-oriented guides with self-contained code examples to help you complete specific tasks.

      .. raw:: html

          </a>

      .. container:: wnext-card

        .. raw:: html

            <a href="core/api/index.html" class="benefit-card-link">

      .. container:: wn-card-content card-blue

        .. image:: _static/img/exploring.svg
            :class: benefit-icon
            :alt: Explore the API docs

        **API Documentation**

        Dive deeper into the API documentation to explore the classes, methods, and functions available in the library.

      .. raw:: html

          </a>

.. toctree::
  :maxdepth: 3
  :hidden:

  Core <core/index>
