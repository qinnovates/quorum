"""The protocol must stay aligned with the skill and CLI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = (ROOT / "references" / "orchestrator.md").read_text(encoding="utf-8")
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_skill_loads_the_protocol():
    assert "orchestrator.md" in SKILL and "`references/`" in SKILL


def test_protocol_keeps_core_rules():
    for rule in ("FAILED_DIVERSITY", "UNRESOLVED", "at least 2 Challengers", "Share facts. Never share opinions."):
        assert rule in PROTOCOL


def test_every_flag_it_names_exists_in_the_skill():
    every_file = SKILL + "".join(p.read_text(encoding="utf-8") for p in (ROOT / "references").glob("*.md"))
    for flag in ("--max", "--set N", "--reviewers", "--ratify", "--no-web", "--no-diverse", "--dry-run", "--ponder", "--artifact"):
        assert flag in every_file


def test_discovery_commands_are_allowed():
    for tool in ("Bash(command -v:*)", "Bash(ollama list:*)", "Bash(quorum-run doctor:*)"):
        assert tool in SKILL


def test_skill_grants_no_direct_provider_or_write_access():
    header = SKILL.split("---")[1]
    for grant in ("Bash(gemini", "Bash(codex", "Bash(quorum-run start", "Bash(quorum-run:*)", "  - Write"):
        assert grant not in header


def test_protocol_names_no_specific_model_version():
    for name in ("gpt-", "opus", "sonnet", "haiku", "gemini-2", "llama3"):
        assert name not in PROTOCOL.lower()
