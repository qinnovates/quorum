"""A handoff keeps a claim's meaning, and evidence is counted honestly."""

import itertools
import json
import time
import unicodedata
from dataclasses import replace
from types import MappingProxyType

import pytest
from quorum_scorer import Claim

from orchestrator import http_transport, source_check
from orchestrator.challenge import challenge_payload
from orchestrator.claim_check import DIRECTION_MISMATCH, NUMBER_MISMATCH, OFF_TOPIC, POLARITY_MISMATCH, fold_text, support_issues
from orchestrator.claim_gather import collect_claims, source_pairs
from orchestrator.conclude import finish_run, issue_host_challenge, record_host_challenge
from orchestrator.config import Config, load
from orchestrator.decision import AnswerError, ScoredClaim, build_brief, parse_answer, pivotal_claims, score_options
from orchestrator.entailment import NEUTRAL, SUPPORTS, UNCHECKED, check_pivotal_claims, parse_label
from orchestrator.events import EventLog
from orchestrator.handoff import PARTIAL_CLAIM_NOTE, TEXT_CAP, build_handoff, claim_id, dedupe_claims, encode_payload
from orchestrator.judge import _judge_payload, run_judge
from orchestrator.limits import RunLimits
from orchestrator.provenance import claim_lineage, content_hash, node_hash, source_root, verify_records
from orchestrator.providers import FakeProvider
from orchestrator.router import Candidate
from orchestrator.option_merge import same_option
from orchestrator.run import RunError, start_run
from orchestrator.runstate import RunState, RunStore, Seat, StateIntegrityError
from orchestrator.source_check import Snapshot, SourceCheck, check_sources, snapshot_quote
from orchestrator.source_match import UNMATCHED, best_assignment
from orchestrator.usage import record_handoff

URL = "https://example.org/report"
QUESTION = "For our API, which database is best given a $100 budget limit and uptime as the goal?"
SNAPSHOT = Snapshot("a" * 64, "2026-10-31T00:00:00+00:00", 0, (("", ""),))


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs")


def scored(family, source=URL, option="a", tier="STRONG", **fields):
    return ScoredClaim(f"C{family}{source}", "text", source, tier, option, family, **fields)


def state_with(*answers):
    seats = [
        Seat(f"S{i}", "research", "p", family, "m", "python", "", "", 100, "unproven", "", "answered", answer)
        for i, (family, answer) in enumerate(answers)
    ]
    return RunState("0" * 16, "q", "low", "OPEN", [], {}, seats=seats)


@pytest.mark.parametrize("first,second", [
    ("latency is > 5 ms", "latency is < 5 ms"),
    ("revenue rose 5%", "revenue rose -5"),
    ("use v1.5", "use v1 5"),
])
def test_claims_with_different_meanings_keep_separate_ids(first, second):
    claims = [Claim(text=first, source=URL), Claim(text=second, source=URL)]
    assert claim_id(claims[0]) != claim_id(claims[1])
    assert len(dedupe_claims(claims)) == 2


def test_spelling_differences_still_dedupe():
    claims = [Claim(text="Uptime  is HIGH.", source=URL), Claim(text="uptime is high", source=URL)]
    assert len(dedupe_claims(claims)) == 1


def test_a_claim_within_the_cap_keeps_its_condition():
    text = "The library is safe to deploy " * 10 + "unless TLS is disabled"
    assert len(text) <= TEXT_CAP
    row = build_handoff([Claim(text=text, source=URL)], "r", open_questions=[], debate_summary="")["claims"][0]
    assert row["text"].endswith("unless TLS is disabled") and "partial" not in row


def test_a_shortened_claim_is_marked_and_receivers_are_told():
    text = "x" * (TEXT_CAP + 1)
    row = build_handoff([Claim(text=text, source=URL)], "r", open_questions=[], debate_summary="")["claims"][0]
    assert row["partial"] is True and "partial" in PARTIAL_CLAIM_NOTE


@pytest.mark.parametrize("claim,quote,expected", [
    ("Latency is 5 ms", "latency is 50 ms in tests", NUMBER_MISMATCH),
    ("Latency is > 5 ms", "measured latency is < 5 ms", NUMBER_MISMATCH),
    ("Revenue fell -5%", "revenue moved 5% in the quarter", NUMBER_MISMATCH),
    ("The drug reduces mortality in adults", "the drug does not reduce mortality in adults", POLARITY_MISMATCH),
    ("Postgres handles the required write throughput", "bananas ripen quickly in warm kitchens", OFF_TOPIC),
])
def test_quote_that_cannot_carry_the_claim_is_flagged(claim, quote, expected):
    assert expected in support_issues(claim, quote)


def test_negation_just_before_the_quote_counts():
    page = "<p>The trial did not show that the drug reduces mortality in adults.</p>"
    snapshot = snapshot_quote("the drug reduces mortality in adults", page)
    issues = support_issues("The drug reduces mortality in adults", "the drug reduces mortality in adults", snapshot.contexts)
    assert POLARITY_MISMATCH in issues


def test_negation_in_an_earlier_sentence_does_not_count():
    contexts = (("this was not a large trial. overall, ", ""),)
    assert support_issues("The drug reduces mortality", "the drug reduces mortality", contexts) == ()


def test_faithful_quote_passes():
    assert support_issues("Uptime was 99.9% across regions", "uptime was 99.9% across all regions") == ()


def test_a_misused_quote_does_not_earn_strong():
    quote = "the drug does not reduce mortality"
    state = state_with(("gemini", {"option": "a", "claims": [{"text": "The drug reduces mortality", "source": URL, "quote": quote}]}))
    checked = SourceCheck(frozenset({(URL, quote)}), frozenset({URL}), MappingProxyType({(URL, quote): SNAPSHOT}))
    claim = collect_claims(state, frozenset(), checked)[0]
    assert claim.tier == "MODERATE" and POLARITY_MISMATCH in claim.issues


def test_a_supported_quote_earns_strong():
    quote = "the drug reduces mortality"
    state = state_with(("gemini", {"option": "a", "claims": [{"text": "The drug reduces mortality", "source": URL, "quote": quote}]}))
    checked = SourceCheck(frozenset({(URL, quote)}), frozenset({URL}), MappingProxyType({(URL, quote): SNAPSHOT}))
    assert collect_claims(state, frozenset(), checked)[0].tier == "STRONG"


def test_three_families_citing_one_document_count_once():
    claims = [scored(f, source=s) for f, s in [("gemini", URL), ("openai", URL + "/"), ("claude", "https://www.example.org/report#top")]]
    top = score_options(claims)[0]
    assert top.score == 1.0 and top.independent_sources == 1 and len(top.families) == 3


def test_independent_documents_from_separate_families_add_up():
    top = score_options([scored("gemini"), scored("openai", source="https://other.example/b")])[0]
    assert top.score == 2.0 and top.independent_sources == 2


def test_one_family_with_many_documents_counts_once():
    top = score_options([scored("gemini"), scored("gemini", source="https://other.example/b")])[0]
    assert top.score == 1.0


@pytest.mark.parametrize("variant", [
    "https://arxiv.org/abs/2610.15095", "https://arxiv.org/pdf/2610.15095v1", "https://arxiv.org/pdf/2610.15095v1.pdf", "arXiv:2610.15095v2",
])
def test_arxiv_variants_share_a_root(variant):
    assert source_root(variant) == "arxiv:2610.15095"


def test_doi_link_and_id_share_a_root():
    assert source_root("https://doi.org/10.1000/ABC") == source_root("doi:10.1000/abc")


def test_a_query_string_cannot_make_a_new_source():
    assert source_root(URL + "?copy=2") == source_root(URL)


