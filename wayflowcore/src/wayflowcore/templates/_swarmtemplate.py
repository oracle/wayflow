# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from textwrap import shorten
from typing import List, Tuple

from wayflowcore._utils.formatting import format_tool_output_for_llm
from wayflowcore.messagelist import Message, MessageType, TextContent
from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates.template import _TOOL_OUTPUT_SYSTEM_RULE
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform,
    CoalesceSystemMessagesTransform,
    MessageTransform,
)

_DEFAULT_SWARM_SYSTEM_PROMPT = (
    """
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

<recipient_names>
Valid recipient names are exactly:
{% for agent in other_agents %}
- `{{agent.name}}`
{% endfor %}
</recipient_names>
</environment>

<response_rules>
<tool_use_rules>
- Never mention any specific tool names to users
- Carefully verify available tools; do not fabricate non-existent tools. Delegate when necessary.
- Tool request/results may originate from other parts of the system; only use explicitly provided tools
- For any `recipient` parameter, copy exactly one name from <recipient_names>. Do not invent, translate, pluralize, misspell, or alter recipient names.
{% if handoff!="always" %}
- Calling MULTIPLE TOOLS at once is supported. Output multiple tool requests at once when the user’s query can be broken into INDEPENDENT subtasks.
- For independent subtasks handled by different agents, output one `send_message` tool request for each agent in the same response before waiting for results.
- If the request has N independent subtasks handled by N different agents, output exactly N `send_message` tool requests in the same response; do not omit, combine, or defer any of those first requests.
- For independent multi-agent requests, calling only the first subtask and waiting is incorrect; the first response after the request must include every independent `send_message` call.
- Every `send_message` tool request must include a non-empty `message` parameter that states the specific subtask for that recipient.
{% endif %}
- If a result says a subtask failed, is unavailable, cannot be computed, or had an internal error, do not repeat the same request to the same recipient. Continue any other independent requested subtasks that can still be completed, then answer with the complete or partial result available.
- If a recipient returns partial but actionable information, proceed with the next requested step using that information. Do not ask the same recipient again just to fill in optional missing metadata.
- When forwarding one agent's result to another agent, pass through the returned details verbatim. If optional details are missing, say they were not specified instead of stopping.
- A response with empty content and no tool call is invalid.
- Hidden reasoning is not visible to your caller and is not a final answer.
- After receiving all tool or agent results needed for your current subtask, your next response must answer your caller with non-empty visible content.
If `handoff_conversation` is included in multiple tool calls, it must be the final tool call in the response.
{% if handoff=="optional" %}
- Use `send_message` when you need an agent's result back, need to coordinate more than one agent, or need to decide another step after the agent replies.
- Use `handoff_conversation` only when a single recipient can continue the whole conversation directly with the caller and you do not need the result back.
{% endif %}
{% if handoff=="always" %}
- You must use the handoff_conversation tool when delegating to another agent.
{% endif %}
</tool_use_rules>

{% if _add_talk_to_user_tool | default(true) %}
Always structure your response as a thought followed by one or multiple tool calls using JSON compliant syntax.
The user can only see the content of the messages sent with `talk_to_user` and will not see any of your thoughts.
-> Put **internal-only** information in the thoughts
-> Put all necessary information in the tool calls to communicate to user/other entity.
-> When answering the user, use `talk_to_user` with a non-empty `text` parameter containing the complete final answer.
-> When forming a final answer from tool results, preserve the relevant details accurately.
{% else %}
Use tool calls only when you need to act. When all requested work is complete, answer your caller directly with non-empty visible text.
Hidden thoughts are not visible to your caller. When forming a final answer from tool results, preserve the relevant details accurately.
{% endif %}

{% if _add_talk_to_user_tool | default(true) %}
Do not use variables in the function call. Do not wrap tool calls in an outer object with keys like `thought`, `calls`, or `tools`.
Each tool call must be one JSON object with exactly `name` and `parameters` keys. Here's the structure:

YOUR THOUGHTS (WHAT ACTION YOU ARE GOING TO TAKE; NOT VISIBLE TO THE USER)

{"name": function name, "parameters": dictionary of argument name and its value}
{% else %}
When you need to call tools, do not use variables in the function call. Do not wrap tool calls in an outer object with keys like `thought`, `calls`, or `tools`.
Each tool call must be one JSON object with exactly `name` and `parameters` keys. Here's the structure:

OPTIONAL INTERNAL-ONLY THOUGHTS ABOUT THE TOOL ACTION

{"name": function name, "parameters": dictionary of argument name and its value}

When no tool call is needed, return only the visible answer text.
{% endif %}
</response_rules>

<tools>
Here is a list of functions that you can invoke.
{% for tool in __TOOLS__%}
{{tool | tojson}}{{ ",
" }}
{% endfor %}
</tools>

<tool_output_rules>
"""
    + _TOOL_OUTPUT_SYSTEM_RULE
    + """
</tool_output_rules>

{%- if custom_instruction -%}
<system_instructions>
Here are the instructions specific to your role:
{{custom_instruction}}
</system_instructions>{%- endif -%}
"""
).strip()


