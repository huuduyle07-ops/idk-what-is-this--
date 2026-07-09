"""Tests for HARDEN.N4 - Approval Enforcement Operator Report.

HARDEN.N4 turns HARDEN.N3 dry-run gate simulation output into a human operator
summary. It stays report-only: no enforcement, no token issuance/consumption,
no runtime route/auth changes, and no real approval authority.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.approval_enforcement_dry_run_gate_simulator import DECISION_VALUES
from core.approval_enforcement_operator_report import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    build_approval_enforcement_operator_report,
    render_approval_enforcement_operator_report_markdown,
    write_approval_enforcement_operator_report,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
import scripts.create_approval_enforcement_operator_report as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "approval_enforcement_operator_report.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_approval_enforcement_operator_report.py"


def _report(**kwargs) -> dict:
    return build_approval_enforcement_operator_report(
        repo_root=PROJECT_ROOT,
        report_id="harden-n4-test",
        created_at="2026-07-08T00:00:00+09:00",
        **kwargs,
    )


def _items_by_scenario(report: dict) -> dict[str, dict]:
    return {str(item["scenario_id"]): item for item in report["operator_review_items"]}


def test_constants_match_harden_n4_contract():
    assert REPORT_KIND == "approval_enforcement_operator_report"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "harden" / "approval_enforcement_operator_report"
    assert JSON_NAME == "approval_enforcement_operator_report.json"
    assert MD_NAME == "approval_enforcement_operator_report.md"


def test_default_report_is_ready_with_warnings_and_report_only():
    report = _report()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == "HARDEN.N4"
    assert report["report_status"] == STATUS_READY_WITH_WARNINGS
    assert report["report_id"] == "harden-n4-test"
    assert report["scenario_count"] == 10
    assert report["recommended_next_phase"]["phase_id"] == "HARDEN.CLOSE"
    assert report["enforcement_was_applied"] is False
    assert report["token_was_issued"] is False
    assert report["token_was_consumed"] is False
    assert report["runtime_behavior_changed"] is False
    assert report["simulated_only_notice"]["simulated_only"] is True
    assert "future enforcement remains intentionally unimplemented" in " ".join(report["warnings"]).lower()
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["operator_report_only"] is True
    assert report["guardrails"]["no_runtime_enforcement"] is True
    assert report["guardrails"]["no_token_validation_gate"] is True
    assert report["guardrails"]["no_route_behavior_change"] is True
    assert report["guardrails"]["no_auth_policy_change"] is True


def test_report_schema_contains_operator_fields_and_source_paths():
    report = _report()

    for key in (
        "report_id",
        "report_status",
        "source_simulator_path",
        "source_attachment_plan_path",
        "source_readiness_audit_path",
        "source_token_contract_path",
        "scenario_count",
        "decision_summary",
        "allow_simulations",
        "deny_simulations",
        "block_simulations",
        "warning_simulations",
        "incomplete_simulations",
        "operator_review_items",
        "high_risk_items",
        "blocked_forever_items",
        "simulated_only_notice",
        "enforcement_was_applied",
        "token_was_issued",
        "token_was_consumed",
        "runtime_behavior_changed",
        "warnings",
        "blocked_reasons",
        "incomplete_reasons",
        "recommended_next_phase",
        "guardrails",
    ):
        assert key in report, key
    assert report["source_simulator_path"].endswith(
        ".agent/harden/approval_enforcement_dry_run_gate_simulator/approval_enforcement_dry_run_gate_simulator.json"
    )
    assert report["source_attachment_plan_path"].endswith(
        ".agent/harden/approval_enforcement_attachment_plan/approval_enforcement_attachment_plan.json"
    )
    assert report["source_readiness_audit_path"].endswith(
        ".agent/harden/approval_enforcement_readiness_audit/approval_enforcement_readiness_audit.json"
    )
    assert report["source_token_contract_path"].endswith(
        ".agent/human/approval_token_contract/human_approval_token_contract.json"
    )


def test_decision_summary_counts_every_known_decision_value():
    report = _report()

    assert tuple(report["decision_summary"]) == DECISION_VALUES
    assert report["decision_summary"]["would_allow_with_valid_token"] == 1
    assert report["decision_summary"]["would_deny_missing_token"] == 1
    assert report["decision_summary"]["would_deny_mismatched_token"] == 1
    assert report["decision_summary"]["would_deny_expired_token"] == 1
    assert report["decision_summary"]["would_deny_revoked_token"] == 1
    assert report["decision_summary"]["would_deny_consumed_token"] == 1
    assert report["decision_summary"]["would_block_auto_approval"] == 1
    assert report["decision_summary"]["would_block_auto_rejection"] == 1
    assert report["decision_summary"]["would_block_hidden_mutation"] == 1
    assert report["decision_summary"]["would_require_human_review"] == 1
    assert sum(report["decision_summary"].values()) == report["scenario_count"] == 10


def test_operator_review_items_map_simulator_results_for_human_review():
    report = _report()
    items = _items_by_scenario(report)

    for item in report["operator_review_items"]:
        for key in (
            "scenario_id",
            "action_category",
            "simulated_decision",
            "human_readable_summary",
            "operator_attention_level",
            "why_it_matters",
            "future_enforcement_note",
            "required_human_boundary",
            "recommended_operator_action",
            "simulated_only",
        ):
            assert key in item, f"{item.get('scenario_id')} missing {key}"
        assert item["simulated_only"] is True

    assert items["valid_patch_apply_request_with_valid_token"]["simulated_decision"] == "would_allow_with_valid_token"
    assert items["valid_patch_apply_request_with_valid_token"]["simulated_only"] is True
    assert items["valid_patch_apply_request_with_valid_token"]["operator_attention_level"] == "info"
    assert items["automatic_approval_attempt"]["operator_attention_level"] == "blocked"
    assert items["automatic_rejection_attempt"]["operator_attention_level"] == "blocked"
    assert items["hidden_mutation_attempt"]["operator_attention_level"] == "blocked"
    assert items["model_routing_without_enforcement_phase"]["operator_attention_level"] in {"review", "blocked"}


def test_token_denial_scenarios_are_caution_or_high_risk():
    items = _items_by_scenario(_report())
    for scenario_id in (
        "patch_apply_missing_token",
        "patch_apply_mismatched_target",
        "expired_token",
        "revoked_token",
        "consumed_single_use_token",
    ):
        assert items[scenario_id]["operator_attention_level"] in {"caution", "high_risk"}


def test_report_buckets_allow_deny_block_warning_and_incomplete_items():
    report = _report()

    assert [item["scenario_id"] for item in report["allow_simulations"]] == [
        "valid_patch_apply_request_with_valid_token"
    ]
    assert {item["scenario_id"] for item in report["deny_simulations"]} == {
        "patch_apply_missing_token",
        "patch_apply_mismatched_target",
        "expired_token",
        "revoked_token",
        "consumed_single_use_token",
    }
    assert {item["scenario_id"] for item in report["block_simulations"]} == {
        "automatic_approval_attempt",
        "automatic_rejection_attempt",
        "hidden_mutation_attempt",
    }
    assert [item["scenario_id"] for item in report["warning_simulations"]] == [
        "model_routing_without_enforcement_phase"
    ]
    assert report["incomplete_simulations"] == []
    assert {item["scenario_id"] for item in report["blocked_forever_items"]} == {
        "automatic_approval_attempt",
        "automatic_rejection_attempt",
        "hidden_mutation_attempt",
    }
    assert {item["scenario_id"] for item in report["high_risk_items"]} >= {
        "patch_apply_missing_token",
        "patch_apply_mismatched_target",
    }


def test_report_blocks_if_simulated_allow_or_runtime_markers_become_authority():
    authority = _report(simulated_allow_treated_as_real_authority=True)
    applied = _report(enforcement_was_applied=True)
    issued = _report(token_was_issued=True)
    consumed = _report(token_was_consumed=True)
    changed = _report(runtime_behavior_changed=True)
    auto_allowed = _report(runtime_change_markers={"automatic_approval_allowed": True})
    hidden_allowed = _report(runtime_change_markers={"hidden_mutation_allowed": True})

    for blocked in (authority, applied, issued, consumed, changed, auto_allowed, hidden_allowed):
        assert blocked["report_status"] == STATUS_BLOCKED
        assert blocked["blocked_reasons"]
    assert any("real authority" in reason.lower() for reason in authority["blocked_reasons"])
    assert any("enforcement" in reason.lower() for reason in applied["blocked_reasons"])
    assert any("issued" in reason.lower() for reason in issued["blocked_reasons"])
    assert any("consumed" in reason.lower() for reason in consumed["blocked_reasons"])
    assert any("runtime behavior" in reason.lower() for reason in changed["blocked_reasons"])


def test_missing_or_malformed_simulator_artifact_is_incomplete(tmp_path):
    missing = _report(source_simulator_path=tmp_path / "missing_simulator.json")
    malformed_path = tmp_path / "bad_simulator.json"
    malformed_path.write_text(json.dumps({"report_kind": "approval_enforcement_dry_run_gate_simulator"}), encoding="utf-8")
    malformed = _report(source_simulator_path=malformed_path)

    assert missing["report_status"] == STATUS_INCOMPLETE
    assert any("simulator" in reason.lower() for reason in missing["incomplete_reasons"])
    assert malformed["report_status"] == STATUS_INCOMPLETE
    assert any("no simulation results" in reason.lower() for reason in malformed["incomplete_reasons"])


def test_json_and_markdown_operator_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "harden-n4"

    result = write_approval_enforcement_operator_report(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["report_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HARDEN.CLOSE"
    assert "# Approval Enforcement Operator Report" in markdown
    assert "Operator Review Checklist" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_approval_enforcement_operator_report(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        report_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["report_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HARDEN.CLOSE"
    assert result["summary"]["scenario_count"] == 10
    assert result["summary"]["enforcement_was_applied"] is False
    assert result["summary"]["token_was_issued"] is False
    assert result["summary"]["token_was_consumed"] is False
    assert result["summary"]["runtime_behavior_changed"] is False
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_operator_sections():
    markdown = render_approval_enforcement_operator_report_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## operator notice",
        "## decision summary",
        "## allow simulations",
        "## deny simulations",
        "## block simulations",
        "## human review required",
        "## high-risk items",
        "## blocked-forever items",
        "## operator review checklist",
        "## simulated-only boundary",
        "## warnings",
        "## blocked reasons",
        "## final verdict",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_harden_n4_and_harden_close_complete_then_picker_recommends_ops_test_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HARDEN.N4"]["status"] == "complete"
    assert by_id["HARDEN.N4"]["title"] == "Approval Enforcement Operator Report"
    assert by_id["HARDEN.N4"]["prerequisites"] == ["HARDEN.N3"]
    assert by_id["HARDEN.N4"]["expected_artifacts"] == [
        ".agent/harden/approval_enforcement_operator_report/approval_enforcement_operator_report.json",
        ".agent/harden/approval_enforcement_operator_report/approval_enforcement_operator_report.md",
    ]
    assert by_id["HARDEN.CLOSE"]["status"] == "complete"
    assert by_id["HARDEN.CLOSE"]["title"] == "Approval Enforcement Planning Branch Checkpoint"
    assert by_id["HARDEN.CLOSE"]["prerequisites"] == ["HARDEN.N4"]
    assert by_id["HARDEN.CLOSE"]["network_allowed"] is False
    assert by_id["HARDEN.CLOSE"]["model_calls_allowed"] is False
    assert by_id["HARDEN.CLOSE"]["writes_real_repo"] is False
    assert by_id["OPS.TEST.1"]["status"] == "complete"
    assert by_id["OPS.TEST.1"]["prerequisites"] == ["HARDEN.CLOSE"]
    assert by_id["OPS.TEST.2"]["status"] == "complete"
    assert by_id["OPS.TEST.2"]["prerequisites"] == ["OPS.TEST.1"]
    assert by_id["OPS.TEST.3"]["status"] == "complete"
    assert by_id["OPS.TEST.3"]["prerequisites"] == ["OPS.TEST.2"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="harden-n4-registry",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "UX.RUN.1"


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
