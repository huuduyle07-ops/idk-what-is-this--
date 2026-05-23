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

import logging
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import tool_registry
from core.mcp_audit import record_mcp_invocation
from mcp_server import read_only


logger = logging.getLogger(__name__)


# Documentation-only label — see list_exposed_tool_names for the actual gate.
CAPABILITY_MODE = "artifact_write"

# The *narrow* slice of artifact-write tools this server exposes. This remains
# stricter than the registry's artifact_write capability mode.
_EXTRA_WRITE_TOOLS: tuple[str, ...] = (
    "create_handoff_note",
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
)

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
_IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "worker_run_id",
})
_VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS: frozenset[str] = frozenset({
    "proposal_ref",
    "repo_path",
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
        # All four entry-level rejections (non-string, empty, absolute,
        # traversal) intentionally share the same message — we do not
        # leak which check fired. Add the reason only to internal logs,
        # never to the user-facing error.
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
        # Reject both ".." (parent) and "." (current-dir) segments. "."
        # is technically legal as "no-op" but adds nothing and lets an
        # attacker compose paths that look benign at a glance.
        if any(part in ("..", ".") for part in normalized.split("/")):
            raise ValueError(
                f"{field_name} entry is not a safe relative path: {v!r}"
            )
    # Return a fresh list so a future change in core that mutates the
    # input doesn't silently alter the caller's dict.
    return list(values)


def _handoff_input_summary(input: Any) -> dict:
    if not isinstance(input, dict):
        return {"input_type": type(input).__name__}

    summary = {
        field_name: input[field_name]
        for field_name in (
            "title",
            "intended_worker",
            "task_type",
            "context_summary",
            "repo_path",
            "allowed_files",
            "forbidden_files",
        )
        if field_name in input
    }
    if "validation_command" in input:
        summary["validation_command_present"] = bool(input.get("validation_command"))
    if "expected_output" in input:
        summary["expected_output_present"] = bool(input.get("expected_output"))

    unknown_fields = sorted(str(name) for name in set(input) - _ALLOWED_INPUT_FIELDS)
    if unknown_fields:
        summary["unknown_fields"] = unknown_fields
    return summary


def _record_handoff_audit(
    input: Any,
    *,
    allowed: bool,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> None:
    try:
        record_mcp_invocation(
            tool_name="create_handoff_note",
            capability_mode=CAPABILITY_MODE,
            allowed=allowed,
            input_summary=_handoff_input_summary(input),
            result_summary=result_summary,
            artifacts=artifacts or [],
            error=error,
        )
    except Exception:
        logger.warning(
            "failed to record create_handoff_note MCP audit event",
            exc_info=True,
        )


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
    try:
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
            collect_brain_stamp=False,
            handoff_root=handoff_root,
        )
    except ValueError as error:
        _record_handoff_audit(input, allowed=False, error=str(error))
        raise

    response = {
        "ok": True,
        "handoff_path": result["path"],
        "status": "draft",
        "message": "Handoff note created. This did not run a subagent.",
    }
    _record_handoff_audit(
        input,
        allowed=True,
        result_summary={
            "ok": response["ok"],
            "status": response["status"],
            "message": response["message"],
        },
        artifacts=[response["handoff_path"]],
    )
    return response


def _validate_worker_run_import_input(input: Any) -> str:
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")

    unknown = set(input) - _IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")

    worker_run_id_raw = input.get("worker_run_id")
    if not isinstance(worker_run_id_raw, str):
        raise ValueError("worker_run_id is required and must be a string")
    worker_run_id = worker_run_id_raw.strip()
    if not worker_run_id:
        raise ValueError("worker_run_id is required and must be non-empty")
    if Path(worker_run_id).is_absolute():
        raise ValueError("worker_run_id must be a relative run id")
    if "/" in worker_run_id or "\\" in worker_run_id:
        raise ValueError("worker_run_id must not contain path separators")
    if worker_run_id in {".", ".."}:
        raise ValueError("worker_run_id is not a safe run id")
    return worker_run_id


def _worker_run_import_input_summary(input: Any) -> dict:
    if not isinstance(input, dict):
        return {"input_type": type(input).__name__}

    summary = {}
    if "worker_run_id" in input:
        summary["worker_run_id"] = input["worker_run_id"]
    unknown_fields = sorted(
        str(name)
        for name in set(input) - _IMPORT_WORKER_RUN_ALLOWED_INPUT_FIELDS
    )
    if unknown_fields:
        summary["unknown_fields"] = unknown_fields
    return summary


def _record_worker_run_import_audit(
    input: Any,
    *,
    allowed: bool,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> None:
    try:
        record_mcp_invocation(
            tool_name="import_worker_run_as_proposal",
            capability_mode=CAPABILITY_MODE,
            allowed=allowed,
            input_summary=_worker_run_import_input_summary(input),
            result_summary=result_summary,
            artifacts=artifacts or [],
            error=error,
        )
    except Exception:
        logger.warning(
            "failed to record import_worker_run_as_proposal MCP audit event",
            exc_info=True,
        )


def import_worker_run_as_proposal_harness(input: dict) -> dict:
    """Import one complete worker run into proposals for operator review."""
    try:
        worker_run_id = _validate_worker_run_import_input(input)
        from core.worker_runs import import_worker_run_as_proposal as _core_import
        result = _core_import(worker_run_id)
    except (FileNotFoundError, ValueError) as error:
        _record_worker_run_import_audit(input, allowed=False, error=str(error))
        raise

    response = {
        "ok": True,
        "proposal_dir": result["proposal_dir"],
        "message": (
            "Worker run imported as proposal. "
            "Review it before validation or lesson creation."
        ),
    }
    _record_worker_run_import_audit(
        input,
        allowed=True,
        result_summary={
            "ok": response["ok"],
            "message": response["message"],
        },
        artifacts=[response["proposal_dir"]],
    )
    return response


def _validate_imported_proposal_input(input: Any) -> tuple[str, str]:
    """Validate MCP input for validate_imported_worker_proposal.

    Returns (proposal_ref, repo_path) on success. Raises ValueError on any
    shape problem so the harness can audit `allowed=False` and re-raise.
    """
    if not isinstance(input, dict):
        raise ValueError(f"input must be a dict, got {type(input).__name__}")

    unknown = set(input) - _VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {sorted(unknown)}")

    proposal_ref_raw = input.get("proposal_ref")
    if not isinstance(proposal_ref_raw, str):
        raise ValueError("proposal_ref is required and must be a string")
    proposal_ref = proposal_ref_raw.strip()
    if not proposal_ref:
        raise ValueError("proposal_ref is required and must be non-empty")
    if Path(proposal_ref).is_absolute():
        raise ValueError("proposal_ref must be a relative path")
    normalized = proposal_ref.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError("proposal_ref must be a relative path")
    segments = normalized.split("/")
    if not segments:
        raise ValueError("proposal_ref must have at least one path segment")
    for part in segments:
        if part == "" or part == "." or part == "..":
            raise ValueError(
                f"proposal_ref must not contain empty, '.', or '..' segments: {proposal_ref!r}"
            )

    repo_path_raw = input.get("repo_path")
    if not isinstance(repo_path_raw, str):
        raise ValueError("repo_path is required and must be a string")
    repo_path = repo_path_raw.strip()
    if not repo_path:
        raise ValueError("repo_path is required and must be non-empty")
    repo_dir = Path(repo_path).expanduser().resolve()
    if not repo_dir.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path!r}")

    return proposal_ref, repo_path


def _validate_imported_proposal_input_summary(input: Any) -> dict:
    if not isinstance(input, dict):
        return {"input_type": type(input).__name__}

    summary: dict[str, Any] = {}
    if "proposal_ref" in input:
        summary["proposal_ref"] = input["proposal_ref"]
    if "repo_path" in input:
        rp = input["repo_path"]
        if isinstance(rp, str):
            summary["repo_path_basename"] = Path(rp).name
        else:
            summary["repo_path_type"] = type(rp).__name__
    unknown_fields = sorted(
        str(name)
        for name in set(input)
        - _VALIDATE_IMPORTED_PROPOSAL_ALLOWED_INPUT_FIELDS
    )
    if unknown_fields:
        summary["unknown_fields"] = unknown_fields
    return summary


def _record_validate_imported_proposal_audit(
    input: Any,
    *,
    allowed: bool,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> None:
    try:
        record_mcp_invocation(
            tool_name="validate_imported_worker_proposal",
            capability_mode=CAPABILITY_MODE,
            allowed=allowed,
            input_summary=_validate_imported_proposal_input_summary(input),
            result_summary=result_summary,
            artifacts=artifacts or [],
            error=error,
        )
    except Exception:
        logger.warning(
            "failed to record validate_imported_worker_proposal MCP audit event",
            exc_info=True,
        )


def validate_imported_worker_proposal_harness(input: dict) -> dict:
    """Validate an already-imported worker proposal in a temp clone.

    Delegates resolution to `core.worker_runs.validate_imported_worker_proposal`,
    which resolves `proposal_ref` under `worker_runs.DEFAULT_PROPOSALS_ROOT` and
    re-enforces the path-traversal guard. The harness never accepts an
    absolute proposal directory.

    Returns the narrow MCP response shape:
      {ok, proposal_dir, apply_success, validation_ok, message, artifacts}

    Raises:
      ValueError on invalid input shape.
      FileNotFoundError if the proposal directory or repo_path is missing.
    """
    try:
        proposal_ref, repo_path = _validate_imported_proposal_input(input)
        from core.worker_runs import validate_imported_worker_proposal as _core_validate
        result = _core_validate(
            proposal_dir=proposal_ref,
            repo_path=repo_path,
            proposals_root=None,
        )
    except (ValueError, FileNotFoundError) as error:
        _record_validate_imported_proposal_audit(input, allowed=False, error=str(error))
        raise

    proposal_dir_str = result["proposal_dir"]
    proposal_dir = Path(proposal_dir_str)
    artifacts: list[str] = [proposal_dir_str]
    for fname in (
        "apply_result.json",
        "validation.json",
        "validation_output.txt",
        "case.json",
        "patch_proposal.json",
    ):
        candidate = proposal_dir / fname
        if candidate.is_file():
            artifacts.append(str(candidate))

    response = {
        "ok": True,
        "proposal_dir": proposal_dir_str,
        "apply_success": bool(result.get("apply_success")),
        "validation_ok": result.get("validation_ok"),
        "message": result.get("message") or "",
        "artifacts": artifacts,
    }
    _record_validate_imported_proposal_audit(
        input,
        allowed=True,
        result_summary={
            "ok": response["ok"],
            "apply_success": response["apply_success"],
            "validation_ok": response["validation_ok"],
            "message": response["message"],
        },
        artifacts=artifacts,
    )
    return response


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


def _impl_import_worker_run_as_proposal(input: dict) -> dict:
    """MCP-registered impl for the narrow worker-run import harness."""
    return import_worker_run_as_proposal_harness(input)


def _impl_validate_imported_worker_proposal(input: dict) -> dict:
    """MCP-registered impl for the narrow worker-proposal validation harness."""
    return validate_imported_worker_proposal_harness(input)


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
    "import_worker_run_as_proposal": _impl_import_worker_run_as_proposal,
    "validate_imported_worker_proposal": _impl_validate_imported_worker_proposal,
}

# ---------------------------------------------------------------------------
# Lazy MCP import
# ---------------------------------------------------------------------------

def _import_mcp() -> tuple[Any | None, BaseException | None]:
    """Try to import FastMCP. Returns (FastMCP_class_or_None, error_or_None).

    Isolated as its own function so tests can monkeypatch the missing-dep
    branch even on machines where `mcp` IS installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
        return FastMCP, None
    except ImportError as e:
        return None, e


# ---------------------------------------------------------------------------
# Server construction + CLI entrypoint
# ---------------------------------------------------------------------------

def build_server() -> Any:
    """Construct (but do not run) a FastMCP server with allowed tools wired.

    Raises RuntimeError with the friendly message if the `mcp` package is
    not installed. Never starts a server or opens stdio.
    """
    FastMCP, err = _import_mcp()
    if FastMCP is None:
        raise RuntimeError(_FRIENDLY_MISSING_DEP_MSG) from err

    server = FastMCP(_SERVER_NAME)
    allowed = set(list_exposed_tool_names())

    for name in list(_IMPLS.keys()):
        if name not in allowed:
            continue
        impl = _IMPLS[name]
        meta = tool_registry.get_tool(name) or {}
        description = meta.get("description") or meta.get("title") or name
        server.add_tool(impl, name=name, description=description)

    return server


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code.

    Recognized flags:
      --list-tools   Print the exposed tool names (one per line) and exit 0
                     without constructing or starting a server. Does NOT
                     require the `mcp` package to be installed.

    Exit codes:
      0 — server ran cleanly OR --list-tools printed successfully
      2 — `mcp` package not installed; friendly message printed to stderr
    """
    args = list(argv if argv is not None else sys.argv[1:])

    # --list-tools is a registry-only query. Handle it BEFORE any attempt
    # to import `mcp` — operators must be able to inspect the surface even
    # on machines without the optional dependency.
    if "--list-tools" in args:
        for name in list_exposed_tool_names():
            print(name)
        return 0

    try:
        server = build_server()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via scripts/ shim
    raise SystemExit(main(sys.argv[1:]))
