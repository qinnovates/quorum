"""Weigh panel answers and produce one decision brief.

Weight comes from evidence, counted once per family and once per independent
source. Self-reported confidence, verbosity, persona count and token spend add
nothing. Agreement is not proof, so options the evidence cannot separate end
in UNRESOLVED.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from statistics import median

from .provenance import source_root
from .secrets import redact
from .source_match import UNMATCHED, best_assignment

UNRESOLVED = "UNRESOLVED"
TIER_WEIGHTS = {"STRONG": 1.0, "MODERATE": 0.6, "WEAK": 0.3, "UNVERIFIED": 0.1}
DISPUTED_FACTOR = 0.5
MIN_SEPARATION = 0.25
MIN_VERDICT_SCORE = 0.5
MAX_CLAIMS_PER_PANELIST = 8
MIN_SCORED_ITEMS = 20
CHECKED_TIERS = frozenset({"STRONG", "MODERATE"})
MAX_ANSWER_DEPTH = 32
_SOURCE = re.compile(r"(?i)^(https://[^/\s.]+(\.[^/\s.]+)+(/\S*)?|doi:10\.\S+|arxiv:\d\S+)$")
_OPTION_PREFIX = re.compile(r"^(use|choose|adopt|pick|go with)\s+")


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
    root: str = ""
    quote: str = ""
    issues: tuple[str, ...] = ()


@dataclass
class OptionScore:
    option: str
    score: float
    families: tuple[str, ...]
    independent_sources: int = 0


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
    criteria_rows: list[str] = field(default_factory=list)
    evidence_rows: list[str] = field(default_factory=list)


def _redact_tree(value: object) -> object:
    """Redact after decoding, because JSON escapes can hide a secret from regexes."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_tree(item) for item in value]
    if isinstance(value, dict):
        return {redact(str(key)): _redact_tree(item) for key, item in value.items()}
    return value


def embedded_json(text: str) -> object:
    """The JSON object inside model text. Bad or too-deep JSON raises ValueError."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in text")
    try:
        return json.loads(text[start:end + 1])
    except RecursionError:
        raise ValueError("JSON is nested too deeply") from None


def _nesting_depth(value: object) -> int:
    deepest, level = 0, [value]
    while level:
        deepest += 1
        level = [
            child for item in level if isinstance(item, (list, dict))
            for child in (item.values() if isinstance(item, dict) else item)
        ]
    return deepest


def parse_answer(text: str) -> dict:
    """Validate a panelist's JSON. Prose and refusals do not count as answers."""
    try:
        parsed = embedded_json(text)
        if _nesting_depth(parsed) > MAX_ANSWER_DEPTH:
            raise ValueError("nested too deeply")
        data = _redact_tree(parsed)
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise AnswerError("answer contains invalid unicode") from None
    except (ValueError, RecursionError) as exc:
        raise AnswerError(f"answer is not usable JSON ({exc})") from None
    if not isinstance(data, dict):
        raise AnswerError("answer needs an option and a claims list")
    option = data.get("option")
    claims = data.get("claims")
    if not isinstance(option, str) or not option.strip() or not isinstance(claims, list):
        raise AnswerError("answer needs an option and a claims list")
    clean = [
        c for c in claims
        if isinstance(c, dict) and isinstance(c.get("text"), str) and c["text"].strip()
    ]
    if not clean:
        raise AnswerError("answer needs at least one claim")
    data["claims"] = clean[:MAX_CLAIMS_PER_PANELIST]
    data["claims_dropped"] = len(clean) - len(data["claims"])
    return data


def assign_tier(
    source: str, verified_sources: frozenset[str], reachable_sources: frozenset[str] = frozenset()
) -> str:
    """Python assigns tiers. A panelist's own label is ignored.

    STRONG: you verified it, or its quote was found on the page.
    MODERATE: the page exists, but the quote was not found.
    WEAK: well-formed but unchecked, so it may be invented.
    """
    if source in verified_sources:
        return "STRONG"
    if source in reachable_sources:
        return "MODERATE"
    return "WEAK" if _SOURCE.match(source) else "UNVERIFIED"


def normalize_option(option: str) -> str:
    return _OPTION_PREFIX.sub("", re.sub(r"\s+", " ", option.strip().lower()))


def _claim_weight(claim: ScoredClaim, track_record: dict[str, float] | None) -> float:
    weight = TIER_WEIGHTS[claim.tier] * (DISPUTED_FACTOR if claim.is_disputed else 1.0)
    return weight * (track_record or {}).get(claim.family, 1.0)


def _root_of(claim: ScoredClaim) -> str:
    return claim.root or source_root(claim.source) or f"unsourced:{claim.family}"


def _score_option(option: str, claims: list[ScoredClaim], track_record: dict[str, float] | None) -> OptionScore:
    """The best pairing of families to sources, each used once. Three models citing one page are one source."""
    families = sorted({c.family for c in claims})
    roots = sorted({_root_of(c) for c in claims})
    weights = [[0.0] * len(roots) for _ in families]
    for claim in claims:
        row, column = families.index(claim.family), roots.index(_root_of(claim))
        weights[row][column] = max(weights[row][column], _claim_weight(claim, track_record))
    chosen = best_assignment(weights)
    picked = [(row, column) for row, column in enumerate(chosen) if column != UNMATCHED]
    documents = len({_root_of(c) for c in claims if c.source})
    return OptionScore(option, round(sum(weights[r][c] for r, c in picked), 4), tuple(families), documents)


