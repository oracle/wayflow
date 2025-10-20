# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

# mypy: ignore-errors
# isort:skip_file
# fmt: off
# docs-title: Code Example - How to Ask for User Input in Flows

# .. start-##_Create_LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Create_LLM
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore
# llm.set_next_output("a surprisingly simple answer emerges: 20 pounds of bricks is heavier than 20 feathers by a massive margin, approximately 69.78 pounds.") # docs-skiprow
# .. start-##_Create_Simple_Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import (
    BranchingStep,
    CompleteStep,
    ExtractValueFromJsonStep,
    InputMessageStep,
    PromptExecutionStep,
    StartStep,
    ToolExecutionStep,
)
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def get_user_name_tool() -> str:
    """Tool to get user name."""
    return "Alice"

start_step = StartStep(name="start")

get_user_name_step = ToolExecutionStep(
    name="get_user_name_step",
    tool=get_user_name_tool,
)

ask_user_request_step = InputMessageStep(
    name="ask_user_request_step", message_template="Hi {{username}}. What can I do for you today?"
)

answer_request_step = PromptExecutionStep(
    name="answer_request_step",
    llm=llm,
    prompt_template="Your are an helpful assistant. Help answer the user request: {{request}}",
    output_mapping={
        PromptExecutionStep.OUTPUT: "my_output"
    },  # what we want to expose as the output name
)

end_step = CompleteStep(name="end")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, answer_request_step),
        ControlFlowEdge(answer_request_step, end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            answer_request_step,
            "request",
        ),
    ],
)
# .. end-##_Create_Simple_Flow
# .. start-##_Execute_Simple_Flow
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("What is heavier? 20 pounds of bricks of 20 feathers?")
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")
print(
    status.output_values["my_output"]
)  # using the key name that we defined in the `output_mapping`
# [...] a surprisingly simple answer emerges: 20 pounds of bricks is heavier than 20 feathers by a massive margin, approximately 69.78 pounds.
# .. end-##_Execute_Simple_Flow
# .. start-##_Create_Complex_Flow
import json
from typing import Dict

from wayflowcore.contextproviders.constantcontextprovider import ConstantContextProvider
from wayflowcore.property import DictProperty, StringProperty

@tool(description_mode="only_docstring")
def my_tool(params: Dict[str, str]) -> str:
    """Params: {"param": str}"""
    return f"Invoked tool with {params=}"

prompt_template = """
Your are an helpful assistant. Help answer the user request.

Here is the list of tools:
{{tools}}

Here is the user request:
{{request}}

## Response format
Your response should be JSON-compliant dictionary with the following structure.

{
    "action": "answer|execute_tool",
    "tool_name": "None|tool_name",
    "tool_args": {"param1": "value1"}
}

When the action is "answer", "tool_name" should be "None" and "tool_args" should be {}
When the action is "execute_tool", "tool_name" should be the name of the tool to execute
and "tool_args" should be the JSON-compliant dictionary of arguments to pass to the tool.

CRITICAL: Only output the JSON-compliant dictionary otherwise the parsing will fail.
fail.
""".strip()

available_tools = [my_tool]
tool_context_provider = ConstantContextProvider(
    json.dumps([tool_.to_dict() for tool_ in available_tools]),
    output_description=StringProperty("tool_info"),
)

generate_action_step = PromptExecutionStep(
    name="generate_action_step", llm=llm, prompt_template=prompt_template
)

extract_result_step = ExtractValueFromJsonStep(
    name="extract_result_step",
    output_values={
        "action": ".action",
        "tool_name": ".tool_name",
        "tool_args": ".tool_args",
    },
    output_descriptors=[
        StringProperty(name='action'),
        StringProperty(name='tool_name'),
        DictProperty(name='tool_args'),
    ]
)

branching_step = BranchingStep(
    name="branching_step", branch_name_mapping={"answer": "answer", "execute_tool": "execute_tool"}
)

answer_end_step = CompleteStep(name="answer_end_step")

user_tool_validation_step = InputMessageStep(
    name="user_tool_validation_step",
    message_template="Requesting to invoke tool {{name}} with parameters {{params}}. Do you accept the request? (y/n)",
)

