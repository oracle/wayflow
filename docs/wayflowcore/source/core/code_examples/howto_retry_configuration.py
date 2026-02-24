# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Configure Retries on Remote Components

# .. start-##_Create_a_retry_policy
from wayflowcore.retrypolicy import RetryPolicy

retry_policy = RetryPolicy(
    max_attempts=3,
    request_timeout=20.0,
    initial_retry_delay=1.0,
    max_retry_delay=8.0,
    backoff_factor=2.0,
    jitter="full_and_equal_for_throttle",
)
# .. end-##_Create_a_retry_policy

# .. start-##_Configure_a_remote_LLM
from wayflowcore.models import OpenAICompatibleModel

llm = OpenAICompatibleModel(
    model_id="my-model",
    base_url="https://example.com",
    retry_policy=retry_policy,
)
# .. end-##_Configure_a_remote_LLM

# .. start-##_Configure_remote_steps_and_tools
from wayflowcore.steps import ApiCallStep
from wayflowcore.tools import RemoteTool

api_step = ApiCallStep(
    name="fetch_order_step",
    url="https://example.com/orders",
    method="POST",
    retry_policy=retry_policy,
)

remote_tool = RemoteTool(
    name="fetch_order",
    description="Fetch an order from a remote API.",
    url="https://example.com/orders/{{ order_id }}",
    method="GET",
    retry_policy=retry_policy,
)
# .. end-##_Configure_remote_steps_and_tools

# .. start-##_Configure_remote_agents_and_MCP_transports
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
# .. end-##_Configure_remote_agents_and_MCP_transports

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(oci_agent)
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

loaded_agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
