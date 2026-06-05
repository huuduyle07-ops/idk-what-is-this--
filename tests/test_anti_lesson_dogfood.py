from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core import anti_lesson_dogfood as dogfood
from scripts import create_anti_lesson_dogfood_report as report_cli


REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_SOURCE = REPO_ROOT / "core" / "anti_lesson_dogfood.py"
CLI_SOURCE = REPO_ROOT / "scripts" / "create_anti_lesson_dogfood_report.py"

FORBIDDEN_IMPORT_ROOTS = {
    "agents",
    "aiohttp",
    "anthropic",
    "benchmarks",
    "database",
    "docker",
    "google",
    "httpx",
    "openai",
    "patching",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_IMPORTS = {
    "benchmarks.run_benchmarks",
    "core.control_engine",
    "core.dream_artifacts",
    "core.dream_references",
    "core.dream_trials",
    "core.lesson_retrieval",
    "core.mutation_oracle",
    "core.prompter",
    "core.proposal_runner",
    "core.run_lifecycle",
    "core.sleeping_consultant",
    "patching.patch_plan_executor",
}
FORBIDDEN_MUTATION_CALLS = {
    "apply_patch",
    "apply_patch_plan",
    "archive_lesson",
    "block_lesson",
    "build_control_prompt",
    "build_deepseek_review",
    "build_prompt",
    "call_api",
    "call_model",
    "check_call",
    "check_output",
    "ChatCompletion",
    "create_merge",
    "create_manual_anti_lesson",
    "create_mutation_oracle",
    "generate_content",
    "generate_patch",
    "patch_lesson_fields",
    "Popen",
    "promote_lesson",
    "run_benchmark",
    "run_benchmarks",
    "run_deepseek",
    "run_dream",
    "run_gemini",
    "run_gemini_request_2",
    "run_mutation_oracle",
    "run_ollama",
    "run_patch_plan_with_artifacts",
    "run_reverse_dream",
    "save_candidate_lesson",
    "save_raw_lesson_record",
    "system",
}
DOGFOOD_MODULE_NAME = "anti_lesson_dogfood"
SENSITIVE_SOURCE_PATHS = (
    REPO_ROOT / "core" / "control_engine.py",
    REPO_ROOT / "core" / "prompter.py",
    REPO_ROOT / "core" / "lesson_retrieval.py",
)


@pytest.fixture
def tmp_repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir(parents=True)
    return path


def _case(
    name: str,
    *,
    success: bool,
    flaky: bool = False,
    difficulty: str = "medium",
    changed_files: list[str] | None = None,
    patched_files: list[str] | None = None,
    unexpected_mutations: list[str] | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    duration_sec: float | None = None,
    fallback_count: int | None = None,
) -> dict:
    out = {
        "name": name,
        "success": success,
        "flaky": flaky,
        "difficulty": difficulty,
        "changed_files": changed_files or [],
        "patched_files": patched_files or [],
        "unexpected_mutations": unexpected_mutations or [],
    }
    if total_tokens is not None:
        out["total_tokens"] = total_tokens
    if estimated_cost_usd is not None:
        out["estimated_cost_usd"] = estimated_cost_usd
    if duration_sec is not None:
        out["duration_sec"] = duration_sec
    if fallback_count is not None:
        out["fallback_count"] = fallback_count
    return out


def _parse_source(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _import_roots(tree: ast.AST) -> set[str]:
    return {name.split(".", maxsplit=1)[0] for name in _imported_modules(tree)}


def _dogfood_references(tree: ast.AST) -> set[str]:
    references: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == DOGFOOD_MODULE_NAME:
                    references.add(alias.name)
                if alias.asname == DOGFOOD_MODULE_NAME:
                    references.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[-1] == DOGFOOD_MODULE_NAME:
                references.add(node.module)
            for alias in node.names:
                if alias.name == DOGFOOD_MODULE_NAME:
                    references.add(alias.name)
                if alias.asname == DOGFOOD_MODULE_NAME:
                    references.add(alias.asname)
        elif isinstance(node, ast.Name) and node.id == DOGFOOD_MODULE_NAME:
            references.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr == DOGFOOD_MODULE_NAME:
            references.add(node.attr)
    return references


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _report(
    cases: list[dict],
    *,
    filename: str = "benchmark_report_test.json",
    suite_id: str = "dev_v1",
) -> dict:
    passed = sum(1 for c in cases if c.get("success") and not c.get("flaky"))
    flaky = sum(1 for c in cases if c.get("flaky"))
    failed = sum(1 for c in cases if not c.get("success") and not c.get("skipped"))
    return {
        "filename": filename,
        "suite_id": suite_id,
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "flaky": flaky,
        "duration_sec": sum(c.get("duration_sec", 0.0) for c in cases),
        "total_tokens": sum(c.get("total_tokens", 0) for c in cases),
        "total_estimated_cost_usd": sum(c.get("estimated_cost_usd", 0.0) for c in cases),
        "total_fallbacks": sum(c.get("fallback_count", 0) for c in cases),
        "results": cases,
    }


def test_core_module_has_no_forbidden_control_model_patch_or_network_edges():
    tree = _parse_source(CORE_SOURCE)

    assert _imported_modules(tree) & FORBIDDEN_IMPORTS == set()
    assert _import_roots(tree) & FORBIDDEN_IMPORT_ROOTS == set()
    assert _called_names(tree) & FORBIDDEN_MUTATION_CALLS == set()


def test_cli_has_no_benchmark_model_patch_lesson_mutation_or_subprocess_edges():
    tree = _parse_source(CLI_SOURCE)

    assert _imported_modules(tree) & FORBIDDEN_IMPORTS == set()
    assert _import_roots(tree) & FORBIDDEN_IMPORT_ROOTS == set()
    assert _called_names(tree) & FORBIDDEN_MUTATION_CALLS == set()


@pytest.mark.parametrize("source_path", SENSITIVE_SOURCE_PATHS)
def test_sensitive_control_prompt_and_retrieval_modules_do_not_reference_dogfood(source_path):
    assert _dogfood_references(_parse_source(source_path)) == set()


def test_pass_rate_unchanged_greenlights_default_off_experiment_path():
    baseline = _report([_case("a", success=True), _case("b", success=False)])
    experiment = _report([_case("a", success=True), _case("b", success=False)])

    report = dogfood.build_anti_lesson_dogfood_report(
        baseline, experiment, generated_at="2026-06-04T00:00:00+00:00"
    )

    assert report["decision"]["status"] == "greenlight_default_off_experiment_path"
    assert "default-off" in " ".join(report["decision"]["reasons"])
    assert report["pass_rate"]["delta_percentage_points"] == 0.0


def test_pass_rate_drop_of_five_points_rejects_correctness_regression():
    baseline_cases = [_case(f"case_{i}", success=True) for i in range(20)]
    experiment_cases = [
        _case(f"case_{i}", success=(i != 0)) for i in range(20)
    ]

    report = dogfood.build_anti_lesson_dogfood_report(
        _report(baseline_cases), _report(experiment_cases)
    )

    assert report["decision"]["status"] == "reject_correctness_regression"
    assert report["pass_rate"]["delta_percentage_points"] == -5.0


def test_low_shared_case_ratio_is_inconclusive_but_keeps_partial_rows():
    baseline = _report([_case(f"case_{i}", success=True) for i in range(10)])
    experiment = _report([_case("case_0", success=True), _case("case_1", success=True)])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["case_matching"]["shared_case_ratio"] == 0.2
    assert report["decision"]["status"] == "inconclusive_missing_matching_cases"
    assert [row["case_name"] for row in report["per_case"]] == ["case_0", "case_1"]


def test_previously_passing_hard_case_failure_needs_review():
    baseline = _report(
        [_case("hard_case", success=True, difficulty="hard")]
        + [_case(f"normal_case_{i}", success=True) for i in range(39)]
    )
    experiment = _report(
        [_case("hard_case", success=False, difficulty="hard")]
        + [_case(f"normal_case_{i}", success=True) for i in range(39)]
    )

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert any("hard_case" in reason for reason in report["decision"]["reasons"])


def test_pass_rate_reject_takes_precedence_over_hard_case_review():
    baseline = _report(
        [_case("hard_case", success=True, difficulty="hard")]
        + [_case(f"normal_case_{i}", success=True) for i in range(19)]
    )
    experiment = _report(
        [_case("hard_case", success=False, difficulty="hard")]
        + [_case(f"normal_case_{i}", success=True) for i in range(19)]
    )

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "reject_correctness_regression"
    assert report["pass_rate"]["delta_percentage_points"] == -5.0


def test_small_negative_pass_rate_delta_needs_review_instead_of_greenlight():
    baseline = _report([_case(f"case_{i}", success=True) for i in range(40)])
    experiment = _report(
        [_case("case_0", success=False)]
        + [_case(f"case_{i}", success=True) for i in range(1, 40)]
    )

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert report["pass_rate"]["delta_percentage_points"] == -2.5
    assert any("pass rate" in reason.lower() for reason in report["decision"]["reasons"])


def test_malformed_truthy_skipped_and_flaky_values_do_not_change_case_status():
    baseline = {
        "filename": "baseline.json",
        "suite_id": "dev_v1",
        "total": 1,
        "passed": 1,
        "results": [{"name": "case_a", "success": True, "skipped": "yes", "flaky": "yes"}],
    }
    experiment = {
        "filename": "experiment.json",
        "suite_id": "dev_v1",
        "total": 1,
        "passed": 1,
        "results": [{"name": "case_a", "success": True, "skipped": 1, "flaky": ["yes"]}],
    }

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["per_case"][0]["baseline_status"] == "passed"
    assert report["per_case"][0]["experiment_status"] == "passed"
    assert report["per_case"][0]["outcome"] == "unchanged"


def test_zero_baseline_positive_usage_increase_needs_review():
    baseline = _report([_case("case_a", success=True)])
    baseline["model_calls"] = 0
    baseline["total_fallbacks"] = 0
    experiment = _report([_case("case_a", success=True)])
    experiment["model_calls"] = 5
    experiment["total_fallbacks"] = 2

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert any("model_calls" in reason for reason in report["decision"]["reasons"])
    assert any("total_fallbacks" in reason for reason in report["decision"]["reasons"])


def test_zero_baseline_positive_token_increase_needs_review():
    baseline = _report([_case("case_a", success=True)])
    baseline["total_tokens"] = 0
    experiment = _report([_case("case_a", success=True)])
    experiment["total_tokens"] = 100

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert any("total_tokens" in reason for reason in report["decision"]["reasons"])


def test_missing_baseline_usage_value_does_not_count_as_zero_increase():
    baseline = _report([_case("case_a", success=True)])
    baseline.pop("total_tokens")
    experiment = _report([_case("case_a", success=True)])
    experiment["total_tokens"] = 100

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "greenlight_default_off_experiment_path"
    assert report["summary"]["total_tokens"]["baseline"] is None


def test_per_case_file_comparison_tracks_added_removed_and_unchanged_files():
    baseline = _report(
        [
            _case(
                "case_a",
                success=True,
                changed_files=["shared.py", "baseline_only.py"],
                patched_files=["patch_shared.py", "patch_removed.py"],
                unexpected_mutations=["mutation_shared.py", "mutation_removed.py"],
            )
        ]
    )
    experiment = _report(
        [
            _case(
                "case_a",
                success=True,
                changed_files=["shared.py", "experiment_only.py"],
                patched_files=["patch_shared.py", "patch_added.py"],
                unexpected_mutations=["mutation_shared.py", "mutation_added.py"],
            )
        ]
    )

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["per_case"][0]["file_comparison"] == {
        "changed_files": {
            "baseline_only": ["baseline_only.py"],
            "experiment_only": ["experiment_only.py"],
            "shared": ["shared.py"],
        },
        "patched_files": {
            "baseline_only": ["patch_removed.py"],
            "experiment_only": ["patch_added.py"],
            "shared": ["patch_shared.py"],
        },
        "unexpected_mutations": {
            "baseline_only": ["mutation_removed.py"],
            "experiment_only": ["mutation_added.py"],
            "shared": ["mutation_shared.py"],
        },
    }


def test_markdown_includes_guardrail_decision_and_per_case_table():
    baseline = _report([_case("case_a", success=True)])
    experiment = _report([_case("case_a", success=True)])
    report = dogfood.build_anti_lesson_dogfood_report(
        baseline,
        experiment,
        generated_at="2026-06-04T00:00:00+00:00",
    )

    markdown = dogfood.format_anti_lesson_dogfood_markdown(report)

    assert "# Anti-Lesson CONTROL Dogfood Evaluation Report" in markdown
    assert dogfood.GUARDRAIL_NOTE in markdown
    assert "greenlight_default_off_experiment_path" in markdown
    assert "default-off" in markdown
    assert "| case | baseline | experiment | outcome |" in markdown
    assert "Not safe to make anti-lesson CONTROL injection default-on" in markdown


def test_markdown_escapes_per_case_table_cells():
    case_name = "case|pipe\nline"
    baseline = _report([_case(case_name, success=True)])
    experiment = _report([_case(case_name, success=True)])
    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    markdown = dogfood.format_anti_lesson_dogfood_markdown(report)

    assert "case\\|pipe<br>line" in markdown
    assert f"| {case_name} |" not in markdown


@pytest.mark.parametrize(
    ("baseline", "experiment", "expected"),
    [
        (_case("case_a", success=False), _case("case_a", success=True), "improved"),
        (_case("case_a", success=True), _case("case_a", success=False), "regressed"),
        (_case("case_a", success=True), _case("case_a", success=True), "unchanged"),
        (_case("case_a", success=True), {"name": "case_a"}, "inconclusive"),
    ],
)
def test_per_case_outcome_classification(baseline, experiment, expected):
    report = dogfood.build_anti_lesson_dogfood_report(
        _report([baseline]),
        _report([experiment]),
    )

    assert report["per_case"][0]["outcome"] == expected


def test_missing_optional_per_case_cost_and_token_fields_are_unknown_without_error():
    report = dogfood.build_anti_lesson_dogfood_report(
        _report([_case("case_a", success=True)]),
        _report([_case("case_a", success=True)]),
    )

    usage_delta = report["per_case"][0]["usage_delta"]
    assert usage_delta["total_tokens"] == {
        "baseline": None,
        "experiment": None,
        "delta": None,
        "delta_ratio": None,
    }
    assert usage_delta["estimated_cost_usd"] == {
        "baseline": None,
        "experiment": None,
        "delta": None,
        "delta_ratio": None,
    }


def _write_report(path: Path, report: dict) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(data)
    return data


def _run_cli(repo_path: Path, *args: str) -> int:
    return report_cli.main(
        [
            "--repo-path",
            str(repo_path),
            *args,
        ]
    )


def test_cli_writes_json_and_markdown_under_experiments_without_mutating_sources(
    tmp_repo,
):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    baseline_bytes = _write_report(baseline_path, _report([_case("case_a", success=True)]))
    experiment_bytes = _write_report(experiment_path, _report([_case("case_a", success=True)]))

    result = _run_cli(
        tmp_repo,
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
    )

    assert result == 0
    outputs = sorted((tmp_repo / ".agent" / "experiments").glob("*_anti-lesson-control-dogfood.*"))
    assert {path.suffix for path in outputs} == {".json", ".md"}
    output_json = next(path for path in outputs if path.suffix == ".json")
    output_md = next(path for path in outputs if path.suffix == ".md")
    assert output_json.parent == tmp_repo / ".agent" / "experiments"
    assert output_md.parent == tmp_repo / ".agent" / "experiments"
    assert output_json.stem == output_md.stem
    assert json.loads(output_json.read_text(encoding="utf-8"))["decision"]["status"] == (
        "greenlight_default_off_experiment_path"
    )
    assert "# Anti-Lesson CONTROL Dogfood Evaluation Report" in output_md.read_text(encoding="utf-8")
    assert baseline_path.read_bytes() == baseline_bytes
    assert experiment_path.read_bytes() == experiment_bytes


def test_cli_requires_repo_path(tmp_repo, capsys):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    _write_report(baseline_path, _report([_case("case_a", success=True)]))
    _write_report(experiment_path, _report([_case("case_a", success=True)]))

    with pytest.raises(SystemExit) as excinfo:
        report_cli.main(
            [
                "--baseline-report",
                str(baseline_path),
                "--experiment-report",
                str(experiment_path),
            ]
        )

    assert excinfo.value.code == 2
    assert "--repo-path" in capsys.readouterr().err


def test_cli_rejects_source_report_outside_allowed_agent_report_dirs(tmp_repo, capsys):
    baseline_path = tmp_repo / "reports" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    _write_report(baseline_path, _report([_case("case_a", success=True)]))
    _write_report(experiment_path, _report([_case("case_a", success=True)]))

    result = _run_cli(
        tmp_repo,
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
    )

    assert result == 2
    err = capsys.readouterr().err
    assert "benchmarks" in err
    assert "experiments" in err


@pytest.mark.parametrize(
    "extra_args",
    [
        ("--output-json", ".agent/experiments/../report.json"),
        ("--output-json", ".agent/experiments/report.txt"),
        ("--output-md", ".agent/experiments/../report.md"),
        ("--output-md", ".agent/experiments/report.json"),
        ("--baseline-report", ".agent/benchmarks/../benchmarks/baseline.json"),
    ],
)
def test_cli_rejects_traversal_and_non_json_non_md_output_suffixes(
    tmp_repo,
    extra_args,
):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    _write_report(baseline_path, _report([_case("case_a", success=True)]))
    _write_report(experiment_path, _report([_case("case_a", success=True)]))

    args = [
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
        *extra_args,
    ]
    result = _run_cli(tmp_repo, *args)

    assert result == 2
    assert not list((tmp_repo / ".agent" / "experiments").glob("*_anti-lesson-control-dogfood.*"))


def test_cli_does_not_overwrite_input_reports(tmp_repo, capsys):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    baseline_bytes = _write_report(baseline_path, _report([_case("case_a", success=True)]))
    experiment_bytes = _write_report(experiment_path, _report([_case("case_a", success=True)]))

    result = _run_cli(
        tmp_repo,
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
        "--output-json",
        str(experiment_path),
    )

    assert result == 2
    assert "input report" in capsys.readouterr().err
    assert baseline_path.read_bytes() == baseline_bytes
    assert experiment_path.read_bytes() == experiment_bytes


def test_cli_rejects_existing_output_paths_without_mutating_sources(tmp_repo, capsys):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    output_json = tmp_repo / ".agent" / "experiments" / "existing.json"
    output_md = tmp_repo / ".agent" / "experiments" / "new.md"
    baseline_bytes = _write_report(baseline_path, _report([_case("case_a", success=True)]))
    experiment_bytes = _write_report(experiment_path, _report([_case("case_a", success=True)]))
    output_bytes = _write_report(output_json, {"already": "there"})

    result = _run_cli(
        tmp_repo,
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    )

    assert result == 2
    assert "already exists" in capsys.readouterr().err
    assert baseline_path.read_bytes() == baseline_bytes
    assert experiment_path.read_bytes() == experiment_bytes
    assert output_json.read_bytes() == output_bytes
    assert not output_md.exists()


def test_cli_removes_partial_artifacts_when_markdown_write_fails(tmp_repo, monkeypatch, capsys):
    baseline_path = tmp_repo / ".agent" / "benchmarks" / "baseline.json"
    experiment_path = tmp_repo / ".agent" / "experiments" / "experiment.json"
    output_json = tmp_repo / ".agent" / "experiments" / "partial.json"
    output_md = tmp_repo / ".agent" / "experiments" / "partial.md"
    baseline_bytes = _write_report(baseline_path, _report([_case("case_a", success=True)]))
    experiment_bytes = _write_report(experiment_path, _report([_case("case_a", success=True)]))
    original_write = report_cli._write_text_artifact

    def fail_markdown_write(path: Path, text: str) -> None:
        if path.suffix == ".md":
            raise OSError("simulated markdown write failure")
        original_write(path, text)

    monkeypatch.setattr(report_cli, "_write_text_artifact", fail_markdown_write)

    result = _run_cli(
        tmp_repo,
        "--baseline-report",
        str(baseline_path),
        "--experiment-report",
        str(experiment_path),
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    )

    assert result == 1
    assert "simulated markdown write failure" in capsys.readouterr().err
    assert baseline_path.read_bytes() == baseline_bytes
    assert experiment_path.read_bytes() == experiment_bytes
    assert not output_json.exists()
    assert not output_md.exists()
