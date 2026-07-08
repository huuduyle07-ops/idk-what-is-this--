"""Tests for HARDEN.N2 - Approval Enforcement Attachment Plan.

HARDEN.N2 is plan-only and report-only. It may describe where future approval
token checks could attach, but it must not validate tokens, issue or consume
tokens, block routes, change auth, or enforce anything.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.approval_enforcement_attachment_plan import (
    ACTION_CATEGORIES,
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    PREFERRED_ATTACHMENT_LAYERS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    build_approval_enforcement_attachment_plan,
    render_approval_enforcement_attachment_plan_markdown,
    write_approval_enforcement_attachment_plan,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
import scripts.create_approval_enforcement_attachment_plan as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "approval_enforcement_attachment_plan.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_approval_enforcement_attachment_plan.py"


def _report(**kwargs) -> dict:
    return build_approval_enforcement_attachment_plan(
        repo_root=PROJECT_ROOT,
        plan_id="harden-n2-test",
        created_at="2026-07-08T00:00:00+09:00",
        **kwargs,
    )


def _by_category(report: dict) -> dict[str, dict]:
    return {
        str(item["action_category"]): item
        for item in report["attachment_items"]
    }


def test_constants_match_harden_n2_contract():
    assert REPORT_KIND == "approval_enforcement_attachment_plan"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "harden" / "approval_enforcement_attachment_plan"
    assert JSON_NAME == "approval_enforcement_attachment_plan.json"
    assert MD_NAME == "approval_enforcement_attachment_plan.md"
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
        "replay_apply",
        "dream_execution",
        "remote_execution",
        "approval_token_issuance",
        "approval_token_consumption",
        "automatic_approval",
        "automatic_rejection",
        "hidden_mutation",
    )
    assert PREFERRED_ATTACHMENT_LAYERS == (
        "ui_confirmation_surface",
        "route_precheck",
        "service_layer_precheck",
        "command_dispatch_precheck",
        "file_write_precheck",
        "worker_dispatch_precheck",
        "model_dispatch_precheck",
        "tool_dispatch_precheck",
        "validation_dispatch_precheck",
        "benchmark_dispatch_precheck",
        "registry_write_precheck",
        "auth_policy_precheck",
        "blocked_forever",
        "not_applicable",
    )


def test_default_plan_is_ready_with_warnings_and_report_only():
    report = _report()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == "HARDEN.N2"
    assert report["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert report["plan_id"] == "harden-n2-test"
    assert report["attachment_item_count"] == len(ACTION_CATEGORIES)
    assert report["planned_action_count"] == len(ACTION_CATEGORIES)
    assert report["missing_action_count"] == 0
    assert report["missing_action_categories"] == []
    assert report["enforcement_not_implemented_confirmed"] is True
    assert report["approval_tokens_treated_as_real_authority"] is False
    assert report["recommended_next_phase"]["phase_id"] == "HARDEN.N3"
    assert "future enforcement remains intentionally unimplemented" in " ".join(report["warnings"]).lower()
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["plan_only"] is True
    assert report["guardrails"]["approval_enforcement_added"] is False
    assert report["guardrails"]["token_validation_gate_added"] is False
    assert report["guardrails"]["route_blocker_added"] is False
    assert report["guardrails"]["auth_policy_changed"] is False
    assert report["guardrails"]["route_behavior_changed"] is False
    assert report["guardrails"]["approval_token_issuance_performed"] is False
    assert report["guardrails"]["approval_token_consumption_performed"] is False


def test_plan_covers_all_required_dangerous_action_categories_with_schema():
    report = _report()
    items = _by_category(report)

    assert set(items) == set(ACTION_CATEGORIES)
    for category in ACTION_CATEGORIES:
        item = items[category]
        for key in (
            "action_category",
            "approval_action",
            "current_runtime_status",
            "human_boundary_level",
            "proposed_attachment_points",
            "preferred_attachment_layer",
            "required_token_fields",
            "required_context_fields",
            "precheck_sequence",
            "failure_mode_later",
            "bypass_risks",
            "rollback_considerations",
            "user_confirmation_surface",
            "audit_log_requirements",
            "not_before_phase",
            "enforcement_allowed_now",
            "notes",
        ):
            assert key in item, f"{category} missing {key}"
        assert item["enforcement_allowed_now"] is False
        assert item["preferred_attachment_layer"] in PREFERRED_ATTACHMENT_LAYERS
        assert item["current_runtime_status"] in {
            "existing_dangerous_surface",
            "future_separate_phase",
            "forbidden_boundary",
        }
        assert isinstance(item["proposed_attachment_points"], list) and item["proposed_attachment_points"]
        assert isinstance(item["precheck_sequence"], list) and item["precheck_sequence"]
        assert isinstance(item["bypass_risks"], list) and item["bypass_risks"]
        assert isinstance(item["audit_log_requirements"], list) and item["audit_log_requirements"]


def test_required_attachment_layers_match_boundary_rules():
    items = _by_category(_report())

    assert items["patch_apply"]["preferred_attachment_layer"] in {"route_precheck", "service_layer_precheck"}
    assert items["worker_launch"]["preferred_attachment_layer"] == "worker_dispatch_precheck"
    assert items["model_call"]["preferred_attachment_layer"] == "model_dispatch_precheck"
    assert items["model_routing"]["preferred_attachment_layer"] == "model_dispatch_precheck"
    assert items["validation_run"]["preferred_attachment_layer"] == "validation_dispatch_precheck"
    assert items["benchmark_run"]["preferred_attachment_layer"] == "benchmark_dispatch_precheck"
    assert items["mcp_tool_invocation"]["preferred_attachment_layer"] == "tool_dispatch_precheck"
    assert items["network_access"]["preferred_attachment_layer"] == "tool_dispatch_precheck"
    assert items["subprocess_execution"]["preferred_attachment_layer"] == "command_dispatch_precheck"
    assert items["docker_execution"]["preferred_attachment_layer"] == "command_dispatch_precheck"
    assert items["registry_mutation"]["preferred_attachment_layer"] == "registry_write_precheck"
    assert items["model_catalog_adoption"]["preferred_attachment_layer"] == "registry_write_precheck"
    assert items["auth_policy_change"]["preferred_attachment_layer"] == "auth_policy_precheck"


def test_forbidden_and_future_token_actions_are_not_implemented_here():
    items = _by_category(_report())

    for category in ("automatic_approval", "automatic_rejection", "hidden_mutation"):
        item = items[category]
        assert item["approval_action"] is None
        assert item["current_runtime_status"] == "forbidden_boundary"
        assert item["preferred_attachment_layer"] == "blocked_forever"
        assert item["human_boundary_level"] == "blocked_forever"
        assert item["enforcement_allowed_now"] is False
        assert "No future approval token may authorize this behavior." in item["notes"]

    for category in ("approval_token_issuance", "approval_token_consumption"):
        item = items[category]
        assert item["approval_action"] is None
        assert item["current_runtime_status"] == "future_separate_phase"
        assert item["preferred_attachment_layer"] == "not_applicable"
        assert item["not_before_phase"].startswith("future separate approval-token")
        assert item["enforcement_allowed_now"] is False
        assert "not implemented in HARDEN.N2" in item["notes"]


def test_token_and_context_field_requirements_are_planned_without_validation():
    report = _report()
    items = _by_category(report)

    assert report["token_field_requirements"]["required_fields"] == [
        "token_id",
        "approval_action",
        "target_type",
        "target_id",
        "risk_level",
        "confirmation_text",
        "confirmation_scope",
        "created_at",
        "single_use",
    ]
    assert report["token_field_requirements"]["validation_gate_implemented"] is False
    for category, item in items.items():
        if category in {"approval_token_issuance", "approval_token_consumption", "automatic_approval", "automatic_rejection", "hidden_mutation"}:
            assert item["required_token_fields"] == []
        else:
            assert "token_id" in item["required_token_fields"]
            assert "approval_action" in item["required_token_fields"]
            assert "target_type" in item["required_token_fields"]
        assert "action_category" in item["required_context_fields"]
        assert "evidence_refs" in item["required_context_fields"]


def test_plan_references_harden_n1_human_n2_and_human_close_artifacts():
    report = _report()

    assert report["source_readiness_audit_path"].endswith(
        ".agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.json"
    )
    assert report["source_approval_contract_path"].endswith(
        ".agent/human/approval_token_contract/human_approval_token_contract.json"
    )
    assert report["source_human_checkpoint_path"].endswith(
        ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.json"
    )
    refs = {item["phase_id"]: item for item in report["source_artifacts"]}
    assert refs["HARDEN.N1"]["present"] is True
    assert refs["HARDEN.N1"]["report_kind_ok"] is True
    assert refs["HUMAN.N2"]["present"] is True
    assert refs["HUMAN.N2"]["report_kind_ok"] is True
    assert refs["HUMAN.CLOSE"]["present"] is True
    assert refs["HUMAN.CLOSE"]["report_kind_ok"] is True


def test_missing_required_source_artifacts_produce_incomplete(tmp_path):
    report = _report(source_readiness_audit_path=tmp_path / "missing_harden_n1.json")

    assert report["plan_status"] == STATUS_INCOMPLETE
    assert any("HARDEN.N1" in reason for reason in report["incomplete_reasons"])


def test_missing_required_action_category_produces_incomplete():
    overrides = {
        category: None
        for category in ACTION_CATEGORIES
    }
    overrides.pop("patch_apply")

    report = _report(attachment_items=overrides)

    assert report["plan_status"] == STATUS_INCOMPLETE
    assert report["missing_action_categories"] == ["patch_apply"]


def test_plan_blocks_if_any_item_allows_enforcement_now():
    report = _report(
        attachment_overrides={
            "patch_apply": {
                "enforcement_allowed_now": True,
            }
        }
    )

    assert report["plan_status"] == STATUS_BLOCKED
    assert any("patch_apply" in reason and "enforcement_allowed_now" in reason for reason in report["blocked_reasons"])


def test_plan_blocks_if_tokens_or_runtime_changes_are_treated_as_real_authority():
    token_report = _report(approval_tokens_treated_as_real_authority=True)
    route_report = _report(runtime_change_markers={"route_behavior_changed": True})
    auth_report = _report(runtime_change_markers={"auth_policy_changed": True})
    issuance_report = _report(runtime_change_markers={"approval_token_issuance_performed": True})

    assert token_report["plan_status"] == STATUS_BLOCKED
    assert any("real authority" in reason.lower() for reason in token_report["blocked_reasons"])
    assert route_report["plan_status"] == STATUS_BLOCKED
    assert any("route behavior" in reason.lower() for reason in route_report["blocked_reasons"])
    assert auth_report["plan_status"] == STATUS_BLOCKED
    assert any("auth policy" in reason.lower() for reason in auth_report["blocked_reasons"])
    assert issuance_report["plan_status"] == STATUS_BLOCKED
    assert any("token issuance" in reason.lower() for reason in issuance_report["blocked_reasons"])


def test_json_and_markdown_attachment_plan_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "harden-n2"

    result = write_approval_enforcement_attachment_plan(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        plan_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HARDEN.N3"
    assert "# Approval Enforcement Attachment Plan" in markdown
    assert "Future Enforcement Boundary" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_approval_enforcement_attachment_plan(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        plan_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["plan_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HARDEN.N3"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_report_sections():
    markdown = render_approval_enforcement_attachment_plan_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## attachment philosophy",
        "## dangerous action attachment matrix",
        "## token field requirements",
        "## confirmation surface plan",
        "## audit log plan",
        "## bypass risk analysis",
        "## rollback considerations",
        "## blocked-forever actions",
        "## future enforcement boundary",
        "## warnings",
        "## blocked reasons",
        "## final verdict",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_harden_n2_complete_adds_n3_and_picker_recommends_harden_n4():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HARDEN.N2"]["status"] == "complete"
    assert by_id["HARDEN.N2"]["title"] == "Approval Enforcement Attachment Plan"
    assert by_id["HARDEN.N2"]["prerequisites"] == ["HARDEN.N1"]
    assert by_id["HARDEN.N2"]["expected_artifacts"] == [
        ".agent/harden/approval_enforcement_attachment_plan/approval_enforcement_attachment_plan.json",
        ".agent/harden/approval_enforcement_attachment_plan/approval_enforcement_attachment_plan.md",
    ]
    assert by_id["HARDEN.N3"]["status"] == "complete"
    assert by_id["HARDEN.N3"]["title"] == "Approval Enforcement Dry-Run Gate Simulator"
    assert by_id["HARDEN.N3"]["prerequisites"] == ["HARDEN.N2"]
    assert by_id["HARDEN.N3"]["network_allowed"] is False
    assert by_id["HARDEN.N3"]["model_calls_allowed"] is False
    assert by_id["HARDEN.N3"]["writes_real_repo"] is False
    assert by_id["HARDEN.N4"]["status"] == "complete"
    assert by_id["HARDEN.N4"]["title"] == "Approval Enforcement Operator Report"
    assert by_id["HARDEN.N4"]["prerequisites"] == ["HARDEN.N3"]
    assert by_id["HARDEN.CLOSE"]["status"] == "complete"
    assert by_id["HARDEN.CLOSE"]["title"] == "Approval Enforcement Planning Branch Checkpoint"
    assert by_id["HARDEN.CLOSE"]["prerequisites"] == ["HARDEN.N4"]
    assert by_id["OPS.TEST.1"]["status"] == "proposed"
    assert by_id["OPS.TEST.1"]["prerequisites"] == ["HARDEN.CLOSE"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="harden-n2-registry",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "OPS.TEST.1"


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
