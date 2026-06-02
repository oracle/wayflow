<a id="top-howtoretryconfiguration"></a>

# How to Configure Retries on LLMs and Remote Components![python-icon](_static/icons/python-icon.svg) Download Python Script

Python script/notebook for this guide.

[Retry configuration how-to script](../end_to_end_code_examples/howto_retry_configuration.py)

#### Prerequisites
This guide assumes familiarity with:

- [LLM configuration](llm_from_different_providers.md)
- [Using agents](agents.md)
- [Doing remote API calls](howto_remote_tool_expired_token.md)

WayFlow remote components now share the same [RetryPolicy](../api/retries.md#retrypolicy) object.
You can use it to configure retry timing and per-attempt request timeouts consistently across
[LLMs](../api/llmmodels.md#id1), [embedding models](../api/embeddingmodels.md#id1),
[ApiCallStep](../api/flows.md#apicallstep), [RemoteTool](../api/tools.md#remotetool),
remote MCP transports such as [StreamableHTTPTransport](../api/tools.md#streamablehttptransport),
[OciAgent](../api/agent.md#ociagent), and [A2AAgent](../api/agent.md#a2aagent).

## Create a Retry Policy

Start by defining a `RetryPolicy` with the retry behavior you want to reuse.

```python
from wayflowcore.retrypolicy import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=3,
    request_timeout=20.0,
    initial_retry_delay=1.0,
    max_retry_delay=8.0,
    backoff_factor=2.0,
    jitter="full_and_equal_for_throttle",
)
```

## Apply the Policy to Remote Components

You can then pass the same retry policy to any supported remote component.

```python
from wayflowcore.models import OpenAICompatibleModel

llm = OpenAICompatibleModel(
    model_id="my-model",
    base_url="https://example.com",
    retry_policy=retry_policy,
)
```

```python
from wayflowcore.steps import ApiCallStep
from wayflowcore.tools import RemoteTool

ORDER_API_BASE_URL = "https://example.com/orders"

api_step = ApiCallStep(
    name="fetch_order_step",
    url=ORDER_API_BASE_URL,
    method="POST",
    retry_policy=retry_policy,
)

remote_tool = RemoteTool(
    name="fetch_order",
    description="Fetch an order from a remote API.",
    url=ORDER_API_BASE_URL + "/{{ order_id }}",  # keep the base URL fixed and template only the path parameter
    method="GET",
    retry_policy=retry_policy,
    url_allow_list=[ORDER_API_BASE_URL],
)
```

```python
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.mcp import StreamableHTTPTransport
from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal
from wayflowcore.ociagent import OciAgent

a2a_agent = A2AAgent(
    agent_url="https://example.com/a2a",
    connection_config=A2AConnectionConfig(verify=False, retry_policy=retry_policy),
)

oci_agent = OciAgent(
    agent_endpoint_id="ocid1.agentendpoint.oc1..example",
    client_config=OCIClientConfigWithInstancePrincipal(service_endpoint="https://example.com"),
    retry_policy=retry_policy,
)

transport = StreamableHTTPTransport(
    url="https://example.com/mcp",
    retry_policy=retry_policy,
)
```

WayFlow applies `request_timeout` per attempt. Retries are limited to transient failures such
as configured recoverable status codes, eligible `5xx` responses, and connection errors.
Authentication failures, validation failures, and TLS/certificate verification failures are not retried.

## Agent Spec Exporting/Loading

You can export a configuration that includes the retry policy to Agent Spec using the `AgentSpecExporter`.

```python
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(oci_agent)
```

Here is what the **Agent Spec representation will look like ↓**

<details>
<summary>Details</summary>

JSON

```json
{
  "component_type": "OciAgent",
  "id": "d3ec0b4c-ab23-4555-82e8-3dda8a831fb2",
  "name": "oci_agent_5008210d__auto",
  "description": "",
  "metadata": {
    "__metadata_info__": {}
  },
  "inputs": [],
  "outputs": [],
  "agent_endpoint_id": "ocid1.agentendpoint.oc1..example",
  "client_config": {
    "component_type": "OciClientConfigWithInstancePrincipal",
    "id": "45384ec0-c3c7-4d55-a37e-f8e28d8027e5",
    "name": "oci_client_config",
    "description": null,
    "metadata": {},
    "service_endpoint": "https://example.com",
    "auth_type": "INSTANCE_PRINCIPAL"
  },
  "retry_policy": {
    "max_attempts": 3,
    "request_timeout": 20.0,
    "initial_retry_delay": 1.0,
    "max_retry_delay": 8.0,
    "backoff_factor": 2.0,
    "jitter": "full_and_equal_for_throttle",
    "service_error_retry_on_any_5xx": true,
    "recoverable_statuses": {
      "409": [],
      "429": []
    }
  },
  "agentspec_version": "26.2.0"
}
```

YAML

```yaml
component_type: OciAgent
id: d3ec0b4c-ab23-4555-82e8-3dda8a831fb2
name: oci_agent_5008210d__auto
description: ''
metadata:
  __metadata_info__: {}
inputs: []
outputs: []
agent_endpoint_id: ocid1.agentendpoint.oc1..example
client_config:
  component_type: OciClientConfigWithInstancePrincipal
  id: 45384ec0-c3c7-4d55-a37e-f8e28d8027e5
  name: oci_client_config
  description: null
  metadata: {}
  service_endpoint: https://example.com
  auth_type: INSTANCE_PRINCIPAL
retry_policy:
  max_attempts: 3
  request_timeout: 20.0
  initial_retry_delay: 1.0
  max_retry_delay: 8.0
  backoff_factor: 2.0
  jitter: full_and_equal_for_throttle
  service_error_retry_on_any_5xx: true
  recoverable_statuses:
    '409': []
    '429': []
agentspec_version: 26.2.0
```

</details>

You can then load the configuration back with the `AgentSpecLoader`.

```python
from wayflowcore.agentspec import AgentSpecLoader

loaded_agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
```

## Next steps

Now that you have learned how to configure retries on remote components, you may proceed to
[How to Use OCI Generative AI Agents](howto_ociagent.md) or
[How to Connect to A2A Agents](howto_a2aagent.md).

## Full code

Click on the card at the [top of this page](#top-howtoretryconfiguration) to download the full code for this guide or copy the code below.

```python
# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Configure Retries on Remote Components
# ------------------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1.2" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_retry_configuration.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Create a retry policy

# %%
from wayflowcore.retrypolicy import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=3,
    request_timeout=20.0,
    initial_retry_delay=1.0,
    max_retry_delay=8.0,
    backoff_factor=2.0,
    jitter="full_and_equal_for_throttle",
)


# %%[markdown]
## Configure a remote LLM

# %%
from wayflowcore.models import OpenAICompatibleModel

llm = OpenAICompatibleModel(
    model_id="my-model",
    base_url="https://example.com",
    retry_policy=retry_policy,
)


# %%[markdown]
## Configure remote steps and tools

# %%
from wayflowcore.steps import ApiCallStep
from wayflowcore.tools import RemoteTool

ORDER_API_BASE_URL = "https://example.com/orders"

api_step = ApiCallStep(
    name="fetch_order_step",
    url=ORDER_API_BASE_URL,
    method="POST",
    retry_policy=retry_policy,
)

remote_tool = RemoteTool(
    name="fetch_order",
    description="Fetch an order from a remote API.",
    url=ORDER_API_BASE_URL + "/{{ order_id }}",  # keep the base URL fixed and template only the path parameter
    method="GET",
    retry_policy=retry_policy,
    url_allow_list=[ORDER_API_BASE_URL],
)


# %%[markdown]
## Configure remote agents and MCP transports

# %%
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.mcp import StreamableHTTPTransport
from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal
from wayflowcore.ociagent import OciAgent

a2a_agent = A2AAgent(
    agent_url="https://example.com/a2a",
    connection_config=A2AConnectionConfig(verify=False, retry_policy=retry_policy),
)

oci_agent = OciAgent(
    agent_endpoint_id="ocid1.agentendpoint.oc1..example",
    client_config=OCIClientConfigWithInstancePrincipal(service_endpoint="https://example.com"),
    retry_policy=retry_policy,
)

transport = StreamableHTTPTransport(
    url="https://example.com/mcp",
    retry_policy=retry_policy,
)


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(oci_agent)


# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

loaded_agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
```
