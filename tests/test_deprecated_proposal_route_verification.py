"""A.14 tests: Deprecated Proposal Route Verification.

This phase is report-only. The verifier scans repository text for the
legacy/manual proposal candidate route and writes JSON/Markdown artifacts
without importing Flask, model clients, DB modules, subprocess, or lesson write
paths.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.deprecated_proposal_route_verification import (
    ROUTE_FUNCTION,
    ROUTE_PATH,
    VERIFICATION_VERSION,
    build_report,
    classify_route,
    recommendation_for,
    render_markdown,
    scan_route_callers,
    write_artifacts,
)

MODULE_PATH = PROJECT_ROOT / "core" / "deprecated_proposal_route_verification.py"
CLI_PATH = PROJECT_ROOT / "scripts" / "verify_deprecated_proposal_route.py"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _all_imported_modules(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            modules.add(mod)
            modules.add(mod.split(".")[0])
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _ast_call_names(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_report_builds_json_and_markdown():
    report = build_report(repo_path=PROJECT_ROOT)
    assert report["verification_version"] == VERIFICATION_VERSION
    assert report["route"]["path"] == ROUTE_PATH
    assert "callers" in report
    assert "safety" in report

    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    assert ROUTE_PATH in encoded

    md = render_markdown(report)
    assert "# Deprecated Proposal Route Verification" in md
    assert ROUTE_PATH in md
    assert "## Classification" in md


def test_target_route_string_is_present_in_report():
    report = build_report(repo_path=PROJECT_ROOT)
    text = json.dumps(report, ensure_ascii=False) + "\n" + render_markdown(report)
    assert ROUTE_PATH in text
    assert ROUTE_FUNCTION in text


def test_route_definition_is_detected():
    report = build_report(repo_path=PROJECT_ROOT)
    route = report["route"]
    assert route["defined"] is True
    assert route["file"] == "web/app.py"
    assert route["function_name"] == ROUTE_FUNCTION
    assert route["path"] == ROUTE_PATH
    assert route["http_methods"] == ["POST"]


def test_ui_caller_scan_finds_fetch_form_data_and_constants():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root / "web" / "templates" / "index.html",
            f"""
            <form action="{ROUTE_PATH}" method="post"></form>
            <button data-endpoint="{ROUTE_PATH}">Create</button>
            <script>
              const proposalRoute = "{ROUTE_PATH}";
              fetch("{ROUTE_PATH}", {{method: "POST"}});
            </script>
            """,
        )
        scan = scan_route_callers(root)
        files = {m["file"] for m in scan["ui"]}
        assert "web/templates/index.html" in files
        assert len(scan["ui"]) >= 4


def test_test_caller_scan_finds_route_and_function_name():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(
            root / "tests" / "test_route.py",
            f"""
            def test_route(client):
                client.post("{ROUTE_PATH}")

            def test_function_name():
                assert "{ROUTE_FUNCTION}"
            """,
        )
        scan = scan_route_callers(root)
        assert {m["pattern"] for m in scan["tests"]} >= {"route_path", "function_name"}


def test_script_core_docs_scan_finds_fixture_references():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write(root / "scripts" / "probe.py", f'URL = "{ROUTE_PATH}"\n')
        _write(root / "core" / "probe.py", f'NAME = "{ROUTE_FUNCTION}"\n')
        _write(root / "docs" / "proposal-route.md", f"Manual route: `{ROUTE_PATH}`\n")

        scan = scan_route_callers(root)
        assert any(m["file"] == "scripts/probe.py" for m in scan["scripts_core"])
        assert any(m["file"] == "core/probe.py" for m in scan["scripts_core"])
        assert any(m["file"] == "docs/proposal-route.md" for m in scan["docs"])


def test_classification_active_ui_caller():
    classification = classify_route(
        route_defined=True,
        callers={"ui": [{"file": "web/templates/index.html"}], "tests": [], "scripts_core": [], "docs": []},
        safety={"safe": True},
    )
    assert classification == "active_caller_found"


def test_classification_tests_only():
    classification = classify_route(
        route_defined=True,
        callers={"ui": [], "tests": [{"file": "tests/test_route.py"}], "scripts_core": [], "docs": []},
        safety={"safe": True},
    )
    assert classification == "test_only"


def test_classification_docs_only():
    classification = classify_route(
        route_defined=True,
        callers={"ui": [], "tests": [], "scripts_core": [], "docs": [{"file": "README.md"}]},
        safety={"safe": True},
    )
    assert classification == "docs_only"


def test_classification_no_callers_but_defined_is_unused_but_safe():
    classification = classify_route(
        route_defined=True,
        callers={"ui": [], "tests": [], "scripts_core": [], "docs": []},
        safety={"safe": True},
    )
    assert classification == "unused_but_safe"


def test_classification_unsafe_needs_fix():
    classification = classify_route(
        route_defined=True,
        callers={"ui": [], "tests": [], "scripts_core": [], "docs": []},
        safety={"safe": False},
    )
    assert classification == "unsafe_needs_fix"


def test_recommendation_logic():
    assert recommendation_for("active_caller_found") == "keep_and_document"
    assert recommendation_for("test_only") == "freeze_and_deprecate_later"
    assert recommendation_for("manual_legacy_surface") == "freeze_and_deprecate_later"
    assert recommendation_for("unsafe_needs_fix") == "fix_before_freeze"


def test_write_artifacts_produces_json_and_md():
    with tempfile.TemporaryDirectory() as td:
        report = build_report(repo_path=PROJECT_ROOT)
        paths = write_artifacts(report, audits_root=td)
        assert "json" in paths
        assert "markdown" in paths
        assert Path(paths["json"]).is_file()
        assert Path(paths["markdown"]).is_file()
        assert "deprecated-proposal-route-verification" in Path(paths["json"]).name
        payload = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
        assert payload["route"]["path"] == ROUTE_PATH


def test_report_only_import_and_side_effect_guard():
    assert MODULE_PATH.is_file(), f"{MODULE_PATH} not found"
    modules = _all_imported_modules(MODULE_PATH)
    imported_roots = {m.split(".", 1)[0] for m in modules if m}
    forbidden_roots = {
        "agents",
        "benchmarks",
        "database",
        "flask",
        "httpx",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "web",
    }
    assert imported_roots.isdisjoint(forbidden_roots)

    calls = _ast_call_names(MODULE_PATH)
    forbidden_calls = {
        "save_candidate_lesson",
        "save_raw_lesson_record",
        "promote_lesson",
        "apply_patch",
        "run_benchmarks",
        "Popen",
        "check_call",
        "check_output",
        "system",
    }
    assert calls.isdisjoint(forbidden_calls)


def test_cli_file_exists_and_dry_run_does_not_write():
    assert CLI_PATH.is_file(), f"{CLI_PATH} not found"
    from scripts.verify_deprecated_proposal_route import _main

    with tempfile.TemporaryDirectory() as td:
        audits_root = Path(td) / "audits"
        ret = _main(["--repo-path", str(PROJECT_ROOT), "--audits-root", str(audits_root), "--dry-run"])
        assert ret == 0
        assert not audits_root.exists()
