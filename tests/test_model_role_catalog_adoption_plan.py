"""Tests for MODEL.N6 - Model Role Catalog Adoption Plan."""
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
from core.phase_picker import pick_phase_candidates
from core.model_role_catalog_adoption_plan import (
    ADOPTION_PLAN_STATUSES,
    BOUNDARIES,
    REPORT_KIND,
    build_model_role_catalog_adoption_plan,
    render_model_role_catalog_adoption_plan_markdown,
    write_model_role_catalog_adoption_plan,
)
import scripts.create_model_role_catalog_adoption_plan as script


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


def _review_bundle() -> tuple[dict, dict, dict]:
    proposal, proposed_registry, source_registry = _proposal_bundle()
    review = build_model_role_catalog_proposal_review(
        proposal_path="model_role_catalog_update_proposal.json",
        proposal_data=proposal,
        proposed_registry_path="proposed_model_role_registry.json",
        proposed_registry_data=proposed_registry,
        source_registry_path="model_role_registry.json",
        source_registry_data=source_registry,
    )
    return review, source_registry, proposed_registry


def _plan(
    review: dict | None = None,
    source_registry: dict | None = None,
    proposed_registry: dict | None = None,
    **overrides,
) -> dict:
    base_review, base_source, base_proposed = _review_bundle()
    kwargs = {
        "review_path": "model_role_catalog_proposal_review.json",
        "review_data": base_review if review is None else review,
        "source_registry_path": "model_role_registry.json",
        "source_registry_data": base_source if source_registry is None else source_registry,
        "proposed_registry_path": "proposed_model_role_registry.json",
        "proposed_registry_data": base_proposed if proposed_registry is None else proposed_registry,
    }
    kwargs.update(overrides)
    return build_model_role_catalog_adoption_plan(**kwargs)


def _role_by_id(roles: list[dict], role_id: str) -> dict:
    return next(role for role in roles if role.get("role_id") == role_id)


def test_valid_model_n5_review_and_registries_produce_adoption_plan():
    plan = _plan()
    assert plan["report_kind"] == REPORT_KIND == "model_role_catalog_adoption_plan"
    assert plan["plan_id"] == "model-role-catalog-adoption-plan"
    assert plan["adoption_plan_status"] == "adoption_plan_ready_with_warnings"
    assert plan["current_role_count"] == 7
    assert plan["proposed_role_count"] == 10
    assert {role["role_id"] for role in plan["proposed_new_roles"]} == {
        "ui_reviewer",
        "test_designer",
        "documentation_reviewer",
    }
    assert plan["blocked_reasons"] == []
    assert plan["recommended_next_phase"]["phase_id"] == "MODEL.N7"
    assert all(value is False for value in plan["guardrails"].values())


def test_ready_with_warnings_review_produces_ready_with_warnings_plan():
    plan = _plan()
    assert plan["source_review"]["review_status"] == "catalog_proposal_review_ready_with_warnings"
    assert plan["adoption_plan_status"] == "adoption_plan_ready_with_warnings"
    assert any("review status is catalog_proposal_review_ready_with_warnings" in item for item in plan["warnings"])


def test_review_with_blockers_blocks_adoption_plan():
    review, source, proposed = _review_bundle()
    review["review_status"] = "catalog_proposal_review_blocked"
    review["blocked_reasons"] = ["unsafe proposed registry"]
    plan = _plan(review, source, proposed)
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("review blocker" in reason for reason in plan["blocked_reasons"])


def test_missing_proposed_registry_blocks():
    review, source, _proposed = _review_bundle()
    plan = _plan(
        review=review,
        source_registry=source,
        proposed_registry=None,
        proposed_registry_path="",
        proposed_registry_data=None,
    )
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("proposed registry is missing" in reason for reason in plan["blocked_reasons"])


