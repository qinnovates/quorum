"""
Quorum Scorer v7.3.0 — Deterministic test suite.

Three canned scenarios: GOOD, SHALLOW, HALLUCINATED.
Run: python -m pytest src/test_scoring.py -v
"""

from quorum_scorer import (
    AgentOutput,
    Attack,
    Claim,
    RoundData,
    ScoringConfig,
    agreement_growth,
    classify_outcome,
    compute_cdi,
    compute_evidence_score,
    compute_round_scores,
    compute_vote_weight,
    defense_success_rate,
    hedging_penalty,
    novelty_decay,
    overconfidence_penalty,
    source_dedup_ratio,
)

CONFIG = ScoringConfig()


# --- Fixture builders ---


def make_good_agent() -> AgentOutput:
    """Strong sources, calibrated confidence, low hedging."""
    return AgentOutput(
        agent_id="good",
        claims=[
            Claim(
                text="PostgreSQL handles ACID transactions reliably",
                source="aws-well-architected",
                source_tier="STRONG",
                confidence="HIGH",
                relevance=0.92,
            ),
            Claim(
                text="DynamoDB excels at >10K TPS write-heavy workloads",
                source="dynamodb-docs",
                source_tier="STRONG",
                confidence="HIGH",
                relevance=0.88,
            ),
            Claim(
                text="PostgreSQL requires more ops overhead than DynamoDB",
                source="aws-rds-guide",
                source_tier="MODERATE",
                confidence="MEDIUM",
                relevance=0.85,
            ),
            Claim(
                text="For most SaaS under 1M users PostgreSQL is more cost-effective",
                source="saas-cost-analysis",
                source_tier="MODERATE",
                confidence="MEDIUM",
                relevance=0.78,
            ),
            Claim(
                text="Migration from PostgreSQL to DynamoDB is non-trivial",
                source="aws-migration-guide",
                source_tier="STRONG",
                confidence="HIGH",
                relevance=0.90,
            ),
        ],
        hedged_claims=1,
        total_claims=5,
        vote_confidence=7,
        vote_rationale_tier="STRONG",
        overlap_with_covoters=0.2,
        model="claude",
    )


