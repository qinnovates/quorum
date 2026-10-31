"""Epic and task ledger: who researched what, so work is not repeated.

Exact matching decides reuse. Similar wording is never merged automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .secrets import redact

try:
    import fcntl
except ImportError:  # Windows has no fcntl; runs there are single-writer
    fcntl = None


@dataclass
class TaskRecord:
    task_id: str
    epic: str
    topic: str
    status: str
    run_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def topic_key(topic: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", topic.lower()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


@dataclass
class TaskTrack:
    path: Path

    def _load(self) -> dict[str, TaskRecord]:
        if not self.path.exists():
            return {}
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        return {row["task_id"]: TaskRecord(**row) for row in rows}

    def _save(self, tasks: dict[str, TaskRecord]) -> None:
        temporary = self.path.with_suffix(f".{os.getpid()}.{secrets.token_hex(4)}.tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump([asdict(t) for t in tasks.values()], stream, indent=2)
        temporary.replace(self.path)

    def find(self, topic: str) -> TaskRecord | None:
        return self._load().get(topic_key(topic))

    @contextmanager
    def _locked(self) -> Iterator[None]:
        descriptor = os.open(self.path.with_suffix(".lock"), os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def claim(self, topic: str, epic: str, run_id: str) -> tuple[TaskRecord, bool]:
        """Return the task and whether it already existed."""
        with self._locked():
            tasks = self._load()
            key = topic_key(topic)
            existing = key in tasks
            task = tasks.get(key) or TaskRecord(key, redact(epic), redact(topic), "open")
            task.run_ids.append(run_id)
            tasks[key] = task
            self._save(tasks)
        return task, existing

    def complete(self, topic: str, evidence: list[str]) -> None:
        with self._locked():
            tasks = self._load()
            task = tasks.get(topic_key(topic))
            if task is None:
                return
            task.status = "done"
            task.evidence.extend(redact(item) for item in evidence)
            self._save(tasks)
