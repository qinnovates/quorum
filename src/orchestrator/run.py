"""The run loop. Python owns state, budgets, gates and the verdict.

Claude panelists run as host subagents, so their seats are `host` attested:
Python issues the prompt and records the answer but cannot watch the call.
Limits on host agents depend on the host. The brief states which seats were
Python-called, and the family floor needs at least one of them.
"""

from __future__ import annotations

import hashlib
import secrets as stdlib_secrets
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import date

from quorum_scorer import Claim

from .challenge import challenge_prompt, new_disputes, run_challenges, with_disputes
from .config import Config
from .decision import (
    AnswerError, ScoredClaim, assign_tier, build_brief, normalize_option,
    parse_answer, render_brief, UNRESOLVED,
)
from .diversity import DiversityError, enforce_family_floor
from .events import EventLog
from .evidence import route_role
from .handoff import claim_id
from .intent import IntentResult, assess_intent
from .limits import STAKES_PROFILES, PhaseBudgets, SpawnRefused
from .prompts import build_seat_prompt
from .providers import Result, estimate_tokens
from .runstate import RunState, RunStore, Seat
from .secrets import redact
from .tasktrack import TaskTrack
from .usage import charge_usage, usage_report

HOST_FAMILY = "claude"


class RunError(RuntimeError):
    """A run step was refused. The message says what to do."""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seat(seat_id, provider, family, model_id, attestation, prompt, cap, route) -> Seat:
    return Seat(
        seat_id, "research", provider, family, model_id, attestation, prompt, _hash(prompt),
        cap, route[0], route[1],
    )


def _external_seats(config: Config, prompt: str, cap: int, today: date) -> list[Seat]:
    candidates = [c for c in config.candidates if c.name != config.pm_provider]
    seats = []
    for family in sorted({c.family for c in candidates}):
        decision = route_role(
            candidates, "research", frozenset(), config.evidence, config.role_bars, today,
            family=family,
        )
        provider = config.providers[decision.provider]
        seats.append(_seat(
            f"S{len(seats) + 1}", decision.provider, family, provider.model_id, "python",
            prompt, cap, (decision.status, decision.reason),
        ))
    return seats


