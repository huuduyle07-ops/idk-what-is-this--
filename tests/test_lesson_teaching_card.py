from __future__ import annotations

import ast
import importlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-lesson-teaching-card"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _module():
    try:
        return importlib.import_module("core.lesson_teaching_card")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"core.lesson_teaching_card is missing: {exc}") from exc


def _cli_module():
    try:
        return importlib.import_module("scripts.create_lesson_teaching_card")
    except ModuleNotFoundError as exc:
        raise AssertionError(f"scripts.create_lesson_teaching_card is missing: {exc}") from exc


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _lesson_source(**overrides: Any) -> dict[str, Any]:
    source: dict[str, Any] = {
        "id": "20260601_010101_000001",
        "status": "active",
        "title": "Benchmark report lesson: checkout total",
        "summary": "Use the existing money helper when calculating checkout totals.",
        "source": "benchmark_report",
        "source_report": "benchmark_report_123.json",
        "case_name": "python_checkout_total",
        "candidate": {
            "language": "python",
            "category": "nested_dispatch_root_cause",
            "changed_files": ["core/checkout.py"],
            "patch_summary": "Updated checkout total calculation to reuse the existing money helper.",
            "validation_summary": {
                "validation_ok": True,
                "validation_output_tail": "2 passed",
            },
        },
        "evaluation": {
            "promotion": "auto_approved",
            "reasons": ["all auto-approval checks passed"],
        },
    }
    source.update(overrides)
    return source


def _anti_lesson_source(**overrides: Any) -> dict[str, Any]:
    source: dict[str, Any] = {
        "id": "20260601_010101_000002",
        "kind": "anti_lesson",
        "status": "candidate",
        "title": "Do not delete failing tests",
        "summary": "Do NOT remove a failing test just to make validation pass.",
        "candidate": {
            "anti_lesson": True,
            "tempting_wrong_pattern": "Delete the failing regression test.",
            "why_wrong": "The failure is evidence of the bug, not noise.",
            "safer_alternative": "Fix the implementation while keeping the test.",
            "evidence_refs": ["proposals/run-1/item-1/validation.json"],
        },
    }
    source.update(overrides)
    return source


def test_lesson_source_creates_teaching_card(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / ".agent" / "lessons" / "active" / "lesson.json",
        _lesson_source(),
    )

    result = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        created_at="2026-01-01T00:00:00Z",
        teaching_card_id="lesson-card",
    )

    assert result["ok"] is True
    assert result["status"] == "card_created"
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path == repo / ".agent" / "teaching_cards" / "lesson-card" / "teaching_card.json"
    assert md_path == json_path.with_name("teaching_card.md")
    assert json_path.is_file()
    assert md_path.is_file()

    record = json.loads(json_path.read_text(encoding="utf-8"))
    assert record["teaching_card_id"] == "lesson-card"
    assert record["created_at"] == "2026-01-01T00:00:00Z"
    assert record["source_type"] == "lesson"
    assert record["source_path"] == str(source_path.resolve())
    assert record["title"] == "Benchmark report lesson: checkout total"
    assert "money helper" in record["summary"]
    assert "core/checkout.py" in record["what_happened"]
    assert record["human_review_recommended"] is True
    assert record["model_call_performed"] is False


def test_anti_lesson_source_creates_card_with_anti_pattern_warning(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / ".agent" / "lessons" / "blocked" / "anti.json",
        _anti_lesson_source(),
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        anti_lesson_path=str(source_path),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        teaching_card_id="anti-card",
    )["record"]

    assert record["source_type"] == "anti_lesson"
    assert "Delete the failing regression test" in record["common_trap"]
    assert "Fix the implementation while keeping the test" in record["safe_fix_strategy"]
    assert "Do not" in record["anti_pattern_warning"]
    assert "Delete the failing regression test" in record["anti_pattern_warning"]


def test_benchmark_case_source_creates_teaching_card(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / "benchmarks" / "cases" / "python" / "case.json",
        {
            "name": "python_config_env_mismatch",
            "language": "python",
            "category": "config_mismatch",
            "difficulty": "easy",
            "validation_command": "python main.py",
            "expected_changed_files": ["config.py"],
            "forbidden_changed_files": ["main.py"],
            "prompt": "Fix the Python config environment variable mismatch.",
        },
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        benchmark_case_path=str(source_path),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        teaching_card_id="benchmark-card",
    )["record"]

    assert record["source_type"] == "benchmark_case"
    assert record["title"] == "Benchmark case: python_config_env_mismatch"
    assert "config_mismatch" in record["what_happened"]
    assert "config.py" in record["safe_fix_strategy"]
    assert len(record["mini_quiz"]) == 3


