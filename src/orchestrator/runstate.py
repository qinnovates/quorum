"""Run state, kept outside the project so panelists do not read it."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_RUN_ID = re.compile(r"^[a-f0-9]{16}$")


@dataclass
class Seat:
    seat_id: str
    role: str
    provider: str
    family: str
    model_id: str
    attestation: str
    prompt: str
    prompt_hash: str
    max_output_tokens: int
    route_status: str
    route_reason: str
    status: str = "issued"
    answer: dict | None = None
    error: str | None = None


@dataclass
class RunState:
    run_id: str
    question: str
    stakes: str
    status: str
    assumptions: list[str]
    allowance: dict[str, int]
    spent: dict[str, int] = field(default_factory=dict)
    seats: list[Seat] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    usage: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    reused_task: bool = False
    brief: str = ""


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "quorum" / "runs"


@dataclass
class RunStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise ValueError("run id must be 16 lowercase hex characters")
        path = self.root / run_id
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    def save(self, state: RunState) -> None:
        target = self.run_dir(state.run_id) / "state.json"
        temporary = target.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(asdict(state), stream, indent=2)
        temporary.replace(target)

    def load(self, run_id: str) -> RunState:
        data = json.loads((self.run_dir(run_id) / "state.json").read_text(encoding="utf-8"))
        data["seats"] = [Seat(**seat) for seat in data["seats"]]
        return RunState(**data)
