"""B.10 Project Evolution Review Gate contract tests."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import project_evolution_review_gate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "core" / "project_evolution_review_gate.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_evolution_review_gate.py"


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-project-evolution-review-gate"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------

def test_builds_review_gate_from_minimal_executable_patch_draft(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["status"] == "ok"
    assert record["mode"] == "project_evolution_review_gate"
    assert record["schema_version"] == "evolution_review_gate_v1"
    assert record["draft_id"] == draft_path.stem
    assert record["source_draft_path"] == str(draft_path)
    assert record["apply_allowed"] is False
    assert record["human_approval_required"] is True
    assert record["approval_status"] == "pending"
    assert isinstance(record["affected_files"], list)
    assert isinstance(record["planned_edit_count"], int)
    assert record["risk_level"] in ("low", "medium", "high")
    assert isinstance(record["risk_reasons"], list)
    assert isinstance(record["missing_evidence"], list)
    assert record["rollback_notes_required"] is True
    assert isinstance(record["tests_required"], list)
    assert isinstance(record["docs_required"], list)
    assert isinstance(record["reviewer_checklist"], list)
    decision = record["final_decision"]
    assert "APPROVE_MANUAL_REVIEW_ONLY" in decision["options"]
    assert "REQUEST_CHANGES" in decision["options"]
    assert "REJECT" in decision["options"]
    assert decision["selected"] is None


def test_emits_json_and_markdown(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    out = project_evolution_review_gate.write_project_evolution_review_gate_artifacts(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file(), "JSON artifact was not written"
    assert md_path.is_file(), "Markdown artifact was not written"
    assert json_path.name.endswith("_review_gate.json")
    assert md_path.name.endswith("_review_gate.md")

    review_root = (repo / ".agent" / "project_evolution" / "review_gates").resolve()
    json_path.resolve().relative_to(review_root)
    md_path.resolve().relative_to(review_root)

    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted == out["record"]


def test_apply_allowed_is_always_false(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["apply_allowed"] is False


def test_human_approval_required_is_true(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["human_approval_required"] is True


def test_approval_status_defaults_to_pending(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["approval_status"] == "pending"


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

def test_high_risk_for_dependency_config_runtime_files(tmp_path):
    repo, draft_path = _seed_draft_with_content(
        tmp_path,
        target_files=[
            {"path": "config.py", "candidate_id": "c1", "category": "config", "reason": "config", "confidence": 0.9},
            {"path": "requirements.txt", "candidate_id": "c1", "category": "dependency", "reason": "deps", "confidence": 0.9},
        ],
        edit_units=[_make_unit("c1", "config.py"), _make_unit("c1", "requirements.txt")],
        tests_required_later=["run regression tests"],
        rollback_notes=["revert config changes if broken"],
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["risk_level"] == "high"
    assert record["risk_reasons"]
    combined = " ".join(record["risk_reasons"])
    assert "config" in combined or "dependency" in combined or "protected" in combined


def test_high_risk_for_many_affected_files(tmp_path):
    files = [
        {"path": f"core/module_{i}.py", "candidate_id": "c1", "category": "provider", "reason": "test", "confidence": 0.8}
        for i in range(6)
    ]
    units = [_make_unit("c1", f["path"]) for f in files]
    repo, draft_path = _seed_draft_with_content(
        tmp_path,
        target_files=files,
        edit_units=units,
        tests_required_later=["run tests"],
        rollback_notes=["revert if broken"],
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["risk_level"] == "high"
    assert any("6" in r for r in record["risk_reasons"])


def test_medium_risk_when_tests_missing(tmp_path):
    repo, draft_path = _seed_draft_with_content(
        tmp_path,
        target_files=[_single_safe_file()],
        edit_units=[_make_unit("c1", "core/search.py")],
        tests_required_later=[],
        rollback_notes=["revert if broken"],
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["risk_level"] in ("medium", "high")
    combined = " ".join(record["risk_reasons"])
    assert "test" in combined.lower()


def test_medium_risk_when_rollback_notes_missing(tmp_path):
    repo, draft_path = _seed_draft_with_content(
        tmp_path,
        target_files=[_single_safe_file()],
        edit_units=[_make_unit("c1", "core/search.py")],
        tests_required_later=["run regression suite"],
        rollback_notes=[],
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["risk_level"] in ("medium", "high")
    combined = " ".join(record["risk_reasons"])
    assert "rollback" in combined.lower()


def test_low_risk_only_for_small_complete_drafts(tmp_path):
    repo, draft_path = _seed_draft_with_content(
        tmp_path,
        target_files=[_single_safe_file()],
        edit_units=[_make_unit("c1", "core/search.py")],
        tests_required_later=["run focused search tests"],
        rollback_notes=["revert core/search.py if output shape changes"],
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert record["risk_level"] == "low"


# ---------------------------------------------------------------------------
# Mutation guards
# ---------------------------------------------------------------------------

def test_source_draft_is_not_mutated(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)
    original = draft_path.read_text(encoding="utf-8")

    project_evolution_review_gate.write_project_evolution_review_gate_artifacts(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert draft_path.read_text(encoding="utf-8") == original


def test_source_repo_files_are_not_modified(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)
    source_file = repo / "core" / "search.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("def search(): pass\n", encoding="utf-8")
    original = source_file.read_text(encoding="utf-8")

    project_evolution_review_gate.write_project_evolution_review_gate_artifacts(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    assert source_file.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_writes_artifacts_under_review_gates(tmp_path, capsys):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    from scripts import create_evolution_review_gate as cli

    rc = cli.main(
        [
            "--repo-path", str(repo),
            "--executable-patch-draft-path", str(draft_path),
        ]
    )

    assert rc == 0
    output = capsys.readouterr().out
    assert "json_path:" in output
    assert "md_path:" in output
    assert "risk_level:" in output
    assert "apply_allowed:" in output
    assert "approval_status:" in output
    review_root = repo / ".agent" / "project_evolution" / "review_gates"
    assert review_root.exists()
    assert any(f.suffix == ".json" for f in review_root.iterdir())
    assert any(f.suffix == ".md" for f in review_root.iterdir())


def test_cli_returns_nonzero_on_missing_draft(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    missing = repo / ".agent" / "project_evolution" / "executable_patch_drafts" / "missing.json"

    from scripts import create_evolution_review_gate as cli

    rc = cli.main(
        [
            "--repo-path", str(repo),
            "--executable-patch-draft-path", str(missing),
        ]
    )

    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# Security: path traversal
# ---------------------------------------------------------------------------

def test_path_traversal_is_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps({"schema_version": "evolution_executable_patch_draft_v1", "status": "ok"}),
        encoding="utf-8",
    )

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(secrets),
    )

    assert record["status"] == "error"
    assert record["error"]["code"] == "draft_path_outside_executable_patch_drafts"
    assert record["apply_allowed"] is False


def test_relative_path_traversal_is_blocked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path="../../secrets.json",
    )

    assert record["status"] == "error"
    assert record["error"]["code"] == "draft_path_outside_executable_patch_drafts"


# ---------------------------------------------------------------------------
# Error records still enforce gates
# ---------------------------------------------------------------------------

def test_error_record_still_has_apply_allowed_false(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    missing = repo / ".agent" / "project_evolution" / "executable_patch_drafts" / "missing.json"

    record = project_evolution_review_gate.build_project_evolution_review_gate(
        repo_path=str(repo),
        executable_patch_draft_path=str(missing),
    )

    assert record["status"] == "error"
    assert record["apply_allowed"] is False
    assert record["human_approval_required"] is True
    assert record["approval_status"] == "pending"


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def test_markdown_includes_guardrail_text(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    out = project_evolution_review_gate.write_project_evolution_review_gate_artifacts(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    md = Path(out["md_path"]).read_text(encoding="utf-8")
    assert "# Project Evolution Review Gate" in md
    assert "This phase is review-only." in md
    assert "No patch was generated or applied." in md
    assert "apply_allowed remains false." in md
    assert "Human approval is required before any future apply step." in md
    assert "This report is not permission to mutate the repository." in md


def test_markdown_has_all_required_sections(tmp_path):
    repo, draft_path = _seed_minimal_draft(tmp_path)

    out = project_evolution_review_gate.write_project_evolution_review_gate_artifacts(
        repo_path=str(repo),
        executable_patch_draft_path=str(draft_path),
    )

    md = Path(out["md_path"]).read_text(encoding="utf-8")
    for section in (
        "## Decision",
        "## Summary",
        "## Risk Classification",
        "## Affected Files",
        "## Planned Edit Units",
        "## Missing Evidence",
        "## Required Tests",
        "## Required Docs",
        "## Rollback Notes",
        "## Reviewer Checklist",
        "## Guardrails",
    ):
        assert section in md, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# Purity: no forbidden imports or calls
# ---------------------------------------------------------------------------

def test_no_forbidden_imports_or_calls():
    trees = [
        ast.parse(MODULE_PATH.read_text(encoding="utf-8")),
        ast.parse(SCRIPT_PATH.read_text(encoding="utf-8")),
    ]
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in trees:
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "docker",
        "openai",
        "patching",
        "requests",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "validator",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.debug_workflow",
        "core.executor",
        "core.mode_router",
        "core.run_lifecycle",
        "core.validator",
        "database",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
        "build_graph_from_repo",
        "call_api",
        "call_model",
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
        "Popen",
        "system",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), (
        f"Forbidden import roots found: {imported_roots & forbidden_import_roots}"
    )
    assert imports.isdisjoint(forbidden_imports), (
        f"Forbidden imports found: {imports & forbidden_imports}"
    )
    assert calls.isdisjoint(forbidden_calls), (
        f"Forbidden calls found: {calls & forbidden_calls}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_minimal_draft(tmp_path: Path) -> tuple[Path, Path]:
    return _seed_draft_with_content(
        tmp_path,
        target_files=[_single_safe_file()],
        edit_units=[_make_unit("c1", "core/search.py")],
        tests_required_later=[],
        rollback_notes=[],
    )


def _seed_draft_with_content(
    tmp_path: Path,
    *,
    target_files: list[dict[str, Any]],
    edit_units: list[dict[str, Any]],
    tests_required_later: list[str],
    rollback_notes: list[str],
    **extra: Any,
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    drafts_dir = repo / ".agent" / "project_evolution" / "executable_patch_drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    draft: dict[str, Any] = {
        "generated_at": "2026-06-10T12:00:00Z",
        "repo_path": str(repo),
        "mode": "project_evolution",
        "schema_version": "evolution_executable_patch_draft_v1",
        "status": "ok",
        "migration_goal": "Test migration",
        "source_plan_hash": "abc123def456",
        "approval_path": str(repo / ".agent" / "project_evolution" / "approvals" / "approval.json"),
        "patch_draft_package_path": str(repo / ".agent" / "project_evolution" / "patch_drafts" / "draft.json"),
        "patch_candidates_path": str(repo / ".agent" / "project_evolution" / "patch_candidates" / "candidates.json"),
        "patch_text_draft_path": str(repo / ".agent" / "project_evolution" / "patch_text_drafts" / "text.json"),
        "approval_verified": True,
        "approval_decision": "approve",
        "executable_patch_draft_only": True,
        "source_files_mutated": False,
        "real_repo_apply_allowed": False,
        "sandbox_apply_allowed_later": True,
        "validation_execution_allowed": False,
        "requires_patch_safety_before_apply": True,
        "requires_sandbox_before_validation": True,
        "target_files": target_files,
        "executable_edit_units": edit_units,
        "tests_required_later": tests_required_later,
        "rollback_notes": rollback_notes,
        "risks": [],
        "limitations": ["Placeholder draft for testing."],
        "human_next_steps": ["Review."],
        **extra,
    }

    draft_path = drafts_dir / "20260610T120000Z_executable_patch_draft.json"
    draft_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
    return repo, draft_path


def _single_safe_file() -> dict[str, Any]:
    return {
        "path": "core/search.py",
        "candidate_id": "c1",
        "category": "provider",
        "reason": "provider surface",
        "confidence": 0.85,
    }


def _make_unit(candidate_id: str, target_file: str) -> dict[str, Any]:
    return {
        "edit_id": f"{candidate_id}-01",
        "candidate_id": candidate_id,
        "target_file": target_file,
        "edit_type": "replace_text",
        "intent": "Update provider wiring",
        "anchor_strategy": "full_file_read_required_before_anchor_selection",
        "old_text": None,
        "new_text": None,
        "unified_diff": None,
        "apply_allowed": False,
        "sandbox_only_later": True,
        "requires_full_file_read": True,
        "safety_notes": ["placeholder"],
    }


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
