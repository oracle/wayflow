# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional

from wayflowcore.conversation import Conversation
from wayflowcore.conversationalcomponent import ConversationalComponent

if TYPE_CHECKING:
    from wayflowcore.evaluation.assistantevaluator import EvaluationEnvironment, EvaluationTask


class TaskScorer(ABC):
    OUTPUT_METRICS: List[str]
    DEFAULT_SCORER_ID: str

    def __init__(self, scorer_id: Optional[str] = None):
        """
        TaskScorer is an API to implement different scores and metrics to evaluate LLMs.
        It needs to implement a `score` method to give a metric for a successful conversation
        and a `score_exceptional_case` method to give a metric for a conversation that threw an error

        Parameters
        ----------
        scorer_id:
            Name of the scorer, to avoid conflicts if several scorers are named the same
        """
        if scorer_id is None and not hasattr(self, "DEFAULT_SCORER_ID"):
            raise ValueError(
                f"TaskScorers should either have a `DEFAULT_SCORER_ID` attribute or be given a specific id"
            )
        self.scorer_id = scorer_id or self.DEFAULT_SCORER_ID
        if not hasattr(self, "OUTPUT_METRICS"):
            raise TypeError(
                f"Can't instantiate abstract class {self.__class__.__name__} with missing attribute OUTPUT_METRICS (the names of supported metrics)"
            )
        super().__init__()

    @abstractmethod
    def score(
        self,
        environment: "EvaluationEnvironment",
        task: "EvaluationTask",
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        """
        Retrieves relevant information from the assistants, conversations and task
        to score a specific task
        """

    @abstractmethod
    def score_exceptional_case(
        self,
        environment: "EvaluationEnvironment",
        exception: Exception,
        task: "EvaluationTask",
        assistant: ConversationalComponent,
        assistant_conversation: Conversation,
    ) -> Dict[str, float]:
        """scores a specific task that failed with an exception"""
