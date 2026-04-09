# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Wayflow Code Example - How to Return Tool Artifacts


# .. start-##_Define_the_llm
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Define_the_llm
(llm,) = _update_globals(["llm_big"])  # docs-skiprow # type: ignore

# .. start-##_Imports_for_this_guide
import uuid

from wayflowcore.agent import Agent
from wayflowcore.events.event import Event, ToolExecutionResultEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.flow import Flow
from wayflowcore.steps import ToolExecutionStep
from wayflowcore.tools import ReturnArtifact, ToolOutputType, tool
# .. end-##_Imports_for_this_guide

# .. start-##_Define_tool_with_artifacts
@tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
def analyze_logs(path: str) -> ReturnArtifact[str]:
    """Summarize a log file for the agent and attach the full log for the UI."""

    full_log = f"INFO Starting app for {path}\nWARN Example warning in {path}\n"
    summary = (
        f"Log summary for {path}\n"
        "- status: warning detected\n"
        "- suggested action: inspect the attached artifact\n"
    )
    return summary, {
        "name": f"log_{uuid.uuid4()}.txt",
        "mime_type": "text/plain",
        "data": full_log,
    }
# .. end-##_Define_tool_with_artifacts

# .. start-##_Define_tool_with_multiple_artifacts
@tool(description_mode="only_docstring", output_type=ToolOutputType.CONTENT_AND_ARTIFACT)
def analyze_logs_with_multiple_artifacts(path: str) -> ReturnArtifact[str]:
    """Summarize a log file and attach multiple artifacts for the UI."""

    full_log = f"INFO Starting app for {path}\nWARN Example warning in {path}\n"
    report = '{"status": "warning", "path": "' + path + '"}'
    summary = (
        f"Log summary for {path}\n"
        "- status: warning detected\n"
        "- suggested action: inspect the attached artifacts\n"
    )
    return summary, {
        f"log_{uuid.uuid4()}.txt": {
            "mime_type": "text/plain",
            "data": full_log,
        },
        "report.json": {
            "mime_type": "application/json",
            "data": report,
        },
    }
# .. end-##_Define_tool_with_multiple_artifacts

# .. start-##_Define_event_listener
class CaptureArtifacts(EventListener):
    def __init__(self):
        self.artifacts = []

    def __call__(self, event: Event) -> None:
        if isinstance(event, ToolExecutionResultEvent):
            self.artifacts.extend(event.tool_result.artifacts)
# .. end-##_Define_event_listener

# .. start-##_Build_the_agent
assistant = Agent(
    llm=llm,
    name="artifact-agent",
    description="Agent that returns tool artifacts",
    custom_instruction="Use tools to summarize logs and keep bulky outputs as artifacts.",
    tools=[analyze_logs],
)
# .. end-##_Build_the_agent

# .. start-##_Access_artifacts_from_agent_conversation
listener = CaptureArtifacts()
with register_event_listeners([listener]):
    conversation = assistant.start_conversation()
    conversation.append_user_message("Please analyze the logs at /tmp/app.log")
    conversation.execute()

tool_message = next(
    message for message in reversed(conversation.get_messages()) if message.tool_result is not None
)
artifact = tool_message.tool_result.artifacts[0]
print(artifact.name)
print(artifact.data[:80])
# .. end-##_Access_artifacts_from_agent_conversation

# .. start-##_Access_artifacts_from_flow
flow = Flow.from_steps([ToolExecutionStep(tool=analyze_logs)])
listener = CaptureArtifacts()
with register_event_listeners([listener]):
    conversation = flow.start_conversation(inputs={"path": "app.log"})
    conversation.execute()

print(listener.artifacts[0].data[:80])
# .. end-##_Access_artifacts_from_flow

# .. start-##_Access_multiple_artifacts_from_flow
flow = Flow.from_steps([ToolExecutionStep(tool=analyze_logs_with_multiple_artifacts)])
listener = CaptureArtifacts()
with register_event_listeners([listener]):
    conversation = flow.start_conversation(inputs={"path": "service.log"})
    conversation.execute()

artifact_names = {artifact.name for artifact in listener.artifacts}
assert "report.json" in artifact_names
assert any(name is not None and name.endswith(".txt") for name in artifact_names)
# .. end-##_Access_multiple_artifacts_from_flow

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(assistant)
from wayflowcore.agentspec import AgentSpecLoader

loader = AgentSpecLoader(tool_registry={analyze_logs.name: analyze_logs.func})
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
reloaded_assistant = loader.load_json(serialized_assistant)
assert reloaded_assistant.tools[0].output_type == ToolOutputType.CONTENT_AND_ARTIFACT
# .. end-##_Load_Agent_Spec_config
