# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
from dataclasses import replace
from typing import List, Sequence, Union, cast

from wayflowcore._utils._templating_helpers import MessageAsDictT
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.outputparser import JsonOutputParser, RegexOutputParser
from wayflowcore.property import Property, _convert_list_of_properties_to_json_schema
from wayflowcore.templates import PromptTemplate

JSON_CONSTRAINED_GENERATION_PROMPT = "At the end of your answer, finish with <final_answer>$your_answer$</final_answer> with $your_answer$ being a properly formatted json that is valid against this JSON schema:"


def _create_json_instruction_message(
    response_properties: List[Property], system_prompt: str = ""
) -> Message:
    return Message(
        message_type=MessageType.USER,
        content=system_prompt
        + "\n\n\n## Additional instructions: \n"
        + JSON_CONSTRAINED_GENERATION_PROMPT
        + json.dumps(_convert_list_of_properties_to_json_schema(response_properties)),
    )


def _add_json_output_parser(
    prompt_template: PromptTemplate, response_properties: List[Property]
) -> PromptTemplate:
    return prompt_template.with_output_parser(
        [
            RegexOutputParser(r"<final_answer>(.*)</final_answer>", strict=False),
            JsonOutputParser(
                properties=(
                    {prop_.name: f".{prop_.name}" for prop_ in response_properties}
                    if len(response_properties) > 1
                    else None
                )
            ),
        ]
    )


def _system_prompt_to_json_generation_prompt_template(
    system_prompt: str, output_descriptors: List[Property]
) -> PromptTemplate:
    formatted_messages = [_create_json_instruction_message(output_descriptors, system_prompt)]
    return _add_json_output_parser(PromptTemplate(formatted_messages), output_descriptors)


def adapt_prompt_template_for_json_structured_generation(
    prompt_template: PromptTemplate,
) -> PromptTemplate:
    """Adapts a prompt template for native structured generation to one
    that leverages a special system prompt and a JSON Output Parser.

    Parameters
    ----------
    prompt_template : PromptTemplate
        The prompt template to adapt

    Returns
    -------
    PromptTemplate
        The new prompt template, with the special system prompt and
        output parsers configured

    Raises
    ------
    ValueError
        If the prompt template is already configured to use non-native structured generation,
        or the prompt template has no response format.
    """
    if (
        not prompt_template.native_structured_generation
        or prompt_template.output_parser is not None
    ):
        raise ValueError(
            "Prompt template is already configured to use non-native structured generation."
        )

    response_format = prompt_template.response_format
    if response_format is None:
        raise ValueError(
            "Prompt template is missing a response format, and is thus not configured for "
            "structured generation."
        )

    json_instruction = _create_json_instruction_message([response_format])
    prompt_template_messages = cast(List[Message], prompt_template.messages)
    new_messages: Sequence[Union[Message, MessageAsDictT]] = [
        json_instruction
    ] + prompt_template_messages
    new_prompt_template = replace(prompt_template, messages=new_messages)
    new_prompt_template = _add_json_output_parser(new_prompt_template, [response_format])
    new_prompt_template.native_structured_generation = False
    return new_prompt_template
