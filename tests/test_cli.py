"""Tests for the Typer CLI surface (Phase 0)."""

from __future__ import annotations

from typer.testing import CliRunner

from recall import __version__
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