def start_run(
    config: Config, question: str, store: RunStore, *,
    host_seats: int = 0, epic: str = "general", today: date | None = None,
    options: list[str] | None = None,
) -> RunState | IntentResult:
    """Run intent, set budgets and assign seats. Ask first when the question is vague."""
    intent = assess_intent(question)
    if intent.action == "ask":
        return intent
    budgets = PhaseBudgets.from_stakes(config.limits.token_budget, intent.stakes, config.phase_shares)
    panel_size = min(STAKES_PROFILES[intent.stakes]["panel_size"], config.limits.max_agents)
    prompt = build_seat_prompt(question, "research", list(intent.assumptions), options or [])
    cap = min(config.limits.max_output_tokens, budgets.remaining("independent") // max(panel_size, 1) // 2)
    seats = _external_seats(config, prompt, cap, today or date.today())
    open_host_seats = min(host_seats, max(panel_size - len(seats), 0))
    for _ in range(open_host_seats):
        seats.append(_seat(
            f"S{len(seats) + 1}", "host", HOST_FAMILY, "host-model", "host", prompt, cap,
            ("unproven", "host subagent; model chosen by the host"),
        ))
    run_id = stdlib_secrets.token_hex(8)
    state = RunState(run_id, redact(question), intent.stakes, "OPEN", list(intent.assumptions), budgets.allowance)
    state.seats = seats
    state.options = [normalize_option(option) for option in options or []]
    tracker = TaskTrack(store.root / "tasks.json")
    state.reused_task = tracker.claim(state.question, epic, run_id)[1]
    log = _log(store, run_id)
    log.emit("run_started", run_id=run_id, stakes=intent.stakes, reused_task=state.reused_task)
    for seat in seats:
        log.emit("route_decided", seat=seat.seat_id, provider=seat.provider, status=seat.route_status, reason=seat.route_reason)
        log.emit("seat_issued", seat=seat.seat_id, attestation=seat.attestation, prompt_hash=seat.prompt_hash)
    _call_python_seats(config, state, log)
    store.save(state)
    return state


def _log(store: RunStore, run_id: str) -> EventLog:
    return EventLog(store.run_dir(run_id) / "events.jsonl")


def _settle(state: RunState, config: Config, seat: Seat, result: Result, log: EventLog) -> None:
    charge_usage(state, config, "independent", seat.role, result)
    try:
        if not result.ok:
            raise AnswerError(result.error or "provider failed")
        seat.answer = parse_answer(redact(result.text))
        if state.options and normalize_option(seat.answer["option"]) not in state.options:
            raise AnswerError("answer is not one of the listed options")
        seat.status = "answered"
    except AnswerError as exc:
        seat.status, seat.error = "failed", redact(str(exc))
    log.emit("panelist_result", seat=seat.seat_id, status=seat.status, estimated=not result.usage_known)


def _collect(future: Future, seat: Seat) -> Result:
    """A provider bug fails its seat. It does not lose the other paid answers."""
    try:
        return future.result()
    except Exception as exc:  # any provider defect must become a recorded failure
        return Result("", seat.family, seat.model_id, ok=False, usage_known=False, error=type(exc).__name__)


def _call_python_seats(config: Config, state: RunState, log: EventLog) -> None:
    seats = [s for s in state.seats if s.attestation == "python"]
    budgets = PhaseBudgets(state.allowance, state.spent)
    runnable = []
    reserved = 0
    for seat in seats:
        estimate = estimate_tokens(seat.prompt) + seat.max_output_tokens
        try:
            budgets.authorize("independent", reserved + estimate)
            reserved += estimate
            runnable.append(seat)
        except SpawnRefused as exc:
            seat.status, seat.error = "failed", exc.reason
            log.emit("budget_refused", seat=seat.seat_id, reason=exc.reason)
    if not runnable:
        return
    with ThreadPoolExecutor(max_workers=len(runnable), thread_name_prefix="quorum-seat") as pool:
        futures = {
            s.seat_id: pool.submit(
                config.providers[s.provider].complete, s.prompt, max_output_tokens=s.max_output_tokens
            )
            for s in runnable
        }
    for seat in runnable:
        _settle(state, config, seat, _collect(futures[seat.seat_id], seat), log)


def record_host_answer(
    state: RunState, config: Config, store: RunStore, seat_id: str, prompt_hash: str, text: str
) -> Seat:
    """Accept one answer per issued host seat. Usage is computed here, as an estimate."""
    seat = next((s for s in state.seats if s.seat_id == seat_id), None)
    if seat is None or seat.attestation != "host":
        raise RunError(f"seat {seat_id} is not an issued host seat")
    if seat.status != "issued":
        raise RunError(f"seat {seat_id} already recorded; answers cannot be replaced")
    if prompt_hash != seat.prompt_hash:
        raise RunError(f"prompt hash mismatch on {seat_id}; use the prompt the run issued")
    clean = redact(text)
    if estimate_tokens(clean) > seat.max_output_tokens:
        raise RunError(f"answer for {seat_id} exceeds its {seat.max_output_tokens} token cap")
    result = Result(
        clean, seat.family, seat.model_id, estimate_tokens(seat.prompt),
        estimate_tokens(clean), usage_known=False,
    )
    _settle(state, config, seat, result, _log(store, state.run_id))
    store.save(state)
    return seat


def _claims_for_host_challenge(state: RunState, config: Config) -> list[ScoredClaim]:
    if state.status != "OPEN" or any(s.status == "issued" for s in state.seats):
        raise RunError("record every seat before challenging, and only on an open run")
    claims = [c for c in _collect_claims(state, config.verified_sources) if c.family != HOST_FAMILY]
    if not claims:
        raise RunError("no claims from other families to challenge")
    return claims


def issue_host_challenge(state: RunState, config: Config) -> str:
    """Prompt for a host subagent to challenge other families, authors hidden."""
    return challenge_prompt(_claims_for_host_challenge(state, config), state, "")


def record_host_challenge(state: RunState, config: Config, store: RunStore, text: str) -> int:
    """Record one host challenge per host seat. Returns the disputes added."""
    claims = _claims_for_host_challenge(state, config)
    host_seats = [s for s in state.seats if s.attestation == "host" and s.status == "answered"]
    if state.host_challenges_recorded >= len(host_seats):
        raise RunError("every host seat has already recorded a challenge")
    clean = redact(text)
    if estimate_tokens(clean) > host_seats[0].max_output_tokens:
        raise RunError("challenge exceeds the seat's token cap")
    result = Result(clean, HOST_FAMILY, "host-model", tokens_out=estimate_tokens(clean), usage_known=False)
    charge_usage(state, config, "challenge", "challenger", result)
    found = new_disputes(result, {c.claim_id for c in claims}) - set(state.host_disputes)
    state.host_disputes.extend(sorted(found))
    state.host_challenges_recorded += 1
    _log(store, state.run_id).emit("challenge_round", round="host", new_disputes=len(found))
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


def _collect_claims(state: RunState, verified: frozenset[str]) -> list[ScoredClaim]:
    claims = []
    for seat in state.seats:
        if seat.status != "answered" or seat.answer is None:
            continue
        option = normalize_option(seat.answer["option"])
        for raw in seat.answer["claims"]:
            source = str(raw.get("source") or "")
            text = redact(raw["text"])
            cid = claim_id(Claim(text=text, source=source))
            claims.append(ScoredClaim(cid, text, redact(source), assign_tier(source, verified), option, seat.family))
    return claims


def finish_run(state: RunState, config: Config, store: RunStore) -> str:
    """Enforce the gate, challenge the evidence, and render the decision brief."""
    if state.status != "OPEN":
        raise RunError(f"run already finished with status {state.status}")
    log = _log(store, state.run_id)
    try:
        _enforce_gate(state, config, log)
    finally:
        store.save(state)
    before = _collect_claims(state, config.verified_sources)
    first_verdict = build_brief(before, [], []).verdict
    claims = run_challenges(config, state, before, log)
    state.claims = [asdict(c) for c in claims]
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
    if state.reused_task:
        unknowns.append("This exact topic was researched in an earlier run; check that result first.")
    if host_seats and not state.host_challenges_recorded:
        unknowns.append("Host panelists did not take part in the challenge round.")
    brief = build_brief(claims, changes, unknowns)
    if brief.verdict != first_verdict:
        brief.verdict = UNRESOLVED
        brief.unknowns.append("Unverified objections changed the outcome, so no verdict is given.")
    state.brief = render_brief(brief, usage_report(state))
    state.status = UNRESOLVED if brief.verdict == UNRESOLVED else "DONE"
    TaskTrack(store.root / "tasks.json").complete(state.question, [brief.verdict])
    log.emit("brief_ready", verdict=brief.verdict)
    log.emit("run_finished", status=state.status)
    store.save(state)
    return state.brief
