# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import time
import traceback
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import pandas as pd

from wayflowcore import Agent
from wayflowcore._utils._templating_helpers import render_str_template_partially
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.evaluation.taskscorer import TaskScorer
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models import LlmModel

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """Never forget you (AI chatbot) are {{ user_role }} and I (human user) am {{ assistant_role }}. \
Never flip roles! You (the chatbot) must always instruct me (the human) because I need to complete a task. \
My task is: {{ full_task_description }}. \
You must not tell me to do things beyond the scope of my task as described above.
I will start the conversation by asking 'how can I help you', and then you should start instructing me.

However, I may have trouble completing the task. \
You must consider the task failed and end the conversation by writing '<FAILED>' (also give a brief description why it failed) whenever:
(1) I apologize and decline your instruction several times;
(2) we get stuck in a conversation loop (I keep repeating the *exact* same thing multiple times in a row);
(3) I start behaving unexpectedly, e.g., when I switch my role and start ordering you or my reply contains nonsensical words;
Please be lenient to me and allow me to try again several times before terminating the conversation.
Otherwise, you must only instruct me. You must never offer to assist me. You must never apologize.
Whenever I ask you a question, you must only answer with what I am asking for; you must not say unnecessary things.

When you think my task ({{ short_task_description }}) is completed, you must end the conversation by replying 'That's all, thank you. Task completed <ENDED>'.

{%if extra_instructions != '' %}Additionally: {{ extra_instructions }}

{% endif %}\
Most importantly, you must reply with VERY SHORT instructions!"""


class HumanProxyAssistant(Agent):
    """
    `HumanProxyAssistant` is a WayFlow Assistant LLM for interacting with other assistants in place of a human developer.
    """

    def __init__(
        self,
        *,
        llm: LlmModel,
        system_prompt: Optional[str] = None,
        full_task_description: str = "",
        short_task_description: str = "",
        assistant_role: str = "",
        user_role: str = "",
        extra_instructions: str = "",
    ) -> None:
        """Build a new HumanProxyAssistant.

        Parameters
        ----------
        model_configs (`Union[str, List[LlmModel]]`):
            model configs for the LLM
        system_prompt (str, *optional*):
            The system prompt to control the behavior of the Human Proxy. It should at least provide the context of the task of the
            other assistant the proxy is interacting with. It should also instruct the proxy to generate <ENDED> if the task is completed.
            If the system prompt is not provided, the other arguments below need to be provided to render a pre-defined system prompt template.
        full_task_description (str, *optional*):
            the detailed description of the task of the assistant (e.g. help the human build an app for the plumbing store)
        short_task_description (str, *optional*):
            the brief description of the task (e.g. build an app)
        assistant_role (str, *optional*):
            the persona of the assistant (e.g. a software engineer)
        user_role (str, *optional*):
            the persona of the human user, of which the LLM is a proxy (e.g. a busy manager of a plumbing store)
        extra_instructions (str, *optional*):
            extra instructions to the LLM, usually to tell it to only respond in certain ways like only yes/no
            will be inserted to the system prompt at the end

        Example
        -------

        >>> from wayflowcore.evaluation import HumanProxyAssistant
        >>> human_proxy = HumanProxyAssistant(
        ...     llm=llm,
        ...     full_task_description="to provide you with the current general weather (breezy, warm, snowy, etc.) in the largest city of Switzerland (don't tell me which one).",
        ...     short_task_description="get the weather in the largest city of Switzerland",
        ...     assistant_role="a weather reporter",
        ...     user_role="a news viewer"
        ... )

        """
        if system_prompt is not None:
            if (
                full_task_description
                or short_task_description
                or assistant_role
                or user_role
                or extra_instructions
            ):
                raise ValueError(
                    (
                        "Either only provide the system prompt and not any other arguments, "
                        "or do not provide the system prompt but provide other arguments"
                    )
                )
        extra_instructions = extra_instructions or ""
        self.system_prompt = system_prompt or render_str_template_partially(
            _SYSTEM_PROMPT,
            {
                "user_role": user_role.strip(),
                "assistant_role": assistant_role.strip(),
                "full_task_description": full_task_description.strip(),
                "short_task_description": short_task_description.strip(),
                "extra_instructions": extra_instructions.strip(),
            },
        )
        super().__init__(
            llm=llm,
            custom_instruction=self.system_prompt,
            _filter_messages_by_recipient=False,
        )


