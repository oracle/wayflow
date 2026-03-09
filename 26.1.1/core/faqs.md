# Frequently Asked Questions

**What types of assistants can I create using WayFlow?**

> You can create two main types of assistants: [Agents](api/agent.md#agent) and [Flows](api/flows.md#flow). Agents are conversational assistants that can
> perform tasks and ask follow-up questions, while Flows are workflow-based assistants that can be represented as a flow of steps.

**What is the main difference between Agents and Flows?**

> Agents are more autonomous but less reliable and harder to run in production, while Flows are more predictable and easier to debug.

**How do I serialize or deserialize my assistant?**

> You can use the APIs provided by WayFlow to export/load your assistants to/from Agent Spec. You can use a few lines of code to export
> your assistant and load it in WayFlow using a JSON file. See the [API reference](api/agentspec.md) for more information.

**What common steps are available to build Flows in WayFlow?**

> The central step in WayFlow is the [prompt execution step](api/flows.md#promptexecutionstep), which allows you to generate prompts with an LLM.
> Other steps include [regex extraction](api/flows.md#regexextractionstep), [extract from JSON](api/flows.md#extractvaluefromjsonstep),
> [branching](api/flows.md#branchingstep), [user input](api/flows.md#inputmessagestep), [output](api/flows.md#outputmessagestep),
> [flow execution](api/flows.md#flowexecutionstep), [MapStep](api/flows.md#mapstep), [ApiCallStep](api/flows.md#apicallstep), and others.

**What models are available?**

> All WayFlow LLM models have the same API, but they are powered by different models underneath. WayFlow currently supports
> [Self-hosted models](api/llmmodels.md#vllmmodel), [OCI GenAI models](api/llmmodels.md#ocigenaimodel), and [3rd party models](api/llmmodels.md#openaimodel). See the [API reference](api/llmmodels.md#id1) for
> more information.

**How do I interact with data?**

> You can use the `Datastore` abstraction to interact with data structures.
> See the [API reference](api/datastores.md#datastores) for more information.

**Why should I implement my assistant as a config file rather than custom code?**

> To avoid custom steps as much as possible, as they are difficult to test and make it harder to understand the logic of the application.
> Instead, you can use the base classes provided by WayFlow to create your assistant.
