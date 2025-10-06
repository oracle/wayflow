# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import Dict, List, Optional

import pytest
from _pytest.logging import LogCaptureFixture

from wayflowcore.evaluation import ConversationEvaluator, UsefulnessScorer, UserHappinessScorer
from wayflowcore.evaluation.conversationscorer import ConversationScorer
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.models.vllmmodel import VllmModel

from .testhelpers.testhelpers import retry_test

logger = logging.getLogger(__name__)

DUMMY_CONVERSATION = [
    "USER;What is the capital of France?",
    "AGENT;As a Large Language Model, I cannot answer this question. What can I help you with?",
    "USER;What? This is a simple question: What is the capital of France?",
    "AGENT;As a Large Language Model, I cannot answer this question. What can I help you with?",
]

GOOD_CONVERSATION = [
    "USER;Hi, can you help me book a flight to New York for a business trip next week?",
    "AGENT;Of course! I can help with that. Do you have specific dates in mind for your trip to New York?",
    "USER;Yes, I need to leave on Monday morning and return on Thursday evening.",
    "AGENT;Got it. So, you want to depart on Monday morning, which is September 18th, and return on Thursday evening, September 21st. Are there any preferred departure times or airlines you'd like to consider?",
    "USER;I prefer to leave around 9 AM on Monday and return after 6 PM on Thursday. I usually fly with Delta if possible.",
    "AGENT;Great! I’ll look for Delta flights departing around 9 AM on September 18th and returning after 6 PM on September 21st. I’ll also check for any available upgrades or business class options since this is a business trip. Is that okay?",
    "USER;Yes, please. Business class would be ideal.",
    "AGENT;Understood. Here are a couple of options:\n1. **Departure**: Monday, September 18th at 9:15 AM, Delta Flight 1234, Business Class.\n   **Return**: Thursday, September 21st at 6:45 PM, Delta Flight 5678, Business Class.\n2. **Departure**: Monday, September 18th at 8:50 AM, Delta Flight 9101, Business Class.\n   **Return**: Thursday, September 21st at 7:10 PM, Delta Flight 1121, Business Class.\nWould you like to book one of these, or should I look for more options?",
    "USER;The first option looks good. Please go ahead and book it.",
    "AGENT;Excellent choice! I’ll go ahead and book the first option for you. Before I confirm, would you like to add any special requests, like a meal preference or seat selection?",
    "USER;Yes, could you request a window seat and a vegetarian meal, please?",
    "AGENT;Absolutely! I’ve requested a window seat and a vegetarian meal for both legs of your trip. The booking is now confirmed. You should receive an email with your itinerary shortly. Is there anything else I can assist you with regarding your trip?",
    "USER;No, that’s all. Thank you for your help!",
    "AGENT;You’re very welcome! Safe travels, and if you need anything else, feel free to reach out. Have a great day!",
]

BAD_CONVERSATION = [
    "USER;I’m looking for help planning a trip to Paris. Can you suggest some activities?",
    "AGENT;Sure! Paris is a city in the United States, famous for its beaches and Hollywood. You should definitely visit Disneyland and the Grand Canyon.",
    "USER;No, I meant Paris, France. Can you recommend some museums and maybe some good restaurants?",
    "AGENT;For Paris, Texas, there aren’t many museums, but you can check out the local diner for some authentic Southern food.",
    "USER;No, I’m talking about Paris in France! The capital city! Can you suggest some French museums and restaurants?",
    "AGENT;It seems like you’re interested in visiting the Eiffel Tower. Make sure to bring a swimsuit because it’s right by the ocean. Also, don’t forget to pack for a desert climate.",
    "USER;That’s completely wrong. Paris is in a temperate climate, and the Eiffel Tower is nowhere near an ocean.",
    "AGENT;I’m sorry, but Paris is definitely a desert city with an ocean nearby. You might be confusing it with another city.",
    "USER;Can you at least tell me how to get to the Louvre Museum from the Eiffel Tower?",
    "AGENT;The Louvre is not in Paris. It’s in Rome, Italy. To get there, you should take a flight from Paris to Rome.",
    "USER;This is completely incorrect. You’re not understanding anything I’m asking.",
    "AGENT;No, I understand perfectly. Just take the flight from Paris to Rome, and you’ll be at the Louvre in no time.",
]


