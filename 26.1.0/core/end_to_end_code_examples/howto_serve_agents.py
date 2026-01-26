# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Serve Agents with WayFlow
# -------------------------------------------------------

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
# python howto_serve_agents.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


import os


# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)


# %%[markdown]
## Define the agent

# %%
from wayflowcore.agent import Agent
from wayflowcore.tools.toolhelpers import DescriptionMode, tool

@tool(description_mode=DescriptionMode.ONLY_DOCSTRING)
def get_policy(topic: str) -> str:
    """Return a short HR policy excerpt."""
    return f"{topic} is available. Check the HR portal for details."


agent = Agent(
    llm=llm,
    tools=[get_policy],
    custom_instruction="""You are an HR assistant.
- Call tools when you need facts.""",
)


# %%[markdown]
## Export agent spec

# %%
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader

spec = AgentSpecExporter().to_json(agent)
tool_registry = {"get_policy": get_policy}
agent_from_spec = AgentSpecLoader(tool_registry=tool_registry).load_json(spec)


# %%[markdown]
## Serve in memory

# %%
from wayflowcore.agentserver.server import OpenAIResponsesServer

server = OpenAIResponsesServer()
server.serve_agent("hr-assistant", agent)
app = server.get_app()

if __name__ == "__main__":
    server.run(host="127.0.0.1", port=3000)



# %%[markdown]
## Call the server

# %%
from wayflowcore.models import OpenAIAPIType, OpenAICompatibleModel

client = OpenAICompatibleModel(
    model_id="hr-assistant",
    base_url="http://127.0.0.1:3000",
    api_type=OpenAIAPIType.RESPONSES,
)
completion = client.generate("Summarize the vacation policy.")
print(completion.message.content)


# %%[markdown]
## Persistent storage

# %%
from wayflowcore.agentserver import ServerStorageConfig
from wayflowcore.datastore.postgres import (
    WithoutTlsPostgresDatabaseConnectionConfig,
    PostgresDatabaseDatastore,
)

storage_config = ServerStorageConfig(table_name="assistant_conversations")

connection_config = WithoutTlsPostgresDatabaseConnectionConfig(
    user=os.environ.get("PG_USER", "postgres"),
    password=os.environ.get("PG_PASSWORD", "password"),
    url=os.environ.get("PG_HOST", "localhost:5432"),
)

datastore = PostgresDatabaseDatastore(
    schema=storage_config.to_schema(),
    connection_config=connection_config,
)

persistent_server = OpenAIResponsesServer(
    storage=datastore,
    storage_config=storage_config,
)
persistent_server.serve_agent("hr-assistant", agent)


# %%[markdown]
## Add fastapi security

# %%
import secrets
from fastapi import Request, status
from fastapi.responses import JSONResponse

API_TOKEN = os.environ.get("WAYFLOW_SERVER_TOKEN", "change-me")

secured_app = server.get_app()

@secured_app.middleware("http")
async def require_bearer_token(request: Request, call_next):
    auth_header = request.headers.get("authorization", "")
    expected_header = f"Bearer {API_TOKEN}"
    if not secrets.compare_digest(auth_header, expected_header):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid bearer token"},
        )
    return await call_next(request)
