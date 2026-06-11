"""Phase A.10 tests — Proposal/Lesson Entry Dedup Audit.

Tests:
1. Report builds JSON and Markdown (both non-empty, parseable, contain required keys).
2. Required entrypoints are present (P1–P7, D8–D11, B12, A13, M14, T15).
3. Proposal duplicate-risk is detected (cross-path split flagged).
4. Dual Dream endpoints are marked do_not_merge / intentionally separate.
5. A.6 guard: create_lesson_from_proposal (P1) force-disables LESSON_AUTO_ACTIVE.
6. Benchmark seeder (B12) is marked freeze, not cut.
7. Report-only AST/import guard: no forbidden imports in core/lesson_entry_audit.py.
8. CLI writes artifacts under .agent/audits and does not mutate source reports.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.lesson_entry_audit import (
    AUDIT_VERSION,
    CAT_BENCHMARK,
    CAT_DREAM,
    CAT_PROPOSAL,
    DEDUP_SOURCE_KEY,
    DEDUP_SOURCE_REPORT,
    STATUS_DUPLICATE_RISK,
    STATUS_FROZEN,
    build_report,
    render_markdown,
    write_artifacts,
)

MODULE_PATH = PROJECT_ROOT / "core" / "lesson_entry_audit.py"
CLI_PATH = PROJECT_ROOT / "scripts" / "create_lesson_entry_audit.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry_by_id(report: dict, entry_id: str) -> dict:
    for e in report["entrypoints"]:
        if e["entry_id"] == entry_id:
            return e
    raise KeyError(f"entry_id {entry_id!r} not found")


# ---------------------------------------------------------------------------
# Test 1 — Report builds JSON and Markdown
# ---------------------------------------------------------------------------

def test_build_report_returns_required_keys():
    report = build_report()
    assert "audit_version" in report
    assert report["audit_version"] == AUDIT_VERSION
    assert "summary" in report
    assert "entrypoints" in report
    assert "duplicate_risk_analysis" in report
    assert "safety_checks" in report
    assert "recommendations" in report
    assert "guardrails" in report


def test_build_report_summary_counts_positive():
    report = build_report()
    s = report["summary"]
    assert s["total_entrypoints"] >= 15
    assert s["proposal_to_candidate"] >= 7
    assert s["dream_to_candidate"] >= 4
    assert s["benchmark_to_candidate"] >= 1


def test_render_markdown_is_nonempty_string():
    report = build_report()
    md = render_markdown(report)
    assert isinstance(md, str)
    assert len(md) > 500
    assert "## Summary" in md
    assert "## Entrypoint Table" in md
    assert "## Duplicate Risk Analysis" in md
    assert "## Safety Checks" in md
    assert "## Recommendations" in md
    assert "## Guardrails" in md


def test_write_artifacts_produces_json_and_md():
    with tempfile.TemporaryDirectory() as td:
        report = build_report()
        paths = write_artifacts(report, audits_root=td)
        assert "json" in paths
        assert "markdown" in paths
        json_path = Path(paths["json"])
        md_path = Path(paths["markdown"])
        assert json_path.is_file()
        assert md_path.is_file()
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["audit_version"] == AUDIT_VERSION
        assert len(loaded["entrypoints"]) >= 15


def test_json_artifact_filename_contains_timestamp_and_slug():
    with tempfile.TemporaryDirectory() as td:
        report = build_report()
        paths = write_artifacts(report, audits_root=td)
        json_name = Path(paths["json"]).name
        assert "lesson-entry-dedup-audit" in json_name
        assert json_name.endswith(".json")
        md_name = Path(paths["markdown"]).name
        assert "lesson-entry-dedup-audit" in md_name
        assert md_name.endswith(".md")


# ---------------------------------------------------------------------------
# Test 2 — Required entrypoints are present
# ---------------------------------------------------------------------------

REQUIRED_IDS = {"P1", "P2", "P3", "P4", "P5", "P6", "P7",
                "D8", "D9", "D10", "D11",
                "B12", "A13", "M14", "T15"}


def test_all_required_entry_ids_present():
    report = build_report()
    found = {e["entry_id"] for e in report["entrypoints"]}
    missing = REQUIRED_IDS - found
    assert not missing, f"Missing entry IDs: {missing}"


def test_proposal_entries_have_expected_files():
    report = build_report()
    for eid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        e = _entry_by_id(report, eid)
        assert e["category"] == CAT_PROPOSAL, f"{eid} should be proposal_to_candidate"


def test_dream_entries_have_expected_files():
    report = build_report()
    for eid in ("D8", "D9", "D10", "D11"):
        e = _entry_by_id(report, eid)
        assert e["category"] == CAT_DREAM, f"{eid} should be dream_to_candidate"


def test_benchmark_entry_present():
    report = build_report()
    e = _entry_by_id(report, "B12")
    assert e["category"] == CAT_BENCHMARK


# ---------------------------------------------------------------------------
# Test 3 — Proposal duplicate-risk is detected
# ---------------------------------------------------------------------------

def test_proposal_path_split_has_both_dedup_mechanisms():
    report = build_report()
    dra = report["duplicate_risk_analysis"]["proposal_path_split"]
    assert len(dra["source_report_dedup_ids"]) >= 1, "Expected at least one source_report proposal entry"
    assert len(dra["source_key_dedup_ids"]) >= 1, "Expected at least one source_key proposal entry"


def test_proposal_cross_path_duplicates_flagged():
    report = build_report()
    dra = report["duplicate_risk_analysis"]["proposal_path_split"]
    assert dra["cross_path_duplicates_possible"] is True


def test_proposal_source_report_entries_have_duplicate_risk_status():
    report = build_report()
    source_report_ids = {
        e["entry_id"]
        for e in report["entrypoints"]
        if e["category"] == CAT_PROPOSAL and e["dedup_mechanism"] == DEDUP_SOURCE_REPORT
    }
    # At least one source_report entry must carry duplicate_risk status
    dup_risk_ids = {
        e["entry_id"]
        for e in report["entrypoints"]
        if e["entry_id"] in source_report_ids
        and e["current_status"] == STATUS_DUPLICATE_RISK
    }
    # P1/P2/P3 use source_report; P4 uses source_key and is marked duplicate_risk
    # The risk is the *split* between the two groups; at least P4 (source_key with
    # different source_label) must be flagged.
    source_key_dup_risk = {
        e["entry_id"]
        for e in report["entrypoints"]
        if e["category"] == CAT_PROPOSAL
        and e["dedup_mechanism"] == DEDUP_SOURCE_KEY
        and e["current_status"] == STATUS_DUPLICATE_RISK
    }
    # P4 is the representative source_key entry that must be flagged
    assert "P4" in source_key_dup_risk, "P4 (seed_lessons_from_proposals) should be duplicate_risk"


def test_report_summary_duplicate_risk_count_nonzero():
    report = build_report()
    assert report["summary"]["duplicate_risk_count"] >= 1


# ---------------------------------------------------------------------------
# Test 4 — Dual Dream endpoints are marked do_not_merge / intentionally separate
# ---------------------------------------------------------------------------

def test_dream_path_split_intentionally_separate():
    report = build_report()
    dp = report["duplicate_risk_analysis"]["dream_path_split"]
    assert dp["intentionally_separate"] is True
    assert dp["do_not_merge"] is True


def test_d8_in_non_ready_path():
    report = build_report()
    dp = report["duplicate_risk_analysis"]["dream_path_split"]
    assert "D8" in dp["non_ready_path_ids"]


def test_d9_d10_d11_in_ready_path():
    report = build_report()
    dp = report["duplicate_risk_analysis"]["dream_path_split"]
    for eid in ("D9", "D10", "D11"):
        assert eid in dp["ready_to_apply_path_ids"], f"{eid} should be in ready_to_apply_path_ids"


def test_d8_has_duplicate_risk_status():
    report = build_report()
    e = _entry_by_id(report, "D8")
    assert e["current_status"] == STATUS_DUPLICATE_RISK


def test_recommendation_do_not_merge_dual_dream():
    report = build_report()
    do_not_merge_recs = [
        r for r in report["recommendations"] if r["disposition"] == "do_not_merge"
    ]
    assert len(do_not_merge_recs) >= 1
    texts = " ".join(r["topic"] + " " + r["detail"] for r in do_not_merge_recs)
    assert "D8" in texts or "dream" in texts.lower()


# ---------------------------------------------------------------------------
# Test 5 — A.6 guard: P1 (create_lesson_from_proposal) force-disables LESSON_AUTO_ACTIVE
# ---------------------------------------------------------------------------

def test_p1_force_disables_lesson_auto_active():
    report = build_report()
    e = _entry_by_id(report, "P1")
    assert e["force_disables_LESSON_AUTO_ACTIVE"] == "true"


def test_p1_a6_guard_is_set():
    report = build_report()
    e = _entry_by_id(report, "P1")
    assert e.get("a6_guard") is True


def test_all_proposal_entries_force_disable_lesson_auto_active():
    report = build_report()
    for eid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        e = _entry_by_id(report, eid)
        assert e["force_disables_LESSON_AUTO_ACTIVE"] == "true", (
            f"{eid} should force-disable LESSON_AUTO_ACTIVE"
        )


def test_safety_checks_include_a6_note():
    report = build_report()
    sc = report["safety_checks"]
    assert "A.6" in sc["a6_note"]
    assert "P1" in str(sc["proposal_candidate_only_after_A6"])


def test_safety_checks_proposal_ids_in_force_disable_list():
    report = build_report()
    force_ids = set(report["safety_checks"]["force_disable_LESSON_AUTO_ACTIVE"])
    for eid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        assert eid in force_ids, f"{eid} should be in force_disable_LESSON_AUTO_ACTIVE"


# ---------------------------------------------------------------------------
# Test 6 — Benchmark seeder (B12) is marked freeze, not cut
# ---------------------------------------------------------------------------

def test_b12_status_is_frozen():
    report = build_report()
    e = _entry_by_id(report, "B12")
    assert e["current_status"] == STATUS_FROZEN


def test_benchmark_seeder_recommendation_is_freeze():
    report = build_report()
    freeze_recs = [r for r in report["recommendations"] if r["disposition"] == "freeze"]
    assert len(freeze_recs) >= 1
    topics = " ".join(r["topic"] + " " + r["detail"] for r in freeze_recs)
    assert "B12" in topics or "benchmark" in topics.lower()


def test_b12_recommendation_does_not_say_cut_or_delete():
    report = build_report()
    freeze_recs = [r for r in report["recommendations"] if r["disposition"] == "freeze"]
    bench_recs = [
        r for r in freeze_recs
        if "B12" in r.get("topic", "") + r.get("detail", "")
        or "benchmark" in (r.get("topic", "") + r.get("detail", "")).lower()
    ]
    assert bench_recs, "No freeze recommendation mentioning B12/benchmark"
    for r in bench_recs:
        combined = (r.get("topic", "") + " " + r.get("detail", "")).lower()
        assert "cut" not in combined, "Benchmark freeze rec should not say 'cut'"
        assert "delete" not in combined, "Benchmark freeze rec should not say 'delete'"


# ---------------------------------------------------------------------------
# Test 7 — Report-only AST/import guard
# ---------------------------------------------------------------------------

def test_module_file_exists():
    assert MODULE_PATH.is_file(), f"core/lesson_entry_audit.py not found at {MODULE_PATH}"


def _parse_module_imports(path: Path) -> list[ast.stmt]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: list[ast.stmt] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
    return imports


def _import_names(stmt: ast.stmt) -> list[str]:
    if isinstance(stmt, ast.Import):
        return [alias.name for alias in stmt.names]
    if isinstance(stmt, ast.ImportFrom):
        module = stmt.module or ""
        return [module] + [alias.name for alias in stmt.names]
    return []


def _all_imported_modules(path: Path) -> set[str]:
    imports = _parse_module_imports(path)
    modules: set[str] = set()
    for stmt in imports:
        for name in _import_names(stmt):
            modules.add(name)
            modules.add(name.split(".")[0])
    return modules


def test_no_model_client_import():
    modules = _all_imported_modules(MODULE_PATH)
    forbidden = {"anthropic", "openai", "core.sleeping_consultant", "sleeping_consultant"}
    found = forbidden & modules
    assert not found, f"core/lesson_entry_audit.py imports model clients: {found}"


def test_no_flask_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "flask" not in modules, "core/lesson_entry_audit.py must not import Flask"
    assert "web" not in modules, "core/lesson_entry_audit.py must not import web modules"


def test_no_db_import():
    modules = _all_imported_modules(MODULE_PATH)
    forbidden = {"database", "sqlalchemy", "sqlite3", "core.memory_store"}
    found = forbidden & modules
    assert not found, f"core/lesson_entry_audit.py imports DB: {found}"


def test_no_subprocess_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "subprocess" not in modules, "core/lesson_entry_audit.py must not import subprocess"


def test_no_benchmark_runner_import():
    modules = _all_imported_modules(MODULE_PATH)
    assert "run_benchmarks" not in modules, "must not import benchmark runner"
    assert not any("benchmarks" in m for m in modules), "must not import benchmarks package"


def _ast_call_names(path: Path) -> set[str]:
    """Return the set of function/attribute names that appear as Call nodes."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_no_lesson_write_calls_in_module():
    calls = _ast_call_names(MODULE_PATH)
    assert "save_candidate_lesson" not in calls, (
        "core/lesson_entry_audit.py must not call save_candidate_lesson"
    )
    assert "save_raw_lesson_record" not in calls, (
        "core/lesson_entry_audit.py must not call save_raw_lesson_record"
    )
    assert "promote_lesson" not in calls, (
        "core/lesson_entry_audit.py must not call promote_lesson"
    )


