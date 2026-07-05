"""Tests for MODEL.N5 - Model Role Catalog Proposal Review."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_coverage_report import build_model_role_coverage_report
from core.model_role_gap_plan import build_model_role_gap_plan
from core.model_role_registry import build_model_role_registry
from core.model_role_catalog_update_proposal import build_model_role_catalog_update_proposal
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_proposal_review import (
    BOUNDARIES,
    REPORT_KIND,
    REVIEW_STATUSES,
    build_model_role_catalog_proposal_review,
    render_model_role_catalog_proposal_review_markdown,
    write_model_role_catalog_proposal_review,
)
import scripts.create_model_role_catalog_proposal_review as script


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


def _gap_plan(registry: dict | None = None) -> dict:
    return build_model_role_gap_plan(
        coverage_path="model_role_coverage_report.json",
        coverage_data=_coverage(registry),
        model_registry_path="model_role_registry.json",
        model_registry_data=_registry() if registry is None else registry,
    )


def _proposal_bundle() -> tuple[dict, dict, dict]:
    registry = _registry()
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="model_role_gap_plan.json",
        gap_plan_data=_gap_plan(registry),
        model_registry_path="model_role_registry.json",
        model_registry_data=registry,
    )
    return proposal, copy.deepcopy(proposal["proposed_registry"]), registry


def _review(
    proposal: dict | None = None,
    proposed_registry: dict | None = None,
    source_registry: dict | None = None,
    **overrides,
) -> dict:
    base_proposal, base_proposed, base_source = _proposal_bundle()
    kwargs = {
        "proposal_path": "model_role_catalog_update_proposal.json",
        "proposal_data": base_proposal if proposal is None else proposal,
        "proposed_registry_path": "proposed_model_role_registry.json",
        "proposed_registry_data": base_proposed if proposed_registry is None else proposed_registry,
        "source_registry_path": "model_role_registry.json",
        "source_registry_data": base_source if source_registry is None else source_registry,
    }
    kwargs.update(overrides)
    return build_model_role_catalog_proposal_review(**kwargs)


def _role_by_id(roles: list[dict], role_id: str) -> dict:
    return next(role for role in roles if role.get("role_id") == role_id)


def test_valid_model_n4_proposal_produces_review_artifact():
    review = _review()
    assert review["report_kind"] == REPORT_KIND == "model_role_catalog_proposal_review"
    assert review["review_id"] == "model-role-catalog-proposal-review"
    assert review["review_status"] == "catalog_proposal_review_ready_with_warnings"
    assert review["adoption_readiness"] == "ready_with_manual_warnings"
    assert review["proposal_summary"]["source_role_count"] == 7
    assert review["proposal_summary"]["proposed_role_count"] == 10
    assert review["blocked_reasons"] == []
    assert review["recommended_next_phase"]["phase_id"] == "MODEL.N6"
    assert all(value is False for value in review["guardrails"].values())


def test_proposed_registry_with_ui_test_docs_roles_passes_safety_checks():
    review = _review()
    role_review = review["proposed_role_review"]
    assert {"ui_reviewer", "test_designer", "documentation_reviewer"} <= set(
        role_review["proposed_new_role_ids"]
    )
    assert role_review["missing_from_proposed_registry"] == []
    assert review["safety_review"]["advisory_only_failures"] == []
    assert review["safety_review"]["executable_binding_failures"] == []
    assert review["safety_review"]["human_review_failures"] == []
    assert review["authority_review"]["forbidden_authority_hits"] == []
    assert review["authority_review"]["executable_worker_binding_hits"] == []
    assert review["authority_review"]["model_id_authority_hits"] == []
    assert review["fallback_review"]["unknown_fallback_roles"] == []


def test_proposed_role_count_mismatch_warns():
    proposal, proposed_registry, source = _proposal_bundle()
    proposed_registry["role_count"] = 999
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_ready_with_warnings"
    assert any("role count" in warning for warning in review["warnings"])


def test_missing_proposed_registry_is_incomplete():
    proposal, _proposed_registry, source = _proposal_bundle()
    review = _review(
        proposal=proposal,
        proposed_registry=None,
        source_registry=source,
        proposed_registry_path="",
        proposed_registry_data=None,
    )
    assert review["review_status"] == "catalog_proposal_review_incomplete"
    assert review["adoption_readiness"] == "not_ready_missing_evidence"


def test_source_role_dropped_without_explanation_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    proposed_registry["roles"] = [
        role for role in proposed_registry["roles"] if role.get("role_id") != "planner"
    ]
    proposed_registry["role_count"] = len(proposed_registry["roles"])
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("source role dropped" in reason for reason in review["blocked_reasons"])


def test_duplicate_role_id_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    proposed_registry["roles"].append(copy.deepcopy(proposed_registry["roles"][-1]))
    proposed_registry["role_count"] = len(proposed_registry["roles"])
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("duplicate role_id" in reason for reason in review["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    _role_by_id(proposed_registry["roles"], "ui_reviewer")["executable_binding_allowed"] = True
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("executable_binding_allowed" in reason for reason in review["blocked_reasons"])


def test_advisory_only_false_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    _role_by_id(proposed_registry["roles"], "ui_reviewer")["advisory_only"] = False
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("advisory_only" in reason for reason in review["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in (
        "auto_run",
        "auto_apply",
        "auto_merge",
        "route_tasks",
        "launch_worker",
        "run_validation",
        "run_benchmark",
        "mutate_files",
        "approve_patch",
    ):
        proposal, proposed_registry, source = _proposal_bundle()
        _role_by_id(proposed_registry["roles"], "ui_reviewer")[flag] = False
        review = _review(proposal, proposed_registry, source)
        assert review["review_status"] == "catalog_proposal_review_blocked", flag
        assert any(flag in reason for reason in review["blocked_reasons"])


def test_model_ids_authority_claim_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    role = _role_by_id(proposed_registry["roles"], "ui_reviewer")
    role["model_ids"] = ["gpt-example"]
    role["model_id_policy"] = "routing_authority"
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("model_ids" in reason or "model_id_policy" in reason for reason in review["blocked_reasons"])


def test_unknown_fallback_role_blocks():
    proposal, proposed_registry, source = _proposal_bundle()
    _role_by_id(proposed_registry["roles"], "ui_reviewer")["fallback_roles"] = ["missing_fallback"]
    review = _review(proposal, proposed_registry, source)
    assert review["review_status"] == "catalog_proposal_review_blocked"
    assert any("unknown fallback" in reason for reason in review["blocked_reasons"])


def test_unsafe_paths_block(tmp_path):
    result = script.run_create_model_role_catalog_proposal_review(
        proposal="../model_role_catalog_update_proposal.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_unsafe_proposed_registry_path_blocks(tmp_path):
    proposal, _proposed_registry, _source = _proposal_bundle()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    result = script.run_create_model_role_catalog_proposal_review(
        proposal=str(proposal_path),
        proposed_registry="../proposed_model_role_registry.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("proposed registry path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_unsafe_source_registry_path_blocks(tmp_path):
    proposal, proposed_registry, _source = _proposal_bundle()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    proposed_path = tmp_path / "proposed.json"
    proposed_path.write_text(json.dumps(proposed_registry, indent=2), encoding="utf-8")
    result = script.run_create_model_role_catalog_proposal_review(
        proposal=str(proposal_path),
        proposed_registry=str(proposed_path),
        source_registry="../model_role_registry.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("source registry path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_proposal_blocks(tmp_path):
    proposal_path = tmp_path / "bad-proposal.json"
    proposal_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_proposal_review(
        proposal=str(proposal_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_proposed_registry_blocks(tmp_path):
    proposal, _proposed_registry, _source = _proposal_bundle()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    proposed_path = tmp_path / "bad-proposed.json"
    proposed_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_proposal_review(
        proposal=str(proposal_path),
        proposed_registry=str(proposed_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_source_registry_blocks(tmp_path):
    proposal, proposed_registry, _source = _proposal_bundle()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    proposed_path = tmp_path / "proposed.json"
    proposed_path.write_text(json.dumps(proposed_registry, indent=2), encoding="utf-8")
    source_path = tmp_path / "bad-source.json"
    source_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_proposal_review(
        proposal=str(proposal_path),
        proposed_registry=str(proposed_path),
        source_registry=str(source_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "catalog_proposal_review_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_source_and_proposed_registries_are_not_mutated():
    proposal, proposed_registry, source = _proposal_bundle()
    before = copy.deepcopy((proposal, proposed_registry, source))
    _review(proposal, proposed_registry, source)
    assert (proposal, proposed_registry, source) == before


def test_json_and_markdown_review_artifacts_are_written(tmp_path):
    proposal, proposed_registry, source = _proposal_bundle()
    result = write_model_role_catalog_proposal_review(
        proposal_path="proposal.json",
        proposal_data=proposal,
        proposed_registry_path="proposed.json",
        proposed_registry_data=proposed_registry,
        source_registry_path="source.json",
        source_registry_data=source,
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_catalog_proposal_review.json"
    assert Path(result["md_path"]).name == "model_role_catalog_proposal_review.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Adoption Readiness" in md
    assert "MODEL.N6" in md


def test_manual_review_checklist_includes_adoption_boundary():
    checklist = _review()["manual_review_checklist"]
    assert "confirm adoption requires a separate explicit phase" in checklist
    assert "confirm source registry is not replaced automatically" in checklist


def test_markdown_contains_required_sections():
    md = render_model_role_catalog_proposal_review_markdown(_review())
    low = md.lower()
    for section in (
        "## summary",
        "## proposal summary",
        "## proposed role review",
        "## coverage review",
        "## safety review",
        "## authority review",
        "## fallback review",
        "## metadata review",
        "## adoption readiness",
        "## manual review checklist",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(REVIEW_STATUSES) == {
        "catalog_proposal_review_ready",
        "catalog_proposal_review_ready_with_warnings",
        "catalog_proposal_review_incomplete",
        "catalog_proposal_review_blocked",
    }
    assert "no automatic registry update" in BOUNDARIES
    assert "writes review artifacts only" in BOUNDARIES


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_catalog_proposal_review.py",
        root / "scripts" / "create_model_role_catalog_proposal_review.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_catalog_proposal_review.py" and top:
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


def test_registry_and_picker_recommend_model_n6():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N4"]["status"] == "complete"
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
