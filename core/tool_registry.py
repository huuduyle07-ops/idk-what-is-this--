"""Phase 8-prep — central registry of C.A.T.T.U.S operations.

Metadata-only. No MCP server, no network exposure, no behavior changes.
This module is the source of truth for "if we hand the keys to an
external agent tomorrow, what's safe to expose?"

Every registered tool is described by a 14-field dict; the registry is
intentionally a constant tuple so callers cannot mutate the source of
truth. `list_tools` and friends return copies.

Capability modes:
  - read_only:       tools with category="read" AND mcp_exposable=True
  - artifact_write:  read_only + category="artifact_write" tools that are
                     mcp_exposable=True. No real-repo writes.
  - operator:        artifact_write + memory_write / temp_clone_execute
                     IF requires_human_approval=True AND mcp_exposable=True.
                     Never includes real_repo_write.
  - unsafe_dev:      every registered tool. mcp_exposable is ignored — this
                     mode is for internal dashboards only and must never
                     be reached by a real MCP server.

Adding a new tool means appending one dict to `_TOOLS`. There is no
runtime registration API; the registry is static so reviewers can see
exactly what an external agent could ever do.
"""
from __future__ import annotations

import copy
from typing import Any


VALID_CATEGORIES: frozenset[str] = frozenset({
    "read",
    "artifact_write",
    "temp_clone_execute",
    "real_repo_write",
    "memory_write",
})

VALID_CAPABILITY_MODES: frozenset[str] = frozenset({
    "read_only",
    "artifact_write",
    "operator",
    "unsafe_dev",
})


def _tool(
    *,
    name: str,
    title: str,
    description: str,
    category: str,
    phase: str,
    reads: list[str],
    writes: list[str],
    can_touch_real_repo: bool,
    can_run_subprocess: bool,
    requires_human_approval: bool,
    mcp_exposable: bool,
    default_enabled: bool,
    route_or_function: str,
    notes: str,
) -> dict[str, Any]:
    """Helper: build a tool dict, asserting required invariants at module
    import time so a malformed registry entry fails loudly the first time
    anyone imports this module.
    """
    assert category in VALID_CATEGORIES, f"invalid category for {name}: {category}"
    if category == "real_repo_write":
        assert can_touch_real_repo, f"{name} is real_repo_write but can_touch_real_repo is False"
    if category == "read":
        assert not can_touch_real_repo, f"{name} is read but can_touch_real_repo is True"
        assert not can_run_subprocess, f"{name} is read but can_run_subprocess is True"
    return {
        "name": name,
        "title": title,
        "description": description,
        "category": category,
        "phase": phase,
        "reads": list(reads),
        "writes": list(writes),
        "can_touch_real_repo": bool(can_touch_real_repo),
        "can_run_subprocess": bool(can_run_subprocess),
        "requires_human_approval": bool(requires_human_approval),
        "mcp_exposable": bool(mcp_exposable),
        "default_enabled": bool(default_enabled),
        "route_or_function": route_or_function,
        "notes": notes,
    }


