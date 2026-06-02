.. _top-howtoparallelflowexecution:

=====================================
How to Run Multiple Flows in Parallel
=====================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_parallelflowexecution.py
        :link-alt: Parallel flow execution how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

Parallelism is a fundamental concept in computing that enables tasks to be processed concurrently,
significantly enhancing system efficiency, scalability, and overall performance.

WayFlow supports the execution of multiple Flows in parallel, using the :ref:`ParallelFlowExecutionStep <parallelflowexecutionstep>`.
This guide will show you how to:

- use :ref:`ParallelFlowExecutionStep <parallelflowexecutionstep>` to run several tasks in parallel
- use :ref:`PromptExecutionStep <promptexecutionstep>` to summarize the outcome of the parallel tasks

To follow this guide, you need an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Basic implementation
====================

In this guide, we will create a ``Flow`` that generates a marketing message for a user.
Taking the username that identifies the user as input, we will take advantage of the ``ParallelFlowExecutionStep``
to concurrently retrieve information about the user and the context, so that we can finally generate a
personalized marketing welcome message.

We first define the following tools that retrieve the desired information:

* One tool that retrieves the current time;
* One tool that retrieves the user information, like name and date of birth;
* One tool that gathers the user's purchase history;
* One tool that looks for the current list of items on sale, which could be recommended to the user.

.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Define_the_tools
    :end-before: .. end-##_Define_the_tools

These tools simply gather information, therefore they can be easily parallelized.
We create the flows that wrap the tools we just created, and we collect them all in a ``ParallelFlowExecutionStep``
for parallel execution.

.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Create_the_flows_to_be_run_in_parallel
    :end-before: .. end-##_Create_the_flows_to_be_run_in_parallel

The ``ParallelFlowExecutionStep`` will expose all the outputs that the different inner flows generate.
We use this information to ask an LLM to generate a personalized welcome message for the user, which should also
have a marketing purpose.

.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Generate_the_marketing_message
    :end-before: .. end-##_Generate_the_marketing_message

Now that we have all the steps that compose our flow, we just put everything together to create it, and we
execute it to generate our personalized message.

.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Create_and_test_the_final_flow
    :end-before: .. end-##_Create_and_test_the_final_flow


Notes about parallelization
===========================

Not all sub-flows can be executed in parallel.
The table below summarizes the limitations of parallel execution for the :ref:`ParallelFlowExecutionStep <parallelflowexecutionstep>`:

  .. list-table::
   :widths: 30 50 50 45
   :header-rows: 1

   * - Support
     - Type of flow
     - Examples
     - Remarks
   * - **FULLY SUPPORTED**
     - **Flows that do not yield and do not have any side-effect on the conversation** (no variable read/write, posting to the conversation, and so on)
     - Embarrassingly parallel flows (simple independent operation), such as a ``PromptExecutionStep``, ``ApiCallStep`` to post or get, and so on
     - N/A
   * - **SUPPORTED WITH SIDE EFFECTS**
     - **Flows that do not yield but have some side-effect on the conversation** (variable read/write, posting to the conversation, and so on)
     - Flows with ``OutputMessageStep``, ``VariableStep``, ``VariableReadStep``, ``VariableWriteStep``, and so on
     - No guarantee in the order of operations (such as posting to the conversation), only the outputs are guaranteed in order.
   * - **NON SUPPORTED**
     - **Flows that yield**. WayFlow does not support this, otherwise a user might be confused in what branch they are currently when prompted to answer.
     - Flows with ``InputMessageStep``, ``AgentExecutionStep`` that can ask questions, ``ClientTool``, and so on
     - It will raise an exception at instantiation time if a sub-flow can yield and step set to parallel

.. note::
  The Global Interpreter Lock (GIL) in Python is not a problem for parallel remote requests
  because I/O-bound operations, such as network requests, release the GIL during their execution,
  allowing other threads to run concurrently while the I/O operation is in progress.

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_parallelflowexecution.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_parallelflowexecution.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_parallelflowexecution.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``ExtendedParallelFlowNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Having learned how to perform generic parallel operations in WayFlow, you may now proceed to
:doc:`How to Do Map and Reduce Operations in Flows <howto_mapstep>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoparallelflowexecution>` to download the full code
for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_parallelflowexecution.py
    :language: python
    :linenos:
