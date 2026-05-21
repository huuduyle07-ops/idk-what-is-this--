"""Phase 8.1 — read-only MCP server for C.A.T.T.U.S.

Exposes ONLY the tools that `core.tool_registry` marks allowed under
capability_mode='read_only'. The registry is the single source of truth;
this module never special-cases a name list.

Design constraints (per Phase 8.1 spec):
  - No artifact-write, temp-clone-execute, real-repo-write, or
    memory-write tool may be exposed.
  - The module must be importable on machines without the `mcp` package
    installed. `build_server()` is the only function that needs the dep,
    and it raises a friendly RuntimeError if the dep is missing.
  - Importing this module must NOT start a server, open stdio, or have
    any other side effect.
  - Path-traversal guards on every file/path read.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from core import tool_registry


# The only capability mode this server ever operates in. unsafe_dev is
# explicitly NOT honored here — that mode is for internal dashboards only.
CAPABILITY_MODE = "read_only"

_FRIENDLY_MISSING_DEP_MSG = (
    "MCP package not installed. "
    "Install optional MCP dependencies to run this server."
)

_SERVER_NAME = "cattus-readonly"


# ---------------------------------------------------------------------------
# Allowlist API (works without `mcp` installed)
# ---------------------------------------------------------------------------

def list_exposed_tool_names() -> list[str]:
    """Tool names this server exposes.

    Pulled live from `core.tool_registry` under capability_mode='read_only'.
    Preserves the registry's declaration order so MCP clients see a stable
    list across runs.
    """
    return [
        t["name"]
        for t in tool_registry.list_tools()
        if tool_registry.is_tool_allowed(t["name"], capability_mode=CAPABILITY_MODE)
    ]


# ---------------------------------------------------------------------------
# Lazy MCP import
# ---------------------------------------------------------------------------

def _import_mcp() -> tuple[Any | None, BaseException | None]:
    """Try to import FastMCP. Returns (FastMCP_class_or_None, error_or_None).

    Isolated as its own function so tests can monkeypatch the
    missing-dep branch even on machines where `mcp` IS installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
        return FastMCP, None
    except ImportError as e:
        return None, e


# ---------------------------------------------------------------------------
# Thin tool implementations
#
# Every function below is a plain Python callable. They're kept at module
# level so they're importable + testable without FastMCP. `build_server()`
# wires the registered ones into the MCP server only when the dep is
# present. None of these functions write files, run subprocesses, or touch
# the real repo — they only read metadata + artifacts under `.agent/`.
# ---------------------------------------------------------------------------

def _impl_get_health() -> dict:
    """Get cheap workspace health checks (env, DB, embeddings, etc.)."""
    from core.health import get_system_health
    return get_system_health()


def _impl_list_benchmark_reports(repo_path: str) -> list[dict]:
    """List benchmark report JSON files under .agent/benchmarks/ for a repo."""
    from core import benchmarks_view
    if not repo_path or not Path(repo_path).is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")
    return benchmarks_view.list_benchmark_reports(repo_path)


def _impl_read_benchmark_report(repo_path: str, filename: str) -> dict | None:
    """Read one benchmark report by filename (path-traversal guarded)."""
    from core import benchmarks_view
    if not repo_path or not Path(repo_path).is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise ValueError(f"invalid filename: {filename!r}")
    return benchmarks_view.read_benchmark_report(repo_path, filename)


def _impl_list_dream_reports(repo_path: str) -> list[dict]:
    """List Dream run artifacts under .agent/dreams/, newest first."""
    from core import dream_artifacts
    if not repo_path or not Path(repo_path).is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")
    return dream_artifacts.list_all_reports(repo_path)


def _impl_read_dream_report(repo_path: str, date: str, run: str = "") -> dict:
    """Read one Dream report by date (YYYY-MM-DD) and optional run id.

    Path-traversal guarded: date and run must match strict shapes; the
    resolved directory must stay inside .agent/dreams/.
    """
    from core import dream_artifacts

    if not repo_path or not Path(repo_path).is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_path}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""):
        raise ValueError(f"invalid date format: {date!r}")

    dreams_root = dream_artifacts.dreams_root(repo_path)
    if run:
        if not re.match(r"^\d{6}-run(-\d+)?$", run):
            raise ValueError(f"invalid run id: {run!r}")
        report_dir = dreams_root / date / run
    else:
        report_dir = dreams_root / date

    # Defensive: resolved path must stay inside dreams_root.
    try:
        report_dir.resolve().relative_to(dreams_root.resolve())
    except ValueError as e:
        raise ValueError("report path escapes dreams root") from e

    if not report_dir.is_dir():
        raise FileNotFoundError(
            f"no report for date={date}{(' run=' + run) if run else ' (legacy)'}"
        )
    return dream_artifacts.read_report(report_dir)


def _impl_list_lessons(status: str = "") -> list[dict]:
    """List lessons by status (candidate | active | blocked) or all if empty."""
    from core import lesson_store
    norm = (status or "").strip() or None
    if norm is not None and norm not in lesson_store.LESSON_STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    return lesson_store.list_lessons(status=norm)