# Note: order in this tuple is the order tests will list them.
_TOOLS: tuple[dict[str, Any], ...] = (
    # --- Read-only (9) -----------------------------------------------------
    _tool(
        name="get_health",
        title="Get workspace health",
        description="Cheap, non-blocking checks for API keys, DB, embeddings, Ollama, tree-sitter, and local toolchains.",
        category="read",
        phase="5",
        reads=["env", "config", "DB if available", "Ollama if enabled"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /health",
        notes="Safe for any external agent. Returns a flat dict of named checks.",
    ),
    _tool(
        name="list_benchmark_reports",
        title="List benchmark reports",
        description="List recent benchmark report JSON files under .agent/benchmarks/.",
        category="read",
        phase="5",
        reads=[".agent/benchmarks/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /benchmarks/list",
        notes="Read-only directory scan; never executes a benchmark.",
    ),
    _tool(
        name="read_benchmark_report",
        title="Read a benchmark report",
        description="Return the structured contents of a single benchmark report by filename.",
        category="read",
        phase="5",
        reads=[".agent/benchmarks/<file>"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /benchmarks/report",
        notes="Path-traversal guarded against escaping .agent/benchmarks/.",
    ),
    _tool(
        name="list_dream_reports",
        title="List Dream reports",
        description="List recent Dream run artifacts under .agent/dreams/.",
        category="read",
        phase="5",
        reads=[".agent/dreams/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /dream/reports",
        notes="Read-only sidebar feed for the Dream tab; never queues or runs Dream.",
    ),
    _tool(
        name="read_dream_report",
        title="Read a Dream report",
        description="Return the structured contents of a Dream run by id or path.",
        category="read",
        phase="5",
        reads=[".agent/dreams/<run>/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /dream/report",
        notes="Path-traversal guarded.",
    ),
    _tool(
        name="list_lessons",
        title="List lessons",
        description="List lesson candidates / active / blocked records.",
        category="read",
        phase="6.2",
        reads=[".agent/lessons/{candidate,active,blocked}/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /lessons/list",
        notes="Active lessons only ever reach the prompt when LESSON_RETRIEVAL_ENABLED=true.",
    ),
    _tool(
        name="read_lesson_proposal",
        title="Read a lesson's source proposal",
        description="Return the proposal.md backing a lesson by id, when one exists.",
        category="read",
        phase="6.2",
        reads=[".agent/proposals/<run>/<item>/proposal.md"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /lessons/proposal",
        notes="Path-traversal guarded against escaping the proposals root.",
    ),
    _tool(
        name="list_worker_runs",
        title="List worker runs",
        description="List Phase 7.1 worker run artifacts under .agent/worker_runs/.",
        category="read",
        phase="7.2",
        reads=[".agent/worker_runs/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /worker-runs/list",
        notes="Returns the listing shape from core.worker_runs.list_worker_runs.",
    ),
    _tool(
        name="read_worker_run",
        title="Read a worker run",
        description="Return full detail (including raw_output_preview) for one worker run.",
        category="read",
        phase="7.2",
        reads=[".agent/worker_runs/<run>/"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /worker-runs/view",
        notes="raw_output_preview is capped at 2000 chars; full file lives on disk.",
    ),
    _tool(
        name="list_tool_registry",
        title="List the C.A.T.T.U.S tool registry",
        description="Return the full tool registry as metadata (every tool's category, flags, route, notes). Pure metadata — does not invoke any tool.",
        category="read",
        phase="8.1",
        reads=["core.tool_registry (in-process)"],
        writes=[],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="GET /tools/registry",
        notes="Self-describing endpoint for MCP clients. Mirrors the dict shape from tool_registry.list_tools().",
    ),

    # --- Artifact-write (3) ------------------------------------------------
    _tool(
        name="create_handoff_note",
        title="Create a handoff note",
        description="Write a bounded handoff note under .agent/handoffs/. Does not run any subagent.",
        category="artifact_write",
        phase="7.1",
        reads=["config"],
        writes=[".agent/handoffs/<note>.md"],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="POST /handoffs/create",
        notes="Note creation is the default-safe action; running the handoff is a separate explicit step (run_subagent_handoff, disabled for MCP).",
    ),
    _tool(
        name="import_worker_run_as_proposal",
        title="Import a worker run as a proposal",
        description="Copy a complete (non-dry-run) worker run into .agent/proposals/<run>/01-<slug>/ for downstream review.",
        category="artifact_write",
        phase="7.2",
        reads=[".agent/worker_runs/<run>/"],
        writes=[".agent/proposals/<run>/<item>/"],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=False,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="POST /worker-runs/import",
        notes="Refuses incomplete and dry-run worker outputs. Path-traversal guarded.",
    ),
    _tool(
        name="validate_imported_worker_proposal",
        title="Validate a worker-imported proposal",
        description="Apply the imported patch_plan.json in a temp clone of repo_path and run the inferred validation command.",
        category="artifact_write",
        phase="7.2.1",
        reads=[".agent/proposals/<run>/<item>/", "<repo_path> (read-only copy to temp clone)"],
        writes=[".agent/proposals/<run>/<item>/apply_result.json",
                ".agent/proposals/<run>/<item>/validation.json",
                ".agent/proposals/<run>/<item>/validation_output.txt",
                ".agent/proposals/<run>/<item>/case.json (synth, 7.2.1.1)",
                ".agent/proposals/<run>/<item>/patch_proposal.json (synth, 7.2.1.1)"],
        can_touch_real_repo=False,
        can_run_subprocess=True,
        requires_human_approval=True,
        mcp_exposable=True,
        default_enabled=True,
        route_or_function="POST /proposals/validate",
        notes="Categorized as artifact_write because the deliverable is .agent/ JSON; subprocess risk is encoded via can_run_subprocess + requires_human_approval, not the category. Real repo and repo_path are byte-identical before and after; subprocess runs only inside the temp clone. Synth step (7.2.1.1) lands case.json + patch_proposal.json on success.",
    ),

    # --- Registered but disabled for MCP (6) -------------------------------
    _tool(
        name="apply_patch",
        title="Apply a single-file patch",
        description="Apply one snippet patch to the real repo. Patch Safety gate runs first.",
        category="real_repo_write",
        phase="7",
        reads=["<repo>"],
        writes=["<repo>/<target_file>"],
        can_touch_real_repo=True,
        can_run_subprocess=True,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="POST /apply_patch",
        notes="DISABLED FOR MCP. The Patch Safety gate is in place inside the route, but real-repo writes from external agents are out of scope for Phase 8.",
    ),
    _tool(
        name="apply_patch_plan",
        title="Apply a multi-op patch plan",
        description="Apply a structured patch_plan list to the real repo with rollback on validation failure.",
        category="real_repo_write",
        phase="7",
        reads=["<repo>"],
        writes=["<repo>/*"],
        can_touch_real_repo=True,
        can_run_subprocess=True,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="POST /apply_patch_plan",
        notes="DISABLED FOR MCP. Same reasoning as apply_patch.",
    ),
    _tool(
        name="dream_apply",
        title="Apply a Dream-ready item",
        description="Take a ready_to_apply Dream item and apply its patch_plan to the real repo with validation.",
        category="real_repo_write",
        phase="preexisting",
        reads=[".agent/dreams/<run>/"],
        writes=["<repo>/*"],
        can_touch_real_repo=True,
        can_run_subprocess=True,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="POST /dream/apply",
        notes="DISABLED FOR MCP. Same Patch Safety gate as apply_patch_plan.",
    ),
    _tool(
        name="run_subagent_handoff",
        title="Run a subagent handoff in a temp clone",
        description="Execute the worker command described in a handoff note inside a temp clone. Disabled here even though the work happens in isolation.",
        category="temp_clone_execute",
        phase="7.1",
        reads=[".agent/handoffs/<note>.md", "<repo_path> (read-only copy to temp clone)"],
        writes=[".agent/worker_runs/<run>/"],
        can_touch_real_repo=False,
        can_run_subprocess=True,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="scripts.run_subagent_handoff.run_handoff",
        notes="DISABLED FOR MCP. The --allow-run gate is operator-only; exposing this would let an external agent spend Codex/Claude/Gemini quota.",
    ),
    _tool(
        name="promote_lesson",
        title="Promote a candidate lesson to active",
        description="Move a candidate lesson from .agent/lessons/candidate/ to .agent/lessons/active/.",
        category="memory_write",
        phase="6.2",
        reads=[".agent/lessons/candidate/<id>.json"],
        writes=[".agent/lessons/active/<id>.json"],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="POST /lessons/promote",
        notes="DISABLED FOR MCP. Promotion to active makes a lesson prompt-eligible — an explicitly human decision.",
    ),
    _tool(
        name="block_lesson",
        title="Block a candidate or active lesson",
        description="Move a lesson into .agent/lessons/blocked/ so it is never retrieved.",
        category="memory_write",
        phase="6.2",
        reads=[".agent/lessons/{candidate,active}/<id>.json"],
        writes=[".agent/lessons/blocked/<id>.json"],
        can_touch_real_repo=False,
        can_run_subprocess=False,
        requires_human_approval=True,
        mcp_exposable=False,
        default_enabled=False,
        route_or_function="POST /lessons/block",
        notes="DISABLED FOR MCP. Lesson-state changes stay operator-only.",
    ),
)


def list_tools() -> list[dict[str, Any]]:
    """Return a deep copy of every registered tool, preserving registry order."""
    return [copy.deepcopy(t) for t in _TOOLS]


def get_tool(name: str) -> dict[str, Any] | None:
    """Return a deep copy of the tool with the given name, or None."""
    for t in _TOOLS:
        if t["name"] == name:
            return copy.deepcopy(t)
    return None


def tools_by_category(category: str) -> list[dict[str, Any]]:
    """Return deep copies of every tool with the given category.

    Raises ValueError for an unknown category.
    """
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"unknown category: {category!r}; must be one of {sorted(VALID_CATEGORIES)}"
        )
    return [copy.deepcopy(t) for t in _TOOLS if t["category"] == category]


def is_tool_allowed(name: str, capability_mode: str = "read_only") -> bool:
    """Check whether `name` is allowed under the given `capability_mode`.

    Unknown tool names return False (not an exception). Unknown
    capability_mode raises ValueError.
    """
    if capability_mode not in VALID_CAPABILITY_MODES:
        raise ValueError(
            f"unknown capability_mode: {capability_mode!r}; must be one of "
            f"{sorted(VALID_CAPABILITY_MODES)}"
        )
    # Find tool without copying (we won't expose it).
    tool: dict[str, Any] | None = None
    for t in _TOOLS:
        if t["name"] == name:
            tool = t
            break
    if tool is None:
        return False

    if capability_mode == "unsafe_dev":
        # Internal-only listing mode: mcp_exposable is ignored.
        return True

    if not tool["mcp_exposable"]:
        # Global kill switch for every mode except unsafe_dev.
        return False

    category = tool["category"]
    if capability_mode == "read_only":
        return category == "read"
    if capability_mode == "artifact_write":
        return category in {"read", "artifact_write"}
    if capability_mode == "operator":
        if category in {"read", "artifact_write"}:
            return True
        if category in {"memory_write", "temp_clone_execute"}:
            return bool(tool["requires_human_approval"])
        # real_repo_write never reaches operator mode.
        return False

    # Defensive — should be unreachable given VALID_CAPABILITY_MODES check above.
    return False
