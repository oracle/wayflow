# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import re
from collections import Counter
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, overload

import jinja2.exceptions
from jinja2 import DebugUndefined, Environment, StrictUndefined, Template, meta
from jinja2.nodes import For, Name, Node
from typing_extensions import NotRequired, TypedDict

from wayflowcore.messagelist import Message, MessageContent, MessageType, TextContent
from wayflowcore.property import AnyProperty, Property, StringProperty

_DEFAULT_VARIABLE_DESCRIPTION_TEMPLATE = '"{var_name}" input variable for the template'


class ToolRequestAsDictT(TypedDict, total=True):
    tool_request_id: str
    name: str
    args: Dict[str, Any]


class ToolResultAsDictT(TypedDict, total=True):
    tool_request_id: str
    content: Any


class MessageAsDictT(TypedDict, total=False):
    role: Literal["user", "assistant", "system"]
    content: str
    tool_requests: NotRequired[Optional[List[ToolRequestAsDictT]]]
    tool_result: NotRequired[Optional[ToolResultAsDictT]]


def check_template_validity(template: str) -> None:
    """Check whether the template is a valid jinja2 template"""
    Template(template)


def get_variable_names_from_object(
    object: Any, ignore_unknown: bool = True, allow_duplicates: bool = True
) -> List[str]:
    """Retrieve the used variable names from any python object.
    Recursively traverses dicts, lists, sets, tuples, etc. and collects all jinja template variables in found strings and byte sequences.

    Parameters
    ----------
    object : Any
        A potentially nested python object (str, bytes, dict, list, set, tuple)
    ignore_unknown : bool, optional
        If True, an unknown object (something that is not a str, bytes, dict, list, set, tuple) will return an empty list.
        If False, an exception is thrown.
        By default True
    allow_duplicates : bool, optional
        If True, duplicate template variables are okay.
        If False, an exception is thrown on duplicate variables.
        By default True

    Returns
    -------
    List[str]
        List of the extracted variable names.
        Note: this list is flattened and does not follow the structure of the inputted object

    Raises
    ------
    ValueError
        Thrown if there are duplicate variable names and `allow_duplicates` is False
        or if `ignore_unknown` is False and an invalid object is encountered
    """
    if isinstance(object, str):
        return get_variable_names_from_str_template(object)
    elif isinstance(object, bytes):
        return get_variable_names_from_object(object.decode("utf-8", errors="replace"))
    elif isinstance(object, dict):
        key_templates = get_variable_names_from_object(list(object.keys()), ignore_unknown)
        value_templates = get_variable_names_from_object(list(object.values()), ignore_unknown)
        return key_templates + value_templates
    elif isinstance(object, list) or isinstance(object, set) or isinstance(object, tuple):
        counted_keys = Counter(
            nested_item
            for item in object
            for nested_item in get_variable_names_from_object(item, ignore_unknown)
        )
        if not allow_duplicates:
            duplicates = [item for item, count in dict(counted_keys).items() if count > 1]
            if len(duplicates) > 0:
                raise ValueError(f"duplicate keys: {duplicates}")
        return list(counted_keys)
    else:
        # unknown object reached, ignore if configured, otherwise throw
        if ignore_unknown:
            return []
        else:
            raise ValueError(f"Cannot extract template variables from {object}")


def get_variable_names_from_str_template(jinja_template: str) -> List[str]:
    """Extracts the variable name from a jinja template."""
    # we skip pybandit alert because we don't want to escape the content
    ast = Environment().parse(jinja_template)  # nosec
    # extract all variable names using jinja2 function, in case our implementation
    # is missing some variables
    found_var_names_using_jinja2 = set(meta.find_undeclared_variables(ast))
    found_variables: List[str] = []

    def traverse(node: Node, targets: List[str]) -> None:
        if isinstance(node, Name):
            var_name = node.name
            if (
                var_name not in found_variables
                and var_name not in targets
                and var_name in found_var_names_using_jinja2
            ):
                found_variables.append(var_name)

        if isinstance(node, For) and isinstance(node.target, Name):
            # if for loop, mark the "for" target variable as existing already
            targets = targets + [node.target.name]

        # order is important because it needs to be in order of hwo it appears in the template
        for attr in [
            "name",
            "node",
            "nodes",
            "args",
            "kwargs",
            "test",
            "iter",
            "body",
            "target",
            "elif_",
            "else_",
            "expr",
            "ops",
        ]:
            next_node = getattr(node, attr, None)

            if isinstance(next_node, Node):
                traverse(next_node, targets=targets)
            elif isinstance(next_node, list):
                for sub_node in next_node:
                    if isinstance(sub_node, Node):
                        traverse(sub_node, targets=targets)

    traverse(ast, targets=[])

    # safety guard in case our custom code doesn't catch all variable names
    for var_name in found_var_names_using_jinja2:
        if var_name not in found_variables:
            found_variables.append(var_name)

    return found_variables


def _wrap_variable(var_name: str) -> str:
    return "{{" + var_name + "}}"


def get_non_str_variables_names_from_str_template(
    jinja_template: str, var_names: List[str]
) -> List[str]:
    # we can easily detect pure strings, these are just {{ var_name }}.
    # the formatting allows for having spaces, so we just remove all spaces from the template
    # and check for {{var_name}}
    jinja_template_without_spaces = jinja_template.replace(" ", "")
    non_str_var_names = [
        var_name
        for var_name in var_names
        if not _wrap_variable(var_name) in jinja_template_without_spaces
    ]
    return non_str_var_names


def get_optional_variable_names_from_str(jinja_template: str, var_names: List[str]) -> List[str]:
    optional_var_names: List[str] = []
    for var_name in var_names:
        patterns = [
            r"{% *if +(not +)*" + var_name + r" *%}",
            r"{% *if +" + var_name + r" +is +(not +)*none *%}",
        ]
        for pattern in patterns:
            if re.findall(pattern=pattern, string=jinja_template):
                optional_var_names.append(var_name)
                break
    return optional_var_names


def get_variables_names_and_types_from_str_template(
    jinja_template: str,
) -> List[Property]:

    all_found_var_names = get_variable_names_from_str_template(jinja_template)
    found_non_str_var_names = get_non_str_variables_names_from_str_template(
        jinja_template, all_found_var_names
    )
    found_optional_var_names = get_optional_variable_names_from_str(
        jinja_template, all_found_var_names
    )
    return [
        StringProperty(
            name=var_name,
            description=_DEFAULT_VARIABLE_DESCRIPTION_TEMPLATE.format(var_name=var_name),
            default_value="" if var_name in found_optional_var_names else Property.empty_default,
        )
        for var_name in all_found_var_names
        if var_name not in found_non_str_var_names
    ] + [
        AnyProperty(
            name=var_name,
            description=_DEFAULT_VARIABLE_DESCRIPTION_TEMPLATE.format(var_name=var_name),
            default_value=f"" if var_name in found_optional_var_names else Property.empty_default,
        )
        for var_name in found_non_str_var_names
        if var_name in all_found_var_names
    ]


def get_variables_names_and_types_from_template(
    template: Union[str, "Message", MessageAsDictT],
) -> List[Property]:
    from wayflowcore.messagelist import Message

    if isinstance(template, str):  # must be a jinja template
        return get_variables_names_and_types_from_str_template(template)
    elif isinstance(template, Message):
        return get_variables_names_and_types_from_str_template(template.content)
    elif isinstance(template, dict):
        return get_variables_names_and_types_from_str_template(template.get("content", ""))
    raise NotImplementedError(f"Template {template}, {type(template)} not supported.")


def render_str_template_partially(template: str, inputs: Dict[str, Any]) -> str:
    variable_names = get_variable_names_from_str_template(template)
    return Template(
        template,
        undefined=DebugUndefined,
    ).render(**{k: v for k, v in inputs.items() if k in variable_names})


@overload
def render_template_partially(template: str, inputs: Dict[str, Any]) -> str: ...


@overload
def render_template_partially(
    template: List[Tuple[str, str]],
    inputs: Dict[str, Any],
) -> List[Tuple[str, str]]: ...


def render_template_partially(
    template: Union[str, List[Tuple[str, str]]],
    inputs: Dict[str, Any],
) -> Union[str, List[Tuple[str, str]]]:
    """
    Renders a str template or a chat template (list of tuples) using the given inputs.
    The templates need to follow jinja2 formatting.
    Will ignore if some variables from the templates are missing from inputs.

    Parameters:
    -----------
    template: Union[str, List[Tuple[str, str]]]
        Template to render. Is either a simple string, or a list of tuples in the form:
        ```
        [
            ('system', system_message)
            ('user', user_message),
            ('agent', agent_message),
        ]
        ```
    **inputs: variable to render in template.
    """
    if isinstance(template, str):
        return render_str_template_partially(template, inputs)
    else:
        return [
            (message_type, render_str_template_partially(message_template, inputs))
            for message_type, message_template in template
        ]