def test_the_same_quote_on_two_pages_is_one_source():
    quote = "uptime reached four nines this year"
    second = "https://mirror.example/copy"
    state = state_with(
        ("gemini", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": URL, "quote": quote}]}),
        ("openai", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": second, "quote": quote}]}),
    )
    snapshots = {(URL, quote): SNAPSHOT, (second, quote): SNAPSHOT}
    checked = SourceCheck(frozenset(snapshots), frozenset({URL, second}), MappingProxyType(snapshots))
    assert score_options(collect_claims(state, frozenset(), checked))[0].independent_sources == 1


def test_brief_shows_evidence_parts_not_one_percentage():
    rows = build_brief([scored("gemini", is_disputed=True, issues=("off_topic",))], [], []).evidence_rows
    assert "1 distinct cited document(s), 1 checked" in rows[0] and "1 disputed" in rows[0] and "1 failed a support check" in rows[0]
    assert "%" not in rows[0]


def finished(store):
    numbers = itertools.count()

    def reply(prompt):
        if "challenger" in prompt:
            return json.dumps({"objections": []})
        source = f"https://example.org/doc{next(numbers)}"
        return json.dumps({"option": "postgres", "claims": [{"text": "Evidence favours this", "source": source}], "would_change": "x"})

    config = Config(min_families=2, limits=RunLimits(token_budget=100_000))
    for rank, (name, family) in enumerate([("g", "gemini"), ("o", "openai")]):
        provider = FakeProvider(name, family, reply)
        config.providers[name] = provider
        config.candidates.append(Candidate(name, family, provider.capabilities, rank, provider.model_id))
    state = start_run(config, QUESTION, store)
    finish_run(state, config, store)
    return state


def test_verdict_traces_to_its_claims_through_the_record(store):
    state = finished(store)
    path = store.run_dir(state.run_id) / "record.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    verdict = next(r for r in rows if r["kind"] == "verdict")["fields"]
    claim_nodes = {r["fields"]["node"] for r in rows if r["kind"] == "claim"}
    assert verdict["parents"] and set(verdict["parents"]) <= claim_nodes
    assert verify_records(path, state.record_head).is_intact


def test_a_forged_parent_fails_verification(store):
    state = finished(store)
    path = store.run_dir(state.run_id) / "record.jsonl"
    from orchestrator.provenance import append_record
    forged = node_hash("claim", "b" * 64, ["c" * 64])
    fields = {"node": forged, "content": "b" * 64, "parents": ["c" * 64]}
    head = append_record(path, state.record_count, "claim", fields, state.record_head)
    assert not verify_records(path, head).is_intact


def test_lineage_returns_hashes_and_never_claim_text(store):
    state = finished(store)
    claim = state.claims[0]
    rows = claim_lineage(store.run_dir(state.run_id) / "record.jsonl", claim["claim_id"])
    assert any(r["kind"] == "claim" for r in rows)
    assert claim["text"] not in json.dumps(rows)


def test_handoff_records_exactly_what_was_sent(store):
    state = RunState("2" * 16, "q", "low", "OPEN", [], {})
    state.claim_nodes["C1"] = store.add_node(state, "claim", "d" * 64)
    payload = {"role": "judge", "claims": [{"id": "C1", "text": "t"}]}
    node = record_handoff(state, store, payload)
    rows = [json.loads(line) for line in (store.run_dir(state.run_id) / "record.jsonl").read_text().splitlines()]
    assert rows[-1]["fields"]["node"] == node and rows[-1]["fields"]["claim_ids"] == ["C1"]
    assert rows[-1]["fields"]["content"] == content_hash(encode_payload(payload))
    assert rows[-1]["fields"]["parents"] == [state.claim_nodes["C1"]]


@pytest.mark.parametrize("text,label", [
    ('{"label": "supports"}', SUPPORTS), ('note {"label": "neutral"}', NEUTRAL),
    ('{"label": "maybe"}', UNCHECKED), ("no json", UNCHECKED), ("[1]", UNCHECKED),
])
def test_only_listed_labels_are_accepted(text, label):
    assert parse_label(text) == label


def entailment_setup(tmp_path, response, *families):
    config = Config(min_families=1, limits=RunLimits(token_budget=100_000), should_check_entailment=True)
    for rank, family in enumerate(families):
        provider = FakeProvider(family, family, lambda prompt: response)
        config.providers[family] = provider
        config.candidates.append(Candidate(family, family, provider.capabilities, rank, provider.model_id))
    store = RunStore(tmp_path / "runs")
    state = RunState("1" * 16, "q", "low", "OPEN", [], {"independent": 50_000, "challenge": 50_000, "judge": 50_000})
    return config, state, store, EventLog(store.run_dir(state.run_id) / "events.jsonl")


def pivotal_pair():
    return [scored("gemini", quote="exact words from the report"), scored("gemini", source="https://b.example/c", option="b", tier="WEAK")]


@pytest.mark.parametrize("response,tier,is_disputed", [
    ('{"label": "supports"}', "STRONG", False),
    ('{"label": "neutral"}', "MODERATE", False),
    ('{"label": "contradicts"}', "MODERATE", True),
    ("garbage", "MODERATE", False),
])
def test_entailment_can_only_lower_trust(tmp_path, response, tier, is_disputed):
    config, state, store, log = entailment_setup(tmp_path, response, "gemini", "openai")
    claim = check_pivotal_claims(config, state, store, pivotal_pair(), log, lambda: False)[0]
    assert claim.tier == tier and claim.is_disputed is is_disputed


def test_a_model_never_checks_its_own_family(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "supports"}', "gemini")
    claim = check_pivotal_claims(config, state, store, pivotal_pair(), log, lambda: False)[0]
    assert claim.tier == "MODERATE" and not config.providers["gemini"].calls


def test_entailment_is_off_by_default_and_spends_nothing(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "contradicts"}', "gemini", "openai")
    config.should_check_entailment = False
    claims = pivotal_pair()
    assert check_pivotal_claims(config, state, store, claims, log, lambda: False) == claims
    assert not config.providers["openai"].calls


def test_repeated_pairs_use_the_run_cache(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "supports"}', "gemini", "openai")
    claims = [scored("gemini", quote="exact words from the report"), scored("gemini", quote="exact words from the report"), scored("gemini", source="https://b.example/c", option="b", tier="WEAK")]
    check_pivotal_claims(config, state, store, claims, log, lambda: False)
    assert len(config.providers["openai"].calls) <= 1


def test_a_project_file_cannot_turn_entailment_on(tmp_path):
    path = tmp_path / "quorum.toml"
    path.write_text("[verification]\nentailment = true\n")
    with pytest.raises(ValueError):
        load(path)


def host_run(store, family_answers, **config_fields):
    """A finished run where each family gives a fixed answer."""
    config = Config(min_families=2, limits=RunLimits(token_budget=100_000), **config_fields)
    for rank, (family, text) in enumerate(family_answers.items()):
        provider = FakeProvider(family, family, lambda prompt, reply=text: reply)
        config.providers[family] = provider
        config.candidates.append(Candidate(family, family, provider.capabilities, rank, provider.model_id))
    return config, start_run(config, QUESTION, store)


def one_claim(option, source, text="Evidence favours this", quote=""):
    return json.dumps({"option": option, "claims": [{"text": text, "source": source, "quote": quote}], "would_change": "x"})


@pytest.mark.parametrize("label", ["neutral", "contradicts", "garbage"])
def test_a_checker_cannot_flip_the_verdict(tmp_path, label):
    response = "garbage" if label == "garbage" else json.dumps({"label": label})
    config, state, store, log = entailment_setup(tmp_path, response, "gemini", "openai", "checker")
    answers = [
        ("gemini", "postgres", "https://a.example/1", "postgres write throughput reached the target"),
        ("openai", "postgres", "https://b.example/2", ""),
        ("checker", "mongo", "https://c.example/3", ""),
    ]
    state.seats = [
        Seat(f"S{i}", "research", family, family, "fake", "python", "", "", 100, "unproven", "", "answered",
             {"option": option, "claims": [{"text": "Postgres write throughput reached the target", "source": source, "quote": quote}]})
        for i, (family, option, source, quote) in enumerate(answers)
    ]
    config.verified_sources = frozenset({"https://a.example/1"})
    config.limits = RunLimits(token_budget=100_000)
    brief = finish_with_quote(config, state, store, "https://a.example/1", "postgres write throughput reached the target")
    assert brief.splitlines()[0] in ("# Decision: postgres", "# Decision: UNRESOLVED")


def finish_with_quote(config, state, store, url, quote):
    import orchestrator.claim_gather as gather
    original = gather.check_sources
    snapshot = Snapshot("a" * 64, "t", 0, (("", ""),))
    gather.check_sources = lambda pairs, hosts: SourceCheck(frozenset({(url, quote)}), frozenset({url}), MappingProxyType({(url, quote): snapshot}))
    config.should_fetch_sources = True
    try:
        store.save(state)
        return finish_run(state, config, store)
    finally:
        gather.check_sources = original


def test_a_neutral_family_is_preferred_and_an_ally_never_checks(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "supports"}', "gemini", "ally", "rival", "neutral")
    claims = [
        scored("gemini", quote="exact words from the report"), scored("ally", source="https://c.example/d", tier="WEAK"),
        scored("rival", source="https://b.example/c", option="b", tier="MODERATE"),
    ]
    check_pivotal_claims(config, state, store, claims, log, lambda: False)
    assert config.providers["neutral"].calls and not config.providers["ally"].calls and not config.providers["rival"].calls


def test_a_rival_checks_when_no_neutral_family_exists(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "supports"}', "gemini", "openai")
    claims = [scored("gemini", quote="exact words from the report"), scored("openai", source="https://b.example/c", option="b", tier="WEAK")]
    check_pivotal_claims(config, state, store, claims, log, lambda: False)
    assert config.providers["openai"].calls


@pytest.mark.parametrize("text", ['{"option": "a", "claims": [{"text": "\\ud800", "source": ""}]}', '{"option": "\\ud800", "claims": [{"text": "x"}]}'])
def test_invalid_unicode_is_a_failed_answer_not_a_crash(text):
    with pytest.raises(AnswerError):
        parse_answer(text)


@pytest.mark.parametrize("source", ["https://[bad", "https://a℀b.example/x"])
def test_a_broken_url_cannot_stop_a_run(store, source):
    config, state = host_run(store, {"gemini": one_claim("postgres", source), "openai": one_claim("postgres", "https://b.example/1")})
    assert finish_run(state, config, store).startswith("# Decision:")


def test_deep_json_is_handled_in_every_parser():
    deep = "{" + '"a":[' * 200_000
    assert parse_label(deep + "]" * 200_000 + "}") == UNCHECKED


def test_a_crash_while_weighing_closes_the_run_and_keeps_the_record_valid(store, monkeypatch):
    import orchestrator.conclude as conclude
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})

    def explode(*args):
        raise LookupError("defect")

    monkeypatch.setattr(conclude, "check_pivotal_claims", explode)
    with pytest.raises(RunError, match="start a new run"):
        finish_run(state, config, store)
    saved = store.load(state.run_id)
    assert saved.status == "FAILED"
    assert verify_records(store.run_dir(state.run_id) / "record.jsonl", saved.record_head).is_intact
    with pytest.raises(RunError, match="already finished"):
        finish_run(saved, config, store)


