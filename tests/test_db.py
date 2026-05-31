"""Tests for the SQLite storage layer (Phase 1)."""

from __future__ import annotations

from recall.db import Snippet, SnippetDB

DOCKER_CMD = "docker run -d --restart unless-stopped -p 8080:80 nginx:latest"
DOCKER_DESC = "run nginx container detached on port 8080"


def test_add_creates_record(db: SnippetDB) -> None:
    snippet = db.add(DOCKER_CMD, DOCKER_DESC, tags=["docker"], source="auto")
    assert isinstance(snippet, Snippet)
    assert snippet.id > 0
    assert snippet.command == DOCKER_CMD
    assert snippet.description == DOCKER_DESC
    assert snippet.tags == ["docker"]
    assert snippet.source == "auto"
    assert snippet.run_count == 1


def test_get_returns_none_for_missing_id(db: SnippetDB) -> None:
    assert db.get(999) is None


def test_update_description_changes_text_and_fts(db: SnippetDB) -> None:
    snippet = db.add(DOCKER_CMD, "run docker run")
    assert db.update_description(snippet.id, "start an nginx web server container") is True
    assert db.get(snippet.id).description == "start an nginx web server container"
    # FTS5 reflects the new wording (trigger-synced on UPDATE).
    hits = db.keyword_search("nginx server")
    assert any(hit.id == snippet.id for hit in hits)


def test_update_description_missing_id_returns_false(db: SnippetDB) -> None:
    assert db.update_description(999, "nope") is False


def test_keyword_search_finds_by_command_word(db: SnippetDB) -> None:
    db.add(DOCKER_CMD, DOCKER_DESC)
    results = db.keyword_search("nginx")
    assert len(results) == 1
    assert results[0].command == DOCKER_CMD


def test_keyword_search_finds_by_description_word(db: SnippetDB) -> None:
    db.add(DOCKER_CMD, DOCKER_DESC)
    results = db.keyword_search("detached")
    assert len(results) == 1
    assert results[0].command == DOCKER_CMD


def test_keyword_search_empty_query_returns_empty(db: SnippetDB) -> None:
    db.add(DOCKER_CMD, DOCKER_DESC)
    assert db.keyword_search("   ") == []


def test_keyword_search_tolerates_shell_metacharacters(db: SnippetDB) -> None:
    cmd = "docker rm $(docker ps -aq)"
    db.add(cmd, "remove all stopped docker containers")
    # The query itself contains FTS5-hostile characters; must not raise.
    results = db.keyword_search("$(docker ps -aq)")
    assert any(s.command == cmd for s in results)


def test_exists_true_for_stored_command(db: SnippetDB) -> None:
    db.add(DOCKER_CMD, DOCKER_DESC)
    assert db.exists(DOCKER_CMD) is True


def test_exists_false_for_unknown_command(db: SnippetDB) -> None:
    assert db.exists("ls -la") is False


def test_delete_removes_record(db: SnippetDB) -> None:
    snippet = db.add(DOCKER_CMD, DOCKER_DESC)
    assert db.delete(snippet.id) is True
    assert db.get(snippet.id) is None
    assert db.keyword_search("nginx") == []


def test_delete_returns_false_for_missing_id(db: SnippetDB) -> None:
    assert db.delete(12345) is False


def test_increment_run_count(db: SnippetDB) -> None:
    snippet = db.add(DOCKER_CMD, DOCKER_DESC)
    db.increment_run_count(DOCKER_CMD)
    db.increment_run_count(DOCKER_CMD)
    refreshed = db.get(snippet.id)
    assert refreshed is not None
    assert refreshed.run_count == 3


def test_increment_run_count_unknown_command_is_noop(db: SnippetDB) -> None:
    db.increment_run_count("never-seen")  # must not raise
    assert db.list_all() == []


def test_list_all_orders_newest_first(db: SnippetDB) -> None:
    first = db.add("first long command here for ordering test alpha", "first")
    second = db.add("second long command here for ordering test beta", "second")
    ids = [s.id for s in db.list_all()]
    assert ids[0] == second.id
    assert ids[-1] == first.id


def test_unicode_command_roundtrip(db: SnippetDB) -> None:
    cmd = "echo 'café ☕ñ 日本語' && grep --color=auto 'naïve'"
    snippet = db.add(cmd, "print unicode greeting and grep")
    fetched = db.get(snippet.id)
    assert fetched is not None
    assert fetched.command == cmd
    assert db.keyword_search("unicode")[0].command == cmd