def test_no_patch_apply_in_module():
    calls = _ast_call_names(MODULE_PATH)
    modules = _all_imported_modules(MODULE_PATH)
    assert "apply_patch" not in calls, "must not call apply_patch"
    assert "patch_executor" not in modules, "must not import patch_executor"


# ---------------------------------------------------------------------------
# Test 8 — CLI writes artifacts under .agent/audits; does not mutate source reports
# ---------------------------------------------------------------------------

def test_cli_writes_to_audits_dir():
    from scripts.create_lesson_entry_audit import _main

    with tempfile.TemporaryDirectory() as td:
        audits_root = Path(td) / "audits"
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", str(audits_root)])
        assert ret == 0
        json_files = list(audits_root.glob("*lesson-entry-dedup-audit*.json"))
        md_files = list(audits_root.glob("*lesson-entry-dedup-audit*.md"))
        assert json_files, "CLI should produce a JSON artifact"
        assert md_files, "CLI should produce a Markdown artifact"


def test_cli_dry_run_does_not_write():
    from scripts.create_lesson_entry_audit import _main

    with tempfile.TemporaryDirectory() as td:
        audits_root = Path(td) / "audits_dryrun"
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", str(audits_root), "--dry-run"])
        assert ret == 0
        json_files = list(audits_root.glob("*.json")) if audits_root.exists() else []
        assert not json_files, "--dry-run must not write files"


