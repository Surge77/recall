"""Typer CLI entrypoint for Recall.

This is the public command surface. Phases 2-5 extend it with ``search``,
``list``, ``add``, ``delete``, ``install`` and the internal ``_capture`` hook.
For now it exposes ``recall version`` so the package is runnable end to end.
"""

from __future__ import annotations

import typer
from rich.console import Console

from recall import __version__

app = typer.Typer(
    name="recall",
    help="Automated, AI-powered CLI snippet manager.",
    no_args_is_help=True,
    add_completion=False,
)
_console = Console()


@app.callback()
def _main() -> None:
    """Recall — group root. Keeps subcommands (e.g. ``recall version``) intact."""


@app.command()
def version() -> None:
    """Print the installed Recall version."""
    _console.print(f"recall {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
