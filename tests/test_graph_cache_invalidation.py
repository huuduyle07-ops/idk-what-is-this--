"""Phase 13.1 — Graph Cache Invalidation Unification.

The Phase 13 audit found four independent module-level graph caches:

    core/control_engine.py
    core/retriever.py
    core/semantic_graph_pipeline.py
    reasoning/deep_project_understand.py

Historically ``core.control_engine.clear_graph_cache`` cleared only the
control_engine cache, while CLI and web call it believing the graph cache is
fully invalidated. These tests pin the unified behaviour: every graph cache used
by CONTROL / retrieval / reasoning is cleared, and clearing introduces no graph
building, scoring, or other side effects.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from core import control_engine, retriever, semantic_graph_pipeline
from reasoning import deep_project_understand


# rel-path -> imported module.  rel-path is also used for AST source inspection.
GRAPH_CACHE_MODULES = {
    "core/control_engine.py": control_engine,
    "core/retriever.py": retriever,
    "core/semantic_graph_pipeline.py": semantic_graph_pipeline,
    "reasoning/deep_project_understand.py": deep_project_understand,
}


@pytest.fixture(autouse=True)
def _preserve_graph_caches():
    """Snapshot and restore every module-level graph cache around each test so
    these tests never leak fake entries into (or steal real ones from) the rest
    of the suite."""
    snapshots = {m: dict(m._graph_cache) for m in GRAPH_CACHE_MODULES.values()}
    try:
        yield
    finally:
        for module, snap in snapshots.items():
            module._graph_cache.clear()
            module._graph_cache.update(snap)


# ---------------------------------------------------------------------------
# 1-4: each module's own cache is cleared
# ---------------------------------------------------------------------------

def test_control_engine_cache_is_cleared():
    control_engine._graph_cache["/repo/a"] = object()
    control_engine.clear_graph_cache()
    assert control_engine._graph_cache == {}


def test_retriever_cache_is_cleared():
    retriever._graph_cache["/repo/a"] = object()
    retriever.clear_graph_cache()
    assert retriever._graph_cache == {}


def test_semantic_graph_pipeline_cache_is_cleared():
    semantic_graph_pipeline._graph_cache["/repo/a"] = object()
    semantic_graph_pipeline.clear_graph_cache()
    assert semantic_graph_pipeline._graph_cache == {}


def test_deep_project_understand_cache_is_cleared():
    deep_project_understand._graph_cache["/repo/a"] = object()
    deep_project_understand.clear_graph_cache()
    assert deep_project_understand._graph_cache == {}


# ---------------------------------------------------------------------------
# Per-repo clearing honours each module's own key convention
# ---------------------------------------------------------------------------

def test_retriever_per_repo_clear_pops_both_key_conventions():
    # retriever populates _graph_cache under two conventions for the same repo:
    # get_cached_graph keys by the raw path, _get_cached_repo_graph by abspath.
    repo = "relrepo"
    retriever._graph_cache[repo] = object()
    retriever._graph_cache[os.path.abspath(repo)] = object()
    retriever._graph_cache["keep_me"] = object()

    retriever.clear_graph_cache(repo)

    assert repo not in retriever._graph_cache
    assert os.path.abspath(repo) not in retriever._graph_cache
    assert "keep_me" in retriever._graph_cache  # unrelated repo untouched


def test_semantic_graph_pipeline_per_repo_clear(tmp_path):
    repo = str(tmp_path)
    key = str(Path(repo).resolve())  # the exact key get_semantic_graph stores
    semantic_graph_pipeline._graph_cache[key] = object()
    semantic_graph_pipeline._graph_cache["keep_me"] = object()

    semantic_graph_pipeline.clear_graph_cache(repo)

    assert key not in semantic_graph_pipeline._graph_cache
    assert "keep_me" in semantic_graph_pipeline._graph_cache


def test_deep_project_understand_per_repo_clear():
    repo = "rel/repo"
    deep_project_understand._graph_cache[repo] = object()
    deep_project_understand._graph_cache["keep_me"] = object()

    deep_project_understand.clear_graph_cache(repo)

    assert repo not in deep_project_understand._graph_cache
    assert "keep_me" in deep_project_understand._graph_cache


def test_control_engine_per_repo_clear():
    repo = "rel/repo"
    key = os.path.abspath(repo)  # control_engine keys by abspath
    control_engine._graph_cache[key] = object()
    control_engine._graph_cache["keep_me"] = object()

    control_engine.clear_graph_cache(repo)

    assert key not in control_engine._graph_cache
    assert "keep_me" in control_engine._graph_cache


# ---------------------------------------------------------------------------
# 5: control_engine.clear_graph_cache clears all four
# ---------------------------------------------------------------------------

def test_control_engine_clear_graph_cache_clears_all_four():
    control_engine._graph_cache["/repo"] = object()
    retriever._graph_cache["/repo"] = object()
    semantic_graph_pipeline._graph_cache["/repo"] = object()
    deep_project_understand._graph_cache["/repo"] = object()

    control_engine.clear_graph_cache()  # no arg => clear everything everywhere

    assert control_engine._graph_cache == {}
    assert retriever._graph_cache == {}
    assert semantic_graph_pipeline._graph_cache == {}
    assert deep_project_understand._graph_cache == {}


def test_control_engine_clear_graph_cache_per_repo_clears_all_four(tmp_path):
    repo = str(tmp_path)
    # Populate each cache under the exact key its own getter would use.
    control_engine._graph_cache[os.path.abspath(repo)] = object()
    retriever._graph_cache[repo] = object()
    retriever._graph_cache[os.path.abspath(repo)] = object()
    semantic_graph_pipeline._graph_cache[str(Path(repo).resolve())] = object()
    deep_project_understand._graph_cache[repo] = object()

    control_engine.clear_graph_cache(repo)

    assert control_engine._graph_cache == {}
    assert retriever._graph_cache == {}
    assert semantic_graph_pipeline._graph_cache == {}
    assert deep_project_understand._graph_cache == {}


# ---------------------------------------------------------------------------
# 6: repeated clearing is safe / idempotent
# ---------------------------------------------------------------------------

def test_repeated_clearing_is_idempotent():
    retriever._graph_cache["/repo"] = object()
    retriever.clear_graph_cache()
    retriever.clear_graph_cache()              # second clear: no error
    retriever.clear_graph_cache("/never/cached")  # pop missing key: no error
    assert retriever._graph_cache == {}

    # The unified entry point is equally safe to call repeatedly.
    control_engine.clear_graph_cache()
    control_engine.clear_graph_cache()
    control_engine.clear_graph_cache("/never/cached")
    assert control_engine._graph_cache == {}
    assert retriever._graph_cache == {}
    assert semantic_graph_pipeline._graph_cache == {}
    assert deep_project_understand._graph_cache == {}


# ---------------------------------------------------------------------------
# AST helpers for the structural guards (tests 7 & 8)
# ---------------------------------------------------------------------------

def _clear_graph_cache_func(rel_path: str) -> ast.FunctionDef | None:
    tree = ast.parse(Path(rel_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "clear_graph_cache":
            return node
    return None


def _called_names(func_node: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _imported_roots(func_node: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("rel_path", list(GRAPH_CACHE_MODULES.keys()))
def test_module_defines_clear_graph_cache(rel_path):
    assert _clear_graph_cache_func(rel_path) is not None, f"{rel_path} is missing clear_graph_cache"


# ---------------------------------------------------------------------------
# 7: no graph scoring or builder logic is changed (clear must not build/score)
# ---------------------------------------------------------------------------

GRAPH_BUILD_SCORE_CALLS = {
    "build_graph_from_repo",
    "build_graph",
    "compute_node_weights",
    "get_node_weight",
    "compute_scope_aware_spread",
    "add_edge",
    "add_node",
}


@pytest.mark.parametrize("rel_path", list(GRAPH_CACHE_MODULES.keys()))
def test_clear_does_not_build_or_score_graph(rel_path):
    func = _clear_graph_cache_func(rel_path)
    assert func is not None, f"{rel_path} is missing clear_graph_cache"
    leaked = _called_names(func) & GRAPH_BUILD_SCORE_CALLS
    assert not leaked, (
        f"{rel_path}:clear_graph_cache must only invalidate the cache, never "
        f"build or score a graph; found calls to {sorted(leaked)}"
    )


# ---------------------------------------------------------------------------
# 8: AST guard — no model/API calls, no DB writes, no patching, no validation,
#    no benchmark execution inside any clear_graph_cache.
# ---------------------------------------------------------------------------

FORBIDDEN_CALLS = {
    # model / API
    "run_gemini", "run_ollama", "generate_content", "ChatCompletion", "embed", "encode",
    # subprocess / shell
    "system", "Popen", "run", "check_output", "check_call",
    # db writes
    "commit", "execute", "executemany",
    # patching
    "apply_patch_from_json", "apply_patch_plan", "backup_file", "restore_backup",
    # validation / benchmark
    "run_validation_command", "run_benchmarks", "run_benchmark",
}

FORBIDDEN_IMPORT_ROOTS = {
    "subprocess", "requests", "urllib", "socket", "http", "httpx", "aiohttp",
    "openai", "google", "database",
}


@pytest.mark.parametrize("rel_path", list(GRAPH_CACHE_MODULES.keys()))
def test_clear_is_pure_no_model_db_patch_validate_benchmark(rel_path):
    func = _clear_graph_cache_func(rel_path)
    assert func is not None, f"{rel_path} is missing clear_graph_cache"
    bad_calls = _called_names(func) & FORBIDDEN_CALLS
    bad_imports = _imported_roots(func) & FORBIDDEN_IMPORT_ROOTS
    assert not bad_calls, f"{rel_path}:clear_graph_cache calls forbidden {sorted(bad_calls)}"
    assert not bad_imports, f"{rel_path}:clear_graph_cache imports forbidden {sorted(bad_imports)}"
