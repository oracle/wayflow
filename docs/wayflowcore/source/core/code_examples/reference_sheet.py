# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

import logging
import os
from datetime import datetime
from types import MethodType
from typing import Annotated, Any

from wayflowcore.agent import Agent
from wayflowcore.contextproviders import (
    ChatHistoryContextProvider,
    FlowContextProvider,
    ToolContextProvider,
)
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.models import StreamChunkType, VllmModel
from wayflowcore.models.llmmodel import LlmCompletion
from wayflowcore.property import AnyProperty, FloatProperty, ListProperty, StringProperty
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.steps import (
    AgentExecutionStep,
    BranchingStep,
    FlowExecutionStep,
    MapStep,
    OutputMessageStep,
    PromptExecutionStep,
    ToolExecutionStep,
    VariableReadStep,
)
from wayflowcore.tools import ClientTool, DescribedFlow, register_server_tool, tool
from wayflowcore.variable import Variable

logging.basicConfig(level=logging.CRITICAL)

llm = VllmModel(
    model_id="model-id",
    host_port=os.environ["VLLM_HOST_PORT"],
)


async def _patch_generate_impl(
    self,
    messages,
    tools=None,
    use_tools=True,
    outputs=None,
    generation_config=None,
):
    return LlmCompletion(Message("hello", message_type=MessageType.AGENT), None)


async def _patch_stream_generate_impl(
    self,
    messages,
    tools=None,
    use_tools=True,
    generation_config=None,
):
    yield StreamChunkType.START_CHUNK, Message(content=""), None
    yield StreamChunkType.END_CHUNK, Message("Hello", MessageType.AGENT), None


llm._generate_impl = MethodType(_patch_generate_impl, llm)
llm._stream_generate_impl = MethodType(_patch_stream_generate_impl, llm)
# .. start-single_generation::
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.steps import PromptExecutionStep

flow = create_single_step_flow(PromptExecutionStep(prompt_template="{{prompt}}", llm=llm))
prompt = "Write a simple Python function to sum two numbers"
response = run_flow_and_return_outputs(flow, {"prompt": prompt})[PromptExecutionStep.OUTPUT]

print(response)  # Here's a simple Python function...
# .. end-single_generation
# .. start-parallel_generation::
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.property import ListProperty
from wayflowcore.steps import MapStep, PromptExecutionStep

flow = create_single_step_flow(
    MapStep(
        create_single_step_flow(PromptExecutionStep(prompt_template="{{prompt}}", llm=llm)),
        parallel_execution=True,
        unpack_input={"prompt": "."},
        output_descriptors=[ListProperty(PromptExecutionStep.OUTPUT)],
    )
)

NUM_RESPONSES = 3
prompt = "Write a simple Python function to sum two numbers"
prompt_batch = [prompt] * NUM_RESPONSES
response = run_flow_and_return_outputs(flow, {MapStep.ITERATED_INPUT: prompt_batch})[
    PromptExecutionStep.OUTPUT
]

print(*response, sep=f"\n\n{'-'*30}\n\n")
# .. end-parallel_generation
# .. start-structured_generation::
from wayflowcore.flowhelpers import create_single_step_flow, run_flow_and_return_outputs
from wayflowcore.property import ListProperty, StringProperty
from wayflowcore.steps import PromptExecutionStep

product_name = StringProperty(
    name="product_name",
    description="name of the product",
    default_value="",
)
product_description = StringProperty(
    name="product_description",
    description="One sentence description of the product.",
    default_value="",
)
functionalities = ListProperty(
    name="functionalities",
    description="List of functionalities of the product",
    item_type=StringProperty("functionality"),
    default_value=[],
)

flow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="{{prompt}}",
        llm=llm,
        output_descriptors=[product_name, product_description, functionalities],
    )
)
prompt = "Create a simple product for students."
response = run_flow_and_return_outputs(flow, {"prompt": prompt})

print(
    f"Name: {response['product_name']}\n"
    f"Description: {response['product_description']}\n"
    f"Functionalities:\n{response['functionalities']}"
)
# .. end-structured_generation
# .. start-simple_server_tool::
from datetime import datetime
from typing import Annotated

from wayflowcore.tools import tool


@tool
def days_between_dates(
    date1: Annotated[str, "First date in 'dd/mm/yyyy' format."],
    date2: Annotated[str, "Second date in 'dd/mm/yyyy' format."],
) -> Annotated[int, "Absolute difference in days between the two dates."]:
    """
    Calculate the absolute difference in days between two dates.
    """
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


# days_between_dates is not a callable anymore, it is a `ServerTool`
print(days_between_dates.func("01/01/2020", "31/12/2020"))  # 365
# .. end-simple_server_tool
# .. start-simple_stateful_tool::
from wayflowcore.tools import tool


class Counter:
    def __init__(self):
        self.value = 0

    def increment(self) -> str:
        """Increment the counter"""
        self.value += 1
        return f"The updated count is {self.value}"


counter = Counter()
counter_tool = tool("increment_counter", counter.increment)
print(counter_tool.func())  # The updated count is 1
# .. end-simple_stateful_tool
# .. start-client_tool::
from datetime import datetime
from typing import Any

from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ClientTool, ToolRequest, ToolResult


def _days_between_dates(date1: str, date2: str) -> int:
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


def execute_client_tool_from_tool_request(tool_request: ToolRequest) -> Any:
    if tool_request.name == "days_between_dates":
        return _days_between_dates(**tool_request.args)
    else:
        raise ValueError(f"Tool name {tool_request.name} is not recognized")


days_client_tools = ClientTool(
    name="days_between_dates",
    description="Calculate the absolute difference in days between two dates.",
    parameters={
        "date1": {
            "description": "First date in 'dd/mm/yyyy' format.",
            "type": "string",
        },
        "date2": {
            "description": "Second date in 'dd/mm/yyyy' format.",
            "type": "string",
        },
    },
    output={"type": "string", "description": "Absolute difference in days between the two dates."},
)

flow = create_single_step_flow(ToolExecutionStep(days_client_tools))
conversation = flow.start_conversation({"date1": "01/01/2020", "date2": "31/12/2020"})
status = conversation.execute()
assert isinstance(status, ToolRequestStatus)
tool_request = status.tool_requests[0]
tool_execution_content = execute_client_tool_from_tool_request(tool_request)

conversation.append_tool_result(ToolResult(tool_execution_content, tool_request.tool_request_id))
# conversation.execute() # continue the execution of the Flow
# .. end-client_tool
# .. start-simple_agent::
from wayflowcore.agent import Agent

agent = Agent(
    llm, custom_instruction="You are a helpful assistant, please answer the user requests."
)

conversation = agent.start_conversation()
conversation.append_user_message(
    "Please write a simple Python function to compute the sum of 2 numbers."
)
conversation.execute()
print(conversation.get_last_message().content)
# Here's a simple Python function that...
# .. end-simple_agent
# .. start-agent_with_tool::
from datetime import datetime
from typing import Annotated

from wayflowcore.agent import Agent
from wayflowcore.tools import tool


@tool
def days_between_dates(
    date1: Annotated[str, "First date in 'dd/mm/yyyy' format."],
    date2: Annotated[str, "Second date in 'dd/mm/yyyy' format."],
) -> Annotated[int, "Absolute difference in days between the two dates."]:
    """
    Calculate the absolute difference in days between two dates.
    """
    return abs((datetime.strptime(date2, "%d/%m/%Y") - datetime.strptime(date1, "%d/%m/%Y")).days)


agent = Agent(llm, tools=[days_between_dates])
conversation = agent.start_conversation()
conversation.append_user_message("How many days are there between 01/01/2020 and 31/12/2020?")
conversation.execute()
print(conversation.get_last_message().content)
# There are 365 days between 01/01/2020 and 31/12/2020.
# .. end-agent_with_tool
# .. start-simple_flow::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

opening_step = OutputMessageStep("Opening session")
closing_step = OutputMessageStep('Closing session"')
flow = Flow(
    begin_step_name="open_step",
    steps={
        "open_step": opening_step,
        "close_step": closing_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=opening_step, destination_step=closing_step),
        ControlFlowEdge(source_step=closing_step, destination_step=None),
    ],
)
conversation = flow.start_conversation()
status = conversation.execute()
print(conversation.get_messages())
# .. end-simple_flow
# .. start-flow_with_dataconnection::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

FAKE_PROCESSING_STEP = "processing_step"
OUTPUT_STEP = "output_step"
fake_processing_step = OutputMessageStep("Sucessfully processed username {{username}}")
output_step = OutputMessageStep('{{session_id}}: Received message "{{processing_message}}"')
flow = Flow(
    begin_step_name=FAKE_PROCESSING_STEP,
    steps={
        FAKE_PROCESSING_STEP: fake_processing_step,
        OUTPUT_STEP: output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(source_step=fake_processing_step, destination_step=output_step),
        ControlFlowEdge(source_step=output_step, destination_step=None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            fake_processing_step, OutputMessageStep.OUTPUT, output_step, "processing_message"
        )
    ],
)
conversation = flow.start_conversation(
    inputs={"username": "Username#123", "session_id": "Session#456"}
)
status = conversation.execute()
last_message = conversation.get_last_message()
# last_message.content
# Session#456: Received message "Sucessfully processed username Username#123"
# .. end-flow_with_dataconnection
# .. start-flow_with_mapstep::
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.property import AnyProperty
from wayflowcore.steps import MapStep, OutputMessageStep

sub_flow = create_single_step_flow(
    OutputMessageStep(message_template="username={{user}}"), step_name="step"
)
step = MapStep(
    flow=sub_flow,
    unpack_input={"user": "."},
    output_descriptors=[AnyProperty(name=OutputMessageStep.OUTPUT)],
)
iterable = ["a", "b"]
assistant = create_single_step_flow(step, "step")
conversation = assistant.start_conversation(inputs={MapStep.ITERATED_INPUT: iterable})
status = conversation.execute()
status.output_values  # {'output_message': ['username=a', 'username=b']}
# .. end-flow_with_mapstep
# .. start-flow_with_branching::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import BranchingStep, OutputMessageStep

NEXT_STEP_NAME_IO = "$next_step_name"
branching_step = BranchingStep(
    branch_name_mapping={"yes": "access_is_granted", "no": "access_is_denied"},
    input_mapping={BranchingStep.NEXT_BRANCH_NAME: NEXT_STEP_NAME_IO},
)
access_granted_output_step = OutputMessageStep("Access granted. Press any key to continue...")
access_denied_output_step = OutputMessageStep("Access denied. Please exit the conversation.")
assistant = Flow(
    begin_step_name="branching_step",
    steps={
        "branching_step": branching_step,
        "access_granted_output_step": access_granted_output_step,
        "access_denied_output_step": access_denied_output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(
            branching_step, access_granted_output_step, source_branch="access_is_granted"
        ),
        ControlFlowEdge(
            branching_step, access_denied_output_step, source_branch="access_is_denied"
        ),
        ControlFlowEdge(
            branching_step, access_denied_output_step, source_branch=branching_step.BRANCH_DEFAULT
        ),
        ControlFlowEdge(access_granted_output_step, None),
        ControlFlowEdge(access_denied_output_step, None),
    ],
)
conversation = assistant.start_conversation(inputs={NEXT_STEP_NAME_IO: "yes"})
status = conversation.execute()
# conversation.get_last_message().content
# Access granted. Press any key to continue...
# .. end-flow_with_branching::
# .. start-flow_with_tools::
from typing import Annotated

from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import tool

@tool
def compute_square_root(x: Annotated[float, "input number to square"]) -> float:
    """Computes the square root of a number"""
    return x**0.5

step = ToolExecutionStep(tool=compute_square_root)
assistant = create_single_step_flow(step)
conversation = assistant.start_conversation(inputs={"x": 123456789.0})
status = conversation.execute()
print(status.output_values)
# .. end-flow_with_tools
# .. start-agent_in_flow::
from wayflowcore.agent import Agent
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import AgentExecutionStep

code_agent = Agent(
    llm=llm, custom_instruction="Please assist the user by answering their code-related questions"
)

flow = create_single_step_flow(AgentExecutionStep(code_agent))
conversation = flow.start_conversation()
status = conversation.execute()
print(conversation.get_last_message().content)  # Hi! How can I help you?
conversation.append_user_message("Write a simple Python function to sum two numbers")
status = conversation.execute()
print(conversation.get_last_message().content)  # Here's a simple Python function that ...
# .. end-agent_in_flow
# .. start-agent_in_agent::
from wayflowcore.agent import Agent

code_expert_agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their code-related questions",
    agent_id="code_expert_subagent",
    name="code_expert",
    description="Expert agent that can assist with code questions",
)
agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their questions. Call the expert agents at your disposal when needed.",
    agents=[code_expert_agent],
    agent_id="main_agent",
)

