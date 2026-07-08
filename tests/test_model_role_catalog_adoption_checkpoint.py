"""Tests for ADOPT.MODEL.CLOSE - Model Catalog Adoption Branch Checkpoint."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core.model_role_registry import build_model_role_registry
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_adoption_checkpoint import (
    ADDED_ROLE_IDS,
    CHECKPOINT_STATUSES,
    DEFAULT_OUTPUT_ROOT,
    EXPECTED_ROLE_COUNT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    build_model_role_catalog_adoption_checkpoint,
    render_model_role_catalog_adoption_checkpoint_markdown,
    write_model_role_catalog_adoption_checkpoint,
)
import scripts.create_model_role_catalog_adoption_checkpoint as script


PROJECT_ROOT = Path(__file__).parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "model_role_catalog_adoption_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_model_role_catalog_adoption_checkpoint.py"

PRESERVED_ROLE_IDS = (
    "fast_scout",
    "planner",
    "patch_implementer",
    "code_reviewer",
    "evidence_checker",
    "risk_auditor",
    "local_fallback",
)


def _new_role(role_id: str) -> dict:
    return {
        "role_id": role_id,
        "display_name": role_id.replace("_", " ").title(),
        "role_kind": "reviewer",
        "description": f"{role_id} advisory role for adoption checkpoint tests.",
        "strengths": [f"{role_id} advisory review"],
        "weaknesses": ["does not execute", "does not approve changes"],
        "best_for": [f"{role_id} coverage"],
        "not_for": ["execution authority", "automatic mutation"],
        "risk_level": "low",
        "cost_tier": "low",
        "latency_tier": "fast",
        "context_tier": "medium",
        "reliability_tier": "strong",
        "evidence_expectation": "cite artifact evidence and name uncertainty",
        "allowed_task_types": [f"{role_id}_review"],
        "forbidden_task_types": ["model_call", "model_routing", "worker_launch", "patch_apply"],
        "advisory_only": True,
        "executable_binding_allowed": False,
        "model_ids": [],
        "fallback_roles": ["code_reviewer", "planner"],
        "human_review_required": True,
        "notes": ["Advisory card only; no executable model binding or routing authority."],
    }


def _ten_role_registry() -> dict:
    base = build_model_role_registry()
    roles = copy.deepcopy(base["roles"])
    roles += [_new_role(role_id) for role_id in ADDED_ROLE_IDS]
    registry = build_model_role_registry(role_catalog={"roles": roles}, role_catalog_path="adopted.json")
    registry["recommended_next_phase"] = {
        "phase_id": "ADOPT.MODEL.CLOSE",
        "title": "Model Catalog Adoption Branch Checkpoint",
        "reason": "Freeze the report-only model catalog adoption branch.",
    }
    return registry


def _adoption_receipt(**overrides) -> dict:
    data = {
        "report_kind": "model_role_catalog_adoption_receipt",
        "adoption_status": "model_role_catalog_adoption_complete_with_warnings",
        "adopted_phase_id": "ADOPT.MODEL.1",
        "active_catalog_path": ".agent/model_role_registry/model_role_registry.json",
        "previous_role_count": 7,
        "adopted_role_count": 10,
        "added_roles": list(ADDED_ROLE_IDS),
        "preserved_roles": list(PRESERVED_ROLE_IDS),
        "advisory_only_confirmed": True,
        "executable_binding_allowed_confirmed_false": True,
        "model_routing_enabled_confirmed_false": True,
        "model_calls_allowed_confirmed_false": True,
        "worker_launch_allowed_confirmed_false": True,
        "model_ids_metadata_only_confirmed": True,
        "blocked_reasons": [],
        "warnings": ["post-adoption role coverage recheck was required before close"],
    }
    data.update(overrides)
    return data


def _coverage_report(**overrides) -> dict:
    data = {
        "report_kind": "model_role_post_adoption_coverage",
        "post_adoption_coverage_status": "model_role_post_adoption_coverage_ready_with_warnings",
        "active_role_count": 10,
        "expected_role_count": 10,
        "resolved_gaps": list(ADDED_ROLE_IDS),
        "unresolved_gaps": [],
        "added_roles_verified": True,
        "preserved_roles_verified": True,
        "advisory_only_confirmed": True,
        "executable_binding_allowed_confirmed_false": True,
        "model_routing_enabled_confirmed_false": True,
        "model_calls_allowed_confirmed_false": True,
        "worker_launch_allowed_confirmed_false": True,
        "model_ids_metadata_only_confirmed": True,
        "warnings": ["future routing remains intentionally unimplemented"],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "guardrails": {
            "model_call_performed": False,
            "model_routing_performed": False,
            "worker_launch_performed": False,
            "executable_model_binding_created": False,
            "approval_token_enforcement_changed": False,
        },
    }
    data.update(overrides)
    return data


def _phase(phase_id: str, *, status: str = "complete", track: str | None = None, prereqs: list[str] | None = None) -> dict:
    return {
        "phase_id": phase_id,
        "title": f"{phase_id} title",
        "track": track or phase_id.split(".", 1)[0],
        "status": status,
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
        "prerequisites": prereqs or [],
        "expected_artifacts": [".agent/x.json"],
        "notes": ["Report-only; adds no runtime authority."],
    }


def _phase_registry() -> dict:
    return {
        "schema_version": "1.0",
        "updated_at": "2026-07-08T00:00:00+09:00",
        "phases": [
            _phase("ADOPT.MODEL.1", track="ADOPT", prereqs=["HUMAN.CLOSE"]),
            _phase("ADOPT.MODEL.2", track="ADOPT", prereqs=["ADOPT.MODEL.1"]),
            _phase("ADOPT.MODEL.CLOSE", track="ADOPT", prereqs=["ADOPT.MODEL.2"]),
            _phase("HARDEN.N1", status="proposed", track="HARDEN", prereqs=["ADOPT.MODEL.CLOSE"]),
        ],
    }


def _model_close() -> dict:
    return {
        "report_kind": "model_role_planning_checkpoint",
        "checkpoint_status": "model_role_planning_frozen_with_adoption_ready_warnings",
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "warnings": ["historical MODEL.CLOSE adoption readiness warning"],
    }


def _human_close(**overrides) -> dict:
    data = {
        "report_kind": "human_authority_branch_checkpoint",
        "checkpoint_status": "human_authority_branch_frozen_with_warnings",
        "authority_boundary_summary": {
            "model_catalog_adoption_requires_explicit_human_approval": True,
            "model_routing_is_not_automatic": True,
        },
        "human_approval_boundary": {
            "model_catalog_adoption_requires_explicit_human_approval": True,
            "approval_tokens_authorize_runtime_actions": False,
        },
        "runtime_non_enforcement_verification": {
            "no_model_routing_changed": True,
            "no_runtime_enforcement_route_added": True,
        },
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "warnings": ["future enforcement remains intentionally separate"],
    }
    data.update(overrides)
    return data


def _build(**overrides) -> dict:
    kwargs = {
        "registry_path": "docs/roadmap/phase_registry.json",
        "registry_data": _phase_registry(),
        "active_catalog_path": ".agent/model_role_registry/model_role_registry.json",
        "active_catalog_data": _ten_role_registry(),
        "adoption_receipt_path": ".agent/model_role_registry/adoption/model_role_catalog_adoption_receipt.json",
        "adoption_receipt_data": _adoption_receipt(),
        "post_adoption_coverage_path": ".agent/model_role_registry/post_adoption_coverage/model_role_post_adoption_coverage.json",
        "post_adoption_coverage_data": _coverage_report(),
        "model_close_path": ".agent/model_role_registry/model_role_planning_checkpoint/model_role_planning_checkpoint.json",
        "model_close_data": _model_close(),
        "human_close_path": ".agent/human/authority_branch_checkpoint/human_authority_branch_checkpoint.json",
        "human_close_data": _human_close(),
    }
    kwargs.update(overrides)
    return build_model_role_catalog_adoption_checkpoint(**kwargs)


def test_constants_match_checkpoint_contract():
    assert REPORT_KIND == "model_role_catalog_adoption_checkpoint"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "model_role_registry" / "adoption_checkpoint"
    assert JSON_NAME == "model_role_catalog_adoption_checkpoint.json"
    assert MD_NAME == "model_role_catalog_adoption_checkpoint.md"
    assert EXPECTED_ROLE_COUNT == 10
    assert ADDED_ROLE_IDS == ("ui_reviewer", "test_designer", "documentation_reviewer")
    assert set(CHECKPOINT_STATUSES) == {
        STATUS_FROZEN,
        STATUS_FROZEN_WITH_WARNINGS,
        STATUS_INCOMPLETE,
        STATUS_BLOCKED,
    }


def test_complete_adoption_and_post_coverage_freeze_with_warnings():
    report = _build()

    assert report["report_kind"] == REPORT_KIND
    assert report["checkpoint_id"] == "model-role-catalog-adoption-checkpoint"
    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["active_role_count"] == EXPECTED_ROLE_COUNT
    assert report["expected_role_count"] == EXPECTED_ROLE_COUNT
    assert report["added_roles"] == list(ADDED_ROLE_IDS)
    assert report["resolved_gaps"] == list(ADDED_ROLE_IDS)
    assert report["unresolved_gaps"] == []
    assert report["preserved_roles_verified"] is True
    assert report["advisory_only_confirmed"] is True
    assert report["executable_binding_allowed_confirmed_false"] is True
    assert report["model_routing_enabled_confirmed_false"] is True
    assert report["model_calls_allowed_confirmed_false"] is True
    assert report["worker_launch_allowed_confirmed_false"] is True
    assert report["model_ids_metadata_only_confirmed"] is True
    assert report["human_authority_boundary_referenced"] is True
    assert report["blocked_reasons"] == []
    assert report["incomplete_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "HARDEN.N1"


def test_missing_adoption_receipt_reports_incomplete():
    report = _build(adoption_receipt_data=None)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("adoption receipt" in reason for reason in report["incomplete_reasons"])


def test_missing_post_adoption_coverage_reports_incomplete():
    report = _build(post_adoption_coverage_data=None)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("post-adoption coverage" in reason for reason in report["incomplete_reasons"])


@pytest.mark.parametrize(
    ("fragment", "mutate"),
    [
        ("executable binding", lambda role, catalog: role.__setitem__("executable_binding_allowed", True)),
        ("model routing", lambda role, catalog: catalog.__setitem__("model_routing_enabled", True)),
        ("model calls", lambda role, catalog: catalog.__setitem__("model_calls_allowed", True)),
        ("worker launch", lambda role, catalog: role.__setitem__("launch_worker", True)),
    ],
)
def test_catalog_executable_routing_model_call_and_worker_launch_markers_block(fragment, mutate):
    catalog = _ten_role_registry()
    role = next(role for role in catalog["roles"] if role["role_id"] == "ui_reviewer")
    mutate(role, catalog)

    report = _build(active_catalog_data=catalog)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any(fragment in reason for reason in report["blocked_reasons"])


def test_model_ids_executable_binding_blocks():
    catalog = _ten_role_registry()
    role = next(role for role in catalog["roles"] if role["role_id"] == "ui_reviewer")
    role["model_ids"] = ["descriptive-example-only"]
    metadata_report = _build(active_catalog_data=catalog)
    assert metadata_report["model_ids_metadata_only_confirmed"] is True
    assert metadata_report["blocked_reasons"] == []

    role["model_id_policy"] = "routing_authority"
    blocked_report = _build(active_catalog_data=catalog)

    assert blocked_report["checkpoint_status"] == STATUS_BLOCKED
    assert any("model_id_policy" in reason for reason in blocked_report["blocked_reasons"])


def test_human_authority_boundary_contradiction_blocks():
    report = _build(
        human_close_data=_human_close(
            authority_boundary_summary={
                "model_catalog_adoption_requires_explicit_human_approval": False,
                "model_routing_is_not_automatic": True,
            }
        )
    )

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("HUMAN authority" in reason for reason in report["blocked_reasons"])


def test_writer_writes_checkpoint_json_and_markdown(tmp_path):
    active_path = tmp_path / "model_role_registry.json"
    receipt_path = tmp_path / "model_role_catalog_adoption_receipt.json"
    coverage_path = tmp_path / "model_role_post_adoption_coverage.json"
    registry_path = tmp_path / "phase_registry.json"
    model_close_path = tmp_path / "model_role_planning_checkpoint.json"
    human_close_path = tmp_path / "human_authority_branch_checkpoint.json"
    active_path.write_text(json.dumps(_ten_role_registry(), indent=2), encoding="utf-8")
    receipt_path.write_text(json.dumps(_adoption_receipt(), indent=2), encoding="utf-8")
    coverage_path.write_text(json.dumps(_coverage_report(), indent=2), encoding="utf-8")
    registry_path.write_text(json.dumps(_phase_registry(), indent=2), encoding="utf-8")
    model_close_path.write_text(json.dumps(_model_close(), indent=2), encoding="utf-8")
    human_close_path.write_text(json.dumps(_human_close(), indent=2), encoding="utf-8")

    result = write_model_role_catalog_adoption_checkpoint(
        registry_path=registry_path,
        active_catalog_path=active_path,
        adoption_receipt_path=receipt_path,
        post_adoption_coverage_path=coverage_path,
        model_close_path=model_close_path,
        human_close_path=human_close_path,
        output_dir=tmp_path / "adoption_checkpoint",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    saved = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert saved["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Phase Completion",
        "## Artifact Coverage",
        "## Active Catalog Verification",
        "## Added Role Verification",
        "## Gap Resolution Summary",
        "## Safety Boundary Verification",
        "## Human Authority Boundary Reference",
        "## Runtime Non-Execution Verification",
        "## Warnings",
        "## Blocked Reasons",
        "## Incomplete Reasons",
        "## Final Verdict",
        "## Recommended Next Phase",
        "## Guardrails",
    ):
        assert section in markdown


def test_script_writes_summary_json(tmp_path):
    active_path = tmp_path / "model_role_registry.json"
    receipt_path = tmp_path / "model_role_catalog_adoption_receipt.json"
    coverage_path = tmp_path / "model_role_post_adoption_coverage.json"
    registry_path = tmp_path / "phase_registry.json"
    active_path.write_text(json.dumps(_ten_role_registry(), indent=2), encoding="utf-8")
    receipt_path.write_text(json.dumps(_adoption_receipt(), indent=2), encoding="utf-8")
    coverage_path.write_text(json.dumps(_coverage_report(), indent=2), encoding="utf-8")
    registry_path.write_text(json.dumps(_phase_registry(), indent=2), encoding="utf-8")

    result = script.run_create_model_role_catalog_adoption_checkpoint(
        registry=str(registry_path),
        active_catalog=str(active_path),
        adoption_receipt=str(receipt_path),
        post_adoption_coverage=str(coverage_path),
        model_close=None,
        human_close=None,
        output_dir=str(tmp_path / "adoption_checkpoint"),
    )

    assert result["ok"] is True
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["active_role_count"] == 10
    assert result["summary"]["resolved_gaps"] == list(ADDED_ROLE_IDS)
    assert result["summary"]["unresolved_gaps"] == []
    assert result["summary"]["recommended_next_phase"] == "HARDEN.N1"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()


def test_real_registry_marks_close_complete_adds_harden_n1_and_picker_recommends_harden_n1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["ADOPT.MODEL.CLOSE"]["status"] == "complete"
    assert phases["ADOPT.MODEL.CLOSE"]["prerequisites"] == ["ADOPT.MODEL.2"]
    assert "core/model_role_catalog_adoption_checkpoint.py" in phases["ADOPT.MODEL.CLOSE"]["allowed_files"]
    assert ".agent/model_role_registry/adoption_checkpoint/model_role_catalog_adoption_checkpoint.json" in phases[
        "ADOPT.MODEL.CLOSE"
    ]["expected_artifacts"]
    assert phases["HARDEN.N1"]["status"] == "proposed"
    assert phases["HARDEN.N1"]["title"] == "Approval Enforcement Readiness Audit"
    assert phases["HARDEN.N1"]["prerequisites"] == ["ADOPT.MODEL.CLOSE"]
    assert phases["HARDEN.N1"]["network_allowed"] is False
    assert phases["HARDEN.N1"]["model_calls_allowed"] is False
    assert phases["HARDEN.N1"]["writes_real_repo"] is False

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "HARDEN.N1"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_core_and_script_do_not_call_route_auth_model_worker_or_runtime_sinks():
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

        assert imports.isdisjoint(
            {
                "subprocess",
                "socket",
                "requests",
                "httpx",
                "urllib",
                "openai",
                "anthropic",
                "sqlite3",
                "sqlalchemy",
                "pymongo",
            }
        )
        assert calls.isdisjoint(
            {
                "run",
                "Popen",
                "call",
                "check_call",
                "check_output",
                "urlopen",
                "request",
                "run_validation",
                "run_safe_validation",
                "run_benchmarks",
                "run_gemini_request",
                "run_deepseek_review",
                "apply_patch",
                "patch_apply",
                "launch_worker",
                "spawn_worker",
                "invoke_mcp",
                "issue_token",
                "consume_token",
            }
        )
