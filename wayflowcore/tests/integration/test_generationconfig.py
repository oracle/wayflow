# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.
from unittest.mock import patch

import pytest

from wayflowcore.messagelist import Message
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import LlmModel, Prompt
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.serialization import deserialize_from_dict, serialize_to_dict

from ..conftest import VLLM_MODEL_CONFIG


def test_config_serde():
    llm = VllmModel(
        model_id=VLLM_MODEL_CONFIG["model_id"],
        host_port=VLLM_MODEL_CONFIG["host_port"],
        generation_config=LlmGenerationConfig(
            max_tokens=1234, temperature=0.5, extra_args={"custom": 1}
        ),
    )

    serialized_llm = serialize_to_dict(llm)
    assert serialized_llm["generation_config"]["max_tokens"] == 1234
    assert serialized_llm["generation_config"]["temperature"] == 0.5
    assert serialized_llm["generation_config"]["custom"] == 1

    deserialized_model = deserialize_from_dict(LlmModel, serialized_llm)

    assert deserialized_model.generation_config.max_tokens == 1234
    assert deserialized_model.generation_config.temperature == 0.5
    assert deserialized_model.generation_config.extra_args == {"custom": 1}


def test_overriding_configs():
    default_config = LlmGenerationConfig(max_tokens=1234, temperature=0.5)
    second_config = LlmGenerationConfig(max_tokens=12345, top_p=0.4)
    new_config = default_config.merge_config(second_config)

    # new config is properly configured
    assert new_config.max_tokens == 12345
    assert new_config.temperature == 0.5
    assert new_config.top_p == 0.4

    # default is untouched
    assert default_config.max_tokens == 1234
    assert default_config.temperature == 0.5
    assert default_config.top_p is None

    # new is also untouched
    assert second_config.max_tokens == 12345
    assert second_config.temperature is None
    assert second_config.top_p == 0.4


def test_overriding_configs_with_extra_args():
    default_config = LlmGenerationConfig(
        max_tokens=1234, temperature=0.5, extra_args={"a": "old", "b": True}
    )
    second_config = LlmGenerationConfig(
        max_tokens=12345, top_p=0.4, extra_args={"a": "new", "c": 3}
    )
    new_config = default_config.merge_config(second_config)

    # new config is properly configured
    assert new_config.max_tokens == 12345
    assert new_config.temperature == 0.5
    assert new_config.top_p == 0.4
    assert new_config.extra_args == {"a": "new", "b": True, "c": 3}

    # default is untouched
    assert default_config.max_tokens == 1234
    assert default_config.temperature == 0.5
    assert default_config.top_p is None
    assert default_config.extra_args == {"a": "old", "b": True}

    # new is also untouched
    assert second_config.max_tokens == 12345
    assert second_config.temperature is None
    assert second_config.top_p == 0.4
    assert second_config.extra_args == {"a": "new", "c": 3}


def test_overriding_configs_keeps_none_values():
    default_config = LlmGenerationConfig(max_tokens=1234)
    second_config = LlmGenerationConfig(top_p=0.4)
    new_config = default_config.merge_config(second_config)

    # new config is properly configured
    assert new_config.max_tokens == 1234
    assert new_config.temperature is None
    assert new_config.top_p == 0.4

    # default is untouched
    assert default_config.max_tokens == 1234
    assert default_config.temperature is None
    assert default_config.top_p is None

    # new is also untouched
    assert second_config.max_tokens is None
    assert second_config.temperature is None
    assert second_config.top_p == 0.4


