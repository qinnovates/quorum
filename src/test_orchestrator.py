"""Unit tests for the BYOAI orchestrator. No network: providers are stubbed."""

import subprocess
from pathlib import Path

import pytest

from quorum_scorer import Claim
from orchestrator.config import load
from orchestrator.diversity import DiversityError, enforce_family_floor, family_report
from orchestrator.handoff import (
    build_handoff,
    dedupe_claims,
    full_pool_bytes,
    payload_bytes,
    pool_stats,
)
from orchestrator.ledger import Ledger, Price
from orchestrator.limits import RunBudget, RunLimits, SpawnRefused
from orchestrator.providers import (
    CliProvider,
    FakeProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    Result,
)
from orchestrator.router import (
    Candidate,
    EscalationSignals,
    NoRoute,
    choose,
    escalate,
    escalation_reasons,
)


def ok(family, model="m", tokens_in=10, tokens_out=5):
    return Result(text="x", family=family, model_id=model, tokens_in=tokens_in, tokens_out=tokens_out)


def failed(family, model="m"):
    return Result(text="", family=family, model_id=model, ok=False, error="boom")


# --- R1: family-diversity guard ----------------------------------------------

class TestDiversity:
    def test_all_claude_panel_fails_loudly(self):
        results = [ok("claude") for _ in range(5)]
        with pytest.raises(DiversityError) as exc:
            enforce_family_floor(results, min_families=2)
        assert "FAILED_DIVERSITY" in str(exc.value)
        assert exc.value.report.answered == {"claude"}

    def test_floor_met_passes(self):
        report = enforce_family_floor([ok("claude"), ok("gemini")], min_families=2)
        assert report.passed
        assert report.answered == {"claude", "gemini"}

    def test_failed_panelists_do_not_count_toward_floor(self):
        results = [ok("claude"), failed("gemini", model="gemini-2.5-pro")]
        with pytest.raises(DiversityError):
            enforce_family_floor(results, min_families=2)
        report = family_report(results, min_families=2)
        assert report.failed == ("gemini:gemini-2.5-pro",)

    def test_no_external_family_is_a_hard_failure_at_floor_three(self):
        results = [ok("claude"), ok("claude"), ok("gemini", model="g"), failed("openai")]
        report = family_report(results, min_families=3)
        assert not report.passed


# --- R4: token ledger ---------------------------------------------------------

class TestLedger:
    def test_cost_uses_configured_price_per_million_tokens(self):
        ledger = Ledger(pricing={"m": Price(input_per_mtok=3.0, output_per_mtok=15.0)})
        entry = ledger.record("phase1", ok("claude", model="m", tokens_in=1_000_000, tokens_out=100_000))
        assert entry.cost_usd == pytest.approx(3.0 + 1.5)

    def test_unpriced_model_reports_none_not_a_guess(self):
        ledger = Ledger()
        ledger.record("phase1", ok("gemini", model="gemini-x"))
        assert ledger.by_model()["gemini-x"]["cost_usd"] is None
        assert ledger.unpriced_models() == ["gemini-x"]

    def test_totals_by_model(self):
        ledger = Ledger(pricing={"a": Price(1.0, 1.0)})
        ledger.record("p1", ok("claude", model="a", tokens_in=10, tokens_out=10))
        ledger.record("p2", ok("claude", model="a", tokens_in=10, tokens_out=10))
        row = ledger.by_model()["a"]
        assert row["calls"] == 2
        assert row["tokens"] == 40
        assert ledger.total_tokens() == 40


# --- R5: subagent spawn limits ------------------------------------------------

