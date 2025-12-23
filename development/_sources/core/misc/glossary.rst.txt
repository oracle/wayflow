.. _core_ref_glossary:

================
WayFlow Glossary
================

This glossary introduces the key terms and concepts used across the WayFlow library.

Assistant
=========

WayFlow enables the creation of **AI-powered assistants** including:

- :ref:`Flows <flow>` which are structured assistants that follow a pre-defined task completion process;
- :ref:`Agents <agent>` which are conversational assistants that can autonomously plan, think, act, and execute tools to complete tasks in a flexible manner.

WayFlow assistants can be composed together and configured to solve complex tasks with varying degrees of autonomy, ranging from fully self-directed
to highly prescriptive, allowing for a spectrum of flexibility in task completion.

See the :doc:`Tutorials and Use-Case Examples <../tutorials/index>` to learn to build WayFlow assistants.

Agent
=====

An :ref:`Agent <agent>` is a type of LLM-powered assistant that can interact with users, leverage external tools, and interact with other WayFlow assistants
to take specific actions in order to solve user requests through conversational interfaces.

A simple agentic system may involve a single Agent interacting with a human user. More advanced assistants may also involve the use of multiple agents.
Finally, Agents can be integrated in Flows with the :ref:`AgentExecutionStep <agentexecutionstep>`.

To learn more about Agents, see the tutorial :doc:`Build a Simple Conversational Assistant with Agents <../tutorials/basic_agent>`, or read the :ref:`API reference <agent>`.

Branching
=========

Branching is the ability of a :ref:`Flow<flow>` to conditionally transition between different steps based on specific input values or conditions.
Developers can then create more dynamic and adaptive workflows that respond to varying scenarios. Branching is achieved through the use of the
:ref:`BranchingStep <branchingstep>`, which defines multiple possible branches and maps input values to specific steps.

Read the guide :doc:`How to Create Conditional Transitions in Flows <../howtoguides/conditional_flows>` for how to use branching. For more information, read the :ref:`API reference <branchingstep>`.

.. _defclienttool:

Client Tool
===========

See :ref:`tools <tools_section>`

.. _context_section:

Context Provider
================

:ref:`Context providers <contextprovider>` are callable components that are used to provide dynamic contextual information to WayFlow assistants.
They are useful to connect external datasources to an assistant.

For instance, giving the current time of the day to an assistant can be achieved with a context provider.

Read about the different types of context providers in the :ref:`API reference <contextprovider>`.

Control Flow Edge
=================

A :ref:`Control Flow Edge <controlflowedge>` is a connector that represents a directional link between two steps in a :ref:`Flow <flow>`.
It specifies a possible transition between a specific branch of a source step and a destination step.

This concept enables assistant developers to explicitly define the expected transitions that can occur within a Flow.

Read more about control flow edges in the :ref:`API reference <controlflowedge>`.

Composability
=============

Composability refers to the ability of WayFlow assistants to be decomposed into smaller components, combined with other components, and rearranged
to form new assistants that can solve a wide range of tasks. By supporting composability, you can create complex agentic systems
from simpler building blocks.

WayFlow supports four types of agentic patterns:

* Calling :doc:`Agents in Flows <../howtoguides/howto_agents_in_flows>`: Integrate conversational capabilities into structured workflows.
* Calling :ref:`Agents in Agents <describedassistant>`: Combine multiple agents to execute complex tasks autonomously.
* Calling :ref:`Flows in Agents <describedflow>`: Use structured workflows as tools within conversational agents.
* Calling :ref:`Flows in Flows <flowexecutionstep>`: Create nested workflows to model complex business processes.

Conversation
============

A :ref:`Conversation <conversation>` is a stateful object that represents the execution state of a WayFlow assistant.
It stores the list of :ref:`messages <message>` as well as information produced during the assistant execution (for example, tool calls, inputs/outputs produced by steps in a flow).

The conversation object can be modified by the assistant through the ``execute`` method which updates the conversation state based on the assistant's logic.
It also serves as the interface from which end users can interact with WayFlow assistants (for example, by getting the current list of messages, appending a user message, and so on).

The usual code flow when executing WayFlow assistants would be as follows:

