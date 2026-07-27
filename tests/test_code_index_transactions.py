from database.memory import (
    _insert_code_unit_with_cursor,
    delete_code_index_for_file,
    reconcile_code_index_scope,
    replace_code_index_for_file,
    save_code_unit,
    search_code_units,
    search_dependencies,
)
import pytest


class FakeCursor:
    def __init__(
        self,
        *,
        fail_on_execute: int | None = None,
        rowcounts: list[int | None] | None = None,
        rows: list[tuple] | None = None,
    ):
        self.executions = []
        self.fail_on_execute = fail_on_execute
        self.rowcounts = list(rowcounts or [])
        self.rowcount = 0
        self.rows = list(rows or [])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executions.append((query, params))

        index = len(self.executions) - 1
        if index < len(self.rowcounts):
            self.rowcount = self.rowcounts[index]
        else:
            self.rowcount = 0

        if (
            self.fail_on_execute is not None
            and len(self.executions)
            == self.fail_on_execute
        ):
            raise RuntimeError("simulated database failure")

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(
        self,
        *,
        fail_on_execute: int | None = None,
        rowcounts: list[int | None] | None = None,
        rows: list[tuple] | None = None,
    ):
        self.cursor_instance = FakeCursor(
            fail_on_execute=fail_on_execute,
            rowcounts=rowcounts,
            rows=rows,
        )
        self.commit_count = 0
        self.rollback_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

def test_replace_file_uses_one_transaction(
    monkeypatch,
):
    conn = FakeConnection()
    connection_calls = 0
    scope = "code-index-example-" + "a" * 32

    def fake_get_conn():
        nonlocal connection_calls
        connection_calls += 1
        return conn

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        fake_get_conn,
    )

    inserted = replace_code_index_for_file(
        file_path="core/router.py",
        index_scope=scope,
        code_units=[
            {
                "kind": "function",
                "name": "route",
                "content": "def route(): pass",
                "embedding": [0.0] * 384,
            }
        ],
        dependencies=[
            {
                "target_file": "core/config.py",
                "dependency_type": "import",
            }
        ],
    )

    assert inserted == 1
    assert connection_calls == 1
    assert conn.commit_count == 1
    assert conn.rollback_count == 0

    for _, params in conn.cursor_instance.executions:
        assert scope in params

def test_replace_file_rolls_back_on_failure(
    monkeypatch,
):
    conn = FakeConnection(fail_on_execute=4)

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated database failure",
    ):
        replace_code_index_for_file(
            file_path="core/router.py",
            index_scope="code-index-example-" + "a" * 32,
            code_units=[
                {
                    "kind": "function",
                    "name": "route",
                    "content": "def route(): pass",
                    "embedding": [0.0] * 384,
                }
            ],
            dependencies=[
                {
                    "target_file": "core/config.py",
                    "dependency_type": "import",
                }
            ],
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1

def test_empty_replacement_clears_stale_rows(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    inserted = replace_code_index_for_file(
        file_path="core/empty.py",
        index_scope="code-index-example-" + "b" * 32,
        code_units=[],
        dependencies=[],
    )

    assert inserted == 0
    assert len(conn.cursor_instance.executions) == 2
    assert conn.commit_count == 1
    assert conn.rollback_count == 0

def test_replace_file_is_noop_when_db_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: False,
    )

    def forbidden_connection():
        raise AssertionError("connection must not be opened")

    monkeypatch.setattr(
        "database.memory.get_conn",
        forbidden_connection,
    )

    result = replace_code_index_for_file(
        file_path="core/router.py",
        index_scope="code-index-example-" + "c" * 32,
        code_units=[],
        dependencies=[],
    )

    assert result == 0

def test_replace_file_rejects_missing_scope(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )

    with pytest.raises(
        ValueError,
        match="index_scope is required",
    ):
        replace_code_index_for_file(
            file_path="core/router.py",
            index_scope="",
            code_units=[],
            dependencies=[],
        )

def test_delete_file_uses_one_transaction(
    monkeypatch,
):
    conn = FakeConnection()
    scope = "code-index-example-" + "d" * 32

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = delete_code_index_for_file(
        file_path="core/deleted.py",
        index_scope=scope,
    )

    executions = conn.cursor_instance.executions

    assert result is True
    assert len(executions) == 3
    assert conn.commit_count == 1
    assert conn.rollback_count == 0

    assert "DELETE FROM code_units" in executions[0][0]
    assert executions[0][1] == (
        "core/deleted.py",
        scope,
    )

    assert "source_file = %s" in executions[1][0]
    assert executions[1][1] == (
        "core/deleted.py",
        scope,
    )

    assert "target_file = %s" in executions[2][0]
    assert executions[2][1] == (
        "core/deleted.py",
        scope,
    )

def test_delete_file_rolls_back_on_failure(
    monkeypatch,
):
    conn = FakeConnection(fail_on_execute=2)

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated database failure",
    ):
        delete_code_index_for_file(
            file_path="core/deleted.py",
            index_scope="code-index-example-" + "d" * 32,
        )

    assert conn.commit_count == 0
    assert conn.rollback_count == 1

