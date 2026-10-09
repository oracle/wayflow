=================================
How to Create a Tool Using a Flow
=================================

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Tools <../api/tools>`
    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

Equipping assistants with :doc:`Tools <../api/tools>` enhances their capabilities.
In WayFlow, tools can be defined in various ways.
One approach is to define a flow as the basis for the tool.
In this guide, you will see a basic example of how a flow is used to define a tool.


Defining the tool
=================

In this guide, you will use an LLM.

WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

Now define a flow and pass additional information to describe the tool, including a name, description, and the output choice.

.. literalinclude:: ../code_examples/howto_tool_from_flow.py
    :language: python
    :start-after: .. start:
    :end-before: .. end-start

.. note::
    The above example also works with more complex flows. However, only flows that do not yield are supported — meaning the flow must run to completion without pausing to request additional input from the user.

.. tip::
    You can now use this tool like any other server tool, and pass it either to an :ref:`Agent <agent>` or to a :ref:`ToolExecutionStep <toolexecutionstep>`.


Recap
=====

In this guide, you learned how to create server tools from ``Flows`` by using the ``ServerTool.from_flow`` method.

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/howto_tool_from_flow.py
        :language: python
        :start-after: .. start:
        :end-before: .. end-start

Next steps
==========

Having learned how to use tools in WayFlow, you may now proceed to :doc:`How to Build Assistants with Tools <howto_build_assistants_with_tools>`.
