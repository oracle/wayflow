# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
import math
import os
import re
import time
import traceback
from dataclasses import dataclass
from datetime import date, datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Mapping, Optional

from wayflowcore._utils._templating_helpers import render_template
from wayflowcore.agent import Agent
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.conversationalcomponent import ConversationalComponent
from wayflowcore.flow import Flow
from wayflowcore.steps import StartStep
from wayflowcore.steps.step import Step

logger = logging.getLogger(__name__)

DISABLE_RETRY = "DISABLE_RETRY"
FLAKY_TEST_EVALUATION_MODE = "FLAKY_TEST_EVALUATION_MODE"
FLAKY_TEST_MAX_EXECUTION_TIME_PER_TEST = 20 * 60  # seconds

FLAKY_TEST_DOCSTRING_TEMPLATE = """
    \"\"\"
    Failure rate:          {{ failed_attempts }} out of {{ total_attempts }}
    Observed on:           {{ iso_date }}
    Average success time:  {% if average_success_time %}{{ "%.2f"|format(average_success_time) }} seconds per successful attempt{% else %}No time measurement{% endif %}
    Average failure time:  {% if average_failure_time %}{{ "%.2f"|format(average_failure_time) }} seconds per failed attempt{% else %}No time measurement{% endif %}
    Max attempt:           {{ max_attempts }}
    Justification:         ({{ "%.2f"|format(failure_rate) }} ** {{ max_attempts }}) ~= {{ "%.1f"|format(expected_failure_per_100_000) }} / 100'000
    \"\"\"
"""

FLAKY_TEST_FAILURE_ERROR_MESSAGE_TEMPLATE = """
A flaky test "{{ test_name }}" failed all of the {{ max_attempts }} attempts.

⚠️ Either:
(1) Your code changes had a bug that made the test fail. In that case, simply
update your changes
(2) The test error is not due to your code changes. In that case, please
re-evaluate the failure rate of the test with the command:
$ FLAKY_TEST_EVALUATION_MODE=100 pytest {{test_file}}::{{test_name}}

⚠️ Be careful not to use a high number of repetition when evaluating models
behind APIs (e.g. OpenAI) in order not to consume too many API credits.

Find below the traceback from the error in the last test attempt:

{{ error_traceback }}
"""

FLAKY_WRONG_DOCSTRING_ERROR_MESSAGE_TEMPLATE = """
The flaky test {{test_name}} seems to have no doctstring or a docstring with an
incorrect format. You can automatically re-evaluate the failure rate of the test
and generate a suggestion for the docstring with the command:
$ FLAKY_TEST_EVALUATION_MODE=100 pytest {{test_file}}::{{test_name}}

If the test you are evaluating outputs too much logs, you can make pytest hide
these logs using the option `--show-capture=log --disable-warnings`.
"""

FLAKY_TEST_DOCSTRING_REGEX_PATTERN = r"[\s\S]*Failure rate:.*\n\s*Observed on:.*\n\s*Average success time:.*\n\s*Average failure time:.*\n\s*Max attempt:.*\n\s*Justification:.*"


def _validate_retry_decorator_docstring_format(test_func: Callable[..., Any]) -> None:
    if not test_func.__doc__ or not re.match(FLAKY_TEST_DOCSTRING_REGEX_PATTERN, test_func.__doc__):
        logger.error(
            "Failed to find a correctly formatted retry information in docstring %s",
            test_func.__doc__,
        )
        raise ValueError(
            render_template(
                template=FLAKY_WRONG_DOCSTRING_ERROR_MESSAGE_TEMPLATE,
                inputs=dict(
                    test_name=test_func.__name__,
                    test_file=test_func.__globals__["__file__"],
                ),
            )
        )


