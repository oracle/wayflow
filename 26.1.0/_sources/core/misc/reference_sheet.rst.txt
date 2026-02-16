.. _core_ref_sheet:

=======================
WayFlow Reference Sheet
=======================

This reference sheet provides a single-page overview of basic code snippets covering the core concepts used in WayFlow.

Each section includes links to additional tutorials and guides for deeper learning.

LLMs
====

WayFlow Agents and Flows may require the use of Large Language Models (LLMs).
This section shows how to initialize an LLM and perform quick tests.


Loading an LLM instance
-----------------------

WayFlow supports several LLM API providers.
For an overview of supported LLMs, see the guide
:doc:`How to Use LLMs from Different Providers <../howtoguides/llm_from_different_providers>`.

Start by selecting an LLM from one of the available providers:

.. include:: ../_components/llm_config_tabs.rst

Read more about the LLMs support in the :ref:`API reference <llmmodel>`.


Testing inference with LLMs
---------------------------

Single prompt generation
^^^^^^^^^^^^^^^^^^^^^^^^

Use a simple :ref:`PromptExecutionStep <promptexecutionstep>` to test an LLM.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-single_generation:
   :end-before: .. end-single_generation

**API Reference:** :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`Flow <flow>`

.. tip::

   Use the helper methods ``create_single_step_flow`` and ``run_flow_and_return_outputs`` for quick prototyping.


Parallel generation
^^^^^^^^^^^^^^^^^^^

Add a :ref:`MapStep <mapstep>` to perform inference on a batch of inputs (parallel generation).

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-parallel_generation:
   :end-before: .. end-parallel_generation

**API Reference:** :ref:`ListProperty <listproperty>` | :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`MapStep <mapstep>` | :ref:`Flow <flow>`

.. note::

   Note the use of a :ref:`ListProperty <listproperty>` to specify the output of the :ref:`MapStep <mapstep>`.


Structured generation
^^^^^^^^^^^^^^^^^^^^^

WayFlow supports :ref:`structured generation <defstructuredgeneration>` (such as controlling LLM outputs to conform to specific formats, schemas, or patterns, for example, Json Schema).

