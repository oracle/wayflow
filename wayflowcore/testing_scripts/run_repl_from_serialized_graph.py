# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

# Usage:
# ```
# > python run_repl_from_serialized_flow.py path/to/config/file.yaml
# ```

import sys
from typing import cast

from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.flow import Flow
from wayflowcore.messagelist import MessageType
from wayflowcore.serialization import deserialize

# needed for registration

if __name__ == "__main__":
    serialized_flow_file_path = sys.argv[1]
    with open(serialized_flow_file_path) as serialized_flow_file:
        serialized_flow = serialized_flow_file.read()
    assistant: Flow = cast(Flow, deserialize(Flow, serialized_flow))
    conversation = assistant.start_conversation()
    user_input, finished = None, False

    print()
    message_idx = 0
    while not finished:
        user_input = input("\nUSER >>> ")
        conversation.append_user_message(user_input)
        message_idx += 1
        status = assistant.execute(conversation)
        finished = isinstance(status, FinishedStatus)
        messages = conversation.get_messages()
        for message in messages[message_idx:]:
            if message.message_type == MessageType.TOOL_REQUEST:
                print(f"\n{message.message_type.value} >>> {message.tool_requests}")
            else:
                print(f"\n{message.message_type.value} >>> {message.content}")
        message_idx = len(messages)