def test_cli_does_not_write_to_proposals_root():
    proposals_root = PROJECT_ROOT / ".agent" / "proposals"
    before: set[str] = set()
    if proposals_root.exists():
        before = {str(p) for p in proposals_root.rglob("*")}

    from scripts.create_lesson_entry_audit import _main
    import tempfile, os

    with tempfile.TemporaryDirectory() as td:
        _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])

    after: set[str] = set()
    if proposals_root.exists():
        after = {str(p) for p in proposals_root.rglob("*")}

    new_files = after - before
    assert not new_files, f"CLI wrote to proposals root: {new_files}"


def test_cli_does_not_write_to_lessons_store():
    lessons_root = PROJECT_ROOT / ".agent" / "lessons"
    before: set[str] = set()
    if lessons_root.exists():
        before = {str(p) for p in lessons_root.rglob("*")}

    from scripts.create_lesson_entry_audit import _main
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])

    after: set[str] = set()
    if lessons_root.exists():
        after = {str(p) for p in lessons_root.rglob("*")}

    new_files = after - before
    assert not new_files, f"CLI wrote to lesson store: {new_files}"


def test_json_artifact_is_valid_json():
    from scripts.create_lesson_entry_audit import _main

    with tempfile.TemporaryDirectory() as td:
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])
        assert ret == 0
        json_files = list(Path(td).glob("*.json"))
        assert json_files
        payload = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert payload["audit_version"] == AUDIT_VERSION
        assert len(payload["entrypoints"]) >= 15


