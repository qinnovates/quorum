"""Typed run events, redacted at the emitter. Any UI subscribes to this file.

Notes are data. Only a confirmed `instruction_confirmed` event can change a run.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .secrets import redact

EVENT_TYPES = frozenset({
    "run_started", "route_decided", "seat_issued", "panelist_result",
    "gate_passed", "gate_failed", "budget_refused", "challenge_round",
    "note_added", "instruction_confirmed", "brief_ready", "run_finished",
})


@dataclass
class EventLog:
    path: Path

    def emit(self, event_type: str, **fields: object) -> None:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {event_type!r}")
        if event_type == "instruction_confirmed" and fields.get("confirmed_by_user") is not True:
            raise ValueError("instruction events need explicit user confirmation")
        line = redact(json.dumps({"type": event_type, **fields}, sort_keys=True, default=str))
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(row) for row in self.path.read_text(encoding="utf-8").splitlines()]
