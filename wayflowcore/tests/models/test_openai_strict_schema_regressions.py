# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
import os

import pytest

from wayflowcore import Message
from wayflowcore.models import OpenAIAPIType, OpenAIModel
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.openaicompatiblemodel import OPEN_API_KEY
from wayflowcore.property import DictProperty, ObjectProperty, StringProperty
from wayflowcore.templates import PromptTemplate

OPENAI_MODEL_ID = "gpt-6-astra"

pytestmark = pytest.mark.skipif(
    OPEN_API_KEY not in os.environ,
    reason="OPENAI_API_KEY is not set",
)


def test_openai_model_rejects_dynamic_dicts_in_native_structured_output() -> None:
    model = OpenAIModel(
        model_id=OPENAI_MODEL_ID,
        api_type=OpenAIAPIType.RESPONSES,
        generation_config=LlmGenerationConfig(max_tokens=128),
    )
    supported_template = PromptTemplate(
        messages=[Message(role="user", content="Return value exactly 'ok'.")],
        response_format=ObjectProperty(
            name="result",
            properties={"value": StringProperty()},
        ),
    )
    supported_completion = model.generate(supported_template.format())
    assert json.loads(supported_completion.message.content) == {"value": "ok"}

    template = PromptTemplate(
        messages=[Message(role="user", content="Return labels.")],
        response_format=ObjectProperty(
            name="result",
            properties={"labels": DictProperty(value_type=StringProperty())},
        ),
    )

    with pytest.raises(ValueError, match="DictProperty.*strict structured output"):
        model.generate(template.format())
