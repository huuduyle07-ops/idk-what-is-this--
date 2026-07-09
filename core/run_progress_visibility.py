"""UX.RUN.1 - Run Progress / Operator Visibility.

Defines a read-only progress-stage contract and writes operator-facing report
artifacts for long C.A.T.T.U.S runs. This module does not change run behavior,
launch workers, route models, enforce approval, apply patches, run validation,
run benchmarks, or alter execution logic.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "run_progress_visibility"
JSON_NAME = "run_progress_visibility_report.json"
MD_NAME = "run_progress_visibility_report.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ux" / "run_progress_visibility"

READY = "run_progress_visibility_ready"
READY_WITH_WARNINGS = "run_progress_visibility_ready_with_warnings"
INCOMPLETE = "run_progress_visibility_incomplete"
BLOCKED = "run_progress_visibility_blocked"

VISIBILITY_LEVELS: tuple[str, ...] = (
    "always_visible",
    "advanced_visible",
    "debug_visible",
    "hidden_until_available",
)

REQUIRED_STAGE_FIELDS: tuple[str, ...] = (
    "stage_id",
    "label",
    "description",
    "operator_meaning",
    "expected_source",
    "visibility_level",
    "is_runtime_authority",
    "may_block_action",
    "may_trigger_action",
    "safe_to_display",
    "notes",
)

REQUIRED_STAGE_IDS: tuple[str, ...] = (
    "request_received",
    "input_normalized",
    "goal_brief_checked",
    "mode_selected",
    "context_prepared",
    "prompt_built",
    "model_call_pending",
    "model_response_received",
    "patch_candidate_detected",
    "evidence_collected",
    "validation_not_run",
    "validation_reported",
    "benchmark_not_run",
    "benchmark_reported",
    "approval_boundary_checked",
    "final_response_ready",
    "error_reported",
)

SAFETY_CONTEXT_FALSE_FLAGS: tuple[str, ...] = (
    "runtime_execution_changed",
    "worker_launch_performed",
    "model_call_performed",
    "model_routing_changed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "approval_enforcement_changed",
    "errors_hidden",
    "progress_treated_as_success",
    "action_triggering_controls_added",
    "polling_route_added",
    "network_call_performed",
    "database_write_performed",
    "mcp_invocation_performed",
    "authority_escalation_performed",
    "token_issued_or_consumed",
)

_STAGE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "request_received": {
        "label": "Request received",
        "description": "The operator request is present in the run workspace.",
        "operator_meaning": "C.A.T.T.U.S has something to work on, but no result is implied.",
        "expected_source": "Existing request/session state",
    },
    "input_normalized": {
        "label": "Input normalized",
        "description": "The request has been shaped into the internal input format.",
        "operator_meaning": "The input is readable by the existing flow.",
        "expected_source": "Existing web/runner input preparation",
    },
    "goal_brief_checked": {
        "label": "Goal brief checked",
        "description": "Available goal-brief or 4W1H context has been considered.",
        "operator_meaning": "Structured intent may be available, but it is advisory only.",
        "expected_source": "Existing goal brief artifacts or in-page state",
    },
    "mode_selected": {
        "label": "Mode selected",
        "description": "The run mode has been selected by the existing UI or request.",
        "operator_meaning": "The selected mode is visible; this layer does not choose it.",
        "expected_source": "Existing mode selection state",
    },
    "context_prepared": {
        "label": "Context prepared",
        "description": "Context has been gathered by the existing execution flow.",
        "operator_meaning": "Context may be ready for prompt construction.",
        "expected_source": "Existing context/preflight state",
    },
    "prompt_built": {
        "label": "Prompt built",
        "description": "The prompt or work packet is available to the existing flow.",
        "operator_meaning": "Prompt preparation is visible, not authoritative.",
        "expected_source": "Existing prompt assembly state",
    },
    "model_call_pending": {
        "label": "Model call pending",
        "description": "The existing flow is at or near a model-call boundary.",
        "operator_meaning": "Waiting may be normal here; UX.RUN.1 does not call models.",
        "expected_source": "Existing runner status or future snapshot artifact",
    },
    "model_response_received": {
        "label": "Model response received",
        "description": "A response has been received by the existing flow.",
        "operator_meaning": "A response exists, but correctness and evidence are not implied.",
        "expected_source": "Existing response/session state",
    },
    "patch_candidate_detected": {
        "label": "Patch candidate detected",
        "description": "A candidate patch may be present for human review.",
        "operator_meaning": "A candidate is visible; it has not been approved or applied.",
        "expected_source": "Existing patch candidate state",
    },
    "evidence_collected": {
        "label": "Evidence collected",
        "description": "Existing evidence or references have been surfaced.",
        "operator_meaning": "Evidence is available for review, not automatically trusted.",
        "expected_source": "Existing evidence/report artifacts",
    },
    "validation_not_run": {
        "label": "Validation not run",
        "description": "No validation execution is represented for this run state.",
        "operator_meaning": "Validation was not run; this must never be read as passed.",
        "expected_source": "Missing validation artifact or explicit not-run marker",
    },
    "validation_reported": {
        "label": "Validation reported",
        "description": "A validation result was already reported by another boundary.",
        "operator_meaning": "Validation is reported; inspect the evidence before trusting it.",
        "expected_source": "Existing validation output or report artifact",
    },
    "benchmark_not_run": {
        "label": "Benchmark not run",
        "description": "No benchmark execution is represented for this run state.",
        "operator_meaning": "Benchmarks were not run; this must never be read as passed.",
        "expected_source": "Missing benchmark artifact or explicit not-run marker",
    },
    "benchmark_reported": {
        "label": "Benchmark reported",
        "description": "A benchmark result was already reported by another boundary.",
        "operator_meaning": "Benchmarks are reported; inspect the evidence before trusting them.",
        "expected_source": "Existing benchmark output or report artifact",
    },
    "approval_boundary_checked": {
        "label": "Approval boundary checked",
        "description": "The human-review boundary has been described for the operator.",
        "operator_meaning": "Approval remains human-owned; progress does not approve action.",
        "expected_source": "Existing approval/human-review metadata",
    },
    "final_response_ready": {
        "label": "Final response ready",
        "description": "The answer is ready for operator review in the existing UI.",
        "operator_meaning": "A final response is visible, not automatically accepted.",
        "expected_source": "Existing answer/session state",
    },
    "error_reported": {
        "label": "Error reported",
        "description": "An error is available and must be surfaced directly.",
        "operator_meaning": "Inspect the error; it must not be hidden behind a generic spinner.",
        "expected_source": "Existing error/session state",
    },
}

_STAGE_NOTES: dict[str, str] = {
    "validation_not_run": "Distinct from validation_reported; not-run is not success.",
    "validation_reported": "Reported validation is evidence to review, not a pass token.",
    "benchmark_not_run": "Distinct from benchmark_reported; not-run is not success.",
    "benchmark_reported": "Reported benchmark output is evidence to review, not a pass token.",
    "error_reported": "Errors must remain visible and specific.",
}

SAFETY_RULE_DETAILS: tuple[dict[str, str], ...] = (
    {
        "rule_id": "descriptive_only",
        "text": "Progress stages are descriptive only.",
    },
    {
        "rule_id": "does_not_imply_success",
        "text": "Progress visibility does not imply success.",
    },
    {
        "rule_id": "does_not_approve_patch_application",
        "text": "Progress visibility does not approve patch application.",
    },
    {
        "rule_id": "does_not_validate_evidence",
        "text": "Progress visibility does not validate evidence by itself.",
    },
    {
        "rule_id": "does_not_run_missing_validation",
        "text": "Progress visibility does not run missing validation.",
    },
    {
        "rule_id": "does_not_launch_workers",
        "text": "Progress visibility does not launch workers.",
    },
    {
        "rule_id": "does_not_call_models",
        "text": "Progress visibility does not call models.",
    },
    {
        "rule_id": "does_not_route_tasks",
        "text": "Progress visibility does not route tasks.",
    },
    {
        "rule_id": "does_not_enforce_approval",
        "text": "Progress visibility does not enforce approval signals.",
    },
    {
        "rule_id": "distinguishes_not_run_from_passed",
        "text": "Progress visibility must distinguish not run from passed.",
    },
    {
        "rule_id": "errors_are_visible",
        "text": "Errors must be visible, not hidden behind generic loading.",
    },
)

SAFETY_RULE_IDS: tuple[str, ...] = tuple(rule["rule_id"] for rule in SAFETY_RULE_DETAILS)
SAFETY_RULES: tuple[str, ...] = tuple(rule["text"] for rule in SAFETY_RULE_DETAILS)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.RUN.2",
    "title": "Run Progress Snapshot Loader",
    "reason": (
        "Add a GET-only/read-only loader for existing progress snapshot artifacts "
        "without creating live progress or changing execution behavior."
    ),
}

GUARDRAIL_NOTE = (
    "Run Progress / Operator Visibility is read-only: it defines and reports "
    "operator-visible progress stages. It does not change run behavior, launch "
    "workers, route models, enforce approval, apply patches, run validation, run "
    "benchmarks, does not call models, contact the network, write databases, or alter "
    "existing execution logic."
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _base_stage(stage_id: str) -> dict[str, Any]:
    text = _STAGE_DESCRIPTIONS[stage_id]
    return {
        "stage_id": stage_id,
        "label": text["label"],
        "description": text["description"],
        "operator_meaning": text["operator_meaning"],
        "expected_source": text["expected_source"],
        "visibility_level": "always_visible",
        "is_runtime_authority": False,
        "may_block_action": False,
        "may_trigger_action": False,
        "safe_to_display": True,
        "notes": _STAGE_NOTES.get(stage_id, "Read-only visibility stage."),
    }


def _default_stages() -> list[dict[str, Any]]:
    return [_base_stage(stage_id) for stage_id in REQUIRED_STAGE_IDS]


def _apply_stage_overrides(
    stages: list[dict[str, Any]],
    stage_overrides: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not stage_overrides:
        return stages
    updated: list[dict[str, Any]] = []
    for stage in stages:
        next_stage = dict(stage)
        override = stage_overrides.get(stage["stage_id"])
        if override:
            next_stage.update(override)
        updated.append(next_stage)
    known = {stage["stage_id"] for stage in updated}
    for stage_id, override in stage_overrides.items():
        if stage_id not in known:
            next_stage = {"stage_id": stage_id}
            next_stage.update(override)
            updated.append(next_stage)
    return updated


def _guardrails(safety_context: dict[str, Any] | None = None) -> dict[str, bool]:
    guardrails = {flag: False for flag in SAFETY_CONTEXT_FALSE_FLAGS}
    for key, value in (safety_context or {}).items():
        if key in guardrails:
            guardrails[key] = bool(value)
    return guardrails


def _add_unique(items: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in items):
        items.append({"reason": reason, "message": message})


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return BLOCKED
    if incomplete:
        return INCOMPLETE
    if warnings:
        return READY_WITH_WARNINGS
    return READY


def _evaluate_stage_contract(stages: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    blocked: list[dict[str, str]] = []
    incomplete: list[str] = []
    ids = [str(stage.get("stage_id", "")) for stage in stages]
    missing = [stage_id for stage_id in REQUIRED_STAGE_IDS if stage_id not in ids]
    if missing:
        incomplete.append("Missing progress stages: " + ", ".join(missing))

    for stage in stages:
        stage_id = str(stage.get("stage_id") or "(unknown)")
        missing_fields = [field for field in REQUIRED_STAGE_FIELDS if field not in stage]
        if missing_fields:
            incomplete.append(f"Stage {stage_id} missing fields: " + ", ".join(missing_fields))
        if stage.get("visibility_level") not in VISIBILITY_LEVELS:
            incomplete.append(f"Stage {stage_id} has invalid visibility_level")
        if stage.get("is_runtime_authority") is True:
            _add_unique(
                blocked,
                f"stage:{stage_id}:is_runtime_authority",
                f"Stage {stage_id} must not be runtime authority.",
            )
        if stage.get("may_block_action") is True:
            _add_unique(
                blocked,
                f"stage:{stage_id}:may_block_action",
                f"Stage {stage_id} must not block operator action by itself.",
            )
        if stage.get("may_trigger_action") is True:
            _add_unique(
                blocked,
                f"stage:{stage_id}:may_trigger_action",
                f"Stage {stage_id} must not trigger actions.",
            )
        if stage.get("safe_to_display") is False and stage.get("visibility_level") not in {
            "debug_visible",
            "hidden_until_available",
        }:
            incomplete.append(f"Stage {stage_id} is neither safe to display nor explicitly limited")
    return blocked, incomplete


def build_run_progress_visibility_report(
    *,
    report_id: str = "ux-run-1",
    created_at: str = "",
    stage_contract: list[dict[str, Any]] | None = None,
    stage_overrides: dict[str, dict[str, Any]] | None = None,
    safety_context: dict[str, Any] | None = None,
    live_stream_implemented: bool = False,
) -> dict[str, Any]:
    """Build the UX.RUN.1 visibility report without reading or running anything."""
    stages = copy.deepcopy(stage_contract) if stage_contract is not None else _default_stages()
    stages = _apply_stage_overrides(stages, stage_overrides)
    guardrails = _guardrails(safety_context)
    blocked, incomplete = _evaluate_stage_contract(stages)

    for flag, value in guardrails.items():
        if value:
            _add_unique(
                blocked,
                f"guardrail:{flag}",
                f"Forbidden runtime power was reported: {flag}.",
            )

    warnings: list[str] = []
    if not live_stream_implemented:
        warnings.append(
            "No live progress stream is implemented yet; UX.RUN.1 defines the "
            "contract and safe display boundary only."
        )

    status = _status(blocked, incomplete, warnings)
    return {
        "report_kind": REPORT_KIND,
        "report_id": str(report_id),
        "created_at": str(created_at),
        "status": status,
        "guardrail_note": GUARDRAIL_NOTE,
        "stage_contract": stages,
        "safety_rule_details": copy.deepcopy(list(SAFETY_RULE_DETAILS)),
        "safety_rules": list(SAFETY_RULES),
        "progress_semantics": {
            "progress_is_descriptive_only": True,
            "progress_implies_success": bool(guardrails["progress_treated_as_success"]),
            "progress_approves_patch_application": False,
            "progress_validates_evidence": False,
        },
        "error_visibility": {
            "errors_must_be_visible": True,
            "generic_loading_must_not_hide_errors": True,
            "error_stage_id": "error_reported",
        },
        "ui_stub_plan": {
            "status": "planned_stub_only",
            "placement": "Near the Workbench/Evidence area.",
            "empty_state": (
                "No live progress stream yet. Future runs may surface read-only "
                "progress stages here."
            ),
            "placeholder_stage_chips": list(REQUIRED_STAGE_IDS),
            "fetch_live_data": False,
            "action_controls": False,
            "replaces_answer_patch_or_evidence": False,
        },
        "live_stream": {
            "implemented": bool(live_stream_implemented),
            "polling_route_added": bool(guardrails["polling_route_added"]),
            "future_phase": "UX.RUN.2",
        },
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "guardrails": guardrails,
        "status_logic": {
            "ready": "Contract, artifacts, and safe display boundary exist with no blockers.",
            "ready_with_warnings": "Safe report/UI boundary exists but no live stream exists yet.",
            "incomplete": "Stages, safety rules, or output artifact contract are missing.",
            "blocked": "Runtime behavior, authority, action triggers, or hidden errors are present.",
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def render_run_progress_visibility_markdown(report: dict[str, Any]) -> str:
    """Render the visibility report as operator-readable Markdown."""
    lines: list[str] = [
        "# Run Progress / Operator Visibility",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id', ''))}`",
        f"- **Created at:** `{_md(report.get('created_at', ''))}`",
        f"- **Status:** `{_md(report.get('status', ''))}`",
        f"- **Stage count:** {len(report.get('stage_contract') or [])}",
        f"- **Live stream implemented:** `{str(bool((report.get('live_stream') or {}).get('implemented'))).lower()}`",
        "",
        "## Stage Contract",
        "",
        "| Stage | Label | Visibility | Runtime authority | Triggers action | Operator meaning |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for stage in report.get("stage_contract") or []:
        lines.append(
            "| {stage} | {label} | {visibility} | {authority} | {trigger} | {meaning} |".format(
                stage=_md(stage.get("stage_id", "")),
                label=_md(stage.get("label", "")),
                visibility=_md(stage.get("visibility_level", "")),
                authority=str(bool(stage.get("is_runtime_authority"))).lower(),
                trigger=str(bool(stage.get("may_trigger_action"))).lower(),
                meaning=_md(stage.get("operator_meaning", "")),
            )
        )

    lines.extend(["", "## Safety Rules", ""])
    for rule in report.get("safety_rule_details") or []:
        lines.append(f"- `{_md(rule.get('rule_id', ''))}`: {_md(rule.get('text', ''))}")

    lines.extend(["", "## UI Stub Plan", ""])
    stub = report.get("ui_stub_plan") or {}
    for key in sorted(stub):
        value = stub[key]
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append(f"- `{_md(key)}`: {_md(value)}")

    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    lines.extend([f"- {_md(warning)}" for warning in warnings] if warnings else ["_None._"])

    lines.extend(["", "## Blocked Reasons", ""])
    blocked = report.get("blocked_reasons") or []
    if blocked:
        for reason in blocked:
            lines.append(f"- `{_md(reason.get('reason', ''))}`: {_md(reason.get('message', ''))}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Boundaries", ""])
    for text in (
        "UX.RUN.1 does not change run behavior.",
        "UX.RUN.1 does not call models or route models.",
        "UX.RUN.1 does not launch workers.",
        "UX.RUN.1 does not apply patches.",
        "UX.RUN.1 does not run validation.",
        "UX.RUN.1 does not run benchmarks.",
        "UX.RUN.1 does not enforce approval.",
        "UX.RUN.1 does not add action-triggering controls.",
    ):
        lines.append(f"- {text}")

    next_phase = report.get("recommended_next_phase") or {}
    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_run_progress_visibility_report(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "ux-run-1",
    created_at: str = "",
    stage_contract: list[dict[str, Any]] | None = None,
    stage_overrides: dict[str, dict[str, Any]] | None = None,
    safety_context: dict[str, Any] | None = None,
    live_stream_implemented: bool = False,
) -> dict[str, Any]:
    """Write UX.RUN.1 JSON and Markdown report artifacts."""
    report = build_run_progress_visibility_report(
        report_id=report_id,
        created_at=created_at,
        stage_contract=stage_contract,
        stage_overrides=stage_overrides,
        safety_context=safety_context,
        live_stream_implemented=live_stream_implemented,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_run_progress_visibility_markdown(report), encoding="utf-8")
    return {
        "ok": report["status"] in {READY, READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
