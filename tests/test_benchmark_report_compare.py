"""Tests for EVAL.2 — Benchmark Report Compare / Single-Case Flake Evidence (report-only).

EVAL.2 explains one benchmark case (or every suspected flake candidate) across the
existing benchmark report artifacts: which reports mention it, which runs passed or
failed, which report is latest and why, and whether the evidence supports a likely
flake or a likely broken case. It optionally cross-checks the EVAL.1 ledger but works
without it. It does not run benchmarks, call models, apply patches, edit benchmark
cases, run validation, contact network services, write to a database, launch workers,
or merge.

Covers the prescribed cases:
1.  missing benchmark reports produces no_evidence with a warning.
2.  a malformed report is skipped with a warning.
3.  an unknown case produces no_evidence.
4.  a single pass produces single_pass_only.
5.  a single failure produces single_failure_only.
6.  pass then fail produces mixed_pass_fail_history and regressed_after_pass labels.
7.  fail then pass produces a recovered_on_later_run label.
8.  repeated failures with no pass produces likely_broken.
9.  mixed pass/fail produces likely_flake.
10. the latest observation is deterministic.
11. ordering explains created_at ordering.
12. ordering falls back deterministically when created_at is missing.
13. full-suite vs single-case scope labels are detected.
14. the ledger cross-check marks ledger_flake_candidate when the ledger contains the case.
15. a missing ledger is a warning only, not a blocker.
16. all-flake-candidates mode writes an aggregate report.
17. the CLI writes JSON + Markdown for a single case.
18. the CLI --json prints the summary JSON.
19. the Markdown contains the required sections and boundaries.
20. the guardrails are all false.
21. the source contains no forbidden benchmark-execution / model / network / patch /
    validation / worker / database / merge behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.benchmark_report_compare import (
    ALL_FLAKE_JSON_NAME,
    ALL_FLAKE_MD_NAME,
    BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE,
    REPORT_KIND,
    build_case_comparison,
    build_flake_candidates_comparison,
    load_ledger,
    render_benchmark_report_compare_markdown,
    render_flake_candidates_compare_markdown,
    write_case_comparison,
    write_flake_candidates_comparison,
)
import scripts.compare_benchmark_reports as script


# ── synthetic benchmark-report builders ────────────────────────────────────────

def _case(
    name,
    success=True,
    *,
    skipped=False,
    duration_sec=1.0,
    language="python",
    category="bugfix",
    difficulty="easy",
    flaky=False,
    failure_kind_display="",
    failure_cause="",
    failure_evidence="",
):
    case = {
        "name": name,
        "success": success,
        "skipped": skipped,
        "duration_sec": duration_sec,
        "language": language,
        "category": category,
        "difficulty": difficulty,
        "flaky": flaky,
    }
    if failure_kind_display:
        case["failure_kind_display"] = failure_kind_display
    if failure_cause:
        case["failure_cause"] = failure_cause
    if failure_evidence:
        case["failure_evidence"] = failure_evidence
    return case


def _report(
    created_at,
    *,
    run_id=None,
    cases=None,
    filters=None,
    models_used=None,
    fallbacks=0,
    total_tokens=None,
    cost=None,
    duration_sec=None,
):
    results = list(cases or [])
    passed = sum(1 for c in results if c.get("success") and not c.get("skipped"))
    failed = sum(1 for c in results if not c.get("success") and not c.get("skipped"))
    total = len(results)
    data = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": round(passed / total, 6) if total else 0.0,
        "duration_sec": duration_sec,
        "total_fallbacks": fallbacks,
        "filters": filters or {"case": None, "suite": None},
        "models_used": models_used or {},
        "results": results,
        "brain_stamp": {"created_at": created_at, "brain_stamp_id": run_id or created_at},
    }
    if total_tokens is not None:
        data["total_tokens"] = total_tokens
    if cost is not None:
        data["total_estimated_cost_usd"] = cost
    return data


def _entry(data, path=None):
    stamp = data.get("brain_stamp", {}).get("created_at", "x")
    return {"path": path or f".agent/benchmarks/benchmark_report_{stamp}.json", "data": data}


def _write_report(bench_dir: Path, epoch: str, data: dict) -> Path:
    path = bench_dir / f"benchmark_report_{epoch}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _bench(tmp_path: Path) -> Path:
    bench = tmp_path / ".agent" / "benchmarks"
    bench.mkdir(parents=True, exist_ok=True)
    return bench


def _write_ledger(tmp_path: Path, flake_candidates) -> Path:
    ledger_dir = tmp_path / ".agent" / "eval" / "benchmark_run_ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / "benchmark_run_ledger.json"
    path.write_text(json.dumps({"flake_candidates": flake_candidates}), encoding="utf-8")
    return path


# ── 1. missing benchmark reports → no_evidence with warning ────────────────────

def test_missing_reports_produces_no_evidence(tmp_path):
    out = tmp_path / "out"
    res = write_case_comparison(
        str(tmp_path), str(out), case_id="c1", ledger_path=str(tmp_path / "no_ledger.json")
    )
    report = res["report"]
    assert report["classification"] == "no_evidence"
    assert report["case_timeline"] == []
    assert report["latest_observation"] is None
    assert any("no benchmark reports" in w.lower() for w in report["warnings"])
    assert (out / "c1_compare.json").is_file()
    assert (out / "c1_compare.md").is_file()


# ── 2. malformed report skipped with warning ───────────────────────────────────

def test_malformed_report_is_skipped_with_warning(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="g", cases=[_case("c1")]))
    (bench / "benchmark_report_1001.json").write_text("{ bad json", encoding="utf-8")
    res = write_case_comparison(str(tmp_path), str(tmp_path / "out"), case_id="c1", ledger_path=str(tmp_path / "no.json"))
    report = res["report"]
    assert report["loaded_report_count"] == 1
    assert report["skipped_report_count"] == 1
    assert any("malformed" in w.lower() for w in report["warnings"])


# ── 3. unknown case → no_evidence ──────────────────────────────────────────────

def test_unknown_case_produces_no_evidence():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    report = build_case_comparison([_entry(data)], "does_not_exist", comparison_id="x", created_at="t")
    assert report["classification"] == "no_evidence"
    assert report["case_timeline"] == []
    assert report["latest_observation"] is None


# ── 4. single pass → single_pass_only ──────────────────────────────────────────

def test_single_pass_produces_single_pass_only():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True)])
    report = build_case_comparison([_entry(data)], "c1", comparison_id="x", created_at="t")
    assert report["classification"] == "single_pass_only"
    assert report["status_counts"] == {"pass": 1, "fail": 0, "skipped": 0}


# ── 5. single failure → single_failure_only ────────────────────────────────────

def test_single_failure_produces_single_failure_only():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    report = build_case_comparison([_entry(data)], "c1", comparison_id="x", created_at="t")
    assert report["classification"] == "single_failure_only"
    assert report["status_counts"]["fail"] == 1


# ── 6. pass then fail → mixed + regressed labels ───────────────────────────────

def test_pass_then_fail_produces_mixed_and_regressed_labels():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)])
    report = build_case_comparison([_entry(r1), _entry(r2)], "c1", comparison_id="x", created_at="t")
    assert "mixed_pass_fail_history" in report["evidence_labels"]
    assert "regressed_after_pass" in report["evidence_labels"]
    assert "latest_is_fail" in report["evidence_labels"]
    assert report["classification"] == "likely_flake"


# ── 7. fail then pass → recovered label ────────────────────────────────────────

def test_fail_then_pass_produces_recovered_label():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    report = build_case_comparison([_entry(r1), _entry(r2)], "c1", comparison_id="x", created_at="t")
    assert "recovered_on_later_run" in report["evidence_labels"]
    assert "latest_is_pass" in report["evidence_labels"]
    assert report["classification"] == "likely_flake"


# ── 8. repeated failures, no pass → likely_broken ──────────────────────────────

def test_repeated_failures_no_pass_produces_likely_broken():
    reports = [
        _report(f"2026-06-2{i}T00:00:00+00:00", run_id=f"r{i}", cases=[_case("c1", success=False)])
        for i in range(1, 4)
    ]
    report = build_case_comparison([_entry(r) for r in reports], "c1", comparison_id="x", created_at="t")
    assert report["classification"] == "likely_broken"
    assert report["status_counts"]["fail"] == 3
    assert report["status_counts"]["pass"] == 0


# ── 9. mixed pass/fail → likely_flake ──────────────────────────────────────────

def test_mixed_pass_fail_produces_likely_flake():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    r3 = _report("2026-06-22T00:00:00+00:00", run_id="r3", cases=[_case("c1", success=False)])
    report = build_case_comparison([_entry(r1), _entry(r2), _entry(r3)], "c1", comparison_id="x", created_at="t")
    assert report["classification"] == "likely_flake"
    assert "mixed_pass_fail_history" in report["evidence_labels"]


# ── 10. latest observation deterministic ───────────────────────────────────────

def test_latest_observation_is_deterministic():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)])
    r3 = _report("2026-06-22T00:00:00+00:00", run_id="r3", cases=[_case("c1", success=True)])
    a = build_case_comparison([_entry(r1), _entry(r2), _entry(r3)], "c1", comparison_id="x", created_at="t")
    b = build_case_comparison([_entry(r3), _entry(r1), _entry(r2)], "c1", comparison_id="x", created_at="t")
    assert a["latest_observation"] == b["latest_observation"]
    assert a["latest_observation"]["run_id"] == "r3"
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ── 11. ordering explains created_at ───────────────────────────────────────────

def test_ordering_explains_created_at():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    report = build_case_comparison([_entry(data)], "c1", comparison_id="x", created_at="t")
    ordering = report["report_ordering"]
    assert ordering[0]["ordering_source"] == "created_at"
    assert ordering[0]["ordering_value"] == "2026-06-20T00:00:00+00:00"
    assert ordering[0]["is_latest"] is True


# ── 12. ordering falls back deterministically when created_at missing ──────────

def test_ordering_falls_back_to_path_when_created_at_missing():
    d1 = {"results": [_case("c1", success=True)], "total": 1, "passed": 1, "failed": 0}
    d2 = {"results": [_case("c1", success=False)], "total": 1, "passed": 0, "failed": 1}
    e1 = {"path": ".agent/benchmarks/benchmark_report_1001.json", "data": d1}
    e2 = {"path": ".agent/benchmarks/benchmark_report_1002.json", "data": d2}
    a = build_case_comparison([e1, e2], "c1", comparison_id="x", created_at="t")
    b = build_case_comparison([e2, e1], "c1", comparison_id="x", created_at="t")
    assert a["report_ordering"] == b["report_ordering"]
    assert all(row["ordering_source"] == "path" for row in a["report_ordering"])
    assert a["latest_observation"]["report_path"].endswith("benchmark_report_1002.json")


# ── 13. full-suite vs single-case scope labels ─────────────────────────────────

def test_scope_labels_are_detected():
    suite = _report("2026-06-20T00:00:00+00:00", run_id="suite", cases=[_case("c1", success=False)])
    rerun = _report(
        "2026-06-21T00:00:00+00:00",
        run_id="rerun",
        cases=[_case("c1", success=True)],
        filters={"case": "c1", "suite": None},
    )
    report = build_case_comparison([_entry(suite), _entry(rerun)], "c1", comparison_id="x", created_at="t")
    labels = report["evidence_labels"]
    assert "seen_in_full_suite" in labels
    assert "failed_in_full_suite" in labels
    assert "seen_in_single_case_run" in labels
    assert "passed_in_single_case_run" in labels


# ── 14. ledger cross-check ─────────────────────────────────────────────────────

def test_ledger_cross_check_marks_flake_candidate(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)]))
    _write_ledger(tmp_path, [{"case_id": "c1", "notes": ["mixed_pass_fail_history"]}])
    res = write_case_comparison(str(tmp_path), str(tmp_path / "out"), case_id="c1")
    report = res["report"]
    assert report["ledger_reference"]["present"] is True
    assert report["ledger_reference"]["case_is_flake_candidate"] is True
    assert "ledger_flake_candidate" in report["evidence_labels"]
    # reports show only a failure, but the ledger records a flake -> likely_flake.
    assert report["classification"] == "likely_flake"


def test_load_ledger_reads_flake_candidates(tmp_path):
    _write_ledger(tmp_path, [{"case_id": "c1", "notes": ["x"]}, {"case_id": "c2", "notes": []}])
    info = load_ledger(str(tmp_path), None)
    assert info["present"] is True
    assert info["flake_candidate_ids"] == ["c1", "c2"]
    assert info["warnings"] == []


# ── 15. missing ledger is warning only ─────────────────────────────────────────

def test_missing_ledger_is_warning_only(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    res = write_case_comparison(
        str(tmp_path), str(tmp_path / "out"), case_id="c1", ledger_path=str(tmp_path / "missing.json")
    )
    report = res["report"]
    assert report["ledger_reference"]["present"] is False
    assert any("ledger" in w.lower() for w in report["warnings"])
    assert report["blockers"] == []


# ── 16. all-flake-candidates aggregate ─────────────────────────────────────────

def test_all_flake_candidates_writes_aggregate(tmp_path):
    bench = _bench(tmp_path)
    _write_report(
        bench, "1000",
        _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True), _case("c2", success=True)]),
    )
    _write_report(
        bench, "1001",
        _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False), _case("c2", success=True)]),
    )
    res = write_flake_candidates_comparison(str(tmp_path), str(tmp_path / "out"), ledger_path=str(tmp_path / "no.json"))
    report = res["report"]
    assert report["mode"] == "all_flake_candidates"
    assert "c1" in report["case_ids"]  # mixed -> flake candidate
    assert "c2" not in report["case_ids"]  # always passing -> not a candidate
    assert (tmp_path / "out" / ALL_FLAKE_JSON_NAME).is_file()
    assert (tmp_path / "out" / ALL_FLAKE_MD_NAME).is_file()


def test_all_flake_candidates_markdown_has_boundaries():
    report = build_flake_candidates_comparison(
        [
            _entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])),
            _entry(_report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])),
        ],
        comparison_id="x",
        created_at="t",
    )
    md = render_flake_candidates_compare_markdown(report)
    assert "# Benchmark Report Compare" in md
    assert "eval.2 is a report-only comparison tool." in md.lower()


# ── 17-18. CLI ─────────────────────────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    out = tmp_path / "out"
    res = script.run_compare_benchmark_reports(
        repo_path=str(tmp_path),
        output_root=str(out),
        case_id="c1",
        ledger_path=str(tmp_path / "no.json"),
        comparison_id="cli",
        created_at="2026-06-20T00:00:00+00:00",
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).name == "c1_compare.json"
    assert Path(res["md_path"]).name == "c1_compare.md"
    assert (out / "c1_compare.json").is_file()
    assert (out / "c1_compare.md").is_file()
    report = json.loads((out / "c1_compare.json").read_text(encoding="utf-8"))
    assert report["case_id"] == "c1"
    assert report["comparison_id"] == "cli"


def test_cli_main_smoke(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(tmp_path), "--output-root", str(out), "--case-id", "c1",
         "--ledger", str(tmp_path / "no.json"), "--comparison-id", "s", "--created-at", "t"]
    )
    assert code == 0
    assert (out / "c1_compare.json").is_file()


def test_cli_requires_case_id_or_all_flake(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(SystemExit):
        script.main(["--repo-path", str(tmp_path), "--output-root", str(out)])


def test_cli_json_flag_prints_report(tmp_path, capsys):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(tmp_path), "--output-root", str(out), "--case-id", "c1",
         "--ledger", str(tmp_path / "no.json"), "--comparison-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["case_id"] == "c1"
    assert printed["report_kind"] == REPORT_KIND


def test_cli_all_flake_candidates(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True)]))
    _write_report(bench, "1001", _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)]))
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(tmp_path), "--output-root", str(out), "--all-flake-candidates",
         "--ledger", str(tmp_path / "no.json"), "--comparison-id", "a", "--created-at", "t"]
    )
    assert code == 0
    assert (out / ALL_FLAKE_JSON_NAME).is_file()


# ── 19. Markdown sections + boundaries ─────────────────────────────────────────

def test_markdown_contains_required_sections_and_boundaries():
    r1 = _report(
        "2026-06-20T00:00:00+00:00", run_id="r1",
        cases=[_case("c1", success=False, failure_kind_display="CODE / UNKNOWN", failure_cause="no signal")],
    )
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    report = build_case_comparison([_entry(r1), _entry(r2)], "c1", comparison_id="x", created_at="t")
    md = render_benchmark_report_compare_markdown(report)
    assert "# Benchmark Report Compare" in md
    low = md.lower()
    for section in (
        "## summary",
        "## classification",
        "## latest observation",
        "## report ordering",
        "## case timeline",
        "## evidence labels",
        "## failure notes",
        "## ledger cross-check",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    report = build_case_comparison(
        [_entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))],
        "c1",
        comparison_id="x",
        created_at="t",
    )
    low = render_benchmark_report_compare_markdown(report).lower()
    for boundary in (
        "eval.2 does not run benchmarks.",
        "eval.2 does not call models.",
        "eval.2 does not apply patches.",
        "eval.2 does not edit benchmark cases.",
        "eval.2 does not run validation.",
        "eval.2 does not contact network services.",
        "eval.2 does not launch workers.",
        "eval.2 is a report-only comparison tool.",
    ):
        assert boundary in low, boundary


def test_failure_summary_is_surfaced():
    data = _report(
        "2026-06-20T00:00:00+00:00", run_id="r1",
        cases=[_case("c1", success=False, failure_kind_display="CODE / UNKNOWN", failure_cause="no toolchain signal")],
    )
    report = build_case_comparison([_entry(data)], "c1", comparison_id="x", created_at="t")
    summary = report["case_timeline"][0]["failure_summary"]
    assert "CODE / UNKNOWN" in summary
    md = render_benchmark_report_compare_markdown(report)
    assert "no toolchain signal" in md


def test_guardrail_note_is_report_only():
    assert "report-only" in BENCHMARK_REPORT_COMPARE_GUARDRAIL_NOTE.lower()


# ── 20. guardrails all false ───────────────────────────────────────────────────

def test_guardrails_are_all_false():
    report = build_case_comparison(
        [_entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))],
        "c1",
        comparison_id="x",
        created_at="t",
    )
    guardrails = report["guardrails"]
    for key in (
        "benchmark_run_performed",
        "model_call_performed",
        "patch_applied",
        "benchmark_case_modified",
        "validation_run",
        "network_call_performed",
        "database_write_performed",
        "worker_launch_performed",
        "merge_performed",
    ):
        assert guardrails[key] is False, key


def test_report_has_all_required_fields():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    report = build_case_comparison([_entry(r1), _entry(r2)], "c1", comparison_id="cid", created_at="2026-06-22", repo_path=".")
    for key in (
        "comparison_id",
        "created_at",
        "repo_path",
        "input_glob",
        "case_id",
        "report_count",
        "matched_report_count",
        "loaded_report_count",
        "skipped_report_count",
        "report_ordering",
        "case_timeline",
        "latest_observation",
        "status_counts",
        "evidence_labels",
        "classification",
        "classification_reason",
        "ledger_reference",
        "warnings",
        "blockers",
        "guardrails",
    ):
        assert key in report, key
    assert report["report_kind"] == REPORT_KIND

    item = report["case_timeline"][0]
    for key in (
        "report_path",
        "run_id",
        "created_at",
        "ordering_key",
        "suite_scope",
        "case_id",
        "status",
        "passed",
        "failed",
        "duration_seconds",
        "models_used",
        "fallbacks",
        "tokens_total",
        "estimated_cost",
        "failure_summary",
        "notes",
    ):
        assert key in item, key


def test_build_does_not_mutate_entries():
    import copy

    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    entries = [_entry(data)]
    snap = copy.deepcopy(entries)
    build_case_comparison(entries, "c1", comparison_id="x", created_at="t")
    assert entries == snap


# ── 21. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "benchmark_report_compare.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "compare_benchmark_reports.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_or_ledger():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module == "core.benchmark_run_ledger", (
                    f"EVAL.2 may only import core.benchmark_run_ledger, got {module!r}"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "os.popen", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive token {bad!r}"


def test_no_benchmark_or_validation_execution():
    for bad in (
        "run_benchmarks",
        "run_benchmark(",
        "run_safe_validation",
        "SafeValidationCommand",
        "validation_execution",
        "create_managed_sandbox",
        "apply_candidate_in_sandbox",
    ):
        assert bad not in _BOTH, f"Found benchmark/validation execution token {bad!r}"


def test_no_model_or_llm_calls():
    for bad in (
        "anthropic",
        "openai",
        "litellm",
        "ollama",
        "bedrock",
        "generativeai",
        "claude",
        "codex",
        "gemini",
        "deepseek",
        "call_model(",
        "llm_call(",
    ):
        assert bad not in _BOTH, f"Found model/LLM client token {bad!r}"


def test_no_network_remote_or_automation():
    for bad in (
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "telegram",
        "n8n",
        "github",
        "api.telegram.org",
        "api.github.com",
        "send_message(",
        "sendMessage",
    ):
        assert bad not in _BOTH, f"Found network/remote/automation token {bad!r}"


def test_no_patch_generation_or_apply():
    for bad in ("generate_patch", "apply_patch", "patch_apply", "run_patch", "build_patch_plan"):
        assert bad not in _BOTH, f"Found patch token {bad!r}"


def test_no_benchmark_case_mutation():
    for bad in ("write_case(", "mutate_case(", "modify_case(", "edit_case("):
        assert bad not in _BOTH, f"Found benchmark-case mutation token {bad!r}"


def test_no_worker_launch_or_proposal():
    for bad in ("launch_worker(", "worker_launch(", "spawn_worker", "run_worker(", "import_proposal", "proposal_runner"):
        assert bad not in _BOTH, f"Found worker/proposal token {bad!r}"


def test_no_database_writes():
    for bad in ("sqlite3", "psycopg", "sqlalchemy", "pymongo", "INSERT INTO", "conn.execute(", "cursor.execute("):
        assert bad not in _BOTH, f"Found database token {bad!r}"


def test_no_auto_merge_or_git_push():
    for bad in (
        "auto_merge(",
        "perform_merge",
        "perform_auto_merge",
        "merge_to_real",
        "git_merge",
        "git push",
        "gh pr",
        "git commit",
        "git checkout",
    ):
        assert bad not in _BOTH, f"Found auto-merge / git token {bad!r}"
