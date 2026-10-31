"""Eval measures. Token controls ship only if recall holds and cost falls."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .conclude import finish_run
from .decision import UNRESOLVED, normalize_option
from .diversity import DiversityError
from .run import start_run
from .runstate import RunState, RunStore
from .usage import total_tokens


DEFERRAL_COST = 0.25


def decision_regret(verdicts: Sequence[str], expected: Sequence[str]) -> float:
    """Mean regret: 0 for right, 1 for wrong, a fixed cost for UNRESOLVED."""
    def regret(verdict: str, answer: str) -> float:
        if verdict == answer:
            return 0.0
        return DEFERRAL_COST if verdict == UNRESOLVED else 1.0

    return sum(map(regret, verdicts, expected)) / len(verdicts)


def recall(expected: set[str], found: set[str]) -> float:
    return 1.0 if not expected else len(expected & found) / len(expected)


def brier_score(forecasts: Sequence[tuple[float, bool]]) -> float:
    """Mean squared error of probabilities against outcomes. Lower is better."""
    if not forecasts:
        raise ValueError("brier_score needs at least one forecast")
    return sum((p - float(hit)) ** 2 for p, hit in forecasts) / len(forecasts)


def control_passes(baseline: dict[str, float], candidate: dict[str, float]) -> bool:
    """Accept a control only when recall holds and cost falls."""
    holds_recall = candidate["recall"] > 0 and candidate["recall"] >= baseline["recall"]
    return holds_recall and candidate["cost"] < baseline["cost"]


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected: str
    options: tuple[str, ...] = ()


def load_cases(path: Path) -> list[EvalCase]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [EvalCase(r["question"], r["expected"], tuple(r.get("options", ()))) for r in rows]


def _verdict_of(config: Config, case: EvalCase, store: RunStore) -> tuple[str, int]:
    state = start_run(config, case.question, store, options=list(case.options))
    if not isinstance(state, RunState):
        return "ASKED", 0
    try:
        brief = finish_run(state, config, store)
    except DiversityError:
        return "FAILED_DIVERSITY", total_tokens(state)
    return brief.splitlines()[0].removeprefix("# Decision: "), total_tokens(state)


def _expected_verdict(case: EvalCase) -> str:
    return UNRESOLVED if case.expected == UNRESOLVED else normalize_option(case.expected)


def run_arm(config: Config, cases: list[EvalCase], store: RunStore) -> dict[str, float]:
    """Score one configuration. Cost is tokens, so arms compare without prices."""
    if not cases:
        raise ValueError("eval needs at least one case")
    verdicts, tokens = [], 0
    for case in cases:
        verdict, used = _verdict_of(config, case, store)
        verdicts.append(verdict)
        tokens += used
    expected = [_expected_verdict(case) for case in cases]
    correct = sum(map(str.__eq__, verdicts, expected))
    return {
        "recall": correct / len(cases), "cost": float(tokens),
        "regret": decision_regret(verdicts, expected),
    }
