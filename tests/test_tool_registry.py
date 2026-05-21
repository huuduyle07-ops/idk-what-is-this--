"""Phase 8-prep — unit tests for core/tool_registry.py."""
from __future__ import annotations

import pytest

from core import tool_registry


_REQUIRED_KEYS = {
    "name",
    "title",
    "description",
    "category",
    "phase",
    "reads",
    "writes",
    "can_touch_real_repo",
    "can_run_subprocess",
    "requires_human_approval",
    "mcp_exposable",
    "default_enabled",
    "route_or_function",
    "notes",
}

_EXPECTED_READ_TOOLS = {
    "get_health",
    "list_benchmark_reports",
    "read_benchmark_report",
    "list_dream_reports",
    "read_dream_report",
    "list_lessons",
    "read_lesson_proposal",
    "list_worker_runs",
    "read_worker_run",
    "list_tool_registry",  # Phase 8.1
}

_EXPECTED_ARTIFACT_WRITE_TOOLS = {
    "create_handoff_note",
    "import_worker_run_as_proposal",
    "validate_imported_worker_proposal",
}

_EXPECTED_DISABLED_TOOLS = {
    "apply_patch",
    "apply_patch_plan",
    "dream_apply",
    "run_subagent_handoff",
    "promote_lesson",
    "block_lesson",
}


# ---- list_tools ------------------------------------------------------------


def test_list_tools_returns_initial_set():
    tools = tool_registry.list_tools()
    names = {t["name"] for t in tools}
    assert names == _EXPECTED_READ_TOOLS | _EXPECTED_ARTIFACT_WRITE_TOOLS | _EXPECTED_DISABLED_TOOLS
    assert len(tools) == 19

    for t in tools:
        missing = _REQUIRED_KEYS - set(t.keys())
        assert not missing, f"{t['name']} missing keys: {missing}"
        assert t["category"] in tool_registry.VALID_CATEGORIES
        assert isinstance(t["reads"], list)
        assert isinstance(t["writes"], list)
        assert isinstance(t["can_touch_real_repo"], bool)
        assert isinstance(t["can_run_subprocess"], bool)
        assert isinstance(t["requires_human_approval"], bool)
        assert isinstance(t["mcp_exposable"], bool)
        assert isinstance(t["default_enabled"], bool)


def test_list_tools_returns_copies():
    first = tool_registry.list_tools()
    first[0]["name"] = "MUTATED"
    first[0]["reads"].append("MUTATED_READ")
    second = tool_registry.list_tools()
    assert second[0]["name"] != "MUTATED"
    assert "MUTATED_READ" not in second[0]["reads"]


# ---- get_tool --------------------------------------------------------------


def test_get_tool_known():
    t = tool_registry.get_tool("get_health")
    assert t is not None
    assert t["name"] == "get_health"
    assert t["category"] == "read"


def test_get_tool_unknown_returns_none():
    assert tool_registry.get_tool("does_not_exist") is None


def test_get_tool_returns_copy():
    a = tool_registry.get_tool("get_health")
    a["name"] = "MUTATED"
    b = tool_registry.get_tool("get_health")
    assert b["name"] == "get_health"


# ---- tools_by_category -----------------------------------------------------


def test_tools_by_category_read_returns_ten():
    reads = tool_registry.tools_by_category("read")
    assert {t["name"] for t in reads} == _EXPECTED_READ_TOOLS


def test_tools_by_category_artifact_write_returns_three():
    aw = tool_registry.tools_by_category("artifact_write")
    assert {t["name"] for t in aw} == _EXPECTED_ARTIFACT_WRITE_TOOLS


def test_tools_by_category_real_repo_write_returns_three():
    rrw = tool_registry.tools_by_category("real_repo_write")
    assert {t["name"] for t in rrw} == {"apply_patch", "apply_patch_plan", "dream_apply"}


def test_tools_by_category_invalid_raises():
    with pytest.raises(ValueError, match="category"):
        tool_registry.tools_by_category("nonsense_category")


# ---- is_tool_allowed: read_only mode ---------------------------------------


def test_read_only_allows_read_tools():
    for name in _EXPECTED_READ_TOOLS:
        assert tool_registry.is_tool_allowed(name, "read_only"), f"{name} should be allowed in read_only"


def test_read_only_blocks_artifact_write():
    assert tool_registry.is_tool_allowed("create_handoff_note", "read_only") is False
    assert tool_registry.is_tool_allowed("import_worker_run_as_proposal", "read_only") is False


