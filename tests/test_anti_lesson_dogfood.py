from __future__ import annotations

from core import anti_lesson_dogfood as dogfood


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
    baseline = _report([
        _case("hard_case", success=True, difficulty="hard"),
        _case("normal_case", success=True),
    ])
    experiment = _report([
        _case("hard_case", success=False, difficulty="hard"),
        _case("normal_case", success=True),
    ])

    report = dogfood.build_anti_lesson_dogfood_report(baseline, experiment)

    assert report["decision"]["status"] == "needs_review_regression"
    assert any("hard_case" in reason for reason in report["decision"]["reasons"])
