"""UX.1 — Operator Cockpit & Idea Intake Plan (report-only).

Builds a deterministic UX planning report that defines the C.A.T.T.U.S operator
cockpit and idea intake system. The report inventories known UX pain points, proposes
an operator workflow, maps cockpit sections, separates primary / advanced / debug
actions, classifies ideas into an intake board, places the 4W1H / Navier-Stokes /
Excavator metaphors, and proposes a UX roadmap.

Core principle: UX.1 plans the cockpit. It does not implement the UI, change backend
behavior, execute tasks, run agents, call models, apply patches, run validation, run
benchmarks, contact network services, launch workers, push, merge, or open PRs.

This module is stdlib-only and pure. ``write_operator_cockpit_plan`` reads nothing
and writes the two report artifacts; all analysis functions are side-effect-free.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "operator_cockpit_plan"

PLAN_STATUS_READY = "ready_for_review"
PLAN_STATUS_NEEDS_INPUT = "needs_more_input"
PLAN_STATUS_BLOCKED = "blocked"

JSON_NAME = "operator_cockpit_plan.json"
MD_NAME = "operator_cockpit_plan.md"

GUARDRAIL_NOTE = (
    "Operator Cockpit Plan is report-only: it defines the UX plan for the "
    "C.A.T.T.U.S operator cockpit. It does not implement the UI, change backend "
    "behavior, execute tasks, run agents, call models, apply patches, run validation, "
    "run benchmarks, contact network services, launch workers, push, merge, or open "
    "PRs. Human review is required before any UX implementation begins."
)

# ── Default UX problems ───────────────────────────────────────────────────────

DEFAULT_UX_PROBLEMS: tuple[dict[str, str], ...] = (
    {
        "id": "goal_brief_unclear",
        "description": "Goal Brief is hard to use and its impact is unclear.",
        "severity": "high",
    },
    {
        "id": "silent_ui",
        "description": "UI feels silent while running — no visible progress model.",
        "severity": "high",
    },
    {
        "id": "no_continue_from_frame",
        "description": "User cannot continue from previous frames or runs.",
        "severity": "high",
    },
    {
        "id": "view_only_history",
        "description": "History is view-only instead of reusable context.",
        "severity": "medium",
    },
    {
        "id": "chat_vs_instant_run_friction",
        "description": "Chat vs Instant Run split creates unnecessary friction.",
        "severity": "medium",
    },
    {
        "id": "no_progress_model",
        "description": (
            "No clear progress model analogous to Claude Code or Codex — "
            "operator cannot see where in the run cycle C.A.T.T.U.S is."
        ),
        "severity": "high",
    },
    {
        "id": "demo_not_cockpit",
        "description": "Interface feels like a demo rather than an operator cockpit.",
        "severity": "high",
    },
    {
        "id": "idea_roadmap_hijack",
        "description": (
            "New ideas keep appearing and can hijack the roadmap unless classified "
            "safely via a structured intake process."
        ),
        "severity": "medium",
    },
)

# ── Default ideas ─────────────────────────────────────────────────────────────

DEFAULT_IDEAS: tuple[dict[str, Any], ...] = (
    {
        "idea_id": "4w1h_goal_brief",
        "name": "4W1H Goal Brief simplifier",
        "description": (
            "Structured intake form: What/Why/Where/When/How fields that guide "
            "the operator through writing a precise goal brief."
        ),
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "navier_stokes_commander_flow",
        "name": "Navier-Stokes Commander flow visualization",
        "description": (
            "Visualize Commander task flow using fluid-dynamics metaphors: "
            "pressure=urgency/depth, viscosity=friction/uncertainty, "
            "external_force=human instruction, flow=task progression."
        ),
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "excavator_metaphor",
        "name": "Excavator repeated work/idea extraction metaphor",
        "description": (
            "C.A.T.T.U.S lifts useful chunks from a large problem like an excavator. "
            "Visualizes repeated extraction without turning it into autonomous execution."
        ),
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "run_timeline",
        "name": "Run timeline / progress stream",
        "description": "Surface real-time run progress so the UI is never silent.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "continue_from_frame",
        "name": "Continue-from-frame",
        "description": "Let operator continue from a previous run frame or session.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "mixed_mode_intent_router",
        "name": "Mixed mode intent router",
        "description": (
            "Smart routing that eliminates the chat vs. instant-run split "
            "by classifying operator intent automatically."
        ),
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "evidence_cards",
        "name": "Evidence cards",
        "description": "Compact evidence cards showing benchmark/validation story per run.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "goal_brief_impact_score",
        "name": "Goal Brief impact score",
        "description": "Score the clarity and likely impact of a goal brief before running.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "commander_cockpit",
        "name": "Commander cockpit",
        "description": "Dedicated panel for Commander-mode tasks with gates and checkpoints visible.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
    {
        "idea_id": "before_after_patch_impact",
        "name": "Before/after patch impact",
        "description": "Show diff-level and metric-level before/after for each patch reviewed.",
        "autonomy_increasing": False,
        "bypasses_approval": False,
        "adds_execution_power": False,
    },
)

# ── Idea classification rules ─────────────────────────────────────────────────

def _classify_idea(idea: dict[str, Any]) -> str:
    """Classify one idea into use_now / prototype_later / park / block."""
    name_lower = (idea.get("name", "") + " " + idea.get("description", "")).lower()

    # Block if autonomy / bypass / execution power flags are set
    if idea.get("autonomy_increasing") or idea.get("bypasses_approval") or idea.get("adds_execution_power"):
        return "block"

    # Block known autonomy keywords in name/description
    autonomy_signals = (
        "auto-approve", "auto_approve", "bypass human", "bypass approval",
        "auto-merge", "push directly", "without human review",
        "autonomous endless", "hidden background worker",
    )
    if any(sig in name_lower for sig in autonomy_signals):
        return "block"

    idea_id = idea.get("idea_id", "").lower()

    # use_now: directly reduces a current UX pain point
    use_now_ids = {
        "4w1h_goal_brief", "run_timeline", "continue_from_frame",
        "mixed_mode_intent_router", "evidence_cards",
        "goal_brief_impact_score", "commander_cockpit",
        "before_after_patch_impact",
    }
    if idea_id in use_now_ids:
        return "use_now"

    # prototype_later: useful metaphor or visualization, not needed for first cockpit
    prototype_ids = {"navier_stokes_commander_flow", "excavator_metaphor"}
    if idea_id in prototype_ids:
        return "prototype_later"

    # Heuristic for unknown ideas
    visualization_signals = ("visuali", "metaphor", "flow diagram", "graph", "chart")
    if any(sig in name_lower for sig in visualization_signals):
        return "prototype_later"

    complexity_signals = ("advanced", "experimental", "lab", "deep learning", "ml model")
    if any(sig in name_lower for sig in complexity_signals):
        return "park"

    return "use_now"


def _build_intake_board(ideas: list[dict[str, Any]]) -> dict[str, list]:
    board: dict[str, list] = {"use_now": [], "prototype_later": [], "park": [], "block": []}
    for idea in ideas:
        bucket = _classify_idea(idea)
        board[bucket].append(idea)
    return board


# ── Operator workflow ─────────────────────────────────────────────────────────

def _operator_workflow() -> list[dict[str, str]]:
    return [
        {
            "step_id": "start",
            "title": "Start",
            "description": (
                "Operator gives a task or question. The interface accepts a Goal Brief "
                "(4W1H fields) or free-form input. The system classifies intent and "
                "routes to the appropriate mode."
            ),
        },
        {
            "step_id": "run",
            "title": "Run",
            "description": (
                "C.A.T.T.U.S shows progress and current mode via the Run Timeline. "
                "The operator can see which phase, tool, or sub-step is active. "
                "Silence is never acceptable."
            ),
        },
        {
            "step_id": "review",
            "title": "Review",
            "description": (
                "Result is presented: answer, patch, evidence pack, and benchmark/"
                "validation story. The operator inspects before any action is taken. "
                "No patch is applied without explicit approval."
            ),
        },
        {
            "step_id": "continue",
            "title": "Continue",
            "description": (
                "Operator can continue from a previous run frame or session, reuse "
                "context, compare results across runs, and build on history rather "
                "than restarting from scratch."
            ),
        },
        {
            "step_id": "learn",
            "title": "Learn",
            "description": (
                "Lessons, anti-lessons, and flake evidence are surfaced. The operator "
                "can replay a run, inspect what changed, and understand why an outcome "
                "occurred."
            ),
        },
    ]


# ── Cockpit sections ──────────────────────────────────────────────────────────

def _cockpit_sections() -> list[dict[str, str]]:
    return [
        {"name": "Task Bar", "purpose": "Accept goal brief or free-form task input."},
        {"name": "Mode Decision", "purpose": "Display the chosen run mode (instant_run / commander_run / needs_clarification)."},
        {"name": "Run Timeline", "purpose": "Show real-time progress: current phase, tool, sub-step, and elapsed time."},
        {"name": "Current Output", "purpose": "Stream the latest answer or output as it is produced."},
        {"name": "Patch & Evidence", "purpose": "Show diff, evidence cards, validation story, and benchmark story."},
        {"name": "Continue From History", "purpose": "Browse previous frames/runs; click to continue from any prior context."},
        {"name": "Commander Panel", "purpose": "Commander-mode gates, checkpoints, budget, and stop conditions."},
        {"name": "Memory / Lessons", "purpose": "Surfaced lessons, anti-lessons, and replay links."},
        {"name": "Advanced / Debug Drawer", "purpose": "Collapsible drawer for benchmark internals, route health, raw JSON, etc."},
        {"name": "Idea Intake Board", "purpose": "Capture new ideas, classify them, and prevent roadmap hijack."},
    ]


# ── Action maps ───────────────────────────────────────────────────────────────

def _primary_action_map() -> list[dict[str, str]]:
    return [
        {"action_id": "chat_or_run", "label": "Chat or Run", "description": "Submit a task or question in any mode."},
        {"action_id": "start_instant_run", "label": "Start Instant Run", "description": "Trigger a lightweight instant run for small tasks."},
        {"action_id": "review_patch", "label": "Review Patch", "description": "Open the patch + evidence view for the current result."},
        {"action_id": "apply_patch_after_approval", "label": "Apply Patch (after approval)", "description": "Apply a patch only after explicit operator approval."},
        {"action_id": "continue_from_frame", "label": "Continue from Frame", "description": "Resume from a previous run frame or session context."},
        {"action_id": "open_evidence", "label": "Open Evidence", "description": "View benchmark/validation evidence cards for the current run."},
        {"action_id": "open_commander_readiness", "label": "Commander Readiness", "description": "Check Commander gates and readiness before a large run."},
    ]


def _advanced_action_map() -> list[dict[str, str]]:
    return [
        {"action_id": "view_benchmark_reports", "label": "Benchmark Reports", "description": "Browse EVAL track benchmark run history."},
        {"action_id": "replay_compare", "label": "Replay Compare", "description": "Compare two runs side by side."},
        {"action_id": "graph_explainability", "label": "Graph Explainability", "description": "Visualize the semantic graph for a result."},
        {"action_id": "lesson_management", "label": "Lesson Management", "description": "Review, promote, and manage lessons."},
        {"action_id": "anti_lesson_reports", "label": "Anti-Lesson Reports", "description": "Browse anti-lesson evidence."},
        {"action_id": "model_lab_reports", "label": "Model Lab Reports", "description": "View MODEL track reports."},
        {"action_id": "checkpoint_audits", "label": "Checkpoint Audits", "description": "View ROAD track checkpoint audit results."},
    ]


def _debug_action_map() -> list[dict[str, str]]:
    return [
        {"action_id": "raw_json_view", "label": "Raw JSON", "description": "View raw report JSON for any artifact."},
        {"action_id": "route_health", "label": "Route Health", "description": "Check router health and mode decision details."},
        {"action_id": "tool_registry_view", "label": "Tool Registry", "description": "Inspect the tool registry state."},
        {"action_id": "mcp_audit_view", "label": "MCP Audit", "description": "View MCP audit results."},
        {"action_id": "prompt_dumps", "label": "Prompt Dumps", "description": "Inspect prompt history for a run."},
        {"action_id": "benchmark_internals", "label": "Benchmark Internals", "description": "View low-level benchmark case details."},
        {"action_id": "graph_internals", "label": "Graph Internals", "description": "Inspect semantic graph internals."},
    ]


# ── Metaphor placement ────────────────────────────────────────────────────────

def _metaphor_placement() -> list[dict[str, Any]]:
    return [
        {
            "metaphor": "4W1H",
            "intake_classification": "use_now",
            "placement": "Goal Brief simplifier",
            "fields": {
                "What": "What are we changing?",
                "Why": "Why are we changing it?",
                "Where": "Where in the repo?",
                "When": "When should it stop?",
                "How": "How do we validate?",
            },
            "rationale": (
                "Directly reduces the 'Goal Brief is hard to use' pain point. "
                "Does not add execution power. Can be explained to the operator."
            ),
        },
        {
            "metaphor": "Navier-Stokes",
            "intake_classification": "prototype_later",
            "placement": "Commander flow visualization",
            "fields": {
                "pressure": "urgency / depth of the task",
                "viscosity": "friction / uncertainty / disagreement",
                "external_force": "human instruction",
                "flow": "task progression",
            },
            "rationale": (
                "Useful visualization metaphor for Commander mode. Not needed for "
                "the first cockpit; requires design validation."
            ),
        },
        {
            "metaphor": "Excavator",
            "intake_classification": "prototype_later",
            "placement": "Repeated work/idea extraction metaphor",
            "fields": {
                "lift": "C.A.T.T.U.S lifts useful chunks from a large problem",
                "boundary": "avoid turning this into autonomous endless execution",
            },
            "rationale": (
                "Vivid metaphor for how C.A.T.T.U.S extracts value iteratively. "
                "Prototype later; ensure it never implies autonomous endless running."
            ),
        },
    ]


# ── UX roadmap ────────────────────────────────────────────────────────────────

def _ux_roadmap() -> list[dict[str, str]]:
    return [
        {
            "phase_id": "UX.1",
            "title": "Operator Cockpit & Idea Intake Plan",
            "status": "current",
            "summary": "Pure UX planning report — cockpit sections, action maps, idea intake board, metaphor placement.",
        },
        {
            "phase_id": "UX.2",
            "title": "Run Timeline / Progress Surface",
            "status": "proposed",
            "summary": "Contract for surfacing real-time run progress so the UI is never silent.",
        },
        {
            "phase_id": "UX.3",
            "title": "Continue-from-Frame Contract",
            "status": "proposed",
            "summary": "Contract for resuming from a previous run frame or session context.",
        },
        {
            "phase_id": "UX.4",
            "title": "Mixed Mode Intent Router Preview",
            "status": "proposed",
            "summary": "Preview of smart routing that eliminates the chat vs. instant-run split.",
        },
        {
            "phase_id": "UX.5",
            "title": "Goal Brief 4W1H Simplifier",
            "status": "proposed",
            "summary": "Implement the 4W1H structured intake form to reduce Goal Brief friction.",
        },
        {
            "phase_id": "UX.6",
            "title": "Evidence Card Layout",
            "status": "proposed",
            "summary": "Compact evidence card design for benchmark/validation stories.",
        },
    ]


# ── Non-goals, allowed/forbidden next steps ───────────────────────────────────

def _non_goals() -> list[str]:
    return [
        "No full visual redesign yet.",
        "No Commander execution.",
        "No new model calls.",
        "No new remote automation.",
        "No hidden background workers.",
        "No auto-approval.",
        "No patch behavior changes.",
        "No validation/benchmark execution changes.",
    ]


def _allowed_next_steps() -> list[str]:
    return [
        "review_operator_cockpit_plan",
        "revise_ux_problem_inventory",
        "choose_first_ux_implementation_phase",
        "create_ux2_run_timeline_contract",
        "create_ux3_continue_from_frame_contract",
    ]


def _forbidden_next_steps() -> list[str]:
    return [
        "implement_full_redesign_without_plan",
        "add_commander_execution",
        "launch_worker",
        "call_model",
        "apply_patch",
        "run_validation",
        "run_benchmark",
        "contact_remote_service",
        "push_or_merge",
        "open_pr",
        "auto_approve",
    ]


def _guardrails() -> dict[str, bool]:
    return {
        "ui_implemented": False,
        "backend_behavior_changed": False,
        "task_execution_performed": False,
        "agent_launched": False,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


def _boundaries() -> list[str]:
    return [
        "UX.1 does not implement the UI yet.",
        "UX.1 does not change backend behavior.",
        "UX.1 does not execute tasks.",
        "UX.1 does not run agents.",
        "UX.1 does not call models.",
        "UX.1 does not apply patches.",
        "UX.1 does not run validation.",
        "UX.1 does not run benchmarks.",
        "UX.1 does not contact network services.",
        "UX.1 does not launch workers.",
        "UX.1 does not push, merge, or open PRs.",
        "UX.1 is a report-only UX planning phase.",
    ]


# ── Core builder ──────────────────────────────────────────────────────────────

def build_operator_cockpit_plan(
    *,
    repo_path: str = ".",
    plan_id: str = "operator_cockpit_plan",
    created_at: str = "2026-06-24T00:00:00+00:00",
    extra_problems: list[str] | None = None,
    extra_ideas: list[dict[str, Any]] | None = None,
    include_default_problems: bool = True,
    include_default_ideas: bool = True,
) -> dict[str, Any]:
    """Build the UX.1 operator cockpit plan report (pure, no I/O)."""
    # Problem inventory
    problems: list[dict[str, str]] = []
    if include_default_problems:
        problems.extend(DEFAULT_UX_PROBLEMS)
    for desc in (extra_problems or []):
        problems.append({
            "id": f"custom_{len(problems)}",
            "description": desc,
            "severity": "medium",
        })

    # Idea pool
    ideas: list[dict[str, Any]] = []
    if include_default_ideas:
        ideas.extend(DEFAULT_IDEAS)
    for item in (extra_ideas or []):
        if isinstance(item, str):
            name_lower = item.lower()
            autonomy = any(sig in name_lower for sig in (
                "auto-approve", "auto_approve", "bypass human", "bypass approval",
                "auto-merge", "push directly", "without human review",
            ))
            ideas.append({
                "idea_id": f"custom_{len(ideas)}",
                "name": item,
                "description": item,
                "autonomy_increasing": autonomy,
                "bypasses_approval": autonomy,
                "adds_execution_power": False,
            })
        else:
            ideas.append(item)

    intake_board = _build_intake_board(ideas)

    return {
        "report_kind": REPORT_KIND,
        "plan_id": plan_id,
        "created_at": created_at,
        "repo_path": repo_path,
        "plan_status": PLAN_STATUS_READY,
        "ux_problem_inventory": problems,
        "operator_workflow": _operator_workflow(),
        "cockpit_sections": _cockpit_sections(),
        "primary_action_map": _primary_action_map(),
        "advanced_action_map": _advanced_action_map(),
        "debug_action_map": _debug_action_map(),
        "idea_intake_board": intake_board,
        "metaphor_placement": _metaphor_placement(),
        "ux_roadmap": _ux_roadmap(),
        "non_goals": _non_goals(),
        "allowed_next_steps": _allowed_next_steps(),
        "forbidden_next_steps": _forbidden_next_steps(),
        "warnings": [],
        "blockers": [],
        "guardrails": _guardrails(),
        "guardrail_note": GUARDRAIL_NOTE,
        "boundaries": _boundaries(),
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "_None._"


def _md_table_rows(rows: list[dict], keys: list[str]) -> str:
    if not rows:
        return "_None._"
    header = " | ".join(keys)
    sep = " | ".join(["---"] * len(keys))
    lines = [f"| {header} |", f"| {sep} |"]
    for row in rows:
        cells = " | ".join(str(row.get(k, "")).replace("|", "\\|").replace("\n", " ") for k in keys)
        lines.append(f"| {cells} |")
    return "\n".join(lines)


def render_operator_cockpit_plan_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []

    lines.append("# Operator Cockpit & Idea Intake Plan")
    lines.append(f"\n**Plan ID:** {report.get('plan_id')}  ")
    lines.append(f"**Created:** {report.get('created_at')}  ")
    lines.append(f"**Plan Status:** {report.get('plan_status')}  ")
    lines.append(f"**Repo:** {report.get('repo_path')}\n")

    lines.append("## Summary")
    lines.append(
        "UX.1 defines the C.A.T.T.U.S operator cockpit experience and idea intake system. "
        "It inventories UX pain points, proposes a five-step operator workflow, maps cockpit "
        "sections, separates primary / advanced / debug actions, classifies ideas, and proposes "
        "a UX roadmap. No UI is implemented; no backend behavior is changed.\n"
    )

    lines.append("## UX Problem Inventory")
    problems = report.get("ux_problem_inventory", [])
    lines.append(f"**{len(problems)} problem(s) identified.**\n")
    for p in problems:
        sev = p.get("severity", "?")
        lines.append(f"- **[{sev}]** {p.get('description', '')}")
    lines.append("")

    lines.append("## Operator Workflow")
    for step in report.get("operator_workflow", []):
        lines.append(f"### {step['step_id'].capitalize()}. {step['title']}")
        lines.append(step["description"])
        lines.append("")

    lines.append("## Cockpit Sections")
    sections = report.get("cockpit_sections", [])
    lines.append(_md_table_rows(sections, ["name", "purpose"]))
    lines.append("")

    lines.append("## Primary Actions")
    primary = report.get("primary_action_map", [])
    lines.append(_md_table_rows(primary, ["action_id", "label", "description"]))
    lines.append("")

    lines.append("## Advanced Actions")
    advanced = report.get("advanced_action_map", [])
    lines.append(_md_table_rows(advanced, ["action_id", "label", "description"]))
    lines.append("")

    lines.append("## Debug Actions")
    debug = report.get("debug_action_map", [])
    lines.append(_md_table_rows(debug, ["action_id", "label", "description"]))
    lines.append("")

    lines.append("## Idea Intake Board")
    board = report.get("idea_intake_board", {})
    for bucket, label in (
        ("use_now", "Use Now"),
        ("prototype_later", "Prototype Later"),
        ("park", "Park"),
        ("block", "Block"),
    ):
        items = board.get(bucket, [])
        lines.append(f"### {label} ({len(items)})")
        if items:
            for idea in items:
                lines.append(f"- **{idea.get('name', idea.get('idea_id', '?'))}**: {idea.get('description', '')}")
        else:
            lines.append("_None._")
        lines.append("")

    lines.append("## Metaphor Placement")
    for m in report.get("metaphor_placement", []):
        lines.append(f"### {m['metaphor']} — {m['placement']}")
        lines.append(f"**Intake classification:** `{m['intake_classification']}`")
        lines.append(f"**Rationale:** {m['rationale']}")
        fields = m.get("fields", {})
        if fields:
            lines.append("\n| Key | Meaning |")
            lines.append("| --- | --- |")
            for k, v in fields.items():
                lines.append(f"| {k} | {v} |")
        lines.append("")

    lines.append("## UX Roadmap")
    roadmap = report.get("ux_roadmap", [])
    lines.append(_md_table_rows(roadmap, ["phase_id", "title", "status", "summary"]))
    lines.append("")

    lines.append("## Non-goals")
    lines.append(_md_list(report.get("non_goals", [])))
    lines.append("")

    lines.append("## Allowed Next Steps")
    lines.append(_md_list(report.get("allowed_next_steps", [])))
    lines.append("")

    lines.append("## Forbidden Next Steps")
    lines.append(_md_list(report.get("forbidden_next_steps", [])))
    lines.append("")

    lines.append("## Warnings")
    warnings = report.get("warnings", [])
    lines.append(_md_list(warnings) if warnings else "_None._")
    lines.append("")

    lines.append("## Blockers")
    blockers = report.get("blockers", [])
    lines.append(_md_list(blockers) if blockers else "_None._")
    lines.append("")

    lines.append("## Boundaries")
    for b in report.get("boundaries", []):
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"> {report.get('guardrail_note', '')}")

    return "\n".join(lines)


# ── I/O writers ───────────────────────────────────────────────────────────────

def write_operator_cockpit_plan(
    repo_path: str,
    output_root: str,
    *,
    plan_id: str = "operator_cockpit_plan",
    created_at: str = "2026-06-24T00:00:00+00:00",
    extra_problems: list[str] | None = None,
    extra_ideas: list[dict[str, Any]] | None = None,
    include_default_problems: bool = True,
    include_default_ideas: bool = True,
) -> dict[str, Any]:
    """Build the plan, write JSON + Markdown, return {ok, json_path, md_path, report}."""
    report = build_operator_cockpit_plan(
        repo_path=repo_path,
        plan_id=plan_id,
        created_at=created_at,
        extra_problems=extra_problems,
        extra_ideas=extra_ideas,
        include_default_problems=include_default_problems,
        include_default_ideas=include_default_ideas,
    )
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_operator_cockpit_plan_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
