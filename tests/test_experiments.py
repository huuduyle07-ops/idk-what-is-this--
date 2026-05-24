from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import experiments
from scripts import compare_experiment as compare_cli
from scripts import create_experiment as create_cli


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-experiments"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    agent = tmp_path / ".agent"
    benchmark_root = agent / "benchmarks"
    experiments_root = agent / "experiments"
    benchmark_root.mkdir(parents=True)
    return benchmark_root, experiments_root


def _write_report(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_create_experiment_writes_registry_record_under_agent_experiments(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    baseline = _write_report(benchmark_root / "baseline.json", {"total": 2})
    variant = _write_report(benchmark_root / "variant.json", {"total": 2})

    record = experiments.create_experiment(
        title="Tune fallback routing",
        hypothesis="Fewer fallback calls without hurting pass rate.",
        baseline_report=str(baseline),
        variant_report=str(variant),
        subset="python smoke",
        metric_names=["passed", "failed", "fallback_count"],
        greenlight_rule="passed must not drop",
        experiment_id="fallback-routing",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    path = experiments_root / "fallback-routing.json"
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == record
    assert saved["schema_version"] == experiments.SCHEMA_VERSION
    assert saved["experiment_id"] == "fallback-routing"
    assert saved["baseline_report"] == ".agent/benchmarks/baseline.json"
    assert saved["variant_report"] == ".agent/benchmarks/variant.json"
    assert saved["subset"] == "python smoke"
    assert saved["metric_names"] == ["passed", "failed", "fallback_count"]
    assert saved["status"] == "created"
    assert saved["result"] is None
    assert "created_at" in saved


def test_create_experiment_rejects_unsafe_benchmark_report_path(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "variant.json", {"total": 1})

    with pytest.raises(experiments.ExperimentError, match="benchmark report"):
        experiments.create_experiment(
            title="Unsafe path",
            hypothesis="Should be rejected.",
            baseline_report="../outside.json",
            variant_report="variant.json",
            experiment_id="unsafe",
            benchmark_root=benchmark_root,
            experiments_root=experiments_root,
        )


def test_compare_experiment_updates_result_with_deltas_and_unknowns(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(
        benchmark_root / "baseline.json",
        {
            "total": 3,
            "passed": 2,
            "failed": 1,
            "flaky": 0,
            "average_duration": 1.5,
            "model_calls": 10,
        },
    )
    _write_report(
        benchmark_root / "variant.json",
        {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "average_duration": 1.25,
            "model_calls": 12,
            "fallback_count": 1,
        },
    )
    experiments.create_experiment(
        title="Compare metrics",
        hypothesis="Variant improves pass rate.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=[
            "total",
            "passed",
            "failed",
            "flaky",
            "average_duration",
            "model_calls",
            "fallback_count",
        ],
        experiment_id="compare-metrics",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    updated = experiments.compare_experiment(
        "compare-metrics",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    metrics = updated["result"]["metrics"]
    assert updated["status"] == "compared"
    assert metrics["passed"] == {
        "baseline": 2,
        "variant": 3,
        "delta": 1,
        "status": "increased",
    }
    assert metrics["failed"]["delta"] == -1
    assert metrics["failed"]["status"] == "decreased"
    assert metrics["flaky"] == {
        "baseline": 0,
        "variant": None,
        "delta": None,
        "status": "unknown",
    }
    assert metrics["fallback_count"] == {
        "baseline": None,
        "variant": 1,
        "delta": None,
        "status": "unknown",
    }

    saved = json.loads((experiments_root / "compare-metrics.json").read_text(encoding="utf-8"))
    assert saved["result"] == updated["result"]


@pytest.mark.parametrize(
    ("label", "ref_factory"),
    [
        ("experiment id", lambda root, path: "accepted-forms"),
        ("filename", lambda root, path: "accepted-forms.json"),
        (
            ".agent path",
            lambda root, path: ".agent/experiments/accepted-forms.json",
        ),
        ("absolute path", lambda root, path: str(path)),
    ],
)
def test_compare_experiment_accepts_supported_reference_forms(
    tmp_path,
    label,
    ref_factory,
):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 2})
    experiments.create_experiment(
        title=f"Accepted form: {label}",
        hypothesis="All supported refs resolve to the same experiment.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=["passed"],
        experiment_id="accepted-forms",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    ref = ref_factory(experiments_root, experiments_root / "accepted-forms.json")
    updated = experiments.compare_experiment(
        ref,
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    assert updated["experiment_id"] == "accepted-forms"
    assert updated["result"]["metrics"]["passed"]["delta"] == 1


def test_compare_experiment_rejects_experiment_path_traversal(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)

    with pytest.raises(experiments.ExperimentError, match="experiment"):
        experiments.compare_experiment(
            "../escape",
            benchmark_root=benchmark_root,
            experiments_root=experiments_root,
        )


def test_create_cli_fail_soft_for_path_errors(tmp_path, capsys, monkeypatch):
    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(create_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(create_cli.experiments, "default_experiments_root", lambda: experiments_root)

    exit_code = create_cli.main(
        [
            "--title",
            "Bad path",
            "--hypothesis",
            "Should fail cleanly.",
            "--baseline-report",
            "../outside.json",
            "--variant-report",
            "variant.json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_compare_cli_prints_summary_and_updates_record(tmp_path, capsys, monkeypatch):
    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(compare_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(compare_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(benchmark_root / "baseline.json", {"passed": 1, "failed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 2, "failed": 0})
    experiments.create_experiment(
        title="CLI summary",
        hypothesis="Variant should improve pass count.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=["passed", "failed"],
        experiment_id="cli-summary",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    exit_code = compare_cli.main(["cli-summary"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Experiment: CLI summary" in captured.out
    assert "passed: 1 -> 2 (delta +1)" in captured.out
    assert "failed: 1 -> 0 (delta -1)" in captured.out
    assert json.loads((experiments_root / "cli-summary.json").read_text(encoding="utf-8"))[
        "status"
    ] == "compared"


def test_compare_cli_accepts_agent_experiments_path(tmp_path, capsys, monkeypatch):
    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(compare_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(compare_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 2})
    experiments.create_experiment(
        title="CLI agent path",
        hypothesis="The CLI should accept .agent/experiments refs.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=["passed"],
        experiment_id="cli-agent-path",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    exit_code = compare_cli.main([".agent/experiments/cli-agent-path.json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Experiment: CLI agent path" in captured.out
    assert "Traceback" not in captured.err
