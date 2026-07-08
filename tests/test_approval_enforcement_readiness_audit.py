"""Tests for HARDEN.N1 - Approval Enforcement Readiness Audit.

HARDEN.N1 is report-only. It maps dangerous action surfaces to future
HUMAN.N2 approval-token requirements and attachment candidates. It must not add
approval enforcement, token gates, route blockers, auth changes, runtime checks,
automatic approval/rejection, or hidden mutation behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.approval_enforcement_readiness_audit import (
    ACTION_CATEGORIES,
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    build_approval_enforcement_readiness_audit,
    render_approval_enforcement_readiness_audit_markdown,
    write_approval_enforcement_readiness_audit,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
import scripts.create_approval_enforcement_readiness_audit as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "approval_enforcement_readiness_audit.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_approval_enforcement_readiness_audit.py"


def _report(**kwargs) -> dict:
    return build_approval_enforcement_readiness_audit(
        repo_root=PROJECT_ROOT,
        audit_id="harden-n1-test",
        created_at="2026-07-08T00:00:00+09:00",
        **kwargs,
    )


def _by_category(report: dict) -> dict[str, dict]:
    return {
        str(item["action_category"]): item
        for item in report["action_surface_findings"]
    }


def test_constants_match_harden_n1_contract():
    assert REPORT_KIND == "approval_enforcement_readiness_audit"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "harden" / "approval_enforcement_readiness_audit"
    assert JSON_NAME == "approval_enforcement_readiness_audit.json"
    assert MD_NAME == "approval_enforcement_readiness_audit.md"
    assert ACTION_CATEGORIES == (
        "patch_apply",
        "direct_file_mutation",
        "worker_launch",
        "model_call",
        "model_routing",
        "validation_run",
        "benchmark_run",
        "mcp_tool_invocation",
        "network_access",
        "subprocess_execution",
        "docker_execution",
        "database_write",
        "auth_policy_change",
        "route_behavior_change",
        "registry_mutation",
        "model_catalog_adoption",
        "dream_execution",
        "replay_apply",
        "remote_execution",
        "automatic_approval",
        "automatic_rejection",
        "hidden_mutation",
    )


def test_default_audit_is_ready_with_warnings_and_report_only():
    report = _report()

    assert report["report_kind"] == REPORT_KIND
    assert report["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert report["audit_id"] == "harden-n1-test"
    assert report["action_surface_count"] == len(ACTION_CATEGORIES)
    assert report["mapped_action_count"] == len(ACTION_CATEGORIES)
    assert report["unmapped_action_count"] == 0
    assert report["missing_approval_mappings"] == []
    assert report["enforcement_not_implemented_confirmed"] is True
    assert report["recommended_next_phase"]["phase_id"] == "HARDEN.N2"
    assert "future enforcement is intentionally not implemented" in " ".join(report["warnings"]).lower()
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["approval_enforcement_added"] is False
    assert report["guardrails"]["token_validation_gate_added"] is False
    assert report["guardrails"]["route_blocker_added"] is False
    assert report["guardrails"]["auth_policy_changed"] is False
    assert report["guardrails"]["automatic_approval_allowed"] is False
    assert report["guardrails"]["automatic_rejection_allowed"] is False
    assert report["guardrails"]["hidden_mutation_allowed"] is False


def test_audit_maps_all_required_dangerous_action_categories():
    report = _report()
    findings = _by_category(report)

    assert set(findings) == set(ACTION_CATEGORIES)
    for category in ACTION_CATEGORIES:
        item = findings[category]
        for key in (
            "action_category",
            "current_known_surface",
            "current_authority_status",
            "future_approval_required",
            "required_approval_action_from_HUMAN_N2",
            "required_target_type_from_HUMAN_N2",
            "risk_level",
            "existing_human_boundary_reference",
            "enforcement_attachment_candidate",
            "enforcement_not_implemented_confirmed",
            "warnings",
            "blockers",
        ):
            assert key in item, f"{category} missing {key}"
        assert item["enforcement_not_implemented_confirmed"] is True
        assert "HUMAN.N1" in item["existing_human_boundary_reference"]


def test_required_future_approval_mappings_follow_human_n2_actions():
    findings = _by_category(_report())

    expected = {
        "patch_apply": ("approve_patch_apply", "patch"),
        "worker_launch": ("approve_worker_launch", "worker_task"),
        "validation_run": ("approve_validation_run", "validation_plan"),
        "benchmark_run": ("approve_benchmark_run", "benchmark_plan"),
        "model_catalog_adoption": ("approve_model_catalog_adoption", "model_catalog"),
        "registry_mutation": ("approve_registry_mutation", "registry"),
        "mcp_tool_invocation": ("approve_mcp_tool_invocation", "mcp_tool"),
        "network_access": ("approve_network_access", "network_request"),
        "database_write": ("approve_database_write", "database_change"),
        "auth_policy_change": ("approve_auth_policy_change", "auth_policy"),
        "remote_execution": ("approve_remote_execution", "remote_command"),
        "replay_apply": ("approve_replay_apply", "replay_action"),
        "dream_execution": ("approve_dream_execution", "dream_run"),
    }
    for category, (approval_action, target_type) in expected.items():
        item = findings[category]
        assert item["required_approval_action_from_HUMAN_N2"] == approval_action
        assert item["required_target_type_from_HUMAN_N2"] == target_type
        assert item["future_approval_required"] is True


def test_automatic_approval_rejection_and_hidden_mutation_are_forbidden():
    findings = _by_category(_report())

    for category in ("automatic_approval", "automatic_rejection", "hidden_mutation"):
        item = findings[category]
        assert item["future_approval_required"] is False
        assert item["required_approval_action_from_HUMAN_N2"] is None
        assert item["required_target_type_from_HUMAN_N2"] is None
        assert item["current_authority_status"] == "blocked_forbidden"
        assert item["risk_level"] == "critical"
        assert item["blockers"] == []
        assert any("forbidden" in warning.lower() for warning in item["warnings"])


def test_audit_references_human_and_model_adoption_source_artifacts():
    report = _report()

    assert report["source_human_boundary_path"].endswith(
        ".agent/human/review_boundary_map/human_review_boundary_map.json"
    )
    assert report["source_approval_contract_path"].endswith(
        ".agent/human/approval_token_contract/human_approval_token_contract.json"
    )
    assert report["source_human_checkpoint_path"].endswith(
        ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.json"
    )
    assert report["source_model_adoption_checkpoint_path"].endswith(
        ".agent/model_role_registry/adoption_checkpoint/model_role_catalog_adoption_checkpoint.json"
    )
    refs = {item["phase_id"]: item for item in report["source_artifacts"]}
    assert refs["HUMAN.N1"]["present"] is True
    assert refs["HUMAN.N2"]["present"] is True
    assert refs["HUMAN.CLOSE"]["present"] is True
    assert refs["ADOPT.MODEL.CLOSE"]["present"] is True


def test_missing_human_artifacts_produce_incomplete(tmp_path):
    report = _report(
        source_human_boundary_path=tmp_path / "missing_human_n1.json",
    )

    assert report["audit_status"] == STATUS_INCOMPLETE
    assert any("HUMAN.N1" in reason for reason in report["incomplete_reasons"])


def test_missing_approval_mapping_produces_incomplete_or_warning():
    mappings = {
        category: mapping
        for category, mapping in _report()["future_enforcement_candidates"].items()
        if category != "patch_apply"
    }

    report = _report(approval_mappings=mappings)

    assert "patch_apply" in report["missing_approval_mappings"]
    assert report["audit_status"] in {STATUS_INCOMPLETE, STATUS_READY_WITH_WARNINGS}


def test_unexpected_enforcement_marker_blocks_audit():
    report = _report(runtime_change_markers={"approval_enforcement_added": True})

    assert report["audit_status"] == STATUS_BLOCKED
    assert any("approval enforcement" in reason.lower() for reason in report["blocked_reasons"])


def test_json_and_markdown_audit_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "harden-n1"

    result = write_approval_enforcement_readiness_audit(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        audit_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HARDEN.N2"
    assert "# Approval Enforcement Readiness Audit" in markdown
    assert "Runtime Non-Enforcement Confirmation" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_approval_enforcement_readiness_audit(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        audit_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["audit_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HARDEN.N2"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_report_sections():
    markdown = render_approval_enforcement_readiness_audit_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## human authority reference",
        "## model adoption reference",
        "## dangerous action surface map",
        "## future approval mapping",
        "## enforcement attachment candidates",
        "## runtime non-enforcement confirmation",
        "## missing mappings",
        "## warnings",
        "## blocked reasons",
        "## incomplete reasons",
        "## final verdict",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_harden_n1_complete_and_picker_recommends_harden_n2():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HARDEN.N1"]["status"] == "complete"
    assert by_id["HARDEN.N1"]["prerequisites"] == ["ADOPT.MODEL.CLOSE"]
    assert by_id["HARDEN.N1"]["expected_artifacts"] == [
        ".agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.json",
        ".agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.md",
    ]
    assert by_id["HARDEN.N2"]["status"] == "proposed"
    assert by_id["HARDEN.N2"]["title"] == "Approval Enforcement Design Plan"
    assert by_id["HARDEN.N2"]["prerequisites"] == ["HARDEN.N1"]
    assert by_id["HARDEN.N2"]["network_allowed"] is False
    assert by_id["HARDEN.N2"]["model_calls_allowed"] is False
    assert by_id["HARDEN.N2"]["writes_real_repo"] is False

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="harden-n1-registry",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "HARDEN.N2"


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
