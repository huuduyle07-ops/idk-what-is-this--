"""Phase 8.1 — launcher for the read-only MCP server.

Usage:
    python scripts/mcp_readonly_server.py

This is a thin shim that delegates to `mcp_server.read_only.main`. It
exists so the entrypoint is discoverable under `scripts/` alongside the
other operator scripts; the real implementation (allowlist, tool
wrappers, friendly missing-dep error) lives in the `mcp_server` package.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    """Allow `python scripts/mcp_readonly_server.py` to work from anywhere."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def main() -> int:
    _ensure_project_root_on_path()
    from mcp_server.read_only import main as _server_main
    return _server_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
