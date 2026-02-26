# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from __future__ import annotations

from wayflowcore.messagelist import TextContent, TextTokenLogProb, TextTokenTopLogProb
from wayflowcore.serialization.context import DeserializationContext, SerializationContext
from wayflowcore.serialization.serializer import autodeserialize_any_from_dict, serialize_to_dict


def test_textcontent_logprobs_roundtrip_serialization() -> None:
    content = TextContent(
        content="Hello",
        logprobs=[
            TextTokenLogProb(
                token="Hello",
                logprob=-0.01,
                top_logprobs=[
                    TextTokenTopLogProb(token="Hello", logprob=-0.01),
                    TextTokenTopLogProb(token="Hi", logprob=-0.5),
                ],
            )
        ],
    )

    serialized = serialize_to_dict(content, SerializationContext(root=content))
    deserialized = autodeserialize_any_from_dict(serialized, DeserializationContext())
    assert isinstance(deserialized, TextContent)
    assert deserialized.content == "Hello"
    assert deserialized.logprobs is not None
    assert deserialized.logprobs[0].token == "Hello"
    assert deserialized.logprobs[0].top_logprobs is not None
    assert deserialized.logprobs[0].top_logprobs[1].token == "Hi"


def test_textcontent_accepts_raw_dict_logprobs() -> None:
    content = TextContent(
        content="Hello",
        logprobs=[
            {
                "token": "Hello",
                "logprob": -0.01,
                "top_logprobs": [
                    {"token": "Hello", "logprob": -0.01},
                ],
            }
        ],
    )

    assert content.logprobs is not None
    assert isinstance(content.logprobs[0], TextTokenLogProb)
    assert content.logprobs[0].top_logprobs is not None
    assert content.logprobs[0].top_logprobs[0].token == "Hello"


def test_textcontent_no_logprobs_backward_compat() -> None:
    content = TextContent(content="Hello")
    serialized = serialize_to_dict(content, SerializationContext(root=content))
    assert "logprobs" in serialized
    assert serialized["logprobs"] is None
