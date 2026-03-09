<a id="landing-page"></a>

# WayFlow

**Build robust AI-powered assistants for task automation and enhanced user experiences**

WayFlow is a powerful, intuitive Python library for building advanced AI-powered assistants.
It offers a standard library of modular building blocks to streamline the creation of both
workflow-based and agent-style assistants, encourages reusability and speeds up the development process.

WayFlow is a reference runtime implementation for [Agent Spec](https://github.com/oracle/agent-spec/), with native support for all Agent Spec Agents and Flows.

[Get Started](core/installation.md)
[Documentation](core/index.md)

### Why WayFlow?

![Flexibility](_static/img/flexibility.svg)

**Flexibility**
WayFlow supports multiple approaches to building AI Assistants, including Agents and Flows.

![Interoperability](_static/img/interoperability.svg)

**Interoperability**
WayFlow works with LLMs from many different vendors and supports an open approach to integration.

![Reusability](_static/img/reusability.svg)

**Reusability**
WayFlow enables you to build reusable and composable components for rapid development of AI assistants.

![Extensibility](_static/img/extensibility.svg)

**Extensibility**
WayFlow has powerful abstractions to handle all types of LLM applications and provides a standard library of steps.

![Openness](_static/img/opennes.svg)

**Openness**
WayFlow is an open-source project, welcoming contributions from diverse teams looking to take AI agents to the next step.

### Quick Start

To install WayFlow on Python 3.10, use the following command to install it from the package index:

```bash
pip install "wayflowcore==26.1.1"
```

For complete installation instructions, including supported Python versions and platforms, see the [installation guide](core/installation.md).

With WayFlow installed, you can now try it out.

WayFlow supports several LLM API providers. Select an LLM from the options below:




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

Then create an agent and start a conversation, as shown in the example below:

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
**Self-Hosted Models**: To use locally hosted models, see the guide on integrating them with WayFlow [Installing Ollama](core/howtoguides/installing_ollama.md).

### What’s Next?

<a href="core/tutorials/index.html" class="benefit-card-link">![How-to Guides](_static/img/tutorials.svg)

**Tutorials**

A series of tutorials that introduces key WayFlow concepts through practical, example-driven learning.

</a><a href="core/howtoguides/index.html" class="benefit-card-link">![How-to Guides](_static/img/examples.svg)

**How-to Guides**

Goal-oriented guides with self-contained code examples to help you complete specific tasks.

</a><a href="core/api/index.html" class="benefit-card-link">![Explore the API docs](_static/img/exploring.svg)

**API Documentation**

Dive deeper into the API documentation to explore the classes, methods, and functions available in the library.

</a>
