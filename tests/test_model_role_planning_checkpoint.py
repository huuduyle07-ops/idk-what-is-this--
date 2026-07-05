"""Tests for MODEL.CLOSE - Model Role Planning Checkpoint."""
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
from core.model_role_catalog_adoption_readiness import build_model_role_catalog_adoption_readiness
from core.phase_picker import pick_phase_candidates
from core.model_role_planning_checkpoint import (
    BOUNDARIES,
    CHECKPOINT_STATUSES,
    REPORT_KIND,
    build_model_role_planning_checkpoint,
    render_model_role_planning_checkpoint_markdown,
    write_model_role_planning_checkpoint,
)
import scripts.create_model_role_planning_checkpoint as script


_ROOT = Path(__file__).parent.parent


def _phase_registry() -> dict:
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    phases["MODEL.CLOSE"]["status"] = "complete"
    if "EVAL.N1" not in phases:
        data["phases"].append(
            {
                "phase_id": "EVAL.N1",
                "title": "Evidence Quality Planning",
                "track": "EVAL",
                "status": "complete",
                "summary": "Report-only evidence quality planning artifact.",
                "automation_level": "LOCAL_0_OBSERVE",
                "budget_tier": "local_only",
                "risk_level": "low",
                "allowed_files": ["core/evidence_quality_plan.py", "tests/test_evidence_quality_plan.py"],
                "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
                "validation": ["python -m pytest tests/test_evidence_quality_plan.py -q"],
                "human_approval_required": True,
                "merge_allowed": False,
                "network_allowed": False,
                "model_calls_allowed": False,
                "writes_real_repo": False,
                "requires_sandbox": False,
                "prerequisites": ["MODEL.CLOSE"],
                "expected_artifacts": [".agent/eval/evidence_quality_plan/evidence_quality_plan.json"],
                "notes": ["Report-only evidence quality planning phase."],
            }
        )
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    if "EVAL.N2" not in phases:
        data["phases"].append(
            {
                "phase_id": "EVAL.N2",
                "title": "Evidence Quality Report Contract",
                "track": "EVAL",
                "status": "complete",
                "summary": "Report-only contract for applying the EVAL.N1 evidence quality plan to existing artifacts.",
                "automation_level": "LOCAL_0_OBSERVE",
                "budget_tier": "local_only",
                "risk_level": "low",
                "allowed_files": ["core/evidence_quality_report_contract.py", "tests/test_evidence_quality_report_contract.py"],
                "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
                "validation": ["python -m pytest tests/test_evidence_quality_report_contract.py -q"],
                "human_approval_required": True,
                "merge_allowed": False,
                "network_allowed": False,
                "model_calls_allowed": False,
                "writes_real_repo": False,
                "requires_sandbox": False,
                "prerequisites": ["EVAL.N1"],
                "expected_artifacts": [".agent/eval/evidence_quality_report_contract/evidence_quality_report_contract.json"],
                "notes": ["Report-only evidence quality report contract phase."],
            }
        )
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    if "EVAL.N3" not in phases:
        data["phases"].append(
            {
                "phase_id": "EVAL.N3",
                "title": "Evidence Quality Report Builder",
                "track": "EVAL",
                "status": "complete",
                "summary": "Report-only builder for an actual evidence quality report from existing run/evidence artifacts.",
                "automation_level": "LOCAL_0_OBSERVE",
                "budget_tier": "local_only",
                "risk_level": "low",
                "allowed_files": ["core/evidence_quality_report_builder.py", "tests/test_evidence_quality_report_builder.py"],
                "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
                "validation": ["python -m pytest tests/test_evidence_quality_report_builder.py -q"],
                "human_approval_required": True,
                "merge_allowed": False,
                "network_allowed": False,
                "model_calls_allowed": False,
                "writes_real_repo": False,
                "requires_sandbox": False,
                "prerequisites": ["EVAL.N2"],
                "expected_artifacts": [".agent/eval/evidence_quality_report/evidence_quality_report.json"],
                "notes": ["Proposed evidence quality report builder phase."],
            }
        )
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    if "EVAL.N4" not in phases:
        data["phases"].append(
            {
                "phase_id": "EVAL.N4",
                "title": "Evidence Quality Artifact Loader Plan",
                "track": "EVAL",
                "status": "proposed",
                "summary": "Report-only artifact loader plan for existing evidence quality reports.",
                "automation_level": "LOCAL_0_OBSERVE",
                "budget_tier": "local_only",
                "risk_level": "low",
                "allowed_files": ["core/evidence_quality_artifact_loader_plan.py", "tests/test_evidence_quality_artifact_loader_plan.py"],
                "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
                "validation": ["python -m pytest tests/test_evidence_quality_artifact_loader_plan.py -q"],
                "human_approval_required": True,
                "merge_allowed": False,
                "network_allowed": False,
                "model_calls_allowed": False,
                "writes_real_repo": False,
                "requires_sandbox": False,
                "prerequisites": ["EVAL.N3"],
                "expected_artifacts": [".agent/eval/evidence_quality_artifact_loader_plan/evidence_quality_artifact_loader_plan.json"],
                "notes": ["Proposed evidence quality artifact loader planning phase."],
            }
        )
    return data


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


