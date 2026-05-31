"""Typer CLI entrypoint for Recall.

This is the public command surface. Phase 5 extends it with ``search``,
``list``, ``add`` and ``delete``. Today it exposes ``version``, ``install`` and
the internal ``_capture`` hook.
"""

from __future__ import annotations

import logging
import os

import typer
from rich.console import Console

from recall import __version__
from recall import capture as capture_mod
from recall import search as search_mod
from recall.config import get_config
from recall.db import SnippetDB

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="recall",
    help="Automated, AI-powered CLI snippet manager.",
    no_args_is_help=True,
    add_completion=False,
)
_console = Console()


def _open_db() -> SnippetDB:
    return SnippetDB(get_config().db_path)


def _open_search() -> search_mod.SemanticSearch | None:
    """Build the semantic index, or None if the optional extra is unavailable."""
    if not search_mod.is_available():
        return None
    try:
        return search_mod.SemanticSearch(get_config().chroma_path)
    except Exception as error:  # noqa: BLE001 - semantic search is best-effort
        logger.warning("semantic search unavailable: %s", error)
        return None


def _detect_shell() -> str:
    shell_path = os.environ.get("SHELL", "")
    if "zsh" in shell_path:
        return "zsh"
    if "bash" in shell_path:
        return "bash"
    return ""


@app.callback()
def _main() -> None:
    """Recall — group root. Keeps subcommands (e.g. ``recall version``) intact."""


@app.command()
def version() -> None:
    """Print the installed Recall version."""
    _console.print(f"recall {__version__}")


@app.command()
def install() -> None:
    """Install the auto-capture hook into your shell's rc file."""
    shell = _detect_shell()
    if not shell:
        _console.print(
            "[red]Could not detect zsh or bash from $SHELL.[/red] "
            "On Windows, use WSL or Git Bash."
        )
        raise typer.Exit(code=1)
    rc_file = capture_mod.install_hook(shell)
    _console.print(
        f"[green]Hook installed[/green] in {rc_file}. "
        "Restart your terminal to activate."
    )


@app.command(name="_capture", hidden=True)
def capture_command(command: str) -> None:
    """Internal: invoked by the shell hook after each command. Silent."""
    try:
        capture_mod.capture(command, _open_db(), _open_search())
    except Exception as error:  # noqa: BLE001 - must never disturb the shell
        logger.debug("capture failed: %s", error)


if __name__ == "__main__":  # pragma: no cover
    app()
