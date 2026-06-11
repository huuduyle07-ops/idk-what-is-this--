"""Phase 12.9a - Generated Artifact Ledger.

A benchmark validation command can create runtime artifacts (e.g.
``customer_report.png`` from ``plt.savefig(...)``). Reporting these as plain
"changed files" alongside the intended patch is misleading. This ledger
separates:

* patched_files        - files the patch intentionally changed (expected)
* generated_artifacts  - files created/modified by validation/runtime output
                         AND explicitly allowed by case config
* unexpected_mutations - changed files that are neither of the above

forbidden_changed_files stays strict: a forbidden file that changes still
fails, even if it is also listed in allowed_generated_files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import web.runner  # noqa: E402  (patched in integration tests)
from benchmarks import run_benchmarks as rb  # noqa: E402
from benchmarks.artifact_ledger import (  # noqa: E402
    classify_changed_files,
    is_generated_artifact_path,
)


# --------------------------------------------------------------------------
# Pure classifier unit tests
# --------------------------------------------------------------------------

def _case(*, expected=None, forbidden=None, allowed=None) -> dict:
    return {
        "name": "demo",
        "expected_changed_files": expected if expected is not None else ["app.py"],
        "forbidden_changed_files": forbidden or [],
        "allowed_generated_files": allowed if allowed is not None else [],
    }


def test_classifies_expected_changed_files_as_patched():
    led = classify_changed_files(_case(expected=["app.py"]), ["app.py"])
    assert led["patched_files"] == ["app.py"]
    assert led["generated_artifacts"] == []
    assert led["unexpected_mutations"] == []


def test_classifies_allowed_generated_files_as_generated_artifacts():
    case = _case(expected=["app.py"], allowed=["customer_report.png"])
    led = classify_changed_files(case, ["app.py", "customer_report.png"])
    assert led["patched_files"] == ["app.py"]
    assert led["generated_artifacts"] == ["customer_report.png"]
    assert led["unexpected_mutations"] == []


def test_marks_extra_changed_files_as_unexpected_mutations():
    case = _case(expected=["app.py"], allowed=["report.png"])
    led = classify_changed_files(case, ["app.py", "report.png", "scratch.tmp"])
    assert led["unexpected_mutations"] == ["scratch.tmp"]
    assert "scratch.tmp" not in led["patched_files"]
    assert "scratch.tmp" not in led["generated_artifacts"]


def test_forbidden_not_laundered_even_if_listed_as_allowed_generated():
    # A file in BOTH forbidden and allowed_generated must never be reported as a
    # generated artifact (allowed_generated must not override forbidden), and it
    # must not be hidden in unexpected_mutations either - forbidden keeps its
    # own category/failure signal.
    case = _case(
        expected=["app.py"],
        forbidden=["customers.csv"],
        allowed=["customers.csv"],
    )
    led = classify_changed_files(case, ["app.py", "customers.csv"])
    assert "customers.csv" not in led["generated_artifacts"]
    assert "customers.csv" not in led["unexpected_mutations"]
    assert "customers.csv" not in led["patched_files"]
    assert led["patched_files"] == ["app.py"]


def test_classifier_is_deterministic_and_sorted():
    case = _case(expected=["b.py", "a.py"], allowed=["z.png", "y.png"])
    led = classify_changed_files(
        case, ["b.py", "a.py", "z.png", "y.png", "m.tmp", "c.tmp"]
    )
    assert led["patched_files"] == ["a.py", "b.py"]
    assert led["generated_artifacts"] == ["y.png", "z.png"]
    assert led["unexpected_mutations"] == ["c.tmp", "m.tmp"]


def test_missing_allowed_generated_key_defaults_empty():
    case = {"expected_changed_files": ["app.py"], "forbidden_changed_files": []}
    led = classify_changed_files(case, ["app.py", "out.png"])
    assert led["patched_files"] == ["app.py"]
    assert led["generated_artifacts"] == []
    assert led["unexpected_mutations"] == ["out.png"]


def test_no_default_glob_patterns():
    # A pattern like "*.csv" must NOT match files by glob - exact paths only.
    case = _case(expected=["app.py"], allowed=["*.csv"])
    led = classify_changed_files(case, ["app.py", "customers.csv"])
    assert led["generated_artifacts"] == []
    assert led["unexpected_mutations"] == ["customers.csv"]


def test_dotnet_bin_obj_artifacts_are_generated_artifact_paths():
    generated_paths = [
        "buggy_repo/obj/Debug/net10.0/App.AssemblyInfo.cs",
        "buggy_repo/obj/Debug/net10.0/App.AssemblyInfoInputs.cache",
        "buggy_repo/obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig",
        "buggy_repo/obj/project.assets.json",
        "buggy_repo/bin/Debug/net10.0/App.dll",
        "buggy_repo/bin/Debug/net10.0/App.pdb",
        "buggy_repo/bin/Debug/net10.0/apphost.exe",
    ]

    for path in generated_paths:
        assert is_generated_artifact_path(path), path


def test_dotnet_generated_artifact_matching_is_path_normalized():
    assert is_generated_artifact_path(
        r"buggy_repo\obj\Debug\net10.0\App.AssemblyInfo.cs"
    )
    assert is_generated_artifact_path(
        r"buggy_repo\bin\Debug\net10.0\App.dll"
    )


def test_dotnet_source_files_outside_build_outputs_are_not_generated():
    for path in [
        "buggy_repo/DataService.cs",
        "buggy_repo/ScoreReport.cs",
        "buggy_repo/Program.cs",
        "src/App.AssemblyInfo.cs",
    ]:
        assert not is_generated_artifact_path(path), path


def test_csharp_build_outputs_are_reported_as_generated_not_unexpected():
    case = _case(expected=["DataService.cs"])
    changed = [
        "DataService.cs",
        "obj/Debug/net10.0/App.AssemblyInfo.cs",
        "obj/Debug/net10.0/App.AssemblyInfoInputs.cache",
        "obj/Debug/net10.0/App.GeneratedMSBuildEditorConfig.editorconfig",
        "obj/project.assets.json",
        "bin/Debug/net10.0/App.dll",
        "bin/Debug/net10.0/App.pdb",
        "bin/Debug/net10.0/apphost.exe",
    ]

    led = classify_changed_files(case, changed)

    assert led["patched_files"] == ["DataService.cs"]
    assert led["generated_artifacts"] == sorted(changed[1:])
    assert led["unexpected_mutations"] == []


def test_real_non_generated_wrong_file_still_reports_unexpected():
    case = _case(expected=["DataService.cs"])
    led = classify_changed_files(
        case,
        [
            "DataService.cs",
            "Program.cs",
            "obj/Debug/net10.0/App.AssemblyInfo.cs",
        ],
    )

    assert led["patched_files"] == ["DataService.cs"]
    assert led["generated_artifacts"] == [
        "obj/Debug/net10.0/App.AssemblyInfo.cs"
    ]
    assert led["unexpected_mutations"] == ["Program.cs"]


def test_check_case_rejects_non_list_allowed_generated_files(tmp_path):
    case_file = _write_case(tmp_path)
    case = json.loads(case_file.read_text(encoding="utf-8"))
    case["allowed_generated_files"] = "customer_report.png"
    case_file.write_text(json.dumps(case), encoding="utf-8")

    result = rb.check_case(case_file)

    assert result["ok"] is False
    assert "allowed_generated_files must be a list" in result["errors"]


# --------------------------------------------------------------------------
# Real pandas case config
# --------------------------------------------------------------------------

def test_pandas_case_reports_app_patched_and_report_generated():
    case_file = Path(
        "benchmarks/cases/python/"
        "python_pandas_iloc_off_by_one_and_decoy_enumerate/case.json"
    )
    case = json.loads(case_file.read_text(encoding="utf-8"))
    assert case.get("allowed_generated_files") == ["customer_report.png"]

    led = classify_changed_files(case, ["app.py", "customer_report.png"])
    assert led["patched_files"] == ["app.py"]
    assert led["generated_artifacts"] == ["customer_report.png"]
    assert led["unexpected_mutations"] == []


# --------------------------------------------------------------------------
# run_case integration (JSON report fields + scoring unchanged)
# --------------------------------------------------------------------------

def _write_case(tmp_path: Path, *, expected=None, forbidden=None, allowed=None,
                validation="python --version") -> Path:
    case_dir = tmp_path / "case"
    buggy = case_dir / "buggy_repo"
    buggy.mkdir(parents=True)
    (buggy / "app.py").write_text("print('hi')\n", encoding="utf-8")
    if forbidden:
        for f in forbidden:
            (buggy / f).write_text("original\n", encoding="utf-8")
    case = {
        "name": "demo_case",
        "language": "python",
        "validation_command": validation,
        "expected_changed_files": expected or ["app.py"],
        "forbidden_changed_files": forbidden or [],
        "prompt": "fix it",
    }
    if allowed is not None:
        case["allowed_generated_files"] = allowed
    case_file = case_dir / "case.json"
    case_file.write_text(json.dumps(case), encoding="utf-8")
    return case_file


def _patch_agent(monkeypatch, mutate):
    def fake_agent(*args, **kwargs):
        repo = Path(kwargs["repo_path"])
        mutate(repo)
        return {"answer": "", "validation": ""}

    # run_case uses a local `from web.runner import run_agent_web`, so we must
    # patch it on the source module, not on run_benchmarks.
    monkeypatch.setattr(web.runner, "run_agent_web", fake_agent)


def test_run_case_report_includes_ledger_fields(tmp_path, monkeypatch):
    case_file = _write_case(tmp_path, expected=["app.py"], allowed=["out.png"])

    def mutate(repo):
        (repo / "app.py").write_text("print('fixed')\n", encoding="utf-8")
        (repo / "out.png").write_bytes(b"PNGDATA")

    _patch_agent(monkeypatch, mutate)
    result = rb.run_case(case_file)

    assert result["changed_files"] == ["app.py", "out.png"]
    assert result["patched_files"] == ["app.py"]
    assert result["generated_artifacts"] == ["out.png"]
    assert result["unexpected_mutations"] == []


def test_run_case_marks_extra_file_as_unexpected_mutation(tmp_path, monkeypatch):
    case_file = _write_case(tmp_path, expected=["app.py"], allowed=["out.png"])

    def mutate(repo):
        (repo / "app.py").write_text("print('fixed')\n", encoding="utf-8")
        (repo / "out.png").write_bytes(b"PNGDATA")
        (repo / "scratch.tmp").write_text("junk\n", encoding="utf-8")

    _patch_agent(monkeypatch, mutate)
    result = rb.run_case(case_file)

    assert result["generated_artifacts"] == ["out.png"]
    assert result["unexpected_mutations"] == ["scratch.tmp"]


def test_run_case_without_allowed_generated_keeps_old_pass_behavior(tmp_path, monkeypatch):
    # Case with no allowed_generated_files: an extra generated file must NOT
    # flip the pass verdict (scoring unchanged); it is reported as an
    # unexpected mutation only.
    case_file = _write_case(tmp_path, expected=["app.py"], validation="python --version")

    def mutate(repo):
        (repo / "app.py").write_text("print('fixed')\n", encoding="utf-8")
        (repo / "extra.log").write_text("x\n", encoding="utf-8")

    _patch_agent(monkeypatch, mutate)
    result = rb.run_case(case_file)

    assert result["success"] is True
    assert result["generated_artifacts"] == []
    assert "extra.log" in result["unexpected_mutations"]
    assert result["patched_files"] == ["app.py"]


def test_run_case_forbidden_in_allowed_generated_still_fails(tmp_path, monkeypatch):
    case_file = _write_case(
        tmp_path,
        expected=["app.py"],
        forbidden=["customers.csv"],
        allowed=["customers.csv"],
    )

    def mutate(repo):
        (repo / "app.py").write_text("print('fixed')\n", encoding="utf-8")
        (repo / "customers.csv").write_text("tampered\n", encoding="utf-8")

    _patch_agent(monkeypatch, mutate)
    result = rb.run_case(case_file)

    assert result["success"] is False
    assert "customers.csv" in result["touched_forbidden_files"]
    assert "customers.csv" not in result["generated_artifacts"]


# --------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------

def test_markdown_report_displays_ledger_categories(tmp_path):
    report = {
        "summary": {"total": 1, "passed": 1, "failed": 0, "pass_rate": 100.0},
        "results": [
            {
                "name": "case_x",
                "success": True,
                "duration_sec": 1.0,
                "changed_files": ["app.py", "customer_report.png"],
                "patched_files": ["app.py"],
                "generated_artifacts": ["customer_report.png"],
                "unexpected_mutations": [],
            },
        ],
    }
    out = tmp_path / "report.md"
    rb.write_markdown_report(report, out)
    md = out.read_text(encoding="utf-8")

    assert "case_x" in md
    assert "customer_report.png" in md
    assert "Patched" in md
    assert "Generated Artifacts" in md
    assert "Unexpected Mutations" in md


def test_markdown_report_back_compatible_without_ledger_fields(tmp_path):
    # Reports predating the ledger (no patched/generated/unexpected) still render.
    report = {
        "summary": {"total": 1, "passed": 1, "failed": 0, "pass_rate": 100.0},
        "results": [
            {
                "name": "case_y",
                "success": True,
                "duration_sec": 1.2,
                "changed_files": ["app.py"],
            },
        ],
    }
    out = tmp_path / "report.md"
    rb.write_markdown_report(report, out)
    md = out.read_text(encoding="utf-8")

    assert "case_y" in md
    assert "app.py" in md
    assert "PASS" in md


def test_cli_output_displays_ledger_categories(tmp_path, monkeypatch, capsys):
    case_file = _write_case(tmp_path)

    def fake_discover_cases(root):
        return [case_file]

    def fake_run_case(case_path, capture):
        assert case_path == case_file
        return {
            "name": "demo_case",
            "success": True,
            "duration_sec": 0.1,
            "language": "python",
            "category": "demo",
            "difficulty": "easy",
            "changed_files": ["app.py", "customer_report.png"],
            "patched_files": ["app.py"],
            "generated_artifacts": ["customer_report.png"],
            "unexpected_mutations": [],
            "missing_expected_files": [],
            "touched_forbidden_files": [],
        }

    monkeypatch.setattr(rb, "discover_cases", fake_discover_cases)
    monkeypatch.setattr(rb, "_run_case_with_capture", fake_run_case)
    monkeypatch.setattr(rb, "collect_brain_stamp", lambda repo: {})
    monkeypatch.setattr(rb, "PROJECT_ROOT", tmp_path)

    exit_code = rb.main(["--case", "demo_case"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "Changed: app.py, customer_report.png" in out
    assert "Patched: app.py" in out
    assert "Generated artifacts: customer_report.png" in out
    assert "Unexpected mutations: none" in out
