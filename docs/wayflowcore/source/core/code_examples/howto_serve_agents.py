# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: WayFlow Code Example - How to Serve Agents with WayFlow

import os

# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore

# .. start-##_Define_the_agent
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
# .. end-##_Define_the_agent

# .. start-##_Export_agent_spec
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader

spec = AgentSpecExporter().to_json(agent)
tool_registry = {"get_policy": get_policy}
agent_from_spec = AgentSpecLoader(tool_registry=tool_registry).load_json(spec)
# .. end-##_Export_agent_spec

# .. start-##_Serve_in_memory
from wayflowcore.agentserver.server import OpenAIResponsesServer

server = OpenAIResponsesServer()
server.serve_agent("hr-assistant", agent)
app = server.get_app()

if __name__ == "__main__":
    server.run(host="127.0.0.1", port=3000)
# .. end-##_Serve_in_memory

from wayflowcore.models import OpenAICompatibleModel  # docs-skiprow
from wayflowcore.models import LlmCompletion  # docs-skiprow
from wayflowcore.messagelist import Message  # docs-skiprow
OpenAICompatibleModel.generate = lambda *args, **kwargs: LlmCompletion(message=Message(content="Vacation", role='assistant'), token_usage=None)  # docs-skiprow

# .. start-##_Call_the_server
from wayflowcore.models import OpenAIAPIType, OpenAICompatibleModel

client = OpenAICompatibleModel(
    model_id="hr-assistant",
    base_url="http://127.0.0.1:3000",
    api_type=OpenAIAPIType.RESPONSES,
)
completion = client.generate("Summarize the vacation policy.")
print(completion.message.content)
# .. end-##_Call_the_server

"""  # docs-skiprow
# .. start-##_Persistent_storage
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
# .. end-##_Persistent_storage
"""  # docs-skiprow

# .. start-##_Add_fastapi_security
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
# .. end-##_Add_fastapi_security
