"""Token and cost accounting per phase, role and model."""

from __future__ import annotations

from dataclasses import asdict

from .config import Config
from .ledger import Ledger
from .limits import PhaseBudgets
from .providers import Result
from .runstate import RunState


def charge_usage(state: RunState, config: Config, phase: str, seat_role: str, result: Result) -> None:
    budgets = PhaseBudgets(state.allowance, state.spent)
    budgets.charge(phase, result.tokens_in + result.tokens_out)
    entry = Ledger(pricing=config.pricing).record(phase, result)
    state.usage.append({**asdict(entry), "role": seat_role})


def usage_report(state: RunState) -> dict:
    totals: dict[str, int] = {}
    cost, is_cost_complete = 0.0, True
    for row in state.usage:
        for key in (f"phase {row['phase']}", f"role {row['role']}", f"model {row['model_id']}"):
            totals[key] = totals.get(key, 0) + row["tokens_in"] + row["tokens_out"]
        if row["cost_usd"] is None:
            is_cost_complete = False
        else:
            cost += row["cost_usd"]
    has_estimates = any(not row["usage_known"] for row in state.usage)
    report = {key: f"{value} tokens" for key, value in sorted(totals.items())}
    report["cost"] = f"${cost:.4f}" + ("" if is_cost_complete else " plus unpriced or estimated usage")
    report["token counts"] = "include estimates" if has_estimates else "provider reported"
    return report


def total_tokens(state: RunState) -> int:
    return sum(row["tokens_in"] + row["tokens_out"] for row in state.usage)
