"""Auto-capture logic and shell-hook installation.

This module imports with **no side effects** — importing it never touches the
filesystem or installs anything. The shell hook is installed only when
``install_hook`` is called. Captured command strings are *stored*, never
executed, so there is no shell-injection surface here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from recall.ai import generate_description
from recall.config import Config, get_config
from recall.db import SnippetDB
from recall.search import SemanticSearch

logger = logging.getLogger(__name__)

_TRIVIAL_COMMANDS = frozenset({"cd", "ls", "pwd", "exit", "clear", "history"})
_MARKER = "# recall auto-capture hook"
_RC_FILES = {"zsh": ".zshrc", "bash": ".bashrc"}

_HOOK_BLOCKS = {
    "zsh": (
        f"\n{_MARKER}\n"
        "autoload -Uz add-zsh-hook\n"
        '_recall_hook() {{ recall _capture "$1" &! }}\n'
        "add-zsh-hook preexec _recall_hook\n"
    ),
    "bash": (
        f"\n{_MARKER}\n"
        '_recall_hook() {{ recall _capture "$BASH_COMMAND" & }}\n'
        "trap '_recall_hook' DEBUG\n"
    ),
}


def should_capture(command: str, db: SnippetDB, cfg: Config | None = None) -> bool:
    """Decide whether a command is worth auto-saving.

    Skips comments, ``recall`` itself, trivial navigation commands, anything
    shorter than the configured minimum, and commands already stored.
    """
    cfg = cfg or get_config()
    stripped = command.strip()
    if not stripped or stripped.startswith("#"):
        return False
    first_token = stripped.split()[0]
    if first_token == "recall" or first_token in _TRIVIAL_COMMANDS:
        return False
    if len(stripped) < cfg.min_command_length:
        return False
    return not db.exists(stripped)


def capture(
    command: str,
    db: SnippetDB,
    open_search: Callable[[], SemanticSearch | None] | None = None,
    cfg: Config | None = None,
) -> None:
    """Store a new command (with description + index) or bump an existing one.

    ``open_search`` is a zero-arg factory returning a ``SemanticSearch`` (or
    None). It is invoked **only** when a new snippet is actually stored, so the
    heavy embedding model never loads for duplicates or skipped commands.

    Silent by design — it runs in the background from the shell hook and writes
    only to the log, never to the user's terminal.
    """
    cfg = cfg or get_config()
    stripped = command.strip()
    if db.exists(stripped):
        db.increment_run_count(stripped)
        return
    if not should_capture(stripped, db, cfg):
        return
    description = generate_description(stripped, cfg)
    snippet = db.add(stripped, description, source="auto")
    search = open_search() if open_search is not None else None
    if search is not None:
        search.add(snippet.id, snippet.command, snippet.description)
    logger.info("captured snippet %d", snippet.id)


def install_hook(shell: str, rc_path: Path | None = None) -> Path:
    """Append the capture hook to the shell's rc file. Idempotent.

    Returns the rc file path written. Raises ``ValueError`` for unsupported
    shells. ``rc_path`` overrides the default ``~/.zshrc`` / ``~/.bashrc``.
    """
    shell = shell.lower()
    if shell not in _HOOK_BLOCKS:
        raise ValueError(f"unsupported shell: {shell!r} (expected zsh or bash)")
    rc_file = rc_path or (Path.home() / _RC_FILES[shell])
    existing = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    if _MARKER in existing:
        return rc_file
    with rc_file.open("a", encoding="utf-8") as handle:
        handle.write(_HOOK_BLOCKS[shell])
    return rc_file
