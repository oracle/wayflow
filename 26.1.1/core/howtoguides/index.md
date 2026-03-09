<a id="how-to-guides"></a>

# How-to Guides

Within this section, you will find answers to “How do I…” types of questions.
The proposed guides are goal-oriented and concrete, as they are meant to help you complete a specific task.
Each code example in these how-to guides is self-contained and can be executed with [WayFlow](../index.md).

For comprehensive, end-to-end walkthroughs, refer to the [Tutorials](../tutorials/index.md).
For detailed descriptions of every class and function, see the [API Reference](../api/index.md).

## Building Assistants

WayFlow offers a wide range of features for building [Agents](../api/agent.md#agent), [Flows](../api/flows.md#flow) as well
as multi-agent patterns such as [hierarchical multi-agent](howto_multiagent.md) and [Swarm](../api/agent.md#swarm).
These how-to guides demonstrate how to use the main features to create and customize your assistants.

* [Change Input and Output Descriptors of Components](io_descriptors.md)
* [Use Asynchronous APIs](howto_async.md)

## LLMs
* [Install and Use Ollama](installing_ollama.md)
* [Specify the Generation Configuration when Using LLMs](generation_config.md)
* [Use LLM from Different LLM Sources and Providers](llm_from_different_providers.md)
* [Handle long context with agents](howto_long_context.md)

## Agents
* [Create a ReAct Agent](agents.md)
* [How to Send Images to LLMs and Agents](howto_imagecontent.md)
* [Use OCI Generative AI Agents](howto_ociagent.md)
* [How to Connect to A2A Agents](howto_a2aagent.md)
* [Use Templates for Advanced Prompting Techniques](howto_prompttemplate.md)

## Flows
* [Ask for User Input in Flows](howto_userinputinflows.md)
* [Create Conditional Transitions in Flows](conditional_flows.md)
* [Do Structured LLM Generation in Flows](howto_promptexecutionstep.md)
* [Add User Confirmation to a Tool Call Request](howto_userconfirmation.md)
* [Catch Exceptions in Flows](catching_exceptions.md)
* [Do Map and Reduce Operations in Flows](howto_mapstep.md)
* [Run Multiple Flows in Parallel](howto_parallelflowexecution.md)
* [Build Flows with the Flow Builder](howto_flowbuilder.md)

## Multi-Agent Patterns
* [Use Agents in Flows](howto_agents_in_flows.md)
* [Build a Hierarchical Multi-Agent System](howto_multiagent.md)
* [Build a Swarm of Agents](howto_swarm.md)
* [Build a ManagerWorkers of Agents](howto_managerworkers.md)

## Deployment
* [Serve Agents with WayFlow](howto_serve_agents.md)
* [Serve Assistants with A2A protocol](howto_a2a_serving.md)

## Tools in Assistants

Equipping AI assistants with tools unlock key capabilities such as being able to fetch data,
take action, and connect to external data and systems. These guides cover how to leverage the
several tools features available in WayFlow, such as [server-side tools](../api/tools.md#servertool),
[client-side tools](../api/tools.md#clienttool), tools to perform [remote API calls](../api/tools.md#remotetool),
and support for [Model Context Protocol (MCP) tools](../api/tools.md#mcptool).

* [Build Assistants with Tools](howto_build_assistants_with_tools.md)
* [Create Tools with Multiple Outputs](howto_multiple_output_tool.md)
* [Convert Flows to Tools](create_a_tool_from_a_flow.md)
* [Connect MCP tools to Assistants](howto_mcp.md)
* [Enable Tool Output Streaming](howto_tooloutputstreaming.md)
* [Do Remote API Calls with Tokens](howto_remote_tool_expired_token.md)

## Configuration and State Management

These guides demonstrate how to configure the components of assistants built with WayFlow.

* [Load and Execute an Agent Spec Configuration](howto_execute_agentspec_with_wayflowcore.md)
* [Serialize and Deserialize Flows and Agents](howto_serdeser.md)
* [Serialize and Deserialize Conversations](howto_serialize_conversations.md)
* [Build a New WayFlow Component](howto_plugins.md)
* [Enable Tracing](howto_tracing.md)
* [Use the Event System](howto_event_system.md)

## Data in Assistants

* [Connect Assistants to Your Data](howto_datastores.md)
* [Use Embedding Models from Different Providers](embeddingmodels_from_different_providers.md)
* [Use Variables for Shared State in Flows](howto_variable.md)
* [Synthesize Data in WayFlow](howto_data_synthesis.md)

## Assistant Testing and Evaluation

* [Evaluate Assistants](howto_evaluation.md)
* [Evaluate Conversations](howto_conversation_evaluation.md)
