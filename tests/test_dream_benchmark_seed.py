import json
from pathlib import Path

from core import dream_artifacts


def _write_report(repo: Path, filename: str, data: dict) -> None:
    bench_dir = repo / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True, exist_ok=True)
    (bench_dir / filename).write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def test_seed_benchmark_includes_flaky_cases_and_dedupes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(
        dream_artifacts,
        "get_agent_dir",
        lambda repo_path=None: Path(repo_path or repo) / ".agent",
    )

    report = {
        "total": 3,
        "flaky": 1,
        "results": [
            {
                "name": "failed_case",
                "success": False,
                "validation_output": "Assertion failed",
            },
            {
                "name": "ts_optional_property_guard",
                "success": True,
                "flaky": True,
                "attempts": 2,
                "retry_results": [
                    {"attempt": 1, "success": False},
                    {"attempt": 2, "success": True},
                ],
            },
            {
                "name": "slow_case",
                "success": True,
                "duration_sec": 30.0,
            },
        ],
        "slowest_cases": [
            {"name": "slow_case", "success": True, "duration_sec": 30.0}
        ],
    }
    _write_report(repo, "benchmark_report_1.json", report)

    added = dream_artifacts.seed_queue_from_latest_benchmark(
        repo,
        report_filename="benchmark_report_1.json",
    )

    flaky = [
        item for item in added
        if item.get("case_name") == "ts_optional_property_guard"
    ]
    assert len(flaky) == 1
    assert flaky[0]["kind"] == "bug"
    assert flaky[0]["title"] == "Flaky case: ts_optional_property_guard"
    assert flaky[0]["flaky"] is True
    assert flaky[0]["attempts"] == 2
    assert flaky[0]["retry_results"] == report["results"][1]["retry_results"]
    assert "Case passed on retry attempt 2/2" in flaky[0]["hint"]

    assert [item["kind"] for item in added].count("bug") == 2
    assert [item["kind"] for item in added].count("debt") == 1

    added_again = dream_artifacts.seed_queue_from_latest_benchmark(
        repo,
        report_filename="benchmark_report_1.json",
    )

    assert added_again == []
    assert len(dream_artifacts.read_queue(str(repo))) == 3
