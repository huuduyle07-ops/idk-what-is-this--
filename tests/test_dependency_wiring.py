from __future__ import annotations

from collections import Counter
from pathlib import Path

from core import indexer as indexer_module
from core import repo_librarian
from core.indexer import _build_dependency_rows
from core import repository_identity
from core.repository_inventory import create_repository_inventory
from graph import builder as graph_builder


def test_python_import_is_stored_as_canonical_target_file(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="pkg/app.py",
        language="python",
        parsed_data={
            "imports": ["from pkg.utils import helper"],
            "symbols": [],
            "calls": [],
        },
        repository_files={
            "pkg/app.py",
            "pkg/utils.py",
        },
    )

    assert rows == [{
        "dependency_type": "import",
        "source_symbol": None,
        "target_file": "pkg/utils.py",
        "target_symbol": None,
    }]


def test_dependency_rows_use_canonical_internal_target(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.ts",
        language="typescript",
        parsed_data={
            "imports": ["./utils"],
            "symbols": [],
            "calls": [],
        },
        repository_files={
            "src/app.ts",
            "src/utils.ts",
        },
    )

    assert rows == [{
        "dependency_type": "import",
        "source_symbol": None,
        "target_file": "src/utils.ts",
        "target_symbol": None,
    }]


def test_external_javascript_package_is_stored_as_target_symbol(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.js",
        language="javascript",
        parsed_data={
            "imports": ['import React from "react";'],
            "symbols": [],
            "calls": [],
        },
        repository_files={"src/app.js"},
    )

    assert rows == [{
        "dependency_type": "import",
        "source_symbol": None,
        "target_file": None,
        "target_symbol": "react",
    }]


def test_unsafe_import_is_omitted(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.ts",
        language="typescript",
        parsed_data={
            "imports": ["../../outside"],
            "symbols": [],
            "calls": [],
        },
        repository_files={"src/app.ts"},
    )

    assert rows == []


def test_duplicate_parser_imports_collapse_to_one_dependency(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.ts",
        language="typescript",
        parsed_data={
            "imports": [
                "./utils",
                'import "./utils";',
                "./utils",
            ],
            "symbols": [],
            "calls": [],
        },
        repository_files={
            "src/app.ts",
            "src/utils.ts",
        },
    )

    assert rows == [{
        "dependency_type": "import",
        "source_symbol": None,
        "target_file": "src/utils.ts",
        "target_symbol": None,
    }]


def test_symbol_calls_and_file_level_calls_are_preserved(
    tmp_path,
):
    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.py",
        language="python",
        parsed_data={
            "imports": [],
            "symbols": [{
                "name": "run",
                "calls": ["helper", "shared"],
            }],
            "calls": [
                "helper",
                "shared",
                "top_level",
                "top_level",
            ],
        },
        repository_files={"src/app.py"},
    )

    assert rows == [
        {
            "dependency_type": "call",
            "source_symbol": "run",
            "target_file": None,
            "target_symbol": "helper",
        },
        {
            "dependency_type": "call",
            "source_symbol": "run",
            "target_file": None,
            "target_symbol": "shared",
        },
        {
            "dependency_type": "call",
            "source_symbol": None,
            "target_file": None,
            "target_symbol": "top_level",
        },
    ]


def test_indexer_uses_one_atomic_replacement_per_file(
    tmp_path,
    monkeypatch,
):
    _write_source(tmp_path, "app.py", "app fixture")
    _write_source(tmp_path, "utils.py", "utils fixture")
    replacement_calls = _stub_indexer(
        monkeypatch,
        parsed_by_text={
            "app fixture": {
                "imports": [],
                "symbols": [
                    {
                        "kind": "function",
                        "name": "app",
                        "content": "def app(): pass",
                        "execution_flow": [],
                        "calls": ["helper"],
                    },
                    {
                        "kind": "function",
                        "name": "helper",
                        "content": "def helper(): pass",
                        "execution_flow": [],
                        "calls": ["leaf"],
                    },
                ],
                "calls": [
                    "helper",
                    "leaf",
                    "top_level",
                ],
            },
            "utils fixture": _parsed_with_function("utils"),
        },
    )

    indexer_module.index_repository(
        str(tmp_path),
        project_tag="display-only",
    )

    assert Counter(
        call["file_path"]
        for call in replacement_calls
    ) == Counter({
        "app.py": 1,
        "utils.py": 1,
    })
    assert all(
        call["index_scope"] == "test-index-scope"
        for call in replacement_calls
    )
    app_replacement = next(
        call
        for call in replacement_calls
        if call["file_path"] == "app.py"
    )
    assert [
        unit["name"]
        for unit in app_replacement["code_units"]
    ] == ["app", "helper"]
    assert app_replacement["dependencies"] == [
        {
            "dependency_type": "call",
            "source_symbol": "app",
            "target_file": None,
            "target_symbol": "helper",
        },
        {
            "dependency_type": "call",
            "source_symbol": "helper",
            "target_file": None,
            "target_symbol": "leaf",
        },
        {
            "dependency_type": "call",
            "source_symbol": None,
            "target_file": None,
            "target_symbol": "top_level",
        },
    ]


def test_empty_file_still_performs_empty_replacement(
    tmp_path,
    monkeypatch,
):
    _write_source(tmp_path, "empty.py", "")
    replacement_calls = _stub_indexer(
        monkeypatch,
        parsed_by_text={
            "": {
                "imports": [],
                "symbols": [],
                "calls": [],
            },
        },
    )

    indexer_module.index_repository(str(tmp_path))

    assert replacement_calls == [{
        "file_path": "empty.py",
        "index_scope": "test-index-scope",
        "code_units": [],
        "dependencies": [],
    }]


def test_graph_builder_and_indexer_resolve_same_import_identically(
    tmp_path,
    monkeypatch,
):
    app_text = 'import { helper } from "./utils";'
    utils_text = "export const helper = () => 1;"
    _write_source(tmp_path, "src/app.ts", app_text)
    _write_source(tmp_path, "src/utils.ts", utils_text)
    parsed_by_text = {
        app_text: {
            "imports": ["./utils"],
            "symbols": [],
            "calls": [],
        },
        utils_text: {
            "imports": [],
            "symbols": [],
            "calls": [],
        },
    }
    monkeypatch.setattr(
        graph_builder,
        "parse_code_with_treesitter",
        lambda text, _language: parsed_by_text[text],
    )

    rows = _build_dependency_rows(
        repo_path=str(tmp_path),
        rel_path="src/app.ts",
        language="typescript",
        parsed_data=parsed_by_text[app_text],
        repository_files={
            "src/app.ts",
            "src/utils.ts",
        },
    )
    graph = graph_builder.build_graph_from_repo(str(tmp_path))
    graph_import_targets = {
        edge.target
        for edge in graph.edges
        if edge.source == "src/app.ts"
        and edge.type == "imports"
    }

    assert rows[0]["target_file"] == "src/utils.ts"
    assert graph_import_targets == {
        rows[0]["target_file"],
    }


def test_graph_builder_does_not_create_file_node_for_external_package(
    tmp_path,
    monkeypatch,
):
    app_text = 'import React from "react";'
    app_path = _write_source(
        tmp_path,
        "src/app.js",
        app_text,
    )
    # A colliding Python file must not turn a bare JS package into an
    # internal file dependency.
    _write_source(tmp_path, "react.py", "react collision")
    monkeypatch.setattr(
        graph_builder,
        "iter_repo_files",
        lambda _repo_path: [
            (app_path, Path("src/app.js")),
        ],
    )
    monkeypatch.setattr(
        graph_builder,
        "parse_code_with_treesitter",
        lambda _text, _language: {
            "imports": ["react"],
            "symbols": [],
            "calls": [],
        },
    )

    graph = graph_builder.build_graph_from_repo(str(tmp_path))

    assert set(graph.nodes) == {"src/app.js"}
    assert [
        edge
        for edge in graph.edges
        if edge.type == "imports"
    ] == []


def test_graph_builder_uses_precomputed_repository_scan(
    tmp_path,
    monkeypatch,
):
    app_text = 'import { helper } from "./utils";'
    utils_text = "export const helper = () => 1;"
    app_path = _write_source(
        tmp_path,
        "src/app.ts",
        app_text,
    )
    utils_path = _write_source(
        tmp_path,
        "src/utils.ts",
        utils_text,
    )
    inventory = create_repository_inventory(tmp_path)
    inventory_before = inventory.entry_pairs
    repository_files = set(inventory.relative_paths(None))
    repository_files_before = set(repository_files)
    parsed_by_text = {
        app_text: {
            "imports": ["./utils"],
            "symbols": [],
            "calls": [],
        },
        utils_text: {
            "imports": [],
            "symbols": [],
            "calls": [],
        },
    }

    monkeypatch.setattr(
        graph_builder,
        "iter_repo_files",
        lambda _repo_path: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "repository must not be scanned again"
            )
        ),
    )
    monkeypatch.setattr(
        graph_builder,
        "parse_code_with_treesitter",
        lambda text, _language: parsed_by_text[text],
    )

    graph = graph_builder.build_graph_from_repo(
        str(tmp_path),
        inventory=inventory,
        repository_files=repository_files,
    )

    assert inventory.entry_pairs == inventory_before
    assert repository_files == repository_files_before
    assert {
        (edge.source, edge.target, edge.type)
        for edge in graph.edges
        if edge.type == "imports"
    } == {
        ("src/app.ts", "src/utils.ts", "imports"),
    }


def test_graph_builder_legacy_path_walks_shared_scanner_once(
    tmp_path,
    monkeypatch,
):
    _write_source(tmp_path, "app.py", "app fixture")
    _write_source(
        tmp_path,
        "src/nested.py",
        "nested fixture",
    )
    real_walk = repo_librarian._walk_policy_files
    walk_calls = 0

    def counting_walk(root):
        nonlocal walk_calls
        walk_calls += 1
        yield from real_walk(root)

    monkeypatch.setattr(
        repo_librarian,
        "_walk_policy_files",
        counting_walk,
    )
    monkeypatch.setattr(
        graph_builder,
        "parse_code_with_treesitter",
        lambda _text, _language: {
            "imports": [],
            "symbols": [],
            "calls": [],
        },
    )

    graph = graph_builder.build_graph_from_repo(str(tmp_path))

    assert walk_calls == 1
    assert set(graph.nodes) == {
        "app.py",
        "src/nested.py",
    }


def _write_source(
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


def _stub_indexer(
    monkeypatch,
    *,
    parsed_by_text: dict[str, dict],
) -> list[dict]:
    replacement_calls: list[dict] = []

    class FakeEmbedding:
        def tolist(self):
            return [0.0]

    def capture_replacement(**kwargs):
        replacement_calls.append(kwargs)
        return len(kwargs["code_units"])

    monkeypatch.setenv("BENCHMARK_SKIP_PHANTOM", "true")
    monkeypatch.setenv("BENCHMARK_SKIP_PROJECT_MAP", "true")
    monkeypatch.setenv("INDEX_USE_EMBEDDINGS", "true")
    monkeypatch.setattr(
        indexer_module,
        "is_safe_path",
        lambda _path, allowed_roots: bool(allowed_roots),
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
    monkeypatch.setattr(indexer_module, "init_db", lambda: None)
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
        lambda _repo_path, *, inventory=None: {
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

    return replacement_calls


def test_indexer_does_not_use_legacy_code_index_mutators():
    import inspect
    import core.indexer

    source = inspect.getsource(
        core.indexer.index_repository
    )

    assert "clear_code_units_for_file" not in source
    assert "clear_dependencies_for_file" not in source
    assert "save_dependency(" not in source


def test_indexer_embedding_disabled_still_persists_units(
    tmp_path,
    monkeypatch,
):
    _write_source(
        tmp_path,
        "app.py",
        "app fixture",
    )

    replacement_calls = _stub_indexer(
        monkeypatch,
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    monkeypatch.setenv(
        "INDEX_USE_EMBEDDINGS",
        "false",
    )
    monkeypatch.setattr(
        indexer_module,
        "get_embedding",
        lambda _content: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "embedding must not be generated"
            )
        ),
    )

    indexer_module.index_repository(
        str(tmp_path),
    )

    assert len(replacement_calls) == 1
    assert replacement_calls[0]["code_units"] == [{
        "kind": "function",
        "name": "app",
        "content": "def app(): pass",
        "embedding": None,
    }]


def test_indexer_reuses_repository_scan_for_graph(
    tmp_path,
    monkeypatch,
):
    _write_source(
        tmp_path,
        "app.py",
        "app fixture",
    )
    inventory = create_repository_inventory(tmp_path)
    inventory_before = inventory.entry_pairs
    _stub_indexer(
        monkeypatch,
        parsed_by_text={
            "app fixture": _parsed_with_function("app"),
        },
    )

    captured_graph_args: dict = {}
    graph_sentinel = object()

    def capture_graph(
        repo_path,
        *,
        inventory,
    ):
        captured_graph_args.update({
            "repo_path": repo_path,
            "inventory": inventory,
        })
        return graph_sentinel

    monkeypatch.setenv(
        "BENCHMARK_SKIP_PROJECT_MAP",
        "false",
    )
    monkeypatch.setattr(
        indexer_module,
        "create_repository_inventory",
        lambda _repo_path: (
            _ for _ in ()
        ).throw(
            AssertionError(
                "supplied inventory must prevent a repository rescan"
            )
        ),
    )
    monkeypatch.setattr(
        indexer_module,
        "build_graph_from_repo",
        capture_graph,
    )
    monkeypatch.setattr(
        indexer_module,
        "build_project_map",
        lambda _summaries, **_kwargs: "project map",
    )
    monkeypatch.setattr(
        indexer_module,
        "write_project_map",
        lambda _repo_path, _content: "project-map.md",
    )

    result = indexer_module.index_repository(
        str(tmp_path),
        inventory=inventory,
    )

    assert captured_graph_args["inventory"] is inventory
    assert inventory.entry_pairs == inventory_before
    assert result["project_map"] == "project-map.md"