def test_proposed_registry_dropping_source_role_blocks():
    review, source, proposed = _review_bundle()
    proposed["roles"] = [role for role in proposed["roles"] if role.get("role_id") != "planner"]
    proposed["role_count"] = len(proposed["roles"])
    plan = _plan(review, source, proposed)
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("source role dropped" in reason for reason in plan["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    review, source, proposed = _review_bundle()
    _role_by_id(proposed["roles"], "ui_reviewer")["executable_binding_allowed"] = True
    plan = _plan(review, source, proposed)
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("executable_binding_allowed" in reason for reason in plan["blocked_reasons"])


def test_advisory_only_false_blocks():
    review, source, proposed = _review_bundle()
    _role_by_id(proposed["roles"], "ui_reviewer")["advisory_only"] = False
    plan = _plan(review, source, proposed)
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("advisory_only" in reason for reason in plan["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "route_tasks", "launch_worker"):
        review, source, proposed = _review_bundle()
        _role_by_id(proposed["roles"], "ui_reviewer")[flag] = True
        plan = _plan(review, source, proposed)
        assert plan["adoption_plan_status"] == "adoption_plan_blocked", flag
        assert any(flag in reason for reason in plan["blocked_reasons"])


def test_model_ids_authority_claim_blocks():
    review, source, proposed = _review_bundle()
    role = _role_by_id(proposed["roles"], "ui_reviewer")
    role["model_ids"] = ["gpt-example"]
    role["model_id_policy"] = "routing_authority"
    plan = _plan(review, source, proposed)
    assert plan["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("model_id_policy" in reason or "model_ids" in reason for reason in plan["blocked_reasons"])


def test_unsafe_review_source_and_proposed_paths_block(tmp_path):
    result = script.run_create_model_role_catalog_adoption_plan(
        review="../model_role_catalog_proposal_review.json",
        source_registry="../model_role_registry.json",
        proposed_registry="../proposed_model_role_registry.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_review_blocks(tmp_path):
    review_path = tmp_path / "bad-review.json"
    review_path.write_text("{bad-json", encoding="utf-8")
    source_path = tmp_path / "source.json"
    proposed_path = tmp_path / "proposed.json"
    _review, source, proposed = _review_bundle()
    source_path.write_text(json.dumps(source, indent=2), encoding="utf-8")
    proposed_path.write_text(json.dumps(proposed, indent=2), encoding="utf-8")
    result = script.run_create_model_role_catalog_adoption_plan(
        review=str(review_path),
        source_registry=str(source_path),
        proposed_registry=str(proposed_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["adoption_plan_status"] == "adoption_plan_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_registries_block(tmp_path):
    review, _source, _proposed = _review_bundle()
    review_path = tmp_path / "review.json"
    source_path = tmp_path / "bad-source.json"
    proposed_path = tmp_path / "bad-proposed.json"
    review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    source_path.write_text("{bad-json", encoding="utf-8")
    proposed_path.write_text("{bad-json", encoding="utf-8")
    result = script.run_create_model_role_catalog_adoption_plan(
        review=str(review_path),
        source_registry=str(source_path),
        proposed_registry=str(proposed_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["adoption_plan_status"] == "adoption_plan_blocked"
    assert sum("valid JSON" in reason for reason in result["report"]["blocked_reasons"]) >= 2


def test_source_and_proposed_registries_are_not_mutated():
    review, source, proposed = _review_bundle()
    before = copy.deepcopy((review, source, proposed))
    _plan(review, source, proposed)
    assert (review, source, proposed) == before


def test_adoption_steps_and_rollback_plan_are_present():
    plan = _plan()
    assert len(plan["adoption_steps"]) >= 11
    assert any("Re-run MODEL.N1 validation" in step["action"] for step in plan["adoption_steps"])
    assert any("Re-run MODEL.N2 coverage" in step["action"] for step in plan["adoption_steps"])
    rollback = plan["rollback_plan"]
    assert rollback["preserve_current_registry_artifact_path"] == ".agent/model_role_registry/model_role_registry.json"
    assert rollback["never_roll_forward_automatically_after_failed_validation"] is True
    assert rollback["human_confirmation_required_before_retry"] is True


def test_files_and_human_checklist_include_boundaries():
    plan = _plan()
    assert ".agent/model_role_registry/model_role_registry.json" in plan["files_that_would_change"]
    assert ".agent/model_role_registry/model_role_registry.json" in plan["files_that_must_not_change"]
    assert ".agent/model_role_registry/model_role_registry.md" in plan["files_that_must_not_change"]
    assert any("separate explicit phase" in item for item in plan["human_approval_checklist"])


def test_json_and_markdown_adoption_artifacts_are_written(tmp_path):
    review, source, proposed = _review_bundle()
    result = write_model_role_catalog_adoption_plan(
        review_path="review.json",
        review_data=review,
        source_registry_path="source.json",
        source_registry_data=source,
        proposed_registry_path="proposed.json",
        proposed_registry_data=proposed,
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_catalog_adoption_plan.json"
    assert Path(result["md_path"]).name == "model_role_catalog_adoption_plan.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Rollback Plan" in md
    assert "MODEL.N7" in md


def test_markdown_contains_required_sections():
    md = render_model_role_catalog_adoption_plan_markdown(_plan())
    low = md.lower()
    for section in (
        "## summary",
        "## source review",
        "## source registry",
        "## proposed registry",
        "## adoption plan",
        "## rollback plan",
        "## files that would change later",
        "## files that must not change now",
        "## human approval checklist",
        "## safety checks",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(ADOPTION_PLAN_STATUSES) == {
        "adoption_plan_ready",
        "adoption_plan_ready_with_warnings",
        "adoption_plan_incomplete",
        "adoption_plan_blocked",
    }
    assert "no automatic adoption" in BOUNDARIES
    assert "writes adoption plan artifacts only" in BOUNDARIES


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_catalog_adoption_plan.py",
        root / "scripts" / "create_model_role_catalog_adoption_plan.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_catalog_adoption_plan.py" and top:
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


def test_registry_and_picker_recommend_model_n7():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N5"]["status"] == "complete"
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
    assert pick["top_recommendation"]["phase_id"] == "HARDEN.CLOSE"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
