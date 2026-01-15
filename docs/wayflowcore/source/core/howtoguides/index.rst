.. _how-to_guides:

:html_theme.sidebar_secondary.remove:

How-to Guides
=============

Within this section, you will find answers to "How do I..." types of questions.
The proposed guides are goal-oriented and concrete, as they are meant to help you complete a specific task.
Each code example in these how-to guides is self-contained and can be executed with :doc:`WayFlow <../index>`.

For comprehensive, end-to-end walkthroughs, refer to the :doc:`Tutorials <../tutorials/index>`.
For detailed descriptions of every class and function, see the :doc:`API Reference <../api/index>`.


Building Assistants
-------------------

WayFlow offers a wide range of features for building :ref:`Agents <agent>`, :ref:`Flows <flow>` as well
as multi-agent patterns such as :doc:`hierarchical multi-agent <howto_multiagent>` and :ref:`Swarm <swarm>`.
These how-to guides demonstrate how to use the main features to create and customize your assistants.

.. toctree::
   :maxdepth: 1

   Change Input and Output Descriptors of Components <io_descriptors>
   Use Asynchronous APIs <howto_async>

.. toctree::
   :maxdepth: 1
   :caption: LLMs

   Install and Use Ollama <installing_ollama>
   Specify the Generation Configuration when Using LLMs <generation_config>
   Use LLM from Different LLM Sources and Providers <llm_from_different_providers>
   Handle long context with agents <howto_long_context>

.. toctree::
   :maxdepth: 1
   :caption: Agents

   Create a ReAct Agent <agents>
   How to Send Images to LLMs and Agents <howto_imagecontent>
   Use OCI Generative AI Agents <howto_ociagent>
   How to Connect to A2A Agents <howto_a2aagent>
   Use Templates for Advanced Prompting Techniques <howto_prompttemplate>

.. toctree::
   :maxdepth: 1
   :caption: Flows

   Ask for User Input in Flows <howto_userinputinflows>
   Create Conditional Transitions in Flows <conditional_flows>
   Do Structured LLM Generation in Flows <howto_promptexecutionstep>
   Add User Confirmation to a Tool Call Request <howto_userconfirmation>
   Catch Exceptions in Flows <catching_exceptions>
   Do Map and Reduce Operations in Flows <howto_mapstep>
   Run Multiple Flows in Parallel <howto_parallelflowexecution>
   Build Flows with the Flow Builder <howto_flowbuilder>

.. toctree::
   :maxdepth: 1
   :caption: Multi-Agent Patterns

   Use Agents in Flows <howto_agents_in_flows>
   Build a Hierarchical Multi-Agent System <howto_multiagent>
   Build a Swarm of Agents <howto_swarm>
   Build a ManagerWorkers of Agents <howto_managerworkers>


.. toctree::
   :maxdepth: 1
   :caption: Deployment

   Serve Agents with WayFlow <howto_serve_agents>
   Serve Assistants with A2A protocol <howto_a2a_serving>

Tools in Assistants
-------------------

Equipping AI assistants with tools unlock key capabilities such as being able to fetch data,
take action, and connect to external data and systems. These guides cover how to leverage the
several tools features available in WayFlow, such as :ref:`server-side tools <servertool>`,
:ref:`client-side tools <clienttool>`, tools to perform :ref:`remote API calls <remotetool>`,
and support for :ref:`Model Context Protocol (MCP) tools <mcptool>`.

.. toctree::
   :maxdepth: 1

   Build Assistants with Tools <howto_build_assistants_with_tools>
   Create Tools with Multiple Outputs <howto_multiple_output_tool>
   Convert Flows to Tools <create_a_tool_from_a_flow>
   Connect MCP tools to Assistants <howto_mcp>
   Do Remote API Calls with Tokens <howto_remote_tool_expired_token>


Configuration and State Management
----------------------------------

These guides demonstrate how to configure the components of assistants built with WayFlow.

.. toctree::
   :maxdepth: 1

   Load and Execute an Agent Spec Configuration <howto_execute_agentspec_with_wayflowcore>
   Serialize and Deserialize Flows and Agents <howto_serdeser>
   Serialize and Deserialize Conversations <howto_serialize_conversations>
   Build a New WayFlow Component <howto_plugins>
   Enable Tracing <howto_tracing>
   Use the Event System <howto_event_system>


Data in Assistants
------------------

.. toctree::
   :maxdepth: 1

   Connect Assistants to Your Data <howto_datastores>
   Use Embedding Models from Different Providers <embeddingmodels_from_different_providers>
   Use Variables for Shared State in Flows <howto_variable>
   Synthesize Data in WayFlow <howto_data_synthesis>
   Build RAG-Powered Assistants <howto_rag>


Assistant Testing and Evaluation
--------------------------------

.. toctree::
   :maxdepth: 1

   Evaluate Assistants <howto_evaluation>
   Evaluate Conversations <howto_conversation_evaluation>