def test_delete_file_is_noop_when_db_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: False,
    )

    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: (_ for _ in ()).throw(
            AssertionError("connection must not be opened")
        ),
    )

    result = delete_code_index_for_file(
        file_path="core/deleted.py",
        index_scope="code-index-example-" + "e" * 32,
    )

    assert result is False

def test_delete_file_rejects_missing_scope(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )

    with pytest.raises(
        ValueError,
        match="index_scope is required",
    ):
        delete_code_index_for_file(
            file_path="core/deleted.py",
            index_scope="",
        )

def test_delete_file_rolls_back_when_inbound_cleanup_fails(
    monkeypatch,
):
    conn = FakeConnection(fail_on_execute=3)

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated database failure",
    ):
        delete_code_index_for_file(
            file_path="core/deleted.py",
            index_scope="code-index-example-" + "e" * 32,
        )

    assert len(conn.cursor_instance.executions) == 3
    assert conn.commit_count == 0
    assert conn.rollback_count == 1

def test_inbound_cleanup_is_scoped_by_target_file_and_scope(
    monkeypatch,
):
    from database.memory import (
        _delete_inbound_dependencies_for_file_with_cursor,
    )

    cursor = FakeCursor()
    scope = "code-index-example-" + "f" * 32

    _delete_inbound_dependencies_for_file_with_cursor(
        cursor,
        target_file="core/config.py",
        project_tag=scope,
    )

    assert len(cursor.executions) == 1

    query, params = cursor.executions[0]

    assert "target_file = %s" in query
    assert "project_tag = %s" in query
    assert "source_file = %s" not in query
    assert params == (
        "core/config.py",
        scope,
    )

