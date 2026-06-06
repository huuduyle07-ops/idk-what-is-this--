"""A.2 debug workflow stage-map contract tests.

This suite pins the workflow map as inert metadata and documentation only. It
must not execute the runtime pipeline, validation, patching, benchmarks, models,
lessons, Docker, subprocesses, web routes, or database code.
"""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

from core.debug_workflow import (
    DEBUG_WORKFLOW_STAGES,
    DebugWorkflowStage,
    canonical_stage_names,
    get_debug_workflow_stages,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "debug_workflow_map.md"
HELPER_PATH = PROJECT_ROOT / "core" / "debug_workflow.py"

EXPECTED_STAGE_NAMES = (
    "Intake",
    "Context",
    "Proposal",
    "Safety",
    "Execution",
    "Validation",
    "Evidence",
    "Learning",
)

EXPECTED_RESPONSIBILITY_TERMS = {
    "Intake": ("repo path", "query", "mode/options", "validation intent", "per-run toggles"),
    "Context": ("CONTROL prompt assembly", "Scout snippets", "graph evidence", "active lessons"),
    "Proposal": ("model draft", "answer", "patch candidate", "patch plan", "candidate alternatives"),
    "Safety": ("patch safety", "path traversal guard", "forbidden files", "validation command safety"),
    "Execution": ("patch apply", "executor", "lifecycle runner", "temp clone", "sandbox boundary"),
    "Validation": ("validation output", "self-correct attempts", "failure taxonomy"),
    "Evidence": ("replay bundle", "benchmark report", "diff", "raw JSON", "run details"),
    "Learning": ("lesson candidates", "anti-lessons", "lesson promotion", "default-off memory"),
}

DOC_REQUIRED_PHRASES = (
    "CONTROL",
    "patch safety",
    "validation command safety",
    "replay",
    "benchmark report",
    "failure taxonomy",
    "lesson retrieval",
    "anti-lessons default-off two-key gate",
    "harness controls",
)


def test_stage_order_is_exact_and_stable():
    assert canonical_stage_names() == EXPECTED_STAGE_NAMES
    assert tuple(stage.name for stage in DEBUG_WORKFLOW_STAGES) == EXPECTED_STAGE_NAMES


def test_stage_names_are_unique():
    names = canonical_stage_names()
    assert len(names) == len(set(names))


def test_stage_metadata_shape_is_frozen_and_tuple_based():
    assert is_dataclass(DebugWorkflowStage)
    assert DebugWorkflowStage.__dataclass_params__.frozen is True
    assert isinstance(DEBUG_WORKFLOW_STAGES, tuple)
    assert get_debug_workflow_stages() is DEBUG_WORKFLOW_STAGES

    stage = DEBUG_WORKFLOW_STAGES[0]
    with pytest.raises(FrozenInstanceError):
        stage.name = "Changed"

    for field_name in (
        "responsibilities",
        "modules",
        "artifacts",
        "approval",
        "guardrails",
    ):
        assert isinstance(getattr(stage, field_name), tuple)


def test_every_stage_has_required_contract_fields():
    for stage in DEBUG_WORKFLOW_STAGES:
        assert isinstance(stage, DebugWorkflowStage)
        assert stage.name
        assert stage.description.strip()
        assert stage.responsibilities and _all_nonblank(stage.responsibilities)
        assert stage.modules and _all_nonblank(stage.modules)
        assert stage.artifacts and _all_nonblank(stage.artifacts)
        assert stage.approval and _all_nonblank(stage.approval)
        assert stage.guardrails and _all_nonblank(stage.guardrails)


def test_stage_responsibilities_pin_required_terms():
    by_name = {stage.name: stage for stage in DEBUG_WORKFLOW_STAGES}
    assert set(by_name) == set(EXPECTED_STAGE_NAMES)
    for stage_name, terms in EXPECTED_RESPONSIBILITY_TERMS.items():
        text = "\n".join(by_name[stage_name].responsibilities)
        for term in terms:
            assert term in text, f"{stage_name} missing responsibility term {term!r}"


def test_docs_exist_and_mention_required_contract_terms():
    text = DOC_PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    for name in EXPECTED_STAGE_NAMES:
        assert f"## {name}" in text

    for phrase in DOC_REQUIRED_PHRASES:
        assert phrase.lower() in lowered, f"doc missing {phrase!r}"


def test_debug_workflow_helper_ast_guard_metadata_only():
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    allowed_imports = {"__future__", "dataclasses", "typing"}
    assert imports <= allowed_imports

    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "core.executor",
        "core.pipeline",
        "core.run_lifecycle",
        "core.validation_command",
        "core.validator",
        "database",
        "docker",
        "mcp_server",
        "patching",
        "requests",
        "subprocess",
        "web",
    }
    forbidden_calls = {
        "ChatCompletion",
        "Popen",
        "apply_patch",
        "apply_patch_plan",
        "check_call",
        "check_output",
        "commit",
        "connect",
        "create_lesson",
        "create_lesson_candidate",
        "execute",
        "executemany",
        "from_env",
        "generate_content",
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_deepseek_review",
        "run_gemini_request",
        "run_patch_plan_with_artifacts",
        "run_validation_command",
        "save_lesson",
        "set_override",
        "start_overnight_async",
        "system",
        "write_bytes",
        "write_text",
    }

    assert imports.isdisjoint(forbidden_import_roots)
    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(
        {name.split(".", 1)[0] for name in forbidden_import_roots}
    )
    assert calls.isdisjoint(forbidden_calls)
    assert calls <= {"DebugWorkflowStage", "dataclass", "tuple"}


def _all_nonblank(values: tuple[str, ...]) -> bool:
    return all(isinstance(value, str) and value.strip() for value in values)


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names
