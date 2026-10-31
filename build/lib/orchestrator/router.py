"""Model routing: cheapest adequate adapter, escalate only on a trigger.

`rank` is declared in the config (lower is cheaper). The router never
guesses prices. Escalation thresholds come from the eval; the confidence
trigger is disabled until a floor is configured, and the run reports that.
"""

from __future__ import annotations

from dataclasses import dataclass


class NoRoute(RuntimeError):
    pass


@dataclass(frozen=True)
class Candidate:
    name: str
    family: str
    capabilities: frozenset[str]
    rank: int
    model_id: str = ""
    strength: int = 0


def choose(
    candidates: list[Candidate],
    needs: frozenset[str],
    family: str | None = None,
) -> Candidate:
    """Cheapest candidate that has every needed capability and the family."""
    eligible = [
        c
        for c in candidates
        if needs <= c.capabilities and (family is None or c.family == family)
    ]
    if not eligible:
        raise NoRoute(f"no provider has {sorted(needs)} (family={family})")
    return min(eligible, key=lambda c: c.rank)


@dataclass(frozen=True)
class EscalationSignals:
    contradiction: bool = False
    disputed_strong_claim: bool = False
    verdict_confidence: float | None = None
    ratify: bool = False
    confidence_floor: float | None = None


def escalation_reasons(sig: EscalationSignals) -> list[str]:
    """Every trigger that fires. Empty list means stay on the cheap route."""
    reasons = []
    if sig.contradiction:
        reasons.append("triage found a contradiction between strong claims")
    if sig.disputed_strong_claim:
        reasons.append("a STRONG-tier claim is disputed")
    if sig.ratify:
        reasons.append("--ratify requires the strongest model")
    if (
        sig.confidence_floor is not None
        and sig.verdict_confidence is not None
        and sig.verdict_confidence < sig.confidence_floor
    ):
        reasons.append(
            f"verdict confidence {sig.verdict_confidence:.2f} below floor {sig.confidence_floor:.2f}"
        )
    return reasons


def escalate(candidates: list[Candidate], needs: frozenset[str]) -> Candidate:
    """Strongest eligible candidate, by declared strength, then rank."""
    eligible = [c for c in candidates if needs <= c.capabilities]
    if not eligible:
        raise NoRoute(f"no provider has {sorted(needs)} for escalation")
    return max(eligible, key=lambda c: (c.strength, c.rank))