QUOTE = "the drug reduces mortality in adults"


@pytest.mark.parametrize("page", [
    f"<p>The trial did not&nbsp;show that {QUOTE}.</p>",
    f"<p>The trial didn&#8217;t show that {QUOTE}.</p>",
    f"<p>The trial didn’t show that {QUOTE}.</p>",
    f"<h1>{QUOTE}</h1><p>The trial did not show that {QUOTE}.</p>",
    f"<p>We expected that {QUOTE}, but the measurements refuted this.</p>",
])
def test_a_negated_quote_is_caught_however_the_page_writes_it(page):
    snapshot = snapshot_quote(QUOTE, page)
    assert POLARITY_MISMATCH in support_issues("The drug reduces mortality in adults", QUOTE, snapshot.contexts)


@pytest.mark.parametrize("claim,quote,expected", [
    ("Latency is more than 5 ms", "latency is less than 5 ms", NUMBER_MISMATCH),
    ("Latency is at least 5 ms", "latency is at most 5 ms", NUMBER_MISMATCH),
    ("Coverage reached 5%", "coverage across 5 trials reached 90%", NUMBER_MISMATCH),
    ("Caching increases latency", "caching decreases latency", DIRECTION_MISMATCH),
    ("Postgres is faster here", "postgres is slower here", DIRECTION_MISMATCH),
    ("The drug works", "this is a myth that the drug works", POLARITY_MISMATCH),
])
def test_opposed_wording_is_flagged(claim, quote, expected):
    assert expected in support_issues(claim, quote)


def test_abbreviations_do_not_end_a_sentence():
    assert POLARITY_MISMATCH in support_issues("The dose works", "the dose works", (("smith et al. did not find that ", ""),))


def test_benign_not_only_is_not_negation():
    assert support_issues("Postgres improves throughput, not just average latency", "postgres improves throughput") == ()


def test_invisible_characters_cannot_hide_a_word():
    assert POLARITY_MISMATCH in support_issues("The dose works", "the dose does n​ot work")


def test_page_entities_are_decoded_before_matching():
    assert snapshot_quote("latency stayed < 5 ms", "<p>latency stayed &lt; 5 ms</p>") is not None


