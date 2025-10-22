.. _top-userconfirmation:

==================================================
How to Add User Confirmation to Tool Call Requests
==================================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_userconfirmation.py
        :link-alt: User Confirmation how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

WayFlow :ref:`Agents <agent>` can be equipped with :doc:`Tools <../api/tools>` to enhance their capabilities.
However, end users may want to confirm or deny tool call requests emitted from the agent.

This guide shows you how to achieve this with the :ref:`ServerTool <servertool>`. You can also do this using a :ref:`ClientTool <clienttool>`


Basic implementation
====================

In this example, you will build a simple :ref:`Agent <agent>` equipped with three tools:

* A tool to add numbers
* A tool to subtract numbers
* A tool to multiply numbers

This guide requires the use of an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

To learn more about the different LLM providers, read the guide on :doc:`How to Use LLMs from Different Providers <llm_from_different_providers>`.
The sample LLM used for this guide is defined as follows:

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-##Configure_LLM
    :end-before: .. end-##Configure_LLM


Creating the tools
------------------

Sometimes you will want to ask for user confirmation before executing certain tools. You can do this by using a :ref:`ServerTool <servertool>` with the flag ``requires_confirmation`` set to ``True``. This will raise a ``ToolExecutionConfirmationStatus``
whenever the ``Agent`` tries to execute the tool. We set the multiply_numbers tool to not require confirmation to highlight the differences. Note that the ``requires_confirmation`` flag can be used for any WayFlow tool.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-##Create_tools
    :end-before: .. end-##Create_tools


Creating the user-side execution logic
----------------------------------------

To enable users to accept or deny tool call requests, you add simple validation logic before executing the tools requested by the agent.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-##Create_tool_execution
    :end-before: .. end-##Create_tool_execution

Here, you simply loop until the user answers whether to accept the tool request or reject it. You can accept the tool request by using the ``status.confirm_tool_execution`` method.
While accepting, you need to specify the specific tool request and you also have the option to add ``modified_args`` in this method to change the arguments of the called tool.
Similarly, for rejection you can use the ``status.reject_tool_execution`` with an optional ``reason`` so that the  ``Agent`` can take the reason into account while planning the next action to take.


Creating the agent
------------------

Finally, you create a simple ``Agent`` to test the execution code written in the previous section.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-##Create_agent
    :end-before: .. end-##Create_agent


Running the agent in an execution loop
--------------------------------------

Now, you create a simple execution loop to test the agent.
In this loop, you can input the instructions you want the agent to execute and test it out for yourself!

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-##Run_tool_loop
    :end-before: .. end-##Run_tool_loop

Recap
=====

In this guide, you learned how to support user-side confirmation for tool call requests by using ``ServerTool``.


Next steps
==========

Having learned how to add user confirmation for tool calls, you may now proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`

Full code
=========

Click on the card at the :ref:`top of this page <top-userconfirmation>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_userconfirmation.py
    :language: python
    :linenos:
