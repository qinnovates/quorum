"""CLI consent, handoff limits, doctor and config safety. All offline."""

import json
from pathlib import Path

import pytest

from orchestrator import cli
from orchestrator.config import Config, ConfigError, load
from orchestrator.doctor import remote_providers, run_doctor
from orchestrator.limits import RunLimits
from orchestrator.providers import CliProvider, FakeProvider, OllamaProvider, OpenAICompatibleProvider
from orchestrator.secrets import Secret, from_env

SETUP_KEYS_PATTERN = ("api_key", "token =", "password")
SECRET_VALUE = "canary-" + "doctor-value"
USER_TOML = """
[panel]
min_families = 1

[providers.g]
type = "gemini_cli"
model = "<placeholder>"
command = ["gemini", "-p", "go"]
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".config" / "quorum").mkdir(parents=True)
    (home / ".config" / "quorum" / "quorum.toml").write_text(USER_TOML, encoding="utf-8")
    monkeypatch.setattr(cli, "USER_CONFIG", home / ".config" / "quorum" / "quorum.toml")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")
    work = tmp_path / "work"
    (work / "_swarm" / "tmp").mkdir(parents=True)
    monkeypatch.chdir(work)
    return work


def test_start_refuses_without_consent_and_keeps_the_file(project, capsys):
    question = project / "_swarm" / "tmp" / "q.txt"
    question.write_text("For our API, which is best under a budget as the goal?", encoding="utf-8")
    assert cli.main(["start", "--question-file", str(question)]) == 2
    assert "--allow-provider g" in capsys.readouterr().err and question.exists()


def test_handoff_outside_swarm_tmp_is_refused_and_not_deleted(project, capsys):
    outside = project / "secret.txt"
    outside.write_text("private", encoding="utf-8")
    assert cli.main(["start", "--question-file", str(outside), "--allow-provider", "g"]) == 2
    assert "handoff files" in capsys.readouterr().err and outside.exists()


def test_remote_providers_exclude_only_local_ollama():
    config = Config(min_families=1, limits=RunLimits())
    config.providers["local"] = OllamaProvider("local", "m")
    config.providers["far"] = OllamaProvider("far", "m", base_url="https://models.example.org")
    config.providers["api"] = OpenAICompatibleProvider("api", "m", "https://x.example/v1")
    assert remote_providers(config) == ["api", "far"]


def test_doctor_never_prints_the_key(tmp_path):
    config = Config(min_families=1, limits=RunLimits())
    config.providers["api"] = OpenAICompatibleProvider(
        "api", "m", "https://x.example/v1", api_key=Secret("env:X", lambda: SECRET_VALUE)
    )
    checks = run_doctor(config, project_root=tmp_path)
    assert SECRET_VALUE not in json.dumps([c.detail for c in checks])


def test_doctor_names_a_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("QUORUM_NO_SUCH_KEY", raising=False)
    config = Config(min_families=1, limits=RunLimits())
    config.providers["api"] = OpenAICompatibleProvider(
        "api", "m", "https://x.example/v1", api_key=from_env("QUORUM_NO_SUCH_KEY")
    )
    bad = [c for c in run_doctor(config, project_root=tmp_path) if not c.is_ok]
    assert any("QUORUM_NO_SUCH_KEY" in c.detail for c in bad)


def test_doctor_live_reports_a_failed_provider(tmp_path):
    def boom(prompt):
        raise RuntimeError("logged out")
    config = Config(min_families=1, limits=RunLimits())
    config.providers["g"] = FakeProvider("g", "gemini", boom)
    checks = run_doctor(config, live=True, project_root=tmp_path)
    assert any(c.name == "g live" and not c.is_ok for c in checks)


@pytest.mark.parametrize("flag", ["--yolo", "--dangerously-bypass-approvals-and-sandbox", "-y", "--approval-mode=yolo", "-yp", "--allowed-tools=Bash"])
def test_approval_bypass_flags_are_refused(tmp_path, monkeypatch, flag):
    monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")
    path = tmp_path / "quorum.toml"
    path.write_text(f'[providers.g]\ntype = "gemini_cli"\nmodel = "m"\ncommand = ["gemini", "{flag}"]\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="safe list"):
        load(path, trusted=True)


def test_configured_model_reaches_the_command(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")
    path = tmp_path / "quorum.toml"
    path.write_text('[providers.c]\ntype = "codex_cli"\nmodel = "real-model"\ncommand = ["codex", "exec", "-"]\n', encoding="utf-8")
    provider = load(path, trusted=True).providers["c"]
    assert isinstance(provider, CliProvider)
    assert provider.command == ["codex", "exec", "-m", "real-model", "-"]


def test_setup_writes_a_private_keyless_config_that_loads(tmp_path, monkeypatch):
    from orchestrator.setup_config import DetectedTools, write_user_config
    monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")
    path = tmp_path / "quorum" / "quorum.toml"
    tools = DetectedTools(has_gemini=True, has_codex=True, ollama_models=["llama3:latest"])
    message = write_user_config(path, tools)
    assert "no keys" in message and "codex login" in message
    assert path.stat().st_mode & 0o777 == 0o600
    active = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    assert not any(word in line for line in active for word in SETUP_KEYS_PATTERN)
    config = load(path, trusted=True)
    assert config.min_families == 2 and config.providers["local"].family == "meta"


def test_setup_keeps_an_existing_config_unless_forced(tmp_path):
    from orchestrator.setup_config import DetectedTools, write_user_config
    path = tmp_path / "quorum.toml"
    path.write_text("# mine\n", encoding="utf-8")
    assert "Kept" in write_user_config(path, DetectedTools())
    assert path.read_text(encoding="utf-8") == "# mine\n"
    write_user_config(path, DetectedTools(), force=True)
    assert path.with_suffix(".toml.previous").read_text(encoding="utf-8") == "# mine\n"


def test_setup_with_no_other_models_stays_single_family(tmp_path):
    from orchestrator.setup_config import DetectedTools, build_config
    path = tmp_path / "quorum.toml"
    path.write_text(build_config(DetectedTools()), encoding="utf-8")
    assert load(path, trusted=True).min_families == 1


def test_unknown_local_model_stays_unattributed():
    from orchestrator.setup_config import ollama_family
    assert ollama_family("mystery-model") == "other"
    assert ollama_family("qwen2:7b") == "alibaba"


def test_config_has_placeholders_only_for_missing_models():
    from orchestrator.setup_config import DetectedTools, build_config
    empty = build_config(DetectedTools())
    for marker in ("# GEMINI CLI", "# CODEX CLI", "# LOCAL MODEL WITH OLLAMA", "# HOSTED OR SELF-HOSTED API", "<your-endpoint>"):
        assert marker in empty
    connected = build_config(DetectedTools(has_gemini=True))
    assert "# GEMINI CLI" not in connected and "# CODEX CLI" in connected


def test_filled_in_api_placeholder_loads(tmp_path):
    from orchestrator.setup_config import API_TEMPLATE
    lines = [line[2:] for line in API_TEMPLATE.splitlines() if line.startswith("# ") and "=" in line or line.startswith("# [")]
    body = "\n".join(line for line in lines if "api_key_cmd" not in line)
    for placeholder, value in (
        ("<short-name>", "byo"), ("<model-id>", "m"), ("<your-endpoint>", "api.example.org"),
        ("<who-trained-it>", "mistral"), ("<SHORT_NAME>", "BYO"),
    ):
        body = body.replace(placeholder, value)
    path = tmp_path / "quorum.toml"
    path.write_text(body, encoding="utf-8")
    assert load(path, trusted=True).providers["byo"].family == "mistral"


def test_model_name_cannot_smuggle_a_flag(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.config.shutil.which", lambda name: f"/bin/{name}")
    path = tmp_path / "quorum.toml"
    path.write_text('[providers.g]\ntype = "gemini_cli"\nmodel = "--yolo"\ncommand = ["gemini"]\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="not allowed"):
        load(path, trusted=True)


def test_symlinked_handoff_dir_is_refused_and_outside_file_survives(project, capsys):
    import shutil
    outside = project / "outside"
    outside.mkdir()
    victim = outside / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")
    shutil.rmtree(project / "_swarm" / "tmp")
    (project / "_swarm" / "tmp").symlink_to(outside)
    args = ["record", "--run", "0" * 16, "--seat", "S1", "--prompt-hash", "h", "--file", "_swarm/tmp/victim.txt"]
    assert cli.main(args) == 2
    assert victim.read_text(encoding="utf-8") == "keep me"


def test_symlink_and_hard_link_files_are_refused(project):
    import os
    secret = project / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    link = project / "_swarm" / "tmp" / "link.txt"
    link.symlink_to(secret)
    with pytest.raises(OSError):
        cli._read_handoff(str(link))
    hard = project / "_swarm" / "tmp" / "hard.txt"
    os.link(secret, hard)
    with pytest.raises(cli.RunError, match="one link"):
        cli._read_handoff(str(hard))


def test_swapped_file_is_not_deleted(project):
    path = project / "_swarm" / "tmp" / "a.txt"
    path.write_text("x", encoding="utf-8")
    handoff = cli._read_handoff(str(path))
    path.unlink()
    path.write_text("replacement", encoding="utf-8")
    cli._discard_handoff(cli.Handoff(handoff.path, -1, handoff.text))
    assert path.exists()


def test_lookalike_localhost_needs_consent():
    config = Config(min_families=1, limits=RunLimits())
    config.providers["x"] = OllamaProvider("x", "m", base_url="https://localhost.attacker.example")
    assert remote_providers(config) == ["x"]


def test_backups_are_never_overwritten(tmp_path):
    from orchestrator.setup_config import DetectedTools, write_user_config
    path = tmp_path / "quorum.toml"
    path.write_text("# one\n", encoding="utf-8")
    write_user_config(path, DetectedTools(), force=True)
    write_user_config(path, DetectedTools(), force=True)
    assert path.with_suffix(".toml.previous").read_text(encoding="utf-8") == "# one\n"
    assert path.with_suffix(".toml.previous2").exists()


def test_fifo_handoff_does_not_hang(project):
    import os
    fifo = project / "_swarm" / "tmp" / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(cli.RunError, match="regular"):
        cli._read_handoff(str(fifo))
