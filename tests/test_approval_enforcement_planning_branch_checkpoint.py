"""Tests for HARDEN.CLOSE - Approval Enforcement Planning Branch Checkpoint.

HARDEN.CLOSE freezes HARDEN.N1-HARDEN.N4 as a report-only approval enforcement
planning branch. It must not install approval gates, validate live tokens,
issue/consume tokens, approve/reject real actions, or change route/auth/runtime
behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.approval_enforcement_planning_branch_checkpoint import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REQUIRED_HARDEN_PHASE_IDS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    THIS_PHASE_ID,
    build_approval_enforcement_planning_branch_checkpoint,
    render_approval_enforcement_planning_branch_checkpoint_markdown,
    write_approval_enforcement_planning_branch_checkpoint,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_approval_enforcement_planning_branch_checkpoint import (
    run_create_approval_enforcement_planning_branch_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "approval_enforcement_planning_branch_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_approval_enforcement_planning_branch_checkpoint.py"


def _phase(phase_id: str, **over) -> dict:
    data = {
        "phase_id": phase_id,
        "title": f"{phase_id} title",
        "track": "HARDEN" if phase_id.startswith("HARDEN") else "OPS",
        "status": "complete",
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_x.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/harden/x.json"],
        "notes": ["Report-only; no runtime enforcement."],
    }
    data.update(over)
    return data


def _registry(*, drop: tuple[str, ...] = (), close_status: str = "complete") -> dict:
    phases = []
    for phase_id in REQUIRED_HARDEN_PHASE_IDS:
        if phase_id not in drop:
            prereq = [] if phase_id == "HARDEN.N1" else [f"HARDEN.N{int(phase_id.rsplit('N', 1)[1]) - 1}"]
            phases.append(_phase(phase_id, prerequisites=prereq))
    if THIS_PHASE_ID not in drop:
        phases.append(_phase(THIS_PHASE_ID, status=close_status, prerequisites=["HARDEN.N4"]))
    phases.append(
        _phase(
            "OPS.TEST.1",
            title="Full Suite Runtime / Slow Test Audit",
            track="OPS",
            status="proposed",
            prerequisites=[THIS_PHASE_ID],
            expected_artifacts=[
                ".agent/ops/full_suite_runtime_slow_test_audit/full_suite_runtime_slow_test_audit.json",
                ".agent/ops/full_suite_runtime_slow_test_audit/full_suite_runtime_slow_test_audit.md",
            ],
        )
    )
    return {"schema_version": "1.0", "updated_at": "2026-07-08T00:00:00+09:00", "phases": phases}


def _guardrails(**over) -> dict:
    data = {
        "report_only": True,
        "audit_only": True,
        "plan_only": True,
        "simulation_only": True,
        "operator_report_only": True,
        "approval_enforcement_added": False,
        "runtime_enforcement_added": False,
        "runtime_check_added": False,
        "token_validation_gate_added": False,
        "route_blocker_added": False,
        "approval_gate_enforced": False,
        "enforcement_was_applied": False,
        "approval_or_rejection_performed": False,
        "approval_token_issuance_performed": False,
        "approval_token_consumption_performed": False,
        "approval_tokens_treated_as_real_authority": False,
        "sample_token_treated_as_real_authority": False,
        "automatic_approval_allowed": False,
        "automatic_rejection_allowed": False,
        "hidden_mutation_allowed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "model_call_performed": False,
        "model_routing_performed": False,
        "worker_launch_performed": False,
        "patch_apply_performed": False,
        "validation_run_performed": False,
        "benchmark_run_performed": False,
        "mcp_invocation_performed": False,
        "network_contacted": False,
        "database_write_performed": False,
    }
    data.update(over)
    return data


def _readiness(**over) -> dict:
    findings = [
        {"action_category": "patch_apply", "future_approval_required": True, "enforcement_not_implemented_confirmed": True},
        {"action_category": "worker_launch", "future_approval_required": True, "enforcement_not_implemented_confirmed": True},
        {"action_category": "automatic_approval", "future_approval_required": False, "forbidden_boundary": True},
        {"action_category": "automatic_rejection", "future_approval_required": False, "forbidden_boundary": True},
        {"action_category": "hidden_mutation", "future_approval_required": False, "forbidden_boundary": True},
    ]
    data = {
        "report_kind": "approval_enforcement_readiness_audit",
        "phase_id": "HARDEN.N1",
        "audit_status": "approval_enforcement_readiness_ready_with_warnings",
        "action_surface_count": len(findings),
        "mapped_action_count": len(findings),
        "unmapped_action_count": 0,
        "action_surface_findings": findings,
        "missing_approval_mappings": [],
        "runtime_non_enforcement_confirmation": {"runtime_enforcement_added": False},
        "forbidden_runtime_changes_checked": True,
        "warnings": ["Future approval enforcement is intentionally not implemented."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _attachment(**over) -> dict:
    items = [
        {
            "action_category": "patch_apply",
            "approval_action": "approve_patch_apply",
            "preferred_attachment_layer": "route_precheck",
            "proposed_attachment_points": ["patch review route before source write"],
            "enforcement_allowed_now": False,
        },
        {
            "action_category": "worker_launch",
            "approval_action": "approve_worker_launch",
            "preferred_attachment_layer": "worker_dispatch_precheck",
            "proposed_attachment_points": ["worker task planner before enqueue"],
            "enforcement_allowed_now": False,
        },
        {
            "action_category": "hidden_mutation",
            "approval_action": "",
            "preferred_attachment_layer": "blocked_boundary",
            "proposed_attachment_points": ["never automatic"],
            "enforcement_allowed_now": False,
        },
    ]
    data = {
        "report_kind": "approval_enforcement_attachment_plan",
        "phase_id": "HARDEN.N2",
        "plan_status": "approval_enforcement_attachment_plan_ready_with_warnings",
        "attachment_item_count": len(items),
        "planned_action_count": len(items),
        "missing_action_count": 0,
        "missing_action_categories": [],
        "attachment_items": items,
        "dangerous_action_attachment_matrix": [
            {
                "action_category": item["action_category"],
                "approval_action": item["approval_action"],
                "attachment_points": item["proposed_attachment_points"],
                "enforcement_allowed_now": False,
            }
            for item in items
        ],
        "runtime_non_enforcement_confirmation": {"runtime_enforcement_added": False},
        "warnings": ["Future enforcement remains intentionally unimplemented."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _simulator(**over) -> dict:
    results = [
        {
            "scenario_id": "valid_patch_apply_request_with_valid_token",
            "simulated_decision": "would_allow_with_valid_token",
            "action_request_summary": {"action_category": "patch_apply"},
            "boundary_result": {
                "simulation_only": True,
                "authorizes_real_action": False,
                "real_dispatch_allowed": False,
                "runtime_enforcement_added": False,
                "route_or_auth_changed": False,
                "token_issued": False,
                "token_consumed": False,
            },
        },
        {
            "scenario_id": "patch_apply_missing_token",
            "simulated_decision": "would_deny_missing_token",
            "action_request_summary": {"action_category": "patch_apply"},
            "boundary_result": {"simulation_only": True, "authorizes_real_action": False},
        },
        {
            "scenario_id": "automatic_approval_attempt",
            "simulated_decision": "would_block_auto_approval",
            "action_request_summary": {"action_category": "automatic_approval"},
            "boundary_result": {"simulation_only": True, "authorizes_real_action": False},
        },
        {
            "scenario_id": "automatic_rejection_attempt",
            "simulated_decision": "would_block_auto_rejection",
            "action_request_summary": {"action_category": "automatic_rejection"},
            "boundary_result": {"simulation_only": True, "authorizes_real_action": False},
        },
        {
            "scenario_id": "hidden_mutation_attempt",
            "simulated_decision": "would_block_hidden_mutation",
            "action_request_summary": {"action_category": "hidden_mutation"},
            "boundary_result": {"simulation_only": True, "authorizes_real_action": False},
        },
    ]
    data = {
        "report_kind": "approval_enforcement_dry_run_gate_simulator",
        "phase_id": "HARDEN.N3",
        "simulator_status": "approval_gate_simulation_ready_with_warnings",
        "sample_scenario_count": len(results),
        "simulation_results": results,
        "decision_counts": {
            "would_allow_with_valid_token": 1,
            "would_deny_missing_token": 1,
            "would_block_auto_approval": 1,
            "would_block_auto_rejection": 1,
            "would_block_hidden_mutation": 1,
        },
        "enforcement_was_applied": False,
        "sample_tokens_treated_as_real_authority": False,
        "boundary_checks": {"token_issuance_performed": False, "token_consumption_performed": False},
        "warnings": ["Future enforcement remains intentionally unimplemented."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "guardrails": _guardrails(),
    }
    data.update(over)
    return data


def _operator(**over) -> dict:
    items = [
        {"scenario_id": "valid_patch_apply_request_with_valid_token", "action_category": "patch_apply", "simulated_decision": "would_allow_with_valid_token", "simulated_only": True},
        {"scenario_id": "patch_apply_missing_token", "action_category": "patch_apply", "simulated_decision": "would_deny_missing_token", "simulated_only": True},
        {"scenario_id": "automatic_approval_attempt", "action_category": "automatic_approval", "simulated_decision": "would_block_auto_approval", "simulated_only": True},
        {"scenario_id": "automatic_rejection_attempt", "action_category": "automatic_rejection", "simulated_decision": "would_block_auto_rejection", "simulated_only": True},
        {"scenario_id": "hidden_mutation_attempt", "action_category": "hidden_mutation", "simulated_decision": "would_block_hidden_mutation", "simulated_only": True},
    ]
    data = {
        "report_kind": "approval_enforcement_operator_report",
        "phase_id": "HARDEN.N4",
        "report_status": "approval_enforcement_operator_report_ready_with_warnings",
        "scenario_count": len(items),
        "decision_summary": {
            "would_allow_with_valid_token": 1,
            "would_deny_missing_token": 1,
            "would_block_auto_approval": 1,
            "would_block_auto_rejection": 1,
            "would_block_hidden_mutation": 1,
        },
        "allow_simulations": [items[0]],
        "deny_simulations": [items[1]],
        "block_simulations": items[2:],
        "warning_simulations": [],
        "operator_review_items": items,
        "simulated_only_notice": {"simulated_only": True, "authorizes_real_action": False},
        "enforcement_was_applied": False,
        "token_was_issued": False,
        "token_was_consumed": False,
        "runtime_behavior_changed": False,
        "warnings": ["Future enforcement remains intentionally unimplemented in HARDEN.N4."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "recommended_next_phase": {"phase_id": "HARDEN.CLOSE"},
        "guardrails": _guardrails(
            no_runtime_enforcement=True,
            no_token_validation_gate=True,
            no_token_issuance=True,
            no_token_consumption=True,
            no_route_behavior_change=True,
            no_auth_policy_change=True,
        ),
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_fake_repo(
    root: Path,
    *,
    registry: dict | None = None,
    readiness: dict | None = None,
    attachment: dict | None = None,
    simulator: dict | None = None,
    operator: dict | None = None,
    write_readiness: bool = True,
    write_attachment: bool = True,
    write_simulator: bool = True,
    write_operator: bool = True,
) -> Path:
    _write_json(root / "docs" / "roadmap" / "phase_registry.json", registry or _registry())
    if write_readiness:
        _write_json(
            root / ".agent" / "harden" / "approval_enforcement_readiness_audit" / "approval_enforcement_readiness_audit.json",
            readiness or _readiness(),
        )
    if write_attachment:
        _write_json(
            root / ".agent" / "harden" / "approval_enforcement_attachment_plan" / "approval_enforcement_attachment_plan.json",
            attachment or _attachment(),
        )
    if write_simulator:
        _write_json(
            root / ".agent" / "harden" / "approval_enforcement_dry_run_gate_simulator" / "approval_enforcement_dry_run_gate_simulator.json",
            simulator or _simulator(),
        )
    if write_operator:
        _write_json(
            root / ".agent" / "harden" / "approval_enforcement_operator_report" / "approval_enforcement_operator_report.json",
            operator or _operator(),
        )
    _write_json(
        root / ".agent" / "human" / "authority_branch_checkpoint" / "human_authority_branch_checkpoint.json",
        {"report_kind": "human_authority_branch_checkpoint", "checkpoint_status": "human_authority_branch_frozen_with_warnings"},
    )
    _write_json(
        root / ".agent" / "human" / "approval_token_contract" / "human_approval_token_contract.json",
        {"report_kind": "human_approval_token_contract", "contract_status": "approval_token_contract_ready_with_warnings"},
    )
    return root


def _build(root: Path, **kwargs) -> dict:
    _write_fake_repo(root, **kwargs)
    return build_approval_enforcement_planning_branch_checkpoint(
        repo_root=root,
        registry_path="docs/roadmap/phase_registry.json",
        checkpoint_id="test-harden-close",
        created_at="2026-07-08T00:00:00+09:00",
    )


def test_constants_match_spec():
    assert REPORT_KIND == "approval_enforcement_planning_branch_checkpoint"
    assert THIS_PHASE_ID == "HARDEN.CLOSE"
    assert REQUIRED_HARDEN_PHASE_IDS == ("HARDEN.N1", "HARDEN.N2", "HARDEN.N3", "HARDEN.N4")
    assert STATUS_FROZEN == "approval_enforcement_planning_branch_frozen"
    assert STATUS_FROZEN_WITH_WARNINGS == "approval_enforcement_planning_branch_frozen_with_warnings"
    assert STATUS_INCOMPLETE == "approval_enforcement_planning_branch_incomplete"
    assert STATUS_BLOCKED == "approval_enforcement_planning_branch_blocked"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "harden" / "approval_enforcement_planning_branch_checkpoint"
    assert JSON_NAME == "approval_enforcement_planning_branch_checkpoint.json"
    assert MD_NAME == "approval_enforcement_planning_branch_checkpoint.md"


def test_complete_harden_n1_to_n4_registry_produces_frozen_with_warnings(tmp_path):
    report = _build(tmp_path)

    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["phase_completion_summary"]["all_required_harden_phases_complete"] is True
    assert report["artifact_coverage"]["required_artifacts_present"] is True
    assert report["dangerous_action_coverage"]["maps_dangerous_action_surfaces"] is True
    assert report["attachment_plan_coverage"]["plans_future_attachment_points"] is True
    assert report["simulation_summary"]["simulates_approval_decisions_only"] is True
    assert report["operator_report_summary"]["summarizes_simulated_outcomes_only"] is True
    assert report["non_enforcement_verification"]["no_runtime_enforcement_added"] is True
    assert report["blocked_reasons"] == []
    assert report["incomplete_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "OPS.TEST.1"
    assert report["recommended_next_phase"]["alternatives"][0]["phase_id"] == "UX.RUN.1"


def test_missing_harden_n4_reports_incomplete(tmp_path):
    report = _build(tmp_path, registry=_registry(drop=("HARDEN.N4",)))

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("HARDEN.N4" in reason for reason in report["incomplete_reasons"])


@pytest.mark.parametrize(
    ("write_flag", "needle"),
    [
        ("write_operator", "operator report"),
        ("write_simulator", "dry-run simulator"),
        ("write_attachment", "attachment plan"),
        ("write_readiness", "readiness audit"),
    ],
)
def test_missing_required_source_artifact_reports_incomplete(tmp_path, write_flag, needle):
    report = _build(tmp_path, **{write_flag: False})

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any(needle in reason.lower() for reason in report["incomplete_reasons"])


@pytest.mark.parametrize(
    ("marker", "reason"),
    [
        ("runtime_enforcement_added", "runtime_enforcement_added"),
        ("approval_token_issuance_performed", "token_issuance_added"),
        ("approval_token_consumption_performed", "token_consumption_added"),
        ("route_behavior_changed", "route_behavior_changed"),
        ("auth_policy_changed", "auth_policy_changed"),
        ("automatic_approval_allowed", "auto_approval_allowed"),
        ("automatic_rejection_allowed", "auto_rejection_allowed"),
        ("hidden_mutation_allowed", "hidden_mutation_allowed"),
        ("simulated_allow_treated_as_real_authority", "simulated_allow_treated_as_real_authority"),
    ],
)
def test_forbidden_runtime_or_authority_markers_block(tmp_path, marker, reason):
    _write_fake_repo(tmp_path)
    report = build_approval_enforcement_planning_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        runtime_change_markers={marker: True},
    )

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["forbidden_runtime_changes"][reason] is True
    assert any(reason in blocked for blocked in report["blocked_reasons"])


def test_simulated_allow_inside_simulator_treated_as_real_authority_blocks(tmp_path):
    simulator = _simulator()
    simulator["simulation_results"][0]["boundary_result"]["authorizes_real_action"] = True

    report = _build(tmp_path, simulator=simulator)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["forbidden_runtime_changes"]["simulated_allow_treated_as_real_authority"] is True


def test_checkpoint_json_and_markdown_artifacts_are_written(tmp_path):
    _write_fake_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = write_approval_enforcement_planning_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=output_dir,
        checkpoint_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["checkpoint_id"] == "write-test"
    assert saved["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    for section in (
        "## Summary",
        "## Phase Completion",
        "## Artifact Coverage",
        "## Dangerous Action Coverage",
        "## Attachment Plan Coverage",
        "## Dry-Run Simulation Summary",
        "## Operator Report Summary",
        "## Non-Enforcement Verification",
        "## Forbidden Runtime Changes",
        "## Warnings",
        "## Blocked Reasons",
        "## Incomplete Reasons",
        "## Final Verdict",
        "## Recommended Next Phase",
        "## Guardrails",
    ):
        assert section in markdown


def test_script_writes_summary_json(tmp_path):
    _write_fake_repo(tmp_path)

    result = run_create_approval_enforcement_planning_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=tmp_path / "cli-out",
        checkpoint_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "OPS.TEST.1"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_renderer_does_not_mutate_report(tmp_path):
    report = _build(tmp_path)
    before = json.loads(json.dumps(report, sort_keys=True))
    assert render_approval_enforcement_planning_branch_checkpoint_markdown(report)
    assert report == before


def test_real_registry_marks_harden_close_complete_adds_ops_test_1_and_picker_recommends_ops_test_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HARDEN.CLOSE"]["status"] == "complete"
    assert by_id["HARDEN.CLOSE"]["prerequisites"] == ["HARDEN.N4"]
    assert by_id["HARDEN.CLOSE"]["expected_artifacts"] == [
        ".agent/harden/approval_enforcement_planning_branch_checkpoint/approval_enforcement_planning_branch_checkpoint.json",
        ".agent/harden/approval_enforcement_planning_branch_checkpoint/approval_enforcement_planning_branch_checkpoint.md",
    ]
    assert by_id["HARDEN.CLOSE"]["network_allowed"] is False
    assert by_id["HARDEN.CLOSE"]["model_calls_allowed"] is False
    assert by_id["HARDEN.CLOSE"]["writes_real_repo"] is False
    assert by_id["OPS.TEST.1"]["status"] == "proposed"
    assert by_id["OPS.TEST.1"]["title"] == "Full Suite Runtime / Slow Test Audit"
    assert by_id["OPS.TEST.1"]["prerequisites"] == ["HARDEN.CLOSE"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="harden-close-checkpoint",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "OPS.TEST.1"
    assert report["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_core_and_cli_do_not_import_or_call_runtime_enforcement_primitives():
    forbidden_imports = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "openai",
        "anthropic",
        "flask",
        "sqlite3",
    }
    forbidden_calls = {
        "run_validation",
        "run_safe_validation_command",
        "run_benchmarks",
        "call_model",
        "route_model",
        "launch_worker",
        "invoke_mcp",
        "issue_token",
        "consume_token",
        "validate_token",
        "approve",
        "reject",
        "before_request",
        "abort",
        "Popen",
        "run",
        "check_call",
        "check_output",
        "urlopen",
    }

    for path in (CORE_PATH, SCRIPT_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)
