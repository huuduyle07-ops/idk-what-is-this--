"""Tests for MIRROR.CLOSE - Mirror Tunnel Branch Checkpoint.

MIRROR.CLOSE freezes the manual Mirror Tunnel evidence loop before any live
runtime instrumentation is added. It is report-only: it reads registry/source/
artifact evidence and writes checkpoint JSON/Markdown only.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.mirror_tunnel_branch_checkpoint import (
    REQUIRED_MIRROR_PHASE_IDS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN_COMPLETE,
    STATUS_FROZEN_WARNINGS,
    STATUS_NEEDS_MANUAL_EVIDENCE,
    THIS_PHASE_ID,
    build_mirror_tunnel_branch_checkpoint,
    gather_mirror_tunnel_branch_checkpoint_inputs,
    render_mirror_tunnel_branch_checkpoint_markdown,
    write_mirror_tunnel_branch_checkpoint,
)
import scripts.create_mirror_tunnel_branch_checkpoint as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _phase(pid: str, **over) -> dict:
    data = {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": "MIRROR",
        "status": "complete",
        "summary": "Report-only Mirror Tunnel phase.",
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
        "prerequisites": [],
        "expected_artifacts": [".agent/mirror_tunnel/x.json"],
        "notes": ["Report-only; adds no runtime power."],
    }
    data.update(over)
    return data


def _registry(phases: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "updated_at": "2026-06-30T00:00:00+00:00",
        "phases": phases
        if phases is not None
        else [
            _phase("MIRROR.1"),
            _phase("MIRROR.2", prerequisites=["MIRROR.1"]),
            _phase("MIRROR.3", prerequisites=["MIRROR.2"]),
            _phase("MIRROR.4", prerequisites=["MIRROR.3"]),
            _phase("MIRROR.5", prerequisites=["MIRROR.4"]),
            _phase("MIRROR.6", prerequisites=["MIRROR.5"]),
            _phase(THIS_PHASE_ID, prerequisites=["MIRROR.6"]),
        ],
    }


def _safe_guardrails(**over) -> dict:
    data = {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "execution_blocking_performed": False,
        "writes_report_artifacts_only": True,
    }
    data.update(over)
    return data


def _artifact(kind: str, **over) -> dict:
    data = {"report_kind": kind, "guardrails": _safe_guardrails(), "boundaries": ["report-only"]}
    data.update(over)
    return data


def _complete_artifacts(**over) -> dict:
    data = {
        "trace_contract": _artifact(
            "mirror_tunnel_trace_contract",
            status="complete_trace",
            frames=[{"frame_type": "user_intent"}, {"frame_type": "final_answer"}],
        ),
        "derailment_score": _artifact("mirror_tunnel_derailment_score", verdict="aligned"),
        "claim_diff_check": _artifact("mirror_tunnel_claim_diff_check", overall_claim_support="supported"),
        "ingestion_plan": _artifact("mirror_tunnel_ingestion_plan", status="ready_for_manual_ingestion"),
        "manual_trace": _artifact(
            "mirror_tunnel_trace_contract",
            assembly_method="manual_trace_assembler",
            status="complete_trace",
            frames=[{"frame_type": "user_intent"}, {"frame_type": "validation_evidence"}, {"frame_type": "final_answer"}],
        ),
        "manual_review": _artifact(
            "mirror_tunnel_manual_review",
            combined_verdict="trustworthy_trace",
            warnings=[],
            frame_coverage={"available_frame_count": 3, "unknown_artifact_count": 0},
        ),
    }
    data.update(over)
    return data


def _artifact_errors(**over) -> dict:
    data = {key: "" for key in _complete_artifacts()}
    data.update(over)
    return data


def _core_checks(ok: bool = True) -> list[dict]:
    return [
        {
            "phase_id": pid,
            "path": f"core/{pid.lower().replace('.', '_')}.py",
            "exists": ok,
            "source_guardrails_ok": ok,
            "issues": [] if ok else ["missing core module"],
        }
        for pid in (*REQUIRED_MIRROR_PHASE_IDS, THIS_PHASE_ID)
    ]


def _source_guardrail_summary(ok: bool = True) -> dict:
    return {
        "ok": ok,
        "files_checked": ["core/mirror_tunnel_trace_contract.py"],
        "forbidden_imports": [] if ok else ["subprocess"],
        "forbidden_calls": [] if ok else ["apply_patch"],
    }


def _live_instrumentation_summary(found: bool = False) -> dict:
    return {
        "live_runtime_instrumentation_added": found,
        "matches": [{"path": "web/app.py", "token": "mirror_tunnel"}] if found else [],
    }


def _build(**over) -> dict:
    kwargs = dict(
        registry_data=_registry(),
        registry_load_error="",
        artifact_reports=_complete_artifacts(),
        artifact_load_errors=_artifact_errors(),
        core_module_checks=_core_checks(),
        source_guardrail_summary=_source_guardrail_summary(),
        live_instrumentation_summary=_live_instrumentation_summary(),
        report_id="r",
        created_at="2026-06-30T00:00:00+00:00",
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
    )
    kwargs.update(over)
    return build_mirror_tunnel_branch_checkpoint(**kwargs)


def test_constants_match_spec():
    assert REPORT_KIND == "mirror_tunnel_branch_checkpoint"
    assert THIS_PHASE_ID == "MIRROR.CLOSE"
    assert REQUIRED_MIRROR_PHASE_IDS == ("MIRROR.1", "MIRROR.2", "MIRROR.3", "MIRROR.4", "MIRROR.5", "MIRROR.6")
    assert STATUS_FROZEN_COMPLETE == "frozen_manual_pipeline_complete"
    assert STATUS_FROZEN_WARNINGS == "frozen_with_manual_review_warnings"
    assert STATUS_NEEDS_MANUAL_EVIDENCE == "needs_more_manual_evidence"
    assert STATUS_BLOCKED == "blocked"


def test_complete_manual_pipeline_freezes_cleanly():
    report = _build()
    assert report["checkpoint_status"] == STATUS_FROZEN_COMPLETE
    assert report["recommended_next_phase"] == "MIRROR.7 - Shadow Live Trace Writer"
    assert report["manual_pipeline_summary"]["usable_even_if_real_trace_quality_is_weak"] is True
    assert report["freeze_decision"]["live_instrumentation_allowed_only_as_shadow_default_off_non_blocking"] is True
    assert report["guardrail_summary"]["all_clear"] is True
    assert report["blockers"] == []
    assert report["warnings"] == []


def test_current_weak_reports_freeze_with_manual_review_warnings():
    artifacts = _complete_artifacts(
        trace_contract=_artifact(
            "mirror_tunnel_trace_contract",
            status="insufficient_evidence",
            frames=[{"frame_type": "unknown_artifact"}],
        ),
        derailment_score=_artifact("mirror_tunnel_derailment_score", verdict="insufficient_trace"),
        claim_diff_check=_artifact("mirror_tunnel_claim_diff_check", overall_claim_support="insufficient_evidence"),
        manual_review=_artifact(
            "mirror_tunnel_manual_review",
            combined_verdict="review_recommended",
            warnings=["unsupported claims detected"],
            frame_coverage={"available_frame_count": 3, "unknown_artifact_count": 0},
        ),
    )

    report = _build(artifact_reports=artifacts)

    assert report["checkpoint_status"] == STATUS_FROZEN_WARNINGS
    assert report["manual_pipeline_summary"]["meaningful_manual_frame_count"] == 3
    assert any("insufficient_trace" in warning for warning in report["warnings"])
    assert any("unsupported claims detected" in warning for warning in report["warnings"])


def test_missing_required_phase_blocks_checkpoint():
    phases = [_phase("MIRROR.1"), _phase("MIRROR.2"), _phase("MIRROR.3")]
    report = _build(registry_data=_registry(phases=phases))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("MIRROR.4 is missing" in blocker for blocker in report["blockers"])


def test_missing_manual_artifact_needs_more_manual_evidence():
    report = _build(
        artifact_reports=_complete_artifacts(manual_review=None),
        artifact_load_errors=_artifact_errors(manual_review="missing manual review artifact"),
    )
    assert report["checkpoint_status"] == STATUS_NEEDS_MANUAL_EVIDENCE
    assert any("manual review" in blocker.lower() for blocker in report["manual_evidence_gaps"])
    assert report["freeze_decision"]["can_freeze_manual_branch"] is False


def test_unsafe_artifact_guardrail_blocks_checkpoint():
    unsafe = _artifact("mirror_tunnel_derailment_score", verdict="aligned")
    unsafe["guardrails"] = _safe_guardrails(model_call_performed=True)

    report = _build(artifact_reports=_complete_artifacts(derailment_score=unsafe))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("model_call_performed" in blocker for blocker in report["blockers"])


def test_live_runtime_instrumentation_blocks_checkpoint():
    report = _build(live_instrumentation_summary=_live_instrumentation_summary(found=True))
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("live runtime instrumentation" in blocker.lower() for blocker in report["blockers"])


def test_markdown_contains_required_sections():
    md = render_mirror_tunnel_branch_checkpoint_markdown(_build())
    assert "# Mirror Tunnel Branch Checkpoint" in md
    low = md.lower()
    for section in (
        "## summary",
        "## phase status",
        "## artifact evidence",
        "## manual pipeline",
        "## live instrumentation",
        "## guardrail summary",
        "## freeze decision",
        "## recommended next phase",
        "## warnings",
        "## blockers",
        "## boundaries",
    ):
        assert section in low, section


def test_write_outputs_json_and_markdown(tmp_path):
    result = write_mirror_tunnel_branch_checkpoint(
        repo_path=".",
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=tmp_path / "checkpoint",
        report_id="write",
        created_at="2026-06-30T00:00:00+00:00",
        inputs={
            "registry_data": _registry(),
            "registry_load_error": "",
            "artifact_reports": _complete_artifacts(),
            "artifact_load_errors": _artifact_errors(),
            "core_module_checks": _core_checks(),
            "source_guardrail_summary": _source_guardrail_summary(),
            "live_instrumentation_summary": _live_instrumentation_summary(),
        },
    )
    assert result["ok"] is True
    assert Path(result["json_path"]).name == "mirror_tunnel_branch_checkpoint.json"
    assert Path(result["md_path"]).name == "mirror_tunnel_branch_checkpoint.md"
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_id"] == "write"
    assert data["report_kind"] == REPORT_KIND


def test_gather_real_inputs_and_cli_current_status(tmp_path):
    inputs = gather_mirror_tunnel_branch_checkpoint_inputs(repo_path=PROJECT_ROOT, registry_path=REAL_REGISTRY)
    report = build_mirror_tunnel_branch_checkpoint(**inputs, report_id="real", created_at="2026-06-30T00:00:00+00:00")
    assert report["checkpoint_status"] == STATUS_FROZEN_WARNINGS
    assert report["phase_status"]["all_required_mirror_phases_complete"] is True
    assert report["manual_pipeline_summary"]["usable_even_if_real_trace_quality_is_weak"] is True
    assert report["live_instrumentation_summary"]["live_runtime_instrumentation_added"] is False
    assert report["live_instrumentation_summary"]["allowed_shadow_only_default_off_matches"]

    result = script.run_create_mirror_tunnel_branch_checkpoint(
        repo_path=str(PROJECT_ROOT),
        registry=str(REAL_REGISTRY),
        output_root=str(tmp_path / "out"),
        report_id="cli",
        created_at="2026-06-30T00:00:00+00:00",
    )
    assert result["checkpoint_status"] == STATUS_FROZEN_WARNINGS
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_cli_exit_codes_for_warning_and_blocked(tmp_path):
    warn_reg = tmp_path / "registry.json"
    warn_reg.write_text(json.dumps(_registry()), encoding="utf-8")
    base = [
        "--repo-path",
        str(PROJECT_ROOT),
        "--registry",
        str(warn_reg),
        "--output-root",
        str(tmp_path / "out"),
        "--report-id",
        "x",
        "--created-at",
        "t",
    ]
    assert script.main(base) != 0
    assert script.main(base + ["--allow-warnings"]) == 0

    missing = tmp_path / "missing.json"
    assert script.main(base + ["--manual-review", str(missing), "--allow-warnings"]) != 0


def test_real_registry_registers_mirror7_complete_and_mirror8_proposed():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert THIS_PHASE_ID in by_id
    assert by_id[THIS_PHASE_ID]["status"] == "complete"
    assert by_id[THIS_PHASE_ID]["prerequisites"] == ["MIRROR.6"]
    assert "MIRROR.7" in by_id
    assert by_id["MIRROR.7"]["status"] == "complete"
    assert by_id["MIRROR.7"]["prerequisites"] == [THIS_PHASE_ID]
    assert by_id["MIRROR.7"]["title"] == "Shadow Live Trace Writer"
    assert by_id["MIRROR.7"]["model_calls_allowed"] is False
    assert by_id["MIRROR.7"]["network_allowed"] is False
    assert by_id["MIRROR.7"]["writes_real_repo"] is False
    assert by_id["MIRROR.8"]["status"] == "complete"
    assert by_id["MIRROR.8"]["prerequisites"] == ["MIRROR.7"]
    assert by_id["MIRROR.9"]["status"] == "proposed"
    assert by_id["MIRROR.9"]["prerequisites"] == ["MIRROR.8"]


def test_guardrail_flags_show_report_only_boundaries():
    guardrails = _build()["guardrails"]
    assert guardrails["report_only"] is True
    for key, value in guardrails.items():
        if key == "report_only":
            continue
        assert value is False, key


def test_core_and_script_do_not_call_execution_sinks():
    core_src = (PROJECT_ROOT / "core" / "mirror_tunnel_branch_checkpoint.py").read_text(encoding="utf-8")
    script_src = (PROJECT_ROOT / "scripts" / "create_mirror_tunnel_branch_checkpoint.py").read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    imported_roots: set[str] = set()
    call_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.add(node.func.id)

    forbidden_imports = {
        "anthropic",
        "benchmarks",
        "database",
        "docker",
        "httpx",
        "mcp",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
        "web",
    }
    assert sorted(forbidden_imports & imported_roots) == []

    forbidden_calls = {
        "apply_patch",
        "call_model",
        "check_call",
        "check_output",
        "connect",
        "create_dream",
        "execute",
        "invoke_mcp",
        "launch_worker",
        "Popen",
        "post",
        "request",
        "run",
        "run_benchmarks",
        "run_safe_validation_command",
        "system",
        "urlopen",
    }
    assert sorted(forbidden_calls & call_names) == []
