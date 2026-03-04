.. _top-howtovariable:

==============================================
How to Use Variables for Shared State in Flows
==============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_variable.py
        :link-alt: Variable how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with :doc:`Flows <../tutorials/basic_flow>`

When building Flows, you may need a way to preserve information as it moves from one step to another.
WayFlow provides this through :ref:`Variable <Variable>`, which serves as the flow’s state — a place where values can be stored, accessed, and updated throughout execution.

Why to use Variable?

- **Shared state**: Holds data that multiple steps can share.
- **Intermediate results**: Store partial results and reuse them later.
- **Simpler data flow**: Avoid passing outputs between every step, persist them as state using Variable.

This guide will show you how to:

- Define a :ref:`Variable <Variable>` in a Flow.
- Read its value with :ref:`VariableReadStep <VariableReadStep>`.
- Write to it with :ref:`VariableWriteStep <VariableWriteStep>`.

In this guide, you will see a simple example including defining a ``Variable`` that stores a list of user feedback,
using ``VariableWriteStep`` to insert new feedback into the list, and
using ``VariableReadStep`` to read all collected feedback.

Define a Variable
=================

To define a variable, you need to define it with a name, type and optionally, a default value.
The type of variable determines the kind of data it can hold and is defined using ``Property``.
In this case, our ``feedback_variable`` has the type of ``ListProperty`` and the ``item_type`` of ``StringProperty``.

.. literalinclude:: ../code_examples/howto_variable.py
   :language: python
   :linenos:
   :start-after: .. start-##_Define_a_Variable
   :end-before: .. end-##_Define_a_Variable

**API Reference:** :ref:`Variable <Variable>` | :ref:`Property <Property>`

Define Flow Steps
=================

We will define a simple flow including the following steps.

.. literalinclude:: ../code_examples/howto_variable.py
   :language: python
   :linenos:
   :start-after: .. start-##_Define_Flow_Steps
   :end-before: .. end-##_Define_Flow_Steps

For simplicity, we pass initial feedback to the ``start_step``, which then routes values to ``write_feedback_1`` and ``write_feedback_2``.
In practice, those inputs could come from other steps (e.g. :ref:`ToolExecutionStep<ToolExecutionStep>`).

The :ref:`VariableWriteStep <VariableWriteStep>` requires the ``variable`` that it writes to. It also accepts the following options of write operation:

- ``VariableWriteOperation.OVERWRITE`` (or ``'overwrite'``) works on any type of variable to replace its value with the incoming value.
- ``VariableWriteOperation.MERGE`` (or ``'merge'``) updates a ``Variable`` of type dict (resp. list),
- ``VariableWriteOperation.INSERT`` (or ``'insert'``) operation can be used to append a single element at the end of a list.

Here, we choose ``insert`` as we want to append new user feedback to the our list.

Define a Flow with Variable
===========================

Now we connect everything into a flow: two write steps add feedback, and a read step collects it all for output.

.. literalinclude:: ../code_examples/howto_variable.py
   :language: python
   :linenos:
   :start-after: .. start-##_Define_a_Flow_with_variable
   :end-before: .. end-##_Define_a_Flow_with_variable

The ``VariableWriteStep`` has a single input descriptor ``VariableWriteStep.VALUE`` - the value to write to the variable it holds.
Similarly, the ``VariableReadStep`` has a single output descriptor ``VariableReadStep.VALUE``- the value it reads from the variable it holds.

Remember to include your defined variables in the Flow’s ``variables`` parameter.

Execute the Flow
================

Finally, run the flow:

.. literalinclude:: ../code_examples/howto_variable.py
   :language: python
   :linenos:
   :start-after: .. start-##_Execute_flow
   :end-before: .. end-##_Execute_flow

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_variable.py
    :language: python
    :start-after: .. start-##_Export_config_to_Agent_Spec
    :end-before: .. end-##_Export_config_to_Agent_Spec

Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the AgentSpec assistant configuration.

    .. tabs::

        .. tab:: YAML

            .. literalinclude:: ../config_examples/howto_variable.yaml
                :language: yaml

        .. tab:: JSON

            .. literalinclude:: ../config_examples/howto_variable.json
                :language: json

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_variable.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_config
    :end-before: .. end-##_Load_Agent_Spec_config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginReadVariableNode``
    - ``PluginWriteVariableNode``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`

Next steps
==========

Now that you have learned how to use Variables in Flows, you may proceed to :ref:`FlowContextProvider<FlowContextProvider>` to learn how to provide context for flow execution.

Full code
=========

Click on the card at the :ref:`top of this page <top-howtovariable>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_variable.py
    :language: python
    :linenos:
