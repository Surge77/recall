"""Typer CLI entrypoint for Recall.

This is the public command surface: ``search``, ``list``, ``add``, ``delete``,
``sync``, ``install``, ``version`` and the internal ``_capture`` hook. All
output is human-readable; errors never surface as tracebacks.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from recall import __version__
from recall import capture as capture_mod
from recall import search as search_mod
from recall.ai import generate_description
from recall.config import get_config
from recall.db import Snippet, SnippetDB

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_LIMIT = 10
DEFAULT_LIST_LIMIT = 20

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


def _parse_tags(raw: str | None) -> list[str]:
    """Split a comma-separated ``--tags`` value into a clean list."""
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _copy_to_clipboard(text: str) -> None:
    """Best-effort clipboard copy; never fails the command if unavailable."""
    try:
        import pyperclip

        pyperclip.copy(text)
    except Exception as error:  # noqa: BLE001 - clipboard is a nicety, not core
        logger.debug("clipboard copy failed: %s", error)


def _render_snippets(snippets: list[Snippet]) -> None:
    """Print snippets as a rich table (id, command, description, runs)."""
    table = Table(show_lines=False, expand=False)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Command", style="green", overflow="fold")
    table.add_column("Description", overflow="fold")
    table.add_column("Runs", justify="right", no_wrap=True)
    for snippet in snippets:
        table.add_row(
            str(snippet.id), snippet.command, snippet.description, str(snippet.run_count)
        )
    _console.print(table)


def _run_search(
    query: str,
    db: SnippetDB,
    search: search_mod.SemanticSearch | None,
    limit: int,
) -> list[Snippet]:
    """Semantic search hydrated from the DB, falling back to FTS5 keyword search."""
    if search is not None:
        ids = search.search(query, limit)
        hits = [snippet for snippet in (db.get(sid) for sid in ids) if snippet is not None]
        if hits:
            return hits
    return db.keyword_search(query)[:limit]


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


@app.command()
def add(
    command: str,
    desc: str = typer.Option(None, "--desc", "-d", help="Description (auto-generated if omitted)."),
    tags: str = typer.Option(None, "--tags", "-t", help="Comma-separated tags."),
) -> None:
    """Manually store a command snippet."""
    db = _open_db()
    if db.exists(command):
        _console.print(f"[yellow]Already stored:[/yellow] {command}")
        raise typer.Exit(code=1)
    description = desc or generate_description(command)
    snippet = db.add(command, description, tags=_parse_tags(tags), source="manual")
    search = _open_search()
    if search is not None:
        search.add(snippet.id, snippet.command, snippet.description)
    _console.print(f"[green]Added[/green] snippet {snippet.id}: {description}")


@app.command(name="list")
def list_snippets(
    tag: str = typer.Option(None, "--tag", help="Only show snippets with this tag."),
    limit: int = typer.Option(DEFAULT_LIST_LIMIT, "--limit", "-n", help="Max snippets to show."),
) -> None:
    """List stored snippets, newest first."""
    snippets = _open_db().list_all()
    if tag:
        snippets = [snippet for snippet in snippets if tag in snippet.tags]
    snippets = snippets[:limit]
    if not snippets:
        _console.print("No snippets stored yet.")
        return
    _render_snippets(snippets)


@app.command()
def search(
    query: str,
    limit: int = typer.Option(DEFAULT_SEARCH_LIMIT, "--limit", "-n", help="Max results."),
) -> None:
    """Find snippets by meaning (semantic), falling back to keyword search."""
    snippets = _run_search(query, _open_db(), _open_search(), limit)
    if not snippets:
        _console.print("No matching snippets found.")
        return
    _render_snippets(snippets)
    _copy_to_clipboard(snippets[0].command)
    _console.print(f"[dim]Copied to clipboard:[/dim] {snippets[0].command}")


@app.command()
def delete(
    snippet_id: int,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete a snippet by id from both the database and the search index."""
    db = _open_db()
    snippet = db.get(snippet_id)
    if snippet is None:
        _console.print(f"[red]Snippet {snippet_id} not found.[/red]")
        raise typer.Exit(code=1)
    if not yes and not typer.confirm(f"Delete snippet {snippet_id}: {snippet.command!r}?"):
        _console.print("Aborted.")
        return
    db.delete(snippet_id)
    search = _open_search()
    if search is not None:
        search.delete(snippet_id)
    _console.print(f"[green]Deleted[/green] snippet {snippet_id}.")


@app.command()
def sync(
    path: Path = typer.Option(..., "--path", help="Target file in a synced folder."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation when target exists."),
) -> None:
    """Relocate the database to a synced folder and symlink it back.

    If the target already exists it is adopted (the local database is replaced);
    otherwise the local database is moved to the target. Either way ``db_path``
    becomes a symlink so future writes land in the synced location.
    """
    target = path.expanduser().resolve()
    db_path = get_config().db_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not yes and not typer.confirm(
            f"{target} exists; adopt it and discard the local database?"
        ):
            _console.print("Aborted.")
            return
        if db_path.exists() or db_path.is_symlink():
            db_path.unlink()
    elif db_path.exists():
        shutil.move(str(db_path), str(target))
    else:
        target.touch()
    try:
        db_path.symlink_to(target)
    except OSError as error:
        _console.print(
            f"[red]Could not create symlink[/red] at {db_path}: {error}. "
            "On Windows, enable Developer Mode or run from WSL."
        )
        raise typer.Exit(code=1)
    _console.print(f"[green]Linked[/green] {db_path} -> {target}")


@app.command(name="_capture", hidden=True)
def capture_command(command: str) -> None:
    """Internal: invoked by the shell hook after each command. Silent."""
    try:
        capture_mod.capture(command, _open_db(), _open_search())
    except Exception as error:  # noqa: BLE001 - must never disturb the shell
        logger.debug("capture failed: %s", error)


if __name__ == "__main__":  # pragma: no cover
    app()
