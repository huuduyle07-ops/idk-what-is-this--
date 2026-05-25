"""Phase 6.4b tests: seed lesson candidates from benchmark reports."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from core import lesson_store
from scripts import seed_lessons_from_benchmark as seeder


def _agent_answer(*, summary: str = "Fix the root cause.", changed_file: str = "app.py") -> str:
    return json.dumps(
        {
            "summary": summary,
            "patch_candidate": None,
            "patch_plan": [
                {
                    "op": "replace_snippet",
                    "relative_path": changed_file,
                    "target_snippet": "old",
                    "patched_snippet": "new",
                }
            ],
        }
    )


def _case_result(
    name: str,
    *,
    success: bool = True,
    validation_ok: bool | None = True,
    flaky: bool = False,
    changed_files: list[str] | None = None,
    agent_answer: str | None = None,
    touched_forbidden_files: list[str] | None = None,
    missing_expected_files: list[str] | None = None,
    patch_minimality: dict | None = None,
) -> dict:
    changed_files = ["app.py"] if changed_files is None else changed_files
    return {
        "name": name,
        "success": success,
        "validation_ok": validation_ok,
        "flaky": flaky,
        "language": "python",
        "category": "logic_validation",
        "difficulty": "easy",
        "changed_files": changed_files,
        "missing_expected_files": list(missing_expected_files or []),
        "touched_forbidden_files": list(touched_forbidden_files or []),
        "validation_output": "OK" if validation_ok else "AssertionError: failed",
        "patch_kind": "patch_plan",
        "rollback_happened": False,
        "agent_answer": _agent_answer(changed_file=changed_files[0]) if agent_answer is None and changed_files else (agent_answer or ""),
        "patch_minimality": patch_minimality
        or {
            "status": "known",
            "files_touched": len(changed_files),
            "added_lines": 2,
            "removed_lines": 1,
            "net_changed_lines": 1,
            "total_changed_lines": 3,
            "touched_test_files": 0,
            "touched_forbidden_files": list(touched_forbidden_files or []),
            "patch_size_score": 8,
        },
    }


def _write_report(root: Path, name: str, results: list[dict]) -> Path:
    payload = {
        "total": len(results),
        "passed": sum(1 for item in results if item.get("success")),
        "failed": sum(1 for item in results if not item.get("success")),
        "skipped": 0,
        "flaky": sum(1 for item in results if item.get("flaky")),
        "results": results,
    }
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _lesson_files(repo: Path) -> list[Path]:
    lessons_root = repo / ".agent" / "lessons"
    if not lessons_root.exists():
        return []
    return sorted(lessons_root.rglob("*.json"))


def _configure_tmp_roots(tmp_path, monkeypatch):
    benchmarks_root = tmp_path / ".agent" / "benchmarks"
    reports_root = tmp_path / ".agent" / "reports"
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    monkeypatch.setattr(seeder, "DEFAULT_BENCHMARK_ROOT", benchmarks_root)
    monkeypatch.setattr(seeder, "DEFAULT_REPORTS_ROOT", reports_root)
    return benchmarks_root, reports_root


def test_dry_run_creates_no_lesson_files(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_case")],
    )

    summary = seeder.seed_lessons_from_report(report, dry_run=True)

    assert summary["counts"]["created"] == 0
    assert summary["counts"]["dry_run"] == 1
    assert _lesson_files(tmp_path) == []


def test_passed_case_creates_candidate_lesson(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_discount_validation")],
    )

    summary = seeder.seed_lessons_from_report(report)

    assert summary["counts"]["created"] == 1
    lessons = lesson_store.list_lessons(status="candidate")
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["source"] == "benchmark_report"
    assert lesson["source_report"] == "benchmark_report_1.json"
    assert lesson["case_name"] == "python_discount_validation"
    assert lesson["active_knowledge_allowed"] is False
    assert "python" in lesson["tags"]
    assert "logic-validation" in lesson["tags"]

    candidate = lesson["candidate"]
    assert candidate["case_name"] == "python_discount_validation"
    assert candidate["benchmark_status"] == "passed"
    assert candidate["benchmark_passed"] is True
    assert candidate["benchmark_failed"] is False
    assert candidate["benchmark_flaky"] is False
    assert candidate["patch_summary"] == "Fix the root cause."
    assert candidate["changed_files"] == ["app.py"]
    assert candidate["diff_stats"]["added"] == 2
    assert candidate["diff_stats"]["removed"] == 1


def test_failed_case_is_blocked_or_skipped_never_active(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [
            _case_result(
                "python_failed_validation",
                success=False,
                validation_ok=False,
            )
        ],
    )

    summary = seeder.seed_lessons_from_report(report)

    assert summary["counts"]["blocked"] == 1
    assert lesson_store.list_lessons(status="active") == []
    blocked = lesson_store.list_lessons(status="blocked")
    assert len(blocked) == 1
    assert blocked[0]["candidate"]["validation_ok"] is False
    assert blocked[0]["evaluation"]["promotion"] == "blocked"


def test_flaky_case_creates_candidate_marked_for_review(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_flaky_case", flaky=True)],
    )

    seeder.seed_lessons_from_report(report)

    lesson = lesson_store.list_lessons(status="candidate")[0]
    candidate = lesson["candidate"]
    assert candidate["benchmark_status"] == "flaky"
    assert candidate["benchmark_flaky"] is True
    assert candidate["needs_human_review"] is True
    assert "flaky benchmark case" in candidate["review_evidence"]
    assert lesson["evaluation"]["promotion"] == "needs_human_review"


def test_duplicate_source_key_is_idempotent(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_duplicate_case")],
    )

    first = seeder.seed_lessons_from_report(report)
    second = seeder.seed_lessons_from_report(report)

    assert first["counts"]["created"] == 1
    assert second["counts"]["duplicates"] == 1
    assert len(lesson_store.list_lessons()) == 1


def test_missing_patch_evidence_is_skipped_safely(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [
            _case_result(
                "python_no_patch",
                changed_files=[],
                agent_answer="",
                patch_minimality={"status": "unknown", "reason": "no_patch"},
            )
        ],
    )

    summary = seeder.seed_lessons_from_report(report)

    assert summary["counts"]["skipped"] == 1
    assert summary["skipped"][0]["reason"] == "missing_patch_evidence"
    assert lesson_store.list_lessons() == []


def test_path_traversal_in_report_name_is_blocked(tmp_path, monkeypatch, capsys):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    _write_report(benchmarks_root, "benchmark_report_1.json", [_case_result("case")])

    exit_code = seeder._main(["--report", "..\\benchmark_report_1.json"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "must be a benchmark_report_*.json filename" in err


def test_no_benchmark_runner_or_model_client_is_called(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_case")],
    )
    sys.modules.pop("benchmarks.run_benchmarks", None)
    sys.modules.pop("agents.gemini_client", None)
    sys.modules.pop("agents.ollama_client", None)
    sys.modules.pop("agents.deepseek_client", None)

    seeder.seed_lessons_from_report(report)

    assert "benchmarks.run_benchmarks" not in sys.modules
    assert "agents.gemini_client" not in sys.modules
    assert "agents.ollama_client" not in sys.modules
    assert "agents.deepseek_client" not in sys.modules


def test_existing_benchmark_report_is_not_modified(tmp_path, monkeypatch):
    benchmarks_root, _reports_root = _configure_tmp_roots(tmp_path, monkeypatch)
    report = _write_report(
        benchmarks_root,
        "benchmark_report_1.json",
        [_case_result("python_case")],
    )
    before = report.read_text(encoding="utf-8")

    seeder.seed_lessons_from_report(report)

    assert report.read_text(encoding="utf-8") == before
