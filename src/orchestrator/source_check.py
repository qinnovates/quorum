"""Check cited sources: does the page exist, and does it contain the quote?

Off by default, because fetching contacts the cited hosts. Pages are read by
Python only and never reach a model. URLs come from models, so each one is
treated as hostile, because a model can hide data in a hostname or path. Only
hosts on the user's allowlist are contacted: HTTPS only, public addresses only,
no redirects, no credential-shaped or long queries, and the connection is
pinned to the checked address, so DNS cannot change between check and call.
"""

from __future__ import annotations

import html
import http.client
import ipaddress
import queue
import re
import socket
import ssl
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from urllib.parse import urlsplit

from .claim_check import fold_text
from .provenance import content_hash
from .secrets import contains_credential

FETCH_TIMEOUT_S = 8.0
FETCH_DEADLINE_S = 10.0
READ_CHUNK_BYTES = 8_192
MAX_PAGE_BYTES = 500_000
MAX_QUERY_CHARS = 64
MAX_SOURCES = 12
MIN_QUOTE_CHARS = 12
MIN_QUOTE_WORDS = 3
OVERALL_DEADLINE_S = 30.0
MAX_WORKERS = 4
CONTEXT_CHARS = 120
MAX_OCCURRENCES = 5
USER_AGENT = "quorum-source-check"
_HIDDEN_TAGS = ("script", "style", "noscript", "template", "title", "noframes", "noembed", "iframe", "datalist")
_TAG_NAME_END = r"(?=[\s/>]|$)"
_HIDDEN_OPEN = re.compile(rf"<({'|'.join(_HIDDEN_TAGS)}){_TAG_NAME_END}", re.IGNORECASE)
_HIDDEN_CLOSE = {tag: re.compile(rf"</{tag}{_TAG_NAME_END}", re.IGNORECASE) for tag in _HIDDEN_TAGS}
_MARKUP_START = re.compile(r"<[a-zA-Z/!?]")
_TAG_STOP = re.compile(r"""[>"']""")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class UnsafeUrl(ValueError):
    """A URL was refused before any connection was made."""


@dataclass(frozen=True)
class Snapshot:
    """What a page said when checked. Contexts stay in memory and are never recorded."""

    page_hash: str
    retrieved_at: str
    quote_offset: int
    contexts: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SourceCheck:
    """`verified` holds (url, quote) pairs, so a quote cannot borrow a URL's tier."""

    verified: frozenset[tuple[str, str]] = frozenset()
    reachable: frozenset[str] = frozenset()
    snapshots: Mapping[tuple[str, str], Snapshot] = field(default_factory=lambda: MappingProxyType({}))
    over_limit: int = 0


def _is_public(address: str) -> bool:
    parsed = ipaddress.ip_address(address.split("%")[0])
    is_nat64 = parsed.version == 6 and parsed in _NAT64
    return parsed.is_global and not parsed.is_multicast and not is_nat64


def host_is_allowed(host: str, allowed_hosts: frozenset[str]) -> bool:
    return any(host == item or host.endswith(f".{item}") for item in allowed_hosts)


def public_address(host: str) -> str:
    """Resolve a host and refuse it unless every address is public."""
    try:
        records = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise UnsafeUrl(f"cannot resolve host ({type(exc).__name__})") from None
    addresses = [record[4][0] for record in records]
    if not addresses or not all(_is_public(a) for a in addresses):
        raise UnsafeUrl("host does not resolve only to public addresses")
    return addresses[0]


def validate_url(url: str) -> tuple[str, str]:
    """Return (host, path). Refuse anything that could carry data out."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise UnsafeUrl("only https URLs are checked")
    if parts.username or parts.password or parts.port not in (None, 443):
        raise UnsafeUrl("URLs with credentials or custom ports are refused")
    if len(parts.query) > MAX_QUERY_CHARS or contains_credential(url):
        raise UnsafeUrl("long or credential-shaped queries are refused")
    path = parts.path or "/"
    return parts.hostname, f"{path}?{parts.query}" if parts.query else path


class _PinnedConnection(http.client.HTTPSConnection):
    """Connect to an already-checked address, still verifying the certificate."""

    def __init__(self, host: str, address: str) -> None:
        super().__init__(host, 443, timeout=FETCH_TIMEOUT_S, context=ssl.create_default_context())
        self._pinned_address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._pinned_address, 443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


def _read_within_limits(response: http.client.HTTPResponse) -> bytes:
    """Stop at the size cap or the deadline, so a slow server cannot stall a run."""
    deadline = time.monotonic() + FETCH_DEADLINE_S
    body = bytearray()
    while len(body) < MAX_PAGE_BYTES and time.monotonic() < deadline:
        chunk = response.read1(READ_CHUNK_BYTES)
        if not chunk:
            break
        body.extend(chunk)
    return bytes(body[:MAX_PAGE_BYTES])


def fetch_page(url: str) -> str:
    """Fetch one page. A redirect or an error counts as unreachable."""
    host, path = validate_url(url)
    connection = _PinnedConnection(host, public_address(host))
    try:
        connection.request("GET", path, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
        response = connection.getresponse()
        if response.status != 200:
            raise UnsafeUrl(f"status {response.status}")
        return _read_within_limits(response).decode("utf-8", errors="replace")
    finally:
        connection.close()


def _opens_attribute_value(page: str, quote_index: int) -> bool:
    """A quote mark opens a value only straight after `=`, as in `<a href="x">`."""
    position = quote_index - 1
    while position >= 0 and page[position].isspace():
        position -= 1
    return position >= 0 and page[position] == "="


def _tag_end(page: str, start: int) -> int:
    """Index after a tag's closing `>`, skipping quoted attributes. Never moves backward."""
    position = start
    while True:
        stop = _TAG_STOP.search(page, position)
        if stop is None:
            return len(page)
        if stop.group() == ">":
            return stop.end()
        if not _opens_attribute_value(page, stop.start()):
            position = stop.end()
            continue
        closing_quote = page.find(stop.group(), stop.end())
        if closing_quote < 0:
            return len(page)
        position = closing_quote + 1


