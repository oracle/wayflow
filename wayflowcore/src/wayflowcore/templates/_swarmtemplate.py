# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from textwrap import shorten
from typing import List, Tuple

from wayflowcore.messagelist import Message, MessageType, TextContent
from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform,
    CoalesceSystemMessagesTransform,
    MessageTransform,
)

_DEFAULT_SWARM_SYSTEM_PROMPT = """
You are a helpful AI Agent.
- name: {{name}}
- description: {{description}}

<environment>
You are part of a Swarm of Agents.
You can use tools to interact with other agents in the swarm.

<user>
Your user/caller is: {{caller_name}}.
- The user is **not** aware of the other entities you can communicate with.
- Include all necessary context when communicating with the user/other entity.
</user>

<other_entities>
You can communicate with the following entities.
{% for agent in other_agents %}
- {{agent.name}}: {{agent.description}}
{% endfor %}
</other_entities>
</environment>

<response_rules>
<tool_use_rules>
- Never mention any specific tool names to users
- Carefully verify available tools; do not fabricate non-existent tools. Delegate when necessary.
- Tool request/results may originate from other parts of the system; only use explicitly provided tools
- Call MULTIPLE TOOLS at once is supported. Output multiple tool requests at once when the user’s query can be broken into independent subtasks.
If `handoff_conversation` is included, it must be the final tool call.
Note that tool calls are executed sequentially, but all tool results are returned to you together.
- {%- if handoff=="optional" -%} You SHOULD use handoff_conversation tool if you think another agent can answer to the user directly,
as this reduces unnecessary relaying and lowers latency {%- endif -%}
- {%- if handoff=="always" -%} You must use the handoff_conversation tool when delegating to another agent.{%- endif -%}
</tool_use_rules>

Always structure your response as a thought followed by one or multiple tool calls using JSON compliant syntax.
The user can only see the content of the messages sent with `talk_to_user` and will not see any of your thoughts.
-> Put **internal-only** information in the thoughts
-> Put all necessary information in the tool calls to communicate to user/other entity.

Do not use variables in the function call. Here's the structure:

YOUR THOUGHTS (WHAT ACTION YOU ARE GOING TO TAKE; NOT VISIBLE TO THE USER)

{"name": function name, "parameters": dictionary of argument name and its value}
</response_rules>

<tools>
Here is a list of functions that you can invoke.
{% for tool in __TOOLS__%}
{{tool | tojson}}{{ ",
" }}
{% endfor %}
</tools>

{%- if custom_instruction -%}
<system_instructions>
Here are the instructions specific to your role:
{{custom_instruction}}
</system_instructions>{%- endif -%}
""".strip()


_DEFAULT_SWARM_SYSTEM_REMINDER = """
--- SYSTEM REMINDER ---
You are a helpful AI Agent, your name: {{name}}. Your user/caller is: {{caller_name}}.

The user can only see the content of the messages sent with `talk_to_user` and will not see any of your thoughts.

Always structure your response as a thought followed by a function call using JSON compliant syntax.
Do not use variables in the function call. Here's the structure:

YOUR THOUGHTS (WHAT ACTION YOU ARE GOING TO TAKE; NOT VISIBLE TO THE USER)

{"name": function name, "parameters": dictionary of argument name and its value}
""".strip()


def _is_system_reminder(message: "Message") -> bool:
    return message.message_type == MessageType.SYSTEM and message.content.startswith(
        "--- SYSTEM REMINDER ---"
    )


_HANDOFF_CONFIRMATION_MESSAGE_TEMPLATE = """
The conversation was transferred from agent '{{sender_agent_name}}' to agent '{{new_agent_name}}'.
The user will see that the conversation has been transferred, do not reintroduce yourself.
Simply continue the conversation from where the previous agent left off.
""".strip()

_MAX_CHAR_TOOL_RESULT_HEADER = 140
"""Max number of characters in the message header when formatting a Tool Result"""


class _ToolRequestAndCallsTransform(MessageTransform, SerializableObject):
    def __call__(self, messages: List["Message"]) -> List["Message"]:
        """
        Format Tool requests as Agent messages and Tool results as User messages to have a simple User/Agent
        sequence of messages.
        """
        from wayflowcore import Message, MessageType

        tool_request_by_id = {  # Mapping for fast lookup
            tool_request.tool_request_id: tool_request
            for msg in messages
            if msg.message_type is MessageType.TOOL_REQUEST and msg.tool_requests
            for tool_request in msg.tool_requests
        }

        formatted_messages = []
        for message in messages:
            if message.message_type == MessageType.TOOL_RESULT:
                # Find corresponding ToolRequest by tool_request_id
                if not message.tool_result:
                    raise ValueError(f"TOOL_RESULT message must contain tool_result: {message}")
                tool_request_id = message.tool_result.tool_request_id
                tool_request = tool_request_by_id.get(tool_request_id)
                if not tool_request:
                    raise ValueError(
                        f"Could not find matching ToolRequest for TOOL_RESULT with id: {tool_request_id}"
                    )

                message_header_tool_info = shorten(
                    f"name={tool_request.name}, parameters={tool_request.args}",
                    width=_MAX_CHAR_TOOL_RESULT_HEADER,
                    placeholder=" ...}",
                )
                formatted_messages.append(
                    Message(
                        content=(
                            f"--- TOOL RESULT: {message_header_tool_info} ---\n"
                            f"{message.tool_result.content!r}"
                        ),
                        message_type=MessageType.USER,
                    )
                )

            elif message.message_type == MessageType.TOOL_REQUEST:
                if not message.tool_requests:
                    raise ValueError(
                        "Message is of type TOOL_REQUEST but has no tool_requests. This should be reported."
                    )

                formatted_tool_calls = "\n".join(
                    json.dumps({"name": tool_request.name, "parameters": tool_request.args})
                    for tool_request in message.tool_requests
                )

                formatted_messages.append(
                    Message(
                        content=(
                            f"--- MESSAGE: From: {message.sender} ---\n"
                            f"{message.content}\n"
                            f"{formatted_tool_calls}"
                        ),
                        message_type=MessageType.AGENT,
                    )
                )
            elif message.message_type == MessageType.SYSTEM:
                formatted_messages.append(message)
            else:
                message_copy = message.copy()
                if message_copy.role == "user" and not message_copy.sender:
                    # If the message's sender is None, it is from the HUMAN USER
                    message_copy.sender = "HUMAN USER"

                message_copy.contents.insert(
                    0, TextContent(f"--- MESSAGE: From: {message_copy.sender} ---\n")
                )
                formatted_messages.append(message_copy)
        return formatted_messages


class SwarmJsonToolOutputParser(JsonToolOutputParser, SerializableObject):
    def parse_thoughts_and_calls(self, raw_txt: str) -> Tuple[str, str]:
        """Swarm-specific function to separate thoughts and tool calls."""
        if "{" not in raw_txt:  # Will need to be adapted for parallel tool calls
            return "", raw_txt
        thoughts, raw_tool_calls = raw_txt.split("{", maxsplit=1)
        return thoughts.strip(), "{" + raw_tool_calls.replace("args={", "parameters={")


_DEFAULT_SWARM_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": _DEFAULT_SWARM_SYSTEM_PROMPT},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {"role": "system", "content": _DEFAULT_SWARM_SYSTEM_REMINDER},
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        _ToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        AppendTrailingSystemMessageToUserMessageTransform(),
    ],
    output_parser=SwarmJsonToolOutputParser(),
)
