"""Tests for scripts/harden_profile.py — the hardened privacy/approval profile.

The script is a security control, so two properties are checked here: a dry run
writes nothing, and an apply is read back and is idempotent.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "harden_profile.py"


def _load():
    spec = importlib.util.spec_from_file_location("harden_profile", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from hermes_cli import config

    config._LOAD_CONFIG_CACHE.clear()
    config._RAW_CONFIG_CACHE.clear()
    yield tmp_path / ".hermes"
    config._LOAD_CONFIG_CACHE.clear()
    config._RAW_CONFIG_CACHE.clear()


def test_dry_run_writes_nothing(home, capsys):
    mod = _load()
    assert mod.main([]) == 0
    assert not (home / "config.yaml").exists(), "dry run must not touch the config file"
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "approvals.mode" in out


def test_apply_writes_privacy_section_and_is_idempotent(home, capsys):
    mod = _load()
    assert mod.main(["--apply", "--only", "privacy"]) == 0

    written = (home / "config.yaml").read_text(encoding="utf-8")
    assert "check: false" in written, written
    # Only settings that actually differ are written: telemetry is already off by default,
    # so pinning it here would just be noise in the user's file.
    assert "telemetry" not in written, written

    capsys.readouterr()
    assert mod.main(["--only", "privacy"]) == 0
    assert "Already hardened" in capsys.readouterr().out


def test_apply_does_not_leak_into_other_sections(home, capsys):
    mod = _load()
    assert mod.main(["--apply", "--only", "privacy"]) == 0

    capsys.readouterr()
    assert mod.main(["--only", "approvals"]) == 0
    out = capsys.readouterr().out
    # approvals were not applied, so they still show as pending changes.
    assert "approvals.mode" in out and "CHANGE" in out


def test_unknown_section_is_refused(home):
    mod = _load()
    with pytest.raises(SystemExit):
        mod.main(["--only", "nope"])