def test_read_only_blocks_real_repo_write():
    assert tool_registry.is_tool_allowed("apply_patch", "read_only") is False
    assert tool_registry.is_tool_allowed("dream_apply", "read_only") is False


def test_read_only_blocks_disabled_mcp_tools():
    for name in _EXPECTED_DISABLED_TOOLS:
        assert tool_registry.is_tool_allowed(name, "read_only") is False, \
            f"{name} is mcp_exposable=False and should be blocked"


# ---- is_tool_allowed: artifact_write mode ----------------------------------


def test_artifact_write_allows_read():
    assert tool_registry.is_tool_allowed("get_health", "artifact_write") is True


def test_artifact_write_allows_artifact_write_tools():
    assert tool_registry.is_tool_allowed("create_handoff_note", "artifact_write") is True
    assert tool_registry.is_tool_allowed("import_worker_run_as_proposal", "artifact_write") is True
    assert tool_registry.is_tool_allowed("validate_imported_worker_proposal", "artifact_write") is True


def test_artifact_write_blocks_real_repo_write():
    assert tool_registry.is_tool_allowed("apply_patch", "artifact_write") is False
    assert tool_registry.is_tool_allowed("apply_patch_plan", "artifact_write") is False
    assert tool_registry.is_tool_allowed("dream_apply", "artifact_write") is False


def test_artifact_write_blocks_memory_write():
    assert tool_registry.is_tool_allowed("promote_lesson", "artifact_write") is False
    assert tool_registry.is_tool_allowed("block_lesson", "artifact_write") is False


# ---- is_tool_allowed: operator mode ----------------------------------------


def test_operator_allows_read_and_artifact_write():
    assert tool_registry.is_tool_allowed("get_health", "operator") is True
    assert tool_registry.is_tool_allowed("create_handoff_note", "operator") is True


def test_operator_blocks_real_repo_write_even_with_approval():
    # apply_patch has requires_human_approval=True but is real_repo_write —
    # operator mode never includes real_repo_write.
    assert tool_registry.is_tool_allowed("apply_patch", "operator") is False
    assert tool_registry.is_tool_allowed("dream_apply", "operator") is False


def test_operator_blocks_disabled_mcp_tools():
    # Even with the right category, mcp_exposable=False is a kill switch
    # outside unsafe_dev mode.
    for name in _EXPECTED_DISABLED_TOOLS:
        assert tool_registry.is_tool_allowed(name, "operator") is False


# ---- is_tool_allowed: unsafe_dev mode --------------------------------------


def test_unsafe_dev_allows_everything_including_disabled_tools():
    # unsafe_dev is the "metadata-only debug" mode; it ignores mcp_exposable.
    # Useful for internal dashboards listing every registered tool.
    for name in (_EXPECTED_READ_TOOLS | _EXPECTED_ARTIFACT_WRITE_TOOLS | _EXPECTED_DISABLED_TOOLS):
        assert tool_registry.is_tool_allowed(name, "unsafe_dev") is True, \
            f"unsafe_dev should allow {name}"


# ---- is_tool_allowed: error and edge cases ---------------------------------


def test_is_tool_allowed_unknown_tool_returns_false():
    assert tool_registry.is_tool_allowed("does_not_exist", "read_only") is False
    assert tool_registry.is_tool_allowed("", "read_only") is False


def test_is_tool_allowed_invalid_mode_raises():
    with pytest.raises(ValueError, match="capability_mode"):
        tool_registry.is_tool_allowed("get_health", "bogus_mode")


# ---- Invariants on the registered tools ------------------------------------


def test_real_repo_write_tools_have_can_touch_real_repo_true():
    for t in tool_registry.tools_by_category("real_repo_write"):
        assert t["can_touch_real_repo"] is True, \
            f"{t['name']} is real_repo_write but can_touch_real_repo is False"


def test_disabled_for_mcp_tools_have_mcp_exposable_false():
    for name in _EXPECTED_DISABLED_TOOLS:
        t = tool_registry.get_tool(name)
        assert t["mcp_exposable"] is False, \
            f"{name} should have mcp_exposable=False"
        assert t["default_enabled"] is False, \
            f"{name} should have default_enabled=False"


def test_read_tools_do_not_touch_real_repo_or_run_subprocess():
    for t in tool_registry.tools_by_category("read"):
        assert t["can_touch_real_repo"] is False, f"{t['name']} read tool can_touch_real_repo"
        assert t["can_run_subprocess"] is False, f"{t['name']} read tool can_run_subprocess"
