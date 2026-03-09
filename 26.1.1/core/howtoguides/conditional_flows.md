<a id="top-howtoconditionaltransitions"></a>

# How to Create Conditional Transitions in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Conditional Transitions in Flows how-to script](../end_to_end_code_examples/howto_branching.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

Software applications utilize branching and conditionals to make decisions and respond dynamically
based on user inputs or data. This capability is essential for adapting to diverse scenarios,
ensuring a seamless and responsive user experience.

WayFlow enables conditional transitions in Flows too. This guide demonstrates how to use
the [BranchingStep](../api/flows.md#branchingstep) to execute different flows based on specific conditions.

![Flow diagram of a simple branching step](core/_static/howto/branchingstep.svg)

WayFlow offers additional APIs for managing conditional transitions, such as
[ChoiceSelectionStep](../api/flows.md#choiceselectionstep), [FlowExecutionStep](../api/flows.md#flowexecutionstep),
and [RetryStep](../api/flows.md#retrystep). For more information, refer to the API documentation.

## Basic implementation

Suppose there is a variable `my_var` that can be equal to `"[SUCCESS]"` or `"[FAILURE]"`.
You want to perform different actions depending on its value. A `BranchingStep` can be used
to map each value to a corresponding branch:

```python
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep

branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)
```

Once this is done, create the flow and map each branch to its corresponding next step. In this
example, the branching step has 2 branches based on the configuration (specified in the
`branch_name_mapping`), and also the default one (`BranchingStep.BRANCH_DEFAULT`).

You can check the branch name of a step using the `step.get_branches()` function.

```python
success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)
```

#### NOTE
Most steps only have a single next step, so you do not need to specify a transition dictionary,
and can just use a list with a single element.

For steps with several branches (such as [BranchingStep](../api/flows.md#branchingstep), [ChoiceSelectionStep](../api/flows.md#choiceselectionstep),
[RetryStep](../api/flows.md#retrystep), and [FlowExecutionStep](../api/flows.md#flowexecutionstep)), you need to mapping each branch name to
the next step using an edge. Creating the flow will inform you if you are missing a branch in
the mapping.

You now have a flow which takes a different transition depending on the value of some variable:

```python
conversation = flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"
```

You now have the possibility to export your Flow as an Agent Spec configuration. The Agent Spec
configuration is a convenient serialized format that can be easily shared and stored. Additionally,
it allows execution in compatible environments.

```python
from wayflowcore.agentspec import AgentSpecExporter
serialized_flow = AgentSpecExporter().to_json(flow)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "Flow",
  "id": "77a036ac-c0bd-4b9b-a83a-d92ed10c439c",
  "name": "flow_fb5f11e1__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "title": "my_var",
      "type": "string"
    }
  ],
  "outputs": [
    {
      "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
      "default": "",
      "title": "output",
      "type": "string"
    },
    {
      "description": "the message added to the messages list",
      "title": "output_message",
      "type": "string"
    }
  ],
  "start_node": {
    "$component_ref": "fbedaf76-4ad6-4685-af53-e92e0f861b80"
  },
  "nodes": [
    {
      "$component_ref": "fbedaf76-4ad6-4685-af53-e92e0f861b80"
    },
    {
      "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
    },
    {
      "$component_ref": "5caca307-4822-4e85-8df5-e8ee7de01203"
    },
    {
      "$component_ref": "f4f49441-ff33-47c0-a46d-012556117992"
    },
    {
      "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "91469c9b-817f-46ea-9917-35e12140ce42",
      "name": "outer_start_step_to_subflow_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "fbedaf76-4ad6-4685-af53-e92e0f861b80"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "ef3dda69-e480-490e-bae8-3da59efea428",
      "name": "subflow_step_to_success_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
      },
      "from_branch": "success_internal_step",
      "to_node": {
        "$component_ref": "5caca307-4822-4e85-8df5-e8ee7de01203"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "fb72a951-7bdf-4b48-87df-828755e31900",
      "name": "subflow_step_to_failure_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
      },
      "from_branch": "failure_internal_step",
      "to_node": {
        "$component_ref": "f4f49441-ff33-47c0-a46d-012556117992"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "009977e8-49b9-4378-8fd5-5a168d24f54e",
      "name": "success_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "5caca307-4822-4e85-8df5-e8ee7de01203"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "ad33df8a-d907-4735-a9e5-9c72782715f0",
      "name": "failure_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "f4f49441-ff33-47c0-a46d-012556117992"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "1fd49451-f772-452d-b82f-0337cbbcc5d0",
      "name": "outer_start_step_my_var_to_subflow_step_my_var_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "fbedaf76-4ad6-4685-af53-e92e0f861b80"
      },
      "source_output": "my_var",
      "destination_node": {
        "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
      },
      "destination_input": "my_var"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "ead87d3d-ef10-439e-86ea-27c03d0aed50",
      "name": "subflow_step_output_to_None End node_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "9f320a77-0c89-4a68-890d-6f15e4951f41"
      },
      "source_output": "output",
      "destination_node": {
        "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
      },
      "destination_input": "output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "96a375d7-8555-453f-a2b7-73a559c5c29f",
      "name": "success_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "5caca307-4822-4e85-8df5-e8ee7de01203"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
      },
      "destination_input": "output_message"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "87cdc413-f1a8-494b-b449-d87e70ba268d",
      "name": "failure_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "f4f49441-ff33-47c0-a46d-012556117992"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "ba398191-3e18-41c0-acef-2940637299cf"
      },
      "destination_input": "output_message"
    }
  ],
  "$referenced_components": {
    "9f320a77-0c89-4a68-890d-6f15e4951f41": {
      "component_type": "FlowNode",
      "id": "9f320a77-0c89-4a68-890d-6f15e4951f41",
      "name": "subflow_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "title": "my_var",
          "type": "string"
        }
      ],
      "outputs": [
        {
          "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
          "default": "",
          "title": "output",
          "type": "string"
        }
      ],
      "branches": [
        "failure_internal_step",
        "success_internal_step"
      ],
      "subflow": {
        "component_type": "Flow",
        "id": "9319f3be-3d97-470f-a74c-946e71831a9e",
        "name": "flow_ad0e97b3__auto",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "title": "my_var",
            "type": "string"
          }
        ],
        "outputs": [
          {
            "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
            "default": "",
            "title": "output",
            "type": "string"
          }
        ],
        "start_node": {
          "$component_ref": "c921ea31-5d7f-4a84-9b9f-21559d3725db"
        },
        "nodes": [
          {
            "$component_ref": "c921ea31-5d7f-4a84-9b9f-21559d3725db"
          },
          {
            "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
          },
          {
            "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
          },
          {
            "$component_ref": "553882d4-a7c3-4ece-934a-86627a760951"
          },
          {
            "$component_ref": "b17890ce-10de-46d9-8ef7-505b25364343"
          }
        ],
        "control_flow_connections": [
          {
            "component_type": "ControlFlowEdge",
            "id": "42d7c2ba-8d8c-4d55-a9fb-73c4c8256526",
            "name": "sub_start_step_to_regex_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "c921ea31-5d7f-4a84-9b9f-21559d3725db"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "97c4c82b-597d-4924-8109-7c26f8275736",
            "name": "regex_step_to_branching_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "4afb7077-3517-4d5e-b443-013e2757ea25",
            "name": "branching_step_to_success_internal_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
            },
            "from_branch": "success",
            "to_node": {
              "$component_ref": "553882d4-a7c3-4ece-934a-86627a760951"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "4c04c350-d2f3-4a56-b9ff-656dc00eacdd",
            "name": "branching_step_to_failure_internal_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
            },
            "from_branch": "failure",
            "to_node": {
              "$component_ref": "b17890ce-10de-46d9-8ef7-505b25364343"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "9dcde3d1-971f-492b-bf6f-ce7150e2acbb",
            "name": "branching_step_to_failure_internal_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
            },
            "from_branch": "default",
            "to_node": {
              "$component_ref": "b17890ce-10de-46d9-8ef7-505b25364343"
            }
          }
        ],
        "data_flow_connections": [
          {
            "component_type": "DataFlowEdge",
            "id": "43de5266-2e5c-4541-829d-0456cb1d1e0d",
            "name": "sub_start_step_my_var_to_regex_step_text_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "c921ea31-5d7f-4a84-9b9f-21559d3725db"
            },
            "source_output": "my_var",
            "destination_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            },
            "destination_input": "text"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "b2508f9c-4ee9-44f4-817c-90b226ddb035",
            "name": "regex_step_output_to_branching_step_next_step_name_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            },
            "source_output": "output",
            "destination_node": {
              "$component_ref": "411335e3-ad41-4549-8372-0f9549d375c9"
            },
            "destination_input": "next_step_name"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "85416132-fa2c-4015-ab85-906af9f26cca",
            "name": "regex_step_output_to_success_internal_step_output_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            },
            "source_output": "output",
            "destination_node": {
              "$component_ref": "553882d4-a7c3-4ece-934a-86627a760951"
            },
            "destination_input": "output"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "681f604a-35c2-4e74-9529-176e070c0b0a",
            "name": "regex_step_output_to_failure_internal_step_output_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e"
            },
            "source_output": "output",
            "destination_node": {
              "$component_ref": "b17890ce-10de-46d9-8ef7-505b25364343"
            },
            "destination_input": "output"
          }
        ],
        "$referenced_components": {
          "cf622bf5-1acd-4d9d-80a5-724d11b2db5e": {
            "component_type": "PluginRegexNode",
            "id": "cf622bf5-1acd-4d9d-80a5-724d11b2db5e",
            "name": "regex_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "raw text to extract information from",
                "title": "text",
                "type": "string"
              }
            ],
            "outputs": [
              {
                "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
                "default": "",
                "title": "output",
                "type": "string"
              }
            ],
            "branches": [
              "next"
            ],
            "input_mapping": {},
            "output_mapping": {},
            "regex_pattern": "(\\[SUCCESS\\]|\\[FAILURE\\])",
            "return_first_match_only": true,
            "component_plugin_name": "NodesPlugin",
            "component_plugin_version": "25.4.0.dev0"
          },
          "c921ea31-5d7f-4a84-9b9f-21559d3725db": {
            "component_type": "StartNode",
            "id": "c921ea31-5d7f-4a84-9b9f-21559d3725db",
            "name": "sub_start_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "title": "my_var",
                "type": "string"
              }
            ],
            "outputs": [
              {
                "title": "my_var",
                "type": "string"
              }
            ],
            "branches": [
              "next"
            ]
          },
          "411335e3-ad41-4549-8372-0f9549d375c9": {
            "component_type": "BranchingNode",
            "id": "411335e3-ad41-4549-8372-0f9549d375c9",
            "name": "branching_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "Next branch name in the flow",
                "default": "default",
                "title": "next_step_name",
                "type": "string"
              }
            ],
            "outputs": [],
            "branches": [
              "default",
              "failure",
              "success"
            ],
            "mapping": {
              "[FAILURE]": "failure",
              "[SUCCESS]": "success"
            }
          },
          "553882d4-a7c3-4ece-934a-86627a760951": {
            "component_type": "EndNode",
            "id": "553882d4-a7c3-4ece-934a-86627a760951",
            "name": "success_internal_step",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
                "default": "",
                "title": "output",
                "type": "string"
              }
            ],
            "outputs": [
              {
                "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
                "default": "",
                "title": "output",
                "type": "string"
              }
            ],
            "branches": [],
            "branch_name": "success_internal_step"
          },
          "b17890ce-10de-46d9-8ef7-505b25364343": {
            "component_type": "EndNode",
            "id": "b17890ce-10de-46d9-8ef7-505b25364343",
            "name": "failure_internal_step",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
                "default": "",
                "title": "output",
                "type": "string"
              }
            ],
            "outputs": [
              {
                "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
                "default": "",
                "title": "output",
                "type": "string"
              }
            ],
            "branches": [],
            "branch_name": "failure_internal_step"
          }
        }
      }
    },
    "fbedaf76-4ad6-4685-af53-e92e0f861b80": {
      "component_type": "StartNode",
      "id": "fbedaf76-4ad6-4685-af53-e92e0f861b80",
      "name": "outer_start_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "title": "my_var",
          "type": "string"
        }
      ],
      "outputs": [
        {
          "title": "my_var",
          "type": "string"
        }
      ],
      "branches": [
        "next"
      ]
    },
    "ba398191-3e18-41c0-acef-2940637299cf": {
      "component_type": "EndNode",
      "id": "ba398191-3e18-41c0-acef-2940637299cf",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
          "default": "",
          "title": "output",
          "type": "string"
        },
        {
          "description": "the message added to the messages list",
          "title": "output_message",
          "type": "string"
        }
      ],
      "outputs": [
        {
          "description": "the first extracted value using the regex \"(\\[SUCCESS\\]|\\[FAILURE\\])\" from the raw input",
          "default": "",
          "title": "output",
          "type": "string"
        },
        {
          "description": "the message added to the messages list",
          "title": "output_message",
          "type": "string"
        }
      ],
      "branches": [],
      "branch_name": "next"
    },
    "5caca307-4822-4e85-8df5-e8ee7de01203": {
      "component_type": "PluginOutputMessageNode",
      "id": "5caca307-4822-4e85-8df5-e8ee7de01203",
      "name": "success_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "description": "the message added to the messages list",
          "title": "output_message",
          "type": "string"
        }
      ],
      "branches": [
        "next"
      ],
      "expose_message_as_output": true,
      "message": "It was a success",
      "input_mapping": {},
      "output_mapping": {},
      "message_type": "AGENT",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "f4f49441-ff33-47c0-a46d-012556117992": {
      "component_type": "PluginOutputMessageNode",
      "id": "f4f49441-ff33-47c0-a46d-012556117992",
      "name": "failure_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "description": "the message added to the messages list",
          "title": "output_message",
          "type": "string"
        }
      ],
      "branches": [
        "next"
      ],
      "expose_message_as_output": true,
      "message": "It was a failure",
      "input_mapping": {},
      "output_mapping": {},
      "message_type": "AGENT",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    }
  },
  "agentspec_version": "25.4.1"
}
```

YAML

```yaml
component_type: Flow
id: 77a036ac-c0bd-4b9b-a83a-d92ed10c439c
name: flow_fb5f11e1__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- title: my_var
  type: string
outputs:
- description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
    from the raw input
  default: ''
  title: output
  type: string
- description: the message added to the messages list
  title: output_message
  type: string
start_node:
  $component_ref: fbedaf76-4ad6-4685-af53-e92e0f861b80
nodes:
- $component_ref: fbedaf76-4ad6-4685-af53-e92e0f861b80
- $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
- $component_ref: 5caca307-4822-4e85-8df5-e8ee7de01203
- $component_ref: f4f49441-ff33-47c0-a46d-012556117992
- $component_ref: ba398191-3e18-41c0-acef-2940637299cf
control_flow_connections:
- component_type: ControlFlowEdge
  id: 91469c9b-817f-46ea-9917-35e12140ce42
  name: outer_start_step_to_subflow_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: fbedaf76-4ad6-4685-af53-e92e0f861b80
  from_branch: null
  to_node:
    $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
- component_type: ControlFlowEdge
  id: ef3dda69-e480-490e-bae8-3da59efea428
  name: subflow_step_to_success_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
  from_branch: success_internal_step
  to_node:
    $component_ref: 5caca307-4822-4e85-8df5-e8ee7de01203
- component_type: ControlFlowEdge
  id: fb72a951-7bdf-4b48-87df-828755e31900
  name: subflow_step_to_failure_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
  from_branch: failure_internal_step
  to_node:
    $component_ref: f4f49441-ff33-47c0-a46d-012556117992
- component_type: ControlFlowEdge
  id: 009977e8-49b9-4378-8fd5-5a168d24f54e
  name: success_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 5caca307-4822-4e85-8df5-e8ee7de01203
  from_branch: null
  to_node:
    $component_ref: ba398191-3e18-41c0-acef-2940637299cf
- component_type: ControlFlowEdge
  id: ad33df8a-d907-4735-a9e5-9c72782715f0
  name: failure_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: f4f49441-ff33-47c0-a46d-012556117992
  from_branch: null
  to_node:
    $component_ref: ba398191-3e18-41c0-acef-2940637299cf
data_flow_connections:
- component_type: DataFlowEdge
  id: 1fd49451-f772-452d-b82f-0337cbbcc5d0
  name: outer_start_step_my_var_to_subflow_step_my_var_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: fbedaf76-4ad6-4685-af53-e92e0f861b80
  source_output: my_var
  destination_node:
    $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
  destination_input: my_var
- component_type: DataFlowEdge
  id: ead87d3d-ef10-439e-86ea-27c03d0aed50
  name: subflow_step_output_to_None End node_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 9f320a77-0c89-4a68-890d-6f15e4951f41
  source_output: output
  destination_node:
    $component_ref: ba398191-3e18-41c0-acef-2940637299cf
  destination_input: output
- component_type: DataFlowEdge
  id: 96a375d7-8555-453f-a2b7-73a559c5c29f
  name: success_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 5caca307-4822-4e85-8df5-e8ee7de01203
  source_output: output_message
  destination_node:
    $component_ref: ba398191-3e18-41c0-acef-2940637299cf
  destination_input: output_message
- component_type: DataFlowEdge
  id: 87cdc413-f1a8-494b-b449-d87e70ba268d
  name: failure_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: f4f49441-ff33-47c0-a46d-012556117992
  source_output: output_message
  destination_node:
    $component_ref: ba398191-3e18-41c0-acef-2940637299cf
  destination_input: output_message
$referenced_components:
  9f320a77-0c89-4a68-890d-6f15e4951f41:
    component_type: FlowNode
    id: 9f320a77-0c89-4a68-890d-6f15e4951f41
    name: subflow_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - title: my_var
      type: string
    outputs:
    - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
        from the raw input
      default: ''
      title: output
      type: string
    branches:
    - failure_internal_step
    - success_internal_step
    subflow:
      component_type: Flow
      id: 9319f3be-3d97-470f-a74c-946e71831a9e
      name: flow_ad0e97b3__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - title: my_var
        type: string
      outputs:
      - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
          from the raw input
        default: ''
        title: output
        type: string
      start_node:
        $component_ref: c921ea31-5d7f-4a84-9b9f-21559d3725db
      nodes:
      - $component_ref: c921ea31-5d7f-4a84-9b9f-21559d3725db
      - $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
      - $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
      - $component_ref: 553882d4-a7c3-4ece-934a-86627a760951
      - $component_ref: b17890ce-10de-46d9-8ef7-505b25364343
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: 42d7c2ba-8d8c-4d55-a9fb-73c4c8256526
        name: sub_start_step_to_regex_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: c921ea31-5d7f-4a84-9b9f-21559d3725db
        from_branch: null
        to_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
      - component_type: ControlFlowEdge
        id: 97c4c82b-597d-4924-8109-7c26f8275736
        name: regex_step_to_branching_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
        from_branch: null
        to_node:
          $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
      - component_type: ControlFlowEdge
        id: 4afb7077-3517-4d5e-b443-013e2757ea25
        name: branching_step_to_success_internal_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
        from_branch: success
        to_node:
          $component_ref: 553882d4-a7c3-4ece-934a-86627a760951
      - component_type: ControlFlowEdge
        id: 4c04c350-d2f3-4a56-b9ff-656dc00eacdd
        name: branching_step_to_failure_internal_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
        from_branch: failure
        to_node:
          $component_ref: b17890ce-10de-46d9-8ef7-505b25364343
      - component_type: ControlFlowEdge
        id: 9dcde3d1-971f-492b-bf6f-ce7150e2acbb
        name: branching_step_to_failure_internal_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
        from_branch: default
        to_node:
          $component_ref: b17890ce-10de-46d9-8ef7-505b25364343
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 43de5266-2e5c-4541-829d-0456cb1d1e0d
        name: sub_start_step_my_var_to_regex_step_text_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: c921ea31-5d7f-4a84-9b9f-21559d3725db
        source_output: my_var
        destination_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
        destination_input: text
      - component_type: DataFlowEdge
        id: b2508f9c-4ee9-44f4-817c-90b226ddb035
        name: regex_step_output_to_branching_step_next_step_name_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
        source_output: output
        destination_node:
          $component_ref: 411335e3-ad41-4549-8372-0f9549d375c9
        destination_input: next_step_name
      - component_type: DataFlowEdge
        id: 85416132-fa2c-4015-ab85-906af9f26cca
        name: regex_step_output_to_success_internal_step_output_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
        source_output: output
        destination_node:
          $component_ref: 553882d4-a7c3-4ece-934a-86627a760951
        destination_input: output
      - component_type: DataFlowEdge
        id: 681f604a-35c2-4e74-9529-176e070c0b0a
        name: regex_step_output_to_failure_internal_step_output_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
        source_output: output
        destination_node:
          $component_ref: b17890ce-10de-46d9-8ef7-505b25364343
        destination_input: output
      $referenced_components:
        cf622bf5-1acd-4d9d-80a5-724d11b2db5e:
          component_type: PluginRegexNode
          id: cf622bf5-1acd-4d9d-80a5-724d11b2db5e
          name: regex_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: raw text to extract information from
            title: text
            type: string
          outputs:
          - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
              from the raw input
            default: ''
            title: output
            type: string
          branches:
          - next
          input_mapping: {}
          output_mapping: {}
          regex_pattern: (\[SUCCESS\]|\[FAILURE\])
          return_first_match_only: true
          component_plugin_name: NodesPlugin
          component_plugin_version: 25.4.0.dev0
        c921ea31-5d7f-4a84-9b9f-21559d3725db:
          component_type: StartNode
          id: c921ea31-5d7f-4a84-9b9f-21559d3725db
          name: sub_start_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - title: my_var
            type: string
          outputs:
          - title: my_var
            type: string
          branches:
          - next
        411335e3-ad41-4549-8372-0f9549d375c9:
          component_type: BranchingNode
          id: 411335e3-ad41-4549-8372-0f9549d375c9
          name: branching_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - description: Next branch name in the flow
            default: default
            title: next_step_name
            type: string
          outputs: []
          branches:
          - default
          - failure
          - success
          mapping:
            '[FAILURE]': failure
            '[SUCCESS]': success
        553882d4-a7c3-4ece-934a-86627a760951:
          component_type: EndNode
          id: 553882d4-a7c3-4ece-934a-86627a760951
          name: success_internal_step
          description: null
          metadata:
            __metadata_info__: {}
          inputs:
          - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
              from the raw input
            default: ''
            title: output
            type: string
          outputs:
          - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
              from the raw input
            default: ''
            title: output
            type: string
          branches: []
          branch_name: success_internal_step
        b17890ce-10de-46d9-8ef7-505b25364343:
          component_type: EndNode
          id: b17890ce-10de-46d9-8ef7-505b25364343
          name: failure_internal_step
          description: null
          metadata:
            __metadata_info__: {}
          inputs:
          - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
              from the raw input
            default: ''
            title: output
            type: string
          outputs:
          - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
              from the raw input
            default: ''
            title: output
            type: string
          branches: []
          branch_name: failure_internal_step
  fbedaf76-4ad6-4685-af53-e92e0f861b80:
    component_type: StartNode
    id: fbedaf76-4ad6-4685-af53-e92e0f861b80
    name: outer_start_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - title: my_var
      type: string
    outputs:
    - title: my_var
      type: string
    branches:
    - next
  ba398191-3e18-41c0-acef-2940637299cf:
    component_type: EndNode
    id: ba398191-3e18-41c0-acef-2940637299cf
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
        from the raw input
      default: ''
      title: output
      type: string
    - description: the message added to the messages list
      title: output_message
      type: string
    outputs:
    - description: the first extracted value using the regex "(\[SUCCESS\]|\[FAILURE\])"
        from the raw input
      default: ''
      title: output
      type: string
    - description: the message added to the messages list
      title: output_message
      type: string
    branches: []
    branch_name: next
  5caca307-4822-4e85-8df5-e8ee7de01203:
    component_type: PluginOutputMessageNode
    id: 5caca307-4822-4e85-8df5-e8ee7de01203
    name: success_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the message added to the messages list
      title: output_message
      type: string
    branches:
    - next
    expose_message_as_output: True
    message: It was a success
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  f4f49441-ff33-47c0-a46d-012556117992:
    component_type: PluginOutputMessageNode
    id: f4f49441-ff33-47c0-a46d-012556117992
    name: failure_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the message added to the messages list
      title: output_message
      type: string
    branches:
    - next
    expose_message_as_output: True
    message: It was a failure
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
agentspec_version: 25.4.1
```

</details>

You can now load back the configuration and execute it in the same manner as before exporting it.

```python
from wayflowcore.agentspec import AgentSpecLoader

new_flow: Flow = AgentSpecLoader().load_json(serialized_flow)

conversation = new_flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = new_flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = new_flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginRegexNode`
- `PluginOutputMessageNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Common patterns and best practices

### Pattern 1: Branching if a token is present in a text

Most of the time, you will use [BranchingStep](../api/flows.md#branchingstep) to branch out depending on whether a token is present
in a text (for example, whether an LLM generated a token `[SUCCESS]` or not).
To do this, pass [RegexExtractionStep](../api/flows.md#regexextractionstep) before the [BranchingStep](../api/flows.md#branchingstep):

```python
import re

from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, OutputMessageStep, RegexExtractionStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)
conversation = flow.start_conversation(
    inputs={"my_var": "The test passed successfully, so it's a [SUCCESS]"},
)
conversation.execute()
# "It was a success"
```

You can apply this pattern for an LLM before producing a decision.
Generating a comprehensive textual review before providing a decision token can reduce hallucinations in LLM outputs.
This approach allows the model to contextualize its decision, leading to more accurate and reliable outcomes.

### Pattern 2: Branching with more advanced expressions

For scenarios requiring branching based on more advanced conditions, consider using
[TemplateRenderingStep](../api/flows.md#templaterenderingstep) (which employs Jinja2) or
[ToolExecutionStep](../api/flows.md#toolexecutionstep) to evaluate conditions on variables.

```python
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep, TemplateRenderingStep
from wayflowcore.property import BooleanProperty

template = "{% if my_var %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for boolean
# template = "{% if my_var > 10 %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for integer
# template = "{% if lower(my_var) == '[success]' %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # with specific expressions

template_step = TemplateRenderingStep(
    name="template_step",
    template=template,
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)
TEMPLATE_STEP = "template_step"
START_STEP = "start_step"

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[BooleanProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=template_step),
        ControlFlowEdge(source_step=template_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", template_step, "my_var"),
        DataFlowEdge(
            template_step, TemplateRenderingStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
        ),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": True})
conversation.execute()
# "It was a success"
```

#### NOTE
Jinja templating introduces security concerns that are addressed by WayFlow by restricting Jinja’s rendering capabilities.
Please check our guide on [How to write secure prompts with Jinja templating](howto_promptexecutionstep.md#securejinjatemplating) for more information.

### Pattern 3: Branching using an LLM

To begin, configure an LLM.

WayFlow supports several LLM API providers. Select an LLM from the options below to
proceed with the configuration.




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

You can implement branching logic determined by the LLM by using
[ChoiceSelectionStep](../api/flows.md#choiceselectionstep). To do so, pass the names and descriptions of the
potential next branches.

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import ChoiceSelectionStep, OutputMessageStep

choice_step = ChoiceSelectionStep(
    name="choice_step",
    llm=llm,
    next_steps=[
        ("success", "in case the test passed successfully"),
        ("failure", "in case the test did not pass"),
    ],
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=choice_step),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", choice_step, ChoiceSelectionStep.INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "TEST IS SUCCESSFUL"})
conversation.execute()
# "It was a success"
```

#### TIP
If needed, override the default template using the `prompt_template` argument.

### Pattern 4: Conditional branching with a sub-flow

To implement branching based on multiple possible outcomes of a sub-flow, wrap it in
[FlowExecutionStep](../api/flows.md#flowexecutionstep). It will expose one branch per one possible end.
Mapping works the same as for [BranchingStep](../api/flows.md#branchingstep):

```python
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, CompleteStep, FlowExecutionStep, OutputMessageStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

sub_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="sub_start_step")
success_internal_step = CompleteStep(name="success_internal_step")
failure_internal_step = CompleteStep(name="failure_internal_step")
subflow = Flow(
    begin_step=sub_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=sub_start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_internal_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
    ],
    data_flow_edges=[
        DataFlowEdge(sub_start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)

subflow_step = FlowExecutionStep(subflow, name="subflow_step")
subflow_step.get_branches()  # ['success_internal_step', 'failure_internal_step']

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
outer_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="outer_start_step")
flow = Flow(
    begin_step=outer_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=outer_start_step, destination_step=subflow_step),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=success_step,
            source_branch="success_internal_step",
        ),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=failure_step,
            source_branch="failure_internal_step",
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(outer_start_step, "my_var", subflow_step, "my_var"),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "Test passed, so [SUCCESS]"})
conversation.execute()
# "It was a success"
```

## Troubleshooting

In case you forget to specify a branch for a step that has several sub-flows, the flow constructor
will inform you about the missing branch names:

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.steps import BranchingStep, OutputMessageStep
from wayflowcore.flow import Flow

branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)
success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
flow = Flow(
    begin_step=branching_step,
    control_flow_edges=[
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        # Missing some control flow edges
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
)

# UserWarning: Missing edge for branch `default` of step `<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>`. You only passed the following `control_flow_edges`: [ControlFlowEdge(source_step=<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>, destination_step=<wayflowcore.steps.outputmessagestep.OutputMessageStep object at 0x1002d61d0>, source_branch='success', __metadata_info__={}), ControlFlowEdge(source_step=<wayflowcore.steps.branchingstep.BranchingStep object at 0x1002d6380>, destination_step=<wayflowcore.steps.outputmessagestep.OutputMessageStep object at 0x103e7aa10>, source_branch='failure', __metadata_info__={})]. The flow will raise at runtime if this branch is taken.
```

## Next steps

In this guide, you explored methods for implementing conditional branching within a Flow:

- [BranchingStep](../api/flows.md#branchingstep).
- [BranchingStep](../api/flows.md#branchingstep) with pattern matching.
- more complex conditionals with [ToolExecutionStep](../api/flows.md#toolexecutionstep), or [TemplateRenderingStep](../api/flows.md#templaterenderingstep), and
  [BranchingStep](../api/flows.md#branchingstep).
- an LLM to decide on the condition using [ChoiceSelectionStep](../api/flows.md#choiceselectionstep).
- a sub-flow to handle the conditional logic using [FlowExecutionStep](../api/flows.md#flowexecutionstep).

Having learned how to implement conditional branching in flows, you may now proceed to [Catching Exceptions](catching_exceptions.md) to see how to ensure robustness in a `Flow`.

## Full code

Click on the card at the [top of this page](#top-howtoconditionaltransitions) to download the
full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# How to Create Conditional Transitions in Flows
# ----------------------------------------------

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
# python howto_branching.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
from typing import cast


from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="meta-llama/Meta-Llama-3.1-8B-Instruct",
    host_port="VLLM_HOST_PORT",
)

from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import StringProperty


# %%[markdown]
## Branching step

# %%
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep

branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)



# %%[markdown]
## Flow

# %%
success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)



# %%[markdown]
## Execute

# %%
conversation = flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"



# %%[markdown]
## Export to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter
serialized_flow = AgentSpecExporter().to_json(flow)


# %%[markdown]
## Load and execute with Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecLoader

new_flow: Flow = AgentSpecLoader().load_json(serialized_flow)

conversation = new_flow.start_conversation(inputs={"my_var": "[SUCCESS]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a success"

conversation = new_flow.start_conversation(inputs={"my_var": "[FAILURE]"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"

conversation = new_flow.start_conversation(inputs={"my_var": "unknown"})
conversation.execute()
assert conversation.get_last_message().content == "It was a failure"


# %%[markdown]
## Branching with a regular expression

# %%
import re

from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, OutputMessageStep, RegexExtractionStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)
conversation = flow.start_conversation(
    inputs={"my_var": "The test passed successfully, so it's a [SUCCESS]"},
)
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a regular expression AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow: Flow = AgentSpecLoader().load_json(serialized_flow)
conversation = flow.start_conversation(
    inputs={"my_var": "The test passed successfully, so it's a [SUCCESS]"},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with a template

# %%
from wayflowcore.steps import BranchingStep, OutputMessageStep, StartStep, TemplateRenderingStep
from wayflowcore.property import BooleanProperty

template = "{% if my_var %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for boolean
# template = "{% if my_var > 10 %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # for integer
# template = "{% if lower(my_var) == '[success]' %}[SUCCESS]{% else %}[FAILURE]{% endif %}"  # with specific expressions

template_step = TemplateRenderingStep(
    name="template_step",
    template=template,
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)
TEMPLATE_STEP = "template_step"
START_STEP = "start_step"

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[BooleanProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=template_step),
        ControlFlowEdge(source_step=template_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", template_step, "my_var"),
        DataFlowEdge(
            template_step, TemplateRenderingStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME
        ),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": True})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a template AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": True},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with an LLM

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import ChoiceSelectionStep, OutputMessageStep

choice_step = ChoiceSelectionStep(
    name="choice_step",
    llm=llm,
    next_steps=[
        ("success", "in case the test passed successfully"),
        ("failure", "in case the test did not pass"),
    ],
)

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="start_step")
flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=choice_step),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=success_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=choice_step,
            destination_step=failure_step,
            source_branch=ChoiceSelectionStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(start_step, "my_var", choice_step, ChoiceSelectionStep.INPUT),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "TEST IS SUCCESSFUL"})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with an LLM AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": True},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"


# %%[markdown]
## Branching with a Subflow

# %%
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, CompleteStep, FlowExecutionStep, OutputMessageStep

tokens = ["[SUCCESS]", "[FAILURE]"]

regex_step = RegexExtractionStep(
    name="regex_step",
    regex_pattern=rf"({'|'.join(re.escape(token) for token in tokens)})",
)
branching_step = BranchingStep(
    name="branching_step",
    branch_name_mapping={
        "[SUCCESS]": "success",
        "[FAILURE]": "failure",
    },
)

sub_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="sub_start_step")
success_internal_step = CompleteStep(name="success_internal_step")
failure_internal_step = CompleteStep(name="failure_internal_step")
subflow = Flow(
    begin_step=sub_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=sub_start_step, destination_step=regex_step),
        ControlFlowEdge(source_step=regex_step, destination_step=branching_step),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=success_internal_step,
            source_branch="success",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch="failure",
        ),
        ControlFlowEdge(
            source_step=branching_step,
            destination_step=failure_internal_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
    ],
    data_flow_edges=[
        DataFlowEdge(sub_start_step, "my_var", regex_step, RegexExtractionStep.TEXT),
        DataFlowEdge(regex_step, RegexExtractionStep.OUTPUT, branching_step, BranchingStep.NEXT_BRANCH_NAME),
    ],
)

subflow_step = FlowExecutionStep(subflow, name="subflow_step")
subflow_step.get_branches()  # ['success_internal_step', 'failure_internal_step']

success_step = OutputMessageStep("It was a success", name="success_step")
failure_step = OutputMessageStep("It was a failure", name="failure_step")
outer_start_step = StartStep(input_descriptors=[StringProperty("my_var")], name="outer_start_step")
flow = Flow(
    begin_step=outer_start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=outer_start_step, destination_step=subflow_step),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=success_step,
            source_branch="success_internal_step",
        ),
        ControlFlowEdge(
            source_step=subflow_step,
            destination_step=failure_step,
            source_branch="failure_internal_step",
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(outer_start_step, "my_var", subflow_step, "my_var"),
    ],
)
conversation = flow.start_conversation(inputs={"my_var": "Test passed, so [SUCCESS]"})
conversation.execute()
# "It was a success"



# %%[markdown]
## Branching with a Subflow AgentSpec export

# %%
serialized_flow = AgentSpecExporter().to_json(flow)
flow = cast(Flow, AgentSpecLoader().load_json(serialized_flow))
conversation = flow.start_conversation(
    inputs={"my_var": "Test passed, so [SUCCESS]"},
)
conversation.execute()
assert conversation.get_last_message().content == "It was a success"
```
