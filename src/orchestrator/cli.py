"""`python -m orchestrator.cli`: the skill's interface to the run loop.

Answers are passed by file path, so the host model does not retype them.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Config, ConfigError, load, tighten
from .diversity import DiversityError
from .doctor import remote_providers, run_doctor
from .intent import IntentResult
from .conclude import finish_run, issue_host_challenge, live_claims, record_host_challenge
from .dashboard import REFRESH_SECONDS, write_dashboard
from .evaluation import control_passes, load_cases, run_arm
from .provenance import verify_records
from .run import RunError, log_for, record_host_answer, start_run
from .secrets import redact
from .setup_config import detect_tools, write_user_config
from .runstate import RunStore, default_state_dir

WATCH_LIMIT_SECONDS = 3600
HANDOFF_PARENT = "_swarm"
HANDOFF_DIR = "_swarm/tmp"
MAX_HANDOFF_BYTES = 1_000_000
USER_CONFIG = Path.home() / ".config" / "quorum" / "quorum.toml"
PROJECT_CONFIG = Path("quorum.toml")


def _load_config() -> Config:
    """User config is required. A project file can only tighten it."""
    if not USER_CONFIG.exists():
        raise ConfigError(f"no config found; create {USER_CONFIG} from docs/quorum.example.toml")
    config = load(USER_CONFIG, trusted=True)
    return tighten(config, load(PROJECT_CONFIG)) if PROJECT_CONFIG.exists() else config


@dataclass(frozen=True)
class Handoff:
    path: str
    inode: int
    text: str


def _read_handoff(path_text: str) -> Handoff:
    """Read a regular, unlinked file directly inside the project's _swarm/tmp."""
    root = Path.cwd()
    path = os.path.abspath(path_text)
    if os.path.dirname(path) != str(root / HANDOFF_DIR):
        raise RunError(f"handoff files must be directly inside {HANDOFF_DIR}")
    if any(os.path.islink(root / part) for part in (HANDOFF_PARENT, HANDOFF_DIR)):
        raise RunError(f"{HANDOFF_DIR} must not be a symbolic link")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        status = os.fstat(stream.fileno())
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
            raise RunError("handoff files must be regular files with one link")
        if status.st_size > MAX_HANDOFF_BYTES:
            raise RunError(f"handoff file is over {MAX_HANDOFF_BYTES} bytes")
        return Handoff(path, status.st_ino, stream.read().decode("utf-8"))


def _discard_handoff(handoff: Handoff) -> None:
    """Delete only the file that was read, never a swapped-in replacement."""
    status = os.lstat(handoff.path)
    if stat.S_ISREG(status.st_mode) and status.st_ino == handoff.inode:
        os.unlink(handoff.path)


def _require_consent(config: Config, allowed: list[str]) -> None:
    """Content leaves this machine only for providers the user named."""
    missing = sorted(set(remote_providers(config)) - set(allowed))
    if missing:
        flags = " ".join(f"--allow-provider {name}" for name in missing)
        raise RunError(f"this sends your question to {', '.join(missing)}. Ask the user, then add: {flags}")


def _criteria(rows: list[str]) -> dict[str, float]:
    """Parse `name:weight` pairs, such as `cost:3`."""
    parsed = {}
    for row in rows:
        name, _, weight = row.rpartition(":")
        if not name or not weight.replace(".", "", 1).isdigit() or float(weight) <= 0:
            raise RunError(f"criterion {row!r} must look like cost:3")
        parsed[name.strip()] = float(weight)
    return parsed


def _floor_is_reachable(state, config: Config) -> bool:
    families = {s.family for s in state.seats if s.status != "failed"}
    return len(families) >= config.min_families


def _start(args, config, store) -> dict:
    _require_consent(config, args.allow_provider)
    handoff = _read_handoff(args.question_file)
    args.question = handoff.text
    state = start_run(
        config, args.question, store, host_seats=args.host_seats, epic=args.epic,
        options=args.option, ratify=args.ratify, criteria=_criteria(args.criterion),
    )
    _discard_handoff(handoff)
    if isinstance(state, IntentResult):
        return asdict(state)
    failed = [{"seat": s.seat_id, "provider": s.provider, "error": s.error} for s in state.seats if s.status == "failed"]
    if not _floor_is_reachable(state, config):
        return {"run_id": state.run_id, "status": "FAILED_DIVERSITY", "failed_seats": failed}
    open_seats = [
        {"seat": s.seat_id, "prompt": s.prompt, "prompt_hash": s.prompt_hash, "max_output_tokens": s.max_output_tokens}
        for s in state.seats if s.status == "issued"
    ]
    return {"run_id": state.run_id, "stakes": state.stakes, "host_seats": open_seats, "failed_seats": failed}


def _record(args, config, store) -> dict:
    handoff = _read_handoff(args.file)
    with store.locked(args.run):
        state = store.load(args.run)
        seat = record_host_answer(state, config, store, args.seat, args.prompt_hash, handoff.text)
    _discard_handoff(handoff)
    return {"seat": seat.seat_id, "status": seat.status}


def _finish(args, config, store) -> dict:
    with store.locked(args.run):
        state = store.load(args.run)
        return {"brief": finish_run(state, config, store), "status": store.load(args.run).status}


