"""Tests for EVAL.N4 - Evidence Quality Artifact Loader Plan.

EVAL.N4 is planning-only. It defines how C.A.T.T.U.S should later load and
display existing EVAL.N3 evidence quality report artifacts without adding a UI,
backend route, runtime loader, approval gate, scoring gate, validation run,
benchmark run, model call, patch application, or automatic decision.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates


VISIBLE_FIELDS = {
    "evidence_quality_status",
    "overall_evidence_quality",
    "claim_count",
    "missing_evidence_count",
    "contradiction_risk_count",
    "confidence_alignment_warnings",
    "validation_evidence_status",
    "benchmark_evidence_status",
    "freshness_status",
    "recommended_human_checks",
    "advisory_note",
}

DEBUG_FIELDS = {
    "artifact_inventory",
    "claim_inventory",
    "evidence_inventory",
    "dimension_reviews",
    "missing_evidence",
    "contradiction_risks",
    "freshness_findings",
    "confidence_alignment_findings",
    "scope_alignment_findings",
    "raw_json",
}

WARNING_LANGUAGE = {
    "Evidence Quality is advisory evidence, not an approval gate.",
    "A strong evidence report does not automatically approve a patch.",
    "A weak evidence report means review the missing evidence, not automatically reject.",
    "Validation and benchmark results are only trusted when matching artifacts exist.",
    "Human approval is still required before patch apply.",
}


def _module():
    try:
        from core import evidence_quality_artifact_loader_plan as loader_plan
    except ModuleNotFoundError as exc:
        pytest.fail(f"core.evidence_quality_artifact_loader_plan is missing: {exc}")
    return loader_plan


def _script():
    try:
        import scripts.create_evidence_quality_artifact_loader_plan as script
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.create_evidence_quality_artifact_loader_plan is missing: {exc}")
    return script


def test_plan_defines_report_only_loader_purpose_and_source_contract():
    loader_plan = _module()

    report = loader_plan.build_evidence_quality_artifact_loader_plan()

    assert report["report_kind"] == "evidence_quality_artifact_loader_plan"
    assert report["plan_id"] == "evidence-quality-artifact-loader-plan"
    assert report["plan_status"] == "evidence_quality_artifact_loader_plan_ready"
    assert "existing EVAL.N3 evidence quality reports" in report["loader_purpose"]
    assert "approval gate" in report["loader_purpose"]
    source = report["allowed_artifact_source"]
    assert source["allowed_root"] == ".agent/eval/evidence_quality_report/"
    assert source["default_latest_report_path"] == ".agent/eval/evidence_quality_report/evidence_quality_report.json"
    assert source["report_id_report_path"] == ".agent/eval/evidence_quality_report/<report_id>/evidence_quality_report.json"
    assert source["optional_report_id_later"] is True
    assert source["no_arbitrary_path_input"] is True
    assert source["path_traversal_blocked"] is True
    assert report["recommended_next_phase"]["phase_id"] == "EVAL.N5"
    assert all(value is False for value in report["guardrails"].values())


def test_future_route_plan_is_get_only_read_only_and_non_executing():
    loader_plan = _module()

    route = loader_plan.build_evidence_quality_artifact_loader_plan()["future_route_contract"]

    assert route["preferred_routes"] == [
        "GET /eval/evidence-quality/report/<report_id>",
        "GET /api/eval/evidence-quality/report/<report_id>",
    ]
    assert route["allowed_methods"] == ["GET"]
    assert route["read_only"] is True
    assert route["no_arbitrary_file_path_input"] is True
    assert route["report_id_sanitized"] is True
    assert route["path_traversal_blocked"] is True
    assert route["allowed_read_root"] == ".agent/eval/evidence_quality_report/"
    assert {"POST", "PUT", "PATCH", "DELETE"} <= set(route["forbidden_methods"])
    assert route["no_validation_execution"] is True
    assert route["no_benchmark_execution"] is True
    assert route["no_model_call"] is True
    assert route["no_patch_apply"] is True
    assert route["no_approval_or_rejection"] is True


def test_future_ui_placement_fields_and_states_are_advisory_only():
    loader_plan = _module()

    report = loader_plan.build_evidence_quality_artifact_loader_plan()
    placement = report["future_ui_placement"]

    assert {"Evidence / Review area", "Advanced / Debug drawer"} <= set(placement["allowed_placements"])
    assert "beside Apply Patch" in placement["forbidden_placements"]
    assert "beside primary Submit" in placement["forbidden_placements"]
    assert "inside run confirmation path" in placement["forbidden_placements"]
    assert "blocking status gate" in placement["forbidden_placements"]
    assert set(report["visible_fields"]) == VISIBLE_FIELDS
    assert set(report["collapsed_debug_fields"]) == DEBUG_FIELDS
    assert {
        "no_report_selected",
        "report_not_found",
        "malformed_report",
        "blocked_unsafe_report_id",
        "report_incomplete",
        "report_blocked",
        "report_ready_with_warnings",
        "report_ready",
    } <= set(report["empty_error_states"])


def test_warning_language_and_non_blocking_policy_preserve_human_boundary():
    loader_plan = _module()

    report = loader_plan.build_evidence_quality_artifact_loader_plan()
    policy = report["non_blocking_policy"]
    boundary = report["human_review_boundary"]

    assert set(report["warning_language"]) == WARNING_LANGUAGE
    assert policy["advisory_only"] is True
    assert policy["blocks_apply"] is False
    assert policy["blocks_submit"] is False
    assert policy["approves_patches"] is False
    assert policy["rejects_patches"] is False
    assert policy["changes_routing_or_mode"] is False
    assert policy["changes_scoring_gates"] is False
    assert boundary["human_approval_required_before_patch_apply"] is True
    assert boundary["report_can_replace_human_review"] is False
    assert any("missing evidence" in item for item in boundary["manual_review_required"])


def test_forbidden_loader_behavior_names_dangerous_ui_and_runtime_actions():
    loader_plan = _module()

    forbidden = set(loader_plan.build_evidence_quality_artifact_loader_plan()["forbidden_loader_behavior"])

    assert {
        "no Approve button",
        "no Reject button",
        "no Apply button inside Evidence Quality panel",
        "no Run Validation button",
        "no Run Benchmark button",
        "no Score Now button",
        "no model-call button",
        "no auto-refresh during active run",
        "no disabling Apply based on evidence quality",
        "no changing routing/mode based on evidence quality",
        "no generating a new EVAL.N3 report from the loader",
        "no mutating evidence reports",
    } <= forbidden


def test_json_and_markdown_artifacts_are_written(tmp_path):
    loader_plan = _module()

    result = loader_plan.write_evidence_quality_artifact_loader_plan(output_dir=tmp_path)

    assert result["ok"] is True
    assert Path(result["json_path"]).name == "evidence_quality_artifact_loader_plan.json"
    assert Path(result["md_path"]).name == "evidence_quality_artifact_loader_plan.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == "evidence_quality_artifact_loader_plan"
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "# Evidence Quality Artifact Loader Plan" in markdown
    assert "## Future Route Contract" in markdown
    assert "## Forbidden Loader Behavior" in markdown
    assert "EVAL.N5" in markdown


def test_cli_writes_plan_artifacts_and_summary(tmp_path):
    script = _script()

    result = script.run_create_evidence_quality_artifact_loader_plan(output_dir=str(tmp_path))

    assert result["ok"] is True
    assert result["summary"]["report_kind"] == "evidence_quality_artifact_loader_plan"
    assert result["summary"]["plan_status"] == "evidence_quality_artifact_loader_plan_ready"
    assert result["summary"]["visible_field_count"] == len(VISIBLE_FIELDS)
    assert result["summary"]["debug_field_count"] == len(DEBUG_FIELDS)
    assert result["summary"]["forbidden_behavior_count"] >= 12
    assert result["summary"]["recommended_next_phase"] == "EVAL.N5"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()


def test_markdown_contains_required_sections():
    loader_plan = _module()

    markdown = loader_plan.render_evidence_quality_artifact_loader_plan_markdown(
        loader_plan.build_evidence_quality_artifact_loader_plan()
    )

    for section in (
        "Summary",
        "Loader Purpose",
        "Allowed Artifact Source",
        "Future Route Contract",
        "Future UI Placement",
        "Visible Fields",
        "Collapsed Debug Fields",
        "Empty and Error States",
        "Warning Language",
        "Non-blocking Policy",
        "Forbidden Loader Behavior",
        "Human Review Boundary",
        "Guardrails",
        "Recommended Next Phase",
    ):
        assert f"## {section}" in markdown, section


def test_source_has_no_forbidden_imports_or_runtime_calls():
    root = Path(__file__).parent.parent
    paths = (
        root / "core" / "evidence_quality_artifact_loader_plan.py",
        root / "scripts" / "create_evidence_quality_artifact_loader_plan.py",
    )
    for path in paths:
        assert path.is_file(), path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "evidence_quality_artifact_loader_plan.py" and top:
                    assert top in {"__future__", "json", "pathlib", "typing"}, (
                        f"Unexpected import in core: {module!r}"
                    )
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
                    "mcp",
                    "docker",
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
                    "invoke_mcp",
                    "call_model",
                    "score_patch",
                    "score_evidence",
                    "load_evidence_quality_report",
                }, f"{path} calls forbidden function {name}"
        for bad_token in (
            "flask",
            "FastAPI",
            "@app.route",
            "Blueprint",
            "render_template",
            "requests.",
            "subprocess.",
        ):
            assert bad_token not in source, f"{path} contains forbidden runtime/UI token {bad_token!r}"


def test_registry_and_picker_recommend_eval_n5_after_eval_n4():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["EVAL.N1"]["status"] == "complete"
    assert phases["EVAL.N2"]["status"] == "complete"
    assert phases["EVAL.N3"]["status"] == "complete"
    assert phases["EVAL.N4"]["status"] == "complete"
    assert phases["EVAL.N4"]["prerequisites"] == ["EVAL.N3"]
    assert phases["EVAL.N4"]["title"] == "Evidence Quality Artifact Loader Plan"
    assert phases["EVAL.N5"]["status"] == "proposed"
    assert phases["EVAL.N5"]["prerequisites"] == ["EVAL.N4"]
    assert phases["EVAL.N5"]["title"] == "Evidence Quality Read-only UI Stub"

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "EVAL.N5"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
