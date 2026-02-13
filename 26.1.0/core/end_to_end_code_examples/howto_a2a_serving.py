# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# How to Serve Agents with A2A Protocol
# -------------------------------------

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
# python howto_a2a_serving.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.




# %%[markdown]
## Create the agent

# %%
from typing import Annotated
from wayflowcore.agent import Agent
from wayflowcore.tools import tool

@tool
def multiply(
    a: Annotated[int, "first required integer"],
    b: Annotated[int, "second required integer"],
) -> int:
    "Return the result of multiplication between number a and b."
    return a * b

agent = Agent(
    llm=llm,
    name="math_agent",
    custom_instruction="You are a Math agent that can do multiplication using the equipped tool.",
    can_finish_conversation=True,
)


# %%[markdown]
## Serve the agent

# %%
from wayflowcore.agentserver.server import A2AServer

server = A2AServer()
server.serve_agent(agent=agent, url="https://<the_public_url_where_agent_can_be_found>")
# server.run(host="127.0.0.1", port=8002) # Uncomment this line to start the server


# %%[markdown]
## Serve a flow

# %%
from wayflowcore.agent import Agent, CallerInputMode
from wayflowcore.property import StringProperty
from wayflowcore.flow import Flow
from wayflowcore.steps import AgentExecutionStep, OutputMessageStep

agent = Agent(llm=llm, can_finish_conversation=True)
agent_step = AgentExecutionStep(
    name="agent_step",
    agent=agent,
    caller_input_mode=CallerInputMode.NEVER,
    output_descriptors=[StringProperty(name="output")],
)

user_output_step = OutputMessageStep(
    name="user_output_step", input_mapping={"message": "output"}
)

flow = Flow.from_steps([agent_step, user_output_step])

server = A2AServer()
server.serve_agent(
    agent=flow,
    url="https://<the_public_url_where_agent_can_be_found>"
)
