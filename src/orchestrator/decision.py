"""Weigh panel answers and produce one decision brief.

Weight comes from evidence, counted once per family. Self-reported confidence,
verbosity, persona count and token spend add nothing. Agreement is not proof,
so options the evidence cannot separate end in UNRESOLVED.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field

from .secrets import redact

UNRESOLVED = "UNRESOLVED"
TIER_WEIGHTS = {"STRONG": 1.0, "MODERATE": 0.6, "WEAK": 0.3, "UNVERIFIED": 0.1}
DISPUTED_FACTOR = 0.5
MIN_SEPARATION = 0.25
MAX_CLAIMS_PER_PANELIST = 8
MIN_SCORED_ITEMS = 20
_SOURCE = re.compile(r"(?i)^(https://|doi:|arxiv:)\S+")


class AnswerError(ValueError):
    """Panel output is not a usable answer; refusals land here."""


@dataclass(frozen=True)
class ScoredClaim:
    claim_id: str
    text: str
    source: str
    tier: str
    option: str
    family: str
    is_disputed: bool = False


@dataclass
class OptionScore:
    option: str
    score: float
    families: tuple[str, ...]


@dataclass
class Brief:
    verdict: str
    runner_up: str | None
    scores: list[OptionScore]
    why: list[str] = field(default_factory=list)
    against: list[str] = field(default_factory=list)
    single_family: list[str] = field(default_factory=list)
    would_change: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)


def parse_answer(text: str) -> dict:
    """Validate a panelist's JSON. Prose and refusals do not count as answers."""
    match = re.search(r"\{.*\}", text, re.S)
    if match is None:
        raise AnswerError("no JSON object in answer")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AnswerError(f"invalid JSON at position {exc.pos}") from None
    option = data.get("option")
    claims = data.get("claims")
    if not isinstance(option, str) or not option.strip() or not isinstance(claims, list):
        raise AnswerError("answer needs an option and a claims list")
    clean = [c for c in claims if isinstance(c, dict) and isinstance(c.get("text"), str)]
    data["claims"] = clean[:MAX_CLAIMS_PER_PANELIST]
    return data


def assign_tier(source: str, verified_sources: frozenset[str]) -> str:
    """Python assigns tiers. A panelist's own label is ignored."""
    if source in verified_sources:
        return "STRONG"
    return "MODERATE" if _SOURCE.match(source) else "UNVERIFIED"


def normalize_option(option: str) -> str:
    return re.sub(r"\s+", " ", option.strip().lower())


def score_options(
    claims: list[ScoredClaim], track_record: dict[str, float] | None = None
) -> list[OptionScore]:
    """Each family adds its best claim once per option."""
    best: dict[str, dict[str, float]] = defaultdict(dict)
    for claim in claims:
        weight = TIER_WEIGHTS[claim.tier] * (DISPUTED_FACTOR if claim.is_disputed else 1.0)
        weight *= (track_record or {}).get(claim.family, 1.0)
        best[claim.option][claim.family] = max(best[claim.option].get(claim.family, 0.0), weight)
    scored = [
        OptionScore(option, round(sum(by_family.values()), 4), tuple(sorted(by_family)))
        for option, by_family in best.items()
    ]
    return sorted(scored, key=lambda s: (-s.score, s.option))


def _single_family(claims: list[ScoredClaim]) -> list[str]:
    families: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        families[claim.claim_id].add(claim.family)
    seen = {c.claim_id: c.text for c in claims}
    return [seen[cid] for cid, fams in families.items() if len(fams) == 1]


def build_brief(
    claims: list[ScoredClaim],
    would_change: list[str],
    unknowns: list[str],
    track_record: dict[str, float] | None = None,
) -> Brief:
    scores = score_options(claims, track_record)
    if not scores:
        return Brief(UNRESOLVED, None, [], unknowns=["No usable evidence was produced."])
    top = scores[0]
    runner = scores[1] if len(scores) > 1 else None
    is_close = runner is not None and top.score - runner.score < MIN_SEPARATION
    verdict = UNRESOLVED if is_close else top.option
    return Brief(
        verdict=verdict,
        runner_up=runner.option if runner else None,
        scores=scores,
        why=[c.text for c in claims if c.option == top.option and not c.is_disputed][:3],
        against=[c.text for c in claims if c.option != top.option or c.is_disputed][:3],
        single_family=_single_family(claims),
        would_change=would_change[:3],
        unknowns=unknowns,
    )


def _bullets(title: str, rows: list[str]) -> list[str]:
    return [f"**{title}**", *(f"- {row}" for row in rows), ""] if rows else []


def render_brief(brief: Brief, usage: dict) -> str:
    """Markdown brief. Everything rendered passes through redaction."""
    score_rows = [f"{s.option}: {s.score} ({', '.join(s.families)})" for s in brief.scores]
    usage_rows = [f"{k}: {v}" for k, v in usage.items()]
    lines = [
        f"# Decision: {brief.verdict}", "",
        *( [f"Next-best option: {brief.runner_up}", ""] if brief.runner_up else [] ),
        *_bullets("Why", brief.why),
        *_bullets("Strongest case against", brief.against),
        *_bullets("Raised by only one model family", brief.single_family),
        *_bullets("What would change this", brief.would_change),
        *_bullets("Unknown", brief.unknowns),
        *_bullets("How options were weighed", score_rows),
        *_bullets("Tokens and cost", usage_rows),
    ]
    return redact("\n".join(lines))
