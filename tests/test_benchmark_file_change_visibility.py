from __future__ import annotations

import ast
import json
from pathlib import Path

from benchmarks import run_benchmarks as rb


def _write_report(tmp_path: Path, report: dict) -> Path:
    bench_dir = tmp_path / ".agent" / "benchmarks"
    bench_dir.mkdir(parents=True)
    path = bench_dir / "benchmark_report_123.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def test_markdown_report_includes_file_change_scope_and_totals(tmp_path):
    report = {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
        "total": 2,
        "success_rate": 0.5,
        "results": [
            {
                "name": "allowed_artifact_case",
                "success": True,
                "duration_sec": 0.1,
                "changed_files": ["app.py", "customer_report.png"],
                "patched_files": ["app.py"],
                "generated_artifacts": ["customer_report.png"],
                "unexpected_mutations": [],
            },
            {
                "name": "unexpected_case",
                "success": False,
                "duration_sec": 0.2,
                "changed_files": ["app.py", "scratch.tmp"],
                "patched_files": ["app.py"],
                "generated_artifacts": [],
                "unexpected_mutations": ["scratch.tmp"],
            },
        ],
    }
    out = tmp_path / "report.md"

    rb.write_markdown_report(report, out)

    md = out.read_text(encoding="utf-8")
    assert "## File Changes" in md
    assert (
        "| Name | Status | Scope | Changed Files Total | Changed Files | "
        "Patched Files | Generated Artifacts | Unexpected Mutations |"
    ) in md
    assert (
        "| `allowed_artifact_case` | PASS | GENERATED | 2 | "
        "`app.py`, `customer_report.png` | `app.py` | `customer_report.png` | "
        "none |"
    ) in md
    assert (
        "| `unexpected_case` | FAIL | UNEXPECTED | 2 | `app.py`, `scratch.tmp` | "
        "`app.py` | none | `scratch.tmp` |"
    ) in md


def test_markdown_report_old_shape_uses_unknown_scope_and_dash(tmp_path):
    report = {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "total": 1,
        "success_rate": 1.0,
        "results": [
            {
                "name": "old_report_case",
                "success": True,
                "duration_sec": 0.1,
                "changed_files": ["app.py"],
            },
        ],
    }
    out = tmp_path / "report.md"

    rb.write_markdown_report(report, out)

    md = out.read_text(encoding="utf-8")
    assert "| `old_report_case` | PASS | UNKNOWN | 1 | `app.py` | - | - | - |" in md


def test_file_change_summary_helper_classifies_scope_labels():
    from core.benchmarks_view import summarize_file_change_scope

    assert summarize_file_change_scope(
        {
            "changed_files": ["app.py"],
            "patched_files": ["app.py"],
            "generated_artifacts": [],
            "unexpected_mutations": [],
        }
    )["scope"] == "CLEAN"
    assert summarize_file_change_scope(
        {
            "changed_files": ["app.py", "customer_report.png"],
            "patched_files": ["app.py"],
            "generated_artifacts": ["customer_report.png"],
            "unexpected_mutations": [],
        }
    )["scope"] == "GENERATED"
    assert summarize_file_change_scope(
        {
            "changed_files": ["app.py", "scratch.tmp"],
            "patched_files": ["app.py"],
            "generated_artifacts": [],
            "unexpected_mutations": ["scratch.tmp"],
        }
    )["scope"] == "UNEXPECTED"
    assert summarize_file_change_scope({"changed_files": ["app.py"]}) == {
        "scope": "UNKNOWN",
        "changed_total": 1,
        "patched_files": [],
        "generated_artifacts": [],
        "unexpected_mutations": [],
        "has_artifact_ledger": False,
    }


def test_web_report_file_change_summary_is_display_only_and_preserves_scores(tmp_path):
    from web import app as web_app

    report = {
        "passed": 1,
        "failed": 1,
        "skipped": 0,
        "total": 2,
        "success_rate": 0.5,
        "results": [
            {
                "name": "allowed_artifact_case",
                "success": True,
                "changed_files": ["app.py", "customer_report.png"],
                "patched_files": ["app.py"],
                "generated_artifacts": ["customer_report.png"],
                "unexpected_mutations": [],
            },
            {
                "name": "unexpected_case",
                "success": False,
                "changed_files": ["app.py", "scratch.tmp"],
                "patched_files": ["app.py"],
                "generated_artifacts": [],
                "unexpected_mutations": ["scratch.tmp"],
            },
        ],
    }
    source = _write_report(tmp_path, report)
    before = source.read_text(encoding="utf-8")

    resp = web_app.app.test_client().get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_123.json",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["passed"] == 1
    assert body["failed"] == 1
    assert [r["success"] for r in body["results"]] == [True, False]
    first, second = body["results"]
    assert first["file_change_summary"]["scope"] == "GENERATED"
    assert first["file_change_summary"]["generated_artifacts"] == [
        "customer_report.png"
    ]
    assert first["file_change_summary"]["unexpected_mutations"] == []
    assert second["file_change_summary"]["scope"] == "UNEXPECTED"
    assert second["file_change_summary"]["unexpected_mutations"] == ["scratch.tmp"]
    assert source.read_text(encoding="utf-8") == before


def test_web_report_old_shape_file_change_summary_is_unknown(tmp_path):
    from web import app as web_app

    source = _write_report(
        tmp_path,
        {
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "total": 1,
            "results": [
                {
                    "name": "old_report_case",
                    "success": True,
                    "changed_files": ["app.py"],
                }
            ],
        },
    )
    before = source.read_text(encoding="utf-8")

    resp = web_app.app.test_client().get(
        "/benchmarks/report",
        query_string={
            "repo_path": str(tmp_path),
            "filename": "benchmark_report_123.json",
        },
    )

    assert resp.status_code == 200
    summary = resp.get_json()["results"][0]["file_change_summary"]
    assert summary["scope"] == "UNKNOWN"
    assert summary["changed_total"] == 1
    assert summary["patched_files"] == []
    assert summary["has_artifact_ledger"] is False
    assert source.read_text(encoding="utf-8") == before


def test_benchmark_template_contains_file_change_scope_renderers():
    template = Path("web/templates/index.html").read_text(encoding="utf-8")
    styles = Path("web/static/style.css").read_text(encoding="utf-8")

    assert "_benchFileChangeScope" in template
    assert "_renderBenchFileChanges" in template
    assert "_benchFileScopeBadge" in template
    assert "<th>Scope</th>" in template
    assert "Patched" in template
    assert "Generated" in template
    assert "Unexpected" in template
    assert "bench-file-scope-badge--unexpected" in styles


def test_benchmarks_view_file_change_helpers_do_not_add_runtime_behaviors():
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
