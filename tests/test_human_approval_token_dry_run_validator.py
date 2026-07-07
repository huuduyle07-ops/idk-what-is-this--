"""Tests for HUMAN.N3 - Human Approval Token Dry-Run Validator.

HUMAN.N3 validates sample approval-token artifacts against the HUMAN.N2 contract
and writes dry-run reports only. It must not authorize actions, reject live
actions, enforce route behavior, consume tokens, apply patches, run validation or
benchmarks, call models, launch workers, invoke MCP tools, use network access, or
write to databases.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.human_approval_token_contract import build_human_approval_token_contract
from core.human_approval_token_dry_run_validator import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INVALID,
    STATUS_VALID,
    STATUS_VALID_WITH_WARNINGS,
    build_human_approval_token_dry_run,
    render_human_approval_token_dry_run_markdown,
    write_human_approval_token_dry_run,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_human_approval_token_dry_run import run_create_human_approval_token_dry_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "human_approval_token_dry_run_validator.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_human_approval_token_dry_run.py"


def _contract() -> dict:
    return build_human_approval_token_contract(
        report_id="human-n3-contract",
        created_at="2026-07-07T00:00:00+00:00",
        warnings=[],
    )


def _token(**overrides) -> dict:
    data = {
        "token_id": "token-123",
        "approval_action": "approve_patch_apply",
        "target_type": "patch",
        "target_id": "patch-123",
        "target_artifact_path": "patches/patch-123.diff",
        "risk_level": "low",
        "confirmation_text": "I approve patch apply for patch patch-123 only.",
        "confirmation_scope": "single_action",
        "operator_id": "operator-alex",
        "created_at": "2026-07-07T00:00:00+00:00",
        "expires_at": "2026-07-08T00:00:00+00:00",
        "revoked_at": "",
        "revocation_reason": "",
        "single_use": True,
        "consumed_at": "",
        "evidence_refs": ["evidence/report.json"],
        "boundary_refs": ["HUMAN.N1", "HUMAN.N2"],
        "warnings": [],
        "metadata": {},
    }
    data.update(overrides)
    return data


def _report(token: dict, **kwargs) -> dict:
    return build_human_approval_token_dry_run(
        token=token,
        contract=_contract(),
        source_token_path="samples/token-123.json",
        source_contract_path=".agent/human/approval_token_contract/human_approval_token_contract.json",
        report_id="human-n3-test",
        created_at="2026-07-07T00:00:00+00:00",
        now="2026-07-07T12:00:00+00:00",
        **kwargs,
    )


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_contract(path: Path) -> None:
    _write_json(path, _contract())


def test_constants_match_human_n3_contract():
    assert REPORT_KIND == "human_approval_token_dry_run"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "human" / "approval_token_dry_run"
    assert JSON_NAME == "human_approval_token_dry_run.json"
    assert MD_NAME == "human_approval_token_dry_run.md"


def test_valid_sample_token_produces_valid_dry_run_without_authority():
    report = _report(_token())

    assert report["report_kind"] == REPORT_KIND
    assert report["dry_run_status"] == STATUS_VALID
    assert report["token_id"] == "token-123"
    assert report["final_verdict"]["dry_run_valid"] is True
    assert report["final_verdict"]["authorizes_action"] is False
    assert report["boundaries"]["dry_run_only"] is True
    assert report["boundaries"]["authorizes_action"] is False
    assert report["boundaries"]["consumes_token"] is False
    assert report["boundaries"]["applies_patches"] is False
    assert report["recommended_next_phase"]["phase_id"] == "HUMAN.N4"


def test_missing_required_field_invalidates_token():
    token = _token()
    del token["confirmation_text"]

    report = _report(token)

    assert report["dry_run_status"] == STATUS_INVALID
    assert "missing_required_field" in {item["reason"] for item in report["schema_findings"]}
    assert "confirmation_text" in report["blocked_reasons"] or report["blocked_reasons"] == []


def test_unknown_action_target_and_risk_invalidate_token():
    report = _report(
        _token(
            approval_action="approve_everything",
            target_type="everything",
            risk_level="spicy",
        )
    )

    assert report["dry_run_status"] == STATUS_INVALID
    assert "unknown_approval_action" in {item["reason"] for item in report["action_findings"]}
    assert "unknown_target_type" in {item["reason"] for item in report["target_findings"]}
    assert "unknown_risk_level" in {item["reason"] for item in report["schema_findings"]}


def test_generic_confirmation_text_invalidates_token():
    report = _report(_token(confirmation_text="approved"))

    assert report["dry_run_status"] == STATUS_INVALID
    assert "generic_confirmation_text" in {
        item["reason"] for item in report["confirmation_text_findings"]
    }


def test_high_risk_without_expiry_is_valid_with_warnings():
    report = _report(
        _token(
            risk_level="high",
            expires_at="",
            confirmation_text="I approve high risk patch apply for patch patch-123 only.",
        )
    )

    assert report["dry_run_status"] == STATUS_VALID_WITH_WARNINGS
    assert "high_or_critical_without_expiry" in {
        item["reason"] for item in report["expiry_findings"]
    }


def test_revoked_expired_and_consumed_single_use_tokens_are_invalid():
    revoked = _report(_token(revoked_at="2026-07-07T01:00:00+00:00"))
    expired = _report(_token(expires_at="2026-07-07T01:00:00+00:00"))
    consumed = _report(_token(consumed_at="2026-07-07T01:00:00+00:00"))

    assert revoked["dry_run_status"] == STATUS_INVALID
    assert expired["dry_run_status"] == STATUS_INVALID
    assert consumed["dry_run_status"] == STATUS_INVALID
    assert "token_revoked" in {item["reason"] for item in revoked["revocation_findings"]}
    assert "token_expired" in {item["reason"] for item in expired["expiry_findings"]}
    assert "single_use_token_already_consumed" in {
        item["reason"] for item in consumed["reuse_findings"]
    }


def test_scope_mismatch_invalidates_token():
    report = _report(_token(confirmation_scope="all_actions"))

    assert report["dry_run_status"] == STATUS_INVALID
    assert "unknown_confirmation_scope" in {item["reason"] for item in report["scope_findings"]}


def test_unsafe_token_path_blocks_before_authority_is_granted(tmp_path):
    token_path = tmp_path / "secrets" / "token.json"
    contract_path = tmp_path / "contract.json"
    _write_json(token_path, _token())
    _write_contract(contract_path)

    result = write_human_approval_token_dry_run(
        token_path=token_path,
        contract_path=contract_path,
        output_dir=tmp_path / "out",
        report_id="unsafe-path",
        created_at="2026-07-07T00:00:00+00:00",
        now="2026-07-07T12:00:00+00:00",
    )

    report = result["report"]
    assert report["dry_run_status"] == STATUS_BLOCKED
    assert "unsafe_token_path" in {item["reason"] for item in report["blocked_reasons"]}
    assert report["final_verdict"]["authorizes_action"] is False


def test_unsafe_target_artifact_path_blocks_token():
    report = _report(_token(target_artifact_path=".env"))

    assert report["dry_run_status"] == STATUS_BLOCKED
    assert "unsafe_target_artifact_path" in {
        item["reason"] for item in report["blocked_reasons"]
    }


def test_forbidden_metadata_authority_blocks_token():
    report = _report(
        _token(
            metadata={
                "auto_run": True,
                "auto_apply": True,
                "launch_worker": True,
                "bypass_auth": True,
            }
        )
    )

    assert report["dry_run_status"] == STATUS_BLOCKED
    reasons = {item["reason"] for item in report["blocked_reasons"]}
    assert {
        "metadata_auto_run_forbidden",
        "metadata_auto_apply_forbidden",
        "metadata_launch_worker_forbidden",
        "metadata_bypass_auth_forbidden",
    } <= reasons
    assert report["boundaries"]["authorizes_action"] is False


def test_missing_or_malformed_contract_blocks_dry_run(tmp_path):
    token_path = tmp_path / "token.json"
    missing_contract = tmp_path / "missing-contract.json"
    malformed_contract = tmp_path / "malformed-contract.json"
    _write_json(token_path, _token())
    malformed_contract.write_text("{not-json", encoding="utf-8")

    missing = write_human_approval_token_dry_run(
        token_path=token_path,
        contract_path=missing_contract,
        output_dir=tmp_path / "missing-out",
        report_id="missing-contract",
        created_at="2026-07-07T00:00:00+00:00",
    )
    malformed = write_human_approval_token_dry_run(
        token_path=token_path,
        contract_path=malformed_contract,
        output_dir=tmp_path / "malformed-out",
        report_id="malformed-contract",
        created_at="2026-07-07T00:00:00+00:00",
    )

    assert missing["report"]["dry_run_status"] == STATUS_BLOCKED
    assert malformed["report"]["dry_run_status"] == STATUS_BLOCKED
    assert "missing_contract" in {
        item["reason"] for item in missing["report"]["blocked_reasons"]
    }
    assert "malformed_contract_json" in {
        item["reason"] for item in malformed["report"]["blocked_reasons"]
    }


def test_json_and_markdown_dry_run_artifacts_are_written(tmp_path):
    token_path = tmp_path / "sample-token.json"
    contract_path = tmp_path / "contract.json"
    output_dir = tmp_path / "out"
    _write_json(token_path, _token())
    _write_contract(contract_path)

    result = write_human_approval_token_dry_run(
        token_path=token_path,
        contract_path=contract_path,
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-07T00:00:00+00:00",
        now="2026-07-07T12:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / "token-123" / JSON_NAME
    assert Path(result["md_path"]) == output_dir / "token-123" / MD_NAME
    saved = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert saved["dry_run_status"] == STATUS_VALID
    assert "# Human Approval Token Dry-Run" in markdown
    assert "Future Enforcement Boundary" in markdown


def test_cli_writes_summary_json(tmp_path):
    token_path = tmp_path / "sample-token.json"
    contract_path = tmp_path / "contract.json"
    output_dir = tmp_path / "cli-out"
    _write_json(token_path, _token())
    _write_contract(contract_path)

    result = run_create_human_approval_token_dry_run(
        token=token_path,
        contract=contract_path,
        output_dir=output_dir,
        report_id="cli-test",
        created_at="2026-07-07T00:00:00+00:00",
        now="2026-07-07T12:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["dry_run_status"] == STATUS_VALID
    assert result["summary"]["recommended_next_phase"] == "HUMAN.N4"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_report_sections():
    markdown = render_human_approval_token_dry_run_markdown(_report(_token()))
    low = markdown.lower()
    for section in (
        "## summary",
        "## source token",
        "## contract reference",
        "## schema findings",
        "## action / target findings",
        "## confirmation text findings",
        "## scope findings",
        "## expiry / revocation / reuse findings",
        "## evidence and boundary references",
        "## authority boundary findings",
        "## warnings",
        "## blocked reasons",
        "## dry-run verdict",
        "## future enforcement boundary",
        "## recommended next phase",
    ):
        assert section in low, section


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


def test_real_registry_marks_human_n3_complete_and_picker_recommends_human_n4():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["HUMAN.N3"]["status"] == "complete"
    assert by_id["HUMAN.N3"]["prerequisites"] == ["HUMAN.N2"]
    assert by_id["HUMAN.N3"]["expected_artifacts"] == [
        ".agent/human/approval_token_dry_run/<token_id-or-sample>/human_approval_token_dry_run.json",
        ".agent/human/approval_token_dry_run/<token_id-or-sample>/human_approval_token_dry_run.md",
    ]
    assert by_id["HUMAN.N3"]["network_allowed"] is False
    assert by_id["HUMAN.N3"]["model_calls_allowed"] is False
    assert by_id["HUMAN.N3"]["writes_real_repo"] is False
    assert by_id["HUMAN.N4"]["status"] == "complete"
    assert by_id["HUMAN.N4"]["prerequisites"] == ["HUMAN.N3"]
    assert by_id["HUMAN.N4"]["title"] == "Human Approval Token Sample Catalog"
    assert by_id["HUMAN.CLOSE"]["status"] == "proposed"
    assert by_id["HUMAN.CLOSE"]["prerequisites"] == ["HUMAN.N4"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="human-n3-registry",
        created_at="2026-07-07T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "HUMAN.CLOSE"
