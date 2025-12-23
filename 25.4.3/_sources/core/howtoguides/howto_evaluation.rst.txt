.. _top-howtoevaluation:

==========================
How to Evaluate Assistants
==========================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_evaluation.py
        :link-alt: Evaluate Assistants how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`WayFlow Agents <../tutorials/basic_agent>`

Evaluating the robustness and performance of assistants requires careful, reproducible measurement. You can benchmark assistants on a dataset and report metrics.
This is what the :ref:`AssistantEvaluator <assistantevaluator>` is designed for.

The ``AssistantEvaluator`` works as follows:

.. image:: ../_static/howto/assistant_evaluator.png
    :align: center
    :scale: 40%

Evaluation is performed by running an :ref:`AssistantEvaluator <assistantevaluator>` over a set of :ref:`EvaluationTask <evaluationtask>` instances within an
:ref:`EvaluationEnvironment <evaluationenvironment>`. The environment provides the assistant under test, a human proxy (if needed), and optional lifecycle hooks
(init/reset). Metrics are produced by :ref:`TaskScorer <taskscorer>` implementations attached to the tasks.

WayFlow supports several LLM API providers. Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst


Basic implementation
====================

A typical end-to-end evaluation includes:

1. Defining an evaluation environment that supplies the assistant and (optionally) a human proxy.
2. Implementing one or more task scorers to compute metrics.
3. Preparing a set of evaluation tasks (dataset).
4. Running the evaluator and collecting results.

Define the evaluation environment:

.. literalinclude:: ../code_examples/howto_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_environment
    :end-before: .. end-##_Define_the_environment

Create a task scorer to compute metrics from the assistant conversation:

.. literalinclude:: ../code_examples/howto_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_scorer
    :end-before: .. end-##_Define_the_scorer

Prepare the evaluation configuration (dataset and tasks):

.. literalinclude:: ../code_examples/howto_evaluation.py
    :language: python
    :start-after: .. start-##_Define_the_evaluation_config
    :end-before: .. end-##_Define_the_evaluation_config

Run the evaluation and inspect the results:

.. literalinclude:: ../code_examples/howto_evaluation.py
    :language: python
    :start-after: .. start-##_Run_the_evaluation
    :end-before: .. end-##_Run_the_evaluation

.. hint::
    **Task kwargs** vs **Scoring kwargs**

    - Use task kwargs to parameterize task execution (information the assistant needs).
    - Use scoring kwargs to store ground truth and other scoring parameters.

.. important::
    Task scorers must extend ``TaskScorer`` and follow its API. See the API docs for details.


Next steps
==========

Having learned how to evaluate WayFlow Assistants end-to-end, you can proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>` to branch out depending on the agent's response.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoevaluation>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_evaluation.py
    :language: python
    :linenos:
