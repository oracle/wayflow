# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

import json
from dataclasses import dataclass
from typing import Dict

import pandas as pd
import pytest

from wayflowcore.evaluation.evaluation_metrics import calculate_accuracy, calculate_set_metrics


@dataclass
class MockTask:
    task_id: str
    scoring_kwargs: Dict


@dataclass
class MockAssistantConversation:
    state: object


@dataclass
class MockState:
    _flow_output_value_dict: Dict


@dataclass
class MockEnvironment:
    predicted_answers: Dict


class SetMetricsDummyScore:
    DEFAULT_SCORER_ID = "dummy_scorer"

    @property
    def OUTPUT_METRICS(self):
        return ["category_precision", "category_recall", "category_f1"]

    def score(self, environment, task, assistant, assistant_conversation):
        predicted_categories = assistant_conversation.state._flow_output_value_dict.get(
            "predicted_categories", []
        )
        ground_truth = task.scoring_kwargs.get("ground_truth", {})
        gt_categories = ground_truth.get("categories_gt", []) or []

        gt_series = pd.Series([json.dumps(gt_categories)])
        pred_series = pd.Series([json.dumps(predicted_categories)])

        metrics = calculate_set_metrics(gt_series, pred_series)
        environment.predicted_answers[task.task_id] = environment.predicted_answers.get(
            task.task_id, {}
        )
        environment.predicted_answers[task.task_id]["categories"] = predicted_categories
        return {
            "category_precision": metrics["precision"],
            "category_recall": metrics["recall"],
            "category_f1": metrics["f1"],
            "category_predictions": predicted_categories,
        }

    def score_exceptional_case(
        self, environment, exception, task, assistant, assistant_conversation
    ):
        environment.predicted_answers[task.task_id] = environment.predicted_answers.get(
            task.task_id, {}
        )
        environment.predicted_answers[task.task_id]["categories"] = []
        return {
            "category_precision": 0.0,
            "category_recall": 0.0,
            "category_f1": 0.0,
            "category_predictions": [],
        }


class AccuracyDummyScorer:
    DEFAULT_SCORER_ID = "accuracy_scorer"

    @property
    def OUTPUT_METRICS(self):
        return ["accuracy"]

    def score(self, environment, task, assistant, assistant_conversation):
        predicted_values = assistant_conversation.state._flow_output_value_dict.get(
            "predicted_values", []
        )
        ground_truth = task.scoring_kwargs.get("ground_truth", {})
        gt_values = ground_truth.get("values_gt", []) or []

        gt_series = pd.Series(gt_values)
        pred_series = pd.Series(predicted_values)

        metrics = calculate_accuracy(gt_series, pred_series)
        environment.predicted_answers[task.task_id] = environment.predicted_answers.get(
            task.task_id, {}
        )
        environment.predicted_answers[task.task_id]["values"] = predicted_values
        return {
            "accuracy": metrics["accuracy"],
            "predictions": predicted_values,
        }

    def score_exceptional_case(
        self, environment, exception, task, assistant, assistant_conversation
    ):
        environment.predicted_answers[task.task_id] = environment.predicted_answers.get(
            task.task_id, {}
        )
        environment.predicted_answers[task.task_id]["values"] = []
        return {
            "accuracy": 0.0,
            "predictions": [],
        }


def test_scorer_perfect_match_set_metrics():
    environment = MockEnvironment(predicted_answers={})
    task = MockTask(
        task_id="task1", scoring_kwargs={"ground_truth": {"categories_gt": ["cat", "dog"]}}
    )
    assistant_conversation = MockAssistantConversation(
        state=MockState(_flow_output_value_dict={"predicted_categories": ["cat", "dog"]})
    )
    scorer = SetMetricsDummyScore()
    result = scorer.score(environment, task, None, assistant_conversation)

    assert result["category_precision"] == pytest.approx(1.0)
    assert result["category_recall"] == pytest.approx(1.0)
    assert result["category_f1"] == pytest.approx(1.0)
    assert result["category_predictions"] == ["cat", "dog"]
    assert environment.predicted_answers["task1"]["categories"] == ["cat", "dog"]


