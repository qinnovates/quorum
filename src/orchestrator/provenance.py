"""Hash-linked run record: what happened in a run, and in what order.

Each record holds hashes, IDs and labels, never question or answer text, and
links to the record before it. The latest hash lives in signed run state, so
an edit to this file is detected. This shows the record is intact. It does not
show that a claim is true, or stop a process running as you from rewriting it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

GENESIS_HASH = "0" * 64


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_hash(sequence: int, kind: str, fields: dict, previous: str) -> str:
    body = json.dumps(
        {"sequence": sequence, "kind": kind, "fields": fields, "previous": previous}, sort_keys=True
    )
    return content_hash(body)


def append_record(path: Path, sequence: int, kind: str, fields: dict, previous: str) -> str:
    """Append one record and return its hash."""
    digest = _record_hash(sequence, kind, fields, previous)
    line = json.dumps(
        {"sequence": sequence, "kind": kind, "fields": fields, "previous": previous, "hash": digest},
        sort_keys=True,
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    return digest


@dataclass(frozen=True)
class RecordCheck:
    is_intact: bool
    records: int
    detail: str


def verify_records(path: Path, expected_head: str) -> RecordCheck:
    """Recompute the chain and compare it to the head in signed run state."""
    previous, count = GENESIS_HASH, 0
    rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for line in rows:
        try:
            row = json.loads(line)
            digest = _record_hash(row["sequence"], row["kind"], row["fields"], row["previous"])
            is_linked = row["previous"] == previous and row["sequence"] == count and row["hash"] == digest
        except (ValueError, KeyError, TypeError):
            return RecordCheck(False, count, f"record {count} is unreadable")
        if not is_linked:
            return RecordCheck(False, count, f"record {count} does not match the chain")
        previous, count = digest, count + 1
    if previous != expected_head:
        return RecordCheck(False, count, "the latest record does not match signed run state")
    return RecordCheck(True, count, f"{count} records intact")
