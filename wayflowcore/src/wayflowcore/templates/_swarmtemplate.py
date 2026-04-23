# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Tuple

from wayflowcore.messagelist import Message, MessageType
from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.templates.agenticpatterntemplate import ToolRequestAndCallsTransform
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform,
    CoalesceSystemMessagesTransform,
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
- Calling MULTIPLE TOOLS at once is supported. Output multiple tool requests at once when the user’s query can be broken into INDEPENDENT subtasks.
If `handoff_conversation` is included in multiple tool calls, it must be the final tool call in the response.
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

Always structure your response as a thought followed by one or multiple function calls using JSON compliant syntax.
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
        ToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        AppendTrailingSystemMessageToUserMessageTransform(),
    ],
    output_parser=SwarmJsonToolOutputParser(),
)
