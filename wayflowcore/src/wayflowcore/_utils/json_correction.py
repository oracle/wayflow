# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import re
from textwrap import dedent
from typing import List

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.conversation import Conversation
from wayflowcore.models.llmmodel import LlmModel

logger = logging.getLogger(__name__)

JSON_CORRECTION_PROMPT = dedent(
    """
    You receive a json string, and an error that is produced, when trying to parse that text.
    You should edit that json blob so that the error is resolved.
    The keys in the json string must match the ones provided here.

    ---------------
    Json string:

    {{ json_string }}
    ---------------
    error:

    {{ error }}


    ----------------
    List of acceptable keys in the string:
    {% for key in keys %} {{ key }}, {% endfor %}

    ----------------
    (reminder to respond in a JSON blob no matter what)
    Assistant:
    """
)


def get_parsed_json_blobs(text: str) -> List[str]:
    text = text.strip()
    blobs = []
    regions = text.split("```")
    strip_json_identifier = r"^\s*\[?\s*(?:json|JSON)\s*]?\s*\:?\s*([\s\S]+?)\s*$"
    for txt in regions:
        # Remove any leading "json" identifiers, possibly in square brackets and with colon.
        m = re.search(strip_json_identifier, txt)
        txt = m.groups()[0] if m is not None else txt

        if len(txt) == 0:
            continue

        blobs.append(txt)
    return blobs


def edit_json(
    json_string: str,
    error: str,
    expected_keys: List[str],
    conversation: Conversation,
    llm: LlmModel,
) -> str:
    """
    Edit the json string, to resolve the error and key mismatches.

    Parameters
    ----------
    json_string : str
        json string to be parsed
    error: str
        The error that came up with parsing the json string
    expected_keys : List[str]
        List of expected keys in the json
    conversation: Conversation
        Conversation between the user and the assistant
    llm: Optional[LlmModel]
        LLM to use for editing the json

    Returns
    -------
    Dict
        Parsed json string
    """
    logger.info("There was a problem parsing the json string, correcting it with an LLM ")
    json_correction_prompt = render_template(
        template=JSON_CORRECTION_PROMPT,
        inputs=dict(
            json_string=json_string,
            error=error,
            keys=expected_keys,
        ),
    )
    text = llm.generate(prompt=json_correction_prompt, _conversation=conversation).message.content
    blobs = get_parsed_json_blobs(text)

    return blobs[0]
