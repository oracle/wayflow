==================================================
How to Add User Confirmation to Tool Call Requests
==================================================

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Agents <../tutorials/basic_agent>`
    - :doc:`Building Assistants with Tools <howto_build_assistants_with_tools>`

WayFlow :ref:`Agents <agent>` can be equipped with :doc:`Tools <../api/tools>` to enhance their capabilities.
However, end users may want to confirm or deny tool call requests emitted from the agent.

This guide shows you how to achieve this with the :ref:`ClientTool <clienttool>`.


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


Creating the tools
------------------

Sometimes you will want to ask for user confirmation before executing certain tools. To do this you use a :ref:`ClientTool <clienttool>`.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-create_tools:
    :end-before: .. end-create_tools


Creating the client-side execution logic
----------------------------------------

To enable users to accept or deny tool call requests, you add simple validation logic before executing the tools requested by the agent.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-create_tool_execution:
    :end-before: .. end-create_tool_execution

Here, you simply loop until the user answers whether to accept the tool request (with ``Y``) or reject it (with ``N``).


Creating the agent
------------------

Finally, you create a simple ``Agent`` to test the execution code written in the previous section.

.. literalinclude:: ../code_examples/howto_userconfirmation.py
    :language: python
    :start-after: .. start-create_agent:
    :end-before: .. end-create_agent


Running the agent in an execution loop
--------------------------------------

Now, you create a simple execution loop to test the agent.
In this loop, you specify that only the ``subtract_numbers`` and ``multiply_numbers`` tools require user confirmation,
while the ``add_numbers`` tool can be executed autonomously by the agent.

.. code:: python

    from wayflowcore.executors.executionstatus import (
        FinishedStatus, UserMessageRequestStatus, ToolRequestStatus
    )
    from wayflowcore.messagelist import Message, MessageType
    from wayflowcore.models import VllmModel
    from wayflowcore.tools import ToolResult

    TOOLS_REQUIRING_CONFIRMATION = ["subtract_numbers", "multiply_numbers"]

    conversation_inputs = {}
    conversation = assistant.start_conversation(inputs=conversation_inputs)

    while True:
        status = conversation.execute()
        assistant_reply = conversation.get_last_message()
        if assistant_reply:
            print(f"Assistant>>> {assistant_reply.content}\n")

        if isinstance(status, FinishedStatus):
            print(f"Finished assistant execution. Output values:\n{status.output_values}",)
            break
        elif isinstance(status, UserMessageRequestStatus):
            user_input = input("User>>> ")
            print("\n")
            conversation.append_user_message(user_input)
        elif isinstance(status, ToolRequestStatus):
            tool_request = status.tool_requests[0]
            tool_result = execute_client_tool_from_tool_request(tool_request, TOOLS_REQUIRING_CONFIRMATION)
            print(f"{tool_result!r}")
            conversation.append_message(
                Message(
                    tool_result=ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id),
                    message_type=MessageType.TOOL_RESULT,
                )
            )
        else:
            raise ValueError(f"Unsupported execution status: '{status}'")

.. end-execution_loop

Recap
=====

In this guide, you learned how to support client-side confirmation for tool call requests.

.. collapse:: Below is the complete code from this guide.

    .. literalinclude:: ../code_examples/howto_userconfirmation.py
        :language: python
        :start-after: .. start-create_tools:
        :end-before: .. end-create_tools

    .. literalinclude:: ../code_examples/howto_userconfirmation.py
        :language: python
        :start-after: .. start-create_tool_execution:
        :end-before: .. end-create_tool_execution

    .. literalinclude:: ../code_examples/howto_userconfirmation.py
        :language: python
        :start-after: .. start-create_agent:
        :end-before: .. end-create_agent

    .. literalinclude:: howto_userconfirmation.rst
        :start-after: .. code:: python
        :end-before: .. end-execution_loop
        :dedent: 4


Next steps
==========

Having learned how to add user confirmation for tool calls, you may now proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`
