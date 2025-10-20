# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.


from typing import Any, ForwardRef, List, Literal, Sequence, Tuple, Union, get_args, get_origin


def is_any_type(tp: type) -> bool:
    return tp is Any  # type: ignore


def is_union_type(tp: type) -> bool:
    return get_origin(tp) is Union


def is_optional_type(tp: type) -> bool:
    origin = get_origin(tp)
    if origin is Union:
        return type(None) in get_args(tp)
    return False


def is_literal_type(tp: type) -> bool:
    return get_origin(tp) is Literal


def is_set_type(tp: type) -> bool:
    origin = get_origin(tp) or tp
    try:
        return issubclass(origin, set)
    except TypeError:
        return False


def is_tuple_type(tp: type) -> bool:
    origin = get_origin(tp) or tp
    try:
        return issubclass(origin, tuple) and origin not in [str, bytes]
    except TypeError:
        return False


def is_list_type(tp: type) -> bool:
    origin = get_origin(tp) or tp
    try:
        return issubclass(origin, (list, Sequence)) and origin not in [str, bytes]
    except TypeError:
        return False


def is_dict_type(tp: type) -> bool:
    origin = get_origin(tp) or tp
    try:
        return issubclass(origin, dict)
    except TypeError:
        return False


def get_union_types(tp: Any) -> List[type]:
    return list(get_args(tp))


def get_set_inner_type(tp: type) -> type:
    origin = get_origin(tp) or tp
    if origin is set or origin.__name__ == "set":
        args = get_args(tp)
        return args[0] if args else None  # type: ignore
    return None  # type: ignore


def get_tuple_inner_types(tp: type) -> List[type]:
    origin = get_origin(tp) or tp
    if origin is tuple or origin.__name__ == "tuple":
        args = get_args(tp)
        return args  # type: ignore
    return None  # type: ignore


def get_list_inner_type(tp: type) -> type:
    origin = get_origin(tp)
    if origin in (list, tuple) or (origin is not None and issubclass(origin, Sequence)):
        args = get_args(tp)
        if origin is tuple and len(args) > 1 and args[1] is Ellipsis:
            return args[0]  # type: ignore
        if origin is tuple and len(args) > 1:
            return args  # type: ignore
        return args[0] if args else None  # type: ignore
    return None  # type: ignore


def get_dict_inner_types(tp: type) -> Tuple[type, type]:
    origin = get_origin(tp) or tp
    if origin is dict or origin.__name__ == "dict":
        args = get_args(tp)
        return args if args else (None, None)
    return None, None  # type: ignore


def get_optional_inner_type(optional_type: type) -> type:
    origin = get_origin(optional_type)
    if origin is not Union:
        raise TypeError(f"{optional_type} is not an Optional/Union type.")

    args = get_args(optional_type)
    non_none_types = [arg for arg in args if arg is not type(None)]  # filter out NoneType

    if len(non_none_types) != 1:
        raise TypeError(f"{optional_type} is not a standard Optional[T] type.")

    return non_none_types[0]  # type: ignore


def respects_literal(obj: Any, literal_type: type) -> bool:
    if get_origin(literal_type) is not Literal:
        return False
    allowed_values = get_args(literal_type)
    return obj in allowed_values


def extract_forward_type_arg(tp: type) -> Union[str, type]:
    if isinstance(tp, ForwardRef):
        return tp.__forward_arg__
    return tp
