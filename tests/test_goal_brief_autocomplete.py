from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core import goal_brief_autocomplete


def test_messy_bug_report_becomes_debug_brief():
    result = goal_brief_autocomplete.autocomplete_goal_brief(
        "Fix the checkout traceback in core/checkout.py. Expected total should be 20.",
        repo_path="/repo/app",
        validation_hint="python -m pytest tests/test_checkout.py -q",
    )

    draft = result["draft"]
    assert result["ok"] is True
    assert draft["suggested_mode"] == "debug"
    assert "checkout traceback" in draft["problem_statement"].lower()
    assert "core/checkout.py" in draft["suspected_files_or_areas"]
    assert draft["validation_hints"] == ["python -m pytest tests/test_checkout.py -q"]
    assert "repo/path unknown" not in draft["open_questions"]


def test_explanation_request_becomes_explain_brief():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Can you explain why the graph weights work this way and teach me how does attraction affect nodes?",
        repo_path="/repo/app",
    )["draft"]

    assert draft["suggested_mode"] == "explain"
    assert "explain" in draft["title"].lower()


def test_benchmark_request_becomes_benchmark_brief():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Build a benchmark suite case for the discount regression.",
        repo_path="/repo/app",
    )["draft"]

    assert draft["suggested_mode"] == "benchmark"


def test_replay_request_becomes_replay_brief():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Replay the previous run and compare why the proposal changed.",
        repo_path="/repo/app",
    )["draft"]

    assert draft["suggested_mode"] == "replay"


def test_migration_request_becomes_project_evolution_brief():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Plan a migration to replace provider usage across this multi-file architecture.",
        repo_path="/repo/app",
    )["draft"]

    assert draft["suggested_mode"] == "project_evolution"


def test_dangerous_text_appears_in_safety_notes_not_executed():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Delete files, edit .env with secrets, install packages, and run shell commands for a broad project rewrite.",
        repo_path="/repo/app",
    )["draft"]

    notes = " ".join(draft["safety_notes"]).lower()
    assert "delete files" in notes
    assert "edit .env" in notes
    assert "install packages" in notes
    assert "run shell commands" in notes
    assert "broad project rewrite" in notes
    assert "credentials/secrets" in notes
    assert draft["constraints"]


def test_empty_input_returns_friendly_error():
    result = goal_brief_autocomplete.autocomplete_goal_brief("   ")

    assert result == {
        "ok": False,
        "error": "messy_intent must be a non-empty string",
    }


def test_markdown_formatter_works():
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        "Fix failing test in tests/test_cart.py",
        repo_path="/repo/app",
        validation_hint="python -m pytest tests/test_cart.py -q",
    )["draft"]

    markdown = goal_brief_autocomplete.render_goal_brief_draft_markdown(draft)

    assert markdown.startswith("# Goal Brief Draft")
    assert "## Suggested Mode" in markdown
    assert "- tests/test_cart.py" in markdown
    assert "python -m pytest tests/test_cart.py -q" in markdown


def test_ast_guard_forbids_execution_and_external_integration_imports():
    source_path = Path(goal_brief_autocomplete.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_import_roots = {
        "subprocess",
        "docker",
        "sqlite3",
        "database",
        "openai",
        "anthropic",
        "google",
        "requests",
        "httpx",
        "urllib",
        "patching",
        "benchmarks",
        "agents",
    }
    forbidden_call_names = {
        "apply_patch",
        "run_patch_plan_with_artifacts",
        "run_benchmarks",
        "validate",
        "run_validation",
        "promote_lesson",
        "create_lesson",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_import_roots
        elif isinstance(node, ast.ImportFrom):
            module_root = (node.module or "").split(".")[0]
            assert module_root not in forbidden_import_roots
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                assert func.id not in forbidden_call_names
            elif isinstance(func, ast.Attribute):
                assert func.attr not in forbidden_call_names


@pytest.mark.parametrize(
    ("intent", "mode"),
    [
        ("dream up a research trial idea", "dream"),
        ("just summarize this vague task", "unknown"),
    ],
)
def test_remaining_mode_rules(intent: str, mode: str):
    draft = goal_brief_autocomplete.autocomplete_goal_brief(
        intent,
        repo_path="/repo/app",
    )["draft"]

    assert draft["suggested_mode"] == mode
