# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from wayflowcore import Agent
from wayflowcore.events import register_event_listeners
from wayflowcore.events.event import (
    ConversationMessageAddedEvent,
    ConversationMessageStreamChunkEvent,
    ConversationMessageStreamEndedEvent,
    ConversationMessageStreamStartedEvent,
    Event,
)
from wayflowcore.events.eventlistener import EventListener


def test_can_build_simple_ui_with_event_listeners(remotely_hosted_llm):

    class CustomUIEventListener(EventListener):

        def __init__(self) -> None:
            self.refresh_calls = 0
            self.currently_streaming = False
            self.ui_chat_list = []

        def __call__(self, event: Event) -> None:
            if isinstance(event, ConversationMessageStreamStartedEvent):
                # 1. message starts being streamed
                self.ui_chat_list.append(event.message)
                self.currently_streaming = True
            elif isinstance(event, ConversationMessageStreamChunkEvent):
                # 2. message is being updated with new chunk
                self.ui_chat_list[-1].content = self.ui_chat_list[-1].content + event.chunk
                self.refresh_calls += 1
                if not self.currently_streaming:
                    raise ValueError()
            elif isinstance(event, ConversationMessageStreamEndedEvent):
                # 3. finished message overrides previous message
                self.ui_chat_list[-1] = event.message
            if isinstance(event, ConversationMessageAddedEvent) and event.streamed is False:
                # 4. post new message only if not streamed, otherwise it's already added
                self.ui_chat_list.append(event.message)
            else:
                pass

    event_listener = CustomUIEventListener()
    agent = Agent(llm=remotely_hosted_llm)

    with register_event_listeners(event_listeners=[event_listener]):
        conv = agent.start_conversation()
        conv.append_user_message("What is the capital of Switzerland?")
        conv.execute()

    assert len(event_listener.ui_chat_list) == 2
    assert event_listener.ui_chat_list[0].role == "user"
    assert event_listener.ui_chat_list[1].role == "assistant"
    assert event_listener.refresh_calls > 0
