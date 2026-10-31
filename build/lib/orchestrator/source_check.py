"""Check cited sources: does the page exist, and does it contain the quote?

Off by default, because fetching contacts the cited hosts. Pages are read by
Python only and never reach a model. URLs come from models, so each one is
treated as hostile, because a model can hide data in a hostname or path. Only
hosts on the user's allowlist are contacted: HTTPS only, public addresses only,
no redirects, no credential-shaped or long queries, and the connection is
pinned to the checked address, so DNS cannot change between check and call.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from urllib.parse import urlsplit

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
USER_AGENT = "quorum-source-check"
_HIDDEN_BLOCK = re.compile(r"(?is)<(script|style|head|noscript)\b.*?</\1\s*>|<!--.*?-->")
_TAG = re.compile(r"(?s)<[^>]*>")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class UnsafeUrl(ValueError):
    """A URL was refused before any connection was made."""


@dataclass(frozen=True)
class SourceCheck:
    """`verified` holds (url, quote) pairs, so a quote cannot borrow a URL's tier."""

    verified: frozenset[tuple[str, str]] = frozenset()
    reachable: frozenset[str] = frozenset()


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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def visible_text(page: str) -> str:
    """Text a reader sees, so markup cannot be quoted as evidence."""
    return _TAG.sub(" ", _HIDDEN_BLOCK.sub(" ", page))


def quote_on_page(quote: str, page: str) -> bool:
    normalized = _normalize(quote)
    is_substantial = len(normalized) >= MIN_QUOTE_CHARS and len(normalized.split()) >= MIN_QUOTE_WORDS
    return is_substantial and normalized in _normalize(visible_text(page))


def _check_one(pair: tuple[str, str], allowed_hosts: frozenset[str]) -> str:
    url, quote = pair
    try:
        host, _ = validate_url(url)
        if not host_is_allowed(host, allowed_hosts):
            return "skipped"
        page = fetch_page(url)
    except (ValueError, OSError, http.client.HTTPException):
        return "unreachable"
    return "verified" if quote_on_page(quote, page) else "reachable"


def _is_listed(url: str, allowed_hosts: frozenset[str]) -> bool:
    try:
        return host_is_allowed(validate_url(url)[0], allowed_hosts)
    except ValueError:
        return False


def check_sources(pairs: list[tuple[str, str]], allowed_hosts: frozenset[str]) -> SourceCheck:
    """Check (url, quote) pairs on allowed hosts. The source count is capped."""
    unique = sorted(pair for pair in set(pairs) if _is_listed(pair[0], allowed_hosts))[:MAX_SOURCES]
    if not unique:
        return SourceCheck()
    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="quorum-source")
    futures = [pool.submit(_check_one, pair, allowed_hosts) for pair in unique]
    wait(futures, timeout=OVERALL_DEADLINE_S)
    pool.shutdown(wait=False, cancel_futures=True)
    outcomes = [f.result() if f.done() and not f.cancelled() else "unreachable" for f in futures]
    verified = frozenset(pair for pair, status in zip(unique, outcomes) if status == "verified")
    reachable = frozenset(pair[0] for pair, status in zip(unique, outcomes) if status != "unreachable" and status != "skipped")
    return SourceCheck(verified, reachable)
