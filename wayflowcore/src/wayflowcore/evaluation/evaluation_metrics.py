# Copyright © 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json
from statistics import mean
from typing import Dict

import pandas as pd


def calculate_set_metrics(ground_truth: pd.Series, predicted: pd.Series) -> Dict[str, float]:
    """
    Calculate precision, recall, and F1 for set-based comparisons (where order doesn't matter)

    This function implements the following rules and behaviors:

    **Input Handling:**
    - Accepts pandas Series containing sets, JSON strings of lists, or single values
    - JSON string representations of lists are parsed and converted to sets
    - Invalid JSON strings fall back to single-element sets containing the original value
    - Non-iterable values (strings, numbers) are wrapped in single-element sets
    - NaN/None values are treated as empty sets
    - Both series must have the same length (raises ValueError otherwise)

    **Metric Calculations:**
    - Precision = intersection_size / predicted_set_size (0.0 if predicted set is empty)
    - Recall = intersection_size / ground_truth_set_size (0.0 if ground truth set is empty)
    - F1 = 2 * (precision * recall) / (precision + recall) (0.0 if both precision and recall are 0)
    - Final metrics are averages across all items in the series

    **Type Conversions:**
    - Sets remain as sets
    - JSON strings like '["a", "b"]' are parsed to sets
    - Single values like "apple" become {"apple"}
    - Invalid JSON becomes single-element sets
    - NaN/None becomes empty set

    Args:
        ground_truth: Series containing ground truth values (can be JSON strings of lists)
        predicted: Series containing predicted values (can be JSON strings of lists)

    Returns:
        Dictionary with precision, recall, and f1 scores (all float values between 0.0 and 1.0)

    Raises:
        ValueError: If the series have different lengths

    Examples
    --------
    >>> import pandas as pd
    >>> from wayflowcore.evaluation.evaluation_metrics import calculate_set_metrics
    >>> ground_truth_series = pd.Series([{"a","b","c"}, set(), {"a", "b"}])
    >>> predicted_series = pd.Series([{"a"}, {"a"}, {"a", "b"}])
    >>> metrics = calculate_set_metrics(ground_truth_series, predicted_series)
    >>> # metrics should be {"precision": 0.6667, "recall": 0.4444, "f1": 0.5333}
    """
    if len(ground_truth) != len(predicted):
        raise ValueError("Series must have the same length")

    precisions = []
    recalls = []

    for gt, pred in zip(ground_truth, predicted):
        if pd.isna(gt) or pd.isna(pred):
            precisions.append(0.0)
            recalls.append(0.0)
            continue

        try:
            gt_set = set(json.loads(gt) if isinstance(gt, str) else gt)
        except (TypeError, json.JSONDecodeError):
            gt_set = set([gt]) if not pd.isna(gt) else set()

        try:
            pred_set = set(json.loads(pred) if isinstance(pred, str) else pred)
        except (TypeError, json.JSONDecodeError):
            pred_set = set([pred]) if not pd.isna(pred) else set()

        precisions.append(len(pred_set & gt_set) / len(pred_set) if pred_set else 0.0)
        recalls.append(len(pred_set & gt_set) / len(gt_set) if gt_set else 0.0)

    precision = mean(precisions) if precisions else 0.0
    recall = mean(recalls) if recalls else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": precision, "recall": recall, "f1": f1}


def calculate_accuracy(ground_truth: pd.Series, predicted: pd.Series) -> Dict[str, float]:
    """
    Calculate accuracy for exact matches (where order matters)

    This function implements the following rules and behaviors:

    **Preprocessing Rules:**
    - All values are converted to strings using astype(str)
    - All strings are converted to lowercase using str.lower() (case-insensitive matching)
    - Leading and trailing whitespace is stripped using str.strip()
    - NaN/None values are replaced with empty strings using fillna("")

    **Type Conversions:**
    - Numbers: 42 → "42", 3.14 → "3.14"
    - Booleans: True → "true", False → "false" (after lowercase conversion)
    - Strings: "APPLE" → "apple", " Hello " → "hello"
    - NaN/None: → "" (empty string)

    **Matching Rules:**
    - Performs exact string matching after all preprocessing
    - Case-insensitive: "APPLE" matches "apple"
    - Whitespace-insensitive: " hello " matches "hello"
    - Type-flexible: 42 matches "42", True matches "true"

    **Calculation:**
    - Accuracy = (number of exact matches) / (total number of items)
    - Returns value between 0.0 (no matches) and 1.0 (all matches)
    - Empty series returns 0.0

    Args:
        ground_truth: Series containing ground truth values
        predicted: Series containing predicted values

    Returns:
        Dictionary with accuracy score (float between 0.0 and 1.0)

    Raises:
        ValueError: If the series have different lengths

    Examples
    --------
    >>> import pandas as pd
    >>> from wayflowcore.evaluation.evaluation_metrics import calculate_accuracy
    >>> ground_truth_series = pd.Series(["apple", "banana", "cherry"])
    >>> predicted_series = pd.Series(["apple", "banana", "orange"])
    >>> metrics = calculate_accuracy(ground_truth_series, predicted_series)
    >>> # metrics should be {"accuracy": 0.6667}
    """
    if len(ground_truth) == 0:
        return {"accuracy": 0.0}

    gt_clean = ground_truth.fillna("").astype(str).str.lower().str.strip()
    pred_clean = predicted.fillna("").astype(str).str.lower().str.strip()

    accuracy = (gt_clean == pred_clean).mean()
    return {"accuracy": accuracy}
