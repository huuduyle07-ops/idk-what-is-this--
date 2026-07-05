"""Tests for MODEL.N2 - Model Role Coverage Report."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_registry import build_model_role_registry
from core.phase_picker import pick_phase_candidates
from core.model_role_coverage_report import (
    COVERAGE_STATUSES,
    REPORT_KIND,
    build_model_role_coverage_report,
    render_model_role_coverage_report_markdown,
    write_model_role_coverage_report,
)
import scripts.create_model_role_coverage_report as script


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
        "preflight_status": "preflight_ready",
        "risk_level": risk_level,
        "advisory_roles": roles,
        "role_binding": "advisory_labels_only",
        "executable_assignment": False,
        "executable_worker_id": "",
        "model_id": "",
        "source_evidence_required": evidence,
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
    }
    row.update(over.pop("assignment_overrides", {}))
    data = {
        "report_kind": "commander_manual_assignment_plan",
        "assignment_status": "assignment_ready",
        "tree_id": "tree-1",
        "boss_id": "boss-1",
        "assignments": [row],
        "unassigned_sub_bosses": [],
        "risk_coverage": [
            {
                "sub_boss_id": row["sub_boss_id"],
                "risk_level": risk_level,
                "risk_auditor_assigned": "risk_auditor" in roles,
                "coverage_required": risk_level in {"high", "unknown"},
            }
        ],
        "evidence_coverage": [
            {
                "sub_boss_id": row["sub_boss_id"],
                "evidence_required_count": len(evidence),
                "missing_evidence": not evidence,
                "evidence_checker_assigned": "evidence_checker" in roles,
            }
        ],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _review_pack(*, roles=None, risk_level="medium", evidence=None, **over) -> dict:
    roles = ["risk", "evidence", "reviewer"] if roles is None else list(roles)
    evidence = ["review evidence"] if evidence is None else list(evidence)
    row = {
        "sub_boss_id": "sub-review",
        "title": "Review Commander assignment",
        "status": "ready_for_preflight",
        "preflight_status": "preflight_ready",
        "assigned_advisory_roles": roles,
        "risk_level": risk_level,
        "evidence_required": evidence,
        "unresolved_warnings": [],
        "blocked_reasons": [],
        "human_review_required": risk_level in {"high", "unknown"},
    }
    row.update(over.pop("review_overrides", {}))
    data = {
        "report_kind": "commander_assignment_review_pack",
        "review_status": "review_pack_ready",
        "tree_id": "tree-1",
        "boss_id": "boss-1",
        "per_sub_boss_review": [row],
        "risk_summary": {
            "coverage": [
                {
                    "sub_boss_id": row["sub_boss_id"],
                    "risk_level": risk_level,
                    "risk_auditor_assigned": "risk_auditor" in roles or "risk" in roles,
                    "coverage_required": risk_level in {"high", "unknown"},
                }
            ],
            "high_or_unknown_without_risk_auditor": [],
        },
        "evidence_summary": {
            "coverage": [
                {
                    "sub_boss_id": row["sub_boss_id"],
                    "evidence_required_count": len(evidence),
                    "missing_evidence": not evidence,
                    "evidence_checker_assigned": "evidence_checker" in roles or "evidence" in roles,
                }
            ],
            "missing_evidence_without_evidence_checker": [],
        },
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _role_ids(rows: list[dict]) -> set[str]:
    return {str(row.get("model_role_id") or row.get("role_id") or row.get("canonical_role_id")) for row in rows}


def test_valid_model_n1_registry_alone_produces_report():
    report = build_model_role_coverage_report(
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry(),
    )
    assert report["report_kind"] == REPORT_KIND == "model_role_coverage_report"
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert report["required_commander_roles"] == []
    assert {"planner", "patch_implementer", "code_reviewer", "risk_auditor"} <= set(report["available_model_roles"])
    assert any("optional" in warning for warning in report["warnings"])
    assert report["recommended_next_phase"]["phase_id"] == "MODEL.N3"
    assert all(value is False for value in report["guardrails"].values())


def test_model_n1_plus_cmd_n5_assignment_produces_matched_role_coverage():
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=["planner", "implementer", "reviewer", "evidence_checker", "risk_auditor"]),
    )
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert {"planner", "patch_implementer", "code_reviewer", "evidence_checker", "risk_auditor"} <= _role_ids(report["matched_roles"])
    assert report["missing_roles"] == []
    assert report["blocked_reasons"] == []


def test_model_n1_plus_cmd_n6_review_pack_produces_matched_role_coverage():
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        review_pack_path="review.json",
        review_pack_data=_review_pack(roles=["risk", "evidence", "reviewer"]),
    )
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert {"risk_auditor", "evidence_checker", "code_reviewer"} <= _role_ids(report["matched_roles"])
    assert report["missing_roles"] == []


def test_missing_commander_role_produces_incomplete_status():
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=["ui_reviewer"]),
    )
    assert report["coverage_status"] == "role_coverage_incomplete"
    assert "ui_reviewer" in report["missing_roles"]


def test_executable_binding_allowed_true_blocks():
    registry = _registry()
    registry["roles"][0]["executable_binding_allowed"] = True
    report = build_model_role_coverage_report(model_registry_path="registry.json", model_registry_data=registry)
    assert report["coverage_status"] == "role_coverage_blocked"
    assert any("executable_binding_allowed" in reason for reason in report["blocked_reasons"])


def test_advisory_only_false_blocks():
    registry = _registry()
    registry["roles"][0]["advisory_only"] = False
    report = build_model_role_coverage_report(model_registry_path="registry.json", model_registry_data=registry)
    assert report["coverage_status"] == "role_coverage_blocked"
    assert any("advisory_only" in reason for reason in report["blocked_reasons"])


def test_auto_apply_route_and_launch_flags_block():
    for flag in ("auto_run", "auto_apply", "route_tasks", "launch_worker"):
        registry = _registry()
        registry["roles"][0][flag] = True
        report = build_model_role_coverage_report(model_registry_path="registry.json", model_registry_data=registry)
        assert report["coverage_status"] == "role_coverage_blocked", flag
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_commander_model_binding_blocks_but_model_ids_remain_metadata_only():
    registry = _registry()
    registry["roles"][0]["model_ids"] = ["gpt-4.1-metadata-only"]
    assignment = _assignment(assignment_overrides={"model_id": "gpt-4.1"})
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=registry,
        assignment_path="assignment.json",
        assignment_data=assignment,
    )
    assert report["coverage_status"] == "role_coverage_blocked"
    assert any("model ID" in reason or "model binding" in reason for reason in report["blocked_reasons"])
    assert report["available_model_role_details"][0]["model_id_policy"] == "descriptive_metadata_only"


def test_model_ids_on_registry_cards_are_metadata_only():
    registry = _registry()
    registry["roles"][0]["model_ids"] = ["gpt-4.1-metadata-only"]
    report = build_model_role_coverage_report(model_registry_path="registry.json", model_registry_data=registry)
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert report["blocked_reasons"] == []
    assert report["available_model_role_details"][0]["model_ids"] == ["gpt-4.1-metadata-only"]


def test_unknown_fallback_role_for_required_role_blocks():
    registry = _registry()
    planner = next(role for role in registry["roles"] if role["role_id"] == "planner")
    planner["fallback_roles"] = ["missing_fallback"]
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=registry,
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=["planner"]),
    )
    assert report["coverage_status"] == "role_coverage_blocked"
    assert any("unknown fallback" in reason for reason in report["blocked_reasons"])


def test_high_risk_assignment_without_risk_auditor_coverage_warns():
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=["planner"], risk_level="high"),
    )
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert report["risk_coverage"]["high_or_unknown_without_risk_auditor"] == ["sub-1"]
    assert any("risk_auditor" in warning for warning in report["warnings"])


def test_missing_evidence_without_evidence_checker_coverage_warns():
    report = build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        assignment_path="assignment.json",
        assignment_data=_assignment(roles=["planner"], evidence=[]),
    )
    assert report["coverage_status"] == "role_coverage_ready_with_warnings"
    assert report["evidence_coverage"]["missing_evidence_without_evidence_checker"] == ["sub-1"]
    assert any("evidence_checker" in warning for warning in report["warnings"])


def test_unsafe_source_path_blocks(tmp_path):
    result = script.run_create_model_role_coverage_report(
        model_registry="../model_role_registry.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["coverage_status"] == "role_coverage_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_source_artifact_blocks(tmp_path):
    registry_path = tmp_path / "bad.json"
    registry_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_coverage_report(
        model_registry=str(registry_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["coverage_status"] == "role_coverage_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_source_artifacts_are_not_mutated():
    registry = _registry()
    assignment = _assignment()
    review = _review_pack()
    before = copy.deepcopy((registry, assignment, review))
    build_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=registry,
        assignment_path="assignment.json",
        assignment_data=assignment,
        review_pack_path="review.json",
        review_pack_data=review,
    )
    assert (registry, assignment, review) == before


def test_json_and_markdown_artifacts_are_written(tmp_path):
    result = write_model_role_coverage_report(
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        assignment_path="assignment.json",
        assignment_data=_assignment(),
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_coverage_report.json"
    assert Path(result["md_path"]).name == "model_role_coverage_report.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    assert "## Role Coverage Matrix" in Path(result["md_path"]).read_text(encoding="utf-8")


def test_markdown_contains_required_sections():
    md = render_model_role_coverage_report_markdown(
        build_model_role_coverage_report(
            model_registry_path="registry.json",
            model_registry_data=_registry(),
            assignment_path="assignment.json",
            assignment_data=_assignment(),
        )
    )
    low = md.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## required commander roles",
        "## available tower cards",
        "## role coverage matrix",
        "## missing roles",
        "## risk coverage",
        "## evidence coverage",
        "## fallback coverage",
        "## forbidden authority checks",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(COVERAGE_STATUSES) == {
        "role_coverage_ready",
        "role_coverage_ready_with_warnings",
        "role_coverage_incomplete",
        "role_coverage_blocked",
    }


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_coverage_report.py",
        root / "scripts" / "create_model_role_coverage_report.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_coverage_report.py" and top:
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


def test_registry_and_picker_recommend_model_n3():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N1"]["status"] == "complete"
    assert phases["MODEL.N2"]["status"] == "complete"
    assert phases["MODEL.N2"]["prerequisites"] == ["MODEL.N1"]
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
