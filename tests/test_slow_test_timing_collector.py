"""Tests for OPS.TEST.2 - Slow Test Timing Collector.

OPS.TEST.2 is report-only. It parses or accepts timing data so operators can see
where test runtime goes without deleting tests, weakening coverage, hiding
failures, or running pytest from the collector.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.slow_test_timing_collector import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_READY,
    STATUS_READY_WITH_WARNINGS,
    build_slow_test_timing_report,
    parse_timing_text,
    render_slow_test_timing_report_markdown,
    write_slow_test_timing_report,
)
import scripts.create_slow_test_timing_report as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "slow_test_timing_collector.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_slow_test_timing_report.py"


def _report(**kwargs) -> dict:
    return build_slow_test_timing_report(
        repo_root=PROJECT_ROOT,
        report_id="ops-test-2-test",
        created_at="2026-07-09T00:00:00+09:00",
        **kwargs,
    )


def test_constants_match_ops_test_2_contract():
    assert REPORT_KIND == "slow_test_timing_report"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ops" / "slow_test_timing_collector"
    assert JSON_NAME == "slow_test_timing_report.json"
    assert MD_NAME == "slow_test_timing_report.md"


def test_parses_pytest_duration_lines_and_aggregates_tests_and_files():
    text = "\n".join(
        [
            "12.34s call     tests/test_example.py::test_alpha",
            "3.21s setup    tests/test_example.py::test_alpha",
            "0.50s call     tests/test_other.py::test_beta",
            "not a timing line",
        ]
    )

    report = _report(timing_text=text, allow_sample_timing=False)

    assert report["report_status"] == STATUS_READY
    assert report["timing_source_type"] == "parsed_pytest_durations"
    assert report["collected_test_count"] == 2
    assert report["collected_file_count"] == 2
    assert report["total_observed_runtime_seconds"] == 16.05
    assert report["slowest_tests"][0]["nodeid"] == "tests/test_example.py::test_alpha"
    assert report["slowest_tests"][0]["total_seconds"] == 15.55
    assert report["slowest_files"][0]["file_path"] == "tests/test_example.py"
    assert report["slowest_files"][0]["total_seconds"] == 15.55


def test_parses_rough_progress_log_when_duration_format_is_unavailable():
    text = "\n".join(
        [
            "tests/test_progress.py::test_a PASSED [ 10%] 2.50s",
            "[32.00s] tests/test_progress.py::test_b",
            "tests/test_progress.py::test_c PASSED",
        ]
    )

    parsed = parse_timing_text(text)
    report = _report(timing_text=text, allow_sample_timing=False)

    assert parsed["source_type"] == "parsed_pytest_progress_log"
    assert report["timing_source_type"] == "parsed_pytest_progress_log"
    assert [item["nodeid"] for item in report["slowest_tests"][:2]] == [
        "tests/test_progress.py::test_b",
        "tests/test_progress.py::test_a",
    ]


def test_runtime_buckets_cover_thresholds():
    report = _report(
        manual_timing_map={
            "tests/test_bucket.py::test_very_fast": 0.99,
            "tests/test_bucket.py::test_fast": 1.0,
            "tests/test_bucket.py::test_medium": 5.0,
            "tests/test_bucket.py::test_slow": 30.0,
            "tests/test_bucket.py::test_very_slow": 120.0,
        }
    )

    buckets = report["runtime_buckets"]
    assert buckets["very_fast"]["test_count"] == 1
    assert buckets["fast"]["test_count"] == 1
    assert buckets["medium"]["test_count"] == 1
    assert buckets["slow"]["test_count"] == 1
    assert buckets["very_slow"]["test_count"] == 1
    assert report["report_status"] == STATUS_READY_WITH_WARNINGS
    assert report["timing_source_type"] == "manual_timing_map"


def test_malformed_timing_lines_warn_without_crashing():
    text = "\n".join(
        [
            "7.00s call     tests/test_good.py::test_ok",
            "4.20s call     missing-node-id",
            "abc.s call     tests/test_bad.py::test_bad",
        ]
    )

    report = _report(timing_text=text, allow_sample_timing=False)

    assert report["report_status"] == STATUS_READY
    assert report["collected_test_count"] == 1
    assert any("ignored malformed timing line" in warning.lower() for warning in report["warnings"])


def test_missing_timing_data_can_use_sample_fallback_with_warnings():
    report = _report()

    assert report["report_status"] == STATUS_READY_WITH_WARNINGS
    assert report["timing_source_type"] == "sample_timing_data"
    assert report["collected_test_count"] > 0
    assert any("sample timing data" in warning.lower() for warning in report["warnings"])


def test_missing_timing_data_without_fallback_is_incomplete():
    report = _report(allow_sample_timing=False)

    assert report["report_status"] == STATUS_INCOMPLETE
    assert report["timing_source_type"] == "missing_timing_data"
    assert report["collected_test_count"] == 0
    assert any("no timing data" in reason.lower() for reason in report["incomplete_reasons"])


def test_blocks_policies_that_delete_weaken_hide_or_mutate():
    for markers in (
        {"test_deletion_recommended": True},
        {"safety_coverage_weakened": True},
        {"timeout_treated_as_pass": True},
        {"failures_hidden": True},
        {"production_behavior_mutated": True},
    ):
        report = _report(policy_violation_markers=markers)
        assert report["report_status"] == STATUS_BLOCKED
        assert report["blocked_reasons"], markers


def test_recommendations_include_profiles_timeouts_and_suite_splitting():
    report = _report()

    profiles = {profile["name"]: profile for profile in report["recommended_profiles"]}
    assert {"smoke", "phase", "branch", "full", "nightly"} <= set(profiles)
    assert "python -m pytest -q" in profiles["full"]["commands"]
    assert report["recommended_timeouts"]["full_seconds"] >= 1800
    assert "timing_collection" in report["recommended_timeouts"]
    assert any("slowest" in item["reason"].lower() for item in report["suite_split_recommendations"])
    assert report["timeout_interpretation"]["timeout_counts_as_pass"] is False


def test_json_and_markdown_timing_artifacts_are_written(tmp_path):
    output_dir = tmp_path / "ops-test-2"

    result = write_slow_test_timing_report(
        repo_root=PROJECT_ROOT,
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-09T00:00:00+09:00",
        manual_timing_map={"tests/test_writer.py::test_a": 1.25},
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["report_status"] == STATUS_READY_WITH_WARNINGS
    assert saved["recommended_next_phase"]["phase_id"] == "OPS.TEST.3"
    assert "# Slow Test Timing Report" in markdown
    assert "## Slowest Files" in markdown


def test_cli_accepts_timing_log_and_writes_summary_json(tmp_path):
    timing_log = tmp_path / "durations.txt"
    timing_log.write_text("2.50s call     tests/test_cli.py::test_a\n", encoding="utf-8")
    output_dir = tmp_path / "cli-out"

    result = script.run_create_slow_test_timing_report(
        repo_root=str(PROJECT_ROOT),
        timing_log=str(timing_log),
        output_dir=str(output_dir),
        report_id="cli-test",
        created_at="2026-07-09T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["report_status"] == STATUS_READY
    assert result["summary"]["timing_source_type"] == "parsed_pytest_durations"
    assert result["summary"]["recommended_next_phase"] == "OPS.TEST.3"
    assert result["summary"]["collected_test_count"] == 1
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_markdown_contains_required_sections():
    markdown = render_slow_test_timing_report_markdown(_report())
    low = markdown.lower()
    for section in (
        "## summary",
        "## slowest tests",
        "## slowest files",
        "## runtime buckets",
        "## recommended profiles",
        "## recommended timeouts",
        "## suite split recommendations",
        "## timeout interpretation",
        "## warnings",
        "## blocked reasons",
        "## recommended next phase",
        "## guardrails",
    ):
        assert section in low, section


def test_real_registry_marks_ops_test_2_complete_and_recommends_ops_test_3():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["OPS.TEST.2"]["status"] == "complete"
    assert by_id["OPS.TEST.2"]["title"] == "Slow Test Timing Collector"
    assert by_id["OPS.TEST.2"]["expected_artifacts"] == [
        ".agent/ops/slow_test_timing_collector/slow_test_timing_report.json",
        ".agent/ops/slow_test_timing_collector/slow_test_timing_report.md",
    ]
    assert by_id["OPS.TEST.3"]["status"] == "proposed"
    assert by_id["OPS.TEST.3"]["title"] == "Suite Split Manifest Plan"
    assert by_id["OPS.TEST.3"]["prerequisites"] == ["OPS.TEST.2"]
    assert by_id["OPS.TEST.3"]["network_allowed"] is False
    assert by_id["OPS.TEST.3"]["model_calls_allowed"] is False
    assert by_id["OPS.TEST.3"]["writes_real_repo"] is False

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="ops-test-2-registry",
        created_at="2026-07-09T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "OPS.TEST.3"


def test_core_and_cli_do_not_import_or_call_pytest_subprocess_or_mutation_primitives():
    forbidden_imports = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "openai",
        "anthropic",
        "flask",
        "sqlite3",
        "benchmark",
        "benchmarks",
    }
    forbidden_calls = {
        "run_validation",
        "run_safe_validation_command",
        "run_benchmarks",
        "call_model",
        "route_model",
        "launch_worker",
        "invoke_mcp",
        "apply_patch",
        "delete_test",
        "remove_test",
        "Popen",
        "run",
        "check_call",
        "check_output",
        "urlopen",
    }
    forbidden_text = ("subprocess", "pytest.main(")

    for path in (CORE_PATH, SCRIPT_PATH):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)
        for text in forbidden_text:
            assert text not in source
