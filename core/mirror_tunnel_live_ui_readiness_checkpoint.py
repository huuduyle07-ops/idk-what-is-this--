"""MIRROR.CLOSE3 - Mirror Tunnel Live UI Readiness Checkpoint.

This checkpoint freezes the MIRROR.7-MIRROR.12 live/UI Mirror Tunnel slice
before capture-quality expansion or a branch change. It reads local registry,
source, and optional MIRROR.12 readiness evidence, then writes checkpoint
artifacts only.

It does not call models, apply patches, run validation, run benchmarks, invoke
MCP tools, launch workers, execute Dream or Replay actions, use Docker or
subprocess, contact network services, write to a database, change route
behavior, change auth policy, score at runtime, mutate live traces, generate
previews, change UI behavior, or block execution.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.phase_picker import pick_phase_candidates


REPORT_KIND = "mirror_tunnel_live_ui_readiness_checkpoint"
JSON_NAME = "mirror_tunnel_live_ui_readiness_checkpoint.json"
MD_NAME = "mirror_tunnel_live_ui_readiness_checkpoint.md"
DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "live_ui_readiness_checkpoint"
DEFAULT_READINESS_ARTIFACT = (
    Path(".agent")
    / "mirror_tunnel"
    / "live_demo_readiness"
    / "mirror_tunnel_live_demo_readiness.json"
)
DEFAULT_PREVIOUS_CHECKPOINT_ARTIFACT = (
    Path(".agent") / "mirror_tunnel" / "branch_checkpoint" / "mirror_tunnel_branch_checkpoint.json"
)

REQUIRED_MIRROR_LIVE_UI_PHASE_IDS: tuple[str, ...] = (
    "MIRROR.7",
    "MIRROR.8",
    "MIRROR.9",
    "MIRROR.10",
    "MIRROR.11",
    "MIRROR.12",
)
THIS_PHASE_ID = "MIRROR.CLOSE3"
RECOMMENDED_NEXT_PHASE = "MIRROR.13 - Live Trace Frame Capture Quality Plan"
ALTERNATIVE_NEXT_BRANCH = "MODEL.N1 or EVAL branch if Mirror should pause after CLOSE3"

STATUS_FROZEN = "live_ui_readiness_frozen"
STATUS_FROZEN_WITH_WARNINGS = "live_ui_readiness_frozen_with_warnings"
STATUS_NEEDS_LIVE_DEMO_EVIDENCE = "needs_live_demo_evidence"
STATUS_BLOCKED = "blocked"

DEMO_READY_STATUSES = {"demo_ready", "demo_ready_with_warnings"}

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

SOURCE_PATHS: dict[str, str] = {
    "mirror7": "core/mirror_tunnel_shadow_live_trace.py",
    "mirror8": "core/mirror_tunnel_live_trace_scoring_preview.py",
    "mirror9": "core/mirror_tunnel_operator_panel_plan.py",
    "template": "web/templates/index.html",
    "route": "web/app.py",
    "mirror12": "core/mirror_tunnel_live_demo_readiness.py",
}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.CLOSE3 is report-only.",
    "MIRROR.CLOSE3 is checkpoint only.",
    "MIRROR.CLOSE3 performs no model call.",
    "MIRROR.CLOSE3 performs no patch apply.",
    "MIRROR.CLOSE3 performs no validation run.",
    "MIRROR.CLOSE3 performs no benchmark run.",
    "MIRROR.CLOSE3 performs no MCP invocation.",
    "MIRROR.CLOSE3 performs no worker launch.",
    "MIRROR.CLOSE3 performs no Dream execution.",
    "MIRROR.CLOSE3 performs no Replay janitor apply.",
    "MIRROR.CLOSE3 performs no Docker/subprocess use.",
    "MIRROR.CLOSE3 performs no network call.",
    "MIRROR.CLOSE3 performs no database write.",
    "MIRROR.CLOSE3 performs no route behavior change.",
    "MIRROR.CLOSE3 performs no auth policy change.",
    "MIRROR.CLOSE3 performs no runtime scoring.",
    "MIRROR.CLOSE3 performs no live trace mutation.",
    "MIRROR.CLOSE3 performs no preview generation.",
    "MIRROR.CLOSE3 performs no UI behavior change.",
    "MIRROR.CLOSE3 performs no execution blocking.",
    "MIRROR.CLOSE3 writes checkpoint artifacts only.",
)

FORBIDDEN_RUNTIME_SCORING_MARKERS: tuple[str, ...] = (
    "build_mirror_tunnel_derailment_score",
    "build_mirror_tunnel_claim_diff_check",
    "build_mirror_tunnel_live_trace_scoring_preview",
    "write_mirror_tunnel_live_trace_scoring_preview",
    "runtime_scoring_performed\": True",
    "runtime_scoring_performed': True",
    "scoring_during_run\": True",
    "scoring_during_run': True",
)

FORBIDDEN_LOADER_GENERATION_MARKERS: tuple[str, ...] = (
    "build_mirror_tunnel_live_trace_scoring_preview",
    "write_mirror_tunnel_live_trace_scoring_preview",
    "build_mirror_tunnel_derailment_score",
    "build_mirror_tunnel_claim_diff_check",
    "maybe_write_shadow_live_trace",
    "write_shadow_live_trace",
)

FORBIDDEN_LOADER_MUTATION_MARKERS: tuple[str, ...] = (
    ".write_text",
    ".mkdir",
    ".unlink",
    ".rename",
    ".replace",
    "open(",
    "request.form",
    "request.values",
)

FORBIDDEN_PANEL_LABELS: tuple[str, ...] = (
    "Apply",
    "Reject",
    "Approve",
    "Run Validation",
    "Run Benchmark",
    "Score Now",
    "Launch Worker",
    "Generate Patch",
)

FORBIDDEN_AST_IMPORT_ROOTS: set[str] = {
    "agents",
    "benchmarks",
    "database",
    "docker",
    "flask",
    "google",
    "httpx",
    "mcp",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}

FORBIDDEN_AST_CALLS: set[str] = {
    "apply_patch",
    "call_model",
    "check_call",
    "check_output",
    "connect",
    "create_dream",
    "invoke_mcp",
    "launch_worker",
    "Popen",
    "post",
    "request",
    "run_benchmarks",
    "run_safe_validation_command",
    "run_validation_command",
    "system",
    "urlopen",
}


def build_mirror_tunnel_live_ui_readiness_checkpoint(
    *,
    registry_data: Any = None,
    registry_load_error: str = "",
    source_texts: dict[str, str] | None = None,
    source_load_errors: dict[str, str] | None = None,
    demo_readiness_artifact: dict[str, Any] | None = None,
    demo_readiness_load_error: str = "",
    previous_checkpoint_artifact: dict[str, Any] | None = None,
    previous_checkpoint_load_error: str = "",
    readiness_artifact_path: str | Path = "",
    previous_checkpoint_path: str | Path = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str | Path = "",
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Build a report-only checkpoint from already-loaded evidence."""
    source_texts = dict(source_texts or {})
    source_load_errors = dict(source_load_errors or {})
    created = str(created_at or _utc_now())

    pick = pick_phase_candidates(registry_data)
    phase_completion = _phase_completion(registry_data, pick)
    runtime_safety = _runtime_safety_checks(source_texts, source_load_errors)
    ui_safety = _ui_safety_checks(source_texts, source_load_errors)
    loader_safety = _loader_safety_checks(source_texts, source_load_errors)
    demo_evidence = _demo_readiness_evidence(
        demo_readiness_artifact,
        demo_readiness_load_error,
        readiness_artifact_path,
    )
    previous_checkpoint = _previous_checkpoint_evidence(
        previous_checkpoint_artifact,
        previous_checkpoint_load_error,
        previous_checkpoint_path,
    )
    source_guardrails = _source_guardrail_checks(source_texts, source_load_errors)

    blockers: list[str] = []
    warnings: list[str] = []

    if registry_load_error:
        blockers.append(f"phase registry missing or unreadable: {registry_load_error}")
    if not pick.get("registry_valid"):
        for error in pick.get("errors") or ["phase registry is invalid"]:
            blockers.append(f"phase registry invalid: {error}")

    blockers.extend(phase_completion["blockers"])
    blockers.extend(runtime_safety["blockers"])
    blockers.extend(ui_safety["blockers"])
    blockers.extend(loader_safety["blockers"])
    blockers.extend(source_guardrails["blockers"])
    blockers.extend(demo_evidence["blockers"])

    if previous_checkpoint.get("load_error"):
        warnings.append("previous MIRROR.CLOSE checkpoint artifact is absent or unreadable")
    if not demo_evidence["present"]:
        warnings.append("no MIRROR.12 readiness artifact was found")
    warnings.extend(demo_evidence["warnings"])
    warnings.extend(source_guardrails["warnings"])

    missing_evidence = _missing_evidence(demo_evidence, previous_checkpoint)

    blockers = _dedupe_strings(blockers)
    warnings = _dedupe_strings(warnings)

    if blockers:
        status = STATUS_BLOCKED
        reason = f"{len(blockers)} blocker(s) prevent freezing the live/UI chain"
    elif not demo_evidence["real_demo_chain_exists"]:
        status = STATUS_NEEDS_LIVE_DEMO_EVIDENCE
        reason = "live/UI chain is safe and complete, but no real MIRROR.7/MIRROR.8/MIRROR.11 demo evidence is available"
    elif warnings or not demo_evidence["useful_frame_coverage"]:
        status = STATUS_FROZEN_WITH_WARNINGS
        reason = "live/UI chain is safe and complete, but demo evidence or trace quality still carries warnings"
    else:
        status = STATUS_FROZEN
        reason = "MIRROR.7 through MIRROR.12 are safe, complete, advisory, and ready to freeze"

    final_verdict = {
        "status": status,
        "reason": reason,
        "can_freeze_live_ui_slice": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "needs_manual_demo_evidence": status == STATUS_NEEDS_LIVE_DEMO_EVIDENCE,
        "advisory_non_blocking_policy_preserved": status != STATUS_BLOCKED,
    }

    return {
        "report_kind": REPORT_KIND,
        "report_id": str(report_id or ""),
        "created_at": created,
        "repo_path": _norm_path(repo_path),
        "registry_path": _norm_path(registry_path),
        "checkpoint_status": status,
        "checkpoint_reason": reason,
        "summary": {
            "required_phase_count": len(REQUIRED_MIRROR_LIVE_UI_PHASE_IDS),
            "all_required_phases_complete": phase_completion["all_required_complete"],
            "runtime_safety_clear": runtime_safety["all_clear"],
            "ui_safety_clear": ui_safety["all_clear"],
            "loader_safety_clear": loader_safety["all_clear"],
            "real_demo_chain_exists": demo_evidence["real_demo_chain_exists"],
            "advisory_non_blocking_policy_preserved": final_verdict["advisory_non_blocking_policy_preserved"],
        },
        "phase_completion": phase_completion,
        "runtime_safety_checks": runtime_safety,
        "ui_safety_checks": ui_safety,
        "loader_safety_checks": loader_safety,
        "demo_readiness_evidence": demo_evidence,
        "previous_checkpoint_evidence": previous_checkpoint,
        "source_guardrail_checks": source_guardrails,
        "missing_evidence": missing_evidence,
        "warnings": warnings,
        "blockers": blockers,
        "final_verdict": final_verdict,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "alternative_next_branch": ALTERNATIVE_NEXT_BRANCH,
        "guardrails": _guardrails(),
        "boundaries": list(BOUNDARIES),
        "artifact_paths": {},
    }


