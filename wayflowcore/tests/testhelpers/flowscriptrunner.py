# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
import time
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore._utils.print import bcolors
from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.executors._flowconversation import FlowConversation
from wayflowcore.executors.executionstatus import FinishedStatus
from wayflowcore.messagelist import Message, MessageType
from wayflowcore.models.llmmodel import LlmModel, Prompt

from ..testhelpers.dummy import DummyModel

logger = logging.getLogger(__name__)


class FlowScriptCheck(ABC):
    @abstractmethod
    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        pass


class AnswerCheck(FlowScriptCheck):
    def __init__(self, check: Union[str, Callable[[str], bool]], index: int = -1) -> None:
        """
        Checks that some conversation message contains some value / the passed function returns True when called on it.

        Parameters
        ----------
        check:
            Either a string that is contained in answer or a callable on the str answer. Insensitive to case.
        index:
            Index of which message in the conversation to check. Defaults to last message of the conversation.

        Example
        -------
        >>> from ..testhelpers.flowscriptrunner import AnswerCheck
        >>> check = AnswerCheck('Bern')  # check whether `Bern` is contained in the last conversation message
        >>> check = AnswerCheck(lambda answer: 'bern' in answer or 'zurich' in answer)  # check whether `bern` or `zurich` is contained in the last conversation message

        """
        # just setting one already for typing
        self.check: Callable[[str], bool] = lambda x: True

        if callable(check):
            self.check = check
            self.check_str = "custom_func"
        elif isinstance(check, str):
            self.check = lambda x: check.lower() in x.lower()
            self.check_str = check
        else:
            raise ValueError("Check should be str or Callable")
        self.index = index

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        return self.check(conversation.get_messages()[self.index].content)

    def __repr__(self) -> str:
        return f"AnswerCheck({self.check_str}, index={self.index})"

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        return f"Answer was: {conversation.get_messages()[self.index].content}, but expected {self.check_str}"


class IODictCheck(FlowScriptCheck):
    """
    Checks that the conversation IO dict contains some value (to check flow outputs).

    Parameters
    ----------
    check:
        Either a string that is contained in the value or a callable. Insensitive to case
    key:
        Output variable name under which to apply the check
    """

    def __init__(
        self,
        check: Union[str, Callable[[str], bool]],
        key: Tuple[str, str],
        _check_mapped_flow_output: bool = True,
    ) -> None:
        # just setting one already for typing
        self.check: Callable[[str], bool] = lambda x: True
        # For backward compatibility, support for `output_mapping` is preserved. In particular,
        # IODictCheck by default has `_check_mapped_flow_output=True` which is not anymore
        # checking the content of the io-dict, but is checking the flow_output which is what the
        # io-dict used to be before `DataFlowEdge` were introduced and changed the structure of
        # the io-dict
        self._check_mapped_flow_output = _check_mapped_flow_output

        if callable(check):
            self.check = check
            self.check_str = "custom_func"
        elif isinstance(check, str):
            self.check = lambda x: check.lower() in x.lower()
            self.check_str = check
        else:
            raise ValueError("Check should be str or Callable")
        self.key = key

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        io_dict = self._get_io_dict(conversation)
        if self.key in io_dict:
            return self.check(io_dict[self.key])
        else:
            raise KeyError(
                f"IODictCheck failed due to missing key '{self.key}', available keys are: "
                f"{list(io_dict.keys())}"
            )

    def _get_io_dict(self, conversation: Conversation) -> Dict[Any, Any]:
        if self._check_mapped_flow_output:
            if not isinstance(conversation, FlowConversation):
                raise TypeError(
                    f"Conversation is of type '{type(conversation)}', but use of "
                    f"_check_mapped_flow_output=True indicates the conversation should be of type:"
                    f"'{FlowConversation.__name__}"
                )
            return conversation.state._flow_output_value_dict
        else:
            if not isinstance(conversation, FlowConversation):
                logger.warning("Trying to access the I/O dict but the state is not a Flow state")
                return {}
            return conversation.state.input_output_key_values

    def __repr__(self) -> str:
        return f"IODictCheck({self.check_str}, key={self.key})"

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        io_dict = self._get_io_dict(conversation)
        return f"IODict was: {io_dict[self.key]}, but expected {self.check_str}"


class AssistantCheck(FlowScriptCheck):
    def __init__(self, check: Union[str, Callable[[ConversationalComponent], bool]]) -> None:
        if callable(check):
            self.check = check
            self.check_str = "custom_func"
        else:
            raise ValueError("Argument 'check' should be str or Callable")

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        return self.check(assistant)

    def __repr__(self) -> str:
        return f"AssistantCheck({self.check_str})"

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        return f"Assistant dict is: {assistant.__dict__}"


class ConversationCheck(FlowScriptCheck):
    def __init__(self, check: Callable[[Conversation], bool]) -> None:
        """
        Checks that the "check" that the conversation returns will be successful on the conversation

        Parameters
        ----------
        check:
            Callable that should return True if check is successful on the conversation
        """
        self.check = check
        self.check_str = "custom_func"

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        return self.check(conversation)

    def __repr__(self) -> str:
        return f"ConversationCheck({self.check_str})"

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        return f"Conversation dict is: {conversation.__dict__}"