conversation = agent.start_conversation()
status = conversation.execute()
print(conversation.get_last_message().content)  # Hi! How can I help you?
conversation.append_user_message("Write a simple Python function to sum two numbers")
status = conversation.execute()
print(conversation.get_last_message().content)  # Here's a simple Python function that ...
# .. end-agent_in_agent
# .. start-flow_in_agent::
from wayflowcore.agent import Agent
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import PromptExecutionStep
from wayflowcore.tools import DescribedFlow

code_reviewing_flow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Here is some code:\n{{input_code}}\n---\nPlease check for potential bugs in the code",
        llm=llm,
    )
)

agent = Agent(
    llm=llm,
    custom_instruction="Please assist the user by answering their code questions. When creating code, use the code reviewing tool to ensure the code validity before answering the user.",
    flows=[
        DescribedFlow(
            flow=code_reviewing_flow,
            name="reviewing_tool",
            description="Tool to check for potential bugs in a given code",
        )
    ],
)

conversation = agent.start_conversation()
status = conversation.execute()
print(conversation.get_last_message().content)  # Hi! How can I help you?
conversation.append_user_message("Write a simple Python function to sum two numbers")
status = conversation.execute()
print(conversation.get_last_message().content)  # Here's a simple Python function that ...
# .. end-flow_in_agent
# .. start-flow_in_flow::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import FlowExecutionStep, OutputMessageStep, PromptExecutionStep

code_generation_subflow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Please answer the following user question:\n{{user_input}}", llm=llm
    )
)
code_reviewing_subflow = create_single_step_flow(
    PromptExecutionStep(
        prompt_template="Here is some code:\n{{code_input}}\n---\nPlease check for potential bugs in the code and propose an improved version of the code",
        llm=llm,
    )
)

code_generation_step = FlowExecutionStep(code_generation_subflow)
code_reviewing_step = FlowExecutionStep(code_reviewing_subflow)
output_step = OutputMessageStep("{{output_content}}")
flow = Flow(
    begin_step_name="code_generation",
    steps={
        "code_generation": code_generation_step,
        "code_reviewing": code_reviewing_step,
        "display_output": output_step,
    },
    control_flow_edges=[
        ControlFlowEdge(code_generation_step, code_reviewing_step),
        ControlFlowEdge(code_reviewing_step, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(
            code_generation_step, PromptExecutionStep.OUTPUT, code_reviewing_step, "code_input"
        ),
        DataFlowEdge(
            code_reviewing_step, PromptExecutionStep.OUTPUT, output_step, "output_content"
        ),
    ],
)

conversation = flow.start_conversation(
    {"user_input": "Write a simple Python function to sum two numbers"}
)
status = conversation.execute()
print(conversation.get_last_message().content)
# .. end-flow_in_flow
# .. start-serialize_simple_assistants::
from wayflowcore.agent import Agent
from wayflowcore.serialization import autodeserialize, serialize

agent = Agent(
    llm, custom_instruction="You are a helpful assistant, please answer the user requests."
)

# saving an assistant to its serialized form
serialized_assistant = serialize(agent)

# with open("path/to/agent_config.yaml", "w") as f:
#     f.write(serialized_assistant)

# loading an assistant from its serialized form
# with open("path/to/agent_config.yaml") as f:
#     serialized_assistant = f.read()

agent = autodeserialize(serialized_assistant)
# .. end-serialize_simple_assistants
# .. start-serialize_assistants_with_tools::
from wayflowcore.agent import Agent
from wayflowcore.serialization import autodeserialize, serialize
from wayflowcore.serialization.context import DeserializationContext
from wayflowcore.tools import register_server_tool, tool


@tool
def say_hello() -> str:
    """Say hello"""
    return "hello"


agent = Agent(
    llm,
    tools=[say_hello],
    custom_instruction="You are a helpful assistant, please answer the user requests.",
)

# saving an assistant to its serialized form
serialized_assistant = serialize(agent)

# with open("path/to/agent_config.yaml", "w") as f:
#     f.write(serialized_assistant)

# loading an assistant from its serialized form
# with open("path/to/agent_config.yaml") as f:
#     serialized_assistant = f.read()

deserialization_context = DeserializationContext()
register_server_tool(say_hello, deserialization_context.registered_tools)
agent = autodeserialize(serialized_assistant, deserialization_context)
# .. end-serialize_assistants_with_tools
# .. start-inputs_provider::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep

output_step = OutputMessageStep("{{message_content}}")
flow = Flow(
    begin_step_name="output_step",
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
)

input_context = {"message_content": "Here is my input context"}
conversation = flow.start_conversation(inputs=input_context)
conversation.execute()
print(conversation.get_last_message().content)
# .. end-inputs_provider
# .. start-tool_contextprovider::
from wayflowcore.contextproviders import ToolContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.steps import OutputMessageStep
from wayflowcore.tools import tool


@tool
def current_time() -> str:
    """Return the current time"""
    from datetime import datetime

    return str(datetime.now())


current_time_contextprovider = ToolContextProvider(current_time, "current_time")
output_step = OutputMessageStep("Current time: {{time}}\nMessage content: {{message_content}}")
flow = Flow(
    begin_step_name="output_step",
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
    data_flow_edges=[
        DataFlowEdge(current_time_contextprovider, "current_time", output_step, "time")
    ],
    context_providers=[current_time_contextprovider],
)

input_context = {"message_content": "Here is my input context"}
conversation = flow.start_conversation(inputs=input_context)
conversation.execute()
print(conversation.get_last_message().content)
# .. end-tool_contextprovider
# .. start-flow_contextprovider::
from wayflowcore.contextproviders import FlowContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import OutputMessageStep

contextual_flow = create_single_step_flow(
    OutputMessageStep(
        message_template="The current time is 2pm.",
        output_mapping={OutputMessageStep.OUTPUT: "time_output"},
    )
)
context_provider = FlowContextProvider(contextual_flow, flow_output_names=["time_output"])
output_step = OutputMessageStep("Last time message: {{time_output_io}}")
flow = Flow(
    begin_step_name="output_step",
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
    data_flow_edges=[DataFlowEdge(context_provider, "time_output", output_step, "time_output_io")],
    context_providers=[context_provider],
)
conversation = flow.start_conversation()
execution_status = conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content)  # Last time message: The current time is 2pm.
# .. end-flow_contextprovider
# .. start-chathistory_contextprovider::
from wayflowcore.contextproviders import ChatHistoryContextProvider
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageList
from wayflowcore.steps import OutputMessageStep

