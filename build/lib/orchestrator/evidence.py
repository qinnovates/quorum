"""Evidence-based model routing: which model has earned which role.

Rankings are data supplied by the user, never built in. A model with no
current, verified evidence for a role is `unproven`, and the run says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .router import Candidate, NoRoute

ROLES = frozenset({"intent", "architecture", "code", "research", "routing", "judge", "challenger"})
DEFAULT_MAX_AGE_DAYS = 180


@dataclass(frozen=True)
class RoleEvidence:
    model_id: str
    role: str
    metric: str
    score: float
    source: str
    measured_on: str
    is_verified: bool = False


@dataclass(frozen=True)
class RouteDecision:
    provider: str
    role: str
    status: str
    reason: str


def _clears_bar(item: RoleEvidence, bar: float, today: date, max_age_days: int) -> bool:
    age_days = (today - date.fromisoformat(item.measured_on)).days
    return item.is_verified and item.score >= bar and age_days <= max_age_days


def _pick(candidates: list[Candidate], prefer_strength: bool) -> Candidate:
    if prefer_strength:
        return max(candidates, key=lambda c: (c.strength, c.rank))
    return min(candidates, key=lambda c: c.rank)


def route_role(
    candidates: list[Candidate],
    role: str,
    needs: frozenset[str],
    evidence: list[RoleEvidence],
    bars: dict[str, float],
    today: date,
    *,
    family: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    prefer_strength: bool = False,
) -> RouteDecision:
    """Cheapest candidate that clears the bar, or strongest on high stakes.

    With no evidence, the same preference applies and the choice is `unproven`.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; use one of {sorted(ROLES)}")
    eligible = [
        c for c in candidates
        if needs <= c.capabilities and (family is None or c.family == family)
    ]
    if not eligible:
        raise NoRoute(f"no provider can fill role {role} (family={family})")
    bar = bars.get(role)
    proven = {}
    if bar is not None:
        for item in evidence:
            if item.role == role and _clears_bar(item, bar, today, max_age_days):
                proven[item.model_id] = item
    cleared = [c for c in eligible if c.model_id in proven]
    if cleared:
        chosen = _pick(cleared, prefer_strength)
        item = proven[chosen.model_id]
        reason = f"{item.metric}={item.score} (source: {item.source}, {item.measured_on}); above bar {bar}"
        return RouteDecision(chosen.name, role, "proven", reason)
    chosen = _pick(eligible, prefer_strength)
    label = "strongest" if prefer_strength else "cheapest"
    return RouteDecision(chosen.name, role, "unproven", f"no current verified evidence for {role}; {label} eligible")
