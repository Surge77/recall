# ADR-0003: Single-file SQLite storage with FTS5 + optional embeddings

- **Status:** Accepted
- **Date:** 2026-05-31

## Problem

Recall must store snippets durably, sync trivially across machines, and support
both exact-term and meaning-based search — while keeping the stack free, local,
and low-friction.

## Options

**Storage**

1. Plain JSON / TOML file — simple, but no indexed search and awkward concurrent
   writes from a background hook.
2. SQLite single file — indexed, transactional, zero-infra, trivially portable.
3. Client/server DB (Postgres) — overkill; violates zero-infra and portability.

**Search**

1. FTS5 only — instant, built in, but literal: misses paraphrases.
2. Embeddings only — meaning-aware, but needs a model download + CPU and adds a
   heavy dependency (`torch`).
3. FTS5 floor + optional embeddings enhancement.

## Decision

- **Storage:** SQLite (`recall.db`), a single portable file. FTS5 stays in sync
  with the main table via triggers.
- **Search:** FTS5 keyword search is always available and is the fallback.
  Semantic search (ChromaDB + `sentence-transformers`, model `all-MiniLM-L6-v2`)
  lives behind the optional `semantic` extra. The embedded text is
  `"{command} {description}"`. The Chroma index is a derived cache, rebuildable
  from the DB via `sync_from_db`.

## Reason

SQLite gives durability, transactions, and one-file portability for free — copy
`recall.db` and you have moved everything. FTS5 ships with SQLite, so basic
search has zero extra cost. Embeddings deliver the "search in your own words"
headline feature but pull in large dependencies, so they are opt-in; the tool
remains fully functional without them.

## Tradeoffs

- Two indexes to keep coherent. Mitigated: FTS5 is trigger-maintained; Chroma is
  a rebuildable cache, not a source of truth.
- `sentence-transformers` is a large install (`torch`) and downloads ~90 MB on
  first run — hence the optional extra and graceful FTS5 fallback.
- SQLite single-writer semantics mean the background capture hook must keep
  writes short (it does: one insert or one counter bump).