def _chain() -> tuple[dict, dict, dict, dict, dict, dict, dict]:
    source_registry = _registry()
    coverage = _coverage(source_registry)
    gap_plan = build_model_role_gap_plan(
        coverage_path="model_role_coverage_report.json",
        coverage_data=coverage,
        model_registry_path="model_role_registry.json",
        model_registry_data=source_registry,
    )
    proposal = build_model_role_catalog_update_proposal(
        gap_plan_path="model_role_gap_plan.json",
        gap_plan_data=gap_plan,
        model_registry_path="model_role_registry.json",
        model_registry_data=source_registry,
    )
    proposed_registry = copy.deepcopy(proposal["proposed_registry"])
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
    readiness = build_model_role_catalog_adoption_readiness(
        proposal_path="model_role_catalog_update_proposal.json",
        proposal_data=proposal,
        review_path="model_role_catalog_proposal_review.json",
        review_data=review,
        adoption_plan_path="model_role_catalog_adoption_plan.json",
        adoption_plan_data=adoption_plan,
        source_registry_path="model_role_registry.json",
        source_registry_data=source_registry,
        proposed_registry_path="proposed_model_role_registry.json",
        proposed_registry_data=proposed_registry,
    )
    return source_registry, coverage, gap_plan, proposal, proposed_registry, review, adoption_plan, readiness


def _checkpoint(
    phase_registry: dict | None = None,
    model_registry: dict | None = None,
    coverage: dict | None = None,
    gap_plan: dict | None = None,
    proposal: dict | None = None,
    proposed_registry: dict | None = None,
    review: dict | None = None,
    adoption_plan: dict | None = None,
    adoption_readiness: dict | None = None,
    **overrides,
) -> dict:
    base_model, base_coverage, base_gap, base_proposal, base_proposed, base_review, base_plan, base_ready = _chain()
    kwargs = {
        "phase_registry_path": "phase_registry.json",
        "phase_registry_data": _phase_registry() if phase_registry is None else phase_registry,
        "model_registry_path": "model_role_registry.json",
        "model_registry_data": base_model if model_registry is None else model_registry,
        "coverage_report_path": "model_role_coverage_report.json",
        "coverage_report_data": base_coverage if coverage is None else coverage,
        "gap_plan_path": "model_role_gap_plan.json",
        "gap_plan_data": base_gap if gap_plan is None else gap_plan,
        "proposal_path": "model_role_catalog_update_proposal.json",
        "proposal_data": base_proposal if proposal is None else proposal,
        "proposed_registry_path": "proposed_model_role_registry.json",
        "proposed_registry_data": base_proposed if proposed_registry is None else proposed_registry,
        "review_path": "model_role_catalog_proposal_review.json",
        "review_data": base_review if review is None else review,
        "adoption_plan_path": "model_role_catalog_adoption_plan.json",
        "adoption_plan_data": base_plan if adoption_plan is None else adoption_plan,
        "adoption_readiness_path": "model_role_catalog_adoption_readiness.json",
        "adoption_readiness_data": base_ready if adoption_readiness is None else adoption_readiness,
    }
    kwargs.update(overrides)
    return build_model_role_planning_checkpoint(**kwargs)


def _role_by_id(roles: list[dict], role_id: str) -> dict:
    return next(role for role in roles if role.get("role_id") == role_id)