@dataclass
class MessageCheck(FlowScriptCheck):
    def __init__(self, check: Union[str, Callable[[List[Message]], bool]]):
        self.check: Callable[[List[Message]], bool] = lambda messages: True
        if callable(check):
            self.check = check
            self.check_str = "custom_func"
        elif isinstance(check, str):
            self.check_str = check
            self.check = lambda messages: messages[-1].content == self.check_str
        else:
            raise ValueError("Check should be str or Callable")

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        return self.check(conversation.get_messages())

    def __repr__(self) -> str:
        return f"MessageCheck({self.check_str})"

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        return f"Messages list: {conversation.get_messages()}"


@dataclass
class StepExecutionCheck(FlowScriptCheck):
    step_names: List[str]

    def __call__(self, assistant: ConversationalComponent, conversation: Conversation) -> bool:
        if not isinstance(conversation, FlowConversation):
            raise ValueError(
                f"Conversation should be of type `FlowConversation` but was {type(conversation)}"
            )
        return set(self.step_names).issubset(set(conversation._step_history))

    def _debug(self, assistant: ConversationalComponent, conversation: Conversation) -> str:
        if not isinstance(conversation, FlowConversation):
            raise ValueError(
                f"Conversation should be of type `FlowConversation` but was {type(conversation)}"
            )
        return f"Step history is: {conversation._step_history}, wanted: {self.step_names}"


@dataclass
class FlowScriptInteraction:
    """Dataclass to represent an interaction

    Parameters
    ----------
    user_input:
        String with which the assistant is prompted. Set it to None if no user input
    can_be_rephrased:
        Whether to rephrase the user input (to enhance robustness) or keep the default text
    checks:
        List of checks to apply. Any function that takes an assistant and a conversation as input and returns a bool
    setup:
        Functions to run prior to calling the assistant, to set up a dummy LLM for example
    is_last:
        Whether this should be the last interaction before the assistant finishes
    """

    user_input: Optional[str]
    can_be_rephrased: bool = False
    checks: Optional[List[FlowScriptCheck]] = None
    setup: Optional[List[Callable[[ConversationalComponent], None]]] = None
    is_last: Optional[bool] = None


def setup_llm_generation_if_dummy(
    llm: LlmModel,
    next_outputs: Union[
        str, List[str], Dict[Optional[str], str], Message, Dict[Optional[str], Message]
    ],
) -> Callable[[Any], Any]:
    if isinstance(llm, DummyModel):
        # the variable helps mypy
        dummy_llm: DummyModel = llm
        return lambda _: dummy_llm.set_next_output(next_outputs)

    return lambda _: None


@dataclass
class FlowScript:
    """
    Dataclass to represent a test script with interactions.

    Parameters
    ----------
    name:
        Name of the script, to be able to differentiate them in the results
    interactions:
        List of interactions that need to happen in order
    """

    name: str = ""
    interactions: List[FlowScriptInteraction] = field(default_factory=list)


REPHRASING_TEMPLATE = """‍Your purpose is to paraphrase text. I will provide you with text, and then you will change up the words, the sentence structure, \
add or remove figurative language, etc and change anything necessary in order to paraphrase the text. \
However, it is extremely important you do not change the original meaning/significance of the text.

Follow this format:
input: I love reading
output: Reading is a passion of mine.

Begin!
input: {{user_input}}
output: """


def rephrase_flow_script(
    flow_script: FlowScript, rephrasing_model: LlmModel, N: int = 5
) -> List[FlowScript]:
    """
    Creates similar scripts by rephrasing user inputs that can be rephrased.

    Parameters
    ----------
      flow_script: FlowScript
        flow script that needs to be tested.
      N: int
        Number of duplicated script to create.
    Returns
    -------
        List[FlowScript]
    """
    new_scripts = [flow_script]
    for i in range(N - 1):
        new_script = deepcopy(flow_script)
        new_script.name += f"-{i}"
        for inter in new_script.interactions:
            if inter.can_be_rephrased:
                completion = rephrasing_model.generate(
                    prompt=Prompt(
                        messages=[
                            Message(
                                render_template(
                                    template=REPHRASING_TEMPLATE,
                                    inputs=dict(user_input=inter.user_input),
                                ),
                                message_type=MessageType.USER,
                            )
                        ],
                        tools=None,
                        response_format=None,
                    )
                )
                inter.user_input = completion.message.content
        new_scripts.append(new_script)
    return new_scripts


AssistantOrFactory = Union[ConversationalComponent, Callable[[], ConversationalComponent]]


