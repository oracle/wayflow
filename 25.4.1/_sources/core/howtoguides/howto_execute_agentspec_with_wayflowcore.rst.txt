.. _top-execute-agentspec:

=============================================
Execute Agent Spec Configuration with WayFlow
=============================================

.. |python-icon| image:: ../../_static/icons/python-icon.svg
   :width: 40px
   :height: 40px

.. grid:: 2

    .. grid-item-card:: |python-icon| Download Python Script
        :link: ../end_to_end_code_examples/howto_execute_agentspec_with_wayflowcore.py
        :link-alt: Execute Agent Spec with WayFlow how-to script

        Python script/notebook for this guide.

.. admonition:: Prerequisites

    This guide assumes familiarity with `Agent Spec <https://github.com/oracle/agent-spec/>`_ and exporting Agent Spec configurations.


This guide will show you how to:

1. Define the execution of tools in a tool registry.
2. Load an Agent Spec configuration with the WayFlow adapter.
3. Run the assistant and interact with it.

This guide shows you how to use a minimal Agent setup with a single tool for performing multiplications.
You can use the same code structure to load and run more complex assistants.


1. Install packages
-------------------

To run the examples in this guide, make sure that ``wayflowcore`` is installed.

For more details, refer to the `WayFlow Agent Spec adapter API documentation <https://oracle.github.io/agent-spec/api/index.html>`_.

2. Define the tool registry
---------------------------

Before loading the configuration, you need to define the tool registry.
This registry specifies how to execute each tool since the implementation of tools is not
included in the Agent Spec assistant configuration.

The example below shows how to register a single tool that performs multiplications.
Adapt this pattern to register all the tools your assistant requires.

This guide uses the simplest type of tool, ``ServerTool``.
For more advanced tool types, refer to the `Agent Spec Language specification <https://oracle.github.io/agent-spec/agentspec/agentspec_language_spec_0_2.html>`_.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :linenos:
    :start-after: .. start-##_Tool_Registry_Setup
    :end-before: .. end-##_Tool_Registry_Setup


3. Load the Agent Spec configuration
------------------------------------

Now load the agent configuration.
The configuration starts by defining two components: ``multiplication_tool`` and ``vllm_config``.
These are referenced in the agent definition later.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :linenos:
    :start-after: .. start-##_AgentSpec_Configuration
    :end-before: .. end-##_AgentSpec_Configuration

Loading the configuration to the WayFlow executor is simple as long as the ``tool_registry`` has been defined.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :linenos:
    :start-after: .. start-##_Load_AgentSpec_Configuration
    :end-before: .. end-##_Load_AgentSpec_Configuration


4. Run the assistant
--------------------

Start by creating a conversation.
Then prompt the user for some input.
The assistant will respond until you interrupt the process with Ctrl+C.
Messages of type ``TOOL_REQUEST`` and ``TOOL_RESULT`` are also displayed.
These messages help you understand how the assistant decides to act.

For more details, see the :doc:`API Reference <../api/conversation>`.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
   :language: python
   :linenos:
   :start-after: .. start-##_Execution_Loop_Conversational
   :end-before: .. end-##_Execution_Loop_Conversational

You can also run a non-conversational flow.
In that case, the execution loop could be implemented as follows:

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :linenos:
    :start-after: .. start-##_Execution_Loop_Non_Conversational
    :end-before: .. end-##_Execution_Loop_Non_Conversational

Agent Spec Exporting/Loading
============================

You can export the assistant configuration to its Agent Spec configuration using the ``AgentSpecExporter``.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :start-after: .. start-##_Export_Config_to_Agent_Spec
    :end-before: .. end-##_Export_Config_to_Agent_Spec

And load it back using the ``AgentSpecLoader``.

.. literalinclude:: ../code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :start-after: .. start-##_Load_Agent_Spec_Config
    :end-before: .. end-##_Load_Agent_Spec_Config


Next steps
==========

In this guide, you learned how to:

1. Install the Agent Spec adapter for WayFlow.
2. Define tool execution using a tool registry.
3. Load an Agent Spec configuration with the WayFlow adapter.
4. Run the assistant and interact with it in a conversation loop.

You may now proceed to:

- :doc:`How to Connect to a MCP Server <howto_mcp>`
- :doc:`How to Add User Confirmation to Tool Call Requests <howto_userconfirmation>`


Full code
=========

Click on the card at the :ref:`top of this page <top-execute-agentspec>` to download the full code for this guide or copy the code below.

.. literalinclude:: ../end_to_end_code_examples/howto_execute_agentspec_with_wayflowcore.py
    :language: python
    :linenos:
