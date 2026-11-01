"""Load `quorum.toml`: the user-owned BYOAI configuration.

Nothing is required except the providers the user wants. Prices, the
confidence floor and budgets are all user-supplied; none are defaulted to
a guessed value.
"""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path, PurePosixPath
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
from .secrets import Secret, from_command, from_env, from_file

DEFAULT_MIN_FAMILIES = 2
ALLOWED_KEY_BINARIES = frozenset({
    "security", "secret-tool", "pass", "op", "bw", "vault", "doppler", "sops", "aws", "gcloud", "az",
})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
UNTRUSTED_SECTIONS = frozenset({"panel", "limits"})
CLI_BINARY_FAMILIES = {"gemini_cli": ("gemini", "gemini"), "codex_cli": ("codex", "openai")}
CREDENTIAL_REFERENCE_KEYS = frozenset({"api_key_env", "api_key_cmd", "api_key_file"})
ALLOWED_CLI_ARGS = {
    "gemini": frozenset({"--skip-trust", "--approval-mode", "plan", "-p", "-o", "json", "text", "-m"}),
    "codex": frozenset({"exec", "--skip-git-repo-check", "--sandbox", "read-only", "--json", "-", "-m"}),
}
FREE_TEXT_FLAGS = frozenset({"-p", "-m"})
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
MODEL_FLAG_POSITION = {"gemini": 1, "codex": 2}
_CREDENTIAL_KEY = re.compile(r"(?i)api_?key|token|secret|password|credential")
_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ConfigError(ValueError):
    """quorum.toml was refused. Messages name the fix and never echo values."""


def _literal_key_message(name: str, key: str) -> str:
    return (
        f"refusing to load config: providers.{name}.{key} is a literal value. "
        "Quorum never reads secrets from config files. Use api_key_env = \"NAME\" or "
        "api_key_cmd = [...] or api_key_file = \"/path\" in your user config, remove the value from the file and "
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


def _reject_unsafe_flags(name: str, command: list[str]) -> None:
    """Allow known-safe arguments only. Denylists miss new or combined flags."""
    allowed = ALLOWED_CLI_ARGS[command[0]]
    previous = ""
    for part in command[1:]:
        if previous in FREE_TEXT_FLAGS and not part.startswith("-"):
            previous = ""
            continue
        if part not in allowed:
            raise ConfigError(
                f"providers.{name}.command: {part!r} is not on the safe list, which blocks "
                "approval-bypass flags. Panelists must not be able to act on your machine"
            )
        previous = part


def _with_model_flag(command: list[str], binary: str, model: str) -> list[str]:
    """Pass the configured model, so routing evidence matches what actually runs."""
    if model.startswith("<") or model == "default" or "-m" in command:
        return command
    if not _MODEL_NAME.match(model):
        raise ConfigError(f"model name {model!r} has characters that are not allowed")
    position = MODEL_FLAG_POSITION[binary]
    return [*command[:position], "-m", model, *command[position:]]


def _validated_key_path(name: str, raw_path: object) -> str:
    """Mounted secrets have fixed absolute paths, so anything else is a mistake."""
    path = PurePosixPath(str(raw_path))
    if not path.is_absolute() or ".." in path.parts or "\0" in str(raw_path):
        raise ConfigError(f"providers.{name}.api_key_file must be an absolute path with no '..'")
    return str(path)


def _credential(name: str, spec: dict) -> Secret | None:
    present = CREDENTIAL_REFERENCE_KEYS & spec.keys()
    if not present:
        return None
    if len(present) > 1:
        raise ConfigError(f"providers.{name}: set only one of {sorted(CREDENTIAL_REFERENCE_KEYS)}")
    if "api_key_env" in spec:
        env_name = str(spec["api_key_env"])
        if not _ENV_NAME.match(env_name):
            raise ConfigError(f"providers.{name}.api_key_env must be a variable name, not a value")
        return from_env(env_name)
    if "api_key_file" in spec:
        return from_file(_validated_key_path(name, spec["api_key_file"]))
    argv = list(spec["api_key_cmd"])
    _validate_binary(name, argv, ALLOWED_KEY_BINARIES, "api_key_cmd")
    return from_command(argv)



@dataclass
class Config:
    min_families: int
    limits: RunLimits
    pm_provider: str | None = None
    evidence: list[RoleEvidence] = field(default_factory=list)
    role_bars: dict[str, float] = field(default_factory=dict)
    verified_sources: frozenset[str] = frozenset()
    should_fetch_sources: bool = False
    should_check_entailment: bool = False
    allowed_source_hosts: frozenset[str] = frozenset()
    phase_shares: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PHASE_SHARES))
    pricing: dict[str, Price] = field(default_factory=dict)
    confidence_floor: float | None = None
    providers: dict[str, Provider] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)


