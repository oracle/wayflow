# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Use the Event System

from collections import defaultdict
import logging

from wayflowcore.events.event import Event, LlmGenerationResponseEvent, ToolExecutionStartEvent
from wayflowcore.events.eventlistener import EventListener, register_event_listeners
from wayflowcore.models import VllmModel
from wayflowcore.agent import Agent
from wayflowcore.tools import tool

# .. start-##_TokenUsage
class TokenUsageListener(EventListener):
    """Custom event listener to track token usage from LLM responses."""
    def __init__(self):
        self.total_tokens_used = 0

    def __call__(self, event: Event):
        if isinstance(event, LlmGenerationResponseEvent):
            token_usage = event.completion.token_usage
            if token_usage:
                self.total_tokens_used += token_usage.total_tokens
                logging.info(f"Tokens used in this response: {token_usage.total_tokens}")
                logging.info(f"Running total tokens used: {self.total_tokens_used}")

    def get_total_tokens_used(self):
        """Return the total number of tokens used."""
        return self.total_tokens_used
# .. end-##_TokenUsage

# .. start-##_Tool_Call_Listener
class ToolCallListener(EventListener):
    """Custom event listener to track the number and type of tool calls."""
    def __init__(self):
        self.tool_calls = defaultdict(int)

    def __call__(self, event: ToolExecutionStartEvent):
        if isinstance(event, ToolExecutionStartEvent):
            self.tool_calls[str(event.tool.name)] += 1

    def get_tool_call_summary(self):
        """Return a summary of tool calls."""
        return self.tool_calls
# .. end-##_Tool_Call_Listener

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)

# .. start-##_Agent
@tool(description_mode="only_docstring")
def add(a: float, b: float) -> float:
    """Add two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The sum of the two numbers.
    """
    return a + b

@tool(description_mode="only_docstring")
def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Parameters:
        a: The first number.
        b: The second number.

    Returns:
        float: The product of the two numbers.
    """
    return a * b

agent = Agent(llm=llm, tools=[add, multiply], name="Calculator Agent")
# .. end-##_Agent

(agent.llm,) = _update_globals(["llm_small"])  # docs-skiprow

# .. start-##_Conversation
token_listener = TokenUsageListener()
tool_call_listener = ToolCallListener()

event_listeners = [token_listener, tool_call_listener]

with register_event_listeners(event_listeners):
    conversation = agent.start_conversation()
    conversation.append_user_message("Calculate 6*2+3 using the tools you have.")
    status = conversation.execute()

print(f"Total Tokens Used in Conversation: {token_listener.get_total_tokens_used()}")
tool_summary = tool_call_listener.get_tool_call_summary()
print(f"Tool Call Summary: {tool_summary}")
# .. end-##_Conversation

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec

# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
