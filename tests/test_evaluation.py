import pytest

from eventlens.evaluation import classification_metrics, nearest_rank, select_balanced


def test_metrics_are_hand_reconciled():
    result = classification_metrics(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert result["confusion_matrix"] == [[1, 1], [0, 1]]
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["macro_f1"] == pytest.approx(2 / 3)
    assert result["majority_baseline_accuracy"] == pytest.approx(2 / 3)
    assert result["per_class"]["a"]["support"] == 2


@pytest.mark.parametrize(
    "truth,predicted", [([], []), (["a"], []), (["missing"], ["a"]), (["a"], ["missing"])]
)
def test_invalid_metric_inputs_fail_closed(truth, predicted):
    with pytest.raises(ValueError):
        classification_metrics(truth, predicted, ["a", "b"])


def test_missing_classes_do_not_invent_precision():
    result = classification_metrics(["a"], ["a"], ["a", "b"])
    assert result["per_class"]["b"]["f1"] == 0
    assert result["macro_f1"] == 0.5


def test_percentile_is_nearest_rank_not_interpolated():
    assert nearest_rank([1, 2, 3, 4], 0.95) == 4
    assert nearest_rank([4, 1, 2, 3], 0.5) == 2
    with pytest.raises(ValueError):
        nearest_rank([], 0.95)


def test_balanced_selection_is_order_independent_and_deduplicated():
    rows = [
        ("good a", "positive"),
        ("good b", "positive"),
        ("bad a", "negative"),
        ("bad b", "negative"),
        ("unchanged a", "neutral"),
        ("unchanged b", "neutral"),
        ("good a", "positive"),
    ]
    first = select_balanced(rows, per_class=1)
    assert first == select_balanced(list(reversed(rows)), per_class=1)
    assert len(first) == 3
    assert {row["label"] for row in first} == {"negative", "neutral", "positive"}
    with pytest.raises(ValueError):
        select_balanced(rows, per_class=3)


def test_conflicting_duplicate_labels_are_not_silently_selected():
    with pytest.raises(ValueError, match="Conflicting"):
        select_balanced([("same", "positive"), ("same", "negative")], per_class=1)


@pytest.mark.parametrize("labels", [[], ["a", "a"]])
def test_metric_label_set_must_be_nonempty_and_unique(labels):
    with pytest.raises(ValueError):
        classification_metrics(["a"], ["a"], labels)


@pytest.mark.parametrize(
    "rows,count", [([], 0), ([("", "positive")], 1), ([("text", "unknown")], 1)]
)
def test_selection_rejects_invalid_configuration_and_rows(rows, count):
    with pytest.raises(ValueError):
        select_balanced(rows, per_class=count)


@pytest.mark.parametrize("values,percentile", [([1], 0), ([1], 1.1), ([float("nan")], 0.95)])
def test_percentile_rejects_invalid_observations(values, percentile):
    with pytest.raises(ValueError):
        nearest_rank(values, percentile)
