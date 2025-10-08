# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import ast
import json
import logging
import uuid
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple

from json_repair import json_repair

from wayflowcore.property import JsonSchemaParam
from wayflowcore.tools import Tool, ToolRequest, ToolResult

if TYPE_CHECKING:
    from wayflowcore import Message, MessageType
    from wayflowcore._utils._templating_helpers import MessageAsDictT


logger = logging.getLogger(__name__)


def _strtobool(v: str) -> bool:
    # we used to use that function from distutils, but distutils
    # are not installed by default in python 3.12+
    v = v.lower()

    true_set = {"y", "yes", "on", "1", "true", "t"}
    if v in true_set:
        return True
    false_set = {"n", "no", "off", "0", "false", "f"}
    if v in false_set:
        return False

    # Error case
    all_values_set = true_set.union(false_set)
    raise ValueError('Expected "%s"' % '", "'.join(all_values_set))


def correct_type(value: Any, json_schema: JsonSchemaParam, catch_exception: bool = True) -> Any:
    if "default" in json_schema and json_schema["default"] is None and value is None:
        return value

    expected_type = json_schema.get("type", None)
    if expected_type is None:
        if "anyOf" in json_schema:
            types_to_try = json_schema["anyOf"]
            types_to_try = sorted(types_to_try, key=lambda x: x.get("type", ""))
            possible_values = []
            while len(types_to_try) > 0:
                type_to_try = types_to_try.pop(0)
                try:
                    possible_values.append(correct_type(value, type_to_try, catch_exception=False))
                except Exception as e:
                    logger.debug(f"Error while trying to convert value into proper type: {e}")
            if len(possible_values) == 0:
                logger.debug(
                    f"The value `{value}` could not be converted to any of the expected types: {expected_type}"
                )
                return value
            elif value in possible_values and type(
                possible_values[possible_values.index(value)]
            ) == type(value):
                # value had one of the expected types
                return value
            else:
                return possible_values[0]
        else:
            expected_type = "object"
    try:
        if expected_type == "string":
            return str(value)
        elif expected_type == "integer":
            return int(value)
        elif expected_type == "boolean":
            if isinstance(value, str):
                return bool(_strtobool(value))
            else:
                return bool(value)
        elif expected_type == "number":
            return float(value)
        elif expected_type == "array":
            if isinstance(value, str):
                value = json_repair.loads(value)
            return [correct_type(item, json_schema["items"]) for item in value]
        elif expected_type == "object" and (
            "additionalProperties" in json_schema or "properties" in json_schema
        ):
            if isinstance(value, str):
                value = json_repair.loads(value)

            result = {}
            for key, value in value.items():
                if "additionalProperties" in json_schema:
                    schema_param = json_schema["additionalProperties"]
                else:
                    schema_param = json_schema["properties"][key]
                result[key] = correct_type(value, schema_param)
            return result

        else:
            raise RuntimeError(
                f"Unsupported type {expected_type} for JSON schema {json_schema} when decoding "
                f"{value}"
            )
    except Exception as e:
        if not catch_exception:
            raise e
        logger.debug(f"Error while trying to convert value into proper type: {e}")
    return value


def correct_arguments(
    args: Dict[str, Any], expected_types: Dict[str, JsonSchemaParam]
) -> Dict[str, Any]:
    corrected_types = {}
    for arg_name, arg_value in args.items():
        if arg_name not in expected_types:
            # model hallucinated a tool argument
            continue
        casted_value = correct_type(arg_value, expected_types[arg_name])
        if casted_value != arg_value:
            logger.debug(
                "The argument `%s` did not have the proper type `%s`. It was converted from `%s` (%s) to `%s` (%s) (according to the schema: %s)",
                arg_name,
                expected_types[arg_name].get("type", "object"),
                arg_value,
                type(arg_value),
                casted_value,
                type(casted_value),
                expected_types[arg_name],
            )
        corrected_types[arg_name] = casted_value
    required_args = [key for key, param in expected_types.items() if "default" not in param]

    if not all(req_arg_name in corrected_types for req_arg_name in required_args):
        logger.warning(
            "Tool request missing some arguments with no default value: %s",
            {req_arg_name: req_arg_name not in corrected_types for req_arg_name in required_args},
        )

    return corrected_types


def _remove_optional_from_signature(
    param: JsonSchemaParam, _deepcopy: bool = True
) -> JsonSchemaParam:
    """
    This functions transforms the var: Optional[X] into var: X = None to respect the behavior that
    Langchain was using, which improves performance on weaker models like Llama.
    """
    if not isinstance(param, dict):
        return param
    if _deepcopy:
        param = deepcopy(param)
    if (
        "anyOf" in param
        and len(param["anyOf"]) == 2
        and any(s == {"type": "null"} for s in param["anyOf"])
    ):
        param.update(next(s for s in param.pop("anyOf") if s != {"type": "null"}))
    for k, v in param.items():
        if k == "items":
            _remove_optional_from_signature(v, False)  # type: ignore
        elif k == "additionalProperties":
            _remove_optional_from_signature(v, False)  # type: ignore
        elif k == "properties" and isinstance(v, dict):
            for _, t in v.items():
                _remove_optional_from_signature(t, False)
    return param


def _to_openai_function_dict(tool: Tool) -> Dict[str, Any]:
    """Function calling as defined in: https://platform.openai.com/docs/guides/function-calling"""
    openai_function_dict: Dict[str, Any] = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
        },
    }
    if any(tool.parameters):
        openai_function_dict["function"]["parameters"] = {
            "type": "object",
            "properties": {
                t_name: _remove_optional_from_signature(t) for t_name, t in tool.parameters.items()
            },
            "required": [
                param_name
                for param_name, param_info in tool.parameters.items()
                if "default" not in param_info
            ],
        }
    else:
        openai_function_dict["function"]["parameters"] = {}
    return openai_function_dict


def stringify(x: Any) -> str:
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x)
    except:
        logger.warning("Result is not jsonable. Converting it to string with `str()`")
        return str(x)


def _tool_to_simple_function_dict(tool: Tool) -> Dict[str, Any]:
    function_dict: Dict[str, Any] = {
        "name": tool.name,
        "description": tool.description,
        "parameters": {},
    }
    for property_ in tool.input_descriptors:
        property_type_str = property_.get_python_type_str()
        default_str = (
            f" (default={property_.default_value!r}) " if property_.has_default else " (required) "
        )
        function_dict["parameters"][
            property_.name
        ] = f"{property_type_str}{default_str}: {property_.description}"
    return function_dict


def stringify_if_not_jsonable(x: Any) -> Any:
    try:
        json.dumps(x)
        return x
    except:
        logger.warning("Result is not jsonable. Converting it to string with `str()`")
        return str(x)


def _format_chat_history_with_tool_results(
    messages: List["Message"],
    tool_request_renderer: Callable[[str, List[ToolRequest]], str],
    tool_result_renderer: Callable[[List[Tuple[ToolRequest, ToolResult]]], List[str]],
    consecutive_tool_messages_allowed: bool = False,
    tool_role_allowed: bool = False,
) -> List["Message"]:
    """
    Given a list of messages with tool requests and tool results,
    create a new list such that each tool request is paired with its tool result.

    tool_request_renderer:
        the first input is the content of the original message,
        the second input is the list of tool calls extracted from the message
    tool_result_renderer:
        the input is a list of tuples (tool_request, corresponding_tool_result)
    consecutive_tool_messages_allowed:
        whether the LLM allows multiple tool result messages in a role.
        This should be False if the LLM requires alternating user/assistant/user... messages
        If this is False, all tool outputs will be collapsed into a single message
    tool_role_allowed:
        whether the LLM accepts the "tool" role: system, user, assistant, tool
        If False, will use the "user" role to store tool outputs
    """
    from wayflowcore import Message, MessageType

    formatted_messages = []
    for message_idx, m in enumerate(messages):
        if m.tool_result is not None:
            # Here we ignore the TOOL_RESULT message because they are being merged with their
            # respective TOOL_REQUEST messages using the tool_call_id
            pass
        elif m.tool_requests is not None:

            tool_request_to_tool_result_mapping: List[Tuple[ToolRequest, ToolResult]] = []
            for tool_request in m.tool_requests:
                potential_tool_result_messages = [  # find the corresponding tool result
                    m
                    for m in messages[message_idx + 1 :]
                    if m.message_type is MessageType.TOOL_RESULT
                    and (m.tool_result is not None)
                    and (m.tool_result.tool_request_id == tool_request.tool_request_id)
                ]
                if len(potential_tool_result_messages) != 1:
                    raise ValueError(
                        f"Found no / too many associated tool calls: {potential_tool_result_messages}"
                        f" for tool_call {tool_request.tool_request_id}. List of messages is: {messages}"
                    )

                tool_result_message = potential_tool_result_messages[0]
                if tool_result_message.tool_result is None:
                    raise ValueError(f"Expected a tool_result to be present, but was None")

                tool_request_to_tool_result_mapping.append(
                    (tool_request, tool_result_message.tool_result)
                )

            formatted_messages.append(
                Message(
                    content=tool_request_renderer(m.content, m.tool_requests),
                    message_type=MessageType.AGENT,
                )
            )
            formatted_tool_messages = tool_result_renderer(tool_request_to_tool_result_mapping)
            tool_result_role = MessageType.TOOL_RESULT if tool_role_allowed else MessageType.USER
            # format tool results in one or more "user" messages (since this is not "native function calling" otherwise we use the "tool" role)
            if consecutive_tool_messages_allowed:
                formatted_messages.extend(
                    [
                        Message(
                            content=m if not tool_role_allowed else "",
                            message_type=tool_result_role,
                            tool_result=(
                                ToolResult(content=m, tool_request_id="")
                                if tool_role_allowed
                                else None
                            ),
                        )
                        for m in formatted_tool_messages
                    ]
                )
            else:
                combined_tool_result = "\n".join(formatted_tool_messages)
                tool_result = ToolResult(content=combined_tool_result, tool_request_id="")
                formatted_messages.append(
                    Message(
                        content=combined_tool_result if not tool_role_allowed else "",
                        message_type=tool_result_role,
                        tool_result=tool_result if tool_role_allowed else None,
                    )
                )
        else:
            formatted_messages.append(m)
    return formatted_messages


