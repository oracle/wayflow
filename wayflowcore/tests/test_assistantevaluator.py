# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from typing import Dict, List

import pytest

from wayflowcore import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.evaluation import (
    AssistantEvaluator,
    EvaluationEnvironment,
    EvaluationTask,
    HumanProxyAssistant,
    TaskScorer,
)
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.models.vllmmodel import VllmModel
from wayflowcore.steps import AgentExecutionStep
from wayflowcore.tools import ServerTool

from .testhelpers.dummy import DummyModel


class EnvWithoutImplementationOfAbstractMethod(EvaluationEnvironment):
    def __init__(self, env_id: str = ""):
        super().__init__(env_id=env_id)


class DummyAssistant:
    def start_conversation(self) -> None:
        return

    def __repr__(self) -> str:
        return "DummyAssistant()"


class DummyTaskScorer(TaskScorer):
    OUTPUT_METRICS = ["metric"]
    DEFAULT_SCORER_ID = "dummy_scorer"

    def score(
        self,
        environment: EvaluationEnvironment,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {metric_name: 0.0 for metric_name in self.OUTPUT_METRICS}

    def score_exceptional_case(
        self,
        environment: EvaluationEnvironment,
        exception: Exception,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {metric_name: None for metric_name in self.OUTPUT_METRICS}


class DummyEnv(EvaluationEnvironment):
    def __init__(self, env_id: str) -> None:
        self.assistant: ConversationalComponent = None
        self.human_proxy: HumanProxyAssistant = None
        super().__init__(env_id=env_id)

    def get_assistant(self, task: EvaluationTask) -> ConversationalComponent:
        self.assistant = DummyAssistant()
        return self.assistant

    def get_human_proxy(self, task: EvaluationTask) -> ConversationalComponent:
        self.human_proxy = DummyAssistant()
        return self.human_proxy

    def init_env(self, task: EvaluationTask) -> None:
        return

    def reset_env(self, task: EvaluationTask) -> None:
        return


def test_environment_and_evaluator_can_init() -> None:
    DUMMY_ENV = "single_env"
    dummy_env = DummyEnv(DUMMY_ENV)

    evaluator = AssistantEvaluator(
        environment=dummy_env,
        metrics=["metric"],
    )
    assert isinstance(evaluator._environment, EvaluationEnvironment)
    assert DUMMY_ENV == evaluator._environment.env_id and isinstance(
        evaluator._environment, DummyEnv
    )


def test_env_has_not_implemented_methods() -> None:
    with pytest.raises(
        TypeError,
        match="Can't instantiate abstract class EnvWithoutImplementationOfAbstractMethod",
    ):
        dummy_env = EnvWithoutImplementationOfAbstractMethod()


def test_exceptional_score() -> None:
    DUMMY_ENV = "dummy"
    dummy_env = DummyEnv(DUMMY_ENV)
    dummy_scorer = DummyTaskScorer()

    tasks = [
        EvaluationTask(task_id="dummy_task", description="", scorers=[dummy_scorer]),
    ]
    evaluator = AssistantEvaluator(
        environment=dummy_env,
        metrics=["metric"],
        max_conversation_rounds=1,
    )
    results_df = evaluator.run_benchmark(tasks, N=1, raise_exceptions=True)
    assert "metric" in results_df.columns
    assert results_df.loc[0, "metric"] == None


def test_evaluation_task_raises_when_two_scorer_have_duplicate_metrics() -> None:
    with pytest.raises(
        ValueError,
        match="Metrics must be unique across scorers, but metric 'metric' is duplicated!",
    ):
        EvaluationTask(
            task_id="dummy_task", description="", scorers=[DummyTaskScorer(), DummyTaskScorer()]
        )


def test_evaluator_raises_when_two_tasks_have_duplicated_metrics() -> None:
    tasks = [
        EvaluationTask(task_id="dummy_task", description="", scorers=[DummyTaskScorer(f"dummy{i}")])
        for i in range(2)
    ]
    evaluator = AssistantEvaluator(
        environment=DummyEnv("dummy"),
        max_conversation_rounds=0,
    )
    with pytest.raises(
        ValueError,
        match="Metric \\{'metric'\\} returned by scorer dummy1 is not unique across scorers from different tasks, found scorer dummy0 with \\{'metric'\\}",
    ):
        evaluator.run_benchmark(tasks, N=1, raise_exceptions=True)


class DummyTaskScorer2(TaskScorer):
    OUTPUT_METRICS = ["metric2"]
    DEFAULT_SCORER_ID = "dummy_scorer"

    def score(
        self,
        environment: EvaluationEnvironment,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {metric_name: 0.0 for metric_name in self.OUTPUT_METRICS}

    def score_exceptional_case(
        self,
        environment: EvaluationEnvironment,
        exception: Exception,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {metric_name: None for metric_name in self.OUTPUT_METRICS}


def test_evaluator_raises_when_scorer_with_same_id_dont_have_same_metrics() -> None:
    tasks = [
        EvaluationTask(  # creates a task for each scorer
            task_id="dummy_task", description="", scorers=[scorer]
        )
        for scorer in [
            DummyTaskScorer(),
            DummyTaskScorer2(),
        ]  # these two scorers have the same id 'dummy_scorer'
    ]
    evaluator = AssistantEvaluator(
        environment=DummyEnv("dummy"),
        max_conversation_rounds=0,
    )
    with pytest.raises(
        ValueError,
        match="Scorer dummy_scorer has different metrics across tasks: \\{'metric2'\\} vs \\{'metric'\\}",
    ):
        evaluator.run_benchmark(tasks, N=1, raise_exceptions=True)


def test_task_implements_evaluation_metrics() -> None:
    DUMMY_ENV = "dummy"
    dummy_env = DummyEnv(DUMMY_ENV)

    tasks = [
        EvaluationTask(  # creates a task for each scorer
            task_id="dummy_task", description="", scorers=[scorer]
        )
        for scorer in [
            DummyTaskScorer(),
            DummyTaskScorer2("dummy_scorer2"),
        ]
    ]
    evaluator = AssistantEvaluator(
        environment=dummy_env,
        metrics=["unexpected_metric"],
        max_conversation_rounds=1,
    )

    with pytest.raises(
        ValueError,
        match="This evaluator's list of metrics \\['unexpected_metric'\\] must be a subset of all metrics across all tasks",
    ):
        results_df = evaluator.run_benchmark(tasks, N=1, raise_exceptions=True)


##--------------------------END TO END EVALUATION TESTING--------------------------##

DEFAULT_FORECASTING_LAST_KNOWN_VALUE = 0


class ForecastTool:
    def __init__(self, data_store: "ForecastingDatastore") -> None:
        self.data_store = data_store

    def __call__(self, forecasting_horizon: int = 5) -> str:
        forecasted_data = [self.data_store.last_known_value]
        for _ in range(forecasting_horizon):
            forecasted_data.append(forecasted_data[-1] + 1)  # advanced forecasting method
        self.data_store.forecasted_data = forecasted_data[1:]
        return f"Successfully forecasted data with a horizon of {forecasting_horizon} days"


def create_forecast_tool(data_store: "ForecastingDatastore") -> ServerTool:
    forecasting_tool = ForecastTool(data_store)

    return ServerTool(
        name="forecast_data",
        description="Tool to forecast data",
        parameters={
            "forecasting_horizon": {
                "description": "The forecasting horizon, in days",
                "type": "integer",
                "default": 5,
            },
        },
        func=forecasting_tool,
        output={"type": "string"},
    )


class RetrieveTool:
    def __init__(self, data_store: "ForecastingDatastore") -> None:
        self.data_store = data_store

    def __call__(self, data_type: str) -> str:
        if data_type == "weather":
            self.data_store.last_known_value = 1
            return f"Successfully retrieved data associated to data type {data_type}"
        else:
            raise ValueError(f"data_type {data_type} is not supported.")


def create_retrieve_tool(data_store: "ForecastingDatastore") -> ServerTool:
    retrieve_tool = RetrieveTool(data_store)

    return ServerTool(
        name="retrieve_previous_data",
        description="Tool to retrieve previous data",
        parameters={
            "data_type": {
                "description": "The type of data to retrieve. Supported types are: weather.",
                "type": "string",
            },
        },
        func=retrieve_tool,
        output={"type": "string"},
    )


class ForecastingDatastore:
    def __init__(self) -> None:
        self.reset()

    def get_tools(self) -> List[ServerTool]:
        return [create_forecast_tool(self), create_retrieve_tool(self)]

    def reset(self) -> None:
        self.forecasted_data = []
        self.last_known_value = DEFAULT_FORECASTING_LAST_KNOWN_VALUE


def get_forecasting_assistant(
    llm: LlmModel,
    datastore: ForecastingDatastore,
    tools: List[ServerTool],
) -> Flow:
    step = AgentExecutionStep(agent=Agent(llm=llm, tools=tools))
    return create_single_step_flow(step, step_name="single_step")


class ForecastingScorer(TaskScorer):
    OUTPUT_METRICS = ["mean_square_error"]
    DEFAULT_SCORER_ID = "forecasting_scorer"

    def score(
        self,
        environment: "ForecastingEnvironment",
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        forecasting_horizon = task.task_kwargs["forecasting_horizon"]
        true_value = list(range(1, forecasting_horizon + 1))

        predicted_value = environment.datastore.forecasted_data

        if len(true_value) != len(predicted_value):
            error = float("inf")
        else:
            error = sum(
                (true - predicted) ** 2 for true, predicted in zip(true_value, predicted_value)
            ) / len(true_value)

        return {"mean_square_error": error}

    def score_exceptional_case(
        self,
        environment: "ForecastingEnvironment",
        exception: Exception,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {"mean_square_error": None}


class ForecastingEnvironment(EvaluationEnvironment):
    DEFAULT_ASSISTANT_ROLE = "A helpful forecaster, whose ONLY job is to forecast data"
    DEFAULT_USER_ROLE = "A user interested ONLY in forecasting data"

    def __init__(self, env_id: str, llm: LlmModel) -> None:
        self.datastore = ForecastingDatastore()
        self.llm = llm
        self.assistant: ConversationalComponent = None
        self.human_proxy: HumanProxyAssistant = None
        super().__init__(env_id=env_id)

    def get_assistant(self, task: EvaluationTask) -> ConversationalComponent:
        if self.assistant is None:
            tools = self.datastore.get_tools()
            self.assistant = get_forecasting_assistant(
                llm=self.llm,
                datastore=self.datastore,
                tools=tools,
            )
        return self.assistant

    def get_human_proxy(self, task: EvaluationTask) -> ConversationalComponent:
        description = task.description
        self.human_proxy = HumanProxyAssistant(
            llm=self.llm,
            full_task_description=description,
            short_task_description=description,
            assistant_role=self.DEFAULT_ASSISTANT_ROLE,
            user_role=self.DEFAULT_USER_ROLE,
        )
        return self.human_proxy

    def init_env(self, task: EvaluationTask) -> None:
        self.datastore.reset()

    def reset_env(self, task: EvaluationTask) -> None:
        self.datastore.reset()


def test_reset_env() -> None:
    llm = DummyModel(fails_if_not_set=False)
    FORECASTING_ENV = "forecasting"
    forecasting_env = ForecastingEnvironment(FORECASTING_ENV, llm=llm)
    forecasting_scorer = ForecastingScorer()
    dummy_task = EvaluationTask(task_id="dummy_task", description="", scorers=[forecasting_scorer])
    evaluator = AssistantEvaluator(
        environment=forecasting_env,
        metrics=["mean_square_error"],
        max_conversation_rounds=0,  # no need for tool
    )
    tools = {tool.name: tool for tool in forecasting_env.datastore.get_tools()}
    assert (
        forecasting_env.datastore.forecasted_data == []
        and forecasting_env.datastore.last_known_value == DEFAULT_FORECASTING_LAST_KNOWN_VALUE
    )
    tools["retrieve_previous_data"].run(data_type="weather")
    tools["forecast_data"].run(forecasting_horizon=3)
    _ = evaluator._run_one_benchmark_attempt_on_task(dummy_task, 1)  # supposed to reset value
    assert (
        forecasting_env.datastore.forecasted_data == []
        and forecasting_env.datastore.last_known_value == DEFAULT_FORECASTING_LAST_KNOWN_VALUE
    )


def test_evaluation_end_to_end_doesnt_crash_vllm(remotely_hosted_llm: VllmModel) -> None:
    FORECASTING_ENV = "forecasting"
    forecasting_env = ForecastingEnvironment(FORECASTING_ENV, llm=remotely_hosted_llm)
    forecasting_scorer = ForecastingScorer()

    # a task has a task_id, description, and extra parameters needed to set the environment for the task or to do scoring
    tasks = [
        EvaluationTask(
            task_id="forecasting_task_1",
            description=f"Perform time series forecasting using a horizon of {h} days. That's your only task. Let me know when that's done (I don't need to see the results, I trust you on that), and I will end the conversation.",
            scorers=[forecasting_scorer],
            task_kwargs={"forecasting_horizon": h},
        )
        for h in [3, 6]
    ]

    evaluator = AssistantEvaluator(
        environment=forecasting_env,
        max_conversation_rounds=1,
    )

    results = evaluator.run_benchmark(tasks, N=1)
