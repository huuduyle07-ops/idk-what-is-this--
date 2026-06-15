"""Tests for H.1 Driver Model Routing Contract.

The Driver Policy is contract/report-only: it inspects a Worker Assignment
(F.5) and recommends the safest allowed "vehicle" (model level). It must never
call a model, switch providers, launch a worker, apply a patch, run validation,
trigger Dream / Project Evolution execution, call webhooks, or promote lessons.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core import driver_model_routing as dmr
from core.driver_model_routing import (
    BLOCKED,
    CHEAP_API_OK,
    FREE_MODEL_OK,
    HUMAN_ONLY,
    LOCAL_ONLY,
    STRONG_MODEL_RECOMMENDED,
    STRONG_MODEL_REQUIRES_APPROVAL,
    VEHICLE_LEVELS,
    VISION_OR_HUMAN_CAPTION_REQUIRED,
    evaluate_assignment_policy,
    evaluate_driver_route,
    render_driver_decision_markdown,
)
from scripts import evaluate_driver_route as cli


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-driver-routing"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Boilerplate that real F.5 worker assignments ALWAYS carry. These lines
# mention "visual evidence" and "secrets/env" but are generic guardrails, not
# task-specific signals. The policy must NOT treat them as visual/security
# triggers.
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
    """A realistic F.5 worker_assignment.json record (narrow Debug by default)."""
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


def _vehicle_index(vehicle: str) -> int:
    return VEHICLE_LEVELS.index(vehicle)


def _at_least(vehicle: str, floor: str) -> bool:
    return _vehicle_index(vehicle) >= _vehicle_index(floor)


# --------------------------------------------------------------------------
# Vehicle level constants
# --------------------------------------------------------------------------


def test_vehicle_level_constants_are_stable_strings():
    assert LOCAL_ONLY == "local_only"
    assert FREE_MODEL_OK == "free_model_ok"
    assert CHEAP_API_OK == "cheap_api_ok"
    assert STRONG_MODEL_RECOMMENDED == "strong_model_recommended"
    assert STRONG_MODEL_REQUIRES_APPROVAL == "strong_model_requires_approval"
    assert VISION_OR_HUMAN_CAPTION_REQUIRED == "vision_or_human_caption_required"
    assert HUMAN_ONLY == "human_only"
    assert BLOCKED == "blocked"
    assert VEHICLE_LEVELS == [
        "local_only",
        "free_model_ok",
        "cheap_api_ok",
        "strong_model_recommended",
        "strong_model_requires_approval",
        "vision_or_human_caption_required",
        "human_only",
        "blocked",
    ]


# --------------------------------------------------------------------------
# Routing rules (pure policy)
# --------------------------------------------------------------------------


def test_narrow_debug_recommends_free_model_ok_with_no_flags():
    decision = evaluate_assignment_policy(_wa())

    assert decision["recommended_vehicle"] == FREE_MODEL_OK
    assert decision["approval_required"] is False
    assert decision["blocked"] is False
    # Boilerplate stop conditions / safety rules must not create false positives.
    assert decision["risk_flags"] == []
    assert decision["missing_requirements"] == []


def test_review_only_recommends_local_or_free_without_approval():
    decision = evaluate_assignment_policy(
        _wa(
            mode="Review-only",
            worker_role="reviewer",
            expected_output="Critique/report only. No patch generation, no file edits, and no validation execution.",
        )
    )

    assert decision["recommended_vehicle"] in {LOCAL_ONLY, FREE_MODEL_OK}
    assert decision["approval_required"] is False
    assert decision["blocked"] is False


def test_project_evolution_recommends_strong_with_approval():
    decision = evaluate_assignment_policy(
        _wa(mode="Project Evolution", title="Migrate the logging framework", allowed_files=["core/log.py"])
    )

    assert decision["recommended_vehicle"] == STRONG_MODEL_RECOMMENDED
    assert decision["approval_required"] is True
    assert "broad_change" in decision["risk_flags"]


def test_dream_trial_flags_experimental_and_requires_approval():
    decision = evaluate_assignment_policy(
        _wa(mode="Dream Trial", title="Try a speculative caching strategy", worker_role="researcher")
    )

    assert decision["approval_required"] is True
    assert "experimental_workflow" in decision["risk_flags"]
    assert decision["recommended_vehicle"] in {CHEAP_API_OK, STRONG_MODEL_RECOMMENDED}


def test_visual_evidence_requires_vision_or_human_caption():
    decision = evaluate_assignment_policy(
        _wa(
            title="Fix the dashboard chart rendering",
            expected_output="Compare the screenshot of the UI layout before and after the change.",
        )
    )

    assert decision["recommended_vehicle"] == VISION_OR_HUMAN_CAPTION_REQUIRED
    assert decision["approval_required"] is True
    assert "visual_evidence_unverified" in decision["risk_flags"]
    assert "human_visual_summary_or_vision_model" in decision["missing_requirements"]


def test_security_sensitive_requires_strong_with_approval():
    decision = evaluate_assignment_policy(
        _wa(
            title="Rotate the leaked API key and credential",
            expected_output="Replace the auth token handling without weakening checks.",
        )
    )

    assert decision["recommended_vehicle"] == STRONG_MODEL_REQUIRES_APPROVAL
    assert decision["approval_required"] is True
    assert "security_sensitive" in decision["risk_flags"]


def test_apply_allowed_true_is_blocked():
    decision = evaluate_assignment_policy(_wa(apply_allowed=True))

    assert decision["recommended_vehicle"] == BLOCKED
    assert decision["blocked"] is True
    assert decision["approval_required"] is True
    assert any("does not permit execution" in reason.lower() for reason in decision["reasons"])


def test_worker_launch_allowed_true_is_blocked():
    decision = evaluate_assignment_policy(_wa(worker_launch_allowed=True))

    assert decision["recommended_vehicle"] == BLOCKED
    assert decision["blocked"] is True
    assert decision["approval_required"] is True


def test_missing_allowed_files_flags_scope_unclear():
    decision = evaluate_assignment_policy(_wa(allowed_files=[]))

    assert "scope_unclear" in decision["risk_flags"]
    assert decision["approval_required"] is True
    assert decision["recommended_vehicle"] in {STRONG_MODEL_REQUIRES_APPROVAL, HUMAN_ONLY}


def test_missing_validation_flags_missing_validation():
    decision = evaluate_assignment_policy(_wa(validation_commands=[]))

    assert "missing_validation" in decision["risk_flags"]
    assert _at_least(decision["recommended_vehicle"], CHEAP_API_OK)
    # Debug + implementer => patch-like output expected => approval required.
    assert decision["approval_required"] is True


def test_missing_validation_non_patch_role_does_not_require_approval():
    # A Debug *reviewer* task with neutral wording is not patch-like. The
    # boilerplate safety/stop lines (which contain "apply" / "patch") must NOT
    # leak into patch-like detection and force approval.
    decision = evaluate_assignment_policy(
        _wa(
            mode="Debug",
            worker_role="reviewer",
            validation_commands=[],
            title="Investigate the checkout total discrepancy",
            expected_output="A written analysis of the discrepancy; no source modifications are requested.",
        )
    )

    assert "missing_validation" in decision["risk_flags"]
    assert decision["approval_required"] is False


def test_external_queue_source_flags_untrusted_and_floors_free_model():
    decision = evaluate_assignment_policy(
        _wa(
            source_type="seed_draft",
            mode="Documentation",
            worker_role="documenter",
            source_path="/repo/.agent/external_queue_exports/q1/goal_brief_seed_draft.json",
        )
    )

    assert "external_untrusted_source" in decision["risk_flags"]
    assert _at_least(decision["recommended_vehicle"], FREE_MODEL_OK)


def test_external_queue_code_modifying_task_requires_approval():
    decision = evaluate_assignment_policy(
        _wa(
            source_type="seed_draft",
            mode="Debug",
            source_path="/repo/.agent/external_queue_exports/q1/seed_draft.json",
        )
    )

    assert "external_untrusted_source" in decision["risk_flags"]
    assert decision["approval_required"] is True
    assert _at_least(decision["recommended_vehicle"], FREE_MODEL_OK)


# --------------------------------------------------------------------------
# Decision record / JSON contract
# --------------------------------------------------------------------------


def test_decision_record_has_required_fields_and_inert_flags():
    result = evaluate_driver_route(assignment=_wa(), dry_run=True, created_at="2026-01-01T00:00:00Z")
    record = result["record"]

    for field in [
        "driver_decision_id",
        "created_at",
        "source_type",
        "source_path",
        "recommended_vehicle",
        "approval_required",
        "blocked",
        "reasons",
        "risk_flags",
        "missing_requirements",
    ]:
        assert field in record, field

    assert record["source_type"] == "worker_assignment"
    inert = {
        "model_call_performed": False,
        "provider_switch_performed": False,
        "worker_launch_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "promotion_performed": False,
    }
    for key, expected in inert.items():
        assert record[key] is expected, key


def test_markdown_includes_execution_boundary_and_sections():
    result = evaluate_driver_route(
        assignment=_wa(),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        driver_decision_id="md-check",
    )
    markdown = render_driver_decision_markdown(result["record"])

    for heading in [
        "# Driver Decision",
        "## Recommended Vehicle",
        "## Approval Required",
        "## Risk Flags",
        "## Missing Requirements",
        "## Reasons",
        "## Execution Boundary",
        "## Source Assignment",
    ]:
        assert heading in markdown, heading

    lowered = markdown.lower()
    assert "no model was called" in lowered
    assert "no provider was switched" in lowered
    assert "no worker was launched" in lowered
    assert "no patch was applied" in lowered
    assert "no validation was run" in lowered
    assert "no promotion occurred" in lowered


# --------------------------------------------------------------------------
# evaluate_driver_route file IO + CLI
# --------------------------------------------------------------------------


def _write_assignment(repo: Path, **overrides: Any) -> Path:
    record = _wa(repo_path=str(repo), **overrides)
    path = repo / ".agent" / "worker_assignments" / record["assignment_id"] / "worker_assignment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def test_evaluate_driver_route_writes_json_and_markdown(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_assignment(repo)

    result = evaluate_driver_route(
        worker_assignment_path=str(source),
        repo_path=str(repo),
        created_at="2026-01-01T00:00:00Z",
        driver_decision_id="decision-1",
    )

    assert result["ok"] is True
    assert result["status"] == "decision_created"
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == repo / ".agent" / "driver_decisions" / "decision-1" / "driver_decision.json"
    assert md_path == json_path.with_name("driver_decision.md")
    assert json_path.is_file()
    assert md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["driver_decision_id"] == "decision-1"
    assert record["source_type"] == "worker_assignment"
    assert record["source_path"] == str(source.resolve())
    assert record["recommended_vehicle"] == FREE_MODEL_OK


def test_dry_run_writes_nothing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_assignment(repo)

    result = evaluate_driver_route(
        worker_assignment_path=str(source),
        repo_path=str(repo),
        dry_run=True,
        driver_decision_id="dry-only",
        created_at="2026-01-01T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert not (repo / ".agent" / "driver_decisions").exists()


def test_missing_worker_assignment_returns_clean_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = evaluate_driver_route(
        worker_assignment_path=str(repo / ".agent" / "worker_assignments" / "missing" / "worker_assignment.json"),
        repo_path=str(repo),
    )

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["error"]["code"] == "worker_assignment_not_found"
    assert not (repo / ".agent" / "driver_decisions").exists()


def test_deterministic_output_with_fixed_hooks(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_assignment(repo)
    kwargs = {
        "worker_assignment_path": str(source),
        "repo_path": str(repo),
        "dry_run": True,
        "created_at": "2026-01-01T00:00:00Z",
        "driver_decision_id": "stable",
    }

    first = dmr.render_driver_decision_json(evaluate_driver_route(**kwargs))
    second = dmr.render_driver_decision_json(evaluate_driver_route(**kwargs))

    assert first == second
    assert json.loads(first)["record"]["driver_decision_id"] == "stable"


def test_cli_creates_json_and_markdown(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_assignment(repo)

    rc = cli.main([
        "--worker-assignment",
        str(source),
        "--repo-path",
        str(repo),
        "--driver-decision-id",
        "cli-smoke",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--json",
    ])
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "decision_created"
    assert parsed["record"]["driver_decision_id"] == "cli-smoke"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()
    markdown = Path(parsed["md_path"]).read_text(encoding="utf-8")
    assert "## Execution Boundary" in markdown
    assert "no model was called" in markdown.lower()


def test_cli_dry_run_writes_nothing(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = _write_assignment(repo)

    rc = cli.main([
        "--worker-assignment",
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
    assert not (repo / ".agent" / "driver_decisions").exists()


def test_cli_missing_worker_assignment_reports_error(capsys, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    rc = cli.main([
        "--worker-assignment",
        str(repo / "missing.json"),
        "--repo-path",
        str(repo),
    ])
    captured = capsys.readouterr()

    assert rc == 1
    assert "worker_assignment_not_found" in captured.err


# --------------------------------------------------------------------------
# Guardrails: the contract must stay inert
# --------------------------------------------------------------------------


def test_no_forbidden_imports_or_calls_in_driver_routing_layers():
    module_tree = ast.parse(Path(dmr.__file__).read_text(encoding="utf-8"))
    script_tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in (module_tree, script_tree):
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "discord",
        "docker",
        "flask",
        "google",
        "httpx",
        "n8n",
        "openai",
        "patching",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
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
        "apply_patch",
        "apply_patch_plan",
        "call_api",
        "call_model",
        "connect",
        "create_dream",
        "create_lesson",
        "create_project_evolution",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "open",
        "Popen",
        "post",
        "promote",
        "promote_lesson",
        "run_benchmark",
        "run_benchmarks",
        "run_handoff",
        "run_overnight",
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
