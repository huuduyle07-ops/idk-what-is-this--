"""Tests for EVAL.N1 - Evidence Quality Planning.

EVAL.N1 is report-only and planning-only. It defines how future evidence
quality reports should judge claim support, patch relevance, validation and
benchmark relevance, freshness, contradictions, confidence alignment, scope
alignment, and human-review boundaries. It must not score a real patch, run
validation, run benchmarks, call models, apply patches, launch workers, invoke
MCP tools, contact networks, or change scoring gates.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates


REQUIRED_DIMENSIONS = [
    "claim_support",
    "patch_relevance",
    "validation_relevance",
    "benchmark_relevance",
    "missing_evidence",
    "evidence_freshness",
    "contradiction_detection",
    "confidence_alignment",
    "scope_alignment",
    "human_review_boundary",
]

PLAN_STATUSES = {
    "evidence_quality_plan_ready",
    "evidence_quality_plan_ready_with_warnings",
    "evidence_quality_plan_incomplete",
    "evidence_quality_plan_blocked",
}

FUTURE_VERDICTS = {
    "strongly_supported",
    "supported",
    "partially_supported",
    "weakly_supported",
    "unsupported",
    "contradicted",
    "missing_evidence",
    "not_applicable",
}

FUTURE_SCORE_FIELDS = {
    "claim_support_score",
    "patch_relevance_score",
    "validation_relevance_score",
    "benchmark_relevance_score",
    "contradiction_risk_score",
    "missing_evidence_score",
    "confidence_alignment_score",
    "overall_evidence_quality_score",
}


def _module():
    try:
        from core import evidence_quality_plan as eqp
    except ModuleNotFoundError as exc:
        pytest.fail(f"core.evidence_quality_plan is missing: {exc}")
    return eqp


def _script():
    try:
        import scripts.create_evidence_quality_plan as script
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.create_evidence_quality_plan is missing: {exc}")
    return script


def test_plan_defines_required_dimensions_statuses_verdicts_and_scores():
    eqp = _module()

    report = eqp.build_evidence_quality_plan()

    assert report["report_kind"] == eqp.REPORT_KIND == "evidence_quality_plan"
    assert report["plan_id"] == "evidence-quality-plan"
    assert report["plan_status"] == "evidence_quality_plan_ready"
    assert [item["dimension_id"] for item in report["evidence_dimensions"]] == REQUIRED_DIMENSIONS
    assert set(report["evidence_quality_plan_statuses"]) == PLAN_STATUSES
    assert set(report["future_verdicts"]) == FUTURE_VERDICTS
    assert set(report["future_score_fields"]) == FUTURE_SCORE_FIELDS
    assert report["recommended_next_phase"]["phase_id"] == "EVAL.N2"
    assert all(value is False for value in report["guardrails"].values())


def test_plan_records_supported_artifact_inputs_and_rule_sections():
    eqp = _module()

    report = eqp.build_evidence_quality_plan()

    assert {
        "patch proposal JSON",
        "diff file",
        "validation result JSON/text",
        "benchmark result JSON/text",
        "replay comparison artifact",
        "Mirror Tunnel trace/scoring preview",
        "Commander review pack",
        "final answer text",
        "evidence pack artifact",
        "roadmap/phase registry artifact",
    } <= set(report["supported_artifact_types"])
    assert any("pre_patch" in rule for rule in report["evidence_freshness_rules"])
    assert any("final answer claims must not imply validation passed" in rule for rule in report["claim_vs_evidence_rules"])
    assert any("changed files" in rule for rule in report["validation_benchmark_relevance_rules"])
    assert any("patch exists but no validation result exists" in rule for rule in report["missing_evidence_rules"])
    assert any("safe" in rule and "verified" in rule for rule in report["confidence_alignment_rules"])
    assert any("human review" in item.lower() for item in report["human_review_boundary"])
    assert "planning only" in report["integration_boundaries"]


def test_json_and_markdown_artifacts_are_written(tmp_path):
    eqp = _module()

    result = eqp.write_evidence_quality_plan(output_dir=tmp_path)

    assert result["ok"] is True
    assert Path(result["json_path"]).name == "evidence_quality_plan.json"
    assert Path(result["md_path"]).name == "evidence_quality_plan.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == "evidence_quality_plan"
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "## Evidence Dimensions" in markdown
    assert "EVAL.N2" in markdown


def test_markdown_contains_required_sections():
    eqp = _module()

    markdown = eqp.render_evidence_quality_plan_markdown(eqp.build_evidence_quality_plan())
    for section in (
        "Summary",
        "Evidence Quality Purpose",
        "Evidence Dimensions",
        "Supported Artifact Types",
        "Future Verdicts",
        "Future Score Fields",
        "Evidence Freshness Rules",
        "Claim-vs-Evidence Rules",
        "Validation/Benchmark Relevance Rules",
        "Missing Evidence Rules",
        "Confidence Alignment Rules",
        "Human Review Boundary",
        "Integration Boundaries",
        "Guardrails",
        "Recommended Next Phase",
    ):
        assert f"## {section}" in markdown, section


def test_cli_writes_plan_artifacts_and_summary(tmp_path):
    script = _script()

    result = script.run_create_evidence_quality_plan(output_dir=str(tmp_path))

    assert result["ok"] is True
    assert result["summary"]["report_kind"] == "evidence_quality_plan"
    assert result["summary"]["plan_status"] == "evidence_quality_plan_ready"
    assert result["summary"]["dimension_count"] == len(REQUIRED_DIMENSIONS)
    assert result["summary"]["recommended_next_phase"] == "EVAL.N2"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()


def test_source_has_no_forbidden_imports_or_execution_calls():
    root = Path(__file__).parent.parent
    paths = (
        root / "core" / "evidence_quality_plan.py",
        root / "scripts" / "create_evidence_quality_plan.py",
    )
    for path in paths:
        assert path.is_file(), path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path.name == "evidence_quality_plan.py" and top:
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
                    "invoke_mcp",
                    "call_model",
                    "score_patch",
                    "score_evidence",
                }, f"{path} calls forbidden function {name}"


def test_registry_and_picker_recommend_eval_n2_after_eval_n1():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["MODEL.CLOSE"]["status"] == "complete"
    assert phases["EVAL.N1"]["status"] == "complete"
    assert phases["EVAL.N1"]["prerequisites"] == ["MODEL.CLOSE"]
    assert phases["EVAL.N2"]["status"] == "proposed"
    assert phases["EVAL.N2"]["prerequisites"] == ["EVAL.N1"]
    assert phases["EVAL.N2"]["title"] == "Evidence Quality Report Contract"

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "EVAL.N2"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
