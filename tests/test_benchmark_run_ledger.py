"""Tests for EVAL.1 — Live Benchmark Run Ledger (report-only).

EVAL.1 reads existing benchmark report artifacts and summarizes live benchmark
history into a deterministic ledger (run history, per-case history, suspected flake
candidates, model usage, cost). It does not run benchmarks, call models, apply
patches, edit benchmark cases, run validation, contact network services, write to a
database, launch workers, or merge. The input reports are read only and never
mutated.

Covers the prescribed cases:
1.  missing benchmark directory produces an empty ledger with a warning.
2.  a malformed report is skipped with a warning.
3.  a single all-pass report produces no flake candidates.
4.  a single report with a failure records the failed case but does not overclaim a flake.
5.  pass then fail for the same case marks mixed history.
6.  fail then pass for the same case marks recovered later.
7.  the latest run summary is deterministic.
8.  the model usage summary aggregates draft/reviewer models.
9.  the fallback count is captured.
10. the token/cost summary is captured when present.
11. the case duration is captured when present.
12. report ordering is deterministic.
13. the limit works deterministically.
14. input reports are not modified.
15. the Markdown contains the required sections and boundaries.
16. the CLI writes JSON + Markdown.
17. the CLI --json prints the summary JSON.
18. the guardrails are all false.
19. the source contains no forbidden benchmark-execution / model / network / patch /
    validation / worker / database / merge behavior.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.benchmark_run_ledger import (
    BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE,
    DEFAULT_INPUT_GLOB,
    LEDGER_JSON_NAME,
    LEDGER_MD_NAME,
    REPORT_KIND,
    build_ledger,
    load_benchmark_reports,
    render_benchmark_run_ledger_markdown,
    summarize_run,
    write_benchmark_run_ledger,
)
import scripts.create_benchmark_run_ledger as script


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
):
    return {
        "name": name,
        "success": success,
        "skipped": skipped,
        "duration_sec": duration_sec,
        "language": language,
        "category": category,
        "difficulty": difficulty,
        "flaky": flaky,
    }


def _report(
    created_at,
    *,
    run_id=None,
    cases=None,
    filters=None,
    models_used=None,
    fallbacks=0,
    total_tokens=None,
    input_tokens=0,
    output_tokens=0,
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
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "brain_stamp": {"created_at": created_at, "brain_stamp_id": run_id or created_at},
    }
    if total_tokens is not None:
        data["total_tokens"] = total_tokens
    if cost is not None:
        data["total_estimated_cost_usd"] = cost
    return data


def _entry(data, path=None):
    stamp = data["brain_stamp"]["created_at"]
    return {"path": path or f".agent/benchmarks/benchmark_report_{stamp}.json", "data": data}


def _write_report(bench_dir: Path, epoch: str, data: dict) -> Path:
    path = bench_dir / f"benchmark_report_{epoch}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _bench(tmp_path: Path) -> Path:
    bench = tmp_path / ".agent" / "benchmarks"
    bench.mkdir(parents=True, exist_ok=True)
    return bench


# ── 1. missing benchmark directory → empty ledger with warning ─────────────────

def test_missing_benchmark_directory_produces_empty_ledger(tmp_path):
    out = tmp_path / "out"
    result = write_benchmark_run_ledger(str(tmp_path), str(out), ledger_id="l", created_at="t")
    report = result["report"]
    assert report["run_count"] == 0
    assert report["case_count"] == 0
    assert report["runs"] == []
    assert report["case_history"] == []
    assert report["flake_candidates"] == []
    assert report["latest_run_summary"] is None
    assert any("no benchmark reports" in w.lower() for w in report["warnings"])
    assert (out / LEDGER_JSON_NAME).is_file()
    assert (out / LEDGER_MD_NAME).is_file()


# ── 2. malformed report skipped with warning ───────────────────────────────────

def test_malformed_report_is_skipped_with_warning(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="good", cases=[_case("c1")]))
    (bench / "benchmark_report_1001.json").write_text("{ not valid json", encoding="utf-8")

    loaded = load_benchmark_reports(str(tmp_path), DEFAULT_INPUT_GLOB)
    assert len(loaded["entries"]) == 1
    assert loaded["skipped"] == 1
    assert any("malformed" in w.lower() for w in loaded["warnings"])

    report = write_benchmark_run_ledger(str(tmp_path), str(tmp_path / "out"), ledger_id="l", created_at="t")["report"]
    assert report["run_count"] == 1
    assert any("malformed" in w.lower() for w in report["warnings"])


def test_non_object_report_is_skipped(tmp_path):
    bench = _bench(tmp_path)
    (bench / "benchmark_report_1002.json").write_text("[1, 2, 3]", encoding="utf-8")
    loaded = load_benchmark_reports(str(tmp_path), DEFAULT_INPUT_GLOB)
    assert loaded["entries"] == []
    assert loaded["skipped"] == 1


# ── 3. single all-pass report → no flake candidates ────────────────────────────

def test_single_all_pass_report_has_no_flake_candidates():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1"), _case("c2")])
    report = build_ledger([_entry(data)], ledger_id="l", created_at="t")
    assert report["flake_candidates"] == []
    assert report["run_count"] == 1
    assert report["case_count"] == 2
    for case in report["case_history"]:
        assert case["suspected_flaky"] is False


# ── 4. single failure records the case but does not overclaim a flake ──────────

def test_single_failure_records_case_without_overclaiming_flake():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    report = build_ledger([_entry(data)], ledger_id="l", created_at="t")
    assert report["flake_candidates"] == []
    run = report["runs"][0]
    assert run["failed_cases"] == ["c1"]
    assert run["failed"] == 1
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["suspected_flaky"] is False
    assert "single_failure_observed" in hist["c1"]["notes"]


# ── 5. pass then fail → mixed history ──────────────────────────────────────────

def test_pass_then_fail_marks_mixed_history():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)])
    report = build_ledger([_entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["suspected_flaky"] is True
    assert "mixed_pass_fail_history" in hist["c1"]["notes"]
    assert hist["c1"]["pass_count"] == 1
    assert hist["c1"]["fail_count"] == 1
    assert any(f["case_id"] == "c1" for f in report["flake_candidates"])


# ── 6. fail then pass → recovered later ────────────────────────────────────────

def test_fail_then_pass_marks_recovered_later():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    report = build_ledger([_entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["suspected_flaky"] is True
    assert "mixed_pass_fail_history" in hist["c1"]["notes"]
    assert "recovered_on_later_run" in hist["c1"]["notes"]
    assert hist["c1"]["latest_status"] == "pass"


def test_fail_then_pass_is_order_independent():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    forward = build_ledger([_entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    reverse = build_ledger([_entry(r2), _entry(r1)], ledger_id="l", created_at="t")
    assert forward["case_history"] == reverse["case_history"]


# ── the live-flake reason: suite failure that passes a single-case rerun ────────

def test_suite_failure_passed_in_single_case_rerun_is_flaky():
    suite = _report(
        "2026-06-20T00:00:00+00:00",
        run_id="suite1",
        cases=[_case("c1", success=False), _case("c2", success=True)],
    )
    rerun = _report(
        "2026-06-21T00:00:00+00:00",
        run_id="rerun1",
        cases=[_case("c1", success=True)],
        filters={"case": "c1", "suite": None},
    )
    report = build_ledger([_entry(suite), _entry(rerun)], ledger_id="l", created_at="t")
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["suspected_flaky"] is True
    assert "passed_in_single_case_rerun" in hist["c1"]["notes"]


def test_within_run_retry_flake_is_detected():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=True, flaky=True)])
    report = build_ledger([_entry(data)], ledger_id="l", created_at="t")
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["suspected_flaky"] is True
    assert "within_run_retry_flake" in hist["c1"]["notes"]


# ── 7. latest run summary is deterministic ─────────────────────────────────────

def test_latest_run_summary_is_deterministic():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)])
    r3 = _report("2026-06-22T00:00:00+00:00", run_id="r3", cases=[_case("c1")])
    a = build_ledger([_entry(r1), _entry(r2), _entry(r3)], ledger_id="l", created_at="t")
    b = build_ledger([_entry(r3), _entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    assert a["latest_run_summary"] == b["latest_run_summary"]
    assert a["latest_run_summary"]["run_id"] == "r3"


# ── 8. model usage summary aggregates draft/reviewer models ────────────────────

def test_model_usage_summary_aggregates_roles():
    r1 = _report(
        "2026-06-20T00:00:00+00:00",
        run_id="r1",
        cases=[_case("c1")],
        models_used={"reviewer": {"rev-a": 1}, "draft": {"draft-a": 1}},
    )
    r2 = _report(
        "2026-06-21T00:00:00+00:00",
        run_id="r2",
        cases=[_case("c1")],
        models_used={"draft": {"draft-a": 1}, "reviewer": {"rev-b": 1}},
    )
    report = build_ledger([_entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    usage = report["model_usage_summary"]
    assert usage["by_role"]["draft"]["draft-a"] == 2
    assert usage["by_role"]["reviewer"]["rev-a"] == 1
    assert usage["by_role"]["reviewer"]["rev-b"] == 1
    assert usage["by_model"]["draft-a"] == 2
    assert usage["total_model_invocations"] == 4


# ── 9. fallback count is captured ──────────────────────────────────────────────

def test_fallback_count_is_captured():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")], fallbacks=3)
    report = build_ledger([_entry(r1)], ledger_id="l", created_at="t")
    assert report["runs"][0]["fallbacks"] == 3
    assert report["cost_summary"]["total_fallbacks"] == 3


# ── 10. token/cost summary captured when present ───────────────────────────────

def test_token_and_cost_summary_captured_when_present():
    r1 = _report(
        "2026-06-20T00:00:00+00:00",
        run_id="r1",
        cases=[_case("c1")],
        total_tokens=4006,
        input_tokens=3111,
        output_tokens=895,
        cost=0.001062,
    )
    report = build_ledger([_entry(r1)], ledger_id="l", created_at="t")
    run = report["runs"][0]
    assert run["tokens_total"] == 4006
    assert run["estimated_cost"] == 0.001062
    cost = report["cost_summary"]
    assert cost["tokens_total"] == 4006
    assert cost["input_tokens_total"] == 3111
    assert cost["output_tokens_total"] == 895
    assert cost["estimated_cost_usd_total"] == 0.001062
    assert cost["runs_with_cost"] == 1
    assert cost["runs_with_tokens"] == 1


def test_missing_token_cost_is_none_not_zero():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    report = build_ledger([_entry(r1)], ledger_id="l", created_at="t")
    run = report["runs"][0]
    assert run["tokens_total"] is None
    assert run["estimated_cost"] is None
    assert report["cost_summary"]["runs_with_cost"] == 0


# ── 11. case duration captured when present ────────────────────────────────────

def test_case_duration_is_captured_when_present():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", duration_sec=142.76)])
    report = build_ledger([_entry(r1)], ledger_id="l", created_at="t")
    hist = {c["case_id"]: c for c in report["case_history"]}
    assert hist["c1"]["latest_duration_seconds"] == 142.76


# ── 12. report ordering is deterministic ───────────────────────────────────────

def test_report_ordering_is_deterministic():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=False)])
    r3 = _report("2026-06-22T00:00:00+00:00", run_id="r3", cases=[_case("c1")])
    a = build_ledger([_entry(r1), _entry(r2), _entry(r3)], ledger_id="fix", created_at="t")
    b = build_ledger([_entry(r3), _entry(r2), _entry(r1)], ledger_id="fix", created_at="t")
    assert [run["run_id"] for run in a["runs"]] == ["r1", "r2", "r3"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ── 13. limit works deterministically ──────────────────────────────────────────

def test_limit_keeps_most_recent_runs_deterministically():
    reports = [
        _report(f"2026-06-2{i}T00:00:00+00:00", run_id=f"r{i}", cases=[_case("c1")])
        for i in range(1, 5)
    ]
    entries = [_entry(r) for r in reports]
    a = build_ledger(list(entries), ledger_id="l", created_at="t", limit=2)
    b = build_ledger(list(reversed(entries)), ledger_id="l", created_at="t", limit=2)
    assert a["run_count"] == 2
    assert [run["run_id"] for run in a["runs"]] == ["r3", "r4"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert any("limited" in w.lower() for w in a["warnings"])


# ── 14. input reports are not modified ─────────────────────────────────────────

def test_input_report_files_are_not_modified(tmp_path):
    bench = _bench(tmp_path)
    path = _write_report(
        bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)])
    )
    before = path.read_bytes()
    write_benchmark_run_ledger(str(tmp_path), str(tmp_path / "out"), ledger_id="l", created_at="t")
    assert path.read_bytes() == before


def test_build_ledger_does_not_mutate_entries():
    data = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")])
    entries = [_entry(data)]
    snap = copy.deepcopy(entries)
    build_ledger(entries, ledger_id="l", created_at="t")
    assert entries == snap


# ── 15. Markdown sections + boundaries ─────────────────────────────────────────

def test_markdown_contains_required_sections_and_boundaries():
    r1 = _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)], models_used={"draft": {"d": 1}})
    r2 = _report("2026-06-21T00:00:00+00:00", run_id="r2", cases=[_case("c1", success=True)])
    report = build_ledger([_entry(r1), _entry(r2)], ledger_id="l", created_at="t")
    md = render_benchmark_run_ledger_markdown(report)
    assert "# Live Benchmark Run Ledger" in md
    low = md.lower()
    for section in (
        "## summary",
        "## latest run",
        "## run history",
        "## case history",
        "## flake candidates",
        "## model usage",
        "## cost summary",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_markdown_states_all_boundaries():
    report = build_ledger(
        [_entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))],
        ledger_id="l",
        created_at="t",
    )
    low = render_benchmark_run_ledger_markdown(report).lower()
    for boundary in (
        "eval.1 does not run benchmarks.",
        "eval.1 does not call models.",
        "eval.1 does not apply patches.",
        "eval.1 does not edit benchmark cases.",
        "eval.1 does not run validation.",
        "eval.1 does not contact network services.",
        "eval.1 does not launch workers.",
        "eval.1 is a report-only ledger.",
    ):
        assert boundary in low, boundary


def test_guardrail_note_is_report_only():
    assert "report-only" in BENCHMARK_RUN_LEDGER_GUARDRAIL_NOTE.lower()


# ── 16-17. CLI ─────────────────────────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    out = tmp_path / "out"
    res = script.run_create_benchmark_run_ledger(
        repo_path=str(tmp_path), output_root=str(out), ledger_id="cli", created_at="2026-06-20T00:00:00+00:00"
    )
    assert res["ok"] is True
    assert Path(res["json_path"]).name == LEDGER_JSON_NAME
    assert Path(res["md_path"]).name == LEDGER_MD_NAME
    assert (out / LEDGER_JSON_NAME).is_file()
    assert (out / LEDGER_MD_NAME).is_file()
    report = json.loads((out / LEDGER_JSON_NAME).read_text(encoding="utf-8"))
    assert report["ledger_id"] == "cli"
    assert report["run_count"] == 1


def test_cli_main_smoke_on_empty_repo(tmp_path):
    out = tmp_path / "out"
    code = script.main(["--repo-path", str(tmp_path), "--output-root", str(out), "--ledger-id", "s", "--created-at", "t"])
    assert code == 0
    assert (out / LEDGER_JSON_NAME).is_file()
    report = json.loads((out / LEDGER_JSON_NAME).read_text(encoding="utf-8"))
    assert report["run_count"] == 0


def test_cli_json_flag_prints_report(tmp_path, capsys):
    bench = _bench(tmp_path)
    _write_report(bench, "1000", _report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(tmp_path), "--output-root", str(out), "--ledger-id", "j", "--created-at", "t", "--json"]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["ledger_id"] == "j"
    assert printed["report_kind"] == REPORT_KIND


def test_cli_limit_flag(tmp_path):
    bench = _bench(tmp_path)
    for i in range(1, 4):
        _write_report(bench, f"100{i}", _report(f"2026-06-2{i}T00:00:00+00:00", run_id=f"r{i}", cases=[_case("c1")]))
    out = tmp_path / "out"
    code = script.main(
        ["--repo-path", str(tmp_path), "--output-root", str(out), "--ledger-id", "x", "--created-at", "t", "--limit", "1"]
    )
    assert code == 0
    report = json.loads((out / LEDGER_JSON_NAME).read_text(encoding="utf-8"))
    assert report["run_count"] == 1


# ── 18. guardrails are all false ───────────────────────────────────────────────

def test_guardrails_are_all_false():
    report = build_ledger(
        [_entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1")]))],
        ledger_id="l",
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


# ── required field coverage ────────────────────────────────────────────────────

def test_report_has_all_required_fields():
    report = build_ledger(
        [_entry(_report("2026-06-20T00:00:00+00:00", run_id="r1", cases=[_case("c1", success=False)]))],
        ledger_id="lid",
        created_at="2026-06-22",
        repo_path=".",
        input_glob=DEFAULT_INPUT_GLOB,
    )
    for key in (
        "ledger_id",
        "created_at",
        "repo_path",
        "input_glob",
        "run_count",
        "case_count",
        "runs",
        "case_history",
        "flake_candidates",
        "latest_run_summary",
        "model_usage_summary",
        "cost_summary",
        "warnings",
        "blockers",
        "guardrails",
    ):
        assert key in report, key
    assert report["ledger_id"] == "lid"
    assert report["report_kind"] == REPORT_KIND

    run = report["runs"][0]
    for key in (
        "report_path",
        "run_id",
        "created_at",
        "total_cases",
        "passed",
        "failed",
        "success_rate",
        "failed_cases",
        "models_used",
        "fallbacks",
        "tokens_total",
        "estimated_cost",
        "duration_seconds",
        "loaded",
        "warnings",
    ):
        assert key in run, key

    case = report["case_history"][0]
    for key in (
        "case_id",
        "seen_runs",
        "pass_count",
        "fail_count",
        "latest_status",
        "latest_duration_seconds",
        "languages",
        "categories",
        "difficulties",
        "suspected_flaky",
        "notes",
    ):
        assert key in case, key


def test_summarize_run_derives_aggregates_from_results_for_old_reports():
    # An older report with no top-level aggregates: counts derive from results.
    data = {
        "results": [_case("c1", success=True), _case("c2", success=False)],
        "brain_stamp": {"created_at": "2026-06-20T00:00:00+00:00"},
    }
    run = summarize_run(".agent/benchmarks/benchmark_report_900.json", data)
    assert run["total_cases"] == 2
    assert run["passed"] == 1
    assert run["failed"] == 1
    assert run["failed_cases"] == ["c2"]
    assert any("total" in w.lower() for w in run["warnings"])


def test_run_id_falls_back_to_filename_stem():
    data = {"results": [], "total": 0, "passed": 0, "failed": 0}
    run = summarize_run(".agent/benchmarks/benchmark_report_777.json", data)
    assert run["run_id"] == "benchmark_report_777"


# ── 19. forbidden-token / import guards (source-only) ──────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "benchmark_run_ledger.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_benchmark_run_ledger.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_are_stdlib_only():
    allowed_top = {"__future__", "glob", "json", "pathlib", "typing"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            assert top != "core", f"EVAL.1 core must not import other core modules: {module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_no_execution_primitives():
    for bad in ("subprocess", "Popen", "os.system", "os.popen", "check_output", "check_call", "shutil", "copytree"):
        assert bad not in _BOTH, f"Found execution primitive token {bad!r}"


def test_no_benchmark_or_validation_execution():
    # The ledger reads reports; it never runs a benchmark or validation. Guardrail
    # field names ("benchmark_run_performed", "validation_run") are data, so we grep
    # only the command / call shapes.
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
