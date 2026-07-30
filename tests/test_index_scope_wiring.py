from pathlib import Path

from core import indexer as indexer_module
from core import repository_identity
from core.retriever import (
    retrieve_context,
    search_safe_code_units,
    search_dependencies,
)
from core.repository_identity import build_code_index_scope
from core.repository_inventory import (
    CANONICAL_WALK_SITE,
    repository_inventory_from_entries,
)


def test_repository_path_overrides_arbitrary_project_tag(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake_search(query_text, limit, index_scope):
        captured["scope"] = index_scope
        return []

    monkeypatch.setattr(
        "core.retriever.search_code_units",
        fake_search,
    )

    search_safe_code_units(
        "router",
        repo_path=str(tmp_path),
        project_tag="user-display-tag",
    )

    assert captured["scope"] == build_code_index_scope(
        tmp_path
    )

def test_missing_repository_never_runs_global_code_search(
    tmp_path,
    monkeypatch,
):
    called = False

    def fake_search(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        "core.retriever.search_code_units",
        fake_search,
    )

    result = search_safe_code_units(
        "router",
        repo_path=str(tmp_path / "missing"),
        project_tag="display-tag",
    )

    assert result == []
    assert called is False

def test_arbitrary_tag_without_repository_is_rejected(
    monkeypatch,
):
    called = False

    def fake_search(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        "core.retriever.search_code_units",
        fake_search,
    )

    result = search_safe_code_units(
        "router",
        repo_path=None,
        project_tag="ordinary-project-tag",
    )

    assert result == []
    assert called is False

def test_valid_explicit_scope_without_repository_is_accepted(
    tmp_path,
    monkeypatch,
):
    scope = build_code_index_scope(tmp_path)
    captured = {}

    def fake_search(query_text, limit, index_scope):
        captured["scope"] = index_scope
        return []

    monkeypatch.setattr(
        "core.retriever.search_code_units",
        fake_search,
    )

    search_safe_code_units(
        "router",
        repo_path=None,
        index_scope=scope,
    )

    assert captured["scope"] == scope


def test_valid_looking_project_tag_without_repository_is_rejected(
    tmp_path,
    monkeypatch,
):
    called = False

    def fake_search(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        "core.retriever.search_code_units",
        fake_search,
    )

    result = search_safe_code_units(
        "router",
        repo_path=None,
        project_tag=build_code_index_scope(tmp_path),
    )

    assert result == []
    assert called is False


def test_dependency_search_uses_repository_scope(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def fake_search(query_text, limit, index_scope):
        captured["scope"] = index_scope
        return []

    monkeypatch.setattr(
        "core.retriever.search_dependencies_db",
        fake_search,
    )

    result = search_dependencies(
        "router",
        repo_path=str(tmp_path),
        project_tag="display-tag",
    )

    assert result == ""
    assert captured["scope"] == build_code_index_scope(
        tmp_path
    )


def test_top_level_retrieval_never_treats_project_tag_as_scope(
    tmp_path,
    monkeypatch,
):
    semantic_tag = build_code_index_scope(tmp_path)
    captured = []
    monkeypatch.setattr(
        "core.retriever.classify_retrieval_level",
        lambda _query: {
            "level": "meso",
            "confidence": 1.0,
            "scores": {
                "macro": 0,
                "meso": 1,
                "micro": 0,
            },
        },
    )
    monkeypatch.setattr(
        "core.retriever.trace_execution_flow",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "core.retriever.search_safe_code_units",
        lambda *_args, **kwargs: (
            captured.append(kwargs.get("index_scope"))
            or []
        ),
    )
    monkeypatch.setattr(
        "core.retriever.search_dependencies",
        lambda *_args, **kwargs: (
            captured.append(kwargs.get("index_scope"))
            or ""
        ),
    )
    monkeypatch.setattr(
        "core.retriever.trace_call_chain",
        lambda *_args, **_kwargs: "",
    )

    retrieve_context(
        "router",
        repo_path=None,
        project_tag=semantic_tag,
    )

    assert captured == [None, None]


def test_top_level_retrieval_accepts_separate_explicit_scope(
    tmp_path,
    monkeypatch,
):
    scope = build_code_index_scope(tmp_path)
    captured = []
    monkeypatch.setattr(
        "core.retriever.classify_retrieval_level",
        lambda _query: {
            "level": "meso",
            "confidence": 1.0,
            "scores": {
                "macro": 0,
                "meso": 1,
                "micro": 0,
            },
        },
    )
    monkeypatch.setattr(
        "core.retriever.trace_execution_flow",
        lambda *_args, **_kwargs: "",
    )
    monkeypatch.setattr(
        "core.retriever.search_safe_code_units",
        lambda *_args, **kwargs: (
            captured.append(kwargs.get("index_scope"))
            or []
        ),
    )
    monkeypatch.setattr(
        "core.retriever.search_dependencies",
        lambda *_args, **kwargs: (
            captured.append(kwargs.get("index_scope"))
            or ""
        ),
    )
    monkeypatch.setattr(
        "core.retriever.trace_call_chain",
        lambda *_args, **_kwargs: "",
    )

    retrieve_context(
        "router",
        repo_path=None,
        project_tag="semantic-only",
        index_scope=scope,
    )

    assert captured == [scope, scope]


def _write_index_source(
    root: Path,
    rel_path: str,
    content: str,
) -> Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _parsed_with_function(name: str) -> dict:
    return {
        "imports": [],
        "symbols": [{
            "kind": "function",
            "name": name,
            "content": f"def {name}(): pass",
            "execution_flow": [],
            "calls": [],
        }],
        "calls": [],
    }


def _stub_reconciliation_indexer(
    monkeypatch,
    *,
    entries: list[tuple[Path, Path]],
    parsed_by_text: dict[str, dict],
) -> tuple[list[dict], list[str]]:
    replacement_calls: list[dict] = []
    scan_calls: list[str] = []

    class FakeEmbedding:
        def tolist(self):
            return [0.0]

    def scan_once(repo_path):
        scan_calls.append(repo_path)
        return repository_inventory_from_entries(
            repo_path,
            entries,
            traversal_count=1,
            walk_sites=(CANONICAL_WALK_SITE,),
            sort_entries=True,
        )

    def capture_replacement(**kwargs):
        replacement_calls.append(kwargs)
        return len(kwargs["code_units"])

    monkeypatch.setenv(
        "BENCHMARK_SKIP_PHANTOM",
        "true",
    )
    monkeypatch.setenv(
        "BENCHMARK_SKIP_PROJECT_MAP",
        "true",
    )
    monkeypatch.setenv(
        "INDEX_USE_EMBEDDINGS",
        "true",
    )
    monkeypatch.setattr(
        indexer_module,
        "create_repository_inventory",
        scan_once,
    )
    monkeypatch.setattr(
        indexer_module,
        "is_safe_path",
        lambda _path, allowed_roots: bool(allowed_roots),
    )
    monkeypatch.setattr(
        indexer_module,
        "extract_file_text",
        lambda file_path, repo_path: Path(
            file_path
        ).read_text(encoding="utf-8"),
    )
    monkeypatch.setattr(
        indexer_module,
        "parse_code_with_treesitter",
        lambda text, _language: parsed_by_text[text],
    )
    monkeypatch.setattr(
        indexer_module,
        "build_code_units",
        lambda _path, _text: [],
    )
    monkeypatch.setattr(
        indexer_module,
        "get_embedding",
        lambda _content: FakeEmbedding(),
    )
    monkeypatch.setattr(
        indexer_module,
        "code_index_db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        indexer_module,
        "init_db",
        lambda: None,
    )
    monkeypatch.setattr(
        indexer_module,
        "replace_code_index_for_file",
        capture_replacement,
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **_kwargs: {
            "dependencies_deleted": 0,
            "code_units_deleted": 0,
        },
    )
    monkeypatch.setattr(
        repository_identity,
        "build_code_index_scope",
        lambda _repo_path: "test-index-scope",
    )
    monkeypatch.setattr(
        indexer_module,
        "compute_dna",
        lambda _repo_path, **_kwargs: {
            "indent": "spaces",
            "naming": "snake_case",
            "max_line_pref": 88,
        },
    )
    monkeypatch.setattr(
        indexer_module,
        "save_dna",
        lambda _repo_path, _dna: Path("code_dna.json"),
    )

    return replacement_calls, scan_calls


def test_indexer_reconciles_once_after_successful_pass(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )
    reconciliation_calls = []

    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **kwargs: (
            reconciliation_calls.append(kwargs)
            or {
                "dependencies_deleted": 2,
                "code_units_deleted": 1,
            }
        ),
    )

    result = indexer_module.index_repository(
        str(tmp_path),
    )

    assert reconciliation_calls == [{
        "index_scope": "test-index-scope",
        "current_files": {"app.py"},
    }]
    assert result["code_index_reconciliation"] == {
        "performed": True,
        "dependencies_deleted": 2,
        "code_units_deleted": 1,
        "skipped_reason": None,
    }
    assert result["project_tag"] is None
    assert result["index_scope"] == "test-index-scope"


def test_indexer_reconciliation_receives_supported_current_files(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    unsupported_path = _write_index_source(
        tmp_path,
        "settings.yaml",
        "enabled: true",
    )
    skipped_path = _write_index_source(
        tmp_path,
        "session_log.txt",
        "sensitive",
    )
    unsafe_path = _write_index_source(
        tmp_path,
        "unsafe.py",
        "unsafe fixture",
    )
    entries = [
        (app_path, Path("app.py")),
        (unsupported_path, Path("settings.yaml")),
        (skipped_path, Path("session_log.txt")),
        (unsafe_path, Path("unsafe.py")),
    ]
    _replacement_calls, scan_calls = (
        _stub_reconciliation_indexer(
            monkeypatch,
            entries=entries,
            parsed_by_text={
                "app fixture": _parsed_with_function("app"),
            },
        )
    )
    dependency_memberships = []
    reconciliation_calls = []

    monkeypatch.setattr(
        indexer_module,
        "is_safe_path",
        lambda path, allowed_roots: (
            bool(allowed_roots)
            and not path.endswith("unsafe.py")
        ),
    )
    monkeypatch.setattr(
        indexer_module,
        "_build_dependency_rows",
        lambda **kwargs: (
            dependency_memberships.append(
                kwargs["repository_files"]
            )
            or []
        ),
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **kwargs: (
            reconciliation_calls.append(kwargs)
            or {
                "dependencies_deleted": 0,
                "code_units_deleted": 0,
            }
        ),
    )

    result = indexer_module.index_repository(str(tmp_path))

    assert reconciliation_calls == []
    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "processing_failed",
    }
    assert dependency_memberships == [{
        "app.py",
        "settings.yaml",
        "session_log.txt",
        "unsafe.py",
    }]
    completion = result["completion"]
    outcomes = {
        item["file_path"]: item
        for item in completion["file_outcomes"]
    }
    assert completion["trusted_completion"] is False
    assert completion["manifest_advance_allowed"] is False
    assert outcomes["unsafe.py"]["processing_status"] == "parse_failed"
    assert outcomes["unsafe.py"]["error_category"] == (
        "inventory_entry_unsafe"
    )
    assert len(scan_calls) == 1


def test_indexer_skips_reconciliation_after_replacement_failure(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    monkeypatch.setattr(
        indexer_module,
        "replace_code_index_for_file",
        lambda **_kwargs: (
            _ for _ in ()
        ).throw(RuntimeError("simulated replacement failure")),
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **_kwargs: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "reconciliation must not run"
            )
        ),
    )

    result = indexer_module.index_repository(str(tmp_path))

    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "file_replacement_failed",
    }
    assert result["completion"]["status"] == "persistence_failed"
    assert result["completion"]["trusted_completion"] is False