class TestLimits:
    def test_max_agents_refusal_is_recorded_with_reason(self):
        budget = RunBudget(RunLimits(max_agents=2))
        budget.authorize_spawn(depth=1, estimated_tokens=10)
        budget.authorize_spawn(depth=1, estimated_tokens=10)
        with pytest.raises(SpawnRefused) as exc:
            budget.authorize_spawn(depth=1, estimated_tokens=10)
        assert "max_agents=2" in exc.value.reason
        assert budget.refusals == [exc.value.reason]
        assert budget.agents_spawned == 2

    def test_depth_limit(self):
        budget = RunBudget(RunLimits(max_depth=2))
        with pytest.raises(SpawnRefused, match="max_depth"):
            budget.authorize_spawn(depth=3, estimated_tokens=1)

    def test_spawn_refused_when_estimate_exceeds_remaining_budget(self):
        budget = RunBudget(RunLimits(token_budget=100))
        budget.charge(90)
        with pytest.raises(SpawnRefused, match="remaining budget 10"):
            budget.authorize_spawn(depth=1, estimated_tokens=50)

    def test_output_cap_clamped_by_per_agent_and_remaining_budget(self):
        budget = RunBudget(RunLimits(token_budget=500, max_output_tokens=200))
        assert budget.clamp_output(1000) == 200
        budget.charge(480)
        assert budget.clamp_output(1000) == 20

    def test_exhausted_after_full_charge(self):
        budget = RunBudget(RunLimits(token_budget=10))
        budget.charge(10)
        assert budget.exhausted()


# --- R2: handoff payloads -----------------------------------------------------

def claim(text, source="s", tier="MODERATE", relevance=1.0):
    return Claim(text=text, source=source, source_tier=tier, relevance=relevance)


class TestHandoff:
    def test_dedupe_by_normalized_text_and_source(self):
        pool = [
            claim("Neural data leaks via EEG.", source="A"),
            claim("neural data leaks via EEG", source="A"),
            claim("Neural data leaks via EEG", source="B"),
        ]
        unique = dedupe_claims(pool)
        assert len(unique) == 2
        assert [c.source for c in unique] == ["A", "B"]

    def test_payload_caps_claims_and_orders_strongest_first(self):
        pool = [claim(f"weak {i}", tier="WEAK") for i in range(20)]
        pool.append(claim("the strong one", tier="STRONG"))
        payload = build_handoff(pool, "devils_advocate", open_questions=[], debate_summary="", max_claims=5)
        assert len(payload["claims"]) == 5
        assert payload["claims"][0]["tier"] == "STRONG"
        assert payload["omitted_claims"] == 16

    def test_claim_id_survives_pool_change(self):
        target = claim("b", source="2")
        first = build_handoff([target], "r", open_questions=[], debate_summary="")
        second = build_handoff(
            [claim("new", source="9"), target], "r", open_questions=[], debate_summary=""
        )
        ids = {c["text"]: c["id"] for c in second["claims"]}
        assert ids["b"] == first["claims"][0]["id"]
        assert len(set(ids.values())) == 2

    def test_dedupe_keeps_strongest_tier(self):
        pool = [claim("same", tier="WEAK"), claim("same", tier="STRONG")]
        assert [c.source_tier for c in dedupe_claims(pool)] == ["STRONG"]

    def test_payload_smaller_than_full_pool_on_large_pool(self):
        pool = [claim(f"finding number {i} with some detail text", source=f"src{i}") for i in range(60)]
        payload = build_handoff(pool, "analysis", open_questions=["q1"], debate_summary="short", max_claims=12)
        assert payload_bytes(payload) < full_pool_bytes(pool)

    def test_summary_and_text_are_capped(self):
        long = "x" * 1000
        payload = build_handoff([claim(long)], "r", open_questions=[], debate_summary=long)
        assert len(payload["claims"][0]["text"]) == 240
        assert len(payload["debate_summary"]) == 400

    def test_pool_stats_reports_raw_and_unique(self):
        pool = [claim("a", source="1"), claim("a", source="1")]
        stats = pool_stats(pool)
        assert (stats.raw_claims, stats.unique_claims) == (2, 1)


# --- R6: routing and escalation ----------------------------------------------

CANDIDATES = [
    Candidate("ollama", "ollama", frozenset({"json_schema"}), rank=1),
    Candidate("gemini", "gemini", frozenset({"web", "json_schema"}), rank=5),
    Candidate("claude", "claude", frozenset({"web", "json_schema", "tool_use"}), rank=9),
]


