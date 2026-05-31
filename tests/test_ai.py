"""Tests for the AI description layer (Phase 2).

The network/SDK boundaries (`_http_post_json`, `_claude_complete`) are stubbed —
no real API is ever called.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recall import ai
from recall.config import Config


def _cfg(tmp_path: Path, provider: str = "ollama", api_key: str | None = None) -> Config:
    return Config(
        config_dir=tmp_path,
        data_dir=tmp_path,
        ai_provider=provider,
        _api_key=api_key,
    )


# --- heuristic --------------------------------------------------------------

@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("docker rm $(docker ps -aq)", "run docker rm"),
        ("sudo systemctl restart nginx", "run systemctl restart"),
        ("FOO=bar python script.py", "run python script.py"),
        ("ls -la", "run ls"),
        ("/usr/bin/git commit -m x", "run git commit"),
    ],
)
def test_heuristic_description(command: str, expected: str) -> None:
    assert ai._heuristic_description(command) == expected


def test_heuristic_empty_command() -> None:
    assert ai._heuristic_description("   ") == "shell command"


def test_normalize_trims_and_caps() -> None:
    assert ai._normalize("Remove   all stopped containers.") == "Remove all stopped containers"
    long = " ".join(str(n) for n in range(20))
    assert len(ai._normalize(long).split()) == ai.MAX_WORDS


# --- ollama (default) -------------------------------------------------------

def test_ollama_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ai, "_http_post_json", lambda *a, **k: {"response": "remove stopped docker containers"}
    )
    result = ai.generate_description("docker rm $(docker ps -aq)", _cfg(tmp_path))
    assert result == "remove stopped docker containers"


def test_ollama_connection_error_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> dict:
        raise ConnectionError("no ollama")

    monkeypatch.setattr(ai, "_http_post_json", boom)
    result = ai.generate_description("docker rm $(docker ps -aq)", _cfg(tmp_path))
    assert result == "run docker rm"  # heuristic fallback


def test_ollama_empty_response_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "_http_post_json", lambda *a, **k: {"response": ""})
    assert ai.generate_description("kubectl get pods", _cfg(tmp_path)) == "run kubectl get"


# --- claude (opt-in) --------------------------------------------------------

def test_claude_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "_claude_complete", lambda *a, **k: "list kubernetes pods")
    cfg = _cfg(tmp_path, provider="claude", api_key="sk-test")
    assert ai.generate_description("kubectl get pods", cfg) == "list kubernetes pods"


def test_claude_auth_error_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> str:
        raise RuntimeError("invalid api key")

    monkeypatch.setattr(ai, "_claude_complete", boom)
    cfg = _cfg(tmp_path, provider="claude", api_key="sk-bad")
    assert ai.generate_description("kubectl get pods", cfg) == "run kubectl get"


def test_claude_without_key_uses_heuristic_provider(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, provider="claude", api_key=None)
    assert isinstance(ai._select_provider(cfg), ai.HeuristicProvider)


def test_select_provider_ollama_default(tmp_path: Path) -> None:
    assert isinstance(ai._select_provider(_cfg(tmp_path)), ai.OllamaProvider)


# --- batch ------------------------------------------------------------------

def test_generate_descriptions_preserves_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai, "_http_post_json", lambda url, payload, t: {"response": payload["prompt"]})
    commands = ["docker ps -a", "git status --short", "npm run build --prod"]
    assert ai.generate_descriptions(commands, _cfg(tmp_path)) == commands


def test_generate_descriptions_empty() -> None:
    assert ai.generate_descriptions([]) == []
