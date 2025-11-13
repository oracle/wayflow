# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import urllib.parse
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union, cast

from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.flows.edges import ControlFlowEdge as AgentSpecControlFlowEdge
from pyagentspec.flows.edges import DataFlowEdge as AgentSpecDataFlowEdge
from pyagentspec.flows.flow import Flow as AgentSpecFlow
from pyagentspec.flows.node import Node as AgentSpecNode
from pyagentspec.flows.nodes import InputMessageNode as AgentSpecInputMessageNode
from pyagentspec.flows.nodes import OutputMessageNode as AgentSpecOutputMessageNode
from pyagentspec.flows.nodes.agentnode import AgentNode as AgentSpecAgentNode
from pyagentspec.flows.nodes.apinode import ApiNode as AgentSpecApiNode
from pyagentspec.flows.nodes.branchingnode import BranchingNode as AgentSpecBranchingNode
from pyagentspec.flows.nodes.endnode import EndNode as AgentSpecEndNode
from pyagentspec.flows.nodes.flownode import FlowNode as AgentSpecFlowNode
from pyagentspec.flows.nodes.llmnode import LlmNode as AgentSpecLlmNode
from pyagentspec.flows.nodes.mapnode import MapNode as AgentSpecMapNode
from pyagentspec.flows.nodes.mapnode import ReductionMethod
from pyagentspec.flows.nodes.startnode import StartNode as AgentSpecStartNode
from pyagentspec.flows.nodes.toolnode import ToolNode as AgentSpecToolNode
from pyagentspec.llms import LlmConfig as AgentSpecLlmConfig
from pyagentspec.llms import OciGenAiConfig as AgentSpecOciGenAiModel
from pyagentspec.llms.llmgenerationconfig import LlmGenerationConfig as AgentSpecLlmGenerationConfig
from pyagentspec.llms.ociclientconfig import OciClientConfig as AgentSpecOciClientConfig
from pyagentspec.llms.ociclientconfig import (
    OciClientConfigWithApiKey as AgentSpecOciClientConfigWithApiKey,
)
from pyagentspec.llms.ociclientconfig import (
    OciClientConfigWithInstancePrincipal as AgentSpecOciClientConfigWithInstancePrincipal,
)
from pyagentspec.llms.ociclientconfig import (
    OciClientConfigWithResourcePrincipal as AgentSpecOciClientConfigWithResourcePrincipal,
)
from pyagentspec.llms.ociclientconfig import (
    OciClientConfigWithSecurityToken as AgentSpecOciClientConfigWithSecurityToken,
)
from pyagentspec.llms.ollamaconfig import OllamaConfig as AgentSpecOllamaModel
from pyagentspec.llms.openaicompatibleconfig import (
    OpenAiCompatibleConfig as AgentSpecOpenAiCompatibleConfig,
)
from pyagentspec.llms.openaiconfig import OpenAiConfig as AgentSpecOpenAiConfig
from pyagentspec.llms.vllmconfig import VllmConfig as AgentSpecVllmModel
from pyagentspec.managerworkers import ManagerWorkers as AgentSpecManagerWorkers
from pyagentspec.mcp.clienttransport import ClientTransport as AgentSpecClientTransport
from pyagentspec.mcp.clienttransport import SSEmTLSTransport as AgentSpecSSEmTLSTransport
from pyagentspec.mcp.clienttransport import SSETransport as AgentSpecSSETransport
from pyagentspec.mcp.clienttransport import StdioTransport as AgentSpecStdioTransport
from pyagentspec.mcp.clienttransport import (
    StreamableHTTPmTLSTransport as AgentSpecStreamableHTTPmTLSTransport,
)
from pyagentspec.mcp.clienttransport import (
    StreamableHTTPTransport as AgentSpecStreamableHTTPTransport,
)
from pyagentspec.mcp.tools import MCPTool as AgentSpecMCPTool
from pyagentspec.mcp.tools import MCPToolBox as AgentSpecMCPToolBox
from pyagentspec.mcp.tools import MCPToolSpec as AgentSpecMCPToolSpec
from pyagentspec.ociagent import OciAgent as AgentSpecOciAgent
from pyagentspec.property import ListProperty as AgentSpecListProperty
from pyagentspec.property import Property as AgentSpecProperty
from pyagentspec.swarm import Swarm as AgentSpecSwarm
from pyagentspec.tools.clienttool import ClientTool as AgentSpecClientTool
from pyagentspec.tools.remotetool import RemoteTool as AgentSpecRemoteTool
from pyagentspec.tools.servertool import ServerTool as AgentSpecServerTool

