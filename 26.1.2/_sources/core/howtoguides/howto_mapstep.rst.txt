.. _top-howtomapstep:

============================================
How to Do Map and Reduce Operations in Flows
============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_mapstep.py
        :link-alt: MapStep how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

Map-Reduce is a programming model essential for efficiently processing large datasets across distributed systems.
It is widely used in software engineering to enhance data processing speed and scalability by parallelizing tasks.

WayFlow supports the Map and Reduce operations in Flows, using the :ref:`MapStep <mapstep>`.
This guide will show you how to:

- use :ref:`MapStep <mapstep>` perform an operation on **all elements of a list**
- use :ref:`MapStep <mapstep>` to perform an operation on **all key/value pairs of a dictionary**
- use :ref:`MapStep <mapstep>` to **parallelize** some operations

.. image:: ../_static/howto/mapstep.svg
    :align: center
    :scale: 100%
    :alt: Flow diagram of a MapStep

To follow this guide, you need an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Basic implementation
====================

Assuming you want to summarize a few articles.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Define_the_articles
    :end-before: .. end-##_Define_the_articles

You have the option to generate the summary with the :ref:`PromptExecutionStep <promptexecutionstep>` class, as explained already in :doc:`the separate guide <howto_promptexecutionstep>`:

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Create_the_Flow_for_the_MapStep
    :end-before: .. end-##_Create_the_Flow_for_the_MapStep

This step takes a single article, and generates a summary.
Since you have a list of articles, use the ``MapStep`` class to generate a summary for each article.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Create_the_MapStep
    :end-before: .. end-##_Create_the_MapStep

.. note::

    In the ``unpack_input`` function, define how each sub-flow input is retrieved.
    Here, the sub-flow requires an ``article`` input. Set its value to ``.``, because each iterated item is the article and ``.`` is the identity
    query in JQ.

    The ``output_descriptors`` parameter specifies which outputs of the sub-flow will be collected and merged into a list.

Once this is done, create the flow for the ``MapStep`` and execute it:

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Create_and_execute_the_final_Flow
    :end-before: .. end-##_Create_and_execute_the_final_Flow

As expected, your flow has generated summaries of three articles!


Processing in parallel
======================

By default, the :ref:`MapStep <mapstep>` runs all operations sequentially in order.
This is done so that any flow (including flows that yield or ask the user) can be run.

In many cases (such as generating articles summary), the work is completely parallelizable because the operations are independent from each other.
In this context, you can just set the ``parallel_execution`` parameter to ``True`` and the operations will be run in parallel using a thread-pool.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Parallel_execution_of_map_reduce_operation
    :end-before: .. end-##_Parallel_execution_of_map_reduce_operation

The same can be achieved using the :ref:`ParallelMapStep <parallelmapstep>`.
This step type is equivalent to the :ref:`MapStep <mapstep>`, the only difference is that parallelization is always enabled.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Parallel_execution_of_map_reduce_operation_with_ParallelMapStep
    :end-before: .. end-##_Parallel_execution_of_map_reduce_operation_with_ParallelMapStep

.. note::
  The Global Interpreter Lock (GIL) in Python is not a problem for parallel remote requests
  because I/O-bound operations, such as network requests, release the GIL during their execution,
  allowing other threads to run concurrently while the I/O operation is in progress.

Not all sub-flows can be executed in parallel.
The table below summarizes the limitations of parallel execution for the :ref:`MapStep <mapstep>`:

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
     - Flows with ``InputMessageStep``, ``AgentExecutionStep`` that can ask questions, and so on
     - It will raise an exception at instantiation time if a sub-flow can yield and step set to parallel


Common patterns and best practices
==================================

Sometimes, you might have a dictionary, and you need to iterate on each of the key/value pairs.
To achieve this, set ``iterated_input_type`` to ``DictProperty(<your_type>)``, and use the queries ``._key`` (respectively ``._value``) to access the key (and respectively the value) from the key/value pair.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Iterate_over_a_dictionary
    :end-before: .. end-##_Iterate_over_a_dictionary


Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_mapstep.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_mapstep.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_mapstep.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``ExtendedMapNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

Having learned how to perform ``map`` and ``reduce`` operations in WayFlow, you may now proceed to :doc:`How to Use Agents in Flows <howto_agents_in_flows>`.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtomapstep>` to download the full code
for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_mapstep.py
    :language: python
    :linenos:
