# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# Code Example - How to Use A2A Agents
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
# python howto_a2aagent.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.



# %%[markdown]
## Creating the agent

# %%
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig

agent = A2AAgent(
    agent_url="http://<URL>",
    connection_config=A2AConnectionConfig(verify=False)
)


# %%[markdown]
## Running the agent

# %%
from wayflowcore.executors.executionstatus import UserMessageRequestStatus

# With a linear conversation
conversation = agent.start_conversation()

conversation.append_user_message("What is the answer to 2+2?")
status = conversation.execute()
if isinstance(status, UserMessageRequestStatus):
    assistant_reply = conversation.get_last_message()
    print(f"---\nAssistant >>> {assistant_reply.content}\n---")
else:
    print(f"Invalid execution status, expected UserMessageRequestStatus, received {type(status)}")


# %%[markdown]
## Export config to Agent Spec

# %%
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)

# %%[markdown]
## Load Agent Spec config

# %%
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