from wayflowcore._metadata import METADATA_ID_KEY
from wayflowcore.agent import Agent as RuntimeAgent
from wayflowcore.agentspec.components import (
    PluginOciGenAiEmbeddingConfig as AgentSpecPluginOciGenAiEmbeddingConfig,
)
from wayflowcore.agentspec.components import (
    PluginOllamaEmbeddingConfig as AgentSpecPluginOllamaEmbeddingConfig,
)
from wayflowcore.agentspec.components import (
    PluginOpenAiCompatibleEmbeddingConfig as AgentSpecPluginOpenAiCompatibleEmbeddingConfig,
)
from wayflowcore.agentspec.components import (
    PluginOpenAiEmbeddingConfig as AgentSpecPluginOpenAiEmbeddingConfig,
)
from wayflowcore.agentspec.components import (
    PluginVllmEmbeddingConfig as AgentSpecPluginVllmEmbeddingConfig,
)
from wayflowcore.agentspec.components.agent import ExtendedAgent as AgentSpecExtendedAgent
from wayflowcore.agentspec.components.contextprovider import (
    PluginConstantContextProvider as AgentSpecPluginConstantContextProvider,
)
from wayflowcore.agentspec.components.contextprovider import (
    PluginFlowContextProvider as AgentSpecPluginFlowContextProvider,
)
from wayflowcore.agentspec.components.contextprovider import (
    PluginToolContextProvider as AgentSpecPluginToolContextProvider,
)
from wayflowcore.agentspec.components.datastores import PluginEntity as AgentSpecPluginEntity
from wayflowcore.agentspec.components.datastores.inmemory_datastore import (
    PluginInMemoryDatastore as AgentSpecPluginInMemoryDatastore,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreCreateNode as AgentSpecPluginDatastoreCreateNode,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreDeleteNode as AgentSpecPluginDatastoreDeleteNode,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreListNode as AgentSpecPluginDatastoreListNode,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreQueryNode as AgentSpecPluginDatastoreQueryNode,
)
from wayflowcore.agentspec.components.datastores.nodes import (
    PluginDatastoreUpdateNode as AgentSpecPluginDatastoreUpdateNode,
)
from wayflowcore.agentspec.components.datastores.oracle_datastore import (
    PluginMTlsOracleDatabaseConnectionConfig as AgentSpecPluginMTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.agentspec.components.datastores.oracle_datastore import (
    PluginOracleDatabaseDatastore as AgentSpecPluginOracleDatabaseDatastore,
)
from wayflowcore.agentspec.components.datastores.oracle_datastore import (
    PluginTlsOracleDatabaseConnectionConfig as AgentSpecPluginTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.agentspec.components.flow import ExtendedFlow as AgentSpecExtendedFlow
from wayflowcore.agentspec.components.managerworkers import (
    PluginManagerWorkers as AgentSpecPluginManagerWorkers,
)
from wayflowcore.agentspec.components.mcp import (
    PluginClientTransport as AgentSpecPluginClientTransport,
)
from wayflowcore.agentspec.components.mcp import PluginMCPTool as AgentSpecPluginMCPTool
from wayflowcore.agentspec.components.mcp import PluginMCPToolBox as AgentSpecPluginMCPToolBox
from wayflowcore.agentspec.components.mcp import PluginMCPToolSpec as AgentSpecPluginMCPToolSpec
from wayflowcore.agentspec.components.mcp import (
    PluginRemoteBaseTransport as AgentSpecPluginRemoteBaseTransport,
)
from wayflowcore.agentspec.components.mcp import (
    PluginSSEmTLSTransport as AgentSpecPluginSSEmTLSTransport,
)
from wayflowcore.agentspec.components.mcp import PluginSSETransport as AgentSpecPluginSSETransport
from wayflowcore.agentspec.components.mcp import (
    PluginStdioTransport as AgentSpecPluginStdioTransport,
)
from wayflowcore.agentspec.components.mcp import (
    PluginStreamableHTTPmTLSTransport as AgentSpecPluginStreamableHTTPmTLSTransport,
)
from wayflowcore.agentspec.components.mcp import (
    PluginStreamableHTTPTransport as AgentSpecPluginStreamableHTTPTransport,
)
from wayflowcore.agentspec.components.messagelist import (
    PluginImageContent as AgentSpecPluginImageContent,
)
from wayflowcore.agentspec.components.messagelist import PluginMessage as AgentSpecPluginMessage
from wayflowcore.agentspec.components.messagelist import (
    PluginMessageContent as AgentSpecPluginMessageContent,
)
from wayflowcore.agentspec.components.messagelist import (
    PluginTextContent as AgentSpecPluginTextContent,
)
from wayflowcore.agentspec.components.node import ExtendedNode as AgentSpecExtendedNode
from wayflowcore.agentspec.components.nodes import ExtendedAgentNode as AgentSpecExtendedAgentNode
from wayflowcore.agentspec.components.nodes import ExtendedLlmNode as AgentSpecExtendedLlmNode
from wayflowcore.agentspec.components.nodes import ExtendedMapNode as AgentSpecExtendedMapNode
from wayflowcore.agentspec.components.nodes import ExtendedToolNode as AgentSpecExtendedToolNode
from wayflowcore.agentspec.components.nodes import (
    PluginCatchExceptionNode as AgentSpecPluginCatchExceptionNode,
)
from wayflowcore.agentspec.components.nodes import PluginChoiceNode as AgentSpecPluginChoiceNode
from wayflowcore.agentspec.components.nodes import (
    PluginConstantValuesNode as AgentSpecPluginConstantValuesNode,
)
from wayflowcore.agentspec.components.nodes import PluginExtractNode as AgentSpecPluginExtractNode
from wayflowcore.agentspec.components.nodes import (
    PluginGetChatHistoryNode as AgentSpecPluginGetChatHistoryNode,
)
from wayflowcore.agentspec.components.nodes import (
    PluginInputMessageNode as AgentSpecPluginInputMessageNode,
)
from wayflowcore.agentspec.components.nodes import (
    PluginOutputMessageNode as AgentSpecPluginOutputMessageNode,
)
from wayflowcore.agentspec.components.nodes import (
    PluginReadVariableNode as AgentSpecPluginReadVariableNode,
)
from wayflowcore.agentspec.components.nodes import PluginRegexNode as AgentSpecPluginRegexNode
from wayflowcore.agentspec.components.nodes import PluginRetryNode as AgentSpecPluginRetryNode
from wayflowcore.agentspec.components.nodes import PluginTemplateNode as AgentSpecPluginTemplateNode
from wayflowcore.agentspec.components.nodes import (
    PluginWriteVariableNode as AgentSpecPluginWriteVariableNode,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginJsonOutputParser as AgentSpecPluginJsonOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginJsonToolOutputParser as AgentSpecPluginJsonToolOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginOutputParser as AgentSpecPluginOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginPythonToolOutputParser as AgentSpecPluginPythonToolOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginReactToolOutputParser as AgentSpecPluginReactToolOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginRegexOutputParser as AgentSpecPluginRegexOutputParser,
)
from wayflowcore.agentspec.components.outputparser import (
    PluginRegexPattern as AgentSpecPluginRegexPattern,
)
from wayflowcore.agentspec.components.swarm import PluginSwarm as AgentSpecPluginSwarm
from wayflowcore.agentspec.components.template import (
    PluginPromptTemplate as AgentSpecPluginPromptTemplate,
)
from wayflowcore.agentspec.components.transforms import (
    PluginAppendTrailingSystemMessageToUserMessageTransform as AgentSpecPluginAppendTrailingSystemMessageToUserMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginCoalesceSystemMessagesTransform as AgentSpecPluginCoalesceSystemMessagesTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginLlamaMergeToolRequestAndCallsTransform as AgentSpecPluginLlamaMergeToolRequestAndCallsTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginMessageTransform as AgentSpecPluginMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginReactMergeToolRequestAndCallsTransform as AgentSpecPluginReactMergeToolRequestAndCallsTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginRemoveEmptyNonUserMessageTransform as AgentSpecPluginRemoveEmptyNonUserMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginSwarmToolRequestAndCallsTransform as AgentSpecPluginSwarmToolRequestAndCallsTransform,
)
from wayflowcore.contextproviders.constantcontextprovider import (
    ConstantContextProvider as RuntimeConstantContextProvider,
)
from wayflowcore.contextproviders.flowcontextprovider import (
    FlowContextProvider as RuntimeFlowContextProvider,
)
from wayflowcore.contextproviders.toolcontextprovider import (
    ToolContextProvider as RuntimeToolContextProvider,
)
from wayflowcore.controlconnection import ControlFlowEdge as RuntimeControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge as RuntimeDataFlowEdge
from wayflowcore.datastore import Entity as RuntimeEntity
from wayflowcore.datastore.inmemory import InMemoryDatastore as RuntimeInMemoryDatastore
from wayflowcore.datastore.oracle import (
    MTlsOracleDatabaseConnectionConfig as RuntimeMTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.oracle import OracleDatabaseDatastore as RuntimeOracleDatabaseDatastore
from wayflowcore.datastore.oracle import (
    TlsOracleDatabaseConnectionConfig as RuntimeTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.embeddingmodels import OCIGenAIEmbeddingModel as RuntimeOCIGenAIEmbeddingModel
from wayflowcore.embeddingmodels import OllamaEmbeddingModel as RuntimeOllamaEmbeddingModel
from wayflowcore.embeddingmodels import (
    OpenAICompatibleEmbeddingModel as RuntimeOpenAiCompatibleEmbeddingModel,
)
from wayflowcore.embeddingmodels import OpenAIEmbeddingModel as RuntimeOpenAiEmbeddingModel
from wayflowcore.embeddingmodels import VllmEmbeddingModel as RuntimeVllmEmbeddingModel
from wayflowcore.flow import Flow as RuntimeFlow
from wayflowcore.managerworkers import ManagerWorkers as RuntimeManagerWorkers
from wayflowcore.mcp import MCPTool as RuntimeMCPTool
from wayflowcore.mcp import MCPToolBox as RuntimeMCPToolBox
from wayflowcore.mcp.clienttransport import SSEmTLSTransport as RuntimeSSEmTLSTransport
from wayflowcore.mcp.clienttransport import SSETransport as RuntimeSSETransport
from wayflowcore.mcp.clienttransport import StdioTransport as RuntimeStdioTransport
from wayflowcore.mcp.clienttransport import (
    StreamableHTTPmTLSTransport as RuntimeStreamableHTTPmTLSTransport,
)
from wayflowcore.mcp.clienttransport import (
    StreamableHTTPTransport as RuntimeStreamableHTTPTransport,
)
from wayflowcore.messagelist import ImageContent as RuntimeImageContent
from wayflowcore.messagelist import Message as RuntimeMessage
from wayflowcore.messagelist import MessageContent as RuntimeMessageContent
from wayflowcore.messagelist import MessageType
from wayflowcore.messagelist import TextContent as RuntimeTextContent
from wayflowcore.models import OCIGenAIModel as RuntimeOCIGenAIModel
from wayflowcore.models import OllamaModel as RuntimeOllamaModel
from wayflowcore.models import OpenAIModel as RuntimeOpenAIModel
from wayflowcore.models import VllmModel as RuntimeVllmModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig as RuntimeLlmGenerationConfig
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithApiKey as RuntimeOCIClientConfigWithApiKey,
)
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithInstancePrincipal as RuntimeOCIClientConfigWithInstancePrincipal,
)
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithResourcePrincipal as RuntimeOCIClientConfigWithResourcePrincipal,
)
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithSecurityToken as RuntimeOCIClientConfigWithSecurityToken,
)
from wayflowcore.models.ocigenaimodel import ModelProvider as RuntimeModelProvider
from wayflowcore.models.ocigenaimodel import ServingMode as RuntimeServingMode
from wayflowcore.models.openaicompatiblemodel import (
    OpenAICompatibleModel as RuntimeOpenAICompatibleModel,
)
from wayflowcore.ociagent import OciAgent as RuntimeOciAgent
from wayflowcore.outputparser import JsonOutputParser as RuntimeJsonOutputParser
from wayflowcore.outputparser import JsonToolOutputParser as RuntimeJsonToolOutputParser
from wayflowcore.outputparser import PythonToolOutputParser as RuntimePythonToolOutputParser
from wayflowcore.outputparser import RegexOutputParser as RuntimeRegexOutputParser
from wayflowcore.outputparser import RegexPattern as RuntimeRegexPattern
from wayflowcore.property import JsonSchemaParam
from wayflowcore.property import ListProperty as RuntimeListProperty
from wayflowcore.property import Property as RuntimeProperty
from wayflowcore.property import UnionProperty
from wayflowcore.stepdescription import StepDescription
from wayflowcore.steps import AgentExecutionStep as RuntimeAgentExecutionStep
from wayflowcore.steps import ApiCallStep as RuntimeApiCallStep
from wayflowcore.steps import BranchingStep as RuntimeBranchingStep
from wayflowcore.steps import CatchExceptionStep as RuntimeCatchExceptionStep
from wayflowcore.steps import ChoiceSelectionStep as RuntimeChoiceSelectionStep
from wayflowcore.steps import CompleteStep as RuntimeCompleteStep
from wayflowcore.steps import ExtractValueFromJsonStep as RuntimeExtractStep
from wayflowcore.steps import FlowExecutionStep as RuntimeFlowExecutionStep
from wayflowcore.steps import InputMessageStep as RuntimeInputMessageStep
from wayflowcore.steps import MapStep as RuntimeMapStep
from wayflowcore.steps import OutputMessageStep as RuntimeOutputMessageStep
from wayflowcore.steps import PromptExecutionStep as RuntimePromptExecutionStep
from wayflowcore.steps import RegexExtractionStep as RuntimeRegexExtractionStep
from wayflowcore.steps import StartStep as RuntimeStartStep
from wayflowcore.steps import TemplateRenderingStep as RuntimeTemplateRenderingStep
from wayflowcore.steps import ToolExecutionStep as RuntimeToolExecutionStep
from wayflowcore.steps.constantvaluesstep import ConstantValuesStep as RuntimeConstantValuesStep
from wayflowcore.steps.datastoresteps import DatastoreCreateStep as RuntimeDatastoreCreateStep
from wayflowcore.steps.datastoresteps import DatastoreDeleteStep as RuntimeDatastoreDeleteStep
from wayflowcore.steps.datastoresteps import DatastoreListStep as RuntimeDatastoreListStep
from wayflowcore.steps.datastoresteps import DatastoreQueryStep as RuntimeDatastoreQueryStep
from wayflowcore.steps.datastoresteps import DatastoreUpdateStep as RuntimeDatastoreUpdateStep
from wayflowcore.steps.getchathistorystep import GetChatHistoryStep as RuntimeGetChatHistoryStep
from wayflowcore.steps.retrystep import RetryStep as RuntimeRetryStep
from wayflowcore.steps.step import Step as RuntimeStep
from wayflowcore.steps.variablesteps.variablereadstep import (
    VariableReadStep as RuntimeVariableReadStep,
)
from wayflowcore.steps.variablesteps.variablewritestep import (
    VariableWriteStep as RuntimeVariableWriteStep,
)
from wayflowcore.swarm import Swarm as RuntimeSwarm
from wayflowcore.templates import PromptTemplate as RuntimePromptTemplate
from wayflowcore.templates._swarmtemplate import (
    _ToolRequestAndCallsTransform as RuntimeSwarmToolRequestAndCallsTransform,
)
from wayflowcore.templates.llamatemplates import (
    _LlamaMergeToolRequestAndCallsTransform as RuntimeLlamaMergeToolRequestAndCallsTransform,
)
from wayflowcore.templates.reacttemplates import (
    ReactToolOutputParser as RuntimeReactToolOutputParser,
)
from wayflowcore.templates.reacttemplates import (
    _ReactMergeToolRequestAndCallsTransform as RuntimeReactMergeToolRequestAndCallsTransform,
)
from wayflowcore.tools import ClientTool as RuntimeClientTool
from wayflowcore.tools import RemoteTool as RuntimeRemoteTool
from wayflowcore.tools import ServerTool as RuntimeServerTool
from wayflowcore.tools import Tool as RuntimeTool
from wayflowcore.tools import ToolRequest as RuntimeToolRequest
from wayflowcore.tools import ToolResult as RuntimeToolResult
from wayflowcore.tools.agentbasedtools import DescribedAgent as RuntimeDescribedAgent
from wayflowcore.tools.flowbasedtools import DescribedFlow as RuntimeDescribedFlow
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform as RuntimeAppendTrailingSystemMessageToUserMessageTransform,
)
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform as RuntimewCoalesceSystemMessagesTransform,
)
from wayflowcore.transforms import (
    RemoveEmptyNonUserMessageTransform as RuntimeRemoveEmptyNonUserMessageTransform,
)
from wayflowcore.variable import Variable as RuntimeVariable