1. A new conversation is created using the ``start_conversation`` method from :ref:`Flows <flow>` and :ref:`Agents <agent>`, with optional inputs.
2. Then in the main execution loop:

   * The user may interact with the assistant (for example, by adding a new message).
   * The assistant execution is started/resumed with the ``execute`` method.

For more information about how the Conversation is used, see the :doc:`Tutorials <../tutorials/index>`, or read the :ref:`API reference <conversation>`.


Data Flow Edge
==============

A :ref:`Data Flow Edge <dataflowedge>` is a connector that represents a logical link between steps or context providers within a :ref:`Flow <flow>`.
It defines how data is propagated from the output of one step, or context provider, to the input of another step.

This concept enables assistant developers to explicitly define the expected orchestration of data flows within Flows.

Read more about data flow edges in the :ref:`API reference <dataflowedge>`.

Execution Interrupts
====================

An :ref:`ExecutionInterrupt <executioninterrupt>` is a mechanism that allows assistant developers to intervene in the standard execution of an assistant,
providing the ability to stop or pause the execution when specific events or conditions are met, and execute a custom callback function in response.

For example, the execution can be interrupted when a :ref:`time limit is reached <softtimeoutexecutioninterrupt>` or when a
:ref:`maximum number of tokens is exceeded <softtokenlimitexecutioninterrupt>`, triggering a callback to handle the interruption.

Read more about execution interrupts in the :ref:`API reference <executioninterrupt>`.


Execution Status
================

The :ref:`ExecutionStatus <executionstatus>` is a runtime indicator of an assistant's execution state in WayFlow.
This status provides information about the assistant's current activity, such as whether it has finished its execution,
is waiting for user input, or is waiting on a tool execution result from a :ref:`Client tool <clienttool>`.

The ``ExecutionStatus`` is used in execution loops of :ref:`Agents <agent>` and :ref:`Flows <flow>` to properly manage the conversation with the assistant.

Read more about the types of execution statuses and their use in the :ref:`API reference <executionstatus>`.

Flow
====

A :ref:`Flow <flow>` is a type of structured assistant composed of individual :ref:`steps <presentstep>` that are connected to form a coherent sequence of actions.
Each step in a Flow is designed to perform a specific function, similar to functions in programming.

Flows can have loops, :ref:`conditional transitions <branchingstep>`, and multiple end points. Flows can also :ref:`integrate sub-flows <flowexecutionstep>` and
:ref:`Agents <agentexecutionstep>` to enable more complex capabilities.

A Flow can be used to tackle a wide range of business processes and other tasks in a controllable and efficient way.

Read the tutorial how to :doc:`Build a Simple Fixed-Flow Assistant with Flows<../tutorials/basic_flow>`, or see the available :doc:`How-to Guides <../howtoguides/index>` about Flows.
Also, check the :ref:`API reference <flow>`.

Generation Config
=================

The :ref:`LLM generation config <llmgenerationconfig>` is the set of parameters that control the output of a :ref:`Large Language Model (LLM) <llmmodel>` in WayFlow.
These parameters include the maximum number of tokens to generate (``max_tokens``), the sampling ``temperature``, and the probability threshold for nucleus sampling (``top_p``).

Learn more about the LLM generation config in the :doc:`How to Specify the Generation Configuration when Using LLMs <../howtoguides/generation_config>`
or read the :ref:`API reference <llmgenerationconfig>`.

.. _llms_section:

Large Language Model (LLM)
==========================

A :ref:`Large Language Model <llmmodel>` is a type deep neural network trained on vast amounts of text data that can understand, generate,
and manipulate human language through pattern recognition and statistical relationships. It processes input text through multiple layers of neural networks,
using specific mechanisms to understand context and relationships between words.

Modern LLMs contain billions of parameters and often require dedicated hardware for both training and inference.
As such, they are typically hosted through APIs by their respective providers, allowing for ease of integration and access.

Notably, WayFlow does not handle the inference of LLMs on its server, instead relying on these external APIs to leverage the power of LLMs.
This approach allows WayFlow to remain lightweight while still providing access to the capabilities of these powerful models.

