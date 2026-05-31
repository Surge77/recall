# Recall

> Automated, AI-powered CLI snippet manager. Stop re-googling that one `ffmpeg`
> incantation — Recall captures your long shell commands, describes them in
> plain English, and lets you find them again by *meaning*, not exact wording.

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

## Free by default

The AI description step is pluggable:

| Provider    | Cost          | Needs               | Default  |
| ----------- | ------------- | ------------------- | -------- |
| `ollama`    | Free, offline | Ollama installed    | ✅ yes    |
| `heuristic` | Free, offline | nothing             | fallback |
| `claude`    | Paid (API)    | `ANTHROPIC_API_KEY` | opt-in   |

If no provider is reachable, Recall falls back to a heuristic description and
keeps working — the tool never breaks because an LLM is unavailable.

---

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/Surge77/recall
cd recall
uv sync
uv run recall version
```

Optional extras (installed on demand):

```bash
uv sync --extra ai         # Ollama / Claude description providers
uv sync --extra semantic   # local semantic search (ChromaDB + embeddings)
```

---

## Usage

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
> Windows PowerShell capture is not supported yet; on Windows use WSL or
> Git Bash. All other commands work on every platform.

---

## License

[MIT](LICENSE)
