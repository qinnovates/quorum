"""Setup check. It reports status and fixes, and never prints a secret value."""

from __future__ import annotations

import re
import shutil
import stat
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
GUIDE_URL = "https://github.com/qinnovates/quorum/blob/main/docs/INTEGRATIONS.md"
PLAINTEXT_LOGIN_FILES = {
    "codex": (".codex/auth.json", f'set cli_auth_credentials_store = "keyring" in ~/.codex/config.toml, then sign in again. See {GUIDE_URL}'),
    "gemini": (".gemini/oauth_creds.json", f"keep it private and check Gemini CLI's docs for keychain storage. See {GUIDE_URL}"),
}
MODEL_HINT = (
    'This model is not available to this account or endpoint. Use model = "default" for a CLI tool, '
    "remove any model pin in the tool's own config, or choose a current model"
)
_MODEL_ERROR = re.compile(r"(?i)\bmodel\b.{0,80}(not supported|not found|unknown|does not exist|unavailable|no access)")
_AUTH_ERROR = re.compile(r"(?i)log ?in|sign ?in|unauthori[sz]ed|\b401\b|\b403\b|authenticat|refresh token|expired")


@dataclass(frozen=True)
class Check:
    name: str
    is_ok: bool
    detail: str
    is_advisory: bool = False


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


def _check_login_storage(name: str, provider: object, home: Path) -> Check | None:
    """Look only at a login file's existence and mode. Its contents are never read."""
    if not isinstance(provider, CliProvider) or provider.command[0] not in PLAINTEXT_LOGIN_FILES:
        return None
    relative_path, advice = PLAINTEXT_LOGIN_FILES[provider.command[0]]
    login_file = home / relative_path
    try:
        mode = login_file.stat().st_mode
    except OSError:  # no file means nothing to report, and an unreadable folder is not a setup fault
        return None
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        detail = f"{login_file.name} is open to other users; run chmod 600 on it, then sign in again"
        return Check(f"{name} login storage", False, detail)
    return Check(f"{name} login storage", True, f"kept in a plaintext file; {advice}", is_advisory=True)


def _live_hint(error: str) -> str:
    """Name the likely fix. A stale model looks like a login failure to a newcomer."""
    if _MODEL_ERROR.search(error):
        return MODEL_HINT
    if _AUTH_ERROR.search(error):
        return "Sign in again, or check the key reference"
    return "Check the endpoint and your network, then retry"


def _check_live(name: str, provider: object) -> Check:
    result = safe_complete(provider, CANARY_PROMPT, CANARY_OUTPUT_TOKENS)
    if result.ok:
        return Check(f"{name} live", True, "answered")
    return Check(f"{name} live", False, f"{result.error}. {_live_hint(result.error)}")


def _live_checks(config: Config, tested: frozenset[str] | None) -> list[Check]:
    """Providers the user did not name are never contacted."""
    def check(name: str, provider: object) -> Check:
        if tested is None or name in tested:
            return _check_live(name, provider)
        return Check(f"{name} live", True, f"skipped; add --allow-provider {name} to test it", is_advisory=True)

    return [check(name, provider) for name, provider in config.providers.items()]


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


def run_doctor(
    config: Config, *, live: bool = False, project_root: Path | None = None, tested: frozenset[str] | None = None,
) -> list[Check]:
    checks = [Check("python", sys.version_info >= MIN_PYTHON, f"running {sys.version_info.major}.{sys.version_info.minor}, needs 3.11 or newer"), _check_floor(config)]
    checks += [_check_provider(name, p) for name, p in config.providers.items()]
    checks += [c for name, p in config.providers.items() if (c := _check_login_storage(name, p, Path.home()))]
    if live:
        checks += _live_checks(config, tested)
    ignore = (project_root or Path.cwd()) / ".gitignore"
    is_ignored = ignore.exists() and "_swarm" in ignore.read_text(encoding="utf-8")
    checks.append(Check("gitignore", is_ignored, "_swarm/ is ignored" if is_ignored else "add _swarm/ and quorum.toml to .gitignore in this project"))
    return checks