_MAX_LESSON_PROPOSAL_BYTES = 512_000


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _impl_read_lesson_proposal(lesson_id: str) -> dict:
    """Read proposal.md backing a lesson by id. Path-traversal guarded.

    Mirrors the defensive logic of the /lessons/proposal route: resolves
    the lesson's source_report and refuses to read any file outside the
    allowed `.agent/proposals/` roots.
    """
    from core import lesson_store
    from config import get_agent_dir

    # Project root: two levels up from this file (mcp_server/ → repo root).
    _project_root = Path(__file__).resolve().parent.parent

    lid = (lesson_id or "").strip()
    if not lid:
        raise ValueError("lesson_id is required")

    record = next(
        (r for r in lesson_store.list_lessons() if r.get("id") == lid),
        None,
    )
    if record is None:
        raise LookupError(f"lesson not found: {lid}")

    raw = record.get("source_report")
    if not isinstance(raw, str) or not raw.strip():
        raise FileNotFoundError("lesson has no source_report")

    source_report = Path(raw.strip())
    if not source_report.is_absolute():
        source_report = _project_root / source_report
    try:
        proposal_dir = source_report.resolve()
    except OSError as e:
        raise FileNotFoundError("source_report path cannot be resolved") from e

    allowed_roots = [
        _project_root / ".agent" / "proposals",
        get_agent_dir(None) / "proposals",
    ]
    if not any(_path_is_inside(proposal_dir, root) for root in allowed_roots):
        raise ValueError("lesson source_report is outside allowed proposal roots")

    proposal_md = (proposal_dir / "proposal.md").resolve()
    if not _path_is_inside(proposal_md, proposal_dir):
        raise ValueError("proposal path escapes source_report")
    if not proposal_md.is_file():
        raise FileNotFoundError("proposal.md not found for this lesson")
    if proposal_md.stat().st_size > _MAX_LESSON_PROPOSAL_BYTES:
        raise ValueError("proposal.md is too large to display")

    return {
        "lesson_id": lid,
        "title": record.get("title") or "Untitled lesson",
        "proposal_path": str(proposal_md),
        "content": proposal_md.read_text(encoding="utf-8", errors="replace"),
    }


def _impl_list_worker_runs() -> list[dict]:
    """List worker run artifacts under .agent/worker_runs/."""
    from core import worker_runs
    return worker_runs.list_worker_runs()


def _impl_read_worker_run(run_id: str) -> dict:
    """Read one worker run by id (raw_output_preview capped at 2000 chars)."""
    from core import worker_runs
    rid = (run_id or "").strip()
    if not rid:
        raise ValueError("run_id is required")
    if "/" in rid or "\\" in rid or rid.startswith("."):
        # core.worker_runs._resolve_run_dir also defends, but keep an
        # outer guard so an obvious traversal attempt never even reaches it.
        raise ValueError(f"invalid run_id: {rid!r}")
    return worker_runs.read_worker_run(rid)


def _impl_list_tool_registry() -> list[dict]:
    """Return the full C.A.T.T.U.S tool registry as metadata (no execution)."""
    return tool_registry.list_tools()


# Tool name -> (implementation, optional description override).
# The dict keys must exactly match registry names; build_server() filters
# this down to the allowlist before wiring anything into MCP.
_IMPLS: dict[str, Callable[..., Any]] = {
    "get_health": _impl_get_health,
    "list_benchmark_reports": _impl_list_benchmark_reports,
    "read_benchmark_report": _impl_read_benchmark_report,
    "list_dream_reports": _impl_list_dream_reports,
    "read_dream_report": _impl_read_dream_report,
    "list_lessons": _impl_list_lessons,
    "read_lesson_proposal": _impl_read_lesson_proposal,
    "list_worker_runs": _impl_list_worker_runs,
    "read_worker_run": _impl_read_worker_run,
    "list_tool_registry": _impl_list_tool_registry,
}


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

    # Sanity assertion: never register a tool the registry says no to. This
    # is belt-and-suspenders over _IMPLS being a hand-maintained mapping.
    for name in list(_IMPLS.keys()):
        if name not in allowed:
            # Registry blocks this — skip silently. (Likely a registry
            # change made an _IMPLS entry stale; surfaces via tests.)
            continue
        impl = _IMPLS[name]
        meta = tool_registry.get_tool(name) or {}
        description = meta.get("description") or meta.get("title") or name
        # FastMCP's add_tool registers a plain callable as an MCP tool;
        # type hints on the impl become the input schema.
        server.add_tool(impl, name=name, description=description)

    return server


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint. Returns a process exit code.

    Recognized flags:
      --list-tools   Print the exposed read-only tool names (one per line)
                     and exit 0 without constructing or starting a server.
                     Does NOT require the `mcp` package to be installed.

    Exit codes:
      0 — server ran cleanly OR --list-tools printed successfully
      2 — `mcp` package not installed; friendly message printed to stderr
    """
    args = list(argv if argv is not None else sys.argv[1:])

    # --list-tools is a registry-only query. Handle it BEFORE any attempt
    # to import `mcp` — operators must be able to inspect the read-only
    # surface even on machines without the optional dependency.
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
