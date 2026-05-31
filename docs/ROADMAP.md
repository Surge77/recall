# Recall — Build Roadmap

Recall is built in small, independently verifiable phases. **No phase is
considered done until its tests pass and coverage stays ≥ 80%.** Each phase
ends with a commit using the format `Phase N: <description>`.

Legend: ✅ done · 🟡 in progress · ⬜ not started

---

## Phase 0 — Project Bootstrap ✅

**Goal:** a runnable, testable skeleton.

| Deliverable | Notes |
| --- | --- |
| Directory layout, `pyproject.toml` | core deps light; `ai`/`semantic`/`dev` extras |
| `recall.__init__` (`__version__`) | single source of version truth |
| `recall.config` | lazy `get_config()`, `platformdirs`, TOML, env override |
| `recall.main` | Typer app + `recall version` |
| `tests/conftest.py` | `recall_home` + `db` fixtures on temp dirs |

**Verify**

```bash
uv sync --extra dev
uv run recall version          # prints "recall 0.1.0"
uv run pytest -v               # all green
```

**Tests:** `test_cli.py` (version, help, no-args), `test_config.py` (default
file creation, path resolution, env API key, caching, existing-file read).

---

## Phase 1 — Database Layer ✅

**Goal:** all SQLite access behind one module.

`recall.db` exposes the `Snippet` dataclass and `SnippetDB` with:
`add`, `get`, `delete`, `list_all`, `keyword_search` (FTS5),
`increment_run_count`, `exists`.

**Design notes**

- FTS5 external-content table kept in sync via `AFTER INSERT/DELETE/UPDATE`
  triggers — no manual index maintenance.
- Every query is parameterized; user text never enters the SQL string.
- A `_fts_match_query` helper quotes each token so shell metacharacters
  (`$`, `(`, `-`) cannot be parsed as FTS5 operators.
- Connections commit **and close** via a `_tx` context manager (plain
  `with conn` in sqlite3 does not close).

**Tests:** `test_db.py` — happy path, missing ids, search by command word /
description word, empty query, shell-metacharacter query, dedup `exists`,
delete (and its FTS removal), run-count increment + no-op, ordering, unicode
roundtrip.

---

## Phase 2 — AI Description Providers ⬜

**Goal:** turn a raw command into a short plain-English description, free by
default. See [ADR-0002](decisions/0002-ai-provider-abstraction.md).

`recall.ai` exposes `generate_description(command) -> str` over a provider
protocol:

- `OllamaProvider` (default) — POSTs to the local Ollama HTTP API.
- `ClaudeProvider` (opt-in) — used only when `ANTHROPIC_API_KEY` is set and
  provider is `claude`.
- `HeuristicProvider` (always-available fallback) — derives a description from
  the command's program name and flags, no network.

**Error policy:** never raise to the caller. Connection / rate-limit / auth
failures degrade to the heuristic fallback. Batched
`generate_descriptions(commands)` runs concurrently.

**Tests:** `test_ai.py` — mock each provider's transport; assert happy path,
connection error → fallback, rate-limit → fallback, auth error → fallback,
provider selection from config. **No real network calls.**

---

## Phase 3 — Semantic Search ⬜

**Goal:** find commands by meaning. See
[ADR-0003](decisions/0003-storage-and-search.md).

`recall.search.SemanticSearch` wraps a local ChromaDB collection with
`sentence-transformers` (`all-MiniLM-L6-v2`). Methods: `add`, `delete`,
`search(query, n) -> list[int]`, `sync_from_db(snippets)`. Embedded text is
`"{command} {description}"` so both syntax and meaning contribute.

**Degradation:** if the `semantic` extra is not installed, `recall search`
falls back to FTS5 keyword search — the tool still works.

**Tests:** `test_search.py` — paraphrase finds the right snippet, delete removes
it, `sync_from_db` rebuilds; all on a temp Chroma path.

---

## Phase 4 — Shell Hook & Auto-Capture ⬜

**Goal:** capture long commands automatically and silently.

`recall.capture`:

- `should_capture(command) -> bool` — length ≥ `min_command_length`; skip
  trivial commands (`cd`, `ls`, `pwd`, `exit`, `clear`, `history`), comments,
  `recall …` itself, and already-stored commands.
- `capture(command, db, search)` — new → describe + store + index; duplicate →
  `increment_run_count` only. Silent; runs in the background.
- `install_hook(shell)` — append a non-blocking hook for `zsh` (`preexec`) or
  `bash` (`bash-preexec`/`DEBUG` trap).

**Platform note:** native PowerShell capture is future work; Windows users use
WSL/Git Bash. The module imports with **no side effects**.

**Tests:** `test_capture.py` — `should_capture` truth table, capture new vs
duplicate paths (mocked db/ai/search), hook string written to a temp rc file.

---

## Phase 5 — Full CLI ⬜

**Goal:** the complete command surface.

`search` (semantic→FTS5 fallback, rich output, clipboard copy of top hit),
`list [--tag --limit]`, `add [--desc --tags]`, `delete <id>` (confirm),
`install`, `sync --path <file>` (symlink the DB), hidden `_capture <command>`,
`version`. Rich formatting; errors shown human-readable, never as tracebacks.

**Tests:** `test_cli.py` — every command's happy path + primary error via
Typer's `CliRunner`.

---

## Phase 6 — Integration & Quality Gate ⬜

Reviewer pass against `CLAUDE.md`; coverage report; an end-to-end
`test_integration.py` (real temp SQLite + Chroma, mocked AI only): add 5
snippets, find each by paraphrase, delete one, verify gone from both stores.
Gate: all tests pass, coverage ≥ 80%.

---

## Phase 7 — Packaging & Install ⬜

`[project.scripts] recall = recall.main:app` (already wired), `scripts/install.sh`
(checks Python 3.11+, installs `uv`, `uv tool install .`, `recall install`),
README usage + uninstall, final full-suite run.

---

## Definition of Done (whole project)

- `recall install` installs the hook without error.
- After a shell restart, a long command is auto-saved silently.
- `recall search "docker cleanup"` returns the right command via paraphrase.
- `recall list` shows snippets with run counts.
- Copying `recall.db` to another machine just works.
- Full suite green, coverage ≥ 80%.
