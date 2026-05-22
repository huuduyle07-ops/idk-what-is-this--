"""Phase 8.2a — tests for create_handoff_note_harness.

Tests the MCP-facing dict-in/dict-out wrapper around
core.handoff_notes.create_handoff_note. Uses tmp_path + the keyword-only
handoff_root arg so no test writes into the real .agent/handoffs/ dir.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from mcp_server.artifact_write import create_handoff_note_harness


def _valid_input() -> dict:
    """Returns a fresh dict of valid input for use as a baseline."""
    return {
        "title": "Refactor compute_compound_interest",
        "intended_worker": "codex",
        "task_type": "proposal_only",
        "context_summary": (
            "compute_compound_interest in interest.cpp accepts negative inputs."
            " Add validation per the case spec."
        ),
    }


# ---- happy path ------------------------------------------------------------


def test_valid_input_writes_file(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["ok"] is True
    handoff_path = Path(result["handoff_path"])
    assert handoff_path.is_file()
    # File lives strictly under tmp_path.
    assert handoff_path.resolve().is_relative_to(tmp_path.resolve())
    # Filename matches handoff_notes convention: YYYYMMDD_HHMMSS_<slug>.md.
    assert re.match(r"^\d{8}_\d{6}_.+\.md$", handoff_path.name)


def test_message_text_is_exact(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["message"] == "Handoff note created. This did not run a subagent."


def test_status_is_draft(tmp_path: Path):
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["status"] == "draft"


def test_default_safety_rules_applied(tmp_path: Path):
    """The harness must never override the do-not-apply/commit/push defaults."""
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    text = Path(result["handoff_path"]).read_text(encoding="utf-8")
    match = re.search(
        r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->", text, re.DOTALL
    )
    assert match, "HANDOFF_META block missing"
    meta = json.loads(match.group("json"))
    rules = meta.get("safety_rules", [])
    assert "do not apply patch" in rules
    assert "do not commit" in rules
    assert "do not push" in rules


def test_default_forbidden_files_applied(tmp_path: Path):
    """The harness must inherit the default forbidden_files list."""
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    text = Path(result["handoff_path"]).read_text(encoding="utf-8")
    match = re.search(
        r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->", text, re.DOTALL
    )
    assert match, "HANDOFF_META block missing"
    meta = json.loads(match.group("json"))
    forbidden = meta.get("forbidden_files", [])
    for required in (".env", ".git", ".agent"):
        assert required in forbidden, f"{required} should be in forbidden_files"
