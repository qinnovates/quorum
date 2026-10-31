"""Eval measure tests."""

import pytest

from orchestrator.evaluation import brier_score, control_passes, recall


def test_recall_and_brier():
    assert recall({"a", "b"}, {"a"}) == 0.5
    assert brier_score([(1.0, True), (0.0, True)]) == 0.5
    with pytest.raises(ValueError):
        brier_score([])


def test_control_rejected_when_recall_drops():
    baseline = {"recall": 0.9, "cost": 10.0}
    assert not control_passes(baseline, {"recall": 0.8, "cost": 1.0})
    assert control_passes(baseline, {"recall": 0.9, "cost": 8.0})
