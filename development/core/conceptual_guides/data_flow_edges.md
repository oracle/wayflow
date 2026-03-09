<a id="conceptual-dataflowedges"></a>

# Data Flow Edges: What are they, when are they needed?![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Data Flow Edges how-to script](../end_to_end_code_examples/conceptual_dataflowedges.py)

WayFlow enables the creation of different types of AI assistants including [Flows](../api/flows.md#flow),
which are great to use when you want to solve complex tasks with an orchestrated sequence of operations.

Building a Flow requires you to define a few different components, including the steps that make up the Flow,
the [Control Flow edges](../api/flows.md#controlflowedge) between those steps (i.e., in which order should the steps be executed),
and finally the [Data Flow Edges](../api/flows.md#dataflowedge) that define how data moves through the Flow.

## Basics of Data Flow Edges

Data Flow Edges have one main purpose: defining how data outputs from one step are passed as inputs to another step.

In some simple Flows, WayFlow can automatically infer how data should flow between steps.
However, in more complex scenarios, you may need to explicitly define Data Flow Edges to ensure that data is routed correctly.

Here is a simple illustration to explain this concept:

![How Data Flow Edges work, when they are needed](core/_static/conceptual/dataflowedges_basics.jpg)

We have three examples:

1. In the first Flow (at the top), the output from Step 1 is named the same way as the input of the Step 2 (A).
   Therefore, WayFlow can automatically infer that the output from Step 1 should be passed as input to Step 2.
2. In the second Flow (in the middle), Step 2’s input is named differently (B) than Step 1’s output (A).
   In this case, WayFlow cannot infer how data should flow between the two steps, and you need to explicitly
   define a Data Flow Edge to connect output A from Step 1 to input B of Step 2.
3. In the third Flow (at the bottom), both Step 1 and Step 2 expose an output named (A). WayFlow cannot infer
   which output should be passed to Step 3. Therefore, you need to define two Data Flow Edges: one connecting
   output A from Step 1 to Step 3, and another connecting output A from Step 2 to Step 3.

## Data Flow Edges in Practice

Now let’s see more concrete examples of how you can use Data Flow Edges in your Flows.

### Example 1: Data routing with multiple outputs![Data Flow Edges for a Flow with data routing](core/_static/conceptual/dataflowedges_routing.jpg)

In this first example, Step 1 produces an output that needs to be sent to two different steps: Step 2 and Step 3.

* When the name of the value is different between the steps (e.g., “A” and “B”), WayFlow cannot automatically
  infer the data routing, and you need to define Data Flow Edges explicitly.
* When the name of the value is shared between the steps (e.g. “A” in the middle Flow), WayFlow can automatically
  infer the data routing without the need to define Data Flow Edges.

#### TIP
To improve the readability of your Flow definitions, it is recommended to always define Data Flow Edges explicitly,
even when WayFlow can infer them automatically.

Code with automatic data routing

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge

# Flow with one step output used by two subsequent steps
producer = OutputMessageStep(name="Step 1", message_template="value", output_mapping={OutputMessageStep.OUTPUT: "A"})
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
)
```

Code with explicit data routing

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

producer = OutputMessageStep(name="Step 1", message_template="value")
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer1, destination_input="A"),
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer2, destination_input="A"),
    ],
)
```

### Example 2: Looping Flows![Data Flow Edges for Looping Flows](core/_static/conceptual/dataflowedges_looping.jpg)

In this second example, we have a Flow that includes a loop.

Similar to the previous example:

* When the names of the values differ between the steps (example flow at the top), WayFlow cannot automatically
  infer the data routing, and you need to define Data Flow Edges explicitly.
* When the names of the values are shared between the steps (middle example), WayFlow can automatically
  infer the data routing without the need to define Data Flow Edges.

When creating looping Flows, it is generally recommended to define Data Flow Edges explicitly to avoid confusion.

Code with automatic data routing

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep, BranchingStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{A}}",
    output_mapping={OutputMessageStep.OUTPUT: "B"},
    input_descriptors=[StringProperty(name="A", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    input_mapping={BranchingStep.NEXT_BRANCH_NAME: "B"},
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(
    name="Step 2",
    output_mapping={OutputMessageStep.OUTPUT: "A"},
    message_template="extra",
)

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
)
```

Code with explicit data routing

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{optional_value}}",
    input_descriptors=[StringProperty(name="optional_value", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(name="Step 3", message_template="extra")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=condition, destination_input=BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(add_extra, source_output=OutputMessageStep.OUTPUT, destination_step=producer, destination_input="optional_value"),
    ],
)
```

#### HINT
You may have noticed that in the code for this looping flow, the input property **A** of **Step 1** has a default value.
This is required because in the first loop iteration, the flow has yet to produce a value for **A**. Later in the execution
of the flow, the **Step 2** produces a value for **A** which is then consumed by the **Step 1**.

## Next steps

Having learned about Data Flow Edges, you may now proceed to:

- [How to use Agents inside Flows](../howtoguides/howto_agents_in_flows.md)

## Full code

Click on the card at the [top of this page](#conceptual-dataflowedges) to download the
full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - Data Flow Edges in Flows
# ---------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.2.0.dev0" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python conceptual_dataflowedges.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


# %%[markdown]
## Flow with multi output routing

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge

# Flow with one step output used by two subsequent steps
producer = OutputMessageStep(name="Step 1", message_template="value", output_mapping={OutputMessageStep.OUTPUT: "A"})
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
)
conv = flow.start_conversation()
_ = conv.execute()

# %%[markdown]
## Flow with multi output routing with explicit edges

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

producer = OutputMessageStep(name="Step 1", message_template="value")
consumer1 = OutputMessageStep(name="Step 2", message_template="{{A}}")
consumer2 = OutputMessageStep(name="Step 3", message_template="{{A}}")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, consumer1),
        ControlFlowEdge(consumer1, consumer2),
        ControlFlowEdge(consumer2, None)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer1, destination_input="A"),
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=consumer2, destination_input="A"),
    ],
)
conv = flow.start_conversation()
_ = conv.execute()

