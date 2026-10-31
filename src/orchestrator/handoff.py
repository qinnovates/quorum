"""Compact handoff payloads between phases and agents.

Today every Phase 2 analysis agent receives the full Research Pool. This
module builds a per-agent payload instead: deduplicated claims with stable
IDs, capped by evidence tier, plus open questions and a short debate
summary. Dedupe is deterministic code, not an LLM call.
"""

from __future__ import annotations

import hashlib
import json
import re

from quorum_scorer import Claim

from .secrets import redact

TIER_ORDER = {"STRONG": 0, "MODERATE": 1, "WEAK": 2, "UNVERIFIED": 3}
TEXT_CAP = 240
SUMMARY_CAP = 400
ID_HEX_CHARS = 10


def _key(claim: Claim) -> tuple[str, str]:
    text = re.sub(r"[\W_]+", " ", claim.text.lower()).strip()
    return text, (claim.source or "").strip().lower()


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
    sources: dict[str, str] = {}
    rows = []
    for claim in ranked:
        source = redact(claim.source) if claim.source else ""
        label = sources.setdefault(source, f"S{len(sources) + 1}") if source else ""
        rows.append({"id": claim_id(claim), "text": redact(claim.text)[:TEXT_CAP], "src": label, "tier": claim.source_tier})
    payload: dict = {"role": role, "provenance": "agent-output", "claims": rows}
    if sources:
        payload["sources"] = {label: url for url, label in sources.items()}
    if open_questions:
        payload["open_questions"] = [redact(q) for q in open_questions[:5]]
    if debate_summary:
        payload["debate_summary"] = redact(debate_summary)[:SUMMARY_CAP]
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
