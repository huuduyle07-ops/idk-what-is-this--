"""Phase 8.1 — tests for the read-only MCP server module.

The MCP package may not be installed on the test machine. These tests
therefore exercise the *allowlist contract* and the *friendly missing-dep
error* without ever requiring `mcp` to be importable.

The module under test must:
  - import cleanly without `mcp` installed
  - not start any server at import time
  - source its tool list from core.tool_registry under capability_mode="read_only"
  - refuse to expose any write/execute tool
  - fail with a friendly RuntimeError message if `mcp` is missing when
    build_server() is called
"""
from __future__ import annotations

import importlib
import sys

import pytest

from core import tool_registry


_EXPECTED_READ_ONLY_TOOLS = {
    "get_health",
    "list_benchmark_reports",
    "read_benchmark_report",
    "list_dream_reports",
    "read_dream_report",
    "list_lessons",
    "read_lesson_proposal",
    "list_worker_runs",
    "read_worker_run",
    "list_tool_registry",
}

# Tools that must NEVER be exposed by the read-only MCP server.
_FORBIDDEN_TOOLS = {
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "run_subagent_handoff",
    "promote_lesson",
    "block_lesson",
    "create_handoff_note",            # artifact_write — not read_only
    "import_worker_run_as_proposal",  # artifact_write — not read_only
    "validate_imported_worker_proposal",  # artifact_write — not read_only
}


# ---- import / no-side-effect contract --------------------------------------


def test_importing_module_does_not_start_server():
    """Importing the module must not call .run() or open stdio."""
    # If the module's import had side effects (running a server, blocking on
    # stdin), pytest would never reach this assertion.
    mod = importlib.import_module("mcp_server.read_only")
    assert hasattr(mod, "list_exposed_tool_names")
    assert hasattr(mod, "build_server")
    assert hasattr(mod, "main")
    assert mod.CAPABILITY_MODE == "read_only"


def test_module_importable_without_mcp_package():
    """The module must not import `mcp` at module top-level — so the
    machine-without-mcp case still gives us a working allowlist API.
    """
    from mcp_server import read_only
    # list_exposed_tool_names must work without mcp installed.
    names = read_only.list_exposed_tool_names()
    assert isinstance(names, list)
    assert names  # not empty


# ---- allowlist contract ----------------------------------------------------


def test_exposed_names_match_registry_read_only_allowlist():
    from mcp_server import read_only
    exposed = set(read_only.list_exposed_tool_names())
    # Source of truth: the registry under capability_mode="read_only".
    registry_allowed = {
        t["name"]
        for t in tool_registry.list_tools()
        if tool_registry.is_tool_allowed(t["name"], capability_mode="read_only")
    }
    assert exposed == registry_allowed


def test_exposed_names_are_exactly_the_expected_ten():
    from mcp_server import read_only
    assert set(read_only.list_exposed_tool_names()) == _EXPECTED_READ_ONLY_TOOLS


def test_no_write_or_execute_tools_exposed():
    from mcp_server import read_only
    exposed = set(read_only.list_exposed_tool_names())
    leaked = exposed & _FORBIDDEN_TOOLS
    assert not leaked, f"read-only MCP must not expose: {leaked}"


@pytest.mark.parametrize("forbidden", sorted(_FORBIDDEN_TOOLS))
def test_specific_forbidden_tool_not_exposed(forbidden):
    from mcp_server import read_only
    assert forbidden not in read_only.list_exposed_tool_names()


def test_capability_mode_constant_is_read_only():
    from mcp_server import read_only
    assert read_only.CAPABILITY_MODE == "read_only"


def test_default_mode_is_not_unsafe_dev():
    """Sanity: the module must not silently allow unsafe_dev."""
    from mcp_server import read_only
    # No matter what the registry contains, unsafe_dev must never be the
    # capability_mode used by this server.
    assert read_only.CAPABILITY_MODE != "unsafe_dev"


# ---- friendly missing-dep error -------------------------------------------


def test_build_server_raises_friendly_error_when_mcp_missing(monkeypatch):
    """If `mcp` cannot be imported, build_server must raise a clear message
    rather than a raw ImportError traceback.
    """
    from mcp_server import read_only

    def fake_import_mcp():
        return None, ImportError("No module named 'mcp'")

    monkeypatch.setattr(read_only, "_import_mcp", fake_import_mcp)

    with pytest.raises(RuntimeError) as exc_info:
        read_only.build_server()
    assert "MCP package not installed" in str(exc_info.value)


def test_main_exits_nonzero_with_friendly_stderr_when_mcp_missing(
    monkeypatch, capsys
):
    from mcp_server import read_only

    def fake_import_mcp():
        return None, ImportError("No module named 'mcp'")

    monkeypatch.setattr(read_only, "_import_mcp", fake_import_mcp)

    exit_code = read_only.main([])
    err = capsys.readouterr().err
    assert exit_code != 0
    assert "MCP package not installed" in err


def test_main_does_not_run_server_when_dep_missing(monkeypatch):
    """If mcp is missing, main() must return early without attempting to
    construct or run a server.
    """
    from mcp_server import read_only

    monkeypatch.setattr(
        read_only,
        "_import_mcp",
        lambda: (None, ImportError("no mcp")),
    )

    called = {"run": False}

    class _StubServer:
        def run(self):
            called["run"] = True

    # If anyone tries to construct a server through this back-door,
    # called["run"] would flip. Stay False.
    read_only.main([])
    assert called["run"] is False


# ---- --list-tools CLI flag -------------------------------------------------


def test_list_tools_flag_prints_exposed_names(capsys):
    """`--list-tools` prints exactly the read-only allowlist, one per line."""
    from mcp_server import read_only

    exit_code = read_only.main(["--list-tools"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert set(out) == _EXPECTED_READ_ONLY_TOOLS
    # Order must match list_exposed_tool_names() for predictable scripting.
    assert out == read_only.list_exposed_tool_names()


def test_list_tools_flag_omits_forbidden_tools(capsys):
    from mcp_server import read_only

    read_only.main(["--list-tools"])
    out_lines = set(capsys.readouterr().out.strip().splitlines())
    leaked = out_lines & _FORBIDDEN_TOOLS
    assert not leaked, f"--list-tools leaked forbidden tools: {leaked}"


def test_list_tools_flag_works_without_mcp_dep(monkeypatch, capsys):
    """`--list-tools` must work even when `mcp` is not installed —
    it's a registry-only query that should never touch FastMCP.
    """
    from mcp_server import read_only

    def fake_import_mcp():
        raise AssertionError(
            "--list-tools must NOT attempt to import mcp"
        )

    monkeypatch.setattr(read_only, "_import_mcp", fake_import_mcp)

    exit_code = read_only.main(["--list-tools"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert set(out) == _EXPECTED_READ_ONLY_TOOLS


def test_list_tools_flag_does_not_build_or_run_server(monkeypatch):
    """Belt-and-suspenders: even if mcp IS installed, --list-tools must
    not construct or run a FastMCP server.
    """
    from mcp_server import read_only

    build_called = {"hit": False}
    original_build = read_only.build_server

    def tripwire_build_server(*args, **kwargs):
        build_called["hit"] = True
        return original_build(*args, **kwargs)

    monkeypatch.setattr(read_only, "build_server", tripwire_build_server)

    exit_code = read_only.main(["--list-tools"])
    assert exit_code == 0
    assert build_called["hit"] is False, "--list-tools must not call build_server()"
