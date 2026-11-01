"""Secret handling: one redaction chokepoint and non-revealing references.

Redaction is a backstop, not the boundary. Pattern matching can miss encoded
or split values, so secrets must also stay out of prompts in the first place.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Iterable

CMD_TIMEOUT_S = 15.0
MAX_KEY_FILE_BYTES = 16_384
UNSAFE_KEY_FILE_BITS = stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH
_MIN_KNOWN_SECRET_CHARS = 8

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\Z)", re.S)),
    ("ANTHROPIC", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}")),
    ("OPENAI", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("STRIPE", re.compile(r"\b[rs]k_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("GITHUB", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("GITLAB", re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}")),
    ("AWS", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("SLACK", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("GOOGLE", re.compile(r"\bAIza[A-Za-z0-9_-]{30,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("XAI", re.compile(r"\bxai-[A-Za-z0-9]{20,}")),
    ("GROQ", re.compile(r"\bgsk_[A-Za-z0-9]{20,}")),
    ("NPM", re.compile(r"\bnpm_[A-Za-z0-9]{20,}")),
    ("HUGGINGFACE", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("SLACK_WEBHOOK", re.compile(r"https://hooks\.slack\.com/services/\S+")),
    ("BASIC", re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/]{8,}={0,2}")),
    ("BEARER", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("URL_USERINFO", re.compile(r"(?<=://)[^\s/@:]+:[^\s/@]+(?=@)")),
    (
        "ASSIGNMENT",
        re.compile(
            r"(?i)\b([a-z0-9_-]{0,40}(?:api[_-]?key|token|secret|password|passwd)[a-z0-9_-]{0,40}"
            r"[\"']?\s*[:=]\s*[\"']?)(?!\$)[^\s\"']{8,}"
        ),
    ),
)


def redact(text: str, known: Iterable[str] = ()) -> str:
    """Replace credential-shaped strings and every known secret value."""
    for value in known:
        if len(value) >= _MIN_KNOWN_SECRET_CHARS:
            text = text.replace(value, "[REDACTED:KNOWN]")
    for label, pattern in _PATTERNS:
        marker = f"[REDACTED:{label}]"
        if label == "ASSIGNMENT":
            text = pattern.sub(lambda m: m.group(1) + marker, text)
        else:
            text = pattern.sub(marker, text)
    return text


def contains_credential(text: str) -> bool:
    return redact(text) != text


class SecretUnavailable(RuntimeError):
    """A credential reference did not resolve. Never carries the value."""


@dataclass(eq=False)
class Secret:
    """Lazy credential reference. `reveal` is called at two sites only."""

    reference: str
    _resolve: Callable[[], str] = field(repr=False)
    _value: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"Secret({self.reference})"

    __str__ = __repr__

    def reveal(self) -> str:
        if self._value is None:
            self._value = self._resolve()
        return self._value

    def known_values(self) -> tuple[str, ...]:
        """Values already resolved, for exact-match redaction."""
        return () if self._value is None else (self._value,)


def from_env(name: str) -> Secret:
    def resolve() -> str:
        value = os.environ.get(name, "")
        if not value:
            raise SecretUnavailable(f"environment variable {name} is not set; export it or use api_key_cmd")
        return value

    return Secret(f"env:{name}", resolve)


def _read_key_file(path: str) -> str:
    """Check the opened file, not the path, so it cannot be swapped between check and read."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(descriptor, "r", encoding="utf-8") as key_file:
        info = os.fstat(key_file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_KEY_FILE_BYTES:
            raise SecretUnavailable(f"api_key_file {path} is not a small regular file")
        if info.st_mode & UNSAFE_KEY_FILE_BITS:
            raise SecretUnavailable(
                f"api_key_file {path} is open to other users; set its mode to 0400 or 0440"
            )
        return key_file.read(MAX_KEY_FILE_BYTES).strip()


def from_file(path: str) -> Secret:
    """A secret mounted by the platform: Kubernetes, Docker, systemd or Vault Agent."""
    def resolve() -> str:
        try:
            value = _read_key_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            raise SecretUnavailable(
                f"api_key_file {path} could not be read ({type(exc).__name__}); check the mount"
            ) from None
        if not value:
            raise SecretUnavailable(f"api_key_file {path} is empty; check the mount")
        return value

    return Secret(f"file:{path}", resolve)


def from_command(argv: list[str]) -> Secret:
    def resolve() -> str:
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=CMD_TIMEOUT_S, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SecretUnavailable(
                f"api_key_cmd {argv[0]} could not run ({type(exc).__name__}); check it manually"
            ) from None
        value = proc.stdout.strip()
        if proc.returncode != 0 or not value:
            raise SecretUnavailable(
                f"api_key_cmd {argv[0]} returned no value (exit {proc.returncode}); check it manually"
            )
        return value

    return Secret(f"cmd:{argv[0]}", resolve)
