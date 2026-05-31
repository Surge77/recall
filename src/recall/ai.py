"""Command-to-description generation.

This is the *only* module that talks to an LLM. Generation is pluggable
(see ADR-0002): a free local Ollama provider by default, an optional Claude
provider, and a network-free heuristic fallback. ``generate_description`` never
raises — any provider failure degrades to the heuristic so the capture pipeline
cannot crash because an LLM is unreachable.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from recall.config import Config, get_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a CLI command documenter. Given a shell command, reply with ONE "
    "short sentence describing what it does. Do not start with 'This command' "
    "or 'This'. No trailing period. Be specific, not generic. Focus on the "
    "effect, not the syntax."
)
# Primary truncation is the first sentence; this is only a safety net for
# runaway output with no sentence boundary.
MAX_WORDS = 25
_FILLER_PREFIXES = ("this command ", "the command ", "this script ", "this ")
_SENTENCE_TERMINATORS = (". ", "! ", "? ")
MAX_TOKENS = 64
OLLAMA_TIMEOUT = 20.0
_SKIP_PREFIX_TOKENS = frozenset({"sudo", "env", "command", "time", "nohup"})
_MAX_BATCH_WORKERS = 8


class DescriptionProvider(Protocol):
    """Anything that turns a command into a description string."""

    def describe(self, command: str) -> str: ...


def _strip_filler_prefix(text: str) -> str:
    """Drop a leading filler clause like 'This command ' so it reads tersely."""
    lowered = text.lower()
    for prefix in _FILLER_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix):]
    return text


def _normalize(text: str) -> str:
    """Produce a clean, complete description.

    Collapses whitespace, drops a filler prefix, keeps the first sentence (so
    output never ends mid-phrase), then applies MAX_WORDS only as a safety net.
    """
    collapsed = _strip_filler_prefix(" ".join(text.strip().split()))
    for terminator in _SENTENCE_TERMINATORS:
        index = collapsed.find(terminator)
        if index != -1:
            collapsed = collapsed[:index]
            break
    words = collapsed.split(" ")
    if len(words) > MAX_WORDS:
        collapsed = " ".join(words[:MAX_WORDS])
    return collapsed.rstrip(".!?,;: ").strip()


def _heuristic_description(command: str) -> str:
    """Derive a description from the program name and subcommand. No network."""
    tokens = command.split()
    index = 0
    while index < len(tokens) and (
        "=" in tokens[index] or tokens[index] in _SKIP_PREFIX_TOKENS
    ):
        index += 1
    if index >= len(tokens):
        return "shell command"
    program = tokens[index].split("/")[-1]
    subcommand = ""
    if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
        subcommand = tokens[index + 1]
    return _normalize(f"run {program} {subcommand}")


# --- thin I/O boundaries (tests stub these) ---------------------------------

def _http_post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:  # pragma: no cover - live network boundary
    """POST JSON and return the decoded response. Lazily imports httpx."""
    import httpx

    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _claude_complete(model: str, api_key: str, system: str, command: str) -> str:  # pragma: no cover - live SDK boundary
    """Call the Anthropic API and return the text. Lazily imports anthropic."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": command}],
    )
    return message.content[0].text


# --- providers --------------------------------------------------------------

class HeuristicProvider:
    """Always-available, network-free fallback provider."""

    def describe(self, command: str) -> str:
        return _heuristic_description(command)


class OllamaProvider:
    """Local, free description provider backed by an Ollama server."""

    def __init__(self, host: str, model: str) -> None:
        self._host = host.rstrip("/")
        self._model = model

    def describe(self, command: str) -> str:
        data = _http_post_json(
            f"{self._host}/api/generate",
            {
                "model": self._model,
                "system": SYSTEM_PROMPT,
                "prompt": command,
                "stream": False,
            },
            OLLAMA_TIMEOUT,
        )
        return _normalize(str(data.get("response", "")))


class ClaudeProvider:
    """Optional, paid description provider backed by the Anthropic API."""

    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key

    def describe(self, command: str) -> str:
        return _normalize(
            _claude_complete(self._model, self._api_key, SYSTEM_PROMPT, command)
        )


def _select_provider(cfg: Config) -> DescriptionProvider:
    """Pick a provider from config, falling back to heuristic when unusable."""
    if cfg.ai_provider == "claude" and cfg.anthropic_api_key:
        return ClaudeProvider(cfg.claude_model, cfg.anthropic_api_key)
    if cfg.ai_provider == "ollama":
        return OllamaProvider(cfg.ollama_host, cfg.ollama_model)
    return HeuristicProvider()


def generate_description(command: str, cfg: Config | None = None) -> str:
    """Describe a command. Never raises; degrades to the heuristic on failure."""
    cfg = cfg or get_config()
    provider = _select_provider(cfg)
    try:
        description = provider.describe(command)
    except Exception as error:  # noqa: BLE001 - boundary: any failure -> fallback
        logger.warning("description provider failed (%s); using heuristic", error)
        return _heuristic_description(command)
    return description or _heuristic_description(command)


def generate_descriptions(commands: list[str], cfg: Config | None = None) -> list[str]:
    """Describe many commands concurrently, preserving input order."""
    if not commands:
        return []
    cfg = cfg or get_config()
    workers = min(_MAX_BATCH_WORKERS, len(commands))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda command: generate_description(command, cfg), commands))
