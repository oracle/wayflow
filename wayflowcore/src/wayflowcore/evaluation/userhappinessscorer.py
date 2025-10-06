# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from textwrap import dedent

from wayflowcore.evaluation.criteriascorer import CriteriaScorer

logger = logging.getLogger(__name__)


HAPPINESS_CRITERIA = {
    "Query Repetition Frequency": dedent(
        """
        - Query Repetition Frequency
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The user consistently needs to repeat queries multiple times, indicating severe communication issues with the AI.
        Disagree: The user frequently needs to repeat queries due to the AI's misunderstanding or inadequate responses.
        Neither Agree nor Disagree: The user occasionally needs to repeat queries, but it doesn't significantly impact the conversation flow.
        Agree: The user rarely needs to repeat queries; the AI generally understands and addresses requests effectively.
        Strongly Agree: The user never needs to repeat queries; the AI understands and addresses all requests on the first attempt.
        """
    ),
    "Misinterpretation of User Intent": dedent(
        """
        - Misinterpretation of User Intent
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The AI consistently misinterprets user intent, repeatedly failing to understand or address the user's true goals.
        Disagree: The AI frequently misinterprets user intent, often providing responses that don't align with the user's actual needs.
        Neither Agree nor Disagree: The AI occasionally misinterprets user intent, but usually corrects itself or seeks clarification.
        Agree: The AI rarely misinterprets user intent, generally providing responses aligned with the user's goals.
        Strongly Agree: The AI never misinterprets user intent, consistently understanding and addressing the user's actual needs.
        """
    ),
    "Conversation Flow Disruption": dedent(
        """
        - Conversation Flow Disruption
        Explanation: [Technical explanation here]
        Score: [Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A]

        Strongly Disagree: The conversation is severely disrupted throughout; the AI consistently loses context, introduces irrelevant information, or abruptly changes topics.
        Disagree: The conversation is frequently disrupted; the AI often loses context or introduces irrelevant information.
        Neither Agree nor Disagree: The conversation has occasional disruptions, but the AI usually recovers and maintains adequate flow.
        Agree: The conversation generally flows well with minimal disruptions; the AI maintains good continuity and context.
        Strongly Agree: The conversation flows seamlessly with no disruptions; the AI maintains perfect continuity and context.
        """
    ),
}
HAPPINESS_CRITERIA_NAMES = list(HAPPINESS_CRITERIA.keys())
HAPPINESS_CRITERIA_DESCRIPTIONS = list(HAPPINESS_CRITERIA.values())


class UserHappinessScorer(CriteriaScorer):
    SCORER_THEME = "User Frustration / Happiness"
    CRITERIA_NAMES = HAPPINESS_CRITERIA_NAMES
    CRITERIA_DESCRIPTIONS = HAPPINESS_CRITERIA_DESCRIPTIONS
