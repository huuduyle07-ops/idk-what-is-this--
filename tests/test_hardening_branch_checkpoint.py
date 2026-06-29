"""HARDEN.CLOSE - Hardening Branch Checkpoint tests.

HARDEN.CLOSE consolidates HARDEN.1, HARDEN.2, and HARDEN.3 evidence into a
report-only branch closure checkpoint. It reads registry/source/artifact data and
writes JSON/Markdown checkpoint artifacts only. It must not call models, apply
patches, run validation or benchmarks, invoke MCP tools, launch workers, contact
the network, write to a database, or change route/auth/UI behavior.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.hardening_branch_checkpoint import (
    HARDEN_PHASE_IDS,
    PHASE_GUARDRAIL_FIELDS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WARNINGS,
    STATUS_NEEDS_HARDEN4,
    THIS_PHASE_ID,
    build_hardening_branch_checkpoint,
    gather_hardening_branch_checkpoint_inputs,
    render_hardening_branch_checkpoint_markdown,
    write_hardening_branch_checkpoint,
)
import scripts.create_hardening_branch_checkpoint as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
HARDEN2_ARTIFACT = (
    PROJECT_ROOT
    / ".agent"
    / "harden"
    / "web_mutation_surface_audit"
    / "web_mutation_surface_audit.json"
)
HARDEN3_ARTIFACT = (
    PROJECT_ROOT
    / ".agent"
    / "harden"
    / "safe_validation_mcp_approval_audit"
    / "safe_validation_mcp_approval_audit.json"
)


def _phase(pid: str, **over) -> dict:
    data = {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": "HARDEN",
        "status": "complete",
        "summary": "Report-only hardening phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "medium",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_x.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/harden/x.json"],
        "notes": ["Report-only; adds no new automation power."],
    }
    data.update(over)
    return data


def _registry(phases: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "updated_at": "2026-06-29T00:00:00+00:00",
        "phases": phases
        if phases is not None
        else [
            _phase("HARDEN.1", title="Web Mutation Auth / CSRF Gate"),
            _phase("HARDEN.2", title="Web Mutation Surface Audit", prerequisites=["HARDEN.1"]),
            _phase(
                "HARDEN.3",
                title="Safe Validation / MCP Approval Enforcement Audit",
                prerequisites=["HARDEN.2"],
            ),
            _phase(
                THIS_PHASE_ID,
                title="Hardening Branch Checkpoint",
                prerequisites=["HARDEN.3"],
            ),
        ],
    }


def _harden1_gate(ok: bool = True) -> dict:
    return {
        "auth_gate_module_exists": ok,
        "gate_function_detected": ok,
        "before_request_wiring_detected": ok,
        "test_exists": ok,
        "token_or_loopback_evidence": ok,
        "status": "present" if ok else "missing",
        "evidence": ["synthetic gate"] if ok else [],
    }


def _harden2_report(warnings: list[str] | None = None, blockers: list[str] | None = None, uncovered: int = 0) -> dict:
    warnings = warnings or []
    blockers = blockers or []
    return {
        "report_kind": "web_mutation_surface_audit",
        "verdict": "fail" if blockers or uncovered else ("pass_with_warnings" if warnings else "pass"),
        "route_counts": {
            "total": 12,
            "mutating": 4,
            "covered_mutating": 4 - uncovered,
            "uncovered_mutating": uncovered,
        },
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": {
            "report_only": True,
            "model_call_performed": False,
            "patch_applied": False,
            "validation_run": False,
            "benchmark_run_performed": False,
            "network_call_performed": False,
            "database_write_performed": False,
            "route_behavior_changed": False,
            "auth_policy_changed": False,
            "ui_behavior_changed": False,
        },
    }


def _harden3_report(warnings: list[str] | None = None, blockers: list[str] | None = None) -> dict:
    warnings = warnings or []
    blockers = blockers or []
    return {
        "report_kind": "safe_validation_mcp_approval_audit",
        "verdict": "fail" if blockers else ("pass_with_warnings" if warnings else "pass"),
        "surface_counts": {
            "routes": 10,
            "functions": 20,
            "validation": 5,
            "mcp": 3,
            "janitor_or_cleanup": 4,
            "approval_gate": 6,
        },
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": {
            "report_only": True,
            "model_call_performed": False,
            "patch_applied": False,
            "validation_run": False,
            "benchmark_run_performed": False,
            "mcp_invocation_performed": False,
            "worker_launch_performed": False,
            "network_call_performed": False,
            "database_write_performed": False,
            "route_behavior_changed": False,
            "auth_policy_changed": False,
            "ui_behavior_changed": False,
        },
    }


def _build(**over) -> dict:
    kwargs = dict(
        registry_data=_registry(),
        registry_load_error="",
        harden1_gate_evidence=_harden1_gate(),
        harden2_report=_harden2_report(),
        harden2_load_error="",
        harden3_report=_harden3_report(),
        harden3_load_error="",
        report_id="r",
        created_at="t",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
        harden2_artifact_path=".agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.json",
        harden3_artifact_path=".agent/harden/safe_validation_mcp_approval_audit/safe_validation_mcp_approval_audit.json",
    )
    kwargs.update(over)
    return build_hardening_branch_checkpoint(**kwargs)


def test_clean_evidence_freezes_without_warnings():
    report = _build()
    assert report["report_kind"] == REPORT_KIND == "hardening_branch_checkpoint"
    assert report["checkpoint_status"] == STATUS_FROZEN == "frozen"
    assert report["warnings"] == []
    assert report["blockers"] == []
    assert report["harden4_required"] is False
    assert report["recommended_next_phase"].startswith("MIRROR.1")
    assert report["phase_status"]["all_required_harden_phases_complete"] is True
    assert report["harden1_gate_evidence"]["status"] == "present"
    assert report["harden2_route_surface_evidence"]["uncovered_mutating_routes"] == 0
    assert report["harden3_validation_mcp_approval_evidence"]["blocker_count"] == 0


def test_manual_review_warnings_freeze_with_warning_status():
    report = _build(
        harden2_report=_harden2_report(warnings=["dangerous GET-only route needs manual review"]),
        harden3_report=_harden3_report(warnings=["approval field exists but enforcement is indirect"]),
    )
    assert report["checkpoint_status"] == STATUS_FROZEN_WARNINGS
    assert report["blockers"] == []
    assert report["harden4_required"] is False
    assert report["recommended_next_phase"].startswith("MIRROR.1")
    assert {item["source"] for item in report["warning_inventory"]} == {"HARDEN.2", "HARDEN.3"}
    assert all(item["classification"] == "manual_review" for item in report["warning_inventory"])


def test_missing_harden2_artifact_blocks_checkpoint():
    report = _build(harden2_report=None, harden2_load_error="missing artifact")
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["recommended_next_phase"] == "Fix missing evidence / artifact first"
    assert any("HARDEN.2 artifact" in blocker for blocker in report["blockers"])


def test_missing_harden1_gate_blocks_checkpoint():
    report = _build(harden1_gate_evidence=_harden1_gate(ok=False))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("HARDEN.1 auth gate" in blocker for blocker in report["blockers"])


def test_incomplete_required_harden_phase_blocks_checkpoint():
    phases = [
        _phase("HARDEN.1"),
        _phase("HARDEN.2"),
        _phase("HARDEN.3", status="proposed"),
        _phase(THIS_PHASE_ID, prerequisites=["HARDEN.3"]),
    ]
    report = _build(registry_data=_registry(phases=phases))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("HARDEN.3" in blocker and "complete" in blocker for blocker in report["blockers"])


def test_harden2_uncovered_mutating_routes_require_harden4():
    report = _build(harden2_report=_harden2_report(uncovered=1))
    assert report["checkpoint_status"] == STATUS_NEEDS_HARDEN4
    assert report["harden4_required"] is True
    assert report["recommended_next_phase"].startswith("HARDEN.4")
    assert any("uncovered mutating" in blocker for blocker in report["blockers"])


def test_harden2_blocker_requires_harden4():
    report = _build(harden2_report=_harden2_report(blockers=["mutating route /x outside gate"]))
    assert report["checkpoint_status"] == STATUS_NEEDS_HARDEN4
    assert any(item["source"] == "HARDEN.2" for item in report["blocker_inventory"])


def test_harden3_blocker_requires_harden4():
    report = _build(harden3_report=_harden3_report(blockers=["confirmed approval bypass"]))
    assert report["checkpoint_status"] == STATUS_NEEDS_HARDEN4
    assert any(item["source"] == "HARDEN.3" for item in report["blocker_inventory"])


def test_harden_phase_guardrail_power_blocks_checkpoint():
    phases = [
        _phase("HARDEN.1"),
        _phase("HARDEN.2", model_calls_allowed=True),
        _phase("HARDEN.3"),
        _phase(THIS_PHASE_ID, prerequisites=["HARDEN.3"]),
    ]
    report = _build(registry_data=_registry(phases=phases))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("model_calls_allowed" in blocker for blocker in report["blockers"])


def test_markdown_contains_required_sections():
    md = render_hardening_branch_checkpoint_markdown(_build())
    assert "# Hardening Branch Checkpoint" in md
    low = md.lower()
    for section in (
        "## summary",
        "## phase status",
        "## harden.1 gate evidence",
        "## harden.2 route surface evidence",
        "## harden.3 validation / mcp / approval evidence",
        "## warning inventory",
        "## blocker inventory",
        "## freeze decision",
        "## recommended next phase",
        "## boundaries / guardrails",
    ):
        assert section in low, section


def test_write_outputs_json_and_markdown(tmp_path):
    out = tmp_path / "out"
    result = write_hardening_branch_checkpoint(
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
        harden2_artifact_path="h2.json",
        harden3_artifact_path="h3.json",
        output_dir=out,
        report_id="write",
        created_at="2026-06-29T00:00:00+00:00",
        inputs={
            "registry_data": _registry(),
            "registry_load_error": "",
            "harden1_gate_evidence": _harden1_gate(),
            "harden2_report": _harden2_report(),
            "harden2_load_error": "",
            "harden3_report": _harden3_report(),
            "harden3_load_error": "",
        },
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "hardening_branch_checkpoint.json"
    assert Path(result["md_path"]).name == "hardening_branch_checkpoint.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_id"] == "write"
    assert data["report_kind"] == REPORT_KIND


def test_gather_tolerates_missing_inputs(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    inputs = gather_hardening_branch_checkpoint_inputs(
        repo_path=repo,
        registry_path=repo / "missing_registry.json",
        harden2_artifact_path=repo / "missing_h2.json",
        harden3_artifact_path=repo / "missing_h3.json",
    )
    assert inputs["registry_data"] is None
    assert inputs["registry_load_error"]
    assert inputs["harden2_load_error"]
    assert inputs["harden3_load_error"]
    report = build_hardening_branch_checkpoint(**inputs)
    assert report["checkpoint_status"] == STATUS_BLOCKED


def test_cli_writes_real_repo_artifacts(tmp_path):
    out = tmp_path / "out"
    result = script.run_create_hardening_branch_checkpoint(
        repo_path=str(PROJECT_ROOT),
        registry=str(REAL_REGISTRY),
        harden2_artifact=str(HARDEN2_ARTIFACT),
        harden3_artifact=str(HARDEN3_ARTIFACT),
        output_root=str(out),
        report_id="cli",
        created_at="2026-06-29T00:00:00+00:00",
    )
    assert result["ok"] is True
    assert result["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WARNINGS}
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    assert result["report"]["phase_status"]["all_required_harden_phases_complete"] is True
    assert result["report"]["harden2_route_surface_evidence"]["uncovered_mutating_routes"] == 0
    assert result["report"]["harden2_route_surface_evidence"]["blocker_count"] == 0
    assert result["report"]["harden3_validation_mcp_approval_evidence"]["blocker_count"] == 0


def test_cli_exit_codes_for_warning_and_blocked(tmp_path):
    warn_reg = tmp_path / "registry.json"
    warn_reg.write_text(json.dumps(_registry()), encoding="utf-8")
    h2 = tmp_path / "h2.json"
    h3 = tmp_path / "h3.json"
    h2.write_text(json.dumps(_harden2_report(warnings=["manual review"])), encoding="utf-8")
    h3.write_text(json.dumps(_harden3_report()), encoding="utf-8")
    base = [
        "--repo-path", str(PROJECT_ROOT),
        "--registry", str(warn_reg),
        "--harden2-artifact", str(h2),
        "--harden3-artifact", str(h3),
        "--output-root", str(tmp_path / "out"),
        "--report-id", "x",
        "--created-at", "t",
    ]
    assert script.main(base) != 0
    assert script.main(base + ["--allow-warnings"]) == 0

    h2.write_text(json.dumps(_harden2_report(uncovered=1)), encoding="utf-8")
    assert script.main(base + ["--allow-warnings"]) != 0


def test_real_registry_registers_harden_close_complete():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert THIS_PHASE_ID in by_id
    close = by_id[THIS_PHASE_ID]
    assert close["status"] == "complete"
    assert close["prerequisites"] == ["HARDEN.3"]
    assert close["merge_allowed"] is False
    assert close["network_allowed"] is False
    assert close["model_calls_allowed"] is False
    assert close["writes_real_repo"] is False


def test_constants_match_spec():
    assert HARDEN_PHASE_IDS == ("HARDEN.1", "HARDEN.2", "HARDEN.3")
    assert THIS_PHASE_ID == "HARDEN.CLOSE"
    assert STATUS_FROZEN == "frozen"
    assert STATUS_FROZEN_WARNINGS == "frozen_with_manual_review_warnings"
    assert STATUS_NEEDS_HARDEN4 == "needs_harden_4"
    assert STATUS_BLOCKED == "blocked"
    assert set(PHASE_GUARDRAIL_FIELDS) == {
        "model_calls_allowed",
        "network_allowed",
        "merge_allowed",
        "writes_real_repo",
    }


def test_guardrail_flags_show_report_only_boundaries():
    guardrails = _build()["guardrails"]
    assert guardrails["report_only"] is True
    for key, value in guardrails.items():
        if key == "report_only":
            continue
        assert value is False, key


def test_core_and_script_do_not_call_execution_sinks():
    core_src = (PROJECT_ROOT / "core" / "hardening_branch_checkpoint.py").read_text(encoding="utf-8")
    script_src = (PROJECT_ROOT / "scripts" / "create_hardening_branch_checkpoint.py").read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    imported_roots: set[str] = set()
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.append(node.func.id)

    forbidden_imports = {
        "subprocess",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "mcp",
        "agents",
        "database",
    }
    assert sorted(forbidden_imports & imported_roots) == []

    forbidden_calls = {
        "run_gemini_request",
        "run_deepseek_review",
        "run_agent_web",
        "apply_patch",
        "run_patch_plan_with_artifacts",
        "run_safe_validation_command",
        "run_benchmarks",
        "start_benchmark_run_async",
        "start_overnight_async",
        "Popen",
        "run",
        "call",
        "check_call",
        "check_output",
        "request",
        "urlopen",
        "launch_worker",
        "consolidate_all",
        "copytree",
        "rmtree",
        "unlink",
    }
    assert sorted(forbidden_calls & set(call_names)) == []
