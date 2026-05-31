# Recall — Architecture

## One-paragraph overview

A shell hook hands each finished command to `recall _capture`. Capture decides
whether the command is worth keeping; if so it asks the **AI layer** for a short
description, stores the pair in a single **SQLite** file, and indexes it for
**semantic search**. Later, `recall search` embeds your query, finds the closest
snippets, and copies the best one to your clipboard. Everything runs locally and
free by default.

## Module map

```
src/recall/
├── __init__.py   # __version__
├── config.py     # lazy get_config(); platformdirs paths; TOML; env API key
├── db.py         # SQLite + FTS5; owns ALL SQL; returns Snippet dataclasses
├── ai.py         # (Phase 2) command -> description; provider protocol
├── search.py     # (Phase 3) ChromaDB + embeddings; same shape as db search
├── capture.py    # (Phase 4) should_capture / capture / install_hook; no import side effects
├── sync.py       # (Phase 5) symlink the DB file to a synced folder
└── main.py       # Typer CLI; the public surface
```

## Data flow

```
        ┌────────────┐   command    ┌─────────────┐
shell ─▶│ shell hook │ ───────────▶ │ recall      │
        └────────────┘  (background) │ _capture    │
                                     └──────┬──────┘
                          should_capture?   │
                            no ─▶ drop /     │ yes
                            increment_run_count
                                             ▼
                                   ┌──────────────────┐
                                   │ ai.generate_     │  (ollama / claude /
                                   │ description()    │   heuristic fallback)
                                   └─────────┬────────┘
                                             ▼
                              db.add() ──▶ SQLite (recall.db)
                                             │  └─ FTS5 triggers keep index live
                                             ▼
                              search.add() ─▶ ChromaDB (embeddings)

query ─▶ recall search ─▶ search.search() ──(ids)──▶ db.get() ─▶ rich output ─▶ clipboard
                              └─ falls back to db.keyword_search() (FTS5)
```

## Boundaries & invariants

1. **`db.py` owns all SQLite.** No raw SQL anywhere else. It returns `Snippet`
   dataclasses, never raw rows.
2. **`ai.py` is the only caller of any LLM API.** It is stateless: command in,
   description out, and it never raises to its caller.
3. **`search.py` mirrors `db.py`'s search shape** so callers can fall back from
   semantic to keyword search transparently.
4. **`capture.py` imports with no side effects** — the shell hook is installed
   separately, never as a consequence of importing the module.
5. **`config.py` is lazy.** Nothing touches the filesystem at import time;
   `get_config()` resolves and caches on first use.
6. **The database is a single portable file.** No sidecar state is required for
   the snippets themselves; copying `recall.db` moves everything. (The Chroma
   index is a derived cache and can be rebuilt from the DB via `sync_from_db`.)

## Why two indexes (FTS5 *and* embeddings)?

- **FTS5** is built into SQLite, instant, and dependency-free — perfect for
  exact-term lookups and as the always-available fallback.
- **Embeddings** capture *meaning*, so "clean docker space" can match
  "remove stopped containers". They cost a model download and CPU, so they live
  behind the optional `semantic` extra.

Recall uses FTS5 as the floor and semantic search as the enhancement. See
[ADR-0003](decisions/0003-storage-and-search.md).

## Configuration & paths

Resolved by `platformdirs`, so they are correct per OS:

| Item | Source | Example (Windows) |
| --- | --- | --- |
| `config.toml` | `user_config_dir("recall")` | `%APPDATA%\recall\config.toml` |
| `recall.db` | `user_data_dir("recall")` | `%LOCALAPPDATA%\recall\recall.db` |
| Chroma index | `user_data_dir("recall")/chroma` | `…\recall\chroma` |
| `ANTHROPIC_API_KEY` | environment only | never written to disk |

Tests set `RECALL_HOME` to a temp dir to isolate all of the above.

## Security posture

- `_capture` receives untrusted command strings. It only **stores** them; it
  never executes or shell-interpolates them.
- No secrets are written to the config file; the Claude key is read from the
  environment.
- All DB access is parameterized — no SQL injection surface.
- These invariants are enforced during the Phase 6 review pass.
