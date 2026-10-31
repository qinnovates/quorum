#!/usr/bin/env python3
"""PreToolUse hook: block Bash commands that expose credentials.

This is defense in depth for host tools. Exit 2 blocks the call. Unreadable
input also blocks, because a guard that fails open guards nothing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BLOCKED_COMMANDS = (
    ("gh auth token", re.compile(r"\bgh\s+auth\s+token\b")),
    ("printenv", re.compile(r"(?m)(?:^|[;&|(`]|\$\()\s*(?:\S*/)?printenv\b")),
    ("env dump", re.compile(r"(?m)(?:^|[;&|(`]|\$\()\s*(?:\S*/)?env\s*(?:$|[;&|)>`])")),
    ("export dump", re.compile(r"\b(?:export\s+-p|declare\s+-[px]|typeset\s+-[px]|compgen\s+-e)\b")),
    ("bare export or set", re.compile(r"(?m)(?:^|[;&|(`]|\$\()\s*(?:export|set)\s*(?:$|[;&|)>`])")),
    ("env flags dump", re.compile(r"(?m)(?:^|[;&|(`]|\$\()\s*(?:\S*/)?env(?:\s+-[0iv]+|\s+-u\s*\S+)+\s*(?:$|[;&|)>`])")),
    ("token display", re.compile(r"--show-token\b|\bgh\s+auth\s+status\s+(?:\S+\s+)*-t\b")),
    ("shell env dump", re.compile(r"\b(?:sh|bash|zsh)\s+-c\s+['\"]?\s*(?:\S*/)?(?:env|printenv)\b")),
    ("process environ read", re.compile(r"/proc/[^\s/]+/environ")),
)


MAX_COMMAND_CHARS = 100_000


def block_reason(command: str) -> str | None:
    from orchestrator.secrets import contains_credential

    if len(command) > MAX_COMMAND_CHARS:
        return "command is too long to check"
    if contains_credential(command):
        return "command contains a credential-shaped string"
    for label, pattern in BLOCKED_COMMANDS:
        if pattern.search(command):
            return f"{label} exposes credentials"
    return None


def main() -> int:
    try:
        command = json.loads(sys.stdin.buffer.read())["tool_input"]["command"]
        if not isinstance(command, str):
            raise TypeError("command is not a string")
    except (ValueError, KeyError, TypeError):
        print("quorum guard: unreadable hook input; blocking", file=sys.stderr)
        return 2
    reason = block_reason(command)
    if reason is None:
        return 0
    print(
        f"quorum guard: blocked, {reason}. Use the tool's logged-in identity or a "
        "credential helper, and ask the user if you need a secret.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a guard that crashes must block, not allow
        print(f"quorum guard: failed ({type(exc).__name__}); blocking", file=sys.stderr)
        sys.exit(2)
