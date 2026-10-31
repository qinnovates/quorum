"""Eval measures. Token controls ship only if recall holds and cost falls."""

from __future__ import annotations

from collections.abc import Callable, Sequence


def recall(expected: set[str], found: set[str]) -> float:
    return 1.0 if not expected else len(expected & found) / len(expected)


def brier_score(forecasts: Sequence[tuple[float, bool]]) -> float:
    """Mean squared error of probabilities against outcomes. Lower is better."""
    if not forecasts:
        raise ValueError("brier_score needs at least one forecast")
    return sum((p - float(hit)) ** 2 for p, hit in forecasts) / len(forecasts)


def flip_rate(verdict_for_order: Callable[[bool], str], repeats: int) -> float:
    """Share of paired runs whose verdict changes when panel order is reversed."""
    flips = sum(verdict_for_order(False) != verdict_for_order(True) for _ in range(repeats))
    return flips / repeats


def control_passes(baseline: dict[str, float], candidate: dict[str, float]) -> bool:
    """Accept a control only when recall holds and cost falls."""
    return candidate["recall"] >= baseline["recall"] and candidate["cost"] < baseline["cost"]