@dataclass
class AssistantEvaluationResult:
    task_id: str
    task_attempt_number: int
    messages: Optional[List[Message]]
    metrics_dict: Dict[str, float]


@dataclass
class EvaluationTask:
    """
    Class representing a Task for the LLM assistant to solve.

    Parameters
    ----------
    task_id:
        name of the task
    description:
        description of the task, to be provided to the LLM
    scorers:
        list of scorers to compute metrics after execution of the LLM conversation.
        Note that each scorer can compute several metrics, but these metrics
        must be unique across scorers across all tasks, otherwise an exception is raised during the evaluation.
    task_kwargs:
        arbitrary dict containing any additional task information for the assistant to solve
    scoring_kwargs:
        arbitrary dict containing any additional task information for the scoring (e.g, ground-truth answers, expected results)
    """

    task_id: str
    description: str
    scorers: List[TaskScorer]
    task_kwargs: Dict[str, Any] = field(default_factory=dict)
    scoring_kwargs: Dict[str, Any] = field(default_factory=dict)

    def score(
        self,
        environment: "EvaluationEnvironment",
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        scores = {}
        for scorer in self.scorers:
            metric_dict = scorer.score(
                environment=environment,
                task=self,
                assistant=assistant,
                assistant_conversation=assistant_conversation,
            )
            scores.update(metric_dict)
        return scores

    def score_exceptional_case(
        self,
        environment: "EvaluationEnvironment",
        exception: Exception,
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        scores = {}
        for scorer in self.scorers:
            metric_dict = scorer.score_exceptional_case(
                environment=environment,
                exception=exception,
                task=self,
                assistant=assistant,
                assistant_conversation=assistant_conversation,
            )
            scores.update(metric_dict)
        return scores

    def __post_init__(self) -> None:
        metrics = set()
        for scorer in self.scorers:
            for m in scorer.OUTPUT_METRICS:
                if m in metrics:
                    raise ValueError(
                        f"Metrics must be unique across scorers, but metric '{m}' is duplicated!"
                    )
                metrics.add(m)
        self.metrics = metrics


class EvaluationEnvironment(ABC):

    def __init__(self, env_id: str) -> None:
        """
        `EvaluationEnvironment` is the abstract class to provide the entry points
        needed for the `AssistantEvaluator`. It is responsible for setting up
        assistants for a given task, as well as properly setting the environment
        before and after evaluating the assistant on a task.
        """
        self.env_id = env_id
        super().__init__()

    def __repr__(self) -> str:
        combined = ", ".join(f"{attr}={value}" for attr, value in self.__dict__.items())
        return f"{self.__class__.__name__}({combined})"

    @abstractmethod
    def get_assistant(self, task: EvaluationTask) -> ConversationalComponent:
        """Creates the assistant for the task (or re-use a specific one already created by the environment)"""

    @abstractmethod
    def get_human_proxy(self, task: EvaluationTask) -> Optional[HumanProxyAssistant]:
        """Creates the human proxy for the task (or re-use a specific one already created by the environment)"""

    @abstractmethod
    def init_env(self, task: EvaluationTask) -> None:
        """Method called before the run of every task to set/reset the environment"""

    @abstractmethod
    def reset_env(self, task: EvaluationTask) -> None:
        """Method called after the run of every task to set/reset the environment"""

    def termination_check(self, human_conversation: Conversation) -> bool:
        """Method called within the assistant-human proxy conversation loop to determine
        when the conversation should terminate, basically checking for, e.g., trigger words, in the
        `human_conversation` (the same as the assistant conversation but switched roles, see AssistantTester).
        If not overridden, the default is to check if the human proxy utters '<ENDED>' or '<FAILED>'.
        """
        return _default_termination_check(human_conversation)


class AssistantEvaluator:
    TASK_ID_COLUMN_NAME = "task_id"
    TASK_ATTEMPT_NO_COLUMN_NAME = "task_attempt_number"

    def __init__(
        self,
        environment: Union[EvaluationEnvironment, Callable[[], EvaluationEnvironment]],
        metrics: Optional[List[str]] = None,
        max_conversation_rounds: int = 10,
    ):
        """
        Class used to run the task evaluations

        Parameters
        ----------
        environment:
            The environment for this evaluation, or a lambda (no args) that returns a new environment instance.
            If you want to run multiple conversations in parallel, you must provide a lambda here.
        metrics:
            The name of the metrics that need to be provided by the scorers.
            If not provided, by default will use all metrics from all the scorers passed to the EvaluationTasks
        max_conversation_rounds:
            The maximum number of conversation rounds per task.
        """

        self._environment = environment
        self.metrics = metrics
        self.max_conversation_rounds = max_conversation_rounds

    def _run_one_benchmark_attempt_on_task(
        self,
        task: EvaluationTask,
        task_attempt_number: int,
        raise_exceptions: bool = False,
    ) -> AssistantEvaluationResult:
        if callable(self._environment):
            environment = self._environment()
        else:
            environment = self._environment
        environment.init_env(task)

        assistant = environment.get_assistant(task)
        assistant_conversation = assistant.start_conversation()

        human_proxy = environment.get_human_proxy(task)
        if human_proxy is None:
            human_conversation = None
        else:
            human_conversation = human_proxy.start_conversation()

        task_metrics: Dict[str, float]
        try:
            run_proxy_agent_conversation(
                assistant_conversation=assistant_conversation,
                assistant=assistant,
                max_conversation_rounds=self.max_conversation_rounds,
                only_agent_msg_type=True,
                raise_exceptions=raise_exceptions,
                human_conversation=human_conversation,
                human_proxy=human_proxy,
                init_human_messages=[task.description],
                termination_check_function=environment.termination_check,
            )

            task_metrics = task.score(
                environment=environment,
                assistant=assistant,
                assistant_conversation=assistant_conversation,
            )

        except Exception as exception:
            task_metrics = task.score_exceptional_case(
                environment=environment,
                exception=exception,
                assistant=assistant,
                assistant_conversation=assistant_conversation,
            )

        environment.reset_env(task)

        return AssistantEvaluationResult(
            task_id=task.task_id,
            task_attempt_number=task_attempt_number,
            metrics_dict=task_metrics,
            messages=(
                None if assistant_conversation is None else assistant_conversation.get_messages()
            ),
        )

    def _retrieve_metrics_from_task_scorers(self, tasks: List[EvaluationTask]) -> List[str]:
        """If self.metrics is None, retrieves all unique metrics from all tasks.
        Since each Task has multiple scorers, and each TaskScorer has multiple metrics, this method validates that:
            - if two scorers have different scorer_ids, their list of metrics must not overlap (isdisjoint)
            - if two scorers have the same scorer_id, their list of metrics must be exactly the same
        """
        output_metrics_per_scorer: Dict[str, Set[str]] = {}
        for task in tasks:
            for scorer in task.scorers:
                new_metrics = set(scorer.OUTPUT_METRICS)
                if scorer.scorer_id not in output_metrics_per_scorer:
                    # different scorer_ids returns different metrics
                    for existing_scorer_id, existing_metrics in output_metrics_per_scorer.items():
                        if not new_metrics.isdisjoint(existing_metrics):
                            raise ValueError(
                                f"Metric {new_metrics} returned by scorer {scorer.scorer_id} "
                                f"is not unique across scorers from different tasks, "
                                f"found scorer {existing_scorer_id} with {existing_metrics}"
                            )
                    output_metrics_per_scorer[scorer.scorer_id] = new_metrics
                else:
                    # each scorer_id returns consistent metrics
                    existing_metrics = output_metrics_per_scorer[scorer.scorer_id]
                    if new_metrics != existing_metrics:
                        raise ValueError(
                            f"TaskScorer {scorer.scorer_id} has different metrics across tasks: {new_metrics} vs {existing_metrics}"
                        )
        all_metrics_names = [m for metrics in output_metrics_per_scorer.values() for m in metrics]
        return all_metrics_names

    def run_benchmark(
        self,
        tasks: List[EvaluationTask],
        N: int,
        raise_exceptions: bool = False,
        _max_concurrency: int = 1,
    ) -> pd.DataFrame:
        """
        Runs all the tasks N times, returning a dataframe with the resulting
        scores for each task round. NaNs values indicate task failures.

        Parameters
        ----------
        tasks:
            List of tasks to run the benchmark on.
        N:
            Number of times to run each task
        raise_exceptions:
            Whether to raise exceptions (for testing) or just mark them as errors (benchmarking)
        """
        if self.metrics is not None:
            all_metrics = set([metric_name for task in tasks for metric_name in task.metrics])
            if not set(self.metrics).issubset(all_metrics):
                raise ValueError(
                    f"This evaluator's list of metrics {self.metrics} must be a subset of all metrics across all tasks: {all_metrics}"
                )
        else:
            self.metrics = self._retrieve_metrics_from_task_scorers(tasks)

        results: List[AssistantEvaluationResult] = []
        if _max_concurrency > 1:
            if not callable(self._environment):
                raise ValueError(
                    "You asked to launch parallel runs, but you only passed in a single environment object, "
                    "potentially leading to race conditions. If you wish to run in parallel, "
                    "please pass a lambda returning a new copy of the env when initializing the AssistantEvaluator"
                )
            _thread_runner = lambda task_and_trial: self._run_one_benchmark_attempt_on_task(
                task=task_and_trial[0],
                task_attempt_number=task_and_trial[1],
                raise_exceptions=raise_exceptions,
            )
            with ThreadPoolExecutor(max_workers=_max_concurrency) as executor:
                batch_results = list(
                    executor.map(
                        _thread_runner,
                        [
                            (task, task_attempt_number)
                            for task_attempt_number in range(N)
                            for task in tasks
                        ],
                    )
                )
                results.extend(batch_results)
        else:
            results.extend(
                [
                    self._run_one_benchmark_attempt_on_task(
                        task, task_attempt_number, raise_exceptions=raise_exceptions
                    )
                    for task_attempt_number in range(N)
                    for task in tasks
                ]
            )

        column_names = [
            self.TASK_ID_COLUMN_NAME,
            self.TASK_ATTEMPT_NO_COLUMN_NAME,
        ]
        if self.metrics is not None:
            column_names.extend(self.metrics)
        if any(r.messages is not None for r in results):
            column_names.append("conversation")

        results_as_dict_for_pandas = [
            {
                "conversation": r.messages,
                self.TASK_ATTEMPT_NO_COLUMN_NAME: r.task_attempt_number,
                self.TASK_ID_COLUMN_NAME: r.task_id,
                **r.metrics_dict,
            }
            for r in results
        ]
        results_df = pd.DataFrame(results_as_dict_for_pandas, columns=column_names)
        return results_df


def run_proxy_agent_conversation(
    *,
    assistant: ConversationalComponent,
    max_conversation_rounds: int,
    only_agent_msg_type: bool = True,
    raise_exceptions: bool = False,
    assistant_conversation: Optional[Conversation] = None,
    human_conversation: Optional[Conversation] = None,
    human_proxy: Optional[ConversationalComponent] = None,
    init_human_messages: Optional[List[str]] = None,
    final_check_function: Optional[Callable[[bool], bool]] = None,
    termination_check_function: Optional[Callable[[Conversation], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Runs a conversation once. In this implementation, the human_proxy begins the conversation first,
    then the assistant, then the human_proxy, etc.

    Parameters
    ----------
    assistant:
        component on which to run the conversation
    max_conversation_rounds:
        max number of rounds of conversations
    only_agent_msg_type:
        messages of the agent to show to the proxy
    raise_exceptions:
        whether to raise exceptions or just record them
    assistant_conversation:
        potential conversation to continue for the component
    human_conversation:
        potential conversation of the proxy to continue
    human_proxy:
        proxy to use for the conversation
    init_human_messages:
        scripted initial interactions for the proxy
    final_check_function:
        callable to return True or False depending on if the conversation was a success or not
    termination_check_function:
        callable to find out if the conversation should be stopped or not
    """
    from wayflowcore.flow import Flow

    summary = []

    agent_messages: Optional[List[str]] = None
    current_agent_chat_history_len = 0
    agent_finished = False
    should_end_loop = False
    should_conversation_terminate = termination_check_function or _default_termination_check
    user_input = None

    init_human_messages = init_human_messages or []

    if (
        len(init_human_messages) > 0
        and init_human_messages[0] is not None
        # only flow assistant require an initial None message
        and isinstance(assistant, Flow)
    ):
        # initial interaction, could be anything, since the first assistant message is "How can I help you"
        init_human_messages = ["Placeholder"] + init_human_messages

    if assistant_conversation is None:
        assistant_conversation = assistant.start_conversation()

    n_init_human_messages = len(init_human_messages)
    num_rounds = n_init_human_messages
    if human_conversation is not None:
        num_rounds += max_conversation_rounds

    for round_idx in range(num_rounds):
        error, answers, duration = None, [], None
        try:
            if agent_messages is not None:
                # note that this is a list; the assistant_conv can emit an arbitrary number of messages per round
                # also note that from the human_proxy's perspective, it is the AGENT, and the other assistant is the USER
                for m in agent_messages:
                    if human_conversation is not None:
                        human_conversation.append_user_message(m)

            user_input, human_proxy_finished = _find_next_user_message(
                round_idx,
                init_human_messages,
                human_conversation,
                human_proxy,
                should_conversation_terminate,
            )

            # interact with the agent assistant
            if not human_proxy_finished:
                if user_input is not None:
                    assistant_conversation.append_user_message(user_input)

                start = time.time()
                conversation_as_str = [
                    f"{m.role.title()}: {m.content}" for m in assistant_conversation.get_messages()
                ]
                logger.info(f"Assistant prompted with: {conversation_as_str}")
                agent_status = assistant_conversation.execute()
                duration = time.time() - start

                agent_finished = isinstance(agent_status, FinishedStatus)

                # retrieve only new messages as outputs of the assistant
                agent_messages, current_agent_chat_history_len = _get_agent_messages(
                    assistant_conversation.get_messages(),
                    current_agent_chat_history_len,
                    only_agent_msg_type=only_agent_msg_type,
                )
                answers = agent_messages
                if agent_messages[-1] == _SCRIPTED_TOOL_CRASH_MESSAGE:
                    raise ValueError(
                        "All creative tool calls crashed until `max_iterations`, "
                        "please make sure to only use supported tools."
                    )

                for m in agent_messages:
                    logger.info(f"The assistant answered with: {m}")

            if human_proxy_finished or agent_finished:
                # logging and loop breaking logic
                should_end_loop = True
                if human_proxy_finished == agent_finished:
                    party = "BOTH"
                elif human_proxy_finished:
                    party = "USER"
                else:
                    party = "AGENT"
                logger.info(f"{party} ENDED THE CONVERSATION, END TRIGGERS ENCOUNTERED")

        except Exception as e:
            # if an error occurs, we break the loop immediately;
            # in which case, in the summary list, the round with the error will always be
            # the second-to-last round (index -2)
            if raise_exceptions:
                # raise the proper error so that we have the stacktrace
                raise e
            logger.error(
                "Encountered error during assistant execution:\n%s",
                "".join(traceback.format_exc()),
            )
            error = _format_failure_message(
                str(round_idx),
                user_input,
                answers[0] if len(answers) == 1 else answers,
                error=e,
                messages=assistant_conversation.get_messages(),
            )

            should_end_loop = True
            logger.warning(f"Interaction threw an exception, ending the conversation now:\n{error}")

        summary.append(
            {
                "interaction": round_idx,
                "user_input": user_input,
                "answer": answers[0] if answers and len(answers) == 1 else answers,
                "succeeded": None,
                "is_scripted_round": round_idx < len(init_human_messages),
                "error": error,
                "duration": duration,
            }
        )
        if should_end_loop:
            break
    else:
        logger.info(f"CONVERSATION REACHED MAX LIMIT OF {num_rounds} ROUNDS")

    succeeded = error is None

    if final_check_function:
        succeeded = final_check_function(succeeded)

    summary.append(
        {
            "interaction": _POST_SCRIPT_INTERACTION,
            "user_input": None,
            "answer": None,
            "succeeded": succeeded,
        }
    )

    if human_conversation is not None:
        for c in human_conversation.get_messages():
            logger.debug(c)

    logger.info(
        "Conversation ended. Predicted tool calls were: %s",
        [
            f"{tr.name}({tr.args})"
            for m in assistant_conversation.get_messages()
            for tr in (m.tool_requests or [])
        ],
    )

    return summary


_SCRIPTED_TOOL_CRASH_MESSAGE = "[SCRIPTED RESPONSE] [UNRECOVERABLE] multiple errors occurred while calling tools, please fail this conversation."


def _find_next_user_message(
    round_idx: int,
    init_human_messages: List[str],
    human_conversation: Optional[Conversation],
    human_proxy: Optional[ConversationalComponent],
    should_conversation_terminate: Callable[[Conversation], bool],
) -> Tuple[Optional[str], bool]:
    is_scripted_round = round_idx < len(init_human_messages)

    if is_scripted_round:
        user_input = init_human_messages[round_idx]
        logger.info(f"Calling the assistant with: {user_input}")

        if human_conversation is None:
            return user_input, False

        if user_input is not None:
            # note that this is NOT a list, the human_conversation can only emit one new message per round
            human_conversation.append_agent_message(user_input)
        return user_input, should_conversation_terminate(human_conversation)

    else:
        if human_conversation is None or human_proxy is None:
            raise ValueError(
                "Human proxy and human conversation must be provided in case of unscripted rounds."
            )
        conversation_as_str = [f"{m.role}: {m.content}" for m in human_conversation.get_messages()]
        logger.info(f"Human proxy prompted with: {conversation_as_str}")
        human_proxy_status = human_conversation.execute()
        human_proxy_finished = isinstance(human_proxy_status, FinishedStatus)
        user_input = _get_last_agent_message(human_conversation).content
        logger.info(f"Human proxy answered with: {user_input}")

        return user_input, human_proxy_finished or should_conversation_terminate(human_conversation)


_POST_SCRIPT_INTERACTION = -1


def _format_failure_message(
    interaction_idx: str,
    user_input: Optional[str],
    answer: Union[str, List[str]],
    checks_success: Optional[List[str]] = None,
    checks_log: Optional[List[str]] = None,
    error: Optional[Exception] = None,
    messages: Optional[List[Message]] = None,
) -> str:
    checks_log_formatted = "\n".join(
        [f"  - {success}: {log}" for success, log in zip(checks_success or [], checks_log or [])]
    )
    checks_log_formatted = "" if checks_log_formatted == "" else f"\n- Checks:\n{checks_log}"
    return f"""Interaction {interaction_idx} was unsucessful:
- User input: {user_input}
- Answer: {answer}{checks_log_formatted}
- Failure: {error}
- Full conversation: {messages}
"""


def _get_agent_messages(
    chat_history: List[Message], prev_len: int, only_agent_msg_type: bool = True
) -> Tuple[List[str], int]:
    """Get new agent messages in the conversation. This function should be called only after invoking the agent.

    Parameters
    ----------
    chat_history: List[Message]
        list of Messages in the current conversation
    prev_len: int
        the length of the conversation right before invoking the agent in this round
    only_agent_msg_type: bool
        whether to return only AGENT and TOOL_REQUEST message types, if False, will also append
        THOUGHT and TOOL_RESULT

    Returns
    -------
    Tuple of list, int:
        all agent messages (including thoughts and tool calls if specified) as determined by chat_history[prev_len:]
        the current length of the conversation
    """
    allowed_message_types = [MessageType.AGENT, MessageType.TOOL_REQUEST]
    if not only_agent_msg_type:
        allowed_message_types += [MessageType.THOUGHT, MessageType.TOOL_RESULT]

    current_len = len(chat_history)
    new_messages = chat_history[prev_len:]
    if len(new_messages) == 0:
        raise ValueError(
            "Agent did not produce any new message. Invoking an assistant "
            "conversation should result in at least a AGENT, THOUGHT or TOOL_REQUEST message"
        )

    new_message_contents = [
        m.content
        for m in new_messages
        if m.message_type in allowed_message_types and m.content != ""
    ]  # if it's a TOOL_REQUEST message and content is empty, it means the message is just calling the tools, check additional_kwargs

    if len(new_message_contents) == 0:
        # this case occurs if the AgentExecutionStep has run until max_iterations (specified through Agent)
        # but all the tool calls encountered errors and the assistant did not yield
        new_message_contents = [_SCRIPTED_TOOL_CRASH_MESSAGE]

    return new_message_contents, current_len


def _get_last_agent_message(conversation: Conversation) -> Message:
    try:
        return next(m for m in reversed(conversation.get_messages()) if m.role == "assistant")
    except StopIteration:
        raise ValueError("Did not find any agent messages in the conversation")


def _default_termination_check(human_conversation: Conversation) -> bool:
    end_tokens = ["<FAILED>", "<ENDED>"]
    if len(human_conversation.get_messages()) == 0:
        return False
    user_input = _get_last_agent_message(human_conversation).content
    return True if any(end_token in user_input for end_token in end_tokens) else False
