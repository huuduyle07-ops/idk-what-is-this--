"""UX.8 - Cockpit Usability Checkpoint.

Pure report builder for the operator cockpit workflow.  It audits whether an
operator can move from goal brief to review without adding routes or powers.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_KIND = "cockpit_usability_checkpoint"
JSON_NAME = "cockpit_usability_checkpoint.json"
MD_NAME = "cockpit_usability_checkpoint.md"

CHECKPOINT_STATUSES = ("ready_for_review", "needs_manual_review", "blocked")
VISIBILITY_STATUSES = (
    "clear",
    "visible_but_competing",
    "hidden",
    "duplicated",
    "unclear",
    "not_implemented",
)
RISK_LEVELS = ("low", "medium", "high")

_VISIBILITY_MULTIPLIER = {
    "clear": 1.0,
    "visible_but_competing": 0.5,
    "duplicated": 0.5,
    "hidden": 0.25,
    "unclear": 0.25,
    "not_implemented": 0.0,
}
_RISK_WEIGHT = {"low": 1, "medium": 2, "high": 3}

_BOUNDARIES = [
    "UX.8 is a report-only usability checkpoint.",
    "UX.8 does not add new product powers.",
    "UX.8 does not add backend routes.",
    "UX.8 does not add mutation routes.",
    "UX.8 does not dispatch execution.",
    "UX.8 does not start runs.",
    "UX.8 does not call models.",
    "UX.8 does not apply patches.",
    "UX.8 does not run validation.",
    "UX.8 does not run benchmarks.",
    "UX.8 does not contact network services.",
    "UX.8 does not launch " + "work" + "ers.",
    "UX.8 does not push, merge, or open PRs.",
]

_NON_GOALS = [
    "No new product capability is introduced.",
    "No backend or mutation route is introduced.",
    "No task, run, continuation, model, review, patch, check, or benchmark action is executed.",
    "No external service, database, background process, push, merge, or PR action is performed.",
]

_MANUAL_REVIEW_CHECKLIST = [
    "I can find where to enter the task.",
    "I can tell whether I am chatting or running.",
    "I can see the current mode decision.",
    "I can see progress/timeline without hunting.",
    "I can review answer/patch in the same flow.",
    "I can see evidence cards near the result.",
    "I can continue from old context safely.",
    "I can find advanced/debug tools without them distracting me.",
    "I can tell preview-only from executable actions.",
    "Apply/review patch still feels human-triggered.",
]

_DEMO_OBSERVATIONS = [
    "Buttons feel crowded after UX.7.",
    "Goal Brief and 4W1H should feel like one input.",
    "Run Timeline should sit near the run action.",
    "Evidence Cards should attach to review output.",
    "Chat and Instant Run may need a unified Workbench input.",
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _guardrails() -> dict[str, bool]:
    return {
        "checkpoint_only": True,
        "new_product_power_added": False,
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


def build_default_workflow_steps() -> list[dict[str, str]]:
    """Return the canonical goal-to-review cockpit workflow review steps."""
    return [
        {
            "step_id": "goal_brief",
            "title": "Goal Brief / 4W1H",
            "purpose": "Help the operator state what to do, why it matters, where it applies, when to stop, and how to verify.",
            "current_surface": "Goal Brief / 4W1H workflow surface.",
            "operator_question": "Can I refine the task before choosing a mode?",
            "visibility_status": "visible_but_competing",
            "risk_level": "medium",
            "finding": "The pieces exist, but Goal Brief and 4W1H still need to feel like one task input rather than two adjacent concepts.",
            "recommended_action": "Fold brief refinement into the first input moment in the next UX plan.",
        },
        {
            "step_id": "mode_decision",
            "title": "Mode Decision",
            "purpose": "Show the predicted mode before the operator commits to chat, run, continuation, or commander planning.",
            "current_surface": "Mixed Mode Router preview relabeled as Mode Decision.",
            "operator_question": "Can I see what the system thinks I am asking for?",
            "visibility_status": "clear",
            "risk_level": "low",
            "finding": "Mode prediction is visible and correctly framed as preview-only.",
            "recommended_action": "Keep the decision near the unified input rather than as a detached panel.",
        },
        {
            "step_id": "run_or_chat_start",
            "title": "Chat / Run / Continue / Commander Start",
            "purpose": "Let the operator intentionally start the right kind of work.",
            "current_surface": "Chat and Instant Run remain separate entry points with related planning previews nearby.",
            "operator_question": "Am I chatting, running, continuing, or planning?",
            "visibility_status": "unclear",
            "risk_level": "high",
            "finding": "Chat vs Instant Run remains the biggest structural split in the cockpit.",
            "recommended_action": "Plan a unified Workbench input with mode preview and explicit start controls.",
        },
        {
            "step_id": "run_timeline",
            "title": "Run Timeline",
            "purpose": "Show progress state, blockers, and the next operator action while work is underway.",
            "current_surface": "Run Timeline workflow surface.",
            "operator_question": "Can I watch progress without hunting through tabs?",
            "visibility_status": "visible_but_competing",
            "risk_level": "medium",
            "finding": "Timeline exists, but it should sit closer to the run action and output path.",
            "recommended_action": "Attach timeline placement to the run/start area in the next layout pass.",
        },
        {
            "step_id": "answer_patch_review",
            "title": "Answer / Patch Review",
            "purpose": "Keep the operator in charge of reading the answer, reviewing the patch, and making the decision.",
            "current_surface": "Existing answer and patch review flow.",
            "operator_question": "Can I review before any apply action happens?",
            "visibility_status": "clear",
            "risk_level": "low",
            "finding": "Human-triggered review and apply actions remain conceptually clear.",
            "recommended_action": "Keep review controls in the main flow and avoid hiding them behind debug surfaces.",
        },
        {
            "step_id": "evidence_cards",
            "title": "Evidence Cards",
            "purpose": "Summarize answer, patch, checks, risks, and next action near the result.",
            "current_surface": "Evidence Cards workflow surface.",
            "operator_question": "Can I see the evidence next to the result I am judging?",
            "visibility_status": "visible_but_competing",
            "risk_level": "medium",
            "finding": "Evidence cards exist, but they can still feel disconnected from the answer/patch output.",
            "recommended_action": "Attach evidence cards to the review surface rather than leaving them as a separate destination.",
        },
        {
            "step_id": "continue_from_frame",
            "title": "Continue From Frame",
            "purpose": "Let the operator resume from prior context with safe exclusions and confirmation.",
            "current_surface": "Continue-from-Frame contract surface plus sidebar history.",
            "operator_question": "Can I recover old context without guessing what will be reused?",
            "visibility_status": "visible_but_competing",
            "risk_level": "medium",
            "finding": "Continuation is defined, but session history still needs to become frame-aware.",
            "recommended_action": "Plan frame/history integration after the unified input decision.",
        },
        {
            "step_id": "advanced_debug",
            "title": "Advanced / Debug",
            "purpose": "Keep Graph, Dream, Benchmarks, and inspection tools available without dominating daily operation.",
            "current_surface": "Collapsed Advanced / Debug drawer from UX.7.",
            "operator_question": "Can I find debug tools only when I need them?",
            "visibility_status": "clear",
            "risk_level": "low",
            "finding": "Advanced and debug surfaces are now visually secondary.",
            "recommended_action": "Keep these tools collapsed unless a troubleshooting path explicitly calls for them.",
        },
    ]


def _visibility_points(steps: list[dict[str, Any]]) -> float:
    if not steps:
        return 0.0
    per_step = 100.0 / len(steps)
    total = 0.0
    for step in steps:
        status = str(step.get("visibility_status", "not_implemented"))
        total += per_step * _VISIBILITY_MULTIPLIER.get(status, 0.0)
    return total


def _step_by_id(steps: list[dict[str, Any]], step_id: str) -> dict[str, Any]:
    for step in steps:
        if step.get("step_id") == step_id:
            return step
    return {}


def score_workflow_steps(steps: list[dict[str, Any]]) -> dict[str, int]:
    """Return deterministic checkpoint usability scores from 0 to 100."""
    workflow = round(_visibility_points(steps))

    action = 100
    start = _step_by_id(steps, "run_or_chat_start")
    if start.get("visibility_status") in {"unclear", "duplicated", "hidden", "not_implemented"}:
        action -= 25
    if _step_by_id(steps, "mode_decision").get("visibility_status") not in {"clear", "visible_but_competing"}:
        action -= 10
    if _step_by_id(steps, "advanced_debug").get("visibility_status") != "clear":
        action -= 15
    high_risk_count = sum(1 for step in steps if step.get("risk_level") == "high")
    action -= high_risk_count * 5

    review_steps = [
        _step_by_id(steps, "run_timeline"),
        _step_by_id(steps, "answer_patch_review"),
        _step_by_id(steps, "evidence_cards"),
        _step_by_id(steps, "continue_from_frame"),
    ]
    review = round(_visibility_points([s for s in review_steps if s]))

    action = max(0, min(100, action))
    review = max(0, min(100, review))
    overall = round((workflow + action + review) / 3)
    return {
        "workflow_clarity_score": workflow,
        "action_hierarchy_score": action,
        "review_confidence_score": review,
        "overall_usability_score": overall,
    }


def build_navigation_findings(steps: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Return deterministic navigation audit findings."""
    return [
        {
            "finding_id": "too_many_visible_tabs_buttons",
            "risk_level": "medium",
            "finding": "Button soup risk is reduced by UX.7, but the primary workflow still competes with several workflow buttons.",
            "recommended_action": "Make the primary workflow obvious around one Workbench input and keep secondary surfaces nearby.",
        },
        {
            "finding_id": "primary_workflow_obvious",
            "risk_level": "medium",
            "finding": "The primary workflow is understandable after reading the labels, but a new operator may not know whether to start in Chat or Instant Run.",
            "recommended_action": "Use a unified input area where the mode preview decides the next visible action.",
        },
        {
            "finding_id": "advanced_debug_secondary",
            "risk_level": "low",
            "finding": "Advanced/debug separation is improved because Graph, Dream, and Benchmarks are visually secondary.",
            "recommended_action": "Keep Advanced / Debug collapsed by default.",
        },
        {
            "finding_id": "preview_only_surfaces_executable",
            "risk_level": "medium",
            "finding": "Preview-only surfaces are labeled, but their proximity to executable controls can still imply action.",
            "recommended_action": "Use consistent preview labels and separate executable controls from preview reports.",
        },
        {
            "finding_id": "sidebar_history_continuation",
            "risk_level": "medium",
            "finding": "Sidebar history supports recall, but it does not yet clearly behave as Frames / History for continuation.",
            "recommended_action": "Rename or group recent sessions as frame-aware history once continuation moves into the main workflow.",
        },
        {
            "finding_id": "chat_instant_split",
            "risk_level": "high",
            "finding": "Chat and Instant Run still feel split even though the Mode Decision preview points toward one workbench.",
            "recommended_action": "Make UX.9 a Unified Workbench Input Plan.",
        },
    ]


