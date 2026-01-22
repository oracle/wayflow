# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
import ast
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from wayflowcore._utils.formatting import generate_tool_id, stringify
from wayflowcore.messagelist import Message
from wayflowcore.outputparser import ToolOutputParser
from wayflowcore.serialization.serializer import SerializableObject
from wayflowcore.templates.template import PromptTemplate
from wayflowcore.tools import ToolRequest, ToolResult
from wayflowcore.transforms import MessageTransform

####################################################
###########      MESSAGE TRANSFORM       ###########
####################################################


class Llama4PythonicTransform(MessageTransform, SerializableObject):
    """Simple message processor that joins tool requests and calls into a python-like message"""

    def __call__(self, messages: List["Message"]) -> List["Message"]:
        formatted_messages = []
        for msg in messages:
            if msg.tool_requests is not None:
                new_message = Message(
                    role="assistant",
                    content=Llama4PythonicTransform._tool_requests_to_call_str(msg.tool_requests),
                )
            elif msg.tool_result is not None:
                new_message = Message(
                    role="user",
                    content=Llama4PythonicTransform._tool_result_to_str(msg.tool_result),
                )
            else:
                new_message = msg
            formatted_messages.append(new_message)
        return formatted_messages

    @staticmethod
    def _format_value(v: Any) -> str:
        if v is None or isinstance(v, (bool, int, float, str)):
            return repr(v)
        if isinstance(v, (list, tuple)):
            inner = ", ".join(Llama4PythonicTransform._format_value(x) for x in v)
            return f"[{inner}]" if isinstance(v, list) else f"({inner}{',' if len(v) == 1 else ''})"
        if isinstance(v, dict):
            items = ", ".join(
                f"{repr(k)}: {Llama4PythonicTransform._format_value(vv)}"
                for k, vv in sorted(v.items(), key=lambda kv: str(kv[0]))
            )
            return "{" + items + "}"
        if isinstance(v, str):
            return repr(v)
        try:
            return json.dumps(v, sort_keys=True, ensure_ascii=False)
        except TypeError:
            return repr(v)

    @staticmethod
    def _tool_request_to_call_str(req: ToolRequest) -> str:
        # Deterministic order
        items = []
        for k in sorted(req.args.keys()):
            items.append(f"{k}={Llama4PythonicTransform._format_value(req.args[k])}")
        return f"{req.name}({', '.join(items)})"

    @staticmethod
    def _tool_requests_to_call_str(tool_requests: List[ToolRequest]) -> str:
        return (
            "["
            + ",".join(
                Llama4PythonicTransform._tool_request_to_call_str(tr) for tr in tool_requests
            )
            + "]"
        )

    @staticmethod
    def _tool_result_to_str(
        tool_result: ToolResult,
    ) -> str:
        return f"<tool_result>{stringify(tool_result)}</tool_result>"


####################################################
###########      TOOL OUTPUT PARSER      ###########
####################################################


@dataclass(frozen=True)
class ToolCall:
    name: str
    kwargs: Dict[str, Any]


_UNPARSE_ERRORS = (AttributeError, ValueError, TypeError)


