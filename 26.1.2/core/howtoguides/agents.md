# How to Configure Agents Instructions

#### Prerequisites
This guide assumes familiarity with [Agents](../tutorials/basic_agent.md).

Agents can be configured to tackle many scenarios.
Proper configuration of their instructions is essential.

In this how to guide, we will learn how to:

- Configure the instructions of an [Agent](../api/agent.md#agent).
- Set up instructions that vary with each `Conversation`.
- Maintain instructions that are consistently updated and refreshed.

WayFlow supports several LLM API providers.
Select an LLM from the options below:




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

## Basic implementation

Assuming you need an agent to assist a user in writing articles, use the implementation below for that purpose:

```python
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, but keep it short""",
    initial_message=None,
)
```

Then execute it:

```python
conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Welcome to our article writing guide. How can I assist you today?
```

Sometimes, there is contextual information relevant to the conversation.
Assume a user is interacting with the assistant named “Jerry.”
To make the assistant more context-aware, define a variable or expression in the `custom_instruction` Jinja template, and pass it when creating the conversation:

#### NOTE
Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja’s rendering capabilities.
Please check our guide on [How to write secure prompts with Jinja templating](howto_promptexecutionstep.md#securejinjatemplating) for more information.

```python
agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, their name is {{user_name}}, but keep it short""",
    initial_message=None,
)

conversation = agent.start_conversation(inputs={"user_name": "Jerry"})
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Hello Jerry, I'm here to help with any article writing-related questions you may have. Go ahead and ask away!
```

#### NOTE
It is useful to use the same [Agent](../api/agent.md#agent), but change some part of the `custom_instruction` for each different conversation.

Finally, incorporating dynamic context into the agent’s instructions can significantly improve its responsiveness.
For example, the instructions can contain the current time making the agent more aware of the situation.
The time value is constantly changing, so you need to make sure it is always up-to-date.
To do this, use the `ContextProvider`:

```python
from datetime import datetime

from wayflowcore.contextproviders import ToolContextProvider
from wayflowcore.tools import tool

@tool
def get_current_time() -> str:
    """Tool that gets the current time"""
    return datetime.now().strftime("%d, %B %Y, %I:%M %p")

time_provider = ToolContextProvider(tool=get_current_time, output_name="current_time")

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
It's currently {{current_time}}.""",
    initial_message=None,
    context_providers=[time_provider],
)

conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# I'm here to assist you with any article writing-related questions or concerns. What do you need help with today?
```

You successfully customized the prompt of your agent.

## Recap

In this guide, you learned how to configure [Agent](../api/agent.md#agent) instructions with:

- pure text instructions;
- specific variables for each `Conversation`;
- instructions with variables that needs to be always updated.

<details>
<summary>Details</summary>

```python
from wayflowcore.models import LlmModelFactory

llm = LlmModelFactory.from_config(model_config)
```

```python
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, but keep it short""",
    initial_message=None,
)
```

```python
conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Welcome to our article writing guide. How can I assist you today?
```

```python
agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, their name is {{user_name}}, but keep it short""",
    initial_message=None,
)

conversation = agent.start_conversation(inputs={"user_name": "Jerry"})
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Hello Jerry, I'm here to help with any article writing-related questions you may have. Go ahead and ask away!
```

```python
from datetime import datetime

from wayflowcore.contextproviders import ToolContextProvider
from wayflowcore.tools import tool

@tool
def get_current_time() -> str:
    """Tool that gets the current time"""
    return datetime.now().strftime("%d, %B %Y, %I:%M %p")

time_provider = ToolContextProvider(tool=get_current_time, output_name="current_time")

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
It's currently {{current_time}}.""",
    initial_message=None,
    context_providers=[time_provider],
)

conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# I'm here to assist you with any article writing-related questions or concerns. What do you need help with today?
```

</details>

## Next steps

Having learned how to configure agent instructions, you may now proceed to:

- [How to Build Assistants with Tools](howto_build_assistants_with_tools.md)
- [How to Use Agents in Flows](howto_agents_in_flows.md)