_DEFAULT_SWARM_SYSTEM_REMINDER = (
    """
--- SYSTEM REMINDER ---
You are a helpful AI Agent, your name: {{name}}. Your user/caller is: {{caller_name}}.

{% if _add_talk_to_user_tool | default(true) %}
The user can only see the content of the messages sent with `talk_to_user` and will not see any of your thoughts.

Always structure your response as a thought followed by one or multiple function calls using JSON compliant syntax.
{% else %}
Use function calls only when you need to act. When all requested work is complete, answer your caller directly with non-empty visible text.
{% endif %}
Valid recipient names are exactly: [{% for agent in other_agents %}`{{agent.name}}`{% if not loop.last %}, {% endif %}{% endfor %}].
For any `recipient` parameter, copy exactly one name from the valid recipient names. Do not invent, translate, pluralize, misspell, or alter recipient names.
{% if handoff!="always" %}
For independent subtasks handled by different agents, output one `send_message` tool request for each agent in the same response before waiting for results.
If the request has N independent subtasks handled by N different agents, output exactly N `send_message` tool requests in the same response; do not omit, combine, or defer any of those first requests.
For independent multi-agent requests, calling only the first subtask and waiting is incorrect; the first response after the request must include every independent `send_message` call.
Every `send_message` tool request must include a non-empty `message` parameter that states the specific subtask for that recipient.
{% endif %}
If a result says a subtask failed, is unavailable, cannot be computed, or had an internal error, do not repeat the same request to the same recipient. Continue any other independent requested subtasks that can still be completed, then answer with the complete or partial result available.
If a recipient returns partial but actionable information, proceed with the next requested step using that information. Do not ask the same recipient again just to fill in optional missing metadata.
When forwarding one agent's result to another agent, pass through the returned details verbatim. If optional details are missing, say they were not specified instead of stopping.
A response with empty content and no tool call is invalid.
Hidden reasoning is not visible to your caller and is not a final answer.
After receiving all tool or agent results needed for your current subtask, your next response must answer your caller with non-empty visible content.
{% if _add_talk_to_user_tool | default(true) %}
When answering the user, use `talk_to_user` with a non-empty `text` parameter containing the complete final answer.
{% else %}
When answering your caller, write a non-empty visible message directly.
{% endif %}
When forming a final answer from tool results, preserve the relevant details accurately.
{% if _add_talk_to_user_tool | default(true) %}
Do not use variables in the function call. Do not wrap tool calls in an outer object with keys like `thought`, `calls`, or `tools`.
Each tool call must be one JSON object with exactly `name` and `parameters` keys. Here's the structure:

YOUR THOUGHTS (WHAT ACTION YOU ARE GOING TO TAKE; NOT VISIBLE TO THE USER)

{"name": function name, "parameters": dictionary of argument name and its value}
{% else %}
When you need to call tools, do not use variables in the function call. Do not wrap tool calls in an outer object with keys like `thought`, `calls`, or `tools`.
Each tool call must be one JSON object with exactly `name` and `parameters` keys. Here's the structure:

OPTIONAL INTERNAL-ONLY THOUGHTS ABOUT THE TOOL ACTION

{"name": function name, "parameters": dictionary of argument name and its value}

When no tool call is needed, return only the visible answer text.
{% endif %}

"""
    + _TOOL_OUTPUT_SYSTEM_RULE
).strip()

