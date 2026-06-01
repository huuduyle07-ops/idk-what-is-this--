"""Phase 13.14 - Router gating characterization (tests only).

A pure characterization slice that pins the *current* behavior of
``core/router.py`` before any future refactor. The router owns the live
auto-patch / retriever gating consumed by ``core.pipeline`` (``should_auto_patch``
at the patch chokepoint, ``should_use_retriever`` for context hydration), so its
decision boundaries deserve a regression net even though none of this code is
being changed here.

These tests assert behavior as it is today; they do not modify production code.
To keep the suite hermetic and fast, an autouse fixture forces the embedding
router OFF (``ROUTER_USE_EMBEDDINGS=false``) so ``sentence-transformers`` / torch
are never imported; the single embedding-branch test re-enables it and injects
deterministic fakes. No model/API calls, no DB writes, no benchmark execution,
no subprocess, and no Docker lifecycle (asserted by the AST self-guard, last
test).

Characterization note (NOT a fix): ``detect_language`` contains a Python
operator-precedence quirk in its Kotlin branch
(``"fun " in text or "suspend fun" in text or "val " in text and "var " in text``
binds as ``... or ("val " in text and "var " in text)``). A lone ``val`` is
therefore NOT detected as Kotlin, while ``val`` + ``var`` together is. The tests
below pin that exact current behavior; changing it would be a routing/behavior
change and is intentionally out of scope for this tests-only slice.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import numpy as np
import pytest

import config
import core.router as router

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]


@pytest.fixture(autouse=True)
def _disable_embedding_router(monkeypatch):
    """Force the deterministic, no-model routing path for every test by default.

    ``classify_task`` reads ``ROUTER_USE_EMBEDDINGS`` at call time; forcing it
    false guarantees no test accidentally loads sentence-transformers/torch (a
    heavy, network-touching import) when an intent hint fails to match. The
    dedicated embedding-branch test overrides this and supplies fakes.
    """
    monkeypatch.setenv("ROUTER_USE_EMBEDDINGS", "false")


# ===========================================================================
# detect_repo_language
# ===========================================================================
def _write(repo: Path, rel: str, text: str = "x\n") -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detect_repo_language_picks_most_common_code_language(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.py")
    _write(tmp_path, "c.rs")
    assert router.detect_repo_language(str(tmp_path)) == "python"


def test_detect_repo_language_ignores_text_doc_json_only_repos(tmp_path):
    # text / document / json languages are explicitly excluded from the count.
    _write(tmp_path, "README.md")
    _write(tmp_path, "data.json")
    _write(tmp_path, "notes.txt")
    assert router.detect_repo_language(str(tmp_path)) == "unknown"


def test_detect_repo_language_empty_dir_is_unknown(tmp_path):
    assert router.detect_repo_language(str(tmp_path)) == "unknown"


def test_detect_repo_language_missing_path_is_unknown(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert router.detect_repo_language(str(missing)) == "unknown"


def test_detect_repo_language_file_path_is_unknown(tmp_path):
    f = tmp_path / "single.py"
    f.write_text("print(1)\n", encoding="utf-8")
    # A file (not a directory) returns "unknown" per the is_dir() guard.
    assert router.detect_repo_language(str(f)) == "unknown"


# ===========================================================================
# detect_input_mode  (ordered: patch_request -> error_log -> architecture ->
#                      code -> question)
# ===========================================================================
def test_detect_input_mode_patch_request():
    payload = '{"target_snippet": "a", "patched_snippet": "b"}'
    assert router.detect_input_mode(payload) == "patch_request"


def test_detect_input_mode_patch_request_requires_leading_brace():
    # Same signal but not starting with "{" -> not a patch request.
    payload = 'here is "target_snippet" inline'
    assert router.detect_input_mode(payload) != "patch_request"


def test_detect_input_mode_error_log_traceback():
    assert router.detect_input_mode("Traceback (most recent call last):") == "error_log"


def test_detect_input_mode_error_log_build_failed():
    assert router.detect_input_mode("Build failed during compile") == "error_log"


def test_detect_input_mode_architecture():
    assert router.detect_input_mode("Explain the overall system design") == "architecture"


def test_detect_input_mode_code():
    assert router.detect_input_mode("def foo():\n    return 1") == "code"


def test_detect_input_mode_question_fallback():
    assert router.detect_input_mode("What is the capital of France?") == "question"


def test_detect_input_mode_error_log_precedes_architecture():
    # Contains both an error signal ("failed") and an architecture signal
    # ("architecture"); error_log is checked first.
    assert router.detect_input_mode("the architecture build failed") == "error_log"


# ===========================================================================
# detect_language
# ===========================================================================
def test_detect_language_file_path_extension_wins():
    assert router.detect_language("totally unrelated prose", "module.rs") == "rust"


def test_detect_language_unknown_extension_falls_back_to_text():
    # Unknown extension -> ignored; prose has no signals -> unknown.
    assert router.detect_language("just words here", "thing.unknownext") == "unknown"


def test_detect_language_python_from_text():
    assert router.detect_language("def foo():\n    pass") == "python"


def test_detect_language_typescript_from_interface():
    assert router.detect_language("interface Foo { id: number }") == "typescript"


def test_detect_language_javascript_from_function():
    assert router.detect_language("function add(a, b) { return a + b }") == "javascript"


def test_detect_language_cpp_from_include():
    # Note: C-style code is reported as "cpp" by the #include heuristic.
    assert router.detect_language("#include <stdio.h>") == "cpp"


def test_detect_language_go_from_package_and_func():
    assert router.detect_language("package main\nfunc main() {}") == "go"


def test_detect_language_fallback_regex_uses_mentioned_filename():
    # No syntax signals, but a known extension is mentioned in prose.
    assert router.detect_language("please look at handler.go in the repo") == "go"


@pytest.mark.parametrize("text", ["fun greet() {}", "suspend fun load() {}"])
def test_detect_language_kotlin_from_fun(text):
    assert router.detect_language(text) == "kotlin"


def test_detect_language_kotlin_requires_both_val_and_var():
    # PINNED QUIRK (precedence): val + var together -> kotlin.
    assert router.detect_language("val a = 1\nvar b = 2") == "kotlin"


def test_detect_language_lone_val_is_not_kotlin():
    # PINNED QUIRK (precedence): a lone `val` does NOT classify as kotlin and,
    # with no other signal, resolves to "unknown". This documents current
    # behavior; it is intentionally not "fixed" in this tests-only slice.
    assert router.detect_language("val a = 1") == "unknown"


# ===========================================================================
# should_allow_ai_language_guess
# ===========================================================================
def test_should_allow_ai_language_guess_unknown_returns_guidance():
    out = router.should_allow_ai_language_guess("unknown")
    assert out.strip() != ""
    assert "unknown" in out.lower()
    assert "auto patch" in out.lower()


def test_should_allow_ai_language_guess_known_returns_empty():
    assert router.should_allow_ai_language_guess("python") == ""


# ===========================================================================
# estimate_complexity  (extreme -> complex -> agent-role -> simple)
# ===========================================================================
def test_estimate_complexity_extreme_signal():
    assert router.estimate_complexity("design the system architecture") == "extreme"


def test_estimate_complexity_complex_signal():
    assert router.estimate_complexity("fix this bug please") == "complex"


def test_estimate_complexity_testing_is_complex():
    assert router.estimate_complexity("add a test for this") == "complex"


def test_estimate_complexity_simple_default():
    assert router.estimate_complexity("hello there friend") == "simple"


def test_estimate_complexity_agent_reviewer_is_complex():
    assert router.estimate_complexity("hello", mode="reviewer", audience="agent") == "complex"


def test_estimate_complexity_extreme_precedes_complex():
    # "refactor" (complex) + "architecture" (extreme) -> extreme wins.
    assert router.estimate_complexity("refactor the architecture") == "extreme"


# ===========================================================================
# should_use_retriever
# ===========================================================================
def test_should_use_retriever_no_file_path_is_false():
    assert router.should_use_retriever(None) is False


def test_should_use_retriever_unsupported_extension_is_false():
    assert router.should_use_retriever("notes.unknownext") is False


def test_should_use_retriever_supported_file_no_taskinfo_is_true():
    assert router.should_use_retriever("module.py") is True


def test_should_use_retriever_input_mode_triggers_true():
    assert router.should_use_retriever("module.py", {"input_mode": "error_log"}) is True


def test_should_use_retriever_intent_triggers_true():
    assert router.should_use_retriever("module.py", {"intent": "bug_fix"}) is True


def test_should_use_retriever_irrelevant_taskinfo_is_false():
    info = {"intent": "small_talk", "input_mode": "question"}
    assert router.should_use_retriever("module.py", info) is False


# ===========================================================================
# should_auto_patch  (the live patch gate)
# ===========================================================================
def _agent_reviewer_info(**overrides):
    info = {"intent": "bug_fix", "complexity": "simple", "language": "python"}
    info.update(overrides)
    return info


def test_should_auto_patch_non_agent_audience_is_false():
    assert router.should_auto_patch("reviewer", "human", 0.95, _agent_reviewer_info()) is False


def test_should_auto_patch_non_reviewer_mode_is_false():
    assert router.should_auto_patch("tutor", "agent", 0.95, _agent_reviewer_info()) is False


def test_should_auto_patch_low_confidence_is_false():
    assert router.should_auto_patch("reviewer", "agent", 0.69, _agent_reviewer_info()) is False


def test_should_auto_patch_unknown_language_is_false():
    info = _agent_reviewer_info(language="unknown")
    assert router.should_auto_patch("reviewer", "agent", 0.95, info) is False


def test_should_auto_patch_no_taskinfo_is_true():
    # audience/mode/confidence all satisfied and task_info is None -> True.
    assert router.should_auto_patch("reviewer", "agent", 0.95, None) is True


def test_should_auto_patch_architecture_intent_is_false():
    info = _agent_reviewer_info(intent="architecture_planning")
    assert router.should_auto_patch("reviewer", "agent", 0.95, info) is False


def test_should_auto_patch_workflow_orchestration_intent_is_false():
    info = _agent_reviewer_info(intent="workflow_orchestration")
    assert router.should_auto_patch("reviewer", "agent", 0.95, info) is False


def test_should_auto_patch_extreme_complexity_is_false():
    info = _agent_reviewer_info(complexity="extreme")
    assert router.should_auto_patch("reviewer", "agent", 0.95, info) is False


def test_should_auto_patch_happy_path_is_true():
    assert router.should_auto_patch("reviewer", "agent", 0.95, _agent_reviewer_info()) is True


def test_should_auto_patch_confidence_threshold_is_inclusive_at_0_7():
    # confidence < 0.7 is rejected; exactly 0.7 passes the threshold.
    assert router.should_auto_patch("reviewer", "agent", 0.7, _agent_reviewer_info()) is True


# ===========================================================================
# classify_task
# ===========================================================================
def test_classify_task_intent_hint_short_circuits_embeddings():
    out = router.classify_task("please fix this bug", mode="tutor", language="python", audience="agent")
    assert out["intent"] == "bug_fix"
    assert out["complexity"] == "complex"  # "bug" is a complex signal
    assert out["language"] == "python"
    assert out["mode"] == "tutor"
    assert out["audience"] == "agent"


@pytest.mark.parametrize(
    ("mode", "expected_intent"),
    [
        ("reviewer", "code_review"),
        ("planner", "architecture_planning"),
        ("tutor", "code_explanation"),
    ],
)
def test_classify_task_embeddings_disabled_mode_fallback(mode, expected_intent):
    # Neutral prompt carries no intent hint; with embeddings off the mode-based
    # fallback decides the intent.
    out = router.classify_task("neutral wording only", mode=mode, language="python", audience="human")
    assert out["intent"] == expected_intent


def test_classify_task_unknown_language_is_inferred_from_prompt():
    # No hint, embeddings off, language "unknown" -> detect_language(prompt).
    out = router.classify_task("interface Shape { area(): number }", mode="tutor", language="unknown")
    assert out["language"] == "typescript"


def test_classify_task_embedding_branch_selects_argmax_label(monkeypatch):
    # Re-enable the embedding router and inject deterministic fakes so the
    # cosine/argmax wiring is characterized without loading any real model.
    monkeypatch.setenv("ROUTER_USE_EMBEDDINGS", "true")

    n = len(config.TASK_LABELS)
    target_index = config.TASK_LABELS.index("refactor")

    class _FakeModel:
        def encode(self, prompts):
            # Return a one-hot query vector selecting the target label.
            return np.array([np.eye(n)[target_index]])

    monkeypatch.setattr(router, "get_model", lambda: _FakeModel())
    monkeypatch.setattr(router, "get_label_embeddings", lambda: np.eye(n))

    out = router.classify_task("neutral wording only", mode="tutor", language="python", audience="human")
    assert out["intent"] == "refactor"


# ===========================================================================
# _cosine_scores  (pure)
# ===========================================================================
def test_cosine_scores_identity_is_one_hot():
    labels = np.eye(3)
    query = np.array([0.0, 1.0, 0.0])
    scores = router._cosine_scores(query, labels)
    assert int(np.argmax(scores)) == 1
    assert scores[1] == pytest.approx(1.0)


# ===========================================================================
# route_request  (integration over the public surface)
# ===========================================================================
def test_route_request_shape_and_wiring():
    result = router.route_request(
        user_input="please fix this bug",
        mode="reviewer",
        audience="agent",
        file_path="app.py",
    )
    assert set(result.keys()) == {"input_mode", "language", "task_info"}
    assert result["language"] == "python"  # from app.py extension
    assert result["input_mode"] == "question"  # "fix this bug" has no code/error signal

    task_info = result["task_info"]
    assert task_info["intent"] == "bug_fix"
    assert task_info["input_mode"] == "question"
    # .py is supported and intent bug_fix is retrieval-eligible.
    assert task_info["use_retriever"] is True


def test_route_request_unsupported_file_disables_retriever():
    result = router.route_request(
        user_input="just a question",
        mode="tutor",
        audience="human",
        file_path="notes.unknownext",
    )
    assert result["task_info"]["use_retriever"] is False


# ===========================================================================
# AST self-guard: this characterization slice introduces no forbidden behavior
# ===========================================================================
def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def test_router_gating_test_has_no_forbidden_sinks():
    tree = ast.parse(THIS_FILE.read_text(encoding="utf-8"))
    imported_roots = _imported_roots(tree)
    called = _called_names(tree)

    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "subprocess",
        "socket",
        "sentence_transformers",
        "torch",
    }
    assert imported_roots.isdisjoint(forbidden_import_roots)

    forbidden_calls = {
        "ChatCompletion",
        "generate_content",
        "run_gemini",
        "run_ollama",
        "apply_patch_plan",
        "commit",
        "execute",
        "executemany",
        "run_benchmark",
        "run_benchmarks",
        "Popen",
        "check_call",
        "check_output",
        "system",
        "unlink",
        "rmtree",
        "remove",
    }
    assert forbidden_calls.isdisjoint(called)
