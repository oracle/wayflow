<a id="top-howtoserveagents"></a>

# How to Serve Agents with WayFlow![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Serve Agents how-to script](../end_to_end_code_examples/howto_serve_agents.py)

#### Prerequisites
This guide assumes familiarity with:

- [Agents](../tutorials/basic_agent.md)
- [Datastores](howto_datastores.md)
- [WayFlow Tools](../api/tools.md)

WayFlow can host agents behind an
[OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) compatible
endpoint. Reliable serving unlocks predictable SLAs, reusable state, and consistent security, while
letting clients keep using familiar OpenAI SDKs. Start with an in-memory setup for quick
experiments, then add persistence to reuse conversation state and layer FastAPI security controls
that fit your environment.

## Create an agent to host

WayFlow supports several LLM API providers.
Select an LLM from the options below:




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

#### NOTE
API keys should not be stored anywhere in the code. Use environment variables or tools such as [python-dotenv](https://pypi.org/project/python-dotenv/).

Then, create or reuse an agent you want to serve. You can define it as code:

```python
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
```

API Reference: [Agent](../api/agent.md#agent) | [Tool](../api/tools.md#servertool)

## Export and reload agent specs

Save your agent as an Agent Spec so you can deploy from a config file or ship it to another team.
Reloading requires a `tool_registry` that maps tool names back to callables.

```python
from wayflowcore.agentspec import AgentSpecExporter, AgentSpecLoader

spec = AgentSpecExporter().to_json(agent)
tool_registry = {"get_policy": get_policy}
agent_from_spec = AgentSpecLoader(tool_registry=tool_registry).load_json(spec)
```

API Reference: [AgentSpecExporter](../api/agentspec.md#agentspecexporter) | [AgentSpecLoader](../api/agentspec.md#agentspecloader)

## Run an in-memory Responses API server

Expose the agent with [OpenAIResponsesServer](../api/agentserver.md#openairesponsesserver). The server mounts
`/v1/responses` and `/v1/models` endpoints that work with the official `openai` SDK or
[OpenAICompatibleModel](../api/llmmodels.md#openaicompatiblemodel).

```python
from wayflowcore.agentserver.server import OpenAIResponsesServer

server = OpenAIResponsesServer()
server.serve_agent("hr-assistant", agent)
app = server.get_app()

if __name__ == "__main__":
    server.run(host="127.0.0.1", port=3000)
```

You can now call the server with an OpenAI-compatible client:

```python
from wayflowcore.models import OpenAIAPIType, OpenAICompatibleModel

client = OpenAICompatibleModel(
    model_id="hr-assistant",
    base_url="http://127.0.0.1:3000",
    api_type=OpenAIAPIType.RESPONSES,
)
completion = client.generate("Summarize the vacation policy.")
print(completion.message.content)
```

API Reference: [OpenAIResponsesServer](../api/agentserver.md#openairesponsesserver)

## Persist conversations with datastores

To reuse conversation history across requests or server restarts, attach a datastore. Use
[ServerStorageConfig](../api/agentserver.md#serverstorageconfig) to define table and column names, then pass a
supported [Datastore](../api/datastores.md#datastore) implementation such as
[PostgresDatabaseDatastore](../api/datastores.md#postgresdatabasedatastore) or
[OracleDatabaseDatastore](../api/datastores.md#oracledatabasedatastore).

```python
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
```

In production, create the table beforehand or run `wayflow serve` with `--setup-datastore yes`
to let WayFlow prepare it when the backend supports schema management. It will not override any
existing table, so you will need to first delete any existing table to allow wayflow to set it up
for you.

API Reference: [ServerStorageConfig](../api/agentserver.md#serverstorageconfig) | [Datastore](../api/datastores.md#datastore)

## Add FastAPI security controls

[OpenAIResponsesServer](../api/agentserver.md#openairesponsesserver) gives you the FastAPI `app` instance so
you can stack your own middleware, dependencies, or routers. This example enforces a simple bearer
token check.

```python
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
```

Replace the token check with your own authentication handler (OAuth2, mTLS validation, signed
cookies, IP filtering, etc.) and add rate limiting or CORS rules as needed.

API Reference: [OpenAIResponsesServer](../api/agentserver.md#openairesponsesserver)

## Use the CLI

You can also serve an agent spec file directly from the CLI:

```bash
wayflow serve \
  --api openai-responses \
  --agent-config hr_agent.json \
  --agent-id hr-assistant \
  --server-storage postgres-db \
  --datastore-connection-config postgres_conn.yaml \
  --setup-datastore yes
```

Pass `--tool-registry` to load your own tools, swap `--server-storage` to `oracle-db` or
`in-memory`, and set `--server-storage-config` to override column names. See the [API reference](../api/agentserver.md#cliwayflowreference) for a
complete description of all arguments.

#### WARNING
This CLI does not implement any security features; use it only for development or inside an
already-secured environment such as OCI agent deployments. Missing controls include:

- **Authentication**: No verification of caller identity—anyone with network access can invoke the agent.
- **Authorization**: No role or permission checks to restrict which users can access specific agents or actions.
- **Rate limiting**: No protection against excessive requests that could exhaust resources or incur runaway costs.
- **TLS/HTTPS**: Traffic is unencrypted by default, risking interception of sensitive prompts and responses.

For production deployments, wrap the server with an API gateway, reverse proxy, or custom FastAPI middleware that enforces these controls.

## Next steps
- [Use Agents in Flows](howto_agents_in_flows.md)
- [Connect Assistants to Your Data](howto_datastores.md)
- [Build Assistants with Tools](howto_build_assistants_with_tools.md)

## Full code

Click on the card at the [top of this page](#top-howtoserveagents) to download the full code
for this guide or copy the code below.

```python
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
# pip install "wayflowcore==26.1.1" 
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
```
