"""Tests for MODEL.N4 - Model Role Catalog Update Proposal."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_coverage_report import build_model_role_coverage_report
from core.model_role_gap_plan import build_model_role_gap_plan
from core.model_role_registry import build_model_role_registry
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_update_proposal import (
    FORBIDDEN_CHANGES,
    PROPOSAL_STATUSES,
    REPORT_KIND,
    build_model_role_catalog_update_proposal,
    render_model_role_catalog_update_proposal_markdown,
    write_model_role_catalog_update_proposal,
)
import scripts.create_model_role_catalog_update_proposal as script


def _registry() -> dict:
    return build_model_role_registry()


def _assignment(*, roles=None) -> dict:
    return {
        "report_kind": "commander_manual_assignment_plan",
        "assignment_status": "assignment_ready",
        "assignments": [
            {
                "assignment_id": "sub-1-advisory-assignment",
                "sub_boss_id": "sub-1",
                "title": "Implement safe report",
                "risk_level": "low",
                "advisory_roles": ["planner", "implementer", "reviewer"] if roles is None else list(roles),
                "role_binding": "advisory_labels_only",
                "executable_assignment": False,
                "model_id": "",
                "source_evidence_required": ["pytest evidence"],
                "warnings": [],
                "blocked_reasons": [],
            }
        ],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }


def _coverage(registry: dict | None = None) -> dict:
    return build_model_role_coverage_report(
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry() if registry is None else registry,
        assignment_path="assignment.json",
        assignment_data=_assignment(),
    )


def _gap_plan(registry: dict | None = None, **over) -> dict:
    data = build_model_role_gap_plan(
        coverage_path="model_role_coverage_report.json",
        coverage_data=_coverage(registry),
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry() if registry is None else registry,
    )
    data.update(over)
    return data


def _role_by_id(roles: list[dict], role_id: str) -> dict:
    return next(role for role in roles if role["role_id"] == role_id)


def _new_role_ids(proposal: dict) -> set[str]:
    return {role["role_id"] for role in proposal["proposed_new_roles"]}


def test_valid_model_n3_gap_plan_produces_catalog_update_proposal():
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="model_role_gap_plan.json",
        gap_plan_data=_gap_plan(),
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry(),
    )
    assert proposal["report_kind"] == REPORT_KIND == "model_role_catalog_update_proposal"
    assert proposal["proposal_status"] == "catalog_update_proposal_ready_with_warnings"
    assert proposal["proposal_id"] == "model-role-catalog-update-proposal"
    assert proposal["source_gap_plan_path"] == "model_role_gap_plan.json"
    assert proposal["blocked_reasons"] == []
    assert proposal["recommended_next_phase"]["phase_id"] == "MODEL.N5"
    assert all(value is False for value in proposal["guardrails"].values())


def test_expected_ui_test_docs_cards_are_proposed_and_safe():
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=_gap_plan(),
        model_registry_path="registry.json",
        model_registry_data=_registry(),
    )
    assert {"ui_reviewer", "test_designer", "documentation_reviewer"} <= _new_role_ids(proposal)
    ui = _role_by_id(proposal["proposed_new_roles"], "ui_reviewer")
    tests = _role_by_id(proposal["proposed_new_roles"], "test_designer")
    docs = _role_by_id(proposal["proposed_new_roles"], "documentation_reviewer")
    assert ui["role_kind"] == "reviewer"
    assert tests["role_kind"] == "evidence_checker"
    assert docs["role_kind"] == "reviewer"
    for role in (ui, tests, docs):
        assert role["advisory_only"] is True
        assert role["executable_binding_allowed"] is False
        assert role["human_review_required"] is True
        assert role["model_ids"] == []
        assert role["model_id_policy"] == "descriptive_metadata_only"
        assert any(item in role["forbidden_task_types"] for item in ("patch_apply", "approval_authority"))


def test_proposed_registry_has_increased_role_count_when_missing_roles_exist():
    registry = _registry()
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=_gap_plan(registry),
        model_registry_path="registry.json",
        model_registry_data=registry,
    )
    assert proposal["current_role_count"] == 7
    assert proposal["proposed_role_count"] == 10
    assert len(proposal["unchanged_roles"]) == 7
    assert proposal["diff_summary"]["new_role_count"] == 3


def test_no_source_registry_mutation_occurs():
    registry = _registry()
    gap = _gap_plan(registry)
    before = copy.deepcopy((registry, gap))
    build_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=gap,
        model_registry_path="registry.json",
        model_registry_data=registry,
    )
    assert (registry, gap) == before


def test_duplicate_proposed_role_id_blocks():
    gap = _gap_plan()
    duplicate = dict(gap["missing_role_plans"][0])
    duplicate["gap_id"] = "duplicate-gap"
    gap["missing_role_plans"].append(duplicate)
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=gap,
        model_registry_path="registry.json",
        model_registry_data=_registry(),
    )
    assert proposal["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("duplicate proposed role_id" in reason for reason in proposal["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    gap = _gap_plan()
    gap["missing_role_plans"][0]["executable_binding_allowed"] = True
    proposal = build_model_role_catalog_update_proposal(gap_plan_path="gap.json", gap_plan_data=gap)
    assert proposal["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("executable_binding_allowed" in reason for reason in proposal["blocked_reasons"])


def test_advisory_only_false_blocks():
    gap = _gap_plan()
    gap["missing_role_plans"][0]["advisory_only"] = False
    proposal = build_model_role_catalog_update_proposal(gap_plan_path="gap.json", gap_plan_data=gap)
    assert proposal["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("advisory_only" in reason for reason in proposal["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "route_tasks", "launch_worker"):
        gap = _gap_plan()
        gap["missing_role_plans"][0][flag] = True
        proposal = build_model_role_catalog_update_proposal(gap_plan_path="gap.json", gap_plan_data=gap)
        assert proposal["proposal_status"] == "catalog_update_proposal_blocked", flag
        assert any(flag in reason for reason in proposal["blocked_reasons"])


def test_unknown_fallback_role_blocks():
    gap = _gap_plan()
    gap["missing_role_plans"][0]["suggested_fallback_roles"] = ["missing_fallback"]
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=gap,
        model_registry_path="registry.json",
        model_registry_data=_registry(),
    )
    assert proposal["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("unknown fallback" in reason for reason in proposal["blocked_reasons"])


def test_incomplete_gap_plan_without_useful_changes_is_incomplete():
    gap = {
        "report_kind": "model_role_gap_plan",
        "gap_plan_status": "gap_plan_incomplete",
        "missing_role_plans": [],
        "weak_role_plans": [],
        "risky_role_plans": [],
        "fallback_improvement_plans": [],
        "metadata_improvement_plans": [],
        "warnings": [],
        "blocked_reasons": [],
    }
    proposal = build_model_role_catalog_update_proposal(gap_plan_path="gap.json", gap_plan_data=gap)
    assert proposal["proposal_status"] == "catalog_update_proposal_incomplete"


def test_unsafe_gap_plan_path_blocks(tmp_path):
    result = script.run_create_model_role_catalog_update_proposal(
        gap_plan="../model_role_gap_plan.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_gap_plan_blocks(tmp_path):
    gap_path = tmp_path / "bad-gap.json"
    gap_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_update_proposal(
        gap_plan=str(gap_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_registry_blocks(tmp_path):
    gap_path = tmp_path / "gap.json"
    gap_path.write_text(json.dumps(_gap_plan(), indent=2), encoding="utf-8")
    registry_path = tmp_path / "bad-registry.json"
    registry_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_update_proposal(
        gap_plan=str(gap_path),
        model_registry=str(registry_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["proposal_status"] == "catalog_update_proposal_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_proposed_model_role_registry_json_is_written_separately(tmp_path):
    result = write_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=_gap_plan(),
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        output_dir=tmp_path,
    )
    proposed_path = Path(result["proposed_registry_path"])
    assert proposed_path.name == "proposed_model_role_registry.json"
    assert proposed_path.is_file()
    proposed = json.loads(proposed_path.read_text(encoding="utf-8"))
    assert proposed["report_kind"] == "proposed_model_role_registry"
    assert len(proposed["roles"]) == result["report"]["proposed_role_count"]


def test_json_and_markdown_proposal_artifacts_are_written(tmp_path):
    result = write_model_role_catalog_update_proposal(
        gap_plan_path="gap.json",
        gap_plan_data=_gap_plan(),
        model_registry_path="registry.json",
        model_registry_data=_registry(),
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_catalog_update_proposal.json"
    assert Path(result["md_path"]).name == "model_role_catalog_update_proposal.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    assert "## Proposed New Roles" in Path(result["md_path"]).read_text(encoding="utf-8")


def test_markdown_contains_required_sections():
    md = render_model_role_catalog_update_proposal_markdown(
        build_model_role_catalog_update_proposal(
            gap_plan_path="gap.json",
            gap_plan_data=_gap_plan(),
            model_registry_path="registry.json",
            model_registry_data=_registry(),
        )
    )
    low = md.lower()
    for section in (
        "## summary",
        "## source gap plan",
        "## source registry",
        "## proposed new roles",
        "## proposed role updates",
        "## diff summary",
        "## rejected gap items",
        "## safety checks",
        "## manual review checklist",
        "## forbidden changes",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(PROPOSAL_STATUSES) == {
        "catalog_update_proposal_ready",
        "catalog_update_proposal_ready_with_warnings",
        "catalog_update_proposal_incomplete",
        "catalog_update_proposal_blocked",
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
        "do not mutate MODEL.N1 registry artifact",
    } <= set(FORBIDDEN_CHANGES)


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_catalog_update_proposal.py",
        root / "scripts" / "create_model_role_catalog_update_proposal.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_catalog_update_proposal.py" and top:
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


def test_registry_and_picker_recommend_model_n5():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N3"]["status"] == "complete"
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
