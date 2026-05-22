"""Phase 8.2a — tests for the artifact-write MCP server module.

Mirrors tests/test_mcp_readonly_server.py. The MCP package may not be
installed on the test machine; tests exercise the allowlist contract and
friendly missing-dep error without ever requiring `mcp` to be importable.
"""
from __future__ import annotations

import importlib

import pytest

from core import tool_registry


_EXPECTED_EXPOSED_TOOLS = {
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
    "create_handoff_note",
}

# Tools that must NEVER be exposed by the artifact-write MCP server.
_FORBIDDEN_TOOLS = {
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
    "run_subagent_handoff",
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "promote_lesson",
    "block_lesson",
}


# ---- import / no-side-effect contract --------------------------------------


def test_importing_module_does_not_start_server():
    mod = importlib.import_module("mcp_server.artifact_write")
    assert hasattr(mod, "list_exposed_tool_names")
    assert hasattr(mod, "create_handoff_note_harness")
    assert hasattr(mod, "CAPABILITY_MODE")


def test_module_importable_without_mcp_package():
    from mcp_server import artifact_write
    names = artifact_write.list_exposed_tool_names()
    assert isinstance(names, list)
    assert names  # not empty


def test_capability_mode_constant_is_artifact_write():
    from mcp_server import artifact_write
    assert artifact_write.CAPABILITY_MODE == "artifact_write"
    assert artifact_write.CAPABILITY_MODE != "unsafe_dev"


# ---- allowlist contract ----------------------------------------------------


def test_exposed_names_are_exactly_eleven():
    from mcp_server import artifact_write
    assert set(artifact_write.list_exposed_tool_names()) == _EXPECTED_EXPOSED_TOOLS
    assert len(artifact_write.list_exposed_tool_names()) == 11


def test_create_handoff_note_is_exposed():
    from mcp_server import artifact_write
    assert "create_handoff_note" in artifact_write.list_exposed_tool_names()


@pytest.mark.parametrize("forbidden", sorted(_FORBIDDEN_TOOLS))
def test_specific_forbidden_tool_not_exposed(forbidden):
    from mcp_server import artifact_write
    assert forbidden not in artifact_write.list_exposed_tool_names()


def test_read_only_server_still_omits_create_handoff_note():
    """Cross-server regression: the read-only server must not gain
    create_handoff_note just because the artifact-write module exists."""
    from mcp_server import read_only
    assert "create_handoff_note" not in read_only.list_exposed_tool_names()
    # And the read-only server should still expose exactly 10.
    assert len(read_only.list_exposed_tool_names()) == 10

# ---- friendly missing-dep error -------------------------------------------


def test_build_server_raises_friendly_error_when_mcp_missing(monkeypatch):
    from mcp_server import artifact_write

    def fake_import_mcp():
        return None, ImportError("No module named 'mcp'")

    monkeypatch.setattr(artifact_write, "_import_mcp", fake_import_mcp)

    with pytest.raises(RuntimeError) as exc_info:
        artifact_write.build_server()
    assert "MCP package not installed" in str(exc_info.value)


def test_main_exits_nonzero_with_friendly_stderr_when_mcp_missing(
    monkeypatch, capsys
):
    from mcp_server import artifact_write

    monkeypatch.setattr(
        artifact_write,
        "_import_mcp",
        lambda: (None, ImportError("no mcp")),
    )

    exit_code = artifact_write.main([])
    err = capsys.readouterr().err
    assert exit_code == 2
    assert "MCP package not installed" in err


def test_main_does_not_run_server_when_dep_missing(monkeypatch):
    from mcp_server import artifact_write

    monkeypatch.setattr(
        artifact_write,
        "_import_mcp",
        lambda: (None, ImportError("no mcp")),
    )

    called = {"run": False}

    class _StubServer:
        def run(self):
            called["run"] = True

    artifact_write.main([])
    assert called["run"] is False