# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import json
from typing import TYPE_CHECKING, List, Tuple

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.formatting import _format_chat_history_with_tool_results, stringify
from wayflowcore.outputparser import JsonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates.template import PromptTemplate
from wayflowcore.tools import ToolRequest, ToolResult
from wayflowcore.transforms import (
    CoalesceSystemMessagesTransform,
    MessageTransform,
    RemoveEmptyNonUserMessageTransform,
)

if TYPE_CHECKING:
    from wayflowcore import Message


class _LlamaMergeToolRequestAndCallsTransform(MessageTransform, SerializableObject):
    def __call__(self, messages: List["Message"]) -> List["Message"]:
        return _format_chat_history_with_tool_results(
            messages=messages,
            tool_request_renderer=self._render_tool_requests,
            tool_result_renderer=self._render_tool_results,
            consecutive_tool_messages_allowed=False,
        )

    @staticmethod
    def _render_tool_requests(content: str, tool_requests: List[ToolRequest]) -> str:
        # see comments in _PythonMergeToolRequestAndCallsTransform._render_tool_requests
        tool_calls = []
        for tool_request in tool_requests:
            tool_calls.append(
                json.dumps({"name": tool_request.name, "parameters": tool_request.args})
            )
        if len(tool_calls) > 1:
            return f"[{', '.join(tool_calls)}]"
        else:
            return tool_calls[0]

    @staticmethod
    def _render_tool_results(
        tool_request_and_results: List[Tuple[ToolRequest, ToolResult]],
    ) -> List[str]:
        return [
            render_template(
                "<tool_response>{{tool_result}}</tool_response>",
                inputs=dict(
                    tool_result=f'"{content}"' if isinstance(content, str) else content,
                ),
            )
            for tool_request, tool_result in tool_request_and_results
            if (content := stringify(tool_result.content)) is not None
        ]


LLAMA_SYSTEM_TEMPLATE = """\
{%- if __TOOLS__ -%}
Environment: ipython
Cutting Knowledge Date: December 2023

You are a helpful assistant with tool calling capabilities. Only reply with a tool call if the function exists in the library provided by the user. If it doesn't exist, just reply directly in natural language. When you receive a tool call response, use the output to format an answer to the original user question.

You have access to the following functions. To call a function, please respond with JSON for a function call.
Respond in the format {"name": function name, "parameters": dictionary of argument name and its value}.
Do not use variables.

{% for tool in __TOOLS__%}- {{tool["function"] | tojson}}{{ "
" }}{% endfor %}
{%- endif -%}
"""


LLAMA_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": LLAMA_SYSTEM_TEMPLATE},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        _LlamaMergeToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        RemoveEmptyNonUserMessageTransform(),
    ],
    output_parser=JsonToolOutputParser(),
)
"""Chat template for legacy llama models"""

LLAMA_AGENT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": LLAMA_SYSTEM_TEMPLATE},
        {
            "role": "system",
            "content": "{%- if custom_instruction -%}Additional instructions:\n{{custom_instruction}}{%- endif -%}",
        },
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
        _LlamaMergeToolRequestAndCallsTransform(),
    ],
    output_parser=JsonToolOutputParser(),
)
"""Agent template for legacy llama models"""