class TestRouter:
    def test_cheapest_with_needed_capability(self):
        assert choose(CANDIDATES, frozenset({"json_schema"})).name == "ollama"

    def test_capability_filters_out_cheap_option(self):
        assert choose(CANDIDATES, frozenset({"web"})).name == "gemini"

    def test_family_filter(self):
        assert choose(CANDIDATES, frozenset({"json_schema"}), family="claude").name == "claude"

    def test_no_route_raises(self):
        with pytest.raises(NoRoute):
            choose(CANDIDATES, frozenset({"tool_use"}), family="gemini")

    def test_no_escalation_when_no_trigger_fires(self):
        assert escalation_reasons(EscalationSignals()) == []

    def test_contradiction_and_ratify_fire(self):
        reasons = escalation_reasons(EscalationSignals(contradiction=True, ratify=True))
        assert len(reasons) == 2

    def test_confidence_trigger_disabled_without_configured_floor(self):
        sig = EscalationSignals(verdict_confidence=0.1, confidence_floor=None)
        assert escalation_reasons(sig) == []

    def test_confidence_trigger_fires_below_floor(self):
        sig = EscalationSignals(verdict_confidence=0.4, confidence_floor=0.6)
        assert len(escalation_reasons(sig)) == 1

    def test_escalate_picks_strongest(self):
        assert escalate(CANDIDATES, frozenset({"json_schema"})).name == "claude"


# --- Providers (offline stubs) ------------------------------------------------

class TestProviders:
    def test_fake_provider_reports_family(self):
        res = FakeProvider("f", "gemini").complete("hello world", max_output_tokens=50)
        assert res.family == "gemini" and res.ok

    def test_cli_prompt_goes_over_stdin_never_argv(self):
        seen = {}

        def runner(argv, **kwargs):
            seen.update(argv=argv, **kwargs)
            return subprocess.CompletedProcess(argv, 0, stdout=" answer \n", stderr="")

        p = CliProvider("g", "gemini", ["gemini", "-p", "go"], "m", runner=runner)
        res = p.complete("CANARY-PROMPT", max_output_tokens=10)
        assert seen["input"] == "CANARY-PROMPT"
        assert "CANARY-PROMPT" not in " ".join(seen["argv"])
        assert res.ok and res.text == "answer"

    def test_cli_nonzero_exit_is_recorded_not_raised(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="auth failed")

        p = CliProvider("g", "gemini", ["gemini"], "m", runner=runner)
        res = p.complete("Q", max_output_tokens=10)
        assert not res.ok and "auth failed" in res.error

    def test_cli_timeout_is_recorded_not_raised(self):
        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 1)

        p = CliProvider("g", "gemini", ["gemini"], "m", runner=runner)
        assert not p.complete("Q", max_output_tokens=10).ok

    def test_ollama_parses_response_and_counts_tokens(self):
        def transport(url, body, timeout):
            assert url.endswith("/api/chat") and body["stream"] is False
            return {"message": {"content": "{\"ok\": true}"}, "prompt_eval_count": 7, "eval_count": 3}

        p = OllamaProvider("pm", "qwen-local", transport=transport)
        res = p.complete("route this", max_output_tokens=100, output_schema={"type": "object"})
        assert res.family == "ollama" and res.tokens_in == 7 and res.tokens_out == 3

    def test_ollama_transport_error_is_recorded(self):
        def transport(url, body, timeout):
            raise ConnectionError("no server on 11434")

        res = OllamaProvider("pm", "m", transport=transport).complete("x", max_output_tokens=5)
        assert not res.ok and "11434" in res.error

    def test_openai_compatible_family_is_user_declared(self):
        def transport(url, body, timeout, headers):
            return {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 2, "completion_tokens": 1}}

        p = OpenAICompatibleProvider("byo", "my-model", "http://x/v1", family="other", transport=transport)
        res = p.complete("hi", max_output_tokens=5)
        assert res.family == "other" and res.text == "hi" and res.tokens_out == 1


# --- Config -------------------------------------------------------------------

CONFIG_TOML = """
[panel]
min_families = 2

[limits]
token_budget = 1000
max_agents = 4
max_depth = 2
max_output_tokens = 300

[pricing."gemini-2.5-pro"]
input_per_mtok = 1.25
output_per_mtok = 10.0

[providers.pm]
type = "ollama"
model = "local-model"
rank = 1
capabilities = ["json_schema"]

[providers.gemini]
type = "gemini_cli"
model = "gemini-2.5-pro"
command = ["gemini", "-p", "go"]
rank = 5
"""


