"""JSON over HTTP: no redirects, and no proxy for loopback."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would forward Authorization to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


OPENER = urllib.request.build_opener(_NoRedirect)
DIRECT_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
MAX_RESPONSE_BYTES = 10_000_000


def opener_for(url: str) -> urllib.request.OpenerDirector:
    """Loopback traffic never goes through an environment proxy."""
    is_loopback = urllib.parse.urlsplit(url).hostname in _LOOPBACK_HOSTS
    return DIRECT_OPENER if is_loopback else OPENER


def post_json(url: str, body: dict, timeout_s: float, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with opener_for(url).open(req, timeout=timeout_s) as resp:  # noqa: S310 - user-configured endpoint
        raw = resp.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError(f"response is over {MAX_RESPONSE_BYTES} bytes")
    return json.loads(raw.decode())
