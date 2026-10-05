"""Small, deterministic evaluation helpers; no training or application side effects."""

import hashlib
import math
from collections import Counter

SENTIMENT_LABELS = ("negative", "neutral", "positive")


def classification_metrics(truth, predicted, labels):
    if not truth or len(truth) != len(predicted):
        raise ValueError("Expected equally sized, nonempty label sequences")
    if not labels or len(set(labels)) != len(labels):
        raise ValueError("Expected unique labels")
    index = {label: position for position, label in enumerate(labels)}
    if any(label not in index for label in [*truth, *predicted]):
        raise ValueError("Observed a label outside the declared label set")
    matrix = [[0 for _ in labels] for _ in labels]
    for actual, prediction in zip(truth, predicted, strict=True):
        matrix[index[actual]][index[prediction]] += 1
    per_class = {}
    for label, position in index.items():
        correct = matrix[position][position]
        support = sum(matrix[position])
        predicted_count = sum(row[position] for row in matrix)
        precision = correct / predicted_count if predicted_count else 0.0
        recall = correct / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"support": support, "precision": precision, "recall": recall, "f1": f1}
    return {
        "count": len(truth),
        "labels": list(labels),
        "confusion_matrix": matrix,
        "accuracy": sum(matrix[i][i] for i in range(len(labels))) / len(truth),
        "macro_f1": sum(row["f1"] for row in per_class.values()) / len(labels),
        "majority_baseline_accuracy": max(Counter(truth).values()) / len(truth),
        "per_class": per_class,
    }


def nearest_rank(values, percentile):
    if not values or not 0 < percentile <= 1 or any(not math.isfinite(x) for x in values):
        raise ValueError("Expected finite observations and 0 < percentile <= 1")
    return sorted(values)[math.ceil(percentile * len(values)) - 1]


def select_balanced(rows, per_class=30):
    if per_class < 1:
        raise ValueError("per_class must be positive")
    unique = {}
    for sentence, label in rows:
        if not sentence or label not in SENTIMENT_LABELS:
            raise ValueError("Invalid sentiment record")
        if sentence in unique and unique[sentence] != label:
            raise ValueError("Conflicting duplicate labels")
        unique[sentence] = label
    selected = []
    for label in SENTIMENT_LABELS:
        candidates = sorted(
            (hashlib.sha256(text.encode("utf-8")).hexdigest(), text)
            for text, actual in unique.items()
            if actual == label
        )
        if len(candidates) < per_class:
            raise ValueError(f"Insufficient records for {label}")
        selected.extend(
            {"id": digest, "text": text, "label": label} for digest, text in candidates[:per_class]
        )
    return selected
