from __future__ import annotations

import ast
from pathlib import Path

from core import handoff_composer


def _goal_brief() -> dict:
    return {
        "goal": "Fix checkout total regression",
        "problem_type": "bug_fix",
        "evidence": {
            "expected_result": "checkout total is 20",
            "actual_result": "checkout total is 19",
            "error_output": "FAILED test_checkout_total",
            "changed_files": ["core/checkout.py"],
        },
        "constraints": {
            "allowed_files": ["core/checkout.py"],
            "forbidden_files": ["database/schema.sql"],
            "do_not_weaken": ["Do not loosen total assertions"],
        },
        "validation": {
            "command": "python -m pytest tests/test_checkout.py -q",
            "success_criteria": "pytest exits 0",
        },
    }


def test_normal_goal_brief_becomes_handoff_draft():
    result = handoff_composer.compose_handoff_draft(
        goal_brief=_goal_brief(),
        repo_path="/repo/app",
    )

    draft = result["draft"]
    assert result["ok"] is True
    assert draft["title"] == "Fix checkout total regression"
    assert "checkout total is 19" in draft["task_summary"]
    assert draft["repo_path"] == "/repo/app"
    assert draft["allowed_files"] == ["core/checkout.py"]
    assert "database/schema.sql" in draft["forbidden_files"]
    assert ".env" in draft["forbidden_files"]
    assert "tests" in draft["forbidden_files"]
    assert draft["validation_command"] == "python -m pytest tests/test_checkout.py -q"
    assert draft["human_approved_for_proposal"] is False


def test_missing_allowed_files_creates_open_question():
    brief = _goal_brief()
    brief["constraints"]["allowed_files"] = []

    draft = handoff_composer.compose_handoff_draft(goal_brief=brief)["draft"]

    assert draft["allowed_files"] == []
    assert "Choose the allowed files for this handoff." in draft["open_questions"]


def test_missing_validation_creates_open_question():
    brief = _goal_brief()
    brief["validation"]["command"] = ""

    draft = handoff_composer.compose_handoff_draft(goal_brief=brief)["draft"]

    assert draft["validation_command"] == ""
    assert "Provide the validation command for this handoff." in draft["open_questions"]


def test_risky_files_are_placed_in_risk_and_safety_notes():
    draft = handoff_composer.compose_handoff_draft(
        goal_brief={
            "goal": "Update config",
            "constraints": {"allowed_files": [".env", "tests/test_config.py", ".agent/state.json"]},
            "validation": {"command": "python -m pytest tests/test_config.py -q"},
        },
    )["draft"]

    risk = " ".join(draft["risk_notes"]).lower()
    safety = " ".join(draft["safety_notes"]).lower()
    assert ".env" in risk
    assert "tests/test_config.py" in risk
    assert ".agent/state.json" in risk
    assert ".env" in safety
    assert "tests" in safety


def test_human_approved_for_proposal_is_always_false():
    draft = handoff_composer.compose_handoff_draft(
        goal_brief=_goal_brief(),
        human_approved_for_proposal=True,
    )["draft"]

    assert draft["human_approved_for_proposal"] is False


def test_markdown_formatter_works():
    draft = handoff_composer.compose_handoff_draft(goal_brief=_goal_brief())["draft"]

    markdown = handoff_composer.render_handoff_draft_markdown(draft)

    assert markdown.startswith("# Handoff Draft")
    assert "## Task Summary" in markdown
    assert "- core/checkout.py" in markdown
    assert "human_approved_for_proposal: false" in markdown


def test_ast_guard_forbids_execution_and_external_integration_imports():
    source = Path(handoff_composer.__file__).read_text(encoding="utf-8")
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
