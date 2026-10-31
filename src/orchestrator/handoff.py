"""Compact handoff payloads between phases and agents.

Today every Phase 2 analysis agent receives the full Research Pool. This
module builds a per-agent payload instead: deduplicated claims with stable
IDs, capped by evidence tier, plus open questions and a short debate
summary. Dedupe is deterministic code, not an LLM call.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata

from quorum_scorer import Claim

from .secrets import redact

TIER_ORDER = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "UNVERIFIED": 3}
TEXT_CAP = 600
SUMMARY_CAP = 400
ID_HEX_CHARS = 16
_TRAILING_PUNCTUATION = ".,;:!? "
PARTIAL_CLAIM_NOTE = 'A claim marked "partial" was shortened: do not infer its missing conditions.'


def _normalized(text: str) -> str:
    """Fold case and spacing only. Symbols and units such as < and MW carry meaning."""
    words = unicodedata.normalize("NFC", text).split()
    kept = [
        word if any(c.isdigit() for c in word) or (i and words[i - 1][-1].isdigit()) else word.casefold()
        for i, word in enumerate(words)
    ]
    return " ".join(kept).rstrip(_TRAILING_PUNCTUATION)


def _key(claim: Claim) -> tuple[str, str]:
    return _normalized(claim.text), (claim.source or "").strip().lower()


def _tier_rank(claim: Claim) -> int:
    return TIER_ORDER.get(claim.source_tier, TIER_ORDER["UNVERIFIED"])


def claim_id(claim: Claim) -> str:
    """Content-derived ID: the same claim keeps it when the pool changes."""
    digest = hashlib.sha256("\0".join(_key(claim)).encode("utf-8")).hexdigest()
    return f"C{digest[:ID_HEX_CHARS]}"


def dedupe_claims(claims: list[Claim]) -> list[Claim]:
    """One claim per (normalized text, source), keeping the strongest tier.

    First-seen order is preserved.
    """
    strongest: dict[tuple[str, str], Claim] = {}
    for claim in claims:
        key = _key(claim)
        current = strongest.get(key)
        if current is None or _tier_rank(claim) < _tier_rank(current):
            strongest[key] = claim
    return list(strongest.values())


def _fit(text: str, cap: int) -> tuple[str, bool]:
    """Return text within the cap, and whether anything was removed."""
    return (text, False) if len(text) <= cap else (text[:cap], True)


def _claim_row(claim: Claim, source_label: str) -> dict:
    """A shortened claim is marked, because a cut can remove its condition."""
    text, is_partial = _fit(redact(claim.text), TEXT_CAP)
    row = {"id": claim_id(claim), "text": text, "src": source_label, "tier": claim.source_tier}
    return {**row, "partial": True} if is_partial else row


def _claims_payload(role: str, claims: list[Claim]) -> dict:
    """Each URL appears once, in a table the rows point to."""
    sources: dict[str, str] = {}
    rows = []
    for claim in claims:
        source = redact(claim.source) if claim.source else ""
        rows.append(_claim_row(claim, sources.setdefault(source, f"S{len(sources) + 1}") if source else ""))
    payload: dict = {"role": role, "provenance": "agent-output", "claims": rows}
    if sources:
        payload["sources"] = {label: url for url, label in sources.items()}
    return payload


def build_handoff(
    pool: list[Claim],
    role: str,
    *,
    open_questions: list[str],
    debate_summary: str,
    max_claims: int = 12,
) -> dict:
    """Payload for one agent. Claim IDs derive from content, not position."""
    unique = dedupe_claims(pool)
    ranked = sorted(
        unique,
        key=lambda c: (_tier_rank(c), -c.relevance),
    )[:max_claims]
    payload = _claims_payload(role, ranked)
    if open_questions:
        payload["open_questions"] = [redact(q) for q in open_questions[:5]]
    if debate_summary:
        payload["debate_summary"], is_partial = _fit(redact(debate_summary), SUMMARY_CAP)
        if is_partial:
            payload["debate_summary_partial"] = True
    if len(unique) > len(ranked):
        payload["omitted_claims"] = len(unique) - len(ranked)
    return payload


def encode_payload(payload: dict) -> str:
    """Compact JSON: no spaces, and each URL appears once."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def payload_bytes(payload: dict) -> int:
    return len(encode_payload(payload).encode("utf-8"))


def full_pool_bytes(pool: list[Claim]) -> int:
    """Baseline: what the current full-pool distribution would send."""
    full = [
        {"text": c.text, "source": c.source, "tier": c.source_tier}
        for c in dedupe_claims(pool)
    ]
    return payload_bytes({"claims": full})
