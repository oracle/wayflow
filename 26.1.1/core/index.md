# WayFlow

*Robust AI-powered assistants for task automation and enhanced user experiences.*

**WayFlow** is a powerful, intuitive Python library for building advanced AI-powered assistants.
It offers a standard library of modular building blocks to streamline the creation of both
workflow-based and agent-style assistants, encourages reusability and speeds up the development process.

With WayFlow you can build both structured [Flows](api/flows.md#flow) and autonomous [Agents](api/agent.md#agent), giving you complete
flexibility and allowing you to choose the paradigm that best fits your use case.

### Why WayFlow?

WayFlow has several advantages over other existing open-source frameworks:

* **Flexibility**: WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.
* **Interoperability**: WayFlow works with LLMs from many different vendors and supports an open approach to integration.
* **Reusability**: Build reusable and composable components to enable rapid development of AI Assistants.
* **Extensibility**: WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.
* **Openness**: We want to build a community and welcome contributions from diverse teams looking to take the next step in open-source AI Agents.

### Quick start

To install WayFlow from PyPI:

To install `wayflowcore` (on Python 3.10), use the following command to install it from PyPI:

```bash
pip install "wayflowcore==26.1.1"
```

For full details on installation including what Python versions and platforms are supported please see our [installation guide](installation.md).

With WayFlow installed, you can now try it out.

WayFlow supports several LLM API providers. First choose an LLM from one of the options below:




OCI GenAI

```python
from wayflowcore.models import OCIGenAIModel, OCIClientConfigWithApiKey

llm = OCIGenAIModel(
    model_id="provider.model-id",
    compartment_id="compartment-id",
    client_config=OCIClientConfigWithApiKey(
        service_endpoint="https://url-to-service-endpoint.com",
    ),
)
```

vLLM

```python
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port="VLLM_HOST_PORT",
)
```

Ollama

```python
from wayflowcore.models import OllamaModel

llm = OllamaModel(
    model_id="model-id",
)
```

Then create an agent and have a conversation with it, as shown in the code below:

```python
from wayflowcore.agent import Agent

assistant = Agent(llm=llm)

conversation = assistant.start_conversation()
conversation.append_user_message("I need help regarding my sql query")
conversation.execute()

# get the assistant's response to your query
assistant_answer = conversation.get_last_message().content
# I'd be happy to help with your SQL query...

print(assistant_answer)
```

#### TIP
**Self Hosted Models**: If you are interested in using locally hosted models, please see our guide on using them with WayFlow, [How to install Ollama](howtoguides/installing_ollama.md).

### Next Steps

1. **Familiarize yourself with the basics - Tutorials**
   * Start with the [Tutorial building a simple conversational assistant with Agents](tutorials/basic_agent.md).
   * Step through the [Tutorial building a simple conversational assistant with Flows](tutorials/basic_flow.md).
   * And then do the [Tutorial building a simple code review assistant](tutorials/usecase_prbot.md).
2. **Ways to use WayFlow to solve common tasks - How-to Guides**

   The [how-to guides](howtoguides/index.md) show you how to achieve common tasks and use-cases using WayFlow.
   They cover topics such as:
   * [How to create conditional transitions in Flows](howtoguides/conditional_flows.md).
   * [How to build assistants with Tools](howtoguides/howto_build_assistants_with_tools.md).
   * [How to catch exceptions in flows](howtoguides/catching_exceptions.md).
   * [How to use Agents in Flows](howtoguides/howto_agents_in_flows.md).
   * [How to connect assistants to data](howtoguides/howto_datastores.md).
3. **Explore the API documentation**

   Dive deeper into the [API documentation](api/index.md) to learn about the various classes, methods, and functions available in the
   library.

### Dive Deeper

### Security

LLM-based assistants and LLM-based flows require careful security assessments before deployment.
Please see our [Security considerations page](security.md) to learn more.

### Frequently Asked Questions

Look through our [Frequently Asked Questions](faqs.md).
