# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Tuple

from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates import PromptTemplate
from wayflowcore.transforms import (
    AppendTrailingSystemMessageToUserMessageTransform,
    CoalesceSystemMessagesTransform,
)

_DEFAULT_MANAGERWORKERS_SYSTEM_PROMPT = """
You are an helpful AI Agent.
- name: {{name}}
- description: {{description}}

<environment>
You are part of a group of Agents.
You can use tools to interact with other agents in your group.

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
- Do not mention any specific tool names to users
- Carefully verify available tools; do not fabricate non-existent tools. Delegate when necessary.
- Call MULTIPLE TOOLS at once is supported. Output multiple tool requests at once when the user’s query can be broken into INDEPENDENT subtasks.
</tool_use_rules>

Always structure your response as as a thought followed by one or multiple tool calls using JSON compliant syntax.
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
Here are the instructions specific to your role.:
{{custom_instruction}}
</system_instructions>{%- endif -%}
""".strip()

_DEFAULT_MANAGERWORKERS_SYSTEM_REMINDER = """
--- SYSTEM REMINDER ---
You are an helpful AI Agent, your name: {{name}}. Your user/caller is: {{caller_name}}.

The user can only see the content of the messages sent with `talk_to_user` and will not see any of your thoughts.

Always structure your response as a thought followed by one or multiple tool calls using JSON compliant syntax.
Do not use variables in the function call. Here's the structure:

YOUR THOUGHTS (WHAT ACTION YOU ARE GOING TO TAKE; NOT VISIBLE TO THE USER)

{"name": function name, "parameters": dictionary of argument name and its value}
""".strip()

_MAX_CHAR_TOOL_RESULT_HEADER = 140
"""Max number of characters in the message header when formatting a Tool Result"""


class ManagerWorkersJsonToolOutputParser(JsonToolOutputParser, SerializableObject):
    def parse_thoughts_and_calls(self, raw_txt: str) -> Tuple[str, str]:
        """Mananagerworkers-specific function to separate thoughts and tool calls."""
        if "{" not in raw_txt:
            return "", raw_txt
        thoughts, raw_tool_calls = raw_txt.split("{", maxsplit=1)
        return thoughts.strip(), "{" + raw_tool_calls.replace("args={", "parameters={")


_DEFAULT_MANAGERWORKERS_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": _DEFAULT_MANAGERWORKERS_SYSTEM_PROMPT},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {"role": "system", "content": _DEFAULT_MANAGERWORKERS_SYSTEM_REMINDER},
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        CoalesceSystemMessagesTransform(),
        AppendTrailingSystemMessageToUserMessageTransform(),
    ],
    output_parser=ManagerWorkersJsonToolOutputParser(),
)
