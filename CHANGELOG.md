# Changelog

All notable changes to Recall are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- A ChromaDB failure during `add` / `delete` / `redescribe` no longer aborts the
  operation or prints a traceback — semantic-index updates are now best-effort,
  consistent with the index being a rebuildable cache.

## [0.2.0] - 2026-05-31

### Added
- **PowerShell auto-capture** — native hook for PowerShell 7+ via PSReadLine's
  `AddToHistoryHandler`; `recall install` resolves the profile through
  `$PROFILE` so Windows users no longer need WSL/Git Bash.
- **`recall redescribe`** — regenerate AI descriptions for stored snippets
  (all, or a single id), e.g. after enabling a better LLM provider.
- **Configurable capture blocklist** — `trivial_commands` in `config.toml`
  lets you skip your own noise commands without editing source.

### Changed
- Descriptions are now complete phrases: output is trimmed on the first
  sentence (never mid-word) and a leading "This command…" filler is stripped.
- `list` / `search` tables draw a separator line between rows for readability.

### Fixed
- Silenced the HuggingFace `HF_TOKEN` warning and model-loading progress bars
  that leaked into the terminal on every `search` / `redescribe`.

### Internal
- Extracted rich rendering helpers into `recall/render.py` to keep `main.py`
  within the 300-line limit.

## [0.1.0] - 2026-05-31

First working release. Everything runs locally and free by default.

### Added
- Silent auto-capture of long shell commands via a zsh / bash hook.
- AI descriptions with pluggable providers: local Ollama (default), optional
  Claude API, and an always-available heuristic fallback.
- Single-file SQLite storage with FTS5 keyword search.
- Local semantic search over a ChromaDB collection (optional `semantic` extra).
- Full CLI: `search`, `list`, `add`, `delete`, `sync`, `install`, `version`.
- One-step installer (`scripts/install.sh`).

[Unreleased]: https://github.com/Surge77/recall/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Surge77/recall/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Surge77/recall/releases/tag/v0.1.0
