# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import Dict, List, Optional, Union

import pandas as pd

from wayflowcore._utils.async_helpers import run_async_function_in_parallel, run_async_in_sync
from wayflowcore.evaluation.conversationscorer import ConversationScorer
from wayflowcore.messagelist import MessageList

logger = logging.getLogger(__name__)


class ConversationEvaluator:
    def __init__(
        self,
        scorers: Union[ConversationScorer, List[ConversationScorer]],
    ):
        """
        Class used to run the conversation evaluation given a list of conversation scorers.

        Parameters
        ----------
        scorers:
            Scorers to be used to evaluate the conversation.

        Examples
        --------
        >>> from wayflowcore.messagelist import MessageList
        >>> from wayflowcore.evaluation import ConversationEvaluator, UsefulnessScorer
        >>>
        >>> conversation = MessageList()
        >>> conversation.append_user_message("What is the capital of France")
        >>> conversation.append_agent_message("The capital of France is Paris")
        >>> usefulness_scorer = UsefulnessScorer("usefulness_scorer1", llm=llm)
        >>>
        >>> evaluator = ConversationEvaluator(scorers=[usefulness_scorer])
        >>> evaluation_results = evaluator.run_evaluations([conversation])

        """
        if isinstance(scorers, ConversationScorer):
            scorers = [scorers]
        if len(scorers) == 0:
            raise ValueError("At least one conversation scorer is needed")
        scorer_ids = [scorer.scorer_id for scorer in scorers]
        if len(scorer_ids) != len(set(scorer_ids)):
            raise ValueError(f"Found duplicates in the list of scorer ids: {scorer_ids}")
        self.scorers = scorers

    async def _run_single_evaluation(
        self,
        scorer: ConversationScorer,
        conversation_messages: MessageList,
        conversation_index: int,
        output_raw_evaluation: bool = False,
    ) -> Dict[str, Optional[float]]:
        try:
            scorer_results = await scorer.score_async(
                conversation_messages, output_raw_evaluation=output_raw_evaluation
            )
            return {
                f"{scorer.scorer_id}.{score_name}": scorer_result
                for score_name, scorer_result in scorer_results.items()
            }
        except Exception as e:
            logger.warning(
                "Failed to evaluate conversation (idx=%s) with scorer (id=%s), error is\n%s\n%s",
                conversation_index,
                scorer.scorer_id,
                e,
                "-" * 20,
            )
            return {f"{scorer.scorer_id}.score": None}

    async def _run_evaluation(
        self,
        conversation_messages: MessageList,
        conversation_index: int,
        output_raw_evaluation: bool = False,
    ) -> Dict[str, Optional[float]]:

        scores_by_scorers_list = await run_async_function_in_parallel(
            func_async=lambda args: self._run_single_evaluation(*args),
            input_list=[
                (scorer, conversation_messages, conversation_index, output_raw_evaluation)
                for scorer in self.scorers
            ],
        )
        return {
            score_name: score_value
            for scores in scores_by_scorers_list
            for score_name, score_value in scores.items()
        }

    def run_evaluations(
        self,
        conversations: List[MessageList],
        output_raw_evaluation: bool = False,
    ) -> pd.DataFrame:
        """
        Evaluates the conversations using the list of scorers.

        Parameters
        ----------
        conversations:
            The list of conversations to evaluate
        output_raw_evaluation:
            Whether to output the raw evaluation results

        Returns
        -------
        A DataFrame with the conversation id [int] and the different scores [float] (columns)
            for each conversation (rows)
        """
        return run_async_in_sync(
            self.run_evaluations_async,
            conversations,
            output_raw_evaluation,
            method_name="run_evaluations_async",
        )

    async def run_evaluations_async(
        self,
        conversations: List[MessageList],
        output_raw_evaluation: bool = False,
    ) -> pd.DataFrame:
        """
        Evaluates the conversations using the list of scorers.

        Parameters
        ----------
        conversations:
            The list of conversations to evaluate
        output_raw_evaluation:
            Whether to output the raw evaluation results

        Returns
        -------
        A DataFrame with the conversation id [int] and the different scores [float] (columns)
            for each conversation (rows)
        """
        if len(conversations) == 0:
            raise ValueError("Found no conversation to evaluate")
        if any(len(conversation.get_messages()) == 0 for conversation in conversations):
            raise ValueError("Found empty conversations in the list of conversations")
        results = {}
        for conversation_index, conversation in enumerate(conversations):
            conversation_results = await self._run_evaluation(
                conversation,
                conversation_index=conversation_index,
                output_raw_evaluation=output_raw_evaluation,
            )
            results[conversation_index] = conversation_results

        results_df = pd.DataFrame(results).T.reset_index(names="conversation_id")
        return results_df
