import json
from pathlib import Path

from scripts import build_presentation_evidence_pack as pack


EXPECTED_FILES = [
    "00_evidence_index.md",
    "01_full_suite_summary.md",
    "02_held_out_suite_summary.md",
    "03_held_out_watchlist.md",
    "04_patch_minimality_experiment.md",
    "05_same_suite_trends.md",
    "06_graph_weight_explainability.md",
]


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_benchmark_report(
    bench_dir: Path,
    name: str,
    *,
    total: int = 31,
    passed: int = 31,
    failed: int = 0,
    flaky: int = 0,
    suite_id: str | None = None,
    case_names: list[str] | None = None,
    created_at: str = "2026-05-24T00:00:00+00:00",
    extra: dict | None = None,
) -> Path:
    case_names = case_names or ["ts_nested_dispatch_root_cause", "case_b"]
    payload: dict = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "flaky": flaky,
        "results": [
            {"name": n, "success": True, "duration_sec": 1.0, "fallback_count": 0}
            for n in case_names
        ],
        "avg_duration_sec": 1.0,
        "total_fallbacks": 0,
        "total_tokens": 100,
        "total_estimated_cost_usd": 0.001,
        "created_at": created_at,
    }
    if suite_id is not None:
        payload["suite_id"] = suite_id
    if extra:
        payload.update(extra)
    return _write_json(bench_dir / name, payload)


def test_creates_output_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    assert result["output_dir"].exists()
    assert result["output_dir"].is_dir()
    assert result["output_dir"] == project / ".agent" / "presentation_evidence"


def test_generates_all_expected_markdown_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    for name in EXPECTED_FILES:
        path = result["output_dir"] / name
        assert path.exists(), f"missing {name}"
        assert path.read_text(encoding="utf-8").strip(), f"empty {name}"


