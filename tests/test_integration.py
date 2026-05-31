"""End-to-end integration test (Phase 6).

Exercises the real storage stack — a temp SQLite database plus a real ChromaDB
collection — wired together exactly as the CLI wires them. Only the AI provider
is avoided (descriptions are supplied directly), so no network is touched.

Marked ``integration`` and skipped unless the optional ``semantic`` extra is
installed, matching the marker contract in ``pyproject.toml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recall import search as search_mod
from recall.db import SnippetDB
from recall.search import SemanticSearch

pytestmark = pytest.mark.integration

# (command, description) pairs stored verbatim — AI is intentionally bypassed.
_SNIPPETS = [
    ("docker system prune -af", "remove all unused docker images and containers"),
    ("git rebase -i HEAD~3", "interactively rewrite the last three commits"),
    ("kubectl get pods -A", "list pods across all namespaces"),
    ("tar -czf backup.tgz ./data", "compress the data directory into an archive"),
    ("grep -rn TODO src/", "find all TODO comments in the source tree"),
]

# (paraphrase, command it should surface) — none reuse the stored wording.
_PARAPHRASES = [
    ("reclaim disk space used by docker", "docker system prune -af"),
    ("edit my recent git history", "git rebase -i HEAD~3"),
    ("show kubernetes pods in every namespace", "kubectl get pods -A"),
    ("make a compressed backup of the data folder", "tar -czf backup.tgz ./data"),
    ("locate unfinished work markers in code", "grep -rn TODO src/"),
]

_TOP_N = 3


@pytest.mark.skipif(
    not search_mod.is_available(), reason="optional 'semantic' extra not installed"
)
def test_end_to_end_add_search_delete(tmp_path: Path) -> None:
    db = SnippetDB(tmp_path / "recall.db")
    index = SemanticSearch(tmp_path / "chroma")

    ids_by_command: dict[str, int] = {}
    for command, description in _SNIPPETS:
        snippet = db.add(command, description, source="manual")
        index.add(snippet.id, snippet.command, snippet.description)
        ids_by_command[command] = snippet.id

    for query, expected_command in _PARAPHRASES:
        hit_ids = index.search(query, n_results=_TOP_N)
        commands = [s.command for s in (db.get(hid) for hid in hit_ids) if s is not None]
        assert expected_command in commands, f"{query!r} -> {commands}"

    victim_command = "kubectl get pods -A"
    victim_id = ids_by_command[victim_command]
    db.delete(victim_id)
    index.delete(victim_id)

    assert db.get(victim_id) is None
    remaining_ids = index.search("show kubernetes pods in every namespace", n_results=_TOP_N)
    assert victim_id not in remaining_ids


@pytest.mark.skipif(
    not search_mod.is_available(), reason="optional 'semantic' extra not installed"
)
def test_sync_from_db_rebuilds_index(tmp_path: Path) -> None:
    db = SnippetDB(tmp_path / "recall.db")
    for command, description in _SNIPPETS:
        db.add(command, description, source="manual")

    index = SemanticSearch(tmp_path / "chroma")
    index.sync_from_db(db.list_all())

    hit_ids = index.search("reclaim disk space used by docker", n_results=_TOP_N)
    commands = [s.command for s in (db.get(hid) for hid in hit_ids) if s is not None]
    assert "docker system prune -af" in commands
