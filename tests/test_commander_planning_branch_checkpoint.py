"""Tests for CMD.CLOSE - Commander Planning Branch Checkpoint (report-only)."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.commander_planning_branch_checkpoint import (
    REPORT_KIND,
    REQUIRED_PHASE_IDS,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WARNINGS,
    STATUS_INCOMPLETE,
    build_commander_planning_branch_checkpoint,
    render_commander_planning_branch_checkpoint_markdown,
    write_commander_planning_branch_checkpoint,
)
import scripts.create_commander_planning_branch_checkpoint as script


def _phase(pid: str, *, status: str = "complete", track: str = "CMD", prereq: list[str] | None = None) -> dict:
    return {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": track,
        "status": status,
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_x.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [] if prereq is None else prereq,
        "expected_artifacts": [".agent/x.json"],
        "notes": ["Report-only."],
    }


def _registry(*, drop: tuple[str, ...] = (), status_overrides: dict[str, str] | None = None) -> dict:
    status_overrides = status_overrides or {}
    phases = []
    for pid in REQUIRED_PHASE_IDS:
        if pid not in drop:
            phases.append(_phase(pid, status=status_overrides.get(pid, "complete")))
    if "CMD.CLOSE" not in drop:
        phases.append(_phase("CMD.CLOSE", status=status_overrides.get("CMD.CLOSE", "complete"), prereq=["CMD.N6"]))
    if "MODEL.N1" not in drop:
        phases.append(_phase("MODEL.N1", status="proposed", track="MODEL", prereq=["CMD.CLOSE"]))
    return {"schema_version": "1.0", "updated_at": "2026-07-03T00:00:00+09:00", "phases": phases}


def _n1(**over) -> dict:
    data = {
        "report_kind": "boss_half_life_fracture_plan",
        "formula": {
            "expected_remaining": "B_t = B_0 * (1/2) ** (t / H)",
            "half_life": "H = T / k",
            "fracture_pressure": "actual_remaining / expected_remaining",
        },
        "fracture_pressure_thresholds": [
            {"status": "on_track", "range": "1.0 <= fracture_pressure < 1.2"},
            {"status": "fracture_recommended", "range": "1.5 <= fracture_pressure < 2.0"},
        ],
        "decision": {"status": "fracture_recommended"},
        "warnings": [],
        "blockers": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _n2(**over) -> dict:
    data = {
        "report_kind": "manual_boss_fracture_report",
        "boss_input": {"boss_id": "cmd-root", "title": "Commander root boss"},
        "commander_decision": {"status": "fracture_recommended"},
        "fracture_tree": {"tree_id": "cmd-tree"},
        "warnings": [],
        "blockers": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _sub_boss(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-close-core",
        "parent_boss_id": "cmd-root",
        "title": "Commander planning checkpoint",
        "status": "ready_for_preflight",
        "risk_level": "low",
        "expected_complexity": 30,
        "attempt_budget": 2,
        "allowed_files": ["core/commander_planning_branch_checkpoint.py"],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "evidence_required": ["checkpoint tests"],
        "rollback_boundary": "writes checkpoint artifacts only",
        "completion_signal": "checkpoint artifacts written",
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "dependencies": [],
    }
    data.update(over)
    return data


def _n3(sub_bosses: list[dict] | None = None, **over) -> dict:
    rows = [_sub_boss()] if sub_bosses is None else sub_bosses
    data = {
        "report_kind": "commander_fracture_tree_registry",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "root_boss": {"boss_id": "cmd-root", "commander_decision": "fracture_recommended"},
        "sub_bosses": rows,
        "dependency_edges": [],
        "validation_status": "registry_ready",
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"model_call_performed": False, "worker_launch_performed": False},
    }
    data.update(over)
    return data


def _finding(**over) -> dict:
    sub = _sub_boss()
    data = {
        "sub_boss_id": sub["sub_boss_id"],
        "title": sub["title"],
        "status": sub["status"],
        "preflight_status": "preflight_ready",
        "risk_level": sub["risk_level"],
        "allowed_files": list(sub["allowed_files"]),
        "forbidden_files": list(sub["forbidden_files"]),
        "evidence_required": list(sub["evidence_required"]),
        "rollback_boundary": sub["rollback_boundary"],
        "completion_signal": sub["completion_signal"],
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
    }
    data.update(over)
    return data


def _n4(findings: list[dict] | None = None, **over) -> dict:
    rows = [_finding()] if findings is None else findings
    data = {
        "report_kind": "commander_preflight_contract",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "source_tree_path": "tree.json",
        "evaluated_sub_boss_count": len(rows),
        "preflight_status": "preflight_ready",
        "per_sub_boss_findings": rows,
        "human_approval_policy": {
            "required_before_patch_apply": True,
            "required_before_worker_launch": True,
            "assignment_authority": "human_only",
        },
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
        "guardrails": {
            "real_worker_assignment_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
        },
    }
    data.update(over)
    return data


def _assignment(**over) -> dict:
    sub = _sub_boss()
    data = {
        "assignment_id": "cmd-close-core-advisory-assignment",
        "sub_boss_id": sub["sub_boss_id"],
        "title": sub["title"],
        "preflight_status": "preflight_ready",
        "risk_level": "low",
        "advisory_roles": ["planner", "reviewer", "evidence_checker"],
        "role_binding": "advisory_labels_only",
        "executable_assignment": False,
        "executable_worker_id": "",
        "model_id": "",
        "assignment_reasons": ["preflight_ready may receive planning coverage"],
        "source_evidence_required": list(sub["evidence_required"]),
        "source_allowed_files": list(sub["allowed_files"]),
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
    }
    data.update(over)
    return data


def _n5(assignments: list[dict] | None = None, **over) -> dict:
    rows = [_assignment()] if assignments is None else assignments
    data = {
        "report_kind": "commander_manual_assignment_plan",
        "plan_id": "cmd-n5-cmd-tree-manual-assignment-plan",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "source_preflight_path": "preflight.json",
        "assignment_status": "assignment_ready",
        "assignments": rows,
        "unassigned_sub_bosses": [],
        "human_approval_boundary": {
            "required_before_patch_apply": True,
            "required_before_worker_launch": True,
            "required_before_file_mutation": True,
            "assignment_authority": "human_only",
        },
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {"worker_launch_performed": False, "model_call_performed": False, "patch_apply_performed": False},
    }
    data.update(over)
    return data


def _n6(**over) -> dict:
    data = {
        "report_kind": "commander_assignment_review_pack",
        "review_id": "cmd-n6-cmd-tree-assignment-review-pack",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "review_status": "review_pack_ready",
        "source_artifacts": {
            "tree": {"path": "tree.json", "report_kind": "commander_fracture_tree_registry", "status": "registry_ready"},
            "preflight": {"path": "preflight.json", "report_kind": "commander_preflight_contract", "status": "preflight_ready"},
            "assignment": {"path": "assignment.json", "report_kind": "commander_manual_assignment_plan", "status": "assignment_ready"},
        },
        "per_sub_boss_review": [
            {
                "sub_boss_id": "cmd-close-core",
                "preflight_status": "preflight_ready",
                "assigned_advisory_roles": ["planner", "reviewer", "evidence_checker"],
                "human_review_required": False,
                "unresolved_warnings": [],
                "blocked_reasons": [],
            }
        ],
        "human_review_checklist": [
            "confirm no worker/model is authorized to execute",
            "confirm validation/benchmark runs remain human-triggered",
            "confirm patch apply remains human-triggered",
        ],
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {
            "model_call_performed": False,
            "worker_launch_performed": False,
            "patch_apply_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
            "route_behavior_change_performed": False,
            "database_write_performed": False,
        },
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_inputs(tmp_path: Path, *, registry=None, n1=None, n2=None, n3=None, n4=None, n5=None, n6=None) -> dict[str, Path]:
    paths = {
        "registry": _write_json(tmp_path / "phase_registry.json", _registry() if registry is None else registry),
        "boss_half_life": _write_json(tmp_path / "boss_half_life_fracture_plan.json", _n1() if n1 is None else n1),
        "manual_fracture": _write_json(tmp_path / "manual_boss_fracture_report.json", _n2() if n2 is None else n2),
        "fracture_tree": _write_json(tmp_path / "commander_fracture_tree_registry.json", _n3() if n3 is None else n3),
        "preflight": _write_json(tmp_path / "commander_preflight_contract.json", _n4() if n4 is None else n4),
        "assignment": _write_json(tmp_path / "commander_manual_assignment_plan.json", _n5() if n5 is None else n5),
        "review_pack": _write_json(tmp_path / "commander_assignment_review_pack.json", _n6() if n6 is None else n6),
    }
    return paths


def _build_from_paths(paths: dict[str, Path], **over) -> dict:
    kwargs = {
        "registry_path": paths["registry"],
        "boss_half_life_path": paths["boss_half_life"],
        "manual_fracture_path": paths["manual_fracture"],
        "fracture_tree_path": paths["fracture_tree"],
        "preflight_path": paths["preflight"],
        "assignment_path": paths["assignment"],
        "review_pack_path": paths["review_pack"],
    }
    kwargs.update(over)
    return build_commander_planning_branch_checkpoint(**kwargs)


def test_complete_cmd_n1_to_cmd_n6_registry_and_artifacts_produce_frozen_status(tmp_path):
    paths = _write_inputs(tmp_path)
    report = _build_from_paths(paths)
    assert report["report_kind"] == REPORT_KIND == "commander_planning_branch_checkpoint"
    assert report["checkpoint_status"] == STATUS_FROZEN
    assert report["phase_completion"]["all_required_phases_complete"] is True
    assert report["artifact_coverage"]["all_required_artifacts_present"] is True
    assert report["execution_prohibition_checks"]["execution_capability_detected"] is False
    assert report["recommended_next_phase"]["phase_id"] == "MODEL.N1"


def test_missing_cmd_n6_phase_blocks(tmp_path):
    paths = _write_inputs(tmp_path, registry=_registry(drop=("CMD.N6",)))
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("CMD.N6" in reason for reason in report["blocked_reasons"])


def test_missing_required_artifact_reports_incomplete(tmp_path):
    paths = _write_inputs(tmp_path)
    report = _build_from_paths(paths, assignment_path=tmp_path / "missing_assignment.json")
    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("assignment artifact is missing" in reason for reason in report["incomplete_reasons"])


def test_unsafe_artifact_path_blocks(tmp_path):
    paths = _write_inputs(tmp_path)
    report = _build_from_paths(paths, fracture_tree_path="../commander_fracture_tree_registry.json")
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("fracture_tree path must not contain traversal" in reason for reason in report["blocked_reasons"])


def test_executable_worker_binding_blocks(tmp_path):
    paths = _write_inputs(tmp_path, n5=_n5(assignments=[_assignment(worker_id="worker-7")]))
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("executable worker binding" in reason for reason in report["blocked_reasons"])


def test_model_id_as_execution_authority_blocks(tmp_path):
    paths = _write_inputs(tmp_path, n5=_n5())
    assignment = json.loads(paths["assignment"].read_text(encoding="utf-8"))
    assignment["authority"] = "gpt-4.1"
    paths["assignment"].write_text(json.dumps(assignment, indent=2), encoding="utf-8")
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("model" in reason.lower() and "authority" in reason.lower() for reason in report["blocked_reasons"])


def test_auto_run_auto_apply_auto_merge_flags_block(tmp_path):
    for flag in ("auto_run", "auto_apply", "auto_merge"):
        paths = _write_inputs(tmp_path / flag, n5=_n5(**{flag: True}))
        report = _build_from_paths(paths)
        assert report["checkpoint_status"] == STATUS_BLOCKED
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_route_behavior_change_marker_blocks_if_detectable(tmp_path):
    paths = _write_inputs(tmp_path, n6=_n6(route_behavior_changed=True))
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("route behavior" in reason.lower() for reason in report["blocked_reasons"])


def test_execution_capability_marker_blocks_if_detectable(tmp_path):
    paths = _write_inputs(tmp_path, n6=_n6(worker_launch_path="workers/launch.py"))
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("worker launch path" in reason.lower() for reason in report["blocked_reasons"])


def test_planning_only_artifacts_pass(tmp_path):
    paths = _write_inputs(tmp_path)
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_FROZEN
    assert report["planning_capability_summary"] == {
        "can_define_half_life_stagnation_math": True,
        "can_report_manual_boss_fracture": True,
        "can_store_and_validate_fracture_trees": True,
        "can_preflight_sub_bosses": True,
        "can_assign_advisory_role_labels": True,
        "can_produce_assignment_review_pack": True,
        "can_execute_anything": False,
    }
    assert all(value is False for value in report["guardrails"].values())


def test_warning_heavy_but_safe_artifacts_produce_frozen_with_warnings(tmp_path):
    warning_n4 = _n4(preflight_status="preflight_ready_with_warnings", warnings=["demo preflight warning"])
    warning_n5 = _n5(assignment_status="assignment_ready_with_warnings", warnings=["demo assignment warning"])
    warning_n6 = _n6(review_status="review_pack_ready_with_warnings", warnings=["demo review warning"])
    paths = _write_inputs(tmp_path, n4=warning_n4, n5=warning_n5, n6=warning_n6)
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_FROZEN_WARNINGS
    assert any("demo preflight warning" in warning for warning in report["warnings"])
    assert report["blocked_reasons"] == []


def test_review_pack_alignment_gap_reports_incomplete(tmp_path):
    second = _sub_boss(sub_boss_id="cmd-close-extra", title="Extra sub-boss")
    paths = _write_inputs(tmp_path, n3=_n3(sub_bosses=[_sub_boss(), second]))
    report = _build_from_paths(paths)
    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("missing preflight coverage" in reason for reason in report["incomplete_reasons"])


def test_json_and_markdown_checkpoint_artifacts_are_written(tmp_path):
    paths = _write_inputs(tmp_path)
    result = write_commander_planning_branch_checkpoint(
        registry_path=paths["registry"],
        boss_half_life_path=paths["boss_half_life"],
        manual_fracture_path=paths["manual_fracture"],
        fracture_tree_path=paths["fracture_tree"],
        preflight_path=paths["preflight"],
        assignment_path=paths["assignment"],
        review_pack_path=paths["review_pack"],
        output_dir=tmp_path / "out",
    )
    assert result["ok"] is True
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert Path(result["json_path"]).name == "commander_planning_branch_checkpoint.json"
    assert Path(result["md_path"]).name == "commander_planning_branch_checkpoint.md"
    assert data["checkpoint_status"] == STATUS_FROZEN
    for section in (
        "## Summary",
        "## Phase Completion",
        "## Artifact Coverage",
        "## Planning Capability Summary",
        "## Safety Boundary Verification",
        "## Execution-Prohibition Checks",
        "## Human Approval Boundary",
        "## Warnings",
        "## Blocked Reasons",
        "## Final Verdict",
        "## Recommended Next Phase",
        "## Boundaries / Guardrails",
    ):
        assert section in md


def test_script_writes_checkpoint_json_and_markdown(tmp_path):
    paths = _write_inputs(tmp_path)
    result = script.run_create_commander_planning_branch_checkpoint(
        registry=str(paths["registry"]),
        boss_half_life=str(paths["boss_half_life"]),
        manual_fracture=str(paths["manual_fracture"]),
        fracture_tree=str(paths["fracture_tree"]),
        preflight=str(paths["preflight"]),
        assignment=str(paths["assignment"]),
        review_pack=str(paths["review_pack"]),
        output_dir=str(tmp_path / "script-out"),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN


def test_markdown_renderer_does_not_mutate_report(tmp_path):
    paths = _write_inputs(tmp_path)
    report = _build_from_paths(paths)
    snap = json.loads(json.dumps(report, sort_keys=True))
    assert render_commander_planning_branch_checkpoint_markdown(report)
    assert report == snap


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "commander_planning_branch_checkpoint.py"
_SCRIPT = _ROOT / "scripts" / "create_commander_planning_branch_checkpoint.py"


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


def test_registry_and_picker_recommend_model_n1_after_cmd_close():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N6"]["status"] == "complete"
    assert phases["CMD.CLOSE"]["status"] == "complete"
    assert phases["CMD.CLOSE"]["prerequisites"] == ["CMD.N6"]
    assert phases["MODEL.N1"]["status"] == "proposed"
    assert phases["MODEL.N1"]["prerequisites"] == ["CMD.CLOSE"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "MODEL.N1"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
