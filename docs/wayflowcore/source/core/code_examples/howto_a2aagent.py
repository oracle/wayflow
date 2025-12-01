# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Use A2A Agents

# .. start-##_Creating_the_agent
from wayflowcore.a2a.a2aagent import A2AAgent, A2AConnectionConfig

agent = A2AAgent(
    agent_url="http://<URL>",
    connection_config=A2AConnectionConfig(verify=False)
)
# .. end-##_Creating_the_agent
agent: A2AAgent  # docs-skiprow
(agent,) = _update_globals(["a2a_agent"])  # docs-skiprow # type: ignore

# .. start-##_Running_the_agent
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
# .. end-##_Running_the_agent

# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent: A2AAgent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