Structured generation can be achieved by specifying the output descriptors of the :ref:`PromptExecutionStep <promptexecutionstep>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-structured_generation:
   :end-before: .. end-structured_generation

**API Reference:** :ref:`StringProperty <stringproperty>` | :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`Flow <flow>`

Read the guide on :doc:`How to Perform Structured Generation <../howtoguides/howto_promptexecutionstep>` for more information.


Tools
=====

Tools are essential for building powerful Agents and Flows.
WayFlow supports the use of :ref:`ServerTool <servertool>` (which can be simply built with the :ref:`tool <tooldecorator>` decorator), the :ref:`RemoteTool <remotetool>` as well as
the :ref:`ClientTool <clienttool>`.

.. image:: ../_static/howto/types_of_tools.svg
   :align: center
   :scale: 60%

**Figure:** The different tools in WayFlow.


Creating a simple tool
----------------------

The simplest way to create a tool in WayFlow is by using the :ref:`tool <tooldecorator>` decorator, which creates a :ref:`ServerTool <servertool>` (see definition :ref:`in the glossary <defservertool>`).

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-simple_server_tool:
   :end-before: .. end-simple_server_tool

**API Reference:** :ref:`tool <tooldecorator>`

For more information, read the guide on :doc:`How to Build Assistants with Tools <../howtoguides/howto_build_assistants_with_tools>` or read
the :doc:`API reference <../api/tools>` to learn about the available types of tools in WayFlow.


Creating a stateful tool
------------------------

To build stateful tools, simply use the :ref:`tool <tooldecorator>` helper as a wrapper to the method of an instantiated class.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-simple_stateful_tool:
   :end-before: .. end-simple_stateful_tool

**API Reference:** :ref:`tool <tooldecorator>`


Creating and using a Client tool
--------------------------------

Use the :ref:`ClientTool <clienttool>` to create tools that are meant to be executed on the client side (see :ref:`definition in the glossary <defclienttool>`).

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-client_tool:
   :end-before: .. end-client_tool

**API Reference:** :ref:`ClientTool <clienttool>` | :ref:`ToolRequest <toolrequest>` | :ref:`ToolResult <toolresult>` | :ref:`ToolExecutionStep <toolexecutionstep>` | :ref:`ToolRequestStatus <toolrequestexecutionstatus>` | :ref:`Flow <flow>`

Learn more about tools by reading :doc:`How to Build Assistants with Tools <../howtoguides/howto_build_assistants_with_tools>`, and the :doc:`Tools API reference <../api/tools>`.

.. _refsheet_executionloop:

Execution loop and statuses
===========================

This section illustrates a basic execution loop for WayFlow assistants (Agents and Flows).

1. A new conversation is created.
2. The assistant is executed on the conversation.
3. Based on the status returned from the assistant execution:
   * The loop exits if the status is ``FinishedStatus``.
   * The user is prompted for input if the status is ``UserMessageRequestStatus``.
   * A ``ClientTool`` is executed if the status is ``ToolRequestStatus``.

The loop continues until the assistant returns a ``FinishedStatus``.

.. code:: python

   from typing import Any
   from wayflowcore.messagelist import Message, MessageType
   from wayflowcore.executors.executionstatus import (
      FinishedStatus, UserMessageRequestStatus, ToolRequestStatus
   )
   from wayflowcore.tools import ToolRequest, ToolResult

   def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
      if tool_request.name == "my_tool_name":
         return _my_tool_callable(**tool_request.args)
      else:
         raise ValueError(f"Tool name {tool_request.name} is not recognized")

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
         tool_result = execute_client_tool_from_tool_request(tool_request)
         print(f"{tool_result!r}")
         conversation.append_message(
               Message(
                  tool_result=ToolResult(content=tool_result, tool_request_id=tool_request.tool_request_id),
                  message_type=MessageType.TOOL_RESULT,
               )
         )
      else:
         raise ValueError(f"Unsupported execution status: '{status}'")


Learn more about execution loops by reading the :ref:`Execution Status API reference <executionstatus>`.

Agents
======

WayFlow :ref:`Agents <agent>` are LLM-powered assistants that can interact with users, leverage external tools, and interact with other WayFlow assistants to take specific actions
in order to solve user requests through conversational interfaces.

Creating a simple Agent
-----------------------

Creating an :ref:`Agent <agent>` only requires an LLM and optional instructions to guide the agent behavior.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-simple_agent:
   :end-before: .. end-simple_agent

**API Reference:** :ref:`Agent <agent>`

Learn more about Agents by reading the tutorial :doc:`Build a Simple Conversational Assistant with Agents <../tutorials/basic_agent>`
and the :ref:`Agent API reference <agent>`.


Creating a Agent with tools
---------------------------

You can simply equip :ref:`Agents <agent>` with tools using the ``tools`` attribute of the agent.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-agent_with_tool:
   :end-before: .. end-agent_with_tool

**API Reference:** :ref:`Agent <agent>` | :ref:`tool <tooldecorator>`


Flows
=====

WayFlow :ref:`Flows <flow>` are LLM-powered structured assistants composed of individual steps that are connected to form a coherent sequence of actions.
Each step in a ``Flow`` is designed to perform a specific function, similar to functions in programming.


Creating a simple Flow
----------------------

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-simple_flow:
   :end-before: .. end-simple_flow

**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`Flow <flow>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more about Flows by reading the tutorial :doc:`Build a Simple Fixed-Flow Assistant with Flows <../tutorials/basic_flow>` and the :ref:`Flow API reference <flow>`.


Creating Flow with explicit data connection
-------------------------------------------

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_with_dataconnection:
   :end-before: .. end-flow_with_dataconnection

**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more about data flow edges in the :ref:`Data Flow Edges API reference <dataflowedge>`.


Executing a sub-flow to an iterable with the MapStep
----------------------------------------------------

Applying or executing a sub-flow to an iterable is a common pattern and can be achieved in WayFlow using the :ref:`MapStep <mapstep>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_with_mapstep:
   :end-before: .. end-flow_with_mapstep

**API Reference:** :ref:`Flow <flow>` | :ref:`MapStep <mapstep>` | :ref:`OutputMessageStep <outputmessagestep>` | :ref:`AnyProperty <anyproperty>`

Learn more about MapSteps by reading :doc:`How to Do Map and Reduce Operations in Flows <../howtoguides/howto_mapstep>` and the :ref:`MapStep API reference <mapstep>`.


Adding conditional branching to Flows with the BranchingStep
------------------------------------------------------------

It is also frequent to want to transition in a :ref:`Flow <flow>` depending on a condition, and this can be achieved in WayFlow with the :ref:`BranchingStep <branchingstep>`.

.. image:: ../_static/howto/branchingstep.svg
   :align: center
   :scale: 95%
   :alt: Flow diagram of a simple branching step

**Figure:** An example of a ``Flow`` using a ``BranchingStep``.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_with_branching:
   :end-before: .. end-flow_with_branching

**API Reference:** :ref:`Flow <flow>` | :ref:`BranchingStep <branchingstep>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more about branching steps by reading :doc:`How to Create Conditional Transitions in Flows <../howtoguides/conditional_flows>` and
the :ref:`BranchingStep API reference <branchingstep>`.


