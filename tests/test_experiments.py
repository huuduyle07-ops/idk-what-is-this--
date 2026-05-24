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


def test_decide_experiment_result_greenlight_with_noncritical_unknown_warning():
    metrics = {
        "total": {"baseline": 4, "variant": 4, "delta": 0, "status": "unchanged"},
        "passed": {"baseline": 4, "variant": 4, "delta": 0, "status": "unchanged"},
        "failed": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
        "flaky": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
        "average_duration": {
            "baseline": 1.0,
            "variant": 1.0,
            "delta": 0,
            "status": "unchanged",
        },
        "fallback_count": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
        "model_calls": {
            "baseline": None,
            "variant": None,
            "delta": None,
            "status": "unknown",
        },
    }

    decision = experiments.decide_experiment_result(metrics)

    assert decision["status"] == "greenlight"
    assert decision["human_review_required"] is False
    assert decision["reasons"] == ["no critical regressions or review triggers"]
    assert decision["warnings"] == ["model_calls unknown"]
    assert decision["critical_regressions"] == []


def test_decide_experiment_result_rejects_critical_regressions():
    decision = experiments.decide_experiment_result(
        {
            "passed": {"baseline": 5, "variant": 4, "delta": -1, "status": "decreased"},
            "failed": {"baseline": 0, "variant": 1, "delta": 1, "status": "increased"},
            "flaky": {"baseline": 0, "variant": 1, "delta": 1, "status": "increased"},
        }
    )

    assert decision["status"] == "reject"
    assert decision["human_review_required"] is True
    assert decision["critical_regressions"] == [
        "passed decreased",
        "failed increased",
        "flaky increased",
    ]
    assert decision["reasons"] == [
        "passed decreased",
        "failed increased",
        "flaky increased",
    ]


def test_decide_experiment_result_needs_review_for_total_and_cost_increases():
    decision = experiments.decide_experiment_result(
        {
            "total": {"baseline": 4, "variant": 5, "delta": 1, "status": "increased"},
            "average_duration": {
                "baseline": 1.0,
                "variant": 1.2,
                "delta": 0.2,
                "status": "increased",
            },
            "fallback_count": {"baseline": 1, "variant": 2, "delta": 1, "status": "increased"},
            "model_calls": {"baseline": 4, "variant": 5, "delta": 1, "status": "increased"},
        }
    )

    assert decision["status"] == "needs_review"
    assert decision["human_review_required"] is True
    assert decision["reasons"] == [
        "total changed",
        "average_duration increased",
        "fallback_count increased",
        "model_calls increased",
    ]


def test_decide_experiment_result_tracks_improvements():
    decision = experiments.decide_experiment_result(
        {
            "passed": {"baseline": 3, "variant": 4, "delta": 1, "status": "increased"},
            "failed": {"baseline": 1, "variant": 0, "delta": -1, "status": "decreased"},
            "flaky": {"baseline": 1, "variant": 0, "delta": -1, "status": "decreased"},
            "average_duration": {
                "baseline": 2.0,
                "variant": 1.5,
                "delta": -0.5,
                "status": "decreased",
            },
            "fallback_count": {"baseline": 2, "variant": 1, "delta": -1, "status": "decreased"},
            "model_calls": {"baseline": 5, "variant": 4, "delta": -1, "status": "decreased"},
        }
    )

    assert decision["status"] == "greenlight"
    assert decision["improvements"] == [
        "passed increased",
        "failed decreased",
        "flaky decreased",
        "average_duration decreased",
        "fallback_count decreased",
        "model_calls decreased",
    ]


def test_compare_experiment_writes_advisory_decision(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(
        benchmark_root / "baseline.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
        },
    )
    _write_report(
        benchmark_root / "variant.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
        },
    )
    experiments.create_experiment(
        title="Decision smoke",
        hypothesis="Same reports should greenlight with model call warning.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=[
            "total",
            "passed",
            "failed",
            "flaky",
            "average_duration",
            "fallback_count",
            "model_calls",
        ],
        experiment_id="decision-smoke",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    updated = experiments.compare_experiment(
        "decision-smoke",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    decision = updated["result"]["decision"]
    assert decision["status"] == "greenlight"
    assert decision["human_review_required"] is False
    assert decision["warnings"] == ["model_calls unknown"]
    saved = json.loads((experiments_root / "decision-smoke.json").read_text(encoding="utf-8"))
    assert saved["result"]["decision"] == decision


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
        metric_names=["passed", "failed", "model_calls"],
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
    assert "Decision:" in captured.out
    assert "  status: greenlight" in captured.out
    assert "  human_review_required: false" in captured.out
    assert "  reasons:" in captured.out
    assert "    - no critical regressions or review triggers" in captured.out
    assert "  warnings:" in captured.out
    assert "    - model_calls unknown" in captured.out
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


def test_export_experiment_markdown_includes_decision_block(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    _write_report(
        benchmark_root / "baseline.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
        },
    )
    _write_report(
        benchmark_root / "variant.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
        },
    )
    experiments.create_experiment(
        title="Decision Markdown",
        hypothesis="Markdown should surface advisory decision.",
        baseline_report="baseline.json",
        variant_report="variant.json",
        metric_names=[
            "total",
            "passed",
            "failed",
            "flaky",
            "average_duration",
            "fallback_count",
            "model_calls",
        ],
        experiment_id="decision-markdown",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )
    experiments.compare_experiment(
        "decision-markdown",
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )

    result = experiments.export_experiment_markdown(
        "decision-markdown",
        experiments_root=experiments_root,
    )

    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "## Decision" in text
    assert "- Status: `greenlight`" in text
    assert "- Human review required: `false`" in text
    assert "- Reasons:" in text
    assert "  - no critical regressions or review triggers" in text
    assert "- Warnings:" in text
    assert "  - model_calls unknown" in text


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


def test_list_experiments_skips_markdown_and_malformed_json_newest_first(tmp_path):
    _benchmark_root, experiments_root = _roots(tmp_path)
    experiments_root.mkdir(parents=True, exist_ok=True)
    (experiments_root / "alpha.json").write_text(
        json.dumps(
            {
                "experiment_id": "alpha",
                "title": "Alpha",
                "status": "created",
                "created_at": "2026-05-24T01:00:00+00:00",
                "baseline_report": ".agent/benchmarks/a.json",
                "variant_report": ".agent/benchmarks/b.json",
            }
        ),
        encoding="utf-8",
    )
    (experiments_root / "bravo.json").write_text(
        json.dumps(
            {
                "experiment_id": "bravo",
                "title": "Bravo",
                "status": "compared",
                "created_at": "2026-05-24T02:00:00+00:00",
                "baseline_report": ".agent/benchmarks/c.json",
                "variant_report": ".agent/benchmarks/d.json",
            }
        ),
        encoding="utf-8",
    )
    (experiments_root / "charlie.json").write_text(
        json.dumps(
            {
                "experiment_id": "charlie",
                "title": "Charlie",
                "status": "created",
                "created_at": "",
                "baseline_report": ".agent/benchmarks/e.json",
                "variant_report": ".agent/benchmarks/f.json",
            }
        ),
        encoding="utf-8",
    )
    (experiments_root / "notes.md").write_text("# ignore me\n", encoding="utf-8")
    (experiments_root / "broken.json").write_text("{not json", encoding="utf-8")

    rows = experiments.list_experiments(experiments_root=experiments_root)

    assert [row["experiment_id"] for row in rows] == ["bravo", "alpha", "charlie"]
    assert all(set(experiments.EXPERIMENT_LIST_COLUMNS) <= set(row) for row in rows)


def test_list_experiments_filters_status_and_limit(tmp_path):
    _benchmark_root, experiments_root = _roots(tmp_path)
    experiments_root.mkdir(parents=True, exist_ok=True)
    for idx, status in enumerate(["created", "compared", "compared"], start=1):
        (experiments_root / f"exp-{idx}.json").write_text(
            json.dumps(
                {
                    "experiment_id": f"exp-{idx}",
                    "title": f"Experiment {idx}",
                    "status": status,
                    "created_at": f"2026-05-24T0{idx}:00:00+00:00",
                    "baseline_report": f".agent/benchmarks/base-{idx}.json",
                    "variant_report": f".agent/benchmarks/variant-{idx}.json",
                }
            ),
            encoding="utf-8",
        )

    rows = experiments.list_experiments(
        status="compared",
        limit=1,
        experiments_root=experiments_root,
    )

    assert len(rows) == 1
    assert rows[0]["experiment_id"] == "exp-3"
    assert rows[0]["status"] == "compared"


def test_list_experiments_rejects_negative_limit(tmp_path):
    _benchmark_root, experiments_root = _roots(tmp_path)

    with pytest.raises(experiments.ExperimentError, match="limit"):
        experiments.list_experiments(limit=-1, experiments_root=experiments_root)


