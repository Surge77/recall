"""SQLite storage for Recall snippets, with FTS5 keyword search.

This module owns *all* SQLite access. No other module issues raw SQL. Every
query is parameterized — user-supplied text never reaches the SQL string. The
database is a single portable file so it can be copied or synced verbatim.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snippets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    command     TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    source      TEXT NOT NULL DEFAULT 'manual',
    created_at  TEXT NOT NULL,
    run_count   INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS snippets_fts USING fts5(
    command, description,
    content='snippets', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS snippets_ai AFTER INSERT ON snippets BEGIN
    INSERT INTO snippets_fts(rowid, command, description)
    VALUES (new.id, new.command, new.description);
END;

CREATE TRIGGER IF NOT EXISTS snippets_ad AFTER DELETE ON snippets BEGIN
    INSERT INTO snippets_fts(snippets_fts, rowid, command, description)
    VALUES ('delete', old.id, old.command, old.description);
END;

CREATE TRIGGER IF NOT EXISTS snippets_au AFTER UPDATE ON snippets BEGIN
    INSERT INTO snippets_fts(snippets_fts, rowid, command, description)
    VALUES ('delete', old.id, old.command, old.description);
    INSERT INTO snippets_fts(rowid, command, description)
    VALUES (new.id, new.command, new.description);
END;
"""


@dataclass
class Snippet:
    """A single stored command and its generated metadata."""

    id: int
    command: str
    description: str
    tags: list[str]
    source: str
    created_at: datetime
    run_count: int


def _fts_match_query(query: str) -> str:
    """Build a safe FTS5 MATCH string from raw user input.

    Each whitespace token is wrapped as a quoted FTS5 string so that shell
    metacharacters (``$``, ``-``, ``(`` ...) cannot be parsed as FTS5 operators.
    """
    tokens = [token for token in query.split() if token]
    escaped = [f'"{token.replace(chr(34), "")}"' for token in tokens]
    return " ".join(escaped)


def _row_to_snippet(row: sqlite3.Row) -> Snippet:
    return Snippet(
        id=row["id"],
        command=row["command"],
        description=row["description"],
        tags=json.loads(row["tags"]),
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        run_count=row["run_count"],
    )


class SnippetDB:
    """Repository over the snippets SQLite database."""

    def __init__(self, db_path: Path) -> None:
        """Open (creating if needed) the database at ``db_path``."""
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection that commits on success and always closes.

        ``sqlite3``'s own ``with conn`` block only manages the transaction — it
        does not close the connection — so closing is done explicitly here.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def add(
        self,
        command: str,
        description: str,
        tags: list[str] | None = None,
        source: str = "manual",
    ) -> Snippet:
        """Insert a new snippet and return it. Raises on duplicate command."""
        created_at = datetime.now(timezone.utc).isoformat()
        with self._tx() as conn:
            cursor = conn.execute(
                "INSERT INTO snippets (command, description, tags, source, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (command, description, json.dumps(tags or []), source, created_at),
            )
            snippet_id = int(cursor.lastrowid)
        created = self.get(snippet_id)
        assert created is not None  # just inserted
        return created

    def get(self, snippet_id: int) -> Snippet | None:
        """Return the snippet with ``snippet_id``, or None if absent."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM snippets WHERE id = ?", (snippet_id,)
            ).fetchone()
        return _row_to_snippet(row) if row else None

    def delete(self, snippet_id: int) -> bool:
        """Delete by id. Return True if a row was removed."""
        with self._tx() as conn:
            cursor = conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
            return cursor.rowcount > 0

    def list_all(self) -> list[Snippet]:
        """Return all snippets, newest first."""
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM snippets ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [_row_to_snippet(row) for row in rows]

    def keyword_search(self, query: str) -> list[Snippet]:
        """Full-text search over command + description, ranked by relevance."""
        match = _fts_match_query(query)
        if not match:
            return []
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT s.* FROM snippets_fts f "
                "JOIN snippets s ON s.id = f.rowid "
                "WHERE snippets_fts MATCH ? ORDER BY rank",
                (match,),
            ).fetchall()
        return [_row_to_snippet(row) for row in rows]

    def update_description(self, snippet_id: int, description: str) -> bool:
        """Replace a snippet's description. Return True if a row was updated.

        The ``snippets_au`` trigger keeps the FTS5 index in sync automatically.
        """
        with self._tx() as conn:
            cursor = conn.execute(
                "UPDATE snippets SET description = ? WHERE id = ?",
                (description, snippet_id),
            )
            return cursor.rowcount > 0

    def increment_run_count(self, command: str) -> None:
        """Bump ``run_count`` for an existing command. No-op if absent."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE snippets SET run_count = run_count + 1 WHERE command = ?",
                (command,),
            )

    def exists(self, command: str) -> bool:
        """Return True if a snippet with this exact command is stored."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT 1 FROM snippets WHERE command = ? LIMIT 1", (command,)
            ).fetchone()
        return row is not None