class CallVisitor(ast.NodeVisitor):
    """
    Collects function call expressions.

    Design goals:
    - Never crash on weird AST shapes
    - Preserve python values where safe (ast.literal_eval), otherwise fall back to source strings
    - Keep explicit *args/**kwargs separate (they aren't normal positional/keyword args)
    """

    def __init__(
        self,
        *,
        allowed_names: Optional[Sequence[str]] = None,
    ) -> None:
        self.tool_calls: List[ToolCall] = []
        self.allowed_names = set(allowed_names) if allowed_names else None

    def _safe_value(self, expr: ast.AST) -> Any:
        """
        Return a real python value if it's a literal (numbers, strings, dict/list literals, etc.),
        otherwise return source code string.
        """
        try:
            return ast.literal_eval(expr)
        except (ValueError, SyntaxError, TypeError):
            try:
                return ast.unparse(expr)
            except _UNPARSE_ERRORS:
                return ast.dump(expr, include_attributes=False)

    def _call_name(self, func: ast.AST) -> str:
        """
        Best-effort fully qualified-ish name:
          - Name: foo
          - Attribute chain: pkg.mod.foo or obj.method
          - Other callables: <expr>
        """
        # Name: foo
        if isinstance(func, ast.Name):
            return func.id

        # Attribute: x.y (possibly chained)
        if isinstance(func, ast.Attribute):
            parts: List[str] = []
            cur: ast.AST = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value

            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                return ".".join(reversed(parts))

            # Something like (get_obj()).method -> can't name base cleanly
            try:
                base = ast.unparse(cur)
            except _UNPARSE_ERRORS:
                return "<attribute>"

            # parts currently holds attrs from outer->inner, reversed gives inner->outer.
            # For (get_obj()).method, parts would be ["method"] so this becomes "base.method".
            return f"{base}." + ".".join(reversed(parts))

        # Subscript call: fns[i](...)
        if isinstance(func, ast.Subscript):
            try:
                return ast.unparse(func)
            except _UNPARSE_ERRORS:
                return "<subscript>"

        # Lambda / Call / etc.
        try:
            return ast.unparse(func)
        except _UNPARSE_ERRORS:
            return "<expr>"

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)

        name = self._call_name(node.func)
        if self.allowed_names is not None and name not in self.allowed_names:
            return

        kwargs: Dict[str, Any] = {}
        starred_kwargs: List[str] = []

        for kw in node.keywords:
            if kw.arg is None:
                try:
                    starred_kwargs.append(ast.unparse(kw.value))
                except _UNPARSE_ERRORS:
                    try:
                        starred_kwargs.append(ast.dump(kw.value, include_attributes=False))
                    except TypeError:
                        starred_kwargs.append("<kwargs>")
            else:
                kwargs[kw.arg] = self._safe_value(kw.value)

        self.tool_calls.append(
            ToolCall(
                name=name,
                kwargs=kwargs,
            )
        )


class PythonToolOutputParser(ToolOutputParser):
    """Parses tool requests from Python function call syntax."""

    def parse_tool_request_from_str(self, raw_txt: str) -> List[ToolRequest]:
        """Parses tool calls of the format 'some_tool(arg1=...)'"""
        try:
            ast_tree = ast.parse(raw_txt)
            visitor = CallVisitor()
            visitor.visit(ast_tree)
            return [
                ToolRequest(
                    name=tool_call.name,
                    args=tool_call.kwargs,
                    tool_request_id=generate_tool_id(),
                )
                for tool_call in visitor.tool_calls
            ]

        except (SyntaxError, ValueError, TypeError, RecursionError) as e:
            logging.debug("Could not find any tool call in %s (%s)", raw_txt, str(e))
            return []


####################################################
###########           TEMPLATE           ###########
####################################################

PYTHON_CALL_CHAT_SYSTEM_TEMPLATE = """{%- if custom_instruction -%}{{custom_instruction}}{%- endif -%}

Here is a list of functions in JSON format that you can invoke. Use exact python format:
[func_name1(param1=value1, param2=value2), func_name2(...)]

Do not use variables. Do not output pure text, always output tool calls.

Available tools:

{%- for tool in __TOOLS__ %}
  {{- tool.function | tojson(indent=4) }}
  {{- "\n\n" }}
{%- endfor %}

You ONLY have access to those tools, calling any tool not mentioned above will result in a FAILURE.

Tool outputs will be put inside delimiters: <tool_result>...</tool_result> in user messages.
Never output an empty tool list, use `talk_to_user` or `submit_tool` (whichever is available) instead.
"""


LLAMA4_PYTHONIC_AGENT_TEMPLATE = PromptTemplate(
    messages=[
        Message(role="system", content=PYTHON_CALL_CHAT_SYSTEM_TEMPLATE),
        PromptTemplate.CHAT_HISTORY_PLACEHOLDER,
    ],
    native_tool_calling=False,  #  <-- important, so that we don't use the buggy tool calling support
    post_rendering_transforms=[
        Llama4PythonicTransform()
    ],  #  <-- we format ourselves the tool format
    output_parser=PythonToolOutputParser(),  #  <-- we parse ourselves the tool calls
)
"""Pythonic agent template that leverages llama4 pythonic syntax to write tool calls"""
