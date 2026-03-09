<a id="top-howiodescriptors"></a>

# How to Change Input and Output Descriptors of Components![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[IO descriptors how-to script](../end_to_end_code_examples/howto_io_descriptors.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

WayFlow components such as [Agents](../api/agent.md#agent), [Flows](../api/flows.md#flow), and [Steps](../api/flows.md#assistantstep) accept inputs and produce outputs.
These inputs and outputs allow you to pass values to be used, and return some new values.
You can inspect the input/output descriptors on classes that inherit from `ComponentWithInputsOutputs` by accessing the `input_descriptors` and `output_descriptors` attributes, respectively.
See the [Property](../api/flows.md#property) API documentation to learn more about the IO typing system operations.

Sometimes, it is helpful to change their description, either because the type is not specific enough, or if you want
to specify a default value.

This guide will show you how to **override the default input and output descriptions of Agents, Flows, or Steps**.

## Basic implementation

When creating a step, input and output descriptors are automatically detected based on the step’s configuration.

```python
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:"
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description=""service" input variable for the template")
print("Output descriptors: ", *step.output_descriptors)
# Output descriptors:  StringProperty(name="user_provided_input", description="the input value provided by the user")
```

In this case, the input descriptor `service` does not have a default value, and the description is not very informative.
To improve the user experience, you can provide a more informative description and set a default value by overriding the input descriptors:

```python
from wayflowcore.property import StringProperty
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:",
    input_descriptors=[
        StringProperty(
            name="service",
            description="service to which the user wants to connect to",
            default_value="OCI",
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description="service to which the user wants to connect to", default_value="OCI")
```

#### NOTE
Since a step requires specific variables to work well, the overriding descriptor must have the same `name` as the original descriptor.

The same process can be applied to output descriptors.

## Refining a type

In certain situations, the automatic detection of input and output types may not determine the appropriate type for a variable.
For example, consider the following step where an `AnyProperty` input is detected:

```python
step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  AnyProperty(name="snacks", description=""snacks" input variable for the template")
```

Here, the service input is expected to be a list.
To improve clarity, you can override the `AnyProperty` descriptor to specify the expected type:

```python
from wayflowcore.property import ListProperty

step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
    input_descriptors=[
        ListProperty(
            name="snacks",
            description="list of snacks",
            item_type=StringProperty(),
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  ListProperty(name="snacks", item=StringProperty(), description="list of snacks")
```

#### NOTE
Currently, type validation is not implemented. When overriding a descriptor’s type, make sure to specify the correct type to prevent runtime crashes during step execution.

## Changing the name of a descriptor

Sometimes, the default name of an input or output descriptor can be complex or unclear.

In this case, you can not just modify the names of the `input_descriptors` or `output_descriptors`, as these names are integral to mapping between new and default descriptors.

You can still rename the input or output descriptor of a `Step` by using `input_mapping` or `output_mapping`.
These mappings associate the default descriptor names (keys) with the desired new names (values).
The associated `input_descriptors` and `output_descriptors` need to reflect these new names accordingly.

```python
step = InputMessageStep(
    message_template="Hi {{unclear_var_name}}. How are you doing?",
    input_descriptors=[StringProperty(name="username")],
    input_mapping={"unclear_var_name": "username"},
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="username")
```

Without providing the `input_mapping` value, the step will not recognize the input descriptor name and will raise an error.

```python
step = InputMessageStep(
    message_template="Hi {{unclear_var_name}}. How are you doing?",
    input_descriptors=[StringProperty(name="username", description="name of the current user")],
)
# ValueError: Unknown input descriptor specified: StringProperty(name='username', description='name of the current user'). Make sure there is no misspelling.
# Expected input descriptors are: [StringProperty(name='unclear_var_name', description='"unclear_var_name" input variable for the template')]
```

## Agent Spec Exporting/Loading

You can export the step configuration to its Agent Spec configuration using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(step)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "PluginInputMessageNode",
  "id": "c7f3b49e-0db5-45b6-9a18-42c565230dc9",
  "name": "step_7137de34",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "type": "string",
      "title": "username"
    }
  ],
  "outputs": [
    {
      "description": "the input value provided by the user",
      "type": "string",
      "title": "user_provided_input"
    }
  ],
  "branches": [
    "next"
  ],
  "input_mapping": {
    "unclear_var_name": "username"
  },
  "output_mapping": {},
  "message_template": "Hi {{unclear_var_name}}. How are you doing?",
  "rephrase": false,
  "llm_config": null,
  "component_plugin_name": "NodesPlugin",
  "component_plugin_version": "25.4.0.dev0",
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: PluginInputMessageNode
id: c7f3b49e-0db5-45b6-9a18-42c565230dc9
name: step_7137de34
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: string
  title: username
outputs:
- description: the input value provided by the user
  type: string
  title: user_provided_input
branches:
- next
input_mapping:
  unclear_var_name: username
output_mapping: {}
message_template: Hi {{unclear_var_name}}. How are you doing?
rephrase: false
llm_config: null
component_plugin_name: NodesPlugin
component_plugin_version: 25.4.0.dev0
agentspec_version: 25.4.1
```

</details>

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

new_step = AgentSpecLoader().load_json(config)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginInputMessageNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

Having learned how to override the default input and output descriptions of a component, you may now proceed to:

- [How to Do Structured LLM Generation in Flows](howto_promptexecutionstep.md)
- [How to Use Agents in Flows](howto_agents_in_flows.md)

## Full code

Click on the card at the [top of this page](#top-howiodescriptors) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to change input and output descriptors of Components
# -------------------------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_io_descriptors.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Auto IO detection

# %%
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:"
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description=""service" input variable for the template")
print("Output descriptors: ", *step.output_descriptors)
# Output descriptors:  StringProperty(name="user_provided_input", description="the input value provided by the user")

# %%[markdown]
## Specify input descriptor:

# %%
from wayflowcore.property import StringProperty
from wayflowcore.steps import InputMessageStep

step = InputMessageStep(
    message_template="You're trying to connect to {{service}}. Please enter your username:",
    input_descriptors=[
        StringProperty(
            name="service",
            description="service to which the user wants to connect to",
            default_value="OCI",
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="service", description="service to which the user wants to connect to", default_value="OCI")

# %%[markdown]
## Default any descriptor

# %%
step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  AnyProperty(name="snacks", description=""snacks" input variable for the template")

# %%[markdown]
## List descriptor

# %%
from wayflowcore.property import ListProperty

step = InputMessageStep(
    message_template="Here are some snacks: {% for snack in snacks %}{{snack}}{% endfor %}. Which one is your favorite?",
    input_descriptors=[
        ListProperty(
            name="snacks",
            description="list of snacks",
            item_type=StringProperty(),
        )
    ],
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  ListProperty(name="snacks", item=StringProperty(), description="list of snacks")

# %%[markdown]
## Rename a descriptor

# %%
step = InputMessageStep(
    message_template="Hi {{unclear_var_name}}. How are you doing?",
    input_descriptors=[StringProperty(name="username")],
    input_mapping={"unclear_var_name": "username"},
)
print("Input descriptors: ", *step.input_descriptors)
# Input descriptors:  StringProperty(name="username")

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(step)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_step = AgentSpecLoader().load_json(config)

```
