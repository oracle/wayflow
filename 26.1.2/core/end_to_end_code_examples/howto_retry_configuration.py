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