def test_parse_failure_does_not_remove_file_from_membership(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )
    reconciliation_calls = []

    monkeypatch.setattr(
        indexer_module,
        "parse_code_with_treesitter",
        lambda _text, _language: (
            _ for _ in ()
        ).throw(RuntimeError("simulated parse failure")),
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **kwargs: (
            reconciliation_calls.append(kwargs)
            or {
                "dependencies_deleted": 0,
                "code_units_deleted": 0,
            }
        ),
    )

    indexer_module.index_repository(str(tmp_path))

    assert reconciliation_calls == [{
        "index_scope": "test-index-scope",
        "current_files": {"app.py"},
    }]


def test_unsupported_file_is_not_in_code_index_membership(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    unsupported_path = _write_index_source(
        tmp_path,
        "settings.yaml",
        "enabled: true",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[
            (app_path, Path("app.py")),
            (unsupported_path, Path("settings.yaml")),
        ],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )
    reconciliation_calls = []

    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **kwargs: (
            reconciliation_calls.append(kwargs)
            or {
                "dependencies_deleted": 0,
                "code_units_deleted": 0,
            }
        ),
    )

    indexer_module.index_repository(str(tmp_path))

    assert reconciliation_calls[0]["current_files"] == {
        "app.py",
    }


def test_indexer_skips_reconciliation_when_db_initialization_fails(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    monkeypatch.setattr(
        indexer_module,
        "init_db",
        lambda: (
            _ for _ in ()
        ).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **_kwargs: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "reconciliation must not run"
            )
        ),
    )

    result = indexer_module.index_repository(str(tmp_path))

    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "db_initialization_failed",
    }


