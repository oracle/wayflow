# Agent Server

This page covers the components used to expose WayFlow agents through different protocols.

## Server application

<a id="openairesponsesserver"></a>

### *class* wayflowcore.agentserver.server.OpenAIResponsesServer(agents=None, storage=None, storage_config=None)

FastAPI application for task management with AI agents.

Public-facing server for exposing an Agent or Flow via the OpenAI Responses protocol.
The assistant can be queried via the OpenAI Responses protocol at the provided URL.

* **Parameters:**
  * **agents** (`Optional`[`Dict`[`str`, [`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)]]) – Dictionary storing the agent_ids and agents to serve. The model_id will be the one
    clients will have to mention in request.model to choose which agent to use for their request.
  * **storage** (`Optional`[[`Datastore`](datastores.md#wayflowcore.datastore.Datastore)]) – Datastore for server persistence. Needs to have the proper table and columns as specified
    in the storage_config.
  * **storage_config** (`Optional`[[`ServerStorageConfig`](#wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig)]) – Cch will not guarantee persistence of data across runs.

#### get_app()

Get the FastAPI application instance.

#### NOTE
For production environments, you should use this function to get the FastAPI
application that implements the OpenAI Responses endpoints, and then add your
own security/authentication layer on top of it.

Consider adding:

- **HTTPS/TLS**: Terminate TLS at a reverse proxy or load balancer, or use
  `uvicorn --ssl-keyfile` and `--ssl-certfile`.
- **Rate limiting**: Use `slowapi` or an API gateway to prevent abuse.
- **CORS**: Configure `CORSMiddleware` if serving browser-based clients.
- **Request validation**: Add input size limits and content-type checks.

### Example

Here is a very simple example of how to implement token-based authentication:

```pycon
>>> import os
>>> import secrets
>>> from fastapi import Request, status
>>> from fastapi.responses import JSONResponse
>>> API_TOKEN = os.environ.get("WAYFLOW_SERVER_TOKEN", "change-me")
>>>
>>> app = server.get_app()  
>>>
>>> @app.middleware("http")  
... async def require_bearer_token(request: Request, call_next):
...     auth_header = request.headers.get("authorization", "")
...     expected_header = f"Bearer {API_TOKEN}"
...     if not secrets.compare_digest(auth_header, expected_header):
...         return JSONResponse(
...             status_code=status.HTTP_401_UNAUTHORIZED,
...             content={"detail": "Missing or invalid bearer token"},
...         )
...     return await call_next(request)
```

and then run `uvicorn main:app --host 0.0.0.0 --port 8000`.

* **Returns:**
  A FastAPI application that implements the OpenAI Responses endpoints.
* **Return type:**
  fastapi.FastAPI

#### run(host='127.0.0.1', port=8000, api_key=None)

Starts the server and serves all the registered agents in a blocking way.

* **Parameters:**
  * **host** (`str`) – Host to serve the server.
  * **port** (`int`) – Port to expose the server.
  * **api_key** (`Optional`[`str`]) – A key that will be required to authenticate the requests. It needs to be provided as a bearer token.
* **Return type:**
  `None`

#### serve_agent(agent_id, agent)

Adds an agent to the service.

* **Parameters:**
  * **agent_id** (`str`) – Name of the agent to serve.
  * **agent** ([`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)) – The agent to serve.
* **Return type:**
  `None`

<a id="a2aserver"></a>

### *class* wayflowcore.agentserver.server.A2AServer(storage_config=None)

A server for exposing a WayFlow conversational component via the A2A protocol.

The A2AServer wraps around an internal A2AApp (a Starlette application)
to handle HTTP-based communication between external A2A clients and an agent.
It automatically serves the agent card and task endpoints.

The assistant can be queried via the A2A protocol at the provided URL.

This server supports **server** tools in the served assistant.
In A2A, the WayFlow ToolRequest and ToolResult are represented as the DataPart
object.

A DataPart contains:
: - **metadata**: a dictionary with a type key indicating whether this
    part represents a ToolRequest or a ToolResult.
  - **data**: a dictionary with the actual fields of the ToolRequest
    or ToolResult.

* **Parameters:**
  **storage_config** (`Optional`[[`ServerStorageConfig`](#wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig)]) – Config for the storage to save the conversations. If not provided, the default storage with InMemoryDatastore will be used.

#### get_app(host='127.0.0.1', port=8000)

* **Return type:**
  `A2AApp`
* **Parameters:**
  * **host** (*str*)
  * **port** (*int*)

#### run(host='127.0.0.1', port=8000, api_key=None)

Starts the server and serve the assistant.

* **Parameters:**
  * **host** (`str`) – Host to serve the server.
  * **port** (`int`) – Port to expose the server.
  * **api_key** (`Optional`[`str`]) – A key that will be required to authenticate the requests. It needs to be provided as a bearer token.
* **Return type:**
  `None`

#### serve_agent(agent, url=None)

Specifies the agent to be served.

* **Parameters:**
  * **agent** ([`ConversationalComponent`](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent)) – The agent to be served which can be any conversational component in WayFlow (e.g Agent, Flow, Swarm, etc.).
  * **url** (`Optional`[`str`]) – The public address the agent is hosted at.
* **Return type:**
  `None`

<a id="serverstorageconfig"></a>

### *class* wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig(datastore=None, table_name='conversations', agent_id_column_name='agent_id', conversation_id_column_name='conversation_id', turn_id_column_name='turn_id', created_at_column_name='created_at', conversation_turn_state_column_name='conversation_turn_state', is_last_turn_column_name='is_last_turn', extra_metadata_column_name='extra_metadata', max_retention=None)

Configuration for server storage management.

* **Parameters:**
  * **datastore** ([*Datastore*](datastores.md#wayflowcore.datastore.Datastore) *|* *None*)
  * **table_name** (*str*)
  * **agent_id_column_name** (*str*)
  * **conversation_id_column_name** (*str*)
  * **turn_id_column_name** (*str*)
  * **created_at_column_name** (*str*)
  * **conversation_turn_state_column_name** (*str*)
  * **is_last_turn_column_name** (*str*)
  * **extra_metadata_column_name** (*str*)
  * **max_retention** (*int* *|* *None*)

#### agent_id_column_name *: `str`* *= 'agent_id'*

Name of the column where the agent id of the state is stored

#### conversation_id_column_name *: `str`* *= 'conversation_id'*

Name of the column where the id of the conversation is stored

#### conversation_turn_state_column_name *: `str`* *= 'conversation_turn_state'*

Name of the column where the serialized state of turn is store

#### created_at_column_name *: `str`* *= 'created_at'*

Name of the column where the creation timestamp is stored

#### datastore *: `Optional`[[`Datastore`](datastores.md#wayflowcore.datastore.Datastore)]* *= None*

Datastore to use for persistence

#### extra_metadata_column_name *: `str`* *= 'extra_metadata'*

Name of the column where the server stores its own attributes

#### is_last_turn_column_name *: `str`* *= 'is_last_turn'*

Name of the column where the marker for the most recent turn of a given conversation is stored

#### max_retention *: `Optional`[`int`]* *= None*

Number of seconds for which to retain a conversation before discarding it

#### table_name *: `str`* *= 'conversations'*

Name of the table in which the states are stored

#### to_schema()

* **Return type:**
  `Dict`[`str`, [`Entity`](datastores.md#wayflowcore.datastore.Entity)]

#### turn_id_column_name *: `str`* *= 'turn_id'*

Name of the column where the turn id / response id is stored

### wayflowcore.agentserver.app.create_server_app(api, agents, storage, storage_config)

* **Return type:**
  `Union`[[`OpenAIResponsesServer`](#wayflowcore.agentserver.server.OpenAIResponsesServer), [`A2AServer`](#wayflowcore.agentserver.server.A2AServer)]
* **Parameters:**
  * **api** (*Literal* *[* *'openai-responses'* *,*  *'a2a'* *]*)
  * **agents** (*Dict* *[**str* *,* [*ConversationalComponent*](conversation.md#wayflowcore.conversationalcomponent.ConversationalComponent) *]*)
  * **storage** ([*Datastore*](datastores.md#wayflowcore.datastore.Datastore))
  * **storage_config** ([*ServerStorageConfig*](#wayflowcore.agentserver.serverstorageconfig.ServerStorageConfig))

## CLI Reference

<a id="cliwayflowreference"></a>

WayFlow command line interface.

```default
usage: wayflow [-h] {serve} ...
```

### Positional Arguments
* `command` — 

  Possible choices: serve

### Sub-commands

#### serve

Launch a WayFlow server hosting agents with the selected API protocol.

```default
wayflow serve [-h] [--api {openai-responses,a2a}] [--agent-config AGENT_CONFIG [AGENT_CONFIG ...]] [--agent-id AGENT_ID [AGENT_ID ...]] [--port PORT]
              [--host HOST] [--tool-registry TOOL_REGISTRY] [--server-storage {in-memory,oracle-db,postgres-db}]
              [--server-storage-config SERVER_STORAGE_CONFIG] [--datastore-connection-config DATASTORE_CONNECTION_CONFIG] [--setup-datastore {no,yes}]
              [--api-key API_KEY]
```

##### Named Arguments
* `--api` — 

  Possible choices: openai-responses, a2a

  Protocol to expose (default: openai-responses).

  Default: `'openai-responses'`
* `--agent-config` — 

  Path to the agent specification file (default: agent.json).
* `--agent-id` — 

  Identifier used by clients to select the hosted agent (default: my-agent).
* `--port` — 

  Port to bind the server to (default: 3000).

  Default: `3000`
* `--host` — 

  Host interface to bind to (default: 127.0.0.1).

  Default: `'127.0.0.1'`
* `--tool-registry` — 

  Optional path to a Python module exposing a tool_registry dictionary for agent server tools.
* `--server-storage` — 

  Possible choices: in-memory, oracle-db, postgres-db

  Persistence backend for conversations (default: in-memory).

  Default: `'in-memory'`
* `--server-storage-config` — 

  Optional YAML file overriding ServerStorageConfig defaults.
* `--datastore-connection-config` — 

  YAML file containing the type of connection to use and its configuration.
  For example: type: TlsPostgresDatabaseConnectionConfig
  user: my_user
  password: my_password
  url:localhost:7777
* `--setup-datastore` — 

  Possible choices: no, yes

  Whether to create or reset datastore tables when supported (default: no). It will NOT delete any existing table, you should do it first.

  Default: `'no'`
* `--api-key` — 

  Optional api key to add an authentication layer to the server. This API_KEY will be required on requests as a bearer token in the headers: {‘authorization’: ‘Bearer SOME_FAKE_SECRET’}
