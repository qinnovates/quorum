"""Load `quorum.toml`: the user-owned BYOAI configuration.

Nothing is required except the providers the user wants. Prices, the
confidence floor and budgets are all user-supplied; none are defaulted to
a guessed value.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from .evidence import RoleEvidence
from .ledger import Price
from .limits import DEFAULT_PHASE_SHARES, RunLimits
from .providers import (
    Families,
    CliProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    Provider,
)
from .router import Candidate
from .secrets import Secret, from_command, from_env

DEFAULT_MIN_FAMILIES = 2
ALLOWED_PROVIDER_BINARIES = frozenset({"gemini", "codex"})
ALLOWED_KEY_BINARIES = frozenset({"security", "secret-tool", "op", "vault", "sops", "aws", "gcloud"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
CREDENTIAL_REFERENCE_KEYS = frozenset({"api_key_env", "api_key_cmd"})
_CREDENTIAL_KEY = re.compile(r"(?i)api_?key|token|secret|password|credential")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ConfigError(ValueError):
    """quorum.toml was refused. Messages name the fix and never echo values."""


def _literal_key_message(name: str, key: str) -> str:
    return (
        f"refusing to load config: providers.{name}.{key} is a literal value. "
        "Quorum never reads secrets from config files. Use api_key_env = \"NAME\" or "
        "api_key_cmd = [...] in your user config, remove the value from the file and "
        "shell history, and rotate it. The value was not logged."
    )


def _reject_literal_credentials(name: str, spec: dict) -> None:
    for key in spec:
        if key not in CREDENTIAL_REFERENCE_KEYS and _CREDENTIAL_KEY.search(key):
            raise ConfigError(_literal_key_message(name, key))


def _validate_base_url(name: str, url: str) -> str:
    parts = urlsplit(url)
    if parts.username or parts.password or parts.query:
        raise ConfigError(
            f"providers.{name}.base_url must not contain credentials or a query string; "
            "use api_key_env and rotate anything that was in the URL"
        )
    is_loopback = parts.hostname in LOOPBACK_HOSTS
    if parts.scheme != "https" and not (parts.scheme == "http" and is_loopback):
        raise ConfigError(f"providers.{name}.base_url must use https unless it is loopback")
    return url


def _validate_binary(name: str, argv: list[str], allowed: frozenset[str], field_name: str) -> None:
    if not argv or argv[0] not in allowed or shutil.which(argv[0]) is None:
        raise ConfigError(
            f"providers.{name}.{field_name}: first item must be an installed bare command "
            f"from {sorted(allowed)}"
        )


def _credential(name: str, spec: dict, trusted: bool) -> Secret | None:
    present = CREDENTIAL_REFERENCE_KEYS & spec.keys()
    if not present:
        return None
    if not trusted:
        raise ConfigError(
            f"providers.{name}: credential references are only read from user config, "
            "because a cloned repo could otherwise send your key to its own endpoint"
        )
    if len(present) > 1:
        raise ConfigError(f"providers.{name}: set api_key_env or api_key_cmd, not both")
    if "api_key_env" in spec:
        env_name = str(spec["api_key_env"])
        if not _ENV_NAME.match(env_name):
            raise ConfigError(f"providers.{name}.api_key_env must be a variable name, not a value")
        return from_env(env_name)
    argv = list(spec["api_key_cmd"])
    _validate_binary(name, argv, ALLOWED_KEY_BINARIES, "api_key_cmd")
    return from_command(argv)

_CLI_FAMILY_DEFAULTS = {"gemini_cli": "gemini", "codex_cli": "openai"}


@dataclass
class Config:
    min_families: int
    limits: RunLimits
    pm_provider: str | None = None
    evidence: list[RoleEvidence] = field(default_factory=list)
    role_bars: dict[str, float] = field(default_factory=dict)
    phase_shares: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PHASE_SHARES))
    pricing: dict[str, Price] = field(default_factory=dict)
    confidence_floor: float | None = None
    providers: dict[str, Provider] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)


def _build_provider(name: str, spec: dict, trusted: bool) -> Provider:
    _reject_literal_credentials(name, spec)
    kind = spec["type"]
    declared_family = spec.get("family")
    if declared_family is not None and declared_family not in Families:
        raise ValueError(
            f"provider {name!r}: unknown family {declared_family!r}; use one of {sorted(Families)}"
        )
    if declared_family is not None and not trusted:
        raise ConfigError(
            f"providers.{name}.family is only read from user config; "
            "a cloned repo must not claim diversity it does not have"
        )
    caps = frozenset(spec.get("capabilities", []))
    if kind in _CLI_FAMILY_DEFAULTS:
        command = list(spec["command"])
        if any("{prompt}" in part for part in command):
            raise ConfigError(
                f"providers.{name}.command must not contain {{prompt}}; prompts go over stdin"
            )
        _validate_binary(name, command, ALLOWED_PROVIDER_BINARIES, "command")
        return CliProvider(
            name=name,
            family=spec.get("family", _CLI_FAMILY_DEFAULTS[kind]),
            command=command,
            env_passthrough=tuple(spec.get("env_passthrough", ())) if trusted else (),
            model_id=spec["model"],
            timeout_s=float(spec.get("timeout_s", 300)),
            capabilities=caps or frozenset({"web"}),
        )
    if kind == "ollama":
        return OllamaProvider(
            name=name,
            model_id=spec["model"],
            family=spec.get("family", "ollama"),
            base_url=_validate_base_url(name, spec.get("base_url", "http://localhost:11434")),
            timeout_s=float(spec.get("timeout_s", 120)),
            capabilities=caps or frozenset({"json_schema"}),
        )
    if kind == "openai_compatible":
        return OpenAICompatibleProvider(
            name=name,
            model_id=spec["model"],
            base_url=_validate_base_url(name, spec["base_url"]),
            api_key=_credential(name, spec, trusted),
            family=spec.get("family", "other"),
            timeout_s=float(spec.get("timeout_s", 120)),
            capabilities=caps or frozenset({"json_schema"}),
        )
    raise ValueError(f"unknown provider type {kind!r} for {name!r}")


def load(path: str | Path, *, trusted: bool = False) -> Config:
    """Load config. Only pass `trusted=True` for the user's own config file."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    panel = data.get("panel", {})
    min_families = int(panel.get("min_families", DEFAULT_MIN_FAMILIES))
    if min_families < 1:
        raise ValueError("panel.min_families must be at least 1")

    if not trusted and min_families < DEFAULT_MIN_FAMILIES:
        raise ConfigError(
            f"panel.min_families below {DEFAULT_MIN_FAMILIES} is only read from user config; "
            "a cloned repo may tighten the floor, not lower it"
        )

    limits_data = data.get("limits", {})
    limits = RunLimits(**{k: int(v) for k, v in limits_data.items()})

    pricing = {
        model: Price(float(p["input_per_mtok"]), float(p["output_per_mtok"]))
        for model, p in data.get("pricing", {}).items()
    }

    floor = data.get("escalation", {}).get("confidence_floor")
    config = Config(
        min_families=min_families,
        limits=limits,
        pricing=pricing,
        confidence_floor=None if floor is None else float(floor),
        pm_provider=data.get("pm", {}).get("provider"),
        evidence=[RoleEvidence(**row) for row in data.get("evidence", [])],
        role_bars={k: float(v) for k, v in data.get("role_bars", {}).items()},
    )
    if "phase_shares" in data:
        config.phase_shares = {k: float(v) for k, v in data["phase_shares"].items()}

    for name, spec in data.get("providers", {}).items():
        provider = _build_provider(name, spec, trusted)
        config.providers[name] = provider
        config.candidates.append(
            Candidate(
                name=name,
                family=provider.family,
                capabilities=provider.capabilities,
                rank=int(spec.get("rank", 100)),
                model_id=provider.model_id,
            )
        )
    return config