Adding tools to Flows with the ToolExecutionStep
------------------------------------------------

To use tools in :ref:`Flows <flow>`, use the :ref:`ToolExecutionStep <toolexecutionstep>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_with_tools:
   :end-before: .. end-flow_with_tools

**API Reference:** :ref:`Flow <flow>` | :ref:`ToolExecutionStep <toolexecutionstep>` | :ref:`ServerTool <servertool>`

Learn more about ``ToolexecutionSteps`` by reading :doc:`How to Build Assistants with Tools <../howtoguides/howto_build_assistants_with_tools>`
and the :ref:`ToolexecutionSteps API reference <toolexecutionstep>`.


Agentic composition patterns
============================

There are four majors agentic composition patterns supported in WayFlow:

* Calling Agents in Flows
* Calling Agents in Agents
* Calling Flows in Agents
* Calling Flows in Flows


Using an Agent in a Flow
------------------------

To use :ref:`Agents <agent>` in :ref:`Flows <flow>`, you can use the :ref:`AgentExecutionStep <agentexecutionstep>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-agent_in_flow:
   :end-before: .. end-agent_in_flow

**API Reference:** :ref:`Flow <flow>` | :ref:`Agent <agent>` | :ref:`AgentExecutionStep <agentexecutionstep>`

Learn more about Agents in Flows by reading :doc:`How to Use Agents in Flows <../howtoguides/howto_agents_in_flows>`
and the :ref:`Agent Execution Step API reference <agentexecutionstep>`.

.. warning::

   The ``AgentExecutionStep`` is currently in beta and may undergo significant changes.
   The API and behaviour are not guaranteed to be stable and may change in future versions.


Multi-Level Agent Workflows
---------------------------

WayFlow supports hierarchical multi-agent systems, by using expert :ref:`Agents <agent>` with a master / manager agent.
This can be achieved by using a :ref:`DescribedAgent <describedassistant>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-agent_in_agent:
   :end-before: .. end-agent_in_agent


**API Reference:** :ref:`Agent <agent>` | :ref:`DescribedAgent <describedassistant>`

.. warning::

   The use of expert agents is currently in beta and may undergo significant changes.
   The API and behaviour are not guaranteed to be stable and may change in future versions.


Using Flows Within Agents
-------------------------

To use :ref:`Flows <flow>` in :ref:`Agents <agent>`, use the :ref:`DescribedFlow <describedflow>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_in_agent:
   :end-before: .. end-flow_in_agent


**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`PromptExecutionStep <promptexecutionstep>` | :ref:`DescribedFlow <describedflow>`

Learn more about the use of :ref:`Flows <flow>` in :ref:`Agents <agent>` in the :ref:`API reference <describedflow>`.


Using Sub-Flows Within Flows
----------------------------

