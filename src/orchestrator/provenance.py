"""Hash-linked run record: what happened in a run, and what came from what.

Each record holds hashes, IDs and labels, never question or answer text, and
links to the record before it. The latest hash lives in signed run state, so
an edit to this file is detected. Records can also be lineage nodes, whose hash
covers their content and parents, forming a Merkle DAG from sources to verdict.
This shows the record is intact. It does not show that a claim is true, or stop
a process running as you from rewriting it.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

GENESIS_HASH = "0" * 64
_ARXIV_PATH = re.compile(r"^/(?:abs|pdf|html|format|ps)/(.+?)(?:\.pdf)?$")
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(.+)$")
_ARXIV_VERSION = re.compile(r"v\d+$")


def content_hash(text: str) -> str:
    """Hash any text. Invalid unicode from a provider cannot stop a run here."""
    return hashlib.sha256(text.encode("utf-8", errors="backslashreplace")).hexdigest()


def node_hash(kind: str, content_digest: str, parents: Iterable[str] = ()) -> str:
    """Identify a node by what it is and everything it came from."""
    body = json.dumps({"kind": kind, "content": content_digest, "parents": sorted(parents)}, sort_keys=True)
    return content_hash(body)


def _clean_host(hostname: str) -> str:
    """One spelling per host: NFKC, no trailing dot, no www or mobile prefix."""
    host = unicodedata.normalize("NFKC", hostname).rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass  # keep the folded name: this labels a citation, and nothing connects to it
    return host.removeprefix("www.").removeprefix("m.")


def _clean_path(path: str) -> str:
    decoded = posixpath.normpath(re.sub(r"/+", "/", unquote(path.split(";")[0])))
    return "" if decoded in (".", "/") else decoded.rstrip("/")


def _scheme_root(text: str) -> str | None:
    prefix, has_colon, rest = text.partition(":")
    if not has_colon or prefix not in ("arxiv", "doi"):
        return None
    identifier = unquote(rest).split("?")[0].split("#")[0].strip("/")
    if prefix == "doi":
        return _document_root("doi.org", f"/{identifier}")
    return f"arxiv:{_ARXIV_VERSION.sub('', identifier)}"


def _document_root(host: str, path: str) -> str | None:
    arxiv = _ARXIV_PATH.match(path) if host == "arxiv.org" or host.endswith(".arxiv.org") else None
    if arxiv:
        return f"arxiv:{_ARXIV_VERSION.sub('', arxiv.group(1))}"
    if host != "doi.org" and not host.endswith(".doi.org"):
        return None
    identifier = path.strip("/").removeprefix("doi:")
    registered = _ARXIV_DOI.match(identifier)
    return f"arxiv:{_ARXIV_VERSION.sub('', registered.group(1))}" if registered else f"doi:{identifier}"


def source_root(source: str) -> str:
    """One name per document, so URL variants do not count as separate sources.

    Query strings are dropped because they are free to vary. Two documents that
    differ only by query therefore count as one. Unparseable text stays as it is.
    """
    text = source.strip().lower()
    named = _scheme_root(text)
    if named:
        return named
    try:
        parts = urlsplit(text)
        hostname = parts.hostname
    except ValueError:
        return text
    if parts.scheme != "https" or not hostname:
        return text
    host, path = _clean_host(hostname), _clean_path(parts.path)
    return _document_root(host, path) or f"{host}{path}"


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


def _node_is_valid(kind: str, fields: dict, seen: set[str]) -> bool:
    """A node must match its own hash and name only earlier nodes as parents."""
    if "node" not in fields:
        return True
    parents = fields["parents"]
    is_valid = set(parents) <= seen and node_hash(kind, fields["content"], parents) == fields["node"]
    seen.add(fields["node"])
    return is_valid


def verify_records(path: Path, expected_head: str) -> RecordCheck:
    """Recompute the chain and lineage, and compare to the signed head."""
    previous, count = GENESIS_HASH, 0
    nodes: set[str] = set()
    try:
        rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except UnicodeDecodeError:
        return RecordCheck(False, 0, "the record is not valid text")
    for line in rows:
        try:
            row = json.loads(line)
            digest = _record_hash(row["sequence"], row["kind"], row["fields"], row["previous"])
            is_linked = row["previous"] == previous and row["sequence"] == count and row["hash"] == digest
            is_linked = is_linked and _node_is_valid(row["kind"], row["fields"], nodes)
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
            return RecordCheck(False, count, f"record {count} is unreadable")
        if not is_linked:
            return RecordCheck(False, count, f"record {count} does not match the chain")
        previous, count = digest, count + 1
    if previous != expected_head:
        return RecordCheck(False, count, "the latest record does not match signed run state")
    return RecordCheck(True, count, f"{count} records intact")


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def claim_summaries(path: Path) -> list[dict]:
    """Every claim's ID and labels, so a reader can pick one to trace."""
    fields = ("claim_id", "tier", "family", "issues")
    return [{k: r["fields"].get(k) for k in fields} for r in _load_rows(path) if r["kind"] == "claim"]


def claim_lineage(path: Path, claim_id: str) -> list[dict]:
    """A claim's direct parents and children, never its siblings on the same page."""
    rows = _load_rows(path)
    own = [r for r in rows if r["fields"].get("claim_id") == claim_id]
    parents = {parent for r in own for parent in r["fields"].get("parents", ())}
    nodes = {r["fields"]["node"] for r in own if "node" in r["fields"]}
    return [
        r for r in rows
        if r in own or r["fields"].get("node") in parents
        or claim_id in r["fields"].get("claim_ids", ())
        or nodes & set(r["fields"].get("parents", ()))
    ]
