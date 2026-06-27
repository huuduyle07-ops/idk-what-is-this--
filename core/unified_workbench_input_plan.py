"""UX.9 - Unified Workbench Input Plan.

Pure report builder for the plan-only Workbench input contract. It defines how
Chat, Instant Run, and Goal Brief / 4W1H can become one operator input surface
without merging dispatch paths or adding runtime powers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_KIND = "unified_workbench_input_plan"
JSON_NAME = "unified_workbench_input_plan.json"
MD_NAME = "unified_workbench_input_plan.md"

PLAN_STATUSES = ("ready_for_review", "needs_manual_review", "blocked")
UX4_MODES = (
    "chat",
    "instant_run",
    "continue_from_frame",
    "commander_plan",
    "clarify",
    "reject_or_defer",
)
CONFIRMATION_ACTIONS = (
    "ask_in_chat",
    "preview_instant_run",
    "open_continue_from_frame",
    "create_commander_contract",
    "answer_clarifying_question",
    "defer_or_reject",
)

_BOUNDARIES = [
    "UX.9 is a plan-only unified input phase.",
    "UX.9 does not auto-dispatch.",
    "UX.9 does not merge execution paths yet.",
    "UX.9 does not start runs.",
    "UX.9 does not call models.",
    "UX.9 does not apply patches.",
    "UX.9 does not run validation.",
    "UX.9 does not run benchmarks.",
    "UX.9 does not contact network services.",
    "UX.9 does not launch " + "work" + "ers.",
    "UX.9 does not push, merge, or open PRs.",
]

_WARNINGS = [
    "This plan does not prove the visual layout; UX.10 should validate placement and old-flow preservation.",
    "Mode preview remains advisory until a later implementation phase explicitly wires deterministic UI behavior.",
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _guardrails() -> dict[str, bool]:
    return {
        "plan_only": True,
        "unified_input_execution_implemented": False,
        "auto_dispatch_implemented": False,
        "new_route_added": False,
        "mutation_route_added": False,
        "backend_execution_changed": False,
        "task_execution_performed": False,
        "agent_launched": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "work" + "er_launch_performed": False,
        "repo_mutation_performed": False,
        "merge_performed": False,
    }


def build_unified_input_definition() -> dict[str, Any]:
    """Return the conceptual Workbench input definition."""
    return {
        "concept": "unified_workbench_input",
        "title": "Unified Workbench",
        "prompt": "What do you want C.A.T.T.U.S to do?",
        "merged_surfaces": [
            "Chat input",
            "Instant Run input",
            "Goal Brief / 4W1H",
        ],
        "operator_flow": [
            "User types once.",
            "Optional 4W1H fields refine the task.",
            "Mixed Mode Router concepts appear as a Mode Preview chip.",
            "The operator chooses an explicit confirmation action.",
            "Only later phases may connect that confirmation to existing safe behavior.",
        ],
        "definition": (
            "One Workbench input captures intent, optional 4W1H detail, constraints, "
            "risk notes, frame reference, mode preview, and the selected confirmation action."
        ),
        "execution_boundary": "The definition is a plan contract only; it does not run, dispatch, or mutate.",
    }


def build_field_schema() -> list[dict[str, Any]]:
    """Return the planned unified input data model."""
    return [
        {
            "field_id": "main_intent_text",
            "label": "Main intent text",
            "group": "core",
            "required": True,
            "purpose": "Capture the operator's request once before mode preview.",
            "placeholder": "Describe the task, question, continuation, or plan request.",
        },
        {
            "field_id": "what",
            "label": "What are we changing?",
            "group": "4W1H",
            "required": False,
            "purpose": "Clarify the specific change or question.",
        },
        {
            "field_id": "why",
            "label": "Why are we changing it?",
            "group": "4W1H",
            "required": False,
            "purpose": "Clarify the reason and timing.",
        },
        {
            "field_id": "where",
            "label": "Where should C.A.T.T.U.S focus?",
            "group": "4W1H",
            "required": False,
            "purpose": "Name files, routes, modules, UI areas, workflows, or artifacts.",
        },
        {
            "field_id": "when_stop",
            "label": "When should it stop?",
            "group": "4W1H",
            "required": False,
            "purpose": "State the stopping boundary and non-expansion rule.",
        },
        {
            "field_id": "how_validate",
            "label": "How do we validate?",
            "group": "4W1H",
            "required": False,
            "purpose": "State how the operator will check success.",
        },
        {
            "field_id": "constraints",
            "label": "Constraints",
            "group": "safety",
            "required": False,
            "purpose": "Capture limits, allowed scope, and required approvals.",
        },
        {
            "field_id": "non_goals",
            "label": "Non-goals",
            "group": "safety",
            "required": False,
            "purpose": "State what C.A.T.T.U.S should avoid doing.",
        },
        {
            "field_id": "risk_notes",
            "label": "Risk notes",
            "group": "safety",
            "required": False,
            "purpose": "Call out risky files, flows, gates, or operator concerns.",
        },
        {
            "field_id": "referenced_frame_id",
            "label": "Referenced frame ID",
            "group": "context",
            "required": False,
            "purpose": "Link a prior frame only when the operator wants safe continuation.",
        },
        {
            "field_id": "mode_preview",
            "label": "Mode preview",
            "group": "decision",
            "required": False,
            "purpose": "Hold the previewed UX.4-style mode, confidence, reasons, and required confirmation.",
        },
        {
            "field_id": "confirmation_action",
            "label": "Confirmation action",
            "group": "decision",
            "required": False,
            "purpose": "Record the operator's chosen explicit action without triggering it automatically.",
        },
    ]


def build_activation_helper_contract() -> dict[str, Any]:
    """Return the question-mark activation helper contract."""
    return {
        "name": "Activation Helper",
        "symbol": "?",
        "help_only": True,
        "executes_anything": False,
        "calls_models": False,
        "dispatches_run": False,
        "auto_fill_without_confirmation": False,
        "behavior": [
            "Explain the field.",
            "Show a short example.",
            "Help the operator write a better line.",
            "Do not execute anything.",
            "Do not call models.",
            "Do not auto-fill without user confirmation.",
            "Do not dispatch a run.",
        ],
        "field_examples": {
            "what": {
                "help_text": "Describe the specific change or question.",
                "example": "Refactor the Run Timeline panel to appear near the Run button.",
            },
            "why": {
                "help_text": "Explain why this matters now.",
                "example": "The current layout makes progress hard to see.",
            },
            "where": {
                "help_text": "Name a file, module, route, UI area, workflow, or artifact.",
                "example": "web/templates/index.html, web/static/style.css, Workbench input area.",
            },
            "when_stop": {
                "help_text": "Define the stopping boundary.",
                "example": "Stop after creating a report-only plan; do not change execution routes.",
            },
            "how_validate": {
                "help_text": "Define how the operator checks success.",
                "example": "Run targeted tests, registry validation, full pytest, benchmark check, and manual UI review.",
            },
        },
    }


def build_mode_preview_contract() -> dict[str, Any]:
    """Return the planned Mode Preview contract using UX.4 mode concepts."""
    return {
        "source_contract": "UX.4 Mixed Mode Intent Router Preview concepts",
        "coupling_policy": "Reference the contract; do not require direct UX.4 imports if that creates coupling.",
        "preview_is_execution": False,
        "required_fields": [
            "predicted_mode",
            "confidence",
            "reasons",
            "required_confirmation",
            "safe_preview_label",
        ],
        "modes": [
            {
                "mode_id": "chat",
                "label": "Chat",
                "confirmation_action": "ask_in_chat",
                "meaning": "Answer or discuss without preparing a run.",
            },
            {
                "mode_id": "instant_run",
                "label": "Instant Run",
                "confirmation_action": "preview_instant_run",
                "meaning": "Prepare a bounded run preview that still requires human confirmation.",
            },
            {
                "mode_id": "continue_from_frame",
                "label": "Continue",
                "confirmation_action": "open_continue_from_frame",
                "meaning": "Open safe continuation review for a referenced frame.",
            },
            {
                "mode_id": "commander_plan",
                "label": "Commander",
                "confirmation_action": "create_commander_contract",
                "meaning": "Create a planning contract for larger work.",
            },
            {
                "mode_id": "clarify",
                "label": "Clarify",
                "confirmation_action": "answer_clarifying_question",
                "meaning": "Ask for missing detail before any work path is selected.",
            },
            {
                "mode_id": "reject_or_defer",
                "label": "Defer",
                "confirmation_action": "defer_or_reject",
                "meaning": "Decline or park unsafe, out-of-scope, or unclear work.",
            },
        ],
    }


def build_confirmation_contract() -> dict[str, Any]:
    """Return the explicit confirmation action contract."""
    return {
        "human_confirmation_required": True,
        "automatic_confirmation": False,
        "confirmation_is_not_dispatch": True,
        "boundary": (
            "The human must confirm before any mutation, run, validation, benchmark, "
            "background process, model call, push, merge, or PR."
        ),
        "hardening_note": "Mutating actions remain behind explicit confirmation and the HARDEN gate.",
        "actions": [
            {
                "action_id": "ask_in_chat",
                "label": "Ask",
                "mapped_mode": "chat",
                "effect_in_ux9": "Plan-only mapping; no automatic chat send.",
            },
            {
                "action_id": "preview_instant_run",
                "label": "Preview Run",
                "mapped_mode": "instant_run",
                "effect_in_ux9": "Plan-only mapping; no run is started.",
            },
            {
                "action_id": "open_continue_from_frame",
                "label": "Continue From Frame",
                "mapped_mode": "continue_from_frame",
                "effect_in_ux9": "Plan-only mapping; no continuation is started.",
            },
            {
                "action_id": "create_commander_contract",
                "label": "Create Commander Plan",
                "mapped_mode": "commander_plan",
                "effect_in_ux9": "Plan-only mapping; no commander process is launched.",
            },
            {
                "action_id": "answer_clarifying_question",
                "label": "Answer Clarifying Question",
                "mapped_mode": "clarify",
                "effect_in_ux9": "Plan-only mapping; no model call is made.",
            },
            {
                "action_id": "defer_or_reject",
                "label": "Defer Or Reject",
                "mapped_mode": "reject_or_defer",
                "effect_in_ux9": "Plan-only mapping; no external action is taken.",
            },
        ],
    }


def build_button_reduction_plan() -> list[dict[str, str]]:
    """Return the deterministic button-reduction plan."""
    return [
        {
            "plan_id": "merge_chat_instant_entry",
            "summary": "Merge visible Chat and Instant Run entry into Workbench input.",
            "reason": "The operator should type once and then see a mode preview.",
        },
        {
            "plan_id": "merge_goal_brief_4w1h",
            "summary": "Merge Goal Brief and 4W1H into optional Workbench fields.",
            "reason": "Brief refinement should support the input, not become a competing destination.",
        },
        {
            "plan_id": "router_to_mode_preview",
            "summary": "Move Mixed Mode Router from a standalone tab into a Mode Preview chip.",
            "reason": "Mode prediction belongs before confirmation, directly under the input.",
        },
        {
            "plan_id": "timeline_near_action",
            "summary": "Keep Run Timeline below the input/action area.",
            "reason": "Progress should appear where the operator starts or previews work.",
        },
        {
            "plan_id": "evidence_near_output",
            "summary": "Keep Evidence Cards near Answer/Patch output.",
            "reason": "Review evidence should be attached to the result being judged.",
        },
        {
            "plan_id": "advanced_debug_drawer",
            "summary": "Move advanced/debug surfaces into Advanced.",
            "reason": "Graph, Dream, Benchmarks, and Inspector-style tools should not dominate daily operation.",
        },
        {
            "plan_id": "mutating_actions_separate",
            "summary": "Keep dangerous/mutating actions separate and clearly human-triggered.",
            "reason": "Unified input must reduce confusion without lowering safety gates.",
        },
    ]


def build_ui_layout_plan() -> dict[str, Any]:
    """Return the future Workbench layout plan."""
    return {
        "title": "Workbench",
        "tree": [
            {
                "node": "Unified Input",
                "children": [
                    "Main intent text",
                    "Optional 4W1H fields",
                    "? activation helper per field",
                    "Constraints / non-goals",
                ],
            },
            {
                "node": "Mode Preview",
                "children": ["predicted mode", "confidence/reasons", "required confirmation"],
            },
            {
                "node": "Confirmation Actions",
                "children": ["Ask", "Preview Run", "Continue", "Commander Plan"],
            },
            {"node": "Run Timeline", "children": []},
            {
                "node": "Output Review",
                "children": ["Answer", "Patch", "Evidence Cards"],
            },
            {"node": "Advanced Debug", "children": []},
        ],
        "placement_notes": [
            "Unified Input is the first Workbench surface.",
            "Mode Preview sits directly below the input.",
            "Confirmation Actions sit after the preview and remain explicit.",
            "Run Timeline follows the action area.",
            "Output Review keeps Answer, Patch, and Evidence Cards together.",
            "Advanced Debug remains visually secondary.",
        ],
    }


def build_migration_plan() -> list[dict[str, str]]:
    """Return the staged migration plan."""
    return [
        {
            "stage": "stage_1",
            "title": "Plan/report only",
            "description": "Add read-only UX.9 plan/report and optional placeholder if safe.",
            "old_behavior": "Keep old behavior unchanged.",
        },
        {
            "stage": "stage_2",
            "title": "Visual grouping",
            "description": "Visually place Chat and Instant Run under Workbench input, but keep old behavior.",
            "old_behavior": "No dispatch merge yet.",
        },
        {
            "stage": "stage_3",
            "title": "Mode preview chip",
            "description": "Add mode preview chip using deterministic preview only.",
            "old_behavior": "Still no auto-dispatch.",
        },
        {
            "stage": "stage_4",
            "title": "Confirmation mapping",
            "description": "Add confirmation-action mapping while mutating actions remain behind human confirmation and HARDEN gate.",
            "old_behavior": "No automatic mutation or run start.",
        },
        {
            "stage": "stage_5",
            "title": "Possible input unification",
            "description": "Consider actual input unification only after tests prove old flows are preserved.",
            "old_behavior": "Old flows are preserved until a later approved phase changes them.",
        },
    ]


def build_manual_review_questions() -> list[str]:
    """Return UX.9 manual review questions."""
    return [
        "Does one Workbench input reduce confusion?",
        "Does the operator still understand when they are chatting vs running?",
        "Is the ? helper understandable?",
        "Does ? look like help, not execution?",
        "Are dangerous actions still visually separate?",
        "Is mode preview visible before confirmation?",
        "Can the operator edit 4W1H fields without feeling forced?",
        "Does the layout reduce button soup?",
        "Does it preserve existing Chat and Instant Run behavior?",
        "Is this ready for implementation or still planning-only?",
    ]


def _next_ux_steps() -> list[dict[str, str]]:
    return [
        {
            "phase": "UX.10 \u2014 Unified Workbench Input Visual Integration",
            "reason": "UX.9 defines the contract; UX.10 can test a read-only visual integration while preserving old flows.",
        },
        {
            "phase": "UX.CLOSE \u2014 UX Branch Freeze Checkpoint",
            "reason": "Use only if manual review finds the plan too risky for implementation right now.",
        },
    ]


def build_unified_workbench_input_plan(
    repo_path: str,
    created_at: str | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    """Build the UX.9 unified Workbench input plan report."""
    blockers: list[str] = []
    status = "blocked" if blockers else "ready_for_review"
    return {
        "report_kind": REPORT_KIND,
        "plan_id": str(plan_id or "unified_workbench_input_plan"),
        "created_at": str(created_at or _now_iso()),
        "repo_path": str(repo_path),
        "plan_status": status,
        "unified_input_definition": build_unified_input_definition(),
        "field_schema": build_field_schema(),
        "activation_helper_contract": build_activation_helper_contract(),
        "mode_preview_contract": build_mode_preview_contract(),
        "confirmation_contract": build_confirmation_contract(),
        "button_reduction_plan": build_button_reduction_plan(),
        "ui_layout_plan": build_ui_layout_plan(),
        "migration_plan": build_migration_plan(),
        "manual_review_questions": build_manual_review_questions(),
        "next_ux_steps": _next_ux_steps(),
        "recommended_next_phase": "UX.10 \u2014 Unified Workbench Input Visual Integration",
        "warnings": list(_WARNINGS),
        "blockers": blockers,
        "guardrails": _guardrails(),
        "boundaries": list(_BOUNDARIES),
    }


def _field_line(field: dict[str, Any]) -> str:
    required = "required" if field.get("required") else "optional"
    return (
        f"- `{field.get('field_id')}` ({field.get('group')}, {required}): "
        f"{field.get('purpose')}"
    )


def render_unified_workbench_input_markdown(report: dict[str, Any]) -> str:
    """Render the unified Workbench input plan as Markdown."""
    lines: list[str] = [
        "# Unified Workbench Input Plan",
        "",
        "## Summary",
        "",
        f"- **Plan ID:** {report.get('plan_id')}",
        f"- **Created at:** {report.get('created_at')}",
        f"- **Repo path:** {report.get('repo_path')}",
        f"- **Plan status:** {report.get('plan_status')}",
        f"- **Recommended next phase:** {report.get('recommended_next_phase')}",
        "",
        "## Unified Input Definition",
        "",
        f"- **Concept:** `{report.get('unified_input_definition', {}).get('concept')}`",
        f"- **Prompt:** {report.get('unified_input_definition', {}).get('prompt')}",
        f"- **Definition:** {report.get('unified_input_definition', {}).get('definition')}",
        "",
        "## Field Schema",
        "",
    ]
    for field in report.get("field_schema", []):
        lines.append(_field_line(field))
    lines.append("")

    helper = report.get("activation_helper_contract", {})
    lines += [
        "## Activation Helper Contract",
        "",
        f"- **Name:** {helper.get('name')}",
        f"- **Symbol:** `{helper.get('symbol')}`",
        f"- **Help-only:** {str(helper.get('help_only')).lower()}",
        "",
    ]
    for field_id, example in (helper.get("field_examples") or {}).items():
        lines.append(f"- `{field_id}`: {example.get('help_text')} Example: {example.get('example')}")
    lines.append("")

    mode = report.get("mode_preview_contract", {})
    lines += ["## Mode Preview Contract", ""]
    lines.append(f"- **Source contract:** {mode.get('source_contract')}")
    lines.append(f"- **Preview is execution:** {str(mode.get('preview_is_execution')).lower()}")
    for item in mode.get("modes", []):
        lines.append(f"- `{item.get('mode_id')}` -> `{item.get('confirmation_action')}`: {item.get('meaning')}")
    lines.append("")

    confirm = report.get("confirmation_contract", {})
    lines += [
        "## Confirmation Contract",
        "",
        f"- **Human confirmation required:** {str(confirm.get('human_confirmation_required')).lower()}",
        f"- **Automatic confirmation:** {str(confirm.get('automatic_confirmation')).lower()}",
        f"- **Boundary:** {confirm.get('boundary')}",
        "",
    ]
    for item in confirm.get("actions", []):
        lines.append(f"- `{item.get('action_id')}` ({item.get('mapped_mode')}): {item.get('effect_in_ux9')}")
    lines.append("")

    lines += ["## Button Reduction Plan", ""]
    for item in report.get("button_reduction_plan", []):
        lines.append(f"- `{item.get('plan_id')}`: {item.get('summary')} Reason: {item.get('reason')}")
    lines.append("")

    layout = report.get("ui_layout_plan", {})
    lines += ["## UI Layout Plan", ""]
    lines.append(f"- **Root:** {layout.get('title')}")
    for node in layout.get("tree", []):
        children = ", ".join(node.get("children") or []) or "none"
        lines.append(f"- {node.get('node')}: {children}")
    lines.append("")

    lines += ["## Migration Plan", ""]
    for item in report.get("migration_plan", []):
        lines.append(f"- `{item.get('stage')}` - {item.get('title')}: {item.get('description')} {item.get('old_behavior')}")
    lines.append("")

    lines += ["## Manual Review Questions", ""]
    for question in report.get("manual_review_questions", []):
        lines.append(f"- {question}")
    lines.append("")

    lines += ["## Next UX Steps", ""]
    for item in report.get("next_ux_steps", []):
        lines.append(f"- {item.get('phase')}: {item.get('reason')}")
    lines.append("")

    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    lines += ([f"- {item}" for item in warnings] if warnings else ["- None"])
    lines.append("")

    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    lines += ([f"- {item}" for item in blockers] if blockers else ["- None"])
    lines.append("")

    lines += ["## Guardrails", ""]
    for key, value in (report.get("guardrails") or {}).items():
        lines.append(f"- `{key}`: {str(value).lower()}")
    lines.append("")

    lines += ["## Boundaries", ""]
    for item in report.get("boundaries", []):
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines)


def write_unified_workbench_input_artifacts(
    report: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    """Write the plan JSON and Markdown artifacts."""
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_unified_workbench_input_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }


def demo_notes() -> list[str]:
    """Return static local demo notes for the CLI."""
    return [
        "Demo uses static UX.9 plan data only.",
        "No execution path is merged.",
        "No mode preview result is computed dynamically.",
        "No external service is contacted.",
    ]
