import json
from pathlib import Path

from scripts import build_suite_watchlist as watchlist


def _write_report(
    root: Path,
    name: str,
    *,
    suite_id: str | None = "held_out_v1",
    cases: list[dict],
    created_at: str = "2026-05-24T00:00:00+00:00",
    extra: dict | None = None,
) -> Path:
    payload: dict = {
        "results": [
            {
                "name": c["name"],
                "success": c.get("success", True),
                "flaky": c.get("flaky", False),
                "duration_sec": c.get("duration_sec", 1.0),
                "fallback_count": c.get("fallback_count", 0),
            }
            for c in cases
        ],
        "created_at": created_at,
    }
    if suite_id is not None:
        payload["suite_id"] = suite_id
    if extra:
        payload.update(extra)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _stable_run(name: str) -> dict:
    return {
        "name": name,
        "success": True,
        "flaky": False,
        "duration_sec": 1.0,
        "fallback_count": 0,
    }


def test_stable_case_is_not_watchlisted(tmp_path):
    root = tmp_path / "benchmarks"
    for i in range(3):
        _write_report(
            root,
            f"benchmark_report_{i + 1}.json",
            cases=[_stable_run("case_a"), _stable_run("case_b")],
            created_at=f"2026-05-24T0{i + 1}:00:00+00:00",
        )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert "case_a" not in data["watchlist"]
    assert "case_a" in data["stable"]
    case_a = next(c for c in data["cases"] if c["name"] == "case_a")
    assert case_a["watchlisted"] is False
    assert case_a["watchlist_reasons"] == []


def test_case_with_one_failure_is_watchlisted(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        cases=[_stable_run("case_a"), _stable_run("case_b")],
        created_at="2026-05-24T01:00:00+00:00",
    )
    _write_report(
        root,
        "benchmark_report_2.json",
        cases=[
            {"name": "case_a", "success": False, "duration_sec": 1.0, "fallback_count": 0},
            _stable_run("case_b"),
        ],
        created_at="2026-05-24T02:00:00+00:00",
    )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert "case_a" in data["watchlist"]
    case_a = next(c for c in data["cases"] if c["name"] == "case_a")
    assert case_a["failures"] == 1
    assert case_a["passes"] == 1
    assert "failures" in case_a["watchlist_reasons"]
    assert case_a["last_status"] == "fail"


def test_flaky_case_is_watchlisted(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        cases=[
            {
                "name": "case_a",
                "success": True,
                "flaky": True,
                "duration_sec": 1.0,
                "fallback_count": 0,
            },
            _stable_run("case_b"),
        ],
        created_at="2026-05-24T01:00:00+00:00",
    )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert "case_a" in data["watchlist"]
    case_a = next(c for c in data["cases"] if c["name"] == "case_a")
    assert case_a["flaky_passes"] == 1
    assert "flaky_passes" in case_a["watchlist_reasons"]


def test_slow_case_over_threshold_is_watchlisted(tmp_path):
    root = tmp_path / "benchmarks"
    for i in range(2):
        _write_report(
            root,
            f"benchmark_report_{i + 1}.json",
            cases=[
                {"name": "case_fast_1", "success": True, "duration_sec": 10.0, "fallback_count": 0},
                {"name": "case_fast_2", "success": True, "duration_sec": 10.0, "fallback_count": 0},
                {"name": "case_fast_3", "success": True, "duration_sec": 10.0, "fallback_count": 0},
                {"name": "case_slow", "success": True, "duration_sec": 40.0, "fallback_count": 0},
            ],
            created_at=f"2026-05-24T0{i + 1}:00:00+00:00",
        )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert "case_slow" in data["watchlist"]
    assert "case_fast_1" not in data["watchlist"]
    slow = next(c for c in data["cases"] if c["name"] == "case_slow")
    assert "slow" in slow["watchlist_reasons"]


def test_reports_from_other_suite_id_are_ignored(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_other.json",
        suite_id="dev_v1",
        cases=[{"name": "case_a", "success": False, "duration_sec": 1.0, "fallback_count": 0}],
        created_at="2026-05-24T01:00:00+00:00",
    )
    _write_report(
        root,
        "benchmark_report_held.json",
        suite_id="held_out_v1",
        cases=[_stable_run("case_a")],
        created_at="2026-05-24T02:00:00+00:00",
    )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert "case_a" not in data["watchlist"]
    case_a = next(c for c in data["cases"] if c["name"] == "case_a")
    assert case_a["runs_seen"] == 1
    assert case_a["failures"] == 0


def test_missing_suite_id_is_skipped_by_default(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_no_suite.json",
        suite_id=None,
        cases=[{"name": "case_a", "success": False, "duration_sec": 1.0, "fallback_count": 0}],
        created_at="2026-05-24T01:00:00+00:00",
    )
    _write_report(
        root,
        "benchmark_report_target.json",
        suite_id="held_out_v1",
        cases=[_stable_run("case_a")],
        created_at="2026-05-24T02:00:00+00:00",
    )

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")
    assert "case_a" not in data["watchlist"]
    assert any(
        entry["report"] == "benchmark_report_no_suite.json"
        and entry["reason"] == "missing_suite_id"
        for entry in data["skipped_reports"]
    )

    data_inc = watchlist.build_watchlist(
        root, suite_id="held_out_v1", include_unknown_suite=True
    )
    assert "case_a" in data_inc["watchlist"]


def test_markdown_output_renders_watchlist_table(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        cases=[_stable_run("case_stable"), _stable_run("case_flaky")],
        created_at="2026-05-24T01:00:00+00:00",
    )
    _write_report(
        root,
        "benchmark_report_2.json",
        cases=[
            _stable_run("case_stable"),
            {
                "name": "case_flaky",
                "success": True,
                "flaky": True,
                "duration_sec": 1.0,
                "fallback_count": 0,
            },
        ],
        created_at="2026-05-24T02:00:00+00:00",
    )

    written = watchlist.write_watchlist_files(
        root, suite_id="held_out_v1", output_md=True
    )

    md_path = written["md_path"]
    assert md_path is not None
    md = md_path.read_text(encoding="utf-8")
    assert "held_out_v1" in md
    assert "case_flaky" in md
    assert "case_stable" in md
    assert "Watchlisted" in md
    assert "observational" in md.lower()
    assert "| case |" in md


def test_malformed_reports_are_skipped_safely(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_good.json",
        cases=[_stable_run("case_a")],
        created_at="2026-05-24T01:00:00+00:00",
    )
    (root / "benchmark_report_bad.json").write_text("{not json", encoding="utf-8")

    data = watchlist.build_watchlist(root, suite_id="held_out_v1")

    assert any(
        entry["report"] == "benchmark_report_bad.json"
        and entry["reason"] == "malformed_json"
        for entry in data["skipped_reports"]
    )
    assert any(case["name"] == "case_a" for case in data["cases"])


def test_source_benchmark_reports_are_not_modified(tmp_path):
    root = tmp_path / "benchmarks"
    path = _write_report(
        root,
        "benchmark_report_1.json",
        cases=[_stable_run("case_a")],
        created_at="2026-05-24T01:00:00+00:00",
    )
    before = path.read_text(encoding="utf-8")

    written = watchlist.write_watchlist_files(
        root, suite_id="held_out_v1", output_md=True
    )

    assert path.read_text(encoding="utf-8") == before
    assert written["json_path"].parent == root / "trends"
    assert written["md_path"].parent == root / "trends"
