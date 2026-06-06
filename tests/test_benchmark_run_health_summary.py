from __future__ import annotations

import ast
import json
from pathlib import Path

from benchmarks import run_benchmarks as rb


def _write_report(tmp_path: Path, report: dict) -> Path:
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    path = bench_dir / "benchmark_report_456.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def _case(
    name: str,
    *,
    success: bool = True,
    duration_sec: float = 1.0,
    failure_kind: str | None = None,
    failure_kind_display: str | None = None,
    scope: str = "CLEAN",
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    fallback_count: int | None = None,
) -> dict:
    result = {
        "name": name,
        "success": success,
        "duration_sec": duration_sec,
        "changed_files": ["app.py"],
        "patched_files": ["app.py"],
        "generated_artifacts": [],
        "unexpected_mutations": [],
    }
    if scope == "GENERATED":
        result["changed_files"] = ["app.py", "customer_report.png"]
        result["generated_artifacts"] = ["customer_report.png"]
    elif scope == "UNEXPECTED":
        result["changed_files"] = ["app.py", "scratch.tmp"]
        result["unexpected_mutations"] = ["scratch.tmp"]
    elif scope == "UNKNOWN":
        result.pop("patched_files")
        result.pop("generated_artifacts")
        result.pop("unexpected_mutations")
    if failure_kind is not None:
        result["failure_kind"] = failure_kind
    if failure_kind_display is not None:
        result["failure_kind_display"] = failure_kind_display
    if total_tokens is not None:
        result["total_tokens"] = total_tokens
    if estimated_cost_usd is not None:
        result["estimated_cost_usd"] = estimated_cost_usd
    if fallback_count is not None:
        result["fallback_count"] = fallback_count
    return result


def test_run_health_summary_computes_counts_rate_slowest_costs_and_labels():
    from core.benchmarks_view import summarize_run_health

    report = {
        "passed": 1,
        "failed": 3,
        "skipped": 1,
        "total": 5,
        "total_fallbacks": 4,
        "results": [
            _case("fast_pass", duration_sec=0.1, total_tokens=10, estimated_cost_usd=0.01),
            _case(
                "security_failure",
                success=False,
                duration_sec=2.5,
                failure_kind="security_tool",
                failure_kind_display="SECURITY TOOL",
                total_tokens=20,
                estimated_cost_usd=0.03,
            ),
            _case(
                "toolchain_failure",
                success=False,
                duration_sec=1.5,
                failure_kind="toolchain",
                failure_kind_display="TOOLCHAIN",
                total_tokens=30,
                estimated_cost_usd=0.02,
            ),
            _case(
                "unknown_failure",
                success=False,
                duration_sec=3.0,
                failure_kind="code_unknown",
                failure_kind_display="CODE / UNKNOWN",
                scope="GENERATED",
                total_tokens=40,
                estimated_cost_usd=0.04,
            ),
            {
                "name": "skipped_case",
                "success": False,
                "skipped": True,
                "duration_sec": 0.0,
                "changed_files": [],
                "patched_files": [],
                "generated_artifacts": [],
                "unexpected_mutations": [],
            },
        ],
    }

    summary = summarize_run_health(report)

    assert summary["total_cases"] == 5
    assert summary["passed"] == 1
    assert summary["failed"] == 3
    assert summary["skipped"] == 1
    assert summary["pass_rate"] == 0.25
    assert summary["pass_rate_display"] == "1/4 (25.0%)"
    assert summary["health_label"] == "ATTENTION"
    assert summary["failure_kind_counts"] == {
        "CODE / UNKNOWN": 1,
        "SECURITY TOOL": 1,
        "TOOLCHAIN": 1,
    }
    assert summary["environment_or_toolchain_failure_count"] == 2
    assert summary["code_unknown_failure_count"] == 1
    assert summary["clean_scope_count"] == 4
    assert summary["generated_scope_count"] == 1
    assert summary["unexpected_scope_count"] == 0
    assert summary["unknown_scope_count"] == 0
    assert [case["name"] for case in summary["slowest_cases"]] == [
        "unknown_failure",
        "security_failure",
        "toolchain_failure",
        "fast_pass",
        "skipped_case",
    ]
    assert [case["name"] for case in summary["highest_cost_cases"]] == [
        "unknown_failure",
        "security_failure",
        "toolchain_failure",
        "fast_pass",
    ]
    assert summary["total_tokens"] == 100
    assert summary["estimated_cost_usd"] == 0.1
    assert summary["fallback_count"] == 4


def test_run_health_label_rules_green_attention_mixed_and_unknown():
    from core.benchmarks_view import summarize_run_health

    all_passed = {
        "passed": 2,
        "failed": 0,
        "skipped": 0,
        "total": 2,
        "results": [
            _case("clean_pass"),
            _case("generated_pass", scope="GENERATED"),
        ],
    }
    high_rate_security = {
        "passed": 53,
        "failed": 1,
        "skipped": 0,
        "total": 54,
        "results": [
            *[_case(f"pass_{idx}") for idx in range(53)],
            _case(
                "security_block",
                success=False,
                failure_kind="security_tool",
                failure_kind_display="SECURITY TOOL",
            ),
        ],
    }
    unexpected = {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "total": 1,
        "results": [_case("unexpected_mutation", scope="UNEXPECTED")],
    }
    code_unknown = {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
        "total": 2,
        "results": [
            _case("pass"),
            _case(
                "logic_failure",
                success=False,
                failure_kind="code_unknown",
                failure_kind_display="CODE / UNKNOWN",
            ),
        ],
    }
    old_report = {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "total": 1,
        "results": [{"name": "old_shape", "success": True, "duration_sec": 1.0}],
    }

    assert summarize_run_health(all_passed)["health_label"] == "GREEN"
    assert summarize_run_health(high_rate_security)["health_label"] == "ATTENTION"
    assert summarize_run_health(unexpected)["health_label"] == "ATTENTION"
    assert summarize_run_health(code_unknown)["health_label"] == "MIXED"
    assert summarize_run_health(old_report)["health_label"] == "UNKNOWN"


