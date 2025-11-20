# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to Do Remote API Calls with Potentially Expiring Tokens
# --------------------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==25.4" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_remote_tool_expired_token.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.




# %%[markdown]
## Mock server

# %%
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.exceptions import HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

async def protected_endpoint(request: Request):
    user = request.query_params.get("user")
    if user is None:
        return JSONResponse({"detail": "Missing 'user' query parameter."}, status_code=400)

    authorization = request.headers.get("authorization")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]
    if token == "valid-token":
        return JSONResponse({"response": f"Success! You are authenticated, {user}."})
    elif token == "expired-token":
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token', error_description='The access token expired'"},
        )
    else:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer error='invalid_token'"},
        )

app = Starlette(debug=True, routes=[
    Route("/protected", protected_endpoint)
])

# Start the server: Uncomment these lines
# import uvicorn
# uvicorn.run(app, host="localhost", port=8001)

# %%[markdown]
## Import libraries

# %%
from wayflowcore.property import StringProperty
from wayflowcore.tools import ClientTool
from wayflowcore.steps import (
    StartStep,
    CompleteStep,
    ApiCallStep,
    ToolExecutionStep
)
from wayflowcore.flow import Flow
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge

# %%[markdown]
## Configure your LLM

# %%
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# %%[markdown]
## Variable names

# %%
TOKEN = "token"
USER = "user"

# %%[markdown]
## Defining steps

# %%
# 1. Start step
start_step = StartStep(
    name="start_step",
    input_descriptors=[StringProperty(name=USER)]
)

# 2. Get token step
# A client tool to get token at client side
get_token_tool = ClientTool(
    name="get_token_tool",
    description="Get token from user",
    input_descriptors=[],
    output_descriptors=[StringProperty(name=TOKEN)]
)

# A step gets token by using the get_token_tool
get_token_tool_step = ToolExecutionStep(
    name="get_token_step",
    tool=get_token_tool,
)

# 3. Call API step
call_api_step = ApiCallStep(
    name="call_api_step",
    url="http://localhost:8003/protected",
    allow_insecure_http=True,
    method="GET",
    headers={"Authorization": "Bearer {{ token }}"},
    params={"user": "{{ user }}"},
)

# 4. End step
end_step = CompleteStep(name="end_step")

# %%[markdown]
## Defining flow

# %%
remote_call_flow = Flow(
    name="Remote Call Flow",
    description="Perform a call to a remote endpoint given the `user` parameter.",
    begin_step=start_step,
    control_flow_edges=[
        ControlFlowEdge(source_step=start_step, destination_step=get_token_tool_step),
        ControlFlowEdge(source_step=get_token_tool_step, destination_step=call_api_step),
        ControlFlowEdge(source_step=call_api_step, destination_step=end_step),
    ],
    data_flow_edges=[
        DataFlowEdge(
            source_step=start_step,
            source_output=USER,
            destination_step=call_api_step,
            destination_input=USER,
        ),
        DataFlowEdge(
            source_step=get_token_tool_step,
            source_output=TOKEN,
            destination_step=call_api_step,
            destination_input=TOKEN,
        ),
    ]
)

# %%[markdown]
## Testing flow

# %%
from wayflowcore.executors.executionstatus import ToolRequestStatus
from wayflowcore.tools import ToolResult

inputs = {"user": "alice"}
conversation = remote_call_flow.start_conversation(inputs=inputs)

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error

status = conversation.execute()
if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Need to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )

# %%[markdown]
## Defining agent

# %%
from wayflowcore.agent import Agent

agent = Agent(
    name="Agent",
    flows=[remote_call_flow],
    llm=llm,
)

# %%[markdown]
## Testing agent

# %%
from wayflowcore.executors.executionstatus import ToolRequestStatus, UserMessageRequestStatus
from wayflowcore.tools import ToolResult

conversation = agent.start_conversation()
conversation.append_user_message("Call the remote tool with user `alice`")

auth_token = "valid-token"
# auth_token = "expired-token" # This will raise error
status = conversation.execute()

if isinstance(status, ToolRequestStatus): # Asking for token
    tool_request_id = status.tool_requests[0].tool_request_id # Needs to be adapted when using parallel tool calling (not the case here)
    conversation.append_tool_result(ToolResult(content=auth_token, tool_request_id=tool_request_id))
else:
    print(
        f"Invalid execution status, expected ToolRequestStatus, received {type(status)}"
    )

status = conversation.execute() # Resuming the conversation after the client provided the auth token
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(
        f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}"
    )

# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

assistant: Agent = AgentSpecLoader().load_json(serialized_assistant)