def _format_llm_url(url: str) -> str:
    if url.startswith("http://"):
        url = url.replace("http://", "", 1)
    elif url.startswith("https://"):
        url = url.replace("https://", "", 1)
    if "/v1/chat/completions" in url:
        url = url.replace(
            "/v1/chat/completions",
            "",
        )
    elif "/v1" in url:
        url = url.replace(
            "/v1",
            "",
        )
    return url


def _format_embedding_model_url(url: str) -> str:
    if url.startswith("http://"):
        url = url.replace("http://", "", 1)
    elif url.startswith("https://"):
        url = url.replace("https://", "", 1)
    return url


class AgentSpecToRuntimeConverter:

    def convert(
        self,
        agentspec_component: AgentSpecComponent,
        tool_registry: Dict[str, Union[RuntimeServerTool, Callable[..., Any]]],
        converted_components: Optional[Dict[str, Any]] = None,
        described: bool = False,
    ) -> Any:
        """Convert the given PyAgentSpec component object into the corresponding Runtime component"""
        if converted_components is None:
            converted_components = {}
        if agentspec_component.id not in converted_components:
            converted_components[agentspec_component.id] = self._convert(
                agentspec_component,
                tool_registry,
                converted_components,
                described,
            )
        return converted_components[agentspec_component.id]

    def _convert_property_to_runtime(
        self, agentspec_property: AgentSpecProperty
    ) -> RuntimeProperty:
        return RuntimeProperty.from_json_schema(
            cast(JsonSchemaParam, agentspec_property.json_schema)
        )

    def _convert_property_to_runtime_variable(
        self, agentspec_property: AgentSpecProperty
    ) -> RuntimeVariable:
        runtime_property = self._convert_property_to_runtime(agentspec_property)
        return RuntimeVariable.from_property(runtime_property)

    def _convert_entity_to_runtime(self, agentspec_entity: AgentSpecPluginEntity) -> RuntimeEntity:
        return RuntimeEntity(
            name=agentspec_entity.title,
            description=agentspec_entity.description or "",
            properties={
                k: self._convert_property_to_runtime(AgentSpecProperty(json_schema=v))
                for k, v in agentspec_entity.json_schema.get("properties", {}).items()
            },
        )

    def _agentspec_properties_have_same_type(
        self, property_a: AgentSpecProperty, property_b: AgentSpecProperty
    ) -> bool:
        return self._runtime_properties_have_same_type(
            self._convert_property_to_runtime(property_a),
            self._convert_property_to_runtime(property_b),
        )

    def _runtime_properties_have_same_type(
        self, property_a: RuntimeProperty, property_b: RuntimeProperty
    ) -> bool:

        def _extract_type_relevant_info(
            json_schema: Union[JsonSchemaParam, Dict[str, Any]],
        ) -> Dict[str, Any]:
            type_relevant_info: Dict[str, Any] = {"type": json_schema.get("type", {})}
            if "properties" in json_schema:
                type_relevant_info["properties"] = {
                    property_name: _extract_type_relevant_info(property_)
                    for property_name, property_ in json_schema["properties"].items()
                }
            if "items" in json_schema:
                type_relevant_info["items"] = _extract_type_relevant_info(json_schema["items"])
            if "additionalProperties" in json_schema:
                type_relevant_info["additionalProperties"] = _extract_type_relevant_info(
                    json_schema["additionalProperties"]
                )
            return type_relevant_info

        return _extract_type_relevant_info(
            property_a._type_to_json_schema()
        ) == _extract_type_relevant_info(property_b._type_to_json_schema())

    def _convert_llmgenerationconfig_to_runtime(
        self, agentspec_generationconfig: AgentSpecLlmGenerationConfig
    ) -> RuntimeLlmGenerationConfig:
        parameters: Dict[str, Any] = {}
        agentspec_generationconfig_dict: Dict[str, Any] = agentspec_generationconfig.model_dump()  # type: ignore
        for parameter in ["max_tokens", "temperature", "top_p", "stop", "frequency_penalty"]:
            parameters[parameter] = agentspec_generationconfig_dict.pop(parameter, None)
        parameters["extra_args"] = agentspec_generationconfig_dict
        return RuntimeLlmGenerationConfig(**parameters)

    def _convert_messagecontent_to_runtime(
        self, message_content: AgentSpecPluginMessageContent
    ) -> RuntimeMessageContent:
        if isinstance(message_content, AgentSpecPluginTextContent):
            return RuntimeTextContent(content=message_content.content)
        elif isinstance(message_content, AgentSpecPluginImageContent):
            return RuntimeImageContent(base64_content=message_content.base64_content)
        else:
            raise ValueError(f"Message content of type {type(message_content)} is not supported")

    def _convert_message_to_runtime(
        self,
        agentspec_message: AgentSpecPluginMessage,
    ) -> RuntimeMessage:
        tool_requests = (
            [
                RuntimeToolRequest(
                    name=tr.name,
                    args=tr.args,
                    tool_request_id=tr.tool_request_id,
                )
                for tr in agentspec_message.tool_requests
            ]
            if agentspec_message.tool_requests is not None
            else None
        )
        tool_result = (
            RuntimeToolResult(
                content=agentspec_message.tool_result.content,
                tool_request_id=agentspec_message.tool_result.tool_request_id,
            )
            if agentspec_message.tool_result is not None
            else None
        )
        return RuntimeMessage(
            role=agentspec_message.role,
            contents=[
                self._convert_messagecontent_to_runtime(content_)
                for content_ in agentspec_message.contents
            ],
            tool_requests=tool_requests,
            tool_result=tool_result,
            display_only=agentspec_message.display_only,
            sender=agentspec_message.sender,
            recipients=set(agentspec_message.recipients),
            time_created=agentspec_message.time_created,
            time_updated=agentspec_message.time_updated,
            __metadata_info__={},
        )

    def _convert_prompttemplate_to_runtime(
        self,
        agentspec_template: AgentSpecPluginPromptTemplate,
        tool_registry: Dict[str, Union[RuntimeServerTool, Callable[..., Any]]],
        converted_components: Optional[Dict[str, Any]] = None,
    ) -> RuntimePromptTemplate:
        return RuntimePromptTemplate(
            messages=[
                self._convert_message_to_runtime(message_)
                for message_ in agentspec_template.messages
            ],
            output_parser=(
                (
                    [
                        self.convert(output_parser_, tool_registry, converted_components)
                        for output_parser_ in agentspec_template.output_parser
                    ]
                    if isinstance(agentspec_template.output_parser, list)
                    else self.convert(
                        agentspec_template.output_parser, tool_registry, converted_components
                    )
                )
                if agentspec_template.output_parser
                else None
            ),
            input_descriptors=[
                self._convert_property_to_runtime(input_)
                for input_ in agentspec_template.inputs or []
            ],
            pre_rendering_transforms=(
                [
                    self.convert(transform, tool_registry, converted_components)
                    for transform in agentspec_template.pre_rendering_transforms
                ]
                if agentspec_template.pre_rendering_transforms
                else None
            ),
            post_rendering_transforms=(
                [
                    self.convert(transform, tool_registry, converted_components)
                    for transform in agentspec_template.post_rendering_transforms
                ]
                if agentspec_template.post_rendering_transforms
                else None
            ),
            tools=(
                [
                    cast(RuntimeTool, self.convert(tool_, tool_registry, converted_components))
                    for tool_ in agentspec_template.tools
                ]
                if agentspec_template.tools
                else None
            ),
            native_tool_calling=agentspec_template.native_tool_calling,
            response_format=(
                self._convert_property_to_runtime(agentspec_template.response_format)
                if agentspec_template.response_format
                else None
            ),
            native_structured_generation=agentspec_template.native_structured_generation,
            generation_config=(
                self._convert_llmgenerationconfig_to_runtime(agentspec_template.generation_config)
                if agentspec_template.generation_config
                else None
            ),
            id=agentspec_template.id,
            description=agentspec_template.description,
            name=agentspec_template.name,
        )

    def _convert_mapnode_to_runtime(
        self,
        agentspec_node: AgentSpecMapNode,
        unpack_input: Optional[Dict[str, str]] = None,
        tool_registry: Optional[Dict[str, Union[RuntimeServerTool, Callable[..., Any]]]] = None,
        converted_components: Optional[Dict[str, Any]] = None,
    ) -> RuntimeMapStep:
        for output_name, reducer in (agentspec_node.reducers or {}).items():
            if reducer != ReductionMethod.APPEND:
                raise ValueError(
                    f"Cannot convert MapNode to Runtime. ReductionMethod {reducer} is not supported."
                )
        if unpack_input and len(unpack_input) > 1:
            raise ValueError(
                "Cannot convert MapNode to Runtime. Only one input can be iterated on."
            )
        input_descriptors = [
            self._convert_property_to_runtime(input_property)
            for input_property in agentspec_node.inputs or []
        ]
        input_mapping: Dict[str, str] = {}
        if unpack_input:
            # The MapStep requires one single input to iterate over, called MapStep.ITERATED_INPUT
            # We have to look for it and rename the input descriptor
            unpack_input_name = next(k for k in unpack_input.keys())
            for i, input_descriptor in enumerate(input_descriptors):
                if input_descriptor.name == f"iterated_{unpack_input_name}":
                    if not isinstance(input_descriptor, UnionProperty):
                        raise ValueError(
                            f"The input descriptor {input_descriptor.name} has the wrong type. "
                            f"Expected UnionProperty, received {type(input_descriptor)}"
                        )
                    # This the input we are looking for, and its type is the union of two types: T and List[T]
                    # We need to extract List[T] because runtime requires to have that one only
                    if self._runtime_properties_have_same_type(
                        input_descriptor.any_of[0],
                        RuntimeListProperty(item_type=input_descriptor.any_of[1]),
                    ):
                        input_descriptors[i] = input_descriptor.any_of[0].copy(
                            name=input_descriptor.name
                        )
                    else:
                        input_descriptors[i] = input_descriptor.any_of[1].copy(
                            name=input_descriptor.name
                        )
                    input_mapping[RuntimeMapStep.ITERATED_INPUT] = f"iterated_{unpack_input_name}"
                else:
                    input_mapping[input_descriptor.name.replace("iterated_", "", 1)] = (
                        input_descriptor.name
                    )
        return RuntimeMapStep(
            name=agentspec_node.name,
            flow=self.convert(
                agentspec_node.subflow,
                tool_registry=tool_registry or {},
                converted_components=converted_components,
            ),
            unpack_input=unpack_input,
            parallel_execution=False,
            input_descriptors=input_descriptors,
            output_descriptors=[
                self._convert_property_to_runtime(output_property)
                for output_property in agentspec_node.outputs or []
            ],
            input_mapping=input_mapping,
            output_mapping={
                output_.json_schema["title"].replace("collected_", "", 1): output_.json_schema[
                    "title"
                ]
                for output_ in agentspec_node.outputs or []
            },
            __metadata_info__=(agentspec_node.metadata or {}).get("__metadata_info__", {}),
        )

    def _convert_llm_config_to_runtime(
        self,
        agentspec_component: AgentSpecLlmConfig,
        tool_registry: Dict[str, Union[RuntimeServerTool, Callable[..., Any]]],
        converted_components: Dict[str, Any],
    ) -> Any:
        generation_config = (
            self._convert_llmgenerationconfig_to_runtime(
                agentspec_component.default_generation_parameters
            )
            if agentspec_component.default_generation_parameters
            else None
        )

        if isinstance(agentspec_component, AgentSpecVllmModel):
            return RuntimeVllmModel(
                model_id=agentspec_component.model_id,
                # TODO enable more flexibility in base url
                host_port=_format_llm_url(agentspec_component.url),
                generation_config=generation_config,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecOciGenAiModel):
            client_config = self.convert(
                agentspec_component.client_config, tool_registry, converted_components
            )
            kwargs: Dict[str, Any] = {}
            if agentspec_component.provider is not None:
                kwargs["provider"] = RuntimeModelProvider(agentspec_component.provider.value)
            return RuntimeOCIGenAIModel(
                model_id=agentspec_component.model_id,
                compartment_id=agentspec_component.compartment_id,
                serving_mode=RuntimeServingMode(agentspec_component.serving_mode.value),
                client_config=client_config,
                generation_config=generation_config,
                **kwargs,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecOllamaModel):
            return RuntimeOllamaModel(
                model_id=agentspec_component.model_id,
                host_port=_format_llm_url(agentspec_component.url),
                generation_config=generation_config,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecOpenAiConfig):
            return RuntimeOpenAIModel(
                model_id=agentspec_component.model_id,
                generation_config=generation_config,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecOpenAiCompatibleConfig):
            return RuntimeOpenAICompatibleModel(
                model_id=agentspec_component.model_id,
                base_url=_format_llm_url(agentspec_component.url),
                generation_config=generation_config,
                **self._get_component_arguments(agentspec_component),
            )
        else:
            raise ValueError(
                f"Agent Spec LlmConfig '{agentspec_component.__class__.__name__}' is not supported yet."
            )

    def _convert(
        self,
        agentspec_component: AgentSpecComponent,
        tool_registry: Dict[str, Union[RuntimeServerTool, Callable[..., Any]]],
        converted_components: Dict[str, Any],
        described: bool = False,
    ) -> Any:
        metadata_info = (agentspec_component.metadata or {}).get("__metadata_info__", {})
        if isinstance(agentspec_component, AgentSpecLlmConfig):
            return self._convert_llm_config_to_runtime(
                agentspec_component, tool_registry, converted_components
            )
        elif isinstance(agentspec_component, AgentSpecOciClientConfig):
            if isinstance(agentspec_component, AgentSpecOciClientConfigWithSecurityToken):
                return RuntimeOCIClientConfigWithSecurityToken(
                    service_endpoint=agentspec_component.service_endpoint,
                    auth_profile=agentspec_component.auth_profile,
                    _auth_file_location=agentspec_component.auth_file_location,
                )
            elif isinstance(agentspec_component, AgentSpecOciClientConfigWithInstancePrincipal):
                return RuntimeOCIClientConfigWithInstancePrincipal(
                    service_endpoint=agentspec_component.service_endpoint,
                )
            elif isinstance(agentspec_component, AgentSpecOciClientConfigWithResourcePrincipal):
                return RuntimeOCIClientConfigWithResourcePrincipal(
                    service_endpoint=agentspec_component.service_endpoint,
                )
            elif isinstance(agentspec_component, AgentSpecOciClientConfigWithApiKey):
                return RuntimeOCIClientConfigWithApiKey(
                    service_endpoint=agentspec_component.service_endpoint,
                    auth_profile=agentspec_component.auth_profile,
                    _auth_file_location=agentspec_component.auth_file_location,
                )
            else:
                raise ValueError(
                    f"Agent Spec OciClientConfig '{agentspec_component.__class__.__name__}' is not supported yet."
                )

        elif isinstance(agentspec_component, AgentSpecOciAgent):
            client_config = self.convert(
                agentspec_component.client_config, tool_registry, converted_components
            )
            return RuntimeOciAgent(
                name=agentspec_component.name,
                description=agentspec_component.description or "",
                id=agentspec_component.id,
                agent_endpoint_id=agentspec_component.agent_endpoint_id,
                client_config=client_config,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecAgent):
            if not agentspec_component.llm_config:
                raise ValueError(
                    "wayflowcore.agent.Agent requires an LLM configuration, was ``None``"
                )

            extra_arguments: Dict[str, Any] = {
                "initial_message": None,
                "tools": [
                    *[
                        self.convert(t, tool_registry, converted_components)
                        for t in (agentspec_component.tools or [])
                    ],
                    *[
                        self.convert(t, tool_registry, converted_components)
                        for t in (agentspec_component.toolboxes or [])
                    ],
                ],
            }
            if isinstance(agentspec_component, AgentSpecExtendedAgent):
                extra_arguments["context_providers"] = (
                    [
                        self.convert(context_provider_, tool_registry, converted_components)
                        for context_provider_ in agentspec_component.context_providers
                    ]
                    if agentspec_component.context_providers
                    else None
                )
                extra_arguments["can_finish_conversation"] = (
                    agentspec_component.can_finish_conversation
                )
                extra_arguments["raise_exceptions"] = agentspec_component.raise_exceptions
                extra_arguments["max_iterations"] = agentspec_component.max_iterations
                extra_arguments["initial_message"] = agentspec_component.initial_message
                extra_arguments["caller_input_mode"] = agentspec_component.caller_input_mode
                extra_arguments["agents"] = [
                    self.convert(a, tool_registry, converted_components, described=True)
                    for a in agentspec_component.agents
                ]
                extra_arguments["flows"] = [
                    self.convert(f, tool_registry, converted_components, described=True)
                    for f in agentspec_component.flows
                ]
                extra_arguments["agent_template"] = (
                    self._convert_prompttemplate_to_runtime(
                        agentspec_component.agent_template, tool_registry, converted_components
                    )
                    if isinstance(agentspec_component.agent_template, AgentSpecPluginPromptTemplate)
                    else agentspec_component.agent_template
                )

            agent = RuntimeAgent(
                name=agentspec_component.name,
                id=agentspec_component.id,
                description=agentspec_component.description or "",
                llm=self.convert(
                    agentspec_component.llm_config, tool_registry, converted_components
                ),
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                custom_instruction=agentspec_component.system_prompt or None,
                __metadata_info__=metadata_info,
                **extra_arguments,
            )
            return (
                RuntimeDescribedAgent(
                    agent=agent,
                    name=agentspec_component.name,
                    description=agentspec_component.description or "",
                )
                if described
                else agent
            )
        elif isinstance(agentspec_component, (AgentSpecMCPTool, AgentSpecPluginMCPTool)):
            return RuntimeMCPTool(
                name=agentspec_component.name,
                client_transport=self.convert(
                    agentspec_component.client_transport, tool_registry, converted_components
                ),
                description=agentspec_component.description,
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                requires_confirmation=agentspec_component.requires_confirmation,
                id=agentspec_component.id,
                _validate_server_exists=False,
                _validate_tool_exist_on_server=False,
            )
        elif isinstance(agentspec_component, AgentSpecPluginConstantValuesNode):
            # Map PluginConstantValuesNode -> RuntimeConstantValuesStep
            return RuntimeConstantValuesStep(
                constant_values=agentspec_component.constant_values,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginGetChatHistoryNode):
            # Map PluginGetChatHistoryNode -> RuntimeGetChatHistoryStep
            return RuntimeGetChatHistoryStep(
                n=agentspec_component.n,
                which_messages=agentspec_component.which_messages,
                offset=agentspec_component.offset,
                message_types=(
                    tuple(agentspec_component.message_types)
                    if agentspec_component.message_types is not None
                    else None
                ),
                output_template=agentspec_component.output_template,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginRetryNode):
            # Map PluginRetryNode -> RuntimeRetryStep
            return RuntimeRetryStep(
                flow=self.convert(agentspec_component.flow, tool_registry, converted_components),
                success_condition=agentspec_component.success_condition,
                max_num_trials=agentspec_component.max_num_trials,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginToolContextProvider):
            return RuntimeToolContextProvider(
                name=agentspec_component.name,
                tool=self._convert(
                    agentspec_component=agentspec_component.tool,
                    tool_registry=tool_registry,
                    converted_components=converted_components,
                ),
                output_name=agentspec_component.output_name,
                id=agentspec_component.id,
                description=agentspec_component.description,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecPluginFlowContextProvider):
            return RuntimeFlowContextProvider(
                name=agentspec_component.name,
                flow_output_names=agentspec_component.output_names,
                flow=self._convert(
                    agentspec_component=agentspec_component.flow,
                    tool_registry=tool_registry,
                    converted_components=converted_components,
                ),
                id=agentspec_component.id,
                description=agentspec_component.description,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecPluginOciGenAiEmbeddingConfig):
            # Map to RuntimeOCIGenAIEmbeddingModel
            # Fields: model_id, compartment_id, serving_mode, client_config
            client_config = (
                self.convert(agentspec_component.client_config, tool_registry, converted_components)
                if hasattr(agentspec_component, "client_config")
                and agentspec_component.client_config is not None
                else None
            )
            return RuntimeOCIGenAIEmbeddingModel(
                model_id=agentspec_component.model_id,
                compartment_id=agentspec_component.compartment_id,
                # serving_mode=agentspec_component.serving_mode, not supported yet
                config=client_config,
                name=agentspec_component.name,
                description=agentspec_component.description,
                id=agentspec_component.id,
            )
        elif isinstance(agentspec_component, AgentSpecPluginOllamaEmbeddingConfig):
            # Map to RuntimeOllamaEmbeddingModel
            return RuntimeOllamaEmbeddingModel(
                model_id=agentspec_component.model_id,
                base_url=_format_embedding_model_url(agentspec_component.url),
                name=agentspec_component.name,
                description=agentspec_component.description,
                id=agentspec_component.id,
            )
        elif isinstance(agentspec_component, AgentSpecPluginVllmEmbeddingConfig):
            # Map to RuntimeVllmEmbeddingModel
            return RuntimeVllmEmbeddingModel(
                model_id=agentspec_component.model_id,
                base_url=_format_embedding_model_url(agentspec_component.url),
                name=agentspec_component.name,
                description=agentspec_component.description,
                id=agentspec_component.id,
            )
        elif isinstance(agentspec_component, AgentSpecPluginOpenAiEmbeddingConfig):
            # Map to RuntimeOpenAiEmbeddingModel
            return RuntimeOpenAiEmbeddingModel(
                model_id=agentspec_component.model_id,
                name=agentspec_component.name,
                description=agentspec_component.description,
                id=agentspec_component.id,
                _validate_api_key=False,  # we dont need the API key for the conversion
            )
        elif isinstance(agentspec_component, AgentSpecPluginOpenAiCompatibleEmbeddingConfig):
            # after all others because the agentspec component might also extend this one
            return RuntimeOpenAiCompatibleEmbeddingModel(
                model_id=agentspec_component.model_id,
                base_url=_format_embedding_model_url(agentspec_component.url),
                name=agentspec_component.name,
                description=agentspec_component.description,
                id=agentspec_component.id,
            )
        elif isinstance(agentspec_component, AgentSpecServerTool):
            if agentspec_component.name not in tool_registry:
                raise ValueError(
                    f"The Agent Spec representation includes a tool '{agentspec_component.name}' but"
                    f" this tool does not appear in the tool registry"
                )
            tool = tool_registry[agentspec_component.name]
            if isinstance(tool, RuntimeServerTool):
                return tool
            elif callable(tool):
                return RuntimeServerTool(
                    name=agentspec_component.name,
                    description=agentspec_component.description or "",
                    input_descriptors=[
                        self._convert_property_to_runtime(input_property)
                        for input_property in agentspec_component.inputs or []
                    ],
                    output_descriptors=[
                        self._convert_property_to_runtime(output_property)
                        for output_property in agentspec_component.outputs or []
                    ],
                    func=tool,
                    requires_confirmation=agentspec_component.requires_confirmation,
                    id=agentspec_component.id,
                )
            raise ValueError(f"Unexpected tool type provided in the tool_registry: {type(tool)}")
        elif isinstance(agentspec_component, AgentSpecManagerWorkers):
            for agent in [agentspec_component.group_manager] + agentspec_component.workers:  # type: ignore[assignment]
                if not isinstance(agent, AgentSpecAgent):
                    raise ValueError(
                        f"WayFlow ManagerWorkers only supports agents of type `Agent`, "
                        f"but received `{type(agent).__name__}` instead."
                    )

            return RuntimeManagerWorkers(
                name=agentspec_component.name,
                description=agentspec_component.description or "",
                group_manager=self.convert(
                    agentspec_component.group_manager, tool_registry, converted_components
                ),
                workers=[
                    self.convert(worker, tool_registry, converted_components)
                    for worker in agentspec_component.workers
                ],
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                id=agentspec_component.id,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecPluginManagerWorkers):
            warnings.warn(
                "PluginManagerWorkers is deprecated. Convert to Agent Spec ManagerWorkers instead.",
                DeprecationWarning,
            )
            return RuntimeManagerWorkers(
                name=agentspec_component.name,
                description=agentspec_component.description or "",
                group_manager=self.convert(
                    agentspec_component.group_manager, tool_registry, converted_components
                ),
                workers=[
                    self.convert(worker, tool_registry, converted_components)
                    for worker in agentspec_component.workers
                ],
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                id=agentspec_component.id,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecSwarm):
            for relationship in agentspec_component.relationships:
                for agent in relationship:  # type: ignore[assignment]
                    if not isinstance(agent, AgentSpecAgent):
                        raise ValueError(
                            f"WayFlow Swarm only supports agents of type `Agent`, "
                            f"but received `{type(agent).__name__}` instead."
                        )

            return RuntimeSwarm(
                name=agentspec_component.name,
                description=agentspec_component.description,
                first_agent=self.convert(
                    agentspec_component.first_agent,
                    tool_registry,
                    converted_components,
                ),
                relationships=[
                    (
                        self.convert(sender, tool_registry, converted_components),
                        self.convert(recipient, tool_registry, converted_components),
                    )
                    for sender, recipient in agentspec_component.relationships
                ],
                handoff=agentspec_component.handoff,
                id=agentspec_component.id,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecPluginSwarm):
            warnings.warn(
                "PluginSwarm is deprecated. Convert to Agent Spec Swarm instead.",
                DeprecationWarning,
            )

            return RuntimeSwarm(
                name=agentspec_component.name,
                description=agentspec_component.description,
                first_agent=self.convert(
                    agentspec_component.first_agent,
                    tool_registry,
                    converted_components,
                ),
                relationships=[
                    (
                        self.convert(sender, tool_registry, converted_components),
                        self.convert(recipient, tool_registry, converted_components),
                    )
                    for sender, recipient in agentspec_component.relationships
                ],
                handoff=agentspec_component.handoff,
                id=agentspec_component.id,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecFlow):
            step_id_to_name_mapping: Dict[str, str] = {}
            name_usage_counts: Dict[str, int] = {}
            steps: Dict[str, RuntimeStep] = {}

            def _find_property(properties: List[AgentSpecProperty], name: str) -> AgentSpecProperty:
                return next((property_ for property_ in properties if property_.title == name))

            for agentspec_node in agentspec_component.nodes:
                if agentspec_node.id not in step_id_to_name_mapping:
                    if agentspec_node.name in name_usage_counts:
                        name_usage_counts[agentspec_node.name] += 1
                        step_id_to_name_mapping[agentspec_node.id] = (
                            f"{agentspec_node.name} {name_usage_counts[agentspec_node.name]}"
                        )
                        agentspec_node.name = step_id_to_name_mapping[agentspec_node.id]
                    else:
                        name_usage_counts[agentspec_node.name] = 1
                        step_id_to_name_mapping[agentspec_node.id] = agentspec_node.name

                # We need to infer the unpack strategy for the MapSteps. Therefore, we go over the
                # Agent Spec Flow's MapNodes, and we check the inputs. If they are connected to Lists
                # of the inner flow's input type, we add it to the unpack setting
                if isinstance(agentspec_node, AgentSpecMapNode):
                    unpack_input: Dict[str, str] = {}
                    for data_flow_edge in agentspec_component.data_flow_connections or []:
                        if data_flow_edge.destination_node is agentspec_node:
                            source_property = _find_property(
                                data_flow_edge.source_node.outputs or [],
                                data_flow_edge.source_output,
                            )
                            inner_flow_input_property = _find_property(
                                agentspec_node.subflow.inputs or [],
                                data_flow_edge.destination_input.replace("iterated_", "", 1),
                            )
                            if self._agentspec_properties_have_same_type(
                                source_property,
                                AgentSpecListProperty(item_type=inner_flow_input_property),
                            ):
                                # The type checker is not smart enough to understand that the title of the property
                                # here cannot be None, as it must match the name given to the _find_property function
                                unpack_input[inner_flow_input_property.title] = "."
                    if agentspec_node.id not in converted_components:
                        converted_components[agentspec_node.id] = self._convert_mapnode_to_runtime(
                            agentspec_node,
                            unpack_input=unpack_input,
                            tool_registry=tool_registry,
                            converted_components=converted_components,
                        )
                    runtime_step = converted_components[agentspec_node.id]
                else:
                    runtime_step = self.convert(agentspec_node, tool_registry, converted_components)
                steps[step_id_to_name_mapping[agentspec_node.id]] = runtime_step

            data_flow_edges = [
                self.convert(edge, tool_registry, converted_components)
                for edge in agentspec_component.data_flow_connections or []
            ]
            control_flow_edges: List[RuntimeControlFlowEdge] = [
                self.convert(edge, tool_registry, converted_components)
                for edge in agentspec_component.control_flow_connections
            ]
            for step in steps.values():
                for branch in step.get_branches():
                    edge_exists = any(
                        edge.source_step is step and edge.source_branch == branch
                        for edge in control_flow_edges
                    )
                    if not edge_exists:
                        control_flow_edges.append(
                            RuntimeControlFlowEdge(
                                source_step=step, source_branch=branch, destination_step=None
                            )
                        )
            context_providers = None
            if (
                isinstance(agentspec_component, AgentSpecExtendedFlow)
                and agentspec_component.context_providers is not None
            ):
                context_providers = [
                    self.convert(context_provider, tool_registry, converted_components)
                    for context_provider in agentspec_component.context_providers
                ]
            variables: List[RuntimeVariable] = []
            for value in getattr(agentspec_component, "state", []):
                variables.append(self._convert_property_to_runtime_variable(value))

            flow = RuntimeFlow(
                name=agentspec_component.name,
                description=agentspec_component.description or "",
                begin_step=steps[step_id_to_name_mapping[agentspec_component.start_node.id]],
                control_flow_edges=control_flow_edges,
                data_flow_edges=data_flow_edges,
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                id=agentspec_component.id,
                context_providers=context_providers,
                variables=variables,
                __metadata_info__=metadata_info,
            )
            return (
                RuntimeDescribedFlow(
                    flow=flow,
                    name=agentspec_component.name,
                    description=agentspec_component.description or "",
                )
                if described
                else flow
            )
        elif isinstance(agentspec_component, AgentSpecPluginConstantContextProvider):
            outputs = agentspec_component.outputs
            if outputs is None or len(outputs) < 1:
                raise ValueError(
                    f"ExtendedConstantContextProvider should have an output, but got: {outputs}"
                )
            return RuntimeConstantContextProvider(
                name=agentspec_component.name,
                value=agentspec_component.value,
                output_description=self._convert_property_to_runtime(outputs[0]),
                id=agentspec_component.id,
                description=agentspec_component.description,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecPluginConstantContextProvider):
            outputs = agentspec_component.outputs
            if outputs is None or len(outputs) < 1:
                raise ValueError(
                    f"ExtendedConstantContextProvider should have an output, but got: {outputs}"
                )
            return RuntimeConstantContextProvider(
                name=agentspec_component.name,
                value=agentspec_component.value,
                output_description=self._convert_property_to_runtime(outputs[0]),
                id=agentspec_component.id,
                description=agentspec_component.description,
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecExtendedLlmNode):
            return RuntimePromptExecutionStep(
                prompt_template=(
                    self._convert_prompttemplate_to_runtime(
                        agentspec_component.prompt_template_object,
                        tool_registry,
                        converted_components,
                    )
                    if agentspec_component.prompt_template_object
                    else agentspec_component.prompt_template
                ),
                send_message=agentspec_component.send_message,
                llm=self.convert(
                    agentspec_component.llm_config, tool_registry, converted_components
                ),
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecLlmNode):
            return RuntimePromptExecutionStep(
                prompt_template=agentspec_component.prompt_template,
                llm=self.convert(
                    agentspec_component.llm_config, tool_registry, converted_components
                ),
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecExtendedMapNode):
            return RuntimeMapStep(
                flow=self.convert(agentspec_component.flow, tool_registry, converted_components),
                unpack_input=agentspec_component.unpack_input,
                parallel_execution=agentspec_component.parallel_execution,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecMapNode):
            return self._convert_mapnode_to_runtime(
                agentspec_component,
                tool_registry=tool_registry,
                converted_components=converted_components,
            )
        elif isinstance(agentspec_component, AgentSpecPluginReadVariableNode):
            return RuntimeVariableReadStep(
                variable=self._convert_property_to_runtime_variable(agentspec_component.variable),
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginWriteVariableNode):
            return RuntimeVariableWriteStep(
                variable=self._convert_property_to_runtime_variable(agentspec_component.variable),
                operation=agentspec_component.operation,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecExtendedToolNode):
            # This must come before AgentSpecToolNode because it's a subclass, and the condition fires
            return RuntimeToolExecutionStep(
                tool=self.convert(agentspec_component.tool, tool_registry, converted_components),
                raise_exceptions=agentspec_component.raise_exceptions,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecToolNode):
            return RuntimeToolExecutionStep(
                tool=self.convert(agentspec_component.tool, tool_registry, converted_components),
                raise_exceptions=True,
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginExtractNode):
            output_values: Dict[Union[str, RuntimeProperty], str] = {}
            for k, v in agentspec_component.output_values.items():
                output_values[k] = v
            return RuntimeExtractStep(
                output_values=output_values,
                llm=(
                    self.convert(
                        agentspec_component=agentspec_component.llm_config,
                        tool_registry=tool_registry,
                        converted_components=converted_components,
                    )
                    if agentspec_component.llm_config is not None
                    else None
                ),
                retry=agentspec_component.retry,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecBranchingNode):
            return RuntimeBranchingStep(
                name=agentspec_component.name,
                branch_name_mapping=agentspec_component.mapping,
                input_mapping=(
                    {
                        RuntimeBranchingStep.NEXT_BRANCH_NAME: agentspec_component.inputs[
                            0
                        ].json_schema["title"]
                    }
                    if agentspec_component.inputs
                    else {}
                ),
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                __metadata_info__=metadata_info,
            )
        elif isinstance(agentspec_component, AgentSpecApiNode):
            store_response = False
            # If among the outputs we expect the full http response, we make the ApiStep store it
            # This is preventing us from having to write a full ExtendedApiNode plugin
            if any(
                output.title == "http_response" and output.type == "string"
                for output in (agentspec_component.outputs or [])
            ):
                store_response = True
            return RuntimeApiCallStep(
                url=agentspec_component.url,
                method=agentspec_component.http_method,
                # api_spec_uri=agentspec_component.api_spec_uri,
                # TODO improve behaviour & configurations definition of RemoteTool / ApiNode
                json_body=agentspec_component.data if agentspec_component.data else None,
                params=(
                    agentspec_component.query_params if agentspec_component.query_params else None
                ),
                headers=agentspec_component.headers if agentspec_component.headers else None,
                store_response=store_response,
                output_values_json={
                    output_.title: f".{output_.title}"
                    for output_ in (agentspec_component.outputs or [])
                    if output_.title
                },
                allow_insecure_http=urllib.parse.urlparse(agentspec_component.url).scheme == "http",
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginDatastoreListNode):
            return RuntimeDatastoreListStep(
                datastore=self.convert(
                    agentspec_component.datastore, tool_registry, converted_components
                ),
                collection_name=agentspec_component.collection_name,
                where=agentspec_component.where,
                limit=agentspec_component.limit,
                unpack_single_entity_from_list=agentspec_component.unpack_single_entity_from_list,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginDatastoreDeleteNode):
            return RuntimeDatastoreDeleteStep(
                datastore=self.convert(
                    agentspec_component.datastore, tool_registry, converted_components
                ),
                collection_name=agentspec_component.collection_name,
                where=agentspec_component.where,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginDatastoreUpdateNode):
            return RuntimeDatastoreUpdateStep(
                datastore=self.convert(
                    agentspec_component.datastore, tool_registry, converted_components
                ),
                collection_name=agentspec_component.collection_name,
                where=agentspec_component.where,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginDatastoreQueryNode):
            return RuntimeDatastoreQueryStep(
                datastore=self.convert(
                    agentspec_component.datastore, tool_registry, converted_components
                ),
                query=agentspec_component.query,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginDatastoreCreateNode):
            return RuntimeDatastoreCreateStep(
                datastore=self.convert(
                    agentspec_component.datastore, tool_registry, converted_components
                ),
                collection_name=agentspec_component.collection_name,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginInputMessageNode):
            # The output of the extended input message node might be renamed, but the input message step
            # does not support renaming, so we have to use output mapping
            rt_nodes_arguments = self._get_rt_nodes_arguments(agentspec_component, metadata_info)
            if agentspec_component.outputs:
                output_property = agentspec_component.outputs[0]
                if output_property.title != RuntimeInputMessageStep.USER_PROVIDED_INPUT:
                    rt_nodes_arguments["output_mapping"][
                        RuntimeInputMessageStep.USER_PROVIDED_INPUT
                    ] = output_property.title
            return RuntimeInputMessageStep(
                message_template=agentspec_component.message_template,
                rephrase=agentspec_component.rephrase,
                llm=(
                    self.convert(
                        agentspec_component.llm_config, tool_registry, converted_components
                    )
                    if agentspec_component.llm_config
                    else None
                ),
                **rt_nodes_arguments,
            )
        elif isinstance(agentspec_component, AgentSpecInputMessageNode):
            # The output of the extended input message node might be renamed, but the input message step
            # does not support renaming, so we have to use output mapping
            rt_nodes_arguments = self._get_node_arguments(agentspec_component, metadata_info)
            if agentspec_component.outputs:
                output_property = agentspec_component.outputs[0]
                if output_property.title != RuntimeInputMessageStep.USER_PROVIDED_INPUT:
                    rt_nodes_arguments["output_mapping"] = {
                        RuntimeInputMessageStep.USER_PROVIDED_INPUT: output_property.title
                    }
            return RuntimeInputMessageStep(
                message_template=None,
                rephrase=False,
                llm=None,
                **rt_nodes_arguments,
            )
        elif isinstance(agentspec_component, AgentSpecPluginOutputMessageNode):
            return RuntimeOutputMessageStep(
                message_template=agentspec_component.message,
                message_type=agentspec_component.message_type,
                rephrase=agentspec_component.rephrase,
                llm=(
                    self.convert(
                        agentspec_component.llm_config, tool_registry, converted_components
                    )
                    if agentspec_component.llm_config
                    else None
                ),
                expose_message_as_output=agentspec_component.expose_message_as_output,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecOutputMessageNode):
            return RuntimeOutputMessageStep(
                message_template=agentspec_component.message,
                message_type=MessageType.AGENT,
                rephrase=False,
                llm=None,
                expose_message_as_output=False,
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginCatchExceptionNode):
            return RuntimeCatchExceptionStep(
                flow=self.convert(agentspec_component.flow, tool_registry, converted_components),
                catch_all_exceptions=agentspec_component.catch_all_exceptions,
                except_on=agentspec_component.except_on,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginRegexNode):
            regex_pattern = self._regex_pattern_to_runtime(agentspec_component.regex_pattern)
            if not (
                isinstance(regex_pattern, str) or isinstance(regex_pattern, RuntimeRegexPattern)
            ):
                raise ValueError(
                    f"Runtime RegexExtractionStep only supports str and RegexPattern, not {regex_pattern}"
                )
            return RuntimeRegexExtractionStep(
                regex_pattern=regex_pattern,
                return_first_match_only=agentspec_component.return_first_match_only,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginTemplateNode):
            return RuntimeTemplateRenderingStep(
                template=agentspec_component.template,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecPluginChoiceNode):
            next_steps: List[Union[Tuple[str, str], Tuple[str, str, str], StepDescription]] = []
            for branch_description in agentspec_component.next_branches:
                if len(branch_description) == 2:
                    step_name, step_description = branch_description
                    next_steps.append((step_name, step_description))
                elif len(branch_description) == 3:
                    step_name, step_description, step_display_name = branch_description
                    next_steps.append((step_name, step_description, step_display_name))
                else:
                    raise ValueError(
                        "The elements of `next_branches` of a PluginChoiceNode must have length 2 or 3"
                    )
            return RuntimeChoiceSelectionStep(
                llm=self.convert(
                    agentspec_component.llm_config, tool_registry, converted_components
                ),
                next_steps=next_steps,
                prompt_template=agentspec_component.prompt_template,
                num_tokens=agentspec_component.num_tokens,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecRemoteTool):
            return RuntimeRemoteTool(
                tool_name=agentspec_component.name,
                tool_description=agentspec_component.description or "missing description",
                url=agentspec_component.url,
                method=agentspec_component.http_method,
                allow_insecure_http=urllib.parse.urlparse(agentspec_component.url).scheme == "http",
                # api_spec_uri=agentspec_component.api_spec_uri,
                # TODO improve behaviour & configurations definition of RemoteTool / ApiNode
                json_body=agentspec_component.data if agentspec_component.data else None,
                params=(
                    agentspec_component.query_params if agentspec_component.query_params else None
                ),
                headers=agentspec_component.headers if agentspec_component.headers else None,
                requires_confirmation=agentspec_component.requires_confirmation,
                **self._get_component_arguments(agentspec_component),
            )

        elif isinstance(agentspec_component, AgentSpecClientTool):
            return RuntimeClientTool(
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                requires_confirmation=agentspec_component.requires_confirmation,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, (AgentSpecPluginMCPToolSpec, AgentSpecMCPToolSpec)):
            return RuntimeTool(
                input_descriptors=[
                    self._convert_property_to_runtime(input_property)
                    for input_property in agentspec_component.inputs or []
                ],
                output_descriptors=[
                    self._convert_property_to_runtime(output_property)
                    for output_property in agentspec_component.outputs or []
                ],
                requires_confirmation=agentspec_component.requires_confirmation,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(
            agentspec_component, (AgentSpecPluginClientTransport, AgentSpecClientTransport)
        ):
            if isinstance(
                agentspec_component, (AgentSpecPluginStdioTransport, AgentSpecStdioTransport)
            ):
                if isinstance(agentspec_component, AgentSpecPluginStdioTransport):
                    return RuntimeStdioTransport(
                        command=agentspec_component.command,
                        args=agentspec_component.args,
                        env=agentspec_component.env,
                        cwd=agentspec_component.cwd,
                        encoding=agentspec_component.encoding,
                        encoding_error_handler=agentspec_component.encoding_error_handler,
                    )
                return RuntimeStdioTransport(
                    command=agentspec_component.command,
                    args=agentspec_component.args,
                    env=agentspec_component.env,
                    cwd=agentspec_component.cwd,
                )

            class SupportsTimeoutKwargs(TypedDict, total=False):
                timeout: float
                sse_read_timeout: float
                id: str

            kwargs: SupportsTimeoutKwargs = dict(
                id=agentspec_component.id,
            )
            if isinstance(agentspec_component, AgentSpecPluginRemoteBaseTransport):
                kwargs.update(
                    dict(
                        timeout=agentspec_component.timeout,
                        sse_read_timeout=agentspec_component.sse_read_timeout,
                    )
                )
            if isinstance(
                agentspec_component, (AgentSpecPluginSSEmTLSTransport, AgentSpecSSEmTLSTransport)
            ):
                return RuntimeSSEmTLSTransport(
                    url=agentspec_component.url,
                    headers=agentspec_component.headers,
                    # auth is not supported yet
                    key_file=agentspec_component.key_file,
                    cert_file=agentspec_component.cert_file,
                    ssl_ca_cert=agentspec_component.ca_file,
                    **kwargs,
                )
            elif isinstance(
                agentspec_component, (AgentSpecPluginSSETransport, AgentSpecSSETransport)
            ):
                return RuntimeSSETransport(
                    url=agentspec_component.url, headers=agentspec_component.headers, **kwargs
                )
            elif isinstance(
                agentspec_component,
                (AgentSpecPluginStreamableHTTPmTLSTransport, AgentSpecStreamableHTTPmTLSTransport),
            ):
                return RuntimeStreamableHTTPmTLSTransport(
                    url=agentspec_component.url,
                    headers=agentspec_component.headers,
                    # auth is not supported yet
                    key_file=agentspec_component.key_file,
                    cert_file=agentspec_component.cert_file,
                    ssl_ca_cert=agentspec_component.ca_file,
                    **kwargs,
                )
            elif isinstance(
                agentspec_component,
                (AgentSpecPluginStreamableHTTPTransport, AgentSpecStreamableHTTPTransport),
            ):
                return RuntimeStreamableHTTPTransport(
                    url=agentspec_component.url,
                    headers=agentspec_component.headers,
                    # auth is not supported yet
                    **kwargs,
                )
            else:
                raise ValueError(
                    f"Agent Spec ClientTransport '{agentspec_component.__class__.__name__}' is not supported yet."
                )
        elif isinstance(agentspec_component, (AgentSpecPluginMCPToolBox, AgentSpecMCPToolBox)):
            tool_filter = (
                [
                    (
                        tool_
                        if isinstance(tool_, str)
                        else self.convert(tool_, tool_registry, converted_components)
                    )
                    for tool_ in agentspec_component.tool_filter
                ]
                if agentspec_component.tool_filter is not None
                else None
            )
            return RuntimeMCPToolBox(
                client_transport=self.convert(
                    agentspec_component.client_transport, tool_registry, converted_components
                ),
                tool_filter=tool_filter,
                **self._get_component_arguments(agentspec_component),
                _validate_mcp_client_transport=False,
            )
        elif isinstance(agentspec_component, AgentSpecAgentNode):
            return RuntimeAgentExecutionStep(
                agent=self.convert(agentspec_component.agent, tool_registry, converted_components),
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecExtendedAgentNode):
            return RuntimeAgentExecutionStep(
                agent=self.convert(agentspec_component.agent, tool_registry, converted_components),
                caller_input_mode=agentspec_component.caller_input_mode,
                **self._get_rt_nodes_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecFlowNode):
            return RuntimeFlowExecutionStep(
                flow=self.convert(agentspec_component.subflow, tool_registry, converted_components),
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecStartNode):
            return RuntimeStartStep(**self._get_node_arguments(agentspec_component, metadata_info))
        elif isinstance(agentspec_component, AgentSpecEndNode):
            return RuntimeCompleteStep(
                branch_name=(
                    agentspec_component.branch_name
                    if agentspec_component.name != agentspec_component.branch_name
                    else None
                ),
                **self._get_node_arguments(agentspec_component, metadata_info),
            )
        elif isinstance(agentspec_component, AgentSpecControlFlowEdge):
            return RuntimeControlFlowEdge(
                source_step=self.convert(
                    agentspec_component.from_node, tool_registry, converted_components
                ),
                source_branch=(
                    agentspec_component.from_branch
                    if agentspec_component.from_branch
                    else RuntimeStep.BRANCH_NEXT
                ),
                destination_step=self.convert(
                    agentspec_component.to_node, tool_registry, converted_components
                ),
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecDataFlowEdge):
            return RuntimeDataFlowEdge(
                source_step=self.convert(
                    agentspec_component.source_node, tool_registry, converted_components
                ),
                source_output=agentspec_component.source_output,
                destination_step=self.convert(
                    agentspec_component.destination_node, tool_registry, converted_components
                ),
                destination_input=agentspec_component.destination_input,
                **self._get_component_arguments(agentspec_component),
            )
        elif isinstance(agentspec_component, AgentSpecPluginInMemoryDatastore):
            return RuntimeInMemoryDatastore(
                schema={
                    k: self._convert_entity_to_runtime(v)
                    for k, v in agentspec_component.datastore_schema.items()
                },
                id=agentspec_component.id,
            )
        elif isinstance(agentspec_component, AgentSpecPluginTlsOracleDatabaseConnectionConfig):
            return RuntimeTlsOracleDatabaseConnectionConfig(
                user=agentspec_component.user,
                password=agentspec_component.password,
                dsn=agentspec_component.dsn,
                config_dir=agentspec_component.config_dir,
            )
        elif isinstance(agentspec_component, AgentSpecPluginMTlsOracleDatabaseConnectionConfig):
            return RuntimeMTlsOracleDatabaseConnectionConfig(
                config_dir=agentspec_component.config_dir,
                dsn=agentspec_component.dsn,
                user=agentspec_component.user,
                password=agentspec_component.password,
                wallet_location=agentspec_component.wallet_location,
                wallet_password=agentspec_component.wallet_password,
            )
        elif isinstance(agentspec_component, AgentSpecPluginOracleDatabaseDatastore):
            return RuntimeOracleDatabaseDatastore(
                schema={
                    k: self._convert_entity_to_runtime(v)
                    for k, v in agentspec_component.datastore_schema.items()
                },
                connection_config=self.convert(
                    agentspec_component.connection_config, tool_registry, converted_components
                ),
            )
        elif isinstance(agentspec_component, AgentSpecPluginMessageTransform):
            if isinstance(agentspec_component, AgentSpecPluginCoalesceSystemMessagesTransform):
                return RuntimewCoalesceSystemMessagesTransform()
            elif isinstance(agentspec_component, AgentSpecPluginRemoveEmptyNonUserMessageTransform):
                return RuntimeRemoveEmptyNonUserMessageTransform()
            elif isinstance(
                agentspec_component,
                AgentSpecPluginAppendTrailingSystemMessageToUserMessageTransform,
            ):
                return RuntimeAppendTrailingSystemMessageToUserMessageTransform()
            elif isinstance(
                agentspec_component, AgentSpecPluginLlamaMergeToolRequestAndCallsTransform
            ):
                return RuntimeLlamaMergeToolRequestAndCallsTransform()
            elif isinstance(
                agentspec_component, AgentSpecPluginReactMergeToolRequestAndCallsTransform
            ):
                return RuntimeReactMergeToolRequestAndCallsTransform()
            elif isinstance(agentspec_component, AgentSpecPluginSwarmToolRequestAndCallsTransform):
                return RuntimeSwarmToolRequestAndCallsTransform()
            raise ValueError(f"Unsupported type of MessageTransform: {type(agentspec_component)}")

        elif isinstance(agentspec_component, AgentSpecPluginOutputParser):
            if isinstance(agentspec_component, AgentSpecPluginRegexOutputParser):

                return RuntimeRegexOutputParser(
                    regex_pattern=self._regex_pattern_to_runtime(agentspec_component.regex_pattern),
                    strict=agentspec_component.strict,
                    id=agentspec_component.id,
                )
            elif isinstance(agentspec_component, AgentSpecPluginJsonOutputParser):
                return RuntimeJsonOutputParser(
                    properties=agentspec_component.properties,
                    id=agentspec_component.id,
                )
            elif isinstance(agentspec_component, AgentSpecPluginJsonToolOutputParser):
                return RuntimeJsonToolOutputParser(
                    tools=(
                        [
                            self.convert(t, tool_registry, converted_components)
                            for t in agentspec_component.tools
                        ]
                        if agentspec_component.tools
                        else None
                    ),
                    id=agentspec_component.id,
                )
            elif isinstance(agentspec_component, AgentSpecPluginPythonToolOutputParser):
                return RuntimePythonToolOutputParser(
                    tools=(
                        [
                            self.convert(t, tool_registry, converted_components)
                            for t in agentspec_component.tools
                        ]
                        if agentspec_component.tools
                        else None
                    ),
                    id=agentspec_component.id,
                )
            elif isinstance(agentspec_component, AgentSpecPluginReactToolOutputParser):
                return RuntimeReactToolOutputParser(
                    tools=(
                        [
                            self.convert(t, tool_registry, converted_components)
                            for t in agentspec_component.tools
                        ]
                        if agentspec_component.tools
                        else None
                    ),
                    id=agentspec_component.id,
                )
            raise ValueError(f"Unsupported type of OutputParser: {type(agentspec_component)}")
        elif isinstance(agentspec_component, AgentSpecPluginPromptTemplate):
            return self._convert_prompttemplate_to_runtime(
                agentspec_template=agentspec_component,
                tool_registry=tool_registry,
                converted_components=converted_components,
            )
        elif isinstance(agentspec_component, AgentSpecComponent):
            raise NotImplementedError(
                f"The Agent Spec type '{agentspec_component.__class__.__name__}' is not yet supported "
                f"for conversion."
            )
        else:
            raise TypeError(
                f"Expected object of type 'pyagentspec.component.Component', but got "
                f"{type(agentspec_component)} instead"
            )

    def _regex_pattern_to_runtime(
        self,
        agentspec_component: Union[
            str, AgentSpecPluginRegexPattern, Dict[str, str | AgentSpecPluginRegexPattern]
        ],
    ) -> str | RuntimeRegexPattern | Dict[str, str | RuntimeRegexPattern]:
        regex_pattern: str | RuntimeRegexPattern | Dict[str, str | RuntimeRegexPattern]
        if isinstance(agentspec_component, str):
            regex_pattern = agentspec_component
        elif isinstance(agentspec_component, AgentSpecPluginRegexPattern):
            regex_pattern = RuntimeRegexPattern(
                pattern=agentspec_component.pattern,
                match=agentspec_component.match,
                flags=agentspec_component.flags,
            )
        else:
            regex_pattern = {
                k: (
                    v
                    if isinstance(v, str)
                    else RuntimeRegexPattern(pattern=v.pattern, match=v.match, flags=v.flags)
                )
                for k, v in agentspec_component.items()
            }
        return regex_pattern

    def _get_rt_nodes_arguments(
        self, agentspec_component: AgentSpecExtendedNode, metadata_info: Any
    ) -> Dict[str, Any]:
        return dict(
            **self._get_node_arguments(agentspec_component, metadata_info),
            input_mapping=agentspec_component.input_mapping,
            output_mapping=agentspec_component.output_mapping,
        )

    def _get_node_arguments(
        self, agentspec_component: AgentSpecNode, metadata_info: Any
    ) -> Dict[str, Any]:
        metadata_info[METADATA_ID_KEY] = agentspec_component.id
        return dict(
            input_descriptors=[
                self._convert_property_to_runtime(input_property)
                for input_property in agentspec_component.inputs or []
            ],
            output_descriptors=[
                self._convert_property_to_runtime(output_property)
                for output_property in agentspec_component.outputs or []
            ],
            name=agentspec_component.name,
            __metadata_info__=metadata_info,
        )

    def _get_component_arguments(self, agentspec_component: AgentSpecComponent) -> Dict[str, Any]:
        return dict(
            name=agentspec_component.name,
            id=agentspec_component.id,
            description=agentspec_component.description,
            __metadata_info__=(agentspec_component.metadata or {}).get("__metadata_info__", {}),
        )
