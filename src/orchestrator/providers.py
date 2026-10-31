"""Provider contract for the BYOAI orchestrator.

Every model the orchestrator can call -- frontier, open-source, or a user's
own endpoint -- implements `Provider.complete`. Each call returns a `Result`
that carries the model family, which the diversity guard counts.

Network-backed adapters take an injected `transport` or `runner` so the unit
tests run offline. Live use needs the real service.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from .http_transport import post_json
from .secrets import Secret, SecretUnavailable, redact

Families = frozenset(
    {"claude", "gemini", "openai", "meta", "mistral", "deepseek", "alibaba", "xai", "ollama", "other"}
)
# Labels that say where a model runs or that nobody declared, not who trained it.
# They can answer, but they cannot satisfy the diversity floor.
UNATTRIBUTED_FAMILIES = frozenset({"ollama", "other"})
CHARS_PER_TOKEN_ESTIMATE = 4
CHILD_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "TERM")


def estimate_tokens(text: str) -> int:
    """Rough count for budget enforcement when a provider reports no usage."""
    return (len(text) + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE


@dataclass(frozen=True)
class Result:
    text: str
    family: str
    model_id: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    ok: bool = True
    error: str | None = None
    usage_known: bool = True


class Provider(Protocol):
    name: str
    family: str
    model_id: str
    capabilities: frozenset[str]

    def complete(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        output_schema: dict | None = None,
    ) -> Result: ...


@dataclass
class FakeProvider:
    """Deterministic provider for tests and dry runs."""

    name: str
    family: str
    responder: Callable[[str], str] = lambda prompt: "ok"
    model_id: str = "fake"
    capabilities: frozenset[str] = frozenset({"json_schema"})
    calls: list[str] = field(default_factory=list)

    def complete(self, prompt, *, max_output_tokens, output_schema=None):
        self.calls.append(prompt)
        text = self.responder(prompt)
        return Result(
            text=text,
            family=self.family,
            model_id=self.model_id,
            tokens_in=len(prompt.split()),
            tokens_out=min(len(text.split()), max_output_tokens),
        )


def child_env(passthrough: Iterable[str] = ()) -> dict[str, str]:
    """Allowlisted environment for a child process. Nothing else is inherited."""
    names = (*CHILD_ENV_ALLOWLIST, *passthrough)
    return {name: os.environ[name] for name in names if name in os.environ}


def _failed(
    name: str,
    family: str,
    model_id: str,
    error: str,
    started: float,
    known: Iterable[str] = (),
) -> Result:
    return Result(
        text="",
        family=family,
        model_id=model_id,
        latency_s=time.monotonic() - started,
        ok=False,
        usage_known=False,
        error=redact(f"{name}: {error}", known),
    )


def safe_complete(provider: Provider, prompt: str, max_output_tokens: int) -> Result:
    """A provider defect becomes a failed result, so paid work is not lost."""
    try:
        return provider.complete(prompt, max_output_tokens=max_output_tokens)
    except Exception as exc:  # any adapter defect must become a recorded failure
        return Result(
            "", provider.family, provider.model_id, ok=False, usage_known=False,
            error=f"{provider.name}: {type(exc).__name__}",
        )


def _token_count(value: object) -> int:
    """Provider usage is untrusted input: bad values count as unknown."""
    return value if isinstance(value, int) and value >= 0 else 0


def _usable_text(content: object) -> str | None:
    """Return non-blank string content; anything else is not an answer."""
    if isinstance(content, str) and content.strip():
        return content
    return None


@dataclass
class CliProvider:
    """A panelist reached through a command-line tool (gemini, codex).

    The prompt goes over stdin, never argv: argv reaches `ps`, audit logs and
    session transcripts. The child gets an allowlisted environment.
    The runner defaults to subprocess and is injected in tests.
    """

    name: str
    family: str
    command: list[str]
    model_id: str
    timeout_s: float = 300.0
    capabilities: frozenset[str] = frozenset({"web"})
    env_passthrough: tuple[str, ...] = ()
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run

    def complete(self, prompt, *, max_output_tokens, output_schema=None):
        started = time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="quorum-seat-") as empty_workdir:
                proc = self.runner(
                    self.command,
                    input=prompt,
                    env=child_env(self.env_passthrough),
                    cwd=empty_workdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _failed(self.name, self.family, self.model_id, str(exc), started)
        if proc.returncode != 0:
            return _failed(
                self.name, self.family, self.model_id,
                (proc.stderr or "").strip()[:300] or f"exit {proc.returncode}",
                started,
            )
        raw_output = proc.stdout.strip()
        text = redact(raw_output)[:max_output_tokens * CHARS_PER_TOKEN_ESTIMATE]
        if not text:
            return _failed(self.name, self.family, self.model_id, "empty response", started)
        return Result(
            text=text,
            family=self.family,
            model_id=self.model_id,
            tokens_in=estimate_tokens(prompt),
            tokens_out=estimate_tokens(raw_output),
            latency_s=time.monotonic() - started,
            usage_known=False,
        )


@dataclass
class OllamaProvider:
    """Local open-source model served by Ollama. Used as orchestrator/PM."""

    name: str
    model_id: str
    base_url: str = "http://localhost:11434"
    timeout_s: float = 120.0
    family: str = "ollama"
    capabilities: frozenset[str] = frozenset({"json_schema"})
    transport: Callable[[str, dict, float], dict] = post_json

    def complete(self, prompt, *, max_output_tokens, output_schema=None):
        started = time.monotonic()
        body = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_output_tokens},
        }
        if output_schema is not None:
            body["format"] = output_schema
        try:
            data = self.transport(f"{self.base_url}/api/chat", body, self.timeout_s)
        except Exception as exc:  # network or HTTP failure: record, do not raise
            return _failed(self.name, self.family, self.model_id, str(exc), started)
        text = _usable_text(data.get("message", {}).get("content"))
        if text is None:
            return _failed(self.name, self.family, self.model_id, "empty response", started)
        return Result(
            text=redact(text),
            family=self.family,
            model_id=self.model_id,
            tokens_in=_token_count(data.get("prompt_eval_count")),
            tokens_out=_token_count(data.get("eval_count")),
            latency_s=time.monotonic() - started,
        )


@dataclass
class OpenAICompatibleProvider:
    """Any OpenAI-compatible chat endpoint (BYOAI). Family is user-declared."""

    name: str
    model_id: str
    base_url: str
    family: str = "other"
    api_key: Secret | None = None
    timeout_s: float = 120.0
    capabilities: frozenset[str] = frozenset({"json_schema"})
    transport: Callable[[str, dict, float], dict] = post_json

    def complete(self, prompt, *, max_output_tokens, output_schema=None):
        started = time.monotonic()
        body = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        if output_schema is not None:
            body["response_format"] = {"type": "json_object"}
        try:
            headers = (
                {"Authorization": f"Bearer {self.api_key.reveal()}"} if self.api_key else {}
            )
            data = self.transport(
                f"{self.base_url.rstrip('/')}/chat/completions", body, self.timeout_s, headers
            )
            text = _usable_text(data["choices"][0]["message"]["content"])
        except SecretUnavailable as exc:
            return _failed(self.name, self.family, self.model_id, str(exc), started)
        except (KeyError, IndexError, TypeError) as exc:
            return _failed(
                self.name, self.family, self.model_id,
                f"malformed response ({type(exc).__name__})", started,
            )
        except Exception as exc:
            known = self.api_key.known_values() if self.api_key else ()
            return _failed(self.name, self.family, self.model_id, str(exc), started, known)
        if text is None:
            return _failed(self.name, self.family, self.model_id, "empty response", started)
        known = self.api_key.known_values() if self.api_key else ()
        text = redact(text, known)
        usage = data.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        reported_in = _token_count(usage.get("prompt_tokens"))
        reported_out = _token_count(usage.get("completion_tokens"))
        return Result(
            text=text,
            family=self.family,
            model_id=self.model_id,
            tokens_in=reported_in or estimate_tokens(prompt),
            tokens_out=reported_out or estimate_tokens(text),
            latency_s=time.monotonic() - started,
            usage_known=bool(reported_in and reported_out),
        )