def test_markdown_report_includes_run_health_section(tmp_path):
    report = {
        "passed": 2,
        "failed": 1,
        "skipped": 0,
        "total": 3,
        "total_fallbacks": 2,
        "results": [
            _case("fast_clean", duration_sec=0.1, total_tokens=100, estimated_cost_usd=0.01),
            _case(
                "slow_generated",
                duration_sec=2.5,
                scope="GENERATED",
                total_tokens=200,
                estimated_cost_usd=0.02,
            ),
            _case(
                "security_block",
                success=False,
                duration_sec=1.5,
                failure_kind="security_tool",
                failure_kind_display="SECURITY TOOL",
                total_tokens=300,
                estimated_cost_usd=0.03,
            ),
        ],
    }
    out = tmp_path / "report.md"

    rb.write_markdown_report(report, out)

    md = out.read_text(encoding="utf-8")
    assert "## Run Health" in md
    assert "- Status: ATTENTION" in md
    assert "- Pass rate: 2/3 (66.7%)" in md
    assert "- Failure kinds: SECURITY TOOL: 1" in md
    assert "- File-change scope: CLEAN: 2, GENERATED: 1, UNEXPECTED: 0, UNKNOWN: 0" in md
    assert "- Slowest cases: `slow_generated` 2.50s, `security_block` 1.50s, `fast_clean` 0.10s" in md
    assert "- Cost/tokens: 600 total tokens / $0.0600 estimated" in md
    assert "- Fallbacks: 2" in md


def test_web_report_attaches_run_health_summary_without_mutating_scores_or_file(tmp_path):
    from web import app as web_app

    report = {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
        "total": 2,
        "success_rate": 0.5,
        "results": [
            _case("clean_pass", success=True),
            _case(
                "unexpected_failure",
                success=False,
                failure_kind="code_unknown",
                failure_kind_display="CODE / UNKNOWN",
                scope="UNEXPECTED",
            ),
        ],
    }
    source = _write_report(tmp_path, report)
    before = source.read_text(encoding="utf-8")

    resp = web_app.app.test_client().get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_456.json",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["passed"] == 1
    assert body["failed"] == 1
    assert [item["success"] for item in body["results"]] == [True, False]
    assert body["run_health_summary"]["health_label"] == "ATTENTION"
    assert body["run_health_summary"]["unexpected_scope_count"] == 1
    assert body["run_health_summary"]["failure_kind_counts"] == {"CODE / UNKNOWN": 1}
    assert source.read_text(encoding="utf-8") == before


def test_old_report_run_health_summary_is_unknown_and_limited(tmp_path):
    from web import app as web_app

    source = _write_report(
        tmp_path,
        {
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "total": 1,
            "results": [{"name": "old_shape", "success": True, "duration_sec": 1.0}],
        },
    )
    before = source.read_text(encoding="utf-8")

    resp = web_app.app.test_client().get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_456.json",
        },
    )

    assert resp.status_code == 200
    summary = resp.get_json()["run_health_summary"]
    assert summary["health_label"] == "UNKNOWN"
    assert summary["pass_rate_display"] == "1/1 (100.0%)"
    assert summary["unknown_scope_count"] == 1
    assert summary["total_tokens"] is None
    assert summary["estimated_cost_usd"] is None
    assert source.read_text(encoding="utf-8") == before


def test_benchmark_template_contains_run_health_card_and_badges():
    template = Path("web/templates/index.html").read_text(encoding="utf-8")
    styles = Path("web/static/style.css").read_text(encoding="utf-8")

    assert "_renderBenchRunHealth" in template
    assert "Run Health" in template
    assert "run_health_summary" in template
    assert "bench-run-health-card" in template
    assert "bench-run-health-badge--attention" in styles
    assert "bench-run-health-kind--environment" in styles
    assert "bench-run-health-kind--code" in styles


def test_benchmarks_view_run_health_helpers_do_not_add_runtime_behaviors():
    tree = ast.parse(Path("core/benchmarks_view.py").read_text(encoding="utf-8"))
    forbidden_import_roots = {
        "agents",
        "docker",
        "openai",
        "anthropic",
        "google",
        "requests",
        "subprocess",
        "web",
    }
    forbidden_imports = {
        "benchmarks.run_benchmarks",
        "core.validator",
        "core.run_lifecycle",
        "core.dream_artifacts",
        "core.lessons",
        "core.lesson_store",
    }
    forbidden_calls = {
        "run_agent_web",
        "run_validation_command",
        "run_benchmarks",
        "run_case",
        "apply_patch",
        "apply_patch_plan",
        "run_patch_plan_with_artifacts",
        "promote_lesson",
        "block_lesson",
        "seed_queue_from_latest_benchmark",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
    }

    imports: list[str] = []
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)

    for imported in imports:
        assert imported not in forbidden_imports
        assert imported.split(".")[0] not in forbidden_import_roots
    assert not (set(calls) & forbidden_calls)
