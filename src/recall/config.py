"""Configuration loading for Recall.

Loaded lazily via :func:`get_config` (never on import) so that modules such as
``capture`` remain importable without side effects. Paths are resolved with
``platformdirs`` so they are correct on Windows, macOS and Linux.

Override the base directory in tests by setting ``RECALL_HOME`` to a temp dir.
The Anthropic API key is read from the environment only — it is never written
to the config file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomli_w
from platformdirs import user_config_dir, user_data_dir

_APP_NAME = "recall"
_ENV_HOME = "RECALL_HOME"
_ENV_API_KEY = "ANTHROPIC_API_KEY"

DEFAULT_MIN_COMMAND_LENGTH = 40
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TRIVIAL_COMMANDS = frozenset({"cd", "ls", "pwd", "exit", "clear", "history"})


@dataclass(frozen=True)
class Config:
    """Resolved Recall configuration. Immutable once built."""

    config_dir: Path
    data_dir: Path
    min_command_length: int = DEFAULT_MIN_COMMAND_LENGTH
    trivial_commands: frozenset[str] = DEFAULT_TRIVIAL_COMMANDS
    ai_provider: str = "ollama"  # "ollama" | "claude" | "heuristic"
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_host: str = DEFAULT_OLLAMA_HOST
    claude_model: str = DEFAULT_CLAUDE_MODEL
    _api_key: str | None = field(default=None, repr=False)

    @property
    def db_path(self) -> Path:
        """Path to the single portable SQLite database file."""
        return self.data_dir / "recall.db"

    @property
    def chroma_path(self) -> Path:
        """Path to the local ChromaDB persistence directory."""
        return self.data_dir / "chroma"

    @property
    def anthropic_api_key(self) -> str | None:
        """Anthropic key from the environment, or None if unset."""
        return self._api_key


def _base_dirs() -> tuple[Path, Path]:
    """Return ``(config_dir, data_dir)``, honouring the ``RECALL_HOME`` override."""
    override = os.environ.get(_ENV_HOME)
    if override:
        base = Path(override)
        return base / "config", base / "data"
    return Path(user_config_dir(_APP_NAME)), Path(user_data_dir(_APP_NAME))


def _default_file_contents() -> dict[str, Any]:
    return {
        "capture": {
            "min_command_length": DEFAULT_MIN_COMMAND_LENGTH,
            "trivial_commands": sorted(DEFAULT_TRIVIAL_COMMANDS),
        },
        "ai": {
            "provider": "ollama",
            "ollama_model": DEFAULT_OLLAMA_MODEL,
            "ollama_host": DEFAULT_OLLAMA_HOST,
            "claude_model": DEFAULT_CLAUDE_MODEL,
        },
    }


def _load_or_create_file(config_dir: Path) -> dict[str, Any]:
    """Read ``config.toml``, creating it with defaults if it does not exist."""
    config_file = config_dir / "config.toml"
    if not config_file.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file.write_text(tomli_w.dumps(_default_file_contents()), encoding="utf-8")
        return _default_file_contents()
    with config_file.open("rb") as handle:
        return tomllib.load(handle)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Build and cache the active configuration. Safe to call repeatedly."""
    config_dir, data_dir = _base_dirs()
    data_dir.mkdir(parents=True, exist_ok=True)
    raw = _load_or_create_file(config_dir)
    capture = raw.get("capture", {})
    ai = raw.get("ai", {})
    return Config(
        config_dir=config_dir,
        data_dir=data_dir,
        min_command_length=int(capture.get("min_command_length", DEFAULT_MIN_COMMAND_LENGTH)),
        trivial_commands=frozenset(capture.get("trivial_commands", DEFAULT_TRIVIAL_COMMANDS)),
        ai_provider=str(ai.get("provider", "ollama")),
        ollama_model=str(ai.get("ollama_model", DEFAULT_OLLAMA_MODEL)),
        ollama_host=str(ai.get("ollama_host", DEFAULT_OLLAMA_HOST)),
        claude_model=str(ai.get("claude_model", DEFAULT_CLAUDE_MODEL)),
        _api_key=os.environ.get(_ENV_API_KEY),
    )


def reset_config_cache() -> None:
    """Clear the cached config. Used by tests after changing ``RECALL_HOME``."""
    get_config.cache_clear()
