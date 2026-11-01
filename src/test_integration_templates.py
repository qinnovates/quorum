"""Every template in docs/INTEGRATIONS.md must load, and mounted key files must be safe."""

import os
import re
import tomllib
from pathlib import Path

import pytest

from orchestrator import config as config_module
from orchestrator import doctor
from orchestrator.config import ALLOWED_KEY_BINARIES, Config, ConfigError, load
from orchestrator.doctor import _live_hint, run_doctor
from orchestrator.limits import RunLimits
from orchestrator.providers import CliProvider, FakeProvider, _stderr_summary
from orchestrator.secrets import SecretUnavailable, from_file

GUIDE = Path(__file__).resolve().parent.parent / "docs" / "INTEGRATIONS.md"
KEY_VALUE = "canary-" + "file-value"


def key_file_template() -> str:
    return filled(next(block for block in guide_toml_blocks() if "api_key_file" in block))


def guide_toml_blocks() -> list[str]:
    return re.findall(r"```toml\n(.*?)```", GUIDE.read_text(encoding="utf-8"), re.DOTALL)


def filled(block: str) -> str:
    replacements = {
        "<model-from-ollama-list>": "m", "<model-id>": "m", "<your-endpoint>": "api.example.org",
        "<who-trained-it>": "mistral", "<your-vault>": "v",
    }
    for placeholder, value in replacements.items():
        block = block.replace(placeholder, value)
    return block