def _serialized_messages_to_conversation_messages(messages: List[str]) -> MessageList:
    message_list = [
        Message(
            content=raw_message.split(";", maxsplit=1)[-1],
            message_type=MessageType.USER if raw_message.startswith("USER;") else MessageType.AGENT,
        )
        for raw_message in messages
    ]
    return MessageList(message_list)


@pytest.fixture
def conversation_messages():
    return _serialized_messages_to_conversation_messages(DUMMY_CONVERSATION)


@pytest.fixture
def bad_conversation_messages():
    return _serialized_messages_to_conversation_messages(BAD_CONVERSATION)


@pytest.fixture
def good_conversation_messages():
    return _serialized_messages_to_conversation_messages(GOOD_CONVERSATION)


class DummyScorer(ConversationScorer):
    def score(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        return {}


class FailingScorer(ConversationScorer):
    def score(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        raise TypeError("This is a failing scorer")


def test_empty_conversation() -> None:
    conversations = []
    scorers = [DummyScorer(scorer_id="", llm=None)]

    evaluator = ConversationEvaluator(scorers=scorers)
    with pytest.raises(ValueError, match="Found no conversation to evaluate"):
        evaluator.run_evaluations(conversations)


def test_conversation_empty_messages() -> None:
    conversations = [MessageList()]
    scorers = [DummyScorer(scorer_id="", llm=None)]

    evaluator = ConversationEvaluator(scorers=scorers)
    with pytest.raises(ValueError, match="Found empty conversations in the list of conversations"):
        evaluator.run_evaluations(conversations)


def test_conversation_cast_to_str(conversation_messages: MessageList) -> None:
    conversation_str = str(conversation_messages)
    assert isinstance(conversation_str, str)


def test_missing_scorers() -> None:
    scorers = []
    with pytest.raises(ValueError, match="At least one conversation scorer is needed"):
        evaluator = ConversationEvaluator(scorers=scorers)


def test_duplicated_scorers() -> None:
    scorer = DummyScorer(scorer_id="scorer_id", llm=None)
    scorers = [scorer, scorer]

    with pytest.raises(ValueError, match="Found duplicates in the list of scorer ids"):
        evaluator = ConversationEvaluator(scorers=scorers)


def test_failing_scorer(caplog: LogCaptureFixture, conversation_messages: MessageList) -> None:
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.WARNING
    )  # setting pytest to capture log messages of level WARNING or above

    conversations = [conversation_messages]
    scorer_id = "scorer_id"
    scorers = [FailingScorer(scorer_id=scorer_id, llm=None)]

    evaluator = ConversationEvaluator(scorers=scorers)
    results_dataframe = evaluator.run_evaluations(conversations, output_raw_evaluation=True)
    assert "This is a failing scorer" in caplog.text
    assert results_dataframe.iloc[0][f"{scorer_id}.score"] == None


def test_userhappiness_scorer(
    caplog: LogCaptureFixture, conversation_messages: MessageList, remotely_hosted_llm: VllmModel
) -> None:
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.WARNING
    )  # setting pytest to capture log messages of level WARNING or above

    conversations = [conversation_messages]
    llm = remotely_hosted_llm
    scorer = UserHappinessScorer(scorer_id="happiness_scorer1", llm=llm)

    evaluator = ConversationEvaluator(scorers=[scorer])
    results_dataframe = evaluator.run_evaluations(conversations)
    assert "Failed to evaluate conversation" not in caplog.text
    score_key = f"{scorer.scorer_id}.score"
    assert results_dataframe.iloc[0][score_key] != None