Read our guide :doc:`How to Use LLMs from Different LLM Providers <../howtoguides/llm_from_different_providers>`, or see the :ref:`API reference <llmmodel>`
for the list of supported models.

Message
=======

A :ref:`Message <message>` is a core concept in WayFlow, representing a unit of communication between users and assistants. It provides a structured
way to hold information and can contain various types of data including text, :ref:`tool requests <toolrequest>`, :ref:`results <toolresult>`, as well as other metadata.

Messages are used throughout the library to hold information and facilitate communication between different components.
The list of messages generated during an assistant execution can be accessed directly from a :ref:`Conversation <conversation>`.

Read more about messages in the :ref:`API reference <message>`.

.. _prompt_engineering_section:

Prompt Engineering and Optimization
===================================

Prompt engineering and optimization is the systematic process of designing, refining, and improving prompts to achieve more accurate,
reliable, and desired outputs from language models. It involves iterative testing and refinement of prompt structures, careful consideration of
context windows, and strategic use of examples and formatting.

Methods such as Automated Prompt Engineering can help improve prompts by using algorithms to optimize the prompt performance on a specific metric.

Prompt Engineering Styles
-------------------------

.. list-table::
   :widths: 30 30 50
   :header-rows: 1

   * - Technique
     - Description
     - Example
   * - Zero-shot
     - No example, just task
     - "Summarize this article."
   * - Few-shot
     - Provide examples
     - "Q: What is 2+2? A: 4..."
   * - Chain-of-thought
     - Encourage step-by-step thinking
     - "Let's think step-by-step..."
   * - Role prompting
     - Assign a persona
     - "You are an expert lawyer..."
   * - Constraint-based
     - Set strict formats or word limits
     - Answer in JSON with keys 'title'..."

Prompt Template
===============

A prompt template is a standardized prompt structure with placeholders for variable inputs, designed to maintain consistency across similar queries
while allowing for customization. WayFlow uses Jinja-style placeholders to specify the input variables to the prompt (for more information check
the `reference of Jinja2 <https://jinja.palletsprojects.com/en/stable/templates>`_).

See the :doc:`Tutorials and Use-Case Examples <../tutorials/index>` for concrete examples, or check the
:ref:`TemplateRenderingStep API reference <templaterenderingstep>`.

.. note::

    Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja's rendering capabilities.
    Please check our guide on :ref:`How to write secure prompts with Jinja templating <securejinjatemplating>` for more information.

Prompt templates can be used in WayFlow components that use LLMs, such as :ref:`Agents <agent>` and the :ref:`PromptExecutionStep <promptexecutionstep>`.

Properties
==========

A :ref:`Property <property>` is a metadata descriptor that provides information about an input/output value of a component (:doc:`Tools <../api/tools>`,
:ref:`Steps <presentstep>`, :ref:`Flows <flow>`, and :ref:`Agents <agent>`) in a WayFlow assistant. Properties can represent various data types such as
:ref:`boolean <booleanproperty>`, :ref:`float <floatproperty>`, :ref:`integer <integerproperty>`, :ref:`string <stringproperty>`,
as well as nested types such as :ref:`list <listproperty>`, :ref:`dict <dictproperty>`, or :ref:`object <objectproperty>`.

Properties include attributes such as name, description, and default value, which help to clarify the purpose and behavior of the component,
making it easier to understand and interact with the component.

To learn more about the use of properties, read the guide :doc:`How to Change Input and Output Descriptors of Components<../howtoguides/io_descriptors>`,
and check the :ref:`API reference <property>`.


Remote Tool
===========

See :ref:`tools <tools_section>`


Retrieval Augmented Generation (RAG)
====================================

Retrieval Augmented Generation  (RAG) is a technique to enhance LLM outputs by first retrieving relevant information from a knowledge base and then incorporating
it into the generation process. This approach enhances the model's ability to access and utilize specific information beyond its training data.

RAG systems typically involves a retrieval component that searches for relevant information and a generation component that incorporates this
information into the final output.

Serialization
=============
.. _defserialization:

In WayFlow, serialization refers to the ability to capture the current configuration of an assistant and represent it in a compact, human-readable form.
This allows assistants to be easily shared, stored, or deployed across different environments, while maintaining their functionality and consistency.

