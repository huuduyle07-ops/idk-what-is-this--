from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core import mode_router


@pytest.mark.parametrize(
    ("intent", "mode"),
    [
        ("Fix the checkout traceback and failing test.", "debug"),
        ("Explain why the graph weights work this way.", "explain"),
        ("Build a benchmark suite case for the regression pass rate.", "benchmark"),
        ("Replay the previous run and compare the debug artifact.", "replay"),
        ("Run a dream trial for this research idea and refutation.", "dream_trial"),
        ("Plan a migration for this multi-file architecture provider replacement.", "project_evolution"),
        ("Delegate this to Claude as a subagent handoff.", "handoff"),
    ],
)
def test_each_mode_classification(intent: str, mode: str):
    result = mode_router.route_mode(intent)

    assert result["ok"] is True
    draft = result["draft"]
    assert draft["suggested_mode"] == mode
    assert draft["required_user_confirmation"] is True
    assert draft["reasons"]
    assert draft["next_safe_action"]


def test_ambiguous_request_returns_unknown_or_low_confidence():
    draft = mode_router.route_mode("Please look at this when you have time.")["draft"]

    assert draft["suggested_mode"] == "unknown"
    assert draft["confidence"] <= 0.4
    assert "Ask the user to clarify the intended workflow mode." in draft["next_safe_action"]


def test_risky_broad_rewrite_becomes_project_evolution_with_risk_notes():
    draft = mode_router.route_mode(
        "Project-wide broad rewrite to replace provider architecture and delete old files."
    )["draft"]

    assert draft["suggested_mode"] == "project_evolution"
    risks = " ".join(draft["risk_notes"]).lower()
    assert "broad project rewrite" in risks
    assert "delete files" in risks


def test_goal_brief_and_handoff_context_are_used_without_execution():
    draft = mode_router.route_mode(
        "",
        goal_brief={"suggested_mode": "debug", "problem_statement": "failing test"},
        handoff_draft={"title": "Worker handoff"},
    )["draft"]

    assert draft["suggested_mode"] == "handoff"
    assert any("handoff" in reason.lower() for reason in draft["reasons"])
    assert draft["required_user_confirmation"] is True


def test_empty_input_returns_friendly_error():
    result = mode_router.route_mode("   ")

    assert result == {
        "ok": False,
        "error": "user_intent must be a non-empty string or include goal/handoff context",
    }


def test_markdown_formatter_works():
    draft = mode_router.route_mode("Explain how replay comparison works.")["draft"]

    markdown = mode_router.render_mode_route_markdown(draft)

    assert markdown.startswith("# Mode Router Draft")
    assert "## Suggested Mode" in markdown
    assert "explain" in markdown
    assert "## Next Safe Action" in markdown


def test_ast_guard_forbids_execution_and_external_integration_imports():
    source = Path(mode_router.__file__).read_text(encoding="utf-8")
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
        "scripts",
    }
    forbidden_call_names = {
        "apply_patch",
        "run_patch_plan_with_artifacts",
        "run_benchmarks",
        "validate",
        "run_validation",
        "run_handoff",
        "create_handoff_note",
        "run_overnight",
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
