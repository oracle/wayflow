# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import subprocess
from textwrap import dedent

from wayflowcore.serialization.serializer import _import_all_submodules

_import_all_submodules("wayflowcore")


ALL_SERIALIZABLE_CLASSES = {
    "A2AAgent",
    "A2AAgentConversation",
    "A2AAgentState",
    "A2AConnectionConfig",
    "A2ASessionParameters",
    "Agent",
    "AgentConversation",
    "AgentConversationExecutionState",
    "AgentExecutionStep",
    "CanonicalizationMessageTransform",
    "AnyProperty",
    "ApiCallStep",
    "AppendTrailingSystemMessageToUserMessageTransform",
    "BooleanProperty",
    "BranchingStep",
    "CallableMessageTransform",
    "CatchExceptionStep",
    "ChoiceSelectionStep",
    "ClientTool",
    "ClientTransport",
    "ClientTransportWithAuth",
    "CoalesceSystemMessagesTransform",
    "CompleteStep",
    "Component",
    "ComponentWithInputsOutputs",
    "ConstantContextProvider",
    "ConstantValuesStep",
    "ContextProvider",
    "ControlFlowEdge",
    "Conversation",
    "ConversationExecutionState",
    "ConversationalComponent",
    "DataFlowEdge",
    "DataclassComponent",
    "Datastore",
    "DatastoreCreateStep",
    "DatastoreDeleteStep",
    "DatastoreListStep",
    "DatastoreQueryStep",
    "DatastoreUpdateStep",
    "DescribedAgent",
    "DescribedFlow",
    "DictProperty",
    "EmbeddingModel",
    "Entity",
    "Event",
    "ExecutionInterrupt",
    "ExecutionStatus",
    "ExtractValueFromJsonStep",
    "FinishedStatus",
    "FlexibleExecutionInterrupt",
    "FloatProperty",
    "Flow",
    "FlowContextProvider",
    "FlowConversation",
    "FlowConversationExecutionState",
    "FlowExecutionInterrupt",
    "FlowExecutionStep",
    "FrozenDataclassComponent",
    "FrozenSerializableDataclass",
    "GetChatHistoryStep",
    "HTTPmTLSBaseTransport",
    "HumanProxyAssistant",
    "ImageContent",
    "InMemoryDatastore",
    "InputMessageStep",
    "IntegerProperty",
    "InterruptedExecutionStatus",
    "JsonOutputParser",
    "JsonToolOutputParser",
    "ListProperty",
    "LlmCompletion",
    "LlmGenerationConfig",
    "LlmModel",
    "MCPTool",
    "MCPToolBox",
    "MTlsOracleDatabaseConnectionConfig",
    "ManagerWorkers",
    "ManagerWorkersConversation",
    "ManagerWorkersConversationExecutionState",
    "ManagerWorkersJsonToolOutputParser",
    "MapStep",
    "Message",
    "MessageContent",
    "MessageList",
    "MessageProperty",
    "MessageSummarizationTransform",
    "ConversationSummarizationTransform",
    "MessageTransform",
    "NullProperty",
    "OCIClientConfig",
    "OCIClientConfigWithApiKey",
    "OCIClientConfigWithInstancePrincipal",
    "OCIClientConfigWithResourcePrincipal",
    "OCIClientConfigWithSecurityToken",
    "OCIClientConfigWithUserAuthentication",
    "OCIGenAIEmbeddingModel",
    "OCIGenAIModel",
    "ObjectProperty",
    "OciAgent",
    "OciAgentConversation",
    "OciAgentState",
    "OllamaEmbeddingModel",
    "OllamaModel",
    "OpenAICompatibleEmbeddingModel",
    "OpenAICompatibleModel",
    "OpenAIEmbeddingModel",
    "OpenAIModel",
    "OracleDatabaseConnectionConfig",
    "OracleDatabaseDatastore",
    "OutputMessageStep",
    "OutputParser",
    "ParallelFlowExecutionStep",
    "ParallelMapStep",
    "PostgresDatabaseConnectionConfig",
    "PostgresDatabaseDatastore",
    "Prompt",
    "PromptExecutionStep",
    "PromptTemplate",
    "Property",
    "PythonToolOutputParser",
    "ReactToolOutputParser",
    "RegexExtractionStep",
    "RegexOutputParser",
    "RegexPattern",
    "RelationalDatastore",
    "RemoteBaseTransport",
    "RemoteTool",
    "RemoveEmptyNonUserMessageTransform",
    "RetryStep",
    "SSETransport",
    "SSEmTLSTransport",
    "SerializableDataclass",
    "ServerTool",
    "SessionParameters",
    "SoftTimeoutExecutionInterrupt",
    "SoftTokenLimitExecutionInterrupt",
    "SplitPromptOnMarkerMessageTransform",
    "StartStep",
    "StdioTransport",
    "Step",
    "StepDescription",
    "StreamableHTTPTransport",
    "StreamableHTTPmTLSTransport",
    "StringProperty",
    "Swarm",
    "SwarmConversation",
    "SwarmConversationExecutionState",
    "SwarmJsonToolOutputParser",
    "SwarmThread",
    "SwarmUser",
    "TemplateRenderingStep",
    "TextContent",
    "TlsOracleDatabaseConnectionConfig",
    "TlsPostgresDatabaseConnectionConfig",
    "TokenUsage",
    "Tool",
    "ToolBox",
    "ToolContextProvider",
    "ToolExecutionConfirmationStatus",
    "ToolExecutionStep",
    "ToolOutputParser",
    "ToolRequest",
    "ToolRequestStatus",
    "ToolResult",
    "UnionProperty",
    "UserMessageRequestStatus",
    "Variable",
    "VariableReadStep",
    "VariableStep",
    "VariableWriteStep",
    "VllmEmbeddingModel",
    "VllmModel",
    "_LlamaMergeToolRequestAndCallsTransform",
    "_NullExecutionInterrupt",
    "_PythonMergeToolRequestAndCallsTransform",
    "_ReactMergeToolRequestAndCallsTransform",
    "_TokenConsumptionEvent",
    "_ToolRequestAndCallsTransform",
}


