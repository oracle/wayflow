# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# %%[markdown]
# Code Example - How to Enable Tracing
# ------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_tracing.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import warnings

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.CRITICAL)


# %%[markdown]
## Span Exporter Setup

# %%
import pprint
from pathlib import Path
from typing import List, Union

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

    def export(self, spans: List[Span]) -> None:
        with open(self.filepath, "a") as file:
            for span in spans:
                print(
                    pprint.pformat(span.to_tracing_info(), width=80, compact=True),
                    file=file,
                )

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

# %%[markdown]
## Build Calculator Agent

# %%
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

# %%[markdown]
## Export Config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

config = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec Config

# %%
from wayflowcore.agentspec import AgentSpecLoader

tool_registry = {
    multiply.name: multiply,
    divide.name: divide,
    sum.name: sum,
    subtract.name: subtract,
}
new_agent = AgentSpecLoader(tool_registry=tool_registry).load_json(config)

# %%[markdown]
## Tracing Basics

# %%
from wayflowcore.tracing.spanprocessor import SimpleSpanProcessor

span_processor = SimpleSpanProcessor(
    span_exporter=FileSpanExporter(filepath="calculator_agent_traces.txt")
)

# %%[markdown]
## Agent Execution With Tracing

# %%
from wayflowcore.tracing.span import ConversationSpan
from wayflowcore.tracing.trace import Trace

conversation = agent.start_conversation()
with Trace(span_processors=[span_processor]):
    with ConversationSpan(conversation=conversation) as conversation_span:
        conversation.execute()
        conversation.append_user_message("Compute 2+3")
        status = conversation.execute()
        conversation_span.record_end_span_event(execution_status=status)
