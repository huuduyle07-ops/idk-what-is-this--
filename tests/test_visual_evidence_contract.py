"""Tests for A.16 Visual Evidence Intake Contract.

The contract is pure / report-only: it inspects a Worker Assignment (F.5) or a
Driver Decision (H.1) and records whether a visual/UI/design issue is referenced
and whether a resolution claim is allowed. It must never perform OCR, call a
vision model, call any model, switch providers, launch a worker, apply a patch,
run validation, trigger Dream / Project Evolution execution, call webhooks, or
promote lessons.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import visual_evidence_contract as vec
from core.visual_evidence_contract import (
    MISSING_REQUIREMENTS,
    RISK_FLAGS,
    create_visual_evidence_contract,
    evaluate_visual_evidence_policy,
    render_visual_evidence_markdown,
)
from scripts import create_visual_evidence_contract as cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-visual-evidence"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Boilerplate that real F.5 worker assignments ALWAYS carry. These lines mention
# "visual evidence" and "secrets/env" but are generic guardrails, not
# task-specific signals. The contract must NOT treat them as visual triggers.
BOILERPLATE_STOP_CONDITIONS = [
    "Stop if required files are missing.",
    "Stop if the task requires files outside allowed scope.",
    "Stop if a validation command is unavailable or cannot be run in the worker environment.",
    "Stop if secrets/env/protected files are needed.",
    "Stop if patch safety would block the change.",
    "Stop if visual evidence is required but unavailable.",
    "Stop before applying real repo changes unless explicitly approved by the human.",
]
BOILERPLATE_SAFETY_RULES = [
    "Draft-only Worker Assignment / Route Card.",
    "Do not call models or external agents from assignment creation.",
    "Do not apply patches, commit, push, run validation, run benchmarks, start Dream, run Project Evolution execution, call webhooks, or promote lessons.",
    "Human approval is required before any worker action or repo mutation.",
    "apply_allowed remains false unless a human creates a separate explicit approval.",
]


def _wa(**overrides: Any) -> dict[str, Any]:
    """A realistic, NON-visual F.5 worker_assignment.json record."""
    base: dict[str, Any] = {
        "assignment_id": "wa-checkout",
        "created_at": "2026-01-01T00:00:00Z",
        "source_type": "goal_brief",
        "source_path": "/repo/.agent/goal_briefs/x/goal_brief.json",
        "title": "Fix checkout total regression",
        "mode": "Debug",
        "worker_role": "implementer",
        "repo_path": "/repo",
        "allowed_files": ["core/checkout.py"],
        "forbidden_files": [".env", ".agent", ".git"],
        "validation_commands": ["python -m pytest tests/test_checkout.py -q"],
        "stop_conditions": list(BOILERPLATE_STOP_CONDITIONS),
        "safety_rules": list(BOILERPLATE_SAFETY_RULES),
        "expected_output": "A concise worker report with findings, proposed changes, validation evidence, and blockers.",
        "human_approval_required": True,
        "apply_allowed": False,
        "worker_launch_allowed": False,
    }
    base.update(overrides)
    return base


def _visual_wa(**overrides: Any) -> dict[str, Any]:
    """A worker assignment that references a visual/UI issue (task-specific)."""
    base = _wa(
        title="Fix the dashboard chart rendering",
        expected_output="Compare the screenshot of the UI layout before and after the change.",
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------
# Stable constants
# --------------------------------------------------------------------------


def test_risk_flag_and_missing_requirement_constants_are_stable():
    assert set(RISK_FLAGS) == {
        "visual_evidence_unverified",
        "human_visual_summary_missing",
        "vision_model_unavailable",
        "validation_does_not_cover_visual_issue",
        "resolution_claim_not_allowed",
        "visual_paths_missing",
        "source_mentions_visual_issue",
    }
    assert set(MISSING_REQUIREMENTS) == {
        "human_visual_summary_or_vision_model",
        "visual_evidence_path_or_caption",
        "visual_verification_step",
        "explicit_visual_validation_coverage",
    }


# --------------------------------------------------------------------------
# Detection rules (pure policy)
# --------------------------------------------------------------------------


def test_non_visual_source_allows_resolution_claim():
    decision = evaluate_visual_evidence_policy(_wa())

    assert decision["visual_evidence_referenced"] is False
    assert decision["visual_verification_required"] is False
    assert decision["resolution_claim_allowed"] is True
    # Boilerplate stop conditions / safety rules must not create false positives.
    assert decision["risk_flags"] == []
    assert decision["missing_requirements"] == []


def test_visual_source_no_path_or_summary_requires_summary_and_blocks_claim():
    decision = evaluate_visual_evidence_policy(_visual_wa())

    assert decision["visual_evidence_referenced"] is True
    assert decision["human_visual_summary_required"] is True
    assert decision["visual_verification_required"] is True
    assert decision["resolution_claim_allowed"] is False
    assert "source_mentions_visual_issue" in decision["risk_flags"]
    assert "human_visual_summary_missing" in decision["risk_flags"]
    assert "resolution_claim_not_allowed" in decision["risk_flags"]


def test_visual_source_with_path_unreadable_model_no_summary_requires_summary():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(),
        visual_paths=["docs/dashboard_before.png"],
    )

    assert decision["visual_evidence_present"] is True
    assert decision["visual_evidence_paths"] == ["docs/dashboard_before.png"]
    # A path alone does not satisfy the requirement: model can't read it and
    # there's no human summary.
    assert decision["human_visual_summary_required"] is True
    assert decision["resolution_claim_allowed"] is False
    # Path supplied => visual_paths_missing must NOT be flagged.
    assert "visual_paths_missing" not in decision["risk_flags"]


def test_visual_source_with_summary_but_no_validation_coverage_blocks_claim():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(),
        human_summary="Before: chart bars overlap the legend. After: bars are spaced and the legend is clear.",
    )

    assert decision["human_visual_summary_required"] is False
    assert decision["validation_covers_visual_issue"] is False
    assert decision["resolution_claim_allowed"] is False
    assert "validation_does_not_cover_visual_issue" in decision["risk_flags"]
    assert "explicit_visual_validation_coverage" in decision["missing_requirements"]


def test_visual_source_with_summary_and_validation_coverage_allows_claim():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(),
        human_summary="Before: chart bars overlap the legend. After: bars are spaced and the legend is clear.",
        validation_covers_visual=True,
    )

    assert decision["human_visual_summary_required"] is False
    assert decision["validation_covers_visual_issue"] is True
    assert decision["visual_verification_required"] is False
    assert decision["resolution_claim_allowed"] is True
    assert "resolution_claim_not_allowed" not in decision["risk_flags"]


def test_visual_readable_by_model_true_reduces_human_summary_requirement():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(),
        visual_readable_by_model=True,
    )

    assert decision["visual_evidence_readable_by_model"] is True
    assert decision["human_visual_summary_required"] is False
    assert "human_visual_summary_missing" not in decision["risk_flags"]
    assert "vision_model_unavailable" not in decision["risk_flags"]


def test_visual_paths_stored_correctly():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(),
        visual_paths=["a.png", "b.png", "a.png"],
    )

    assert decision["visual_evidence_present"] is True
    assert decision["visual_evidence_paths"] == ["a.png", "b.png"]


def test_source_artifact_embedded_paths_are_picked_up():
    decision = evaluate_visual_evidence_policy(
        _visual_wa(visual_evidence_paths=["artifacts/ui_after.png"]),
    )

    assert decision["visual_evidence_present"] is True
    assert "artifacts/ui_after.png" in decision["visual_evidence_paths"]


def test_driver_decision_visual_vehicle_is_detected_as_visual():
    driver_decision = {
        "driver_decision_id": "dd-1",
        "title": "Investigate rendering issue",
        "recommended_vehicle": "vision_or_human_caption_required",
        "risk_flags": ["visual_evidence_unverified"],
        "reasons": ["Task references visual evidence; a vision model or human caption summary is required."],
    }
    decision = evaluate_visual_evidence_policy(driver_decision)

    assert decision["visual_evidence_referenced"] is True
    assert decision["resolution_claim_allowed"] is False


def test_risk_flags_are_stable_for_fully_unverified_visual_source():
    decision = evaluate_visual_evidence_policy(_visual_wa())

    assert decision["risk_flags"] == [
        "source_mentions_visual_issue",
        "visual_paths_missing",
        "vision_model_unavailable",
        "human_visual_summary_missing",
        "validation_does_not_cover_visual_issue",
        "visual_evidence_unverified",
        "resolution_claim_not_allowed",
    ]


def test_missing_requirements_are_stable_for_fully_unverified_visual_source():
    decision = evaluate_visual_evidence_policy(_visual_wa())

    assert decision["missing_requirements"] == [
        "visual_evidence_path_or_caption",
        "human_visual_summary_or_vision_model",
        "explicit_visual_validation_coverage",
        "visual_verification_step",
    ]


# --------------------------------------------------------------------------
# Contract record / JSON contract
# --------------------------------------------------------------------------


def test_contract_record_has_required_fields_and_inert_flags():
    result = create_visual_evidence_contract(
        source=_visual_wa(), dry_run=True, created_at="2026-01-01T00:00:00Z"
    )
    record = result["record"]

    required = [
        "visual_evidence_id",
        "created_at",
        "source_type",
        "source_path",
        "visual_evidence_present",
        "visual_evidence_referenced",
        "visual_evidence_paths",
        "visual_evidence_readable_by_model",
        "human_visual_summary",
        "human_visual_summary_required",
        "validation_covers_visual_issue",
        "visual_verification_required",
        "resolution_claim_allowed",
        "risk_flags",
        "missing_requirements",
        "reasons",
    ]
    for field in required:
        assert field in record, field

    assert record["source_type"] == "worker_assignment"

    inert = {
        "model_call_performed": False,
        "ocr_performed": False,
        "vision_model_called": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }
    for key, expected in inert.items():
        assert record[key] is expected, key


def test_markdown_includes_execution_boundary_and_sections():
    result = create_visual_evidence_contract(
        source=_visual_wa(),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        visual_evidence_id="md-check",
    )
    markdown = render_visual_evidence_markdown(result["record"])

    for heading in [
        "# Visual Evidence Contract",
        "## Source",
        "## Visual Evidence Status",
        "## Human Summary",
        "## Validation Coverage",
        "## Resolution Claim Status",
        "## Risk Flags",
        "## Missing Requirements",
        "## Execution Boundary",
    ]:
        assert heading in markdown, heading

    lowered = markdown.lower()
    assert "no ocr was performed" in lowered
    assert "no vision model was called" in lowered
    assert "no model was called" in lowered
    assert "no worker was launched" in lowered
    assert "no patch was applied" in lowered
    assert "no validation was run" in lowered
    assert "no promotion occurred" in lowered


# --------------------------------------------------------------------------
# create_visual_evidence_contract file IO + CLI
# --------------------------------------------------------------------------


def _write_source(repo: Path, **overrides: Any) -> Path:
    record = _visual_wa(repo_path=str(repo), **overrides)
    path = repo / ".agent" / "worker_assignments" / record["assignment_id"] / "worker_assignment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def test_create_contract_writes_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)

    result = create_visual_evidence_contract(
        source_path=str(source),
        repo_path=str(repo),
        human_summary="Human caption of the chart change.",
        created_at="2026-01-01T00:00:00Z",
        visual_evidence_id="contract-1",
    )

    assert result["ok"] is True
    assert result["status"] == "contract_created"
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == repo / ".agent" / "visual_evidence" / "contract-1" / "visual_evidence_contract.json"
    assert md_path == json_path.with_name("visual_evidence_contract.md")
    assert json_path.is_file()
    assert md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["visual_evidence_id"] == "contract-1"
    assert record["source_type"] == "worker_assignment"
    assert record["source_path"] == str(source.resolve())
    assert record["visual_evidence_referenced"] is True
    assert record["human_visual_summary"] == "Human caption of the chart change."


def test_dry_run_writes_nothing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)

    result = create_visual_evidence_contract(
        source_path=str(source),
        repo_path=str(repo),
        dry_run=True,
        visual_evidence_id="dry-only",
        created_at="2026-01-01T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert not (repo / ".agent" / "visual_evidence").exists()


def test_missing_source_returns_clean_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = create_visual_evidence_contract(
        source_path=str(repo / ".agent" / "worker_assignments" / "missing" / "worker_assignment.json"),
        repo_path=str(repo),
    )

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["error"]["code"] == "source_not_found"
    assert not (repo / ".agent" / "visual_evidence").exists()


def test_deterministic_output_with_fixed_hooks(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)
    kwargs = {
        "source_path": str(source),
        "repo_path": str(repo),
        "dry_run": True,
        "created_at": "2026-01-01T00:00:00Z",
        "visual_evidence_id": "stable",
    }

    first = vec.render_visual_evidence_json(create_visual_evidence_contract(**kwargs))
    second = vec.render_visual_evidence_json(create_visual_evidence_contract(**kwargs))

    assert first == second
    assert json.loads(first)["record"]["visual_evidence_id"] == "stable"


def test_cli_creates_json_and_markdown(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)

    rc = cli.main([
        "--source",
        str(source),
        "--repo-path",
        str(repo),
        "--human-summary",
        "Chart bars no longer overlap the legend.",
        "--visual-evidence-id",
        "cli-smoke",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "contract_created"
    assert parsed["record"]["visual_evidence_id"] == "cli-smoke"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()
    markdown = Path(parsed["md_path"]).read_text(encoding="utf-8")
    assert "## Execution Boundary" in markdown
    assert "no ocr was performed" in markdown.lower()


def test_cli_visual_readable_flag_reduces_summary_requirement(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)

    rc = cli.main([
        "--source",
        str(source),
        "--repo-path",
        str(repo),
        "--visual-readable-by-model",
        "true",
        "--visual-evidence-id",
        "cli-readable",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--dry-run",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    record = parsed["record"]
    assert record["visual_evidence_readable_by_model"] is True
    assert record["human_visual_summary_required"] is False


def test_cli_dry_run_writes_nothing(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_source(repo)

    rc = cli.main([
        "--source",
        str(source),
        "--repo-path",
        str(repo),
        "--dry-run",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "dry_run"
    assert not (repo / ".agent" / "visual_evidence").exists()


def test_cli_missing_source_reports_error(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    rc = cli.main([
        "--source",
        str(repo / "missing.json"),
        "--repo-path",
        str(repo),
    ])
    captured = capsys.readouterr()

    assert rc == 1
    assert "source_not_found" in captured.err


# --------------------------------------------------------------------------
# Guardrails: the contract must stay inert (no OCR / vision / model / network)
# --------------------------------------------------------------------------


def test_no_forbidden_imports_or_calls_in_visual_evidence_layers():
    module_tree = ast.parse(Path(vec.__file__).read_text(encoding="utf-8"))
    script_tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in (module_tree, script_tree):
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        # OCR + image processing for analysis
        "cv2",
        "easyocr",
        "numpy",
        "PIL",
        "pillow",
        "pytesseract",
        "skimage",
        "tesseract",
        # model / provider clients
        "agents",
        "anthropic",
        "cohere",
        "google",
        "openai",
        # network / webhooks
        "httpx",
        "requests",
        "socket",
        "urllib",
        # execution / other subsystems
        "benchmarks",
        "database",
        "discord",
        "docker",
        "flask",
        "n8n",
        "patching",
        "subprocess",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.driver_model_routing",
        "core.dream_trials",
        "core.executor",
        "core.lesson_store",
        "core.project_evolution_mode",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "core.validation_command",
        "scripts.create_dream_trial",
        "scripts.run_background_dream_planner",
        "scripts.run_patch_proposal_queue",
        "scripts.validate_evolution_patch_sandbox",
    }
    forbidden_calls = {
        "annotate_image",
        "apply_patch",
        "apply_patch_plan",
        "call_api",
        "call_model",
        "connect",
        "create_dream",
        "create_lesson",
        "create_project_evolution",
        "detect_text",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "image_to_string",
        "ocr",
        "open",
        "Popen",
        "post",
        "promote",
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_ocr",
        "run_validation_command",
        "system",
        "urlopen",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), imported_roots & forbidden_import_roots
    assert imports.isdisjoint(forbidden_imports), imports & forbidden_imports
    assert calls.isdisjoint(forbidden_calls), calls & forbidden_calls


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