class TestConfig:
    @pytest.fixture(autouse=True)
    def installed_binaries(self, monkeypatch):
        monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")

    def test_example_config_loads_and_leaves_unset_values_unset(self):
        example = Path(__file__).resolve().parent.parent / "docs" / "quorum.example.toml"
        cfg = load(example)
        assert cfg.min_families == 2
        assert cfg.confidence_floor is None
        assert cfg.pricing == {}

    def test_loads_providers_limits_and_pricing(self, tmp_path):
        path = tmp_path / "quorum.toml"
        path.write_text(CONFIG_TOML, encoding="utf-8")
        cfg = load(path)
        assert cfg.min_families == 2
        assert cfg.limits.max_agents == 4
        assert cfg.pricing["gemini-2.5-pro"].output_per_mtok == 10.0
        assert cfg.confidence_floor is None
        assert {c.name for c in cfg.candidates} == {"pm", "gemini"}
        assert cfg.providers["gemini"].family == "gemini"

    def test_rejects_zero_min_families(self, tmp_path):
        path = tmp_path / "quorum.toml"
        path.write_text("[panel]\nmin_families = 0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="min_families"):
            load(path)

    def test_rejects_unknown_provider_type(self, tmp_path):
        path = tmp_path / "quorum.toml"
        path.write_text('[providers.x]\ntype = "mystery"\nmodel = "m"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="unknown provider type"):
            load(path)


# --- Regressions from the integration review ---------------------------------

class TestRegressions:
    @pytest.mark.parametrize("family", ["ollama", "other"])
    def test_unattributed_family_cannot_satisfy_floor(self, family):
        with pytest.raises(DiversityError):
            enforce_family_floor([ok("claude"), ok(family)], min_families=2)

    def test_cli_empty_stdout_is_a_failure(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="  \n", stderr="")

        res = CliProvider("g", "gemini", ["gemini"], "m", runner=runner).complete("Q", max_output_tokens=5)
        assert not res.ok and "empty" in res.error

    def test_ollama_null_content_is_a_failure(self):
        p = OllamaProvider("pm", "m", transport=lambda *a: {"message": {"content": None}})
        assert not p.complete("x", max_output_tokens=5).ok

    @pytest.mark.parametrize("body", [
        {"error": "bad"},
        {"choices": []},
        {"choices": [{"message": {"content": None}}]},
    ])
    def test_openai_bad_body_is_a_failure_not_a_crash(self, body):
        p = OpenAICompatibleProvider("b", "m", "http://x/v1", transport=lambda *a: body)
        assert not p.complete("x", max_output_tokens=5).ok

    def test_cli_usage_is_estimated_charged_and_never_priced(self):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout="a" * 40, stderr="")

        res = CliProvider("g", "gemini", ["gemini"], "m", runner=runner).complete("Q" * 40, max_output_tokens=50)
        assert not res.usage_known and res.tokens_in == 10 and res.tokens_out == 10
        ledger = Ledger(pricing={"m": Price(1.0, 1.0)})
        assert ledger.record("p1", res).cost_usd is None
        assert ledger.by_model()["m"]["cost_usd"] is None
        assert ledger.estimated_usage_models() == ["m"]
        assert ledger.unpriced_models() == []

    def test_clamp_output_refuses_when_budget_is_gone(self):
        budget = RunBudget(RunLimits(token_budget=10))
        budget.charge(10)
        with pytest.raises(SpawnRefused, match="exhausted"):
            budget.clamp_output(100)

    def test_config_rejects_unknown_family(self, tmp_path):
        path = tmp_path / "quorum.toml"
        path.write_text('[providers.x]\ntype = "ollama"\nmodel = "m"\nfamily = "claudee"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="unknown family"):
            load(path)

    def test_min_families_defaults_to_two(self, tmp_path):
        path = tmp_path / "quorum.toml"
        path.write_text("", encoding="utf-8")
        assert load(path).min_families == 2
