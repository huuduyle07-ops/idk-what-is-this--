from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core import review_pack_generator


def _debug_goal_brief() -> dict:
    return {
        "title": "Debug checkout failure",
        "problem_statement": "Checkout raises a traceback when payment auth fails.",
        "desired_outcome": "Checkout shows a friendly error and the failing test passes.",
        "suspected_files_or_areas": ["core/checkout.py", "tests/test_checkout.py"],
        "constraints": ["Draft-only review pack source."],
        "safety_notes": ["Do not edit .env."],
        "validation_hints": ["python -m pytest tests/test_checkout.py -q"],
    }


def test_complete_debug_brief_creates_worker_prompt():
    result = review_pack_generator.generate_review_pack(
        goal_brief=_debug_goal_brief(),
        mode_router_result={"suggested_mode": "debug", "risk_notes": ["credentials/secrets"]},
        repo_path="C:/repo/app",
        worker_target="claude",
    )

    assert result["ok"] is True
    draft = result["draft"]
    assert draft["worker_target"] == "claude"
    assert draft["recommended_mode"] == "debug"
    assert "Checkout raises a traceback" in draft["task_prompt"]
    assert "do not apply patches" in draft["task_prompt"].lower()
    assert "do not commit" in draft["task_prompt"].lower()
    assert "do not push" in draft["task_prompt"].lower()
    assert "ask before touching forbidden files" in draft["task_prompt"].lower()
    assert "report changed files and validation evidence" in draft["task_prompt"].lower()
    assert "core/checkout.py" in draft["allowed_files"]
    assert "python -m pytest tests/test_checkout.py -q" in draft["validation_hints"]
    assert not draft["missing_information"]


def test_migration_project_evolution_brief_creates_broader_planning_prompt():
    result = review_pack_generator.generate_review_pack(
        goal_brief={
            "title": "Provider replacement migration",
            "problem_statement": "Replace provider architecture project-wide.",
            "desired_outcome": "A migration plan with scoped phases.",
            "suspected_files_or_areas": ["core/providers.py"],
            "validation_hints": ["python -m pytest tests -q"],
        },
        mode_router_result={"suggested_mode": "project_evolution"},
        worker_target="generic",
    )

    draft = result["draft"]
    assert draft["recommended_mode"] == "project_evolution"
    assert "planning-oriented review" in draft["task_prompt"].lower()
    assert "phase" in draft["expected_deliverable"].lower()


def test_missing_validation_becomes_todo():
    draft = review_pack_generator.generate_review_pack(
        goal_brief={
            "title": "Explain config loading",
            "problem_statement": "Explain how config loading works.",
            "desired_outcome": "Clear explanation.",
        },
        mode_router_result={"suggested_mode": "explain"},
    )["draft"]

    joined = "\n".join(draft["validation_hints"] + draft["missing_information"])
    assert "TODO" in joined
    assert "validation" in joined.lower()


def test_forbidden_files_are_preserved():
    draft = review_pack_generator.generate_review_pack(
        goal_brief=_debug_goal_brief(),
        handoff_draft={"forbidden_files": [".env", ".git", "secrets.json"]},
    )["draft"]

    assert ".env" in draft["forbidden_files"]
    assert ".git" in draft["forbidden_files"]
    assert "secrets.json" in draft["forbidden_files"]
    assert any(".env" in note for note in draft["safety_notes"])


@pytest.mark.parametrize("worker_target", ["claude", "codex", "gemini", "generic", "weird"])
def test_worker_target_changes_wording_lightly_but_not_safety_rules(worker_target: str):
    draft = review_pack_generator.generate_review_pack(
        goal_brief=_debug_goal_brief(),
        mode_router_result={"suggested_mode": "debug"},
        worker_target=worker_target,
    )["draft"]

    expected_target = worker_target if worker_target in {"claude", "codex", "gemini", "generic"} else "generic"
    assert draft["worker_target"] == expected_target
    assert expected_target in draft["task_prompt"].lower()
    prompt = draft["task_prompt"].lower()
    assert "do not apply patches" in prompt
    assert "do not commit" in prompt
    assert "do not push" in prompt
    assert "ask before touching forbidden files" in prompt


def test_empty_goal_brief_returns_friendly_error():
    result = review_pack_generator.generate_review_pack(goal_brief={})

    assert result["ok"] is False
    assert "goal_brief" in result["error"]


def test_markdown_formatter_works():
    draft = review_pack_generator.generate_review_pack(
        goal_brief=_debug_goal_brief(),
        mode_router_result={"suggested_mode": "debug"},
    )["draft"]

    markdown = review_pack_generator.render_review_pack_markdown(draft)

    assert markdown.startswith("# Review Pack")
    assert "## Task Prompt" in markdown
    assert "do not apply patches" in markdown.lower()
    assert "## Missing Information" in markdown


def test_ast_guard_forbids_execution_and_external_integration_imports():
    source = Path(review_pack_generator.__file__).read_text(encoding="utf-8")
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
