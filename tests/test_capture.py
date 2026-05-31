"""Tests for auto-capture logic and hook installation (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from recall import capture
from recall.config import Config
from recall.db import SnippetDB

LONG_CMD = "docker run -d --restart unless-stopped -p 8080:80 nginx:latest"


def _cfg(tmp_path: Path, min_len: int = 40) -> Config:
    return Config(config_dir=tmp_path, data_dir=tmp_path, min_command_length=min_len)


class RecordingSearch:
    def __init__(self) -> None:
        self.added: list[tuple[int, str, str]] = []

    def add(self, snippet_id: int, command: str, description: str) -> None:
        self.added.append((snippet_id, command, description))


# --- should_capture ---------------------------------------------------------

def test_should_capture_rejects_trivial_command(db: SnippetDB, tmp_path: Path) -> None:
    assert capture.should_capture("ls -la", db, _cfg(tmp_path)) is False


def test_should_capture_rejects_short_command(db: SnippetDB, tmp_path: Path) -> None:
    assert capture.should_capture("git status", db, _cfg(tmp_path)) is False


def test_should_capture_rejects_comment(db: SnippetDB, tmp_path: Path) -> None:
    comment = "# this is a long comment line that exceeds the minimum length"
    assert capture.should_capture(comment, db, _cfg(tmp_path)) is False


def test_should_capture_rejects_recall_itself(db: SnippetDB, tmp_path: Path) -> None:
    cmd = "recall search something that is long enough to pass the length gate"
    assert capture.should_capture(cmd, db, _cfg(tmp_path)) is False


def test_should_capture_accepts_long_new_command(db: SnippetDB, tmp_path: Path) -> None:
    assert capture.should_capture(LONG_CMD, db, _cfg(tmp_path)) is True


def test_should_capture_rejects_existing_command(db: SnippetDB, tmp_path: Path) -> None:
    db.add(LONG_CMD, "run nginx", source="auto")
    assert capture.should_capture(LONG_CMD, db, _cfg(tmp_path)) is False


# --- capture ----------------------------------------------------------------

def test_capture_stores_new_command(
    db: SnippetDB, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture, "generate_description", lambda c, cfg=None: "run nginx detached")
    search = RecordingSearch()
    capture.capture(LONG_CMD, db, search, _cfg(tmp_path))
    stored = db.keyword_search("nginx")
    assert len(stored) == 1
    assert stored[0].source == "auto"
    assert stored[0].description == "run nginx detached"
    assert search.added == [(stored[0].id, LONG_CMD, "run nginx detached")]


def test_capture_duplicate_only_increments(
    db: SnippetDB, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snippet = db.add(LONG_CMD, "run nginx", source="auto")

    def boom(*_a: object, **_k: object) -> str:
        raise AssertionError("generate_description must not run for duplicates")

    monkeypatch.setattr(capture, "generate_description", boom)
    capture.capture(LONG_CMD, db, None, _cfg(tmp_path))
    refreshed = db.get(snippet.id)
    assert refreshed is not None
    assert refreshed.run_count == 2


def test_capture_ignores_trivial_command(
    db: SnippetDB, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capture, "generate_description", lambda c, cfg=None: "x")
    capture.capture("ls -la", db, None, _cfg(tmp_path))
    assert db.list_all() == []


# --- install_hook -----------------------------------------------------------

def test_install_hook_writes_zsh_block(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    returned = capture.install_hook("zsh", rc)
    text = rc.read_text(encoding="utf-8")
    assert returned == rc
    assert "# recall auto-capture hook" in text
    assert 'recall _capture "$1"' in text
    assert "add-zsh-hook preexec _recall_hook" in text


def test_install_hook_writes_bash_block(tmp_path: Path) -> None:
    rc = tmp_path / ".bashrc"
    capture.install_hook("bash", rc)
    text = rc.read_text(encoding="utf-8")
    assert "trap '_recall_hook' DEBUG" in text
    assert 'recall _capture "$BASH_COMMAND"' in text


def test_install_hook_is_idempotent(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    capture.install_hook("zsh", rc)
    capture.install_hook("zsh", rc)
    assert rc.read_text(encoding="utf-8").count("# recall auto-capture hook") == 1


def test_install_hook_rejects_unknown_shell(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        capture.install_hook("fish", tmp_path / ".fishrc")


def test_capture_module_imports_without_side_effects() -> None:
    import importlib

    # Re-importing must not create files or require any config on disk.
    importlib.reload(capture)
