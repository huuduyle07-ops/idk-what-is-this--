"""Tests for EVAL.3 - Flake Classification Report (report-only).

EVAL.3 reads existing EVAL.1 ledger artifacts, EVAL.2 compare artifacts, and
benchmark reports as fallback evidence. It classifies cases into conservative
stability buckets for human review. It does not run benchmarks, call models,
apply patches, edit benchmark cases, run validation, contact network services,
write to a database, launch workers, or merge.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.flake_classification_report import (
    CLASSIFICATIONS,
    DEFAULT_COMPARE_ROOT,
    DEFAULT_INPUT_GLOB,
    DEFAULT_LEDGER_PATH,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    build_flake_classification_report,
    render_flake_classification_markdown,
    write_flake_classification_report,
)
import scripts.create_flake_classification_report as script


def _case(
    case_id,
    *,
    pass_count=0,
    fail_count=0,
    seen_runs=None,
    latest_status="",
    notes=None,
    latest_run_id="",
    latest_scope="",
):
    return {
        "case_id": case_id,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "seen_runs": seen_runs if seen_runs is not None else pass_count + fail_count,
        "latest_status": latest_status,
        "latest_run_id": latest_run_id,
        "latest_scope": latest_scope,
        "notes": list(notes or []),
    }


def _ledger(cases=None, flakes=None):
    return {
        "report_kind": "benchmark_run_ledger",
        "case_history": list(cases or []),
        "flake_candidates": list(flakes or []),
        "latest_run_summary": {"run_id": "latest-ledger-run"},
    }


def _obs(case_id, status, created_at, *, run_id=None, scope="full", notes=None):
    return {
        "case_id": case_id,
        "status": status,
        "created_at": created_at,
        "run_id": run_id or created_at,
        "suite_scope": scope,
        "notes": list(notes or [f"scope:{scope}"]),
    }


def _compare(case_id, timeline=None, *, classification=None, labels=None):
    timeline = list(timeline or [])
    counts = {
        "pass": sum(1 for item in timeline if item.get("status") == "pass"),
        "fail": sum(1 for item in timeline if item.get("status") == "fail"),
        "skipped": sum(1 for item in timeline if item.get("status") == "skipped"),
    }
    latest = dict(timeline[-1]) if timeline else None
    return {
        "report_kind": "benchmark_report_compare",
        "case_id": case_id,
        "classification": classification or "no_evidence",
        "evidence_labels": list(labels or []),
        "status_counts": counts,
        "case_timeline": timeline,
        "latest_observation": latest,
        "ledger_reference": {"case_is_flake_candidate": False, "ledger_notes": []},
    }


def _case_result(name, success=True, *, flaky=False):
    return {
        "name": name,
        "success": success,
        "skipped": False,
        "duration_sec": 1.0,
        "language": "python",
        "category": "bugfix",
        "difficulty": "easy",
        "flaky": flaky,
    }


def _bench_report(created_at, *, run_id=None, cases=None, filters=None):
    results = list(cases or [])
    passed = sum(1 for item in results if item.get("success") and not item.get("skipped"))
    failed = sum(1 for item in results if not item.get("success") and not item.get("skipped"))
    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": round(passed / total, 6) if total else 0.0,
        "filters": filters or {"case": None, "suite": None},
        "results": results,
        "brain_stamp": {"created_at": created_at, "brain_stamp_id": run_id or created_at},
    }


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_benchmark(repo: Path, name: str, data: dict) -> Path:
    return _write_json(repo / ".agent" / "benchmarks" / f"benchmark_report_{name}.json", data)


def _by_case(report):
    out = {}
    for bucket in (
        "stable_cases",
        "likely_flakes",
        "likely_broken_cases",
        "insufficient_history_cases",
        "needs_rerun_cases",
    ):
        for item in report[bucket]:
            out[item["case_id"]] = item
    return out


def test_no_artifacts_produces_empty_report_with_warning(tmp_path):
    result = write_flake_classification_report(str(tmp_path), str(tmp_path / "out"), report_id="r", created_at="t")
    report = result["report"]
    assert report["case_count"] == 0
    assert report["stable_cases"] == []
    assert report["likely_flakes"] == []
    assert report["blockers"] == []
    assert any("no flake classification evidence" in w.lower() for w in report["warnings"])
    assert (tmp_path / "out" / JSON_NAME).is_file()
    assert (tmp_path / "out" / MD_NAME).is_file()


def test_malformed_ledger_is_skipped_with_warning(tmp_path):
    ledger = tmp_path / DEFAULT_LEDGER_PATH
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{ bad json", encoding="utf-8")
    result = write_flake_classification_report(str(tmp_path), str(tmp_path / "out"), report_id="r", created_at="t")
    report = result["report"]
    assert report["source_summary"]["ledger_loaded"] is False
    assert any("ledger" in w.lower() and "could not be read" in w.lower() for w in report["warnings"])
    assert report["source_summary"]["skipped_artifacts"]


def test_malformed_compare_report_is_skipped_with_warning(tmp_path):
    root = tmp_path / DEFAULT_COMPARE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    (root / "bad.json").write_text("{ bad json", encoding="utf-8")
    _write_json(root / "good.json", _compare("c1", [_obs("c1", "pass", "2026-06-20")], classification="single_pass_only"))
    result = write_flake_classification_report(str(tmp_path), str(tmp_path / "out"), report_id="r", created_at="t")
    report = result["report"]
    assert report["source_summary"]["compare_reports_loaded"] == 1
    assert any("malformed compare report" in w.lower() for w in report["warnings"])
    assert report["source_summary"]["skipped_artifacts"]


def test_stable_repeated_passes_classify_as_stable():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=3, fail_count=0, latest_status="pass")]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "stable"
    assert case["recommended_action"] == "no_action"


def test_mixed_pass_fail_classifies_as_likely_flake():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=2, fail_count=1, latest_status="pass")]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "likely_flake"
    assert "mixed_pass_fail_history" in case["evidence_labels"]


def test_recovered_failure_classifies_as_likely_flake():
    report = build_flake_classification_report(
        ledger_data=_ledger([
            _case("c1", pass_count=1, fail_count=1, latest_status="pass", notes=["recovered_on_later_run"])
        ]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "likely_flake"
    assert "recovered_on_later_run" in case["evidence_labels"]


def test_repeated_failures_with_no_pass_classify_as_likely_broken():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=0, fail_count=3, latest_status="fail")]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "likely_broken"
    assert case["recommended_action"] == "inspect_failure_notes"


def test_single_failure_classifies_as_needs_rerun():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=0, fail_count=1, latest_status="fail")]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "needs_rerun"
    assert case["recommended_action"] == "rerun_single_case"


def test_single_pass_classifies_as_insufficient_history():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=1, fail_count=0, latest_status="pass")]),
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "insufficient_history"
    assert case["recommended_action"] == "monitor"


def test_eval2_likely_flake_overrides_weak_ledger_ambiguity():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=0, fail_count=1, latest_status="fail")]),
        compare_reports=[_compare("c1", [_obs("c1", "fail", "2026-06-20")], classification="likely_flake")],
        report_id="r",
        created_at="t",
    )
    case = _by_case(report)["c1"]
    assert case["classification"] == "likely_flake"
    assert "eval2_likely_flake" in case["evidence_labels"]


def test_latest_fail_with_mixed_history_remains_likely_flake():
    comparison = _compare(
        "c1",
        [_obs("c1", "pass", "2026-06-20"), _obs("c1", "fail", "2026-06-21")],
        classification="likely_flake",
        labels=["mixed_pass_fail_history", "latest_is_fail"],
    )
    report = build_flake_classification_report(compare_reports=[comparison], report_id="r", created_at="t")
    case = _by_case(report)["c1"]
    assert case["classification"] == "likely_flake"
    assert case["latest_status"] == "fail"
    assert case["recommended_action"] == "rerun_single_case"


def test_recommended_actions_are_conservative():
    report = build_flake_classification_report(
        ledger_data=_ledger([
            _case("broken", pass_count=0, fail_count=2, latest_status="fail"),
            _case("single", pass_count=0, fail_count=1, latest_status="fail"),
            _case("flake", pass_count=1, fail_count=1, latest_status="pass"),
        ]),
        report_id="r",
        created_at="t",
    )
    cases = _by_case(report)
    assert cases["broken"]["recommended_action"] == "inspect_failure_notes"
    assert cases["single"]["recommended_action"] == "rerun_single_case"
    assert cases["flake"]["recommended_action"] == "monitor"
    actions = {item["action"] for item in report["recommended_actions"]}
    assert "do_not_patch_yet" in actions
    assert "rerun_single_case" in actions
    assert not any("auto" in action or "merge" in action or "patch" == action for action in actions)


def test_source_summary_records_ledger_compare_and_benchmark_coverage(tmp_path):
    _write_json(
        tmp_path / DEFAULT_LEDGER_PATH,
        _ledger([_case("c1", pass_count=2, fail_count=0, latest_status="pass")]),
    )
    _write_json(
        tmp_path / DEFAULT_COMPARE_ROOT / "c1_compare.json",
        _compare("c1", [_obs("c1", "pass", "2026-06-20")], classification="single_pass_only"),
    )
    _write_benchmark(tmp_path, "1000", _bench_report("2026-06-20", cases=[_case_result("c1")]))
    result = write_flake_classification_report(str(tmp_path), str(tmp_path / "out"), report_id="r", created_at="t")
    summary = result["report"]["source_summary"]
    assert summary["ledger_loaded"] is True
    assert summary["ledger_case_count"] == 1
    assert summary["compare_reports_loaded"] == 1
    assert summary["benchmark_reports_loaded"] == 0
    assert summary["fallback_used"] is False


def test_fallback_to_benchmark_reports_when_ledger_and_compare_missing(tmp_path):
    _write_benchmark(tmp_path, "1000", _bench_report("2026-06-20", run_id="r1", cases=[_case_result("c1")]))
    _write_benchmark(tmp_path, "1001", _bench_report("2026-06-21", run_id="r2", cases=[_case_result("c1")]))
    result = write_flake_classification_report(str(tmp_path), str(tmp_path / "out"), report_id="r", created_at="t")
    report = result["report"]
    case = _by_case(report)["c1"]
    assert case["classification"] == "stable"
    assert case["source"] == "benchmark_reports"
    assert report["source_summary"]["fallback_used"] is True
    assert report["source_summary"]["benchmark_reports_loaded"] == 2


def test_output_ordering_is_deterministic():
    cases = [
        _case("b_case", pass_count=2, fail_count=0, latest_status="pass"),
        _case("a_case", pass_count=0, fail_count=2, latest_status="fail"),
        _case("c_case", pass_count=1, fail_count=1, latest_status="pass"),
    ]
    a = build_flake_classification_report(ledger_data=_ledger(cases), report_id="r", created_at="t")
    b = build_flake_classification_report(ledger_data=_ledger(list(reversed(cases))), report_id="r", created_at="t")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert [case["case_id"] for case in a["stable_cases"]] == ["b_case"]
    assert [case["case_id"] for case in a["likely_flakes"]] == ["c_case"]
    assert [case["case_id"] for case in a["likely_broken_cases"]] == ["a_case"]


def test_limit_works_deterministically():
    report = build_flake_classification_report(
        ledger_data=_ledger([
            _case("stable", pass_count=3, fail_count=0, latest_status="pass"),
            _case("broken", pass_count=0, fail_count=2, latest_status="fail"),
            _case("flake", pass_count=1, fail_count=1, latest_status="fail"),
        ]),
        report_id="r",
        created_at="t",
        limit=2,
    )
    assert report["case_count"] == 2
    assert report["classification_counts"]["likely_broken"] == 1
    assert report["classification_counts"]["likely_flake"] == 1
    assert report["classification_counts"]["stable"] == 0
    assert any("limited to 2" in w.lower() for w in report["warnings"])


def test_markdown_contains_required_sections_and_boundaries():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=1, fail_count=1, latest_status="pass")]),
        report_id="r",
        created_at="t",
    )
    md = render_flake_classification_markdown(report)
    assert "# Flake Classification Report" in md
    low = md.lower()
    for section in (
        "## summary",
        "## source coverage",
        "## classification counts",
        "## likely flakes",
        "## likely broken cases",
        "## needs rerun",
        "## stable cases",
        "## recommended human actions",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section
    for boundary in (
        "eval.3 does not run benchmarks.",
        "eval.3 does not call models.",
        "eval.3 does not apply patches.",
        "eval.3 does not edit benchmark cases.",
        "eval.3 does not run validation.",
        "eval.3 does not contact network services.",
        "eval.3 does not launch workers.",
        "eval.3 is a report-only triage tool.",
    ):
        assert boundary in low, boundary


def test_cli_writes_json_and_markdown(tmp_path):
    _write_json(
        tmp_path / DEFAULT_LEDGER_PATH,
        _ledger([_case("c1", pass_count=2, fail_count=0, latest_status="pass")]),
    )
    out = tmp_path / "out"
    result = script.run_create_flake_classification_report(
        repo_path=str(tmp_path),
        output_root=str(out),
        report_id="cli",
        created_at="2026-06-22T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    data = json.loads((out / JSON_NAME).read_text(encoding="utf-8"))
    assert data["report_id"] == "cli"
    assert data["report_kind"] == REPORT_KIND


def test_cli_json_flag_prints_summary_json(tmp_path, capsys):
    _write_json(
        tmp_path / DEFAULT_LEDGER_PATH,
        _ledger([_case("c1", pass_count=2, fail_count=0, latest_status="pass")]),
    )
    out = tmp_path / "out"
    code = script.main(
        [
            "--repo-path",
            str(tmp_path),
            "--output-root",
            str(out),
            "--report-id",
            "json",
            "--created-at",
            "t",
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_id"] == "json"
    assert printed["classification_counts"]["stable"] == 1


def test_guardrails_are_all_false():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=2, fail_count=0, latest_status="pass")]),
        report_id="r",
        created_at="t",
    )
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
        assert report["guardrails"][key] is False, key


def test_report_has_required_json_fields():
    report = build_flake_classification_report(
        ledger_data=_ledger([_case("c1", pass_count=1, fail_count=1, latest_status="pass")]),
        report_id="rid",
        created_at="created",
        repo_path=".",
        ledger_path=DEFAULT_LEDGER_PATH,
        compare_root=DEFAULT_COMPARE_ROOT,
        input_glob=DEFAULT_INPUT_GLOB,
    )
    for key in (
        "report_id",
        "created_at",
        "repo_path",
        "ledger_path",
        "compare_root",
        "input_glob",
        "source_summary",
        "case_count",
        "classification_counts",
        "stable_cases",
        "likely_flakes",
        "likely_broken_cases",
        "insufficient_history_cases",
        "needs_rerun_cases",
        "recommended_actions",
        "top_risks",
        "warnings",
        "blockers",
        "guardrails",
    ):
        assert key in report, key
    case = report["likely_flakes"][0]
    for key in (
        "case_id",
        "classification",
        "confidence",
        "evidence_labels",
        "pass_count",
        "fail_count",
        "seen_runs",
        "latest_status",
        "latest_run_id",
        "latest_scope",
        "reason",
        "recommended_action",
        "source",
    ):
        assert key in case, key
    assert tuple(CLASSIFICATIONS) == (
        "stable",
        "likely_flake",
        "likely_broken",
        "insufficient_history",
        "needs_rerun",
        "no_evidence",
    )


_CORE = Path(__file__).parent.parent / "core" / "flake_classification_report.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_flake_classification_report.py"


def _sources():
    return _CORE.read_text(encoding="utf-8") + "\n" + _SCRIPT.read_text(encoding="utf-8")


def test_core_imports_are_stdlib_or_eval_layers():
    allowed_top = {"__future__", "json", "pathlib", "typing", "core"}
    tree = ast.parse(_CORE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            top = module.split(".")[0]
            assert top in allowed_top, f"Unexpected import in core: {module!r}"
            if top == "core":
                assert module == "core.benchmark_run_ledger", module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed_top, f"Unexpected import in core: {alias.name!r}"


def test_source_contains_no_forbidden_execution_or_remote_behavior():
    both = _sources()
    forbidden = (
        "subprocess",
        "Popen",
        "os.system",
        "os.popen",
        "check_output",
        "check_call",
        "run_benchmarks",
        "run_benchmark(",
        "run_safe_validation",
        "validation_execution",
        "generate_patch",
        "apply_patch",
        "patch_apply",
        "write_case(",
        "mutate_case(",
        "modify_case(",
        "edit_case(",
        "launch_worker(",
        "worker_launch(",
        "spawn_worker",
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "pymongo",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
        "aiohttp",
        "webhook",
        "telegram",
        "n8n",
        "api.telegram.org",
        "api.github.com",
        "auto_merge(",
        "perform_merge",
        "git push",
        "gh pr",
    )
    for bad in forbidden:
        assert bad not in both, f"Found forbidden behavior token {bad!r}"
