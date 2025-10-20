# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# isort:skip_file
# fmt: off
# mypy: ignore-errors

from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="model-id",
    host_port=os.environ["VLLM_HOST_PORT"],
)

# .. full-code:
from wayflowcore.agent import Agent

assistant = Agent(llm=llm)

conversation = assistant.start_conversation()
conversation.append_user_message("I need help regarding my sql query")
conversation.execute()

# get the assistant's response to your query
assistant_answer = conversation.get_last_message().content
# I'd be happy to help with your SQL query...

print(assistant_answer)
# .. end-full-code
