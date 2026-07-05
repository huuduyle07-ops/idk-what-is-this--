"""Tests for MODEL.N7 - Model Role Catalog Adoption Readiness Check."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.model_role_coverage_report import build_model_role_coverage_report
from core.model_role_gap_plan import build_model_role_gap_plan
from core.model_role_registry import build_model_role_registry
from core.model_role_catalog_update_proposal import build_model_role_catalog_update_proposal
from core.model_role_catalog_proposal_review import build_model_role_catalog_proposal_review
from core.model_role_catalog_adoption_plan import build_model_role_catalog_adoption_plan
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_adoption_readiness import (
    BOUNDARIES,
    READINESS_STATUSES,
    REPORT_KIND,
    build_model_role_catalog_adoption_readiness,
    render_model_role_catalog_adoption_readiness_markdown,
    write_model_role_catalog_adoption_readiness,
)
import scripts.create_model_role_catalog_adoption_readiness as script


def _registry() -> dict:
    return build_model_role_registry()


def _assignment() -> dict:
    return {
        "report_kind": "commander_manual_assignment_plan",
        "assignment_status": "assignment_ready",
        "assignments": [
            {
                "assignment_id": "sub-1-advisory-assignment",
                "sub_boss_id": "sub-1",
                "title": "Implement safe report",
                "risk_level": "low",
                "advisory_roles": ["planner", "implementer", "reviewer"],
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


def _readiness_bundle() -> tuple[dict, dict, dict, dict, dict]:
    proposal, proposed_registry, source_registry = _proposal_bundle()
    review = build_model_role_catalog_proposal_review(
        proposal_path="model_role_catalog_update_proposal.json",
        proposal_data=proposal,
        proposed_registry_path="proposed_model_role_registry.json",
        proposed_registry_data=proposed_registry,
        source_registry_path="model_role_registry.json",
        source_registry_data=source_registry,
    )
    adoption_plan = build_model_role_catalog_adoption_plan(
        review_path="model_role_catalog_proposal_review.json",
        review_data=review,
        source_registry_path="model_role_registry.json",
        source_registry_data=source_registry,
        proposed_registry_path="proposed_model_role_registry.json",
        proposed_registry_data=proposed_registry,
    )
    return proposal, review, adoption_plan, source_registry, proposed_registry


def _readiness(
    proposal: dict | None = None,
    review: dict | None = None,
    adoption_plan: dict | None = None,
    source_registry: dict | None = None,
    proposed_registry: dict | None = None,
    **overrides,
) -> dict:
    base_proposal, base_review, base_plan, base_source, base_proposed = _readiness_bundle()
    kwargs = {
        "proposal_path": "model_role_catalog_update_proposal.json",
        "proposal_data": base_proposal if proposal is None else proposal,
        "review_path": "model_role_catalog_proposal_review.json",
        "review_data": base_review if review is None else review,
        "adoption_plan_path": "model_role_catalog_adoption_plan.json",
        "adoption_plan_data": base_plan if adoption_plan is None else adoption_plan,
        "source_registry_path": "model_role_registry.json",
        "source_registry_data": base_source if source_registry is None else source_registry,
        "proposed_registry_path": "proposed_model_role_registry.json",
        "proposed_registry_data": base_proposed if proposed_registry is None else proposed_registry,
    }
    kwargs.update(overrides)
    return build_model_role_catalog_adoption_readiness(**kwargs)


def _role_by_id(roles: list[dict], role_id: str) -> dict:
    return next(role for role in roles if role.get("role_id") == role_id)


def test_valid_model_chain_produces_readiness_report():
    report = _readiness()
    assert report["report_kind"] == REPORT_KIND == "model_role_catalog_adoption_readiness"
    assert report["readiness_id"] == "model-role-catalog-adoption-readiness"
    assert report["readiness_status"] == "adoption_readiness_ready_with_warnings"
    assert report["proposal_check"]["proposal_status"] == "catalog_update_proposal_ready_with_warnings"
    assert report["review_check"]["review_status"] == "catalog_proposal_review_ready_with_warnings"
    assert report["adoption_plan_check"]["adoption_plan_status"] == "adoption_plan_ready_with_warnings"
    assert report["proposed_registry_safety_check"]["proposed_role_count"] == 10
    assert report["blocked_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "MODEL.CLOSE"
    assert all(value is False for value in report["guardrails"].values())


def test_ready_with_warnings_inputs_produce_ready_with_warnings_readiness():
    report = _readiness()
    assert report["readiness_status"] == "adoption_readiness_ready_with_warnings"
    assert any("proposal status is catalog_update_proposal_ready_with_warnings" in item for item in report["warnings"])
    assert any("review status is catalog_proposal_review_ready_with_warnings" in item for item in report["warnings"])
    assert any("adoption plan status is adoption_plan_ready_with_warnings" in item for item in report["warnings"])


def test_missing_required_artifacts_block_readiness():
    for label, override in (
        ("proposal", {"proposal_data": None, "proposal_path": ""}),
        ("review", {"review_data": None, "review_path": ""}),
        ("adoption plan", {"adoption_plan_data": None, "adoption_plan_path": ""}),
        ("proposed registry", {"proposed_registry_data": None, "proposed_registry_path": ""}),
    ):
        report = _readiness(**override)
        assert report["readiness_status"] == "adoption_readiness_blocked", label
        assert any(label in reason for reason in report["blocked_reasons"])


def test_review_blockers_block_readiness():
    proposal, review, plan, source, proposed = _readiness_bundle()
    review["review_status"] = "catalog_proposal_review_blocked"
    review["blocked_reasons"] = ["unsafe proposed registry"]
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("review blocker" in reason for reason in report["blocked_reasons"])


def test_adoption_plan_blockers_block_readiness():
    proposal, review, plan, source, proposed = _readiness_bundle()
    plan["adoption_plan_status"] = "adoption_plan_blocked"
    plan["blocked_reasons"] = ["rollback missing"]
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("adoption plan blocker" in reason for reason in report["blocked_reasons"])


def test_proposed_registry_dropping_source_role_blocks():
    proposal, review, plan, source, proposed = _readiness_bundle()
    proposed["roles"] = [role for role in proposed["roles"] if role.get("role_id") != "planner"]
    proposed["role_count"] = len(proposed["roles"])
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("source role dropped" in reason for reason in report["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    proposal, review, plan, source, proposed = _readiness_bundle()
    _role_by_id(proposed["roles"], "ui_reviewer")["executable_binding_allowed"] = True
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("executable_binding_allowed" in reason for reason in report["blocked_reasons"])


def test_advisory_only_false_blocks():
    proposal, review, plan, source, proposed = _readiness_bundle()
    _role_by_id(proposed["roles"], "ui_reviewer")["advisory_only"] = False
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("advisory_only" in reason for reason in report["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "route_tasks", "launch_worker"):
        proposal, review, plan, source, proposed = _readiness_bundle()
        _role_by_id(proposed["roles"], "ui_reviewer")[flag] = True
        report = _readiness(proposal, review, plan, source, proposed)
        assert report["readiness_status"] == "adoption_readiness_blocked", flag
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_model_ids_authority_claim_blocks():
    proposal, review, plan, source, proposed = _readiness_bundle()
    role = _role_by_id(proposed["roles"], "ui_reviewer")
    role["model_ids"] = ["gpt-example"]
    role["model_id_policy"] = "routing_authority"
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("model_id_policy" in reason or "model_ids" in reason for reason in report["blocked_reasons"])


def test_missing_rollback_plan_blocks_readiness():
    proposal, review, plan, source, proposed = _readiness_bundle()
    plan["rollback_plan"] = {}
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("rollback" in reason for reason in report["blocked_reasons"])


def test_missing_separate_adoption_boundary_blocks_readiness():
    proposal, review, plan, source, proposed = _readiness_bundle()
    plan["human_approval_checklist"] = ["human reviewed proposed registry"]
    report = _readiness(proposal, review, plan, source, proposed)
    assert report["readiness_status"] == "adoption_readiness_blocked"
    assert any("separate" in reason and "adoption" in reason for reason in report["blocked_reasons"])


def test_unsafe_paths_block_cli(tmp_path):
    result = script.run_create_model_role_catalog_adoption_readiness(
        proposal="../proposal.json",
        review="../review.json",
        adoption_plan="../adoption.json",
        source_registry="../source.json",
        proposed_registry="../proposed.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["readiness_status"] == "adoption_readiness_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_artifacts_block_cli(tmp_path):
    bad_paths = []
    for name in ("proposal", "review", "adoption", "source", "proposed"):
        path = tmp_path / f"{name}.json"
        path.write_text("{bad-json", encoding="utf-8")
        bad_paths.append(path)
    result = script.run_create_model_role_catalog_adoption_readiness(
        proposal=str(bad_paths[0]),
        review=str(bad_paths[1]),
        adoption_plan=str(bad_paths[2]),
        source_registry=str(bad_paths[3]),
        proposed_registry=str(bad_paths[4]),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["readiness_status"] == "adoption_readiness_blocked"
    assert sum("valid JSON" in reason for reason in result["report"]["blocked_reasons"]) >= 5


def test_source_and_proposed_registries_are_not_mutated():
    proposal, review, plan, source, proposed = _readiness_bundle()
    before = copy.deepcopy((proposal, review, plan, source, proposed))
    _readiness(proposal, review, plan, source, proposed)
    assert (proposal, review, plan, source, proposed) == before


def test_json_and_markdown_readiness_artifacts_are_written(tmp_path):
    proposal, review, plan, source, proposed = _readiness_bundle()
    result = write_model_role_catalog_adoption_readiness(
        proposal_path="proposal.json",
        proposal_data=proposal,
        review_path="review.json",
        review_data=review,
        adoption_plan_path="adoption.json",
        adoption_plan_data=plan,
        source_registry_path="source.json",
        source_registry_data=source,
        proposed_registry_path="proposed.json",
        proposed_registry_data=proposed,
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_catalog_adoption_readiness.json"
    assert Path(result["md_path"]).name == "model_role_catalog_adoption_readiness.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Final Verdict" in md
    assert "MODEL.CLOSE" in md


def test_markdown_contains_required_sections():
    md = render_model_role_catalog_adoption_readiness_markdown(_readiness())
    low = md.lower()
    for section in (
        "## summary",
        "## source artifacts",
        "## proposal readiness",
        "## review readiness",
        "## adoption plan readiness",
        "## source registry safety",
        "## proposed registry safety",
        "## rollback readiness",
        "## human approval boundary",
        "## files that must not change",
        "## warnings",
        "## blocked reasons",
        "## final verdict",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(READINESS_STATUSES) == {
        "adoption_readiness_ready",
        "adoption_readiness_ready_with_warnings",
        "adoption_readiness_incomplete",
        "adoption_readiness_blocked",
    }
    assert "no automatic adoption" in BOUNDARIES
    assert "writes readiness artifacts only" in BOUNDARIES


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_catalog_adoption_readiness.py",
        root / "scripts" / "create_model_role_catalog_adoption_readiness.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_catalog_adoption_readiness.py" and top:
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


def test_registry_and_picker_recommend_model_close():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N6"]["status"] == "complete"
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