To use sub-flows in :ref:`Flows <flow>`, use the :ref:`FlowExecutionStep <flowexecutionstep>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_in_flow:
   :end-before: .. end-flow_in_flow


**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`FlowExecutionStep <flowexecutionstep>` | :ref:`OutputMessageStep <outputmessagestep>` | :ref:`PromptExecutionStep <promptexecutionstep>`

Learn more about the use of sub-flows in :ref:`Flows <flow>` by reading the :ref:`FlowExecutionStep API reference <flowexecutionstep>`.


Saving and loading WayFlow assistants
=====================================

.. image:: ../_static/howto/ser_deser.svg
   :align: center
   :scale: 100%
   :alt: Serialization/deserialization of Agents and Flows in WayFlow

**Figure:** How serialization works in WayFlow.


Saving and loading simple assistants
------------------------------------

Save and load WayFlow assistants using the :ref:`serialize <serialize>` and :ref:`autodeserialize <autodeserialize>` helper functions.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-serialize_simple_assistants:
   :end-before: .. end-serialize_simple_assistants

**API Reference:** :ref:`Agent <agent>` | :ref:`serialize <serialize>` | :ref:`autodeserialize <autodeserialize>`

Learn more about Serialisation by reading :doc:`How to Serialize and Deserialize Flows and Agents <../howtoguides/howto_serdeser>`
and the :ref:`Serialisation API reference <serialization>`.


Saving and loading assistants with tools
----------------------------------------

Register tools to a ``DeserializationContext`` to load assistants using tools.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-serialize_assistants_with_tools:
   :end-before: .. end-serialize_assistants_with_tools

**API Reference:** :ref:`Agent <agent>` | :ref:`serialize <serialize>` | :ref:`autodeserialize <autodeserialize>` | :ref:`tool <tooldecorator>`

Learn more about Serialisation by reading :doc:`How to Serialize and Deserialize Flows and Agents <../howtoguides/howto_serdeser>`
and the :ref:`Serialisation API reference <serialization>`.


Providing context to assistants
===============================

Passing contextual information to assistants can be done in several ways, including:

* By specifying input values when creating the :ref:`Conversation <conversation>`.
* By using :ref:`ContextProviders <contextprovider>`.
* By using :ref:`Variables <variable>`.


Providing context with inputs
-----------------------------

You can pass static inputs when creating a new :ref:`Conversation <conversation>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-inputs_provider:
   :end-before: .. end-inputs_provider

**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`Flow <flow>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more about passing static inputs in the :ref:`Conversation API reference <conversation>`.

Providing dynamic inputs with ContextProviders
----------------------------------------------

:ref:`ContextProviders <contextprovider>` can be used to provide dynamic information to WayFlow assistants.

Using the ToolContextProvider
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the :ref:`ToolContextProvider <toolcontextprovider>` to provide information to an assistant with a tool.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-tool_contextprovider:
   :end-before: .. end-tool_contextprovider

**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`ToolContextProvider <toolcontextprovider>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`tool <tooldecorator>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more by reading the :ref:`ToolContextProvider API reference <toolcontextprovider>`.


Using the FlowContextProvider
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use the :ref:`FlowContextProvider <flowcontextprovider>` to provide information to an assistant with a :ref:`Flow <flow>`.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-flow_contextprovider:
   :end-before: .. end-flow_contextprovider

**API Reference:** :ref:`FlowContextProvider <flowcontextprovider>` | :ref:`ControlFlowEdge <controlflowedge>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`OutputMessageStep <outputmessagestep>`

Learn more by reading the :ref:`FlowContextProvider API reference <flowcontextprovider>`.


Using Variables to provide context
----------------------------------

You can use :ref:`Variables <variable>` as an alternative way to manage context (or shared state) in :ref:`Flows <flow>`.
They let you store and reuse information across different steps in Flows.

.. literalinclude:: ../code_examples/reference_sheet.py
   :language: python
   :start-after: .. start-context_with_variables:
   :end-before: .. end-context_with_variables

**API Reference:** :ref:`ControlFlowEdge <controlflowedge>` | :ref:`DataFlowEdge <dataflowedge>` | :ref:`Flow <flow>` | :ref:`ListProperty <listproperty>` | :ref:`FloatProperty <floatproperty>` | :ref:`VariableReadStep <variablereadstep>` | :ref:`VariableWriteStep <variablewritestep>` | :ref:`OutputMessageStep <outputmessagestep>` | :ref:`Variable <variable>`

Learn more by reading the :ref:`Variables API reference <variable>`.



.. _flowbuilder_ref_sheet:

Flow Builder quick snippets
---------------------------

Build a sequence, then entry/finish:

.. literalinclude:: ../code_examples/howto_flowbuilder.py
   :language: python
   :start-after: .. start-##_Build_a_linear_flow
   :end-before: .. end-##_Build_a_linear_flow

API Reference: :ref:`FlowBuilder <flowbuilder>`

Build a linear flow in one line:

.. literalinclude:: ../code_examples/howto_flowbuilder.py
   :language: python
   :start-after: .. start-##_Build_a_linear_flow_equivalent
   :end-before: .. end-##_Build_a_linear_flow_equivalent


Add a conditional using a step output as key, with a default branch:

.. literalinclude:: ../code_examples/howto_flowbuilder.py
   :language: python
   :start-after: .. start-##_Build_a_flow_with_a_conditional
   :end-before: .. end-##_Build_a_flow_with_a_conditional
