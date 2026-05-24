"""Phase 12.5j — tests for the read-only ESLint/Pylint adapter."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import linter_adapter


# ---------------- helpers ----------------

def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _read_findings(repo: Path) -> list[dict]:
    out = repo / ".agent" / "linter" / "findings.json"
    return json.loads(out.read_text(encoding="utf-8"))


def _make_repo_file(repo: Path, rel: str, content: str = "// stub\n") -> Path:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------- ESLint ----------------

def test_eslint_report_is_normalized(tmp_path):
    target = _make_repo_file(tmp_path, "src/foo.js")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {
            "filePath": str(target),
            "messages": [
                {
                    "ruleId": "no-unused-vars",
                    "severity": 2,
                    "message": "x is defined but never used",
                    "line": 3,
                    "column": 7,
                },
                {
                    "ruleId": "semi",
                    "severity": 1,
                    "message": "Missing semicolon",
                    "line": 5,
                    "column": 12,
                },
            ],
        }
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        eslint_json=str(eslint_path),
    )

    findings = _read_findings(tmp_path)
    assert summary["imported"] == 2
    assert summary["skipped"] == 0
    assert {f["rule_id"] for f in findings} == {"no-unused-vars", "semi"}
    err = next(f for f in findings if f["rule_id"] == "no-unused-vars")
    assert err["tool"] == "eslint"
    assert err["file"] == "src/foo.js"
    assert err["line"] == 3
    assert err["column"] == 7
    assert err["severity"] == "error"
    assert err["message"] == "x is defined but never used"
    assert err["symbol"] is None
    assert err["source"] == "external_linter"

    warn = next(f for f in findings if f["rule_id"] == "semi")
    assert warn["severity"] == "warning"


# ---------------- Pylint ----------------

def test_pylint_report_is_normalized(tmp_path):
    _make_repo_file(tmp_path, "src/foo.py", "# stub\n")
    pylint_path = tmp_path / "pylint.json"
    _write_json(pylint_path, [
        {
            "type": "warning",
            "module": "src.foo",
            "obj": "",
            "line": 10,
            "column": 4,
            "path": "src/foo.py",
            "symbol": "unused-import",
            "message": "Unused import json",
            "message-id": "W0611",
        },
        {
            "type": "convention",
            "module": "src.foo",
            "obj": "Foo",
            "line": 1,
            "column": 0,
            "path": "src/foo.py",
            "symbol": "missing-class-docstring",
            "message": "Missing class docstring",
            "message-id": "C0115",
        },
        {
            "type": "error",
            "module": "src.foo",
            "obj": "bar",
            "line": 22,
            "column": 8,
            "path": "src/foo.py",
            "symbol": "undefined-variable",
            "message": "Undefined variable 'qux'",
            "message-id": "E0602",
        },
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        pylint_json=str(pylint_path),
    )

    findings = _read_findings(tmp_path)
    assert summary["imported"] == 3
    assert summary["skipped"] == 0

    by_id = {f["rule_id"]: f for f in findings}
    assert by_id["W0611"]["severity"] == "warning"
    assert by_id["W0611"]["tool"] == "pylint"
    assert by_id["W0611"]["file"] == "src/foo.py"
    assert by_id["W0611"]["line"] == 10
    assert by_id["W0611"]["column"] == 4
    assert by_id["W0611"]["source"] == "external_linter"
    assert by_id["W0611"]["symbol"] is None
    assert by_id["C0115"]["severity"] == "info"
    assert by_id["E0602"]["severity"] == "error"


# ---------------- path handling ----------------

def test_windows_style_backslash_path_normalizes_to_slash(tmp_path):
    """A backslash-style filePath must normalize to forward slashes in the
    output, regardless of host OS. On Windows the input is realistic; on
    Linux/macOS this still exercises the backslash-to-slash conversion path.
    """
    target = _make_repo_file(tmp_path, "src/sub/foo.js")
    win_style = str(target).replace("/", "\\")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {
            "filePath": win_style,
            "messages": [{
                "ruleId": "x", "severity": 2, "message": "m",
                "line": 1, "column": 1,
            }],
        }
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        eslint_json=str(eslint_path),
    )

    findings = _read_findings(tmp_path)
    assert summary["imported"] == 1
    assert findings[0]["file"] == "src/sub/foo.js"
    # No backslashes leak into the normalized output.
    assert "\\" not in findings[0]["file"]


def test_normalize_path_unit_handles_backslashes(tmp_path):
    """Unit test the path normalizer directly with a relative backslash path."""
    _make_repo_file(tmp_path, "src/foo.js")
    repo_root = tmp_path.resolve()
    assert linter_adapter._normalize_path("src\\foo.js", repo_root) == "src/foo.js"


def test_path_outside_repo_is_skipped(tmp_path):
    """A finding for a file outside `repo_path` must be counted as skipped
    and never appear in the output.
    """
    outside_dir = tmp_path.parent / "outside_repo_phase12_5j"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "evil.js"
    outside_file.write_text("// outside\n", encoding="utf-8")
    try:
        eslint_path = tmp_path / "eslint.json"
        _write_json(eslint_path, [
            {
                "filePath": str(outside_file),
                "messages": [{
                    "ruleId": "x", "severity": 2, "message": "m",
                    "line": 1, "column": 1,
                }],
            }
        ])

        summary = linter_adapter.import_linter_findings(
            repo_path=str(tmp_path),
            eslint_json=str(eslint_path),
        )

        findings = _read_findings(tmp_path)
        assert summary["imported"] == 0
        # The one dropped message must be counted as skipped.
        assert summary["skipped"] == 1
        assert findings == []
    finally:
        try:
            outside_file.unlink()
            outside_dir.rmdir()
        except OSError:
            pass


# ---------------- robustness ----------------

def test_malformed_entries_are_skipped_not_fatal(tmp_path):
    """Garbage entries must increment `skipped` instead of raising."""
    _make_repo_file(tmp_path, "src/foo.js")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        # Garbage 1: not a dict.
        "this is not a file entry",
        # Garbage 2: valid file but messages list contains a non-dict.
        {
            "filePath": str(tmp_path / "src" / "foo.js"),
            "messages": [
                "not a message",
                {
                    "ruleId": "ok-rule",
                    "severity": 2,
                    "message": "valid",
                    "line": 1,
                    "column": 1,
                },
                # Message with unknown severity code.
                {
                    "ruleId": "skipped",
                    "severity": 99,
                    "message": "weird",
                    "line": 1,
                    "column": 1,
                },
                # Message with non-string message field.
                {
                    "ruleId": "skipped-2",
                    "severity": 2,
                    "message": 12345,
                    "line": 1,
                    "column": 1,
                },
            ],
        },
        # Garbage 3: messages is not a list (and not None).
        {"filePath": str(tmp_path / "src" / "foo.js"), "messages": "nope"},
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        eslint_json=str(eslint_path),
    )

    findings = _read_findings(tmp_path)
    assert summary["imported"] == 1
    assert findings[0]["rule_id"] == "ok-rule"
    # 4 malformed bits: top-level string, "not a message", severity 99,
    # non-string message field; plus 1 for the bad "messages" field.
    assert summary["skipped"] >= 4


def test_pylint_unknown_type_is_skipped(tmp_path):
    _make_repo_file(tmp_path, "src/foo.py", "# stub\n")
    pylint_path = tmp_path / "pylint.json"
    _write_json(pylint_path, [
        {
            "type": "totally-unknown",
            "path": "src/foo.py",
            "line": 1,
            "column": 1,
            "symbol": "x",
            "message": "y",
            "message-id": "X1234",
        }
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        pylint_json=str(pylint_path),
    )

    findings = _read_findings(tmp_path)
    assert summary["imported"] == 0
    assert summary["skipped"] == 1
    assert findings == []


def test_output_directory_is_created_safely(tmp_path):
    """The `.agent/linter/` subtree must be created on demand if missing."""
    assert not (tmp_path / ".agent").exists()
    _make_repo_file(tmp_path, "src/foo.js")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {
            "filePath": str(tmp_path / "src" / "foo.js"),
            "messages": [{
                "ruleId": "x", "severity": 1, "message": "m",
                "line": 1, "column": 1,
            }],
        }
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        eslint_json=str(eslint_path),
    )

    out_file = tmp_path / ".agent" / "linter" / "findings.json"
    assert out_file.is_file()
    assert Path(summary["output"]).resolve() == out_file.resolve()


def test_zero_messages_file_does_not_count_as_skipped(tmp_path):
    """A clean ESLint file entry (empty messages list) is normal — not an
    error and must not inflate the skipped count.
    """
    _make_repo_file(tmp_path, "src/clean.js")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {"filePath": str(tmp_path / "src" / "clean.js"), "messages": []}
    ])

    summary = linter_adapter.import_linter_findings(
        repo_path=str(tmp_path),
        eslint_json=str(eslint_path),
    )
    assert summary["imported"] == 0
    assert summary["skipped"] == 0


# ---------------- CLI ----------------

def _import_cli():
    """Import the CLI script as a module without executing main()."""
    spec_path = PROJECT_ROOT / "scripts" / "import_linter_findings.py"
    sys.path.insert(0, str(spec_path.parent))
    try:
        mod = importlib.import_module("import_linter_findings")
        # Reload so any prior import sees fresh state if files changed.
        return importlib.reload(mod)
    finally:
        sys.path.pop(0)


def test_cli_friendly_error_for_missing_eslint_report(tmp_path, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(tmp_path),
        "--eslint-json", str(tmp_path / "does-not-exist.json"),
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error" in captured.err.lower()
    assert "does-not-exist.json" in captured.err


def test_cli_friendly_error_for_missing_pylint_report(tmp_path, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(tmp_path),
        "--pylint-json", str(tmp_path / "nope.json"),
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error" in captured.err.lower()


def test_cli_requires_at_least_one_report(tmp_path, capsys):
    cli = _import_cli()
    exit_code = cli.main(["--repo-path", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--eslint-json" in captured.err or "--pylint-json" in captured.err


def test_cli_combines_eslint_and_pylint(tmp_path, capsys):
    _make_repo_file(tmp_path, "src/foo.js")
    _make_repo_file(tmp_path, "src/foo.py", "# stub\n")

    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {
            "filePath": str(tmp_path / "src" / "foo.js"),
            "messages": [{
                "ruleId": "no-unused-vars",
                "severity": 2,
                "message": "m",
                "line": 4,
                "column": 1,
            }],
        }
    ])

    pylint_path = tmp_path / "pylint.json"
    _write_json(pylint_path, [
        {
            "type": "warning",
            "module": "src.foo",
            "obj": "",
            "line": 2,
            "column": 1,
            "path": "src/foo.py",
            "symbol": "unused-import",
            "message": "Unused import",
            "message-id": "W0611",
        }
    ])

    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(tmp_path),
        "--eslint-json", str(eslint_path),
        "--pylint-json", str(pylint_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    findings = _read_findings(tmp_path)
    assert any(f["tool"] == "eslint" for f in findings)
    assert any(f["tool"] == "pylint" for f in findings)
    assert len(findings) == 2

    # Console summary contains all three required lines.
    assert "imported: 2" in captured.out
    assert "skipped: 0" in captured.out
    assert "output: " in captured.out
    # Output line uses the project-relative form when possible.
    assert ".agent/linter/findings.json" in captured.out


def test_cli_friendly_error_for_invalid_json(tmp_path, capsys):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(tmp_path),
        "--eslint-json", str(bad_path),
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error" in captured.err.lower()


def test_cli_friendly_error_for_bad_repo_path(tmp_path, capsys):
    missing = tmp_path / "does-not-exist-as-repo"
    _make_repo_file(tmp_path, "src/foo.js")
    eslint_path = tmp_path / "eslint.json"
    _write_json(eslint_path, [
        {"filePath": str(tmp_path / "src" / "foo.js"), "messages": []}
    ])
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(missing),
        "--eslint-json", str(eslint_path),
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error" in captured.err.lower()
