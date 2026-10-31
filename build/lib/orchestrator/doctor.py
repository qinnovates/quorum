"""Setup check. It reports status and fixes, and never prints a secret value."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .config import Config
from .providers import (
    UNATTRIBUTED_FAMILIES, CliProvider, OllamaProvider, OpenAICompatibleProvider, safe_complete,
)
from .secrets import SecretUnavailable

CANARY_PROMPT = "Reply with the single word ok."
CANARY_OUTPUT_TOKENS = 16
MIN_PYTHON = (3, 11)
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class Check:
    name: str
    is_ok: bool
    detail: str


def remote_providers(config: Config) -> list[str]:
    """Providers that send content off this machine, so consent applies."""
    def stays_local(provider: object) -> bool:
        return isinstance(provider, OllamaProvider) and urlsplit(provider.base_url).hostname in LOOPBACK_HOSTS

    return sorted(name for name, provider in config.providers.items() if not stays_local(provider))


def _check_provider(name: str, provider: object) -> Check:
    if isinstance(provider, CliProvider) and shutil.which(provider.command[0]) is None:
        return Check(name, False, f"{provider.command[0]} is not installed")
    if isinstance(provider, OpenAICompatibleProvider) and provider.api_key is not None:
        try:
            provider.api_key.reveal()
        except SecretUnavailable as exc:
            return Check(name, False, str(exc))
        return Check(name, True, f"key reference resolves ({provider.api_key.reference})")
    if isinstance(provider, CliProvider):
        return Check(name, True, "installed; run `quorum-run doctor --live --allow-provider " + name + "` to confirm sign-in")
    return Check(name, True, f"configured as family {provider.family}")


def _check_live(name: str, provider: object) -> Check:
    result = safe_complete(provider, CANARY_PROMPT, CANARY_OUTPUT_TOKENS)
    if result.ok:
        return Check(f"{name} live", True, "answered")
    return Check(f"{name} live", False, f"{result.error}. Log in or check the endpoint, then retry")


def _check_floor(config: Config) -> Check:
    families = {
        p.family for name, p in config.providers.items()
        if p.family not in UNATTRIBUTED_FAMILIES and name != config.pm_provider
    }
    needed_external = config.min_families - 1
    is_ok = len(families) >= needed_external
    detail = (
        f"{len(families)} extra model families; your Claude Code model adds one more; floor is {config.min_families}"
        if is_ok else "not enough model families for your floor: add a provider and set its family"
    )
    return Check("diversity", is_ok, detail)


def run_doctor(config: Config, *, live: bool = False, project_root: Path | None = None) -> list[Check]:
    checks = [Check("python", sys.version_info >= MIN_PYTHON, f"running {sys.version_info.major}.{sys.version_info.minor}, needs 3.11 or newer"), _check_floor(config)]
    checks += [_check_provider(name, p) for name, p in config.providers.items()]
    if live:
        checks += [_check_live(name, p) for name, p in config.providers.items()]
    ignore = (project_root or Path.cwd()) / ".gitignore"
    is_ignored = ignore.exists() and "_swarm" in ignore.read_text(encoding="utf-8")
    checks.append(Check("gitignore", is_ignored, "_swarm/ is ignored" if is_ignored else "add _swarm/ and quorum.toml to .gitignore in this project"))
    return checks
