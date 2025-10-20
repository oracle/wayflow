# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.agent import Agent


def test_events_list_length_limit_is_respected(remotely_hosted_llm):
    events_max_len = 1
    agent = Agent(llm=remotely_hosted_llm)
    conversation = agent.start_conversation()
    conversation.state._EVENTS_LIST_MAX_LENGTH = events_max_len
    assert len(conversation.state.events) == 0
    conversation.append_user_message("Hello, how are you?")
    _ = agent.execute(conversation)
    assert len(conversation.state.events) == events_max_len
    conversation.append_user_message("Tell me a nice joke")
    _ = agent.execute(conversation)
    assert len(conversation.state.events) == events_max_len
