=====================================
Build Flows with the Flow Builder
=====================================

This guide shows how to assemble WayFlow Flows using the chainable ``FlowBuilder`` API.

.. admonition:: Prerequisites

    This guide assumes you are familiar with the following concepts:

    - :ref:`Flows <flow>` and basic steps/edges


Overview
========

``FlowBuilder`` lets you quickly construct flows without manually wiring every edge. It supports:

- ``add_sequence``: add steps in order and wire control edges between them.
- ``set_entry_point`` and ``set_finish_points``: declare the entry and terminal steps.
- ``add_conditional``: branch based on an input to a :ref:`BranchingStep <branchingstep>`.
- ``build_linear_flow``: convenience to assemble a linear flow in one call.

See the full API in :doc:`API › Flows <../api/flows>` and quick snippets in the :ref:`Reference Sheet <flowbuilder_ref_sheet>`.


1. Build a linear flow
======================

Create two steps and connect them linearly with a single call.

.. literalinclude:: ../code_examples/howto_flowbuilder.py
    :language: python
    :start-after: .. start-##_Build_a_linear_flow
    :end-before: .. end-##_Build_a_linear_flow

API Reference: :ref:`FlowBuilder <flowbuilder>`


You can also use the ``build_linear_flow`` method:

.. literalinclude:: ../code_examples/howto_flowbuilder.py
    :language: python
    :start-after: .. start-##_Build_a_linear_flow_equivalent
    :end-before: .. end-##_Build_a_linear_flow_equivalent


2. Add a conditional branch
===========================

Add a branching step where an upstream step’s output determines which branch to execute.

.. literalinclude:: ../code_examples/howto_flowbuilder.py
    :language: python
    :start-after: .. start-##_Build_a_flow_with_a_conditional
    :end-before: .. end-##_Build_a_flow_with_a_conditional

Notes:

- ``add_conditional`` accepts the branch key as a string output name, or a tuple ``(step_or_name, output_name)`` to read from another step.
- ``set_finish_points`` declares which steps finish the flow (creates control edges to ``CompleteStep``).


3. Export the flow
==================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_flowbuilder.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec



Here is what the Agent Spec representation will look like ↓
-----------------------------------------------------------

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_flowbuilder.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_flowbuilder.yaml
            :language: yaml


You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_flowbuilder.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config


Recap
=====

This how-to guide showed how to:

- Build a linear flow in one line with ``build_linear_flow``
- Add a conditional branch with ``set_conditional``
- Declare entry and finish points and serialize your flow


Next steps
==========

- Explore more patterns in the :ref:`Reference Sheet <flowbuilder_ref_sheet>`
- See the complete API in :doc:`API › Flows <../api/flows>`
- Learn about branching and loops in :doc:`How to Develop a Flow with Conditional Branches <conditional_flows>`
