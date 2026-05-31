"""Shared pytest fixtures.

Every filesystem-touching test runs against a temp ``RECALL_HOME`` so the real
user database and config are never read or written.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from recall import config
from recall.db import SnippetDB


@pytest.fixture
def recall_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point Recall's config and data dirs at an isolated temp directory."""
    monkeypatch.setenv("RECALL_HOME", str(tmp_path))
    config.reset_config_cache()
    yield tmp_path
    config.reset_config_cache()


@pytest.fixture
def db(tmp_path: Path) -> SnippetDB:
    """A fresh SnippetDB backed by a temp file."""
    return SnippetDB(tmp_path / "recall.db")
