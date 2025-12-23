.. _top-howtoconditionaltransitions:

==============================================
How to Create Conditional Transitions in Flows
==============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_branching.py
        :link-alt: Conditional Transitions in Flows how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`.

Software applications utilize branching and conditionals to make decisions and respond dynamically
based on user inputs or data. This capability is essential for adapting to diverse scenarios,
ensuring a seamless and responsive user experience.

WayFlow enables conditional transitions in Flows too. This guide demonstrates how to use
the :ref:`BranchingStep <branchingstep>` to execute different flows based on specific conditions.

.. image:: ../_static/howto/branchingstep.svg
    :align: center
    :scale: 100%
    :alt: Flow diagram of a simple branching step

WayFlow offers additional APIs for managing conditional transitions, such as
:ref:`ChoiceSelectionStep <choiceselectionstep>`, :ref:`FlowExecutionStep <flowexecutionstep>`,
and :ref:`RetryStep <retrystep>`. For more information, refer to the API documentation.


Basic implementation
====================

Suppose there is a variable ``my_var`` that can be equal to ``"[SUCCESS]"`` or ``"[FAILURE]"``.
You want to perform different actions depending on its value. A ``BranchingStep`` can be used
to map each value to a corresponding branch:

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Branching_step
    :end-before: .. end-##_Branching_step

Once this is done, create the flow and map each branch to its corresponding next step. In this
example, the branching step has 2 branches based on the configuration (specified in the
``branch_name_mapping``), and also the default one (``BranchingStep.BRANCH_DEFAULT``).

You can check the branch name of a step using the ``step.get_branches()`` function.

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Flow
    :end-before: .. end-##_Flow

.. note::
    Most steps only have a single next step, so you do not need to specify a transition dictionary,
    and can just use a list with a single element.

    For steps with several branches (such as :ref:`BranchingStep <branchingstep>`, :ref:`ChoiceSelectionStep <choiceselectionstep>`,
    :ref:`RetryStep <retrystep>`, and :ref:`FlowExecutionStep <flowexecutionstep>`), you need to mapping each branch name to
    the next step using an edge. Creating the flow will inform you if you are missing a branch in
    the mapping.


You now have a flow which takes a different transition depending on the value of some variable:

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Execute
    :end-before: .. end-##_Execute

You now have the possibility to export your Flow as an Agent Spec configuration. The Agent Spec
configuration is a convenient serialized format that can be easily shared and stored. Additionally,
it allows execution in compatible environments.

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Export_to_Agent_Spec
    :end-before: .. end-##_Export_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_branching.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_branching.yaml
            :language: yaml

You can now load back the configuration and execute it in the same manner as before exporting it.

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Load_and_execute_with_Agent_Spec
    :end-before: .. end-##_Load_and_execute_with_Agent_Spec

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginRegexNode``
    - ``PluginOutputMessageNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Common patterns and best practices
==================================


Pattern 1: Branching if a token is present in a text
----------------------------------------------------

Most of the time, you will use :ref:`BranchingStep <branchingstep>` to branch out depending on whether a token is present
in a text (for example, whether an LLM generated a token ``[SUCCESS]`` or not).
To do this, pass :ref:`RegexExtractionStep <regexextractionstep>` before the :ref:`BranchingStep <branchingstep>`:

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Branching_with_a_regular_expression
    :end-before: .. end-##_Branching_with_a_regular_expression


You can apply this pattern for an LLM before producing a decision.
Generating a comprehensive textual review before providing a decision token can reduce hallucinations in LLM outputs.
This approach allows the model to contextualize its decision, leading to more accurate and reliable outcomes.


Pattern 2: Branching with more advanced expressions
---------------------------------------------------

For scenarios requiring branching based on more advanced conditions, consider using
:ref:`TemplateRenderingStep <templaterenderingstep>` (which employs Jinja2) or
:ref:`ToolExecutionStep <toolexecutionstep>` to evaluate conditions on variables.

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Branching_with_a_template
    :end-before: .. end-##_Branching_with_a_template

.. note::

    Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja's rendering capabilities.
    Please check our guide on :ref:`How to write secure prompts with Jinja templating <securejinjatemplating>` for more information.

Pattern 3: Branching using an LLM
---------------------------------

To begin, configure an LLM.

WayFlow supports several LLM API providers. Select an LLM from the options below to
proceed with the configuration.

.. include:: ../_components/llm_config_tabs.rst

You can implement branching logic determined by the LLM by using
:ref:`ChoiceSelectionStep <choiceselectionstep>`. To do so, pass the names and descriptions of the
potential next branches.

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Branching_with_an_LLM
    :end-before: .. end-##_Branching_with_an_LLM

.. tip::
    If needed, override the default template using the ``prompt_template`` argument.

Pattern 4: Conditional branching with a sub-flow
------------------------------------------------

To implement branching based on multiple possible outcomes of a sub-flow, wrap it in
:ref:`FlowExecutionStep <flowexecutionstep>`. It will expose one branch per one possible end.
Mapping works the same as for :ref:`BranchingStep <branchingstep>`:

.. literalinclude:: ../code_examples/howto_branching.py
    :language: python
    :start-after: .. start-##_Branching_with_a_Subflow
    :end-before: .. end-##_Branching_with_a_Subflow


Troubleshooting
===============

In case you forget to specify a branch for a step that has several sub-flows, the flow constructor
will inform you about the missing branch names:

.. code-block:: python

    from wayflowcore.controlconnection import ControlFlowEdge
    from wayflowcore.steps import BranchingStep, OutputMessageStep
    from wayflowcore.flow import Flow

    branching_step = BranchingStep(
        name="branching_step",
        branch_name_mapping={
            "[SUCCESS]": "success",
            "[FAILURE]": "failure",
        },
    )
    success_step = OutputMessageStep("It was a success", name="success_step")
    failure_step = OutputMessageStep("It was a failure", name="failure_step")
    flow = Flow(
        begin_step=branching_step,
        control_flow_edges=[
            ControlFlowEdge(
                source_step=branching_step,
                destination_step=success_step,
                source_branch="success",
            ),
            ControlFlowEdge(
                source_step=branching_step,
                destination_step=failure_step,
                source_branch="failure",
            ),
            # Missing some control flow edges
            ControlFlowEdge(source_step=success_step, destination_step=None),
            ControlFlowEdge(source_step=failure_step, destination_step=None),
        ],
    )

    # UserWarning: Missing edge for branch `default` of step `<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>`. You only passed the following `control_flow_edges`: [ControlFlowEdge(source_step=<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>, destination_step=<wayflowcore.steps.outputmessagestep.OutputMessageStep object at 0x1002d61d0>, source_branch='success', __metadata_info__={}), ControlFlowEdge(source_step=<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>, destination_step=<wayflowcore.steps.outputmessagestep.OutputMessageStep object at 0x103e7aa10>, source_branch='failure', __metadata_info__={})]. The flow will raise at runtime if this branch is taken.



Next steps
==========

In this guide, you explored methods for implementing conditional branching within a Flow:

- :ref:`BranchingStep <branchingstep>`.
- :ref:`BranchingStep <branchingstep>` with pattern matching.
- more complex conditionals with :ref:`ToolExecutionStep <toolexecutionstep>`, or :ref:`TemplateRenderingStep <templaterenderingstep>`, and
  :ref:`BranchingStep <branchingstep>`.
- an LLM to decide on the condition using :ref:`ChoiceSelectionStep <choiceselectionstep>`.
- a sub-flow to handle the conditional logic using :ref:`FlowExecutionStep <flowexecutionstep>`.

Having learned how to implement conditional branching in flows, you may now proceed to :doc:`Catching Exceptions <catching_exceptions>` to see how to ensure robustness in a ``Flow``.


Full code
=========

Click on the card at the :ref:`top of this page <top-howtoconditionaltransitions>` to download the
full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_branching.py
    :language: python
    :linenos:
