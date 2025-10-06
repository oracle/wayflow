# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# WayFlow Code Example - How to connect MCP tools to Assistants
# -------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_mcp.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
##Create a MCP Server

# %%
from mcp.server.fastmcp import FastMCP

PAYSLIPS = [
    {
        "Amount": 7612,
        "Currency": "USD",
        "PeriodStartDate": "2025/05/15",
        "PeriodEndDate": "2025/06/15",
        "PaymentDate": "",
        "DocumentId": 2,
        "PersonId": 2,
    },
    {
        "Amount": 5000,
        "Currency": "CHF",
        "PeriodStartDate": "2024/05/01",
        "PeriodEndDate": "2024/06/01",
        "PaymentDate": "2024/05/15",
        "DocumentId": 1,
        "PersonId": 1,
    },
    {
        "Amount": 10000,
        "Currency": "EUR",
        "PeriodStartDate": "2025/06/15",
        "PeriodEndDate": "2025/10/15",
        "PaymentDate": "",
        "DocumentsId": 3,
        "PersonId": 3,
    },
]

def create_server(host: str, port: int):
    """Create and configure the MCP server"""
    server = FastMCP(
        name="Example MCP Server",
        instructions="A MCP Server.",
        host=host,
        port=port,
    )

    @server.tool(description="Return session details for the current user")
    def get_user_session():
        return {
            "PersonId": "1",
            "Username": "Bob.b",
            "DisplayName": "Bob B",
        }

    @server.tool(description="Return payslip details for a given PersonId")
    def get_payslips(PersonId: int):
        return [payslip for payslip in PAYSLIPS if payslip["PersonId"] == int(PersonId)]

    return server


def start_mcp_server() -> str:
    host: str = "localhost"
    port: int = 8080
    server = create_server(host=host, port=port)
    server.run(transport="sse")

    return f"http://{host}:{port}/sse"

# mcp_server_url = start_mcp_server() # <--- Move the code above to a separate file then uncomment

# %%[markdown]
## Imports for this guide

# %%
from wayflowcore.executors.executionstatus import FinishedStatus, UserMessageRequestStatus
from wayflowcore.agent import Agent
from wayflowcore.mcp import MCPTool, MCPToolBox, SSETransport, enable_mcp_without_auth
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep

mcp_server_url = f"http://localhost:8080/sse" # change to your own URL
# We will see below how to connect a specific tool to an assistant, e.g.
MCP_TOOL_NAME = "get_user_session"
# And see how to build an agent that can answer questions, e.g.
USER_QUERY = "What was the payment date of the last payslip for the current user?"

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Connecting an agent to the MCP server

# %%
enable_mcp_without_auth() # <--- See https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization#security-considerations
mcp_client = SSETransport(url=mcp_server_url)
mcp_toolbox = MCPToolBox(client_transport=mcp_client)

assistant = Agent(
    llm=llm,
    tools=[mcp_toolbox]
)


# %%[markdown]
## Running the agent

# %%
# With a linear conversation
conversation = assistant.start_conversation()

conversation.append_user_message(USER_QUERY)
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")

# then continue the conversation

# %%[markdown]
## Running with an execution loop

# %%
def run_agent_in_command_line(assistant: Agent):
    inputs = {}
    conversation = assistant.start_conversation(inputs)

    while True:
        status = conversation.execute()
        if isinstance(status, FinishedStatus):
            break
        assistant_reply = conversation.get_last_message()
        if assistant_reply is not None:
            print("\nAssistant >>>", assistant_reply.content)
        user_input = input("\nUser >>> ")
        conversation.append_user_message(user_input)

# run_agent_in_command_line(assistant)
# ^ uncomment and execute

# %%[markdown]
## Connecting a flow to the MCP server

# %%
mcp_tool = MCPTool(
    name=MCP_TOOL_NAME,
    client_transport=mcp_client
)

assistant = Flow.from_steps([
    ToolExecutionStep(name="mcp_tool_step", tool=mcp_tool)
])

# %%[markdown]
## Running the flow

# %%
inputs = {}
conversation = assistant.start_conversation(inputs=inputs)

status = conversation.execute()
if isinstance(status, FinishedStatus):
    flow_outputs = status.output_values
    print(f"---\nFlow outputs >>> {flow_outputs}\n---")
else:
    print(
        f"Invalid execution status, expected FinishedStatus, received {type(status)}"
    )

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Flow = AgentSpecLoader().load_json(serialized_assistant)
