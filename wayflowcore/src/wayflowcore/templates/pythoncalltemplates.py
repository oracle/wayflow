# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import TYPE_CHECKING, Any, List, Tuple

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.formatting import _format_chat_history_with_tool_results, stringify
from wayflowcore.outputparser import PythonToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates.template import PromptTemplate
from wayflowcore.tools import ToolRequest, ToolResult
from wayflowcore.transforms import (
    CanonicalizationMessageTransform,
    CoalesceSystemMessagesTransform,
    MessageTransform,
    RemoveEmptyNonUserMessageTransform,
)

if TYPE_CHECKING:
    from wayflowcore import Message


class _PythonMergeToolRequestAndCallsTransform(MessageTransform, SerializableObject):
    """Simple message processor that joins tool requests and calls into a python-like message"""

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        return _format_chat_history_with_tool_results(
            messages=messages,
            tool_request_renderer=self._render_tool_requests,
            tool_result_renderer=self._render_tool_results,
            consecutive_tool_messages_allowed=False,
        )

    @staticmethod
    def _convert_json_value_into_python_value(v: Any) -> str:
        if v in ["true", "false"]:
            return str(v.title())
        return repr(v)

    @staticmethod
    def _render_tool_requests(content: str, tool_requests: List[ToolRequest]) -> str:
        # Although content may be nonempty, this default template does not handle this case
        # because the default PythonToolOutputParser is unable to determine which part is plain text and which part is the tool_call string
        # Consider this raw output: Okay, I need to call this tool.\n\n[get_current_temperature(location="SF, CA")]
        # and note that the whitespace between the plain text part and the tool call part can be arbitrary
        # Basically, if interleaved tool calls and plain text is desired, the system instruction needs to be updated
        # to tell the model to generate a tool call marker, e.g. <tool_call></tool_call>
        # in which case parsing would be trivial
        tool_calls = []
        for tool_request in tool_requests:
            args_as_str = ",".join(
                [
                    f"{k}={_PythonMergeToolRequestAndCallsTransform._convert_json_value_into_python_value(v)}"
                    for k, v in tool_request.args.items()
                ]
            )
            tool_calls.append(f"{tool_request.name}({args_as_str})")
        return f"[{', '.join(tool_calls)}]"

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


PYTHON_CALL_CHAT_SYSTEM_TEMPLATE = """\
You are an expert in composing functions. You are given a question and a set of possible functions.
Based on the question, you will need to make one or more function/tool calls to achieve the purpose.
If none of the functions can be used, point it out. If the given question lacks the parameters required by the function, also point it out.
You should only return the function calls in your response.

If you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]
You SHOULD NOT include any other text in the response.

At each turn, you should try your best to complete the tasks requested by the user within the current turn. Continue to output functions to call until you have fulfilled the user's request to the best of your ability. Once you have no more functions to call, the system will consider the current turn complete and proceed to the next turn or task.

Here is a list of functions in JSON format that you can invoke.
[
{% for tool in __TOOLS__%}- {{tool.function | tojson}}{{ ",
" }}{% endfor %}]
"""

PYTHON_CALL_CHAT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": PYTHON_CALL_CHAT_SYSTEM_TEMPLATE},
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    native_tool_calling=False,
    post_rendering_transforms=[
        _PythonMergeToolRequestAndCallsTransform(),
        CoalesceSystemMessagesTransform(),
        RemoveEmptyNonUserMessageTransform(),
    ],
    output_parser=PythonToolOutputParser(),
)
"""Pythonic chat template that leverages python syntax to write tool calls"""

PYTHON_CALL_AGENT_TEMPLATE = PromptTemplate(
    messages=[
        {"role": "system", "content": PYTHON_CALL_CHAT_SYSTEM_TEMPLATE},
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
        _PythonMergeToolRequestAndCallsTransform(),
    ],
    output_parser=PythonToolOutputParser(),
)
"""Pythonic agent template that leverages python syntax to write tool calls"""


GEMMA_AGENT_TEMPLATE = PYTHON_CALL_AGENT_TEMPLATE.with_additional_post_rendering_transform(
    CanonicalizationMessageTransform()
)
"""Template for gemma models that do not support native tool calling"""