# %%[markdown]
## Flow with looping

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep, BranchingStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.property import StringProperty

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{A}}",
    output_mapping={OutputMessageStep.OUTPUT: "B"},
    input_descriptors=[StringProperty(name="A", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    input_mapping={BranchingStep.NEXT_BRANCH_NAME: "B"},
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(
    name="Step 2",
    output_mapping={OutputMessageStep.OUTPUT: "A"},
    message_template="extra",
)

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
)
conv = flow.start_conversation()
_ = conv.execute()

# %%[markdown]
## Flow with looping with explicit edges

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# Looping flow
producer = OutputMessageStep(
    name="Step 1",
    message_template="value{{optional_value}}",
    input_descriptors=[StringProperty(name="optional_value", default_value="")],
    # ^ note that in this looping flow the default_value is required,
    # read the conceptual guide for more information
)
condition = BranchingStep(
    name="Branching",
    branch_name_mapping={"value": "branch1", "valueextra": "branch2"},
)
add_extra = OutputMessageStep(name="Step 3", message_template="extra")

flow = Flow(
    begin_step=producer,
    control_flow_edges=[
        ControlFlowEdge(producer, condition),
        ControlFlowEdge(condition, add_extra, source_branch="branch1"),
        ControlFlowEdge(condition, None, source_branch="branch2"),
        ControlFlowEdge(condition, None, source_branch=BranchingStep.BRANCH_DEFAULT),
        ControlFlowEdge(add_extra, producer)
    ],
    data_flow_edges=[
        DataFlowEdge(producer, source_output=OutputMessageStep.OUTPUT, destination_step=condition, destination_input=BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(add_extra, source_output=OutputMessageStep.OUTPUT, destination_step=producer, destination_input="optional_value"),
    ],
)
conv = flow.start_conversation()
_ = conv.execute()
```