def gather_mirror_tunnel_live_ui_readiness_checkpoint_inputs(
    *,
    repo_path: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY,
    readiness_artifact_path: str | Path | None = None,
    previous_checkpoint_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read local registry, source, and optional artifacts without running anything."""
    repo = Path(repo_path or ".").expanduser().resolve()
    registry_file = _resolve_repo_path(repo, registry_path)
    registry_data, registry_load_error = _load_json_object(registry_file)

    source_texts: dict[str, str] = {}
    source_load_errors: dict[str, str] = {}
    for key, rel in SOURCE_PATHS.items():
        path = repo / rel
        text, error = _load_text(path)
        if key == "route" and text:
            text = _between_markers(
                text,
                "# MIRROR.11 read-only preview loader",
                "# /MIRROR.11 read-only preview loader",
            )
        source_texts[key] = text
        source_load_errors[key] = error

    readiness_raw = readiness_artifact_path
    if readiness_raw is None:
        readiness_raw = DEFAULT_READINESS_ARTIFACT
    readiness_file = _resolve_repo_path(repo, readiness_raw) if str(readiness_raw or "").strip() else None
    readiness_artifact, readiness_error = _load_json_object(readiness_file)

    previous_raw = previous_checkpoint_path
    if previous_raw is None:
        previous_raw = DEFAULT_PREVIOUS_CHECKPOINT_ARTIFACT
    previous_file = _resolve_repo_path(repo, previous_raw) if str(previous_raw or "").strip() else None
    previous_artifact, previous_error = _load_json_object(previous_file)

    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "source_texts": source_texts,
        "source_load_errors": source_load_errors,
        "demo_readiness_artifact": readiness_artifact,
        "demo_readiness_load_error": readiness_error,
        "previous_checkpoint_artifact": previous_artifact,
        "previous_checkpoint_load_error": previous_error,
        "readiness_artifact_path": _norm_path(readiness_file or readiness_raw or ""),
        "previous_checkpoint_path": _norm_path(previous_file or previous_raw or ""),
    }


def write_mirror_tunnel_live_ui_readiness_checkpoint(
    *,
    repo_path: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY,
    output_dir: str | Path | None = None,
    readiness_artifact_path: str | Path | None = None,
    previous_checkpoint_path: str | Path | None = None,
    report_id: str = "",
    created_at: str = "",
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gather inputs, build the checkpoint, and write JSON/Markdown artifacts."""
    repo = Path(repo_path or ".").expanduser().resolve()
    raw_inputs = inputs or gather_mirror_tunnel_live_ui_readiness_checkpoint_inputs(
        repo_path=repo,
        registry_path=registry_path,
        readiness_artifact_path=readiness_artifact_path,
        previous_checkpoint_path=previous_checkpoint_path,
    )
    report = build_mirror_tunnel_live_ui_readiness_checkpoint(
        registry_data=raw_inputs.get("registry_data"),
        registry_load_error=str(raw_inputs.get("registry_load_error") or ""),
        source_texts=raw_inputs.get("source_texts") or {},
        source_load_errors=raw_inputs.get("source_load_errors") or {},
        demo_readiness_artifact=raw_inputs.get("demo_readiness_artifact"),
        demo_readiness_load_error=str(raw_inputs.get("demo_readiness_load_error") or ""),
        previous_checkpoint_artifact=raw_inputs.get("previous_checkpoint_artifact"),
        previous_checkpoint_load_error=str(raw_inputs.get("previous_checkpoint_load_error") or ""),
        readiness_artifact_path=raw_inputs.get("readiness_artifact_path") or "",
        previous_checkpoint_path=raw_inputs.get("previous_checkpoint_path") or "",
        report_id=report_id,
        created_at=created_at,
        repo_path=str(repo),
        registry_path=registry_path,
    )
    out_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
    if not out_dir.is_absolute():
        out_dir = repo / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    report["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_mirror_tunnel_live_ui_readiness_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] != STATUS_BLOCKED,
        "checkpoint_status": report["checkpoint_status"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }


def render_mirror_tunnel_live_ui_readiness_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the checkpoint report as operator-readable Markdown."""
    lines: list[str] = [
        "# Mirror Tunnel Live UI Readiness Checkpoint",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Status:** `{_md(report.get('checkpoint_status') or '(none)')}`",
        f"- **Reason:** {_md(report.get('checkpoint_reason') or '(none)')}",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase') or RECOMMENDED_NEXT_PHASE)}`",
        "",
        "## Phase Completion",
        "",
        _phase_table(report.get("phase_completion")),
        "",
        "## Runtime Safety Checks",
        "",
        _check_section(report.get("runtime_safety_checks")),
        "",
        "## UI Safety Checks",
        "",
        _check_section(report.get("ui_safety_checks")),
        "",
        "## Loader Safety Checks",
        "",
        _check_section(report.get("loader_safety_checks")),
        "",
        "## Demo Readiness Evidence",
        "",
        _dict_block(report.get("demo_readiness_evidence")),
        "",
        "## Missing Evidence",
        "",
        _evidence_table(report.get("missing_evidence")),
        "",
        "## Warnings",
        "",
        _bullet_list(report.get("warnings")),
        "",
        "## Final Verdict",
        "",
        _dict_block(report.get("final_verdict")),
        "",
        "## Recommended Next Phase",
        "",
        f"- `{_md(report.get('recommended_next_phase') or RECOMMENDED_NEXT_PHASE)}`",
        f"- Alternative: {_md(report.get('alternative_next_branch') or ALTERNATIVE_NEXT_BRANCH)}",
        "",
        "## Boundaries / Guardrails",
        "",
        _bullet_list(report.get("boundaries")),
        "",
    ]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    if guardrails:
        for key in sorted(guardrails):
            lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
        lines.append("")
    return "\n".join(lines)


def _phase_completion(registry_data: Any, pick: dict[str, Any]) -> dict[str, Any]:
    phase_map = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    for phase_id in REQUIRED_MIRROR_LIVE_UI_PHASE_IDS:
        phase = phase_map.get(phase_id)
        present = phase is not None
        status = str(phase.get("status", "")) if present else "(missing)"
        complete = present and status == "complete"
        guardrail_violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            blockers.append(f"{phase_id} is missing from the phase registry")
        elif not complete:
            blockers.append(f"{phase_id} is not registered complete (status={status})")
        for violation in guardrail_violations:
            blockers.append(f"{phase_id} adds forbidden power: {violation}")
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": status,
                "complete": complete,
                "guardrails_ok": present and not guardrail_violations,
                "guardrail_violations": guardrail_violations,
            }
        )

    this_phase = phase_map.get(THIS_PHASE_ID)
    mirror13 = phase_map.get("MIRROR.13")
    return {
        "required_phase_ids": list(REQUIRED_MIRROR_LIVE_UI_PHASE_IDS),
        "phase_checks": checks,
        "all_required_complete": all(check["complete"] for check in checks),
        "all_required_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_registered": this_phase is not None,
        "this_phase_status": str(this_phase.get("status", "")) if this_phase else "(missing)",
        "mirror13_registered": mirror13 is not None,
        "mirror13_status": str(mirror13.get("status", "")) if mirror13 else "(missing)",
        "phase_picker_top_recommendation": pick.get("top_recommendation"),
        "blockers": blockers,
    }


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    return {
        str(phase["phase_id"]): phase
        for phase in phases
        if isinstance(phase, dict) and phase.get("phase_id")
    }


def _phase_guardrail_violations(phase: dict[str, Any] | None) -> list[str]:
    if not isinstance(phase, dict):
        return []
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    automation = str(phase.get("automation_level") or "")
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    return violations


def _runtime_safety_checks(source_texts: dict[str, str], source_errors: dict[str, str]) -> dict[str, Any]:
    mirror7 = source_texts.get("mirror7", "")
    mirror8 = source_texts.get("mirror8", "")
    mirror9 = source_texts.get("mirror9", "")
    mirror12 = source_texts.get("mirror12", "")
    checks = {
        "mirror7_source_loaded": not source_errors.get("mirror7") and bool(mirror7),
        "mirror7_default_off": "MIRROR_TUNNEL_SHADOW_TRACE_ENABLED" in mirror7 and _truthy_marker(mirror7, "default_off"),
        "mirror7_writes_live_trace_artifacts_only": "live_traces" in mirror7 and _truthy_marker(mirror7, "writes_trace_artifacts_only"),
        "mirror7_no_runtime_scoring": not _contains_any(mirror7, FORBIDDEN_RUNTIME_SCORING_MARKERS),
        "mirror8_source_loaded": not source_errors.get("mirror8") and bool(mirror8),
        "mirror8_post_run_only": "post-run" in mirror8.lower() and _truthy_marker(mirror8, "post_run_only"),
        "mirror8_writes_separate_preview_artifacts": "live_trace_scoring_preview" in mirror8 and _truthy_marker(mirror8, "writes_preview_artifacts_only"),
        "mirror8_does_not_mutate_live_trace": "does not mutate live trace" in mirror8.lower() or '"live_trace_mutated": False' in mirror8,
        "mirror9_report_only_planning": "report_only" in mirror9 and ("ui_implemented" in mirror9 or "does not implement UI" in mirror9),
        "mirror12_artifact_inspection_only": "artifact_inspection_only" in mirror12 or "artifact-inspection only" in mirror12,
        "mirror12_does_not_run_demo": not _contains_any(mirror12, ("run_agent_web(", "maybe_write_shadow_live_trace(", "write_shadow_live_trace(")),
    }
    blockers = _check_blockers(
        checks,
        {
            "mirror7_source_loaded": "MIRROR.7 source could not be loaded",
            "mirror7_default_off": "MIRROR.7 default-off guard is missing",
            "mirror7_writes_live_trace_artifacts_only": "MIRROR.7 live trace artifact-only guard is missing",
            "mirror7_no_runtime_scoring": "MIRROR.7 contains runtime scoring or scoring-builder markers",
            "mirror8_source_loaded": "MIRROR.8 source could not be loaded",
            "mirror8_post_run_only": "MIRROR.8 post-run-only guard is missing",
            "mirror8_writes_separate_preview_artifacts": "MIRROR.8 separate preview artifact guard is missing",
            "mirror8_does_not_mutate_live_trace": "MIRROR.8 live trace mutation guard is missing",
            "mirror9_report_only_planning": "MIRROR.9 report-only planning guard is missing",
            "mirror12_artifact_inspection_only": "MIRROR.12 artifact-inspection-only guard is missing",
            "mirror12_does_not_run_demo": "MIRROR.12 appears to run or start the demo automatically",
        },
    )
    return {"checks": checks, "blockers": blockers, "all_clear": not blockers}


def _ui_safety_checks(source_texts: dict[str, str], source_errors: dict[str, str]) -> dict[str, Any]:
    template = source_texts.get("template", "")
    panel = _mirror_panel_source(template)
    panel_lower = panel.lower()
    forbidden_labels = [label for label in FORBIDDEN_PANEL_LABELS if label.lower() in panel_lower]
    checks = {
        "template_source_loaded": not source_errors.get("template") and bool(template),
        "panel_present": 'id="mirrorTunnelPanel"' in template,
        "panel_marked_read_only": "data-mirror-readonly" in panel or "read-only" in template.lower(),
        "advisory_label_present": "advisory evidence, not an approval gate" in panel_lower,
        "no_apply_reject_approve_run_buttons": not forbidden_labels,
        "no_submit_apply_blocking": ".disabled" not in panel and "preventDefault" not in panel,
        "panel_stays_out_of_primary_submit_area": "mirrorTunnelPanel" not in _after_marker(template, 'id="primarySubmit"')[:500],
        "mirror_score_not_trust_decision": "approval gate" in panel_lower and "auto trust" not in panel_lower,
    }
    blockers = _check_blockers(
        checks,
        {
            "template_source_loaded": "MIRROR.10 UI template could not be loaded",
            "panel_present": "MIRROR.10 Mirror Tunnel panel is missing",
            "panel_marked_read_only": "MIRROR.10 panel is not marked read-only",
            "advisory_label_present": "MIRROR.10 advisory label is missing",
            "no_apply_reject_approve_run_buttons": "MIRROR.10 panel contains forbidden buttons: " + ", ".join(forbidden_labels),
            "no_submit_apply_blocking": "MIRROR.10 panel appears to block or disable Submit/Apply behavior",
            "panel_stays_out_of_primary_submit_area": "MIRROR.10 panel appears inside the primary submit area",
            "mirror_score_not_trust_decision": "MIRROR.10 panel does not preserve advisory-only trust boundary",
        },
    )
    return {
        "checks": checks,
        "forbidden_panel_labels": forbidden_labels,
        "blockers": blockers,
        "all_clear": not blockers,
    }


def _loader_safety_checks(source_texts: dict[str, str], source_errors: dict[str, str]) -> dict[str, Any]:
    route = source_texts.get("route", "")
    checks = {
        "route_source_loaded": not source_errors.get("route") and bool(route),
        "route_get_only": 'methods=["GET"]' in route or "methods=['GET']" in route,
        "route_uses_preview_id_path": "preview_id" in route and "live_trace_scoring_preview" in route or "_mirror_preview_artifact_path" in route,
        "route_reads_existing_artifact": ".read_text" in route or "json.loads" in route,
        "route_has_no_write_or_mutation_ops": not _contains_any(route, FORBIDDEN_LOADER_MUTATION_MARKERS),
        "route_does_not_generate_previews": not _contains_any(route, FORBIDDEN_LOADER_GENERATION_MARKERS),
        "route_does_not_call_runtime_scoring": not _contains_any(route, FORBIDDEN_RUNTIME_SCORING_MARKERS),
    }
    blockers = _check_blockers(
        checks,
        {
            "route_source_loaded": "MIRROR.11 loader route source could not be loaded",
            "route_get_only": "MIRROR.11 loader route is not GET-only",
            "route_uses_preview_id_path": "MIRROR.11 loader route does not use sanitized preview-id artifact loading",
            "route_reads_existing_artifact": "MIRROR.11 loader route does not read an existing artifact",
            "route_has_no_write_or_mutation_ops": "MIRROR.11 loader route contains mutating route behavior",
            "route_does_not_generate_previews": "MIRROR.11 loader route contains preview generation or scoring-builder calls",
            "route_does_not_call_runtime_scoring": "MIRROR.11 loader route contains runtime scoring markers",
        },
    )
    return {"checks": checks, "blockers": blockers, "all_clear": not blockers}


def _demo_readiness_evidence(artifact: Any, load_error: str, path: str | Path) -> dict[str, Any]:
    present = isinstance(artifact, dict) and bool(artifact)
    if not present:
        return {
            "present": False,
            "path": _norm_path(path),
            "load_error": str(load_error or ""),
            "report_kind": "",
            "status": "absent",
            "real_demo_chain_exists": False,
            "useful_frame_coverage": False,
            "trace_id": "",
            "preview_id": "",
            "warnings": [],
            "blockers": [],
            "missing_evidence": [
                {
                    "source": "MIRROR.12",
                    "reason": "missing_readiness_artifact",
                    "detail": "No MIRROR.12 readiness artifact was available for the checkpoint.",
                }
            ],
        }
    status = str(artifact.get("status") or "")
    summary = _dict(artifact.get("summary"))
    frame_coverage = _dict(artifact.get("frame_coverage"))
    guardrails = _dict(artifact.get("guardrails"))
    guardrail_breaches = [
        key for key, value in guardrails.items()
        if key in {
            "manual_demo_executed_by_checker",
            "mirror7_writer_called",
            "mirror8_preview_builder_called",
            "runtime_scoring_performed",
            "live_trace_mutated",
            "preview_generated",
        }
        and value is not False
    ]
    blockers = []
    if str(artifact.get("report_kind")) != "mirror_tunnel_live_demo_readiness":
        blockers.append("MIRROR.12 readiness artifact has the wrong report_kind")
    if status == "blocked":
        blockers.append("MIRROR.12 readiness artifact is blocked")
    for breach in guardrail_breaches:
        blockers.append(f"MIRROR.12 readiness artifact reports guardrail breach: {breach}")
    real_demo_chain_exists = (
        status in DEMO_READY_STATUSES
        and summary.get("preview_ready") is not False
        and summary.get("ui_loader_compatible") is not False
    )
    useful_coverage = bool(
        frame_coverage.get("has_useful_frame_coverage")
        or summary.get("live_trace_ready") is True
    )
    warnings: list[str] = []
    if status == "demo_ready_with_warnings":
        warnings.append("MIRROR.12 reports demo_ready_with_warnings")
    elif status and status not in DEMO_READY_STATUSES:
        warnings.append(f"MIRROR.12 reports {status}")
    if real_demo_chain_exists and not useful_coverage:
        warnings.append("real demo artifact chain exists, but frame coverage is weak")
    warnings.extend(str(item) for item in artifact.get("warnings", []) if isinstance(artifact.get("warnings"), list))
    return {
        "present": True,
        "path": _norm_path(path),
        "load_error": str(load_error or ""),
        "report_kind": str(artifact.get("report_kind") or ""),
        "status": status or "unknown",
        "real_demo_chain_exists": real_demo_chain_exists,
        "useful_frame_coverage": useful_coverage,
        "trace_id": str(artifact.get("trace_id") or ""),
        "preview_id": str(artifact.get("preview_id") or ""),
        "warnings": _dedupe_strings(warnings),
        "blockers": blockers,
        "missing_evidence": _list_of_dicts(artifact.get("missing_evidence")),
    }


def _previous_checkpoint_evidence(artifact: Any, load_error: str, path: str | Path) -> dict[str, Any]:
    present = isinstance(artifact, dict) and bool(artifact)
    return {
        "present": present,
        "path": _norm_path(path),
        "load_error": str(load_error or ""),
        "report_kind": str(artifact.get("report_kind") or "") if present else "",
        "status": str(artifact.get("checkpoint_status") or artifact.get("status") or "") if present else "absent",
        "optional": True,
    }


def _source_guardrail_checks(source_texts: dict[str, str], source_errors: dict[str, str]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    files_checked: list[str] = []
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    parse_errors: list[str] = []
    for key, text in source_texts.items():
        if source_errors.get(key) or not text:
            continue
        if key in {"template"}:
            continue
        files_checked.append(key)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            if key == "route":
                warnings.append("MIRROR.11 route slice could not be AST-parsed; token checks were still applied")
                continue
            parse_errors.append(f"{key}: source could not be parsed")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_AST_IMPORT_ROOTS:
                        forbidden_imports.append(f"{key}: {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in FORBIDDEN_AST_IMPORT_ROOTS:
                    forbidden_imports.append(f"{key}: {root}")
            elif isinstance(node, ast.Call):
                call_name = ""
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                if call_name in FORBIDDEN_AST_CALLS:
                    forbidden_calls.append(f"{key}: {call_name}")
    for item in forbidden_imports:
        blockers.append(f"source imports forbidden module: {item}")
    for item in forbidden_calls:
        blockers.append(f"source calls forbidden sink: {item}")
    for item in parse_errors:
        blockers.append(item)
    return {
        "files_checked": files_checked,
        "forbidden_imports": sorted(set(forbidden_imports)),
        "forbidden_calls": sorted(set(forbidden_calls)),
        "parse_errors": parse_errors,
        "warnings": warnings,
        "blockers": blockers,
        "all_clear": not blockers,
    }


def _missing_evidence(demo: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    demo_missing = [item for item in demo.get("missing_evidence") or [] if isinstance(item, dict)]
    if not demo.get("present") and not demo_missing:
        missing.append(
            {
                "source": "MIRROR.12",
                "reason": "missing_readiness_artifact",
                "detail": "No MIRROR.12 readiness artifact was available.",
            }
        )
    for item in demo_missing:
        missing.append(
            {
                "source": str(item.get("source") or "MIRROR.12"),
                "reason": str(item.get("reason") or item.get("evidence_status") or "missing"),
                "detail": str(item.get("detail") or item.get("frame_type") or ""),
            }
        )
    if previous.get("load_error"):
        missing.append(
            {
                "source": "MIRROR.CLOSE",
                "reason": "optional_previous_checkpoint_missing",
                "detail": "Previous MIRROR.CLOSE checkpoint artifact was not available.",
            }
        )
    return _dedupe_evidence(missing)


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "checkpoint_only": True,
        "model_call_performed": False,
        "patch_apply_performed": False,
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
        "runtime_scoring_performed": False,
        "live_trace_mutated": False,
        "preview_generated": False,
        "ui_behavior_changed": False,
        "execution_blocking_performed": False,
        "writes_checkpoint_artifacts_only": True,
    }


def _load_json_object(path: Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None:
        return None, "path was not provided"
    if not path.is_file():
        return None, f"{_norm_path(path)} not found"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def _load_text(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "", f"{_norm_path(path)} not found"
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", f"could not read {_norm_path(path)}: {exc}"


def _resolve_repo_path(repo: Path, raw: str | Path | None) -> Path | None:
    if raw is None or str(raw).strip() == "":
        return None
    path = Path(raw)
    return path.expanduser().resolve() if path.is_absolute() else (repo / path).resolve()


def _between_markers(text: str, start_marker: str, end_marker: str) -> str:
    if start_marker not in text or end_marker not in text:
        return text
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]


def _mirror_panel_source(template: str) -> str:
    marker = 'id="mirrorTunnelPanel"'
    if marker not in template:
        return ""
    start = template.index(marker)
    end_marker = "<!-- /mirror-tunnel-panel -->"
    if end_marker in template[start:]:
        end = template.index(end_marker, start) + len(end_marker)
    else:
        close = template.find("</section>", start)
        end = close + len("</section>") if close >= 0 else len(template)
    return template[start:end]


def _after_marker(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text[text.index(marker):]


def _check_blockers(checks: dict[str, bool], messages: dict[str, str]) -> list[str]:
    return [messages[key] for key, value in checks.items() if not value and key in messages]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _truthy_marker(text: str, key: str) -> bool:
    pattern = rf"['\"]{re.escape(key)}['\"]\s*:\s*True\b"
    return bool(re.search(pattern, text))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe_strings(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "")
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dedupe_evidence(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (str(item.get("source", "")), str(item.get("reason", "")), str(item.get("detail", "")))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _phase_table(value: Any) -> str:
    phase = value if isinstance(value, dict) else {}
    checks = phase.get("phase_checks") if isinstance(phase.get("phase_checks"), list) else []
    if not checks:
        return "_None._"
    lines = [
        "| Phase | Present | Status | Complete | Guardrails OK |",
        "| --- | --- | --- | --- | --- |",
    ]
    for check in checks:
        if not isinstance(check, dict):
            continue
        lines.append(
            f"| {_md(check.get('phase_id'))} | {_lower(check.get('present'))} | "
            f"{_md(check.get('status'))} | {_lower(check.get('complete'))} | "
            f"{_lower(check.get('guardrails_ok'))} |"
        )
    return "\n".join(lines)


def _check_section(value: Any) -> str:
    section = value if isinstance(value, dict) else {}
    checks = section.get("checks") if isinstance(section.get("checks"), dict) else {}
    lines = [f"- **All clear:** `{_lower(section.get('all_clear'))}`"]
    for key in sorted(checks):
        lines.append(f"- `{_md(key)}` = `{_lower(checks[key])}`")
    blockers = section.get("blockers") if isinstance(section.get("blockers"), list) else []
    if blockers:
        lines.append("")
        lines.append("**Blockers:**")
        lines.extend(f"- {_md(item)}" for item in blockers)
    return "\n".join(lines)


def _dict_block(value: Any) -> str:
    data = value if isinstance(value, dict) else {}
    if not data:
        return "_None._"
    lines: list[str] = []
    for key in sorted(data):
        item = data[key]
        if isinstance(item, (dict, list)):
            item = json.dumps(item, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(item)}")
    return "\n".join(lines)


def _evidence_table(value: Any) -> str:
    rows = value if isinstance(value, list) else []
    if not rows:
        return "_None._"
    lines = ["| Source | Reason | Detail |", "| --- | --- | --- |"]
    for row in rows:
        if isinstance(row, dict):
            lines.append(
                f"| {_md(row.get('source'))} | {_md(row.get('reason'))} | {_md(row.get('detail'))} |"
            )
    return "\n".join(lines)


def _bullet_list(value: Any) -> str:
    items = value if isinstance(value, list) else []
    if not items:
        return "_None._"
    return "\n".join(f"- {_md(item)}" for item in items)


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _lower(value: Any) -> str:
    return str(bool(value)).lower()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