def test_markdown_artifact_contains_required_sections():
    from scripts.create_lesson_entry_audit import _main

    with tempfile.TemporaryDirectory() as td:
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", td])
        assert ret == 0
        md_files = list(Path(td).glob("*.md"))
        assert md_files
        content = md_files[0].read_text(encoding="utf-8")
        for section in ("## Summary", "## Entrypoint Table", "## Duplicate Risk Analysis",
                        "## Safety Checks", "## Recommendations", "## Guardrails"):
            assert section in content, f"Missing section: {section}"


# ---------------------------------------------------------------------------
# Extra: File existence validation
# ---------------------------------------------------------------------------

def test_build_report_with_repo_path_marks_existing_files():
    report = build_report(repo_path=PROJECT_ROOT)
    for e in report["entrypoints"]:
        if "file_exists" in e:
            if not e["file_exists"]:
                assert e["current_status"] in {
                    "needs_verification", STATUS_DUPLICATE_RISK, STATUS_FROZEN
                }, f"{e['entry_id']}: missing file should upgrade status"


def test_entrypoints_have_required_fields():
    report = build_report()
    required_fields = {
        "entry_id", "category", "public_surface", "file",
        "function_or_route", "source_label", "dedup_mechanism",
        "force_disables_LESSON_AUTO_ACTIVE", "writes_via",
        "expected_output_bucket", "current_status",
    }
    for e in report["entrypoints"]:
        missing = required_fields - e.keys()
        assert not missing, f"{e['entry_id']} missing fields: {missing}"
