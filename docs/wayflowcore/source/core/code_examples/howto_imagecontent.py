# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to use use images in conversations

# .. start-##_Imports
import requests
from wayflowcore.agent import Agent
from wayflowcore.messagelist import ImageContent, Message, TextContent
from wayflowcore.models.llmmodel import Prompt

# .. end-##_Imports
# .. start-##_Model_configuration
from wayflowcore.models import VllmModel
llm = VllmModel(
    model_id="GEMMA_MODEL_ID",
    host_port="GEMMA_API_URL",
)
# .. end-##_Model_configuration
# .. start-##_Create_prompt
# Download the Oracle logo as PNG (publicly accessible image)
image_url = "https://www.oracle.com/a/ocom/img/oracle-logo.png"
response = requests.get(image_url)
response.raise_for_status()
image_bytes = response.content

# Create ImageContent: format must match the image (in this case: "png")
image_content = ImageContent.from_bytes(bytes_content=image_bytes, format="png")

# Compose a message with both image and question
text_content = TextContent(content="Which company's logo is this?")
user_message = Message(contents=[image_content, text_content], role="user")
prompt = Prompt(messages=[user_message])
# .. end-##_Create_prompt
llm: VllmModel  # docs-skiprow
(llm,) = _update_globals(["vision_llm"])  # docs-skiprow # type: ignore
# .. start-##_Generate_completion_with_an_image_as_input
result = llm.generate(prompt)
print("Model output:", result.message.content)
# For the Oracle logo, output should mention "Oracle Corporation"
# .. end-##_Generate_completion_with_an_image_as_input
# .. start-##_Pass_an_image_to_an_agent_as_input
# Create an Agent configured for vision
agent = Agent(llm=llm)

# Start a new conversation
conversation = agent.start_conversation()

# Add a user message with both image and text as contents
conversation.append_message(Message(contents=[image_content, text_content], role="user"))

# Run agent logic for this input
conversation.execute()

# Retrieve and print the agent's last response
agent_output = conversation.get_last_message()
if agent_output is not None:
    print("Agent output:", agent_output.content)
# The output should mention "Oracle Corporation"
# .. end-##_Pass_an_image_to_an_agent_as_input
# .. start-##_Export_config_to_Agent_Spec
from wayflowcore.agentspec import AgentSpecExporter

serialized_agent = AgentSpecExporter().to_json(agent)
# .. end-##_Export_config_to_Agent_Spec
# .. start-##_Load_Agent_Spec_config
from wayflowcore.agentspec import AgentSpecLoader

agent = AgentSpecLoader().load_json(serialized_agent)
# .. end-##_Load_Agent_Spec_config
