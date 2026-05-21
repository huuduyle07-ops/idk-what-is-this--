"""Phase 8.1 — MCP server packages for C.A.T.T.U.S.

This package never imports a real MCP runtime at module load time. The
read-only server is in `mcp_server.read_only`; the heavy `mcp` SDK import
is deferred to `build_server()` so the allowlist/contract can be inspected
on machines that don't have the optional dependency installed.
"""