def test_scorer_partial_match_set_metrics():
    environment = MockEnvironment(predicted_answers={})
    task = MockTask(
        task_id="task1", scoring_kwargs={"ground_truth": {"categories_gt": ["cat", "dog", "bird"]}}
    )
    assistant_conversation = MockAssistantConversation(
        state=MockState(_flow_output_value_dict={"predicted_categories": ["cat", "dog"]})
    )
    scorer = SetMetricsDummyScore()
    result = scorer.score(environment, task, None, assistant_conversation)

    assert result["category_precision"] == pytest.approx(
        1.0
    )  # 2/2 predicted categories are correct
    assert result["category_recall"] == pytest.approx(
        2.0 / 3.0
    )  # 2/3 ground truth categories matched
    assert result["category_f1"] == pytest.approx(2 * (1.0 * (2.0 / 3.0)) / (1.0 + (2.0 / 3.0)))
    assert result["category_predictions"] == ["cat", "dog"]
    assert environment.predicted_answers["task1"]["categories"] == ["cat", "dog"]


def test_scorer_missing_predictions_key_set_metrics():
    environment = MockEnvironment(predicted_answers={})
    task = MockTask(
        task_id="task1", scoring_kwargs={"ground_truth": {"categories_gt": ["cat", "dog"]}}
    )
    assistant_conversation = MockAssistantConversation(state=MockState(_flow_output_value_dict={}))
    scorer = SetMetricsDummyScore()
    result = scorer.score(environment, task, None, assistant_conversation)

    assert result["category_precision"] == pytest.approx(0.0)
    assert result["category_recall"] == pytest.approx(0.0)
    assert result["category_f1"] == pytest.approx(0.0)
    assert result["category_predictions"] == []
    assert environment.predicted_answers["task1"]["categories"] == []


def test_scorer_perfect_match_accuracy():
    environment = MockEnvironment(predicted_answers={})
    task = MockTask(
        task_id="task1",
        scoring_kwargs={"ground_truth": {"values_gt": ["apple", "banana", "cherry"]}},
    )
    assistant_conversation = MockAssistantConversation(
        state=MockState(_flow_output_value_dict={"predicted_values": ["apple", "banana", "cherry"]})
    )
    scorer = AccuracyDummyScorer()
    result = scorer.score(environment, task, None, assistant_conversation)

    assert result["accuracy"] == pytest.approx(1.0)
    assert result["predictions"] == ["apple", "banana", "cherry"]
    assert environment.predicted_answers["task1"]["values"] == ["apple", "banana", "cherry"]


def test_scorer_partial_match_accuracy():
    environment = MockEnvironment(predicted_answers={})
    task = MockTask(
        task_id="task1",
        scoring_kwargs={"ground_truth": {"values_gt": ["apple", "banana", "cherry"]}},
    )
    assistant_conversation = MockAssistantConversation(
        state=MockState(_flow_output_value_dict={"predicted_values": ["apple", "banana", "orange"]})
    )
    scorer = AccuracyDummyScorer()
    result = scorer.score(environment, task, None, assistant_conversation)

    assert result["accuracy"] == pytest.approx(2.0 / 3.0)  # 2/3 values match
    assert result["predictions"] == ["apple", "banana", "orange"]
    assert environment.predicted_answers["task1"]["values"] == ["apple", "banana", "orange"]