@pytest.mark.parametrize(
    "default_max_tokens,new_max_tokens,expected_min_length,expected_max_length",
    [
        (1, None, 0, 5),
        (10, None, 6, 50),
        (100, None, 51, 500),
        (None, 1, 0, 5),
        (None, 10, 6, 50),
        (None, 100, 51, 500),
        (100, 1, 0, 5),
        (100, 10, 6, 50),
        (100, 100, 51, 500),
    ],
)
def test_config_taken_into_account(
    default_max_tokens, new_max_tokens, expected_min_length, expected_max_length
):

    def make_generate_config(max_tokens: int):
        return LlmGenerationConfig(max_tokens=max_tokens) if max_tokens is not None else None

    llm = VllmModel(
        model_id=VLLM_MODEL_CONFIG["model_id"],
        host_port=VLLM_MODEL_CONFIG["host_port"],
        generation_config=make_generate_config(default_max_tokens),
    )
    prompt = Prompt(
        messages=[Message(content="Count up to 1000. Just output the numbers")],
        generation_config=make_generate_config(new_max_tokens),
    )
    generated_text = llm.generate(prompt).message.content

    assert len(generated_text) > expected_min_length
    assert len(generated_text) < expected_max_length


@pytest.mark.parametrize(
    "max_tokens,temperature,top_p,frequency_penalty",
    [
        (None, None, None, None),
        (1234, None, None, 0),
        (None, 0.66, None, -0.2),
        (None, None, 0.77, 1),
        (1234, 0.66, 0.77, 2),
    ],
)
def test_config_properly_passed_to_langchain(max_tokens, temperature, top_p, frequency_penalty):
    llm = VllmModel(
        model_id=VLLM_MODEL_CONFIG["model_id"],
        host_port=VLLM_MODEL_CONFIG["host_port"],
    )

    async def gen(*args, **kwargs):
        return {"choices": [{"message": {"content": "1, 2, 3"}}]}

    with patch.object(llm, "_post", side_effect=gen) as mock:
        prompt = Prompt(
            messages=[Message(content="Count up to 1. Just output the numbers")],
            generation_config=LlmGenerationConfig(
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
            ),
        )
        llm.generate(prompt)

        kwargs = mock.call_args.kwargs["request_params"]["json"]
        if max_tokens is not None:
            assert max_tokens == kwargs["max_completion_tokens"]
        if temperature is not None:
            assert temperature == kwargs["temperature"]
        if top_p is not None:
            assert top_p == kwargs["top_p"]
        if frequency_penalty is not None:
            assert frequency_penalty == kwargs["frequency_penalty"]


@pytest.mark.parametrize(
    "frequency_penalty",
    [3, -4],
)
def test_frequency_penalty_raises_error_properly(frequency_penalty):
    with pytest.raises(ValueError, match="The frequency penalty should be between -2 and 2"):
        LlmGenerationConfig(frequency_penalty=frequency_penalty)


def test_config_with_known_extra_args_overwrites_fields_if_not_set() -> None:
    extra_args = dict(
        max_tokens=1234,
        temperature=0.5,
        top_p=0.3,
        stop=["exit"],
        frequency_penalty=0.4,
        custom_attribute=1,
    )
    llm_config = LlmGenerationConfig(extra_args=extra_args)
    assert llm_config.max_tokens == 1234
    assert llm_config.temperature == 0.5
    assert llm_config.top_p == 0.3
    assert llm_config.stop == ["exit"]
    assert llm_config.frequency_penalty == 0.4
    assert llm_config.extra_args == dict(custom_attribute=1)


def test_config_with_known_extra_args_ignores_fields_if_set_and_warns() -> None:

    extra_args = dict(
        max_tokens=5678,
        temperature=1.05,
        top_p=0.7,
        frequency_penalty=0.987,
        custom_attribute=1,
    )

    with pytest.warns(UserWarning):
        llm_config = LlmGenerationConfig(
            max_tokens=1234,
            temperature=0.5,
            top_p=0.3,
            stop=["exit"],
            frequency_penalty=0.4,
            extra_args=extra_args,
        )

    assert llm_config.max_tokens == 1234
    assert llm_config.temperature == 0.5
    assert llm_config.top_p == 0.3
    assert llm_config.stop == ["exit"]
    assert llm_config.frequency_penalty == 0.4
    assert llm_config.extra_args == dict(custom_attribute=1)
