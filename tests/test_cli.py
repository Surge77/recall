"""Tests for the Typer CLI surface (Phase 0)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from recall import __version__
from recall import main
from recall.main import app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_flag_shows_description() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "snippet manager" in result.stdout.lower()


def test_no_args_exits_nonzero_with_help() -> None:
    # no_args_is_help prints help and exits with Click's usage code (2).
    result = runner.invoke(app, [])
    assert result.exit_code != 0
    assert "Usage" in result.stdout


def test_install_reports_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    written = tmp_path / ".zshrc"
    monkeypatch.setattr(main.capture_mod, "install_hook", lambda shell: written)
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert "Hook installed" in result.stdout


def test_install_fails_without_detectable_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELL", "")
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 1
    assert "Could not detect" in result.stdout


def test_capture_command_is_silent_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main, "_open_db", lambda: object())
    monkeypatch.setattr(main, "_open_search", lambda: None)
    monkeypatch.setattr(
        main.capture_mod, "capture", lambda command, db, search: calls.append(command)
    )
    result = runner.invoke(app, ["_capture", "docker ps -a --format json"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""
    assert calls == ["docker ps -a --format json"]


def test_capture_command_real_glue_noop(recall_home: Path) -> None:
    # Exercises _open_db / _open_search for real; a trivial command no-ops
    # (no LLM, no network) and stores nothing.
    result = runner.invoke(app, ["_capture", "ls"])
    assert result.exit_code == 0
    assert not (recall_home / "data" / "chroma").exists()  # no semantic extra


def test_install_detects_bash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELL", "/bin/bash")
    seen: list[str] = []
    monkeypatch.setattr(
        main.capture_mod, "install_hook", lambda shell: seen.append(shell) or (tmp_path / ".bashrc")
    )
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert seen == ["bash"]
