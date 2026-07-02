"""Tests for CMD.N3 - Commander Fracture Tree Registry (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.commander_fracture_tree_registry import (
    ALLOWED_SUB_BOSS_STATUSES,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_commander_fracture_tree_registry,
    render_commander_fracture_tree_registry_markdown,
    write_commander_fracture_tree_registry,
)
from core.manual_boss_fracture_report import build_manual_boss_fracture_report
import scripts.create_commander_fracture_tree_registry as script


def _sub_boss(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-tree-1",
        "parent_boss_id": "cmd-root",
        "title": "Commander registry contract",
        "goal": "Define the durable fracture tree registry shape",
        "scope": "Report-only registry and tests",
        "expected_complexity": 40,
        "evidence_required": ["registry tests"],
        "allowed_files": ["core/commander_fracture_tree_registry.py", "tests/test_commander_fracture_tree_registry.py"],
        "forbidden_files": ["web/app.py"],
        "assigned_role": "planner",
        "attempt_budget": 2,
        "completion_signal": "registry artifact written",
        "rollback_boundary": "no runtime behavior changes",
        "dependencies": [],
        "status": "ready_for_preflight",
    }
    data.update(over)
    return data


def _source_report(sub_bosses=None, **over) -> dict:
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
        "sub_bosses": [
            _sub_boss(expected_complexity=35),
            _sub_boss(
                sub_boss_id="cmd-tree-2",
                title="Commander registry renderer",
                expected_complexity=40,
                dependencies=["cmd-tree-1"],
            ),
        ]
        if sub_bosses is None
        else sub_bosses,
    }
    data.update(over)
    return build_manual_boss_fracture_report(**data)


def _manual_tree(sub_bosses=None, **over) -> dict:
    data = {
        "root_boss": {
            "boss_id": "cmd-root",
            "title": "Commander root boss",
            "description": "Manual boss description supplied by an operator.",
            "initial_complexity": 100,
            "actual_remaining": 75,
            "attempt": 3,
            "max_attempts": 6,
            "aggressiveness": 2,
            "tolerance": 0.20,
            "fracture_pressure": 1.5,
            "commander_decision": "fracture_recommended",
        },
        "sub_bosses": [
            _sub_boss(expected_complexity=35),
            _sub_boss(
                sub_boss_id="cmd-tree-2",
                title="Commander registry renderer",
                expected_complexity=40,
                dependencies=["cmd-tree-1"],
            ),
        ]
        if sub_bosses is None
        else sub_bosses,
    }
    data.update(over)
    return data


def test_valid_cmd_n2_source_report_creates_registry_artifact(tmp_path):
    source_path = tmp_path / "manual_boss_fracture_report.json"
    source_path.write_text(json.dumps(_source_report(), indent=2), encoding="utf-8")
    result = script.run_create_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        source_report=str(source_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    registry = result["registry"]
    assert registry["report_kind"] == REPORT_KIND == "commander_fracture_tree_registry"
    assert registry["validation_status"] == "registry_ready"
    assert registry["source_report_path"] == str(source_path)
    assert registry["root_boss"]["commander_decision"] == "fracture_recommended"
    assert registry["total_expected_complexity"] == 75
    assert registry["total_attempt_budget"] == 4
    assert registry["dependency_edges"] == [{"from": "cmd-tree-1", "to": "cmd-tree-2"}]


def test_cmd_n2_source_report_defaults_missing_parent_to_root_boss():
    candidate = _sub_boss(expected_complexity=75)
    candidate.pop("parent_boss_id")
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        source_report=_source_report(sub_bosses=[candidate]),
    )
    assert registry["validation_status"] == "registry_ready"
    assert registry["sub_bosses"][0]["parent_boss_id"] == "cmd-root"


def test_valid_manual_tree_file_creates_registry_artifact(tmp_path):
    tree_file = tmp_path / "tree.json"
    tree_file.write_text(json.dumps(_manual_tree(), indent=2), encoding="utf-8")
    result = script.run_create_commander_fracture_tree_registry(
        tree_id="manual-tree",
        boss_id="cmd-root",
        title="Manual fracture tree",
        tree_file=str(tree_file),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert result["registry"]["validation_status"] == "registry_ready"
    assert result["registry"]["sub_bosses"][1]["dependencies"] == ["cmd-tree-1"]
    assert result["registry"]["dependency_edges"] == [{"from": "cmd-tree-1", "to": "cmd-tree-2"}]


def test_minimal_cli_input_creates_incomplete_tree_with_warnings(tmp_path):
    result = write_commander_fracture_tree_registry(
        output_dir=tmp_path,
        tree_id="empty-tree",
        boss_id="cmd-root",
        title="Empty fracture tree",
    )
    assert result["ok"] is True
    registry = result["registry"]
    assert registry["validation_status"] == "incomplete_tree"
    assert registry["root_boss"]["boss_id"] == "cmd-root"
    assert registry["sub_bosses"] == []
    assert any("no source_report or tree_file" in warning for warning in registry["warnings"])


def test_duplicate_sub_boss_ids_block():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(sub_bosses=[_sub_boss(), _sub_boss(title="Duplicate")]),
    )
    assert registry["validation_status"] == "blocked"
    assert any("duplicate sub_boss_id" in reason for reason in registry["blocked_reasons"])


def test_unknown_dependency_blocks():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(sub_bosses=[_sub_boss(dependencies=["missing-sub-boss"])]),
    )
    assert registry["validation_status"] == "blocked"
    assert any("unknown dependency" in reason for reason in registry["blocked_reasons"])


def test_dependency_cycle_blocks():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(
            sub_bosses=[
                _sub_boss(sub_boss_id="a", dependencies=["b"], expected_complexity=35),
                _sub_boss(sub_boss_id="b", dependencies=["a"], expected_complexity=40),
            ]
        ),
    )
    assert registry["validation_status"] == "blocked"
    assert any("dependency cycle" in reason for reason in registry["blocked_reasons"])


def test_unsafe_tree_id_boss_id_and_input_path_block(tmp_path):
    unsafe_source = tmp_path / "missing" / ".." / "report.json"
    result = script.run_create_commander_fracture_tree_registry(
        tree_id="../tree",
        boss_id="../boss",
        title="Unsafe tree",
        source_report=str(unsafe_source),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert "invalid_tree_id" in Path(result["json_path"]).parts
    assert result["registry"]["validation_status"] == "blocked"
    assert any("tree_id" in reason for reason in result["registry"]["blocked_reasons"])
    assert any("boss_id" in reason for reason in result["registry"]["blocked_reasons"])
    assert any("source_report path must not contain traversal" in reason for reason in result["registry"]["blocked_reasons"])


def test_unsafe_allowed_files_and_forbidden_files_block():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(
            sub_bosses=[
                _sub_boss(
                    allowed_files=["../secret"],
                    forbidden_files=["safe/file.py", "core/../bad.py"],
                )
            ]
        ),
    )
    assert registry["validation_status"] == "blocked"
    assert any("allowed_files" in reason for reason in registry["blocked_reasons"])
    assert any("forbidden_files" in reason for reason in registry["blocked_reasons"])


def test_ready_for_preflight_requires_evidence_and_rollback():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(
            sub_bosses=[
                _sub_boss(
                    evidence_required=[],
                    rollback_boundary="",
                    expected_complexity=75,
                    status="ready_for_preflight",
                )
            ]
        ),
    )
    assert registry["validation_status"] == "registry_ready_with_warnings"
    assert any("evidence_required" in warning for warning in registry["warnings"])
    assert any("rollback_boundary" in warning for warning in registry["warnings"])


def test_complexity_mismatch_warns():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(sub_bosses=[_sub_boss(expected_complexity=20)]),
    )
    assert registry["validation_status"] == "registry_ready_with_warnings"
    assert registry["total_expected_complexity"] == 20
    assert any("differs from root actual_remaining" in warning for warning in registry["warnings"])


def test_assigned_role_is_stored_as_advisory_label_only():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(sub_bosses=[_sub_boss(assigned_role="planner")]),
    )
    sub = registry["sub_bosses"][0]
    assert sub["assigned_role"] == "planner"
    assert sub["assigned_role_binding"] == "advisory_label_only"
    assert registry["guardrails"]["automatic_worker_assignment_performed"] is False


def test_malformed_tree_file_blocks_safely(tmp_path):
    tree_file = tmp_path / "bad.json"
    tree_file.write_text("{not-json", encoding="utf-8")
    result = script.run_create_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_file=str(tree_file),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["registry"]["validation_status"] == "blocked"
    assert any("tree_file must contain valid JSON" in reason for reason in result["registry"]["blocked_reasons"])


def test_markdown_contains_required_sections_and_guardrails():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(),
    )
    md = render_commander_fracture_tree_registry_markdown(registry)
    low = md.lower()
    for section in (
        "## summary",
        "## source inputs",
        "## root boss",
        "## sub-boss registry",
        "## dependency graph",
        "## complexity budget",
        "## attempt budget",
        "## validation findings",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "cmd.n3 does not execute sub-bosses" in low
    assert "cmd.n3 does not assign real workers" in low
    assert "cmd.n3 writes registry artifacts only" in low


def test_guardrails_are_all_false():
    registry = build_commander_fracture_tree_registry(
        tree_id="cmd-tree",
        boss_id="cmd-root",
        title="Commander fracture tree",
        tree_data=_manual_tree(),
    )
    assert set(registry["guardrails"]) == set(GUARDRAIL_FALSE_FLAGS)
    assert all(value is False for value in registry["guardrails"].values())
    assert set(ALLOWED_SUB_BOSS_STATUSES) == {
        "proposed",
        "ready_for_preflight",
        "blocked",
        "deferred",
        "completed",
    }


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "commander_fracture_tree_registry.py"
_SCRIPT = _ROOT / "scripts" / "create_commander_fracture_tree_registry.py"


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


def test_registry_and_picker_recommend_cmd_n4():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N2"]["status"] == "complete"
    assert phases["CMD.N3"]["status"] == "complete"
    assert phases["CMD.N3"]["prerequisites"] == ["CMD.N2"]
    assert phases["CMD.N4"]["status"] == "proposed"
    assert phases["CMD.N4"]["prerequisites"] == ["CMD.N3"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "CMD.N4"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
