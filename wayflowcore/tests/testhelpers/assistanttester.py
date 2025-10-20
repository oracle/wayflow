# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.evaluation.assistantevaluator import (
    _POST_SCRIPT_INTERACTION,
    run_proxy_agent_conversation,
)
from wayflowcore.messagelist import Message

logger = logging.getLogger(__name__)


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
    return f"""Interaction {interaction_idx} was unsuccessful:
- User input: {user_input}
- Answer: {answer}{checks_log_formatted}
- Failure: {error}
- Full conversation: {messages}
"""


class AssistantTester:
    """
    `AssistantTester` is a class that tests LLM-based Assistants that complete tasks in an end-to-end matter.
    There is an assistant under test, and another assistant to simulate the human user
    and interact with the other one to help it complete the task.
    It represents one test case, i.e., one conversation with multiple rounds,
    which can be repeated multiple times to address the non-deterministic nature of LLMs.
    A test case is considered passed if the conversation, when repeated N times, has a sufficient success rate determined by an argument.
    A conversation is considered successful if it passes user-defined outcome checks (checking the final outcome of the conversation,
    especially if tools were used) and there are no exceptions thrown.
    """

    def __init__(
        self,
        assistant_under_test: ConversationalComponent,
        human_proxy: Optional[ConversationalComponent] = None,
        init_human_messages: Optional[List[str]] = None,
        required_checks: Optional[
            List[Callable[[ConversationalComponent, Conversation, Optional[Conversation]], bool]]
        ] = None,
        env_state_resetter: Optional[Callable[[], None]] = None,
        max_rounds: int = 10,
    ) -> None:
        """
        Build a new AssistantTester, representing one test case.

        Parameters
        ----------
        assistant_under_test:
            The assistant being tested
        human_proxy:
            The assistant that simulates a human and helps `assistant_under_test` complete its task (e.g., by answering 'yes' to its questions).
            If not passed, only scripted messages from init_human_messages are used.
        init_human_messages:
            Initial human messages to start and ground the conversation.
            If this is not provided, it might be challenging for the `human_proxy` to generate the right first messages.
        required_checks:
            User-defined callables to verify the final outcome of the conversation. These checks can verify the correctness of environment state
            (obtained after tool execution), or verify properties of the `Conversation`s.
            These callables can be arbitrary, as long as the first arg is the `assistant_under_test`,
            the second arg is the `Conversation` started by `assistant_under_test`,
            and the third arg is the `Conversation` started by `human_proxy`.
        env_state_resetter:
            An arbitrary callable to reset the environment state after each conversation.
            This is very helpful if `assistant_under_test` can call tools that alter the state (e.g. databases, html codes)
        max_rounds:
            The maximum number of assistant-proxy rounds in the conversation. This is in addition to the `init_human_messages`,
            so the actual maximum number of rounds is `len(init_human_messages)+max_rounds`.
            If `human_proxy` is None, this argument will be ignored (effectively = 0).
            One round is one interaction from both parties (`human_proxy`, `assistant_under_test`).
            In each of the `assistant_under_test`'s interactions, it can emit an arbitrary number of messages,
            but the `human_proxy` should only emit one message.

        Example
        -------
        >>> from wayflowcore.agent import Agent
        >>> from .flowscriptrunner import AnswerCheck
        >>> from .assistanttester import AssistantTester, get_last_agent_message
        >>>
        >>> assistant = Agent(llm)
        >>> human_proxy = Agent(llm, custom_instruction="You are a user. You need to find out the capital of Switzerland")
        >>>
        >>> def outcome_check(assistant, assistant_conv, human_proxy_conv):
        ...    return "weather" in get_last_agent_message(assistant_conv).content # checks for the last message (not an internal message like HISTORY_END)
        >>>
        >>> tester = AssistantTester(
        ...    assistant_under_test=assistant,
        ...    init_human_messages=[
        ...        "what is the capital of Switzerland?",  # query str containing the task to solve
        ...    ],
        ...    human_proxy=human_proxy,
        ...    required_checks=[outcome_check],
        ...    max_rounds=1,
        ... )
        >>> passed = tester.run_test(N=1, pass_threshold=0.0)

        """
        self.assistant = assistant_under_test
        self.human_proxy = human_proxy
        self.init_human_messages = init_human_messages or []
        self.checks = required_checks or []
        self.env_state_resetter = env_state_resetter
        self.max_rounds = max_rounds

    def _run_conversation(
        self,
        assistant_conv: Conversation,
        assistant: ConversationalComponent,
        human_proxy_conv: Optional[Conversation] = None,
        human_proxy: Optional[ConversationalComponent] = None,
        only_agent_msg_type: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Runs a conversation once. In this implementation, the human_proxy begins the conversation first,
        then the assistant, then the human_proxy, etc.
        """

        def final_check_function(_succeeded: bool) -> bool:
            outcome_check_results = [
                check(self.assistant, assistant_conv, human_proxy_conv) for check in self.checks
            ]
            _succeeded = _succeeded and all(outcome_check_results)

            if self.env_state_resetter is not None:
                self.env_state_resetter()

            return _succeeded

        return run_proxy_agent_conversation(
            assistant_conversation=assistant_conv,
            assistant=assistant,
            max_conversation_rounds=self.max_rounds,
            only_agent_msg_type=only_agent_msg_type,
            raise_exceptions=False,
            human_conversation=human_proxy_conv,
            human_proxy=human_proxy,
            init_human_messages=self.init_human_messages,
            final_check_function=final_check_function,
        )

    def run_test(
        self, N: int = 1, pass_threshold: float = 0.5, only_agent_msg_type: bool = True
    ) -> Tuple[float, pd.DataFrame]:
        """Runs a conversation `N` times, with `pass_threshold` being the proportion of successful runs to pass the test
        (passing all the outcome checks and not exceptions)

        Parameters
        ----------
        N:
            How many times to run the conversation
        pass_threshold:
            The proportion of successful runs to pass the test
        only_agent_msg_type:
            If True, only appends to the `human_proxy` MessageType.AGENT messages from `assistant_under_test`,
            otherwise, also appends THOUGHT and TOOL_REQUEST messages

        Returns
        -------
            accuracy, DataFrame of logs after each round
        """
        if not 0 <= pass_threshold <= 1:
            raise ValueError(f"pass_threshold must be between 0 and 1 but got {pass_threshold=}")
        if N <= 0:
            raise ValueError(f"Number of conversation runs should be greater than 0, but got {N=}")
        if self.human_proxy is None:
            if len(self.init_human_messages) == 0:
                raise ValueError(
                    "`AssistantTester.human_proxy` is None and no `init_human_messages` were provided"
                )
            human_proxy_conv = None

        reports = []
        errors = []
        accuracy = []

        # repeat the conversation N times
        for seed in range(N):
            assistant_conv = self.assistant.start_conversation()
            human_proxy_conv = None
            if self.human_proxy is not None:
                human_proxy_conv = self.human_proxy.start_conversation()
            summary = self._run_conversation(
                assistant_conv=assistant_conv,
                assistant=self.assistant,
                human_proxy_conv=human_proxy_conv,
                human_proxy=self.human_proxy,
                only_agent_msg_type=only_agent_msg_type,
            )
            # logging info about the run
            summary_df = pd.DataFrame(summary)
            summary_df["seed"] = seed
            reports.append(summary_df)
            # logic to determine if the conversation was successful or not
            accuracy.append(summary[_POST_SCRIPT_INTERACTION]["succeeded"])
            # We absorb all exceptions.
            # If there was an error, the error message would be found in the second-to-last row of summary
            if summary[_POST_SCRIPT_INTERACTION - 1]["error"] is not None:
                error = f'Run #{seed} got an exception:\n{summary[-2]["error"]}'
                errors.append(error)

        avg_accuracy = sum(accuracy) / len(accuracy)
        if avg_accuracy < pass_threshold:
            # if accuracy was less than the pass threshold, and if any errors were encountered, we raise them
            fail_message = f"This test failed as {avg_accuracy=} was smaller than {pass_threshold=}"
            if len(errors) > 0:
                fail_message += f"\nErrors encountered:"
                for e in errors:
                    fail_message += f"\n{e}"
            raise ValueError(fail_message)

        return avg_accuracy, pd.concat(reports, ignore_index=True)
