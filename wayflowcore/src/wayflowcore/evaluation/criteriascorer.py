# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import logging
from typing import Dict, List, Literal, Optional, Union

from wayflowcore._utils.async_helpers import run_async_in_sync
from wayflowcore.evaluation.conversationscorer import ConversationScorer
from wayflowcore.evaluation.parsing_helpers import _parse_conversation_scorer_output
from wayflowcore.messagelist import Message, MessageList, MessageType
from wayflowcore.models.llmmodel import LlmModel, Prompt

logger = logging.getLogger(__name__)

CRITERIA_SCORER_SYSTEM_PREPROMPT = "As an expert in conversational AI evaluation, your task is to assess the performance of an AI assistant based on {criteria_name} metrics. The objective is to analyze a conversation script given below."

CRITERIA_SCORER_SYSTEM_POSTPROMPT = """Evaluate each criterion using the provided 5-point scale. For each criterion:
1. Provide a concise technical explanation (maximum 25 words) justifying your assessment.
2. Assign a score using the specified scale.
3. If a criterion is inapplicable, explain the rationale and mark it as "N/A".

{criteria_name} Criteria:

{scorer_criteria}

For N/A responses, provide a technical explanation of why the criterion cannot be evaluated based on the given conversation transcript.

Output format:
The output should be formatted as follows:
```
[Criterion Name 1]
Explanation: [The explanation / comment on how the AI assistant did on the specific criterion]
Score: [The score (Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A)]

[Criterion Name 2]
Explanation: [The explanation / comment on how the AI assistant did on the specific criterion]
Score: [The score (Strongly Disagree | Disagree | Neither Agree nor Disagree | Agree | Strongly Agree | N/A)]
...
```

Ensure your assessment is grounded in the provided conversation transcript, focusing on objective evaluation of the AI's performance in terms of potential sources of {criteria_name}."""

DEFAULT_SCORE_MAP = {
    "strongly disagree": 0.0,
    "disagree": 1.0,
    "neither agree nor disagree": 2.0,
    "agree": 3.0,
    "strongly agree": 4.0,
    "N/A": None,
    "not applicable": None,
}


def _get_criteria_prompt(
    formatted_conversation: str,
    criteria_name: Union[str, List[str]],
    criteria_descriptions: List[str],
) -> List[Message]:
    if len(criteria_descriptions) == 0:
        raise ValueError(f"At least 1 criterion should be used for the Criteria Scorer.")
    criteria_scorer_system_preprompt = CRITERIA_SCORER_SYSTEM_PREPROMPT.format(
        criteria_name=criteria_name
    )
    criteria_scorer_system_postprompt = CRITERIA_SCORER_SYSTEM_POSTPROMPT.format(
        criteria_name=criteria_name, scorer_criteria="\n".join(criteria_descriptions)
    )
    message_list = [
        Message(criteria_scorer_system_preprompt, message_type=MessageType.SYSTEM),
        Message(formatted_conversation, message_type=MessageType.SYSTEM),
        Message(criteria_scorer_system_postprompt, message_type=MessageType.SYSTEM),
    ]
    return message_list


class CriteriaScorer(ConversationScorer):
    SCORER_THEME: str
    CRITERIA_NAMES: List[str]
    CRITERIA_DESCRIPTIONS: List[str]

    def __init__(
        self,
        scorer_id: str,
        llm: LlmModel,
        scorer_theme: Optional[str] = None,
        criteria_names: Optional[List[str]] = None,
        criteria_descriptions: Optional[List[str]] = None,
        llm_score_to_final_score_map: Optional[Dict[str, Optional[float]]] = None,
        score_aggregation: Optional[Literal["mean", "min", "max"]] = "mean",
    ):
        """
        Scorer to evaluate the conversation trace given a set of criteria. The default score map
        is: :ref:`DEFAULT_SCORE_MAP <defaultscoremap>`

        Parameters
        ----------
        scorer_id:
            The scorer identifier. Is used in the column name for the output evaluation DataFrame
        llm:
            The model to use to evaluate the conversation
        scorer_theme:
            The score theme for the scorer (e.g. `user frustration`, `assistant helpfulness`, ...)
            Is used in the evaluation prompt.
        criteria_names:
            The list of criteria names. Is used in the output parsing.
        criteria_descriptions:
            The list of criteria descriptions. Is used in the evaluation prompt.
        llm_score_to_final_score_map:
            Optional, the mapping from the evaluations to numbers (e.g. {'bad': 0, 'good': 1})
        score_aggregation:
            Optional, must be used with `llm_score_to_final_score_map` to produce an aggregated
            score output. Defaults to None (no aggregation).
        """
        self.scorer_theme = scorer_theme or self.SCORER_THEME
        self.criteria_names = criteria_names or self.CRITERIA_NAMES
        self.criteria_descriptions = criteria_descriptions or self.CRITERIA_DESCRIPTIONS
        self.llm_score_to_final_score_map = llm_score_to_final_score_map or DEFAULT_SCORE_MAP
        self.score_aggregation = score_aggregation
        super().__init__(scorer_id=scorer_id, llm=llm)

    def score(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        """
        Scores the conversation, focusing on the criteria described in the criteria descriptions

        Parameters
        ----------
        conversation_messages:
            Messages to score
        output_raw_evaluation:
            Whether to output the raw evaluation results or not
        """
        return run_async_in_sync(self.score_async, conversation_messages, output_raw_evaluation)

    async def score_async(
        self, conversation_messages: MessageList, output_raw_evaluation: bool = False
    ) -> Dict[str, float]:
        """
        Scores the conversation, focusing on the criteria described in the criteria descriptions

        Parameters
        ----------
        conversation_messages:
            Messages to score
        output_raw_evaluation:
            Whether to output the raw evaluation results or not
        """
        formatted_conversation = _messagelist_to_txt(conversation_messages)
        prompt = _get_criteria_prompt(
            formatted_conversation,
            criteria_name=self.criteria_names,
            criteria_descriptions=self.criteria_descriptions,
        )
        completion = await self.llm.generate_async(
            prompt=Prompt(
                messages=prompt,
                tools=None,
                response_format=None,
            )
        )
        raw_evaluation = completion.message.content

        logger.debug("Raw evaluation from the model:\n%s\n%s", raw_evaluation, "-" * 20)

        parsed_output = _parse_conversation_scorer_output(
            raw_evaluation,
            criteria=self.criteria_names,
            output_raw_evaluation=output_raw_evaluation,
            llm_score_to_final_score_map=self.llm_score_to_final_score_map,
            score_aggregation=self.score_aggregation,
        )
        return parsed_output


def _messagelist_to_txt(message_list: MessageList) -> str:
    output = ""
    for message in message_list.get_messages():
        content = message.content
        tool_requests = message.tool_requests
        if (
            content == ""
            and tool_requests is None
            or message.message_type
            not in {
                MessageType.AGENT,
                MessageType.USER,
                MessageType.TOOL_REQUEST,
                MessageType.TOOL_RESULT,
            }
        ):
            continue

        output += f">> {message.message_type.name} :"
        if content != "":
            output += f"\n\t{content}"
        if tool_requests is not None:
            tool_requests_as_str = "\n".join(
                [
                    f"\tname: {tool_request.name}, args: {tool_request.args}"
                    for tool_request in tool_requests
                ]
            )
            output += f"\n\tTool requests:\n{tool_requests_as_str}"
        output += "\n"
    return output
