"""`python -m orchestrator.cli`: the skill's interface to the run loop.

Answers are passed by file path, so the host model does not retype them.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .config import Config, ConfigError, load, tighten
from .diversity import DiversityError
from .intent import IntentResult
from .run import RunError, finish_run, record_host_answer, start_run
from .runstate import RunStore, default_state_dir

USER_CONFIG = Path.home() / ".config" / "quorum" / "quorum.toml"
PROJECT_CONFIG = Path("quorum.toml")


def _load_config() -> Config:
    """User config is required. A project file can only tighten it."""
    if not USER_CONFIG.exists():
        raise ConfigError(f"no config found; create {USER_CONFIG} from docs/quorum.example.toml")
    config = load(USER_CONFIG, trusted=True)
    return tighten(config, load(PROJECT_CONFIG)) if PROJECT_CONFIG.exists() else config


def _consume(path_text: str) -> str:
    """Read a handoff file, then delete it so its text does not linger."""
    path = Path(path_text).resolve(strict=True)
    text = path.read_text(encoding="utf-8")
    path.unlink()
    return text


def _start(args, config, store) -> dict:
    state = start_run(config, args.question, store, host_seats=args.host_seats, epic=args.epic)
    if isinstance(state, IntentResult):
        return asdict(state)
    open_seats = [
        {"seat": s.seat_id, "prompt": s.prompt, "prompt_hash": s.prompt_hash, "max_output_tokens": s.max_output_tokens}
        for s in state.seats if s.status == "issued"
    ]
    return {"run_id": state.run_id, "stakes": state.stakes, "host_seats": open_seats}


def _record(args, config, store) -> dict:
    text = _consume(args.file)
    with store.locked(args.run):
        state = store.load(args.run)
        seat = record_host_answer(state, config, store, args.seat, args.prompt_hash, text)
    return {"seat": seat.seat_id, "status": seat.status}


def _finish(args, config, store) -> dict:
    state = store.load(args.run)
    return {"brief": finish_run(state, config, store), "status": store.load(args.run).status}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quorum-run")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--question-file", required=True)
    start.add_argument("--host-seats", type=int, default=0)
    start.add_argument("--epic", default="general")
    start.set_defaults(handler=_start)
    record = commands.add_parser("record")
    for name in ("--run", "--seat", "--prompt-hash", "--file"):
        record.add_argument(name, required=True)
    record.set_defaults(handler=_record)
    finish = commands.add_parser("finish")
    finish.add_argument("--run", required=True)
    finish.set_defaults(handler=_finish)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "start":
            args.question = _consume(args.question_file)
        payload = args.handler(args, _load_config(), RunStore(default_state_dir()))
    except (ConfigError, DiversityError, RunError, OSError, ValueError, KeyError) as exc:
        print(f"quorum: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