def _challenge(args, config, store) -> dict:
    return {"prompt": issue_host_challenge(store.load(args.run), config)}


def _record_challenge(args, config, store) -> dict:
    handoff = _read_handoff(args.file)
    with store.locked(args.run):
        found = record_host_challenge(store.load(args.run), config, store, handoff.text)
    _discard_handoff(handoff)
    return {"new_disputes": found}


def _note(args, config, store) -> dict:
    with store.locked(args.run):
        state = store.load(args.run)
        note = redact(args.text)
        state.notes.append(note)
        log_for(store, args.run).emit("note_added", text=note)
        store.save(state)
    return {"notes": len(state.notes)}


def _stop(args, config, store) -> dict:
    """The one run-changing instruction. It needs an explicit --yes."""
    if not args.yes:
        raise RunError("stopping a run needs --yes")
    status = store.load(args.run).status
    if status != "OPEN":
        raise RunError(f"run already finished with status {status}")
    store.request_cancel(args.run)
    log_for(store, args.run).emit("instruction_confirmed", change="stop", confirmed_by_user=True)
    return {"status": "STOP_REQUESTED", "note": "The run stops before its next model call."}


def _dashboard(args, config, store) -> dict:
    run_dir = store.run_dir(args.run)

    def refresh() -> Path:
        state = store.load(args.run)
        is_blind = any(seat.status == "issued" for seat in state.seats)
        return write_dashboard(state, run_dir, None if is_blind else live_claims(state, config))

    path = refresh()
    print(f"dashboard: {path}", file=sys.stderr, flush=True)
    deadline = time.monotonic() + WATCH_LIMIT_SECONDS
    while args.watch and store.load(args.run).status == "OPEN" and time.monotonic() < deadline:
        time.sleep(REFRESH_SECONDS)
        refresh()
    return {"dashboard": str(path)}


def _doctor(args, config, store) -> dict:
    if args.live:
        _require_consent(config, args.allow_provider)
    lines = [
        f"{'OK ' if check.is_ok else 'FIX'} {check.name}: {check.detail}"
        for check in run_doctor(config, live=args.live)
    ]
    return {"text": "\n".join(lines)}


def _verify(args, config, store) -> dict:
    state = store.load(args.run)
    check = verify_records(store.run_dir(args.run) / "record.jsonl", state.record_head)
    return {"text": f"{'OK ' if check.is_intact else 'FAIL'} run record: {check.detail}"}


def _eval(args, config, store) -> dict:
    _require_consent(config, args.allow_provider)
    report = run_arm(config, load_cases(Path(args.cases)), store)
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report["control_passes"] = control_passes(baseline, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quorum-run")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--question-file", required=True)
    start.add_argument("--allow-provider", action="append", default=[])
    start.add_argument("--host-seats", type=int, default=0)
    start.add_argument("--epic", default="general")
    start.add_argument("--option", action="append", default=[])
    start.add_argument("--ratify", action="store_true")
    start.add_argument("--criterion", action="append", default=[])
    start.set_defaults(handler=_start)
    record = commands.add_parser("record")
    for name in ("--run", "--seat", "--prompt-hash", "--file"):
        record.add_argument(name, required=True)
    record.set_defaults(handler=_record)
    challenge = commands.add_parser("challenge")
    challenge.add_argument("--run", required=True)
    challenge.set_defaults(handler=_challenge)
    record_challenge = commands.add_parser("record-challenge")
    record_challenge.add_argument("--run", required=True)
    record_challenge.add_argument("--file", required=True)
    record_challenge.set_defaults(handler=_record_challenge)
    finish = commands.add_parser("finish")
    finish.add_argument("--run", required=True)
    finish.set_defaults(handler=_finish)
    note = commands.add_parser("note")
    note.add_argument("--run", required=True)
    note.add_argument("--text", required=True)
    note.set_defaults(handler=_note)
    stop = commands.add_parser("stop")
    stop.add_argument("--run", required=True)
    stop.add_argument("--yes", action="store_true")
    stop.set_defaults(handler=_stop)
    dashboard = commands.add_parser("dashboard")
    dashboard.add_argument("--run", required=True)
    dashboard.add_argument("--watch", action="store_true")
    dashboard.set_defaults(handler=_dashboard)
    evaluate = commands.add_parser("eval")
    evaluate.add_argument("--cases", required=True)
    evaluate.add_argument("--baseline")
    evaluate.add_argument("--allow-provider", action="append", default=[])
    evaluate.set_defaults(handler=_eval)
    setup = commands.add_parser("setup")
    setup.add_argument("--force", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--run", required=True)
    verify.set_defaults(handler=_verify)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--live", action="store_true")
    doctor.add_argument("--allow-provider", action="append", default=[])
    doctor.set_defaults(handler=_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "setup":
        print(write_user_config(USER_CONFIG, detect_tools(), force=args.force))
        return 0
    try:
        payload = args.handler(args, _load_config(), RunStore(default_state_dir()))
    except (ConfigError, DiversityError, RunError, OSError, ValueError, KeyError) as exc:
        print(f"quorum: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(payload["text"] if set(payload) == {"text"} else json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
