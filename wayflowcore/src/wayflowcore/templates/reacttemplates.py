# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
import re
from typing import TYPE_CHECKING, List, Tuple

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.formatting import parse_tool_call_using_json, stringify
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.outputparser import ToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates.template import PromptTemplate
from wayflowcore.tools import ToolRequest
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform,
    MessageTransform,
    RemoveEmptyNonUserMessageTransform,
)

if TYPE_CHECKING:
    from wayflowcore import Message


class _ReactMergeToolRequestAndCallsTransform(MessageTransform, SerializableObject):
    """Simple message processor that joins tool requests and calls into a python-like message"""

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        from wayflowcore import Message, MessageType

        tool_result_map = {
            message.tool_result.tool_request_id: message.tool_result
            for message in messages
            if message.tool_result is not None
        }

        formatted_messages = []
        for message in messages:
            if message.message_type == MessageType.TOOL_RESULT:
                # we link results to requests
                continue
            elif message.message_type != MessageType.TOOL_REQUEST:
                formatted_messages.append(message)
                continue

            actions = "\n".join(
                [self._render_tool_request(tr) for tr in message.tool_requests or []]
            )
            observations = "\n".join(
                [
                    stringify(tool_result_map[tr.tool_request_id].content)
                    for tr in message.tool_requests or []
                ]
            )

            formatted_messages.append(
                Message(
                    content=render_template(
                        """{%- if thoughts %}Thoughts: {{thoughts}}{% endif %}\nAction:\n```json\n{{actions}}\n```""",
                        inputs=dict(
                            thoughts=message.content,
                            actions=actions,
                            observations=observations,
                        ),
                    ),
                    message_type=MessageType.AGENT,
                )
            )
            formatted_messages.append(
                Message(
                    content=render_template(
                        """Observation: {{observations}}""",
                        inputs=dict(observations=observations),
                    ),
                    message_type=MessageType.USER,
                )
            )
        return formatted_messages

    @staticmethod
    def _render_tool_request(tool_request: ToolRequest) -> str:
        return json.dumps(
            obj={
                "name": tool_request.name,
                "parameters": tool_request.args,
            },
            indent=4,
        )


class ReactToolOutputParser(ToolOutputParser, SerializableObject):
    def parse_tool_request_from_str(self, raw_txt: str) -> List[ToolRequest]:
        """Parses tool calls of the format 'some_tool(arg1=...)'"""
        return parse_tool_call_using_json(raw_txt, parameter_key="parameters")

    def parse_thoughts_and_calls(self, raw_txt: str) -> Tuple[str, str]:
        splits = raw_txt.split("## Action:")
        thoughts = ""
        if len(splits) == 2:
            thoughts, raw_txt = splits
            thoughts = thoughts.lstrip("## Thought:")
        if "## Observation:" in raw_txt:
            raw_txt = raw_txt.split("## Observation:")[0]
        parsed_raw_txt = re.findall(r"```(?:json)?(.*?)```", raw_txt, flags=re.DOTALL)
        if parsed_raw_txt is not None and len(parsed_raw_txt) > 0:
            raw_txt = parsed_raw_txt[0]
        return thoughts, raw_txt


REACT_SYSTEM_TEMPLATE = """\
{%- if __TOOLS__ -%}
Focus your actions on solving the user request. \
Be proactive, act on obvious actions and suggest options when the user hasn't specified anything yet. \
You can either answer with some text, or a tool call format containing 3 sections: Thought, Action and Observation. Here is the format:

## Thought: explain what you plan to do and why
## Action:
```json
{
    "name": $TOOL_NAME,
    "parameters": $INPUTS
}
```
## Observation: the output of the action

The first thought section describes the step by step reasoning about what you should do and why.
The second action section contains a well formatted json describing which tool to call and with what arguments. $INPUTS is a dictionary containing the function arguments.
The third observation section contains the result of the tool. This is not visible by the user, so you might need to repeat its content to the user.


If tool calls appear in the chat, they are formatted with the above template. They are part of the conversation. Here is an example:

User: What is the weather in Zurich today?
Agent: ## Thought: we need to call a tool to get the current weather
## Action:
```json
{
    "name": "get_weather",
    "parameters": {
        "location": "Zurich"
    }
}
```
User: ## Observation: sunny
Agent: The weather is sunny today in Zurich!
...

Here is a list of functions in JSON format that you can invoke.
[
{% for tool in __TOOLS__%}- {{tool.function | tojson}}{{ ",
" }}{% endfor %}]
{%- endif -%}
"""

REACT_REMINDER = """{%- if __TOOLS__ -%}
Reminder: always answer the user request with plain text or specify a tool call using the format above. Only use tools when necessary.
Remember that a tool call with thought, action and observation is NOT VISIBLE by the user, so if it contains information that the user needs to \
know, then make sure to repeat the information as a message.
{%- endif -%}"""


REACT_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": REACT_SYSTEM_TEMPLATE},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        _ReactMergeToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        RemoveEmptyNonUserMessageTransform(),
    ],
    output_parser=ReactToolOutputParser(),
    generation_config=LlmGenerationConfig(stop=["## Observation"]),
)


REACT_AGENT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": REACT_SYSTEM_TEMPLATE},
        {
            "role": "system",
            "content": "{%- if custom_instruction -%}Additional instructions:\n{{custom_instruction}}{%- endif -%}",
        },
        {"role": "system", "content": REACT_REMINDER},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
        {
            "role": "system",
            "content": "{% if __PLAN__ %}The current plan you should follow is the following: \n{{__PLAN__}}{% endif %}",
        },
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        RemoveEmptyNonUserMessageTransform(),
        CoalesceSystemMessagesTransform(),
        _ReactMergeToolRequestAndCallsTransform(),
    ],
    output_parser=ReactToolOutputParser(),
    generation_config=LlmGenerationConfig(stop=["## Observation"]),
)
