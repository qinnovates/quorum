"""Source checking refuses hostile URLs before any connection."""

import pytest

from orchestrator import source_check
from orchestrator.source_check import UnsafeUrl, check_sources, public_address, quote_on_page, validate_url


@pytest.mark.parametrize("url", [
    "http://example.org/a", "https://user:pw@example.org/a", "https://example.org:8443/a",
    "https://example.org/a?" + "x" * 80, "file:///etc/passwd", "https://example.org/?token=" + "abcdefgh" + "12345678",
])
def test_unsafe_urls_are_refused(url):
    with pytest.raises(UnsafeUrl):
        validate_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.8", "169.254.169.254", "192.168.1.1", "::1", "fd00::1"])
def test_private_addresses_are_refused(monkeypatch, address):
    monkeypatch.setattr(source_check.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 443))])
    with pytest.raises(UnsafeUrl, match="public"):
        public_address("internal.example")


def test_one_private_record_taints_the_host(monkeypatch):
    records = [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("10.0.0.1", 443))]
    monkeypatch.setattr(source_check.socket, "getaddrinfo", lambda *a, **k: records)
    with pytest.raises(UnsafeUrl):
        public_address("rebind.example")


def test_quote_matching_needs_a_real_quote():
    page = "The system   met its Uptime target last year."
    assert quote_on_page("met its uptime target", page)
    assert not quote_on_page("uptime", page)
    assert not quote_on_page("never met its target", page)


def test_outcomes_sort_into_verified_and_reachable(monkeypatch):
    pages = {"https://a.example/1": "the exact quoted words here", "https://b.example/2": "other text"}
    def fake_fetch(url):
        if url not in pages:
            raise UnsafeUrl("status 404")
        return pages[url]
    monkeypatch.setattr(source_check, "fetch_page", fake_fetch)
    result = check_sources([
        ("https://a.example/1", "exact quoted words"), ("https://b.example/2", "exact quoted words"),
        ("https://c.example/3", "exact quoted words"),
    ], frozenset({"a.example", "b.example", "c.example"}))
    assert result.verified == {("https://a.example/1", "exact quoted words")}
    assert result.reachable == {"https://a.example/1", "https://b.example/2"}


def test_unlisted_hosts_are_never_contacted(monkeypatch):
    def forbidden(url):
        raise AssertionError("contacted an unlisted host")
    monkeypatch.setattr(source_check, "fetch_page", forbidden)
    result = check_sources([("https://my-question-as-text.attacker.example/x", "exact quoted words")], frozenset({"arxiv.org"}))
    assert not result.verified and not result.reachable


def test_lookalike_host_is_not_allowed():
    assert source_check.host_is_allowed("export.arxiv.org", frozenset({"arxiv.org"}))
    assert not source_check.host_is_allowed("arxiv.org.attacker.example", frozenset({"arxiv.org"}))
    assert not source_check.host_is_allowed("evilarxiv.org", frozenset({"arxiv.org"}))


def test_blank_quote_does_not_match():
    assert not quote_on_page(" " * 20, "any page at all")


@pytest.mark.parametrize("url", ["https://x:abc/", "https://a..b/", "https://example.org/\u00e9"])
def test_malformed_urls_fail_quietly(url):
    assert not check_sources([(url, "exact quoted words")], frozenset({"x", "a..b", "example.org"})).verified


@pytest.mark.parametrize("address", ["64:ff9b::a00:1", "224.0.0.1"])
def test_nat64_and_multicast_are_refused(monkeypatch, address):
    monkeypatch.setattr(source_check.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 443))])
    with pytest.raises(UnsafeUrl):
        public_address("x.example")


@pytest.mark.parametrize("quote", ["<!doctype html", "<meta charset=utf-8>", "font-family: serif; color: red"])
def test_markup_cannot_be_quoted_as_evidence(quote):
    page = "<!doctype html><head><meta charset=utf-8><style>font-family: serif; color: red</style></head><body>real words here</body>"
    assert not quote_on_page(quote, page)


def test_visible_quote_still_matches():
    assert quote_on_page("real words here", "<p>The <b>real</b> words here</p>")


def test_unlisted_urls_do_not_use_up_the_source_limit(monkeypatch):
    monkeypatch.setattr(source_check, "fetch_page", lambda url: "the exact quoted words")
    noise = [(f"https://noise{i}.example/x", "the exact quoted words") for i in range(40)]
    result = check_sources([*noise, ("https://zz.arxiv.org/1", "the exact quoted words")], frozenset({"arxiv.org"}))
    assert len(result.verified) == 1


def test_a_stuck_fetch_cannot_hold_the_run(monkeypatch):
    import threading
    import time
    release = threading.Event()
    monkeypatch.setattr(source_check, "OVERALL_DEADLINE_S", 0.1)
    monkeypatch.setattr(source_check, "fetch_page", lambda url: release.wait(5) or "x")
    started = time.monotonic()
    result = check_sources([("https://arxiv.org/1", "the exact quoted words")], frozenset({"arxiv.org"}))
    release.set()
    assert time.monotonic() - started < 2 and not result.verified
