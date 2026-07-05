"""EVAL.N4 - Evidence Quality Artifact Loader Plan (report-only).

Plans how C.A.T.T.U.S should later load and display existing EVAL.N3 evidence
quality report artifacts. EVAL.N4 never implements a UI panel, backend route,
runtime loader, validation run, benchmark run, model call, patch application,
scoring gate, approval gate, automatic decision, or report mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "evidence_quality_artifact_loader_plan"
JSON_NAME = "evidence_quality_artifact_loader_plan.json"
MD_NAME = "evidence_quality_artifact_loader_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_artifact_loader_plan"

PLAN_STATUSES: tuple[str, ...] = (
    "evidence_quality_artifact_loader_plan_ready",
    "evidence_quality_artifact_loader_plan_ready_with_warnings",
    "evidence_quality_artifact_loader_plan_incomplete",
    "evidence_quality_artifact_loader_plan_blocked",
)

VISIBLE_FIELDS: tuple[str, ...] = (
    "evidence_quality_status",
    "overall_evidence_quality",
    "claim_count",
    "missing_evidence_count",
    "contradiction_risk_count",
    "confidence_alignment_warnings",
    "validation_evidence_status",
    "benchmark_evidence_status",
    "freshness_status",
    "recommended_human_checks",
    "advisory_note",
)

COLLAPSED_DEBUG_FIELDS: tuple[str, ...] = (
    "artifact_inventory",
    "claim_inventory",
    "evidence_inventory",
    "dimension_reviews",
    "missing_evidence",
    "contradiction_risks",
    "freshness_findings",
    "confidence_alignment_findings",
    "scope_alignment_findings",
    "raw_json",
)

EMPTY_ERROR_STATES: tuple[str, ...] = (
    "no_report_selected",
    "report_not_found",
    "malformed_report",
    "blocked_unsafe_report_id",
    "report_incomplete",
    "report_blocked",
    "report_ready_with_warnings",
    "report_ready",
)

WARNING_LANGUAGE: tuple[str, ...] = (
    "Evidence Quality is advisory evidence, not an approval gate.",
    "A strong evidence report does not automatically approve a patch.",
    "A weak evidence report means review the missing evidence, not automatically reject.",
    "Validation and benchmark results are only trusted when matching artifacts exist.",
    "Human approval is still required before patch apply.",
)

FORBIDDEN_LOADER_BEHAVIOR: tuple[str, ...] = (
    "no Approve button",
    "no Reject button",
    "no Apply button inside Evidence Quality panel",
    "no Run Validation button",
    "no Run Benchmark button",
    "no Score Now button",
    "no model-call button",
    "no auto-refresh during active run",
    "no disabling Apply based on evidence quality",
    "no changing routing/mode based on evidence quality",
    "no generating a new EVAL.N3 report from the loader",
    "no mutating evidence reports",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "ui_panel_added",
    "backend_route_added",
    "runtime_artifact_loader_added",
    "model_call_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "route_behavior_changed",
    "auth_policy_changed",
    "scoring_gate_changed",
    "approval_or_rejection_performed",
    "evidence_report_mutated",
)

EVIDENCE_QUALITY_ARTIFACT_LOADER_PLAN_GUARDRAIL_NOTE = (
    "Evidence Quality Artifact Loader Plan is report-only and planning-only: it "
    "defines how a future read-only surface may display existing EVAL.N3 evidence "
    "quality report artifacts. It does not add UI, routes, runtime loading, "
    "validation, benchmarks, model calls, patch application, scoring gates, "
    "approval/rejection logic, or automatic decisions."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.N5",
    "title": "Evidence Quality Read-only UI Stub",
    "reason": (
        "Like MIRROR.10, build the inert visual surface first before adding a "
        "GET-only artifact loader."
    ),
}


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _allowed_artifact_source() -> dict[str, Any]:
    return {
        "allowed_root": ".agent/eval/evidence_quality_report/",
        "default_latest_report_path": ".agent/eval/evidence_quality_report/evidence_quality_report.json",
        "report_id_report_path": ".agent/eval/evidence_quality_report/<report_id>/evidence_quality_report.json",
        "optional_report_id_later": True,
        "no_arbitrary_path_input": True,
        "path_traversal_blocked": True,
        "report_id_policy": (
            "Future loaders may accept a sanitized report_id only; they must not "
            "accept arbitrary file paths or read outside the allowed root."
        ),
    }


def _future_route_contract() -> dict[str, Any]:
    return {
        "preferred_routes": [
            "GET /eval/evidence-quality/report/<report_id>",
            "GET /api/eval/evidence-quality/report/<report_id>",
        ],
        "allowed_methods": ["GET"],
        "forbidden_methods": ["POST", "PUT", "PATCH", "DELETE"],
        "read_only": True,
        "no_arbitrary_file_path_input": True,
        "report_id_sanitized": True,
        "path_traversal_blocked": True,
        "allowed_read_root": ".agent/eval/evidence_quality_report/",
        "no_validation_execution": True,
        "no_benchmark_execution": True,
        "no_model_call": True,
        "no_patch_apply": True,
        "no_approval_or_rejection": True,
    }


def _future_ui_placement() -> dict[str, Any]:
    return {
        "allowed_placements": [
            "Evidence / Review area",
            "Advanced / Debug drawer",
        ],
        "preferred_first_placement": "Advanced / Debug drawer",
        "forbidden_placements": [
            "beside Apply Patch",
            "beside primary Submit",
            "inside run confirmation path",
            "blocking status gate",
        ],
        "placement_note": (
            "Surface the report where an operator reviews evidence, not where "
            "they confirm execution or mutation."
        ),
    }


def _non_blocking_policy() -> dict[str, bool]:
    return {
        "advisory_only": True,
        "blocks_apply": False,
        "blocks_submit": False,
        "approves_patches": False,
        "rejects_patches": False,
        "changes_routing_or_mode": False,
        "changes_scoring_gates": False,
        "auto_decides_next_action": False,
    }


def _human_review_boundary() -> dict[str, Any]:
    return {
        "human_approval_required_before_patch_apply": True,
        "report_can_replace_human_review": False,
        "manual_review_required": [
            "Review missing evidence before trusting completion claims.",
            "Review contradiction risks before deciding whether a patch is ready.",
            "Review validation and benchmark evidence only when matching artifacts exist.",
            "Review production readiness, policy judgment, and risk acceptance manually.",
            "Keep patch apply and final approval as explicit human decisions.",
        ],
    }


def build_evidence_quality_artifact_loader_plan() -> dict[str, Any]:
    """Build the deterministic EVAL.N4 artifact loader plan."""
    return {
        "report_kind": REPORT_KIND,
        "plan_id": "evidence-quality-artifact-loader-plan",
        "plan_status": "evidence_quality_artifact_loader_plan_ready",
        "guardrail_note": EVIDENCE_QUALITY_ARTIFACT_LOADER_PLAN_GUARDRAIL_NOTE,
        "loader_purpose": (
            "Plan how C.A.T.T.U.S should safely load and display existing EVAL.N3 "
            "evidence quality reports as advisory evidence without turning them "
            "into an approval gate, scoring gate, or automatic decision."
        ),
        "allowed_artifact_source": _allowed_artifact_source(),
        "future_route_contract": _future_route_contract(),
        "future_ui_placement": _future_ui_placement(),
        "visible_fields": list(VISIBLE_FIELDS),
        "collapsed_debug_fields": list(COLLAPSED_DEBUG_FIELDS),
        "empty_error_states": list(EMPTY_ERROR_STATES),
        "warning_language": list(WARNING_LANGUAGE),
        "non_blocking_policy": _non_blocking_policy(),
        "forbidden_loader_behavior": list(FORBIDDEN_LOADER_BEHAVIOR),
        "human_review_boundary": _human_review_boundary(),
        "guardrails": _guardrails(),
        "plan_statuses": list(PLAN_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": {
            "phase_id": "EVAL.N5",
            "title": "Evidence Quality GET-only Loader",
            "reason": "Add the read-only backend route before a UI only if the UI stub is deferred.",
        },
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def _render_mapping(lines: list[str], values: dict[str, Any]) -> None:
    if values:
        for key in sorted(values):
            value = values[key]
            if isinstance(value, list):
                rendered = ", ".join(_md(item) for item in value)
            else:
                rendered = _md(value)
            lines.append(f"- `{_md(key)}`: {rendered}")
    else:
        lines.append("_None._")
    lines.append("")


def render_evidence_quality_artifact_loader_plan_markdown(report: dict[str, Any]) -> str:
    """Render an EVAL.N4 artifact loader plan as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Evidence Quality Artifact Loader Plan",
        "",
        f"> {report.get('guardrail_note', EVIDENCE_QUALITY_ARTIFACT_LOADER_PLAN_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.N4 plans a future display layer and adds no UI, route, runtime loader, validation, benchmark, model, patch, scoring, approval, or rejection behavior._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Plan id:** `{_md(report.get('plan_id', ''))}`",
        f"- **Plan status:** `{_md(report.get('plan_status', ''))}`",
        f"- **Visible field count:** {len(report.get('visible_fields') or [])}",
        f"- **Debug field count:** {len(report.get('collapsed_debug_fields') or [])}",
        f"- **Forbidden behavior count:** {len(report.get('forbidden_loader_behavior') or [])}",
        f"- **Recommended next phase:** `{_md(next_phase.get('phase_id', ''))}`",
        "",
        "## Loader Purpose",
        "",
        _md(report.get("loader_purpose", "")),
        "",
        "## Allowed Artifact Source",
        "",
    ]
    source = report.get("allowed_artifact_source") if isinstance(report.get("allowed_artifact_source"), dict) else {}
    _render_mapping(lines, source)

    lines += ["## Future Route Contract", ""]
    route = report.get("future_route_contract") if isinstance(report.get("future_route_contract"), dict) else {}
    _render_mapping(lines, route)

    lines += ["## Future UI Placement", ""]
    placement = report.get("future_ui_placement") if isinstance(report.get("future_ui_placement"), dict) else {}
    _render_mapping(lines, placement)

    for title, key in (
        ("Visible Fields", "visible_fields"),
        ("Collapsed Debug Fields", "collapsed_debug_fields"),
        ("Empty and Error States", "empty_error_states"),
        ("Warning Language", "warning_language"),
    ):
        lines += [f"## {title}", ""]
        _render_list(lines, list(report.get(key) or []), code=(title.endswith("Fields") or title.endswith("States")))

    lines += ["## Non-blocking Policy", ""]
    policy = report.get("non_blocking_policy") if isinstance(report.get("non_blocking_policy"), dict) else {}
    _render_mapping(lines, policy)

    lines += ["## Forbidden Loader Behavior", ""]
    _render_list(lines, list(report.get("forbidden_loader_behavior") or []))

    lines += ["## Human Review Boundary", ""]
    boundary = report.get("human_review_boundary") if isinstance(report.get("human_review_boundary"), dict) else {}
    _render_mapping(lines, boundary)

    lines += ["## Guardrails", ""]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines.append("")

    lines += [
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_evidence_quality_artifact_loader_plan(
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Build and write EVAL.N4 JSON + Markdown plan artifacts."""
    report = build_evidence_quality_artifact_loader_plan()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_evidence_quality_artifact_loader_plan_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