def _format_failure_message(
    message: List[Message],
    interaction_idx: int,
    user_input: str,
    answer: str,
    checks_success: Optional[List[bool]],
    checks_log: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> str:
    formatted_checks_log = "\n".join(
        [f"  - {success}: {log}" for success, log in zip(checks_success or [], checks_log or [])]
    )
    return f"""Interaction {interaction_idx} was unsuccessful:
- User input: {user_input}
- Answer: {answer}
- Messages: {message}
- Checks:
{formatted_checks_log}
- Failure: {error}"""


class FlowScriptRunner:
    def __init__(
        self,
        assistants: Sequence[AssistantOrFactory],
        flow_scripts: List[FlowScript],
    ) -> None:
        """
        Runner class to write fixed flow tests, where a fixed and expected list of interactions is happening.

        Parameters
        -----------
        assistants:
            Assistants on which to run the scripts.
        flow_scripts:
            Flow scripts on which the assistants need to be tested.

        Example
        --------
        >>> from wayflowcore.flow import Flow
        >>> from ..testhelpers.flowscriptrunner import FlowScript, FlowScriptInteraction, FlowScriptRunner, AnswerCheck
        >>> from wayflowcore.steps import OutputMessageStep, InputMessageStep
        >>> assistant = Flow.from_steps([
        ...     InputMessageStep('What is the capital of Switzerland?'),
        ...     OutputMessageStep('Thanks for telling me that the capital of Switzerland is {{ user_provided_input }}')
        ... ])
        >>> script = FlowScript(
        ...     interactions=[
        ...         FlowScriptInteraction(user_input=None),  # calling the assistant to get the question
        ...         FlowScriptInteraction(
        ...                user_input="Bern",  # answering the assistant's question
        ...                checks=[AnswerCheck("the capital of Switzerland is Bern")]
        ...         ),
        ...     ]
        ... )
        >>> runner = FlowScriptRunner(assistants=[assistant], flow_scripts=[script])
        >>> df = runner.execute()

        """
        self.assistants = assistants
        self.flow_scripts = flow_scripts

    @staticmethod
    def execute_single_script(
        conversation: Conversation,
        flow_script: FlowScript,
        assistant: ConversationalComponent,
        raise_exceptions: bool,
    ) -> pd.DataFrame:
        interactions = []
        for inter_idx, interaction in enumerate(flow_script.interactions):

            user_input = interaction.user_input
            success = False
            checks_list, error, debug_logs, answer, duration = None, None, None, None, None

            try:
                start = time.time()
                if interaction.setup:
                    for setup_step in interaction.setup:
                        setup_step(assistant)

                logger.info(
                    bcolors.OKCYAN + f"Calling the assistant with: {user_input}" + bcolors.ENDC
                )
                if user_input is not None:
                    conversation.append_message(
                        Message(content=user_input, message_type=MessageType.USER)
                    )
                status = assistant.execute(conversation)
                finished = isinstance(status, FinishedStatus)

                last_message = conversation.get_last_message()
                if last_message is None:
                    raise ValueError("no last message")

                answer = last_message.content
                duration = time.time() - start
                logger.info(
                    bcolors.OKGREEN + f"The assistant answered with: {answer}" + bcolors.ENDC
                )

                checks_list = [
                    check(assistant, conversation) for check in (interaction.checks or [])
                ]
                debug_logs = [
                    check._debug(assistant, conversation) if hasattr(check, "_debug") else "no logs"
                    for check in (interaction.checks or [])
                ]
                success = all(checks_list)

                if interaction.is_last is not None:
                    checks_list.append(finished == interaction.is_last)
            except Exception as e:
                answer = None
                checks_list = None
                success = False
                error = e
                if raise_exceptions:
                    raise e

            if raise_exceptions:
                if not success:
                    raise ValueError(
                        _format_failure_message(
                            conversation.get_messages(),
                            inter_idx,
                            interaction.user_input or "MISSING_USER_INPUT",
                            answer or "MISSING_ANSWER",
                            checks_list,
                            checks_log=debug_logs,
                        )
                    ) from error

            interactions.append(
                {
                    "interaction": inter_idx,
                    "succeeded": success,
                    "user_input": user_input,
                    "answer": answer,
                    "checks": checks_list,
                    "error": error,
                    "debug": debug_logs,
                    "duration": duration,
                }
            )

        return pd.DataFrame(interactions)

    def execute(
        self,
        raise_exceptions: bool = False,  # used for test to crash when not following given script
        N: int = 1,
    ) -> pd.DataFrame:
        """
        Runs the flow script on all assistants and return the reports

        Parameters
        ----------
        raise_exceptions:
            Throw exceptions when an interaction report is not successful or and exception is thrown by the assistant
        N:
            Number of runs per assistant to do.

        Returns
        -------
          pd.DataFrame
        """
        reports = []

        for flow_script in self.flow_scripts:
            for seed in range(N):
                for assistant_idx, assistant in enumerate(self.assistants):
                    if callable(assistant) and not isinstance(assistant, ConversationalComponent):
                        assistant = assistant()
                    conversation = assistant.start_conversation()

                    df = FlowScriptRunner.execute_single_script(
                        conversation, flow_script, assistant, raise_exceptions=raise_exceptions
                    )
                    df["seed"] = seed
                    df["run"] = flow_script.name
                    df["assistant"] = assistant_idx

                    reports.append(df)

        concatenated_reports: pd.DataFrame = pd.concat(reports)
        return concatenated_reports
