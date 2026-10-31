"""The run loop. Python owns state, budgets, gates and the verdict.

Claude panelists run as host subagents, so their seats are `host` attested:
Python issues the prompt and records the answer but cannot watch the call.
Limits on host agents depend on the host. The brief states which seats were
Python-called, and the family floor needs at least one of them.
"""

from __future__ import annotations

import hashlib
import re
import secrets as stdlib_secrets
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date

from .config import Config
from .decision import AnswerError, normalize_option, parse_answer
from .events import EventLog
from .evidence import route_role
from .intent import IntentResult, assess_intent
from .limits import STAKES_PROFILES, PhaseBudgets, SpawnRefused
from .prompts import build_seat_prompt
from .provenance import content_hash
from .providers import CHARS_PER_TOKEN_ESTIMATE, Result, estimate_tokens
from .runstate import RunState, RunStore, Seat
from .secrets import redact
from .tasktrack import TaskTrack
from .usage import charge_usage

HOST_FAMILY = "claude"
STATUS_QUO_OPTION = "keep things as they are"
MAX_HOST_SEATS = 1
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class RunError(RuntimeError):
    """A run step was refused. The message says what to do."""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seat(seat_id, role, provider, family, model_id, attestation, prompt, cap, route) -> Seat:
    return Seat(
        seat_id, role, provider, family, model_id, attestation, prompt, _hash(prompt),
        cap, route[0], route[1],
    )


def _external_seats(config: Config, intent: IntentResult, prompt: str, cap: int, today: date) -> list[Seat]:
    candidates = [c for c in config.candidates if c.name != config.pm_provider]
    seats = []
    for family in sorted({c.family for c in candidates}):
        decision = route_role(
            candidates, intent.role, frozenset(), config.evidence, config.role_bars, today,
            family=family, prefer_strength=intent.stakes == "high",
        )
        provider = config.providers[decision.provider]
        seats.append(_seat(
            f"S{len(seats) + 1}", intent.role, decision.provider, family, provider.model_id, "python",
            prompt, cap, (decision.status, decision.reason),
        ))
    return seats


def start_run(
    config: Config, question: str, store: RunStore, *,
    host_seats: int = 0, epic: str = "general", today: date | None = None,
    options: list[str] | None = None, ratify: bool = False,
    criteria: dict[str, float] | None = None,
) -> RunState | IntentResult:
    """Run intent, set budgets and assign seats. Ask first when the question is vague."""
    intent = assess_intent(question)
    if intent.action == "ask":
        return intent
    if any(CONTROL_CHARS.search(item) for item in [*(options or []), *(criteria or {})]):
        raise RunError("options and criteria must be single lines")
    budgets = PhaseBudgets.from_stakes(config.limits.token_budget, intent.stakes, config.phase_shares)
    choices = [*options, STATUS_QUO_OPTION] if options else []
    state = RunState(
        stdlib_secrets.token_hex(8), redact(question), intent.stakes, "OPEN", list(intent.assumptions),
        budgets.allowance, ratify=ratify, options=[redact(normalize_option(option)) for option in choices],
        criteria={redact(name): weight for name, weight in (criteria or {}).items()},
    )
    state.seats = _plan_seats(config, intent, question, budgets, choices, criteria, host_seats, today or date.today())
    _open_run(config, state, store, epic)
    return state


def _open_run(config: Config, state: RunState, store: RunStore, epic: str) -> None:
    tracker = TaskTrack(store.root / "tasks.json")
    prior = tracker.find(state.question)
    state.reused_task = prior is not None and prior.status == "done"
    tracker.claim(state.question, epic, state.run_id)
    log = log_for(store, state.run_id)
    _announce_run(state, store, log)
    store.save(state)
    _call_python_seats(config, state, log, store)
    store.save(state)