def test_list_cli_prints_stdlib_table_without_pandas(tmp_path, capsys, monkeypatch):
    from scripts import list_experiments as list_cli

    _benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(list_cli.experiments, "default_experiments_root", lambda: experiments_root)
    monkeypatch.setattr(list_cli, "_try_format_with_pandas", lambda rows: None)
    experiments_root.mkdir(parents=True, exist_ok=True)
    (experiments_root / "table.json").write_text(
        json.dumps(
            {
                "experiment_id": "table",
                "title": "Table Output",
                "status": "created",
                "created_at": "2026-05-24T01:00:00+00:00",
                "baseline_report": ".agent/benchmarks/base.json",
                "variant_report": ".agent/benchmarks/variant.json",
            }
        ),
        encoding="utf-8",
    )

    exit_code = list_cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "created_at" in captured.out
    assert "Table Output" in captured.out
    assert "table" in captured.out
    assert "Traceback" not in captured.err


def test_list_cli_prints_json(tmp_path, capsys, monkeypatch):
    from scripts import list_experiments as list_cli

    _benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(list_cli.experiments, "default_experiments_root", lambda: experiments_root)
    experiments_root.mkdir(parents=True, exist_ok=True)
    (experiments_root / "json-output.json").write_text(
        json.dumps(
            {
                "experiment_id": "json-output",
                "title": "JSON Output",
                "status": "compared",
                "created_at": "2026-05-24T01:00:00+00:00",
                "baseline_report": ".agent/benchmarks/base.json",
                "variant_report": ".agent/benchmarks/variant.json",
            }
        ),
        encoding="utf-8",
    )

    exit_code = list_cli.main(["--status", "compared", "--limit", "20", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    rows = json.loads(captured.out)
    assert rows[0]["experiment_id"] == "json-output"
    assert rows[0]["status"] == "compared"


def test_list_cli_fail_soft_for_invalid_limit(capsys):
    from scripts import list_experiments as list_cli

    exit_code = list_cli.main(["--limit", "-1"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_list_benchmark_reports_filters_min_total_and_sorts_by_timestamp(tmp_path):
    benchmark_root, _experiments_root = _roots(tmp_path)
    _write_report(
        benchmark_root / "old.json",
        {
            "total": 10,
            "passed": 8,
            "failed": 2,
            "created_at": "2026-05-24T01:00:00+00:00",
        },
    )
    _write_report(
        benchmark_root / "new.json",
        {
            "total": 10,
            "passed": 9,
            "failed": 1,
            "timestamp": "2026-05-24T03:00:00+00:00",
        },
    )
    _write_report(
        benchmark_root / "tiny.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "created_at": "2026-05-24T04:00:00+00:00",
        },
    )
    (benchmark_root / "broken.json").write_text("{not json", encoding="utf-8")

    rows = experiments.list_benchmark_reports(
        min_total=5,
        benchmark_root=benchmark_root,
    )

    assert [Path(row["path"]).name for row in rows] == ["new.json", "old.json"]
    assert rows[0]["total"] == 10
    assert rows[0]["passed"] == 9
    assert rows[0]["failed"] == 1


def test_create_experiment_from_latest_creates_record_without_compare_by_default(
    tmp_path,
    capsys,
    monkeypatch,
):
    from scripts import create_experiment_from_latest as latest_cli

    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(latest_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(latest_cli.experiments, "default_experiments_root", lambda: experiments_root)
    baseline = _write_report(
        benchmark_root / "baseline.json",
        {
            "total": 8,
            "passed": 7,
            "failed": 1,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
            "created_at": "2026-05-24T01:00:00+00:00",
        },
    )
    variant = _write_report(
        benchmark_root / "variant.json",
        {
            "total": 8,
            "passed": 8,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
            "created_at": "2026-05-24T02:00:00+00:00",
        },
    )
    _write_report(
        benchmark_root / "tiny.json",
        {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "created_at": "2026-05-24T03:00:00+00:00",
        },
    )
    before_baseline = baseline.read_text(encoding="utf-8")
    before_variant = variant.read_text(encoding="utf-8")

    exit_code = latest_cli.main(
        [
            "--title",
            "Recent benchmark dogfood",
            "--hypothesis",
            "Recent changes should not reduce benchmark quality.",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Selected reports:" in captured.out
    assert "  Baseline: .agent/benchmarks/baseline.json" in captured.out
    assert (
        "    total: 8, passed: 7, failed: 1, flaky: 0, "
        "average_duration: 1.0, fallback_count: 0"
    ) in captured.out
    assert "  Variant: .agent/benchmarks/variant.json" in captured.out
    assert (
        "    total: 8, passed: 8, failed: 0, flaky: 0, "
        "average_duration: 1.0, fallback_count: 0"
    ) in captured.out
    assert "created experiment:" in captured.out
    records = list(experiments_root.glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["title"] == "Recent benchmark dogfood"
    assert record["subset"] == "full-fast"
    assert record["greenlight_rule"] == (
        "No correctness regression; review cost or speed increases."
    )
    assert record["baseline_report"] == ".agent/benchmarks/baseline.json"
    assert record["variant_report"] == ".agent/benchmarks/variant.json"
    assert record["result"] is None
    assert baseline.read_text(encoding="utf-8") == before_baseline
    assert variant.read_text(encoding="utf-8") == before_variant


def test_format_selected_benchmark_reports_summary_uses_unknown_for_missing_fields(
    tmp_path,
):
    benchmark_root, _experiments_root = _roots(tmp_path)
    baseline = benchmark_root / "baseline.json"
    variant = benchmark_root / "variant.json"

    summary = experiments.format_selected_benchmark_reports_summary(
        {"path": str(baseline), "total": 8, "passed": 7, "failed": 1},
        {"path": str(variant), "total": 8, "passed": 8},
        benchmark_root=benchmark_root,
    )

    assert "Selected reports:" in summary
    assert "  Baseline: .agent/benchmarks/baseline.json" in summary
    assert (
        "    total: 8, passed: 7, failed: 1, flaky: unknown, "
        "average_duration: unknown, fallback_count: unknown"
    ) in summary
    assert "  Variant: .agent/benchmarks/variant.json" in summary
    assert (
        "    total: 8, passed: 8, failed: unknown, flaky: unknown, "
        "average_duration: unknown, fallback_count: unknown"
    ) in summary


def test_format_selected_benchmark_reports_summary_uses_metric_aliases(tmp_path):
    benchmark_root, _experiments_root = _roots(tmp_path)
    baseline = benchmark_root / "baseline.json"
    variant = benchmark_root / "variant.json"

    summary = experiments.format_selected_benchmark_reports_summary(
        {
            "path": str(baseline),
            "total": 22,
            "passed": 22,
            "failed": 0,
            "flaky": 0,
            "avg_duration_sec": 39.98,
            "total_fallbacks": 7,
        },
        {
            "path": str(variant),
            "total": 22,
            "passed": 22,
            "failed": 0,
            "flaky": 0,
            "avg_duration_sec": 48.18,
            "total_fallbacks": 14,
        },
        benchmark_root=benchmark_root,
    )

    assert (
        "    total: 22, passed: 22, failed: 0, flaky: 0, "
        "average_duration: 39.98, fallback_count: 7"
    ) in summary
    assert (
        "    total: 22, passed: 22, failed: 0, flaky: 0, "
        "average_duration: 48.18, fallback_count: 14"
    ) in summary


def test_create_experiment_from_latest_can_compare_and_export_markdown(
    tmp_path,
    capsys,
    monkeypatch,
):
    from scripts import create_experiment_from_latest as latest_cli

    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(latest_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(latest_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(
        benchmark_root / "baseline.json",
        {
            "total": 8,
            "passed": 7,
            "failed": 1,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
            "created_at": "2026-05-24T01:00:00+00:00",
        },
    )
    _write_report(
        benchmark_root / "variant.json",
        {
            "total": 8,
            "passed": 8,
            "failed": 0,
            "flaky": 0,
            "average_duration": 1.0,
            "fallback_count": 0,
            "created_at": "2026-05-24T02:00:00+00:00",
        },
    )

    exit_code = latest_cli.main(
        [
            "--title",
            "Compared latest",
            "--hypothesis",
            "Latest run should improve quality.",
            "--compare",
            "--export-md",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "compared experiment:" in captured.out
    assert "markdown report:" in captured.out
    records = list(experiments_root.glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["status"] == "compared"
    assert record["result"]["decision"]["status"] == "greenlight"
    assert records[0].with_suffix(".md").is_file()


def test_create_experiment_from_latest_fail_soft_when_reports_missing(
    tmp_path,
    capsys,
    monkeypatch,
):
    from scripts import create_experiment_from_latest as latest_cli

    benchmark_root, experiments_root = _roots(tmp_path)
    monkeypatch.setattr(latest_cli.experiments, "default_benchmark_root", lambda: benchmark_root)
    monkeypatch.setattr(latest_cli.experiments, "default_experiments_root", lambda: experiments_root)
    _write_report(
        benchmark_root / "only.json",
        {
            "total": 8,
            "passed": 8,
            "failed": 0,
            "created_at": "2026-05-24T01:00:00+00:00",
        },
    )

    exit_code = latest_cli.main(
        [
            "--title",
            "Not enough",
            "--hypothesis",
            "Should fail cleanly.",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
    assert "at least two" in captured.err
    assert "Traceback" not in captured.err