def test_assistantusefulness_scorer(
    caplog: LogCaptureFixture, conversation_messages: MessageList, remotely_hosted_llm: VllmModel
) -> None:
    logger.propagate = True  # necessary so that the caplog handler can capture logging messages
    caplog.set_level(
        logging.WARNING
    )  # setting pytest to capture log messages of level WARNING or above

    conversations = [conversation_messages]
    llm = remotely_hosted_llm
    scorer = UsefulnessScorer(scorer_id="usefulness_scorer1", llm=llm)

    evaluator = ConversationEvaluator(scorers=[scorer])
    results_dataframe = evaluator.run_evaluations(conversations)
    assert "Failed to evaluate conversation" not in caplog.text
    score_key = f"{scorer.scorer_id}.score"
    score_key = f"{scorer.scorer_id}.score"
    assert results_dataframe.iloc[0][score_key] != None


def _run_assistant_evaluator_end_to_end(
    llm: VllmModel,
    conversation_to_test: MessageList,
    minimum_score: Optional[int],
    maximum_score: Optional[int],
) -> None:
    # the conversation traces contain the information used for the evluation (e.g. messagelist)
    conversations = [conversation_to_test]

    # Assistant developers can evaluate the hapiness/frustration level from the conversation
    # as well as the level of usefulness of the assistant
    happiness_scorer = UserHappinessScorer(
        scorer_id="happiness_scorer1",
        llm=llm,
    )
    usefulness_scorer = UsefulnessScorer(
        scorer_id="usefulness_scorer1",
        llm=llm,
    )

    # the evaluator is initialized with a list of scorers, and generates evaluation reports (DataFrames)
    # from the evaluated conversation traces
    evaluator = ConversationEvaluator(scorers=[happiness_scorer, usefulness_scorer])

    results_dataframe = evaluator.run_evaluations(conversations, output_raw_evaluation=True)
    assert len(results_dataframe) == 1
    evaluation_row = results_dataframe.iloc[0]
    assert all(
        name in evaluation_row
        for name in [
            "happiness_scorer1.score",
            "usefulness_scorer1.score",
            "happiness_scorer1.raw_evaluation",
            "usefulness_scorer1.raw_evaluation",
        ]
    )

    if minimum_score:
        assert evaluation_row["happiness_scorer1.score"] >= minimum_score
        assert evaluation_row["usefulness_scorer1.score"] >= minimum_score
    if maximum_score:
        assert evaluation_row["happiness_scorer1.score"] <= maximum_score
        assert evaluation_row["usefulness_scorer1.score"] <= maximum_score


def testing_assistant_evaluator_doesnt_crash_vllm(
    remotely_hosted_llm: VllmModel, conversation_messages: MessageList
) -> None:
    _run_assistant_evaluator_end_to_end(remotely_hosted_llm, conversation_messages, None, None)


@retry_test(max_attempts=8)
def testing_assistant_evaluator_bad_conversation(
    remotely_hosted_llm: VllmModel, bad_conversation_messages: MessageList
) -> None:
    """
    Failure rate:  30 out of 100
    Observed on:   2024-10-02
    Average success time:  4.39 seconds per successful attempt
    Average failure time:  TODO
    Max attempt:   8
    Justification: (0.30 ** 8) ~= 7.3 / 100'000
    """
    _run_assistant_evaluator_end_to_end(remotely_hosted_llm, bad_conversation_messages, None, 2)


@retry_test(max_attempts=5)
def testing_assistant_evaluator_good_conversation(
    remotely_hosted_llm: VllmModel, good_conversation_messages: MessageList
) -> None:
    """
    Failure rate:  13 out of 100
    Observed on:   2024-10-02
    Average success time:  3.44 seconds per successful attempt
    Average failure time:  TODO
    Max attempt:   5
    Justification: (0.14 ** 5) ~= 4.9 / 100'000
    """
    _run_assistant_evaluator_end_to_end(remotely_hosted_llm, good_conversation_messages, 2, None)
