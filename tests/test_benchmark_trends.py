import json
from pathlib import Path

from scripts import build_benchmark_trends as trends


def _write_report(root: Path, name: str, payload: dict) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _report(
    *,
    case_names: list[str],
    created_at: str,
    passed: int = 1,
    failed: int = 0,
    extra: dict | None = None,
) -> dict:
    payload = {
        "created_at": created_at,
        "total": len(case_names),
        "passed": passed,
        "failed": failed,
        "flaky": 0,
        "results": [{"name": name, "success": True} for name in case_names],
    }
    payload.update(extra or {})
    return payload


def test_same_case_names_produce_one_trend_group(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_2.json",
        _report(case_names=["case_b", "case_a"], created_at="2026-05-24T02:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_1.json",
        _report(case_names=["case_a", "case_b"], created_at="2026-05-24T01:00:00+00:00"),
    )

    ledger = trends.build_trend_ledger(root)

    assert len(ledger["groups"]) == 1
    group = ledger["groups"][0]
    assert group["case_names"] == ["case_a", "case_b"]
    assert [run["report"] for run in group["runs"]] == [
        "benchmark_report_1.json",
        "benchmark_report_2.json",
    ]


def test_same_total_different_case_names_produce_separate_groups_and_warning(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_ab.json",
        _report(case_names=["case_a", "case_b"], created_at="2026-05-24T01:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_ac.json",
        _report(case_names=["case_a", "case_c"], created_at="2026-05-24T02:00:00+00:00"),
    )

    ledger = trends.build_trend_ledger(root)

    assert len(ledger["groups"]) == 2
    assert {tuple(group["case_names"]) for group in ledger["groups"]} == {
        ("case_a", "case_b"),
        ("case_a", "case_c"),
    }
    assert ledger["warnings"]
    assert "same total" in ledger["warnings"][0]


def test_reports_sort_chronologically(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_new.json",
        _report(case_names=["case_a"], created_at="2026-05-24T03:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_old.json",
        _report(case_names=["case_a"], created_at="2026-05-24T01:00:00+00:00"),
    )
    _write_report(
        root,
        "benchmark_report_mid.json",
        _report(case_names=["case_a"], created_at="2026-05-24T02:00:00+00:00"),
    )

    runs = trends.build_trend_ledger(root)["groups"][0]["runs"]

    assert [run["report"] for run in runs] == [
        "benchmark_report_old.json",
        "benchmark_report_mid.json",
        "benchmark_report_new.json",
    ]


def test_missing_optional_metrics_become_unknown(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_sparse.json",
        _report(
            case_names=["case_a"],
            created_at="2026-05-24T01:00:00+00:00",
            extra={"brain_stamp": {}},
        ),
    )

    run = trends.build_trend_ledger(root)["groups"][0]["runs"][0]

    assert run["average_duration"] == "unknown"
    assert run["fallback_count"] == "unknown"
    assert run["tokens"]["total"] == "unknown"
    assert run["estimated_cost"] == "unknown"
    assert run["average_total_changed_lines"] == "unknown"
    assert run["brain_stamp"]["git_sha"] == "unknown"


def test_markdown_output_renders_trend_table(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_1.json",
        _report(
            case_names=["case_a"],
            created_at="2026-05-24T01:00:00+00:00",
            extra={
                "avg_duration_sec": 1.25,
                "total_fallbacks": 2,
                "total_tokens": 300,
                "total_estimated_cost_usd": 0.0123,
                "average_total_changed_lines": 4.0,
            },
        ),
    )

    written = trends.write_trend_files(root, output_md=True)

    md_path = written["markdown_files"][0]
    markdown = md_path.read_text(encoding="utf-8")
    assert "| report | passed | failed | flaky | average_duration | fallback_count | tokens_total | estimated_cost | average_total_changed_lines |" in markdown
    assert "| `benchmark_report_1.json` | 1 | 0 | 0 | 1.25 | 2 | 300 | 0.0123 | 4.0 |" in markdown


def test_script_is_read_only_toward_benchmark_reports(tmp_path):
    root = tmp_path / "benchmarks"
    report_path = _write_report(
        root,
        "benchmark_report_1.json",
        _report(case_names=["case_a"], created_at="2026-05-24T01:00:00+00:00"),
    )
    before = report_path.read_text(encoding="utf-8")

    written = trends.write_trend_files(root, output_md=True)

    assert report_path.read_text(encoding="utf-8") == before
    assert written["json_files"]
    assert all(path.parent == root / "trends" for path in written["json_files"])


def test_malformed_benchmark_reports_are_skipped_safely(tmp_path):
    root = tmp_path / "benchmarks"
    _write_report(
        root,
        "benchmark_report_good.json",
        _report(case_names=["case_a"], created_at="2026-05-24T01:00:00+00:00"),
    )
    (root / "benchmark_report_bad.json").write_text("{not json", encoding="utf-8")

    ledger = trends.build_trend_ledger(root)

    assert len(ledger["groups"]) == 1
    assert ledger["skipped_reports"] == [
        {"report": "benchmark_report_bad.json", "reason": "malformed_json"}
    ]
