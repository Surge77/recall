"""Semantic search over snippets, backed by a local ChromaDB collection.

Embeddings (ChromaDB + sentence-transformers) are heavy and live behind the
optional ``semantic`` extra, so the Chroma collection is built lazily and can be
injected — keeping this module importable, and unit-testable, without the extra
installed. Callers fall back to ``db.keyword_search`` (FTS5) when semantic
search is unavailable. See ADR-0003.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from recall.db import Snippet

EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "snippets"
DEFAULT_N_RESULTS = 10


def is_available() -> bool:
    """True if the optional semantic stack (chromadb) is importable."""
    try:
        import chromadb  # noqa: F401
    except ImportError:
        return False
    return True


def _build_collection(chroma_path: Path) -> Any:  # pragma: no cover - needs heavy extra
    """Create or load the persistent Chroma collection with embeddings."""
    import chromadb
    from chromadb.utils import embedding_functions

    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
    return client.get_or_create_collection(
        COLLECTION_NAME, embedding_function=embed_fn
    )


def _document(command: str, description: str) -> str:
    """Text embedded for a snippet — both syntax and meaning contribute."""
    return f"{command} {description}".strip()


class SemanticSearch:
    """Vector search wrapper with the same id-centric shape as ``db`` search."""

    def __init__(self, chroma_path: Path, collection: Any | None = None) -> None:
        """Open the collection at ``chroma_path`` (or use an injected one)."""
        self._collection = (
            collection if collection is not None else _build_collection(chroma_path)
        )

    def add(self, snippet_id: int, command: str, description: str) -> None:
        """Index one snippet under its id."""
        self._collection.add(
            ids=[str(snippet_id)],
            documents=[_document(command, description)],
            metadatas=[{"snippet_id": snippet_id}],
        )

    def delete(self, snippet_id: int) -> None:
        """Remove a snippet from the index."""
        self._collection.delete(ids=[str(snippet_id)])

    def search(self, query: str, n_results: int = DEFAULT_N_RESULTS) -> list[int]:
        """Return snippet ids ranked by semantic similarity to ``query``."""
        if not query.strip():
            return []
        result = self._collection.query(query_texts=[query], n_results=n_results)
        raw_ids = (result.get("ids") or [[]])[0]
        return [int(raw_id) for raw_id in raw_ids]

    def sync_from_db(self, snippets: list[Snippet]) -> None:
        """Rebuild the whole collection from the database (source of truth)."""
        existing = self._collection.get().get("ids", [])
        if existing:
            self._collection.delete(ids=existing)
        if not snippets:
            return
        self._collection.add(
            ids=[str(snippet.id) for snippet in snippets],
            documents=[_document(s.command, s.description) for s in snippets],
            metadatas=[{"snippet_id": snippet.id} for snippet in snippets],
        )
