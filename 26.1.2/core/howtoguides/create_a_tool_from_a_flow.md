# How to Create a Tool Using a Flow

#### Prerequisites
This guide assumes familiarity with:

- [Flows](../tutorials/basic_flow.md)
- [Agents](../tutorials/basic_agent.md)
- [Tools](../api/tools.md)
- [Building Assistants with Tools](howto_build_assistants_with_tools.md)

Equipping assistants with [Tools](../api/tools.md) enhances their capabilities.
In WayFlow, tools can be defined in various ways.
One approach is to define a flow as the basis for the tool.
In this guide, you will see a basic example of how a flow is used to define a tool.

## Defining the tool

In this guide, you will use an LLM.

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

Now define a flow and pass additional information to describe the tool, including a name, description, and the output choice.

```python
import os

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep
from wayflowcore.tools.servertools import ServerTool

model_config = {
    "model_type": "vllm",
    "host_port": os.environ["MY_LLM_HOST_PORT"],
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}
llm = LlmModelFactory.from_config(model_config)

start_step = StartStep(input_descriptors=[StringProperty("topic")])
poem_generation_step = PromptExecutionStep(
    llm=llm, prompt_template="Write a 12 lines poem about the following topic: {{ topic }}"
)
poem_generation_flow = Flow(
    begin_step=start_step,
    steps={"start_step": start_step, "poem_generation_step": poem_generation_step},
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=poem_generation_step),
        ControlFlowEdge(source_step=poem_generation_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(start_step, "topic", poem_generation_step, "topic")],
)

poem_generation_tool = ServerTool.from_flow(
    flow=poem_generation_flow,
    flow_name="generate_poem",
    flow_description="A simple flow to generate a 12 lines poem based on a topic.",
    # The below line is needed to specify which output of the flow should be used as the output of
    # the tool
    flow_output=PromptExecutionStep.OUTPUT,
)

```

#### NOTE
The above example also works with more complex flows. However, only flows that do not yield are supported — meaning the flow must run to completion without pausing to request additional input from the user.

#### TIP
You can now use this tool like any other server tool, and pass it either to an [Agent](../api/agent.md#agent) or to a [ToolExecutionStep](../api/flows.md#toolexecutionstep).

## Recap

In this guide, you learned how to create server tools from `Flows` by using the `ServerTool.from_flow` method.

<details>
<summary>Details</summary>

```python
import os

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.property import StringProperty
from wayflowcore.steps import PromptExecutionStep, StartStep
from wayflowcore.tools.servertools import ServerTool

model_config = {
    "model_type": "vllm",
    "host_port": os.environ["MY_LLM_HOST_PORT"],
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}
llm = LlmModelFactory.from_config(model_config)

start_step = StartStep(input_descriptors=[StringProperty("topic")])
poem_generation_step = PromptExecutionStep(
    llm=llm, prompt_template="Write a 12 lines poem about the following topic: {{ topic }}"
)
poem_generation_flow = Flow(
    begin_step=start_step,
    steps={"start_step": start_step, "poem_generation_step": poem_generation_step},
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=poem_generation_step),
        ControlFlowEdge(source_step=poem_generation_step, destination_step=None),
    ],
    data_flow_edges=[DataFlowEdge(start_step, "topic", poem_generation_step, "topic")],
)

poem_generation_tool = ServerTool.from_flow(
    flow=poem_generation_flow,
    flow_name="generate_poem",
    flow_description="A simple flow to generate a 12 lines poem based on a topic.",
    # The below line is needed to specify which output of the flow should be used as the output of
    # the tool
    flow_output=PromptExecutionStep.OUTPUT,
)

```

</details>

## Next steps

Having learned how to use tools in WayFlow, you may now proceed to [How to Build Assistants with Tools](howto_build_assistants_with_tools.md).
