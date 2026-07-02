"""Tests for CMD.N4 - Commander Preflight Contract (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.commander_preflight_contract import (
    DEFAULT_HUMAN_APPROVAL_POLICY,
    DEFAULT_MUTATION_POLICY,
    DEFAULT_VALIDATION_POLICY,
    GUARDRAIL_FALSE_FLAGS,
    REPORT_KIND,
    build_commander_preflight_contract,
    render_commander_preflight_contract_markdown,
    write_commander_preflight_contract,
)
import scripts.create_commander_preflight_contract as script


def _sub_boss(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-preflight-1",
        "parent_boss_id": "cmd-root",
        "title": "Commander preflight contract",
        "goal": "Define the report-only preflight readiness contract",
        "scope": "Core report, CLI, tests, and roadmap metadata",
        "expected_complexity": 30,
        "evidence_required": ["preflight contract tests"],
        "allowed_files": [
            "core/commander_preflight_contract.py",
            "scripts/create_commander_preflight_contract.py",
            "tests/test_commander_preflight_contract.py",
        ],
        "forbidden_files": ["web/app.py", ".env", ".git", ".agent/private"],
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "attempt_budget": 2,
        "completion_signal": "preflight artifacts written",
        "rollback_boundary": "no route, worker, model, or execution behavior changes",
        "dependencies": [],
        "status": "ready_for_preflight",
        "risk_level": "low",
        "human_approval_policy": dict(DEFAULT_HUMAN_APPROVAL_POLICY),
        "mutation_policy": dict(DEFAULT_MUTATION_POLICY),
        "validation_policy": dict(DEFAULT_VALIDATION_POLICY),
    }
    data.update(over)
    return data


def _tree(sub_bosses=None, **over) -> dict:
    data = {
        "report_kind": "commander_fracture_tree_registry",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "source_report_path": "",
        "root_boss": {
            "boss_id": "cmd-root",
            "title": "Commander root boss",
            "description": "Manual boss description.",
            "initial_complexity": 100,
            "actual_remaining": 60,
            "attempt": 3,
            "max_attempts": 6,
            "aggressiveness": 2,
            "tolerance": 0.20,
            "fracture_pressure": 1.6,
            "commander_decision": "fracture_recommended",
        },
        "sub_bosses": [_sub_boss()] if sub_bosses is None else sub_bosses,
        "dependency_edges": [],
        "total_expected_complexity": 30,
        "total_attempt_budget": 2,
        "validation_status": "registry_ready",
        "warnings": [],
        "blocked_reasons": [],
        "recommended_next_phase": {"phase_id": "CMD.N4", "title": "Commander Preflight Contract"},
    }
    data.update(over)
    return data


def _write_tree(tmp_path: Path, data: dict | None = None) -> Path:
    path = tmp_path / "commander_fracture_tree_registry.json"
    path.write_text(json.dumps(_tree() if data is None else data, indent=2), encoding="utf-8")
    return path


def test_valid_cmd_n3_tree_produces_preflight_artifact(tmp_path):
    tree_path = _write_tree(tmp_path)
    result = script.run_create_commander_preflight_contract(
        tree=str(tree_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    report = result["report"]
    assert report["report_kind"] == REPORT_KIND == "commander_preflight_contract"
    assert report["tree_id"] == "cmd-tree"
    assert report["preflight_status"] == "preflight_ready"
    assert report["evaluated_sub_boss_count"] == 1
    assert report["recommended_next_phase"]["phase_id"] == "CMD.N5"


def test_sub_boss_id_evaluates_only_one_sub_boss(tmp_path):
    tree_path = _write_tree(
        tmp_path,
        _tree(
            sub_bosses=[
                _sub_boss(sub_boss_id="cmd-preflight-1"),
                _sub_boss(sub_boss_id="cmd-preflight-2", title="Second sub-boss"),
            ]
        ),
    )
    result = script.run_create_commander_preflight_contract(
        tree=str(tree_path),
        sub_boss_id="cmd-preflight-2",
        output_dir=str(tmp_path / "out"),
    )
    report = result["report"]
    assert report["preflight_status"] == "preflight_ready"
    assert [row["sub_boss_id"] for row in report["evaluated_sub_bosses"]] == ["cmd-preflight-2"]


def test_missing_sub_boss_blocks(tmp_path):
    tree_path = _write_tree(tmp_path)
    result = script.run_create_commander_preflight_contract(
        tree=str(tree_path),
        sub_boss_id="missing-sub-boss",
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["preflight_status"] == "preflight_blocked"
    assert any("missing sub-boss" in reason for reason in result["report"]["blocked_reasons"])


def test_unsafe_tree_path_blocks(tmp_path):
    unsafe_tree = tmp_path / "missing" / ".." / "tree.json"
    result = script.run_create_commander_preflight_contract(
        tree=str(unsafe_tree),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is False
    assert result["report"]["preflight_status"] == "preflight_blocked"
    assert any("tree path must not contain traversal" in reason for reason in result["report"]["blocked_reasons"])


def test_unsafe_allowed_files_and_forbidden_files_block():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(
            sub_bosses=[
                _sub_boss(
                    allowed_files=["../secret"],
                    forbidden_files=["safe/file.py", "core/../bad.py"],
                )
            ]
        ),
    )
    assert report["preflight_status"] == "preflight_blocked"
    assert any("allowed_files" in reason for reason in report["blocked_reasons"])
    assert any("forbidden_files" in reason for reason in report["blocked_reasons"])


def test_allowed_forbidden_file_conflict_blocks():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(forbidden_files=["core/commander_preflight_contract.py"])]),
    )
    assert report["preflight_status"] == "preflight_blocked"
    assert any("allowed_files and forbidden_files conflict" in reason for reason in report["blocked_reasons"])


def test_executable_worker_binding_blocks():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(worker_binding="worker-7")]),
    )
    assert report["preflight_status"] == "preflight_blocked"
    assert any("executable worker binding" in reason for reason in report["blocked_reasons"])


def test_auto_apply_auto_run_auto_merge_flags_block():
    for flag in ("auto_apply", "auto_run", "auto_merge"):
        report = build_commander_preflight_contract(
            tree_path="tree.json",
            tree_data=_tree(sub_bosses=[_sub_boss(**{flag: True})]),
        )
        assert report["preflight_status"] == "preflight_blocked"
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_missing_evidence_required_causes_preflight_incomplete():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(evidence_required=[])]),
    )
    assert report["preflight_status"] == "preflight_incomplete"
    assert any("evidence_required" in reason for reason in report["incomplete_reasons"])


def test_missing_rollback_boundary_causes_preflight_incomplete():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(rollback_boundary="")]),
    )
    assert report["preflight_status"] == "preflight_incomplete"
    assert any("rollback_boundary" in reason for reason in report["incomplete_reasons"])


def test_missing_completion_signal_causes_preflight_incomplete():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(completion_signal="")]),
    )
    assert report["preflight_status"] == "preflight_incomplete"
    assert any("completion_signal" in reason for reason in report["incomplete_reasons"])


def test_dependencies_pending_warn_when_explicitly_allowed():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(
            sub_bosses=[
                _sub_boss(sub_boss_id="dep-1", status="ready_for_preflight"),
                _sub_boss(
                    sub_boss_id="dep-2",
                    dependencies=["dep-1"],
                    allow_pending_dependencies=True,
                ),
            ]
        ),
    )
    assert report["preflight_status"] == "preflight_ready_with_warnings"
    assert any("pending dependency" in warning for warning in report["warnings"])


def test_dependencies_pending_incomplete_without_policy():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(
            sub_bosses=[
                _sub_boss(sub_boss_id="dep-1", status="ready_for_preflight"),
                _sub_boss(sub_boss_id="dep-2", dependencies=["dep-1"]),
            ]
        ),
    )
    assert report["preflight_status"] == "preflight_incomplete"
    assert any("dependency dep-1 is pending" in reason for reason in report["incomplete_reasons"])


def test_advisory_assigned_role_is_allowed_not_executable():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(sub_bosses=[_sub_boss(assigned_role="planner")]),
    )
    assert report["preflight_status"] == "preflight_ready"
    finding = report["per_sub_boss_findings"][0]
    assert finding["assigned_role"] == "planner"
    assert finding["assigned_role_binding"] == "advisory_label_only"
    assert report["guardrails"]["real_worker_assignment_performed"] is False


def test_default_policies_are_included_for_missing_policy_fields():
    report = build_commander_preflight_contract(
        tree_path="tree.json",
        tree_data=_tree(
            sub_bosses=[
                _sub_boss(
                    human_approval_policy=None,
                    mutation_policy=None,
                    validation_policy=None,
                    risk_level=None,
                )
            ]
        ),
    )
    finding = report["per_sub_boss_findings"][0]
    assert finding["risk_level"] == "unknown"
    assert finding["human_approval_policy"] == DEFAULT_HUMAN_APPROVAL_POLICY
    assert finding["mutation_policy"] == DEFAULT_MUTATION_POLICY
    assert finding["validation_policy"] == DEFAULT_VALIDATION_POLICY
    assert report["preflight_status"] == "preflight_ready_with_warnings"


def test_json_and_markdown_artifacts_are_written(tmp_path):
    tree_path = _write_tree(tmp_path)
    result = write_commander_preflight_contract(
        tree_path=str(tree_path),
        output_dir=tmp_path / "out",
    )
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["report_kind"] == REPORT_KIND
    assert "# Commander Preflight Contract" in md


def test_markdown_contains_required_sections_and_guardrails():
    report = build_commander_preflight_contract(tree_path="tree.json", tree_data=_tree())
    md = render_commander_preflight_contract_markdown(report)
    low = md.lower()
    for section in (
        "## summary",
        "## source tree",
        "## evaluated sub-bosses",
        "## preflight contract",
        "## policy defaults",
        "## per-sub-boss findings",
        "## dependency readiness",
        "## file scope safety",
        "## evidence requirements",
        "## rollback boundaries",
        "## human approval policy",
        "## warnings",
        "## blocked reasons",
        "## boundaries / guardrails",
        "## recommended next phase",
    ):
        assert section in low, section
    assert "cmd.n4 does not execute sub-bosses" in low
    assert "cmd.n4 writes preflight artifacts only" in low


def test_guardrails_are_all_false():
    report = build_commander_preflight_contract(tree_path="tree.json", tree_data=_tree())
    assert set(report["guardrails"]) == set(GUARDRAIL_FALSE_FLAGS)
    assert all(value is False for value in report["guardrails"].values())


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "commander_preflight_contract.py"
_SCRIPT = _ROOT / "scripts" / "create_commander_preflight_contract.py"


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


def test_registry_and_picker_recommend_cmd_n5():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N3"]["status"] == "complete"
    assert phases["CMD.N4"]["status"] == "complete"
    assert phases["CMD.N4"]["prerequisites"] == ["CMD.N3"]
    assert phases["CMD.N5"]["status"] == "complete"
    assert phases["CMD.N5"]["prerequisites"] == ["CMD.N4"]
    assert phases["CMD.N6"]["status"] == "proposed"
    assert phases["CMD.N6"]["prerequisites"] == ["CMD.N5"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "CMD.N6"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