def generate_tool_id() -> str:
    return str(uuid.uuid4())


# AST visitor class to parse tool calls
class CallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.tool_calls: List[Tuple[str, Dict[str, Any]]] = []

    def visit_Call(self, node: ast.Call) -> None:
        arg_dict = {}

        # first parse children to enqueue recursive tool calls first
        self.generic_visit(node)

        # positional arguments
        for i, arg in enumerate(node.args):
            if isinstance(arg, ast.AST):
                key = f"arg{i}"
                arg_dict[key] = ast.unparse(arg)

        # keyword arguments
        for kw in node.keywords:
            if isinstance(kw, ast.keyword):
                key = kw.arg if kw.arg else "**"
                arg_dict[key] = (
                    kw.value.value if isinstance(kw.value, ast.Constant) else ast.unparse(kw.value)
                )

        if isinstance(node.func, ast.Attribute):
            name = f"{getattr(node.func.value, 'id')}.{node.func.attr}"
        else:
            name = getattr(node.func, "id")

        self.tool_calls.append((name, arg_dict))


def parse_tool_call_using_ast(raw_txt: str) -> List[ToolRequest]:
    try:
        ast_tree = ast.parse(raw_txt)
        visitor = CallVisitor()
        visitor.visit(ast_tree)
        return [
            ToolRequest(
                name=name,
                args=args,
                tool_request_id=generate_tool_id(),
            )
            for name, args in visitor.tool_calls
        ]
    except Exception as e:
        logger.debug("Could not find any tool call in %s (%s)", raw_txt, str(e))
        return []


def parse_tool_call_using_json(
    raw_txt: str, parameter_key: str = "parameters"
) -> List[ToolRequest]:
    parsed_results = json_repair.loads(raw_txt)

    if isinstance(parsed_results, dict):
        parsed_results = [parsed_results]
    elif not isinstance(parsed_results, list):
        logger.debug("No tool found in: %s", raw_txt)
        return []

    valid_tool_calls = []
    for tool_call in parsed_results:
        if (
            isinstance(tool_call, dict)
            and all(key in tool_call for key in ["name", parameter_key])
            and isinstance(tool_call[parameter_key], dict)
        ):
            valid_tool_calls.append(
                ToolRequest(
                    name=tool_call["name"],
                    args=tool_call[parameter_key],
                    tool_request_id=generate_tool_id(),
                )
            )
        elif isinstance(tool_call, dict) and "name" in tool_call:
            # it was a dict with name key, but not properly formatted
            logger.warning("Couldn't parse tool request: %s", tool_call)
    return valid_tool_calls


def render_message_dict_template(message_dict: "MessageAsDictT") -> "Message":
    from wayflowcore.messagelist import Message

    message_dict_copy = {**message_dict}
    message_type = role_to_message_type(str(message_dict_copy.pop("role")), message_dict_copy)
    tool_requests_content = message_dict_copy.pop("tool_requests", None)
    tool_result_content = message_dict_copy.pop("tool_result", None)
    return Message(
        message_type=message_type,
        tool_requests=(
            [ToolRequest(**tool_dict) for tool_dict in tool_requests_content]  # type: ignore
            if tool_requests_content is not None
            else None
        ),
        tool_result=ToolResult(**tool_result_content) if tool_result_content is not None else None,  # type: ignore
        **message_dict_copy,  # type: ignore
    )


def role_to_message_type(role: str, message_dict: Dict[str, Any]) -> "MessageType":
    from wayflowcore.messagelist import MessageType

    if role == "system":
        return MessageType.SYSTEM
    elif role == "user":
        if message_dict.get("tool_result") is not None:
            return MessageType.TOOL_RESULT
        else:
            return MessageType.USER
    elif role == "assistant":
        if message_dict.get("tool_requests") is not None:
            return MessageType.TOOL_REQUEST
        else:
            return MessageType.AGENT
    else:
        raise NotImplementedError(
            f"Role {role} not supported. Provided message_dict was {message_dict}"
        )
