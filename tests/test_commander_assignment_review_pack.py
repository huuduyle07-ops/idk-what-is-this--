"""Tests for CMD.N6 - Commander Assignment Review Pack (report-only)."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates

from core.commander_assignment_review_pack import (
    HUMAN_REVIEW_CHECKLIST,
    REPORT_KIND,
    build_commander_assignment_review_pack,
    render_commander_assignment_review_pack_markdown,
    write_commander_assignment_review_pack,
)
import scripts.create_commander_assignment_review_pack as script


def _sub_boss(**over) -> dict:
    data = {
        "sub_boss_id": "cmd-n6-core",
        "parent_boss_id": "cmd-root",
        "title": "Commander assignment review pack",
        "goal": "Combine Commander planning artifacts for human review",
        "scope": "Core report, CLI, tests, and roadmap metadata",
        "expected_complexity": 30,
        "evidence_required": ["assignment review pack tests"],
        "allowed_files": [
            "core/commander_assignment_review_pack.py",
            "scripts/create_commander_assignment_review_pack.py",
            "tests/test_commander_assignment_review_pack.py",
            "docs/roadmap/phase_registry.json",
        ],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "attempt_budget": 2,
        "completion_signal": "review pack artifacts written",
        "rollback_boundary": "writes review-pack artifacts only",
        "dependencies": [],
        "status": "ready_for_preflight",
        "risk_level": "low",
    }
    data.update(over)
    return data


def _tree(sub_bosses: list[dict] | None = None, **over) -> dict:
    rows = [_sub_boss()] if sub_bosses is None else sub_bosses
    data = {
        "report_kind": "commander_fracture_tree_registry",
        "guardrail_note": "Commander Fracture Tree Registry is report-only.",
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
        "sub_bosses": rows,
        "dependency_edges": [],
        "total_expected_complexity": sum(row.get("expected_complexity", 0) for row in rows),
        "total_attempt_budget": sum(row.get("attempt_budget", 0) for row in rows),
        "validation_status": "registry_ready",
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {
            "model_call_performed": False,
            "worker_launch_performed": False,
            "patch_apply_performed": False,
        },
        "recommended_next_phase": {"phase_id": "CMD.N4", "title": "Commander Preflight Contract"},
    }
    data.update(over)
    return data


def _finding(**over) -> dict:
    base = _sub_boss()
    data = {
        "sub_boss_id": base["sub_boss_id"],
        "title": base["title"],
        "status": base["status"],
        "preflight_status": "preflight_ready",
        "assigned_role": "planner",
        "assigned_role_binding": "advisory_label_only",
        "risk_level": base["risk_level"],
        "expected_complexity": base["expected_complexity"],
        "attempt_budget": base["attempt_budget"],
        "allowed_files": list(base["allowed_files"]),
        "forbidden_files": list(base["forbidden_files"]),
        "evidence_required": list(base["evidence_required"]),
        "rollback_boundary": base["rollback_boundary"],
        "completion_signal": base["completion_signal"],
        "dependency_readiness": [],
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
        "evidence_requirements": [
            {"sub_boss_id": row["sub_boss_id"], "evidence_required": row.get("evidence_required", [])}
            for row in rows
        ],
        "rollback_boundaries": [
            {"sub_boss_id": row["sub_boss_id"], "rollback_boundary": row.get("rollback_boundary", "")}
            for row in rows
        ],
        "warnings": [],
        "incomplete_reasons": [],
        "blocked_reasons": [],
        "guardrails": {
            "real_worker_assignment_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
        },
        "recommended_next_phase": {"phase_id": "CMD.N5", "title": "Commander Manual Assignment Plan"},
    }
    data.update(over)
    return data


def _assignment(rows: list[dict] | None = None, unassigned: list[dict] | None = None, **over) -> dict:
    findings = [_finding()] if rows is None else rows
    assignments = [
        {
            "assignment_id": f"{row['sub_boss_id']}-advisory-assignment",
            "sub_boss_id": row["sub_boss_id"],
            "title": row["title"],
            "preflight_status": row["preflight_status"],
            "risk_level": row.get("risk_level", "low"),
            "advisory_roles": [
                "planner",
                "implementer",
                "reviewer",
                "evidence_checker",
                "test_designer",
                "documentation_reviewer",
            ],
            "role_binding": "advisory_labels_only",
            "executable_assignment": False,
            "executable_worker_id": "",
            "model_id": "",
            "assignment_reasons": ["preflight_ready may receive planning coverage"],
            "source_evidence_required": list(row.get("evidence_required") or []),
            "source_allowed_files": list(row.get("allowed_files") or []),
            "warnings": list(row.get("warnings") or []),
            "incomplete_reasons": list(row.get("incomplete_reasons") or []),
            "blocked_reasons": list(row.get("blocked_reasons") or []),
        }
        for row in findings
        if row.get("preflight_status") != "preflight_blocked"
    ]
    data = {
        "report_kind": "commander_manual_assignment_plan",
        "guardrail_note": "Commander Manual Assignment Plan is report-only.",
        "plan_id": "cmd-n5-cmd-tree-manual-assignment-plan",
        "tree_id": "cmd-tree",
        "boss_id": "cmd-root",
        "title": "Commander fracture tree",
        "source_preflight_path": ".agent/commander/preflight_contract/cmd-tree/commander_preflight_contract.json",
        "source_preflight": {
            "report_kind": "commander_preflight_contract",
            "preflight_status": "preflight_ready",
            "evaluated_sub_boss_count": len(findings),
            "source_tree_path": ".agent/commander/fracture_tree_registry/cmd-tree/commander_fracture_tree_registry.json",
        },
        "assignment_status": "assignment_ready",
        "assignment_rules": [
            "high or unknown risk requires risk_auditor coverage.",
            "missing evidence requires evidence_checker coverage.",
        ],
        "assignments": assignments,
        "unassigned_sub_bosses": [] if unassigned is None else unassigned,
        "risk_coverage": [
            {
                "sub_boss_id": row["sub_boss_id"],
                "risk_level": row.get("risk_level", "low"),
                "risk_auditor_assigned": "risk_auditor" in next(
                    (
                        assignment["advisory_roles"]
                        for assignment in assignments
                        if assignment["sub_boss_id"] == row["sub_boss_id"]
                    ),
                    [],
                ),
                "coverage_required": row.get("risk_level") in {"high", "unknown"},
            }
            for row in findings
        ],
        "evidence_coverage": [
            {
                "sub_boss_id": row["sub_boss_id"],
                "evidence_required_count": len(row.get("evidence_required") or []),
                "missing_evidence": not bool(row.get("evidence_required")),
                "evidence_checker_assigned": "evidence_checker" in next(
                    (
                        assignment["advisory_roles"]
                        for assignment in assignments
                        if assignment["sub_boss_id"] == row["sub_boss_id"]
                    ),
                    [],
                ),
            }
            for row in findings
        ],
        "human_approval_boundary": {
            "required_before_patch_apply": True,
            "required_before_worker_launch": True,
            "required_before_file_mutation": True,
            "assignment_authority": "human_only",
        },
        "warnings": [],
        "blocked_reasons": [],
        "guardrails": {
            "worker_launch_performed": False,
            "model_call_performed": False,
            "patch_apply_performed": False,
        },
        "recommended_next_phase": {"phase_id": "CMD.N6", "title": "Commander Assignment Review Pack"},
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_inputs(tmp_path: Path, tree=None, preflight=None, assignment=None) -> tuple[Path, Path, Path]:
    return (
        _write_json(tmp_path / "commander_fracture_tree_registry.json", _tree() if tree is None else tree),
        _write_json(tmp_path / "commander_preflight_contract.json", _preflight() if preflight is None else preflight),
        _write_json(
            tmp_path / "commander_manual_assignment_plan.json",
            _assignment() if assignment is None else assignment,
        ),
    )


def test_valid_tree_preflight_assignment_produces_review_pack_artifacts(tmp_path):
    tree_path, preflight_path, assignment_path = _write_inputs(tmp_path)
    result = script.run_create_commander_assignment_review_pack(
        tree=str(tree_path),
        preflight=str(preflight_path),
        assignment=str(assignment_path),
        output_dir=str(tmp_path / "out"),
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    report = result["report"]
    assert report["report_kind"] == REPORT_KIND == "commander_assignment_review_pack"
    assert report["review_id"] == "cmd-n6-cmd-tree-assignment-review-pack"
    assert report["tree_id"] == "cmd-tree"
    assert report["boss_id"] == "cmd-root"
    assert report["review_status"] == "review_pack_ready"
    assert report["recommended_next_phase"]["phase_id"] == "CMD.CLOSE"
    assert report["per_sub_boss_review"][0]["assigned_advisory_roles"]


def test_high_risk_or_warning_heavy_valid_inputs_produce_ready_with_warnings():
    finding = _finding(
        risk_level="high",
        warnings=["sub_boss cmd-n6-core expected_complexity is high"],
    )
    assignment = _assignment(
        rows=[finding],
        assignments=[
            {
                "assignment_id": "cmd-n6-core-advisory-assignment",
                "sub_boss_id": "cmd-n6-core",
                "title": finding["title"],
                "preflight_status": "preflight_ready_with_warnings",
                "risk_level": "high",
                "advisory_roles": ["reviewer"],
                "role_binding": "advisory_labels_only",
                "executable_assignment": False,
                "executable_worker_id": "",
                "model_id": "",
            }
        ],
        assignment_status="assignment_ready_with_warnings",
    )
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(sub_bosses=[_sub_boss(risk_level="high")]),
        preflight_data=_preflight(findings=[finding], preflight_status="preflight_ready_with_warnings"),
        assignment_data=assignment,
    )
    assert report["review_status"] == "review_pack_ready_with_warnings"
    assert any("risk_auditor" in warning for warning in report["warnings"])


def test_mismatched_tree_id_blocks():
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(tree_id="other-tree"),
        assignment_data=_assignment(),
    )
    assert report["review_status"] == "review_pack_blocked"
    assert any("tree_id" in reason and "mismatch" in reason for reason in report["blocked_reasons"])


def test_missing_source_artifact_blocks(tmp_path):
    tree_path, preflight_path, _ = _write_inputs(tmp_path)
    result = write_commander_assignment_review_pack(
        tree_path=str(tree_path),
        preflight_path=str(preflight_path),
        assignment_path=str(tmp_path / "missing_assignment.json"),
        output_dir=tmp_path / "out",
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "review_pack_blocked"
    assert any("assignment could not be read" in reason for reason in result["report"]["blocked_reasons"])


def test_malformed_source_artifact_blocks(tmp_path):
    tree_path, preflight_path, assignment_path = _write_inputs(tmp_path)
    assignment_path.write_text("{not json", encoding="utf-8")
    result = write_commander_assignment_review_pack(
        tree_path=str(tree_path),
        preflight_path=str(preflight_path),
        assignment_path=str(assignment_path),
        output_dir=tmp_path / "out",
    )
    assert result["ok"] is False
    assert result["report"]["review_status"] == "review_pack_blocked"
    assert any("assignment must contain valid JSON" in reason for reason in result["report"]["blocked_reasons"])


def test_unsafe_source_path_blocks():
    report = build_commander_assignment_review_pack(
        tree_path="../tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=_assignment(),
    )
    assert report["review_status"] == "review_pack_blocked"
    assert any("tree path must not contain traversal" in reason for reason in report["blocked_reasons"])


def test_missing_preflight_coverage_causes_incomplete():
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(
            sub_bosses=[
                _sub_boss(sub_boss_id="cmd-n6-core"),
                _sub_boss(sub_boss_id="cmd-n6-extra", title="Extra sub-boss"),
            ]
        ),
        preflight_data=_preflight(findings=[_finding(sub_boss_id="cmd-n6-core")]),
        assignment_data=_assignment(rows=[_finding(sub_boss_id="cmd-n6-core")]),
    )
    assert report["review_status"] == "review_pack_incomplete"
    assert any("missing preflight coverage" in reason for reason in report["warnings"])


def test_missing_assignment_coverage_causes_incomplete():
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=_assignment(rows=[], assignments=[]),
    )
    assert report["review_status"] == "review_pack_incomplete"
    assert any("missing assignment coverage" in reason for reason in report["warnings"])


def test_missing_evidence_without_evidence_checker_warns():
    finding = _finding(
        evidence_required=[],
        preflight_status="preflight_incomplete",
        incomplete_reasons=["sub_boss cmd-n6-core evidence_required must be non-empty"],
    )
    assignment = _assignment(rows=[finding])
    assignment["assignments"][0]["advisory_roles"] = ["planner", "risk_auditor"]
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(sub_bosses=[_sub_boss(evidence_required=[])]),
        preflight_data=_preflight(findings=[finding], preflight_status="preflight_incomplete"),
        assignment_data=assignment,
    )
    assert report["review_status"] == "review_pack_ready_with_warnings"
    assert any("evidence_checker" in warning for warning in report["warnings"])


def test_scope_specific_roles_warn_when_missing():
    finding = _finding(allowed_files=["web/app.py", "tests/test_ui.py", "docs/roadmap/phase_registry.json"])
    assignment = _assignment(rows=[finding])
    assignment["assignments"][0]["advisory_roles"] = ["planner", "implementer", "reviewer", "evidence_checker"]
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(sub_bosses=[_sub_boss(allowed_files=finding["allowed_files"])]),
        preflight_data=_preflight(findings=[finding]),
        assignment_data=assignment,
    )
    assert report["review_status"] == "review_pack_ready_with_warnings"
    assert any("ui_reviewer" in warning for warning in report["warnings"])
    assert any("test_designer" in warning for warning in report["warnings"])
    assert any("documentation_reviewer" in warning for warning in report["warnings"])


def test_executable_worker_binding_blocks():
    assignment = _assignment()
    assignment["assignments"][0]["worker_id"] = "worker-7"
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=assignment,
    )
    assert report["review_status"] == "review_pack_blocked"
    assert any("executable worker binding" in reason for reason in report["blocked_reasons"])


def test_model_id_as_authority_blocks():
    assignment = _assignment()
    assignment["authority"] = "gpt-4.1"
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=assignment,
    )
    assert report["review_status"] == "review_pack_blocked"
    assert any("model" in reason.lower() for reason in report["blocked_reasons"])


def test_auto_run_auto_apply_auto_merge_flags_block():
    for flag in ("auto_run", "auto_apply", "auto_merge"):
        assignment = _assignment()
        assignment[flag] = True
        report = build_commander_assignment_review_pack(
            tree_path="tree.json",
            preflight_path="preflight.json",
            assignment_path="assignment.json",
            tree_data=_tree(),
            preflight_data=_preflight(),
            assignment_data=assignment,
        )
        assert report["review_status"] == "review_pack_blocked"
        assert any(flag in reason for reason in report["blocked_reasons"])


def test_source_artifacts_are_not_mutated(tmp_path):
    tree_path, preflight_path, assignment_path = _write_inputs(tmp_path)
    before = {
        "tree": tree_path.read_text(encoding="utf-8"),
        "preflight": preflight_path.read_text(encoding="utf-8"),
        "assignment": assignment_path.read_text(encoding="utf-8"),
    }
    result = write_commander_assignment_review_pack(
        tree_path=str(tree_path),
        preflight_path=str(preflight_path),
        assignment_path=str(assignment_path),
        output_dir=tmp_path / "out",
    )
    after = {
        "tree": tree_path.read_text(encoding="utf-8"),
        "preflight": preflight_path.read_text(encoding="utf-8"),
        "assignment": assignment_path.read_text(encoding="utf-8"),
    }
    assert result["ok"] is True
    assert after == before


def test_json_and_markdown_review_pack_artifacts_are_written(tmp_path):
    tree_path, preflight_path, assignment_path = _write_inputs(tmp_path)
    result = write_commander_assignment_review_pack(
        tree_path=str(tree_path),
        preflight_path=str(preflight_path),
        assignment_path=str(assignment_path),
        output_dir=tmp_path / "out",
    )
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["report_kind"] == REPORT_KIND
    assert "# Commander Assignment Review Pack" in md
    for section in (
        "## Summary",
        "## Source Artifacts",
        "## Boss Overview",
        "## Fracture Tree Overview",
        "## Preflight Overview",
        "## Assignment Overview",
        "## Per-Sub-Boss Review",
        "## Risk Coverage",
        "## Evidence Coverage",
        "## Human Review Checklist",
        "## Warnings",
        "## Blocked Reasons",
        "## Boundaries / Guardrails",
        "## Recommended Next Phase",
    ):
        assert section in md


def test_human_review_checklist_includes_approval_validation_and_apply_boundaries():
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=_assignment(),
    )
    checklist = "\n".join(report["human_review_checklist"]).lower()
    assert report["human_review_checklist"] == list(HUMAN_REVIEW_CHECKLIST)
    assert "worker/model" in checklist
    assert "validation/benchmark" in checklist
    assert "patch apply" in checklist


def test_markdown_renderer_does_not_mutate_report():
    report = build_commander_assignment_review_pack(
        tree_path="tree.json",
        preflight_path="preflight.json",
        assignment_path="assignment.json",
        tree_data=_tree(),
        preflight_data=_preflight(),
        assignment_data=_assignment(),
    )
    snap = copy.deepcopy(report)
    assert render_commander_assignment_review_pack_markdown(report)
    assert report == snap


_ROOT = Path(__file__).parent.parent
_CORE = _ROOT / "core" / "commander_assignment_review_pack.py"
_SCRIPT = _ROOT / "scripts" / "create_commander_assignment_review_pack.py"


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


def test_registry_and_picker_recommend_model_n3_after_model_n2():
    data = json.loads((_ROOT / "docs" / "roadmap" / "phase_registry.json").read_text(encoding="utf-8"))
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    assert phases["CMD.N5"]["status"] == "complete"
    assert phases["CMD.N6"]["status"] == "complete"
    assert phases["CMD.N6"]["prerequisites"] == ["CMD.N5"]
    assert phases["CMD.CLOSE"]["status"] == "complete"
    assert phases["CMD.CLOSE"]["prerequisites"] == ["CMD.N6"]
    assert phases["MODEL.N1"]["status"] == "complete"
    assert phases["MODEL.N1"]["prerequisites"] == ["CMD.CLOSE"]
    assert phases["MODEL.N2"]["status"] == "complete"
    assert phases["MODEL.N2"]["prerequisites"] == ["MODEL.N1"]
    assert phases["MODEL.N3"]["status"] == "complete"
    assert phases["MODEL.N3"]["prerequisites"] == ["MODEL.N2"]
    assert phases["MODEL.N4"]["status"] == "complete"
    assert phases["MODEL.N4"]["prerequisites"] == ["MODEL.N3"]
    assert phases["MODEL.N5"]["status"] == "complete"
    assert phases["MODEL.N5"]["prerequisites"] == ["MODEL.N4"]
    assert phases["MODEL.N6"]["status"] == "complete"
    assert phases["MODEL.N6"]["prerequisites"] == ["MODEL.N5"]
    assert phases["MODEL.N7"]["status"] == "complete"
    assert phases["MODEL.N7"]["prerequisites"] == ["MODEL.N6"]
    assert phases["MODEL.CLOSE"]["status"] == "complete"
    assert phases["MODEL.CLOSE"]["prerequisites"] == ["MODEL.N7"]
    assert phases["EVAL.N1"]["status"] == "complete"
    assert phases["EVAL.N1"]["prerequisites"] == ["MODEL.CLOSE"]
    assert phases["EVAL.N2"]["status"] == "complete"
    assert phases["EVAL.N2"]["prerequisites"] == ["EVAL.N1"]
    assert phases["EVAL.N3"]["status"] == "complete"
    assert phases["EVAL.N3"]["prerequisites"] == ["EVAL.N2"]

    pick = pick_phase_candidates(data)
    assert pick["registry_valid"] is True
    assert pick["top_recommendation"]["phase_id"] == "EVAL.N4"
    assert pick["top_recommendation"]["recommended_next_step"] == "prepare_worker_assignment"