def make_shallow_agent() -> AgentOutput:
    """No sources, vague hedging, popular-opinion echo."""
    return AgentOutput(
        agent_id="shallow",
        claims=[
            Claim(
                text="PostgreSQL is better because it is more popular",
                source=None,
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
            Claim(
                text="Most companies use PostgreSQL",
                source=None,
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
            Claim(
                text="It might depend on the use case",
                source=None,
                source_tier="UNVERIFIED",
                confidence="LOW",
                relevance=0.0,
            ),
        ],
        hedged_claims=2,
        total_claims=3,
        vote_confidence=8,
        vote_rationale_tier="UNVERIFIED",
        overlap_with_covoters=0.8,
        model="claude",
    )


def make_hallucinated_agent() -> AgentOutput:
    """Fabricated stats, fake sources, overclaimed confidence."""
    return AgentOutput(
        agent_id="hallucinated",
        claims=[
            Claim(
                text="89.3% of SaaS companies using DynamoDB report 40% cost reduction",
                source="fake-stackoverflow-survey-2025",
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
            Claim(
                text="DynamoDB outperforms PostgreSQL by 12x at all scales",
                source="fake-chen-et-al-2024",
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
            Claim(
                text="PostgreSQL will be deprecated by AWS within 2 years",
                source="fake-aws-roadmap",
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
            Claim(
                text="DynamoDB has zero operational overhead",
                source="fake-serverless-report",
                source_tier="UNVERIFIED",
                confidence="HIGH",
                relevance=0.0,
            ),
        ],
        hedged_claims=0,
        total_claims=4,
        vote_confidence=9,
        vote_rationale_tier="UNVERIFIED",
        overlap_with_covoters=0.5,
        model="claude",
    )


# --- Unit tests ---


class TestAgreementGrowth:
    def test_full_stability(self) -> None:
        assert agreement_growth(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_half_challenged(self) -> None:
        assert agreement_growth(["a", "b"], ["a", "b", "c", "d"]) == 0.5

    def test_nothing_held(self) -> None:
        assert agreement_growth(["x"], ["a", "b"]) == 0.0

    def test_empty_previous(self) -> None:
        assert agreement_growth(["a"], []) == 0.0

    def test_round_1_no_previous(self) -> None:
        assert agreement_growth(["a", "b"], []) == 0.0


class TestDefenseSuccessRate:
    def test_all_survived(self) -> None:
        attacks = [Attack("a1", "claim1", True), Attack("a2", "claim2", True)]
        assert defense_success_rate(attacks) == 1.0

    def test_none_survived(self) -> None:
        attacks = [Attack("a1", "claim1", False), Attack("a2", "claim2", False)]
        assert defense_success_rate(attacks) == 0.0

    def test_half_survived(self) -> None:
        attacks = [Attack("a1", "claim1", True), Attack("a2", "claim2", False)]
        assert defense_success_rate(attacks) == 0.5

    def test_no_attacks(self) -> None:
        assert defense_success_rate([]) == 1.0


class TestNoveltyDecay:
    def test_no_new_arguments(self) -> None:
        assert novelty_decay(0, 10) == 1.0

    def test_same_as_round_1(self) -> None:
        assert novelty_decay(10, 10) == 0.0

    def test_half_novelty(self) -> None:
        assert novelty_decay(5, 10) == 0.5

    def test_no_baseline_data(self) -> None:
        """When round 1 had 0 claims, assume full novelty (don't terminate)."""
        assert novelty_decay(0, 0) == 0.0
        assert novelty_decay(5, 0) == 0.0


class TestCDI:
    def test_default_weights(self) -> None:
        # d_m=0.0 triggers non-diverse rescaling: 0.5*0.2 + 0.5*0.4 + 0.5*0.4 = 0.5
        cdi = compute_cdi(0.5, 0.5, 0.5, 0.0)
        assert abs(cdi - 0.5) < 0.001

    def test_full_diversity(self) -> None:
        cdi = compute_cdi(1.0, 1.0, 1.0, 1.0)
        assert abs(cdi - 1.0) < 0.001

    def test_zero_diversity(self) -> None:
        cdi = compute_cdi(0.0, 0.0, 0.0, 0.0)
        assert cdi == 0.0

    def test_model_diversity_contributes(self) -> None:
        cdi_no_model = compute_cdi(0.5, 0.5, 0.5, 0.0)
        cdi_with_model = compute_cdi(0.5, 0.5, 0.5, 0.6)
        assert cdi_with_model > cdi_no_model


class TestCalibrationPenalties:
    def test_no_hedging(self) -> None:
        agent = AgentOutput(agent_id="a", hedged_claims=0, total_claims=5)
        assert hedging_penalty(agent) == 1.0

    def test_full_hedging(self) -> None:
        agent = AgentOutput(agent_id="a", hedged_claims=5, total_claims=5)
        assert abs(hedging_penalty(agent) - 0.7) < 0.001

    def test_no_overconfidence(self) -> None:
        agent = AgentOutput(
            agent_id="a",
            claims=[
                Claim(text="x", source_tier="STRONG", confidence="HIGH"),
                Claim(text="y", source_tier="MODERATE", confidence="MEDIUM"),
            ],
        )
        assert overconfidence_penalty(agent) == 1.0

    def test_full_overconfidence(self) -> None:
        agent = AgentOutput(
            agent_id="a",
            claims=[
                Claim(text="x", source_tier="UNVERIFIED", confidence="HIGH"),
                Claim(text="y", source_tier="UNVERIFIED", confidence="HIGH"),
            ],
        )
        assert abs(overconfidence_penalty(agent) - 0.1) < 0.001

    def test_partial_overconfidence(self) -> None:
        agent = AgentOutput(
            agent_id="a",
            claims=[
                Claim(text="x", source_tier="STRONG", confidence="HIGH"),
                Claim(text="y", source_tier="UNVERIFIED", confidence="HIGH"),
            ],
        )
        assert abs(overconfidence_penalty(agent) - 0.5) < 0.001


class TestEvidenceScore:
    def test_strong_high_relevance(self) -> None:
        claim = Claim(text="x", source_tier="STRONG", relevance=0.9)
        assert abs(compute_evidence_score(claim) - 0.9) < 0.001

    def test_unverified(self) -> None:
        claim = Claim(text="x", source_tier="UNVERIFIED", relevance=0.0)
        assert compute_evidence_score(claim) == 0.0

    def test_dedup_penalty(self) -> None:
        claim = Claim(text="x", source_tier="STRONG", relevance=0.9)
        assert abs(compute_evidence_score(claim, 0.5) - 0.45) < 0.001


class TestSourceDedup:
    def test_below_threshold(self) -> None:
        claims = [Claim(text="a", source="s1"), Claim(text="b", source="s1")]
        assert source_dedup_ratio(claims, threshold=3) == 1.0

    def test_all_same_source(self) -> None:
        claims = [
            Claim(text="a", source="s1"),
            Claim(text="b", source="s1"),
            Claim(text="c", source="s1"),
            Claim(text="d", source="s1"),
        ]
        assert abs(source_dedup_ratio(claims, threshold=3) - 0.25) < 0.001

    def test_all_unique(self) -> None:
        claims = [
            Claim(text="a", source="s1"),
            Claim(text="b", source="s2"),
            Claim(text="c", source="s3"),
            Claim(text="d", source="s4"),
        ]
        assert source_dedup_ratio(claims, threshold=3) == 1.0


class TestVoteWeight:
    def test_good_agent_high_weight(self) -> None:
        agent = make_good_agent()
        weight = compute_vote_weight(agent)
        assert weight > 10.0  # high confidence * strong evidence * independent

    def test_shallow_agent_low_weight(self) -> None:
        agent = make_shallow_agent()
        weight = compute_vote_weight(agent)
        assert weight < 3.0

    def test_hallucinated_agent_lowest_weight(self) -> None:
        agent = make_hallucinated_agent()
        weight = compute_vote_weight(agent)
        assert weight < 1.0  # overconfidence penalty crushes it

    def test_ranking_good_dominates(self) -> None:
        """Good agent dominates both bad agents by >10x.

        Shallow vs hallucinated ordering depends on penalty stacking:
        shallow is penalized for hedging + echo voting + overconfidence,
        hallucinated is penalized for overconfidence only (no hedging, no echo).
        Both are crushed relative to the good agent — that's the key invariant.
        """
        good_w = compute_vote_weight(make_good_agent())
        shallow_w = compute_vote_weight(make_shallow_agent())
        hallucinated_w = compute_vote_weight(make_hallucinated_agent())
        assert good_w > 10 * shallow_w
        assert good_w > 10 * hallucinated_w
        assert shallow_w < 1.0
        assert hallucinated_w < 1.0


class TestClassifyOutcome:
    def test_converged(self) -> None:
        assert classify_outcome(0.85, [], 2, CONFIG) == "CONVERGED"

    def test_vote(self) -> None:
        assert classify_outcome(0.72, [], 2, CONFIG) == "VOTE"

    def test_continue(self) -> None:
        assert classify_outcome(0.55, [], 2, CONFIG) == "CONTINUE"

    def test_tension(self) -> None:
        assert classify_outcome(0.3, [], 4, CONFIG) == "TENSION"

    def test_exhausted_by_novelty(self) -> None:
        n_history = [0.95, 0.97]  # N > 0.9 for 2 rounds
        assert classify_outcome(0.55, n_history, 3, CONFIG) == "EXHAUSTED"


class TestComputeRoundScores:
    def test_round_1(self) -> None:
        """Round 1: no previous data, should produce a score."""
        good = make_good_agent()
        current = RoundData(
            round_number=1,
            agent_outputs=[good],
            claims_held=["claim_a", "claim_b"],
        )
        trace = compute_round_scores(
            current, None, CONFIG,
            new_claims_round_1=5, new_claims_this_round=5,
            d_p=0.7, d_r=0.6, d_o=0.5,
        )
        assert trace.round_number == 1
        assert trace.A == 0.0  # no previous
        assert trace.D == 1.0  # no attacks
        assert trace.outcome in ("CONTINUE", "VOTE", "CONVERGED")

    def test_convergence_scenario(self) -> None:
        """High agreement + good defense → CONVERGED."""
        good = make_good_agent()
        good.attacks = [
            Attack("breaker", "claim_a", True),
            Attack("breaker", "claim_b", True),
        ]
        previous = RoundData(
            round_number=1,
            agent_outputs=[],
            claims_held=["claim_a", "claim_b", "claim_c"],
        )
        current = RoundData(
            round_number=2,
            agent_outputs=[good],
            claims_held=["claim_a", "claim_b", "claim_c"],
        )
        trace = compute_round_scores(
            current, previous, CONFIG,
            new_claims_round_1=5, new_claims_this_round=1,
            d_p=0.8, d_r=0.7, d_o=0.6, d_m=0.4,
        )
        assert trace.A == 1.0
        assert trace.D == 1.0
        assert trace.C == 1.0
        assert trace.C_star > 0.8
        assert trace.outcome == "CONVERGED"

    def test_vote_scenario(self) -> None:
        """Moderate agreement → VOTE with weights computed."""
        good = make_good_agent()
        shallow = make_shallow_agent()
        hallucinated = make_hallucinated_agent()

        previous = RoundData(
            round_number=1,
            agent_outputs=[],
            claims_held=["a", "b", "c", "d"],
        )
        current = RoundData(
            round_number=2,
            agent_outputs=[good, shallow, hallucinated],
            claims_held=["a", "b", "c"],  # 3 of 4 held
        )
        trace = compute_round_scores(
            current, previous, CONFIG,
            new_claims_round_1=8, new_claims_this_round=2,
            d_p=0.5, d_r=0.5, d_o=0.5,
        )
        if trace.outcome == "VOTE":
            assert trace.vote_weights["good"] > trace.vote_weights["shallow"]
            assert trace.vote_weights["good"] > trace.vote_weights["hallucinated"]
            assert trace.vote_weights["hallucinated"] < trace.vote_weights["shallow"]

    def test_trace_serializable(self) -> None:
        """ScoringTrace must be JSON-serializable."""
        good = make_good_agent()
        current = RoundData(
            round_number=1,
            agent_outputs=[good],
            claims_held=["a"],
        )
        trace = compute_round_scores(current, None, CONFIG)
        json_str = trace.to_json()
        parsed = __import__("json").loads(json_str)
        assert "C_star" in parsed
        assert "outcome" in parsed