@pytest.mark.parametrize("variant", [
    "https://export.arxiv.org/abs/2401.00001", "https://arxiv.org/abs/2401.00001/", "https://doi.org/10.48550/arXiv.2401.00001",
    "https://www.doi.org/10.48550/arxiv.2401.00001", "https://user@arxiv.org:443/abs/2401.00001", "https://arxiv.org/%61bs/2401.00001",
    "https://arxiv.org/format/2401.00001", "arxiv:2401.00001?x=1",
])
def test_arxiv_and_doi_forms_share_a_root(variant):
    assert source_root(variant) == "arxiv:2401.00001"


@pytest.mark.parametrize("variant", [
    "https://example.org//a", "https://example.org/./a", "https://example.org/b/../a", "https://example.org/%61",
    "https://example.org./a", "https://m.example.org/a", "https://example.org/a;v=1", "https://example.org/a/",
    "https://ｅxample.org/a",
])
def test_url_spellings_share_a_root(variant):
    assert source_root(variant) == "example.org/a"


def test_doi_forms_share_a_root():
    roots = {source_root(v) for v in ["https://doi.org/10.1000/abc/", "doi:10.1000/abc", "https://doi.org/doi:10.1000/abc", "https://doi.org/10.1000%2Fabc"]}
    assert roots == {"doi:10.1000/abc"}


def test_with_checking_on_a_verdict_needs_a_reachable_source(store):
    config, state = host_run(
        store, {"gemini": one_claim("postgres", "https://invented.example/1"), "openai": one_claim("postgres", "https://invented.example/2")},
        should_fetch_sources=True, allowed_source_hosts=frozenset({"arxiv.org"}),
    )
    brief = finish_run(state, config, store)
    assert brief.startswith("# Decision: UNRESOLVED") and "could be checked" in brief


def test_a_second_claim_cannot_hide_the_first_from_review():
    first = ScoredClaim("A", "x", "https://a.example/1", "STRONG", "a", "gemini")
    second = ScoredClaim("B", "y", "https://a.example/1#2", "STRONG", "a", "gemini")
    rival = ScoredClaim("C", "z", "https://b.example/1", "WEAK", "b", "openai")
    assert {c.claim_id for c in pivotal_claims([first, second, rival])} >= {"A", "B"}


def test_a_mirror_on_one_option_cannot_take_a_rivals_sources():
    quote = "uptime reached four nines this year"
    state = state_with(
        ("gemini", {"option": "mongo", "claims": [{"text": "Uptime reached four nines", "source": "https://mirror.example/x", "quote": quote}]}),
        ("openai", {"option": "postgres", "claims": [{"text": "Uptime reached four nines", "source": URL, "quote": quote}]}),
    )
    snapshots = {("https://mirror.example/x", quote): SNAPSHOT, (URL, quote): SNAPSHOT}
    checked = SourceCheck(frozenset(snapshots), frozenset({URL}), MappingProxyType(snapshots))
    roots = {c.option: c.root for c in collect_claims(state, frozenset(), checked)}
    assert roots["postgres"] == source_root(URL)