Read the guide :doc:`How to Serialize and Deserialize Flows and Agents <../howtoguides/howto_serdeser>` or check the :ref:`API reference <serialization>` for more information.

.. _defservertool:

Server Tool
===========

See :ref:`tools <tools_section>`

Step
====

A :ref:`Step <presentstep>` is an atomic element of a :ref:`Flow <flow>` that encapsulates a specific piece of logic or functionality.
WayFlow proposes a variety of steps with functionalities ranging from :ref:`LLM generation <promptexecutionstep>` and :ref:`tool use <toolexecutionstep>`
to :ref:`branching <branchingstep>`, :ref:`data extraction <extractvaluefromjsonstep>`, and :ref:`much more <presentstep>`. By composing the steps together, WayFlow enables
the creation of powerful structured assistants to solve diverse use cases efficiently and reliably.

Check the list of available steps in the :ref:`API reference <presentstep>`.

.. _defstructuredgeneration:

Structured Generation
=====================

Structured generation is the process of controlling LLM outputs to conform to specific formats, schemas, or patterns, ensuring consistency and
machine-readability of generated content. It involves techniques for guiding the model to produce outputs that follow predetermined structures
while maintaining natural language fluency.

This approach is particularly valuable for generating data in formats like JSON, XML, or other structured representations.

For more information, see the guide :doc:`How to Do Structured LLM Generation in Flows <../howtoguides/howto_promptexecutionstep>`.

.. _tools_section:

Tools
=====

.. image:: ../_static/howto/types_of_tools.svg
   :align: center
   :scale: 100%
   :alt: Types of tools


WayFlow support three types of tools:

Server Tool
-----------

A :ref:`Server Tool <servertool>` is the simplest type of tool available in WayFlow. It is simply defined with the signature of the tool to execute including:

* A tool name.
* A tool description.
* The names, types, and optional default values for the input parameters of the tool.
* A Python callable, which is the callable to invoke upon the tool execution.
* The output type.

See the guide :doc:`How to Build Assistants with Tools <../howtoguides/howto_build_assistants_with_tools>` for how to use Server tools.
For more information about the ``ServerTool``, read the :ref:`API reference <servertool>`.


Client Tool
-----------

A :ref:`Client tool <clienttool>` is a type of tool that can be built in WayFlow. Contrary to the :ref:`Server Tool <servertool>` which is directly executed on the server side,
upon execution the client tool returns a :ref:`ToolRequest <toolrequest>` to be executed on the client side, which then sends the execution result back to the assistant.

See the guide :doc:`How to Build Assistants with Tools <../howtoguides/howto_build_assistants_with_tools>`. For more information about the ``ClientTool``, read the :ref:`API reference <clienttool>`.


Remote Tool
-----------

A :ref:`Remote tool <remotetool>` is a type of tool that can be used in WayFlow to perform API calls.

For more information about the ``RemoteTool``, read the :ref:`API reference <remotetool>`.

Tokens
======

Tokens are the fundamental units of text processing in LLMs, representing words, parts of words, or characters that the model uses to understand and generate language.

They form the basis for the model's context window size and directly impact processing costs and performance.

It is worth noting that there are two types of tokens relevant to LLMs: input tokens and output tokens.
Input tokens refer to the tokens that are fed into the model as input, whereas output tokens are the tokens generated by the model as output.
In general, output tokens are more expensive than input tokens. An example of pricing can be $3 per 1M input tokens, and $10 per 1M output tokens.

.. _variables_section:

Variable
========

A :ref:`Variable <variable>` is a flow-scoped data container that enables the storage and retrieval of data throughout a :ref:`Flow <flow>`.
Variables act as the shared state or context of a Flow (often referred to as `state` in other frameworks),
providing a way to decouple data from specific steps and make it available for use within multiple parts of the Flow.
They can be accessed and modified throughout a Flow using :ref:`VariableReadStep <variablereadstep>` and :ref:`VariableWriteStep <variablewritestep>` operations.

Note that Variables are complementary to the value stored in the input/output dictionary which is specific to the steps execution.

Learn more about Variables in the :ref:`API reference <variable>`.
