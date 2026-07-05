"""Tests for MODEL.N3 - Model Role Gap Plan."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_coverage_report import build_model_role_coverage_report
from core.model_role_registry import build_model_role_registry
from core.phase_picker import pick_phase_candidates
from core.model_role_gap_plan import (
    FORBIDDEN_CHANGES,
    GAP_PLAN_STATUSES,
    REPORT_KIND,
    build_model_role_gap_plan,
    render_model_role_gap_plan_markdown,
    write_model_role_gap_plan,
)
import scripts.create_model_role_gap_plan as script


def _registry() -> dict:
    return build_model_role_registry()


def _registry_without(*role_ids: str) -> dict:
    registry = _registry()
    omitted = set(role_ids)
    registry["roles"] = [role for role in registry["roles"] if role["role_id"] not in omitted]
    registry["role_count"] = len(registry["roles"])
    return registry


def _assignment(*, roles=None, risk_level="low", evidence=None, **over) -> dict:
    roles = ["planner", "implementer", "reviewer", "evidence_checker"] if roles is None else list(roles)
    evidence = ["pytest evidence"] if evidence is None else list(evidence)
    row = {
        "assignment_id": "sub-1-advisory-assignment",
        "sub_boss_id": "sub-1",
        "title": "Implement safe report",
        "risk_level": risk_level,
        "advisory_roles": roles,
        "role_binding": "advisory_labels_only",
        "executable_assignment": False,
        "model_id": "",
        "source_evidence_required": evidence,
        "warnings": [],
        "blocked_reasons": [],
    }
    row.update(over.pop("assignment_overrides", {}))
    data = {
        "report_kind": "commander_manual_assignment_plan",
        "assignment_status": "assignment_ready",
        "assignments": [row],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _coverage(registry: dict | None = None, *, roles=None, **over) -> dict:
    data = build_model_role_coverage_report(
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry() if registry is None else registry,
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=roles, **over.pop("assignment_options", {})),
    )
    data.update(over)
    return data


def _categories(rows: list[dict]) -> set[str]:
    return {str(row.get("category") or "") for row in rows}


def _affected(rows: list[dict]) -> set[str]:
    return {str(row.get("affected_role") or "") for row in rows}


def test_valid_model_n2_coverage_produces_gap_plan():
    plan = build_model_role_gap_plan(
        coverage_path="model_role_coverage_report.json",
        coverage_data=_coverage(),
    )
    assert plan["report_kind"] == REPORT_KIND == "model_role_gap_plan"
    assert plan["gap_plan_status"] == "gap_plan_ready_with_warnings"
    assert plan["plan_id"] == "model-role-gap-plan"
    assert plan["source_coverage_path"] == "model_role_coverage_report.json"
    assert plan["blocked_reasons"] == []
    assert plan["recommended_next_phase"]["phase_id"] == "MODEL.N4"
    assert all(value is False for value in plan["guardrails"].values())
    assert "do not enable executable_binding_allowed" in plan["forbidden_changes"]


def test_missing_required_role_produces_missing_role_plan():
    coverage = _coverage(registry=_registry_without("risk_auditor"), roles=["risk_auditor"])
    plan = build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=coverage,
    )
    assert "risk_auditor" in _affected(plan["missing_role_plans"])
    row = next(row for row in plan["missing_role_plans"] if row["affected_role"] == "risk_auditor")
    assert row["category"] == "missing_required_role"
    assert row["severity"] == "important"
    assert row["suggested_role_id"] == "risk_auditor"
    assert row["advisory_only"] is True
    assert row["executable_binding_allowed"] is False
    assert any("risk_auditor" in item for item in plan["manual_update_checklist"])


def test_optional_missing_ui_test_docs_roles_produce_warnings_when_not_required():
    plan = build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=_coverage(),
    )
    assert {"ui_reviewer", "test_designer", "documentation_reviewer"} <= _affected(plan["missing_role_plans"])
    assert _categories(plan["missing_role_plans"]) >= {"missing_optional_role"}
    assert any("optional Commander role ui_reviewer" in warning for warning in plan["warnings"])


def test_weak_fallback_produces_fallback_improvement_plan():
    registry = _registry()
    risk = next(role for role in registry["roles"] if role["role_id"] == "risk_auditor")
    risk["fallback_roles"] = []
    coverage = _coverage(registry=registry, roles=["risk_auditor"])
    plan = build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=coverage,
    )
    assert "risk_auditor" in _affected(plan["fallback_improvement_plans"])
    row = next(row for row in plan["fallback_improvement_plans"] if row["affected_role"] == "risk_auditor")
    assert row["category"] == "weak_fallback"
    assert row["suggested_fallback_roles"] == ["code_reviewer", "planner"]


def test_unknown_tiers_produce_metadata_improvement_plans():
    registry = _registry()
    planner = next(role for role in registry["roles"] if role["role_id"] == "planner")
    planner["risk_level"] = "unknown"
    planner["cost_tier"] = "unknown"
    planner["latency_tier"] = "unknown"
    planner["context_tier"] = "unknown"
    planner["reliability_tier"] = "unknown"
    coverage = _coverage(registry=registry, roles=["planner"])
    plan = build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=coverage,
        model_registry_path="model_role_registry.json",
        model_registry_data=registry,
    )
    categories = _categories(plan["metadata_improvement_plans"])
    assert {
        "unknown_risk_level",
        "unknown_cost_tier",
        "unknown_latency_tier",
        "unknown_context_tier",
        "unknown_reliability_tier",
    } <= categories
    assert "planner" in _affected(plan["metadata_improvement_plans"])


def test_weak_evidence_and_forbidden_task_types_produce_weak_role_plans():
    registry = _registry()
    impl = next(role for role in registry["roles"] if role["role_id"] == "patch_implementer")
    impl["evidence_expectation"] = ""
    impl["forbidden_task_types"] = []
    coverage = _coverage(registry=registry, roles=["implementer"])
    plan = build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=coverage,
        model_registry_path="model_role_registry.json",
        model_registry_data=registry,
    )
    assert {"weak_evidence_expectation", "weak_forbidden_task_types"} <= _categories(plan["weak_role_plans"])
    assert "patch_implementer" in _affected(plan["weak_role_plans"])


def test_overpowered_and_unsafe_authority_claims_block():
    coverage = _coverage()
    coverage["available_model_role_details"][0]["can_execute_tasks"] = True
    coverage["overpowered_roles"] = [{"role_id": "planner", "reason": "claims executable authority"}]
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    assert plan["gap_plan_status"] == "gap_plan_blocked"
    assert plan["risky_role_plans"]
    assert any("authority" in reason for reason in plan["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    coverage = _coverage()
    coverage["available_model_role_details"][0]["executable_binding_allowed"] = True
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    assert plan["gap_plan_status"] == "gap_plan_blocked"
    assert any("executable_binding_allowed" in reason for reason in plan["blocked_reasons"])


def test_advisory_only_false_blocks():
    coverage = _coverage()
    coverage["available_model_role_details"][0]["advisory_only"] = False
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    assert plan["gap_plan_status"] == "gap_plan_blocked"
    assert any("advisory_only" in reason for reason in plan["blocked_reasons"])


def test_auto_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "route_tasks", "launch_worker"):
        coverage = _coverage()
        coverage["available_model_role_details"][0][flag] = True
        plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
        assert plan["gap_plan_status"] == "gap_plan_blocked", flag
        assert any(flag in reason for reason in plan["blocked_reasons"])


def test_model_ids_remain_metadata_only_in_recommendations():
    coverage = _coverage()
    coverage["available_model_role_details"][0]["model_ids"] = ["gpt-metadata-label"]
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    rows = [row for row in plan["metadata_improvement_plans"] if row["category"] == "model_id_authority_risk"]
    assert rows
    assert rows[0]["executable_binding_allowed"] is False
    assert "metadata" in rows[0]["reason"].lower()
    assert plan["blocked_reasons"] == []


def test_coverage_report_blocked_blocks_gap_plan():
    coverage = _coverage(coverage_status="role_coverage_blocked", blocked_reasons=["coverage blocker"])
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    assert plan["gap_plan_status"] == "gap_plan_blocked"
    assert any("coverage report is blocked" in reason for reason in plan["blocked_reasons"])


def test_incomplete_coverage_without_useful_data_is_incomplete():
    coverage = {
        "report_kind": "model_role_coverage_report",
        "coverage_status": "role_coverage_incomplete",
        "source_model_registry_path": "",
        "missing_roles": [],
        "available_model_role_details": [],
        "fallback_coverage": [],
        "warnings": [],
        "blocked_reasons": [],
    }
    plan = build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=coverage)
    assert plan["gap_plan_status"] == "gap_plan_incomplete"


def test_unsafe_coverage_path_blocks(tmp_path):
    result = script.run_create_model_role_gap_plan(
        coverage="../model_role_coverage_report.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["gap_plan_status"] == "gap_plan_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_coverage_artifact_blocks(tmp_path):
    coverage_path = tmp_path / "bad.json"
    coverage_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_gap_plan(
        coverage=str(coverage_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["gap_plan_status"] == "gap_plan_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_source_artifacts_are_not_mutated():
    coverage = _coverage()
    registry = _registry()
    before = copy.deepcopy((coverage, registry))
    build_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=coverage,
        model_registry_path="model_role_registry.json",
        model_registry_data=registry,
    )
    assert (coverage, registry) == before


def test_json_and_markdown_artifacts_are_written(tmp_path):
    result = write_model_role_gap_plan(
        coverage_path="coverage.json",
        coverage_data=_coverage(),
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_gap_plan.json"
    assert Path(result["md_path"]).name == "model_role_gap_plan.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    assert "## Manual Update Checklist" in Path(result["md_path"]).read_text(encoding="utf-8")


def test_markdown_contains_required_sections():
    md = render_model_role_gap_plan_markdown(
        build_model_role_gap_plan(coverage_path="coverage.json", coverage_data=_coverage())
    )
    low = md.lower()
    for section in (
        "## summary",
        "## source coverage",
        "## missing role plans",
        "## weak role plans",
        "## risky role plans",
        "## fallback improvements",
        "## metadata improvements",
        "## forbidden changes",
        "## manual update checklist",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(GAP_PLAN_STATUSES) == {
        "gap_plan_ready",
        "gap_plan_ready_with_warnings",
        "gap_plan_incomplete",
        "gap_plan_blocked",
    }
    assert {
        "do not enable executable_binding_allowed",
        "do not set advisory_only false",
        "do not add route_tasks",
        "do not add launch_worker",
        "do not add auto_run",
        "do not add auto_apply",
        "do not add auto_merge",
        "do not allow model IDs to become authority",
        "do not mutate Commander assignments automatically",
    } <= set(FORBIDDEN_CHANGES)


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_gap_plan.py",
        root / "scripts" / "create_model_role_gap_plan.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_gap_plan.py" and top:
                    assert top in allowed_core_imports, f"Unexpected import in core: {module!r}"
                for bad in (
                    "subprocess",
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


def test_registry_and_picker_recommend_model_n4():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N2"]["status"] == "complete"
    assert phases["MODEL.N3"]["status"] == "complete"
    assert phases["MODEL.N3"]["prerequisites"] == ["MODEL.N2"]
    assert phases["MODEL.N4"]["status"] == "complete"
    assert phases["MODEL.N4"]["prerequisites"] == ["MODEL.N3"]
    assert phases["MODEL.N5"]["status"] == "complete"
    assert phases["MODEL.N5"]["prerequisites"] == ["MODEL.N4"]
    assert phases["MODEL.N6"]["status"] == "complete"
    assert phases["MODEL.N6"]["prerequisites"] == ["MODEL.N5"]
    assert phases["MODEL.N7"]["status"] == "complete"
    assert phases["MODEL.N7"]["prerequisites"] == ["MODEL.N6"]
    assert phases["MODEL.CLOSE"]["status"] == "complete"
    assert phases["MODEL.CLOSE"]["prerequisites"] == ["MODEL.N7"]
    assert phases["EVAL.N1"]["status"] == "complete"
    assert phases["EVAL.N1"]["prerequisites"] == ["MODEL.CLOSE"]
    assert phases["EVAL.N2"]["status"] == "complete"
    assert phases["EVAL.N2"]["prerequisites"] == ["EVAL.N1"]
    assert phases["EVAL.N3"]["status"] == "complete"
    assert phases["EVAL.N3"]["prerequisites"] == ["EVAL.N2"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "EVAL.N4"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
