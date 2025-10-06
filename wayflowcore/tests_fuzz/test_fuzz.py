# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import os
import random
import traceback
from pathlib import Path
from typing import List, Optional

from pythonfuzz.main import PythonFuzz

from wayflowcore.agent import Agent
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.flow import Flow
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.models.llmmodelfactory import LlmModelFactory
from wayflowcore.serialization import deserialize, serialize
from wayflowcore.steps import InputMessageStep, OutputMessageStep, PromptExecutionStep

fuzz_output_filename = "wayflowcore.result.fuzz.txt"
fuzz_exceptions_output_filename = "wayflowcore.exceptions.fuzz.txt"
exceptions_found = dict()


def create_flow(
    buf: bytes,
    encoding: str,
) -> Flow:
    message_types = [e.value for e in MessageType]
    message_template = buf.decode(encoding)
    prompt_template = buf.decode(encoding)

    user_input_step = InputMessageStep(
        message_template=buf.decode(encoding),
        rephrase=random.randint(0, 1) == 0,
    )

    prompt_step = PromptExecutionStep(
        prompt_template=prompt_template,
        generation_config=(
            None
            if random.randint(0, 1) == 0
            else LlmGenerationConfig.from_dict({buf.decode(encoding): buf.decode(encoding)})
        ),
    )

    output_step = OutputMessageStep(
        message_template=message_template,
        message_type=message_types[random.choice(message_types)],
        rephrase=random.randint(0, 1) == 0,
    )

    steps = {
        buf[0].decode(encoding): user_input_step,
        buf[1].decode(encoding): prompt_step,
        buf[2].decode(encoding): output_step,
    }

    step_names = [k for k in steps]
    begin_step_name = step_names[0]

    transitions = {
        step_names[0]: [step_names[1]],
        step_names[1]: [step_names[2]],
        step_names[2]: [None],
    }

    return Flow(
        begin_step_name=begin_step_name,
        steps=steps,
        transitions=transitions,
    )


def create_llm(
    buf: bytes,
    encoding: str,
) -> LlmModel:
    return LlmModelFactory.from_config(
        {
            "model_type": "vllm",
            buf.decode(encoding): buf.decode(encoding),
            "generation_config": {buf.decode(encoding): buf.decode(encoding)},
        }
    )


def create_agent(
    buf: bytes,
    encoding: str,
    llm: Optional[LlmModel],
    flows: Optional[List[Flow]] = None,
) -> Agent:
    return Agent(
        llm=llm,
        flows=flows,
        custom_instruction=buf.decode(encoding),
        max_iterations=random.randint(0, 1000000000),
        can_finish_conversation=random.randint(0, 1) == 0,
    )


def create_flow_assistant(
    buf: bytes,
    encoding: str,
    flow: Optional[Flow] = None,
) -> Agent:
    return flow or create_flow(buf, encoding)


def execute_assistant(
    buf: bytes,
    encoding: str,
    assistant: ConversationalComponent,
) -> None:
    conversation = assistant.start_conversation()
    assistant.execute(conversation)
    message_types = [e.value for e in MessageType]
    user_message = Message(
        content=buf.decode(encoding),
        message_type=message_types[random.choice(message_types)],
    )
    conversation.append_message(user_message)
    assistant.execute(conversation)
    conversation.append_agent_message(buf.decode(encoding))
    conversation.append_user_message(buf.decode(encoding))
    assistant.execute(conversation)


def serialize_and_deserialize_assistant(
    buf: bytes,
    encoding: str,
    assistant: ConversationalComponent,
) -> None:
    serialized_assistant = serialize(assistant)
    _ = deserialize(ConversationalComponent, serialized_assistant)


def test_llm_creation(buf: bytes, encoding: str):
    create_llm(buf, encoding)


def test_flow_creation(buf: bytes, encoding: str):
    create_flow(buf, encoding)


def test_flow_assistant(buf: bytes, encoding: str):
    create_flow(buf, encoding)
    assistant = create_flow_assistant(buf, encoding)
    execute_assistant(buf, encoding, assistant)
    serialize_and_deserialize_assistant(buf, encoding, assistant)


def test_agent(buf: bytes, encoding: str):

    if random.randint(0, 1) % 2:
        llm = create_llm(buf, encoding)
    else:
        llm = LlmModelFactory.from_config(
            {
                "model_type": "openai",
                "generation_config": {},
            }
        )

    if random.randint(0, 1) % 2:
        flows = [create_flow(buf, encoding)]
    else:
        flows = None

    assistant = create_agent(buf, encoding, llm, flows)
    execute_assistant(buf, encoding, assistant)
    serialize_and_deserialize_assistant(buf, encoding, assistant)


def test_existing_flow_assistant(buf, encoding):
    configs_dir = Path(os.path.dirname(__file__)).parent / "tests" / "configs"
    with open(configs_dir / "xkcd_tech_support_flow_chart.yaml") as config_file:
        serialized_xkcd_flow = config_file.read()
    xkcd_flow = deserialize(Flow, serialized_xkcd_flow)
    xkcd_assistant = Flow(xkcd_flow)
    execute_assistant(buf, encoding, xkcd_assistant)
    serialize_and_deserialize_assistant(buf, encoding, xkcd_assistant)


def test_deserialize(buf, encoding):
    target_class = random.choice(
        [
            ConversationalComponent,
            Flow,
            LlmModel,
        ]
    )
    deserialize(target_class, buf.decode(encoding))


@PythonFuzz
def fuzz(buf):

    random.seed()
    encoding = "utf-8"
    test_functions = [
        test_llm_creation,
        test_flow_creation,
        test_flow_assistant,
        test_agent,
        test_existing_flow_assistant,
        test_deserialize,
    ]

    # We proceed with a fuzz test only if the buffer can be correctly decoded
    try:
        _ = buf.decode(encoding)
        buffer_can_be_decoded = True
    except UnicodeDecodeError:
        buffer_can_be_decoded = False

    if buffer_can_be_decoded:
        try:

            test_function = random.choice(test_functions)
            test_function(buf, encoding)

        except Exception as e:

            # The way we store exceptions needs to take into account 2 things
            # - The code might raise many exceptions, so result files can grow bigger and bigger
            # - The code can be interrupted at any time, even in the middle of a write
            # To take into account these two concerns, we split the data we store in two parts
            # - an exception file where we store unique exception (verbose) information, including an identifier
            # - a results file where we record only the identifier of the exception raised
            exception_str = str(e)
            if exception_str not in exceptions_found:
                stacktrace = str(traceback.format_exc())
                exceptions_found[exception_str] = len(exceptions_found)
                with open(fuzz_exceptions_output_filename, "a") as outfile:
                    # Strings can contain new lines that are hard to remove, so we use another format
                    # Elements are separated by a line made of four colons: "::::"
                    for s in [exceptions_found[exception_str], type(e), exception_str, stacktrace]:
                        print(s, end="\n::::\n", file=outfile)
            exception_idx = exceptions_found[exception_str]
            with open(fuzz_output_filename, "a") as outfile:
                print(f"{exception_idx}", file=outfile)


if __name__ == "__main__":
    if os.path.isfile(fuzz_output_filename):
        os.remove(fuzz_output_filename)
    if os.path.isfile(fuzz_exceptions_output_filename):
        os.remove(fuzz_exceptions_output_filename)
    fuzz()