_DEFAULT_SWARM_NATIVE_SYSTEM_PROMPT = """
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
- Use the provided tools through native tool calls when you need to act.
{% if handoff!="always" %}
- Use `send_message` to ask another entity in your group to do work.
{% if _add_talk_to_user_tool | default(true) %}
- Do not use `send_message` to reply to your caller; use `talk_to_user` for that.
{% else %}
- Do not use `send_message` to reply to your caller; answer your caller directly with visible text when your work is complete.
{% endif %}
{% endif %}
{% if handoff!="never" %}
- Use `handoff_conversation` to transfer the conversation when the handoff rules require or favor it.
{% endif %}
{% if _add_talk_to_user_tool | default(true) %}
- Use `talk_to_user` to answer your caller.
{% else %}
- Answer your caller directly with non-empty visible text when your work is complete.
{% endif %}
- Call at most one tool in each response.
- When a relevant tool is available for a requested operation, you must call the tool instead of handling the operation yourself.
- Never answer from memory or invented facts when a tool can retrieve, verify, compute, or change the requested information.
- A status or progress message is not a valid response when a tool call can make progress; call the tool instead.
- If you need information from a tool, call the tool now; do not tell the user you are checking or will check.
- Do not say you will use a tool unless the same response contains that native tool call.
- If the conversation has been handed off to you, never tell the user about transfer or routing; continue the original request.
- Do not write raw JSON tool calls in message text.
- Do not answer your caller until you have the information needed.
- If a result says a subtask failed, is unavailable, cannot be computed, or had an internal error, do not repeat the same request to the same recipient. Continue any other independent requested subtasks that can still be completed, then answer with the complete or partial result available.
- If a recipient returns partial but actionable information, proceed with the next requested step using that information. Do not ask the same recipient again just to fill in optional missing metadata.
- When forwarding one agent's result to another agent, pass through the returned details verbatim. If optional details are missing, say they were not specified instead of stopping.
- A response with empty content and no tool call is invalid.
- Hidden reasoning is not visible to your caller and is not a final answer.
- After receiving all tool or agent results needed for your current subtask, your next response must answer your caller with non-empty visible content.
- When all work is complete, answer with non-empty visible text containing the requested final result.
{% if _add_talk_to_user_tool | default(true) %}
- If `talk_to_user` is available, call it with a non-empty `text` value containing the final result; never return only hidden reasoning or an empty message.
{% else %}
- Do not call a final-answer tool unless one is explicitly available; return the final result as visible assistant text.
{% endif %}
{% if handoff=="optional" %}
- Use `send_message` when you need an agent's result back, need to coordinate more than one agent, or need to decide another step after the agent replies.
- Use `handoff_conversation` only when a single recipient can continue the whole conversation directly with the caller and you do not need the result back.
{% endif %}
{% if handoff=="always" %}
- You must use the handoff_conversation tool when delegating to another agent.
{% endif %}
</tool_use_rules>

{% if _add_talk_to_user_tool | default(true) %}
The user can only see the content of the messages sent with `talk_to_user`.
- Put all necessary information in tool calls when communicating to the user or another entity.
{% else %}
Your visible assistant text is sent to your caller.
- Put all necessary information in tool calls when communicating to another entity.
{% endif %}
</response_rules>

{%- if custom_instruction -%}
<system_instructions>
Here are the instructions specific to your role:
{{custom_instruction}}
</system_instructions>{%- endif -%}
""".strip()

