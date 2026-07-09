"""Tests for HUMAN.N2 - Human Approval Token / Confirmation Contract.

HUMAN.N2 is report-only. It defines the future approval token shape and policy
without enforcing approvals, validating live confirmations, issuing tokens,
approving/rejecting work, applying patches, running validation or benchmarks, or
launching workers.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.human_approval_token_contract import (
    ALLOWED_APPROVAL_ACTIONS,
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    REQUIRED_FIELDS,
    RISK_LEVELS,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY_WITH_WARNINGS,
    TARGET_TYPES,
    TOKEN_SCHEMA_FIELDS,
    build_human_approval_token_contract,
    render_human_approval_token_contract_markdown,
    write_human_approval_token_contract,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_human_approval_token_contract import run_create_human_approval_token_contract


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "human_approval_token_contract.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_human_approval_token_contract.py"


def _report(**kwargs) -> dict:
    return build_human_approval_token_contract(
        report_id="human-n2-test",
        created_at="2026-07-07T00:00:00+00:00",
        **kwargs,
    )


def _section(report: dict, key: str) -> dict:
    value = report[key]
    assert isinstance(value, dict)
    return value


def test_constants_match_human_n2_contract():
    assert REPORT_KIND == "human_approval_token_contract"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "human" / "approval_token_contract"
    assert JSON_NAME == "human_approval_token_contract.json"
    assert MD_NAME == "human_approval_token_contract.md"
    assert REQUIRED_FIELDS == (
        "token_id",
        "approval_action",
        "target_type",
        "target_id",
        "risk_level",
        "confirmation_text",
        "confirmation_scope",
        "created_at",
        "single_use",
    )


def test_contract_schema_and_policy_sections_are_ready_with_warnings():
    report = _report()

    assert report["report_kind"] == REPORT_KIND
    assert report["contract_status"] == STATUS_READY_WITH_WARNINGS
    assert set(REQUIRED_FIELDS) <= set(TOKEN_SCHEMA_FIELDS)
    assert report["summary"]["missing_required_fields"] == []
    assert report["summary"]["missing_dangerous_approval_actions"] == []
    assert report["summary"]["policy_sections_complete"] is True
    assert report["future_enforcement_boundary"]["runtime_enforcement_added"] is False
    assert report["guardrails"]["report_only"] is True
    assert report["guardrails"]["token_issuance_performed"] is False


def test_all_required_fields_and_schema_fields_are_documented():
    report = _report()
    schema = _section(report, "token_schema")

    for field in TOKEN_SCHEMA_FIELDS:
        assert field in schema["fields"], field
        assert "description" in schema["fields"][field]
    assert schema["required_fields"] == list(REQUIRED_FIELDS)
    assert schema["optional_fields"] == [
        field for field in TOKEN_SCHEMA_FIELDS if field not in REQUIRED_FIELDS
    ]


def test_all_dangerous_approval_actions_target_types_and_risk_levels_are_covered():
    report = _report()

    assert set(report["allowed_approval_actions"]) == set(ALLOWED_APPROVAL_ACTIONS)
    assert set(report["target_types"]) == set(TARGET_TYPES)
    assert set(report["risk_levels"]) == set(RISK_LEVELS)
    for action in (
        "approve_patch_apply",
        "approve_worker_launch",
        "approve_validation_run",
        "approve_benchmark_run",
        "approve_model_catalog_adoption",
        "approve_registry_mutation",
        "approve_mcp_tool_invocation",
        "approve_network_access",
        "approve_database_write",
        "approve_auth_policy_change",
        "approve_remote_execution",
        "approve_replay_apply",
        "approve_dream_execution",
    ):
        assert action in report["allowed_approval_actions"]


def test_confirmation_text_rules_reject_generic_future_confirmations():
    rules = _section(_report(), "confirmation_text_rules")

    assert rules["must_be_explicit"] is True
    assert rules["must_mention_action"] is True
    assert rules["must_mention_target"] is True
    assert rules["must_not_be_empty"] is True
    assert set(rules["generic_disallowed_examples"]) >= {"yes", "ok", "do it"}
    assert rules["high_or_critical_requires_stronger_text"] is True
    assert "action + target + risk" in rules["future_enforcement_comparison"]


def test_forbidden_token_behavior_blocks_ai_inferred_approval():
    behavior = _section(_report(), "forbidden_token_behavior")

    assert behavior["ai_generated_approvals_allowed"] is False
    assert behavior["infer_from_advisory_reports_allowed"] is False
    assert behavior["infer_from_evidence_quality_allowed"] is False
    assert behavior["infer_from_mirror_score_allowed"] is False
    assert behavior["infer_from_commander_readiness_allowed"] is False
    assert behavior["infer_from_model_role_readiness_allowed"] is False
    assert behavior["bypass_auth_gates_allowed"] is False
    assert behavior["authorize_hidden_mutation_allowed"] is False


def test_scope_expiry_revocation_and_future_enforcement_policies_are_present():
    report = _report()

    assert _section(report, "scope_rules")["must_not_approve_broader_scope"] is True
    assert _section(report, "expiry_policy")["high_or_critical_should_expire"] is True
    assert _section(report, "expiry_policy")["expired_token_must_not_authorize_future_action"] is True
    assert _section(report, "revocation_policy")["revoked_token_must_not_authorize_future_action"] is True
    assert _section(report, "revocation_policy")["consumed_single_use_must_not_authorize_repeated_action"] is True
    assert _section(report, "future_enforcement_boundary")["runtime_enforcement_added"] is False
    assert "no runtime enforcement yet" in _section(report, "future_enforcement_boundary")["boundary_statement"]


def test_missing_required_schema_field_blocks_contract():
    schema_fields = [field for field in TOKEN_SCHEMA_FIELDS if field != "token_id"]

    report = _report(schema_fields=schema_fields)

    assert report["contract_status"] == STATUS_BLOCKED
    assert "missing_required_schema_fields" in {item["reason"] for item in report["blocked_reasons"]}
    assert "token_id" in report["summary"]["missing_required_fields"]


def test_missing_dangerous_approval_action_blocks_contract():
    actions = [action for action in ALLOWED_APPROVAL_ACTIONS if action != "approve_patch_apply"]

    report = _report(allowed_actions=actions)

    assert report["contract_status"] == STATUS_BLOCKED
    assert "missing_dangerous_approval_actions" in {item["reason"] for item in report["blocked_reasons"]}
    assert "approve_patch_apply" in report["summary"]["missing_dangerous_approval_actions"]


def test_generic_confirmation_or_ai_generated_approval_blocks_contract():
    confirmation = dict(_report()["confirmation_text_rules"])
    confirmation["generic_confirmation_allowed"] = True
    behavior = dict(_report()["forbidden_token_behavior"])
    behavior["ai_generated_approvals_allowed"] = True

    report = _report(confirmation_text_rules=confirmation, forbidden_token_behavior=behavior)

    assert report["contract_status"] == STATUS_BLOCKED
    reasons = {item["reason"] for item in report["blocked_reasons"]}
    assert "generic_confirmation_allowed" in reasons
    assert "ai_generated_approvals_allowed" in reasons


def test_tokens_allowed_to_bypass_auth_blocks_contract():
    behavior = dict(_report()["forbidden_token_behavior"])
    behavior["bypass_auth_gates_allowed"] = True

    report = _report(forbidden_token_behavior=behavior)

    assert report["contract_status"] == STATUS_BLOCKED
    assert "tokens_bypass_auth_allowed" in {item["reason"] for item in report["blocked_reasons"]}


def test_missing_policy_section_reports_incomplete():
    report = _report(expiry_policy={})

    assert report["contract_status"] == STATUS_INCOMPLETE
    assert "expiry_policy" in report["summary"]["missing_policy_sections"]


def test_markdown_contains_required_report_sections():
    markdown = render_human_approval_token_contract_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## approval philosophy",
        "## token schema",
        "## required fields",
        "## allowed actions",
        "## target types",
        "## risk levels",
        "## confirmation text rules",
        "## scope rules",
        "## expiry policy",
        "## revocation policy",
        "## forbidden token behavior",
        "## future enforcement boundary",
        "## human review checklist",
        "## guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_json_and_markdown_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "human-n2"

    result = write_human_approval_token_contract(
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["contract_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "HUMAN.N3"
    assert "# Human Approval Token / Confirmation Contract" in markdown
    assert "HUMAN.N3" in markdown


def test_cli_writes_summary_json(tmp_path):
    output_dir = tmp_path / "cli-out"

    result = run_create_human_approval_token_contract(
        output_dir=output_dir,
        report_id="cli-test",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["contract_status"] == STATUS_READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HUMAN.N3"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_core_and_cli_do_not_import_or_call_execution_primitives():
    forbidden_imports = {"subprocess", "socket", "requests", "httpx", "urllib", "openai", "anthropic"}
    forbidden_calls = {
        "run_validation",
        "run_safe_validation",
        "run_benchmarks",
        "run_gemini_request",
        "run_deepseek_review",
        "call_model",
        "route_model",
        "apply_patch",
        "launch_worker",
        "invoke_mcp",
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


def test_real_registry_marks_human_n2_complete_and_picker_recommends_adopt_model_1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HUMAN.N2"]["status"] == "complete"
    assert by_id["HUMAN.N2"]["prerequisites"] == ["HUMAN.N1"]
    assert by_id["HUMAN.N2"]["expected_artifacts"] == [
        ".agent/human/approval_token_contract/human_approval_token_contract.json",
        ".agent/human/approval_token_contract/human_approval_token_contract.md",
    ]
    assert by_id["HUMAN.N2"]["network_allowed"] is False
    assert by_id["HUMAN.N2"]["model_calls_allowed"] is False
    assert by_id["HUMAN.N2"]["writes_real_repo"] is False
    assert by_id["HUMAN.N3"]["status"] == "complete"
    assert by_id["HUMAN.N3"]["prerequisites"] == ["HUMAN.N2"]
    assert by_id["HUMAN.N3"]["title"] == "Human Approval Token Dry-Run Validator"
    assert by_id["HUMAN.N4"]["status"] == "complete"
    assert by_id["HUMAN.N4"]["prerequisites"] == ["HUMAN.N3"]
    assert by_id["HUMAN.CLOSE"]["status"] == "complete"
    assert by_id["HUMAN.CLOSE"]["prerequisites"] == ["HUMAN.N4"]
    assert by_id["ADOPT.MODEL.1"]["status"] == "complete"
    assert by_id["ADOPT.MODEL.1"]["prerequisites"] == ["HUMAN.CLOSE"]
    assert by_id["ADOPT.MODEL.2"]["status"] == "complete"
    assert by_id["ADOPT.MODEL.2"]["prerequisites"] == ["ADOPT.MODEL.1"]
    assert by_id["ADOPT.MODEL.CLOSE"]["status"] == "complete"
    assert by_id["ADOPT.MODEL.CLOSE"]["prerequisites"] == ["ADOPT.MODEL.2"]
    assert by_id["HARDEN.N1"]["status"] == "complete"
    assert by_id["HARDEN.N1"]["prerequisites"] == ["ADOPT.MODEL.CLOSE"]
    assert by_id["HARDEN.N2"]["status"] == "complete"
    assert by_id["HARDEN.N2"]["prerequisites"] == ["HARDEN.N1"]
    assert by_id["HARDEN.N3"]["status"] == "complete"
    assert by_id["HARDEN.N3"]["prerequisites"] == ["HARDEN.N2"]
    assert by_id["HARDEN.N4"]["status"] == "complete"
    assert by_id["HARDEN.N4"]["prerequisites"] == ["HARDEN.N3"]
    assert by_id["HARDEN.CLOSE"]["status"] == "complete"
    assert by_id["HARDEN.CLOSE"]["prerequisites"] == ["HARDEN.N4"]
    assert by_id["OPS.TEST.1"]["status"] == "complete"
    assert by_id["OPS.TEST.1"]["prerequisites"] == ["HARDEN.CLOSE"]
    assert by_id["OPS.TEST.2"]["status"] == "complete"
    assert by_id["OPS.TEST.2"]["prerequisites"] == ["OPS.TEST.1"]
    assert by_id["OPS.TEST.3"]["status"] == "complete"
    assert by_id["OPS.TEST.3"]["prerequisites"] == ["OPS.TEST.2"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="human-n2-registry",
        created_at="2026-07-07T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "UX.RUN.1"
