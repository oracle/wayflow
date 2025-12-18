# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Enable Tracing
import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.CRITICAL)

# .. start-##_Span_Exporter_Setup
import pprint
from pathlib import Path
from typing import List, Union
import os
from wayflowcore.tracing.span import Span
from wayflowcore.tracing.spanexporter import SpanExporter

class FileSpanExporter(SpanExporter):
    """SpanExporter that prints spans to a file.

    This class can be used for diagnostic purposes.
    It prints the exported spans to a file.
    """

    def __init__(self, filepath: Union[str, Path]):
        if isinstance(filepath, str):
            filepath = Path(filepath)
        self.filepath: Path = filepath

    def export(self, spans: List[Span], mask_sensitive_information=True) -> None:
        with open(self.filepath, "a") as file:
            for span in spans:
                print(
                    pprint.pformat(span.to_tracing_info(mask_sensitive_information), width=80, compact=True),
                    file=file,
                )

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
# .. end-##_Span_Exporter_Setup
# .. start-##_Build_Calculator_Agent
from wayflowcore.agent import Agent
from wayflowcore.models import VllmModel
from wayflowcore.tools import tool

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@tool(description_mode="only_docstring")
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b


@tool(description_mode="only_docstring")
def sum(a: float, b: float) -> float:
    """Sum two numbers"""
    return a + b


@tool(description_mode="only_docstring")
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b


llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

agent = Agent(
    agent_id="calculator_agent",
    name="Calculator agent",
    custom_instruction="You are a calculator agent. Please use tools to do math.",
    initial_message="Hi! I am a calculator agent. How can I help you?",
    llm=llm,
    tools=[sum, subtract, multiply, divide],
)
# .. end-##_Build_Calculator_Agent
(agent.llm,) = _update_globals(["llm_small"])  # docs-skiprow
# .. start-##_Export_Config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent)
# .. end-##_Export_Config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_Config
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    multiply.name: multiply,
    divide.name: divide,
    sum.name: sum,
    subtract.name: subtract,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)
# .. end-##_Load_Agent_Spec_Config
# .. start-##_Tracing_Basics
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor

span_processor = SimpleSpanProcessor(
    span_exporter=FileSpanExporter(filepath="calculator_agent_traces.txt")
)
# .. end-##_Tracing_Basics
span_processor.span_exporter =  FileSpanExporter(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "calculator_agent_traces.txt"))  # docs-skiprow
# .. start-##_Agent_Execution_With_Tracing
from wayflowcore.tracing.span import ConversationSpan
from wayflowcore.tracing.trace import Trace

conversation = agent.start_conversation()
with Trace(span_processors=[span_processor]):
    with ConversationSpan(conversation=conversation) as conversation_span:
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
        conversation_span.record_end_span_event(execution_status=status)
# .. end-##_Agent_Execution_With_Tracing

# .. start-##_Enable_Agent_Spec_Tracing
from pyagentspec.tracing.trace import Trace as AgentSpecTrace
from wayflowcore.agentspec.tracing import AgentSpecEventListener
from wayflowcore.events.eventlistener import register_event_listeners

# Here you can register the SpanProcessors that consume Agent Spec Traces emitted by WayFlow
with AgentSpecTrace() as trace:
    with register_event_listeners([AgentSpecEventListener()]):
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
# .. end-##_Enable_Agent_Spec_Tracing