def _markup_end(page: str, start: int) -> int:
    """Index after markup at `start`. Anything left open hides the rest of the page."""
    if page.startswith(("<!-->", "<!--->"), start):
        return page.find(">", start) + 1
    if page.startswith("<!--", start):
        close = page.find("-->", start + 4)
        return len(page) if close < 0 else close + 3
    hidden = _HIDDEN_OPEN.match(page, start)
    if hidden:
        closing = _HIDDEN_CLOSE[hidden.group(1).lower()].search(page, hidden.end())
        return len(page) if closing is None else _tag_end(page, closing.end())
    return _tag_end(page, start)


def visible_text(page: str) -> str:
    """Text outside hidden elements, entities decoded. Linear, so markup cannot stall it.

    CSS and `hidden` attributes are not interpreted, and a page owner can print
    any text visibly anyway, so this keeps out page plumbing, not a hostile author.
    """
    parts, position = [], 0
    while (opening := page.find("<", position)) >= 0:
        parts.append(page[position:opening])
        if _MARKUP_START.match(page, opening):
            parts.append(" ")
            position = _markup_end(page, opening)
        else:
            parts.append("<")
            position = opening + 1
    parts.append(page[position:])
    return html.unescape("".join(parts))


def _occurrences(text: str, quote: str) -> list[int]:
    found, start = [], text.find(quote)
    while start >= 0 and len(found) < MAX_OCCURRENCES:
        found.append(start)
        start = text.find(quote, start + 1)
    return found


def snapshot_quote(quote: str, page: str) -> Snapshot | None:
    """Locate a substantial quote in the visible text, with the words around each use."""
    normalized = fold_text(quote).lower()
    is_substantial = len(normalized) >= MIN_QUOTE_CHARS and len(normalized.split()) >= MIN_QUOTE_WORDS
    text = fold_text(visible_text(page)).lower()
    offsets = _occurrences(text, normalized) if is_substantial else []
    if not offsets:
        return None
    contexts = tuple(
        (text[max(start - CONTEXT_CHARS, 0):start], text[start + len(normalized):start + len(normalized) + CONTEXT_CHARS])
        for start in offsets
    )
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return Snapshot(content_hash(page), retrieved_at, offsets[0], contexts)


def quote_on_page(quote: str, page: str) -> bool:
    return snapshot_quote(quote, page) is not None


def _check_one(pair: tuple[str, str], allowed_hosts: frozenset[str]) -> tuple[str, Snapshot | None]:
    url, quote = pair
    try:
        host, _ = validate_url(url)
        if not host_is_allowed(host, allowed_hosts):
            return "skipped", None
        page = fetch_page(url)
    except (ValueError, OSError, http.client.HTTPException):
        return "unreachable", None
    try:
        snapshot = snapshot_quote(quote, page)
    except ValueError:  # an entity too large to decode: the page was reached, the quote not shown
        return "reachable", None
    return ("verified" if snapshot else "reachable"), snapshot


def _is_listed(url: str, allowed_hosts: frozenset[str]) -> bool:
    try:
        return host_is_allowed(validate_url(url)[0], allowed_hosts)
    except ValueError:
        return False


def _run_checks(pairs: list[tuple[str, str]], allowed_hosts: frozenset[str]) -> list[tuple[str, Snapshot | None]]:
    """Daemon workers, so a stuck fetch cannot hold the run or the process past the deadline."""
    waiting: queue.SimpleQueue[int] = queue.SimpleQueue()
    finished: dict[int, tuple[str, Snapshot | None]] = {}
    expired = threading.Event()
    for index in range(len(pairs)):
        waiting.put(index)

    def work() -> None:
        while not expired.is_set():
            try:
                index = waiting.get_nowait()
            except queue.Empty:
                return
            try:
                finished[index] = _check_one(pairs[index], allowed_hosts)
            except Exception:  # one bad page fails its own check, never the run
                finished[index] = ("unreachable", None)

    workers = [threading.Thread(target=work, name="quorum-source", daemon=True) for _ in range(MAX_WORKERS)]
    for worker in workers:
        worker.start()
    deadline = time.monotonic() + OVERALL_DEADLINE_S
    for worker in workers:
        worker.join(max(deadline - time.monotonic(), 0))
    expired.set()
    return [dict(finished).get(index, ("unreachable", None)) for index in range(len(pairs))]


def check_sources(pairs: list[tuple[str, str]], allowed_hosts: frozenset[str]) -> SourceCheck:
    """Check (url, quote) pairs on allowed hosts, in the order given, up to the cap."""
    listed = [pair for pair in dict.fromkeys(pairs) if _is_listed(pair[0], allowed_hosts)]
    unique = listed[:MAX_SOURCES]
    if not unique:
        return SourceCheck()
    outcomes = _run_checks(unique, allowed_hosts)
    snapshots = {pair: snapshot for pair, (_, snapshot) in zip(unique, outcomes) if snapshot}
    reachable = frozenset(pair[0] for pair, (status, _) in zip(unique, outcomes) if status in ("verified", "reachable"))
    return SourceCheck(frozenset(snapshots), reachable, MappingProxyType(snapshots), len(listed) - len(unique))