def render_nested_object_template(
    object: Any, inputs: Dict[str, Any], ignore_unknown: bool = True, partial: bool = False
) -> Any:
    """Renders any found jinja template in the given input object which can be an arbitrarily nested
    structure of dicts, lists, sets and tuples.

    Parameters
    ----------
    object : Any
        A potentially nested python object (str, bytes, dict, list, set, tuple)
    inputs : Dict[str, Any]
        The inputs to the jinja templates
    ignore_unknown : bool, optional
        If True and an unsupported object is encountered, ignore it.
        Otherwise throw an exception
        by default True

    Returns
    -------
    Any
        An object of the same type as the input object with all found template variables
        replaced according to the given inputs.

    Raises
    ------
    ValueError
        If `ignore_unknown` is False and an unsupported object is encountered.
    """
    if isinstance(object, str):
        return render_str_template(object, inputs, partial)
    elif isinstance(object, bytes):
        return render_nested_object_template(
            object.decode("utf-8", errors="replace"), inputs, ignore_unknown
        )
    elif isinstance(object, dict):
        return {
            render_nested_object_template(k, inputs, ignore_unknown): render_nested_object_template(
                v, inputs, ignore_unknown
            )
            for k, v in object.items()
        }
    elif isinstance(object, list) or isinstance(object, set) or isinstance(object, tuple):
        return object.__class__(
            [render_nested_object_template(item, inputs, ignore_unknown) for item in object]
        )
    else:
        if ignore_unknown:
            return object
        else:
            raise ValueError(f"Cannot render template for {object}")


def render_str_template(template: str, inputs: Dict[str, Any], partial: bool = False) -> str:
    variable_names = get_variable_names_from_str_template(template)
    try:
        # we skip pybandit alert because we don't want to escape the content
        env = Environment(undefined=DebugUndefined if partial else StrictUndefined)  # nosec
        # don't sort the keys in dicts
        env.policies["json.dumps_kwargs"] = {"sort_keys": False}
        return env.from_string(source=template).render(
            **{k: v for k, v in inputs.items() if k in variable_names}
        )
    except jinja2.exceptions.UndefinedError as e:
        raise ValueError(f"The template is expecting a variable but it was not passed: {e}")


def render_message_template(message: "Message", inputs: Dict[str, Any], partial: bool) -> "Message":
    new_contents: List[MessageContent] = []
    text_contents = 0
    for content in message.contents:
        if isinstance(content, TextContent):
            new_contents.append(
                TextContent(render_str_template(message.content, inputs=inputs, partial=partial))
            )
            text_contents += 1
        else:
            # We don't want to copy other message types to not blow up memory
            new_contents.append(content)

    return message.copy(contents=new_contents)


def role_to_message_type(role: str, message_dict: Dict[str, Any]) -> "MessageType":
    from wayflowcore.messagelist import MessageType

    if role == "system":
        return MessageType.SYSTEM
    elif role == "user":
        return MessageType.USER
    elif role != "assistant":
        raise NotImplementedError(f"Role {role} not supported.")

    if message_dict.get("tool_requests") is not None:
        return MessageType.TOOL_REQUEST
    elif message_dict.get("tool_result") is not None:
        return MessageType.TOOL_RESULT
    else:
        return MessageType.AGENT


def render_message_dict_template(
    message_dict: MessageAsDictT, inputs: Dict[str, Any], partial: bool
) -> "Message":
    from wayflowcore.messagelist import Message

    message_dict_copy = {**message_dict}
    content = render_str_template(
        str(message_dict_copy.pop("content", "")), inputs=inputs, partial=partial
    )
    message_type = role_to_message_type(str(message_dict.pop("role")), message_dict_copy)
    return Message(message_type=message_type, content=content, **message_dict_copy)  # type: ignore


@overload
def render_template(template: str, inputs: Dict[str, Any], partial: bool = False) -> str: ...


@overload
def render_template(
    template: List["Message"], inputs: Dict[str, Any], partial: bool = False
) -> List["Message"]: ...


@overload
def render_template(
    template: List[MessageAsDictT], inputs: Dict[str, Any], partial: bool = False
) -> List["Message"]: ...


def render_template(
    template: Union[str, List[MessageAsDictT], List["Message"]],
    inputs: Dict[str, Any],
    partial: bool = False,
) -> Union[str, List["Message"]]:
    """
    Renders a str template or a chat template (list of tuples) using the given inputs.
    The templates need to follow jinja2 formatting.
    Will crash if some variables in the template are missing from inputs

    Parameters:
    -----------
    template: Union[str, List[Tuple[str, str]]]
        Template to render. Is either a simple string, or a list of tuples in the form:
        ```
        [
            ('system', system_message)
            ('user', user_message),
            ('agent', agent_message),
        ]
        ```
    **inputs: variables to render in template.
    """
    from wayflowcore.messagelist import Message

    if isinstance(template, str):
        return render_str_template(template, inputs, partial)
    elif not isinstance(template, List):
        raise NotImplementedError(
            f"Template should either be a str or a list, but was {template}, {type(template)}"
        )

    return [
        (
            render_message_template(message, inputs, partial)
            if isinstance(message, Message)
            else render_message_dict_template(message, inputs, partial)
        )
        for message in template
    ]
