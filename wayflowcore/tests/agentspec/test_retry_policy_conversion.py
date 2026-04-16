# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import warnings

from pyagentspec import A2AAgent as AgentSpecA2AAgent
from pyagentspec import OciAgent as AgentSpecOciAgent

from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig
from wayflowcore.agentspec._agentspecconverter import WayflowToAgentSpecConversionContext
from wayflowcore.agentspec._runtimeconverter import AgentSpecToWayflowConversionContext
from wayflowcore.embeddingmodels import OpenAICompatibleEmbeddingModel
from wayflowcore.mcp import StreamableHTTPTransport
from wayflowcore.models import OpenAICompatibleModel
from wayflowcore.models.ociclientconfig import OCIClientConfigWithInstancePrincipal
from wayflowcore.ociagent import OciAgent
from wayflowcore.retrypolicy import RetryPolicy
from wayflowcore.steps import ApiCallStep


def test_api_call_step_retry_policy_converts_to_agentspec_and_back() -> None:
    runtime_step = ApiCallStep(
        url="https://example.com",
        method="POST",
        retry_policy=RetryPolicy(max_attempts=3),
    )

    agentspec_node = WayflowToAgentSpecConversionContext().convert(
        runtime_step,
        referenced_objects={},
    )
    assert agentspec_node.retry_policy is not None
    assert agentspec_node.retry_policy.max_attempts == 3

    round_tripped = AgentSpecToWayflowConversionContext().convert(
        agentspec_node,
        tool_registry={},
        converted_components={},
    )
    assert round_tripped.retry_policy is not None
    assert round_tripped.retry_policy.max_attempts == 3


def test_openai_compatible_llm_retry_policy_converts_to_agentspec_and_back() -> None:
    runtime_llm = OpenAICompatibleModel(
        model_id="model",
        base_url="https://example.com",
        retry_policy=RetryPolicy(max_attempts=2),
    )

    agentspec_llm = WayflowToAgentSpecConversionContext().convert(
        runtime_llm,
        referenced_objects={},
    )
    assert agentspec_llm.retry_policy is not None
    assert agentspec_llm.retry_policy.max_attempts == 2

    round_tripped = AgentSpecToWayflowConversionContext().convert(
        agentspec_llm,
        tool_registry={},
        converted_components={},
    )
    assert round_tripped.retry_policy is not None
    assert round_tripped.retry_policy.max_attempts == 2


def test_embedding_retry_policy_converts_to_agentspec_and_back() -> None:
    runtime_embedding = OpenAICompatibleEmbeddingModel(
        model_id="embed-model",
        base_url="https://example.com",
        retry_policy=RetryPolicy(max_attempts=5),
    )

    agentspec_embedding = WayflowToAgentSpecConversionContext().convert(
        runtime_embedding,
        referenced_objects={},
    )
    assert agentspec_embedding.retry_policy is not None
    assert agentspec_embedding.retry_policy.max_attempts == 5

    round_tripped = AgentSpecToWayflowConversionContext().convert(
        agentspec_embedding,
        tool_registry={},
        converted_components={},
    )
    assert round_tripped.retry_policy is not None
    assert round_tripped.retry_policy.max_attempts == 5


def test_remote_transport_retry_policy_converts_to_agentspec_and_back() -> None:
    runtime_transport = StreamableHTTPTransport(
        url="https://example.com/mcp",
        retry_policy=RetryPolicy(max_attempts=4),
    )

    agentspec_transport = WayflowToAgentSpecConversionContext().convert(
        runtime_transport,
        referenced_objects={},
    )
    assert agentspec_transport.retry_policy is not None
    assert agentspec_transport.retry_policy.max_attempts == 4

    round_tripped = AgentSpecToWayflowConversionContext().convert(
        agentspec_transport,
        tool_registry={},
        converted_components={},
    )
    assert round_tripped.retry_policy is not None
    assert round_tripped.retry_policy.max_attempts == 4


def test_oci_agent_retry_policy_converts_to_native_agentspec_component() -> None:
    runtime_agent = OciAgent(
        agent_endpoint_id="ocid1.agentendpoint.oc1..example",
        client_config=OCIClientConfigWithInstancePrincipal(service_endpoint="https://example.com"),
        retry_policy=RetryPolicy(max_attempts=2),
    )

    agentspec_agent = WayflowToAgentSpecConversionContext().convert(
        runtime_agent,
        referenced_objects={},
    )
    assert isinstance(agentspec_agent, AgentSpecOciAgent)
    assert agentspec_agent.retry_policy is not None
    assert agentspec_agent.retry_policy.max_attempts == 2

    round_tripped = AgentSpecToWayflowConversionContext().convert(
        agentspec_agent,
        tool_registry={},
        converted_components={},
    )
    assert round_tripped.retry_policy is not None
    assert round_tripped.retry_policy.max_attempts == 2


def test_a2a_agent_retry_policy_converts_to_native_agentspec_component() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        runtime_agent = A2AAgent(
            agent_url="https://example.com/a2a",
            connection_config=A2AConnectionConfig(
                verify=False,
                retry_policy=RetryPolicy(max_attempts=6),
            ),
        )

    agentspec_agent = WayflowToAgentSpecConversionContext().convert(
        runtime_agent,
        referenced_objects={},
    )
    assert isinstance(agentspec_agent, AgentSpecA2AAgent)
    assert agentspec_agent.connection_config.retry_policy is not None
    assert agentspec_agent.connection_config.retry_policy.max_attempts == 6

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        round_tripped = AgentSpecToWayflowConversionContext().convert(
            agentspec_agent,
            tool_registry={},
            converted_components={},
        )
    assert round_tripped.connection_config.retry_policy is not None
    assert round_tripped.connection_config.retry_policy.max_attempts == 6
