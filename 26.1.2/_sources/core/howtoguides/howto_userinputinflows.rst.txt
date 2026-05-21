.. _top-userinputinflows:

==================================
How to Ask for User Input in Flows
==================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_userinputinflows.py
        :link-alt: User input in flows how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with:

    - :doc:`Flows <../tutorials/basic_flow>`
    - :doc:`Tools <../api/tools>`

WayFlow allows you to build powerful automation and agentic workflows.
In many real-world scenarios, your flows will need to request and incorporate input from a human user — either to execute a particular action, validate a decision, or simply continue the process.

This guide explains how to design flows that pause for user input, receive responses, and resume execution seamlessly (also known as Human-in-the-loop (HITL) machine learning).

Overview
========

There are two standard patterns for requesting user input within a flow:

- **Simple user requests** (e.g., prompting the user for a question or parameter)
- **Interactive/branching patterns** (e.g., asking for confirmation before performing an action, with logic based on the user's response)

This guide will show you how to:

- Add a user input request to your flow using the :ref:`InputMessageStep <inputmessagestep>`
- Connect user responses to further steps for flexible flow logic
- Chain multiple interactions, including branching for confirmation scenarios

.. note::
    User input is always delivered via ``InputMessageStep``. WayFlow's status objects make it easy to detect when input is required and to resume execution once the user has responded.


Basic implementation
====================

This guide requires the use of an LLM.
WayFlow supports several LLM API providers.
Select an LLM from the options below:

.. include:: ../_components/llm_config_tabs.rst

The easiest way to capture user input is with ``InputMessageStep``.
Used in combination with an execution loop, this step is used to prompt the user for input,
pause flow execution, and deliver the user's response into the flow's data context for
use by subsequent steps.

.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Create_Simple_Flow
    :end-before: .. end-##_Create_Simple_Flow

API Reference: :ref:`Flow <flow>` | :ref:`InputMessageStep <inputmessagestep>` | :ref:`CompleteStep <completestep>`

You can then execute this flow as shown below. Notice how the execution is paused until the user enters their input:

.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Execute_Simple_Flow
    :end-before: .. end-##_Execute_Simple_Flow

.. note::
    When ``conversation.execute()`` returns a ``UserMessageRequestStatus``, you must append a user message (with ``conversation.append_user_message(...)``) to continue the flow.


Advanced pattern: Request user input for tool calls or approvals
================================================================

.. seealso::

    For details on enabling client-side confirmations, see the guide :doc:`How to Add User Confirmation to Tool Call Requests <howto_userconfirmation>`.

In some cases, it is necessary not only to collect a user's initial input but also request confirmation before executing certain actions — such as validating tool calls or branching flow execution based on user responses.

The following example demonstrates a more sophisticated flow.
The flow pauses both for the user's main request and again for tool call confirmation, using branching to repeat or skip steps depending on the response.

.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Create_Complex_Flow
    :end-before: .. end-##_Create_Complex_Flow

API Reference: :ref:`Flow <flow>` | :ref:`InputMessageStep <inputmessagestep>` | :ref:`BranchingStep <branchingstep>` | :ref:`ToolExecutionStep <toolexecutionstep>`

.. note::
    The ``InputMessageStep`` can be reused at multiple points in a flow for different types of input—questions, approvals, parameter selection, etc. Use ``BranchingStep`` to control your logic flow depending on the user's reply.

To drive this advanced flow, you execute and interact with the agent as follows:

.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Execute_Complex_Flow
    :end-before: .. end-##_Execute_Complex_Flow

.. tip::
    Design your ``message_template`` and branching mapping to ensure robust, user-friendly interactions.
    You can combine user input at any point with decision logic for flexible, agent-like flows.

    You can also use :ref:`CatchExceptionStep <catchexceptionstep>` to handle issues such as user typing something else than "y/n".

Agent Spec Exporting/Loading
============================

You can export the flow configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec


Here is what the **Agent Spec representation will look like ↓**

.. collapse:: Click here to see the assistant configuration.

   .. tabs::

      .. tab:: JSON

         .. literalinclude:: ../config_examples/howto_userinputinflows.json
            :language: json

      .. tab:: YAML

         .. literalinclude:: ../config_examples/howto_userinputinflows.yaml
            :language: yaml

You can then load the configuration back to an assistant using the ``AgentSpecLoader``.


.. literalinclude:: ../code_examples/howto_userinputinflows.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config

.. note::

    This guide uses the following extension/plugin Agent Spec components:

    - ``PluginInputMessageNode``
    - ``PluginConstantContextProvider``
    - ``PluginExtractNode``
    - ``ExtendedToolNode``
    - ``ExtendedFlow``

    See the list of available Agent Spec extension/plugin components in the :doc:`API Reference <../api/agentspec>`


Next steps
==========

In this guide, you learned how to request and handle user input and approval inside WayFlow flows using ``InputMessageStep``, as well as how to combine input with branching for selective actions. You may now proceed to:

- :doc:`How to Create Conditional Transitions in Flows <conditional_flows>`
- :doc:`How to Add User Confirmation to Tool Call Requests <howto_userconfirmation>`
- :doc:`How to Create a ServerTool from a Flow <create_a_tool_from_a_flow>`


Full code
=========

Click on the card at the :ref:`top of this page <top-userinputinflows>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_userinputinflows.py
    :language: python
    :linenos:
