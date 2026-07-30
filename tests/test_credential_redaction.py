"""Credential-leak regression coverage for INDEX.1D.2A."""
from __future__ import annotations

import copy
import json
import sys
import traceback
from types import SimpleNamespace

import pytest

from core.credential_redaction import (
    REDACTED_DATABASE_URL,
    redact_credentials,
)


DATABASE_URL = (
    "postgresql://db-user:db-password@example.test:5432/cattus"
    "?sslmode=require&token=database-token"
)


def _assert_secrets_absent(text: str) -> None:
    assert DATABASE_URL not in text
    assert "db-user" not in text
    assert "db-password" not in text
    assert "database-token" not in text


def test_postgres_url_masks_userinfo_and_query_values():
    safe = redact_credentials(
        f"connection failed for {DATABASE_URL}"
    )

    _assert_secrets_absent(safe)
    assert "example.test:5432/cattus" in safe
    assert "postgresql://***:***@" in safe


def test_redactor_handles_postgres_alias_and_driver_scheme():
    text = (
        "postgres://alice:hunter2@localhost/app "
        "postgresql+psycopg://bob:token@db.internal/app"
    )

    safe = redact_credentials(text)

    assert "alice" not in safe
    assert "hunter2" not in safe
    assert "bob" not in safe
    assert "token@db.internal" not in safe
    assert safe.count("***:***@") == 2


def test_malformed_database_url_fails_closed():
    safe = redact_credentials(
        "could not parse postgresql://user:password@"
    )

    assert safe == f"could not parse {REDACTED_DATABASE_URL}"
    assert "user" not in safe
    assert "password" not in safe


@pytest.mark.parametrize(
    "malformed",
    [
        'postgresql://user:sec"ret@host.test/db',
        "postgresql://user:sec'ret@host.test/db",
        "postgresql://user:sec ret@host.test/db",
    ],
)
def test_known_malformed_database_url_fails_closed(
    malformed,
):
    safe = redact_credentials(
        f"connection failed for {malformed}",
        known_secrets=(malformed,),
    )

    assert safe == (
        f"connection failed for {REDACTED_DATABASE_URL}"
    )
    assert "user" not in safe
    assert "sec" not in safe
    assert "ret" not in safe


def test_sensitive_assignments_are_redacted_but_safe_text_remains():
    safe = redact_credentials(
        "database unavailable; retryable=true; "
        "password=hidden token:also-hidden"
    )

    assert "database unavailable" in safe
    assert "retryable=true" in safe
    assert "hidden" not in safe
    assert "also-hidden" not in safe


def test_quoted_and_json_assignments_are_fully_redacted():
    safe = redact_credentials(
        "password='top secret'; "
        '{"password": "json-secret", "token": "abc def"}'
    )

    assert "top secret" not in safe
    assert "json-secret" not in safe
    assert "abc def" not in safe
    assert "password='[REDACTED]'" in safe
    assert '"password": "[REDACTED]"' in safe
    assert '"token": "[REDACTED]"' in safe


def test_redactor_is_deterministic_and_does_not_mutate_inputs():
    secrets = [DATABASE_URL, "standalone-secret"]
    secrets_before = copy.deepcopy(secrets)
    message = (
        f"primary={DATABASE_URL}; secondary=standalone-secret"
    )

    first = redact_credentials(
        message,
        known_secrets=secrets,
    )
    second = redact_credentials(
        message,
        known_secrets=secrets,
    )

    assert first == second
    assert secrets == secrets_before
    assert message.endswith("secondary=standalone-secret")
    _assert_secrets_absent(first)
    assert "standalone-secret" not in first


def test_known_database_url_redacts_detached_credential_values():
    safe = redact_credentials(
        "password authentication failed for user db-user; "
        "database-token was rejected",
        known_secrets=(DATABASE_URL,),
    )

    _assert_secrets_absent(safe)
    assert "authentication failed" in safe
    assert "was rejected" in safe


def test_short_known_components_do_not_corrupt_safe_words():
    configured = "postgresql://app:u@host.test/db?sslmode=require"
    safe = redact_credentials(
        "safe application message; connection unavailable",
        known_secrets=(configured,),
    )

    assert safe == (
        "safe application message; connection unavailable"
    )


def test_database_pool_error_and_traceback_never_include_url(
    monkeypatch,
):
    from database import memory

    def fail_pool(_database_url):
        raise RuntimeError(
            f"driver rejected {DATABASE_URL}; token=database-token"
        )

    monkeypatch.setattr(memory, "DB_ENABLED", True)
    monkeypatch.setattr(memory, "DATABASE_URL", DATABASE_URL)
    monkeypatch.setattr(memory, "_pool", None)
    monkeypatch.setitem(
        sys.modules,
        "psycopg_pool",
        SimpleNamespace(ConnectionPool=fail_pool),
    )

    try:
        memory.get_pool()
    except RuntimeError as exc:
        rendered = f"{exc}\n{traceback.format_exc()}"
    else:
        raise AssertionError("pool construction should fail")

    _assert_secrets_absent(rendered)
    assert "database connection failed" in rendered


@pytest.mark.parametrize(
    "failure_stage",
    ["connection", "enter", "operation"],
)
def test_database_connection_boundary_redacts_all_failure_stages(
    monkeypatch,
    failure_stage,
):
    from database import memory

    class FailingConnectionContext:
        def __enter__(self):
            if failure_stage == "enter":
                raise RuntimeError(
                    f"enter failed for {DATABASE_URL}"
                )
            return object()

        def __exit__(self, exc_type, exc, traceback_value):
            return False

    class FailingPool:
        def connection(self):
            if failure_stage == "connection":
                raise RuntimeError(
                    f"connection failed for {DATABASE_URL}"
                )
            return FailingConnectionContext()

    monkeypatch.setattr(memory, "DATABASE_URL", DATABASE_URL)
    monkeypatch.setattr(
        memory,
        "get_pool",
        lambda: FailingPool(),
    )

    try:
        with memory.get_conn():
            if failure_stage == "operation":
                raise RuntimeError(
                    f"operation failed for {DATABASE_URL}"
                )
    except RuntimeError as exc:
        rendered = f"{exc}\n{traceback.format_exc()}"
    else:
        raise AssertionError("database boundary should fail")

    _assert_secrets_absent(rendered)
    assert "database operation failed" in rendered


def test_health_payload_redacts_database_url(
    monkeypatch,
):
    from core.health import check_db

    def fail_connect(_database_url, **_kwargs):
        raise RuntimeError(
            f"connect failed for {DATABASE_URL}"
        )

    monkeypatch.setenv("DB_ENABLED", "true")
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.delenv("DATABASE_URL_LOCAL", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=fail_connect),
    )

    result = check_db()
    rendered = json.dumps(result, sort_keys=True)

    assert result["status"] == "error"
    _assert_secrets_absent(rendered)
    assert REDACTED_DATABASE_URL in rendered


def test_retriever_stdout_redacts_database_url(
    tmp_path,
    monkeypatch,
    capsys,
):
    from core import retriever

    monkeypatch.setattr(
        retriever,
        "retriever_db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        retriever,
        "search_code_units",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"query failed using {DATABASE_URL}")
        ),
    )

    result = retriever.search_safe_code_units(
        "router",
        repo_path=str(tmp_path),
    )
    rendered = capsys.readouterr().out

    assert result == []
    _assert_secrets_absent(rendered)
    assert "example.test:5432/cattus" in rendered


def test_web_runner_error_payload_redacts_database_url(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "print('fixture')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda *_args, **_kwargs: {
            "intent": "review",
            "complexity": "simple",
        },
    )
    monkeypatch.setattr(
        runner,
        "index_repository",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"index failed using {DATABASE_URL}")
        ),
    )

    result = runner.run_agent_web(
        "review app.py",
        str(repo),
        runtime_environment="local_windows",
    )
    rendered = json.dumps(result, sort_keys=True)

    _assert_secrets_absent(rendered)
    assert "indexing/control failed" in result["answer"]
    assert "example.test:5432/cattus" in result["answer"]


def test_web_route_response_stdout_and_session_are_redacted(
    tmp_path,
    monkeypatch,
    capsys,
):
    from web import app as web_app
    import web.session_store as session_store

    repo = tmp_path / "repo"
    repo.mkdir()
    session_file = tmp_path / "sessions.json"
    monkeypatch.setattr(
        session_store,
        "SESSION_FILE",
        session_file,
    )
    monkeypatch.setattr(
        web_app,
        "build_project_tag",
        lambda _repo_path, _user_tag: "display-label",
    )
    monkeypatch.setattr(
        web_app,
        "_run_mode",
        lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError(f"pipeline failed using {DATABASE_URL}")
        ),
    )

    with web_app.app.test_client() as client:
        response = client.post(
            "/",
            data={
                "query": "review",
                "repo_path": str(repo),
                "mode": "full",
                "agent_mode": "reviewer",
                "patch_style": "safe_minimal",
            },
        )

    response_text = response.get_data(as_text=True)
    stdout_text = capsys.readouterr().out
    session_text = session_file.read_text(encoding="utf-8")

    assert response.status_code == 200
    for rendered in (
        response_text,
        stdout_text,
        session_text,
    ):
        _assert_secrets_absent(rendered)
    assert "example.test:5432/cattus" in response_text
