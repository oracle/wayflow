# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from textwrap import dedent

from wayflowcore.evaluation.criteriascorer import CriteriaScorer

logger = logging.getLogger(__name__)


USEFULNESS_CRITERIA = {
    "Task Completion Efficiency": dedent(
        """
        - Task Completion Efficiency
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The AI consistently fails to complete tasks or requires an excessive number of turns, severely impacting efficiency.
        Disagree: The AI often struggles to complete tasks, requiring more turns than expected and showing limited efficiency.
        Neither Agree nor Disagree: The AI completes tasks with average efficiency, neither excelling nor failing noticeably.
        Agree: The AI generally completes tasks efficiently, often requiring fewer turns than expected.
        Strongly Agree: The AI consistently completes tasks with exceptional efficiency, minimizing the number of turns and maximizing productivity.
        """
    ),
    "Proactive Assistance": dedent(
        """
        - Proactive Assistance
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The AI never anticipates user needs or offers additional relevant information beyond direct responses.
        Disagree: The AI rarely provides proactive assistance, mostly responding reactively to user queries.
        Neither Agree nor Disagree: The AI occasionally offers proactive assistance but is primarily reactive in its approach.
        Agree: The AI frequently anticipates user needs and provides relevant information or suggestions unprompted.
        Strongly Agree: The AI consistently demonstrates high-level proactive assistance, anticipating complex user needs and offering valuable insights.
        """
    ),
    "Clarification and Elaboration": dedent(
        """
        -. Clarification and Elaboration
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The AI consistently seeks clarification when appropriate and provides comprehensive, insightful elaboration on all responses.
        Disagree: The AI frequently asks for clarification when needed and often provides detailed elaboration on its responses.
        Neither Agree nor Disagree: The AI sometimes seeks clarification and provides basic elaboration when necessary.
        Agree: The AI rarely asks for clarification or elaborates on its responses, often leading to misunderstandings.
        Strongly Agree: The AI never seeks clarification when needed and provides minimal or no elaboration on its responses.
        """
    ),
}


USEFULNESS_CRITERIA_NAMES = list(USEFULNESS_CRITERIA.keys())
USEFULNESS_CRITERIA_DESCRIPTIONS = list(USEFULNESS_CRITERIA.values())


class UsefulnessScorer(CriteriaScorer):
    SCORER_THEME = "User Helpfulness"
    CRITERIA_NAMES = USEFULNESS_CRITERIA_NAMES
    CRITERIA_DESCRIPTIONS = USEFULNESS_CRITERIA_DESCRIPTIONS