def test_componentregistry_is_complete(tmp_path):
    # We need to run this in a separate script to avoid that creating classes in tests poison the registry of components
    all_classes_str = "{" + ", ".join(f'"{c}"' for c in ALL_SERIALIZABLE_CLASSES) + "}"
    script = dedent(
        f"""
        from wayflowcore.serialization.serializer import SerializableObject, _import_all_submodules

        _import_all_submodules("wayflowcore")

        ALL_SERIALIZABLE_CLASSES = {all_classes_str}

        component_registry_set = set(SerializableObject._COMPONENT_REGISTRY)

        missing = sorted(ALL_SERIALIZABLE_CLASSES - component_registry_set)
        extra   = sorted(component_registry_set - ALL_SERIALIZABLE_CLASSES)

        if missing or extra:
            lines = ["Component registry mismatch:"]
            if missing:
                lines.append(f"  Missing ({{len(missing)}}):")
                lines.extend(f"    - {{name}}" for name in missing)
            if extra:
                lines.append(f"  Extra ({{len(extra)}}):")
                lines.extend(f"    + {{name}}" for name in extra)
            raise AssertionError("\\n".join(lines))
        """
    )
    testfile = tmp_path / "_temp_test_componentregistry_is_complete.py"
    with open(testfile, "w") as f:
        f.write(script)
    result = subprocess.run(["python", testfile], capture_output=True, text=True)
    assert (
        result.returncode == 0
    ), f"Component registry does not match the components registry. Did you forget to add a new component to the test list?\n{result.stderr}"


def test_all_components_are_builtin_components(tmp_path):
    # We need to run this in a separate script to avoid that creating classes in tests poison the registry of components
    script = dedent(
        """
        from wayflowcore.serialization._builtins_components import _BUILTIN_COMPONENTS
        from wayflowcore.serialization.serializer import SerializableObject, _import_all_submodules

        _import_all_submodules("wayflowcore")

        component_registry = SerializableObject._COMPONENT_REGISTRY
        assert set(_BUILTIN_COMPONENTS) == set(component_registry)
        """
    )
    testfile = tmp_path / "_temp_test_all_components_are_builtin_components.py"
    with open(testfile, "w") as f:
        f.write(script)
    result = subprocess.run(["python", testfile])
    assert (
        result.returncode == 0
    ), f"Builtins component registry does not match the components registry. Did you forget to add a new component to the _BUILTIN_COMPONENTS?\n{result}"