def _cli_provider(name: str, spec: dict, declared_family: str | None, caps: frozenset[str]) -> Provider:
    command = list(spec["command"])
    if any("{prompt}" in part for part in command):
        raise ConfigError(f"providers.{name}.command must not contain {{prompt}}; prompts go over stdin")
    binary, family = CLI_BINARY_FAMILIES[spec["type"]]
    _validate_binary(name, command, frozenset({binary}), "command")
    _reject_unsafe_flags(name, command)
    if declared_family not in (None, family):
        raise ConfigError(f"providers.{name}: a {binary} command is family {family}")
    return CliProvider(
        name=name, family=family, command=_with_model_flag(command, binary, str(spec["model"])),
        env_passthrough=tuple(spec.get("env_passthrough", ())), model_id=spec["model"],
        timeout_s=float(spec.get("timeout_s", 300)), capabilities=caps or frozenset({"web"}),
    )


def _ollama_provider(name: str, spec: dict, caps: frozenset[str]) -> Provider:
    return OllamaProvider(
        name=name, model_id=spec["model"], family=spec.get("family", "ollama"),
        base_url=_validate_base_url(name, spec.get("base_url", "http://localhost:11434")),
        timeout_s=float(spec.get("timeout_s", 120)), capabilities=caps or frozenset({"json_schema"}),
    )


def _compatible_provider(name: str, spec: dict, caps: frozenset[str]) -> Provider:
    return OpenAICompatibleProvider(
        name=name, model_id=spec["model"], base_url=_validate_base_url(name, spec["base_url"]),
        api_key=_credential(name, spec), family=spec.get("family", "other"),
        timeout_s=float(spec.get("timeout_s", 120)), capabilities=caps or frozenset({"json_schema"}),
    )


def _build_provider(name: str, spec: dict) -> Provider:
    _reject_literal_credentials(name, spec)
    kind = spec["type"]
    declared_family = spec.get("family")
    if declared_family is not None and declared_family not in Families:
        raise ValueError(f"provider {name!r}: unknown family {declared_family!r}; use one of {sorted(Families)}")
    caps = frozenset(spec.get("capabilities", []))
    if kind in CLI_BINARY_FAMILIES:
        return _cli_provider(name, spec, declared_family, caps)
    if kind == "ollama":
        return _ollama_provider(name, spec, caps)
    if kind == "openai_compatible":
        return _compatible_provider(name, spec, caps)
    raise ValueError(f"unknown provider type {kind!r} for {name!r}")


def _min_families(data: dict, trusted: bool) -> int:
    if not trusted:
        for section in data.keys() - UNTRUSTED_SECTIONS:
            raise ConfigError(
                f"{section} is only read from user config; "
                "a project file may only tighten [panel] and [limits]"
            )
    min_families = int(data.get("panel", {}).get("min_families", DEFAULT_MIN_FAMILIES))
    if min_families < 1:
        raise ValueError("panel.min_families must be at least 1")
    if not trusted and min_families < DEFAULT_MIN_FAMILIES:
        raise ConfigError(
            f"panel.min_families below {DEFAULT_MIN_FAMILIES} is only read from user config; "
            "a cloned repo may tighten the floor, not lower it"
        )
    return min_families


def _add_providers(config: Config, specs: dict) -> None:
    for name, spec in specs.items():
        provider = _build_provider(name, spec)
        config.providers[name] = provider
        config.candidates.append(Candidate(
            name=name, family=provider.family, capabilities=provider.capabilities,
            rank=int(spec.get("rank", 100)), model_id=provider.model_id, strength=int(spec.get("strength", 0)),
        ))


def load(path: str | Path, *, trusted: bool = False) -> Config:
    """Load config. Only pass `trusted=True` for the user's own config file."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    min_families = _min_families(data, trusted)
    floor = data.get("escalation", {}).get("confidence_floor")
    verification = data.get("verification", {})
    config = Config(
        min_families=min_families,
        limits=RunLimits(**{k: int(v) for k, v in data.get("limits", {}).items()}),
        pricing={
            model: Price(float(p["input_per_mtok"]), float(p["output_per_mtok"]))
            for model, p in data.get("pricing", {}).items()
        },
        confidence_floor=None if floor is None else float(floor),
        pm_provider=data.get("pm", {}).get("provider"),
        evidence=[RoleEvidence(**row) for row in data.get("evidence", [])],
        role_bars={k: float(v) for k, v in data.get("role_bars", {}).items()},
        verified_sources=frozenset(str(s) for s in data.get("verified_sources", [])),
        should_fetch_sources=verification.get("fetch_sources") is True,
        should_check_entailment=verification.get("entailment") is True,
        allowed_source_hosts=frozenset(str(host).lower() for host in verification.get("allowed_hosts", [])),
    )
    if "phase_shares" in data:
        config.phase_shares = {k: float(v) for k, v in data["phase_shares"].items()}
    _add_providers(config, data.get("providers", {}))
    return config


def tighten(config: Config, project: Config) -> Config:
    """Apply a project file. It can only raise the floor and lower the limits."""
    limits = {
        f.name: min(getattr(config.limits, f.name), getattr(project.limits, f.name))
        for f in fields(RunLimits)
    }
    config.min_families = max(config.min_families, project.min_families)
    config.limits = replace(config.limits, **limits)
    return config