def test_failure_report_source_creates_teaching_card(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / ".agent" / "audits" / "failure-report.json",
        {
            "phase": "14.7a",
            "guardrail_note": "Read-only verification report.",
            "category_fields": {"total_failing": 1},
            "run_health": {
                "passed": 53,
                "failed": 1,
                "failure_category_counts": {"security_tool_or_permission": 1},
            },
        },
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        failure_report_path=str(source_path),
        dry_run=True,
        created_at="2026-01-01T00:00:00Z",
        teaching_card_id="failure-card",
    )["record"]

    assert record["source_type"] == "failure_report"
    assert record["title"] == "Failure report: 14.7a"
    assert "security_tool_or_permission" in record["what_happened"]
    assert any("Read-only verification report" in item for item in record["related_artifacts"])


def test_weak_incomplete_source_adds_uncertainty_notes(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "weak.json", {})

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["record"]

    assert record["source_type"] == "lesson"
    assert record["uncertainty_notes"]
    joined = "\n".join(record["uncertainty_notes"]).lower()
    assert "thin" in joined or "incomplete" in joined
    assert record["human_review_recommended"] is True


def test_visual_source_adds_visual_verification_warning(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / ".agent" / "lessons" / "active" / "visual.json",
        _lesson_source(
            title="Fix dashboard layout screenshot mismatch",
            summary="The screenshot showed the chart legend overlapping the UI layout.",
        ),
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["record"]

    joined = "\n".join([record["anti_pattern_warning"], *record["uncertainty_notes"]]).lower()
    assert "visual" in joined
    assert "verification" in joined


def test_security_source_adds_security_sensitive_warning(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / "benchmarks" / "cases" / "python" / "case.json",
        {
            "name": "python_config_env_mismatch",
            "prompt": "Fix auth token handling without exposing API keys or .env secrets.",
        },
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        benchmark_case_path=str(source_path),
        dry_run=True,
    )["record"]

    joined = "\n".join([record["anti_pattern_warning"], *record["uncertainty_notes"]]).lower()
    assert "security" in joined
    assert "secret" in joined or "api key" in joined


def test_external_untrusted_source_adds_source_trust_warning(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(
        repo / ".agent" / "external_queue" / "queue-1" / "lesson.json",
        _lesson_source(
            source="external_queue",
            source_item_path=".agent/external_queue/queue-1/external_queue_item.json",
            summary="External Discord note suggests looking at checkout totals.",
        ),
    )

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["record"]

    joined = "\n".join([record["anti_pattern_warning"], *record["uncertainty_notes"]]).lower()
    assert "source-trust" in joined
    assert "untrusted" in joined


def test_mini_quiz_has_three_questions_and_exercise_exists(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["record"]

    assert len(record["mini_quiz"]) == 3
    assert all(isinstance(item, str) and item.endswith("?") for item in record["mini_quiz"])
    assert isinstance(record["mini_exercise"], str)
    assert record["mini_exercise"].strip()


def test_json_includes_required_inert_flags(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    record = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["record"]

    expected = {
        "model_call_performed": False,
        "lesson_promotion_performed": False,
        "anti_lesson_created": False,
        "patch_applied": False,
        "validation_run": False,
        "worker_launch_performed": False,
        "dream_triggered": False,
        "project_evolution_triggered": False,
    }
    for key, expected_value in expected.items():
        assert record[key] is expected_value, key


def test_markdown_includes_required_sections(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    markdown = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        dry_run=True,
    )["markdown"]

    for heading in [
        "# Teaching Card",
        "## Source",
        "## Summary",
        "## What Happened",
        "## Why It Matters",
        "## Common Trap",
        "## Safe Fix Strategy",
        "## Anti-pattern Warning",
        "## Mini Quiz",
        "## Mini Exercise",
        "## Related Artifacts",
        "## Uncertainty Notes",
        "## Execution Boundary",
    ]:
        assert heading in markdown, heading
    assert "No model was called" in markdown
    assert "No patch was applied" in markdown
    assert "No validation was run" in markdown


def test_markdown_smoke_fixtures_are_study_friendly_and_not_raw_json(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    sources = [
        (
            "lesson",
            "lesson_path",
            _write_json(
                repo / ".agent" / "lessons" / "active" / "lesson.json",
                _lesson_source(),
            ),
            ["money helper", "core/checkout.py"],
        ),
        (
            "anti_lesson",
            "anti_lesson_path",
            _write_json(
                repo / ".agent" / "lessons" / "blocked" / "anti.json",
                _anti_lesson_source(),
            ),
            ["Do not delete failing tests", "Delete the failing regression test"],
        ),
        (
            "benchmark_case",
            "benchmark_case_path",
            _write_json(
                repo / "benchmarks" / "cases" / "python" / "case.json",
                {
                    "name": "python_config_env_mismatch",
                    "language": "python",
                    "category": "config_mismatch",
                    "validation_command": "python main.py",
                    "expected_changed_files": ["config.py"],
                    "forbidden_changed_files": ["main.py"],
                    "prompt": "Fix the Python config environment variable mismatch.",
                },
            ),
            ["Benchmark case: python_config_env_mismatch", "config.py"],
        ),
        (
            "failure_report",
            "failure_report_path",
            _write_json(
                repo / ".agent" / "audits" / "failure-report.json",
                {
                    "phase": "14.7a",
                    "guardrail_note": "Read-only verification report.",
                    "run_health": {
                        "passed": 53,
                        "failed": 1,
                        "failure_category_counts": {"security_tool_or_permission": 1},
                    },
                },
            ),
            ["Failure report: 14.7a", "security_tool_or_permission"],
        ),
    ]

    for source_type, arg_name, source_path, expected_bits in sources:
        result = mod.create_lesson_teaching_card(
            repo_path=str(repo),
            dry_run=True,
            created_at="2026-01-01T00:00:00Z",
            teaching_card_id=f"{source_type}-card",
            **{arg_name: str(source_path)},
        )
        markdown = result["markdown"]

        assert result["record"]["source_type"] == source_type
        assert markdown.startswith("# Teaching Card")
        assert markdown.count("## Mini Quiz") == 1
        quiz = markdown.split("## Mini Quiz", 1)[1].split("## Mini Exercise", 1)[0]
        assert quiz.count("\n- ") == 3
        assert "## Execution Boundary" in markdown
        assert "No model was called" in markdown
        for bit in expected_bits:
            assert bit in markdown
        assert not _looks_like_raw_json_blob(markdown)


def test_cli_text_output_is_copy_friendly(capsys: Any, tmp_path: Path):
    cli = _cli_module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--lesson",
            str(source_path),
            "--teaching-card-id",
            "copy-card",
            "--created-at",
            "2026-01-01T00:00:00Z",
        ]
    )
    output = capsys.readouterr().out

    assert rc == 0
    assert "Teaching card id: copy-card" in output
    assert "JSON path:" in output
    assert "Markdown path:" in output
    assert "Copy this Markdown" in output
    assert "copy/study artifact" in output
    assert str(repo / ".agent" / "teaching_cards" / "copy-card" / "teaching_card.md") in output


def test_cli_creates_json_and_markdown(tmp_path: Path, capsys: Any):
    cli = _cli_module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--lesson",
            str(source_path),
            "--teaching-card-id",
            "cli-card",
            "--created-at",
            "2026-01-01T00:00:00Z",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert rc == 0
    parsed = json.loads(output)
    assert parsed["status"] == "card_created"
    assert parsed["record"]["teaching_card_id"] == "cli-card"
    assert Path(parsed["json_path"]).is_file()
    assert Path(parsed["md_path"]).is_file()


def test_cli_json_output_is_deterministic_and_has_no_copy_hint(tmp_path: Path, capsys: Any):
    cli = _cli_module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())
    argv = [
        "--repo-path",
        str(repo),
        "--lesson",
        str(source_path),
        "--teaching-card-id",
        "stable-cli-json",
        "--created-at",
        "2026-01-01T00:00:00Z",
        "--dry-run",
        "--json",
    ]

    first_rc = cli.main(argv)
    first = capsys.readouterr().out
    second_rc = cli.main(argv)
    second = capsys.readouterr().out

    assert first_rc == 0
    assert second_rc == 0
    assert first == second
    assert "Copy this Markdown" not in first
    assert json.loads(first)["record"]["teaching_card_id"] == "stable-cli-json"


def test_cli_dry_run_writes_nothing(tmp_path: Path, capsys: Any):
    cli = _cli_module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    rc = cli.main(
        [
            "--repo-path",
            str(repo),
            "--lesson",
            str(source_path),
            "--teaching-card-id",
            "dry-run-card",
            "--created-at",
            "2026-01-01T00:00:00Z",
            "--dry-run",
            "--json",
        ]
    )
    output = capsys.readouterr().out

    assert rc == 0
    assert json.loads(output)["status"] == "dry_run"
    assert not (repo / ".agent" / "teaching_cards").exists()


def test_cli_missing_source_returns_clean_error(tmp_path: Path, capsys: Any):
    cli = _cli_module()
    repo = _repo(tmp_path)

    rc = cli.main(["--repo-path", str(repo), "--lesson", str(repo / "missing.json")])
    captured = capsys.readouterr()

    assert rc == 1
    assert "source_not_found" in captured.err
    assert not (repo / ".agent" / "teaching_cards").exists()


def test_deterministic_hooks_make_json_output_stable(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())
    kwargs = {
        "repo_path": str(repo),
        "lesson_path": str(source_path),
        "dry_run": True,
        "created_at": "2026-01-01T00:00:00Z",
        "teaching_card_id": "stable",
    }

    first = mod.render_lesson_teaching_card_json(mod.create_lesson_teaching_card(**kwargs))
    second = mod.render_lesson_teaching_card_json(mod.create_lesson_teaching_card(**kwargs))

    assert first == second
    assert json.loads(first)["record"]["teaching_card_id"] == "stable"


def test_no_overwrite_by_default(tmp_path: Path):
    mod = _module()
    repo = _repo(tmp_path)
    source_path = _write_json(repo / ".agent" / "lessons" / "active" / "lesson.json", _lesson_source())

    first = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        teaching_card_id="same-id",
        created_at="2026-01-01T00:00:00Z",
    )
    json_path = Path(first["json_path"])
    changed = json_path.read_text(encoding="utf-8") + "\n"
    json_path.write_text(changed, encoding="utf-8")

    second = mod.create_lesson_teaching_card(
        repo_path=str(repo),
        lesson_path=str(source_path),
        teaching_card_id="same-id",
        created_at="2026-01-01T00:00:00Z",
    )

    assert second["ok"] is False
    assert second["status"] == "already_exists"
    assert json_path.read_text(encoding="utf-8") == changed


def test_no_forbidden_imports_or_calls_in_teaching_card_layers():
    mod = _module()
    cli = _cli_module()
    module_tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    script_tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    calls: set[str] = set()
    for tree in (module_tree, script_tree):
        imports.update(_imported_modules(tree))
        calls.update(_called_names(tree))

    forbidden_import_roots = {
        "agents",
        "anthropic",
        "benchmarks",
        "database",
        "discord",
        "docker",
        "flask",
        "http",
        "httpx",
        "n8n",
        "openai",
        "patching",
        "project_evolution_mode",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "validator",
        "web",
    }
    forbidden_imports = {
        "core.control_engine",
        "core.executor",
        "core.lesson_store",
        "core.project_evolution_mode",
        "core.run_lifecycle",
        "core.sleeping_consultant",
        "core.validator",
        "scripts.run_background_dream_planner",
        "scripts.run_patch_proposal_queue",
        "scripts.seed_lessons_from_benchmark",
        "scripts.seed_lessons_from_proposals",
        "scripts.validate_evolution_patch_sandbox",
    }
    forbidden_calls = {
        "apply_patch",
        "apply_patch_plan",
        "call_api",
        "call_model",
        "connect",
        "create_anti_lesson",
        "create_dream",
        "create_lesson",
        "create_project_evolution",
        "execute",
        "executemany",
        "generate_content",
        "get_embedding",
        "open",
        "promote_lesson",
        "promote",
        "Popen",
        "post",
        "run",
        "run_benchmark",
        "run_benchmarks",
        "run_handoff",
        "run_overnight",
        "run_validation_command",
        "system",
        "urlopen",
    }

    imported_roots = {name.split(".", 1)[0] for name in imports}
    assert imported_roots.isdisjoint(forbidden_import_roots), imported_roots & forbidden_import_roots
    assert imports.isdisjoint(forbidden_imports), imports & forbidden_imports
    assert calls.isdisjoint(forbidden_calls), calls & forbidden_calls


def _imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _called_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _looks_like_raw_json_blob(markdown: str) -> bool:
    lines = markdown.splitlines()
    jsonish_lines = [
        line
        for line in lines
        if line.strip().startswith(("{", "}", '"', "],", "},", "["))
        or re.match(r'\s*"[^"]+"\s*:', line)
    ]
    return len(jsonish_lines) >= 4
