# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import uuid
from dataclasses import MISSING, fields, is_dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast
from warnings import warn

from pyagentspec.a2aagent import A2AAgent as AgentSpecA2AAgent
from pyagentspec.a2aagent import A2AConnectionConfig as AgentSpecA2AConnectionConfig
from pyagentspec.a2aagent import A2ASessionParameters as AgentSpecA2ASessionParameters
from pyagentspec.agent import Agent as AgentSpecAgent
from pyagentspec.component import Component as AgentSpecComponent
from pyagentspec.datastores import Datastore as AgentSpecDatastore
from pyagentspec.datastores import InMemoryCollectionDatastore as AgentSpecInMemoryDatastore
from pyagentspec.datastores import (
    MTlsOracleDatabaseConnectionConfig as AgentSpecMTlsOracleDatabaseConnectionConfig,
)
from pyagentspec.datastores import (
    OracleDatabaseConnectionConfig as AgentSpecOracleDatabaseConnectionConfig,
)
from pyagentspec.datastores import OracleDatabaseDatastore as AgentSpecOracleDatabaseDatastore
from pyagentspec.datastores import PostgresDatabaseDatastore as AgentSpecPostgresDatabaseDatastore
from pyagentspec.datastores import RelationalDatastore as AgentSpecRelationalDatastore
from pyagentspec.datastores import (
    TlsOracleDatabaseConnectionConfig as AgentSpecTlsOracleDatabaseConnectionConfig,
)
from pyagentspec.datastores import (
    TlsPostgresDatabaseConnectionConfig as AgentSpecTlsPostgresDatabaseConnectionConfig,
)
from pyagentspec.flows.edges import ControlFlowEdge as AgentSpecControlFlowEdge
from pyagentspec.flows.edges import DataFlowEdge as AgentSpecDataFlowEdge
from pyagentspec.flows.flow import Flow as AgentSpecFlow
from pyagentspec.flows.node import Node as AgentSpecNode
from pyagentspec.flows.nodes import AgentNode as AgentSpecAgentNode
from pyagentspec.flows.nodes import ApiNode as AgentSpecApiNode
from pyagentspec.flows.nodes import BranchingNode as AgentSpecBranchingNode
from pyagentspec.flows.nodes import EndNode as AgentSpecEndNode
from pyagentspec.flows.nodes import FlowNode as AgentSpecFlowNode
from pyagentspec.flows.nodes import InputMessageNode as AgentSpecInputMessageNode
from pyagentspec.flows.nodes import LlmNode as AgentSpecLlmNode
from pyagentspec.flows.nodes import MapNode as AgentSpecMapNode
from pyagentspec.flows.nodes import OutputMessageNode as AgentSpecOutputMessageNode
from pyagentspec.flows.nodes import ParallelFlowNode as AgentSpecParallelFlowNode
from pyagentspec.flows.nodes import ParallelMapNode as AgentSpecParallelMapNode
from pyagentspec.flows.nodes import StartNode as AgentSpecStartNode
from pyagentspec.flows.nodes import ToolNode as AgentSpecToolNode
from pyagentspec.flows.nodes.mapnode import ReductionMethod
from pyagentspec.llms import LlmConfig as AgentSpecLlmConfig
from pyagentspec.llms import OciGenAiConfig as AgentSpecOciGenAiModel
from pyagentspec.llms import OpenAiConfig as AgentSpecOpenAiConfig
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
from pyagentspec.llms.ocigenaiconfig import ModelProvider as AgentSpecModelProvider
from pyagentspec.llms.ocigenaiconfig import ServingMode as AgentSpecOciGenAiServingMode
from pyagentspec.llms.ollamaconfig import OllamaConfig as AgentSpecOllamaModel
from pyagentspec.llms.openaicompatibleconfig import OpenAIAPIType as AgentSpecOpenAIAPIType
from pyagentspec.llms.openaicompatibleconfig import (
    OpenAiCompatibleConfig as AgentSpecOpenAiCompatibleConfig,
)
from pyagentspec.llms.vllmconfig import VllmConfig as AgentSpecVllmModel
from pyagentspec.managerworkers import ManagerWorkers as AgentSpecManagerWorkers
from pyagentspec.mcp import MCPToolBox as AgentSpecMCPToolBox
from pyagentspec.mcp import MCPToolSpec as AgentSpecMCPToolSpec
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
from pyagentspec.ociagent import OciAgent as AgentSpecOciAgent
from pyagentspec.property import Property as AgentSpecProperty
from pyagentspec.serialization import ComponentSerializationPlugin
from pyagentspec.swarm import HandoffMode as AgentSpecHandoffMode
from pyagentspec.swarm import Swarm as AgentSpecSwarm
from pyagentspec.tools import ClientTool as AgentSpecClientTool
from pyagentspec.tools import RemoteTool as AgentSpecRemoteTool
from pyagentspec.tools import ServerTool as AgentSpecServerTool
from pyagentspec.tools import Tool as AgentSpecTool
from pyagentspec.tools import ToolBox as AgentSpecToolBox
from pyagentspec.transforms import (
    ConversationSummarizationTransform as AgentSpecConversationSummarizationTransform,
)
from pyagentspec.transforms import (
    MessageSummarizationTransform as AgentSpecMessageSummarizationTransform,
)
from pyagentspec.transforms import MessageTransform as AgentSpecMessageTransform

