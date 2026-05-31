"""Rich rendering and small output utilities for the Recall CLI.

Kept separate from ``main`` so the command layer stays focused on wiring and the
300-line budget. These functions only format and emit output — they never touch
the database or the AI layer.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.table import Table

from recall.db import Snippet

logger = logging.getLogger(__name__)
console = Console()


def parse_tags(raw: str | None) -> list[str]:
    """Split a comma-separated ``--tags`` value into a clean list."""
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def copy_to_clipboard(text: str) -> None:
    """Best-effort clipboard copy; never fails the command if unavailable."""
    try:
        import pyperclip

        pyperclip.copy(text)
    except Exception as error:  # noqa: BLE001 - clipboard is a nicety, not core
        logger.debug("clipboard copy failed: %s", error)


def render_snippets(snippets: list[Snippet]) -> None:
    """Print snippets as a rich table (id, command, description, runs).

    ``show_lines`` draws a rule between rows so each (often multi-line) snippet
    reads as one clearly separated block.
    """
    table = Table(show_lines=True, expand=False)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Command", style="green", overflow="fold")
    table.add_column("Description", overflow="fold")
    table.add_column("Runs", justify="right", no_wrap=True)
    for snippet in snippets:
        table.add_row(
            str(snippet.id), snippet.command, snippet.description, str(snippet.run_count)
        )
    console.print(table)