tool_selection_branching_step = BranchingStep(
    name="tool_selection_branching_step",
    branch_name_mapping={"y": "execute_tool", "n": "retry_llm"},
)

invoke_tool_step = ToolExecutionStep(
    name="invoke_tool_step",
    tool=my_tool,
)

invoke_tool_end_step = CompleteStep(name="invoke_tool_end_step")

flow = Flow(
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(start_step, get_user_name_step),
        ControlFlowEdge(get_user_name_step, ask_user_request_step),
        ControlFlowEdge(ask_user_request_step, generate_action_step),
        ControlFlowEdge(generate_action_step, extract_result_step),
        ControlFlowEdge(extract_result_step, branching_step),
        ControlFlowEdge(branching_step, answer_end_step, source_branch="answer"),
        ControlFlowEdge(branching_step, user_tool_validation_step, source_branch="execute_tool"),
        ControlFlowEdge(
            branching_step, answer_end_step, source_branch=BranchingStep.BRANCH_DEFAULT
        ),
        ControlFlowEdge(user_tool_validation_step, tool_selection_branching_step),
        ControlFlowEdge(
            tool_selection_branching_step, invoke_tool_step, source_branch="execute_tool"
        ),
        ControlFlowEdge(
            tool_selection_branching_step, generate_action_step, source_branch="retry_llm"
        ),
        ControlFlowEdge(
            tool_selection_branching_step,
            generate_action_step,
            source_branch=BranchingStep.BRANCH_DEFAULT,
        ),
        ControlFlowEdge(invoke_tool_step, invoke_tool_end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            get_user_name_step, ToolExecutionStep.TOOL_OUTPUT, ask_user_request_step, "username"
        ),
        DataFlowEdge(
            ask_user_request_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            generate_action_step,
            "request",
        ),
        DataFlowEdge(tool_context_provider, "tool_info", generate_action_step, "tools"),
        DataFlowEdge(
            generate_action_step,
            PromptExecutionStep.OUTPUT,
            extract_result_step,
            ExtractValueFromJsonStep.TEXT,
        ),
        DataFlowEdge(extract_result_step, "action", branching_step, BranchingStep.NEXT_BRANCH_NAME),
        DataFlowEdge(extract_result_step, "tool_name", user_tool_validation_step, "name"),
        DataFlowEdge(extract_result_step, "tool_args", user_tool_validation_step, "params"),
        DataFlowEdge(
            user_tool_validation_step,
            InputMessageStep.USER_PROVIDED_INPUT,
            tool_selection_branching_step,
            BranchingStep.NEXT_BRANCH_NAME,
        ),
        DataFlowEdge(extract_result_step, "tool_args", invoke_tool_step, "params"),
    ],
)
# .. end-##_Create_Complex_Flow
# .. start-##_Execute_Complex_Flow
conversation = flow.start_conversation()
status = (
    conversation.execute()
)  # will get the user input, then pause the execution to ask for the user input

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Hi Alice. What can I do for you today?

conversation.append_user_message("Invoke the tool with parameter 'value#007'")
status = conversation.execute()  # we resume the execution

if not isinstance(status, UserMessageRequestStatus):
    raise ValueError(
        f"Execution status should be {UserMessageRequestStatus.__name__}, was {type(status)}"
    )
print(conversation.get_last_message().content)
# Requesting to invoke tool my_tool with parameters {"param": "value#007"}. Do you accept the request? (y/n)

conversation.append_user_message("y")  # we accept the tool call request
status = conversation.execute()  # we resume the execution

if not isinstance(status, FinishedStatus):
    raise ValueError(f"Execution status should be {FinishedStatus.__name__}, was {type(status)}")

print(status.output_values[ToolExecutionStep.TOOL_OUTPUT])
# Invoked tool with params={'param': 'value#007'}
# .. end-##_Execute_Complex_Flow

# .. start-##_Export_Config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(flow)
# .. end-##_Export_Config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_Config
from wayflowcore.agentspec import AgentSpecLoader

print(config)
new_flow = AgentSpecLoader(
    tool_registry={
        'get_user_name_tool': get_user_name_tool,
        'my_tool': my_tool
    }
).load_json(config)
# .. end-##_Load_Agent_Spec_Config