def score_options(
    claims: list[ScoredClaim], track_record: dict[str, float] | None = None
) -> list[OptionScore]:
    by_option: dict[str, list[ScoredClaim]] = defaultdict(list)
    for claim in claims:
        by_option[claim.option].append(claim)
    scored = [_score_option(option, rows, track_record) for option, rows in by_option.items()]
    return sorted(scored, key=lambda s: (-s.score, s.option))


def evidence_rows(claims: list[ScoredClaim], scores: list[OptionScore]) -> list[str]:
    """The parts of confidence, shown separately until a score is calibrated."""
    rows = []
    for score in scores:
        mine = [c for c in claims if c.option == score.option]
        tiers = ", ".join(f"{sum(c.tier == t for c in mine)} {t}" for t in TIER_WEIGHTS if any(c.tier == t for c in mine))
        disputed, failed = sum(c.is_disputed for c in mine), sum(bool(c.issues) for c in mine)
        checked = len({_root_of(c) for c in mine if c.source and c.tier in CHECKED_TIERS})
        rows.append(
            f"{score.option}: {score.independent_sources} distinct cited document(s), {checked} checked, "
            f"{len(score.families)} family(ies); claims {tiers}; {disputed} disputed; {failed} failed a support check"
        )
    return rows


def _single_family(claims: list[ScoredClaim]) -> list[str]:
    families: dict[tuple[str, str], set[str]] = defaultdict(set)
    for claim in claims:
        families[claim.claim_id, claim.option].add(claim.family)
    seen = {(c.claim_id, c.option): c.text for c in claims}
    return [seen[key] for key, fams in families.items() if len(fams) == 1]


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
    top_claims = [c for c in claims if c.option == top.option]
    has_live_support = any(not c.is_disputed and c.tier != "UNVERIFIED" for c in top_claims)
    is_weak = top.score < MIN_VERDICT_SCORE or not has_live_support
    verdict = UNRESOLVED if is_close or is_weak else top.option
    return Brief(
        verdict=verdict,
        runner_up=runner.option if runner else None,
        scores=scores,
        why=[c.text for c in claims if c.option == top.option and not c.is_disputed][:3],
        against=[c.text for c in claims if c.option != top.option or c.is_disputed][:3],
        single_family=_single_family(claims),
        would_change=would_change[:3],
        unknowns=unknowns,
        evidence_rows=evidence_rows(claims, scores),
    )


def pivotal_claims(claims: list[ScoredClaim]) -> list[ScoredClaim]:
    """Claims that would change the verdict if disputed. Only these earn review.

    A family's claims for one option are tested together: a family counts once,
    so testing them one by one would let a second claim hide the first.
    """
    verdict = build_brief(claims, [], []).verdict
    pivotal = []
    for key in dict.fromkeys((c.family, c.option) for c in claims):
        trial = [replace(c, is_disputed=True) if (c.family, c.option) == key else c for c in claims]
        if build_brief(trial, [], []).verdict != verdict:
            pivotal += [c for c in claims if (c.family, c.option) == key]
    return pivotal


def criteria_fit(answers: list[dict], criteria: dict[str, float]) -> dict[str, float]:
    """Weighted median panel rating per option, 0 to 5, for the brief."""
    ratings: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for answer in answers:
        scores = answer.get("criteria_scores")
        for name in criteria:
            value = scores.get(name) if isinstance(scores, dict) else None
            if isinstance(value, (int, float)) and 0 <= value <= 5:
                ratings[normalize_option(answer["option"])][name].append(float(value))
    total = sum(criteria.values())
    return {
        option: round(sum(median(by_name.get(n, [0.0])) * w for n, w in criteria.items()) / total, 2)
        for option, by_name in ratings.items()
    } if total else {}


def _one_line(text: str) -> str:
    """Panel text cannot add headings, lines or auto-loading images to the brief."""
    return re.sub(r"\s+", " ", text).replace("![", "[image: ").replace("<", "&lt;").strip()


def _bullets(title: str, rows: list[str]) -> list[str]:
    return [f"**{title}**", *(f"- {_one_line(row)}" for row in rows), ""] if rows else []


def render_brief(brief: Brief, usage: dict) -> str:
    """Markdown brief. Everything rendered passes through redaction."""
    score_rows = [f"{s.option}: {s.score} ({', '.join(s.families)})" for s in brief.scores]
    usage_rows = [f"{k}: {v}" for k, v in usage.items()]
    lines = [
        f"# Decision: {_one_line(brief.verdict)}", "",
        *( [f"Next-best option: {_one_line(brief.runner_up)}", ""] if brief.runner_up else [] ),
        *_bullets("Why", brief.why),
        *_bullets("Strongest case against", brief.against),
        *_bullets("Raised by only one model family", brief.single_family),
        *_bullets("What would change this", brief.would_change),
        *_bullets("Unknown", brief.unknowns),
        *_bullets("Fit to your criteria (panel ratings, 0 to 5)", brief.criteria_rows),
        *_bullets("How options were weighed", score_rows),
        *_bullets("Evidence behind each option", brief.evidence_rows),
        *_bullets("Tokens and cost", usage_rows),
    ]
    return redact("\n".join(lines))
