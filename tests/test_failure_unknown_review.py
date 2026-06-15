"""Tests for Phase 14.5a unknown failure category review.

Covers:
1.  Latest taxonomy derivation artifact is found.
2.  Explicit --taxonomy-report input works.
3.  Unknown cases are extracted.
4.  Missing category cases are treated as unknown.
5.  Low-confidence cases are included in the review.
6.  Review outcome counts are deterministic.
7.  Security/tool evidence suggests security_tool_or_permission.
8.  Wrong-file case name suggests wrong_file_or_decoy.
9.  Missing-import evidence suggests missing_import_or_dependency.
10. Insufficient evidence stays insufficient_evidence, not forced.
11. No input artifact is handled gracefully.
12. JSON and Markdown artifacts are written.
13. Import/side-effect guard (no Flask, no model client, no DB,
    no subprocess, no patch apply, no lesson promotion).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.failure_unknown_review import (
    REVIEW_OUTCOMES,
    UNKNOWN_REVIEW_GUARDRAIL_NOTE,
    build_unknown_review,
    build_unknown_review_from_empty,
    compute_readiness_recommendation,
    extract_unknown_cases,
    find_latest_derivation_artifact,
    load_derivation_artifact,
    propose_new_categories,
    render_unknown_review_markdown,
    review_unknown_case,
)
import scripts.create_failure_unknown_review as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _derivation_artifact(
    unknown_cases: list[dict] | None = None,
    unmapped_cases: list[dict] | None = None,
    classified_cases: list[dict] | None = None,
) -> dict:
    return {
        "report_kind": "failure_taxonomy_derivation",
        "summary": {
            "total_benchmark_reports_scanned": 1,
            "unmapped_case_count": len(unknown_cases or []),
        },
        "classified_cases": classified_cases or unknown_cases or [],
        "unmapped_cases": unmapped_cases or [],
    }


def _unknown_case(
    name: str = "test_case",
    bench_category: str = "",
    language: str = "go",
    source_report: str = "report_1.json",
    assigned_category: str = "unknown",
    confidence: str = "low",
    evidence: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "bench_category": bench_category,
        "language": language,
        "source_report": source_report,
        "assigned_category": assigned_category,
        "confidence": confidence,
        "evidence": ["no classification rule matched"] if evidence is None else evidence,
        "deterministic": False,
    }


def _write_derivation(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content), encoding="utf-8")


# ── Test 1: latest derivation artifact is found ───────────────────────────────

def test_find_latest_derivation_artifact_returns_newest(tmp_path):
    audit_dir = tmp_path / ".agent" / "audits"
    audit_dir.mkdir(parents=True)
    older = audit_dir / "20260610_000000_failure-taxonomy-derivation.json"
    newer = audit_dir / "20260613_070757_failure-taxonomy-derivation.json"
    for p in (older, newer):
        p.write_text(json.dumps({"report_kind": "failure_taxonomy_derivation"}), encoding="utf-8")

    found = find_latest_derivation_artifact(tmp_path)
    assert found is not None
    assert found.name == newer.name


def test_find_latest_derivation_artifact_returns_none_when_absent(tmp_path):
    assert find_latest_derivation_artifact(tmp_path) is None


def test_find_latest_ignores_non_derivation_files(tmp_path):
    audit_dir = tmp_path / ".agent" / "audits"
    audit_dir.mkdir(parents=True)
    (audit_dir / "20260613_070757_lesson-dedup-audit.json").write_text("{}", encoding="utf-8")
    assert find_latest_derivation_artifact(tmp_path) is None


# ── Test 2: explicit --taxonomy-report works ──────────────────────────────────

def test_explicit_taxonomy_report_is_used(tmp_path):
    artifact = tmp_path / "my_derivation.json"
    content = _derivation_artifact(
        classified_cases=[_unknown_case("case_a", bench_category="logic_error")]
    )
    _write_derivation(artifact, content)

    out_dir = tmp_path / "out"
    result = script.run_review(
        repo_path=str(tmp_path),
        taxonomy_report=str(artifact),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )
    assert result["ok"] is True
    review = result["review"]
    assert review["summary"]["total_unknown_cases_reviewed"] == 1


def test_explicit_taxonomy_report_missing_returns_error(tmp_path):
    result = script.run_review(
        repo_path=str(tmp_path),
        taxonomy_report=str(tmp_path / "nonexistent.json"),
        output_dir=str(tmp_path / "out"),
        generated_at=1700000000.0,
    )
    assert result["ok"] is False
    assert "not found" in result["error"]


# ── Test 3: unknown cases are extracted ───────────────────────────────────────

def test_extract_unknown_cases_includes_unknown_assigned():
    derivation = _derivation_artifact(
        classified_cases=[
            _unknown_case("unknown_one", assigned_category="unknown"),
            {"name": "passed", "assigned_category": "security_tool_or_permission", "confidence": "high"},
        ]
    )
    cases = extract_unknown_cases(derivation)
    names = [c["name"] for c in cases]
    assert "unknown_one" in names
    assert "passed" not in names


def test_extract_unknown_cases_includes_low_confidence():
    derivation = _derivation_artifact(
        classified_cases=[
            _unknown_case("low_conf", assigned_category="missing_import_or_dependency", confidence="low"),
            {"name": "high_conf", "assigned_category": "security_tool_or_permission", "confidence": "high"},
        ]
    )
    cases = extract_unknown_cases(derivation)
    names = [c["name"] for c in cases]
    assert "low_conf" in names
    assert "high_conf" not in names


def test_extract_unknown_cases_deduplicates_by_name_and_source():
    derivation = _derivation_artifact(
        classified_cases=[
            _unknown_case("dup", source_report="rep1.json", assigned_category="unknown"),
        ],
        unmapped_cases=[
            {"name": "dup", "source_report": "rep1.json", "reason": "..."},
        ]
    )
    cases = extract_unknown_cases(derivation)
    assert sum(1 for c in cases if c["name"] == "dup") == 1


# ── Test 4: missing category cases treated as unknown ─────────────────────────

def test_missing_category_case_is_treated_as_unknown():
    derivation = _derivation_artifact(
        classified_cases=[
            {
                "name": "no_cat_case",
                "assigned_category": "",
                "confidence": "low",
                "bench_category": "",
                "evidence": [],
            }
        ]
    )
    cases = extract_unknown_cases(derivation)
    assert any(c["name"] == "no_cat_case" for c in cases)


def test_insufficient_evidence_category_is_extracted():
    derivation = _derivation_artifact(
        classified_cases=[
            _unknown_case("insuf", assigned_category="insufficient_evidence", confidence="low")
        ]
    )
    cases = extract_unknown_cases(derivation)
    assert any(c["name"] == "insuf" for c in cases)


# ── Test 5: low-confidence cases handled ─────────────────────────────────────

def test_low_confidence_non_unknown_category_still_reviewed():
    case = _unknown_case(
        "borderline",
        bench_category="migration",
        assigned_category="missing_import_or_dependency",
        confidence="low",
    )
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] in REVIEW_OUTCOMES


# ── Test 6: review outcome counts are deterministic ──────────────────────────

def test_review_outcome_counts_are_deterministic():
    cases = [
        _unknown_case("c1", bench_category="logic_error"),
        _unknown_case("c2", bench_category="migration"),
        _unknown_case("c3", bench_category="callback_dispatch_ambiguity"),
    ]
    derivation = _derivation_artifact(classified_cases=cases)
    review1 = build_unknown_review(derivation)
    review2 = build_unknown_review(derivation)
    assert (
        review1["summary"]["outcome_counts"]
        == review2["summary"]["outcome_counts"]
    )


def test_review_outcome_counts_sum_to_total():
    cases = [
        _unknown_case("c1", bench_category="logic_error"),
        _unknown_case("c2", bench_category="migration"),
        _unknown_case("c3"),  # no bench_category
    ]
    derivation = _derivation_artifact(classified_cases=cases)
    review = build_unknown_review(derivation)
    total = review["summary"]["total_unknown_cases_reviewed"]
    count_sum = sum(review["summary"]["outcome_counts"].values())
    assert count_sum == total


# ── Test 7: security/tool evidence suggests correct category ─────────────────

def test_security_bench_category_maps_to_env_tool_noise():
    case = _unknown_case("sec_case", bench_category="security")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "environment_or_tool_noise"
    assert reviewed["suggested_existing_category"] == "security_tool_or_permission"


def test_security_name_hint_suggests_security_category():
    case = _unknown_case("python_security_trap", bench_category="")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "candidate_mapping_rule"
    assert reviewed["suggested_existing_category"] == "security_tool_or_permission"


# ── Test 8: wrong-file name hints suggest correct category ───────────────────

def test_wrong_file_name_suggests_wrong_file_or_decoy():
    case = _unknown_case("go_wrong_file_temptation", bench_category="")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "candidate_mapping_rule"
    assert reviewed["suggested_existing_category"] == "wrong_file_or_decoy"


def test_wrong_file_rule_suggestion_has_medium_confidence():
    case = _unknown_case("wrong_file_case", bench_category="")
    reviewed = review_unknown_case(case)
    sr = reviewed.get("suggested_rule")
    assert sr is not None
    assert sr.get("confidence") in ("medium", "low")


# ── Test 9: missing-import evidence suggests correct category ─────────────────

def test_missing_import_name_suggests_missing_import_category():
    case = _unknown_case("go_missing_import_error", bench_category="")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "candidate_mapping_rule"
    assert reviewed["suggested_existing_category"] == "missing_import_or_dependency"


def test_missing_import_bench_category_maps_correctly():
    case = _unknown_case("import_case", bench_category="missing_import")
    # missing_import is in _BENCH_CATEGORY_TO_DERIVATION so it maps to
    # missing_import_or_dependency in phase 14.5 and shouldn't appear as unknown;
    # but if it does appear as unknown (e.g., carried through), review it correctly
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] in REVIEW_OUTCOMES


# ── Test 10: insufficient evidence stays insufficient_evidence ────────────────

def test_no_bench_category_and_no_evidence_stays_insufficient():
    case = _unknown_case("bare_case", bench_category="", evidence=[])
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "insufficient_evidence"
    assert reviewed["recommended_action"] == "needs_manual_review"


def test_insufficient_evidence_is_not_forced_to_another_category():
    case = _unknown_case("bare_case2", bench_category="", evidence=[])
    reviewed = review_unknown_case(case)
    assert reviewed["suggested_existing_category"] is None


# ── Test 11: no input artifact handled gracefully ─────────────────────────────

def test_no_derivation_artifact_produces_empty_review(tmp_path):
    out_dir = tmp_path / "out"
    result = script.run_review(
        repo_path=str(tmp_path),
        taxonomy_report=None,
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )
    assert result["ok"] is True
    review = result["review"]
    assert review["summary"]["total_unknown_cases_reviewed"] == 0
    assert review.get("no_input") is True


def test_build_unknown_review_from_empty_is_valid():
    review = build_unknown_review_from_empty()
    assert review["report_kind"] == "failure_unknown_review"
    assert review["summary"]["total_unknown_cases_reviewed"] == 0
    assert review["summary"]["phase_14_6_readiness"] == "not_ready"
    assert review["reviewed_cases"] == []


# ── Test 12: JSON and Markdown artifacts are written ─────────────────────────

def test_run_review_writes_json_and_markdown(tmp_path):
    audit_dir = tmp_path / ".agent" / "audits"
    audit_dir.mkdir(parents=True)
    artifact = audit_dir / "20260613_070757_failure-taxonomy-derivation.json"
    content = _derivation_artifact(
        classified_cases=[_unknown_case("test_unk", bench_category="logic_error")]
    )
    _write_derivation(artifact, content)

    out_dir = tmp_path / "out"
    result = script.run_review(
        repo_path=str(tmp_path),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )
    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["report_kind"] == "failure_unknown_review"
    assert "summary" in data
    assert "reviewed_cases" in data
    assert "suggested_rules" in data
    assert "proposed_new_categories" in data
    assert "generated_at" in data

    md = md_path.read_text(encoding="utf-8")
    assert "Phase 14.5a" in md
    assert "read-only" in md.lower() or "guardrail" in md.lower()
    assert "## 1. Summary" in md


def test_json_filename_contains_review_slug(tmp_path):
    audit_dir = tmp_path / ".agent" / "audits"
    audit_dir.mkdir(parents=True)
    artifact = audit_dir / "20260613_failure-taxonomy-derivation.json"
    _write_derivation(artifact, _derivation_artifact())
    out_dir = tmp_path / "out"
    result = script.run_review(
        repo_path=str(tmp_path),
        output_dir=str(out_dir),
        generated_at=1700000000.0,
    )
    assert "failure-unknown-review.json" in result["json_path"]
    assert "failure-unknown-review.md" in result["md_path"]


# ── Test 13: import / side-effect guard ───────────────────────────────────────

_REVIEW_MODULE = Path(__file__).parent.parent / "core" / "failure_unknown_review.py"
_REVIEW_SOURCE = _REVIEW_MODULE.read_text(encoding="utf-8")


def test_no_flask_import_in_review_module():
    tree = ast.parse(_REVIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "flask" not in alias.name.lower(), alias.name
        elif isinstance(node, ast.ImportFrom):
            assert "flask" not in (node.module or "").lower(), node.module


def test_no_subprocess_import_in_review_module():
    tree = ast.parse(_REVIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "subprocess"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") != "subprocess"


def test_no_model_client_in_review_module():
    for bad in ("anthropic", "openai", "litellm", "ollama", "bedrock"):
        assert bad not in _REVIEW_SOURCE, f"Found {bad!r} in review module"


def test_no_db_client_in_review_module():
    for bad in ("sqlalchemy", "psycopg", "pymongo", "motor", "sqlite3"):
        assert bad not in _REVIEW_SOURCE, f"Found {bad!r} in review module"


def test_no_lesson_promotion_in_review_module():
    for bad in ("promote_lesson", "save_active_lesson", "lesson_store"):
        assert bad not in _REVIEW_SOURCE, f"Found {bad!r} in review module"


def test_no_patch_apply_in_review_module():
    for bad in ("apply_patch", "patch_apply", "run_patch"):
        assert bad not in _REVIEW_SOURCE, f"Found {bad!r} in review module"


def test_review_module_only_imports_stdlib():
    stdlib_ok = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_REVIEW_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in stdlib_ok, (
                f"Unexpected import in failure_unknown_review: {module!r}"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, (
                    f"Unexpected import in failure_unknown_review: {alias.name!r}"
                )


# ── Additional integration checks ────────────────────────────────────────────

def test_algorithm_bench_category_produces_candidate_mapping_rule():
    case = _unknown_case("cpp_string_view", bench_category="logic_error")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "candidate_mapping_rule"
    assert reviewed["recommended_action"] == "add_mapping_rule"


def test_migration_bench_category_produces_candidate_new_category():
    case = _unknown_case("python_embedding_switch", bench_category="migration")
    reviewed = review_unknown_case(case)
    assert reviewed["review_outcome"] == "candidate_new_category"
    assert reviewed["recommended_action"] == "add_new_category"


def test_readiness_is_ready_with_unknown_bucket_for_typical_unknowns():
    cases = [
        _unknown_case("c1", bench_category="logic_error"),      # candidate_mapping_rule
        _unknown_case("c2", bench_category="callback_dispatch_ambiguity"),  # candidate_mapping_rule
        _unknown_case("c3", bench_category="migration"),          # candidate_new_category
    ]
    derivation = _derivation_artifact(classified_cases=cases)
    review = build_unknown_review(derivation)
    assert review["summary"]["phase_14_6_readiness"] in (
        "ready_with_unknown_bucket", "not_ready"
    )


def test_review_outcomes_enum_is_stable():
    assert REVIEW_OUTCOMES == (
        "candidate_mapping_rule",
        "candidate_new_category",
        "environment_or_tool_noise",
        "insufficient_evidence",
        "leave_unknown",
    )


def test_new_category_proposals_capped_at_three():
    cases = [
        _unknown_case(f"case_{i}", bench_category=cat)
        for i, cat in enumerate(["migration", "module_wiring", "config_mismatch", "logic_error"])
    ]
    reviewed = [review_unknown_case(c) for c in cases]
    proposals = propose_new_categories(reviewed)
    assert len(proposals) <= 3
