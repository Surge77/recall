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

Requires Python 3.11+.

**From PyPI** (simplest — works out of the box, zero config):

```bash
pip install recall-snippets          # or: uv tool install recall-snippets
recall version
recall install                       # wire up the shell hook
```

> **Zero-config:** a fresh install needs no LLM, no API key, and no extra
> downloads. Capture, `add`, `list`, `search` (keyword), `delete` and
> `redescribe` all work immediately. Descriptions use the built-in heuristic
> until you install Ollama or set an API key; search uses SQLite FTS5 keyword
> matching until you add the `semantic` extra. Both are optional upgrades, not
> requirements — see [Free by default](#free-by-default).

**One-step install from source** (checks Python, installs `uv` if missing,
installs the `recall` command globally, and wires the shell hook):

```bash
git clone https://github.com/Surge77/recall
cd recall
./scripts/install.sh
```

**Manual / development install:**

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

# from a PyPI install:
pip install "recall-snippets[ai]"
pip install "recall-snippets[semantic]"
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
recall redescribe              # regenerate AI descriptions (all, or one id)
recall sync --path ~/Dropbox/recall.db   # symlink the DB for cross-machine sync
```

> **Platform note:** the auto-capture hook supports **zsh**, **bash** and
> **PowerShell** (7+, via PSReadLine). On Windows you can run Recall natively in
> PowerShell, or use WSL / Git Bash. All other commands work on every platform.

---

## Configuration

A `config.toml` is created on first run (location is per-OS via `platformdirs`,
e.g. `%LOCALAPPDATA%\recall\config.toml` on Windows). Relevant capture knobs:

```toml
[capture]
min_command_length = 40                                  # skip anything shorter
trivial_commands = ["cd", "ls", "pwd", "exit", "clear", "history"]  # never captured
```

A command is auto-captured only if it is **≥ `min_command_length` characters**,
its first word is **not** in `trivial_commands`, it is not a comment or a
`recall …` call, and it is not already stored. Add your own noise commands
(`git`, `npm`, `clear`, …) to `trivial_commands` to skip them.

---

## Uninstall

```bash
uv tool uninstall recall-snippets
```

Then remove the hook block (marked `# recall auto-capture hook`) from your
`~/.zshrc` or `~/.bashrc`. Your snippets live in a single data file; delete it
only if you want to discard them:

```bash
# Linux:   ~/.local/share/recall/recall.db
# macOS:   ~/Library/Application Support/recall/recall.db
# Windows: %LOCALAPPDATA%\recall\recall.db
```

---

## License

[MIT](LICENSE)
