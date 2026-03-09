<a id="top-catchingexceptions"></a>

# How to Catch Exceptions in Flows![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Catching exceptions how-to script](../end_to_end_code_examples/howto_catchingexceptions.py)

#### Prerequisites
This guide assumes familiarity with [Flows](../tutorials/basic_flow.md).

Exception handling is a crucial aspect of building robust and reliable software applications.
It allows a program to gracefully handle unexpected issues without crashing.
In WayFlow, exception handling can be achieved using the [CatchExceptionStep](../api/flows.md#catchexceptionstep) API.

This guide shows you how to use this step to catch and process exceptions in a sub-flow:

![Simple Flow using a catch exception step](core/_static/howto/catchexceptionstep.svg)

#### SEE ALSO
The [RetryStep](../api/flows.md#retrystep) can be used to retry a sub-flow on specific criteria. See API documentation for more information.

## Basic implementation

To catch exceptions in a sub-flow, WayFlow offers the [CatchExceptionStep](../api/flows.md#catchexceptionstep) class.
This step is configured to run a flow and catches any exceptions that occur during its execution.

The following example demonstrates the use of the `CatchExceptionStep`.
Assuming you want to catch only `ValueError` exceptions. Specify them in the `except_on` parameter and define the branch name to which the flow will continue upon catching such exceptions.

```python
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import BooleanProperty
from wayflowcore.steps import (
    CatchExceptionStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def flaky_tool(raise_error: bool = False) -> str:
    """Will throw a ValueError"""
    if raise_error:
        raise ValueError("Raising an error.")
    return "execution successful"


FLAKY_TOOL_STEP = "flaky_tool_step"
VALUE_ERROR_BRANCH = ValueError.__name__
start_step_flaky = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
flaky_tool_step = ToolExecutionStep(tool=flaky_tool, raise_exceptions=True, name="flaky_step")
flaky_subflow = Flow.from_steps(steps=[start_step_flaky, flaky_tool_step])
ERROR_IO = "error_io"
catch_step = CatchExceptionStep(
    flow=flaky_subflow, except_on={ValueError.__name__: VALUE_ERROR_BRANCH}, name="catch_flow_step"
)
```

Once this is done, create the main flow and map each branch of the catch exception step to the next step.
In this example, the catch exception step has one branch for when a `ValueError` is caught (named `VALUE_ERROR_BRANCH`),
and one default branch when no exception is raised (`Step.BRANCH_NEXT`, which is the only branch of the sub-flow).

You can check the branch name of a step using the `step.get_branches()` function.

```python
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catch_step),
        ControlFlowEdge(
            source_step=catch_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catch_step, destination_step=failure_step, source_branch=VALUE_ERROR_BRANCH
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catch_step, "raise_error"),
        DataFlowEdge(
            catch_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)
```

Now you have a complete flow that takes different transitions depending on whether an exception was raised or not:

```python
conversation = flow.start_conversation(inputs={"raise_error": False})
conversation.execute()
# "Success: No error was raised"

conversation = flow.start_conversation(inputs={"raise_error": True})
conversation.execute()
# "Failure: Did get an error: ValueError"
```

#### TIP
When developing flows, similarly to try-catch best practices in Python, we recommended to wrap only the steps that are likely to raise errors.
This approach helps to keep the flow organized and easier to maintain.
By wrapping only the error-prone steps, you can catch and handle specific exceptions more effectively, reducing the likelihood of masking other unexpected issues.

## Common patterns

### Catching all exceptions

To catch all exceptions and redirect to a shared branch, use the `catch_all_exceptions` parameter of the `CatchExceptionStep` class, and specify the transition of the branch `CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH` as shown below:

```python
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
catchall_step = CatchExceptionStep(
    flow=flaky_subflow,
    catch_all_exceptions=True,
    name="catch_flow_step",
)
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catchall_step),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=failure_step,
            source_branch=CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catchall_step, "raise_error"),
        DataFlowEdge(
            catchall_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)
```

### Catching OCI model errors

OCI models may raise a `ServiceError` when used (for example, when an inappropriate content is detected).
You can directly wrap the [PromptExecutionStep](../api/flows.md#promptexecutionstep) using the `CatchExceptionStep` and the helper method `Flow.from_steps`, as follows:

```python
from oci.exceptions import ServiceError
from wayflowcore.models import OCIGenAIModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

llm = OCIGenAIModel(
    model_id="openai.model-id",
    client_config=oci_config,
    compartment_id="COMPARTMENT_ID",
)

robust_prompt_execution_step = CatchExceptionStep(
    flow=Flow.from_steps([PromptExecutionStep(prompt_template="{{prompt_template}}", llm=llm)]),
    except_on={ServiceError.__name__: "oci_service_error"},
)
```

## Agent Spec Exporting/Loading

You can export the flow configuration to its Agent Spec configuration using the `AgentSpecExporter`.

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
  "id": "8790d14c-d174-4e85-9abe-b4cc9c6dbc25",
  "name": "flow_873c86b9__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [
    {
      "type": "boolean",
      "title": "raise_error"
    }
  ],
  "outputs": [
    {
      "description": "Name of the exception that was caught",
      "title": "exception_name",
      "default": ""
    },
    {
      "description": "Payload of the exception that was caught",
      "title": "exception_payload_name",
      "default": ""
    },
    {
      "type": "string",
      "title": "tool_output"
    },
    {
      "description": "the message added to the messages list",
      "type": "string",
      "title": "output_message"
    }
  ],
  "start_node": {
    "$component_ref": "4ed17c58-5626-4f68-88f6-ebf70477af8f"
  },
  "nodes": [
    {
      "$component_ref": "4ed17c58-5626-4f68-88f6-ebf70477af8f"
    },
    {
      "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
    },
    {
      "$component_ref": "9156731d-9ad8-44d0-85e1-3b26dd8950b3"
    },
    {
      "$component_ref": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1"
    },
    {
      "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
    }
  ],
  "control_flow_connections": [
    {
      "component_type": "ControlFlowEdge",
      "id": "60699de0-998d-45aa-99c9-284d59a1dddf",
      "name": "start_step_to_catch_flow_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "4ed17c58-5626-4f68-88f6-ebf70477af8f"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "c88ca590-1015-447f-bc49-8f4ad4da86e8",
      "name": "catch_flow_step_to_success_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "9156731d-9ad8-44d0-85e1-3b26dd8950b3"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "e3f938c9-0ab2-4285-9852-8dcce8289793",
      "name": "catch_flow_step_to_failure_step_control_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "from_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "from_branch": "default_exception_branch",
      "to_node": {
        "$component_ref": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "1d601535-b83a-46b4-91b8-2a1bb7198322",
      "name": "success_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "9156731d-9ad8-44d0-85e1-3b26dd8950b3"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      }
    },
    {
      "component_type": "ControlFlowEdge",
      "id": "094c4349-9eea-4b61-b7c4-d83e370724c2",
      "name": "failure_step_to_None End node_control_flow_edge",
      "description": null,
      "metadata": {},
      "from_node": {
        "$component_ref": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1"
      },
      "from_branch": null,
      "to_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      }
    }
  ],
  "data_flow_connections": [
    {
      "component_type": "DataFlowEdge",
      "id": "b8d87f98-029a-46e4-b149-e00e641eb655",
      "name": "start_step_raise_error_to_catch_flow_step_raise_error_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "4ed17c58-5626-4f68-88f6-ebf70477af8f"
      },
      "source_output": "raise_error",
      "destination_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "destination_input": "raise_error"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "f911cd15-2c43-4732-b12e-f4c73053aa14",
      "name": "catch_flow_step_exception_name_to_failure_step_tool_error_data_flow_edge",
      "description": null,
      "metadata": {
        "__metadata_info__": {}
      },
      "source_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "source_output": "exception_name",
      "destination_node": {
        "$component_ref": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1"
      },
      "destination_input": "tool_error"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "0d6a8f69-aa8d-479c-9538-200cda5015de",
      "name": "catch_flow_step_exception_name_to_None End node_exception_name_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "source_output": "exception_name",
      "destination_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      },
      "destination_input": "exception_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "f93ecced-213b-48d1-89fd-b089c92cbdbe",
      "name": "catch_flow_step_exception_payload_name_to_None End node_exception_payload_name_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "source_output": "exception_payload_name",
      "destination_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      },
      "destination_input": "exception_payload_name"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "bda41fa5-beee-4d94-b4e4-6b916f552c07",
      "name": "catch_flow_step_tool_output_to_None End node_tool_output_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "e6fbadc2-f729-40c9-9520-7e23f559b078"
      },
      "source_output": "tool_output",
      "destination_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      },
      "destination_input": "tool_output"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "6d32d864-b295-41c6-8240-859af65f65d5",
      "name": "success_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "9156731d-9ad8-44d0-85e1-3b26dd8950b3"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      },
      "destination_input": "output_message"
    },
    {
      "component_type": "DataFlowEdge",
      "id": "f922f0b4-a4b2-44f9-aeb1-95eeba6fc077",
      "name": "failure_step_output_message_to_None End node_output_message_data_flow_edge",
      "description": null,
      "metadata": {},
      "source_node": {
        "$component_ref": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1"
      },
      "source_output": "output_message",
      "destination_node": {
        "$component_ref": "743924fc-4c00-4feb-a536-57affd72e3ae"
      },
      "destination_input": "output_message"
    }
  ],
  "$referenced_components": {
    "e6fbadc2-f729-40c9-9520-7e23f559b078": {
      "component_type": "PluginCatchExceptionNode",
      "id": "e6fbadc2-f729-40c9-9520-7e23f559b078",
      "name": "catch_flow_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "boolean",
          "title": "raise_error"
        }
      ],
      "outputs": [
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "Name of the exception that was caught",
          "title": "exception_name",
          "default": ""
        },
        {
          "description": "Payload of the exception that was caught",
          "title": "exception_payload_name",
          "default": ""
        }
      ],
      "branches": [
        "default_exception_branch",
        "next"
      ],
      "input_mapping": {},
      "output_mapping": {},
      "flow": {
        "component_type": "Flow",
        "id": "7182eaa8-b13c-4ce4-a90a-1dccc15af8e1",
        "name": "flow_8fc4ea12__auto",
        "description": "",
        "metadata": {
          "__metadata_info__": {}
        },
        "inputs": [
          {
            "type": "boolean",
            "title": "raise_error"
          }
        ],
        "outputs": [
          {
            "type": "string",
            "title": "tool_output"
          }
        ],
        "start_node": {
          "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
        },
        "nodes": [
          {
            "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
          },
          {
            "$component_ref": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2"
          },
          {
            "$component_ref": "914b281e-f904-4faf-8e5a-b95aefaa944b"
          }
        ],
        "control_flow_connections": [
          {
            "component_type": "ControlFlowEdge",
            "id": "fbf61770-a9a8-4f32-915b-007b8b2c307a",
            "name": "start_step_to_flaky_step_control_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "from_node": {
              "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2"
            }
          },
          {
            "component_type": "ControlFlowEdge",
            "id": "5a2a93dd-f29f-47a1-8323-163fdcd5cc60",
            "name": "flaky_step_to_None End node_control_flow_edge",
            "description": null,
            "metadata": {},
            "from_node": {
              "$component_ref": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2"
            },
            "from_branch": null,
            "to_node": {
              "$component_ref": "914b281e-f904-4faf-8e5a-b95aefaa944b"
            }
          }
        ],
        "data_flow_connections": [
          {
            "component_type": "DataFlowEdge",
            "id": "9abae96c-dcf5-4421-a251-b62f56fa0916",
            "name": "start_step_raise_error_to_start_step_raise_error_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
            },
            "source_output": "raise_error",
            "destination_node": {
              "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
            },
            "destination_input": "raise_error"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "aae9e5ce-036f-405c-9b4a-186e2ec613df",
            "name": "start_step_raise_error_to_flaky_step_raise_error_data_flow_edge",
            "description": null,
            "metadata": {
              "__metadata_info__": {}
            },
            "source_node": {
              "$component_ref": "a5cbef29-1162-4ddb-8891-3d656a803154"
            },
            "source_output": "raise_error",
            "destination_node": {
              "$component_ref": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2"
            },
            "destination_input": "raise_error"
          },
          {
            "component_type": "DataFlowEdge",
            "id": "397bb536-3a7a-445e-9a05-f632e3f0fb92",
            "name": "flaky_step_tool_output_to_None End node_tool_output_data_flow_edge",
            "description": null,
            "metadata": {},
            "source_node": {
              "$component_ref": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2"
            },
            "source_output": "tool_output",
            "destination_node": {
              "$component_ref": "914b281e-f904-4faf-8e5a-b95aefaa944b"
            },
            "destination_input": "tool_output"
          }
        ],
        "$referenced_components": {
          "a5cbef29-1162-4ddb-8891-3d656a803154": {
            "component_type": "StartNode",
            "id": "a5cbef29-1162-4ddb-8891-3d656a803154",
            "name": "start_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "boolean",
                "title": "raise_error"
              }
            ],
            "outputs": [
              {
                "type": "boolean",
                "title": "raise_error"
              }
            ],
            "branches": [
              "next"
            ]
          },
          "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2": {
            "component_type": "ToolNode",
            "id": "4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2",
            "name": "flaky_step",
            "description": "",
            "metadata": {
              "__metadata_info__": {}
            },
            "inputs": [
              {
                "type": "boolean",
                "title": "raise_error",
                "default": false
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "tool_output"
              }
            ],
            "branches": [
              "next"
            ],
            "tool": {
              "component_type": "ServerTool",
              "id": "03df1ec4-1544-4719-8c24-6fa4ad5c4c5d",
              "name": "flaky_tool",
              "description": "Will throw a ValueError",
              "metadata": {
                "__metadata_info__": {}
              },
              "inputs": [
                {
                  "type": "boolean",
                  "title": "raise_error",
                  "default": false
                }
              ],
              "outputs": [
                {
                  "type": "string",
                  "title": "tool_output"
                }
              ]
            }
          },
          "914b281e-f904-4faf-8e5a-b95aefaa944b": {
            "component_type": "EndNode",
            "id": "914b281e-f904-4faf-8e5a-b95aefaa944b",
            "name": "None End node",
            "description": "End node representing all transitions to None in the WayFlow flow",
            "metadata": {},
            "inputs": [
              {
                "type": "string",
                "title": "tool_output"
              }
            ],
            "outputs": [
              {
                "type": "string",
                "title": "tool_output"
              }
            ],
            "branches": [],
            "branch_name": "next"
          }
        }
      },
      "except_on": {},
      "catch_all_exceptions": true,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "4ed17c58-5626-4f68-88f6-ebf70477af8f": {
      "component_type": "StartNode",
      "id": "4ed17c58-5626-4f68-88f6-ebf70477af8f",
      "name": "start_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "type": "boolean",
          "title": "raise_error"
        }
      ],
      "outputs": [
        {
          "type": "boolean",
          "title": "raise_error"
        }
      ],
      "branches": [
        "next"
      ]
    },
    "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1": {
      "component_type": "PluginOutputMessageNode",
      "id": "40fc6a52-5dae-4de9-9f7e-9b168cdf45d1",
      "name": "failure_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [
        {
          "description": "\"tool_error\" input variable for the template",
          "type": "string",
          "title": "tool_error"
        }
      ],
      "outputs": [
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        }
      ],
      "branches": [
        "next"
      ],
      "expose_message_as_output": true,
      "message": "Failure: Did get an error: {{tool_error}}",
      "input_mapping": {},
      "output_mapping": {},
      "message_type": "AGENT",
      "rephrase": false,
      "llm_config": null,
      "component_plugin_name": "NodesPlugin",
      "component_plugin_version": "25.4.0.dev0"
    },
    "743924fc-4c00-4feb-a536-57affd72e3ae": {
      "component_type": "EndNode",
      "id": "743924fc-4c00-4feb-a536-57affd72e3ae",
      "name": "None End node",
      "description": "End node representing all transitions to None in the WayFlow flow",
      "metadata": {},
      "inputs": [
        {
          "description": "Name of the exception that was caught",
          "title": "exception_name",
          "default": ""
        },
        {
          "description": "Payload of the exception that was caught",
          "title": "exception_payload_name",
          "default": ""
        },
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        }
      ],
      "outputs": [
        {
          "description": "Name of the exception that was caught",
          "title": "exception_name",
          "default": ""
        },
        {
          "description": "Payload of the exception that was caught",
          "title": "exception_payload_name",
          "default": ""
        },
        {
          "type": "string",
          "title": "tool_output"
        },
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        }
      ],
      "branches": [],
      "branch_name": "next"
    },
    "9156731d-9ad8-44d0-85e1-3b26dd8950b3": {
      "component_type": "PluginOutputMessageNode",
      "id": "9156731d-9ad8-44d0-85e1-3b26dd8950b3",
      "name": "success_step",
      "description": "",
      "metadata": {
        "__metadata_info__": {}
      },
      "inputs": [],
      "outputs": [
        {
          "description": "the message added to the messages list",
          "type": "string",
          "title": "output_message"
        }
      ],
      "branches": [
        "next"
      ],
      "expose_message_as_output": true,
      "message": "Success: No error was raised",
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
id: 8790d14c-d174-4e85-9abe-b4cc9c6dbc25
name: flow_873c86b9__auto
description: ''
metadata:
  __metadata_info__: {}
inputs:
- type: boolean
  title: raise_error
outputs:
- description: Name of the exception that was caught
  title: exception_name
  default: ''
- description: Payload of the exception that was caught
  title: exception_payload_name
  default: ''
- type: string
  title: tool_output
- description: the message added to the messages list
  type: string
  title: output_message
start_node:
  $component_ref: 4ed17c58-5626-4f68-88f6-ebf70477af8f
nodes:
- $component_ref: 4ed17c58-5626-4f68-88f6-ebf70477af8f
- $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
- $component_ref: 9156731d-9ad8-44d0-85e1-3b26dd8950b3
- $component_ref: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
- $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
control_flow_connections:
- component_type: ControlFlowEdge
  id: 60699de0-998d-45aa-99c9-284d59a1dddf
  name: start_step_to_catch_flow_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: 4ed17c58-5626-4f68-88f6-ebf70477af8f
  from_branch: null
  to_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
- component_type: ControlFlowEdge
  id: c88ca590-1015-447f-bc49-8f4ad4da86e8
  name: catch_flow_step_to_success_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  from_branch: null
  to_node:
    $component_ref: 9156731d-9ad8-44d0-85e1-3b26dd8950b3
- component_type: ControlFlowEdge
  id: e3f938c9-0ab2-4285-9852-8dcce8289793
  name: catch_flow_step_to_failure_step_control_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  from_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  from_branch: default_exception_branch
  to_node:
    $component_ref: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
- component_type: ControlFlowEdge
  id: 1d601535-b83a-46b4-91b8-2a1bb7198322
  name: success_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 9156731d-9ad8-44d0-85e1-3b26dd8950b3
  from_branch: null
  to_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
- component_type: ControlFlowEdge
  id: 094c4349-9eea-4b61-b7c4-d83e370724c2
  name: failure_step_to_None End node_control_flow_edge
  description: null
  metadata: {}
  from_node:
    $component_ref: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
  from_branch: null
  to_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
data_flow_connections:
- component_type: DataFlowEdge
  id: b8d87f98-029a-46e4-b149-e00e641eb655
  name: start_step_raise_error_to_catch_flow_step_raise_error_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: 4ed17c58-5626-4f68-88f6-ebf70477af8f
  source_output: raise_error
  destination_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  destination_input: raise_error
- component_type: DataFlowEdge
  id: f911cd15-2c43-4732-b12e-f4c73053aa14
  name: catch_flow_step_exception_name_to_failure_step_tool_error_data_flow_edge
  description: null
  metadata:
    __metadata_info__: {}
  source_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  source_output: exception_name
  destination_node:
    $component_ref: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
  destination_input: tool_error
- component_type: DataFlowEdge
  id: 0d6a8f69-aa8d-479c-9538-200cda5015de
  name: catch_flow_step_exception_name_to_None End node_exception_name_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  source_output: exception_name
  destination_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
  destination_input: exception_name
- component_type: DataFlowEdge
  id: f93ecced-213b-48d1-89fd-b089c92cbdbe
  name: catch_flow_step_exception_payload_name_to_None End node_exception_payload_name_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  source_output: exception_payload_name
  destination_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
  destination_input: exception_payload_name
- component_type: DataFlowEdge
  id: bda41fa5-beee-4d94-b4e4-6b916f552c07
  name: catch_flow_step_tool_output_to_None End node_tool_output_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: e6fbadc2-f729-40c9-9520-7e23f559b078
  source_output: tool_output
  destination_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
  destination_input: tool_output
- component_type: DataFlowEdge
  id: 6d32d864-b295-41c6-8240-859af65f65d5
  name: success_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 9156731d-9ad8-44d0-85e1-3b26dd8950b3
  source_output: output_message
  destination_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
  destination_input: output_message
- component_type: DataFlowEdge
  id: f922f0b4-a4b2-44f9-aeb1-95eeba6fc077
  name: failure_step_output_message_to_None End node_output_message_data_flow_edge
  description: null
  metadata: {}
  source_node:
    $component_ref: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
  source_output: output_message
  destination_node:
    $component_ref: 743924fc-4c00-4feb-a536-57affd72e3ae
  destination_input: output_message
$referenced_components:
  e6fbadc2-f729-40c9-9520-7e23f559b078:
    component_type: PluginCatchExceptionNode
    id: e6fbadc2-f729-40c9-9520-7e23f559b078
    name: catch_flow_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: boolean
      title: raise_error
    outputs:
    - type: string
      title: tool_output
    - description: Name of the exception that was caught
      title: exception_name
      default: ''
    - description: Payload of the exception that was caught
      title: exception_payload_name
      default: ''
    branches:
    - default_exception_branch
    - next
    input_mapping: {}
    output_mapping: {}
    flow:
      component_type: Flow
      id: 7182eaa8-b13c-4ce4-a90a-1dccc15af8e1
      name: flow_8fc4ea12__auto
      description: ''
      metadata:
        __metadata_info__: {}
      inputs:
      - type: boolean
        title: raise_error
      outputs:
      - type: string
        title: tool_output
      start_node:
        $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
      nodes:
      - $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
      - $component_ref: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
      - $component_ref: 914b281e-f904-4faf-8e5a-b95aefaa944b
      control_flow_connections:
      - component_type: ControlFlowEdge
        id: fbf61770-a9a8-4f32-915b-007b8b2c307a
        name: start_step_to_flaky_step_control_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        from_node:
          $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
        from_branch: null
        to_node:
          $component_ref: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
      - component_type: ControlFlowEdge
        id: 5a2a93dd-f29f-47a1-8323-163fdcd5cc60
        name: flaky_step_to_None End node_control_flow_edge
        description: null
        metadata: {}
        from_node:
          $component_ref: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
        from_branch: null
        to_node:
          $component_ref: 914b281e-f904-4faf-8e5a-b95aefaa944b
      data_flow_connections:
      - component_type: DataFlowEdge
        id: 9abae96c-dcf5-4421-a251-b62f56fa0916
        name: start_step_raise_error_to_start_step_raise_error_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
        source_output: raise_error
        destination_node:
          $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
        destination_input: raise_error
      - component_type: DataFlowEdge
        id: aae9e5ce-036f-405c-9b4a-186e2ec613df
        name: start_step_raise_error_to_flaky_step_raise_error_data_flow_edge
        description: null
        metadata:
          __metadata_info__: {}
        source_node:
          $component_ref: a5cbef29-1162-4ddb-8891-3d656a803154
        source_output: raise_error
        destination_node:
          $component_ref: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
        destination_input: raise_error
      - component_type: DataFlowEdge
        id: 397bb536-3a7a-445e-9a05-f632e3f0fb92
        name: flaky_step_tool_output_to_None End node_tool_output_data_flow_edge
        description: null
        metadata: {}
        source_node:
          $component_ref: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
        source_output: tool_output
        destination_node:
          $component_ref: 914b281e-f904-4faf-8e5a-b95aefaa944b
        destination_input: tool_output
      $referenced_components:
        a5cbef29-1162-4ddb-8891-3d656a803154:
          component_type: StartNode
          id: a5cbef29-1162-4ddb-8891-3d656a803154
          name: start_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: boolean
            title: raise_error
          outputs:
          - type: boolean
            title: raise_error
          branches:
          - next
        4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2:
          component_type: ToolNode
          id: 4ea1f1fe-b93b-4e58-82bf-0c2102e91bf2
          name: flaky_step
          description: ''
          metadata:
            __metadata_info__: {}
          inputs:
          - type: boolean
            title: raise_error
            default: false
          outputs:
          - type: string
            title: tool_output
          branches:
          - next
          tool:
            component_type: ServerTool
            id: 03df1ec4-1544-4719-8c24-6fa4ad5c4c5d
            name: flaky_tool
            description: Will throw a ValueError
            metadata:
              __metadata_info__: {}
            inputs:
            - type: boolean
              title: raise_error
              default: false
            outputs:
            - type: string
              title: tool_output
        914b281e-f904-4faf-8e5a-b95aefaa944b:
          component_type: EndNode
          id: 914b281e-f904-4faf-8e5a-b95aefaa944b
          name: None End node
          description: End node representing all transitions to None in the WayFlow
            flow
          metadata: {}
          inputs:
          - type: string
            title: tool_output
          outputs:
          - type: string
            title: tool_output
          branches: []
          branch_name: next
    except_on: {}
    catch_all_exceptions: true
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  4ed17c58-5626-4f68-88f6-ebf70477af8f:
    component_type: StartNode
    id: 4ed17c58-5626-4f68-88f6-ebf70477af8f
    name: start_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - type: boolean
      title: raise_error
    outputs:
    - type: boolean
      title: raise_error
    branches:
    - next
  40fc6a52-5dae-4de9-9f7e-9b168cdf45d1:
    component_type: PluginOutputMessageNode
    id: 40fc6a52-5dae-4de9-9f7e-9b168cdf45d1
    name: failure_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs:
    - description: '"tool_error" input variable for the template'
      type: string
      title: tool_error
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    expose_message_as_output: True
    message: 'Failure: Did get an error: {{tool_error}}'
    input_mapping: {}
    output_mapping: {}
    message_type: AGENT
    rephrase: false
    llm_config: null
    component_plugin_name: NodesPlugin
    component_plugin_version: 25.4.0.dev0
  743924fc-4c00-4feb-a536-57affd72e3ae:
    component_type: EndNode
    id: 743924fc-4c00-4feb-a536-57affd72e3ae
    name: None End node
    description: End node representing all transitions to None in the WayFlow flow
    metadata: {}
    inputs:
    - description: Name of the exception that was caught
      title: exception_name
      default: ''
    - description: Payload of the exception that was caught
      title: exception_payload_name
      default: ''
    - type: string
      title: tool_output
    - description: the message added to the messages list
      type: string
      title: output_message
    outputs:
    - description: Name of the exception that was caught
      title: exception_name
      default: ''
    - description: Payload of the exception that was caught
      title: exception_payload_name
      default: ''
    - type: string
      title: tool_output
    - description: the message added to the messages list
      type: string
      title: output_message
    branches: []
    branch_name: next
  9156731d-9ad8-44d0-85e1-3b26dd8950b3:
    component_type: PluginOutputMessageNode
    id: 9156731d-9ad8-44d0-85e1-3b26dd8950b3
    name: success_step
    description: ''
    metadata:
      __metadata_info__: {}
    inputs: []
    outputs:
    - description: the message added to the messages list
      type: string
      title: output_message
    branches:
    - next
    expose_message_as_output: True
    message: 'Success: No error was raised'
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

You can then load the configuration back to an assistant using the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {"flaky_tool": flaky_tool}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```

#### NOTE
This guide uses the following extension/plugin Agent Spec components:

- `PluginCatchExceptionNode`
- `PluginOutputMessageNode`

See the list of available Agent Spec extension/plugin components in the [API Reference](../api/agentspec.md)

## Next steps

In this guide, you learned how to do exception handling in WayFlow using the `CatchExceptionStep` class to:

- catch specific exceptions with the `except_on` parameter;
- catch all exceptions with the `catch_all_exceptions` parameter.

By following these steps and best practices, you can build more robust and reliable software applications using Flows.

Having learned how to handle exceptions in flows, you may now proceed to [How to Create Conditional Transitions in Flows](conditional_flows.md).

## Full code

Click on the card at the [top of this page](#top-catchingexceptions) to download the full code for this guide or copy the code below.

```python
# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Catch Exceptions in Flows
# -------------------------------------------------------

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
# python howto_catchingexceptions.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Define Catch Exception Step

# %%
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import BooleanProperty
from wayflowcore.steps import (
    CatchExceptionStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def flaky_tool(raise_error: bool = False) -> str:
    """Will throw a ValueError"""
    if raise_error:
        raise ValueError("Raising an error.")
    return "execution successful"


FLAKY_TOOL_STEP = "flaky_tool_step"
VALUE_ERROR_BRANCH = ValueError.__name__
start_step_flaky = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
flaky_tool_step = ToolExecutionStep(tool=flaky_tool, raise_exceptions=True, name="flaky_step")
flaky_subflow = Flow.from_steps(steps=[start_step_flaky, flaky_tool_step])
ERROR_IO = "error_io"
catch_step = CatchExceptionStep(
    flow=flaky_subflow, except_on={ValueError.__name__: VALUE_ERROR_BRANCH}, name="catch_flow_step"
)

# %%[markdown]
## Build Exception Handling Flow

# %%
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catch_step),
        ControlFlowEdge(
            source_step=catch_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catch_step, destination_step=failure_step, source_branch=VALUE_ERROR_BRANCH
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catch_step, "raise_error"),
        DataFlowEdge(
            catch_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)


# %%[markdown]
## Execute Flow With Exceptions

# %%
conversation = flow.start_conversation(inputs={"raise_error": False})
conversation.execute()
# "Success: No error was raised"

conversation = flow.start_conversation(inputs={"raise_error": True})
conversation.execute()
# "Failure: Did get an error: ValueError"

# %%[markdown]
## Catch All Exceptions

# %%
main_start = StartStep(input_descriptors=[BooleanProperty("raise_error")], name="start_step")
catchall_step = CatchExceptionStep(
    flow=flaky_subflow,
    catch_all_exceptions=True,
    name="catch_flow_step",
)
success_step = OutputMessageStep("Success: No error was raised", name="success_step")
failure_step = OutputMessageStep("Failure: Did get an error: {{tool_error}}", name="failure_step")

flow = Flow(
    begin_step=main_start,
    control_flow_edges=[
        ControlFlowEdge(source_step=main_start, destination_step=catchall_step),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=success_step,
            source_branch=CatchExceptionStep.BRANCH_NEXT,
        ),
        ControlFlowEdge(
            source_step=catchall_step,
            destination_step=failure_step,
            source_branch=CatchExceptionStep.DEFAULT_EXCEPTION_BRANCH,
        ),
        ControlFlowEdge(source_step=success_step, destination_step=None),
        ControlFlowEdge(source_step=failure_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(main_start, "raise_error", catchall_step, "raise_error"),
        DataFlowEdge(
            catchall_step, CatchExceptionStep.EXCEPTION_NAME_OUTPUT_NAME, failure_step, "tool_error"
        ),
    ],
)

# %%[markdown]
## Handle OCI Service Error

# %%
from oci.exceptions import ServiceError
from wayflowcore.models import OCIGenAIModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

llm = OCIGenAIModel(
    model_id="openai.model-id",
    client_config=oci_config,
    compartment_id="COMPARTMENT_ID",
)

robust_prompt_execution_step = CatchExceptionStep(
    flow=Flow.from_steps([PromptExecutionStep(prompt_template="{{prompt_template}}", llm=llm)]),
    except_on={ServiceError.__name__: "oci_service_error"},
)

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_flow = AgentSpecExporter().to_json(flow)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {"flaky_tool": flaky_tool}
flow = AgentSpecLoader(tool_registry=tool_registry).load_json(serialized_flow)
```
