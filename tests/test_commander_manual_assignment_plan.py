"""Tests for CMD.N5 - Commander Manual Assignment Plan (report-only)."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates

from core.commander_manual_assignment_plan import (
    DEFAULT_ROLE_CATALOG,
    REPORT_KIND,
    build_commander_manual_assignment_plan,
    render_commander_manual_assignment_plan_markdown,
    write_commander_manual_assignment_plan,
)
import scripts.create_commander_manual_assignment_plan as script


def _finding(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-n5-core",
        "title": "Commander manual assignment plan",
        "status": "ready_for_preflight",
        "preflight_status": "preflight_ready",
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "risk_level": "low",
        "expected_complexity": 25,
        "attempt_budget": 2,
        "allowed_files": [
            "core/commander_manual_assignment_plan.py",
            "scripts/create_commander_manual_assignment_plan.py",
        ],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "evidence_required": ["manual assignment plan tests"],
        "rollback_boundary": "writes assignment artifacts only",
        "completion_signal": "assignment artifacts written",
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
    }
    data.update(over)
    return data


def _preflight(findings: list[dict] | None = None, **over) -> dict:
    rows = [_finding()] if findings is None else findings
    data = {
        "report_kind": "commander_preflight_contract",
        "guardrail_note": "Commander Preflight Contract is report-only.",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "source_tree_path": ".agent/commander/fracture_tree_registry/cmd-tree/commander_fracture_tree_registry.json",
        "requested_sub_boss_id": "",
        "source_tree": {
            "tree_id": "cmd-tree",
            "boss_id": "cmd-root",
            "title": "Commander fracture tree",
            "validation_status": "registry_ready",
            "sub_boss_count": len(rows),
        },
        "evaluated_sub_bosses": [
            {
                "sub_boss_id": row["sub_boss_id"],
                "title": row["title"],
                "status": row.get("status", ""),
                "preflight_status": row["preflight_status"],
            }
            for row in rows
        ],
        "evaluated_sub_boss_count": len(rows),
        "preflight_status": "preflight_ready",
        "per_sub_boss_findings": rows,
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
        "guardrails": {
            "real_worker_assignment_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
        },
        "recommended_next_phase": {
            "phase_id": "CMD.N5",
            "title": "Commander Manual Assignment Plan",
        },
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_preflight(tmp_path: Path, data: dict | None = None) -> Path:
    return _write_json(tmp_path / "commander_preflight_contract.json", _preflight() if data is None else data)


def _roles_for(report: dict, sub_boss_id: str = "cmd-n5-core") -> list[str]:
    for assignment in report["assignments"]:
        if assignment["sub_boss_id"] == sub_boss_id:
            return assignment["advisory_roles"]
    return []


def test_valid_cmd_n4_preflight_produces_assignment_artifact(tmp_path):
    preflight_path = _write_preflight(tmp_path)
    result = script.run_create_commander_manual_assignment_plan(
        preflight=str(preflight_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    report = result["report"]
    assert report["report_kind"] == REPORT_KIND == "commander_manual_assignment_plan"
    assert report["plan_id"] == "cmd-n5-cmd-tree-manual-assignment-plan"
    assert report["tree_id"] == "cmd-tree"
    assert report["assignment_status"] == "assignment_ready"
    assert report["recommended_next_phase"]["phase_id"] == "CMD.N6"


def test_blocked_preflight_sub_boss_is_unassigned_and_never_executable():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(
            findings=[
                _finding(
                    preflight_status="preflight_blocked",
                    blocked_reasons=["sub_boss cmd-n5-core has executable worker binding"],
                )
            ],
            preflight_status="preflight_blocked",
        ),
    )
    assert report["assignment_status"] == "assignment_incomplete"
    assert report["assignments"] == []
    assert report["unassigned_sub_bosses"][0]["sub_boss_id"] == "cmd-n5-core"
    assert report["unassigned_sub_bosses"][0]["executable_assignment"] is False


def test_incomplete_sub_boss_receives_only_planner_risk_evidence_roles():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(
            findings=[
                _finding(
                    preflight_status="preflight_incomplete",
                    incomplete_reasons=["sub_boss cmd-n5-core rollback_boundary must be non-empty"],
                )
            ],
            preflight_status="preflight_incomplete",
        ),
    )
    assert report["assignment_status"] == "assignment_incomplete"
    assert set(_roles_for(report)) <= {"planner", "risk_auditor", "evidence_checker"}
    assert {"planner", "risk_auditor", "evidence_checker"} <= set(_roles_for(report))


def test_ready_with_warnings_includes_reviewer_and_risk_auditor():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(
            findings=[
                _finding(
                    preflight_status="preflight_ready_with_warnings",
                    warnings=["sub_boss cmd-n5-core risk_level defaulted to unknown"],
                )
            ],
            preflight_status="preflight_ready_with_warnings",
        ),
    )
    roles = _roles_for(report)
    assert report["assignment_status"] == "assignment_ready_with_warnings"
    assert "reviewer" in roles
    assert "risk_auditor" in roles


def test_ready_sub_boss_receives_core_ready_roles():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(),
    )
    assert {"planner", "implementer", "reviewer", "evidence_checker"} <= set(_roles_for(report))


def test_high_or_unknown_risk_includes_risk_auditor():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(
            findings=[
                _finding(sub_boss_id="high-risk", risk_level="high"),
                _finding(sub_boss_id="unknown-risk", risk_level="unknown"),
            ]
        ),
    )
    assert "risk_auditor" in _roles_for(report, "high-risk")
    assert "risk_auditor" in _roles_for(report, "unknown-risk")


def test_missing_evidence_includes_evidence_checker():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(
            findings=[
                _finding(
                    evidence_required=[],
                    preflight_status="preflight_incomplete",
                    incomplete_reasons=["sub_boss cmd-n5-core evidence_required must be non-empty"],
                )
            ],
            preflight_status="preflight_incomplete",
        ),
    )
    assert "evidence_checker" in _roles_for(report)


@pytest.mark.parametrize(
    ("allowed_files", "expected_role"),
    [
        (["web/app.py", "web/templates/index.html"], "ui_reviewer"),
        (["tests/test_commander_manual_assignment_plan.py"], "test_designer"),
        (["docs/roadmap/phase_registry.json"], "documentation_reviewer"),
    ],
)
def test_scope_specific_roles_are_added(allowed_files, expected_role):
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(findings=[_finding(allowed_files=allowed_files)]),
    )
    assert expected_role in _roles_for(report)


def test_custom_role_catalog_is_loaded_safely(tmp_path):
    role_catalog_path = _write_json(
        tmp_path / "role_catalog.json",
        {
            "planner": {
                "best_for": ["custom scope planning"],
                "not_allowed_to": ["mutate files", "run tools"],
            }
        },
    )
    preflight_path = _write_preflight(tmp_path)
    result = script.run_create_commander_manual_assignment_plan(
        preflight=str(preflight_path),
        role_catalog=str(role_catalog_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert result["report"]["advisory_roles"]["planner"]["best_for"] == ["custom scope planning"]
    assert result["report"]["advisory_roles"]["planner"]["role_binding"] == "advisory_label_only"


def test_custom_role_catalog_cannot_define_executable_workers_or_model_authority():
    worker_report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(),
        role_catalog_data={
            "planner": {
                "best_for": ["planning"],
                "not_allowed_to": ["mutate files"],
                "worker_id": "worker-7",
            }
        },
    )
    model_report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(),
        role_catalog_data={
            "planner": {
                "best_for": ["planning"],
                "not_allowed_to": ["mutate files"],
                "authority": "gpt-4.1",
            }
        },
    )
    assert worker_report["assignment_status"] == "assignment_blocked"
    assert any("executable worker" in reason for reason in worker_report["blocked_reasons"])
    assert model_report["assignment_status"] == "assignment_blocked"
    assert any("model" in reason.lower() for reason in model_report["blocked_reasons"])


def test_unsafe_preflight_path_blocks():
    report = build_commander_manual_assignment_plan(
        preflight_path="../commander_preflight_contract.json",
        preflight_data=_preflight(),
    )
    assert report["assignment_status"] == "assignment_blocked"
    assert any("preflight path must not contain traversal" in reason for reason in report["blocked_reasons"])


def test_malformed_preflight_blocks(tmp_path):
    preflight_path = tmp_path / "commander_preflight_contract.json"
    preflight_path.write_text("{not json", encoding="utf-8")
    result = script.run_create_commander_manual_assignment_plan(
        preflight=str(preflight_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["assignment_status"] == "assignment_blocked"
    assert any("valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_source_preflight_is_not_mutated(tmp_path):
    preflight_path = _write_preflight(tmp_path)
    before = preflight_path.read_text(encoding="utf-8")
    result = write_commander_manual_assignment_plan(
        preflight_path=str(preflight_path),
        output_dir=tmp_path / "out",
    )
    after = preflight_path.read_text(encoding="utf-8")
    assert result["ok"] is True
    assert after == before


def test_json_and_markdown_artifacts_are_written(tmp_path):
    preflight_path = _write_preflight(tmp_path)
    result = write_commander_manual_assignment_plan(
        preflight_path=str(preflight_path),
        output_dir=tmp_path / "out",
    )
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["report_kind"] == REPORT_KIND
    assert "# Commander Manual Assignment Plan" in md
    for section in (
        "## Summary",
        "## Source Preflight",
        "## Advisory Role Catalog",
        "## Assignment Rules",
        "## Per-Sub-Boss Assignments",
        "## Unassigned Sub-Bosses",
        "## Risk Coverage",
        "## Evidence Coverage",
        "## Human Approval Boundary",
        "## Warnings",
        "## Blocked Reasons",
        "## Boundaries / Guardrails",
        "## Recommended Next Phase",
    ):
        assert section in md


def test_markdown_renderer_does_not_mutate_report():
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(),
    )
    snap = copy.deepcopy(report)
    assert render_commander_manual_assignment_plan_markdown(report)
    assert report == snap


def test_default_role_catalog_contains_advisory_labels_only():
    assert set(DEFAULT_ROLE_CATALOG) == {
        "planner",
        "implementer",
        "reviewer",
        "evidence_checker",
        "risk_auditor",
        "ui_reviewer",
        "test_designer",
        "documentation_reviewer",
    }
    report = build_commander_manual_assignment_plan(
        preflight_path="commander_preflight_contract.json",
        preflight_data=_preflight(),
    )
    for role in report["advisory_roles"].values():
        assert role["role_binding"] == "advisory_label_only"
        assert role["executable_worker_id"] == ""
        assert role["model_id"] == ""


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "commander_manual_assignment_plan.py"
_SCRIPT = _ROOT / "scripts" / "create_commander_manual_assignment_plan.py"


def test_source_has_no_forbidden_imports_or_execution_calls():
    allowed_core_imports = {"__future__", "json", "pathlib", "typing"}
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


def test_registry_and_picker_recommend_cmd_n6():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N4"]["status"] == "complete"
    assert phases["CMD.N5"]["status"] == "complete"
    assert phases["CMD.N5"]["prerequisites"] == ["CMD.N4"]
    assert phases["CMD.N6"]["status"] == "proposed"
    assert phases["CMD.N6"]["prerequisites"] == ["CMD.N5"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "CMD.N6"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