def test_complete_model_branch_produces_checkpoint():
    report = _checkpoint()
    assert report["report_kind"] == REPORT_KIND == "model_role_planning_checkpoint"
    assert report["checkpoint_id"] == "model-role-planning-checkpoint"
    assert report["checkpoint_status"] == "model_role_planning_frozen_with_adoption_ready_warnings"
    assert report["phase_completion"]["all_model_phases_complete"] is True
    assert report["artifact_coverage"]["all_required_artifacts_present"] is True
    assert report["active_registry_status"]["active_role_count"] == 7
    assert report["proposed_registry_status"]["proposed_role_count"] == 10
    assert report["proposed_registry_status"]["proposed_catalog_adopted"] is False
    assert report["blocked_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "EVAL.N1"
    assert all(value is False for value in report["guardrails"].values())


def test_warning_ready_chain_freezes_with_adoption_ready_warnings():
    report = _checkpoint()
    assert report["checkpoint_status"] == "model_role_planning_frozen_with_adoption_ready_warnings"
    assert any("proposed catalog has not been adopted" in warning for warning in report["warnings"])
    assert any("adoption readiness warning" in warning for warning in report["warnings"])


def test_missing_model_n7_phase_blocks_or_incompletes():
    phase_registry = _phase_registry()
    phase_registry["phases"] = [phase for phase in phase_registry["phases"] if phase["phase_id"] != "MODEL.N7"]
    report = _checkpoint(phase_registry=phase_registry)
    assert report["checkpoint_status"] in {
        "model_role_planning_blocked",
        "model_role_planning_incomplete",
    }
    assert any("MODEL.N7" in reason for reason in report["blocked_reasons"] + report["incomplete_reasons"])


def test_missing_required_artifacts_block_or_incomplete():
    for label, override in (
        ("proposed registry", {"proposed_registry_data": None, "proposed_registry_path": ""}),
        ("adoption readiness", {"adoption_readiness_data": None, "adoption_readiness_path": ""}),
    ):
        report = _checkpoint(**override)
        assert report["checkpoint_status"] in {
            "model_role_planning_blocked",
            "model_role_planning_incomplete",
        }, label
        assert any(label in reason for reason in report["blocked_reasons"] + report["incomplete_reasons"])


def test_missing_active_registry_blocks():
    report = _checkpoint(model_registry=None, model_registry_path="", model_registry_data=None)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("active registry" in reason or "model registry" in reason for reason in report["blocked_reasons"])


def test_active_registry_mutation_marker_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    proposal["guardrails"]["model_n1_registry_artifact_mutated"] = True
    report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("mutated" in reason or "guardrail" in reason for reason in report["blocked_reasons"])


def test_proposed_registry_replacing_active_registry_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    active = copy.deepcopy(proposed)
    active["report_kind"] = "model_role_registry"
    active["validation_status"] = "model_roles_ready"
    report = _checkpoint(_phase_registry(), active, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("active registry" in reason and "proposed" in reason for reason in report["blocked_reasons"])


def test_executable_binding_allowed_true_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    _role_by_id(proposed["roles"], "ui_reviewer")["executable_binding_allowed"] = True
    report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("executable_binding_allowed" in reason for reason in report["blocked_reasons"])


def test_advisory_only_false_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    _role_by_id(proposed["roles"], "ui_reviewer")["advisory_only"] = False
    report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("advisory_only" in reason for reason in report["blocked_reasons"])


def test_forbidden_authority_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge", "route_tasks", "launch_worker"):
        model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
        _role_by_id(proposed["roles"], "ui_reviewer")[flag] = True
        report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
        assert report["checkpoint_status"] == "model_role_planning_blocked", flag
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_model_ids_authority_claim_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    role = _role_by_id(proposed["roles"], "ui_reviewer")
    role["model_ids"] = ["gpt-example"]
    role["model_id_policy"] = "routing_authority"
    report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("model_id_policy" in reason or "model_ids" in reason for reason in report["blocked_reasons"])


def test_missing_separate_adoption_boundary_blocks():
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    ready["human_approval_readiness"]["separate_adoption_phase_required"] = False
    plan["human_approval_checklist"] = ["human reviewed proposed registry"]
    report = _checkpoint(_phase_registry(), model, coverage, gap, proposal, proposed, review, plan, ready)
    assert report["checkpoint_status"] == "model_role_planning_blocked"
    assert any("separate" in reason and "adoption" in reason for reason in report["blocked_reasons"])


def test_unsafe_paths_block_cli(tmp_path):
    result = script.run_create_model_role_planning_checkpoint(
        phase_registry="../phase_registry.json",
        model_registry="../model_role_registry.json",
        coverage_report="../model_role_coverage_report.json",
        gap_plan="../model_role_gap_plan.json",
        proposal="../proposal.json",
        proposed_registry="../proposed.json",
        review="../review.json",
        adoption_plan="../plan.json",
        adoption_readiness="../ready.json",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["checkpoint_status"] == "model_role_planning_blocked"
    assert any("path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_artifacts_block_cli(tmp_path):
    paths = {}
    for name in ("registry", "model", "coverage", "gap", "proposal", "proposed", "review", "plan", "ready"):
        path = tmp_path / f"{name}.json"
        path.write_text("{bad-json", encoding="utf-8")
        paths[name] = path
    result = script.run_create_model_role_planning_checkpoint(
        phase_registry=str(paths["registry"]),
        model_registry=str(paths["model"]),
        coverage_report=str(paths["coverage"]),
        gap_plan=str(paths["gap"]),
        proposal=str(paths["proposal"]),
        proposed_registry=str(paths["proposed"]),
        review=str(paths["review"]),
        adoption_plan=str(paths["plan"]),
        adoption_readiness=str(paths["ready"]),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["checkpoint_status"] == "model_role_planning_blocked"
    assert sum("valid JSON" in reason for reason in result["report"]["blocked_reasons"]) >= 9


def test_source_and_proposed_artifacts_are_not_mutated():
    chain = _chain()
    registry = _phase_registry()
    before = copy.deepcopy((registry, chain))
    _checkpoint(registry, *chain)
    assert (registry, chain) == before


def test_json_and_markdown_checkpoint_artifacts_are_written(tmp_path):
    model, coverage, gap, proposal, proposed, review, plan, ready = _chain()
    result = write_model_role_planning_checkpoint(
        phase_registry_path="phase_registry.json",
        phase_registry_data=_phase_registry(),
        model_registry_path="model.json",
        model_registry_data=model,
        coverage_report_path="coverage.json",
        coverage_report_data=coverage,
        gap_plan_path="gap.json",
        gap_plan_data=gap,
        proposal_path="proposal.json",
        proposal_data=proposal,
        proposed_registry_path="proposed.json",
        proposed_registry_data=proposed,
        review_path="review.json",
        review_data=review,
        adoption_plan_path="plan.json",
        adoption_plan_data=plan,
        adoption_readiness_path="ready.json",
        adoption_readiness_data=ready,
        output_dir=tmp_path,
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "model_role_planning_checkpoint.json"
    assert Path(result["md_path"]).name == "model_role_planning_checkpoint.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Final Verdict" in md
    assert "EVAL.N1" in md


def test_markdown_contains_required_sections():
    md = render_model_role_planning_checkpoint_markdown(_checkpoint())
    low = md.lower()
    for section in (
        "## summary",
        "## phase completion",
        "## artifact coverage",
        "## active registry status",
        "## proposed registry status",
        "## coverage / gap / proposal / review / adoption chain",
        "## safety boundary verification",
        "## forbidden authority checks",
        "## human approval and rollback boundary",
        "## warnings",
        "## blocked reasons",
        "## final verdict",
        "## recommended next phase",
        "## boundaries / guardrails",
    ):
        assert section in low, section


def test_constants_match_contract():
    assert set(CHECKPOINT_STATUSES) == {
        "model_role_planning_frozen",
        "model_role_planning_frozen_with_adoption_ready_warnings",
        "model_role_planning_incomplete",
        "model_role_planning_blocked",
    }
    assert "no automatic adoption" in BOUNDARIES
    assert "writes checkpoint artifacts only" in BOUNDARIES


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
    root = Path(__file__).parent.parent
    for path in (
        root / "core" / "model_role_planning_checkpoint.py",
        root / "scripts" / "create_model_role_planning_checkpoint.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "model_role_planning_checkpoint.py" and top:
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


def test_registry_and_picker_recommend_eval_n1():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MODEL.N7"]["status"] == "complete"
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
