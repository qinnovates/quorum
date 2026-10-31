"""Turn panel answers into scored claims, with their sources on the run record."""

from __future__ import annotations

from dataclasses import replace
from itertools import zip_longest

from quorum_scorer import Claim

from .claim_check import fold_text, support_issues
from .config import Config
from .decision import ScoredClaim, assign_tier, normalize_option
from .handoff import claim_id
from .option_merge import canonical_names
from .provenance import content_hash, source_root
from .runstate import RunState, RunStore
from .secrets import redact
from .source_check import SourceCheck, Snapshot, check_sources

COPIED_QUOTE_OVERLAP = 0.8


def source_pairs(state: RunState) -> list[tuple[str, str]]:
    """Each seat's first claim, then each seat's second, so no seat crowds out another."""
    by_seat = [
        [(str(raw.get("source") or ""), str(raw.get("quote") or "")) for raw in seat.answer["claims"] if raw.get("source")]
        for seat in state.seats if seat.answer
    ]
    return [pair for row in zip_longest(*by_seat) for pair in row if pair]


def _build_claim(raw: dict, family: str, option: str, verified: frozenset[str], checked: SourceCheck) -> ScoredClaim:
    """Python assigns the ID, tier and root. A panelist's own labels are ignored."""
    text, source = redact(raw["text"]), redact(str(raw.get("source") or ""))
    quote = str(raw.get("quote") or "")
    snapshot = checked.snapshots.get((str(raw.get("source") or ""), quote))
    issues = support_issues(text, quote, snapshot.contexts) if snapshot else ()
    trusted = verified - {source} if issues else verified | {source} if snapshot else verified
    return ScoredClaim(
        claim_id(Claim(text=text, source=source)), text, source, assign_tier(source, trusted, checked.reachable),
        option, family, root=source_root(source), quote=redact(quote) if snapshot else "", issues=issues,
    )


def _quote_terms(claim: ScoredClaim) -> set[str]:
    return set(fold_text(claim.quote).lower().split())


def _is_copied(first: ScoredClaim, second: ScoredClaim) -> bool:
    terms_a, terms_b = _quote_terms(first), _quote_terms(second)
    return len(terms_a & terms_b) / max(len(terms_a | terms_b), 1) >= COPIED_QUOTE_OVERLAP


def _copy_groups(claims: list[ScoredClaim]) -> list[list[int]]:
    """Group passing quotes for one option, each pair similar to every other pair.

    Requiring every pair stops a bridging quote from joining two unrelated
    sources, and the fixed order keeps the result the same for any input order.
    """
    order = sorted(
        (i for i, claim in enumerate(claims) if claim.quote and not claim.issues),
        key=lambda i: (claims[i].option, claims[i].root, claims[i].quote),
    )
    groups: list[list[int]] = []
    for index in order:
        home = next(
            (g for g in groups if claims[g[0]].option == claims[index].option
             and all(_is_copied(claims[member], claims[index]) for member in g)),
            None,
        )
        if home is None:
            groups.append([index])
        else:
            home.append(index)
    return groups


def _merge_copied_roots(claims: list[ScoredClaim]) -> list[ScoredClaim]:
    """Near-identical passing quotes behind one option are one source, whichever URL.

    Every claim on a merged page moves too, so a second claim cannot revive a
    mirror. A different located quote can still keep two pages apart.
    """
    merged = list(claims)
    for group in _copy_groups(claims):
        option, roots = claims[group[0]].option, {claims[index].root for index in group}
        merged = [replace(c, root=min(roots)) if c.option == option and c.root in roots else c for c in merged]
    return merged


def collect_claims(
    state: RunState, verified: frozenset[str], checked: SourceCheck = SourceCheck(),
    names: dict[str, str] | None = None,
) -> list[ScoredClaim]:
    claims = []
    for seat in state.seats:
        if seat.status != "answered" or seat.answer is None:
            continue
        option = normalize_option(seat.answer["option"])
        option = (names or {}).get(option, option)
        claims += [_build_claim(raw, seat.family, option, verified, checked) for raw in seat.answer["claims"]]
    return _merge_copied_roots(claims)


def listed_sources(config: Config) -> frozenset[str]:
    """With checking on, a listed source earns nothing until its quote is located."""
    return frozenset() if config.should_fetch_sources else config.verified_sources


def live_claims(state: RunState, config: Config) -> list[ScoredClaim]:
    """Claims so far, so the control center has content during a run."""
    return collect_claims(state, listed_sources(config))


def _record_snapshot(state: RunState, store: RunStore, claim: ScoredClaim, snapshot: Snapshot) -> str:
    return store.add_node(
        state, "source_snapshot", content_hash(f"{claim.source}\0{snapshot.page_hash}\0{claim.quote}"),
        page_hash=snapshot.page_hash, retrieved_at=snapshot.retrieved_at,
        quote_hash=content_hash(claim.quote), quote_offset=snapshot.quote_offset,
    )


def _record_claim(state: RunState, store: RunStore, claim: ScoredClaim, checked: SourceCheck) -> None:
    pair = next((p for p in checked.snapshots if redact(p[0]) == claim.source and redact(p[1]) == claim.quote), None)
    parents = [_record_snapshot(state, store, claim, checked.snapshots[pair])] if pair else []
    node = store.add_node(
        state, "claim", content_hash(f"{claim.text}\0{claim.source}"), parents,
        claim_id=claim.claim_id, option_hash=content_hash(claim.option), tier=claim.tier, family=claim.family,
        source_hash=content_hash(claim.source), root_hash=content_hash(claim.root), issues=list(claim.issues),
    )
    state.claim_nodes.setdefault(claim.claim_id, node)


def gather_claims(state: RunState, config: Config, store: RunStore) -> tuple[list[ScoredClaim], dict[str, str], int]:
    """With checking on, STRONG needs a located, fitting quote, even on a listed source."""
    checked = (
        check_sources(source_pairs(state), config.allowed_source_hosts)
        if config.should_fetch_sources else SourceCheck()
    )
    names = canonical_names(config, state)
    claims = collect_claims(state, listed_sources(config), checked, names)
    for claim in claims:
        _record_claim(state, store, claim, checked)
    for old, new in names.items():
        store.add_record(state, "options_merged", from_hash=content_hash(old), to_hash=content_hash(new))
    return claims, names, checked.over_limit
