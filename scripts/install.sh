#!/usr/bin/env bash
# Install Quorum for this user. No sudo, and it never asks for an API key.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$HOME/.claude/skills/quorum"
APP_DIR="$HOME/.local/share/quorum"
BIN_DIR="$HOME/.local/bin"

find_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

install_skill() {
  if [ -f "$SKILL_DIR/SKILL.md" ]; then
    cp "$SKILL_DIR/SKILL.md" "$SKILL_DIR/SKILL.md.previous"
    echo "Saved your previous skill as SKILL.md.previous"
  fi
  mkdir -p "$SKILL_DIR/references"
  cp "$REPO_ROOT/SKILL.md" "$SKILL_DIR/SKILL.md"
  cp "$REPO_ROOT"/references/*.md "$SKILL_DIR/references/"
}

install_runner() {
  "$1" -m venv "$APP_DIR/venv"
  "$APP_DIR/venv/bin/python" -m pip install --quiet "$REPO_ROOT"
  mkdir -p "$BIN_DIR"
  ln -sf "$APP_DIR/venv/bin/quorum-run" "$BIN_DIR/quorum-run"
}

echo "Installing the Quorum skill..."
install_skill
echo "The /quorum skill is installed."

if ! PYTHON_BIN="$(find_python)"; then
  echo
  echo "Python 3.11 or newer was not found, so multi-model mode was skipped."
  echo "/quorum still works with your Claude Code model."
  echo "To add multi-model mode, install Python from https://www.python.org/downloads/ and run this again."
  exit 0
fi

echo "Installing quorum-run with $PYTHON_BIN..."
install_runner "$PYTHON_BIN"
"$BIN_DIR/quorum-run" setup

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo
    echo "One more step: add this line to your shell profile, then open a new terminal:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac
