"""INDEX.1D.3/INDEX.1E.1 characterization of traversal budgets.

The tests count the shared recursive scanner itself.  Reads of already-known
files, the applied-manifest artifact, and direct path lookups are deliberately
outside that membership-walk budget.
"""

from __future__ import annotations

from pathlib import Path

import config
import core.code_dna as code_dna_module
import core.control_engine as control_engine_module
import core.repo_librarian as repo_librarian_module
import core.retriever as retriever_module
import core.semantic_graph_pipeline as semantic_graph_module
import reasoning.deep_project_understand as deep_understand_module
from core import indexer as indexer_module
from core import repository_identity
from core.project_tag import build_project_tag
from core.repository_inventory import (
    CANONICAL_WALK_SITE,
    create_repository_inventory,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def answer():\n    return 42\n",
        encoding="utf-8",
    )
    return repo


def _count_shared_scanner(monkeypatch) -> list[str]:
    calls: list[str] = []
    real_walk = repo_librarian_module._walk_policy_files

    def counting_walk(repo_path):
        calls.append(str(Path(repo_path).resolve()))
        yield from real_walk(repo_path)

    monkeypatch.setattr(
        repo_librarian_module,
        "_walk_policy_files",
        counting_walk,
    )
    return calls


def _fake_parse(text: str, _language: str) -> dict:
    return {
        "symbols": [{
            "kind": "function",
            "name": "answer",
            "content": text,
            "execution_flow": "",
            "calls": [],
        }],
        "imports": [],
        "calls": [],
    }


def _stub_canonical_heavywork(
    monkeypatch,
    tmp_path: Path,
    *,
    build_project_map: bool = True,
) -> None:
    """Keep real membership consumers while excluding DB/model side effects."""
    monkeypatch.setenv("INDEX_USE_EMBEDDINGS", "false")
    monkeypatch.setenv("BENCHMARK_SKIP_PHANTOM", "true")
    monkeypatch.setenv(
        "BENCHMARK_SKIP_PROJECT_MAP",
        "false" if build_project_map else "true",
    )
    monkeypatch.setattr(
        indexer_module,
        "code_index_db_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        indexer_module,
        "parse_code_with_treesitter",
        _fake_parse,
    )
    monkeypatch.setattr(
        "graph.builder.parse_code_with_treesitter",
        _fake_parse,
    )
    monkeypatch.setattr(
        indexer_module,
        "save_dna",
        lambda _repo, _dna: tmp_path / "code_dna.json",
    )
    monkeypatch.setattr(
        indexer_module,
        "write_project_map",
        lambda _repo, _content: str(tmp_path / "project_map.md"),
    )


def test_direct_canonical_index_uses_exactly_one_shared_traversal(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    _stub_canonical_heavywork(monkeypatch, tmp_path)

    result = indexer_module.index_repository(str(repo))

    assert walks == [str(repo.resolve())]
    assert result["files_processed"] == 1
    diagnostics = result["traversal_diagnostics"]
    assert diagnostics["repository_walks"] == 1
    assert diagnostics["walk_sites"] == [CANONICAL_WALK_SITE]
    assert diagnostics["inventory_reuse"]["indexer"] is True
    assert diagnostics["inventory_reuse"]["code_dna"] is True
    assert diagnostics["inventory_reuse"]["dependency_resolver"] is True
    assert diagnostics["inventory_reuse"]["graph_builder"] is True
    assert diagnostics["inventory_reuse"]["project_map"] is True
    assert diagnostics["inventory_reuse"]["manifest"] is True
    assert result["delta_shadow"]["mode"] == "shadow_only"
    assert result["delta_shadow"]["authoritative"] is False
    assert result["delta_shadow"]["manifest"]["observed_built"] is True


def test_supplied_inventory_adds_zero_repository_traversals(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    _stub_canonical_heavywork(monkeypatch, tmp_path)

    inventory = create_repository_inventory(repo)
    assert walks == [str(repo.resolve())]

    result = indexer_module.index_repository(
        str(repo),
        inventory=inventory,
        include_operation_artifacts=True,
    )

    assert walks == [str(repo.resolve())]
    assert (
        result["_operation_artifacts"]["inventory"]
        is inventory
    )
    assert result["traversal_diagnostics"]["repository_walks"] == 1
    assert (
        result["traversal_diagnostics"]["inventory_reuse"]["manifest"]
        is True
    )
    assert result["delta_shadow"]["manifest"]["observed_built"] is True


def test_web_project_request_reuses_one_inventory_everywhere(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    seen: list[str] = []
    shared: dict[str, object] = {}
    graph = object()

    def record(label: str, inventory) -> None:
        if "inventory" not in shared:
            shared["inventory"] = inventory
        assert inventory is shared["inventory"]
        seen.append(label)

    def fake_index(
        repo_path,
        project_tag=None,
        *,
        inventory=None,
        include_operation_artifacts=False,
        **_kwargs,
    ):
        del repo_path, project_tag
        assert include_operation_artifacts is True
        record("indexer", inventory)
        return {
            "phantom_limb": {"count": 0, "findings": []},
            "_operation_artifacts": {
                "inventory": inventory,
                "program_graph": graph,
            },
        }

    def fake_preflight(
        *,
        repo_path,
        language,
        command=None,
        inventory=None,
    ):
        del repo_path, language, command
        record("preflight", inventory)
        return {"ran": False, "ok": None}

    def fake_control(
        query,
        repo_path,
        *,
        inventory=None,
        graph=None,
    ):
        del query, repo_path
        record("control", inventory)
        assert graph is shared_graph
        return {
            "patch_intent": {
                "file": "app.py",
                "source_snippet": "",
            },
            "top_hypothesis": {"confidence": 0.9},
        }

    def fake_related(
        control_result,
        repo_path,
        *,
        graph=None,
        inventory=None,
    ):
        del control_result, repo_path
        record("related_snippets", inventory)
        assert graph is shared_graph
        return []

    def fake_scout(**kwargs):
        record("scout", kwargs["inventory"])
        return kwargs["control_result"]

    def fake_dna(repo_path, *, inventory=None):
        del repo_path
        record("code_dna", inventory)
        return {}

    shared_graph = graph
    monkeypatch.setattr(runner, "index_repository", fake_index)
    monkeypatch.setattr(runner, "clear_graph_cache", lambda _repo: None)
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        fake_preflight,
    )
    monkeypatch.setattr(runner, "run_control_structured", fake_control)
    monkeypatch.setattr(
        runner,
        "build_related_snippets",
        fake_related,
    )
    monkeypatch.setattr(
        runner,
        "maybe_enrich_with_scout",
        fake_scout,
    )
    monkeypatch.setattr(runner, "get_or_compute_dna", fake_dna)
    monkeypatch.setattr(
        runner,
        "dna_to_prompt_block",
        lambda _dna, mode="match": "",
    )
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(
        runner,
        "get_engineering_memory",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(runner, "create_session", lambda **_kwargs: 1)
    monkeypatch.setattr(
        runner,
        "save_message",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        runner,
        "_maybe_update_run_progress_snapshot_shadow",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        runner,
        "_maybe_write_run_progress_snapshot_shadow",
        lambda *, result, **_kwargs: result,
    )
    monkeypatch.setattr(
        runner,
        "run_draft_pipeline",
        lambda _state: (_ for _ in ()).throw(
            AssertionError("model pipeline must remain stubbed")
        ),
    )

    result = runner.run_agent_web(
        "fix app.py",
        str(repo),
        runtime_environment="local_linux",
    )

    assert result["harness_mode"] == "source_missing"
    assert walks == [str(repo.resolve())]
    assert seen == [
        "indexer",
        "preflight",
        "control",
        "related_snippets",
        "scout",
        "code_dna",
    ]


def test_repeated_identity_and_agent_dir_calls_add_zero_walks(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    monkeypatch.setattr(config, "AGENT_DIR", tmp_path / "agent-output")

    identities = [
        repository_identity.build_repository_identity(repo)
        for _ in range(4)
    ]
    project_tags = [
        build_project_tag(str(repo))
        for _ in range(4)
    ]
    agent_dirs = [
        config.get_agent_dir(str(repo))
        for _ in range(4)
    ]

    assert identities == [identities[0]] * 4
    assert project_tags == [project_tags[0]] * 4
    assert agent_dirs == [agent_dirs[0]] * 4
    assert walks == []


def test_file_disappearing_after_inventory_is_explicit_and_untrusted(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    _stub_canonical_heavywork(
        monkeypatch,
        tmp_path,
        build_project_map=False,
    )
    # Mark persistence available without touching a real database so the
    # completion classifier can represent the processing failure directly.
    monkeypatch.setattr(
        indexer_module,
        "code_index_db_enabled",
        lambda: True,
    )
    monkeypatch.setattr(indexer_module, "init_db", lambda: None)
    inventory = create_repository_inventory(repo)
    assert walks == [str(repo.resolve())]

    (repo / "app.py").unlink()
    result = indexer_module.index_repository(
        str(repo),
        inventory=inventory,
    )

    assert walks == [str(repo.resolve())]
    assert result["files_processed"] == 0
    assert result["traversal_diagnostics"]["repository_walks"] == 1
    completion = result["completion"]
    assert completion["status"] == "processing_failed"
    assert completion["failure_stage"] == "processing"
    assert completion["processing_ok"] is False
    assert completion["trusted_completion"] is False
    assert completion["manifest_advance_allowed"] is False
    assert completion["failed_files"] == ["app.py"]
    assert completion["file_outcomes"] == [{
        "file_path": "app.py",
        "action": "full_refresh",
        "processing_status": "parse_failed",
        "embedding_status": "not_required",
        "persistence_status": "parse_failed",
        "embedding_required": False,
        "error_category": "inventory_entry_unavailable",
        "error_message": (
            "inventory entry disappeared before processing; "
            "the operation snapshot was not rescanned"
        ),
    }]


def test_disappearing_file_is_valid_processing_failure_when_persistence_disabled(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    _stub_canonical_heavywork(
        monkeypatch,
        tmp_path,
        build_project_map=False,
    )
    inventory = create_repository_inventory(repo)
    (repo / "app.py").unlink()

    result = indexer_module.index_repository(
        str(repo),
        inventory=inventory,
    )

    assert walks == [str(repo.resolve())]
    completion = result["completion"]
    assert completion["status"] == "processing_failed"
    assert completion["trusted_completion"] is False
    assert completion["manifest_advance_allowed"] is False
    assert completion["failed_files"] == ["app.py"]
    assert completion["file_outcomes"][0]["persistence_status"] == "blocked"
    assert (
        completion["file_outcomes"][0]["error_category"]
        == "inventory_entry_unavailable"
    )


def test_file_disappearing_during_read_is_untrusted_without_rescan(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    walks = _count_shared_scanner(monkeypatch)
    _stub_canonical_heavywork(
        monkeypatch,
        tmp_path,
        build_project_map=False,
    )
    inventory = create_repository_inventory(repo)

    def disappear_during_read(*_args, **_kwargs):
        (repo / "app.py").unlink()
        raise FileNotFoundError("app.py disappeared")

    monkeypatch.setattr(
        indexer_module,
        "extract_file_text",
        disappear_during_read,
    )

    result = indexer_module.index_repository(
        str(repo),
        inventory=inventory,
    )

    assert walks == [str(repo.resolve())]
    completion = result["completion"]
    assert completion["status"] == "processing_failed"
    assert completion["trusted_completion"] is False
    assert completion["manifest_advance_allowed"] is False
    assert completion["failed_files"] == ["app.py"]
    assert completion["file_outcomes"] == [{
        "file_path": "app.py",
        "action": "full_refresh",
        "processing_status": "parse_failed",
        "embedding_status": "not_required",
        "persistence_status": "blocked",
        "embedding_required": False,
        "error_category": "inventory_entry_unavailable",
        "error_message": (
            "inventory entry disappeared during processing; "
            "the operation snapshot was not rescanned"
        ),
    }]


def test_supplied_inventory_bypasses_graphs_cached_by_prior_operations(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    absolute_root = str(repo.resolve())
    cases = (
        (
            control_engine_module,
            control_engine_module.get_cached_graph,
            absolute_root,
        ),
        (
            retriever_module,
            retriever_module.get_cached_graph,
            absolute_root,
        ),
        (
            semantic_graph_module,
            semantic_graph_module.get_semantic_graph,
            absolute_root,
        ),
        (
            deep_understand_module,
            deep_understand_module.get_cached_graph,
            absolute_root,
        ),
    )

    for module, getter, cache_key in cases:
        stale_graph = object()
        fresh_graph = object()
        calls = []
        module._graph_cache.clear()
        module._graph_cache[cache_key] = stale_graph

        def fake_build(repo_path, *, inventory=None):
            calls.append((str(Path(repo_path).resolve()), inventory))
            return fresh_graph

        monkeypatch.setattr(
            module,
            "build_graph_from_repo",
            fake_build,
        )

        assert getter(str(repo), inventory=inventory) is fresh_graph
        assert calls == [(absolute_root, inventory)]
        assert module._graph_cache[cache_key] is stale_graph
        module._graph_cache.clear()


def test_retrieve_context_passes_operation_graph_to_execution_trace(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)

    class Graph:
        nodes = {}
        edges = []

    graph = Graph()
    seen = {}
    monkeypatch.setattr(
        retriever_module,
        "classify_retrieval_level",
        lambda _query: {
            "level": "micro",
            "confidence": 1.0,
            "scores": {"macro": 0, "meso": 0, "micro": 1},
        },
    )
    monkeypatch.setattr(
        retriever_module,
        "get_cached_graph",
        lambda _repo, *, inventory=None: graph,
    )
    monkeypatch.setattr(
        retriever_module,
        "retriever_embeddings_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        retriever_module,
        "get_agent_dir",
        lambda _repo: tmp_path,
    )
    monkeypatch.setattr(
        retriever_module,
        "explain_symbol",
        lambda _graph, _word: {"called_by": [], "calls": []},
    )
    monkeypatch.setattr(
        retriever_module,
        "search_safe_code_units",
        lambda *_args, **_kwargs: [],
    )

    def fake_trace(
        _query,
        repo_path=None,
        top_k=3,
        *,
        graph=None,
        inventory=None,
    ):
        seen.update(
            repo_path=repo_path,
            top_k=top_k,
            graph=graph,
            inventory=inventory,
        )
        return ""

    monkeypatch.setattr(
        retriever_module,
        "trace_execution_flow",
        fake_trace,
    )

    retriever_module.retrieve_context(
        "answer",
        repo_path=str(repo),
        inventory=inventory,
    )

    assert seen == {
        "repo_path": str(repo),
        "top_k": 3,
        "graph": graph,
        "inventory": inventory,
    }


def test_inventory_backed_code_dna_ignores_unversioned_disk_cache(
    tmp_path,
    monkeypatch,
):
    repo = _write_repo(tmp_path)
    inventory = create_repository_inventory(repo)
    fresh = {"indent": "spaces_4"}
    calls = []
    monkeypatch.setattr(
        code_dna_module,
        "load_dna",
        lambda _repo: {"indent": "stale"},
    )
    monkeypatch.setattr(
        code_dna_module,
        "compute_dna",
        lambda _repo, *, inventory=None: (
            calls.append(inventory) or fresh
        ),
    )
    monkeypatch.setattr(
        code_dna_module,
        "save_dna",
        lambda _repo, dna: calls.append(dna),
    )

    assert (
        code_dna_module.get_or_compute_dna(
            str(repo),
            inventory=inventory,
        )
        is fresh
    )
    assert calls == [inventory, fresh]


def test_production_traversal_inventory_is_documented():
    document = (
        PROJECT_ROOT
        / "docs"
        / "designs"
        / "2026-07-28-index-traversal-budget.md"
    ).read_text(encoding="utf-8")

    for required_site in (
        "core.repo_librarian._walk_policy_files",
        "core.indexer.index_repository",
        "core.code_dna.compute_dna",
        "graph.builder.build_graph_from_repo",
        "graph.project_map.build_project_map",
        "core.index_manifest.inspect_repository_delta",
        "core.dependency_target.resolve_dependency_target",
        "web.runner.run_agent_web",
        "core.control_engine.get_cached_graph",
        "reasoning.deep_project_understand.get_cached_graph",
        "core.retriever.get_cached_graph",
        "core.semantic_graph_pipeline.get_semantic_graph",
        "core.feature_context.build_file_inventory",
        "core.preflight.detect_default_preflight_command",
        "config.get_agent_dir",
        "core.project_tag.build_project_tag",
    ):
        assert required_site in document


def test_canonical_consumers_add_no_recursive_scanner():
    shared_scanner_source = (
        PROJECT_ROOT / "core" / "repo_librarian.py"
    ).read_text(encoding="utf-8")
    assert shared_scanner_source.count("os.walk(") == 1

    for relative_path in (
        "core/repository_inventory.py",
        "core/repo_inventory.py",
        "core/code_dna.py",
        "core/feature_context.py",
        "core/router.py",
        "core/indexer.py",
        "core/index_delta_shadow.py",
        "graph/builder.py",
        "graph/project_map.py",
        "web/runner.py",
    ):
        source = (PROJECT_ROOT / relative_path).read_text(
            encoding="utf-8"
        )
        assert "os.walk(" not in source
        assert ".rglob(" not in source
        assert 'glob("**/*")' not in source
        assert "subprocess" not in source


def test_inventory_layer_has_no_runtime_or_destructive_dispatch():
    source = (
        PROJECT_ROOT / "core" / "repository_inventory.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "inspect_repository_delta",
        "save_repository_manifest",
        "build_index_execution_plan",
        "ActivationGraph",
        "requests",
        "httpx",
        "socket",
        "threading",
        "multiprocessing",
        "unlink(",
        "rmtree(",
        "remove(",
    ):
        assert forbidden not in source
