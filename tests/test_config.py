"""Tests for lazy configuration loading (Phase 0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from recall import config


def test_get_config_creates_default_file(recall_home: Path) -> None:
    cfg = config.get_config()
    assert (cfg.config_dir / "config.toml").exists()
    assert cfg.min_command_length == config.DEFAULT_MIN_COMMAND_LENGTH
    assert cfg.ai_provider == "ollama"


def test_db_and_chroma_paths_under_data_dir(recall_home: Path) -> None:
    cfg = config.get_config()
    assert cfg.db_path == cfg.data_dir / "recall.db"
    assert cfg.chroma_path == cfg.data_dir / "chroma"
    assert cfg.data_dir.exists()


def test_api_key_read_from_environment(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    config.reset_config_cache()
    assert config.get_config().anthropic_api_key == "sk-test-not-real"


def test_api_key_none_when_unset(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.reset_config_cache()
    assert config.get_config().anthropic_api_key is None


def test_get_config_is_cached(recall_home: Path) -> None:
    assert config.get_config() is config.get_config()


def test_reads_existing_config_file(recall_home: Path) -> None:
    # First call writes defaults; overwrite, then re-read on a cleared cache.
    cfg = config.get_config()
    (cfg.config_dir / "config.toml").write_text(
        '[capture]\nmin_command_length = 99\n'
        '[ai]\nprovider = "claude"\n',
        encoding="utf-8",
    )
    config.reset_config_cache()
    reloaded = config.get_config()
    assert reloaded.min_command_length == 99
    assert reloaded.ai_provider == "claude"
