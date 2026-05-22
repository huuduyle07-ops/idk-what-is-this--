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

# Field length caps. These bound external agent input so a runaway prompt
# can't write a 5MB handoff note.
MAX_TITLE_LEN = 200
MAX_CONTEXT_SUMMARY_LEN = 8000
MAX_VALIDATION_COMMAND_LEN = 500
MAX_EXPECTED_OUTPUT_LEN = 4000

_VALID_WORKERS: frozenset[str] = frozenset({"codex", "claude-code", "gemini", "other"})
_VALID_TASK_TYPES: frozenset[str] = frozenset({
    "proposal_only", "review_only", "explain_only", "benchmark_case", "research",
})

_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "title", "intended_worker", "task_type", "context_summary",
    "repo_path", "allowed_files", "forbidden_files",
    "validation_command", "expected_output",
})


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
# Harness — validated (Task 3).
# ---------------------------------------------------------------------------

def _validate_rel_path_list(values: Any, field_name: str) -> list[str] | None:
    """Reject absolute paths and `..` traversal. Backslash is normalized to
    `/` first so Windows-style traversal is caught the same way as POSIX.

    Returns the original list unchanged on success (we don't mutate input).
    Returns None if values is None.
    """
    if values is None:
        return None
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of strings")
    for v in values:
        if not isinstance(v, str):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        normalized = v.replace("\\", "/").strip()
        if not normalized:
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        if normalized.startswith("/"):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
        if any(part == ".." for part in normalized.split("/")):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
    return values


def create_handoff_note_harness(
    input: dict,
    *,
    handoff_root: Path | None = None,
) -> dict:
    """Validated dict-in/dict-out wrapper around
    core.handoff_notes.create_handoff_note.

    `handoff_root` is keyword-only and used only by tests + internal callers.
    External MCP callers cannot influence it (FastMCP introspects the
    signature of `_impl_create_handoff_note`, not this function).

    Returns: {ok, handoff_path, status, message} on success.
    Raises: ValueError on invalid input.
    """
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")

    unknown = set(input.keys()) - _ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")

    title_raw = input.get("title")
    if title_raw is not None and not isinstance(title_raw, str):
        raise ValueError(
            f"title must be a string, got {type(title_raw).__name__}"
        )
    title = (title_raw or "").strip()
    if not title:
        raise ValueError("title is required and must be non-empty")
    if len(title) > MAX_TITLE_LEN:
        raise ValueError(f"title must be <= {MAX_TITLE_LEN} chars")

    intended_worker = input.get("intended_worker")
    if intended_worker not in _VALID_WORKERS:
        raise ValueError(
            f"intended_worker must be one of {sorted(_VALID_WORKERS)}, "
            f"got {intended_worker!r}"
        )

    task_type = input.get("task_type")
    if task_type not in _VALID_TASK_TYPES:
        raise ValueError(
            f"task_type must be one of {sorted(_VALID_TASK_TYPES)}, "
            f"got {task_type!r}"
        )

    context_summary_raw = input.get("context_summary")
    if context_summary_raw is not None and not isinstance(context_summary_raw, str):
        raise ValueError(
            f"context_summary must be a string, "
            f"got {type(context_summary_raw).__name__}"
        )
    context_summary = (context_summary_raw or "").strip()
    if not context_summary:
        raise ValueError("context_summary is required and must be non-empty")
    if len(context_summary) > MAX_CONTEXT_SUMMARY_LEN:
        raise ValueError(
            f"context_summary must be <= {MAX_CONTEXT_SUMMARY_LEN} chars"
        )

    validation_command = input.get("validation_command")
    if validation_command is not None:
        validation_command = str(validation_command)
        if len(validation_command) > MAX_VALIDATION_COMMAND_LEN:
            raise ValueError(
                f"validation_command must be <= {MAX_VALIDATION_COMMAND_LEN} chars"
            )

    expected_output = str(input.get("expected_output") or "")
    if len(expected_output) > MAX_EXPECTED_OUTPUT_LEN:
        raise ValueError(
            f"expected_output must be <= {MAX_EXPECTED_OUTPUT_LEN} chars"
        )

    allowed_files = _validate_rel_path_list(
        input.get("allowed_files"), "allowed_files"
    )
    forbidden_files = _validate_rel_path_list(
        input.get("forbidden_files"), "forbidden_files"
    )

    from core.handoff_notes import create_handoff_note as _core_create
    result = _core_create(
        title=title,
        intended_worker=intended_worker,
        task_type=task_type,
        repo_path=input.get("repo_path"),
        allowed_files=allowed_files,
        forbidden_files=forbidden_files,
        validation_command=validation_command,
        context_summary=context_summary,
        expected_output=expected_output,
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