def test_perfect_match():
    """Test when predicted and ground truth are identical"""
    gt = pd.Series([{"a", "b", "c"}, {"x", "y"}, {"z"}])
    pred = pd.Series([{"a", "b", "c"}, {"x", "y"}, {"z"}])

    result = calculate_set_metrics(gt, pred)

    assert result["precision"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(1.0)
    assert result["f1"] == pytest.approx(1.0)


def test_partial_overlap():
    """Test with partial overlap between predicted and ground truth"""
    gt = pd.Series([{"a", "b", "c"}, {"x", "y"}])
    pred = pd.Series([{"a", "b"}, {"x", "y", "z"}])

    result = calculate_set_metrics(gt, pred)

    # First item: pred={"a","b"}, gt={"a","b","c"} -> precision=1.0, recall=2/3
    # Second item: pred={"x","y","z"}, gt={"x","y"} -> precision=2/3, recall=1.0
    # Average precision: (1.0 + 2/3) / 2 = 5/6 ≈ 0.833
    # Average recall: (2/3 + 1.0) / 2 = 5/6 ≈ 0.833
    # F1: 2 * (5/6 * 5/6) / (5/6 + 5/6) = 5/6 ≈ 0.833

    assert result["precision"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["recall"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["f1"] == pytest.approx(5 / 6, abs=1e-3)


def test_no_overlap():
    """Test when there's no overlap between predicted and ground truth"""
    gt = pd.Series([{"a", "b"}, {"x", "y"}])
    pred = pd.Series([{"c", "d"}, {"z", "w"}])

    result = calculate_set_metrics(gt, pred)

    assert result["precision"] == pytest.approx(0.0)
    assert result["recall"] == pytest.approx(0.0)
    assert result["f1"] == pytest.approx(0.0)


def test_empty_sets():
    """Test with empty sets"""
    gt = pd.Series([set(), {"a", "b"}])
    pred = pd.Series([{"a"}, set()])

    result = calculate_set_metrics(gt, pred)

    assert result["precision"] == pytest.approx(0.0)
    assert result["recall"] == pytest.approx(0.0)
    assert result["f1"] == pytest.approx(0.0)


def test_json_string_format():
    """Test with JSON string representations of lists"""
    gt = pd.Series(['["a", "b", "c"]', '["x", "y"]'])
    pred = pd.Series(['["a", "b"]', '["x", "y", "z"]'])

    result = calculate_set_metrics(gt, pred)

    # Should behave the same as the partial_overlap test
    assert result["precision"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["recall"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["f1"] == pytest.approx(5 / 6, abs=1e-3)


def test_mixed_formats():
    """Test with mixed formats (sets and JSON strings)"""
    gt = pd.Series([{"a", "b", "c"}, '["x", "y"]'])
    pred = pd.Series(['["a", "b"]', {"x", "y", "z"}])

    result = calculate_set_metrics(gt, pred)

    # Should handle mixed formats correctly
    assert result["precision"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["recall"] == pytest.approx(5 / 6, abs=1e-3)
    assert result["f1"] == pytest.approx(5 / 6, abs=1e-3)


def test_nan_values():
    """Test handling of NaN values"""
    gt = pd.Series([{"a", "b"}, None, {"x"}])
    pred = pd.Series([None, {"c"}, {"x"}])

    result = calculate_set_metrics(gt, pred)

    # First item: both NaN -> precision=0.0, recall=0.0
    # Second item: both NaN -> precision=0.0, recall=0.0
    # Third item: perfect match -> precision=1.0, recall=1.0
    # Average: precision=1/3, recall=1/3, f1=1/3

    assert result["precision"] == pytest.approx(1 / 3)
    assert result["recall"] == pytest.approx(1 / 3)
    assert result["f1"] == pytest.approx(1 / 3)


def test_nan_values_different_precision_recall():
    gt = pd.Series([{"a", "b", "c"}, None, {"x"}])
    pred = pd.Series([{"a", "b"}, {"unwanted"}, {"x"}])

    result = calculate_set_metrics(gt, pred)

    # First item: pred={"a","b"}, gt={"a","b","c"} -> precision=1.0, recall=2/3
    # Second item: pred={"unwanted"}, gt=None -> precision=0.0, recall=0.0
    # Third item: pred={"x"}, gt={"x"} -> precision=1.0, recall=1.0
    # Average precision: (1.0 + 0.0 + 1.0) / 3 = 2/3 ≈ 0.667
    # Average recall: (2/3 + 0.0 + 1.0) / 3 = 5/9 ≈ 0.556

    assert result["precision"] == pytest.approx(2 / 3, abs=1e-3)
    assert result["recall"] == pytest.approx(5 / 9, abs=1e-3)
    assert result["f1"] == pytest.approx(2 * (2 / 3 * 5 / 9) / (2 / 3 + 5 / 9), abs=1e-3)


def test_single_values_not_lists():
    """Test with single values (not lists or sets)"""
    gt = pd.Series(["apple", "banana"])
    pred = pd.Series(["apple", "orange"])

    result = calculate_set_metrics(gt, pred)

    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)


def test_invalid_json_strings():
    """Test with invalid JSON strings - should fallback gracefully"""
    gt = pd.Series(['{"invalid": json}', '["valid", "json"]'])
    pred = pd.Series(['["valid", "json"]', "invalid json string"])

    result = calculate_set_metrics(gt, pred)

    # Should handle invalid JSON gracefully by treating as single values
    # First item: gt becomes {'{"invalid": json}'}, pred becomes {'"valid"', '"json"'} -> no overlap
    # Second item: gt becomes {'"valid"', '"json"'}, pred becomes {'invalid json string'} -> no overlap

    assert result["precision"] == pytest.approx(0.0)
    assert result["recall"] == pytest.approx(0.0)
    assert result["f1"] == pytest.approx(0.0)


def test_mismatched_series_lengths():
    """Test that ValueError is raised for mismatched series lengths"""
    gt = pd.Series([{"a", "b"}, {"c", "d"}])
    pred = pd.Series([{"a", "b"}])

    with pytest.raises(ValueError, match="Series must have the same length"):
        calculate_set_metrics(gt, pred)


def test_large_sets_equal_precision_recall():
    large_set_1 = set(range(1000))
    large_set_2 = set(range(500, 1500))

    gt = pd.Series([large_set_1])
    pred = pd.Series([large_set_2])

    result = calculate_set_metrics(gt, pred)

    # Expected: 500 overlap out of 1000 pred -> precision = 0.5
    # Expected: 500 overlap out of 1000 gt -> recall = 0.5
    # Expected: F1 = 0.5

    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)


def test_large_sets_different_precision_recall():
    large_set_gt = set(range(1000))
    large_set_pred = set(range(500, 2500))
    gt = pd.Series([large_set_gt])
    pred = pd.Series([large_set_pred])

    result = calculate_set_metrics(gt, pred)

    # Expected: 500 overlap out of 2000 pred -> precision = 0.25
    # Expected: 500 overlap out of 1000 gt -> recall = 0.5
    # Expected: F1 = 2 * (0.25 * 0.5) / (0.25 + 0.5) = 0.25 / 0.75 = 1/3

    assert result["precision"] == pytest.approx(0.25)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(1 / 3, abs=1e-3)


def test_perfect_accuracy():
    """Test when all predictions match ground truth exactly"""
    gt = pd.Series(["apple", "banana", "cherry"])
    pred = pd.Series(["apple", "banana", "cherry"])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(1.0)


def test_partial_accuracy():
    """Test with some correct and some incorrect predictions"""
    gt = pd.Series(["apple", "banana", "cherry"])
    pred = pd.Series(["apple", "banana", "orange"])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(2 / 3, abs=1e-3)


def test_zero_accuracy():
    """Test when no predictions match ground truth"""
    gt = pd.Series(["apple", "banana", "cherry"])
    pred = pd.Series(["orange", "grape", "kiwi"])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(0.0)


def test_case_insensitive_matching():
    """Test that matching is case insensitive"""
    gt = pd.Series(["APPLE", "Banana", "cherry"])
    pred = pd.Series(["apple", "BANANA", "Cherry"])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(1.0)


def test_whitespace_handling():
    """Test that leading/trailing whitespace is stripped"""
    gt = pd.Series([" apple ", "banana", " cherry"])
    pred = pd.Series(["apple", " banana ", "cherry "])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(1.0)


def test_nan_values():
    """Test handling of NaN values"""
    gt = pd.Series(["apple", None, "cherry"])
    pred = pd.Series([None, "banana", "cherry"])

    result = calculate_accuracy(gt, pred)

    # NaN values are converted to empty strings, so:
    # First item: "apple" vs "" -> no match
    # Second item: "" vs "banana" -> no match
    # Third item: "cherry" vs "cherry" -> match
    # Accuracy: 1/3

    assert result["accuracy"] == pytest.approx(1 / 3, abs=1e-3)


def test_numeric_values():
    """Test with numeric values (converted to strings)"""
    gt = pd.Series([1, 2, 3.5])
    pred = pd.Series([1, 2.0, 3.5])

    result = calculate_accuracy(gt, pred)

    assert result["accuracy"] == pytest.approx(1.0)


def test_mixed_data_types():
    """Test with mixed data types"""
    gt = pd.Series(["apple", 42, True, None])
    pred = pd.Series(["apple", "42", "true", ""])

    result = calculate_accuracy(gt, pred)

    # After conversion to lowercase strings:
    # "apple" == "apple" -> match
    # "42" == "42" -> match
    # "true" == "true" -> match
    # "" == "" -> match (both NaN converted to empty string)

    assert result["accuracy"] == pytest.approx(1.0)


def test_very_large_sets():
    """Test performance with larger sets"""
    large_set_1 = set(range(1000))
    large_set_2 = set(range(500, 1500))

    gt = pd.Series([large_set_1])
    pred = pd.Series([large_set_2])

    result = calculate_set_metrics(gt, pred)

    # Expected: 500 overlap out of 1000 pred -> precision = 0.5
    # Expected: 500 overlap out of 1000 gt -> recall = 0.5
    # Expected: F1 = 0.5

    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)


def test_mismatched_series_lengths():
    """Test that ValueError is raised for mismatched series lengths"""
    gt = pd.Series(["apple", "banana"])
    pred = pd.Series(["apple"])

    with pytest.raises(ValueError, match="Can only compare identically-labeled Series objects"):
        calculate_accuracy(gt, pred)


def test_accuracy_mismatched_lengths():
    """Test that ValueError is raised for mismatched series lengths"""
    gt = pd.Series(["apple", "banana"])
    pred = pd.Series(["apple"])

    with pytest.raises(ValueError) as excinfo:
        calculate_accuracy(gt, pred)

    assert "Can only compare identically-labeled Series objects" in str(excinfo.value)
