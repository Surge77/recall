"""Tests for CLI rendering helpers."""

from __future__ import annotations

import sys
import types

import pytest

from recall import render


def test_parse_tags_splits_and_trims() -> None:
    assert render.parse_tags(" git , vcs ,, cli ") == ["git", "vcs", "cli"]


def test_parse_tags_empty_is_empty_list() -> None:
    assert render.parse_tags(None) == []
    assert render.parse_tags("") == []


def test_copy_to_clipboard_invokes_pyperclip(monkeypatch: pytest.MonkeyPatch) -> None:
    copied: list[str] = []
    fake = types.SimpleNamespace(copy=lambda text: copied.append(text))
    monkeypatch.setitem(sys.modules, "pyperclip", fake)
    render.copy_to_clipboard("docker ps -a")
    assert copied == ["docker ps -a"]


def test_copy_to_clipboard_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_text: str) -> None:
        raise RuntimeError("no clipboard on this host")

    fake = types.SimpleNamespace(copy=boom)
    monkeypatch.setitem(sys.modules, "pyperclip", fake)
    render.copy_to_clipboard("anything")  # must not raise
