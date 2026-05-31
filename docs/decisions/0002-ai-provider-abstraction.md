# ADR-0002: Pluggable AI description provider (free by default)

- **Status:** Accepted
- **Date:** 2026-05-31

## Problem

Recall auto-generates a plain-English description for each captured command.
The original plan called the Claude API directly. But a core project
requirement is that the stack be **completely free and open source**, and the
Claude API is paid and requires an account/key. Hard-coding it would also make
the tool break offline.

## Options

1. **Claude API only** — fast, cheap, high quality, but **not free**, needs a
   key, fails offline. Contradicts the free requirement.
2. **Local model only (Ollama)** — free and offline, but forces every user to
   install and run Ollama, and produces nothing if Ollama is absent.
3. **No LLM, heuristic only** — free and dependency-free, but lower quality
   descriptions.
4. **Pluggable provider** — a small protocol with a free local default, an
   optional paid provider, and an always-available heuristic fallback.

## Decision

Option 4. `recall.ai` defines a provider protocol:

```python
class DescriptionProvider(Protocol):
    def describe(self, command: str) -> str: ...
```

Implementations: `OllamaProvider` (default), `ClaudeProvider` (opt-in, only when
`ANTHROPIC_API_KEY` is set and `ai.provider = "claude"`), and
`HeuristicProvider` (parses program name + flags, no network). Provider
selection comes from `config.ai_provider`. If the selected provider fails for
any reason (connection, rate limit, auth), `generate_description` degrades to the
heuristic fallback and **never raises**.

## Reason

This satisfies "completely free" out of the box (Ollama or heuristic), keeps the
high-quality Claude path available for those who want it, and guarantees the
capture pipeline never crashes because an LLM is unreachable. The model id is
`claude-haiku-4-5-20251001` (the original plan's `claude-haiku-3` does not
exist).

## Tradeoffs

- More code than a single API call (one protocol, three small classes).
- Heuristic descriptions are noticeably weaker than LLM ones — acceptable as a
  last resort, not the headline experience.
- Ollama users must install Ollama separately (documented in the README).
