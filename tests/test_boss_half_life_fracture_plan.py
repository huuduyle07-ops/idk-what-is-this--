"""Tests for CMD.N1 - Boss Half-Life Fracture Plan (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.boss_half_life_fracture_plan import (
    COMMANDER_DECISION_STATUSES,
    GUARDRAIL_FALSE_FLAGS,
    RECOMMENDED_SUB_BOSS_FIELDS,
    REPORT_KIND,
    build_boss_half_life_fracture_plan,
    classify_fracture_pressure,
    expected_remaining_complexity,
    render_boss_half_life_fracture_markdown,
    write_boss_half_life_fracture_plan,
)
import scripts.create_boss_half_life_fracture_plan as script


def _plan(**over) -> dict:
    data = {
        "initial_complexity": 100,
        "actual_remaining": 50,
        "attempt": 3,
        "max_attempts": 6,
        "aggressiveness": 2,
        "tolerance": 0.20,
    }
    data.update(over)
    return build_boss_half_life_fracture_plan(**data)


def test_default_parameters_produce_half_life_three():
    plan = _plan()
    assert plan["report_kind"] == REPORT_KIND == "boss_half_life_fracture_plan"
    assert plan["parameters"]["max_attempts"] == 6
    assert plan["parameters"]["aggressiveness"] == 2
    assert plan["parameters"]["half_life"] == 3
    assert plan["parameters"]["tolerance"] == 0.20
    assert plan["decision"]["status"] == "on_track"


def test_expected_remaining_schedule_is_deterministic():
    plan = _plan()
    schedule = plan["example_decay_schedule"]
    assert [row["attempt"] for row in schedule] == [0, 1, 2, 3, 4, 5, 6]
    assert [row["expected_remaining_rounded"] for row in schedule] == [100, 79, 63, 50, 40, 31, 25]
    assert expected_remaining_complexity(100, 3, 3) == 50
    assert round(expected_remaining_complexity(100, 1, 3), 6) == 79.370053


def test_fracture_pressure_is_computed_correctly():
    plan = _plan(actual_remaining=75, attempt=3)
    assert plan["decision"]["expected_remaining"] == 50
    assert plan["decision"]["actual_remaining"] == 75
    assert plan["decision"]["fracture_pressure"] == 1.5
    assert plan["decision"]["status"] == "fracture_recommended"


def test_thresholds_classify_all_decision_statuses():
    assert set(COMMANDER_DECISION_STATUSES) == {
        "ahead_of_decay",
        "on_track",
        "review_recommended",
        "fracture_recommended",
        "hard_fracture_required",
        "invalid_parameters",
    }
    assert classify_fracture_pressure(0.99) == "ahead_of_decay"
    assert classify_fracture_pressure(1.0) == "on_track"
    assert classify_fracture_pressure(1.19) == "on_track"
    assert classify_fracture_pressure(1.2) == "review_recommended"
    assert classify_fracture_pressure(1.49) == "review_recommended"
    assert classify_fracture_pressure(1.5) == "fracture_recommended"
    assert classify_fracture_pressure(1.99) == "fracture_recommended"
    assert classify_fracture_pressure(2.0) == "hard_fracture_required"


def test_invalid_parameters_are_rejected_safely():
    for kwargs in (
        {"initial_complexity": 0},
        {"actual_remaining": -1},
        {"attempt": -1},
        {"attempt": 7},
        {"max_attempts": 0},
        {"aggressiveness": 0},
        {"tolerance": -0.1},
    ):
        plan = _plan(**kwargs)
        assert plan["decision"]["status"] == "invalid_parameters", kwargs
        assert plan["blockers"], kwargs
        assert plan["decision"]["fracture_pressure"] is None
        assert all(value is False for value in plan["guardrails"].values())


def test_markdown_contains_required_sections_and_boundaries():
    md = render_boss_half_life_fracture_markdown(_plan(actual_remaining=100, attempt=3))
    low = md.lower()
    for section in (
        "## summary",
        "## formula",
        "## parameter definitions",
        "## default policy",
        "## example decay schedule",
        "## fracture pressure thresholds",
        "## example boss fracture decision",
        "## recommended sub-boss fields",
        "## integration boundaries",
        "## guardrails",
        "## recommended next phase",
    ):
        assert section in low, section
    for boundary in (
        "cmd.n1 defines the model and report artifact only.",
        "cmd.n1 does not actually decompose tasks.",
        "cmd.n1 does not assign workers.",
        "cmd.n1 does not call models.",
        "cmd.n1 does not launch commander mode.",
        "cmd.n1 does not affect routing.",
    ):
        assert boundary in low


def test_recommended_sub_boss_fields_are_present():
    plan = _plan()
    assert plan["recommended_sub_boss_fields"] == list(RECOMMENDED_SUB_BOSS_FIELDS)
    for field in (
        "sub_boss_id",
        "parent_boss_id",
        "title",
        "goal",
        "scope",
        "expected_complexity",
        "evidence_required",
        "allowed_files",
        "forbidden_files",
        "assigned_role",
        "attempt_budget",
        "completion_signal",
        "rollback_boundary",
        "dependencies",
    ):
        assert field in plan["recommended_sub_boss_fields"]


def test_write_core_helper_writes_fixed_json_and_markdown_artifacts(tmp_path):
    result = write_boss_half_life_fracture_plan(output_dir=tmp_path, actual_remaining=75, attempt=3)
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "boss_half_life_fracture_plan.json"
    assert Path(result["md_path"]).name == "boss_half_life_fracture_plan.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["decision"]["status"] == "fracture_recommended"
    assert Path(result["md_path"]).read_text(encoding="utf-8").startswith("# Boss Half-Life Fracture Plan")


def test_cli_writes_markdown_and_json(tmp_path):
    result = script.run_create_boss_half_life_fracture_plan(
        initial_complexity=100,
        actual_remaining=100,
        attempt=3,
        max_attempts=6,
        aggressiveness=2,
        tolerance=0.20,
        output_dir=str(tmp_path),
    )
    assert result["ok"] is True
    assert result["summary"]["decision_status"] == "hard_fracture_required"
    assert result["summary"]["fracture_pressure"] == 2
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_cli_json_prints_summary_json(tmp_path, capsys):
    code = script.main(
        [
            "--initial-complexity",
            "100",
            "--actual-remaining",
            "75",
            "--attempt",
            "3",
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision_status"] == "fracture_recommended"
    assert printed["recommended_next_phase"] == "CMD.N2"


def test_guardrails_are_all_false():
    guardrails = _plan()["guardrails"]
    assert set(guardrails) == set(GUARDRAIL_FALSE_FLAGS)
    assert all(value is False for value in guardrails.values())


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "boss_half_life_fracture_plan.py"
_SCRIPT = _ROOT / "scripts" / "create_boss_half_life_fracture_plan.py"


def test_source_has_no_forbidden_imports_or_execution_calls():
    for path in (_CORE, _SCRIPT):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                imported = " ".join(names + [module])
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


def test_registry_and_picker_recommend_cmd_n4_after_cmd_n3():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["MIRROR.CLOSE3"]["status"] == "complete"
    assert phases["CMD.N1"]["status"] == "complete"
    assert phases["CMD.N1"]["prerequisites"] == ["MIRROR.CLOSE3"]
    assert phases["CMD.N2"]["status"] == "complete"
    assert phases["CMD.N2"]["prerequisites"] == ["CMD.N1"]
    assert phases["CMD.N3"]["status"] == "complete"
    assert phases["CMD.N3"]["prerequisites"] == ["CMD.N2"]
    assert phases["CMD.N4"]["status"] == "complete"
    assert phases["CMD.N4"]["prerequisites"] == ["CMD.N3"]
    assert phases["CMD.N5"]["status"] == "complete"
    assert phases["CMD.N5"]["prerequisites"] == ["CMD.N4"]
    assert phases["CMD.N6"]["status"] == "complete"
    assert phases["CMD.N6"]["prerequisites"] == ["CMD.N5"]
    assert phases["CMD.CLOSE"]["status"] == "complete"
    assert phases["CMD.CLOSE"]["prerequisites"] == ["CMD.N6"]
    assert phases["MODEL.N1"]["status"] == "proposed"
    assert phases["MODEL.N1"]["prerequisites"] == ["CMD.CLOSE"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "MODEL.N1"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
