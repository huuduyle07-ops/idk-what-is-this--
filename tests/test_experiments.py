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


def test_export_experiment_markdown_writes_not_compared_lab_note(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title="Markdown note",
        hypothesis="The note is readable without opening JSON.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        subset="python smoke",
        metric_names=["passed"],
        greenlight_rule="passed must not drop",
        experiment_id="markdown-note",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    result = experiments.export_experiment_markdown(
        "markdown-note",
        experiments_root=experiments_root,
    )

    path = experiments_root / "markdown-note.md"
    assert result["path"] == str(path)
    text = path.read_text(encoding="utf-8")
    assert "# Markdown note" in text
    assert "- Experiment ID: `markdown-note`" in text
    assert "- Status: `created`" in text
    assert "- Hypothesis: The note is readable without opening JSON." in text
    assert "- Subset: python smoke" in text
    assert "- Baseline report: `.agent/benchmarks/baseline.json`" in text
    assert "- Variant report: `.agent/benchmarks/variant.json`" in text
    assert "- Greenlight rule: passed must not drop" in text
    assert "| metric | baseline | variant | delta | status |" in text
    assert "| passed | unknown | unknown | unknown | unknown |" in text
    assert "Conclusion: Not compared yet." in text


def test_export_experiment_markdown_includes_metric_table_and_conclusion(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(
        benchmark_root / "baseline.json",
        {"total": 2, "passed": 1, "failed": 1, "fallback_count": 3},
    )
    _write_report(
        benchmark_root / "variant.json",
        {"total": 2, "passed": 2, "failed": 0},
    )
    experiments.create_experiment(
        title="Compared note",
        hypothesis="The variant improves the smoke run.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=["total", "passed", "failed", "fallback_count"],
        experiment_id="compared-note",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )
    compared = experiments.compare_experiment(
        "compared-note",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    result = experiments.export_experiment_markdown(
        ".agent/experiments/compared-note.json",
        experiments_root=experiments_root,
    )

    text = Path(result["path"]).read_text(encoding="utf-8")
    assert f"- Compared at: {compared['result']['compared_at']}" in text
    assert "| total | 2 | 2 | 0 | unchanged |" in text
    assert "| passed | 1 | 2 | +1 | increased |" in text
    assert "| failed | 1 | 0 | -1 | decreased |" in text
    assert "| fallback_count | 3 | unknown | unknown | unknown |" in text
    assert "Conclusion: 2 improved, 0 regressed, 1 unchanged, 1 unknown." in text


@pytest.mark.parametrize(
    ("label", "ref_factory"),
    [
        ("experiment id", lambda root, path: "export-forms"),
        ("filename", lambda root, path: "export-forms.json"),
        (".agent path", lambda root, path: ".agent/experiments/export-forms.json"),
        ("absolute path", lambda root, path: str(path)),
    ],
)
def test_export_experiment_markdown_accepts_supported_reference_forms(
    tmp_path,
    label,
    ref_factory,
):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title=f"Export form: {label}",
        hypothesis="All supported refs can export Markdown.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=["passed"],
        experiment_id="export-forms",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    ref = ref_factory(experiments_root, experiments_root / "export-forms.json")
    result = experiments.export_experiment_markdown(
        ref,
        experiments_root=experiments_root,
    )

    assert Path(result["path"]).is_file()


def test_export_experiment_markdown_supports_guarded_custom_output(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title="Custom output",
        hypothesis="Reports can be grouped under the experiments root.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        experiment_id="custom-output",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    result = experiments.export_experiment_markdown(
        "custom-output",
        output="reports/custom-output.md",
        experiments_root=experiments_root,
    )

    assert result["path"] == str(experiments_root / "reports" / "custom-output.md")
    assert (experiments_root / "reports" / "custom-output.md").is_file()


def test_export_experiment_markdown_rejects_output_traversal(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title="Unsafe output",
        hypothesis="Output must stay in the experiments root.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        experiment_id="unsafe-output",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    with pytest.raises(experiments.ExperimentError, match="output"):
        experiments.export_experiment_markdown(
            "unsafe-output",
            output="../outside.md",
            experiments_root=experiments_root,
        )


def test_export_cli_writes_report_for_agent_experiments_path(
    tmp_path,
    capsys,
    monkeypatch,
):
    from scripts import export_experiment_report as export_cli

    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(export_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title="CLI export",
        hypothesis="The CLI writes a Markdown report.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        experiment_id="cli-export",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    exit_code = export_cli.main([".agent/experiments/cli-export.json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "exported experiment report:" in captured.out
    assert (experiments_root / "cli-export.md").is_file()
    assert "Traceback" not in captured.err


def test_export_cli_fail_soft_for_unsafe_output(tmp_path, capsys, monkeypatch):
    from scripts import export_experiment_report as export_cli

    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(export_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(benchmark_root / "baseline.json", {"passed": 1})
    _write_report(benchmark_root / "variant.json", {"passed": 1})
    experiments.create_experiment(
        title="CLI unsafe output",
        hypothesis="Unsafe output fails cleanly.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        experiment_id="cli-unsafe-output",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    exit_code = export_cli.main(["cli-unsafe-output", "--output", "../outside.md"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
