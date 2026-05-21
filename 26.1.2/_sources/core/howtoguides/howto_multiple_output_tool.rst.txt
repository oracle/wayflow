=========================================
How to Create Tools with Multiple Outputs
=========================================

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Tools <../api/tools>`
    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

:doc:`WayFlow Tools <../api/tools>` are a powerful way to equip assistants with new, controllable capabilities.
A key feature of tools is their ability to return multiple outputs, which can then be used across different steps in a `:doc:Flow <../tutorials/basic_flow>`.
Understanding how to map these outputs to variables within a Flow is useful for creating flexible and modular assistants.

In this tutorial, you will:

- Recap how tools output their variables
- Learn how to output multiple variables from a tool with the tool annotation
- Learn how to output multiple variables from a tool with `ServerTool`

Imports
=======

To get started, import the following elements:

.. literalinclude:: ../code_examples/howto_multiple_output_tool.py
   :language: python
   :linenos:
   :start-after: .. start-imports_multioutput_tool
   :end-before: .. end-imports_multioutput_tool

Basic tool implementation
=========================

When using a tool decorator, the tool step returns a **single output** by default.
If the tool's return type is a dictionary (Dict), the step returns a dictionary object.
This output can be accessed using ``ToolExecutionStep.TOOL_OUTPUT``, which is its default name.
While this is useful in many cases, it does not allow the flow to access each variable individually without additional preprocessing.

.. literalinclude:: ../code_examples/howto_multiple_output_tool.py
   :language: python
   :linenos:
   :start-after: .. start-basic_tool_decorator
   :end-before: .. end-basic_tool_decorator

As can be seen in the next two sections, it is possible to use either the `@tool` annotation or `ServerTool` to be able to output several outputs out of a tool.

Multiple outputs with the tool annotation
=========================================

To enable a tool to return multiple outputs that can be used directly in subsequent steps, all expected outputs must be defined using ``output_descriptors``.
This argument can be passed to the `@tool` annotation.
The flow will then unpack the dictionary returned by the tool and assigns each value to a separate variable.

.. literalinclude:: ../code_examples/howto_multiple_output_tool.py
   :language: python
   :linenos:
   :start-after: .. start-multi_output_decorator
   :end-before: .. end-multi_output_decorator

.. warning::
    If ``output_descriptors`` receives a single variable (i.g., ``[StringProperty(...)]``), the dictionary will not be unpacked.
    Instead, the entire dictionary will be treated as a single output, which may result in a type error.

In this case, the unpacked output becomes ``{'bool_output': False, 'string_output': 'Hello World!', 'integer_output': 2147483647}``, and we can use each of the variables independently inside the Flow.


Multiple outputs with `ServerTool`
==================================

To enable a tool to return multiple outputs that can be used directly in subsequent steps, all expected outputs must be defined using ``output_descriptors``.
The model will then unpack the dictionary returned by the tool and assigns each value to a separate variable.

.. literalinclude:: ../code_examples/howto_multiple_output_tool.py
   :language: python
   :linenos:
   :start-after: .. start-multi_output_server
   :end-before: .. end-multi_output_server

.. warning::
    If ``output_descriptors`` receives a single variable (i.g., ``[StringProperty(...)]``), the dictionary will not be unpacked.
    Instead, the entire dictionary will be treated as a single output, which may result in a type error.

In this case, the unpacked output becomes ``{'bool_output': False, 'string_output': 'Hello World!', 'integer_output': 2147483647}``, and we can use each of the variables independently inside the Flow.

Recap
=====

In this guide, you have learned how to extract individual variables returned by a `ToolExecutionStep` so they can be used independently within a ``Flow``.

.. collapse:: Below is the complete code referenced in this guide.

    .. literalinclude:: ../code_examples/howto_multiple_output_tool.py
        :language: python
        :linenos:
        :start-after: .. start-imports_multioutput_tool
        :end-before: .. end-imports_multioutput_tool

    .. literalinclude:: ../code_examples/howto_multiple_output_tool.py
        :language: python
        :linenos:
        :start-after: .. start-multi_output_decorator
        :end-before: .. end-multi_output_decorator

    .. literalinclude:: ../code_examples/howto_multiple_output_tool.py
        :language: python
        :linenos:
        :start-after: .. start-multi_output_server
        :end-before: .. end-multi_output_server

Next steps
==========

Now that you have learned how to produce multiple outputs in a ``Tool`` and use them in a ``Flow``, you may proceed to:

- Using a :ref:`BranchingStep <BranchingStep>` to decide how to handle those variables.
- :doc:`How to Do Map and Reduce Operations in Flows <howto_mapstep>`.
