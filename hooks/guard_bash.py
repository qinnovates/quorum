#!/usr/bin/env python3
"""PreToolUse hook: block Bash commands that expose credentials.

This is defense in depth for host tools. Exit 2 blocks the call. Unreadable
input also blocks, because a guard that fails open guards nothing.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from orchestrator.secrets import contains_credential  # noqa: E402

BLOCKED_COMMANDS = (
    ("gh auth token", re.compile(r"\bgh\s+auth\s+token\b")),
    ("printenv", re.compile(r"(?:^|[;&|(`]|\$\()\s*printenv\b")),
    ("env dump", re.compile(r"(?:^|[;&|(`]|\$\()\s*env\s*(?:$|[;&|)>`])")),
    ("process environ read", re.compile(r"/proc/[^\s/]+/environ")),
)


def block_reason(command: str) -> str | None:
    if contains_credential(command):
        return "command contains a credential-shaped string"
    for label, pattern in BLOCKED_COMMANDS:
        if pattern.search(command):
            return f"{label} exposes credentials"
    return None


def main() -> int:
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
    except (json.JSONDecodeError, KeyError, TypeError):
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
    sys.exit(main())
