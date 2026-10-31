"""End of a run: gate, challenges, judge and decision brief."""

from __future__ import annotations

from dataclasses import asdict

from quorum_scorer import Claim

from .challenge import challenge_prompt, new_disputes, run_challenges, with_disputes
from .config import Config
from .decision import (
    UNRESOLVED, Brief, ScoredClaim, assign_tier, build_brief, criteria_fit, normalize_option, render_brief,
    pivotal_claims,
)
from .diversity import DiversityError, enforce_family_floor
from .events import EventLog
from .handoff import claim_id
from .judge import escalation_signals, run_judge
from .option_merge import canonical_names
from .providers import Result, estimate_tokens
from .router import escalation_reasons
from .run import HOST_FAMILY, RunError, log_for
from .runstate import RunState, RunStore
from .secrets import redact
from .source_check import SourceCheck, check_sources
from .tasktrack import TaskTrack
from .usage import charge_usage, usage_report


def live_claims(state: RunState, config: Config) -> list[ScoredClaim]:
    """Claims so far, so the control center has content during a run."""
    return _collect_claims(state, config.verified_sources)


def _claims_for_host_challenge(state: RunState, config: Config) -> list[ScoredClaim]:
    if state.status != "OPEN" or any(s.status == "issued" for s in state.seats):
        raise RunError("record every seat before challenging, and only on an open run")
    claims = [c for c in _collect_claims(state, config.verified_sources) if c.family != HOST_FAMILY]
    if not claims:
        raise RunError("no claims from other families to challenge")
    return claims


def pivotal_or_all(claims: list[ScoredClaim]) -> list[ScoredClaim]:
    return pivotal_claims(claims) or claims


def issue_host_challenge(state: RunState, config: Config) -> str:
    """Prompt for a host subagent to challenge other families, authors hidden."""
    return challenge_prompt(pivotal_or_all(_claims_for_host_challenge(state, config)), state)


def record_host_challenge(state: RunState, config: Config, store: RunStore, text: str) -> int:
    """Record one host challenge per host seat. Returns the disputes added."""
    claims = _claims_for_host_challenge(state, config)
    host_seats = [s for s in state.seats if s.attestation == "host" and s.status == "answered"]
    if state.host_challenges_recorded >= len(host_seats):
        raise RunError("every host seat has already recorded a challenge")
    if estimate_tokens(text) > host_seats[0].max_output_tokens:
        raise RunError("challenge exceeds the seat's token cap")
    clean = redact(text)
    result = Result(
        clean, HOST_FAMILY, "host-model", estimate_tokens(challenge_prompt(claims, state)),
        estimate_tokens(clean), usage_known=False,
    )
    charge_usage(state, config, "challenge", "challenger", result)
    found = new_disputes(result, {c.claim_id for c in claims}) - set(state.host_disputes)
    state.host_disputes.extend(sorted(found))
    state.host_challenges_recorded += 1
    log_for(store, state.run_id).emit("challenge_round", round="host", new_disputes=len(found))
    store.save(state)
    return len(found)


def _enforce_gate(state: RunState, config: Config, log: EventLog) -> None:
    waiting = [s.seat_id for s in state.seats if s.status == "issued"]
    if waiting:
        raise RunError(f"waiting on seats {waiting}; record them before finishing")
    results = [
        Result("x", s.family, s.model_id, ok=s.status == "answered") for s in state.seats
    ]
    try:
        enforce_family_floor(results, config.min_families)
        has_python_seat = any(s.attestation == "python" and s.status == "answered" for s in state.seats)
        if config.min_families > 1 and not has_python_seat:
            raise RunError("FAILED_DIVERSITY: no Python-called model answered")
    except (DiversityError, RunError) as exc:
        state.status = "FAILED_DIVERSITY"
        log.emit("gate_failed", reason=str(exc))
        raise
    log.emit("gate_passed", families=sorted({s.family for s in state.seats if s.status == "answered"}))


def _source_pairs(state: RunState) -> list[tuple[str, str]]:
    return [
        (str(raw.get("source") or ""), str(raw.get("quote") or ""))
        for seat in state.seats if seat.answer
        for raw in seat.answer["claims"] if raw.get("source")
    ]