context_provider = ChatHistoryContextProvider(
    n=2,  # will retrieve the last 2 messages
    output_name="history",
)
output_step = OutputMessageStep("Chat history number: {{history}}")
flow = Flow(
    begin_step_name="output_step",
    steps={"output_step": output_step},
    control_flow_edges=[ControlFlowEdge(output_step, None)],
    context_providers=[context_provider],
)
message_list = MessageList([Message(f"Message {i+1}") for i in range(5)])
conversation = flow.start_conversation(messages=message_list)
execution_status = conversation.execute()
print(conversation.get_last_message().content)
# Chat history number: USER >> Message 4
# USER >> Message 5
# .. end-chathistory_contextprovider
# .. start-context_with_variables::
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.property import FloatProperty
from wayflowcore.steps import OutputMessageStep, VariableReadStep, ToolExecutionStep, VariableWriteStep
from wayflowcore.variable import Variable
from wayflowcore.tools import tool

float_variable = Variable(
    name="float_variable",
    type=FloatProperty(),
    description="a float variable",
    default_value=5.0,
)

read_step_1 = VariableReadStep(variable=float_variable)


@tool(description_mode="only_docstring")
def triple_number(x: float) -> float:
    "Tool that triples a number"
    return x*3

triple_step = ToolExecutionStep(tool=triple_number)

write_step = VariableWriteStep(variable=float_variable)
read_step_2 = VariableReadStep(variable=float_variable)
output_step = OutputMessageStep("The variable is {{ variable }}")

flow = Flow(
    begin_step=read_step_1,
    control_flow_edges=[
        ControlFlowEdge(read_step_1, triple_step),
        ControlFlowEdge(triple_step, write_step),
        ControlFlowEdge(write_step, read_step_2),
        ControlFlowEdge(read_step_2, output_step),
        ControlFlowEdge(output_step, None),
    ],
    data_flow_edges=[
        DataFlowEdge(read_step_1, VariableReadStep.VALUE, triple_step, "x"),
        DataFlowEdge(triple_step, ToolExecutionStep.TOOL_OUTPUT, write_step, VariableWriteStep.VALUE),
        DataFlowEdge(read_step_2, VariableReadStep.VALUE, output_step, "variable")
    ],
    variables=[float_variable]
)

conversation = flow.start_conversation()
status = conversation.execute()
print(conversation.get_last_message().content)
# .. end-context_with_variables