@pytest.mark.parametrize("block", guide_toml_blocks())
def test_every_guide_template_loads(block, tmp_path, monkeypatch):
    monkeypatch.setattr(config_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    path = tmp_path / "quorum.toml"
    path.write_text(f"[panel]\nmin_families = 1\n\n{filled(block)}", encoding="utf-8")
    assert load(path, trusted=True).providers


def test_table_commands_are_allowed():
    rows = re.findall(r"^\| [^|]+ \| `(\[.+\])` \|$", GUIDE.read_text(encoding="utf-8"), re.MULTILINE)
    assert len(rows) == 6
    for row in rows:
        argv = tomllib.loads(f"argv = {row}")["argv"]
        assert argv[0] in ALLOWED_KEY_BINARIES


def write_key(tmp_path, mode=0o400, text=KEY_VALUE):
    path = tmp_path / "api-key"
    path.unlink(missing_ok=True)
    path.write_text(f"{text}\n", encoding="utf-8")
    path.chmod(mode)
    return path


def test_key_file_is_read_and_stripped(tmp_path):
    secret = from_file(str(write_key(tmp_path)))
    assert secret.reveal() == KEY_VALUE
    assert KEY_VALUE not in repr(secret)


@pytest.mark.parametrize("mode", [0o444, 0o404, 0o460, 0o402])
def test_key_file_open_to_others_is_refused(tmp_path, mode):
    with pytest.raises(SecretUnavailable, match="open to other users"):
        from_file(str(write_key(tmp_path, mode))).reveal()


def test_group_read_is_allowed_for_kubernetes_fs_group(tmp_path):
    assert from_file(str(write_key(tmp_path, 0o440))).reveal() == KEY_VALUE


def test_symlinked_mount_is_followed(tmp_path):
    target = write_key(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(target)
    assert from_file(str(link)).reveal() == KEY_VALUE


def test_key_file_errors_never_carry_the_value(tmp_path):
    path = write_key(tmp_path, 0o444)
    with pytest.raises(SecretUnavailable) as caught:
        from_file(str(path)).reveal()
    assert KEY_VALUE not in str(caught.value)


def test_directory_empty_and_oversized_files_are_refused(tmp_path):
    with pytest.raises(SecretUnavailable):
        from_file(str(tmp_path)).reveal()
    with pytest.raises(SecretUnavailable, match="empty"):
        from_file(str(write_key(tmp_path, text=" "))).reveal()
    with pytest.raises(SecretUnavailable, match="small regular"):
        from_file(str(write_key(tmp_path, text="k" * 20_000))).reveal()


def test_fifo_cannot_hang_the_run(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo, 0o400)
    with pytest.raises(SecretUnavailable, match="small regular"):
        from_file(str(fifo)).reveal()


@pytest.mark.parametrize("path", ["relative/key", "/var/run/../key"])
def test_key_path_must_be_absolute_and_plain(tmp_path, path):
    config_file = tmp_path / "quorum.toml"
    config_file.write_text(key_file_template().replace("/var/run/secrets/quorum/api-key", path), encoding="utf-8")
    with pytest.raises(ConfigError, match="absolute"):
        load(config_file, trusted=True)


def test_project_config_cannot_add_a_key_file(tmp_path):
    config_file = tmp_path / "quorum.toml"
    config_file.write_text(key_file_template(), encoding="utf-8")
    with pytest.raises(ConfigError, match="only read from user config"):
        load(config_file)


@pytest.mark.parametrize("error, hint", [
    ("codex: ERROR: The 'gpt-5.3-codex' model is not supported when using Codex with a ChatGPT account.", "not available"),
    ("codex: Failed to refresh token status=401 Unauthorized", "Sign in again"),
    ("gemini: Authentication cancelled by user", "Sign in again"),
    ("byo: ConnectionError", "Check the endpoint"),
])
def test_live_hint_names_the_likely_fix(error, hint):
    assert hint in _live_hint(error)


def test_cli_error_keeps_the_end_of_stderr():
    def fails(*_args, **_kwargs):
        class Finished:
            returncode, stdout = 1, ""
            stderr = "OpenAI Codex banner\n" * 100 + "ERROR: the real reason"
        return Finished

    provider = CliProvider("codex", "openai", ["codex"], "default", runner=fails)
    assert "the real reason" in provider.complete("hi", max_output_tokens=8).error


@pytest.mark.parametrize("stderr, kept", [
    ("banner\nError authenticating: cancelled\n    at initOauthClient\n" + "Skill conflict noise\n" * 50, "Error authenticating"),
    ("OpenAI Codex v1\nERROR: the model is not supported\nERROR: the model is not supported", "not supported"),
    ("nothing matched here", "nothing matched"),
])
def test_stderr_summary_keeps_the_failure(stderr, kept):
    summary = _stderr_summary(stderr)
    assert kept in summary and "noise" not in summary and summary.count("not supported") <= 1


def test_stderr_summary_hides_the_home_path():
    assert str(Path.home()) not in _stderr_summary(f"Error: cannot read {Path.home()}/.config/tool")


def cli_config(name="codex"):
    provider = CliProvider(name, "openai", [name, "exec"], "default")
    return Config(min_families=1, limits=RunLimits(), providers={name: provider})


def test_plaintext_login_is_noted_without_reading_it(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor.Path, "home", lambda: tmp_path)
    login = tmp_path / ".codex" / "auth.json"
    login.parent.mkdir()
    login.write_text(KEY_VALUE, encoding="utf-8")
    login.chmod(0o600)
    found = [c for c in run_doctor(cli_config(), project_root=tmp_path) if "login storage" in c.name]
    assert found[0].is_advisory and "keyring" in found[0].detail and KEY_VALUE not in found[0].detail
    login.chmod(0o644)
    found = [c for c in run_doctor(cli_config(), project_root=tmp_path) if "login storage" in c.name]
    assert not found[0].is_ok and not found[0].is_advisory


def test_live_check_skips_providers_not_named(tmp_path):
    calls = []
    named = FakeProvider("named", "openai", lambda p: calls.append("named") or "ok")
    other = FakeProvider("other", "gemini", lambda p: calls.append("other") or "ok")
    config = cli_config()
    config.providers = {"named": named, "other": other}
    checks = run_doctor(config, live=True, project_root=tmp_path, tested=frozenset({"named"}))
    assert calls == ["named"]
    assert next(c for c in checks if c.name == "other live").is_advisory