def _collect_claims(
    state: RunState, verified: frozenset[str], checked: SourceCheck = SourceCheck(),
    names: dict[str, str] | None = None,
) -> list[ScoredClaim]:
    claims = []
    for seat in state.seats:
        if seat.status != "answered" or seat.answer is None:
            continue
        option = normalize_option(seat.answer["option"])
        option = (names or {}).get(option, option)
        for raw in seat.answer["claims"]:
            source = str(raw.get("source") or "")
            is_quote_found = (source, str(raw.get("quote") or "")) in checked.verified
            text = redact(raw["text"])
            cid = claim_id(Claim(text=text, source=source))
            claims.append(ScoredClaim(cid, text, redact(source), assign_tier(source, verified | {source} if is_quote_found else verified, checked.reachable), option, seat.family))
    return claims


def _apply_judge(state: RunState, config: Config, claims: list[ScoredClaim], brief: Brief) -> None:
    """Judge on high stakes or a trigger. A judge can only withhold a verdict."""
    reasons = escalation_reasons(escalation_signals(state, claims, brief, config))
    if brief.verdict == UNRESOLVED or (state.stakes != "high" and not reasons):
        return
    outcome = run_judge(config, state, claims, brief, reasons)
    state.judge = outcome.summary
    if outcome.note:
        brief.unknowns.append(outcome.note)
    if outcome.should_withhold:
        brief.verdict = UNRESOLVED


def finish_run(state: RunState, config: Config, store: RunStore) -> str:
    """Enforce the gate, challenge the evidence, and render the decision brief."""
    if state.status != "OPEN":
        raise RunError(f"run already finished with status {state.status}")
    log = log_for(store, state.run_id)
    if store.is_cancel_requested(state.run_id):
        state.status = "CANCELLED"
        store.save(state)
        raise RunError("run was stopped; no verdict was given")
    try:
        _enforce_gate(state, config, log)
    finally:
        store.save(state)
    checked = (
        check_sources(_source_pairs(state), config.allowed_source_hosts)
        if config.should_fetch_sources else SourceCheck()
    )
    names = canonical_names(config, state)
    before = _collect_claims(state, config.verified_sources, checked, names)
    first_verdict = build_brief(before, [], []).verdict
    is_cancelled = lambda: store.is_cancel_requested(state.run_id)
    claims = run_challenges(config, state, before, log, is_cancelled)
    changes = [
        redact(str(s.answer["would_change"])) for s in state.seats
        if s.answer and s.answer.get("would_change")
    ]
    host_seats = sum(s.attestation == "host" for s in state.seats)
    unknowns = [*state.assumptions]
    if host_seats:
        unknowns.append(f"{host_seats} seat(s) were reported by the host and not observed by Quorum.")
    unknowns += [f"{s.seat_id}: {s.route_reason}" for s in state.seats if s.route_status != "proven"][:3]
    claims = with_disputes(claims, set(state.host_disputes))
    state.claims = [asdict(c) for c in claims]
    if state.reused_task:
        unknowns.append("This exact topic was researched in an earlier run; check that result first.")
    if host_seats and not state.host_challenges_recorded:
        unknowns.append("Host panelists did not take part in the challenge round.")
    unknowns += [f"Treated {old!r} and {new!r} as one option." for old, new in names.items()]
    if not (config.should_fetch_sources and config.allowed_source_hosts):
        unknowns.append("Cited sources were not checked, so citations may be invented.")
    brief = build_brief(claims, changes, unknowns)
    fit = criteria_fit([s.answer for s in state.seats if s.answer], state.criteria)
    brief.criteria_rows = [f"{option}: {score}" for option, score in sorted(fit.items(), key=lambda i: -i[1])]
    if fit and brief.verdict != UNRESOLVED and max(fit, key=fit.get) != brief.verdict:
        brief.unknowns.append("The evidence favours one option, but your criteria favour another.")
    if brief.verdict != first_verdict:
        brief.verdict = UNRESOLVED
        brief.unknowns.append("Unverified objections changed the outcome, so no verdict is given.")
    if is_cancelled():
        state.status = "CANCELLED"
        log.emit("run_finished", status=state.status)
        store.save(state)
        raise RunError("run was stopped; no verdict was given")
    _apply_judge(state, config, claims, brief)
    state.brief = render_brief(brief, usage_report(state))
    state.status = UNRESOLVED if brief.verdict == UNRESOLVED else "DONE"
    TaskTrack(store.root / "tasks.json").complete(state.question, [brief.verdict])
    log.emit("brief_ready", verdict=brief.verdict, judge=state.judge)
    log.emit("run_finished", status=state.status)
    store.save(state)
    return state.brief