@dataclass
class FlakyTestStatistics:
    n_success: int
    n_failure: int
    total_time_success: Optional[float] = None
    total_time_failure: Optional[float] = None
    observation_date: Optional[datetime] = None

    @property
    def total_attempts(self) -> int:
        return self.n_failure + self.n_success

    @property
    def estimated_fail_rate(self) -> float:
        # We estimate the failure rate using Laplace Rule of Succession
        # See: https://en.wikipedia.org/wiki/Rule_of_succession
        # This makes the estimation of failure rate more robust. In particular
        # It does not estimate 100% success when we have 5 out of 5 successes
        return (self.n_failure + 1) / (self.n_failure + self.n_success + 2)

    @property
    def suggested_num_attempts(self) -> int:
        # We estimate the suggested number of attempts based on the objective
        # that we want strictly less than 1 in 10'000 expected failure. Thus giving
        # us the formula:
        #
        #     fail_rate ** N < 1/10'000
        #
        #  Which is transformed with a bit of mathematical magic into:
        #
        #     N > - log(10'000) / log(fail_rate)
        return math.ceil(-math.log(10_000) / math.log(self.estimated_fail_rate))

    @property
    def expected_failure_per_100_000(self) -> float:
        return 100_000 * (self.estimated_fail_rate**self.suggested_num_attempts)

    @property
    def average_success_time(self) -> Optional[float]:
        if self.n_success == 0 or self.total_time_success is None:
            return None
        return self.total_time_success / self.n_success

    @property
    def average_failure_time(self) -> Optional[float]:
        if self.n_failure == 0 or self.total_time_failure is None:
            return None
        return self.total_time_failure / self.n_failure


def _get_suggested_flaky_test_docstring(
    n_success: int, n_failure: int, time_success: float, time_failure: float
) -> str:
    """
    Generate a suggestion of docstring for a flaky based on observations obtained when
    running a test multiple times.

    Parameters
    ----------
    n_success:
        the number of successes observed
    n_failed:
        the number of failures observed
    time_success:
        the total time taken by all successful runs
    """
    test_stats = FlakyTestStatistics(n_success, n_failure, time_success, time_failure)
    suggested_docstring = render_template(
        template=FLAKY_TEST_DOCSTRING_TEMPLATE,
        inputs=dict(
            failed_attempts=test_stats.n_failure,
            total_attempts=test_stats.total_attempts,
            failure_rate=test_stats.estimated_fail_rate,
            iso_date=date.today().isoformat(),
            average_success_time=test_stats.average_success_time,
            average_failure_time=test_stats.average_failure_time,
            max_attempts=test_stats.suggested_num_attempts,
            expected_failure_per_100_000=test_stats.expected_failure_per_100_000,
        ),
    )
    return suggested_docstring


def retry_test(
    max_attempts: int = 3, wait_between_tries: int = 0
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorate a test function in order to attempt to run it again when it fails. This is
    particularly useful for tests that tend to be failing a small fraction of the time due to
    involving unreliable LLMs.

    Parameters
    ----------
    max_attempts:
        The maximum number of attempts the test will be attempted. Note than in average the test
        will be attempted `1/(1-failure_rate)` times (e.g. 1.1 times for a 10% failure rate)
    wait_between_tries:
        The number of seconds to wait after a failed attempt of the test. This can be useful for
        example for tests which make requests to remote APIs which may be rate limited.

    Examples
    --------
    You can decorate your test
    ```python
    @retry_test(max_attempts=10)
    def test_random_number_is_above_two_third():
        \"\"\"
        Failure rate:  63 out of 100
        Observed on:   2024-09-30
        Average success time:  0.00 seconds per successful attempt
        Average failure time:  0.00 seconds per failed attempt
        Max attempt:   20
        Justification: (0.63 ** 20) ~= 8.9 / 100'000
        \"\"\"
        assert random.random() > 2/3
    ```

    Notes
    -----
    The decorator can be used in combination with two environment variables:

    (1) Reevaluate the failure rate for a given test and generate a suggestion for max_attempts
    and the explanation docstring.
    Usage:
    ```bash
    $ FLAKY_TEST_EVALUATION_MODE=<repeat_count> pytest tests/<test_file>::<test_name>
    ```
    In that command, you should specify the repeat_count, test_file and test_name. Note that
    repeat_count should be large enough to get some statistical significance. In practice, a value
    of 20, 50 or 100 would be good to use. The value passed for repeat_count must be a number.

    (2) Disable all retries and run all tests
    ```bash
    $ DISABLE_RETRY=true pytest tests/
    ```
    """
    if max_attempts > 16:
        # The number 16 is chosen, because it is the number of attempts needed
        # when a test has roughly 50% failure rate, which is already quite a
        # for us to want that test in our test-suite.
        raise ValueError(
            "You are trying to set a number of attempt more than the maximum "
            "limit of 16. This is a sign that your test has a very high "
            "failure rate, and we encourage you to make the test more robust "
            "before adding it to the test suite."
        )

    if os.environ.get(DISABLE_RETRY, False):
        change_nothing_decorator = lambda func: func
        return change_nothing_decorator

    if os.environ.get(FLAKY_TEST_EVALUATION_MODE, False):
        repeat_count = int(os.environ[FLAKY_TEST_EVALUATION_MODE])

        def repeat_evaluate_and_generate_docstring_decorator(
            test_func: Callable[..., Any],
        ) -> Callable[..., Any]:
            import signal
            from types import FrameType

            from wayflowcore._utils.print import bcolors

            def _time_handler(signum: int, frame: Optional[FrameType]) -> None:
                raise TimeoutError("Max time for test execution exceeded.")

            @wraps(test_func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                success_count = 0
                failed_count = 0
                total_time_of_successful_runs = 0.0
                total_time_of_failed_runs = 0.0
                signal.signal(signal.SIGALRM, _time_handler)
                signal.alarm(FLAKY_TEST_MAX_EXECUTION_TIME_PER_TEST)
                loop_start_time = time.time()
                for _ in range(repeat_count):
                    try:
                        start_time = time.perf_counter()
                        test_func(*args, **kwargs)
                        total_time_of_successful_runs += time.perf_counter() - start_time
                        success_count += 1
                        signal.alarm(0)  # Clear alarm after successful execution
                    except TimeoutError:
                        logger.warning(
                            "Reached maximum execution time of %s minutes",
                            FLAKY_TEST_MAX_EXECUTION_TIME_PER_TEST // 60,
                        )
                        signal.alarm(0)
                        break
                    except Exception as exception_error:
                        failed_count += 1
                        total_time_of_failed_runs += time.perf_counter() - start_time
                        signal.alarm(0)
                        time.sleep(wait_between_tries)
                    if time.time() - loop_start_time > FLAKY_TEST_MAX_EXECUTION_TIME_PER_TEST:
                        break

                num_total_attempts = success_count + failed_count
                suggested_docstring = _get_suggested_flaky_test_docstring(
                    success_count,
                    failed_count,
                    total_time_of_successful_runs,
                    total_time_of_failed_runs,
                )
                timeout_message = (
                    f" (achieved {num_total_attempts} retry due to time limit of {FLAKY_TEST_MAX_EXECUTION_TIME_PER_TEST // 60:.2f} minutes)"
                    if repeat_count != num_total_attempts
                    else ""
                )
                completion_message = (
                    f"You ran the test with FLAKY_TEST_EVALUATION_MODE={repeat_count}{timeout_message}\n"
                    f"This always fails and is expected to. Nothing wrong about this failure.\n"
                    f"Find below the recommended docstring and attempt count for your test:\n\n"
                    f"{suggested_docstring}"
                )
                logger.info(bcolors.BOLD + bcolors.OKBLUE + completion_message + bcolors.ENDC)
                raise ValueError(completion_message)

            return wrapper

        return repeat_evaluate_and_generate_docstring_decorator

    def repeat_flaky_test_decorator(test_func: Callable[..., Any]) -> Callable[..., Any]:
        _validate_retry_decorator_docstring_format(test_func)

        @wraps(test_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt_count = 0
            last_error, last_error_traceback = None, None
            logger.info("Starting %s attempts for test %s", max_attempts, test_func.__name__)
            while attempt_count < max_attempts:
                try:
                    return test_func(*args, **kwargs)
                except Exception as exception_error:
                    exception_message = exception_error.__str__().split("\n", maxsplit=1)[0]
                    attempt_count += 1
                    logger.warning(
                        "Attempt [%s/%s] failed with error: %s.",
                        attempt_count,
                        max_attempts,
                        exception_message,
                    )
                    logger.info(
                        "Retrying %s new execution in %s second(s)",
                        test_func.__name__,
                        wait_between_tries,
                    )
                    if attempt_count == max_attempts:
                        last_error = exception_error
                        last_error_traceback = "".join(traceback.format_exc())
                    else:
                        time.sleep(wait_between_tries)

            raise ValueError(
                render_template(
                    template=FLAKY_TEST_FAILURE_ERROR_MESSAGE_TEMPLATE,
                    inputs=dict(
                        test_name=test_func.__name__,
                        test_file=test_func.__globals__["__file__"],
                        max_attempts=max_attempts,
                        error_traceback=last_error_traceback,
                    ),
                )
            ) from last_error

        return wrapper

    return repeat_flaky_test_decorator


def assert_equal_with_error_message(
    item1: Any, item2: Any, component_name: str, item_name: str
) -> None:
    """Help format nice assertion error messages for tester checks."""
    if item1 != item2:
        formatted_message = (
            f"{component_name} are not copies of each other, expected matching {item_name}. Got:\n"
            f"\n{item1}\n\nvs.\n\n{item2}"
        )
        raise AssertionError(formatted_message)


def assert_assistants_are_copies(
    assistant_a: ConversationalComponent,
    assistant_b: ConversationalComponent,
    check_llms: bool = True,
    check_tools: bool = True,
    check_files: bool = False,
    check_context_providers: bool = True,
    check_assistants: bool = True,
    check_flows: bool = True,
    check_flow_steps: bool = True,
    check_flow_transitions: bool = True,
    check_flow_starting_node: bool = True,
    check_flow_subflows: bool = True,
    ignore_start_step: bool = False,
) -> None:
    assert_equal_with_error_message(
        assistant_a.__class__,
        assistant_b.__class__,
        "Assistants",
        "assistant classes",
    )
    if isinstance(assistant_a, Flow) and isinstance(assistant_b, Flow):
        assert_flows_are_copies(
            assistant_a,
            assistant_b,
            check_files=check_files,
            check_flows=check_flows,
            check_steps=check_flow_steps,
            check_transitions=check_flow_transitions,
            check_starting_node=check_flow_starting_node,
            check_subflows=check_flow_subflows,
            ignore_start_step=ignore_start_step,
        )
    elif isinstance(assistant_a, Agent) and isinstance(assistant_b, Agent):
        assert_agents_are_copies(
            assistant_a,
            assistant_b,
            check_llms=check_llms,
            check_tools=check_tools,
            check_files=check_files,
            check_context_providers=check_context_providers,
            check_assistants=check_assistants,
            check_flows=check_flows,
            check_flow_steps=check_flow_steps,
            check_flow_transitions=check_flow_transitions,
            check_flow_starting_node=check_flow_starting_node,
            check_flow_subflows=check_flow_subflows,
            ignore_start_step=ignore_start_step,
        )
    else:
        raise TypeError("assistant_a and assistant_b are not assistants.")


def _assert_flows_are_copies(
    flow_a: Flow,
    flow_b: Flow,
    check_steps: bool = True,
    check_transitions: bool = True,
    check_starting_node: bool = True,
    check_subflows: bool = True,
    check_metadata: bool = False,
    ignore_start_step: bool = False,
) -> None:
    assert_equal_with_error_message(
        flow_b.__class__,
        flow_a.__class__,
        "Flows",
        "flow classes",
    )

    # Same steps
    if check_steps:

        def get_steps_to_check(flow_: Flow) -> Dict[str, Step]:
            return {
                step_name_: step_
                for step_name_, step_ in flow_.steps.items()
                if not ignore_start_step or not isinstance(step_, StartStep)
            }

        flow_a_steps_to_check = get_steps_to_check(flow_a)
        flow_b_steps_to_check = get_steps_to_check(flow_b)

        assert_equal_with_error_message(
            flow_a_steps_to_check.keys(),
            flow_b_steps_to_check.keys(),
            "Flows",
            "step names",
        )

        for step_name in flow_a_steps_to_check:
            assert_equal_with_error_message(
                flow_a.steps[step_name].__class__,
                flow_b.steps[step_name].__class__,
                "Flows",
                "step types",
            )

    def filter_empty_entries(
        dictionary: Dict[str, Mapping[str, Optional[str]]],
    ) -> Dict[str, Mapping[str, Optional[str]]]:
        return {
            key: value
            for key, value in dictionary.items()
            if ((value is not None) and len(value) > 0)
        }

    # Same transitions
    if check_transitions:

        def get_control_flow_edges_to_check(flow_: Flow) -> List[ControlFlowEdge]:
            return [
                control_flow_edge_
                for control_flow_edge_ in flow_.control_flow_edges
                if not ignore_start_step
                or (
                    not isinstance(control_flow_edge_.source_step, StartStep)
                    and not isinstance(control_flow_edge_.destination_step, StartStep)
                )
            ]

        def sort_control_flow_edges(edges: List[ControlFlowEdge]) -> List[ControlFlowEdge]:
            def sort_key_edge(control_flow_edge: ControlFlowEdge) -> str:
                sort_key = ""
                if hasattr(control_flow_edge.source_step, "_metadata"):
                    sort_key += control_flow_edge.source_step._metadata.name
                else:
                    sort_key += control_flow_edge.source_step.__class__.__name__
                if control_flow_edge.destination_step is not None:
                    if hasattr(control_flow_edge.destination_step, "_metadata"):
                        sort_key += control_flow_edge.destination_step._metadata.name
                    else:
                        sort_key += control_flow_edge.destination_step.__class__.__name__
                return sort_key

            return sorted(edges, key=sort_key_edge)

        flow_a_control_flow_edges = sort_control_flow_edges(get_control_flow_edges_to_check(flow_a))
        flow_b_control_flow_edges = sort_control_flow_edges(get_control_flow_edges_to_check(flow_b))

        for control_flow_edge_a, control_flow_edge_b in zip(
            flow_a_control_flow_edges, flow_b_control_flow_edges
        ):
            assert_equal_with_error_message(
                control_flow_edge_a.source_step.__class__,
                control_flow_edge_b.source_step.__class__,
                "Steps",
                "source step",
            )
            assert_equal_with_error_message(
                control_flow_edge_a.destination_step.__class__,
                control_flow_edge_b.destination_step.__class__,
                "Steps",
                "destination step",
            )
            assert_equal_with_error_message(
                control_flow_edge_a.source_branch,
                control_flow_edge_b.source_branch,
                "Branches",
                "source branch",
            )

    # Same starting node
    if check_starting_node and not ignore_start_step:
        assert_equal_with_error_message(
            flow_a._get_step(flow_a.begin_step_name).__class__,
            flow_b._get_step(flow_b.begin_step_name).__class__,
            "Flows",
            "source nodes",
        )

    if check_metadata:
        assert_equal_with_error_message(
            flow_a.__metadata_info__, flow_b.__metadata_info__, "Flow", "__metadata_info__"
        )

    # Recursive test over subflows
    if check_subflows:
        for step_name in flow_a.steps:
            flow_a_subflows = flow_a.steps[step_name].sub_flows()
            if flow_a_subflows is not None:
                flow_b_subflows = flow_b.steps[step_name].sub_flows()
                assert len(flow_b_subflows) == len(flow_a_subflows)

                for subflow_a, subflow_b in zip(flow_a_subflows, flow_b_subflows):
                    assert_flows_are_copies(
                        subflow_a,
                        subflow_b,
                        check_steps=check_steps,
                        check_transitions=check_transitions,
                        check_starting_node=check_starting_node,
                        check_subflows=check_subflows,
                        ignore_start_step=ignore_start_step,
                    )


def assert_flows_are_copies(
    assistant_a: Flow,
    assistant_b: Flow,
    check_files: bool = False,
    check_flows: bool = True,
    check_steps: bool = True,
    check_transitions: bool = True,
    check_starting_node: bool = True,
    check_subflows: bool = True,
    check_metadata: bool = False,
    ignore_start_step: bool = False,
) -> None:
    # Flows contain a single flow and some files, we just need to check those

    if check_flows:
        _assert_flows_are_copies(
            assistant_a,
            assistant_b,
            check_steps=check_steps,
            check_transitions=check_transitions,
            check_starting_node=check_starting_node,
            check_subflows=check_subflows,
            ignore_start_step=ignore_start_step,
            check_metadata=check_metadata,
        )


def assert_agents_are_copies(
    assistant_a: Agent,
    assistant_b: Agent,
    check_llms: bool = True,
    check_tools: bool = True,
    check_files: bool = False,
    check_context_providers: bool = True,
    check_assistants: bool = True,
    check_flows: bool = True,
    check_flow_steps: bool = True,
    check_flow_transitions: bool = True,
    check_flow_starting_node: bool = True,
    check_flow_subflows: bool = True,
    check_metadata: bool = False,
    ignore_start_step: bool = False,
) -> None:
    # We check one by one all the components of the assistants

    if check_llms:
        assert_equal_with_error_message(
            # Just check llm names for now
            assistant_a.llm.model_id,
            assistant_b.llm.model_id,
            "Agents",
            "LLM configurations",
        )

    if check_tools:
        # Just check tool names for now
        assistant_a_tools = {tool.name for tool in assistant_a.config.tools}
        assistant_b_tools = {tool.name for tool in assistant_b.config.tools}
        assert_equal_with_error_message(
            assistant_a_tools,
            assistant_b_tools,
            "Agents",
            "tools",
        )

    if check_context_providers:
        # Just check context providers names for now
        assistant_a_cps = {cp for cp in assistant_a.config.context_providers}
        assistant_b_cps = {cp for cp in assistant_b.config.context_providers}
        assert_equal_with_error_message(
            assistant_a_cps,
            assistant_b_cps,
            "Agents",
            "context providers",
        )

    if check_assistants:
        # We check that we have assistants with the same name, then we look inside assistants
        assistant_a_assistants: Dict[str, ConversationalComponent] = {
            assistant.name: assistant for assistant in (assistant_a.config.agents or [])
        }
        assistant_b_assistants: Dict[str, ConversationalComponent] = {
            assistant.name: assistant for assistant in (assistant_b.config.agents or [])
        }
        assert_equal_with_error_message(
            set(assistant_a_assistants.keys()),
            set(assistant_b_assistants.keys()),
            "Agents",
            "sub-assistants",
        )

        if check_metadata:
            assert_equal_with_error_message(
                assistant_a.__metadata_info__,
                assistant_b.__metadata_info__,
                "Agent",
                "__metadata_info__",
            )

        for assistant_name, assistant_a_assistant in assistant_a_assistants.items():
            assistant_b_assistant = assistant_b_assistants[assistant_name]
            if isinstance(assistant_a_assistant, Flow) and isinstance(assistant_b_assistant, Flow):
                assert_flows_are_copies(
                    assistant_a_assistant,
                    assistant_b_assistant,
                    check_files=check_files,
                    check_flows=check_flows,
                    check_steps=check_flow_steps,
                    check_transitions=check_flow_transitions,
                    check_starting_node=check_flow_starting_node,
                    check_subflows=check_flow_subflows,
                    check_metadata=check_metadata,
                    ignore_start_step=ignore_start_step,
                )
            elif isinstance(assistant_a_assistant, Agent) and isinstance(
                assistant_b_assistant, Agent
            ):
                assert_agents_are_copies(
                    assistant_a_assistant,
                    assistant_b_assistant,
                    check_llms=check_llms,
                    check_tools=check_tools,
                    check_files=check_files,
                    check_context_providers=check_context_providers,
                    check_assistants=check_assistants,
                    check_flows=check_flows,
                    check_flow_steps=check_flow_steps,
                    check_flow_transitions=check_flow_transitions,
                    check_flow_starting_node=check_flow_starting_node,
                    check_flow_subflows=check_flow_subflows,
                    check_metadata=check_metadata,
                    ignore_start_step=ignore_start_step,
                )
            else:
                raise TypeError(
                    "Sub-assistants of assistant_a and assistant_b are of invalid types of "
                    "combinations of types. Expected both to be Flows or Agents."
                )

    if check_flows:
        # We check that we have flows with the same name, then we look inside assistants
        assistant_a_flows = {
            described_flow.name: described_flow
            for described_flow in (assistant_a.config.flows or [])
        }
        assistant_b_flows = {
            described_flow.name: described_flow
            for described_flow in (assistant_b.config.flows or [])
        }
        assert_equal_with_error_message(
            set(assistant_a_flows.keys()),
            set(assistant_b_flows.keys()),
            "Agents",
            "assistant flows",
        )
        for flow_name, assistant_a_flow in assistant_a_flows.items():
            assert_flows_are_copies(
                assistant_a_flow,
                assistant_b_flows[flow_name],
                check_steps=check_flow_steps,
                check_transitions=check_flow_transitions,
                check_starting_node=check_flow_starting_node,
                check_subflows=check_flow_subflows,
                ignore_start_step=ignore_start_step,
                check_metadata=check_metadata,
            )

    assert_equal_with_error_message(
        assistant_a.config.initial_message,
        assistant_b.config.initial_message,
        "Agents",
        "initial message",
    )
    assert_equal_with_error_message(
        assistant_a.config.caller_input_mode,
        assistant_b.config.caller_input_mode,
        "Agents",
        "caller input mode",
    )
    assert_equal_with_error_message(
        assistant_a.config.custom_instruction,
        assistant_b.config.custom_instruction,
        "Agents",
        "custom instructions",
    )
    assert_equal_with_error_message(
        assistant_a.config.max_iterations,
        assistant_b.config.max_iterations,
        "Agents",
        "max iterations",
    )
    assert_equal_with_error_message(
        assistant_a.config.can_finish_conversation,
        assistant_b.config.can_finish_conversation,
        "Agents",
        "can_finish_conversation configuration",
    )
