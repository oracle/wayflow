# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

import os

model_config = {
    "model_type": "vllm",
    "host_port": os.environ["VLLM_HOST_PORT"],  # example: 8.8.8.8:8000
    "model_id": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}


# .. start-llm:
from wayflowcore.models import LlmModelFactory

llm = LlmModelFactory.from_config(model_config)
# .. end-llm

# .. start-agent:
from wayflowcore.agent import Agent

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, but keep it short""",
    initial_message=None,
)
# .. end-agent

# .. start-execute:
conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Welcome to our article writing guide. How can I assist you today?
# .. end-execute


# .. start-conversation:
agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
Make sure to welcome the user first, their name is {{user_name}}, but keep it short""",
    initial_message=None,
)

conversation = agent.start_conversation(inputs={"user_name": "Jerry"})
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# Hello Jerry, I'm here to help with any article writing-related questions you may have. Go ahead and ask away!
# .. end-conversation


# .. start-context:
from datetime import datetime

from wayflowcore.contextproviders import ToolContextProvider
from wayflowcore.tools import tool

@tool
def get_current_time() -> str:
    """Tool that gets the current time"""
    return datetime.now().strftime("%d, %B %Y, %I:%M %p")

time_provider = ToolContextProvider(tool=get_current_time, output_name="current_time")

agent = Agent(
    llm=llm,
    custom_instruction="""Your a helpful writing assistant. Answer the user's questions about article writing.
It's currently {{current_time}}.""",
    initial_message=None,
    context_providers=[time_provider],
)

conversation = agent.start_conversation()
conversation.execute()
last_message = conversation.get_last_message()
print(last_message.content if last_message else "No message")
# I'm here to assist you with any article writing-related questions or concerns. What do you need help with today?
# .. end-context
