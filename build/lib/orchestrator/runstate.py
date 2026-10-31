"""Run state, kept outside the project so panelists do not read it."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets as stdlib_secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows has no fcntl; runs there are single-writer
    fcntl = None

_RUN_ID = re.compile(r"^[a-f0-9]{16}$")
KEY_BYTES = 32


class StateIntegrityError(ValueError):
    """Run state changed outside quorum-run, so it is refused."""


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
    options: list[str] = field(default_factory=list)
    host_disputes: list[str] = field(default_factory=list)
    host_challenges_recorded: int = 0
    ratify: bool = False
    judge: dict = field(default_factory=dict)
    criteria: dict[str, float] = field(default_factory=dict)
    brief: str = ""


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "quorum" / "runs"


@dataclass
class RunStore:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.signing_key = self._load_signing_key()

    def _load_signing_key(self) -> bytes:
        path = self.root / ".state.key"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes()
            if len(key) != KEY_BYTES:
                raise StateIntegrityError(f"signing key at {path} is damaged; delete it to start fresh") from None
            return key
        key = stdlib_secrets.token_bytes(KEY_BYTES)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(key)
        return key

    def _sign(self, body: str) -> str:
        return hmac.new(self.signing_key, body.encode("utf-8"), hashlib.sha256).hexdigest()

    def run_dir(self, run_id: str) -> Path:
        if not _RUN_ID.match(run_id):
            raise ValueError("run id must be 16 lowercase hex characters")
        path = self.root / run_id
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    @contextmanager
    def locked(self, run_id: str) -> Iterator[None]:
        """One writer at a time, so parallel records cannot lose a seat."""
        descriptor = os.open(self.run_dir(run_id) / "lock", os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def request_cancel(self, run_id: str) -> None:
        """Works during `finish`: it takes no lock, and calls check it."""
        (self.run_dir(run_id) / "cancel").touch(mode=0o600)

    def is_cancel_requested(self, run_id: str) -> bool:
        return (self.run_dir(run_id) / "cancel").exists()

    def save(self, state: RunState) -> None:
        target = self.run_dir(state.run_id) / "state.json"
        temporary = target.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            body = json.dumps(asdict(state), sort_keys=True)
            json.dump({"signature": self._sign(body), "state": body}, stream)
        temporary.replace(target)

    def load(self, run_id: str) -> RunState:
        stored = json.loads((self.run_dir(run_id) / "state.json").read_text(encoding="utf-8"))
        if not hmac.compare_digest(stored["signature"], self._sign(stored["state"])):
            raise StateIntegrityError(f"run {run_id} changed outside quorum-run; start a new run")
        data = json.loads(stored["state"])
        data["seats"] = [Seat(**seat) for seat in data["seats"]]
        return RunState(**data)
