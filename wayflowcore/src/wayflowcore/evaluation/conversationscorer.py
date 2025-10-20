# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from abc import ABC, abstractmethod
from typing import Dict

from wayflowcore._utils.async_helpers import run_sync_in_thread
from wayflowcore.messagelist import MessageList
from wayflowcore.models.llmmodel import LlmModel


class ConversationScorer(ABC):
    def __init__(
        self,
        scorer_id: str,
        llm: LlmModel,
    ):
        """
        Base Scorer class to evaluate a conversation trace.

        Parameters
        ----------
        scorer_id:
            The scorer identifier. Is used in the column name for the output evaluation DataFrame
        llm:
            The model to use to evaluate the conversation
        """
        self.scorer_id = scorer_id
        self.llm = llm

    @abstractmethod
    def score(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        pass

    async def score_async(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        return await run_sync_in_thread(self.score, conversation_messages, output_raw_evaluation)
