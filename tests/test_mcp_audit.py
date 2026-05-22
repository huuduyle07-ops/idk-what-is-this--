"""Tests for the Phase 8.3 MCP invocation audit ledger."""
from __future__ import annotations

import json
from pathlib import Path


def _redirect_audit_root(monkeypatch, tmp_path: Path):
    from core import mcp_audit

    monkeypatch.setattr(
        mcp_audit,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    return mcp_audit


def test_record_mcp_invocation_appends_jsonl(tmp_path: Path, monkeypatch):
    mcp_audit = _redirect_audit_root(monkeypatch, tmp_path)

    event = mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=True,
        input_summary={"context_summary": "short summary"},
        result_summary={"ok": True},
        artifacts=["handoff.md"],
    )

    audit_path = tmp_path / ".agent" / "mcp_audit" / "invocations.jsonl"
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == event
    assert event["tool_name"] == "create_handoff_note"
    assert event["capability_mode"] == "artifact_write"
    assert event["allowed"] is True
    assert event["error"] is None
    assert set(event) == {
        "id",
        "created_at",
        "tool_name",
        "capability_mode",
        "allowed",
        "input_summary",
        "result_summary",
        "artifacts",
        "error",
    }


def test_record_mcp_invocation_writes_jsonl_per_event(tmp_path: Path, monkeypatch):
    mcp_audit = _redirect_audit_root(monkeypatch, tmp_path)

    mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=False,
        error="title is required",
    )
    mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=True,
    )

    audit_path = tmp_path / ".agent" / "mcp_audit" / "invocations.jsonl"
    parsed = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [event["allowed"] for event in parsed] == [False, True]


def test_context_summary_is_truncated_recursively(tmp_path: Path, monkeypatch):
    mcp_audit = _redirect_audit_root(monkeypatch, tmp_path)

    event = mcp_audit.record_mcp_invocation(
        tool_name="create_handoff_note",
        capability_mode="artifact_write",
        allowed=False,
        input_summary={"nested": {"context_summary": "x" * 900}},
        error="blocked",
    )

    context_summary = event["input_summary"]["nested"]["context_summary"]
    assert len(context_summary) <= 500
    assert context_summary.startswith("x" * 20)


def test_list_mcp_invocations_handles_missing_file(tmp_path: Path, monkeypatch):
    mcp_audit = _redirect_audit_root(monkeypatch, tmp_path)

    assert mcp_audit.list_mcp_invocations() == []


def test_list_mcp_invocations_handles_corrupt_lines(tmp_path: Path, monkeypatch):
    mcp_audit = _redirect_audit_root(monkeypatch, tmp_path)
    audit_path = tmp_path / ".agent" / "mcp_audit" / "invocations.jsonl"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(
        '{"id":"old"}\nnot-json\n["skip"]\n{"id":"new"}\n',
        encoding="utf-8",
    )

    events = mcp_audit.list_mcp_invocations()

    assert [event["id"] for event in events] == ["new", "old"]
