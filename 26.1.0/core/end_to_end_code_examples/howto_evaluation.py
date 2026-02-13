# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# %%[markdown]
# WayFlow Code Example - How to Evaluate Assistants
# -------------------------------------------------

# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore==26.1" 
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python howto_evaluation.py
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# .. imports:
from typing import Dict

from wayflowcore.agent import Agent
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.models.llmmodel import LlmModel
from wayflowcore.evaluation import (
    AssistantEvaluator,
    EvaluationEnvironment,
    EvaluationTask,
    TaskScorer,
    HumanProxyAssistant,
)


# %%[markdown]
## Define the llm

# %%
from wayflowcore.models import VllmModel

llm = VllmModel(
    model_id="LLAMA_MODEL_ID",
    host_port="LLAMA_API_URL",
)



# %%[markdown]
## Define the environment

# %%
class MathEnvironment(EvaluationEnvironment):
    def __init__(self, env_id: str, llm: LlmModel):
        self.llm = llm
        self.assistant: ConversationalComponent = None
        self.human_proxy: HumanProxyAssistant = None
        super().__init__(env_id=env_id)

    def get_assistant(self, task: EvaluationTask) -> ConversationalComponent:
        if self.assistant is not None:
            return self.assistant

        self.assistant = Agent(
            llm=self.llm,
            custom_instruction="""The assistant is MathAssistant, tasked with answering math related questions from users.
When asked a question, the assistant should use mathematical reasoning to compute the correct answer. Remember that you have no tool for this job,
so only use your internal computation skills. The output format should be as follows:
Result: [RESULT]""",
        )
        return self.assistant

    def get_human_proxy(self, task: EvaluationTask) -> ConversationalComponent:
        if self.human_proxy is not None:
            return self.human_proxy
        self.human_proxy = HumanProxyAssistant(
            llm=self.llm,
            full_task_description=task.description,
            short_task_description=task.description,
            assistant_role="An helpful math assistant, whose job is to answer math related questions involving simple math reasoning.",
            user_role="A user having a math-related question. He wants the answer to be formatted in the following format:\nResult: [RESULT]",
        )
        return self.human_proxy

    def init_env(self, task: EvaluationTask):
        pass

    def reset_env(self, task: EvaluationTask):
        pass


math_env = MathEnvironment(env_id="math", llm=llm)



# %%[markdown]
## Define the scorer

# %%
class MathScorer(TaskScorer):
    OUTPUT_METRICS = ["absolute_error"]
    DEFAULT_SCORER_ID = "math_scorer"

    def score(
        self,
        environment: MathEnvironment,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        last_assistant_message = assistant_conversation.get_last_message().content.lower()
        if "result:" not in last_assistant_message:
            raise ValueError("Incorrect output formatting")
        assistant_answer = last_assistant_message.split("result:")[-1]
        assistant_answer = assistant_answer.split("\n")[0].replace("$", "").strip()
        assistant_answer = float(assistant_answer)
        expected_answer = task.scoring_kwargs["expected_output"]
        error = abs(expected_answer - assistant_answer)
        return {"absolute_error": error}

    def score_exceptional_case(
        self,
        environment: MathEnvironment,
        exception: Exception,
        task: EvaluationTask,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        return {"absolute_error": None}


scorers = [MathScorer(scorer_id="benefit_scorer1")]


# %%[markdown]
## Define the evaluation config

# %%
data = [
    {
        "query": "What is the answer to the question: 2+2 = ?",
        "expected_output": 4,
    },
    {
        "query": "What is the answer to the question: 2x2 = ?",
        "expected_output": 4,
    },
    {
        "query": "What is the answer to the question: 2-2 = ?",
        "expected_output": 0,
    },
    {
        "query": "What is the answer to the question: 2/2 = ?",
        "expected_output": 1,
    },
]
tasks = [
    EvaluationTask(
        task_id=f"task_{i}",
        description=question["query"],
        scorers=scorers,
        scoring_kwargs={"expected_output": question["expected_output"]},
    )
    for i, question in enumerate(data)
]

# tasks = []

# %%[markdown]
## Run the evaluation

# %%
evaluator = AssistantEvaluator(
    environment=math_env,
    max_conversation_rounds=1,
)
results = evaluator.run_benchmark(tasks, N=1)
print(results)
#   task_id  task_attempt_number  absolute_error            conversation
# 0  task_0                    0             0.0   [Message(content='...
# 1  task_1                    0             0.0   [Message(content='...
# 2  task_2                    0             0.0   [Message(content='...
# 3  task_3                    0             0.0   [Message(content='...