def test_replace_file_does_not_delete_inbound_dependencies(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    replace_code_index_for_file(
        file_path="core/config.py",
        index_scope="code-index-example-" + "a" * 32,
        code_units=[],
        dependencies=[],
    )

    queries = [
        query
        for query, _params
        in conn.cursor_instance.executions
    ]

    assert len(queries) == 2
    assert any(
        "DELETE FROM code_units" in query
        for query in queries
    )
    assert any(
        "source_file = %s" in query
        for query in queries
    )
    assert not any(
        "target_file = %s" in query
        for query in queries
    )

def test_replace_file_does_not_trust_dependency_source_file(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    replace_code_index_for_file(
        file_path="core/router.py",
        index_scope="code-index-example-" + "f" * 32,
        code_units=[],
        dependencies=[
            {
                "source_file": "other_project/evil.py",
                "target_file": "core/config.py",
                "dependency_type": "import",
            }
        ],
    )

    _, dependency_params = (
        conn.cursor_instance.executions[2]
    )

    assert dependency_params[0] == "core/router.py"

def test_save_code_unit_delegates_to_cursor_primitive(
    monkeypatch,
):
    conn = FakeConnection()
    captured = {}

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    def fake_insert(cursor, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "database.memory._insert_code_unit_with_cursor",
        fake_insert,
    )

    save_code_unit(
        file_path="core/router.py",
        kind="function",
        name="route",
        content="def route(): pass",
        embedding=[0.0] * 384,
        project_tag="scope",
    )

    assert captured["file_path"] == "core/router.py"
    assert captured["project_tag"] == "scope"
    assert conn.commit_count == 1


def test_code_unit_cursor_primitive_preserves_null_embedding():
    cursor = FakeCursor()

    _insert_code_unit_with_cursor(
        cursor,
        file_path="core/router.py",
        kind="function",
        name="route",
        content="def route(): pass",
        embedding=None,
        project_tag="scope",
    )

    assert len(cursor.executions) == 1
    query, params = cursor.executions[0]
    assert "%s::vector" in query
    assert params[4] is None


def test_reconcile_scope_uses_one_transaction(
    monkeypatch,
):
    conn = FakeConnection(rowcounts=[3, 2])

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = reconcile_code_index_scope(
        index_scope="scope",
        current_files={
            "core/router.py",
            "core/config.py",
        },
    )

    assert result == {
        "dependencies_deleted": 3,
        "code_units_deleted": 2,
    }
    assert len(conn.cursor_instance.executions) == 2
    assert conn.commit_count == 1
    assert conn.rollback_count == 0

    dependency_query, dependency_params = (
        conn.cursor_instance.executions[0]
    )
    unit_query, unit_params = (
        conn.cursor_instance.executions[1]
    )

    assert "DELETE FROM code_dependencies" in dependency_query
    assert "project_tag = %s" in dependency_query
    assert "source_file = ANY" in dependency_query
    assert "target_file = ANY" in dependency_query
    assert dependency_params == (
        "scope",
        ["core/config.py", "core/router.py"],
        ["core/config.py", "core/router.py"],
    )

    assert "DELETE FROM code_units" in unit_query
    assert "project_tag = %s" in unit_query
    assert "file_path = ANY" in unit_query
    assert unit_params == (
        "scope",
        ["core/config.py", "core/router.py"],
    )


def test_reconcile_scope_deletes_stale_sources_and_targets(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    reconcile_code_index_scope(
        index_scope="scope",
        current_files={"core/current.py"},
    )

    dependency_query, _ = (
        conn.cursor_instance.executions[0]
    )

    assert "source_file = ANY" in dependency_query
    assert " OR (" in dependency_query
    assert "target_file = ANY" in dependency_query


def test_reconcile_scope_preserves_external_null_targets(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    reconcile_code_index_scope(
        index_scope="scope",
        current_files={"core/current.py"},
    )

    dependency_query, _ = (
        conn.cursor_instance.executions[0]
    )

    assert "target_file IS NOT NULL" in dependency_query


def test_reconcile_scope_sorts_membership_deterministically(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    reconcile_code_index_scope(
        index_scope="scope",
        current_files={
            "zeta.py",
            "core\\router.py",
            "alpha.py",
            "   ",
        },
    )

    dependency_params = (
        conn.cursor_instance.executions[0][1]
    )
    unit_params = conn.cursor_instance.executions[1][1]
    expected_files = [
        "alpha.py",
        "core/router.py",
        "zeta.py",
    ]

    assert dependency_params[1] == expected_files
    assert dependency_params[2] == expected_files
    assert unit_params[1] == expected_files


def test_reconcile_scope_rejects_empty_membership(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )

    with pytest.raises(
        ValueError,
        match="current_files must not be empty",
    ):
        reconcile_code_index_scope(
            index_scope="scope",
            current_files={"", "   "},
        )


def test_reconcile_scope_rejects_missing_scope(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )

    with pytest.raises(
        ValueError,
        match="index_scope is required",
    ):
        reconcile_code_index_scope(
            index_scope="",
            current_files={"core/router.py"},
        )


def test_reconcile_scope_rolls_back_on_unit_cleanup_failure(
    monkeypatch,
):
    conn = FakeConnection(fail_on_execute=2)

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated database failure",
    ):
        reconcile_code_index_scope(
            index_scope="scope",
            current_files={"core/router.py"},
        )

    assert len(conn.cursor_instance.executions) == 2
    assert conn.commit_count == 0
    assert conn.rollback_count == 1


def test_reconcile_scope_is_noop_when_db_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: (_ for _ in ()).throw(
            AssertionError("connection must not be opened")
        ),
    )

    result = reconcile_code_index_scope(
        index_scope="",
        current_files=set(),
    )

    assert result == {
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
    }


def test_reconcile_scope_clamps_negative_rowcounts(
    monkeypatch,
):
    conn = FakeConnection(rowcounts=[-1, None])

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = reconcile_code_index_scope(
        index_scope="scope",
        current_files={"core/router.py"},
    )

    assert result == {
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
    }


def test_scoped_code_search_excludes_null_embeddings(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory._embed_text",
        lambda _query: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = search_code_units(
        "router",
        limit=4,
        project_tag="scope",
    )

    query, params = conn.cursor_instance.executions[0]

    assert result == []
    assert "WHERE project_tag = %s" in query
    assert "AND embedding IS NOT NULL" in query
    assert params == (
        "[0.1, 0.2]",
        "scope",
        "[0.1, 0.2]",
        4,
    )


def test_unscoped_code_search_excludes_null_embeddings(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory._embed_text",
        lambda _query: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = search_code_units(
        "router",
        limit=4,
    )

    query, params = conn.cursor_instance.executions[0]

    assert result == []
    assert "WHERE embedding IS NOT NULL" in query
    assert "project_tag = %s" not in query
    assert params == (
        "[0.1, 0.2]",
        "[0.1, 0.2]",
        4,
    )


def test_scoped_dependency_search_excludes_null_embeddings(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory._embed_text",
        lambda _query: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = search_dependencies(
        "router",
        limit=6,
        project_tag="scope",
    )

    query, params = conn.cursor_instance.executions[0]
    top_files_query = query.split(
        "SELECT source_file",
        maxsplit=1,
    )[0]

    assert result == []
    assert "WHERE project_tag = %s" in top_files_query
    assert "AND embedding IS NOT NULL" in top_files_query
    assert params == (
        "scope",
        "[0.1, 0.2]",
        "scope",
        6,
    )


def test_unscoped_dependency_search_excludes_null_embeddings(
    monkeypatch,
):
    conn = FakeConnection()

    monkeypatch.setattr(
        "database.memory.db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "database.memory._embed_text",
        lambda _query: [0.1, 0.2],
    )
    monkeypatch.setattr(
        "database.memory.get_conn",
        lambda: conn,
    )

    result = search_dependencies(
        "router",
        limit=6,
    )

    query, params = conn.cursor_instance.executions[0]
    top_files_query = query.split(
        "SELECT source_file",
        maxsplit=1,
    )[0]

    assert result == []
    assert "WHERE embedding IS NOT NULL" in top_files_query
    assert "project_tag = %s" not in top_files_query
    assert params == (
        "[0.1, 0.2]",
        6,
    )

