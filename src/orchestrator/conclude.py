"""End of a run: gate, challenges, judge and decision brief."""

from __future__ import annotations

from dataclasses import asdict

from .challenge import (
    challenge_payload, challenge_prompt, new_disputes, run_challenges, with_disputes,
)
from .claim_gather import collect_claims, gather_claims, listed_sources
from .config import Config
from .decision import (
    CHECKED_TIERS, UNRESOLVED, Brief, ScoredClaim, build_brief, criteria_fit, pivotal_claims, render_brief,
)
from .diversity import DiversityError, enforce_family_floor
from .entailment import check_pivotal_claims
from .events import EventLog
from .judge import escalation_signals, run_judge
from .provenance import content_hash
from .providers import Result, estimate_tokens
from .router import escalation_reasons
from .run import HOST_FAMILY, RunError, log_for
from .runstate import RunState, RunStore
from .secrets import redact
from .tasktrack import TaskTrack
from .usage import charge_usage, record_handoff, usage_report


def _claims_for_host_challenge(state: RunState, config: Config) -> list[ScoredClaim]:
    if state.status != "OPEN" or any(s.status == "issued" for s in state.seats):
        raise RunError("record every seat before challenging, and only on an open run")
    claims = [c for c in collect_claims(state, listed_sources(config)) if c.family != HOST_FAMILY]
    if not claims:
        raise RunError("no claims from other families to challenge")
    return claims


def _host_challenge_claims(state: RunState, config: Config) -> list[ScoredClaim]:
    """Sources are checked at finish, so with checking on tiers can still change: send all."""
    claims = _claims_for_host_challenge(state, config)
    return claims if config.should_fetch_sources else pivotal_claims(claims) or claims


def issue_host_challenge(state: RunState, config: Config) -> str:
    """Prompt for a host subagent to challenge other families, authors hidden."""
    return challenge_prompt(_host_challenge_claims(state, config), state)


def record_host_challenge(state: RunState, config: Config, store: RunStore, text: str) -> int:
    """Record one host challenge per host seat. Returns the disputes added."""
    store.require_intact_record(state)
    claims = _host_challenge_claims(state, config)
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
    record_handoff(state, store, challenge_payload(claims))
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


def _apply_judge(state: RunState, config: Config, store: RunStore, claims: list[ScoredClaim], brief: Brief) -> None:
    """Judge on high stakes or a trigger. A judge can only withhold a verdict."""
    reasons = escalation_reasons(escalation_signals(state, claims, brief, config))
    if brief.verdict == UNRESOLVED or (state.stakes != "high" and not reasons):
        return
    outcome = run_judge(config, state, store, claims, brief, reasons)
    state.judge = outcome.summary
    if outcome.note:
        brief.unknowns.append(outcome.note)
    if outcome.should_withhold:
        brief.verdict = UNRESOLVED


def _stop_if_cancelled(state: RunState, store: RunStore, log: EventLog) -> None:
    if store.is_cancel_requested(state.run_id):
        state.status = "CANCELLED"
        log.emit("run_finished", status=state.status)
        store.save(state)
        raise RunError("run was stopped; no verdict was given")


def _run_notes(state: RunState, config: Config, names: dict[str, str]) -> list[str]:
    host_seats = sum(s.attestation == "host" for s in state.seats)
    notes = [*state.assumptions]
    if host_seats:
        notes.append(f"{host_seats} seat(s) were reported by the host and not observed by Quorum.")
    notes += [f"{s.seat_id}: {s.route_reason}" for s in state.seats if s.route_status != "proven"][:3]
    if state.reused_task:
        notes.append("This exact topic was researched in an earlier run; check that result first.")
    if host_seats and not state.host_challenges_recorded:
        notes.append("Host panelists did not take part in the challenge round.")
    notes += [f"Treated {old!r} and {new!r} as one option." for old, new in names.items()]
    if not (config.should_fetch_sources and config.allowed_source_hosts):
        notes.append("Cited sources were not checked, so citations may be invented.")
    return notes


def _add_criteria(brief: Brief, state: RunState) -> None:
    fit = criteria_fit([s.answer for s in state.seats if s.answer], state.criteria)
    brief.criteria_rows = [f"{option}: {score}" for option, score in sorted(fit.items(), key=lambda i: -i[1])]
    if fit and brief.verdict != UNRESOLVED and max(fit, key=fit.get) != brief.verdict:
        brief.unknowns.append("The evidence favours one option, but your criteria favour another.")


def _record_disputes(state: RunState, store: RunStore, claims: list[ScoredClaim]) -> None:
    for claim in claims:
        if claim.is_disputed:
            store.add_record(state, "claim_disputed", claim_id=claim.claim_id)


def _require_checked_source(brief: Brief, claims: list[ScoredClaim], config: Config) -> None:
    """With checking on, a verdict needs a source that was actually reached."""
    if not config.should_fetch_sources or brief.verdict == UNRESOLVED:
        return
    if not any(c.option == brief.verdict and c.tier in CHECKED_TIERS for c in claims):
        brief.verdict = UNRESOLVED
        brief.unknowns.append("No cited source for this option could be checked, so no verdict is given.")


def _add_limit_notes(notes: list[str], state: RunState, over_limit: int) -> None:
    if over_limit:
        notes.append(f"{over_limit} cited source(s) were over the check limit and were not checked.")
    dropped = sum(n for s in state.seats if s.answer and isinstance(n := s.answer.get("claims_dropped"), int))
    if dropped:
        notes.append(f"{dropped} claim(s) over the per-model limit were not weighed.")


def _weigh(state: RunState, config: Config, store: RunStore, log: EventLog) -> Brief:
    """Check and challenge the evidence. Any change to the outcome withholds the verdict."""
    is_cancelled = lambda: store.is_cancel_requested(state.run_id)
    gathered, names, over_limit = gather_claims(state, config, store)
    first_verdict = build_brief(gathered, [], []).verdict
    checked = check_pivotal_claims(config, state, store, gathered, log, is_cancelled)
    claims = with_disputes(run_challenges(config, state, store, checked, log, is_cancelled), set(state.host_disputes))
    state.claims = [asdict(c) for c in claims]
    _record_disputes(state, store, claims)
    changes = [redact(str(s.answer["would_change"])) for s in state.seats if s.answer and s.answer.get("would_change")]
    notes = _run_notes(state, config, names)
    _add_limit_notes(notes, state, over_limit)
    brief = build_brief(claims, changes, notes)
    _add_criteria(brief, state)
    if brief.verdict != first_verdict:
        brief.verdict = UNRESOLVED
        brief.unknowns.append("Checks or objections changed the outcome, so no verdict is given.")
    _require_checked_source(brief, claims, config)
    if state.is_challenge_incomplete and brief.verdict != UNRESOLVED:
        brief.verdict = UNRESOLVED
        brief.unknowns.append("The budget ran out before the challenge round finished, so no verdict is given.")
    _stop_if_cancelled(state, store, log)
    _apply_judge(state, config, store, claims, brief)
    _stop_if_cancelled(state, store, log)
    return brief


def _record_verdict(state: RunState, store: RunStore, brief: Brief) -> None:
    """The verdict links to its option's claims, or to every claim when unresolved."""
    supporting = [c for c in state.claims if brief.verdict in (c["option"], UNRESOLVED)]
    store.add_node(
        state, "verdict", content_hash(brief.verdict), [state.claim_nodes[c["claim_id"]] for c in supporting],
        verdict_hash=content_hash(brief.verdict), status=state.status, judge=state.judge,
    )


def _close_run(state: RunState, store: RunStore, log: EventLog, brief: Brief) -> str:
    state.status = UNRESOLVED if brief.verdict == UNRESOLVED else "DONE"
    _record_verdict(state, store, brief)
    report = {**usage_report(state), "run record": f"{state.record_head[:16]} (check with: quorum-run verify --run {state.run_id})"}
    state.brief = render_brief(brief, report)
    log.emit("brief_ready", verdict=brief.verdict, judge=state.judge)
    log.emit("run_finished", status=state.status)
    store.save(state)
    return state.brief


def _track_result(state: RunState, store: RunStore, log: EventLog, verdict: str) -> None:
    """The tracker is a convenience, so its failure cannot undo a finished run."""
    try:
        TaskTrack(store.root / "tasks.json").complete(state.question, [verdict])
    except (ValueError, OSError, TypeError, LookupError) as exc:
        log.emit("note_added", text=f"task tracker not updated ({type(exc).__name__})")


def _fail_run(state: RunState, store: RunStore, log: EventLog) -> None:
    state.status = "FAILED"
    log.emit("run_finished", status=state.status)
    store.save(state)


def finish_run(state: RunState, config: Config, store: RunStore) -> str:
    """Enforce the gate, weigh the evidence, and render the decision brief."""
    if state.status != "OPEN":
        raise RunError(f"run already finished with status {state.status}")
    store.require_intact_record(state)
    log = log_for(store, state.run_id)
    _stop_if_cancelled(state, store, log)
    try:
        _enforce_gate(state, config, log)
    finally:
        store.save(state)
    try:
        brief = _weigh(state, config, store, log)
        report = _close_run(state, store, log, brief)
    except RunError:
        raise
    except Exception as exc:  # the signed head must always match the record, so a defect closes the run
        _fail_run(state, store, log)
        raise RunError(f"run failed while weighing evidence ({type(exc).__name__}); start a new run") from exc
    except BaseException:  # an interrupt must not leave the record ahead of signed state
        _fail_run(state, store, log)
        raise
    _track_result(state, store, log, brief.verdict)
    return report
