# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import pandas as pd
import pytest
from pandas.core.frame import DataFrame

from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import ChoiceSelectionStep, InputMessageStep, OutputMessageStep
from wayflowcore.steps.choiceselectionstep import _DEFAULT_CHOICE_SELECTION_TEMPLATE

from .testhelpers.promptbenchmarker import PromptBenchmarker
from .testhelpers.testhelpers import retry_test


@pytest.fixture
def choice_selection_dataset():
    TASKS = {
        "answer": [
            "writing_assistance",
            "research_analysis",
            "coding_task",
            "creative_writing",
            "writing_feedback",
        ],
        "description": [
            "Writing Assistance",
            "Research and Analysis",
            "Coding and Technical Tasks",
            "Creative Writing",
            "Writing Feedback and Editing",
        ],
        "question": [
            "Can you help me draft a formal letter to my landlord about a maintenance issue?",
            "What are the key factors driving the rise in electric vehicle adoption globally?",
            "How can I implement a search feature with fuzzy string matching in Python?",
            "I need ideas for a new science fiction short story, can you suggest some unique prompts?",
            "Could you provide constructive criticism on the structure and argumentation in my essay?",
        ],
    }
    return pd.DataFrame(TASKS)


NEW_TEMPLATE = """You are a helpful assistant. Your goal is to understand what task the user wants to solve. The available tasks are:
```
{% for desc in next_steps -%}
- {{ desc.displayed_step_name }}: {{ desc.description }}
{% endfor -%}
```

The format you need to follow is:
```
user_input: question from the human that could be solved using task task_1
task_name: task_1
```

Begin! Remember to only answer with the task name.
```
user_input: {{ input }}
task_name: """


@retry_test(max_attempts=3)
def test_choice_selection_default_and_new_template_score_above_threshold_in_comparator(
    remotely_hosted_llm: VllmModel, choice_selection_dataset: DataFrame
) -> None:
    """
    Failure rate:          2 out of 100
    Observed on:           2024-12-18
    Average success time:  2.55 seconds per successful attempt
    Average failure time:  2.63 seconds per failed attempt
    Max attempt:           3
    Justification:         (0.03 ** 3) ~= 2.5 / 100'000
    """

    step_seq = [
        InputMessageStep(
            "What do you want to do?",
            output_mapping={InputMessageStep.USER_PROVIDED_INPUT: ChoiceSelectionStep.INPUT},
        ),
        PromptBenchmarker.PLACEHOLDER,
        OutputMessageStep(message_template="{{selected_choice}}"),
    ]

    comparator = PromptBenchmarker(
        steps=step_seq,
        df=choice_selection_dataset,
        step_cls=ChoiceSelectionStep,
        step_args=dict(
            llm=remotely_hosted_llm,
            num_tokens=14,
            next_steps=[
                ("step2", row["description"], row["answer"])
                for _, row in choice_selection_dataset.iterrows()
            ],
        ),
        step_diff_args=[
            dict(prompt_template=_DEFAULT_CHOICE_SELECTION_TEMPLATE),
            dict(prompt_template=NEW_TEMPLATE),
        ],
        verbose=True,
    )

    result = comparator.run_comparison(N=2)

    summary = result.groupby(["assistant", "run"])[["succeeded", "duration"]].mean().reset_index()
    pivoted_df = summary.pivot(
        index="run", columns="assistant", values=["succeeded", "duration"]
    ).reset_index()

    num_values = 2
    pivoted_df.columns = (
        ["run"]
        + [f"succeeded_{i}" for i in range(num_values)]
        + [f"duration_{i}" for i in range(num_values)]
    )
    assert pivoted_df["succeeded_0"].mean() > 0.5
    assert pivoted_df["succeeded_1"].mean() > 0.5
