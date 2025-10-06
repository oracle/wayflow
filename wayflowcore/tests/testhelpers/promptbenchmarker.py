# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from typing import Any, Dict, List, Optional, Type

import pandas as pd

from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.flow import Flow
from wayflowcore.property import Property
from wayflowcore.steps.step import Step, StepResult

from ..testhelpers.flowscriptrunner import (
    AnswerCheck,
    FlowScript,
    FlowScriptInteraction,
    FlowScriptRunner,
)


def create_flow_script(user_question: str, answer_contains: str, script_name: str) -> FlowScript:
    return FlowScript(
        name=script_name,
        interactions=[
            FlowScriptInteraction(user_input=""),
            FlowScriptInteraction(
                user_input=user_question,
                can_be_rephrased=True,
                checks=[AnswerCheck(answer_contains)],
            ),
        ],
    )


class PromptBenchmarkerPlaceholder(Step):
    def __init__(
        self,
        input_mapping: Optional[Dict[str, str]] = None,
        output_mapping: Optional[Dict[str, str]] = None,
    ):
        super().__init__(step_static_configuration={})

    @classmethod
    def _get_step_specific_static_configuration_descriptors(
        cls,
    ) -> Dict[str, type]:
        """
        Returns a dictionary in which the keys are the names of the configuration items
        and the values are a descriptor for the expected type
        """
        return {}

    @classmethod
    def _compute_step_specific_input_descriptors_from_static_config(cls) -> List[Property]:
        return []

    @classmethod
    def _compute_step_specific_output_descriptors_from_static_config(cls) -> List[Property]:
        return []

    def _invoke_step(
        self,
        inputs: Dict[str, Any],
        conversation: FlowConversation,
    ) -> StepResult:
        raise ValueError("This step is only a placeholder, it should not be called")


class PromptBenchmarker:
    PLACEHOLDER = PromptBenchmarkerPlaceholder()
    _QUESTION_COLUMN = "question"
    _ANSWER_COLUMN = "answer"

    def __init__(
        self,
        steps: List[Step],  # could be extended to Flow
        df: pd.DataFrame,
        step_cls: Type[Step],
        step_args: Dict[str, Any],
        step_diff_args: List[Dict[str, Any]],
        verbose: bool = False,
    ):
        """
        Class to run a benchmark and compare HP of a step. All arguments are required

        Parameters
        ----------
        steps:
            list of steps representing the sequence of the steps that will be run. This list needs to contain a PromptBenchmarker.PLACEHOLDER,
            which will signify that this step needs to be replaced by the step we test with different HPs.
        df:
            dataframe containing at least 2 columns: `question` and `answer`. The `question` is passed as a user input to the assistant,
            and we count a success if the assistant answer contains `answer`. If some other metric is needed, then introduce a step that
            grades this metric and returns a str that contains `answer`.
        step_cls:
            Step class that will be benchmarked.
        step_args:
            Arguments that are all common to the step (llm, ...)
        step_diff_args:
            List of argument dicts that the benchmarker will compare

        Example
        -------
        >>> import pandas as pd
        >>> from wayflowcore.steps import PromptExecutionStep, InputMessageStep, OutputMessageStep
        >>> from .testhelpers.promptbenchmarker import PromptBenchmarker
        >>> from wayflowcore.models.llmgenerationconfig import LlmGenerationConfig
        >>> step_seq = [
        ...    InputMessageStep("Hi"),
        ...    PromptBenchmarker.PLACEHOLDER,
        ...    OutputMessageStep(message_template="{{output}}"),
        ... ]
        >>> df = pd.DataFrame({
        ...     'question': ['what is the biggest city in Switzerland?'],
        ...     'answer': ['Zurich'],
        ... })
        >>> comparator = PromptBenchmarker(
        ...     steps=step_seq,
        ...     df=df,
        ...     step_cls=PromptExecutionStep,
        ...     step_args=dict(
        ...         llm=llm,
        ...         prompt_template="{{user_provided_input}}"
        ...     ),
        ...     step_diff_args=[
        ...         dict(generation_config=LlmGenerationConfig(max_new_tokens=10)),
        ...         dict(generation_config=LlmGenerationConfig(max_new_tokens=1)), # won't have enough tokens to answer Zurich
        ...     ],
        ... )
        >>> result = comparator.run_comparison(N=2)   # doctest: +SKIP
        >>> pivoted_result = PromptBenchmarker.compare_results_per_script(result)   # doctest: +SKIP
        #      run     succeeded_0  succeeded_1  duration_0  duration_1
        #   0  Zurich  1.0          0.0          0.200946    0.04486
        ```
        """
        flows = []

        for single_step_args in step_diff_args:
            placeholder_found = 0
            # this works since all steps in a flow are stateless
            step_sequence = []
            for i in range(len(steps)):
                if isinstance(steps[i], PromptBenchmarkerPlaceholder):
                    step_sequence.append(step_cls(**step_args, **single_step_args))
                    placeholder_found += 1
                else:
                    step_sequence.append(steps[i])

            if placeholder_found != 1:
                raise ValueError(
                    f"Should have 1 placeholder in step sequence, got {placeholder_found} instead."
                )
            flows.append(step_sequence)

        self.assistants = [Flow.from_steps(step_seq) for step_seq in flows]

        self.scripts = [
            create_flow_script(
                user_question=row[PromptBenchmarker._QUESTION_COLUMN],
                answer_contains=row[PromptBenchmarker._ANSWER_COLUMN],
                script_name=row[PromptBenchmarker._ANSWER_COLUMN],
            )
            for i, (idx, row) in enumerate(df.iterrows())
        ]

    def run_comparison(self, N: int = 1) -> pd.DataFrame:
        runner = FlowScriptRunner(
            assistants=self.assistants,
            flow_scripts=self.scripts,
        )
        df = runner.execute(raise_exceptions=False, N=N)

        # remove the rows where there is no check to have proper success rates
        df = df[df["checks"].apply(lambda x: len(x) > 0 if isinstance(x, List) else True)]
        return df

    @staticmethod
    def compare_results_per_script(df: pd.DataFrame) -> pd.DataFrame:
        summary = df.groupby(["assistant", "run"])[["succeeded", "duration"]].mean().reset_index()
        pivoted_df = summary.pivot(
            index="run", columns="assistant", values=["succeeded", "duration"]
        ).reset_index()

        num_values = len(df["assistant"].unique())
        selected_columns = [
            "run",
            *[f"succeeded_{i}" for i in range(num_values)],
            *[f"duration_{i}" for i in range(num_values)],
        ]
        pivoted_df.columns = selected_columns  # type: ignore
        return pivoted_df
