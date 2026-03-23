# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# isort:skip_file
# fmt: off
# mypy: ignore-errors
# docs-title: Code Example - How to Checkpoint and Resume Conversations

# .. start-##_Configure_your_LLM
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)
# .. end-##_Configure_your_LLM

llm: VllmModel  # docs-skiprow
(llm,) = _update_globals(["llm_small"])  # docs-skiprow # type: ignore

# .. start-##_Start_a_checkpointed_conversation
from wayflowcore import Agent
from wayflowcore.checkpointing import InMemoryCheckpointer

agent = Agent(llm=llm)
checkpointer = InMemoryCheckpointer()

conversation = agent.start_conversation(
    conversation_id="support-thread-1",
    checkpointer=checkpointer,
)

status = conversation.execute()
# .. end-##_Start_a_checkpointed_conversation

# .. start-##_Resume_the_latest_checkpoint
restored_conversation = agent.start_conversation(
    conversation_id="support-thread-1",
    checkpointer=checkpointer,
)

restored_conversation.append_user_message("Continue from where you left off.")
status = restored_conversation.execute()
# .. end-##_Resume_the_latest_checkpoint

# .. start-##_Load_a_specific_checkpoint
checkpoints = checkpointer.list_checkpoints("support-thread-1")

previous_checkpoint = checkpoints[-2]
rewound_conversation = agent.start_conversation(
    conversation_id="support-thread-1",
    checkpoint_id=previous_checkpoint.checkpoint_id,
    checkpointer=checkpointer,
)

rewound_conversation.append_user_message("Try a different path from here.")
status = rewound_conversation.execute()
# .. end-##_Load_a_specific_checkpoint

# .. start-##_Control_checkpoint_frequency
from wayflowcore.checkpointing import CheckpointingInterval, InMemoryCheckpointer

checkpointer = InMemoryCheckpointer(
    checkpointing_interval=CheckpointingInterval.ALL_INTERNAL_TURNS,
)
# .. end-##_Control_checkpoint_frequency