def test_missing_optional_artifacts_create_placeholders(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    graph_md = (result["output_dir"] / "06_graph_weight_explainability.md").read_text(encoding="utf-8")
    assert "explain_graph_weights.py" in graph_md
    assert "--repo-path ." in graph_md
    assert "--top 15" in graph_md
    assert "--include-zero-penalty" in graph_md
    assert "--hide-empty-symbols" in graph_md

    watchlist_md = (result["output_dir"] / "03_held_out_watchlist.md").read_text(encoding="utf-8")
    assert "No watchlist" in watchlist_md or "no watchlist" in watchlist_md.lower()

    minimality_md = (result["output_dir"] / "04_patch_minimality_experiment.md").read_text(encoding="utf-8")
    assert "No" in minimality_md  # placeholder text


def test_does_not_modify_source_reports(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    full = _write_benchmark_report(bench, "benchmark_report_full.json", total=31, passed=31)
    held = _write_benchmark_report(
        bench,
        "benchmark_report_held.json",
        total=7,
        passed=7,
        suite_id="held_out_v1",
        case_names=["a", "b"],
        extra={"suite_case_count": 7},
    )
    trends_dir = bench / "trends"
    watchlist = _write_json(
        trends_dir / "suite_watchlist_held_out_v1.json",
        {
            "suite_id": "held_out_v1",
            "watchlist": [],
            "stable": [],
            "cases": [],
            "report_window": {
                "selected": 1,
                "requested": 10,
                "first_report": "x",
                "last_report": "x",
            },
        },
    )
    trend_index = _write_json(
        trends_dir / "benchmark_trend_index.json",
        {"groups": [], "warnings": [], "skipped_reports": []},
    )
    exp_dir = project / ".agent" / "experiments"
    experiment = _write_json(
        exp_dir / "20260525_patch-minimality.json",
        {
            "experiment_id": "20260525_patch-minimality",
            "title": "Patch minimality metric check",
            "hypothesis": "Patch minimality reporting should preserve correctness.",
            "status": "compared",
            "result": {
                "decision": {"status": "greenlight", "warnings": [], "reasons": []},
                "metrics": {
                    "passed": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                },
            },
            "created_at": "2026-05-25T01:30:52+00:00",
        },
    )

    snapshots = {
        path: path.read_text(encoding="utf-8")
        for path in (full, held, watchlist, trend_index, experiment)
    }

    pack.build_evidence_pack(project)

    for path, content in snapshots.items():
        assert path.read_text(encoding="utf-8") == content


def test_selects_latest_full_suite_report(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    _write_benchmark_report(
        bench,
        "benchmark_report_old.json",
        total=31,
        passed=31,
        created_at="2026-05-23T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_new.json",
        total=31,
        passed=30,
        failed=1,
        created_at="2026-05-24T00:00:00+00:00",
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "01_full_suite_summary.md").read_text(encoding="utf-8")

    assert "benchmark_report_new.json" in md
    assert "Passed: 30" in md
    assert "Failed: 1" in md
    assert "ts_nested_dispatch_root_cause passed" in md


def test_selects_latest_held_out_v1_report(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    _write_benchmark_report(
        bench,
        "benchmark_report_held_old.json",
        total=7,
        passed=6,
        failed=1,
        suite_id="held_out_v1",
        case_names=["x", "y"],
        extra={"suite_case_count": 7},
        created_at="2026-05-23T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_held_new.json",
        total=7,
        passed=7,
        suite_id="held_out_v1",
        case_names=["alpha", "beta"],
        extra={"suite_case_count": 7},
        created_at="2026-05-24T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_full.json",
        total=31,
        passed=31,
        created_at="2026-05-25T00:00:00+00:00",
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "02_held_out_suite_summary.md").read_text(encoding="utf-8")

    assert "benchmark_report_held_new.json" in md
    assert "Passed: 7" in md
    assert "`alpha`" in md
    assert "`beta`" in md


def test_summarizes_held_out_watchlist_json(tmp_path):
    project = tmp_path / "project"
    trends_dir = project / ".agent" / "benchmarks" / "trends"
    _write_json(
        trends_dir / "suite_watchlist_held_out_v1.json",
        {
            "suite_id": "held_out_v1",
            "watchlist": ["case_alpha"],
            "stable": ["case_beta", "case_gamma"],
            "cases": [
                {
                    "name": "case_alpha",
                    "watchlisted": True,
                    "watchlist_reasons": ["failures"],
                    "failure_rate": 0.5,
                    "last_status": "fail",
                    "last_seen_report": "benchmark_report_X.json",
                },
                {
                    "name": "case_beta",
                    "watchlisted": False,
                    "watchlist_reasons": [],
                    "failure_rate": 0.0,
                    "last_status": "pass",
                    "last_seen_report": "benchmark_report_X.json",
                },
            ],
            "report_window": {
                "requested": 10,
                "selected": 2,
                "first_report": "a",
                "last_report": "b",
            },
        },
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "03_held_out_watchlist.md").read_text(encoding="utf-8")

    assert "case_alpha" in md
    assert "failures" in md
    assert "fail" in md
    assert "0.5" in md
    assert "observational" in md.lower()
    assert "Stable cases: 2" in md


def test_summarizes_patch_minimality_experiment(tmp_path):
    project = tmp_path / "project"
    exp_dir = project / ".agent" / "experiments"
    _write_json(
        exp_dir / "20260525_patch-minimality-metric-check.json",
        {
            "experiment_id": "20260525_patch-minimality-metric-check",
            "title": "Patch minimality metric report check",
            "hypothesis": "Patch minimality reporting should preserve correctness.",
            "status": "compared",
            "result": {
                "decision": {
                    "status": "greenlight",
                    "warnings": ["model_calls unknown"],
                    "reasons": ["no critical regressions"],
                    "human_review_required": False,
                },
                "metrics": {
                    "total": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                    "passed": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                    "failed": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
                    "flaky": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
                    "average_duration": {
                        "baseline": 36.31,
                        "variant": 30.7,
                        "delta": -5.61,
                        "status": "decreased",
                    },
                    "fallback_count": {
                        "baseline": 16,
                        "variant": 14,
                        "delta": -2,
                        "status": "decreased",
                    },
                },
            },
            "created_at": "2026-05-25T01:30:52+00:00",
        },
    )
    _write_json(
        exp_dir / "20260524_other-experiment.json",
        {
            "experiment_id": "20260524_other-experiment",
            "title": "Unrelated experiment",
            "status": "compared",
            "created_at": "2026-05-24T00:00:00+00:00",
        },
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "04_patch_minimality_experiment.md").read_text(encoding="utf-8")

    assert "greenlight" in md.lower()
    assert "Patch minimality metric report check" in md
    assert "-5.61" in md
    assert "-2" in md
    assert "model_calls unknown" in md
    # the older unrelated experiment should NOT be the selected one
    assert "Unrelated experiment" not in md


def test_index_links_all_generated_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    index = (result["output_dir"] / "00_evidence_index.md").read_text(encoding="utf-8")

    for name in EXPECTED_FILES[1:]:
        assert f"]({name})" in index, f"index missing link to {name}"
    assert "Full benchmark suite passed" in index
    assert "Held-out suite exists" in index
    assert "Watchlist tracks instability" in index
    assert "Patch minimality" in index
    assert "Same-suite trends prevent fake comparisons" in index