from wayflowcore._metadata import METADATA_KEY
from wayflowcore._utils._templating_helpers import MessageAsDictT as RuntimeMessageAsDictT
from wayflowcore.a2a.a2aagent import A2AAgent as RuntimeA2AAgent
from wayflowcore.a2a.a2aagent import A2AConnectionConfig as RuntimeA2AConnectionConfig
from wayflowcore.agent import Agent as RuntimeAgent
from wayflowcore.agent import CallerInputMode
from wayflowcore.agentspec.components import (
    ExtendedParallelFlowNode as AgentSpecExtendedParallelFlowNode,
)
from wayflowcore.agentspec.components import (
    ExtendedParallelMapNode as AgentSpecExtendedParallelMapNode,
)
from wayflowcore.agentspec.components import PluginEmbeddingConfig as AgentSpecPluginEmbeddingConfig
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
from wayflowcore.agentspec.components import all_serialization_plugin
from wayflowcore.agentspec.components.agent import ExtendedAgent as AgentSpecExtendedAgent
from wayflowcore.agentspec.components.contextprovider import (
    PluginConstantContextProvider as AgentSpecPluginConstantContextProvider,
)
from wayflowcore.agentspec.components.contextprovider import (
    PluginContextProvider as AgentSpecPluginContextProvider,
)
from wayflowcore.agentspec.components.contextprovider import (
    PluginFlowContextProvider as AgentSpecPluginFlowContextProvider,
)
from wayflowcore.agentspec.components.contextprovider import (
    PluginToolContextProvider as AgentSpecPluginToolContextProvider,
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
from wayflowcore.agentspec.components.flow import ExtendedFlow as AgentSpecExtendedFlow
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
from wayflowcore.agentspec.components.nodes import PluginVariableNode as AgentSpecPluginVariableNode
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
from wayflowcore.agentspec.components.template import (
    PluginPromptTemplate as AgentSpecPluginPromptTemplate,
)
from wayflowcore.agentspec.components.tools import PluginToolBox as AgentSpecPluginToolBox
from wayflowcore.agentspec.components.tools import PluginToolRequest as AgentSpecPluginToolRequest
from wayflowcore.agentspec.components.tools import PluginToolResult as AgentSpecPluginToolResult
from wayflowcore.agentspec.components.transforms import (
    PluginAppendTrailingSystemMessageToUserMessageTransform as AgentSpecPluginAppendTrailingSystemMessageToUserMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginCanonicalizationMessageTransform as AgentSpecPluginCanonicalizationMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginCoalesceSystemMessagesTransform as AgentSpecPluginCoalesceSystemMessagesTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginLlamaMergeToolRequestAndCallsTransform as AgentSpecPluginLlamaMergeToolRequestAndCallsTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginReactMergeToolRequestAndCallsTransform as AgentSpecPluginReactMergeToolRequestAndCallsTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginRemoveEmptyNonUserMessageTransform as AgentSpecPluginRemoveEmptyNonUserMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginSplitPromptOnMarkerMessageTransform as AgentSpecPluginSplitPromptOnMarkerMessageTransform,
)
from wayflowcore.agentspec.components.transforms import (
    PluginSwarmToolRequestAndCallsTransform as AgentSpecPluginSwarmToolRequestAndCallsTransform,
)
from wayflowcore.contextproviders import ContextProvider as RuntimeContextProvider
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
from wayflowcore.datastore import Datastore as RuntimeDatastore
from wayflowcore.datastore import Entity as RuntimeEntity
from wayflowcore.datastore.inmemory import InMemoryDatastore as RuntimeInMemoryDatastore
from wayflowcore.datastore.oracle import (
    MTlsOracleDatabaseConnectionConfig as RuntimeMTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.oracle import (
    OracleDatabaseConnectionConfig as RuntimeOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.oracle import OracleDatabaseDatastore as RuntimeOracleDatabaseDatastore
from wayflowcore.datastore.oracle import (
    TlsOracleDatabaseConnectionConfig as RuntimeTlsOracleDatabaseConnectionConfig,
)
from wayflowcore.datastore.postgres import (
    PostgresDatabaseConnectionConfig as RuntimePostgresDatabaseConnectionConfig,
)
from wayflowcore.datastore.postgres import (
    PostgresDatabaseDatastore as RuntimePostgresDatabaseDatastore,
)
from wayflowcore.datastore.postgres import (
    TlsPostgresDatabaseConnectionConfig as RuntimeTlsPostgresDatabaseConnectionConfig,
)
from wayflowcore.embeddingmodels import EmbeddingModel as RuntimeEmbeddingModel
from wayflowcore.embeddingmodels import OCIGenAIEmbeddingModel as RuntimeOCIGenAIEmbeddingModel
from wayflowcore.embeddingmodels import OllamaEmbeddingModel as RuntimeOllamaEmbeddingModel
from wayflowcore.embeddingmodels import (
    OpenAICompatibleEmbeddingModel as RuntimeOpenAiCompatibleEmbeddingModel,
)
from wayflowcore.embeddingmodels import OpenAIEmbeddingModel as RuntimeOpenAiEmbeddingModel
from wayflowcore.embeddingmodels import VllmEmbeddingModel as RuntimeVllmEmbeddingModel
from wayflowcore.flow import Flow as RuntimeFlow
from wayflowcore.managerworkers import ManagerWorkers as RuntimeManagerWorkers
from wayflowcore.mcp import MCPToolBox as RuntimeMCPToolBox
from wayflowcore.mcp.clienttransport import ClientTransport as RuntimeClientTransport
from wayflowcore.mcp.clienttransport import HTTPmTLSBaseTransport as RuntimeHTTPmTLSBaseTransport
from wayflowcore.mcp.clienttransport import RemoteBaseTransport as RuntimeRemoteBaseTransport
from wayflowcore.mcp.clienttransport import SessionParameters as RuntimeSessionParameters
from wayflowcore.mcp.clienttransport import SSEmTLSTransport as RuntimeSSEmTLSTransport
from wayflowcore.mcp.clienttransport import SSETransport as RuntimeSSETransport
from wayflowcore.mcp.clienttransport import StdioTransport as RuntimeStdioTransport
from wayflowcore.mcp.clienttransport import (
    StreamableHTTPmTLSTransport as RuntimeStreamableHTTPmTLSTransport,
)
from wayflowcore.mcp.clienttransport import (
    StreamableHTTPTransport as RuntimeStreamableHTTPTransport,
)
from wayflowcore.mcp.tools import MCPTool as RuntimeMCPTool
from wayflowcore.messagelist import ImageContent as RuntimeImageContent
from wayflowcore.messagelist import Message as RuntimeMessage
from wayflowcore.messagelist import MessageContent as RuntimeMessageContent
from wayflowcore.messagelist import MessageType
from wayflowcore.messagelist import TextContent as RuntimeTextContent
from wayflowcore.models import LlmModel as RuntimeLlmModel
from wayflowcore.models import OCIGenAIModel as RuntimeOCIGenAIModel
from wayflowcore.models import OllamaModel as RuntimeOllamaModel
from wayflowcore.models import OpenAIAPIType as RuntimeOpenAIAPIType
from wayflowcore.models import OpenAIModel as RuntimeOpenAIModel
from wayflowcore.models import VllmModel as RuntimeVllmModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig as RuntimeLlmGenerationConfig
from wayflowcore.models.ociclientconfig import OCIClientConfig as RuntimeOCIClientConfig
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
from wayflowcore.models.ociclientconfig import (
    OCIClientConfigWithUserAuthentication as RuntimeOCIClientConfigWithUserAuthentication,
)
from wayflowcore.models.openaicompatiblemodel import EMPTY_API_KEY
from wayflowcore.models.openaicompatiblemodel import (
    OpenAICompatibleModel as RuntimeOpenAICompatibleModel,
)
from wayflowcore.ociagent import OciAgent as RuntimeOciAgent
from wayflowcore.outputparser import JsonOutputParser as RuntimeJsonOutputParser
from wayflowcore.outputparser import JsonToolOutputParser as RuntimeJsonToolOutputParser
from wayflowcore.outputparser import OutputParser as RuntimeOutputParser
from wayflowcore.outputparser import PythonToolOutputParser as RuntimePythonToolOutputParser
from wayflowcore.outputparser import RegexOutputParser as RuntimeRegexOutputParser
from wayflowcore.outputparser import RegexPattern as RuntimeRegexPattern
from wayflowcore.property import Property as RuntimeProperty
from wayflowcore.serialization._builtins_components import _BUILTIN_COMPONENTS
from wayflowcore.serialization.context import SerializationContext
from wayflowcore.serialization.plugins import WayflowSerializationPlugin
from wayflowcore.serialization.serializer import SerializableObject
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
from wayflowcore.steps.mapstep import ParallelMapStep as RuntimeParallelMapStep
from wayflowcore.steps.parallelflowexecutionstep import (
    ParallelFlowExecutionStep as RuntimeParallelFlowExecutionStep,
)
from wayflowcore.steps.retrystep import RetryStep as RuntimeRetryStep
from wayflowcore.steps.step import Step as RuntimeStep
from wayflowcore.steps.variablesteps.variablereadstep import (
    VariableReadStep as RuntimeVariableReadStep,
)
from wayflowcore.steps.variablesteps.variablestep import VariableStep as RuntimeVariableStep
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
from wayflowcore.tools import DescribedAgent as RuntimeDescribedAgent
from wayflowcore.tools import DescribedFlow as RuntimeDescribedFlow
from wayflowcore.tools import RemoteTool as RuntimeRemoteTool
from wayflowcore.tools import ServerTool as RuntimeServerTool
from wayflowcore.tools import Tool as RuntimeTool
from wayflowcore.tools import ToolBox as RuntimeToolBox
from wayflowcore.tools.servertools import _FlowAsToolCallable
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform as RuntimeAppendTrailingSystemMessageToUserMessageTransform,
)
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform as RuntimewCoalesceSystemMessagesTransform,
)
from wayflowcore.transforms import MessageTransform as RuntimeMessageTransform
from wayflowcore.transforms import (
    RemoveEmptyNonUserMessageTransform as RuntimeRemoveEmptyNonUserMessageTransform,
)
from wayflowcore.transforms.canonicalizationtransform import (
    CanonicalizationMessageTransform as RuntimeCanonicalizationMessageTransform,
)
from wayflowcore.transforms.summarization import (
    ConversationSummarizationTransform as RuntimeConversationSummarizationTransform,
)
from wayflowcore.transforms.summarization import (
    MessageSummarizationTransform as RuntimeMessageSummarizationTransform,
)
from wayflowcore.transforms.transforms import (
    SplitPromptOnMarkerMessageTransform as RuntimeSplitPromptOnMarkerMessageTransform,
)
from wayflowcore.variable import Variable as RuntimeVariable

if TYPE_CHECKING:
    from wayflowcore.agentspec._agentspecconverter import WayflowToAgentSpecConversionContext


JsonSchemaType = Dict[str, Any]


def has_default_value_for_attribute(obj: Any, attr: str) -> bool:
    """Return the default value of a dataclass attribute."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise AttributeError(f"Passed object is not a dataclass instance: {obj}")

    for f in fields(obj):
        if f.name == attr:
            if f.default is not MISSING:
                return bool(f.default == getattr(obj, f.name))
            if f.default_factory is not MISSING:
                return bool(f.default_factory() == getattr(obj, f.name))
            raise AttributeError(f"No default value for field '{attr}'")
    raise AttributeError(f"'{obj.__class__.__name__}' has no field named '{attr}'")


def generate_id() -> str:
    return str(uuid.uuid4())


def _create_agentspec_metadata_from_runtime_component(
    runtime_component: SerializableObject,
) -> Dict[str, Any]:
    return {METADATA_KEY: getattr(runtime_component, METADATA_KEY, {})}


def _normalize_type_to_anyof(json_schema: JsonSchemaType) -> List[JsonSchemaType]:
    # Normalization merges type and anyOf in anyOf
    # It means that we make the types become elements in the list of json_schemas in anyOf
    if "type" not in json_schema:
        return []
    json_schema_type = json_schema["type"]
    if isinstance(json_schema_type, str):
        json_schema_type = [json_schema_type]
    all_types: List[JsonSchemaType] = []
    for type_ in json_schema_type:
        if type_ == "array":
            # If one of the basic types is array, we put the items definition in it
            all_types.append({"type": "array", "items": json_schema.get("items", {})})
        elif type_ == "object":
            # If one of the basic types is object, we put the properties definition in it
            all_types.append(
                {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
                    "additionalProperties": json_schema.get("additionalProperties", {}),
                }
            )
        else:
            # Normally we just carry over the basic type
            all_types.append({"type": type_})
    return all_types


def _json_schemas_have_same_type(
    json_schema_a: JsonSchemaType, json_schema_b: JsonSchemaType
) -> bool:
    # Basic types must match
    if "anyOf" in json_schema_a or "anyOf" in json_schema_b:
        # We need to combine anyOf and the list of types specified in type
        # We normalize them to another json_schema, so that we can compare them afterward using this method
        json_schema_a_type_list = [
            # We keep only the anyOf that actually define a type
            anyof_type
            for anyof_type in json_schema_a.get("anyOf", [])
            if "type" in anyof_type or "anyOf" in anyof_type
        ] + _normalize_type_to_anyof(json_schema_a)
        json_schema_b_type_list = [
            # We keep only the anyOf that actually define a type
            anyof_type
            for anyof_type in json_schema_b.get("anyOf", [])
            if "type" in anyof_type or "anyOf" in anyof_type
        ] + _normalize_type_to_anyof(json_schema_b)
        # For now, we ignore allOf and oneOf
        # We make sure that the set of possible types overlap correctly (same length, same elements)
        if len(json_schema_a_type_list) != len(json_schema_b_type_list):
            return False
        for json_schema_a_type in json_schema_a_type_list:
            if not any(
                _json_schemas_have_same_type(json_schema_a_type, json_schema_b_type)
                for json_schema_b_type in json_schema_b_type_list
            ):
                return False
    else:
        # We transform the list (or single string) of types in a set
        json_schema_a_type = json_schema_a.get("type", [])
        unique_json_schema_a_type = set(
            [json_schema_a_type] if isinstance(json_schema_a_type, str) else json_schema_a_type
        )
        json_schema_b_type = json_schema_b.get("type", [])
        unique_json_schema_b_type = set(
            [json_schema_b_type] if isinstance(json_schema_b_type, str) else json_schema_b_type
        )
        if unique_json_schema_a_type != unique_json_schema_b_type:
            return False
    # If it's an array, the items type must match
    if "items" in json_schema_a or "items" in json_schema_b:
        if not _json_schemas_have_same_type(
            json_schema_a.get("items", {}),
            json_schema_b.get("items", {}),
        ):
            return False
    # If it's an object, the set of properties must match, and their type must match too
    if "properties" in json_schema_a or "properties" in json_schema_b:
        if json_schema_a.get("properties", {}).keys() != json_schema_b.get("properties", {}).keys():
            return False
        for property_name in json_schema_a["properties"]:
            if not _json_schemas_have_same_type(
                json_schema_a["properties"][property_name],
                json_schema_b["properties"][property_name],
            ):
                return False
    if "additionalProperties" in json_schema_a or "additionalProperties" in json_schema_b:
        if not _json_schemas_have_same_type(
            json_schema_a.get("additionalProperties", {}),
            json_schema_b.get("additionalProperties", {}),
        ):
            return False
    return True


def _runtime_property_to_pyagentspec_property(
    runtime_property: RuntimeProperty,
) -> AgentSpecProperty:
    return AgentSpecProperty(json_schema=cast(Dict[str, Any], runtime_property.to_json_schema()))


def _runtime_entity_to_pyagentspec_entity(
    runtime_entity: RuntimeEntity,
) -> AgentSpecProperty:
    properties = {
        k: _runtime_property_to_pyagentspec_property(v).json_schema
        for k, v in runtime_entity.properties.items()
    }
    return AgentSpecProperty(
        json_schema={
            "type": "object",
            "title": runtime_entity.name or "entity",
            "description": runtime_entity.description,
            "properties": properties,
        }
    )


def _runtime_apitype_to_pyagentspec_apitype(
    api_type: RuntimeOpenAIAPIType,
) -> AgentSpecOpenAIAPIType:
    if api_type == RuntimeOpenAIAPIType.CHAT_COMPLETIONS:
        return AgentSpecOpenAIAPIType.CHAT_COMPLETIONS
    elif api_type == RuntimeOpenAIAPIType.RESPONSES:
        return AgentSpecOpenAIAPIType.RESPONSES
    else:
        raise ValueError(f"Received invalid runtime API Type: {api_type}")


def _runtime_messagecontent_to_pyagentspec_messagecontent(
    message_content: RuntimeMessageContent,
) -> AgentSpecPluginMessageContent:
    if isinstance(message_content, RuntimeTextContent):
        return AgentSpecPluginTextContent(content=message_content.content)
    elif isinstance(message_content, RuntimeImageContent):
        return AgentSpecPluginImageContent(base64_content=message_content.base64_content)
    else:
        raise ValueError(f"Message content of type {type(message_content)} is not supported")


def _runtime_nativemessage_to_pyagentspec_message(
    message: RuntimeMessage,
) -> AgentSpecPluginMessage:
    tool_requests = (
        [
            AgentSpecPluginToolRequest(
                name=tr.name,
                args=tr.args,
                tool_request_id=tr.tool_request_id,
            )
            for tr in message.tool_requests
        ]
        if message.tool_requests is not None
        else None
    )
    tool_result = (
        AgentSpecPluginToolResult(
            content=message.tool_result.content,
            tool_request_id=message.tool_result.tool_request_id,
        )
        if message.tool_result is not None
        else None
    )
    val = AgentSpecPluginMessage(
        role=message.role,
        contents=[
            _runtime_messagecontent_to_pyagentspec_messagecontent(content_)
            for content_ in message.contents
        ],
        tool_requests=tool_requests,
        tool_result=tool_result,
        display_only=message.display_only,
        sender=message.sender,
        recipients=list(message.recipients),
        time_created=message.time_created,
        time_updated=message.time_updated,
    )
    return val


def _runtime_dictmessage_to_pyagentspec_message(
    message: RuntimeMessageAsDictT,
) -> AgentSpecPluginMessage:
    tool_requests = (
        [
            AgentSpecPluginToolRequest(
                name=tr["name"],
                args=tr["args"],
                tool_request_id=tr["tool_request_id"],
            )
            for tr in message["tool_requests"]
        ]
        if message["tool_requests"] is not None
        else None
    )
    tool_result = (
        AgentSpecPluginToolResult(
            content=message["tool_result"]["content"],
            tool_request_id=message["tool_result"]["tool_request_id"],
        )
        if message["tool_result"] is not None
        else None
    )
    return AgentSpecPluginMessage(
        role=message["role"],
        content=message["content"],
        tool_requests=tool_requests,
        tool_result=tool_result,
    )


def _runtime_message_to_pyagentspec_message(
    message: Union[RuntimeMessage, RuntimeMessageAsDictT],
) -> AgentSpecPluginMessage:
    return (
        _runtime_nativemessage_to_pyagentspec_message(message)
        if isinstance(message, RuntimeMessage)
        else _runtime_dictmessage_to_pyagentspec_message(message)
    )


class WayflowBuiltinsSerializationPlugin(WayflowSerializationPlugin):

    @property
    def plugin_name(self) -> str:
        return "WayflowBuiltins"

    @property
    def plugin_version(self) -> str:
        from wayflowcore import __version__

        return __version__

    @property
    def supported_component_types(self) -> List[str]:
        return list(_BUILTIN_COMPONENTS)

    @property
    def required_agentspec_serialization_plugins(self) -> List[ComponentSerializationPlugin]:
        return all_serialization_plugin

    def serialize(
        self, obj: SerializableObject, serialization_context: SerializationContext
    ) -> Dict[str, Any]:
        return obj._serialize_to_dict(serialization_context)

    def convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_component: SerializableObject,
        referenced_objects: Dict[str, AgentSpecComponent],
    ) -> AgentSpecComponent:
        # If we did not find the object, we create it, and we record it in the referenced_objects registry
        agentspec_component: AgentSpecComponent
        if isinstance(runtime_component, RuntimeLlmModel):
            agentspec_component = self._llm_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeDescribedAgent):
            agentspec_component = self._described_agent_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeOciAgent):
            agentspec_component = self._ociagent_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeAgent):
            agentspec_component = self._agent_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeSwarm):
            agentspec_component = self._swarm_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeManagerWorkers):
            agentspec_component = self._managerworkers_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeMessageTransform):
            agentspec_component = self._messagetransform_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeOutputParser):
            agentspec_component = self._outputparsers_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeToolBox):
            agentspec_component = self._toolbox_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeTool):
            agentspec_component = self._tool_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeDescribedFlow):
            agentspec_component = self._described_flow_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeFlow):
            agentspec_component = self._flow_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeStep):
            agentspec_component = self._step_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeA2AConnectionConfig):
            agentspec_component = self._a2aconnectionconfig_convert_to_agentspec(
                runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeA2AAgent):
            agentspec_component = self._a2aagent_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeDatastore):
            agentspec_component = self._datastore_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeOracleDatabaseConnectionConfig):
            agentspec_component = self._oracle_db_connection_config_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimePostgresDatabaseConnectionConfig):
            agentspec_component = self._postgres_db_connection_config_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimePromptTemplate):
            agentspec_component = self._prompttemplate_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeEmbeddingModel):
            agentspec_component = self._embeddingmodel_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeControlFlowEdge):
            agentspec_component = self._controlflowedge_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeDataFlowEdge):
            agentspec_component = self._dataflowedge_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )
        elif isinstance(runtime_component, RuntimeContextProvider):
            agentspec_component = self._contextprovider_convert_to_agentspec(
                conversion_context, runtime_component, referenced_objects
            )

        elif isinstance(runtime_component, SerializableObject):
            raise NotImplementedError(
                f"The runtime type '{runtime_component.__class__.__name__}' is not yet supported "
                f"for conversion. Please contact the Runtime/AgentSpec team."
            )
        else:
            raise TypeError(
                f"Expected object of type 'runtime.serialization.serializer.RuntimeSerializableObject',"
                f" but got {type(runtime_component)} instead"
            )
        return agentspec_component

    def _variable_convert_to_agentspec(
        self, runtime_variable: RuntimeVariable
    ) -> AgentSpecProperty:
        return _runtime_property_to_pyagentspec_property(
            RuntimeVariable.to_property(runtime_variable)
        )

    def _variables_convert_to_agentspec(
        self, runtime_variables: List[RuntimeVariable]
    ) -> List[AgentSpecProperty]:
        return [
            self._variable_convert_to_agentspec(runtime_variable)
            for runtime_variable in runtime_variables
        ]

    def _contextprovider_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_context_provider: RuntimeContextProvider,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecPluginContextProvider:
        kwargs = dict(
            name=runtime_context_provider.name,
            description=runtime_context_provider.description,
            id=runtime_context_provider.id,
        )
        if isinstance(runtime_context_provider, RuntimeConstantContextProvider):
            return AgentSpecPluginConstantContextProvider(
                outputs=[
                    _runtime_property_to_pyagentspec_property(
                        runtime_context_provider._output_description
                    )
                ],
                value=runtime_context_provider._value,
                **kwargs,
            )
        elif isinstance(runtime_context_provider, RuntimeToolContextProvider):
            return AgentSpecPluginToolContextProvider(
                tool=cast(
                    AgentSpecServerTool,
                    conversion_context.convert(runtime_context_provider.tool, referenced_objects),
                ),
                output_name=runtime_context_provider.output_name,
                **kwargs,
            )
        elif isinstance(runtime_context_provider, RuntimeFlowContextProvider):
            return AgentSpecPluginFlowContextProvider(
                flow=cast(
                    AgentSpecExtendedFlow,
                    conversion_context.convert(runtime_context_provider.flow, referenced_objects),
                ),
                output_names=runtime_context_provider.flow_output_names,
                **kwargs,
            )
        else:
            raise NotImplementedError(
                f"The runtime type '{runtime_context_provider.__class__.__name__}' is not yet supported "
                f"for conversion. Please contact the Runtime/AgentSpec team."
            )

    def _controlflowedge_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_control_flow_edge: RuntimeControlFlowEdge,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecControlFlowEdge:
        if runtime_control_flow_edge.destination_step is None:
            raise ValueError("AgentSpec does not support transitions to None")
        return AgentSpecControlFlowEdge(
            name=runtime_control_flow_edge.name,
            description=runtime_control_flow_edge.description,
            id=runtime_control_flow_edge.id,
            from_node=cast(
                AgentSpecNode,
                conversion_context.convert(
                    runtime_control_flow_edge.source_step, referenced_objects
                ),
            ),
            from_branch=runtime_control_flow_edge.source_branch,
            to_node=cast(
                AgentSpecNode,
                conversion_context.convert(
                    runtime_control_flow_edge.destination_step, referenced_objects
                ),
            ),
        )

    def _dataflowedge_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_data_flow_edge: RuntimeDataFlowEdge,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecDataFlowEdge:
        return AgentSpecDataFlowEdge(
            name=runtime_data_flow_edge.name,
            description=runtime_data_flow_edge.description,
            id=runtime_data_flow_edge.id,
            source_node=cast(
                AgentSpecNode,
                conversion_context.convert(runtime_data_flow_edge.source_step, referenced_objects),
            ),
            source_output=runtime_data_flow_edge.source_output,
            destination_node=cast(
                AgentSpecNode,
                conversion_context.convert(
                    runtime_data_flow_edge.destination_step, referenced_objects
                ),
            ),
            destination_input=runtime_data_flow_edge.destination_input,
        )

    def _embeddingmodel_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_embedding_model: RuntimeEmbeddingModel,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecPluginEmbeddingConfig:
        kwargs = dict(
            name=runtime_embedding_model.name,
            description=runtime_embedding_model.description,
            id=runtime_embedding_model.id,
        )
        if isinstance(runtime_embedding_model, RuntimeOCIGenAIEmbeddingModel):
            return AgentSpecPluginOciGenAiEmbeddingConfig(
                model_id=runtime_embedding_model._model_id,
                compartment_id=runtime_embedding_model.compartment_id,
                client_config=self._ociclientconfig_convert_to_agentspec(
                    conversion_context,
                    runtime_ociclientconfig=runtime_embedding_model.config,
                    referenced_objects=referenced_objects,
                ),
                **kwargs,
            )
        elif isinstance(runtime_embedding_model, RuntimeOllamaEmbeddingModel):
            return AgentSpecPluginOllamaEmbeddingConfig(
                model_id=runtime_embedding_model._model_id,
                url=runtime_embedding_model._base_url,
                **kwargs,
            )
        elif isinstance(runtime_embedding_model, RuntimeVllmEmbeddingModel):
            return AgentSpecPluginVllmEmbeddingConfig(
                model_id=runtime_embedding_model._model_id,
                url=runtime_embedding_model._base_url,
                **kwargs,
            )
        elif isinstance(runtime_embedding_model, RuntimeOpenAiEmbeddingModel):
            return AgentSpecPluginOpenAiEmbeddingConfig(
                model_id=runtime_embedding_model._model_id, **kwargs
            )
        elif isinstance(runtime_embedding_model, RuntimeOpenAiCompatibleEmbeddingModel):
            # need to be at the end before the others extend it
            return AgentSpecPluginOpenAiCompatibleEmbeddingConfig(
                model_id=runtime_embedding_model._model_id,
                url=runtime_embedding_model._base_url,
                **kwargs,
            )
        else:
            raise NotImplementedError(
                f"The runtime type '{runtime_embedding_model.__class__.__name__}' is not yet supported "
                f"for conversion. Please contact the Runtime/AgentSpec team."
            )

    def _llmgenerationconfig_convert_to_agentspec(
        self, runtime_generationconfig: RuntimeLlmGenerationConfig
    ) -> AgentSpecLlmGenerationConfig:
        extra_args = dict(
            stop=runtime_generationconfig.stop,
            frequency_penalty=runtime_generationconfig.frequency_penalty,
        )
        for extra_arg_key, extra_arg_value in runtime_generationconfig.extra_args.items():
            extra_args[extra_arg_key] = extra_arg_value
        return AgentSpecLlmGenerationConfig(
            max_tokens=runtime_generationconfig.max_tokens,
            temperature=runtime_generationconfig.temperature,
            top_p=runtime_generationconfig.top_p,
            **extra_args,
        )

    def _postgres_db_connection_config_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_postgres_db_connection_config: RuntimePostgresDatabaseConnectionConfig,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecTlsPostgresDatabaseConnectionConfig:
        if isinstance(
            runtime_postgres_db_connection_config, RuntimeTlsPostgresDatabaseConnectionConfig
        ):
            return AgentSpecTlsPostgresDatabaseConnectionConfig(
                user=runtime_postgres_db_connection_config.user,
                password=runtime_postgres_db_connection_config.password,
                url=runtime_postgres_db_connection_config.url,
                sslmode=runtime_postgres_db_connection_config.sslmode,
                sslcert=runtime_postgres_db_connection_config.sslcert,
                sslkey=runtime_postgres_db_connection_config.sslkey,
                sslrootcert=runtime_postgres_db_connection_config.sslrootcert,
                sslcrl=runtime_postgres_db_connection_config.sslcrl,
                id=runtime_postgres_db_connection_config.id,
                description=runtime_postgres_db_connection_config.description,
                name=runtime_postgres_db_connection_config.name,
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_postgres_db_connection_config
                ),
            )
        raise ValueError(
            f"Unsupported type of PostgresDatabaseConnectionConfig in Agent Spec: "
            f"{type(runtime_postgres_db_connection_config)}"
        )

    def _oracle_db_connection_config_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_oracle_db_connection_config: RuntimeOracleDatabaseConnectionConfig,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecOracleDatabaseConnectionConfig:
        if isinstance(
            runtime_oracle_db_connection_config, RuntimeTlsOracleDatabaseConnectionConfig
        ):
            return AgentSpecTlsOracleDatabaseConnectionConfig(
                name=runtime_oracle_db_connection_config.name
                or "TlsOracleDatabaseConnectionConfig",
                user=runtime_oracle_db_connection_config.user,
                password=runtime_oracle_db_connection_config.password,
                dsn=runtime_oracle_db_connection_config.dsn,
                config_dir=runtime_oracle_db_connection_config.config_dir,
                id=runtime_oracle_db_connection_config.id,
                description=runtime_oracle_db_connection_config.description,
            )
        elif isinstance(
            runtime_oracle_db_connection_config, RuntimeMTlsOracleDatabaseConnectionConfig
        ):
            return AgentSpecMTlsOracleDatabaseConnectionConfig(
                name="MTlsOracleDatabaseConnectionConfig",
                config_dir=runtime_oracle_db_connection_config.config_dir,
                dsn=runtime_oracle_db_connection_config.dsn,
                user=runtime_oracle_db_connection_config.user,
                password=runtime_oracle_db_connection_config.password,
                wallet_location=runtime_oracle_db_connection_config.wallet_location,
                wallet_password=runtime_oracle_db_connection_config.wallet_password,
                id=runtime_oracle_db_connection_config.id,
            )
        raise ValueError(
            f"Unsupported type of OracleDatabaseConnectionConfig in Agent Spec: "
            f"{type(runtime_oracle_db_connection_config)}"
        )

    def _datastore_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_datastore: RuntimeDatastore,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecDatastore:
        if isinstance(runtime_datastore, RuntimeInMemoryDatastore):
            return AgentSpecInMemoryDatastore(
                name=runtime_datastore.name or "in-memory-datastore",
                datastore_schema={
                    k: _runtime_entity_to_pyagentspec_entity(v)
                    for k, v in runtime_datastore.schema.items()
                },
                id=runtime_datastore.id,
            )
        elif isinstance(runtime_datastore, RuntimeOracleDatabaseDatastore):
            return AgentSpecOracleDatabaseDatastore(
                name=runtime_datastore.name or "oracle-database-datastore",
                datastore_schema={
                    k: _runtime_entity_to_pyagentspec_entity(v)
                    for k, v in runtime_datastore.schema.items()
                },
                connection_config=self._oracle_db_connection_config_convert_to_agentspec(
                    conversion_context=conversion_context,
                    runtime_oracle_db_connection_config=runtime_datastore.connection_config,
                    referenced_objects=referenced_objects,
                ),
                id=runtime_datastore.id,
            )
        elif isinstance(runtime_datastore, RuntimePostgresDatabaseDatastore):
            return AgentSpecPostgresDatabaseDatastore(
                name=runtime_datastore.name or "postgres-database-datastore",
                datastore_schema={
                    k: _runtime_entity_to_pyagentspec_entity(v)
                    for k, v in runtime_datastore.schema.items()
                },
                connection_config=self._postgres_db_connection_config_convert_to_agentspec(
                    conversion_context=conversion_context,
                    runtime_postgres_db_connection_config=runtime_datastore.connection_config,
                    referenced_objects=referenced_objects,
                ),
                id=runtime_datastore.id,
            )
        raise ValueError(f"Unsupported type of Datastore in Agent Spec: {type(runtime_datastore)}")

    def _described_agent_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_described_agent: RuntimeDescribedAgent,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecAgent:
        agentspec_component = self._agent_convert_to_agentspec(
            conversion_context, runtime_described_agent.agent, referenced_objects
        )
        agentspec_component.name = runtime_described_agent.name
        agentspec_component.description = runtime_described_agent.description
        return agentspec_component

    def _described_flow_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_described_flow: RuntimeDescribedFlow,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecFlow:
        agentspec_component = self._flow_convert_to_agentspec(
            conversion_context, runtime_described_flow.flow, referenced_objects
        )
        agentspec_component.name = runtime_described_flow.name
        agentspec_component.description = runtime_described_flow.description
        return agentspec_component

    def _llm_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_llm: RuntimeLlmModel,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecLlmConfig:
        generation_config = (
            self._llmgenerationconfig_convert_to_agentspec(runtime_llm.generation_config)
            if hasattr(runtime_llm, "generation_config") and runtime_llm.generation_config
            else None
        )
        if isinstance(runtime_llm, RuntimeVllmModel):
            return AgentSpecVllmModel(
                name=runtime_llm.name,
                model_id=runtime_llm.model_id,
                url=runtime_llm.host_port,
                api_type=_runtime_apitype_to_pyagentspec_apitype(runtime_llm.api_type),
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_llm),
                id=runtime_llm.id,
                description=runtime_llm.description,
                default_generation_parameters=generation_config,
                api_key=runtime_llm.api_key if runtime_llm.api_key != EMPTY_API_KEY else None,
            )
        elif isinstance(runtime_llm, RuntimeOCIGenAIModel):
            client_config = self._ociclientconfig_convert_to_agentspec(
                conversion_context,
                runtime_ociclientconfig=runtime_llm.client_config,
                referenced_objects=referenced_objects,
            )
            return AgentSpecOciGenAiModel(
                name=runtime_llm.name,
                model_id=runtime_llm.model_id,
                serving_mode=AgentSpecOciGenAiServingMode(runtime_llm.serving_mode.value),
                client_config=client_config,
                compartment_id=runtime_llm.compartment_id,
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_llm),
                id=runtime_llm.id,
                description=runtime_llm.description,
                default_generation_parameters=generation_config,
                provider=AgentSpecModelProvider(runtime_llm.provider.value),
            )
        elif isinstance(runtime_llm, RuntimeOllamaModel):
            return AgentSpecOllamaModel(
                name=runtime_llm.name,
                model_id=runtime_llm.model_id,
                url=runtime_llm.host_port,
                api_type=_runtime_apitype_to_pyagentspec_apitype(runtime_llm.api_type),
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_llm),
                id=runtime_llm.id,
                description=runtime_llm.description,
                default_generation_parameters=generation_config,
            )
        elif isinstance(runtime_llm, RuntimeOpenAIModel):
            return AgentSpecOpenAiConfig(
                name=runtime_llm.name,
                model_id=runtime_llm.model_id,
                api_type=_runtime_apitype_to_pyagentspec_apitype(runtime_llm.api_type),
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_llm),
                id=runtime_llm.id,
                description=runtime_llm.description,
                default_generation_parameters=generation_config,
                api_key=runtime_llm.api_key if runtime_llm.api_key != EMPTY_API_KEY else None,
            )
        elif isinstance(runtime_llm, RuntimeOpenAICompatibleModel):
            return AgentSpecOpenAiCompatibleConfig(
                name=runtime_llm.name,
                model_id=runtime_llm.model_id,
                url=runtime_llm.base_url,
                api_type=_runtime_apitype_to_pyagentspec_apitype(runtime_llm.api_type),
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_llm),
                id=runtime_llm.id,
                description=runtime_llm.description,
                default_generation_parameters=generation_config,
                api_key=runtime_llm.api_key if runtime_llm.api_key != EMPTY_API_KEY else None,
            )
        raise ValueError(f"Unsupported type of LLM in Agent Spec: {type(runtime_llm)}")

    def _tool_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_tool: RuntimeTool,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecTool:

        metadata = _create_agentspec_metadata_from_runtime_component(runtime_tool)

        # We need to check the RemoteTool first, as it is also an instance of ServerTool
        if isinstance(runtime_tool, RuntimeRemoteTool):

            # This is a workaround, since RuntimeRemoteTool
            # does not save the parameters it is created with.
            inner_api_step = cast(
                RuntimeApiCallStep,
                cast(_FlowAsToolCallable, runtime_tool.func).flow.steps["single_step"],
            )
            return AgentSpecRemoteTool(
                name=runtime_tool.name,
                description=runtime_tool.description,
                url=runtime_tool.url,
                http_method=inner_api_step.method,
                data=(
                    inner_api_step.json_body
                    if isinstance(inner_api_step.json_body, dict)
                    else dict()
                ),
                query_params=(
                    inner_api_step.params if isinstance(inner_api_step.params, dict) else dict()
                ),
                headers=(
                    inner_api_step.headers if isinstance(inner_api_step.headers, dict) else dict()
                ),
                sensitive_headers=(
                    inner_api_step.sensitive_headers
                    if isinstance(inner_api_step.sensitive_headers, dict)
                    else dict()
                ),
                requires_confirmation=runtime_tool.requires_confirmation,
                metadata=metadata,
                id=runtime_tool.id,
            )
        # other cases: mcpservertool, server, client tools
        if isinstance(runtime_tool, RuntimeMCPTool):
            return AgentSpecMCPTool(
                name=runtime_tool.name,
                description=runtime_tool.description,
                metadata=metadata,
                inputs=[
                    _runtime_property_to_pyagentspec_property(input_)
                    for input_ in runtime_tool.input_descriptors or []
                ],
                outputs=[
                    _runtime_property_to_pyagentspec_property(output)
                    for output in runtime_tool.output_descriptors or []
                ],
                client_transport=self._mcp_clienttransport_convert_to_agentspec(
                    conversion_context,
                    runtime_tool.client_transport,
                    referenced_objects,
                ),
                requires_confirmation=runtime_tool.requires_confirmation,
                id=runtime_tool.id,
            )
        elif isinstance(runtime_tool, RuntimeServerTool):
            return AgentSpecServerTool(
                name=runtime_tool.name,
                description=runtime_tool.description,
                metadata=metadata,
                inputs=[
                    _runtime_property_to_pyagentspec_property(input_)
                    for input_ in runtime_tool.input_descriptors or []
                ],
                outputs=[
                    _runtime_property_to_pyagentspec_property(output)
                    for output in runtime_tool.output_descriptors or []
                ],
                requires_confirmation=runtime_tool.requires_confirmation,
                id=runtime_tool.id,
            )
        elif isinstance(runtime_tool, RuntimeClientTool):
            return AgentSpecClientTool(
                name=runtime_tool.name,
                description=runtime_tool.description,
                metadata=metadata,
                inputs=[
                    _runtime_property_to_pyagentspec_property(input_)
                    for input_ in runtime_tool.input_descriptors or []
                ],
                outputs=[
                    _runtime_property_to_pyagentspec_property(output)
                    for output in runtime_tool.output_descriptors or []
                ],
                requires_confirmation=runtime_tool.requires_confirmation,
                id=runtime_tool.id,
            )
        else:
            raise ValueError(f"Unsupported type of tool in Agent Spec: {type(runtime_tool)}")

    def _regex_pattern_to_agentspec(
        self,
        runtime_regex_pattern: Union[
            str, RuntimeRegexPattern, Dict[str, Union[str, RuntimeRegexPattern]]
        ],
    ) -> str | AgentSpecPluginRegexPattern | Dict[str, str | AgentSpecPluginRegexPattern]:
        regex_pattern: (
            str | AgentSpecPluginRegexPattern | Dict[str, str | AgentSpecPluginRegexPattern]
        )
        if isinstance(runtime_regex_pattern, str):
            regex_pattern = runtime_regex_pattern
        elif isinstance(runtime_regex_pattern, RuntimeRegexPattern):
            regex_pattern = AgentSpecPluginRegexPattern(
                pattern=runtime_regex_pattern.pattern,
                match=runtime_regex_pattern.match,
                flags=runtime_regex_pattern.flags,
            )
        else:
            regex_pattern = {
                k: (
                    v
                    if isinstance(v, str)
                    else AgentSpecPluginRegexPattern(
                        pattern=v.pattern, match=v.match, flags=v.flags
                    )
                )
                for k, v in runtime_regex_pattern.items()
            }
        return regex_pattern

    def _outputparsers_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_outputparser: RuntimeOutputParser,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecPluginOutputParser:
        if isinstance(runtime_outputparser, RuntimeRegexOutputParser):

            return AgentSpecPluginRegexOutputParser(
                name="regex_outputparser",
                regex_pattern=self._regex_pattern_to_agentspec(runtime_outputparser.regex_pattern),
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_outputparser),
                strict=runtime_outputparser.strict,
            )
        elif isinstance(runtime_outputparser, RuntimeJsonOutputParser):
            return AgentSpecPluginJsonOutputParser(
                name="json_outputparser",
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_outputparser),
                properties=runtime_outputparser.properties,
            )
        elif isinstance(runtime_outputparser, RuntimeJsonToolOutputParser):
            return AgentSpecPluginJsonToolOutputParser(
                name="jsontool_outputparser",
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_outputparser),
                tools=(
                    [
                        cast(
                            AgentSpecTool,
                            conversion_context.convert(tool, referenced_objects),
                        )
                        for tool in runtime_outputparser.tools
                    ]
                    if runtime_outputparser.tools
                    else None
                ),
                id=runtime_outputparser.id,
            )
        elif isinstance(runtime_outputparser, RuntimeReactToolOutputParser):
            return AgentSpecPluginReactToolOutputParser(
                name="reacttool_outputparser",
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_outputparser),
                tools=(
                    [
                        cast(
                            AgentSpecTool,
                            conversion_context.convert(tool, referenced_objects),
                        )
                        for tool in runtime_outputparser.tools
                    ]
                    if runtime_outputparser.tools
                    else None
                ),
                id=runtime_outputparser.id,
            )
        elif isinstance(runtime_outputparser, RuntimePythonToolOutputParser):
            return AgentSpecPluginPythonToolOutputParser(
                name="pythontool_outputparser",
                metadata=_create_agentspec_metadata_from_runtime_component(runtime_outputparser),
                tools=(
                    [
                        cast(
                            AgentSpecTool,
                            conversion_context.convert(tool, referenced_objects),
                        )
                        for tool in runtime_outputparser.tools
                    ]
                    if runtime_outputparser.tools
                    else None
                ),
                id=runtime_outputparser.id,
            )
        raise ValueError(
            f"Unsupported type of OutputParser in Agent Spec: {type(runtime_outputparser)}"
        )

    def _messagetransform_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_messagetransform: RuntimeMessageTransform,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecMessageTransform:
        if isinstance(runtime_messagetransform, RuntimewCoalesceSystemMessagesTransform):
            return AgentSpecPluginCoalesceSystemMessagesTransform(
                name="coalescesystemmessage_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeRemoveEmptyNonUserMessageTransform):
            return AgentSpecPluginRemoveEmptyNonUserMessageTransform(
                name="removeemptynonusermessage_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(
            runtime_messagetransform, RuntimeAppendTrailingSystemMessageToUserMessageTransform
        ):
            return AgentSpecPluginAppendTrailingSystemMessageToUserMessageTransform(
                name="appendtrailingsystemmessagetousermessage_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeLlamaMergeToolRequestAndCallsTransform):
            return AgentSpecPluginLlamaMergeToolRequestAndCallsTransform(
                name="llamamergetoolrequestandcalls_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeReactMergeToolRequestAndCallsTransform):
            return AgentSpecPluginReactMergeToolRequestAndCallsTransform(
                name="reactmesagetoolrequestandcalls_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeSwarmToolRequestAndCallsTransform):
            return AgentSpecPluginSwarmToolRequestAndCallsTransform(
                name="swarmtoolrequestandcalls_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeCanonicalizationMessageTransform):
            return AgentSpecPluginCanonicalizationMessageTransform(
                name="canonicalization_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        elif isinstance(runtime_messagetransform, RuntimeSplitPromptOnMarkerMessageTransform):
            return AgentSpecPluginSplitPromptOnMarkerMessageTransform(
                name="splitpromptonmarker_messagetransform",
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
                marker=runtime_messagetransform.marker,
            )
        elif isinstance(runtime_messagetransform, RuntimeMessageSummarizationTransform):
            return AgentSpecMessageSummarizationTransform(
                name=runtime_messagetransform.name or "message-summarizer",
                llm=self._llm_convert_to_agentspec(
                    conversion_context, runtime_messagetransform.llm, referenced_objects
                ),
                max_message_size=runtime_messagetransform.max_message_size,
                summarization_instructions=runtime_messagetransform.summarization_instructions,
                summarized_message_template=runtime_messagetransform.summarized_message_template,
                max_cache_size=runtime_messagetransform.max_cache_size,
                max_cache_lifetime=runtime_messagetransform.max_cache_lifetime,
                cache_collection_name=runtime_messagetransform.cache_collection_name,
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )

        elif isinstance(runtime_messagetransform, RuntimeConversationSummarizationTransform):
            return AgentSpecConversationSummarizationTransform(
                name=runtime_messagetransform.name or "conversation-summarizer",
                llm=self._llm_convert_to_agentspec(
                    conversion_context, runtime_messagetransform.llm, referenced_objects
                ),
                max_num_messages=runtime_messagetransform.max_num_messages,
                min_num_messages=runtime_messagetransform.min_num_messages,
                summarization_instructions=runtime_messagetransform.summarization_instructions,
                summarized_conversation_template=runtime_messagetransform.summarized_conversation_template,
                max_cache_size=runtime_messagetransform.max_cache_size,
                max_cache_lifetime=runtime_messagetransform.max_cache_lifetime,
                cache_collection_name=runtime_messagetransform.cache_collection_name,
                metadata=_create_agentspec_metadata_from_runtime_component(
                    runtime_messagetransform
                ),
            )
        raise ValueError(
            f"Unsupported type of MessageTransform in Agent Spec: {type(runtime_messagetransform)}"
        )

    def _prompttemplate_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_prompttemplate: RuntimePromptTemplate,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecPluginPromptTemplate:
        return AgentSpecPluginPromptTemplate(
            name=runtime_prompttemplate.name,
            id=runtime_prompttemplate.id,
            description=runtime_prompttemplate.description,
            metadata=_create_agentspec_metadata_from_runtime_component(runtime_prompttemplate),
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_prompttemplate.input_descriptors or []
            ],
            messages=[
                _runtime_message_to_pyagentspec_message(message_)
                for message_ in runtime_prompttemplate.messages
            ],
            output_parser=(
                (
                    [
                        self._outputparsers_convert_to_agentspec(
                            conversion_context, output_parser_, referenced_objects
                        )
                        for output_parser_ in runtime_prompttemplate.output_parser
                    ]
                    if isinstance(runtime_prompttemplate.output_parser, list)
                    else self._outputparsers_convert_to_agentspec(
                        conversion_context,
                        runtime_prompttemplate.output_parser,
                        referenced_objects,
                    )
                )
                if runtime_prompttemplate.output_parser
                else None
            ),
            pre_rendering_transforms=(
                [
                    self._messagetransform_convert_to_agentspec(
                        conversion_context, transform, referenced_objects
                    )
                    for transform in runtime_prompttemplate.pre_rendering_transforms
                ]
                if runtime_prompttemplate.pre_rendering_transforms
                else None
            ),
            post_rendering_transforms=(
                [
                    self._messagetransform_convert_to_agentspec(
                        conversion_context, transform, referenced_objects
                    )
                    for transform in runtime_prompttemplate.post_rendering_transforms
                ]
                if runtime_prompttemplate.post_rendering_transforms
                else None
            ),
            tools=(
                [
                    cast(
                        AgentSpecTool,
                        conversion_context.convert(tool_, referenced_objects),
                    )
                    for tool_ in runtime_prompttemplate.tools
                ]
                if runtime_prompttemplate.tools
                else None
            ),
            native_tool_calling=runtime_prompttemplate.native_tool_calling,
            response_format=(
                _runtime_property_to_pyagentspec_property(runtime_prompttemplate.response_format)
                if runtime_prompttemplate.response_format
                else None
            ),
            native_structured_generation=runtime_prompttemplate.native_structured_generation,
            generation_config=(
                self._llmgenerationconfig_convert_to_agentspec(
                    runtime_prompttemplate.generation_config
                )
                if runtime_prompttemplate.generation_config
                else None
            ),
        )

    def _ociclientconfig_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_ociclientconfig: RuntimeOCIClientConfig,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecOciClientConfig:
        if isinstance(runtime_ociclientconfig, RuntimeOCIClientConfigWithSecurityToken):
            return AgentSpecOciClientConfigWithSecurityToken(
                name="oci_client_config",
                service_endpoint=runtime_ociclientconfig.service_endpoint,
                auth_profile=runtime_ociclientconfig.auth_profile,
                auth_file_location=(
                    runtime_ociclientconfig.auth_file_location
                    if runtime_ociclientconfig.auth_file_location != "~/.oci/config"
                    else ""
                ),
            )
        elif isinstance(runtime_ociclientconfig, RuntimeOCIClientConfigWithInstancePrincipal):
            return AgentSpecOciClientConfigWithInstancePrincipal(
                name="oci_client_config",
                service_endpoint=runtime_ociclientconfig.service_endpoint,
            )
        elif isinstance(runtime_ociclientconfig, RuntimeOCIClientConfigWithResourcePrincipal):
            return AgentSpecOciClientConfigWithResourcePrincipal(
                name="oci_client_config",
                service_endpoint=runtime_ociclientconfig.service_endpoint,
            )
        elif isinstance(runtime_ociclientconfig, RuntimeOCIClientConfigWithUserAuthentication):
            raise ValueError(
                f"For security reasons converting `OciClientConfigWithUserAuthentication` is not supported"
            )
        elif isinstance(runtime_ociclientconfig, RuntimeOCIClientConfigWithApiKey):
            return AgentSpecOciClientConfigWithApiKey(
                name="oci_client_config",
                service_endpoint=runtime_ociclientconfig.service_endpoint,
                auth_profile=runtime_ociclientconfig.auth_profile,
                auth_file_location=(
                    runtime_ociclientconfig.auth_file_location
                    if runtime_ociclientconfig.auth_file_location != "~/.oci/config"
                    else ""
                ),
            )
        else:
            raise ValueError(
                f"WayFlow OciClientConfig '{runtime_ociclientconfig.__class__.__name__}' is not supported yet."
            )

    def _ociagent_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_ociagent: RuntimeOciAgent,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecOciAgent:
        return AgentSpecOciAgent(
            id=runtime_ociagent.id,
            name=runtime_ociagent.name,
            description=runtime_ociagent.description,
            client_config=self._ociclientconfig_convert_to_agentspec(
                conversion_context,
                runtime_ociagent.client_config,
                referenced_objects=referenced_objects,
            ),
            agent_endpoint_id=runtime_ociagent.agent_endpoint_id,
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_ociagent.input_descriptors or []
            ],
            outputs=[
                _runtime_property_to_pyagentspec_property(output)
                for output in runtime_ociagent.output_descriptors or []
            ],
            metadata=_create_agentspec_metadata_from_runtime_component(runtime_ociagent),
        )

    def _mcptoolspec_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_mcptoolspec: RuntimeTool,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecMCPToolSpec:

        return AgentSpecMCPToolSpec(
            name=runtime_mcptoolspec.name,
            description=runtime_mcptoolspec.description,
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_mcptoolspec.input_descriptors or []
            ],
            outputs=[
                _runtime_property_to_pyagentspec_property(output)
                for output in runtime_mcptoolspec.output_descriptors or []
            ],
            requires_confirmation=runtime_mcptoolspec.requires_confirmation,
            metadata=_create_agentspec_metadata_from_runtime_component(runtime_mcptoolspec),
        )

    def _toolbox_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_toolbox: RuntimeToolBox,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecToolBox:
        if runtime_toolbox.requires_confirmation is not None:
            raise ValueError(
                "ToolBox with `requires_confirmation` flag configured cannot be converted to AgentSpec yet."
            )

        if isinstance(runtime_toolbox, RuntimeMCPToolBox):
            tool_filter = (
                [
                    (
                        tool_
                        if isinstance(tool_, str)
                        else self._mcptoolspec_convert_to_agentspec(
                            conversion_context, tool_, referenced_objects
                        )
                    )
                    for tool_ in runtime_toolbox.tool_filter
                ]
                if runtime_toolbox.tool_filter is not None
                else None
            )
            return AgentSpecMCPToolBox(
                name=runtime_toolbox.name,
                client_transport=self._mcp_clienttransport_convert_to_agentspec(
                    conversion_context,
                    runtime_toolbox.client_transport,
                    referenced_objects,
                ),
                tool_filter=tool_filter,
                id=runtime_toolbox.id,
                description=runtime_toolbox.description,
            )
        else:
            raise ValueError(
                f"WayFlow ToolBox '{runtime_toolbox.__class__.__name__}' is not supported yet."
            )

    def _mcp_clienttransport_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_clienttransport: RuntimeClientTransport,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecClientTransport:
        if (
            hasattr(runtime_clienttransport, "session_parameters")
            and runtime_clienttransport.session_parameters != RuntimeSessionParameters()
        ):
            warn(
                "Client transport `session_parameters` parameter is not supported yet for serialization.",
                UserWarning,
            )
        if hasattr(runtime_clienttransport, "auth") and runtime_clienttransport.auth:
            warn(
                "Client transport `auth` parameter is not supported yet for serialization.",
                UserWarning,
            )
        if isinstance(runtime_clienttransport, RuntimeStdioTransport):
            kwargs = dict(
                name="mcp_client_transport",
                command=runtime_clienttransport.command,
                args=runtime_clienttransport.args,
                env=runtime_clienttransport.env,
                cwd=runtime_clienttransport.cwd,
                id=runtime_clienttransport.id,
            )
            if has_default_value_for_attribute(
                runtime_clienttransport, "encoding"
            ) and has_default_value_for_attribute(
                runtime_clienttransport, "encoding_error_handler"
            ):
                return AgentSpecStdioTransport(**kwargs)
            else:
                return AgentSpecPluginStdioTransport(
                    **kwargs,
                    encoding=runtime_clienttransport.encoding,
                    encoding_error_handler=runtime_clienttransport.encoding_error_handler,
                )

        def _get_remote_client_transport_args(
            remote_transport: RuntimeRemoteBaseTransport, extended: bool = True
        ) -> Dict[str, Any]:
            mtls_kwargs = {}
            if isinstance(remote_transport, RuntimeHTTPmTLSBaseTransport):
                mtls_kwargs = dict(
                    key_file=remote_transport.key_file,
                    cert_file=remote_transport.cert_file,
                    ca_file=remote_transport.ssl_ca_cert,
                )

            return dict(
                name="mcp_client_transport",
                url=remote_transport.url,
                headers=remote_transport.headers,
                sensitive_headers=remote_transport.sensitive_headers,
                id=runtime_clienttransport.id,
                **mtls_kwargs,
            )

        def _can_be_agentspec_remote_transport(
            remote_transport: RuntimeRemoteBaseTransport,
        ) -> bool:
            return has_default_value_for_attribute(
                remote_transport, "timeout"
            ) and has_default_value_for_attribute(remote_transport, "sse_read_timeout")

        if isinstance(runtime_clienttransport, RuntimeSSETransport):
            if _can_be_agentspec_remote_transport(runtime_clienttransport):
                return AgentSpecSSETransport(
                    **_get_remote_client_transport_args(runtime_clienttransport),
                )
            return AgentSpecPluginSSETransport(
                **_get_remote_client_transport_args(runtime_clienttransport),
                timeout=runtime_clienttransport.timeout,
                sse_read_timeout=runtime_clienttransport.sse_read_timeout,
            )

        elif isinstance(runtime_clienttransport, RuntimeSSEmTLSTransport):
            if _can_be_agentspec_remote_transport(runtime_clienttransport):
                return AgentSpecSSEmTLSTransport(
                    **_get_remote_client_transport_args(runtime_clienttransport),
                )
            return AgentSpecPluginSSEmTLSTransport(
                **_get_remote_client_transport_args(runtime_clienttransport),
                timeout=runtime_clienttransport.timeout,
                sse_read_timeout=runtime_clienttransport.sse_read_timeout,
            )
        elif isinstance(runtime_clienttransport, RuntimeStreamableHTTPTransport):
            if _can_be_agentspec_remote_transport(runtime_clienttransport):
                return AgentSpecStreamableHTTPTransport(
                    **_get_remote_client_transport_args(runtime_clienttransport),
                )
            return AgentSpecPluginStreamableHTTPTransport(
                **_get_remote_client_transport_args(runtime_clienttransport),
                timeout=runtime_clienttransport.timeout,
                sse_read_timeout=runtime_clienttransport.sse_read_timeout,
            )
        elif isinstance(runtime_clienttransport, RuntimeStreamableHTTPmTLSTransport):
            if _can_be_agentspec_remote_transport(runtime_clienttransport):
                return AgentSpecStreamableHTTPmTLSTransport(
                    **_get_remote_client_transport_args(runtime_clienttransport),
                )
            return AgentSpecPluginStreamableHTTPmTLSTransport(
                **_get_remote_client_transport_args(runtime_clienttransport),
                timeout=runtime_clienttransport.timeout,
                sse_read_timeout=runtime_clienttransport.sse_read_timeout,
            )
        else:
            raise ValueError(
                f"WayFlow ClientTransport '{runtime_clienttransport.__class__.__name__}' is not supported yet."
            )

    def _agent_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_agent: RuntimeAgent,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecAgent:

        llm_config = cast(
            AgentSpecLlmConfig,
            conversion_context.convert(runtime_agent.llm, referenced_objects),
        )
        tools = [
            cast(AgentSpecTool, conversion_context.convert(tool, referenced_objects))
            for tool in runtime_agent._tools
        ]
        toolboxes = [
            cast(
                AgentSpecPluginToolBox,
                conversion_context.convert(tool, referenced_objects),
            )
            for tool in runtime_agent._toolboxes
        ]
        flows = [
            cast(AgentSpecFlow, conversion_context.convert(flow, referenced_objects))
            for flow in runtime_agent.flows
        ]
        agents = [
            cast(AgentSpecAgent, conversion_context.convert(agent, referenced_objects))
            for agent in runtime_agent.agents
        ]
        system_prompt = runtime_agent.custom_instruction or ""
        inputs = [
            _runtime_property_to_pyagentspec_property(input_)
            for input_ in runtime_agent.input_descriptors or []
        ]
        outputs = [
            _runtime_property_to_pyagentspec_property(output)
            for output in runtime_agent.output_descriptors or []
        ]
        metadata = _create_agentspec_metadata_from_runtime_component(runtime_agent)
        extended_agent_model_fields = AgentSpecExtendedAgent.model_fields
        transforms = [
            cast(
                AgentSpecMessageTransform,
                conversion_context.convert(transform, referenced_objects),
            )
            for transform in runtime_agent.transforms
        ]
        if (
            (has_cp := runtime_agent.context_providers)
            or (
                has_template := (
                    runtime_agent.agent_template is not runtime_agent.llm.agent_template
                )
            )
            or (has_initial_message := (runtime_agent.initial_message is not None))
            or (
                conv_default := (
                    runtime_agent.can_finish_conversation
                    != extended_agent_model_fields["can_finish_conversation"].default
                )
            )
            or (
                raise_exceptions := (
                    runtime_agent.raise_exceptions
                    != extended_agent_model_fields["raise_exceptions"].default
                )
            )
            or (
                maxiter_default := (
                    runtime_agent.max_iterations
                    != extended_agent_model_fields["max_iterations"].default
                )
            )
            or (has_subagents := len(agents) > 0)
            or (has_subflows := len(flows) > 0)
        ):

            return AgentSpecExtendedAgent(
                name=runtime_agent.name,
                description=runtime_agent.description,
                id=runtime_agent.id,
                llm_config=llm_config,
                tools=tools,
                flows=flows,
                agents=agents,
                system_prompt=system_prompt,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
                toolboxes=toolboxes,
                context_providers=(
                    [
                        conversion_context.convert(context_provider_, referenced_objects)
                        for context_provider_ in runtime_agent.context_providers
                    ]
                    if runtime_agent.context_providers
                    else None
                ),
                transforms=transforms,
                can_finish_conversation=runtime_agent.can_finish_conversation,
                max_iterations=runtime_agent.max_iterations,
                initial_message=runtime_agent.initial_message,
                caller_input_mode=runtime_agent.caller_input_mode,
                human_in_the_loop=runtime_agent.caller_input_mode == CallerInputMode.ALWAYS,
                agent_template=(
                    self._prompttemplate_convert_to_agentspec(
                        conversion_context,
                        runtime_agent.agent_template,
                        referenced_objects,
                    )
                    if (
                        isinstance(runtime_agent.agent_template, RuntimePromptTemplate)
                        and runtime_agent.agent_template is not runtime_agent.llm.agent_template
                    )
                    else None
                ),
            )

        return AgentSpecAgent(
            name=runtime_agent.name,
            description=runtime_agent.description,
            id=runtime_agent.id,
            llm_config=llm_config,
            tools=tools,
            toolboxes=toolboxes,
            system_prompt=system_prompt,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
            human_in_the_loop=runtime_agent.caller_input_mode == CallerInputMode.ALWAYS,
            transforms=transforms,
        )

    def _flow_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_flow: RuntimeFlow,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecFlow:

        agentspec_nodes: Dict[str, AgentSpecNode] = {
            runtime_node.id: cast(
                AgentSpecNode,
                conversion_context.convert(runtime_node, referenced_objects),
            )
            for node_name, runtime_node in runtime_flow.steps.items()
            if not issubclass(type(runtime_node), RuntimeCompleteStep)
        }

        start_node = next(
            agentspec_node
            for agentspec_node in agentspec_nodes.values()
            if isinstance(agentspec_node, AgentSpecStartNode)
        )

        # End nodes are created separately because we need to infer the outputs for them.
        # We assume that all the steps are going to expose all the outputs of the flow
        for node_name, runtime_node in runtime_flow.steps.items():
            if issubclass(type(runtime_node), RuntimeCompleteStep):
                agentspec_nodes[runtime_node.id] = AgentSpecEndNode(
                    name=node_name,
                    branch_name=runtime_node.branch_name or node_name,  # type: ignore
                    outputs=[
                        _runtime_property_to_pyagentspec_property(property_)
                        for property_ in runtime_flow.output_descriptors
                    ],
                    metadata=_create_agentspec_metadata_from_runtime_component(runtime_node),
                    id=runtime_node.id,
                )

        # Overwrite the temp names assigned by the conversion
        for node_name, runtime_node in runtime_flow.steps.items():
            if runtime_node.id in agentspec_nodes:
                agentspec_nodes[runtime_node.id].name = str(node_name)

        control_flow_connections: List[AgentSpecControlFlowEdge] = [
            AgentSpecControlFlowEdge(
                name=f"{agentspec_nodes[control_flow_edge.source_step.id].name}_to_{agentspec_nodes[control_flow_edge.destination_step.id].name}_control_flow_edge",
                from_node=agentspec_nodes[control_flow_edge.source_step.id],
                from_branch=(
                    control_flow_edge.source_branch
                    if control_flow_edge.source_branch != RuntimeStep.BRANCH_NEXT
                    else None
                ),
                to_node=agentspec_nodes[control_flow_edge.destination_step.id],
                metadata=_create_agentspec_metadata_from_runtime_component(control_flow_edge),
                id=control_flow_edge.id,
            )
            for control_flow_edge in runtime_flow.control_flow_edges
            if control_flow_edge.destination_step is not None
        ]
        context_providers_dict = {}
        if runtime_flow.context_providers:
            for context_provider in runtime_flow.context_providers:
                context_providers_dict[context_provider.id] = (
                    self._contextprovider_convert_to_agentspec(
                        conversion_context,
                        context_provider,
                        referenced_objects=referenced_objects,
                    )
                )

        data_flow_connections: List[AgentSpecDataFlowEdge] = []
        for runtime_data_flow_edge in runtime_flow.data_flow_edges:
            source_step_id = runtime_data_flow_edge.source_step.id
            destination_node = agentspec_nodes[runtime_data_flow_edge.destination_step.id]
            if source_step_id in agentspec_nodes:
                source_node = agentspec_nodes[source_step_id]
            else:
                # the source is a context provider
                source_node = context_providers_dict[source_step_id]
            new_edge_name = f"{source_node.name}_{runtime_data_flow_edge.source_output}_to_{destination_node.name}_{runtime_data_flow_edge.destination_input}_data_flow_edge"
            # We need to use partial build because we might have to rename inputs and outputs, and validation now could fail
            # We will re-validate the edge later
            new_edge = AgentSpecDataFlowEdge.build_from_partial_config(
                dict(
                    name=new_edge_name,
                    source_node=source_node,
                    source_output=runtime_data_flow_edge.source_output,
                    destination_node=destination_node,
                    destination_input=runtime_data_flow_edge.destination_input,
                    metadata=_create_agentspec_metadata_from_runtime_component(
                        runtime_data_flow_edge
                    ),
                    id=runtime_data_flow_edge.id,
                )
            )
            data_flow_connections.append(new_edge)

        node_name = f"None End node"
        end_node_outputs = [
            _runtime_property_to_pyagentspec_property(property_)
            for property_ in runtime_flow.output_descriptors
        ]
        new_end_node = AgentSpecEndNode(
            name=node_name,
            description="End node representing all transitions to None in the WayFlow flow",
            # In case of a missing end step, the expected branch name is the default BRANCH_NEXT
            branch_name=RuntimeCompleteStep.BRANCH_NEXT,
            outputs=end_node_outputs,
            metadata={},
        )

        def _connect_all_outputs_to_endnode_inputs(end_node_: AgentSpecEndNode) -> None:

            def _check_data_flow_edge_does_not_exist(
                source_node: AgentSpecNode,
                source_output: str,
                destination_node: AgentSpecNode,
                destination_input: str,
            ) -> bool:
                return not any(
                    source_node is data_flow_edge_.source_node
                    and source_output == data_flow_edge_.source_output
                    and destination_node is data_flow_edge_.destination_node
                    and destination_input == data_flow_edge_.destination_input
                    for data_flow_edge_ in data_flow_connections
                )

            # Connect all the inputs that appear in this new end node
            # to all the outputs of all the other nodes that have a matching name (i.e., title)
            for end_node_input in end_node_.inputs or []:
                output_name = end_node_input.json_schema["title"]
                for agentspec_node in agentspec_nodes.values():
                    if not isinstance(agentspec_node, AgentSpecEndNode):
                        for agentspec_node_output in agentspec_node.outputs or []:
                            if (
                                (
                                    output_name == agentspec_node_output.json_schema["title"]
                                    or (
                                        # In case of the MapNode or FlowNode as source node, we might have renamed
                                        # the source output from `title` to `collected_title`, so we have to rename here
                                        isinstance(
                                            agentspec_node,
                                            (
                                                AgentSpecMapNode,
                                                AgentSpecParallelMapNode,
                                                AgentSpecFlowNode,
                                            ),
                                        )
                                        and "collected_" + output_name
                                        == agentspec_node_output.json_schema["title"]
                                    )
                                )
                                and _json_schemas_have_same_type(
                                    end_node_input.json_schema, agentspec_node_output.json_schema
                                )
                                and _check_data_flow_edge_does_not_exist(
                                    source_node=agentspec_node,
                                    source_output=agentspec_node_output.json_schema["title"],
                                    destination_node=end_node_,
                                    destination_input=output_name,
                                )
                            ):
                                data_flow_connections.append(
                                    AgentSpecDataFlowEdge(
                                        name=f"{agentspec_node.name}_{output_name}_to_{end_node_.name}_{output_name}_data_flow_edge",
                                        source_node=agentspec_node,
                                        source_output=agentspec_node_output.json_schema["title"],
                                        destination_node=end_node_,
                                        destination_input=output_name,
                                    )
                                )

        all_nodes = list(agentspec_nodes.values())
        # As currently we do not always have end steps in wayflowcore, we create them if there aren't and we connect them
        end_node_added = False
        for control_flow_edge in runtime_flow.control_flow_edges:
            if control_flow_edge.destination_step is None and not isinstance(
                control_flow_edge.source_step, RuntimeCompleteStep
            ):
                if not end_node_added:
                    all_nodes.append(new_end_node)
                    end_node_added = True
                # Connect the step that was previously ending the flow to the new end node
                control_flow_connections.append(
                    AgentSpecControlFlowEdge(
                        name=f"{agentspec_nodes[control_flow_edge.source_step.id].name}_to_{node_name}_control_flow_edge",
                        from_node=agentspec_nodes[control_flow_edge.source_step.id],
                        from_branch=(
                            control_flow_edge.source_branch
                            if control_flow_edge.source_branch != RuntimeStep.BRANCH_NEXT
                            else None
                        ),
                        to_node=new_end_node,
                    )
                )

        # We connect all the end nodes that have new inputs to the outputs of all the nodes that generate
        # something with the expected name. This is needed because in runtime the flow exposes as output
        # all the outputs generated inside itself, so above in this code we had to expose all the generated outputs
        # as inputs in all the EndNodes, and here we connect these EndNode inputs with DataFlowEdges
        for node in all_nodes:
            if isinstance(node, AgentSpecEndNode):
                _connect_all_outputs_to_endnode_inputs(node)

        renamed_outputs = {}
        for data_flow_edge in data_flow_connections:

            def _add_collected(data_flow_edge: AgentSpecDataFlowEdge) -> None:
                # If it already starts with collected_, we do not add anything
                if data_flow_edge.source_output.startswith("collected_"):
                    return
                # We have to use the right output name of the MapNode in the source_output of the data edge
                # This means that we just need to add `collected_` as a prefix
                collected_source_output = f"collected_{data_flow_edge.source_output}"
                # We save the renamed outputs such that we can modify them on the end node after this block
                renamed_outputs[data_flow_edge.source_output] = collected_source_output
                data_flow_edge.source_output = collected_source_output
                # For consistency, we rename the data edge name as well
                data_flow_edge.name = (
                    f"{data_flow_edge.source_node.name}_{data_flow_edge.source_output}_to_"
                    f"{data_flow_edge.destination_node.name}_{data_flow_edge.destination_input}_"
                    "data_flow_edge"
                )

            if isinstance(data_flow_edge.source_node, (AgentSpecMapNode, AgentSpecParallelMapNode)):
                _add_collected(data_flow_edge)

            elif isinstance(data_flow_edge.source_node, AgentSpecFlowNode):
                for output_property in data_flow_edge.source_node.outputs or []:
                    if output_property.title == "collected_" + data_flow_edge.source_output:
                        _add_collected(data_flow_edge)

            elif isinstance(
                data_flow_edge.destination_node, (AgentSpecMapNode, AgentSpecParallelMapNode)
            ):
                # We have to use the right input name of the MapNode in the destination_input of the data edge
                # This means that we have to:
                # - look for the node input that starts with `iterated_`
                # - rename the destination_input of the edge with that name
                # - rename the data edge name for the consistency

                # The iterated input in WayFlow must be called RuntimeMapStep.ITERATED_INPUT, while
                # in Agent Spec we call all the inputs "iterated_" + name of the input in the inner flow
                # The name of the input we iterate on in the inner flow is given in the unpack_input dictionary of the step
                map_step = cast(
                    RuntimeMapStep, runtime_flow.steps[data_flow_edge.destination_node.name]
                )
                if len(map_step.unpack_input) != 1:
                    raise ValueError(
                        f"Unexpected unpack_input value for step `{map_step.name}`. "
                        f"Expected 1 entry, but found {len(map_step.unpack_input)}, should be converted "
                        f"to ExtendedMapNode but MapNode found"
                    )
                unpack_input_keys = list(map_step.unpack_input.keys())
                input_property_name_to_iterate = "iterated_" + unpack_input_keys[0]

                new_destination_property = next(
                    (
                        property_
                        for property_ in data_flow_edge.destination_node.inputs or []
                        if (
                            property_.title == "iterated_" + data_flow_edge.destination_input
                            or (
                                data_flow_edge.destination_input == RuntimeMapStep.ITERATED_INPUT
                                and property_.title == input_property_name_to_iterate
                            )
                        )
                    ),
                    None,
                )
                if new_destination_property:
                    data_flow_edge.destination_input = new_destination_property.title

            data_flow_edge.name = (
                f"{data_flow_edge.source_node.name}_{data_flow_edge.source_output}_to_"
                f"{data_flow_edge.destination_node.name}_{data_flow_edge.destination_input}_"
                "data_flow_edge"
            )

            # Manually trigger validation
            _ = AgentSpecDataFlowEdge.model_validate(data_flow_edge.__dict__)

        # We align the names in the EndNode input/output with the changes we made above
        # because we do not map an output to a different name at the EndNode.
        for node in all_nodes:
            if isinstance(node, AgentSpecEndNode):
                flow_end_node_inputs = node.inputs
                if flow_end_node_inputs:
                    for i, input_ in enumerate(flow_end_node_inputs):
                        # Since we renamed the output of a MapNode to "collected_XXX", we do the same
                        # using the `renamed_outputs` dictionary we created above to save the changes
                        if input_.title in renamed_outputs:
                            json_schema = input_.json_schema
                            json_schema["title"] = renamed_outputs[input_.title]
                            flow_end_node_inputs[i] = AgentSpecProperty(json_schema=json_schema)
                            # We also need to rename the edges the led to this renamed input
                            for data_flow_edge in data_flow_connections:
                                if data_flow_edge.destination_node is node:
                                    if data_flow_edge.destination_input == input_.title:
                                        data_flow_edge.destination_input = renamed_outputs[
                                            input_.title
                                        ]

                flow_end_node_outputs = node.outputs
                if flow_end_node_outputs:
                    for i, output_ in enumerate(flow_end_node_outputs):
                        if output_.title in renamed_outputs:
                            json_schema = output_.json_schema
                            json_schema["title"] = renamed_outputs[output_.title]
                            flow_end_node_outputs[i] = AgentSpecProperty(json_schema=json_schema)

        # When we define flow outputs, we cannot simply change from flow outputs because names were changed.
        # This means we either need to collect the outputs again from the updated EndNode
        # Or we again check the renamed names when converting from flow outputs
        # Below is the latter option
        flow_outputs: List[AgentSpecProperty] = []
        for flow_output in runtime_flow.output_descriptors or []:
            if flow_output.name in renamed_outputs:
                original_property = _runtime_property_to_pyagentspec_property(flow_output)
                json_schema = original_property.json_schema
                json_schema["title"] = renamed_outputs[flow_output.name]
                flow_outputs.append(AgentSpecProperty(json_schema=json_schema))
            else:
                flow_outputs.append(_runtime_property_to_pyagentspec_property(flow_output))

        flow_name = runtime_flow.name or runtime_flow.__metadata_info__.get("name", generate_id())
        flow_description = runtime_flow.description or runtime_flow.__metadata_info__.get(
            "description", ""
        )
        flow_state: List[AgentSpecProperty] = []
        for variable in runtime_flow.variables:
            flow_state.append(self._variable_convert_to_agentspec(variable))

        flow_args = dict(
            name=flow_name,
            description=flow_description,
            start_node=start_node,
            nodes=all_nodes,
            control_flow_connections=control_flow_connections,
            data_flow_connections=data_flow_connections,
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_flow.input_descriptors or []
            ],
            outputs=flow_outputs,
            metadata=_create_agentspec_metadata_from_runtime_component(runtime_flow),
            id=runtime_flow.id,
        )

        if context_providers_dict or flow_state:
            # has context providers, required a custom component
            context_providers = list(context_providers_dict.values())
            return AgentSpecExtendedFlow(
                **flow_args,
                context_providers=context_providers,
                state=flow_state,
            )
        else:
            # can use agentspec flow
            return AgentSpecFlow(**flow_args)

    def _managerworkers_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_managerworkers: RuntimeManagerWorkers,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecManagerWorkers:
        metadata = _create_agentspec_metadata_from_runtime_component(runtime_managerworkers)

        return AgentSpecManagerWorkers(
            name=runtime_managerworkers.name
            or runtime_managerworkers.__metadata_info__.get("name", generate_id()),
            description=runtime_managerworkers.description
            or runtime_managerworkers.__metadata_info__.get("description", ""),
            id=runtime_managerworkers.id,
            group_manager=cast(
                Union[AgentSpecAgent, AgentSpecLlmConfig],
                conversion_context.convert(
                    runtime_managerworkers.group_manager, referenced_objects
                ),
            ),
            workers=[
                cast(
                    AgentSpecAgent,
                    conversion_context.convert(worker, referenced_objects),
                )
                for worker in runtime_managerworkers.workers
            ],
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_managerworkers.input_descriptors or []
            ],
            outputs=[
                _runtime_property_to_pyagentspec_property(output)
                for output in runtime_managerworkers.output_descriptors or []
            ],
            metadata=metadata,
        )

    def _swarm_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_swarm: RuntimeSwarm,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecSwarm:
        metadata = _create_agentspec_metadata_from_runtime_component(runtime_swarm)

        return AgentSpecSwarm(
            name=runtime_swarm.name,
            description=runtime_swarm.description,
            id=runtime_swarm.id,
            first_agent=cast(
                AgentSpecAgent,
                conversion_context.convert(runtime_swarm.first_agent, referenced_objects),
            ),
            relationships=[
                (
                    cast(
                        AgentSpecAgent,
                        conversion_context.convert(sender, referenced_objects),
                    ),
                    cast(
                        AgentSpecAgent,
                        conversion_context.convert(recipient, referenced_objects),
                    ),
                )
                for sender, recipient in runtime_swarm.relationships
            ],
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_swarm.input_descriptors or []
            ],
            outputs=[
                _runtime_property_to_pyagentspec_property(output)
                for output in runtime_swarm.output_descriptors or []
            ],
            handoff=(
                runtime_swarm.handoff
                if isinstance(runtime_swarm.handoff, bool)
                else AgentSpecHandoffMode(runtime_swarm.handoff.value)
            ),
            metadata=metadata,
        )

    def _step_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_step: RuntimeStep,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecNode:
        # The runtime steps do not contain the name, but it is mandatory to buildAgent Spec Nodes
        # We give a temp name, and we assume that who knows the node's name will overwrite it
        node_name = runtime_step.name or runtime_step.__metadata_info__.get("name", "_temp_name_")
        node_description = runtime_step.__metadata_info__.get("description", "")
        runtime_step_type = type(runtime_step)
        metadata = _create_agentspec_metadata_from_runtime_component(runtime_step)
        inputs = [
            _runtime_property_to_pyagentspec_property(output)
            for output in runtime_step.input_descriptors or []
        ]
        outputs = [
            _runtime_property_to_pyagentspec_property(output)
            for output in runtime_step.output_descriptors or []
        ]
        node_id = runtime_step.id
        step_args = dict(
            name=node_name,
            description=node_description,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
            id=node_id,
        )
        # We compare the type directly instead of using isinstance in order to avoid
        # undesired, multiple node type matches due to class inheritance
        if runtime_step_type is RuntimePromptExecutionStep:
            runtime_step = cast(RuntimePromptExecutionStep, runtime_step)
            if (has_send_message := runtime_step.send_message) or (
                has_prompttemplate := isinstance(
                    runtime_step.prompt_template, RuntimePromptTemplate
                )
                or (has_input_mapping := runtime_step.input_mapping)
                or (has_output_mapping := runtime_step.output_mapping)
            ):
                if isinstance(runtime_step.prompt_template, RuntimePromptTemplate):
                    step_args["prompt_template_object"] = self._prompttemplate_convert_to_agentspec(
                        conversion_context,
                        runtime_step.prompt_template,
                        referenced_objects,
                    )
                    step_args["prompt_template"] = ""
                else:
                    step_args["prompt_template"] = runtime_step.prompt_template
                return AgentSpecExtendedLlmNode(
                    **step_args,
                    send_message=runtime_step.send_message,
                    llm_config=cast(
                        AgentSpecLlmConfig,
                        conversion_context.convert(runtime_step.llm, referenced_objects),
                    ),
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )
            else:
                return AgentSpecLlmNode(
                    **step_args,
                    prompt_template=runtime_step.prompt_template,
                    llm_config=cast(
                        AgentSpecLlmConfig,
                        conversion_context.convert(runtime_step.llm, referenced_objects),
                    ),
                )
        elif runtime_step_type is RuntimeCompleteStep:
            runtime_step = cast(RuntimeCompleteStep, runtime_step)
            return AgentSpecEndNode(
                **step_args,
                branch_name=runtime_step.branch_name or runtime_step.name,
            )
        elif runtime_step_type is RuntimeFlowExecutionStep:
            runtime_step = cast(RuntimeFlowExecutionStep, runtime_step)
            # We need to remove inputs and outputs because we might have renamed some inputs and outputs
            # due to, for example, MapNode i/o names remapping, so it's easier to let the node infer them from
            # the subflow rather than changing them here too
            del step_args["inputs"]
            del step_args["outputs"]
            return AgentSpecFlowNode(
                **step_args,
                subflow=cast(
                    AgentSpecFlow,
                    conversion_context.convert(runtime_step.flow, referenced_objects),
                ),
            )
        elif runtime_step_type is RuntimeAgentExecutionStep:
            runtime_step = cast(RuntimeAgentExecutionStep, runtime_step)
            inner_agent = cast(
                AgentSpecAgent,
                conversion_context.convert(runtime_step.agent, referenced_objects),
            )
            if (
                runtime_step.output_descriptors != runtime_step.agent.output_descriptors
                or (
                    runtime_step.caller_input_mode
                    and runtime_step.caller_input_mode != CallerInputMode.ALWAYS
                )
                or runtime_step.input_mapping
                or runtime_step.output_mapping
            ):
                return AgentSpecExtendedAgentNode(
                    **step_args,
                    agent=inner_agent,
                    caller_input_mode=runtime_step.caller_input_mode,
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )
            return AgentSpecAgentNode(
                **step_args,
                agent=inner_agent,
            )
        elif runtime_step_type is RuntimeConstantValuesStep:
            runtime_step = cast(RuntimeConstantValuesStep, runtime_step)
            return AgentSpecPluginConstantValuesNode(
                **step_args,
                constant_values=runtime_step.constant_values,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeGetChatHistoryStep:
            runtime_step = cast(RuntimeGetChatHistoryStep, runtime_step)
            return AgentSpecPluginGetChatHistoryNode(
                **step_args,
                n=runtime_step.n,
                which_messages=runtime_step.which_messages,
                offset=runtime_step.offset,
                message_types=(
                    list(runtime_step.message_types) if runtime_step.message_types else None
                ),
                output_template=runtime_step.output_template,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeRetryStep:
            runtime_step = cast(RuntimeRetryStep, runtime_step)
            return AgentSpecPluginRetryNode(
                **step_args,
                flow=cast(
                    AgentSpecFlow,
                    conversion_context.convert(runtime_step.flow, referenced_objects),
                ),
                success_condition=runtime_step.success_condition,
                max_num_trials=runtime_step.max_num_trials,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeToolExecutionStep:
            runtime_step = cast(RuntimeToolExecutionStep, runtime_step)
            step_args = dict(
                **step_args,
                tool=cast(
                    AgentSpecTool,
                    conversion_context.convert(runtime_step.tool, referenced_objects),
                ),
            )
            if (
                runtime_step.raise_exceptions
                and not runtime_step.input_mapping
                and not runtime_step.output_mapping
            ):
                return AgentSpecToolNode(**step_args)
            else:
                # requires a custom component for the raise_exceptions parameter
                return AgentSpecExtendedToolNode(
                    **step_args,
                    raise_exceptions=runtime_step.raise_exceptions,
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )
        elif runtime_step_type is RuntimeVariableReadStep:
            runtime_step = cast(RuntimeVariableReadStep, runtime_step)

            return AgentSpecPluginReadVariableNode(
                variable=self._variable_convert_to_agentspec(runtime_step.variable),
                **step_args,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeVariableStep:
            runtime_step = cast(RuntimeVariableStep, runtime_step)
            return AgentSpecPluginVariableNode(
                write_variables=self._variables_convert_to_agentspec(runtime_step.write_variables),
                read_variables=self._variables_convert_to_agentspec(runtime_step.read_variables),
                **step_args,
                write_operations=runtime_step.write_operations,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeVariableWriteStep:
            runtime_step = cast(RuntimeVariableWriteStep, runtime_step)
            return AgentSpecPluginWriteVariableNode(
                variable=self._variable_convert_to_agentspec(runtime_step.variable),
                **step_args,
                operation=runtime_step.operation,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeExtractStep:
            runtime_step = cast(RuntimeExtractStep, runtime_step)
            return AgentSpecPluginExtractNode(
                **step_args,
                output_values={
                    (
                        output_value_key.name
                        if isinstance(output_value_key, RuntimeProperty)
                        else output_value_key
                    ): output_value_value
                    for output_value_key, output_value_value in runtime_step.output_values.items()
                },
                llm_config=(
                    cast(
                        AgentSpecLlmConfig,
                        conversion_context.convert(runtime_step.llm, referenced_objects),
                    )
                    if runtime_step.llm
                    else None
                ),
                retry=runtime_step.retry,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeBranchingStep:
            runtime_step = cast(RuntimeBranchingStep, runtime_step)
            return AgentSpecBranchingNode(
                **step_args,
                mapping=runtime_step.branch_name_mapping,
            )
        elif runtime_step_type is RuntimeParallelFlowExecutionStep:
            runtime_step = cast(RuntimeParallelFlowExecutionStep, runtime_step)
            if (
                runtime_step.max_workers is not None
                or runtime_step.input_mapping
                or runtime_step.output_mapping
            ):
                return AgentSpecExtendedParallelFlowNode(
                    **step_args,
                    flows=[
                        cast(
                            AgentSpecFlow,
                            conversion_context.convert(
                                rt_flow, referenced_objects=referenced_objects
                            ),
                        )
                        for rt_flow in runtime_step.flows
                    ],
                    max_workers=runtime_step.max_workers,
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )
            return AgentSpecParallelFlowNode(
                **step_args,
                subflows=[
                    cast(
                        AgentSpecFlow,
                        conversion_context.convert(rt_flow, referenced_objects=referenced_objects),
                    )
                    for rt_flow in runtime_step.flows
                ],
            )
        elif runtime_step_type is RuntimeParallelMapStep:
            runtime_step = cast(RuntimeParallelMapStep, runtime_step)
            if (
                any(
                    unpacked_input_jq != "."
                    for unpacked_input_jq in (runtime_step.unpack_input or {}).values()
                )
                or runtime_step.max_workers is not None
                or runtime_step.input_mapping
                or runtime_step.output_mapping
            ):
                return AgentSpecExtendedParallelMapNode(
                    **step_args,
                    flow=cast(
                        AgentSpecFlow,
                        conversion_context.convert(runtime_step.flow, referenced_objects),
                    ),
                    unpack_input=runtime_step.unpack_input,
                    max_workers=runtime_step.max_workers,
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )

            reducers: Dict[str, ReductionMethod] = {}
            for output_descriptor in runtime_step.output_descriptors:
                reducers[output_descriptor.name] = ReductionMethod.APPEND

            # We do not add inputs and outputs to let the renaming of the i/o happen automatically
            # according to Agent Spec specification
            del step_args["inputs"]
            del step_args["outputs"]

            return AgentSpecParallelMapNode(
                **step_args,
                subflow=cast(
                    AgentSpecFlow,
                    conversion_context.convert(runtime_step.flow, referenced_objects),
                ),
                reducers=reducers,
            )
        elif runtime_step_type is RuntimeParallelFlowExecutionStep:
            runtime_step = cast(RuntimeParallelFlowExecutionStep, runtime_step)
            return AgentSpecExtendedParallelFlowNode(
                **step_args,
                flows=[
                    cast(
                        AgentSpecFlow,
                        conversion_context.convert(rt_flow, referenced_objects=referenced_objects),
                    )
                    for rt_flow in runtime_step.flows
                ],
                max_workers=runtime_step.max_workers,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeParallelMapStep:
            runtime_step = cast(RuntimeParallelMapStep, runtime_step)
            return AgentSpecExtendedParallelMapNode(
                **step_args,
                flow=cast(
                    AgentSpecFlow, conversion_context.convert(runtime_step.flow, referenced_objects)
                ),
                unpack_input=runtime_step.unpack_input,
                max_workers=runtime_step.max_workers,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeMapStep:
            runtime_step = cast(RuntimeMapStep, runtime_step)
            if (
                runtime_step.parallel_execution
                or any(
                    unpacked_input_jq != "."
                    for unpacked_input_jq in (runtime_step.unpack_input or {}).values()
                )
                or runtime_step.max_workers is not None
                or runtime_step.input_mapping
                or runtime_step.output_mapping
            ):
                # This scenario is not supported by Agent Spec spec, so we use the runtime plugin node
                return AgentSpecExtendedMapNode(
                    **step_args,
                    flow=cast(
                        AgentSpecFlow,
                        conversion_context.convert(runtime_step.flow, referenced_objects),
                    ),
                    unpack_input=runtime_step.unpack_input,
                    max_workers=runtime_step.max_workers,
                    parallel_execution=runtime_step.parallel_execution,
                    input_mapping=runtime_step.input_mapping,
                    output_mapping=runtime_step.output_mapping,
                )

            reducers = {}
            for output_descriptor in runtime_step.output_descriptors:
                reducers[output_descriptor.name] = ReductionMethod.APPEND

            # We do not add inputs and outputs to let the renaming of the i/o happen automatically
            # according to Agent Spec specification
            del step_args["inputs"]
            del step_args["outputs"]
            return AgentSpecMapNode(
                **step_args,
                subflow=cast(
                    AgentSpecFlow,
                    conversion_context.convert(runtime_step.flow, referenced_objects),
                ),
                reducers=reducers,
            )
        elif runtime_step_type is RuntimeStartStep:
            return AgentSpecStartNode(**step_args)
        elif runtime_step_type is RuntimeApiCallStep:
            runtime_step = cast(RuntimeApiCallStep, runtime_step)
            return AgentSpecApiNode(
                **step_args,
                url=runtime_step.url,
                http_method=runtime_step.method,
                data=(
                    runtime_step.json_body if isinstance(runtime_step.json_body, dict) else dict()
                ),
                query_params=(
                    runtime_step.params if isinstance(runtime_step.params, dict) else dict()
                ),
                headers=(
                    runtime_step.headers if isinstance(runtime_step.headers, dict) else dict()
                ),
                sensitive_headers=(
                    runtime_step.sensitive_headers
                    if isinstance(runtime_step.sensitive_headers, dict)
                    else dict()
                ),
            )
        elif runtime_step_type is RuntimeInputMessageStep:
            runtime_step = cast(RuntimeInputMessageStep, runtime_step)
            if (
                runtime_step.message_template is None
                and not runtime_step.rephrase
                and not runtime_step.input_mapping
            ):
                if runtime_step.output_mapping:
                    # If we have an output mapping, we rename the output of the Agent Spec node and use the core component
                    output_name = runtime_step.output_mapping[runtime_step.USER_PROVIDED_INPUT]
                    if len(step_args["outputs"]) > 0:
                        step_args["outputs"][0] = AgentSpecProperty(
                            json_schema=step_args["outputs"][0].json_schema, title=output_name
                        )
                    else:
                        step_args["outputs"] = [AgentSpecProperty(title=output_name, type="string")]
                return AgentSpecInputMessageNode(**step_args)
            return AgentSpecPluginInputMessageNode(
                **step_args,
                message_template=runtime_step.message_template,
                rephrase=runtime_step.rephrase,
                llm_config=(
                    cast(
                        AgentSpecLlmConfig,
                        conversion_context.convert(runtime_step.llm, referenced_objects),
                    )
                    if runtime_step.llm is not None
                    else None
                ),
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeOutputMessageStep:
            runtime_step = cast(RuntimeOutputMessageStep, runtime_step)
            if (
                runtime_step.message_type == MessageType.AGENT
                and not runtime_step.expose_message_as_output
                and not runtime_step.rephrase
                and not runtime_step.input_mapping
                and not runtime_step.output_mapping
            ):
                # The output message node in agentspec does not have outputs
                del step_args["outputs"]
                return AgentSpecOutputMessageNode(
                    **step_args,
                    message=runtime_step.message_template,
                )
            return AgentSpecPluginOutputMessageNode(
                **step_args,
                message=runtime_step.message_template,
                message_type=runtime_step.message_type,
                rephrase=runtime_step.rephrase,
                expose_message_as_output=runtime_step.expose_message_as_output,
                llm_config=(
                    cast(
                        AgentSpecLlmConfig,
                        conversion_context.convert(runtime_step.llm, referenced_objects),
                    )
                    if runtime_step.llm is not None
                    else None
                ),
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeCatchExceptionStep:
            runtime_step = cast(RuntimeCatchExceptionStep, runtime_step)
            return AgentSpecPluginCatchExceptionNode(
                **step_args,
                flow=cast(
                    AgentSpecFlow,
                    conversion_context.convert(runtime_step.flow, referenced_objects),
                ),
                catch_all_exceptions=runtime_step.catch_all_exceptions,
                except_on=runtime_step.except_on,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeDatastoreListStep:
            runtime_step = cast(RuntimeDatastoreListStep, runtime_step)
            return AgentSpecPluginDatastoreListNode(
                **step_args,
                datastore=cast(
                    AgentSpecDatastore,
                    conversion_context.convert(runtime_step.datastore, referenced_objects),
                ),
                collection_name=runtime_step.collection_name,
                where=runtime_step.where,
                limit=runtime_step.limit,
                unpack_single_entity_from_list=runtime_step.unpack_single_entity_from_list,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeDatastoreDeleteStep:
            runtime_step = cast(RuntimeDatastoreDeleteStep, runtime_step)
            return AgentSpecPluginDatastoreDeleteNode(
                **step_args,
                datastore=cast(
                    AgentSpecDatastore,
                    conversion_context.convert(runtime_step.datastore, referenced_objects),
                ),
                collection_name=runtime_step.collection_name,
                where=runtime_step.where,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeDatastoreUpdateStep:
            runtime_step = cast(RuntimeDatastoreUpdateStep, runtime_step)
            return AgentSpecPluginDatastoreUpdateNode(
                **step_args,
                datastore=cast(
                    AgentSpecDatastore,
                    conversion_context.convert(runtime_step.datastore, referenced_objects),
                ),
                collection_name=runtime_step.collection_name,
                where=runtime_step.where,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeDatastoreQueryStep:
            runtime_step = cast(RuntimeDatastoreQueryStep, runtime_step)
            return AgentSpecPluginDatastoreQueryNode(
                **step_args,
                datastore=cast(
                    AgentSpecRelationalDatastore,
                    conversion_context.convert(runtime_step.datastore, referenced_objects),
                ),
                query=runtime_step.query,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeDatastoreCreateStep:
            runtime_step = cast(RuntimeDatastoreCreateStep, runtime_step)
            return AgentSpecPluginDatastoreCreateNode(
                **step_args,
                datastore=cast(
                    AgentSpecDatastore,
                    conversion_context.convert(runtime_step.datastore, referenced_objects),
                ),
                collection_name=runtime_step.collection_name,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeRegexExtractionStep:
            runtime_step = cast(RuntimeRegexExtractionStep, runtime_step)
            return AgentSpecPluginRegexNode(
                **step_args,
                regex_pattern=self._regex_pattern_to_agentspec(runtime_step.regex_pattern),
                return_first_match_only=runtime_step.return_first_match_only,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeTemplateRenderingStep:
            runtime_step = cast(RuntimeTemplateRenderingStep, runtime_step)
            return AgentSpecPluginTemplateNode(
                **step_args,
                template=runtime_step.template,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        elif runtime_step_type is RuntimeChoiceSelectionStep:
            runtime_step = cast(RuntimeChoiceSelectionStep, runtime_step)
            if runtime_step.llm is None:
                raise ValueError(
                    f"Found a {runtime_step.__class__.__name__} without a valid LLM. Please make"
                    f" sure to define the llm properly."
                )
            return AgentSpecPluginChoiceNode(
                **step_args,
                llm_config=cast(
                    AgentSpecLlmConfig,
                    conversion_context.convert(runtime_step.llm, referenced_objects),
                ),
                next_branches=[
                    [
                        step_description.step_name,
                        step_description.description,
                        step_description.displayed_step_name,
                    ]
                    for step_description in runtime_step.next_steps
                ],
                prompt_template=runtime_step.prompt_template,
                num_tokens=runtime_step.num_tokens,
                input_mapping=runtime_step.input_mapping,
                output_mapping=runtime_step.output_mapping,
            )
        raise ValueError(f"Unsupported type of step in Agent Spec: {runtime_step_type}")

    def _a2aconnectionconfig_convert_to_agentspec(
        self,
        runtime_a2aconnectionconfig: RuntimeA2AConnectionConfig,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecA2AConnectionConfig:
        return AgentSpecA2AConnectionConfig(
            id=runtime_a2aconnectionconfig.id,
            name=runtime_a2aconnectionconfig.name,
            description=runtime_a2aconnectionconfig.description,
            metadata=runtime_a2aconnectionconfig.__metadata_info__,
            timeout=runtime_a2aconnectionconfig.timeout,
            headers=runtime_a2aconnectionconfig.headers,
            verify=runtime_a2aconnectionconfig.verify,
            key_file=runtime_a2aconnectionconfig.key_file,
            cert_file=runtime_a2aconnectionconfig.cert_file,
            ssl_ca_cert=runtime_a2aconnectionconfig.ssl_ca_cert,
        )

    def _a2aagent_convert_to_agentspec(
        self,
        conversion_context: "WayflowToAgentSpecConversionContext",
        runtime_a2aagent: RuntimeA2AAgent,
        referenced_objects: Optional[Dict[str, Any]] = None,
    ) -> AgentSpecA2AAgent:
        return AgentSpecA2AAgent(
            id=runtime_a2aagent.id,
            name=runtime_a2aagent.name,
            description=runtime_a2aagent.description,
            agent_url=runtime_a2aagent.agent_url,
            connection_config=cast(
                AgentSpecA2AConnectionConfig,
                conversion_context.convert(runtime_a2aagent.connection_config, referenced_objects),
            ),
            session_parameters=AgentSpecA2ASessionParameters(
                timeout=runtime_a2aagent.session_parameters.timeout,
                poll_interval=runtime_a2aagent.session_parameters.poll_interval,
                max_retries=runtime_a2aagent.session_parameters.max_retries,
            ),
            inputs=[
                _runtime_property_to_pyagentspec_property(input_)
                for input_ in runtime_a2aagent.input_descriptors or []
            ],
            outputs=[
                _runtime_property_to_pyagentspec_property(output)
                for output in runtime_a2aagent.output_descriptors or []
            ],
            metadata=_create_agentspec_metadata_from_runtime_component(runtime_a2aagent),
        )