_DEFAULT_SWARM_NATIVE_SYSTEM_REMINDER = """
--- SYSTEM REMINDER ---
You are a helpful AI Agent, your name: {{name}}. Your user/caller is: {{caller_name}}.

{% if _add_talk_to_user_tool | default(true) %}
The user can only see the content of the messages sent with `talk_to_user`.
{% else %}
Your visible assistant text is sent to your caller.
{% endif %}
Use the provided tools through native tool calls.
{% if handoff!="always" %}
Use `send_message` to ask another entity in your group to do work.
{% if _add_talk_to_user_tool | default(true) %}
Do not use `send_message` to reply to your caller; use `talk_to_user` for that.
{% else %}
Do not use `send_message` to reply to your caller; answer your caller directly with visible text when your work is complete.
{% endif %}
{% endif %}
{% if handoff!="never" %}
Use `handoff_conversation` to transfer the conversation when the handoff rules require or favor it.
{% endif %}
{% if _add_talk_to_user_tool | default(true) %}
Use `talk_to_user` to answer your caller.
{% else %}
Answer your caller directly with non-empty visible text when your work is complete.
{% endif %}
Call at most one tool in each response.
When a relevant tool is available for a requested operation, you must call the tool instead of handling the operation yourself.
Never answer from memory or invented facts when a tool can retrieve, verify, compute, or change the requested information.
A status or progress message is not a valid response when a tool call can make progress; call the tool instead.
If you need information from a tool, call the tool now; do not tell the user you are checking or will check.
Do not say you will use a tool unless the same response contains that native tool call.
If the conversation has been handed off to you, never tell the user about transfer or routing; continue the original request.
Do not write raw JSON tool calls in message text.
Do not answer your caller until you have the information needed.
If a result says a subtask failed, is unavailable, cannot be computed, or had an internal error, do not repeat the same request to the same recipient. Continue any other independent requested subtasks that can still be completed, then answer with the complete or partial result available.
If a recipient returns partial but actionable information, proceed with the next requested step using that information. Do not ask the same recipient again just to fill in optional missing metadata.
When forwarding one agent's result to another agent, pass through the returned details verbatim. If optional details are missing, say they were not specified instead of stopping.
A response with empty content and no tool call is invalid.
Hidden reasoning is not visible to your caller and is not a final answer.
After receiving all tool or agent results needed for your current subtask, your next response must answer your caller with non-empty visible content.
When all work is complete, answer with non-empty visible text containing the requested final result.
{% if _add_talk_to_user_tool | default(true) %}
If `talk_to_user` is available, call it with a non-empty `text` value containing the final result; never return only hidden reasoning or an empty message.
{% else %}
Do not call a final-answer tool unless one is explicitly available; return the final result as visible assistant text.
{% endif %}
{% if handoff=="optional" %}
Use `send_message` when you need an agent's result back, need to coordinate more than one agent, or need to decide another step after the agent replies.
Use `handoff_conversation` only when a single recipient can continue the whole conversation directly with the caller and you do not need the result back.
{% endif %}
{% if handoff=="always" %}
You must use the handoff_conversation tool when delegating to another agent.
{% endif %}
""".strip()


def _is_system_reminder(message: "Message") -> bool:
    return message.message_type == MessageType.SYSTEM and message.content.startswith(
        "--- SYSTEM REMINDER ---"
    )


_HANDOFF_CONFIRMATION_MESSAGE_TEMPLATE = """
The conversation was transferred from agent '{{sender_agent_name}}' to agent '{{new_agent_name}}'.
You are now responsible for continuing from the user's original request.
Do not tell the user that the conversation was transferred.
Do not reintroduce yourself.
""".strip()

_MAX_CHAR_TOOL_RESULT_HEADER = 140
"""Max number of characters in the message header when formatting a Tool Result"""


class _ToolRequestAndCallsTransform(MessageTransform):
    def __call__(self, messages: List["Message"]) -> List["Message"]:
        """
        Format Tool requests as Agent messages and Tool results as clearly-labelled
        tool-result User messages to have a simple User/Agent sequence of
        messages.
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
                            f"{format_tool_output_for_llm(message.tool_result.content)}"
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

                header = f"--- MESSAGE: From: {message.sender} ---\n"
                content = (
                    message.content  # sometimes the llm outputs this header automatically -> no need to add it.
                    if message.content.startswith(header)
                    else f"{header}{message.content}"
                )

                formatted_messages.append(
                    Message(
                        content=(
                            f"{content}\n{formatted_tool_calls}"
                            if formatted_tool_calls not in content
                            else f"{content}"
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
        if "{" not in raw_txt:
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

_DEFAULT_SWARM_NATIVE_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": _DEFAULT_SWARM_NATIVE_SYSTEM_PROMPT},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {"role": "system", "content": _DEFAULT_SWARM_NATIVE_SYSTEM_REMINDER},
    ],
    native_tool_calling=True,
    post_rendering_transforms=[
        CoalesceSystemMessagesTransform(),
        AppendTrailingSystemMessageToUserMessageTransform(),
    ],
)
