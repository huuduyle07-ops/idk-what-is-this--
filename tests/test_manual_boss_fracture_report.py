"""Tests for CMD.N2 - Manual Boss Fracture Report (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.manual_boss_fracture_report import (
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    REQUIRED_SUB_BOSS_FIELDS,
    build_manual_boss_fracture_report,
    read_sub_boss_candidates,
    render_manual_boss_fracture_markdown,
    write_manual_boss_fracture_report,
)
import scripts.create_manual_boss_fracture_report as script


def _sub_boss(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-ui-1",
        "parent_boss_id": "cmd-root",
        "title": "Commander preflight contract",
        "goal": "Define the preflight inputs and output schema",
        "scope": "Report-only schema and tests",
        "expected_complexity": 40,
        "evidence_required": ["schema tests", "registry validation"],
        "allowed_files": ["core/...", "tests/..."],
        "forbidden_files": ["web/app.py"],
        "assigned_role": "planner",
        "attempt_budget": 2,
        "completion_signal": "report artifact written and tests pass",
        "rollback_boundary": "no runtime route changes",
        "dependencies": [],
    }
    data.update(over)
    return data


def _report(**over) -> dict:
    data = {
        "boss_id": "cmd-root",
        "title": "Commander root boss",
        "description": "Manual boss description supplied by an operator.",
        "initial_complexity": 100,
        "actual_remaining": 75,
        "attempt": 3,
        "max_attempts": 6,
        "aggressiveness": 2,
        "tolerance": 0.20,
        "sub_bosses": [],
    }
    data.update(over)
    return build_manual_boss_fracture_report(**data)


def test_valid_boss_input_produces_report_artifacts(tmp_path):
    result = write_manual_boss_fracture_report(
        output_dir=tmp_path,
        boss_id="cmd-root",
        title="Commander root boss",
        description="Manual boss description supplied by an operator.",
        initial_complexity=100,
        actual_remaining=80,
        attempt=3,
        max_attempts=6,
        aggressiveness=2,
        tolerance=0.20,
        sub_bosses=[_sub_boss(expected_complexity=80)],
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    assert Path(result["json_path"]).parent.name == "cmd-root"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_kind"] == REPORT_KIND == "manual_boss_fracture_report"
    assert data["boss_input"]["boss_id"] == "cmd-root"
    assert data["manual_sub_boss_candidates"][0]["sub_boss_id"] == "cmd-ui-1"
    assert Path(result["md_path"]).read_text(encoding="utf-8").startswith("# Manual Boss Fracture Report")


def test_uses_cmd_n1_formula_and_thresholds_correctly():
    report = _report(actual_remaining=75, attempt=3)
    assert report["half_life_parameters"]["half_life"] == 3
    assert report["expected_remaining_complexity"] == 50
    assert report["actual_remaining_complexity"] == 75
    assert report["fracture_pressure"] == 1.5
    assert report["commander_decision"]["status"] == "fracture_recommended"


def test_fracture_recommended_with_no_sub_bosses_warns():
    report = _report(actual_remaining=75, attempt=3, sub_bosses=[])
    assert report["commander_decision"]["status"] == "fracture_recommended"
    assert any("no manual sub-boss candidates" in warning for warning in report["warnings"])
    assert report["fracture_tree"]["children"] == []


def test_valid_sub_boss_file_is_included(tmp_path):
    sub_boss_file = tmp_path / "sub_bosses.json"
    sub_boss_file.write_text(json.dumps([_sub_boss(expected_complexity=75)]), encoding="utf-8")
    candidates, blockers = read_sub_boss_candidates(sub_boss_file)
    assert blockers == []
    result = script.run_create_manual_boss_fracture_report(
        boss_id="cmd-root",
        title="Commander root boss",
        description="Manual boss description supplied by an operator.",
        initial_complexity=100,
        actual_remaining=75,
        attempt=3,
        max_attempts=6,
        aggressiveness=2,
        tolerance=0.20,
        sub_boss_file=str(sub_boss_file),
        output_dir=str(tmp_path / "out"),
    )
    assert result["summary"]["sub_boss_count"] == 1
    assert result["report"]["manual_sub_boss_candidates"] == candidates
    assert result["report"]["fracture_tree"]["children"][0]["sub_boss_id"] == "cmd-ui-1"


def test_missing_required_sub_boss_fields_are_reported():
    candidate = {
        "sub_boss_id": "cmd-ui-1",
        "title": "Partial",
        "expected_complexity": 10,
        "evidence_required": [],
    }
    report = _report(actual_remaining=10, attempt=3, sub_bosses=[candidate])
    missing = report["missing_sub_boss_fields"][0]
    assert missing["sub_boss_id"] == "cmd-ui-1"
    assert "assigned_role" in missing["missing_fields"]
    assert "rollback_boundary" in missing["missing_fields"]
    assert "parent_boss_id" in missing["missing_fields"]
    assert any("assigned_role is missing" in warning for warning in report["warnings"])
    assert any("rollback_boundary is missing" in warning for warning in report["warnings"])
    assert any("evidence_required is empty" in warning for warning in report["warnings"])


def test_expected_complexity_sum_mismatch_warns():
    small = _report(actual_remaining=100, attempt=3, sub_bosses=[_sub_boss(expected_complexity=20)])
    large = _report(actual_remaining=50, attempt=3, sub_bosses=[_sub_boss(expected_complexity=90)])
    assert small["sub_boss_complexity_summary"]["expected_complexity_sum"] == 20
    assert any("much smaller than actual_remaining" in warning for warning in small["warnings"])
    assert any("much larger than actual_remaining" in warning for warning in large["warnings"])


def test_unsafe_boss_id_path_traversal_is_blocked(tmp_path):
    result = write_manual_boss_fracture_report(
        output_dir=tmp_path,
        boss_id="../bad",
        title="Unsafe",
        description="Unsafe path input.",
        initial_complexity=100,
        actual_remaining=50,
        attempt=3,
        max_attempts=6,
        aggressiveness=2,
        tolerance=0.20,
    )
    assert result["ok"] is False
    assert "invalid_boss_id" in Path(result["json_path"]).parts
    assert tmp_path.resolve() in Path(result["json_path"]).resolve().parents
    assert result["report"]["commander_decision"]["status"] == "invalid_parameters"
    assert any("boss_id" in blocker for blocker in result["report"]["blockers"])


def test_malformed_sub_boss_json_reports_safely(tmp_path):
    sub_boss_file = tmp_path / "bad.json"
    sub_boss_file.write_text("{not-json", encoding="utf-8")
    result = script.run_create_manual_boss_fracture_report(
        boss_id="cmd-root",
        title="Commander root boss",
        description="Manual boss description supplied by an operator.",
        initial_complexity=100,
        actual_remaining=50,
        attempt=3,
        max_attempts=6,
        aggressiveness=2,
        tolerance=0.20,
        sub_boss_file=str(sub_boss_file),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["commander_decision"]["status"] == "invalid_parameters"
    assert any("sub_boss_file must contain valid JSON" in blocker for blocker in result["report"]["blockers"])


def test_invalid_parameters_produce_invalid_parameters():
    report = _report(initial_complexity=0, sub_bosses=[_sub_boss()])
    assert report["commander_decision"]["status"] == "invalid_parameters"
    assert report["fracture_pressure"] is None
    assert report["blockers"]
    assert all(value is False for value in report["guardrails"].values())


def test_markdown_contains_required_sections_and_guardrails():
    md = render_manual_boss_fracture_markdown(_report(sub_bosses=[_sub_boss(expected_complexity=75)]))
    low = md.lower()
    for section in (
        "## summary",
        "## boss input",
        "## half-life parameters",
        "## expected remaining complexity",
        "## actual remaining complexity",
        "## fracture pressure",
        "## commander decision",
        "## manual sub-boss candidates",
        "## fracture tree",
        "## missing sub-boss fields",
        "## warnings",
        "## guardrails",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "cmd.n2 does not call models" in low
    assert "cmd.n2 does not launch workers" in low
    assert "cmd.n2 writes report artifacts only" in low


def test_guardrails_are_all_false():
    guardrails = _report()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    assert all(value is False for value in guardrails.values())


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "manual_boss_fracture_report.py"
_SCRIPT = _ROOT / "scripts" / "create_manual_boss_fracture_report.py"


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing", "core"}
    for path in (_CORE, _SCRIPT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
                top = module.split(".")[0] if module else ""
                if path == _CORE and top:
                    assert top in allowed_core_imports, f"Unexpected import in core: {module!r}"
                for bad in (
                    "subprocess",
                    "requests",
                    "httpx",
                    "urllib.request",
                    "socket",
                    "aiohttp",
                    "openai",
                    "anthropic",
                    "litellm",
                    "ollama",
                    "generativeai",
                    "sqlite3",
                    "psycopg",
                    "sqlalchemy",
                    "pymongo",
                ):
                    assert bad not in imported, f"{path} imports {bad}"
            elif isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                assert name not in {
                    "Popen",
                    "run",
                    "call",
                    "check_call",
                    "check_output",
                    "urlopen",
                    "request",
                    "run_safe_validation",
                    "run_benchmarks",
                    "apply_patch",
                    "patch_apply",
                    "launch_worker",
                    "worker_launch",
                    "spawn_worker",
                }, f"{path} calls forbidden function {name}"


def test_registry_and_picker_recommend_cmd_n3():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N1"]["status"] == "complete"
    assert phases["CMD.N2"]["status"] == "complete"
    assert phases["CMD.N2"]["prerequisites"] == ["CMD.N1"]
    assert phases["CMD.N3"]["status"] == "proposed"
    assert phases["CMD.N3"]["prerequisites"] == ["CMD.N2"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "CMD.N3"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
