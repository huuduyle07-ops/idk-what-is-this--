"""Phase 8.2a — artifact-write MCP server for C.A.T.T.U.S.

Exposes every tool the read-only server exposes PLUS exactly one
write-capable tool: `create_handoff_note`. Every other artifact-write,
temp-clone-execute, real-repo-write, and memory-write tool stays blocked.

Design constraints:
  - Re-uses the 10 `_impl_*` callables from mcp_server.read_only by direct
    import; no duplication.
  - The narrow write surface is declared by `_EXTRA_WRITE_TOOLS`, NOT by
    the registry's `artifact_write` capability mode (which would expose
    all 3 artifact_write tools).
  - The module must be importable without the `mcp` package installed.
  - Importing this module must NOT start a server or open stdio.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import tool_registry
from mcp_server import read_only


# Documentation-only label — see list_exposed_tool_names for the actual gate.
CAPABILITY_MODE = "artifact_write"

# The *narrow* slice of artifact-write tools this server exposes. Phase 8.2a
# ships with exactly one. Future phases may extend.
_EXTRA_WRITE_TOOLS: tuple[str, ...] = ("create_handoff_note",)

_SERVER_NAME = "cattus-artifact-write"

_FRIENDLY_MISSING_DEP_MSG = (
    "MCP package not installed. "
    "Install optional MCP dependencies to run this server."
)


# ---------------------------------------------------------------------------
# Allowlist API (works without `mcp` installed)
# ---------------------------------------------------------------------------

def list_exposed_tool_names() -> list[str]:
    """Tool names this server exposes: the 10 read-only tools + the narrow
    `_EXTRA_WRITE_TOOLS` slice (currently just `create_handoff_note`).

    The `is_tool_allowed(n, "artifact_write")` check is defensive — if the
    registry ever sets mcp_exposable=False on an extra write tool, this
    server stops exposing it automatically.
    """
    names = list(read_only.list_exposed_tool_names())
    for n in _EXTRA_WRITE_TOOLS:
        if tool_registry.is_tool_allowed(n, "artifact_write"):
            names.append(n)
    return names


# ---------------------------------------------------------------------------
# Harness — happy path (validation lands in Tasks 3-4).
# ---------------------------------------------------------------------------

def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """Validated dict-in/dict-out wrapper around
    core.handoff_notes.create_handoff_note.

    `handoff_root` is keyword-only and used only by tests + internal callers
    that want to redirect output to a tmp_path. It is NOT part of `input`
    (which is the MCP-facing schema), so external MCP callers cannot
    influence it.

    Returns: {ok, handoff_path, status, message} on success.
    Raises: ValueError on invalid input (validation lands in Tasks 3-4).
    """
    from core.handoff_notes import create_handoff_note as _core_create

    result = _core_create(
        title=input["title"],
        intended_worker=input["intended_worker"],
        task_type=input["task_type"],
        repo_path=input.get("repo_path"),
        allowed_files=input.get("allowed_files"),
        forbidden_files=input.get("forbidden_files"),
        validation_command=input.get("validation_command"),
        context_summary=input.get("context_summary", ""),
        expected_output=input.get("expected_output", ""),
        # extra_safety_rules intentionally NOT exposed via the harness:
        # defaults from core.handoff_notes.DEFAULT_SAFETY_RULES always apply.
        handoff_root=handoff_root,
    )
    return {
        "ok": True,
        "handoff_path": result["path"],
        "status": "draft",
        "message": "Handoff note created. This did not run a subagent.",
    }


# ---------------------------------------------------------------------------
# Thin tool implementations
# ---------------------------------------------------------------------------

# Re-use the read-only impls verbatim by direct import (sibling module in
# the same package — leading underscore signals "internal to mcp_server",
# not "internal to read_only.py").


def _impl_create_handoff_note(input: dict) -> dict:
    """MCP-registered impl. Delegates to the harness without exposing
    `handoff_root` so external clients cannot redirect output."""
    return create_handoff_note_harness(input)


_IMPLS: dict[str, Callable[..., Any]] = {
    "get_health": read_only._impl_get_health,
    "list_benchmark_reports": read_only._impl_list_benchmark_reports,
    "read_benchmark_report": read_only._impl_read_benchmark_report,
    "list_dream_reports": read_only._impl_list_dream_reports,
    "read_dream_report": read_only._impl_read_dream_report,
    "list_lessons": read_only._impl_list_lessons,
    "read_lesson_proposal": read_only._impl_read_lesson_proposal,
    "list_worker_runs": read_only._impl_list_worker_runs,
    "read_worker_run": read_only._impl_read_worker_run,
    "list_tool_registry": read_only._impl_list_tool_registry,
    "create_handoff_note": _impl_create_handoff_note,
}
