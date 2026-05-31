# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-05-31

## Problem

Recall makes several non-obvious technical choices (free-by-default AI, dual
search indexes, single-file storage). Future contributors need to know *why*,
not just *what*, to avoid re-litigating settled tradeoffs.

## Options

1. Keep decisions in commit messages and the README.
2. Maintain lightweight Architecture Decision Records (ADRs) under
   `docs/decisions/`.

## Decision

Use ADRs. Each significant decision gets a short numbered file in
`docs/decisions/` following the format:
**Problem → Options → Decision → Reason → Tradeoffs.**

## Reason

ADRs are greppable, versioned with the code, and give reviewers a stable place
to point at. They are cheap to write and pay off the first time someone asks
"why isn't this just using the Claude API?"

## Tradeoffs

- Slight upkeep cost: superseded decisions must be marked, not deleted.
- Not a substitute for code comments on subtle invariants.
