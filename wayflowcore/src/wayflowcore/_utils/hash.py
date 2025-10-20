# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import zlib
from typing import TYPE_CHECKING, Mapping, Sequence, Union

if TYPE_CHECKING:
    from wayflowcore.messagelist import MessageContent
    from wayflowcore.tools import ToolRequest, ToolResult

logger = logging.getLogger(__name__)

HashableContent = Union[
    str,
    int,
    float,
    bool,
    None,
    Sequence["HashableContent"],
    Mapping["HashableContent", "HashableContent"],
    "ToolRequest",
    "ToolResult",
    "MessageContent",
]


def _to_bytes(value: HashableContent) -> bytes:
    """Convert a supported value into a stable byte representation."""
    from wayflowcore.messagelist import ImageContent, MessageContent, TextContent
    from wayflowcore.tools import ToolRequest, ToolResult

    if value is None:
        return b"n:null"
    elif isinstance(value, ToolRequest):
        return _to_bytes([value.tool_request_id, value.name, value.args])  # type: ignore
    elif isinstance(value, ToolResult):
        return _to_bytes([value.tool_request_id, value.content])
    elif isinstance(value, MessageContent):
        if isinstance(value, TextContent):
            return _to_bytes([value.type, value.content])
        elif isinstance(value, ImageContent):
            return _to_bytes([value.type, value.base64_content])
        else:
            raise ValueError(
                f"Fast hash is not implemented for message content: {value.__class__.__name__}"
            )
    elif isinstance(value, str):
        return b"s:" + value.encode("utf-8")
    elif isinstance(value, bool):
        return b"b:1" if value else b"b:0"
    elif isinstance(value, int):
        return b"i:" + str(value).encode("utf-8")
    elif isinstance(value, float):
        # repr() is consistent across Python versions for floats
        return b"f:" + repr(value).encode("utf-8")
    elif isinstance(value, list):
        # join serialized elements with separator
        parts = [_to_bytes(v) for v in value]
        return b"l:[" + b"|".join(parts) + b"]"
    elif isinstance(value, dict):
        # ensure stable order by sorting keys by their serialized form
        items = []
        for k in sorted(value.keys(), key=lambda x: repr(x)):
            items.append(_to_bytes(k) + b"=>" + _to_bytes(value[k]))
        return b"d:{" + b"|".join(items) + b"}"
    else:
        logger.info(
            "Content of type %s cannot be hashed. Will use the class name only",
            value.__class__.__name__,
        )
        return repr(value).encode("utf-8")


def fast_stable_hash(value: HashableContent, digest_size: int = 8) -> str:
    """Hash a nested structure (str, int, float, bool, list, dict) into a fast, stable, non-cryptographic digest"""
    data = _to_bytes(value)
    crc = zlib.crc32(data)
    result_bytes = crc.to_bytes(4, "big")
    while len(result_bytes) < digest_size:
        crc = zlib.crc32(result_bytes, crc)
        result_bytes += crc.to_bytes(4, "big")
    return result_bytes[:digest_size].hex()