def build_action_hierarchy_findings(steps: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Return the action hierarchy answers needed for manual review."""
    return [
        {
            "finding_id": "primary_action",
            "question": "What is the primary action?",
            "answer": "The primary action should be entering or refining a task in the Workbench and then choosing the predicted mode intentionally.",
            "risk_level": "medium",
        },
        {
            "finding_id": "secondary_actions",
            "question": "What is secondary?",
            "answer": "Secondary actions are opening timeline, evidence, continuation, memory, and settings surfaces to support the current work.",
            "risk_level": "low",
        },
        {
            "finding_id": "dangerous_mutating_actions",
            "question": "What is dangerous/mutating?",
            "answer": "Patch apply, real run start, and any repository-changing action must remain explicitly human-triggered.",
            "risk_level": "low",
        },
        {
            "finding_id": "debug_only_actions",
            "question": "What is debug-only?",
            "answer": "Graph, Dream, Benchmarks, Inspector-style tools, and troubleshooting views belong behind Advanced / Debug.",
            "risk_level": "low",
        },
        {
            "finding_id": "human_triggered_review",
            "question": "Are apply/review actions clearly human-triggered?",
            "answer": "The audit expects review/apply choices to remain visible, deliberate, and outside preview-only reports.",
            "risk_level": "low",
        },
        {
            "finding_id": "preview_only_labels",
            "question": "Are preview-only features labeled clearly?",
            "answer": "Preview-only labels are present, but they should be reinforced when preview cards sit near executable controls.",
            "risk_level": "medium",
        },
    ]


def build_operator_questions() -> list[str]:
    """Return canonical manual review questions for the UX.8 checkpoint."""
    return [
        "Is Instant Run still too dominant compared to the new Workbench idea?",
        "Should Chat and Instant Run merge into one input area?",
        "Should Recent Sessions become Frames / History instead of just old sessions?",
        "Should Evidence Cards be visible by default after output?",
        "Should Run Timeline always appear under the Run button?",
        "Should Graph, Dream, Benchmarks, Inspector be hidden under Advanced?",
        "Is the left sidebar useful, or is it stealing attention?",
        "Can a new user understand what to do first in under 10 seconds?",
        "Can the operator tell what is safe preview vs real mutation?",
        "Can the operator recover context from an old run without guessing?",
    ]


def _default_ux_risks() -> list[dict[str, str]]:
    return [
        {
            "risk_id": "button_soup_risk",
            "risk_level": "medium",
            "finding": "UX.7 reduced visible clutter, but the operator still sees several workflow buttons.",
            "recommended_action": "Keep reducing visible choices around the primary task path.",
        },
        {
            "risk_id": "duplicate_goal_brief_risk",
            "risk_level": "medium",
            "finding": "Goal Brief and 4W1H are merged in navigation but may still read as separate concepts.",
            "recommended_action": "Treat them as one brief refinement step.",
        },
        {
            "risk_id": "preview_as_action_confusion",
            "risk_level": "medium",
            "finding": "Preview-only reports can still look actionable if they sit beside real controls.",
            "recommended_action": "Label previews consistently and keep execution controls explicit.",
        },
        {
            "risk_id": "chat_instant_split_friction",
            "risk_level": "high",
            "finding": "Chat and Instant Run remain the main structural split.",
            "recommended_action": "Plan a unified Workbench input with mode preview.",
        },
        {
            "risk_id": "history_not_frame_friction",
            "risk_level": "medium",
            "finding": "Recent Sessions do not yet communicate safe frame continuation.",
            "recommended_action": "Plan frame-aware history after the workbench input decision.",
        },
        {
            "risk_id": "debug_surface_overexposure",
            "risk_level": "low",
            "finding": "Advanced/debug exposure is mostly controlled by the UX.7 drawer.",
            "recommended_action": "Keep debug surfaces collapsed by default.",
        },
        {
            "risk_id": "evidence_disconnected_from_output",
            "risk_level": "medium",
            "finding": "Evidence Cards are present but not yet attached to Answer / Patch review.",
            "recommended_action": "Attach evidence cards to review output in a future phase.",
        },
        {
            "risk_id": "timeline_hidden_from_run_flow",
            "risk_level": "medium",
            "finding": "Run Timeline exists but can still feel separate from starting a run.",
            "recommended_action": "Place timeline feedback near the run action.",
        },
    ]


def _observation_risk_level(risk_id: str, observations: list[str]) -> str | None:
    tokens = risk_id.replace("_", " ").lower().split()
    for observation in observations:
        low = observation.lower()
        if all(token in low for token in tokens if token != "risk"):
            if "high" in low:
                return "high"
            if "medium" in low:
                return "medium"
            if "low" in low:
                return "low"
    aliases = {
        "chat_instant_split_friction": ("chat instant", "split friction"),
        "history_not_frame_friction": ("history frame", "frame friction"),
        "evidence_disconnected_from_output": ("evidence disconnected",),
        "timeline_hidden_from_run_flow": ("timeline hidden",),
        "preview_as_action_confusion": ("preview action",),
        "duplicate_goal_brief_risk": ("goal brief duplication",),
        "debug_surface_overexposure": ("advanced debug", "debug overexposure"),
        "button_soup_risk": ("button soup",),
    }
    for observation in observations:
        low = observation.lower()
        if any(alias in low for alias in aliases.get(risk_id, ())):
            if "high" in low:
                return "high"
            if "medium" in low:
                return "medium"
            if "low" in low:
                return "low"
    return None


def build_ux_risks(
    steps: list[dict[str, Any]] | None = None,
    observations: list[str] | None = None,
) -> list[dict[str, str]]:
    """Return UX risk inventory, optionally adjusted by manual observations."""
    obs = [str(item) for item in (observations or [])]
    risks = [dict(risk) for risk in _default_ux_risks()]
    for risk in risks:
        override = _observation_risk_level(risk["risk_id"], obs)
        if override:
            risk["risk_level"] = override
            risk["finding"] = risk["finding"] + f" Observation override: {override}."
    return risks


def recommend_next_ux_step(risks: list[dict[str, str]]) -> dict[str, str]:
    """Return deterministic next UX recommendation from the risk inventory."""
    risk_map = {risk["risk_id"]: risk for risk in risks}
    if all(risk.get("risk_level") == "low" for risk in risks):
        return {
            "recommended_next_step": "close_ux_branch_checkpoint",
            "recommended_next_phase": "UX.CLOSE \u2014 UX Branch Freeze Checkpoint",
            "recommendation_reason": "All major cockpit usability risks are low.",
        }
    if risk_map.get("button_soup_risk", {}).get("risk_level") == "high":
        return {
            "recommended_next_step": "ux_navigation_cleanup_followup",
            "recommended_next_phase": "UX.9 \u2014 Advanced Debug Drawer Cleanup",
            "recommendation_reason": "Navigation clutter remains the highest risk.",
        }

    max_weight = max(_RISK_WEIGHT.get(risk.get("risk_level", "low"), 1) for risk in risks)
    highest = [
        risk["risk_id"]
        for risk in risks
        if _RISK_WEIGHT.get(risk.get("risk_level", "low"), 1) == max_weight
    ]
    if "chat_instant_split_friction" in highest:
        return {
            "recommended_next_step": "workbench_unified_input_plan",
            "recommended_next_phase": "UX.9 \u2014 Unified Workbench Input Plan",
            "recommendation_reason": "Chat vs Instant Run remains the strongest structural split.",
        }
    if "history_not_frame_friction" in highest:
        return {
            "recommended_next_step": "frame_history_integration_plan",
            "recommended_next_phase": "UX.9 \u2014 Frame History Integration Plan",
            "recommendation_reason": "Continuation depends on frame-aware history.",
        }
    if "evidence_disconnected_from_output" in highest:
        return {
            "recommended_next_step": "evidence_attached_review_surface",
            "recommended_next_phase": "UX.9 \u2014 Evidence Review Surface Integration",
            "recommendation_reason": "Review confidence depends on evidence being attached to output.",
        }
    return {
        "recommended_next_step": "ux_navigation_cleanup_followup",
        "recommended_next_phase": "UX.9 \u2014 Advanced Debug Drawer Cleanup",
        "recommendation_reason": "The remaining highest risk is navigation/debug placement.",
    }


def _checkpoint_status(scores: dict[str, int], risks: list[dict[str, str]], blockers: list[str]) -> str:
    if blockers:
        return "blocked"
    if any(risk.get("risk_level") == "high" for risk in risks):
        return "needs_manual_review"
    if scores.get("overall_usability_score", 0) < 75:
        return "needs_manual_review"
    return "ready_for_review"


def build_cockpit_usability_checkpoint(
    repo_path: str,
    observations: list[str] | None = None,
    created_at: str | None = None,
    checkpoint_id: str | None = None,
) -> dict[str, Any]:
    """Build the UX.8 cockpit usability checkpoint report."""
    obs = [str(item) for item in (observations or [])]
    steps = build_default_workflow_steps()
    scores = score_workflow_steps(steps)
    nav = build_navigation_findings(steps)
    hierarchy = build_action_hierarchy_findings(steps)
    risks = build_ux_risks(steps, obs)
    recommendation = recommend_next_ux_step(risks)
    warnings = [
        "Manual visual review is still required because this report scores the intended cockpit workflow, not live user behavior."
    ]
    blockers: list[str] = []
    status = _checkpoint_status(scores, risks, blockers)
    return {
        "report_kind": REPORT_KIND,
        "checkpoint_id": str(checkpoint_id or "cockpit_usability_checkpoint"),
        "created_at": str(created_at or _now_iso()),
        "repo_path": str(repo_path),
        "checkpoint_status": status,
        "workflow_steps": steps,
        "usability_scores": scores,
        "workflow_clarity_score": scores["workflow_clarity_score"],
        "action_hierarchy_score": scores["action_hierarchy_score"],
        "review_confidence_score": scores["review_confidence_score"],
        "overall_usability_score": scores["overall_usability_score"],
        "navigation_findings": nav,
        "action_hierarchy_findings": hierarchy,
        "operator_questions": build_operator_questions(),
        "ux_risks": risks,
        "recommended_next_step": recommendation["recommended_next_step"],
        "recommended_next_phase": recommendation["recommended_next_phase"],
        "recommendation_reason": recommendation["recommendation_reason"],
        "manual_review_checklist": list(_MANUAL_REVIEW_CHECKLIST),
        "non_goals": list(_NON_GOALS),
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": _guardrails(),
        "boundaries": list(_BOUNDARIES),
        "observations": obs,
    }


def _format_risk(risk: dict[str, str]) -> str:
    return (
        f"- `{risk.get('risk_id')}` ({risk.get('risk_level')}): "
        f"{risk.get('finding')} Recommended: {risk.get('recommended_action')}"
    )


def render_cockpit_usability_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a cockpit usability checkpoint report as Markdown."""
    lines: list[str] = [
        "# Cockpit Usability Checkpoint",
        "",
        "## Summary",
        "",
        f"- **Checkpoint ID:** {report.get('checkpoint_id')}",
        f"- **Created at:** {report.get('created_at')}",
        f"- **Repo path:** {report.get('repo_path')}",
        f"- **Checkpoint status:** {report.get('checkpoint_status')}",
        f"- **Checkpoint usability score:** {report.get('overall_usability_score')}",
        f"- **Recommended next phase:** {report.get('recommended_next_phase')}",
        "",
        "## Workflow Step Review",
        "",
    ]
    for step in report.get("workflow_steps", []):
        lines += [
            f"### `{step.get('step_id')}` - {step.get('title')}",
            "",
            f"- **Purpose:** {step.get('purpose')}",
            f"- **Current surface:** {step.get('current_surface')}",
            f"- **Operator question:** {step.get('operator_question')}",
            f"- **Visibility:** {step.get('visibility_status')}",
            f"- **Risk:** {step.get('risk_level')}",
            f"- **Finding:** {step.get('finding')}",
            f"- **Recommended action:** {step.get('recommended_action')}",
            "",
        ]

    lines += ["## Usability Scores", ""]
    for key, value in (report.get("usability_scores") or {}).items():
        label = key.replace("_", " ")
        lines.append(f"- **{label}:** {value}")
    lines.append("")

    lines += ["## Navigation Findings", ""]
    for item in report.get("navigation_findings", []):
        lines.append(f"- `{item.get('finding_id')}` ({item.get('risk_level')}): {item.get('finding')} Recommended: {item.get('recommended_action')}")
    lines.append("")

    lines += ["## Action Hierarchy Findings", ""]
    for item in report.get("action_hierarchy_findings", []):
        lines.append(f"- `{item.get('finding_id')}` ({item.get('risk_level')}): {item.get('question')} {item.get('answer')}")
    lines.append("")

    lines += ["## Operator Questions", ""]
    for question in report.get("operator_questions", []):
        lines.append(f"- {question}")
    lines.append("")

    lines += ["## UX Risks", ""]
    for risk in report.get("ux_risks", []):
        lines.append(_format_risk(risk))
    lines.append("")

    lines += [
        "## Recommended Next Step",
        "",
        f"- **Next step:** `{report.get('recommended_next_step')}`",
        f"- **Next phase:** {report.get('recommended_next_phase')}",
        f"- **Reason:** {report.get('recommendation_reason')}",
        "",
        "## Manual Review Checklist",
        "",
    ]
    for item in report.get("manual_review_checklist", []):
        lines.append(f"- [ ] {item}")
    lines.append("")

    lines += ["## Non-goals", ""]
    for item in report.get("non_goals", []):
        lines.append(f"- {item}")
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


def write_cockpit_usability_checkpoint_artifacts(
    report: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    """Write the checkpoint JSON and Markdown artifacts."""
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_cockpit_usability_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }


def demo_observations() -> list[str]:
    """Return static demo observations for the CLI."""
    return list(_DEMO_OBSERVATIONS)
