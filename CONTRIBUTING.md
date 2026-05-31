# Contributing to Recall

Thanks for your interest! Recall is built in small, test-first phases. Please
keep changes scoped and verified.

## Setup

```bash
uv sync --extra dev
uv run pytest -v
```

## Workflow (test-driven)

1. **Write the failing test first**, then the minimum code to pass it.
2. Keep every module behind its boundary (see
   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):
   - all SQL lives in `db.py`;
   - all LLM calls live in `ai.py`;
   - `capture.py` imports with no side effects.
3. Run the suite before and after your change.

## Quality gates (must pass before commit)

```bash
uv run pytest -v --cov=src/recall --cov-report=term-missing
```

- All tests green.
- Coverage **≥ 80%** (100% for data-validation / business logic).
- Type hints + docstrings on every public function.
- Functions ≤ 40 lines; files ≤ 300 lines.
- No raw SQL outside `db.py`; no hardcoded paths (use `config.py`).
- No secrets in code; the Claude key comes from the environment only.

## Commit format

Conventional, one logical change per commit:

```
Phase N: <description>        # phased build commits
feat(search): add tag filter  # feature commits
fix(db): close leaked connection on error
```

Never commit with failing tests. Never commit `recall.db`, model caches, or the
local `.claude/` development files (they are gitignored).

## Tests live alongside source

`src/recall/db.py` → `tests/test_db.py`. One behavior per test, named for the
behavior (`test_keyword_search_finds_by_description_word`). Mock the LLM and any
network — **no real API calls in tests.** Use the `recall_home` / `db` fixtures
for filesystem isolation.

## Reporting issues

Use the GitHub issue templates. Include your OS, shell, Python version, and the
exact command and output.
