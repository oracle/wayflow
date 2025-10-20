# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import logging
from typing import Any, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


def _parse_criterion_output(criterion: str, explanation_raw: str, score_raw: str) -> Dict[str, str]:
    explanation = explanation_raw.split("explanation", maxsplit=1)[-1].replace(":", "").strip()

    pre_score = score_raw.split("score", maxsplit=1)[-1].replace(":", "").strip()
    possible_scores = [
        "strongly disagree",
        "disagree",
        "neither agree nor disagree",
        "agree",
        "strongly agree",
        "N/A",
        "not applicable",
    ]
    final_score = "N/A"
    for score_val in possible_scores:
        if score_val in pre_score:
            final_score = score_val
            break

    return {
        "explanation": explanation,
        "score": final_score,
    }


def _is_criterion_in_sentence(sentence: str, criteria: List[str]) -> Optional[str]:
    for criterion in criteria:
        if criterion.lower() in sentence:
            return criterion
    return None


def _process_sentence(sentence: str) -> str:
    return sentence.strip().lower().replace("*", "")  # used to remove bold formatting from LLMs


def _parse_judge_output(raw_output: str, criteria: List[str]) -> Dict[str, Dict[str, str]]:
    split_output = [x for x in raw_output.split("\n") if len(x.strip()) > 0]
    split_len = len(split_output)
    evaluation = {}
    for i in range(split_len - 2):
        criterion_row = _process_sentence(split_output[i])
        explanation_row = _process_sentence(split_output[i + 1])
        score_row = _process_sentence(split_output[i + 2])

        criterion = _is_criterion_in_sentence(criterion_row, criteria)
        if criterion is None:  # did not find any criterion
            continue
        if "explanation:" in explanation_row and "score:" in score_row:
            evaluation[criterion] = _parse_criterion_output(criterion, explanation_row, score_row)
    return evaluation


def _parse_conversation_scorer_output(
    output: str,
    criteria: List[str],
    output_raw_evaluation: bool = False,
    llm_score_to_final_score_map: Optional[Dict[str, Optional[float]]] = None,
    score_aggregation: Optional[Literal["mean", "min", "max"]] = None,
) -> Dict[str, Any]:
    """In the future, may use a different parsing strategy depending on the llm"""
    evaluation: Dict[str, Dict[str, str]] = _parse_judge_output(output, criteria)
    parsed_eval: Dict[str, Dict[str, str]] = {
        criterion: scores for criterion, scores in evaluation.items() if criterion in criteria
    }
    output_scores: Dict[str, Any] = {}
    if output_raw_evaluation:
        output_scores["raw_evaluation"] = parsed_eval

    if llm_score_to_final_score_map is None:
        output_scores.update(parsed_eval)
        return output_scores

    # we might have a mapping scheme from whatever the LLM output to numbers
    # if so apply it
    mapped_scores: Dict[str, float] = {}
    for criteria_name, result in parsed_eval.items():
        remapped_score = llm_score_to_final_score_map.get(result["score"])

        final_criteria_name = criteria_name.lower().replace(" ", "_")
        if remapped_score is not None:
            mapped_scores[final_criteria_name] = remapped_score

    if len(mapped_scores) == 0:
        logger.warning(
            "Was unable to parse the conversation evaluation output, will default to score = -1. Output:\n%s\n%s",
            output,
            "-" * 20,
        )
        output_scores["score"] = -1
        return output_scores

    if score_aggregation is None:
        # no aggregation is needed, we just return this
        output_scores.update(mapped_scores)
        return output_scores

    # do the required aggregations
    score_list: List[float] = list(mapped_scores.values())
    final_score: float = 0.0
    if score_aggregation == "mean":
        final_score = sum(score_list) / len(score_list)
    elif score_aggregation == "max":
        final_score = max(score_list)
    elif score_aggregation == "min":
        final_score = min(score_list)
    else:
        raise ValueError(
            f"`score_aggregation` should be in ['mean','max','min'], is {score_aggregation}"
        )

    output_scores["score"] = final_score
    return output_scores
