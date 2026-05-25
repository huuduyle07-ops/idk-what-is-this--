import json
from pathlib import Path

from benchmarks import run_benchmarks as benchmark_runner


class _FakeConsole:
    encoding = "cp1252"

    def __init__(self) -> None:
        self.calls = []

    def reconfigure(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_configure_console_encoding_uses_utf8_replace_for_windows_glyphs():
    stdout = _FakeConsole()
    stderr = _FakeConsole()

    benchmark_runner.configure_console_encoding(stdout=stdout, stderr=stderr)

    assert stdout.calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_minimal_patch_records_line_counts(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "app.py", "def answer():\n    return 1\n")
    before = benchmark_runner.snapshot_file_texts(repo)

    _write(repo / "app.py", "def answer():\n    return 2\n")
    after = benchmark_runner.snapshot_file_texts(repo)

    minimality = benchmark_runner.compute_patch_minimality(
        before,
        after,
        ["app.py"],
        touched_forbidden_files=[],
    )

    assert minimality["files_touched"] == 1
    assert minimality["added_lines"] == 1
    assert minimality["removed_lines"] == 1
    assert minimality["net_changed_lines"] == 0
    assert minimality["total_changed_lines"] == 2
    assert minimality["touched_test_files"] == 0
    assert minimality["patch_size_score"] == 7


def test_multi_file_patch_records_files_touched(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "app.py", "VALUE = 1\n")
    _write(repo / "helpers.py", "NAME = 'old'\n")
    before = benchmark_runner.snapshot_file_texts(repo)

    _write(repo / "app.py", "VALUE = 2\n")
    _write(repo / "helpers.py", "NAME = 'new'\n")
    after = benchmark_runner.snapshot_file_texts(repo)

    minimality = benchmark_runner.compute_patch_minimality(
        before,
        after,
        ["app.py", "helpers.py"],
        touched_forbidden_files=[],
    )

    assert minimality["files_touched"] == 2
    assert minimality["added_lines"] == 2
    assert minimality["removed_lines"] == 2
    assert minimality["total_changed_lines"] == 4
    assert minimality["patch_size_score"] == 14


def test_test_file_touches_are_counted(tmp_path):
    repo = tmp_path / "repo"
    _write(repo / "src" / "app.py", "VALUE = 1\n")
    _write(repo / "tests" / "test_app.py", "def test_value():\n    assert True\n")
    before = benchmark_runner.snapshot_file_texts(repo)

    _write(repo / "src" / "app.py", "VALUE = 2\n")
    _write(repo / "tests" / "test_app.py", "def test_value():\n    assert False\n")
    after = benchmark_runner.snapshot_file_texts(repo)

    minimality = benchmark_runner.compute_patch_minimality(
        before,
        after,
        ["src/app.py", "tests/test_app.py"],
        touched_forbidden_files=[],
    )

    assert minimality["touched_test_files"] == 1
    assert minimality["patch_size_score"] == 34


def test_missing_patch_diff_produces_unknown_minimality_safely():
    minimality = benchmark_runner.compute_patch_minimality(
        None,
        None,
        [],
        touched_forbidden_files=[],
    )

    assert minimality["status"] == "unknown"
    assert minimality["reason"] == "no_patch"
    assert minimality["total_changed_lines"] is None
    assert minimality["patch_size_score"] is None

    missing_diff = benchmark_runner.compute_patch_minimality(
        None,
        None,
        ["app.py"],
        touched_forbidden_files=[],
    )

    assert missing_diff["status"] == "unknown"
    assert missing_diff["reason"] == "missing_diff_data"
    assert missing_diff["files_touched"] == 1
    assert missing_diff["total_changed_lines"] is None


def test_json_report_includes_per_case_minimality():
    result = benchmark_runner.with_patch_minimality_fields(
        {
            "name": "case_a",
            "success": True,
            "changed_files": ["app.py"],
            "touched_forbidden_files": [],
        },
        {
            "status": "known",
            "reason": None,
            "files_touched": 1,
            "added_lines": 1,
            "removed_lines": 1,
            "net_changed_lines": 0,
            "total_changed_lines": 2,
            "touched_test_files": 0,
            "touched_forbidden_files": [],
            "patch_size_score": 7,
        },
    )
    report = {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "results": [result],
        **benchmark_runner.patch_minimality_aggregates([result]),
    }

    encoded = json.loads(json.dumps(report))

    assert encoded["results"][0]["patch_minimality"]["files_touched"] == 1
    assert encoded["results"][0]["total_changed_lines"] == 2
    assert encoded["average_total_changed_lines"] == 2.0
    assert encoded["average_files_touched"] == 1.0
    assert encoded["largest_patch_case"]["name"] == "case_a"
    assert encoded["smallest_patch_case"]["name"] == "case_a"


def test_markdown_report_renders_patch_minimality_summary(tmp_path):
    result = benchmark_runner.with_patch_minimality_fields(
        {
            "name": "case_a",
            "success": True,
            "duration_sec": 1.0,
            "changed_files": ["app.py"],
            "touched_forbidden_files": [],
        },
        {
            "status": "known",
            "reason": None,
            "files_touched": 1,
            "added_lines": 1,
            "removed_lines": 1,
            "net_changed_lines": 0,
            "total_changed_lines": 2,
            "touched_test_files": 0,
            "touched_forbidden_files": [],
            "patch_size_score": 7,
        },
    )
    report = {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "results": [result],
        **benchmark_runner.patch_minimality_aggregates([result]),
    }
    path = tmp_path / "report.md"

    benchmark_runner.write_markdown_report(report, path)

    markdown = path.read_text(encoding="utf-8")
    assert "## Patch Minimality" in markdown
    assert "Average total changed lines: 2.00" in markdown
    assert "Smallest patch: `case_a`" in markdown
