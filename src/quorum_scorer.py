"""
Quorum Scorer v7.3.0 — Offline scoring harness for Quorum deliberations.

Computes convergence (C/C*), CDI, vote weights, evidence scores, and
calibration penalties from structured agent output. This module implements
the mathematical specifications from ARCHITECTURE.md and SKILL.md.

Usage:
    from quorum_scorer import compute_round_scores, ScoringConfig, RoundData
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Literal

EvidenceTier = Literal["STRONG", "MODERATE", "WEAK", "UNVERIFIED"]
ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]

EVIDENCE_TIER_WEIGHT: dict[EvidenceTier, float] = {
    "STRONG": 1.0,
    "MODERATE": 0.7,
    "WEAK": 0.3,
    "UNVERIFIED": 0.0,
}

EVIDENCE_TIER_MULT: dict[EvidenceTier, float] = {
    "STRONG": 1.5,
    "MODERATE": 1.0,
    "WEAK": 0.5,
    "UNVERIFIED": 0.5,
}

CONFIDENCE_MAP: dict[ConfidenceLevel, int] = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

TIER_NUMERIC: dict[EvidenceTier, int] = {
    "STRONG": 3,
    "MODERATE": 2,
    "WEAK": 1,
    "UNVERIFIED": 0,
}


@dataclass
class Claim:
    text: str
    source: str | None = None
    source_tier: EvidenceTier = "UNVERIFIED"
    agent_id: str = ""
    confidence: ConfidenceLevel = "MEDIUM"
    round_num: int = 1
    relevance: float = 1.0  # cosine similarity to source (0-1)


@dataclass
class Attack:
    attacker_id: str
    target_claim_text: str
    survived: bool
    round_num: int = 1


@dataclass
class AgentOutput:
    agent_id: str
    claims: list[Claim] = field(default_factory=list)
    attacks: list[Attack] = field(default_factory=list)
    hedged_claims: int = 0
    total_claims: int = 0
    vote_confidence: int = 5  # 1-10 scale for structured vote
    vote_rationale_tier: EvidenceTier = "MODERATE"
    cdp_profile: tuple[int, int, int] = (1, 1, 1)
    model: str = "claude"
    overlap_with_covoters: float = 0.5  # 0=independent, 1=echo


@dataclass
class RoundData:
    round_number: int
    agent_outputs: list[AgentOutput] = field(default_factory=list)
    claims_held: list[str] = field(default_factory=list)


@dataclass
class ScoringConfig:
    tau_match: float = 0.85
    cdi_weights: tuple[float, float, float, float] = (0.15, 0.3, 0.3, 0.25)
    novelty_termination_threshold: float = 0.1
    novelty_termination_rounds: int = 2
    source_dedup_threshold: int = 3


@dataclass
class ScoringTrace:
    round_number: int
    A: float
    D: float
    N: float
    C: float
    CDI: float
    C_star: float
    evidence_scores: dict[str, float]
    vote_weights: dict[str, float]
    calibration: dict[str, dict[str, float]]
    outcome: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def agreement_growth(
    current_held: list[str],
    previous_held: list[str],
) -> float:
    """Compute A: fraction of previous claims still held.

    Uses exact string matching (offline harness). In production, semantic
    similarity with tau_match=0.85 would replace this.
    """
    if not previous_held:
        return 0.0
    held_set = set(current_held)
    prev_set = set(previous_held)
    intersection = held_set & prev_set
    return len(intersection) / len(prev_set)


def defense_success_rate(attacks: list[Attack]) -> float:
    """Compute D: fraction of attacks where the target claim survived."""
    if not attacks:
        return 1.0  # no attacks = nothing to defend against
    survived = sum(1 for a in attacks if a.survived)
    return survived / len(attacks)


def novelty_decay(
    new_claims_this_round: int,
    new_claims_round_1: int,
) -> float:
    """Compute N: termination signal (not scored).

    N = 1 - (new_this_round / new_round_1)
    N approaching 1.0 means no new arguments.
    """
    if new_claims_round_1 == 0:
        return 0.0  # no baseline data — assume full novelty, don't terminate
    return 1.0 - (new_claims_this_round / max(new_claims_round_1, 1))


def compute_cdi(
    d_p: float,
    d_r: float,
    d_o: float,
    d_m: float = 0.0,
    weights: tuple[float, float, float, float] = (0.15, 0.3, 0.3, 0.25),
) -> float:
    """Compute Cognitive Diversity Index.

    Args:
        d_p: persona diversity [0,1]
        d_r: reasoning path diversity [0,1]
        d_o: opinion diversity [0,1]
        d_m: model diversity [0,1] (0 if all same model)
        weights: tunable hyperparameters (defaults per v7.3.0)
    """
    if abs(d_m) < 1e-9:
        # Non-diverse model tier: rescale to 3-term weights [0.2, 0.4, 0.4]
        # so the index sums to 1.0 when all three dimensions are 1.0.
        return 0.2 * d_p + 0.4 * d_r + 0.4 * d_o
    return (
        weights[0] * d_p
        + weights[1] * d_r
        + weights[2] * d_o
        + weights[3] * d_m
    )


def hedging_penalty(agent: AgentOutput) -> float:
    """Compute H: fraction of vaguely hedged claims.

    Returns hedge_multiplier in [0.7, 1.0].
    """
    if agent.total_claims == 0:
        return 1.0
    h = agent.hedged_claims / agent.total_claims
    return 1.0 - (0.3 * h)


def overconfidence_penalty(agent: AgentOutput) -> float:
    """Compute O: fraction of claims where confidence exceeds evidence tier.

    Returns overconfidence_multiplier in [0.1, 1.0].
    """
    if not agent.claims:
        return 1.0
    overclaimed = 0
    for claim in agent.claims:
        if CONFIDENCE_MAP[claim.confidence] > TIER_NUMERIC[claim.source_tier]:
            overclaimed += 1
    o = overclaimed / len(agent.claims)
    return max(0.1, 1.0 - o)


def compute_evidence_score(
    claim: Claim,
    source_dedup_ratio: float = 1.0,
) -> float:
    """Compute E(claim) = source_weight(tier) * relevance * dedup_ratio."""
    base = EVIDENCE_TIER_WEIGHT[claim.source_tier] * claim.relevance
    return base * source_dedup_ratio


def compute_vote_weight(agent: AgentOutput) -> float:
    """Compute vote_weight for structured vote.

    vote_weight = confidence * evidence_tier_mult * independence_mult
                  * hedge_mult * overconf_mult
    """
    confidence = agent.vote_confidence

    evidence_tier_mult = EVIDENCE_TIER_MULT[agent.vote_rationale_tier]

    overlap = agent.overlap_with_covoters
    if overlap < 0.3:
        independence_mult = 1.2
    elif overlap > 0.7:
        independence_mult = 0.8
    else:
        independence_mult = 1.0

    hedge_mult = hedging_penalty(agent)
    overconf_mult = overconfidence_penalty(agent)

    return (
        confidence
        * evidence_tier_mult
        * independence_mult
        * hedge_mult
        * overconf_mult
    )


def source_dedup_ratio(claims: list[Claim], threshold: int = 3) -> float:
    """Compute unique_sources / total_citations when citations > threshold."""
    sources = [c.source for c in claims if c.source is not None]
    if len(sources) <= threshold:
        return 1.0
    unique = len(set(sources))
    return unique / len(sources)


def classify_outcome(
    c_star: float,
    n_history: list[float],
    round_number: int,
    config: ScoringConfig,
) -> str:
    """Classify the round outcome based on C* and termination signals."""
    if c_star >= 0.8:
        return "CONVERGED"

    if len(n_history) >= config.novelty_termination_rounds:
        recent = n_history[-config.novelty_termination_rounds :]
        if all(n > (1.0 - config.novelty_termination_threshold) for n in recent):
            return "EXHAUSTED"
    if c_star >= 0.65:
        return "VOTE"
    if c_star >= 0.5:
        return "CONTINUE"
    if round_number >= 3:
        return "TENSION"
    return "CONTINUE"


def compute_round_scores(
    current: RoundData,
    previous: RoundData | None,
    config: ScoringConfig,
    n_history: list[float] | None = None,
    new_claims_round_1: int = 0,
    new_claims_this_round: int = 0,
    d_p: float = 0.5,
    d_r: float = 0.5,
    d_o: float = 0.5,
    d_m: float = 0.0,
) -> ScoringTrace:
    """Compute all scores for a single round.

    Args:
        current: this round's agent outputs and claims held
        previous: last round's data (None for round 1)
        config: scoring configuration
        n_history: list of N values from all prior rounds
        new_claims_round_1: count of new claims in round 1
        new_claims_this_round: count of new claims this round
        d_p, d_r, d_o, d_m: diversity dimensions for CDI
    """
    if n_history is None:
        n_history = []

    prev_held = previous.claims_held if previous else []
    A = agreement_growth(current.claims_held, prev_held)

    all_attacks = []
    for agent in current.agent_outputs:
        all_attacks.extend(agent.attacks)
    D = defense_success_rate(all_attacks)

    N = novelty_decay(new_claims_this_round, new_claims_round_1)

    C = (A * 0.6) + (D * 0.4)

    CDI = compute_cdi(d_p, d_r, d_o, d_m, config.cdi_weights)
    C_star = C * (1.0 + 0.3 * (CDI - 0.5))

    all_claims = []
    for agent in current.agent_outputs:
        all_claims.extend(agent.claims)
    dedup = source_dedup_ratio(all_claims, config.source_dedup_threshold)

    evidence_scores: dict[str, float] = {}
    for claim in all_claims:
        key = f"{claim.agent_id}:{claim.text}"
        evidence_scores[key] = compute_evidence_score(claim, dedup)

    calibration: dict[str, dict[str, float]] = {}
    for agent in current.agent_outputs:
        calibration[agent.agent_id] = {
            "hedge_mult": hedging_penalty(agent),
            "overconf_mult": overconfidence_penalty(agent),
        }

    full_n_history = n_history + [N]
    outcome = classify_outcome(C_star, full_n_history, current.round_number, config)

    vote_weights: dict[str, float] = {}
    if outcome == "VOTE":
        for agent in current.agent_outputs:
            vote_weights[agent.agent_id] = compute_vote_weight(agent)

    return ScoringTrace(
        round_number=current.round_number,
        A=round(A, 4),
        D=round(D, 4),
        N=round(N, 4),
        C=round(C, 4),
        CDI=round(CDI, 4),
        C_star=round(C_star, 4),
        evidence_scores={k: round(v, 4) for k, v in evidence_scores.items()},
        vote_weights={k: round(v, 4) for k, v in vote_weights.items()},
        calibration=calibration,
        outcome=outcome,
    )
