"""Tests for ADOPT.MODEL.2 - Post-Adoption Role Coverage Recheck."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_registry import build_model_role_registry
from core.phase_picker import pick_phase_candidates
from core.model_role_post_adoption_coverage import (
    ADDED_ROLE_IDS,
    EXPECTED_ROLE_COUNT,
    POST_ADOPTION_COVERAGE_STATUSES,
    REPORT_KIND,
    build_model_role_post_adoption_coverage,
    render_model_role_post_adoption_coverage_markdown,
    write_model_role_post_adoption_coverage,
)
import scripts.create_model_role_post_adoption_coverage as script


PRESERVED_ROLE_IDS = (
    "fast_scout",
    "planner",
    "patch_implementer",
    "code_reviewer",
    "evidence_checker",
    "risk_auditor",
    "local_fallback",
)


def _new_role(
    *,
    role_id: str,
    display_name: str,
    role_kind: str = "reviewer",
    fallback_roles: list[str] | None = None,
) -> dict:
    return {
        "role_id": role_id,
        "display_name": display_name,
        "role_kind": role_kind,
        "description": f"{display_name} advisory role for post-adoption coverage tests.",
        "strengths": [f"{role_id} advisory review"],
        "weaknesses": ["does not execute", "does not approve changes"],
        "best_for": [f"{role_id} coverage"],
        "not_for": ["execution authority", "automatic mutation"],
        "risk_level": "low" if role_id == "documentation_reviewer" else "medium",
        "cost_tier": "low" if role_id == "documentation_reviewer" else "medium",
        "latency_tier": "fast" if role_id == "documentation_reviewer" else "medium",
        "context_tier": "medium",
        "reliability_tier": "strong",
        "evidence_expectation": "cite artifact evidence and name remaining uncertainty",
        "allowed_task_types": [f"{role_id}_review"],
        "forbidden_task_types": ["model_call", "model_routing", "worker_launch", "patch_apply"],
        "advisory_only": True,
        "executable_binding_allowed": False,
        "model_ids": [],
        "fallback_roles": fallback_roles or ["code_reviewer", "planner"],
        "human_review_required": True,
        "notes": ["Advisory card only; no executable model binding or routing authority."],
    }


def _ten_role_registry() -> dict:
    base = build_model_role_registry()
    roles = copy.deepcopy(base["roles"])
    roles += [
        _new_role(role_id="ui_reviewer", display_name="UI Reviewer"),
        _new_role(
            role_id="test_designer",
            display_name="Test Designer",
            role_kind="evidence_checker",
            fallback_roles=["evidence_checker", "code_reviewer"],
        ),
        _new_role(role_id="documentation_reviewer", display_name="Documentation Reviewer"),
    ]
    registry = build_model_role_registry(role_catalog={"roles": roles}, role_catalog_path="proposed.json")
    registry["recommended_next_phase"] = {
        "phase_id": "ADOPT.MODEL.2",
        "title": "Post-Adoption Role Coverage Recheck",
        "reason": "Recheck coverage after advisory catalog adoption.",
    }
    return registry


def _adoption_receipt() -> dict:
    return {
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
        "warnings": ["post-adoption role coverage recheck is still needed"],
    }


def _gap_plan() -> dict:
    return {
        "report_kind": "model_role_gap_plan",
        "gap_plan_status": "gap_plan_ready_with_warnings",
        "missing_role_plans": [
            {"affected_role": role_id, "suggested_role_id": role_id, "category": "missing_optional_role"}
            for role_id in ADDED_ROLE_IDS
        ],
        "blocked_reasons": [],
        "warnings": [
            "optional Commander role ui_reviewer is not present in MODEL.N1 tower cards",
            "optional Commander role test_designer is not present in MODEL.N1 tower cards",
            "optional Commander role documentation_reviewer is not present in MODEL.N1 tower cards",
        ],
    }


def _readiness() -> dict:
    return {
        "report_kind": "model_role_catalog_adoption_readiness",
        "readiness_status": "adoption_readiness_ready_with_warnings",
        "blocked_reasons": [],
        "warnings": [],
    }


def _build_report(**overrides) -> dict:
    data = {
        "active_catalog_path": "model_role_registry.json",
        "active_catalog_data": _ten_role_registry(),
        "adoption_receipt_path": "model_role_catalog_adoption_receipt.json",
        "adoption_receipt_data": _adoption_receipt(),
        "gap_plan_path": "model_role_gap_plan.json",
        "gap_plan_data": _gap_plan(),
        "readiness_path": "model_role_catalog_adoption_readiness.json",
        "readiness_data": _readiness(),
    }
    data.update(overrides)
    return build_model_role_post_adoption_coverage(**data)


def _role_ids(data: dict) -> list[str]:
    return [role["role_id"] for role in data["roles"]]


def test_build_report_detects_active_ten_role_catalog_and_resolved_gaps():
    report = _build_report()

    assert report["report_kind"] == REPORT_KIND == "model_role_post_adoption_coverage"
    assert report["report_id"] == "model-role-post-adoption-coverage"
    assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_ready_with_warnings"
    assert report["active_role_count"] == EXPECTED_ROLE_COUNT == 10
    assert report["expected_role_count"] == 10
    assert report["resolved_gaps"] == list(ADDED_ROLE_IDS)
    assert report["unresolved_gaps"] == []
    assert report["added_roles_verified"] is True
    assert report["preserved_roles_verified"] is True
    assert report["advisory_only_confirmed"] is True
    assert report["executable_binding_allowed_confirmed_false"] is True
    assert report["model_routing_enabled_confirmed_false"] is True
    assert report["model_calls_allowed_confirmed_false"] is True
    assert report["worker_launch_allowed_confirmed_false"] is True
    assert report["model_ids_metadata_only_confirmed"] is True
    assert report["blocked_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "ADOPT.MODEL.CLOSE"


def test_added_roles_are_verified_and_previous_roles_are_preserved():
    active = _ten_role_registry()
    report = _build_report(active_catalog_data=active)

    assert set(ADDED_ROLE_IDS) <= set(_role_ids(active))
    assert set(PRESERVED_ROLE_IDS) <= set(_role_ids(active))
    assert report["added_roles_verified"] is True
    assert report["preserved_roles_verified"] is True
    assert report["safety_findings"]["expected_added_roles_present"] is True
    assert report["safety_findings"]["previous_roles_preserved"] is True


def test_missing_added_role_is_incomplete_with_unresolved_gap():
    active = _ten_role_registry()
    active["roles"] = [role for role in active["roles"] if role["role_id"] != "ui_reviewer"]
    active["role_count"] = len(active["roles"])
    report = _build_report(active_catalog_data=active)

    assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_blocked"
    assert report["resolved_gaps"] == ["test_designer", "documentation_reviewer"]
    assert report["unresolved_gaps"] == ["ui_reviewer"]
    assert any("fewer than 10 roles" in reason for reason in report["blocked_reasons"])


def test_missing_adoption_receipt_is_incomplete():
    report = _build_report(adoption_receipt_data=None)

    assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_incomplete"
    assert any("adoption receipt" in reason for reason in report["incomplete_reasons"])


def test_missing_gap_plan_is_incomplete():
    report = _build_report(gap_plan_data=None)

    assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_incomplete"
    assert any("gap plan" in reason for reason in report["incomplete_reasons"])


def test_missing_readiness_artifact_is_ready_with_warnings():
    report = _build_report(readiness_data=None)

    assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_ready_with_warnings"
    assert any("readiness" in warning for warning in report["warnings"])


def test_safety_blockers_detect_executable_routing_model_calls_and_worker_launch():
    cases = [
        ("executable binding", lambda role, data: role.__setitem__("executable_binding_allowed", True)),
        ("model routing", lambda role, data: data.__setitem__("model_routing_enabled", True)),
        ("model calls", lambda role, data: data.__setitem__("model_calls_allowed", True)),
        ("worker launch", lambda role, data: role.__setitem__("launch_worker", True)),
    ]
    for fragment, mutate in cases:
        active = _ten_role_registry()
        role = next(role for role in active["roles"] if role["role_id"] == "ui_reviewer")
        mutate(role, active)

        report = _build_report(active_catalog_data=active)

        assert report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_blocked", fragment
        assert any(fragment in reason for reason in report["blocked_reasons"]), fragment


def test_model_ids_remain_metadata_only_and_authority_policy_blocks():
    active = _ten_role_registry()
    role = next(role for role in active["roles"] if role["role_id"] == "ui_reviewer")
    role["model_ids"] = ["descriptive-example-only"]
    metadata_report = _build_report(active_catalog_data=active)

    assert metadata_report["model_ids_metadata_only_confirmed"] is True
    assert metadata_report["blocked_reasons"] == []

    role["model_id_policy"] = "routing_authority"
    blocked_report = _build_report(active_catalog_data=active)

    assert blocked_report["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_blocked"
    assert any("model_id_policy" in reason for reason in blocked_report["blocked_reasons"])


def test_writer_writes_json_and_markdown_coverage_artifacts(tmp_path):
    active_path = tmp_path / "model_role_registry.json"
    receipt_path = tmp_path / "model_role_catalog_adoption_receipt.json"
    gap_path = tmp_path / "model_role_gap_plan.json"
    readiness_path = tmp_path / "model_role_catalog_adoption_readiness.json"
    active_path.write_text(json.dumps(_ten_role_registry(), indent=2), encoding="utf-8")
    receipt_path.write_text(json.dumps(_adoption_receipt(), indent=2), encoding="utf-8")
    gap_path.write_text(json.dumps(_gap_plan(), indent=2), encoding="utf-8")
    readiness_path.write_text(json.dumps(_readiness(), indent=2), encoding="utf-8")

    result = write_model_role_post_adoption_coverage(
        active_catalog_path=active_path,
        adoption_receipt_path=receipt_path,
        gap_plan_path=gap_path,
        readiness_path=readiness_path,
        output_dir=tmp_path / "post_adoption_coverage",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_post_adoption_coverage.json"
    assert Path(result["md_path"]).name == "model_role_post_adoption_coverage.md"
    written = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert written["active_role_count"] == 10
    assert written["resolved_gaps"] == list(ADDED_ROLE_IDS)
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "Post-Adoption Role Coverage" in md
    assert "ADOPT.MODEL.CLOSE" in md
    assert "no model routing" in md.lower()


def test_script_writes_summary_json_and_markdown(tmp_path):
    active_path = tmp_path / "model_role_registry.json"
    receipt_path = tmp_path / "model_role_catalog_adoption_receipt.json"
    gap_path = tmp_path / "model_role_gap_plan.json"
    readiness_path = tmp_path / "model_role_catalog_adoption_readiness.json"
    active_path.write_text(json.dumps(_ten_role_registry(), indent=2), encoding="utf-8")
    receipt_path.write_text(json.dumps(_adoption_receipt(), indent=2), encoding="utf-8")
    gap_path.write_text(json.dumps(_gap_plan(), indent=2), encoding="utf-8")
    readiness_path.write_text(json.dumps(_readiness(), indent=2), encoding="utf-8")

    result = script.run_create_model_role_post_adoption_coverage(
        active_catalog=str(active_path),
        adoption_receipt=str(receipt_path),
        gap_plan=str(gap_path),
        readiness=str(readiness_path),
        output_dir=str(tmp_path / "post_adoption_coverage"),
    )

    assert result["ok"] is True
    assert result["summary"]["post_adoption_coverage_status"] == "model_role_post_adoption_coverage_ready_with_warnings"
    assert result["summary"]["active_role_count"] == 10
    assert result["summary"]["resolved_gaps"] == list(ADDED_ROLE_IDS)
    assert result["summary"]["unresolved_gaps"] == []
    assert result["summary"]["recommended_next_phase"] == "ADOPT.MODEL.CLOSE"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()


def test_markdown_contains_required_sections():
    md = render_model_role_post_adoption_coverage_markdown(_build_report())
    low = md.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## resolved gaps",
        "## unresolved gaps",
        "## role verification",
        "## safety confirmations",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_status_constants_match_contract():
    assert set(POST_ADOPTION_COVERAGE_STATUSES) == {
        "model_role_post_adoption_coverage_ready",
        "model_role_post_adoption_coverage_ready_with_warnings",
        "model_role_post_adoption_coverage_incomplete",
        "model_role_post_adoption_coverage_blocked",
    }


def test_phase_registry_marks_adopt_model_2_complete_and_picker_recommends_close():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["ADOPT.MODEL.2"]["status"] == "complete"
    assert phases["ADOPT.MODEL.2"]["prerequisites"] == ["ADOPT.MODEL.1"]
    assert "core/model_role_post_adoption_coverage.py" in phases["ADOPT.MODEL.2"]["allowed_files"]
    assert ".agent/model_role_registry/post_adoption_coverage/model_role_post_adoption_coverage.json" in phases["ADOPT.MODEL.2"]["expected_artifacts"]
    assert phases["ADOPT.MODEL.CLOSE"]["status"] == "complete"
    assert phases["ADOPT.MODEL.CLOSE"]["prerequisites"] == ["ADOPT.MODEL.2"]
    assert phases["HARDEN.N1"]["status"] == "complete"
    assert phases["HARDEN.N1"]["prerequisites"] == ["ADOPT.MODEL.CLOSE"]
    assert phases["HARDEN.N2"]["status"] == "complete"
    assert phases["HARDEN.N2"]["prerequisites"] == ["HARDEN.N1"]
    assert phases["HARDEN.N3"]["status"] == "complete"
    assert phases["HARDEN.N3"]["prerequisites"] == ["HARDEN.N2"]
    assert phases["HARDEN.N4"]["status"] == "complete"
    assert phases["HARDEN.N4"]["prerequisites"] == ["HARDEN.N3"]
    assert phases["HARDEN.CLOSE"]["status"] == "proposed"
    assert phases["HARDEN.CLOSE"]["prerequisites"] == ["HARDEN.N4"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "HARDEN.CLOSE"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"


def test_source_has_no_route_auth_model_worker_or_runtime_changes():
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_post_adoption_coverage.py",
        root / "scripts" / "create_model_role_post_adoption_coverage.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                for bad in (
                    "requests",
                    "httpx",
                    "urllib.request",
                    "socket",
                    "aiohttp",
                    "openai",
                    "anthropic",
                    "litellm",
                    "ollama",
                    "generativeai",
                    "sqlite3",
                    "psycopg",
                    "sqlalchemy",
                    "pymongo",
                    "core.router",
                    "core.driver_model_routing",
                    "web.auth_gate",
                ):
                    assert bad not in imported, f"{path} imports {bad}"
            elif isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                assert name not in {
                    "Popen",
                    "run",
                    "call",
                    "check_call",
                    "check_output",
                    "urlopen",
                    "request",
                    "run_safe_validation",
                    "run_benchmarks",
                    "apply_patch",
                    "patch_apply",
                    "launch_worker",
                    "worker_launch",
                    "spawn_worker",
                }, f"{path} calls forbidden function {name}"
