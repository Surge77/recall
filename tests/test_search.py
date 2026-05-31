"""Tests for the semantic search layer (Phase 3).

Wiring is verified against an in-memory fake collection so no embedding model or
torch is required. A real-embedding test auto-skips when the ``semantic`` extra
is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recall.db import Snippet
from recall.search import SemanticSearch, is_available
from datetime import datetime, timezone


class FakeCollection:
    """Minimal Chroma-collection stand-in with naive lexical ranking."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[str, dict]] = {}

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        for doc_id, document, metadata in zip(ids, documents, metadatas):
            self.store[doc_id] = (document, metadata)

    def delete(self, ids: list[str]) -> None:
        for doc_id in ids:
            self.store.pop(doc_id, None)

    def get(self) -> dict:
        return {"ids": list(self.store.keys())}

    def query(self, query_texts: list[str], n_results: int) -> dict:
        words = query_texts[0].lower().split()
        scored = []
        for doc_id, (document, _meta) in self.store.items():
            score = sum(1 for word in words if word in document.lower())
            if score:
                scored.append((score, int(doc_id)))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return {"ids": [[str(snippet_id) for _s, snippet_id in scored[:n_results]]]}


@pytest.fixture
def search(tmp_path: Path) -> SemanticSearch:
    return SemanticSearch(tmp_path / "chroma", collection=FakeCollection())


def _snippet(snippet_id: int, command: str, description: str) -> Snippet:
    return Snippet(
        id=snippet_id,
        command=command,
        description=description,
        tags=[],
        source="auto",
        created_at=datetime.now(timezone.utc),
        run_count=1,
    )


def test_add_and_search_returns_int_ids(search: SemanticSearch) -> None:
    search.add(1, "docker rm $(docker ps -aq)", "remove stopped docker containers")
    results = search.search("docker containers")
    assert results == [1]
    assert all(isinstance(snippet_id, int) for snippet_id in results)


def test_search_empty_query_returns_empty(search: SemanticSearch) -> None:
    search.add(1, "git push origin main", "push commits to main")
    assert search.search("   ") == []


def test_search_no_match_returns_empty(search: SemanticSearch) -> None:
    search.add(1, "git push origin main", "push commits to main")
    assert search.search("kubernetes") == []


def test_delete_removes_from_results(search: SemanticSearch) -> None:
    search.add(1, "docker ps -a", "list all docker containers")
    search.delete(1)
    assert search.search("docker") == []


def test_search_respects_n_results(search: SemanticSearch) -> None:
    for snippet_id in range(1, 6):
        search.add(snippet_id, f"docker command number {snippet_id}", "docker thing")
    assert len(search.search("docker", n_results=3)) == 3


def test_sync_from_db_rebuilds_collection(search: SemanticSearch) -> None:
    search.add(99, "stale command here", "stale")  # should be wiped by sync
    snippets = [
        _snippet(1, "docker ps -a", "list docker containers"),
        _snippet(2, "git status --short", "show git working tree"),
    ]
    search.sync_from_db(snippets)
    assert search.search("docker") == [1]
    assert search.search("git") == [2]
    assert search.search("stale") == []


def test_sync_from_db_empty_clears(search: SemanticSearch) -> None:
    search.add(1, "docker ps", "list containers")
    search.sync_from_db([])
    assert search.search("docker") == []


def test_is_available_returns_bool() -> None:
    assert isinstance(is_available(), bool)


@pytest.mark.integration
def test_real_embeddings_find_paraphrase(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    pytest.importorskip("sentence_transformers")
    engine = SemanticSearch(tmp_path / "chroma")
    engine.add(1, "docker rm $(docker ps -aq)", "remove stopped docker containers")
    engine.add(2, "git commit -am wip", "commit all changes")
    # Paraphrase that shares no literal words with the stored snippet.
    assert engine.search("clean up docker space")[0] == 1
