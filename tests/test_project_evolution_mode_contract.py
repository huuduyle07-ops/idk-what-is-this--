"""B.1 Project Evolution Mode contract tests.

This suite pins Evolution Mode as metadata and documentation only. It must not
wire into runtime patching, validation, benchmarks, models, lessons, Docker,
subprocesses, or web routes.
"""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, is_dataclass
from pathlib import Path

import pytest

from core.project_evolution_mode import (
    PROJECT_EVOLUTION_STAGES,
    ProjectEvolutionStage,
    canonical_evolution_stage_names,
    get_project_evolution_stages,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs" / "project_evolution_mode.md"
UPGRADE_DOC_PATH = PROJECT_ROOT / "docs" / "project_map_upgrade_plan.md"
HELPER_PATH = PROJECT_ROOT / "core" / "project_evolution_mode.py"

EXPECTED_STAGE_NAMES = (
    "Intake",
    "Existing Map Inventory",
    "Project Map",
    "Architecture Read",
    "Impact Analysis",
    "Migration Plan",
    "Approval Gate",
    "Patch Execution",
    "Evidence",
)


def test_stage_order_is_exact_and_stable():
    assert canonical_evolution_stage_names() == EXPECTED_STAGE_NAMES
    assert tuple(stage.name for stage in PROJECT_EVOLUTION_STAGES) == EXPECTED_STAGE_NAMES


def test_stage_names_are_unique():
    names = canonical_evolution_stage_names()
    assert len(names) == len(set(names))


def test_stage_metadata_shape_is_frozen_and_tuple_based():
    assert is_dataclass(ProjectEvolutionStage)
    assert ProjectEvolutionStage.__dataclass_params__.frozen is True
    assert isinstance(PROJECT_EVOLUTION_STAGES, tuple)
    assert get_project_evolution_stages() is PROJECT_EVOLUTION_STAGES

    stage = PROJECT_EVOLUTION_STAGES[0]
    with pytest.raises(FrozenInstanceError):
        stage.name = "Changed"

    for field_name in ("responsibilities", "artifacts", "approval", "guardrails"):
        assert isinstance(getattr(stage, field_name), tuple)


def test_every_stage_has_required_contract_fields():
    for stage in PROJECT_EVOLUTION_STAGES:
        assert isinstance(stage, ProjectEvolutionStage)
        assert stage.name
        assert stage.description.strip()
        assert stage.responsibilities and _all_nonblank(stage.responsibilities)
        assert stage.artifacts and _all_nonblank(stage.artifacts)
        assert stage.approval and _all_nonblank(stage.approval)
        assert stage.guardrails and _all_nonblank(stage.guardrails)


def test_docs_exist_and_pin_debug_mode_separation_and_approval_rules():
    evolution_text = DOC_PATH.read_text(encoding="utf-8")
    lowered = evolution_text.lower()

    for name in EXPECTED_STAGE_NAMES:
        assert f"## {name}" in evolution_text

    required_phrases = (
        "differs from Debug Mode",
        "Project Evolution Mode must not replace Debug Mode",
        "selected full files",
        "not blindly read every file",
        "migration plan before patching",
        "human approval before patch generation",
        "Semble",
        "optional future",
        "n8n",
        "GitHub",
        "Scholar",
        "Dream",
    )
    for phrase in required_phrases:
        assert phrase.lower() in lowered, f"evolution doc missing {phrase!r}"


def test_upgrade_doc_requires_reuse_of_existing_map_search_layers():
    text = UPGRADE_DOC_PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    required_phrases = (
        "reuse",
        "existing project map",
        "repo librarian",
        "indexer",
        "tree-sitter",
        "graph builder",
        "graph weights",
        "ripgrep",
        "MiniLM",
        "Semble",
        "candidate",
        "not the summarizer",
        "not required",
        "Debug Mode keeps using lightweight mapping",
        "Evolution Mode can request richer mapping",
        "generated/build folders to ignore",
        "full-file-read candidates",
        "migration risk notes",
    )
    for phrase in required_phrases:
        assert phrase.lower() in lowered, f"upgrade doc missing {phrase!r}"

    assert "duplicate" in lowered or "duplicated" in lowered


def test_project_evolution_helper_ast_guard_metadata_only():
    tree = ast.parse(HELPER_PATH.read_text(encoding="utf-8"))
    imports = _imported_modules(tree)
    calls = _called_names(tree)

    allowed_imports = {"__future__", "dataclasses", "typing"}
    assert imports <= allowed_imports

    forbidden_import_roots = {
        "agents",
        "api",
        "benchmarks",
        "core.control_engine",
        "core.executor",
        "core.indexer",
        "core.pipeline",
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
        "build_graph_from_repo",
        "connect",
        "create_lesson",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "index_repository",
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_validation_command",
        "system",
        "write_text",
    }

    assert imports.isdisjoint(forbidden_import_roots)
    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(
        {name.split(".", 1)[0] for name in forbidden_import_roots}
    )
    assert calls.isdisjoint(forbidden_calls)
    assert calls <= {"ProjectEvolutionStage", "dataclass", "tuple"}


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