def test_a_near_copy_quote_is_still_one_source():
    quote = "uptime reached four nines across every region this past year"
    near = "uptime reached four nines across every region this year"
    second = "https://mirror.example/copy"
    state = state_with(
        ("gemini", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": URL, "quote": quote}]}),
        ("openai", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": second, "quote": near}]}),
    )
    snapshots = {(URL, quote): SNAPSHOT, (second, near): SNAPSHOT}
    checked = SourceCheck(frozenset(snapshots), frozenset({URL, second}), MappingProxyType(snapshots))
    assert score_options(collect_claims(state, frozenset(), checked))[0].independent_sources == 1


def test_scoring_finds_the_best_pairing_of_families_and_sources():
    other = "https://other.example/b"
    claims = [scored("gemini", tier="MODERATE"), scored("gemini", source=other, tier="MODERATE"), scored("openai", tier="MODERATE")]
    assert score_options(claims)[0].score == 1.2


def test_every_seat_gets_a_share_of_source_checks():
    hostile = [{"text": "t", "source": f"https://a.example/{i}", "quote": "q"} for i in range(8)]
    state = state_with(("gemini", {"option": "a", "claims": hostile}), ("openai", {"option": "b", "claims": [{"text": "t", "source": URL, "quote": "q"}]}))
    assert (URL, "q") in source_pairs(state)[:2]


def test_sources_over_the_limit_are_reported(monkeypatch):
    monkeypatch.setattr(source_check, "fetch_page", lambda url: "the exact quoted words")
    pairs = [(f"https://arxiv.org/{i}", "the exact quoted words") for i in range(source_check.MAX_SOURCES + 3)]
    assert check_sources(pairs, frozenset({"arxiv.org"})).over_limit == 3


def test_option_text_never_reaches_the_record(store):
    secret_option = "acquire the confidential target company"
    config, state = host_run(store, {"gemini": one_claim(secret_option, "https://a.example/1"), "openai": one_claim(secret_option, "https://b.example/1")})
    finish_run(state, config, store)
    assert secret_option not in (store.run_dir(state.run_id) / "record.jsonl").read_text()


def test_a_judge_refused_for_budget_is_not_recorded_as_sent(store):
    state = RunState("3" * 16, "q", "high", "OPEN", [], {"judge": 1}, spent={})
    config = Config(min_families=1, limits=RunLimits())
    provider = FakeProvider("g", "gemini")
    config.providers["g"] = provider
    config.candidates.append(Candidate("g", "gemini", provider.capabilities, 1, provider.model_id))
    outcome = run_judge(config, state, store, [scored("gemini")], build_brief([scored("gemini")], [], []), [])
    assert outcome.summary["status"] == "refused" and not provider.calls and state.record_count == 0


def test_a_copied_claim_shows_both_options_to_the_judge():
    claims = [scored("gemini", option="a"), scored("openai", option="b")]
    claims = [replace(c, claim_id="x", text="same", source=URL) for c in claims]
    assert _judge_payload(claims)["claims"][0]["options"] == ["a", "b"]


@pytest.mark.parametrize("first,second", [("output is 5 mW", "output is 5 MW"), ("link is 10 Mb", "link is 10 MB"), ("area is 10²", "area is 102")])
def test_units_and_powers_keep_ids_apart(first, second):
    assert claim_id(Claim(text=first, source=URL)) != claim_id(Claim(text=second, source=URL))


def test_a_user_verified_source_does_not_excuse_a_failed_check():
    quote = "latency was 50 ms in the tests"
    state = state_with(("gemini", {"option": "a", "claims": [{"text": "Latency was 5 ms in the tests", "source": URL, "quote": quote}]}))
    checked = SourceCheck(frozenset({(URL, quote)}), frozenset({URL}), MappingProxyType({(URL, quote): SNAPSHOT}))
    assert collect_claims(state, frozenset({URL}), checked)[0].tier == "MODERATE"


def test_lineage_does_not_follow_a_sibling_on_the_same_page(store):
    state = RunState("4" * 16, "q", "low", "OPEN", [], {})
    source = store.add_node(state, "source_snapshot", "e" * 64)
    store.add_node(state, "claim", "a" * 64, [source], claim_id="C1")
    store.add_node(state, "claim", "b" * 64, [source], claim_id="C2")
    ids = {r["fields"].get("claim_id") for r in claim_lineage(store.run_dir(state.run_id) / "record.jsonl", "C1")}
    assert ids == {"C1", None}


def test_a_damaged_record_fails_verification_without_crashing(tmp_path):
    path = tmp_path / "record.jsonl"
    path.write_bytes(b"\xff\xfe")
    assert not verify_records(path, "0" * 64).is_intact
    path.write_text("[" * 200_000)
    assert not verify_records(path, "0" * 64).is_intact


def test_entailment_cache_separates_checker_families(tmp_path):
    config, state, store, log = entailment_setup(tmp_path, '{"label": "supports"}', "gemini", "openai")
    from orchestrator.entailment import _ask
    claim = scored("gemini", quote="exact words from the report")
    _ask(config, state, claim, config.providers["openai"])
    _ask(config, state, claim, config.providers["gemini"])
    assert len(state.entailment) == 2


def test_hostile_whitespace_cannot_stall_the_checks():
    started = time.monotonic()
    support_issues("x" + " " * 500_000 + "5", "quote text" + " " * 500_000)
    assert time.monotonic() - started < 1


@pytest.mark.parametrize("unit", ["<", "<script ", "<!--", '<a href="', "&", "&#", "<!", "<?", "</scrip", "<a ", "'"])
def test_hostile_markup_cannot_stall_page_reading(unit):
    started = time.monotonic()
    source_check.quote_on_page("any three words", unit * (500_000 // len(unit)))
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("page", [
    "<script>hidden words here</script>", "<STYLE>hidden words here</STYLE >", "<!-- hidden words here -->",
    '<a title="x>hidden words here">link</a>', "<head><title>hidden words here</title></head>", "<script>hidden words here",
])
def test_hidden_text_cannot_be_quoted(page):
    assert not source_check.quote_on_page("hidden words here", page)


def test_a_less_than_sign_in_text_is_kept():
    assert source_check.quote_on_page("when a < b holds", "<p>when a < b holds</p>")


def test_a_model_answer_over_its_cap_is_refused(store):
    long_text = "word " * 20_000
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1", long_text), "openai": one_claim("postgres", "https://b.example/1")})
    assert any(s.status == "failed" and "cap" in (s.error or "") for s in state.seats)


def test_oversized_responses_are_refused(monkeypatch):
    class Body:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b"x" * size

    class Opener:
        def open(self, request, timeout):
            return Body()

    monkeypatch.setattr(http_transport, "opener_for", lambda url: Opener())
    with pytest.raises(ValueError, match="over"):
        http_transport.post_json("https://example.org", {}, 1.0)


def test_best_assignment_handles_uneven_tables():
    assert best_assignment([[1.0, 2.0, 0.0]]) == [1]
    assert best_assignment([[1.0], [3.0]]) == [UNMATCHED, 0]
    assert best_assignment([]) == []


@pytest.mark.parametrize("source", ["arXiv", "DOI", "doi", "arxiv:", "doi:"])
def test_a_bare_scheme_word_is_only_a_label(source):
    assert isinstance(source_root(source), str)


def test_combining_mark_floods_cannot_freeze_the_process():
    started = time.monotonic()
    page = "\u0301" * 250_000 + "\u0323" * 250_000
    source_check.quote_on_page("any three words", page)
    assert time.monotonic() - started < 2


def test_accented_text_is_unchanged_by_the_combining_limit():
    assert fold_text("cafe\u0301") == "caf\u00e9"


def test_an_undecodable_entity_only_fails_its_own_quote(monkeypatch):
    monkeypatch.setattr(source_check, "fetch_page", lambda url: "&#" + "9" * 5000 + ";")
    result = check_sources([("https://arxiv.org/1", "the exact quoted words")], frozenset({"arxiv.org"}))
    assert not result.verified and result.reachable


def test_with_checking_on_a_listed_source_needs_a_quote(store, monkeypatch):
    monkeypatch.setattr(source_check, "fetch_page", lambda url: "unrelated page text here")
    listed = {"https://arxiv.org/1", "https://arxiv.org/2"}
    config, state = host_run(
        store, {"gemini": one_claim("postgres", "https://arxiv.org/1"), "openai": one_claim("postgres", "https://arxiv.org/2")},
        should_fetch_sources=True, allowed_source_hosts=frozenset({"arxiv.org"}), verified_sources=frozenset(listed),
    )
    finish_run(state, config, store)
    assert {c["tier"] for c in state.claims} == {"MODERATE"}


def test_a_bridging_quote_cannot_join_two_honest_sources():
    first = "alpha beta gamma delta epsilon zeta eta theta"
    second = "alpha beta gamma delta epsilon zeta iota kappa"
    bridge = "alpha beta gamma delta epsilon zeta eta iota"
    claim = "Alpha beta gamma delta epsilon zeta"
    answers = [("gemini", URL, first), ("openai", "https://b.example/2", second), ("xai", "https://c.example/3", bridge)]
    state = state_with(*[(f, {"option": "a", "claims": [{"text": claim, "source": s, "quote": q}]}) for f, s, q in answers])
    snapshots = {(s, q): SNAPSHOT for _, s, q in answers}
    checked = SourceCheck(frozenset(snapshots), frozenset(s for _, s, _ in answers), MappingProxyType(snapshots))
    assert score_options(collect_claims(state, frozenset(), checked))[0].independent_sources >= 2


def test_root_merging_does_not_depend_on_answer_order():
    quotes = [f"shared words one two three four five six {extra}" for extra in ("a", "b", "c")]
    rows = [(f"f{i}", f"https://s{i}.example/x", quote) for i, quote in enumerate(quotes)]
    results = set()
    for ordered in (rows, rows[::-1]):
        state = state_with(*[(f, {"option": "a", "claims": [{"text": "Shared words one two three", "source": s, "quote": q}]}) for f, s, q in ordered])
        snapshots = {(s, q): SNAPSHOT for _, s, q in rows}
        checked = SourceCheck(frozenset(snapshots), frozenset(s for _, s, _ in rows), MappingProxyType(snapshots))
        results.add(score_options(collect_claims(state, frozenset(), checked))[0].independent_sources)
    assert len(results) == 1


def test_zero_width_marks_do_not_hide_a_copied_quote():
    quote = "uptime reached four nines this year"
    state = state_with(
        ("gemini", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": URL, "quote": quote}]}),
        ("openai", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": "https://b.example/1", "quote": quote.replace("four", "fo\u200bur")}]}),
    )
    pairs = [(URL, quote), ("https://b.example/1", quote.replace("four", "fo\u200bur"))]
    snapshots = {pair: SNAPSHOT for pair in pairs}
    checked = SourceCheck(frozenset(snapshots), frozenset(p[0] for p in pairs), MappingProxyType(snapshots))
    assert score_options(collect_claims(state, frozenset(), checked))[0].independent_sources == 1


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_an_interrupt_closes_the_run_and_blocks_a_retry(store, monkeypatch, interruption):
    import orchestrator.conclude as conclude
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})

    def stop(*args):
        raise interruption

    monkeypatch.setattr(conclude, "check_pivotal_claims", stop)
    with pytest.raises(interruption):
        finish_run(state, config, store)
    saved = store.load(state.run_id)
    assert saved.status == "FAILED"
    assert verify_records(store.run_dir(state.run_id) / "record.jsonl", saved.record_head).is_intact


def test_a_killed_step_cannot_fork_the_record(store):
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    store.add_record(state, "claim", claim_id="written-before-the-kill")
    stale = store.load(state.run_id)
    with pytest.raises(StateIntegrityError):
        finish_run(stale, config, store)


def test_a_surrogate_from_a_provider_fails_nothing_else(store):
    config = Config(min_families=1, limits=RunLimits(token_budget=100_000))
    provider = FakeProvider("g", "gemini", lambda prompt: '{"option": "\ud800", "claims": []}\ud800')
    config.providers["g"] = provider
    config.candidates.append(Candidate("g", "gemini", provider.capabilities, 1, provider.model_id))
    state = start_run(config, QUESTION, store)
    assert state.seats[0].status == "failed"


def test_deep_answers_are_refused_before_they_reach_state():
    deep = '{"option": "a", "claims": [{"text": "x", "n": ' + "[" * 495 + "]" * 495 + "}]}"
    with pytest.raises(AnswerError):
        parse_answer(deep)


def test_every_pivotal_claim_reaches_the_challenger():
    claims = [scored("gemini", source=f"https://a.example/{i}") for i in range(16)]
    claims = [replace(c, claim_id=str(i), text=f"claim number {i}") for i, c in enumerate(claims)]
    assert len(challenge_payload(claims)["claims"]) == 16


def test_document_count_is_about_documents():
    three = [scored("gemini", source=f"https://a.example/{i}") for i in range(3)]
    top = score_options(three)[0]
    assert top.independent_sources == 3 and top.score == 1.0
    assert score_options([scored("gemini", source=""), scored("openai", source="")])[0].independent_sources == 0


@pytest.mark.parametrize("page,quote", [
    ("<head><title>t</title><body>visible words are here</body>", "visible words are here"),
    ("<a href=it's>visible words are here</a>", "visible words are here"),
    ("<!-->visible words are here", "visible words are here"),
    ("<head-line>visible words are here</head-line>", "visible words are here"),
    ("<style-guide>visible words are here</style-guide>", "visible words are here"),
])
def test_visible_text_is_not_hidden_by_odd_markup(page, quote):
    assert source_check.quote_on_page(quote, page)


def test_a_version_number_is_not_a_spelling_variant():
    assert not same_option("mysql", "mysql8") and same_option("postgres", "postgresql")


def test_a_broken_task_tracker_cannot_undo_a_finished_run(store):
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    (store.root / "tasks.json").write_text("not json")
    finish_run(state, config, store)
    assert store.load(state.run_id).status == "DONE"


def test_a_stop_during_the_judge_gives_no_verdict(store, monkeypatch):
    import orchestrator.conclude as conclude
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    monkeypatch.setattr(conclude, "_apply_judge", lambda *args: store.request_cancel(state.run_id))
    with pytest.raises(RunError, match="stopped"):
        finish_run(state, config, store)


def test_a_challenge_cut_short_by_budget_withholds_the_verdict(store):
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    state.is_challenge_incomplete = True
    assert finish_run(state, config, store).startswith("# Decision: UNRESOLVED")


def test_verify_gives_up_when_the_run_stays_busy(store):
    state = RunState("5" * 16, "q", "low", "OPEN", [], {})
    store.save(state)
    with store.locked(state.run_id), pytest.raises(TimeoutError), store.locked(state.run_id, wait_s=0.2):
        pytest.fail("the lock should not be acquired")


@pytest.mark.parametrize("mark", ["\u0f73", "\u0f75", "\u0f81", "\uff9e\u0301", "\u0344"])
def test_characters_that_decompose_to_marks_cannot_freeze_the_process(mark):
    started = time.monotonic()
    fold_text(mark * (160_000 // len(mark)))
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("text", ["caf\u00e9 \u00e9\u00e9\u00e9", "\u0dbb\u0dd4", "\u0915\u094d\u0937", "\u1ec7\u1ec7\u1ec7"])
def test_honest_accented_text_keeps_its_letters(text):
    assert fold_text(text) == unicodedata.normalize("NFKC", text)


def test_a_second_claim_cannot_revive_a_mirror():
    quote = "uptime reached four nines this year"
    mirror = "https://mirror.example/copy"
    state = state_with(
        ("gemini", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": URL, "quote": quote}]}),
        ("openai", {"option": "a", "claims": [{"text": "Uptime reached four nines", "source": mirror, "quote": quote}, {"text": "Other point", "source": mirror}]}),
    )
    snapshots = {(URL, quote): SNAPSHOT, (mirror, quote): SNAPSHOT}
    checked = SourceCheck(frozenset(snapshots), frozenset({URL, mirror}), MappingProxyType(snapshots))
    assert score_options(collect_claims(state, frozenset(), checked))[0].independent_sources == 1


def test_host_challenge_gets_all_claims_while_tiers_can_still_change(store):
    listed = "https://arxiv.org/listed"
    config, state = host_run(
        store, {"gemini": one_claim("postgres", listed), "openai": one_claim("mysql", "https://arxiv.org/other")},
        should_fetch_sources=True, allowed_source_hosts=frozenset({"arxiv.org"}), verified_sources=frozenset({listed}),
    )
    assert issue_host_challenge(state, config).count('"id"') == 2


def test_a_killed_run_refuses_a_host_challenge(store):
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    store.add_record(state, "claim", claim_id="written-before-the-kill")
    with pytest.raises(StateIntegrityError):
        record_host_challenge(store.load(state.run_id), config, store, "{}")


def test_no_fetch_starts_after_the_deadline(monkeypatch):
    calls = []

    def slow(url):
        calls.append(url)
        time.sleep(0.3)
        return "x"

    monkeypatch.setattr(source_check, "OVERALL_DEADLINE_S", 0.05)
    monkeypatch.setattr(source_check, "fetch_page", slow)
    check_sources([(f"https://arxiv.org/{i}", "the exact quoted words") for i in range(12)], frozenset({"arxiv.org"}))
    started = len(calls)
    time.sleep(0.5)
    assert len(calls) == started


@pytest.mark.parametrize("page", [
    '<head><script>var t="<body>internal template plumbing words";</script></head>',
    "<head><!-- <body> internal template plumbing words --></head>",
    "<head><style>a::before{content:'<body>internal template plumbing words'}</style></head>",
])
def test_body_text_inside_head_plumbing_stays_hidden(page):
    assert not source_check.quote_on_page("internal template plumbing words", page)


@pytest.mark.parametrize("content", ["[1]", "null", '[{"x": 1}]'])
def test_a_corrupt_task_list_cannot_lose_the_brief(store, content):
    config, state = host_run(store, {"gemini": one_claim("postgres", "https://a.example/1"), "openai": one_claim("postgres", "https://b.example/1")})
    (store.root / "tasks.json").write_text(content)
    assert finish_run(state, config, store).startswith("# Decision:")


def test_an_answer_slightly_over_the_estimate_is_kept(store):
    config, state = host_run(store, {
        "gemini": one_claim("postgres", "https://a.example/1", "x" * 8_400),
        "openai": one_claim("postgres", "https://b.example/1"),
    })
    assert all(s.status == "answered" for s in state.seats)
