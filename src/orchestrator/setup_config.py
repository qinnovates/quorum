"""First-run setup: find the user's tools and write a keyless config."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

OLLAMA_LIST_TIMEOUT_S = 5.0
# Model name prefixes and who trained them. Unknown names stay unattributed.
OLLAMA_FAMILIES = {
    "llama": "meta", "codellama": "meta", "mistral": "mistral", "mixtral": "mistral",
    "qwen": "alibaba", "deepseek": "deepseek", "gemma": "gemini", "phi": "other",
}
CONFIG_HEADER = """# Created by quorum-run setup. This file holds no keys, and must never hold one.
# Keep keys in a vault you own. See the README section on your API safety.
"""


TEMPLATE_INTRO = """
# ---------------------------------------------------------------------------
# ADD ANOTHER MODEL
# Each block below is a placeholder. To use one:
#   1. Follow its steps.
#   2. Remove the # from its lines, and replace everything in <angle brackets>.
#   3. Run: quorum-run doctor
# Different families mean more independent reviews. `family` is who trained the
# model: claude, gemini, openai, meta, mistral, deepseek, alibaba or xai.
# Never paste a key here. Keys stay in your vault.
# ---------------------------------------------------------------------------
"""
GEMINI_TEMPLATE = """
# GEMINI CLI. Steps: install the Gemini CLI, run `gemini`, sign in, then exit.
# [providers.gemini]
# type = "gemini_cli"
# model = "default"
# command = ["gemini", "--skip-trust", "--approval-mode", "plan", "-p", "Follow the instructions in the input."]
# rank = 5
# strength = 5
"""
CODEX_TEMPLATE = """
# CODEX CLI. Steps: install the Codex CLI, then run `codex login`.
# [providers.codex]
# type = "codex_cli"
# model = "default"
# command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"]
# rank = 5
# strength = 5
"""
OLLAMA_TEMPLATE = """
# LOCAL MODEL WITH OLLAMA. Free, and prompts stay on your computer.
# Steps: install Ollama, run `ollama pull <model>`, and keep Ollama running.
# [providers.local]
# type = "ollama"
# model = "<model-from-ollama-list>"
# family = "<who-trained-it>"
# rank = 1
# strength = 1
"""
API_TEMPLATE = """
# HOSTED OR SELF-HOSTED API (any OpenAI-compatible endpoint).
# Steps: create a dedicated key with a spending limit, store it in your vault,
# then choose ONE key line below. HTTPS is required for remote endpoints.
# HashiCorp Vault, AWS, Google Cloud, Azure, Kubernetes, Docker, 1Password and more
# have copy-ready templates at:
# https://github.com/qinnovates/quorum/blob/main/docs/INTEGRATIONS.md
# [providers.<short-name>]
# type = "openai_compatible"
# model = "<model-id>"
# base_url = "https://<your-endpoint>/v1"
# family = "<who-trained-it>"
# api_key_cmd = ["security", "find-generic-password", "-s", "quorum/<short-name>", "-w"]
# api_key_env = "QUORUM_<SHORT_NAME>_KEY"
# rank = 3
# strength = 3
"""
ROUTING_TEMPLATE = """
# OPTIONAL: PROVE WHICH MODEL IS BEST AT WHAT.
# Roles: intent, architecture, code, research, routing, judge, challenger.
# Without evidence, a model is marked unproven.
# [role_bars]
# code = 0.7
#
# [[evidence]]
# model_id = "<model-id>"
# role = "code"
# metric = "<what-you-measured>"
# score = 0.8
# source = "https://<where-you-measured-it>"
# measured_on = "<YYYY-MM-DD>"
# is_verified = true
#
# OPTIONAL: CHECK THAT CITED SOURCES EXIST.
# Only the hosts you list are contacted, because a model can hide data in a URL.
# [verification]
# fetch_sources = true
# allowed_hosts = ["arxiv.org", "<a-site-you-trust>"]
# Optional: a different model family checks that quotes support verdict-flipping claims.
# entailment = true
"""


@dataclass
class DetectedTools:
    has_gemini: bool = False
    has_codex: bool = False
    ollama_models: list[str] = field(default_factory=list)


def _list_ollama_models() -> list[str]:
    if shutil.which("ollama") is None:
        return []
    try:
        proc = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=OLLAMA_LIST_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = proc.stdout.splitlines()[1:] if proc.returncode == 0 else []
    return [row.split()[0] for row in rows if row.strip()]


def detect_tools() -> DetectedTools:
    return DetectedTools(
        has_gemini=shutil.which("gemini") is not None,
        has_codex=shutil.which("codex") is not None,
        ollama_models=_list_ollama_models(),
    )


def ollama_family(model: str) -> str:
    return next((f for prefix, f in OLLAMA_FAMILIES.items() if model.lower().startswith(prefix)), "other")


def _provider_blocks(tools: DetectedTools) -> list[str]:
    blocks = []
    if tools.has_gemini:
        blocks.append(
            '[providers.gemini]\ntype = "gemini_cli"\nmodel = "default"\n'
            'command = ["gemini", "--skip-trust", "--approval-mode", "plan", "-p", "Follow the instructions in the input."]\n'
            "rank = 5\nstrength = 5\n"
        )
    if tools.has_codex:
        blocks.append(
            '[providers.codex]\ntype = "codex_cli"\nmodel = "default"\n'
            'command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-"]\n'
            "rank = 5\nstrength = 5\n"
        )
    if tools.ollama_models:
        model = tools.ollama_models[0]
        blocks.append(
            f'[providers.local]\ntype = "ollama"\nmodel = "{model}"\n'
            f'family = "{ollama_family(model)}"\nrank = 1\nstrength = 1\n'
        )
    return blocks


def _templates(tools: DetectedTools) -> str:
    """Placeholders for whatever this person has not connected yet."""
    missing = [
        template for template, is_present in (
            (GEMINI_TEMPLATE, tools.has_gemini),
            (CODEX_TEMPLATE, tools.has_codex),
            (OLLAMA_TEMPLATE, bool(tools.ollama_models)),
        ) if not is_present
    ]
    return "".join([TEMPLATE_INTRO, *missing, API_TEMPLATE, ROUTING_TEMPLATE])


def build_config(tools: DetectedTools) -> str:
    blocks = _provider_blocks(tools)
    has_attributed_local = bool(tools.ollama_models) and ollama_family(tools.ollama_models[0]) != "other"
    floor = 2 if tools.has_gemini or tools.has_codex or has_attributed_local else 1
    return "\n".join([
        CONFIG_HEADER,
        f"[panel]\nmin_families = {floor}\n",
        "[limits]\ntoken_budget = 200000\nmax_agents = 8\nmax_output_tokens = 2000\n",
        *blocks,
        _templates(tools),
    ])


def _next_steps(tools: DetectedTools) -> list[str]:
    steps = []
    if tools.has_gemini:
        steps.append("Sign in to Gemini: run `gemini`, finish sign-in, then exit.")
    if tools.has_codex:
        steps.append("Sign in to Codex: run `codex login`.")
    if not (tools.has_gemini or tools.has_codex or tools.ollama_models):
        steps.append("No other models were found, so /quorum uses your Claude Code model only.")
        steps.append("For a more independent panel, install Gemini CLI, Codex CLI or Ollama, then run `quorum-run setup --force`.")
    if tools.ollama_models and ollama_family(tools.ollama_models[0]) == "other":
        steps.append("Set `family` for your local model in the config, so it counts as a separate family.")
    steps.append("Check your setup: run `quorum-run doctor`.")
    steps.append('Open a project, run `claude`, then type: /quorum "your question"')
    return steps


def _backup_path(path: Path) -> Path:
    """Never overwrite an earlier backup."""
    candidate = path.with_suffix(".toml.previous")
    number = 1
    while candidate.exists():
        number += 1
        candidate = path.with_suffix(f".toml.previous{number}")
    return candidate


def write_user_config(path: Path, tools: DetectedTools, *, force: bool = False) -> str:
    """Write the config once. An existing file is kept unless `force` is set."""
    if path.exists() and not force:
        status = f"Kept your existing config at {path}."
    else:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists():
            path.replace(_backup_path(path))
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(build_config(tools))
        status = f"Wrote your config to {path}. It holds no keys."
    found = [n for n, has in (("Gemini CLI", tools.has_gemini), ("Codex CLI", tools.has_codex), ("Ollama", bool(tools.ollama_models))) if has]
    steps = "\n".join(f"  {i}. {step}" for i, step in enumerate(_next_steps(tools), 1))
    return f"{status}\nFound: {', '.join(found) or 'no extra models'}.\n\nNext:\n{steps}"
