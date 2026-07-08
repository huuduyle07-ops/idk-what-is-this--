"""Tests for HARDEN.N3 - Approval Enforcement Dry-Run Gate Simulator.

HARDEN.N3 is simulation-only and report-only. It may say what a future
approval gate would decide for sample requests and sample tokens, but it must
not enforce gates, consume tokens, issue tokens, change routes/auth, or treat a
sample allow decision as real authority.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.approval_enforcement_dry_run_gate_simulator import (
    DECISION_VALUES,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SCENARIO_IDS,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    build_approval_enforcement_dry_run_gate_simulator,
    render_approval_enforcement_dry_run_gate_simulator_markdown,
    write_approval_enforcement_dry_run_gate_simulator,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
import scripts.create_approval_enforcement_dry_run_gate_simulator as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "approval_enforcement_dry_run_gate_simulator.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_approval_enforcement_dry_run_gate_simulator.py"


def _report(**kwargs) -> dict:
    return build_approval_enforcement_dry_run_gate_simulator(
        repo_root=PROJECT_ROOT,
        simulation_id="harden-n3-test",
        created_at="2026-07-08T00:00:00+09:00",
        now="2026-07-08T00:00:00+00:00",
        **kwargs,
    )


def _by_scenario(report: dict) -> dict[str, dict]:
    return {
        str(item["scenario_id"]): item
        for item in report["simulation_results"]
    }


def test_constants_match_harden_n3_contract():
    assert REPORT_KIND == "approval_enforcement_dry_run_gate_simulator"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "harden" / "approval_enforcement_dry_run_gate_simulator"
    assert JSON_NAME == "approval_enforcement_dry_run_gate_simulator.json"
    assert MD_NAME == "approval_enforcement_dry_run_gate_simulator.md"
    assert DEFAULT_SCENARIO_IDS == (
        "valid_patch_apply_request_with_valid_token",
        "patch_apply_missing_token",
        "patch_apply_mismatched_target",
        "expired_token",
        "revoked_token",
        "consumed_single_use_token",
        "automatic_approval_attempt",
        "automatic_rejection_attempt",
        "hidden_mutation_attempt",
        "model_routing_without_enforcement_phase",
    )
    assert DECISION_VALUES == (
        "would_allow_with_valid_token",
        "would_warn_with_weak_token",
        "would_deny_missing_token",
        "would_deny_mismatched_token",
        "would_deny_expired_token",
        "would_deny_revoked_token",
        "would_deny_consumed_token",
        "would_block_forbidden_action",
        "would_block_hidden_mutation",
        "would_block_auto_approval",
        "would_block_auto_rejection",
        "would_block_unsafe_metadata",
        "would_require_human_review",
        "simulation_incomplete",
    )


def test_default_simulator_is_ready_with_warnings_and_report_only():
    report = _report()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == "HARDEN.N3"
    assert report["simulator_status"] == STATUS_READY_WITH_WARNINGS
    assert report["simulation_id"] == "harden-n3-test"
    assert report["sample_scenario_count"] == len(DEFAULT_SCENARIO_IDS)
    assert report["enforcement_was_applied"] is False
    assert report["sample_tokens_treated_as_real_authority"] is False
    assert report["recommended_next_phase"]["phase_id"] == "HARDEN.N4"
    assert "future enforcement remains intentionally unimplemented" in " ".join(report["warnings"]).lower()
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["simulation_only"] is True
    assert report["guardrails"]["approval_gate_enforced"] is False
    assert report["guardrails"]["approval_token_issuance_performed"] is False
    assert report["guardrails"]["approval_token_consumption_performed"] is False
    assert report["guardrails"]["route_behavior_changed"] is False
    assert report["guardrails"]["auth_policy_changed"] is False


def test_default_simulation_results_have_required_schema():
    report = _report()

    assert [item["scenario_id"] for item in report["simulation_results"]] == list(DEFAULT_SCENARIO_IDS)
    for result in report["simulation_results"]:
        for key in (
            "simulation_id",
            "simulator_status",
            "source_attachment_plan_path",
            "source_token_contract_path",
            "action_request_summary",
            "token_summary",
            "simulated_decision",
            "simulated_reasons",
            "required_token_fields_checked",
            "action_category_match",
            "approval_action_match",
            "target_match",
            "risk_level_match",
            "confirmation_scope_match",
            "expiry_result",
            "revocation_result",
            "reuse_result",
            "forbidden_metadata_result",
            "boundary_result",
            "warnings",
            "blocked_reasons",
            "enforcement_was_applied",
            "recommended_next_phase",
        ):
            assert key in result, f"{result.get('scenario_id')} missing {key}"
        assert result["simulated_decision"] in DECISION_VALUES
        assert result["enforcement_was_applied"] is False
        assert result["boundary_result"]["authorizes_real_action"] is False
        assert result["boundary_result"]["simulation_only"] is True


def test_default_sample_scenarios_produce_required_decisions():
    results = _by_scenario(_report())

    expected = {
        "valid_patch_apply_request_with_valid_token": "would_allow_with_valid_token",
        "patch_apply_missing_token": "would_deny_missing_token",
        "patch_apply_mismatched_target": "would_deny_mismatched_token",
        "expired_token": "would_deny_expired_token",
        "revoked_token": "would_deny_revoked_token",
        "consumed_single_use_token": "would_deny_consumed_token",
        "automatic_approval_attempt": "would_block_auto_approval",
        "automatic_rejection_attempt": "would_block_auto_rejection",
        "hidden_mutation_attempt": "would_block_hidden_mutation",
    }
    for scenario_id, decision in expected.items():
        assert results[scenario_id]["simulated_decision"] == decision
    assert results["model_routing_without_enforcement_phase"]["simulated_decision"] in {
        "would_require_human_review",
        "would_block_forbidden_action",
    }


def test_simulated_allow_never_authorizes_or_applies_enforcement():
    allowed = _by_scenario(_report())["valid_patch_apply_request_with_valid_token"]

    assert allowed["simulated_decision"] == "would_allow_with_valid_token"
    assert allowed["enforcement_was_applied"] is False
    assert allowed["boundary_result"]["authorizes_real_action"] is False
    assert allowed["boundary_result"]["token_consumed"] is False
    assert allowed["boundary_result"]["token_issued"] is False
    assert allowed["boundary_result"]["route_or_auth_changed"] is False
    assert allowed["boundary_result"]["real_dispatch_allowed"] is False


def test_custom_request_and_token_can_be_simulated_without_enforcement():
    request = {
        "request_id": "custom_validation_001",
        "action_category": "validation_run",
        "approval_action": "approve_validation_run",
        "target_type": "validation_plan",
        "target_id": "demo_validation_plan_001",
        "target_artifact_path": "demo/validation/demo_validation_plan_001.json",
        "risk_level": "medium",
        "requested_by": "tester",
        "requested_at": "2026-07-08T00:00:00+00:00",
        "confirmation_scope": "single_run",
        "metadata": {},
    }
    token = {
        "token_id": "custom_validation_token",
        "approval_action": "approve_validation_run",
        "target_type": "validation_plan",
        "target_id": "demo_validation_plan_001",
        "target_artifact_path": "demo/validation/demo_validation_plan_001.json",
        "risk_level": "medium",
        "confirmation_text": "I approve validation run for validation plan demo_validation_plan_001.",
        "confirmation_scope": "single_run",
        "created_at": "2026-07-08T00:00:00+00:00",
        "expires_at": "2099-12-31T23:59:59+00:00",
        "revoked_at": "",
        "single_use": True,
        "consumed_at": "",
        "metadata": {},
    }

    result = _report(sample_action_request=request, sample_approval_token=token)["custom_simulation_result"]

    assert result["simulated_decision"] == "would_allow_with_valid_token"
    assert result["enforcement_was_applied"] is False
    assert result["action_category_match"]["passed"] is True
    assert result["approval_action_match"]["passed"] is True
    assert result["target_match"]["passed"] is True


def test_missing_or_mismatched_custom_inputs_return_simulated_denials():
    request = {
        "request_id": "custom_patch_001",
        "action_category": "patch_apply",
        "approval_action": "approve_patch_apply",
        "target_type": "patch",
        "target_id": "demo_patch_001",
        "target_artifact_path": "demo/patches/demo_patch_001.diff",
        "risk_level": "high",
        "requested_by": "tester",
        "requested_at": "2026-07-08T00:00:00+00:00",
        "confirmation_scope": "single_artifact",
        "metadata": {},
    }
    mismatched_token = {
        "token_id": "wrong_target",
        "approval_action": "approve_patch_apply",
        "target_type": "patch",
        "target_id": "demo_patch_999",
        "risk_level": "high",
        "confirmation_scope": "single_artifact",
        "created_at": "2026-07-08T00:00:00+00:00",
        "expires_at": "2099-12-31T23:59:59+00:00",
        "single_use": True,
        "metadata": {},
    }

    missing = _report(sample_action_request=request, sample_approval_token=None)["custom_simulation_result"]
    mismatched = _report(sample_action_request=request, sample_approval_token=mismatched_token)["custom_simulation_result"]

    assert missing["simulated_decision"] == "would_deny_missing_token"
    assert mismatched["simulated_decision"] == "would_deny_mismatched_token"
    assert mismatched["target_match"]["passed"] is False


def test_hidden_mutation_auto_approval_auto_rejection_and_unsafe_metadata_are_blocked():
    base = {
        "request_id": "custom_patch_001",
        "approval_action": "approve_patch_apply",
        "target_type": "patch",
        "target_id": "demo_patch_001",
        "target_artifact_path": "demo/patches/demo_patch_001.diff",
        "risk_level": "high",
        "requested_by": "tester",
        "requested_at": "2026-07-08T00:00:00+00:00",
        "confirmation_scope": "single_artifact",
        "metadata": {},
    }
    token = {
        "token_id": "valid_patch_apply_token",
        "approval_action": "approve_patch_apply",
        "target_type": "patch",
        "target_id": "demo_patch_001",
        "risk_level": "high",
        "confirmation_scope": "single_artifact",
        "created_at": "2026-07-08T00:00:00+00:00",
        "expires_at": "2099-12-31T23:59:59+00:00",
        "single_use": True,
        "metadata": {},
    }

    auto_approval = _report(
        sample_action_request={**base, "action_category": "automatic_approval"},
        sample_approval_token=token,
    )["custom_simulation_result"]
    auto_rejection = _report(
        sample_action_request={**base, "action_category": "automatic_rejection"},
        sample_approval_token=token,
    )["custom_simulation_result"]
    hidden = _report(
        sample_action_request={**base, "action_category": "patch_apply", "metadata": {"hidden_mutation": True}},
        sample_approval_token=token,
    )["custom_simulation_result"]
    unsafe = _report(
        sample_action_request={**base, "action_category": "patch_apply", "metadata": {"bypass_auth": True}},
        sample_approval_token=token,
    )["custom_simulation_result"]

    assert auto_approval["simulated_decision"] == "would_block_auto_approval"
    assert auto_rejection["simulated_decision"] == "would_block_auto_rejection"
    assert hidden["simulated_decision"] == "would_block_hidden_mutation"
    assert unsafe["simulated_decision"] == "would_block_unsafe_metadata"


def test_missing_artifacts_or_malformed_request_make_simulation_incomplete(tmp_path):
    missing_plan = _report(source_attachment_plan_path=tmp_path / "missing_harden_n2.json")
    malformed_request = _report(sample_action_request={"request_id": "bad"}, sample_approval_token={})

    assert missing_plan["simulator_status"] == STATUS_INCOMPLETE
    assert any("HARDEN.N2" in reason for reason in missing_plan["incomplete_reasons"])
    assert malformed_request["simulator_status"] == STATUS_INCOMPLETE
    assert malformed_request["custom_simulation_result"]["simulated_decision"] == "simulation_incomplete"
    assert any("sample action request" in reason.lower() for reason in malformed_request["incomplete_reasons"])


def test_simulator_blocks_if_it_attempts_runtime_authority_or_token_side_effects():
    token_authority = _report(sample_tokens_treated_as_real_authority=True)
    consume = _report(runtime_change_markers={"approval_token_consumption_performed": True})
    issue = _report(runtime_change_markers={"approval_token_issuance_performed": True})
    route = _report(runtime_change_markers={"route_behavior_changed": True})
    applied = _report(runtime_change_markers={"enforcement_was_applied": True})

    for report in (token_authority, consume, issue, route, applied):
        assert report["simulator_status"] == STATUS_BLOCKED
    assert any("real authority" in reason.lower() for reason in token_authority["blocked_reasons"])
    assert any("token consumption" in reason.lower() for reason in consume["blocked_reasons"])
    assert any("token issuance" in reason.lower() for reason in issue["blocked_reasons"])
    assert any("route behavior" in reason.lower() for reason in route["blocked_reasons"])
    assert any("enforcement" in reason.lower() for reason in applied["blocked_reasons"])


def test_json_and_markdown_simulator_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "harden-n3"

    result = write_approval_enforcement_dry_run_gate_simulator(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        simulation_id="write-test",
        created_at="2026-07-08T00:00:00+09:00",
        now="2026-07-08T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["simulator_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HARDEN.N4"
    assert "# Approval Enforcement Dry-Run Gate Simulator" in markdown
    assert "Simulated Decision Matrix" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = script.run_create_approval_enforcement_dry_run_gate_simulator(
        repo_root=str(PROJECT_ROOT),
        output_dir=str(output_dir),
        simulation_id="cli-test",
        created_at="2026-07-08T00:00:00+09:00",
        now="2026-07-08T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["simulator_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HARDEN.N4"
    assert result["summary"]["sample_scenario_count"] == len(DEFAULT_SCENARIO_IDS)
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_report_sections():
    markdown = render_approval_enforcement_dry_run_gate_simulator_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## simulation philosophy",
        "## sample action requests",
        "## sample tokens",
        "## simulated decision matrix",
        "## token field checks",
        "## boundary checks",
        "## forbidden action simulations",
        "## warnings",
        "## blocked reasons",
        "## future enforcement boundary",
        "## final verdict",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_harden_n3_complete_adds_n4_and_picker_recommends_harden_n4():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HARDEN.N3"]["status"] == "complete"
    assert by_id["HARDEN.N3"]["title"] == "Approval Enforcement Dry-Run Gate Simulator"
    assert by_id["HARDEN.N3"]["prerequisites"] == ["HARDEN.N2"]
    assert by_id["HARDEN.N3"]["expected_artifacts"] == [
        ".agent/harden/approval_enforcement_dry_run_gate_simulator/approval_enforcement_dry_run_gate_simulator.json",
        ".agent/harden/approval_enforcement_dry_run_gate_simulator/approval_enforcement_dry_run_gate_simulator.md",
    ]
    assert by_id["HARDEN.N4"]["status"] == "proposed"
    assert by_id["HARDEN.N4"]["title"] == "Approval Enforcement Operator Report"
    assert by_id["HARDEN.N4"]["prerequisites"] == ["HARDEN.N3"]
    assert by_id["HARDEN.N4"]["network_allowed"] is False
    assert by_id["HARDEN.N4"]["model_calls_allowed"] is False
    assert by_id["HARDEN.N4"]["writes_real_repo"] is False

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="harden-n3-registry",
        created_at="2026-07-08T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "HARDEN.N4"


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
