"""Tests for EVAL.N2 - Evidence Quality Report Contract.

EVAL.N2 inspects explicitly supplied artifacts and builds an advisory evidence
quality report contract. It must not run tests, benchmarks, models, subprocesses,
patch application, MCP tools, workers, network calls, databases, scoring gates, or
approval/rejection logic.
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

REPORT_STATUSES = {
    "evidence_quality_report_ready",
    "evidence_quality_report_ready_with_warnings",
    "evidence_quality_report_incomplete",
    "evidence_quality_report_blocked",
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


def _module():
    try:
        from core import evidence_quality_report_contract as eqr
    except ModuleNotFoundError as exc:
        pytest.fail(f"core.evidence_quality_report_contract is missing: {exc}")
    return eqr


def _script():
    try:
        import scripts.create_evidence_quality_report_contract as script
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.create_evidence_quality_report_contract is missing: {exc}")
    return script


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _warning_ids(report: dict) -> set[str]:
    return {str(item.get("warning_id", "")) for item in report.get("warnings", [])}


def _blocked_ids(report: dict) -> set[str]:
    return {str(item.get("reason_id", "")) for item in report.get("blocked_reasons", [])}


def _missing_ids(report: dict) -> set[str]:
    return {str(item.get("missing_id", "")) for item in report.get("missing_evidence", [])}


def _claim_types(report: dict) -> set[str]:
    return {str(item.get("claim_type", "")) for item in report.get("claim_inventory", [])}


def test_no_artifacts_produces_incomplete_report_not_crash(tmp_path):
    eqr = _module()

    report = eqr.build_evidence_quality_report_contract(repo_root=tmp_path)

    assert report["report_kind"] == "evidence_quality_report_contract"
    assert report["report_id"] == "evidence-quality-report-contract"
    assert report["evidence_quality_status"] == "evidence_quality_report_incomplete"
    assert set(report["report_statuses"]) == REPORT_STATUSES
    assert [item["dimension_id"] for item in report["dimension_reviews"]] == REQUIRED_DIMENSIONS
    assert set(report["future_verdicts"]) == FUTURE_VERDICTS
    assert report["source_artifacts"] == []
    assert _warning_ids(report) >= {"no_meaningful_evidence_artifacts", "unknown_freshness"}
    assert report["blocked_reasons"] == []
    assert report["recommended_next_phase"]["phase_id"] == "EVAL.N3"
    assert report["human_review_boundary"]["advisory_only"] is True
    assert report["human_review_boundary"]["approved"] is False
    assert all(value is False for value in report["guardrails"].values())


def test_final_answer_claim_without_validation_artifact_warns_missing_evidence(tmp_path):
    eqr = _module()
    final_answer = _write(
        tmp_path / "final-answer.txt",
        "The fix is complete, verified, safe, and ready. Tests passed with no warnings.",
    )

    report = eqr.build_evidence_quality_report_contract(
        final_answer=final_answer,
        repo_root=tmp_path,
    )

    assert report["evidence_quality_status"] == "evidence_quality_report_ready_with_warnings"
    assert {"complete", "verified", "safe", "ready", "tests_passed", "no_warnings"} <= _claim_types(report)
    assert "missing_validation_for_validation_claim" in _missing_ids(report)
    assert "confidence_overstated" in _warning_ids(report)
    confidence = report["confidence_alignment_findings"]
    assert any(item["finding_id"] == "confidence_overstated" and item["severity"] == "high" for item in confidence)


def test_validation_claim_with_validation_artifact_is_recognized(tmp_path):
    eqr = _module()
    final_answer = _write(tmp_path / "answer.txt", "Validation passed and the change is ready.")
    validation = _write(tmp_path / "validation.txt", "2026-07-05T08:05:00+09:00 validation passed: 12 passed")

    report = eqr.build_evidence_quality_report_contract(
        final_answer=final_answer,
        validation=validation,
        repo_root=tmp_path,
    )

    assert report["evidence_quality_status"] == "evidence_quality_report_ready_with_warnings"
    assert "validation_passed" in _claim_types(report)
    assert "missing_validation_for_validation_claim" not in _missing_ids(report)
    validation_evidence = [item for item in report["evidence_inventory"] if item["artifact_key"] == "validation"]
    assert validation_evidence and validation_evidence[0]["evidence_status"] == "present"
    review = {item["dimension_id"]: item for item in report["dimension_reviews"]}
    assert review["validation_relevance"]["verdict"] in {"supported", "partially_supported"}


def test_benchmark_claim_with_benchmark_artifact_is_recognized(tmp_path):
    eqr = _module()
    final_answer = _write(tmp_path / "answer.txt", "Benchmark passed for the affected case.")
    benchmark = _write(tmp_path / "benchmark.txt", "2026-07-05T08:10:00+09:00 benchmark passed: case alpha")

    report = eqr.build_evidence_quality_report_contract(
        final_answer=final_answer,
        benchmark=benchmark,
        repo_root=tmp_path,
    )

    assert "benchmark_passed" in _claim_types(report)
    assert "missing_benchmark_for_benchmark_claim" not in _missing_ids(report)
    benchmark_evidence = [item for item in report["evidence_inventory"] if item["artifact_key"] == "benchmark"]
    assert benchmark_evidence and benchmark_evidence[0]["evidence_status"] == "present"
    review = {item["dimension_id"]: item for item in report["dimension_reviews"]}
    assert review["benchmark_relevance"]["verdict"] in {"supported", "partially_supported"}


def test_timed_out_or_not_counted_language_reduces_overclaim_severity(tmp_path):
    eqr = _module()
    final_answer = _write(
        tmp_path / "answer.txt",
        "The change is complete, but full pytest timed out and was not counted as passing.",
    )

    report = eqr.build_evidence_quality_report_contract(
        final_answer=final_answer,
        repo_root=tmp_path,
    )

    confidence = report["confidence_alignment_findings"]
    assert any(item["finding_id"] == "confidence_overstated" and item["severity"] == "low" for item in confidence)
    assert "confidence_overstated_caveated" in _warning_ids(report)


def test_unsafe_path_blocks_without_reading_outside_repo(tmp_path):
    eqr = _module()
    outside = _write(tmp_path.parent / "outside-final-answer.txt", "Validation passed.")

    report = eqr.build_evidence_quality_report_contract(
        final_answer=outside,
        repo_root=tmp_path,
    )

    assert report["evidence_quality_status"] == "evidence_quality_report_blocked"
    assert "unsafe_source_path" in _blocked_ids(report)
    assert report["claim_inventory"] == []


def test_env_or_secret_path_blocks(tmp_path):
    eqr = _module()
    env_path = _write(tmp_path / ".env", "SECRET_TOKEN=abc")
    secret_path = _write(tmp_path / "secrets" / "validation.txt", "validation passed")

    env_report = eqr.build_evidence_quality_report_contract(final_answer=env_path, repo_root=tmp_path)
    secret_report = eqr.build_evidence_quality_report_contract(validation=secret_path, repo_root=tmp_path)

    assert env_report["evidence_quality_status"] == "evidence_quality_report_blocked"
    assert "forbidden_source_path" in _blocked_ids(env_report)
    assert secret_report["evidence_quality_status"] == "evidence_quality_report_blocked"
    assert "forbidden_source_path" in _blocked_ids(secret_report)


def test_malformed_json_artifact_blocks_safely(tmp_path):
    eqr = _module()
    mirror_preview = _write(tmp_path / "mirror-preview.json", "{not valid json")

    report = eqr.build_evidence_quality_report_contract(
        mirror_preview=mirror_preview,
        repo_root=tmp_path,
    )

    assert report["evidence_quality_status"] == "evidence_quality_report_blocked"
    assert "malformed_json_artifact" in _blocked_ids(report)
    inventory = {item["artifact_key"]: item for item in report["artifact_inventory"]}
    assert inventory["mirror_preview"]["read_status"] == "malformed_json"


def test_excerpts_are_capped_and_source_artifacts_are_not_mutated(tmp_path):
    eqr = _module()
    long_text = "Validation passed. " + ("x" * (eqr.EXCERPT_CHAR_LIMIT * 3))
    validation = _write(tmp_path / "validation.txt", long_text)
    before = validation.read_text(encoding="utf-8")

    report = eqr.build_evidence_quality_report_contract(
        validation=validation,
        repo_root=tmp_path,
    )

    inventory = {item["artifact_key"]: item for item in report["artifact_inventory"]}
    assert len(inventory["validation"]["excerpt"]) <= eqr.EXCERPT_CHAR_LIMIT + 3
    assert validation.read_text(encoding="utf-8") == before


def test_json_and_markdown_artifacts_are_written(tmp_path):
    eqr = _module()
    final_answer = _write(tmp_path / "answer.txt", "Evidence exists and validation passed.")
    validation = _write(tmp_path / "validation.txt", "validation passed")

    result = eqr.write_evidence_quality_report_contract(
        output_dir=tmp_path / "out",
        final_answer=final_answer,
        validation=validation,
        repo_root=tmp_path,
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == "evidence_quality_report_contract.json"
    assert Path(result["md_path"]).name == "evidence_quality_report_contract.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == "evidence_quality_report_contract"
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert "# Evidence Quality Report Contract" in markdown
    assert "## Dimension Reviews" in markdown
    assert "EVAL.N3" in markdown


def test_cli_writes_report_artifacts_and_summary(tmp_path):
    script = _script()
    final_answer = _write(tmp_path / "answer.txt", "Validation passed.")
    validation = _write(tmp_path / "validation.txt", "validation passed")

    result = script.run_create_evidence_quality_report_contract(
        output_dir=str(tmp_path / "out"),
        final_answer=str(final_answer),
        validation=str(validation),
        repo_root=tmp_path,
    )

    assert result["ok"] is True
    assert result["summary"]["report_kind"] == "evidence_quality_report_contract"
    assert result["summary"]["dimension_count"] == len(REQUIRED_DIMENSIONS)
    assert result["summary"]["recommended_next_phase"] == "EVAL.N3"
    assert Path(result["summary"]["json_path"]).is_file()
    assert Path(result["summary"]["md_path"]).is_file()


def test_markdown_contains_required_sections():
    eqr = _module()

    markdown = eqr.render_evidence_quality_report_contract_markdown(
        eqr.build_evidence_quality_report_contract()
    )

    for section in (
        "Summary",
        "Source Artifacts",
        "Artifact Inventory",
        "Claim Inventory",
        "Evidence Inventory",
        "Dimension Reviews",
        "Missing Evidence",
        "Contradiction Risks",
        "Freshness Findings",
        "Confidence Alignment Findings",
        "Scope Alignment Findings",
        "Human Review Boundary",
        "Warnings",
        "Blocked Reasons",
        "Boundaries",
        "Recommended Next Phase",
    ):
        assert f"## {section}" in markdown, section


def test_source_has_no_forbidden_imports_or_execution_calls():
    root = Path(__file__).parent.parent
    paths = (
        root / "core" / "evidence_quality_report_contract.py",
        root / "scripts" / "create_evidence_quality_report_contract.py",
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
                if path.name == "evidence_quality_report_contract.py" and top:
                    assert top in {"__future__", "json", "pathlib", "re", "typing", "core"}, (
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
                }, f"{path} calls forbidden function {name}"


def test_registry_keeps_eval_report_contract_branch_history_valid():
    root = Path(__file__).parent.parent
    data = json.loads((root / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}

    assert phases["EVAL.N1"]["status"] == "complete"
    assert phases["EVAL.N2"]["status"] == "complete"
    assert phases["EVAL.N2"]["prerequisites"] == ["EVAL.N1"]
    assert phases["EVAL.N2"]["title"] == "Evidence Quality Report Contract"
    assert phases["EVAL.N3"]["status"] == "complete"
    assert phases["EVAL.N3"]["prerequisites"] == ["EVAL.N2"]
    assert phases["EVAL.N3"]["title"] == "Evidence Quality Report Builder"
    assert phases["EVAL.N4"]["status"] == "complete"
    assert phases["EVAL.N4"]["prerequisites"] == ["EVAL.N3"]
    assert phases["EVAL.N5"]["status"] == "complete"
    assert phases["EVAL.N5"]["prerequisites"] == ["EVAL.N4"]
    assert phases["EVAL.N6"]["status"] == "complete"
    assert phases["EVAL.N6"]["prerequisites"] == ["EVAL.N5"]
    assert phases["EVAL.N7"]["status"] == "complete"
    assert phases["EVAL.N7"]["prerequisites"] == ["EVAL.N6"]
    assert phases["EVAL.CLOSE"]["status"] == "complete"
    assert phases["EVAL.CLOSE"]["prerequisites"] == ["EVAL.N7"]
    assert phases["HUMAN.N1"]["status"] == "complete"
    assert phases["HUMAN.N1"]["prerequisites"] == ["EVAL.CLOSE"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
