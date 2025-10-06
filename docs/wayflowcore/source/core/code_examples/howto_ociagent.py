# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Use OCI Agents

# .. start-##_Creating_the_agent
from wayflowcore.models.ociclientconfig import OCIClientConfigWithApiKey
from wayflowcore.ociagent import OciAgent

oci_config = OCIClientConfigWithApiKey(service_endpoint="OCIGENAI_ENDPOINT")

agent = OciAgent(
    agent_endpoint_id="AGENT_ENDPOINT",
    client_config=oci_config,
)
# .. end-##_Creating_the_agent
agent: OciAgent  # docs-skiprow
(agent,) = _update_globals(["oci_agent"])  # docs-skiprow # type: ignore
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

# %%
# Or with an execution loop
# inputs = {}
# conversation = assistant.start_conversation(inputs)

# # What is the answer to 2+2?

# while True:
#     status = conversation.execute()
#     if isinstance(status, FinishedStatus):
#         break
#     assistant_reply = conversation.get_last_message()
#     if assistant_reply is not None:
#         print("\nAssistant >>>", assistant_reply.content)
#     user_input = input("\nUser >>> ")
#     conversation.append_user_message(user_input)
# .. end-##_Running_the_agent
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_assistant = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent: OciAgent = AgentSpecLoader().load_json(serialized_assistant)
# .. end-##_Load_Agent_Spec_config
