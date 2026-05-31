"""Tests for the Typer CLI surface (Phase 0)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from recall import __version__
from recall import main
from recall.main import app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_flag_shows_description() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "snippet manager" in result.stdout.lower()


def test_no_args_exits_nonzero_with_help() -> None:
    # no_args_is_help prints help and exits with Click's usage code (2).
    result = runner.invoke(app, [])
    assert result.exit_code != 0
    assert "Usage" in result.stdout


def test_install_reports_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    written = tmp_path / ".zshrc"
    monkeypatch.setattr(main.capture_mod, "install_hook", lambda shell, rc=None: written)
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert "Hook installed" in result.stdout


def test_install_fails_without_detectable_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELL", "")
    monkeypatch.setattr(main, "_powershell_exe", lambda: None)
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 1
    assert "Could not detect" in result.stdout


def test_install_detects_powershell_and_uses_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SHELL", "")  # no unix shell
    monkeypatch.setattr(main, "_powershell_exe", lambda: "pwsh")
    profile = tmp_path / "Microsoft.PowerShell_profile.ps1"
    monkeypatch.setattr(main, "_powershell_profile_path", lambda: profile)
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        main.capture_mod,
        "install_hook",
        lambda shell, rc=None: seen.update(shell=shell, rc=rc) or profile,
    )
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert seen == {"shell": "powershell", "rc": profile}
    assert "powershell" in result.stdout


def test_powershell_exe_prefers_pwsh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main.shutil, "which", lambda name: "/usr/bin/pwsh" if name == "pwsh" else None
    )
    assert main._powershell_exe() == "/usr/bin/pwsh"


def test_powershell_profile_path_parses_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_powershell_exe", lambda: "pwsh")

    class _Result:
        stdout = "C:\\Users\\me\\profile.ps1\n"

    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: _Result())
    assert main._powershell_profile_path() == Path("C:\\Users\\me\\profile.ps1")


def test_powershell_profile_path_none_without_exe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_powershell_exe", lambda: None)
    assert main._powershell_profile_path() is None


def test_powershell_profile_path_handles_subprocess_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_powershell_exe", lambda: "pwsh")

    def _boom(*_a: object, **_k: object) -> object:
        raise OSError("executable vanished")

    monkeypatch.setattr(main.subprocess, "run", _boom)
    assert main._powershell_profile_path() is None


def test_capture_command_is_silent_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main, "_open_db", lambda: object())
    monkeypatch.setattr(main, "_open_search", lambda: None)
    monkeypatch.setattr(
        main.capture_mod, "capture", lambda command, db, search: calls.append(command)
    )
    result = runner.invoke(app, ["_capture", "docker ps -a --format json"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""
    assert calls == ["docker ps -a --format json"]


def test_capture_command_real_glue_noop(recall_home: Path) -> None:
    # Exercises _open_db / _open_search for real; a trivial command no-ops
    # (no LLM, no network) and stores nothing — regardless of whether the
    # optional semantic extra is installed.
    result = runner.invoke(app, ["_capture", "ls"])
    assert result.exit_code == 0
    assert main._open_db().list_all() == []


def test_install_detects_bash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELL", "/bin/bash")
    seen: list[str] = []
    monkeypatch.setattr(
        main.capture_mod,
        "install_hook",
        lambda shell, rc=None: seen.append(shell) or (tmp_path / ".bashrc"),
    )
    result = runner.invoke(app, ["install"])
    assert result.exit_code == 0
    assert seen == ["bash"]


# --- Phase 5: add -----------------------------------------------------------

def test_add_stores_command_with_explicit_description(recall_home: Path) -> None:
    result = runner.invoke(
        app, ["add", "docker system prune -af", "--desc", "remove unused images"]
    )
    assert result.exit_code == 0
    assert "Added" in result.stdout
    db = main._open_db()
    stored = db.keyword_search("prune")
    assert len(stored) == 1
    assert stored[0].description == "remove unused images"
    assert stored[0].source == "manual"


def test_add_parses_comma_separated_tags(recall_home: Path) -> None:
    result = runner.invoke(
        app, ["add", "git rebase -i HEAD~3", "--desc", "interactive rebase", "--tags", "git, vcs"]
    )
    assert result.exit_code == 0
    db = main._open_db()
    snippet = db.keyword_search("rebase")[0]
    assert snippet.tags == ["git", "vcs"]


def test_add_generates_description_when_omitted(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "generate_description", lambda command: "auto text")
    result = runner.invoke(app, ["add", "kubectl get pods --all-namespaces"])
    assert result.exit_code == 0
    db = main._open_db()
    assert db.keyword_search("kubectl")[0].description == "auto text"


def test_add_rejects_duplicate_command(recall_home: Path) -> None:
    runner.invoke(app, ["add", "terraform apply -auto-approve", "--desc", "apply"])
    result = runner.invoke(app, ["add", "terraform apply -auto-approve", "--desc", "again"])
    assert result.exit_code == 1
    assert "already" in result.stdout.lower()


# --- Phase 5: list ----------------------------------------------------------

def test_list_shows_stored_snippets(recall_home: Path) -> None:
    runner.invoke(app, ["add", "docker compose up -d", "--desc", "start containers"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "start containers" in result.stdout


def test_list_empty_reports_no_snippets(recall_home: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No snippets" in result.stdout


def test_list_filters_by_tag(recall_home: Path) -> None:
    runner.invoke(app, ["add", "git push origin main", "--desc", "push", "--tags", "git"])
    runner.invoke(app, ["add", "docker ps --all", "--desc", "containers", "--tags", "docker"])
    result = runner.invoke(app, ["list", "--tag", "docker"])
    assert result.exit_code == 0
    assert "containers" in result.stdout
    assert "push" not in result.stdout


# --- Phase 5: delete --------------------------------------------------------

def test_delete_with_yes_removes_snippet(recall_home: Path) -> None:
    runner.invoke(app, ["add", "rm -rf node_modules", "--desc", "clean deps"])
    db = main._open_db()
    snippet_id = db.keyword_search("node_modules")[0].id
    result = runner.invoke(app, ["delete", str(snippet_id), "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.stdout
    assert main._open_db().get(snippet_id) is None


def test_delete_missing_id_reports_error(recall_home: Path) -> None:
    result = runner.invoke(app, ["delete", "999", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_delete_aborts_when_not_confirmed(recall_home: Path) -> None:
    runner.invoke(app, ["add", "kubectl delete pod web", "--desc", "delete pod"])
    db = main._open_db()
    snippet_id = db.keyword_search("kubectl")[0].id
    result = runner.invoke(app, ["delete", str(snippet_id)], input="n\n")
    assert result.exit_code == 0
    assert main._open_db().get(snippet_id) is not None


# --- Phase 5: search --------------------------------------------------------

class _FakeSearch:
    """Stand-in for SemanticSearch returning preset ids."""

    def __init__(self, ids: list[int]) -> None:
        self._ids = ids

    def search(self, query: str, n_results: int = 10) -> list[int]:
        return self._ids


def test_search_uses_semantic_results_and_copies_top_hit(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["add", "docker system prune -af", "--desc", "free disk"])
    db = main._open_db()
    snippet_id = db.keyword_search("prune")[0].id
    monkeypatch.setattr(main, "_open_search", lambda: _FakeSearch([snippet_id]))
    copied: list[str] = []
    monkeypatch.setattr(main, "_copy_to_clipboard", lambda text: copied.append(text))
    result = runner.invoke(app, ["search", "reclaim space"])
    assert result.exit_code == 0
    assert "free disk" in result.stdout
    assert copied == ["docker system prune -af"]


def test_search_falls_back_to_keyword_when_no_semantic(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["add", "tar -czf backup.tgz ./data", "--desc", "compress data"])
    monkeypatch.setattr(main, "_open_search", lambda: None)
    monkeypatch.setattr(main, "_copy_to_clipboard", lambda text: None)
    result = runner.invoke(app, ["search", "backup"])
    assert result.exit_code == 0
    assert "compress data" in result.stdout


def test_search_no_results_reports_cleanly(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "_open_search", lambda: None)
    result = runner.invoke(app, ["search", "nonexistent xyzzy"])
    assert result.exit_code == 0
    assert "No matching" in result.stdout


# --- Phase 5: sync ----------------------------------------------------------

def test_sync_moves_db_and_links_to_target(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["add", "echo hello world from recall", "--desc", "greet"])
    db_path = main.get_config().db_path
    assert db_path.exists()
    target = recall_home / "remote" / "recall.db"
    links: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        main.Path, "symlink_to", lambda self, dest: links.append((self, Path(dest)))
    )
    result = runner.invoke(app, ["sync", "--path", str(target)])
    assert result.exit_code == 0
    assert "Linked" in result.stdout
    assert target.exists()  # local db moved to target
    assert links and links[0][1] == target.resolve()


def test_sync_reports_symlink_failure_human_readably(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["add", "echo a slightly longer command here", "--desc", "x"])
    target = recall_home / "remote" / "recall.db"

    def _boom(self: Path, dest: object) -> None:
        raise OSError("symlinks require Developer Mode")

    monkeypatch.setattr(main.Path, "symlink_to", _boom)
    result = runner.invoke(app, ["sync", "--path", str(target)])
    assert result.exit_code == 1
    assert "symlink" in result.stdout.lower()
    assert "Traceback" not in result.stdout


def test_sync_adopts_existing_target_with_yes(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["add", "echo local data goes away on adopt", "--desc", "local"])
    db_path = main.get_config().db_path
    target = recall_home / "remote" / "recall.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("remote-db", encoding="utf-8")
    monkeypatch.setattr(main.Path, "symlink_to", lambda self, dest: None)
    result = runner.invoke(app, ["sync", "--path", str(target), "--yes"])
    assert result.exit_code == 0
    assert "Linked" in result.stdout
    assert not db_path.exists()  # local discarded in favour of the target


def test_sync_creates_target_when_no_local_db(
    recall_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not main.get_config().db_path.exists()
    target = recall_home / "remote" / "recall.db"
    monkeypatch.setattr(main.Path, "symlink_to", lambda self, dest: None)
    result = runner.invoke(app, ["sync", "--path", str(target)])
    assert result.exit_code == 0
    assert target.exists()
