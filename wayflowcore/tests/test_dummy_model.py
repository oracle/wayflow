# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import List

from wayflowcore.flow import Flow
from wayflowcore.steps import InputMessageStep, OutputMessageStep, PromptExecutionStep

from .testhelpers.dummy import DummyModel
from .testhelpers.flowscriptrunner import (
    AnswerCheck,
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
    MessageCheck,
)


def run_dummy_model_generation_assistant(
    llm: DummyModel, interactions: List[FlowScriptInteraction], num_generations: int = 1
) -> None:
    assistant = Flow.from_steps(
        [
            InputMessageStep(message_template="what do you want to do today?"),
        ]
        + [
            step
            for _ in range(num_generations)
            for step in [
                PromptExecutionStep(llm=llm, prompt_template="""{{user_provided_input}}"""),
                OutputMessageStep("""{{output}}"""),
            ]
        ]
    )

    script = FlowScript(
        name="",
        interactions=[FlowScriptInteraction(user_input=None)] + interactions,
    )

    runner = FlowScriptRunner([assistant], [script])
    runner.execute(raise_exceptions=True)


def test_single_generation_dummy_model() -> None:
    llm = DummyModel()
    interactions = [
        FlowScriptInteraction(
            user_input="whatever",
            setup=[lambda _: llm.set_next_output("hi")],
            checks=[AnswerCheck("hi")],
        )
    ]
    run_dummy_model_generation_assistant(llm, interactions)


def test_several_generation_dummy_model() -> None:
    llm = DummyModel()
    interactions = [
        FlowScriptInteraction(
            user_input="whatever",
            setup=[lambda _: llm.set_next_output(["hi1", "hi2", "hi3"])],
            checks=[
                MessageCheck(lambda messages: messages[-3].content == "hi1"),
                MessageCheck(lambda messages: messages[-2].content == "hi2"),
                MessageCheck(lambda messages: messages[-1].content == "hi3"),
            ],
        )
    ]
    run_dummy_model_generation_assistant(llm, interactions, num_generations=3)


def test_mapped_generation_dummy_model() -> None:
    llm = DummyModel()
    interactions = [
        FlowScriptInteraction(
            user_input="whatever",
            setup=[lambda _: llm.set_next_output({"whut": "mmmh", "whatever": "hi5"})],
            checks=[
                AnswerCheck("hi5"),
            ],
        )
    ]
    run_dummy_model_generation_assistant(llm, interactions)