def _plan_seats(
    config: Config, intent: IntentResult, question: str, budgets: PhaseBudgets,
    choices: list[str], criteria: dict[str, float] | None, host_seats: int, today: date,
) -> list[Seat]:
    panel_size = min(STAKES_PROFILES[intent.stakes]["panel_size"], config.limits.max_agents)
    cap = min(config.limits.max_output_tokens, budgets.remaining("independent") // max(panel_size, 1) // 2)
    prompt = build_seat_prompt(
        question, intent.role, list(intent.assumptions), choices, cap * CHARS_PER_TOKEN_ESTIMATE, criteria,
    )
    seats = _external_seats(config, intent, prompt, cap, today)
    for _ in range(min(host_seats, MAX_HOST_SEATS, max(panel_size - len(seats), 0))):
        seats.append(_seat(
            f"S{len(seats) + 1}", intent.role, "host", HOST_FAMILY, "host-model", "host", prompt, cap,
            ("unproven", "host subagent; model chosen by the host"),
        ))
    return seats


def _announce_run(state: RunState, store: RunStore, log: EventLog) -> None:
    log.emit("run_started", run_id=state.run_id, stakes=state.stakes, reused_task=state.reused_task)
    store.add_record(state, "question", question_hash=content_hash(state.question), stakes=state.stakes)
    for seat in state.seats:
        log.emit("route_decided", seat=seat.seat_id, provider=seat.provider, status=seat.route_status, reason=seat.route_reason)
        log.emit("seat_issued", seat=seat.seat_id, attestation=seat.attestation, prompt_hash=seat.prompt_hash)
        store.add_record(
            state, "seat_issued", seat=seat.seat_id, family=seat.family, model=seat.model_id,
            attestation=seat.attestation, prompt_hash=seat.prompt_hash,
        )


def log_for(store: RunStore, run_id: str) -> EventLog:
    return EventLog(store.run_dir(run_id) / "events.jsonl")


def _settle(state: RunState, config: Config, seat: Seat, result: Result, log: EventLog, store: RunStore) -> None:
    charge_usage(state, config, "independent", seat.role, result)
    try:
        if not result.ok:
            raise AnswerError(result.error or "provider failed")
        if estimate_tokens(result.text) > seat.max_output_tokens:
            raise AnswerError(f"answer exceeds the {seat.max_output_tokens} token cap")
        answer = parse_answer(redact(result.text))
        if state.options and normalize_option(answer["option"]) not in state.options:
            raise AnswerError("answer is not one of the listed options")
        seat.answer = answer
        seat.status = "answered"
    except AnswerError as exc:
        seat.status, seat.error = "failed", redact(str(exc))
    log.emit("panelist_result", seat=seat.seat_id, status=seat.status, estimated=not result.usage_known)
    store.add_record(
        state, "seat_answered", seat=seat.seat_id, status=seat.status,
        attestation=seat.attestation, answer_hash=content_hash(redact(result.text)),
    )


def _collect(future: Future, seat: Seat) -> Result:
    """A provider bug fails its seat. It does not lose the other paid answers."""
    try:
        return future.result()
    except Exception as exc:  # any provider defect must become a recorded failure
        return Result("", seat.family, seat.model_id, ok=False, usage_known=False, error=type(exc).__name__)


def _call_python_seats(config: Config, state: RunState, log: EventLog, store: RunStore) -> None:
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
        try:
            _settle(state, config, seat, _collect(futures[seat.seat_id], seat), log, store)
        except Exception as exc:  # one seat's defect must not lose the other paid answers
            seat.status, seat.error = "failed", type(exc).__name__


def record_host_answer(
    state: RunState, config: Config, store: RunStore, seat_id: str, prompt_hash: str, text: str
) -> Seat:
    """Accept one answer per issued host seat. Usage is computed here, as an estimate."""
    if state.status != "OPEN":
        raise RunError(f"run is {state.status}; it no longer accepts answers")
    store.require_intact_record(state)
    seat = next((s for s in state.seats if s.seat_id == seat_id), None)
    if seat is None or seat.attestation != "host":
        raise RunError(f"seat {seat_id} is not an issued host seat")
    if seat.status != "issued":
        raise RunError(f"seat {seat_id} already recorded; answers cannot be replaced")
    if prompt_hash != seat.prompt_hash:
        raise RunError(f"prompt hash mismatch on {seat_id}; use the prompt the run issued")
    if estimate_tokens(text) > seat.max_output_tokens:
        raise RunError(f"answer for {seat_id} exceeds its {seat.max_output_tokens} token cap")
    clean = redact(text)
    result = Result(
        clean, seat.family, seat.model_id, estimate_tokens(seat.prompt),
        estimate_tokens(clean), usage_known=False,
    )
    _settle(state, config, seat, result, log_for(store, state.run_id), store)
    store.save(state)
    return seat
