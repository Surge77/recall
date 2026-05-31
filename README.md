# Recall

> Automated, AI-powered CLI snippet manager. Stop re-googling that one `ffmpeg`
> incantation — Recall captures your long shell commands, describes them in
> plain English, and lets you find them again by *meaning*, not exact wording.

[![Tests](https://img.shields.io/badge/tests-pytest-blue)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

---

## What it does

1. **Auto-captures** long / complex terminal commands via a shell hook (after
   you run them — zero manual effort).
2. **Describes them automatically** using a local LLM (Ollama, free & offline)
   or, optionally, the Claude API.
3. **Stores everything** in a single portable SQLite file you can copy or sync.
4. **Finds commands semantically** — search *"clean up docker space"* and get
   back `docker rm $(docker ps -aq)` even if you never used those words.

Everything runs **locally and free** by default. No account, no cloud, no
telemetry. The single `recall.db` file is the whole product — copy it to a new
machine and you are done.

---

## Why "free and open source"

The AI description step is **pluggable** (see
[ADR-0002](docs/decisions/0002-ai-provider-abstraction.md)):

| Provider    | Cost            | Needs            | Default |
| ----------- | --------------- | ---------------- | ------- |
| `ollama`    | Free, offline   | Ollama installed | ✅ yes   |
| `heuristic` | Free, offline   | nothing          | fallback |
| `claude`    | Paid (API)      | `ANTHROPIC_API_KEY` | opt-in |

If no provider is reachable, Recall falls back to a heuristic description and
keeps working. **The tool never breaks because an LLM is unavailable.**

---

## Status

🚧 **Early development.** Implemented so far:

- ✅ Phase 0 — project bootstrap, lazy config, `recall version`
- ✅ Phase 1 — SQLite storage + FTS5 keyword search
- ⬜ Phase 2 — AI description providers
- ⬜ Phase 3 — semantic search (ChromaDB + embeddings)
- ⬜ Phase 4 — shell hook & auto-capture
- ⬜ Phase 5 — full CLI (`search`, `list`, `add`, `delete`, `install`, `sync`)
- ⬜ Phase 6 — integration & quality gate
- ⬜ Phase 7 — packaging & one-command install

See the full [Roadmap](docs/ROADMAP.md) and [Architecture](docs/ARCHITECTURE.md).

---

## Install (development)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/Surge77/recall
cd recall
uv sync --extra dev            # core + test deps
uv run recall version
```

Optional extras (installed on demand):

```bash
uv sync --extra ai             # Ollama / Claude description providers
uv sync --extra semantic       # ChromaDB + sentence-transformers (large)
```

---

## Planned usage

```bash
recall install                 # install the shell hook (zsh / bash)
# ... run a long command normally; it is captured silently ...
recall search "docker cleanup" # semantic search, copies top hit to clipboard
recall list --tag docker       # browse saved snippets
recall add "<cmd>" --tags net  # manual add (auto-describes if no --desc)
recall delete 12               # remove a snippet
recall sync --path ~/Dropbox/recall.db   # symlink the DB for cross-machine sync
```

> **Platform note:** the auto-capture hook targets **zsh** and **bash**. Native
> Windows PowerShell capture is tracked as future work; on Windows use WSL or
> Git Bash. All other commands work on every platform.

---

## Testing

```bash
uv run pytest -v --cov=src/recall --cov-report=term-missing
```

The project follows test-driven development with an 80%+ coverage gate. Every
module has a matching test file under `tests/`. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

---

## License

[MIT](LICENSE)