def test_indexer_skips_all_db_work_when_persistence_is_disabled(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    monkeypatch.setattr(
        indexer_module,
        "code_index_db_enabled",
        lambda: False,
    )

    def unexpected_db_call(*_args, **_kwargs):
        raise AssertionError(
            "disabled persistence must not perform DB work"
        )

    monkeypatch.setattr(
        indexer_module,
        "init_db",
        unexpected_db_call,
    )
    monkeypatch.setattr(
        indexer_module,
        "replace_code_index_for_file",
        unexpected_db_call,
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        unexpected_db_call,
    )
    monkeypatch.setattr(
        indexer_module,
        "get_embedding",
        unexpected_db_call,
    )

    result = indexer_module.index_repository(str(tmp_path))

    assert result["files_processed"] == 1
    assert result["symbols_stored"] == 0
    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": "persistence_disabled",
    }
    assert result["completion"]["status"] == "persistence_disabled"
    assert result["completion"]["persistence_ok"] is False

def test_indexer_reports_reconciliation_failure_without_crashing(
    tmp_path,
    monkeypatch,
):
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )

    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **_kwargs: (
            _ for _ in ()
        ).throw(
            RuntimeError(
                "simulated reconciliation failure"
            )
        ),
    )

    result = indexer_module.index_repository(
        str(tmp_path),
    )

    assert result["files_processed"] == 1
    assert result["symbols_stored"] == 1
    assert result["code_index_reconciliation"] == {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": (
            "reconciliation_failed: "
            "simulated reconciliation failure"
        ),
    }
    assert result["completion"]["status"] == "reconciliation_failed"
    assert result["completion"]["reconciliation_attempted"] is True
    assert result["completion"]["reconciliation_ok"] is False


def test_indexer_result_and_stdout_redact_database_url(
    tmp_path,
    monkeypatch,
    capsys,
):
    database_url = (
        "postgresql://index-user:index-password@"
        "db.example.test/cattus?token=index-token"
    )
    app_path = _write_index_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    _stub_reconciliation_indexer(
        monkeypatch,
        entries=[(app_path, Path("app.py"))],
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )
    monkeypatch.setattr(
        indexer_module,
        "reconcile_code_index_scope",
        lambda **_kwargs: (
            _ for _ in ()
        ).throw(
            RuntimeError(
                f"reconciliation failed using {database_url}"
            )
        ),
    )

    result = indexer_module.index_repository(str(tmp_path))
    stdout_text = capsys.readouterr().out
    result_text = str(result)

    for rendered in (stdout_text, result_text):
        assert database_url not in rendered
        assert "index-user" not in rendered
        assert "index-password" not in rendered
        assert "index-token" not in rendered
        assert "db.example.test/cattus" in rendered
