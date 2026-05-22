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


# ---- input validation: rejections ------------------------------------------


def test_title_empty_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = ""
    with pytest.raises(ValueError, match="title"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_title_whitespace_only_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = "   \t  "
    with pytest.raises(ValueError, match="title"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_title_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = "x" * 201
    with pytest.raises(ValueError, match="title.*200"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_context_summary_empty_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["context_summary"] = ""
    with pytest.raises(ValueError, match="context_summary"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_context_summary_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["context_summary"] = "x" * 8001
    with pytest.raises(ValueError, match="context_summary.*8000"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_invalid_worker_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["intended_worker"] = "hacker"
    with pytest.raises(ValueError, match="intended_worker"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_invalid_task_type_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["task_type"] = "rm-rf"
    with pytest.raises(ValueError, match="task_type"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_unknown_field_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["shell"] = "rm -rf /"
    with pytest.raises(ValueError, match="unknown field"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_validation_command_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["validation_command"] = "x" * 501
    with pytest.raises(ValueError, match="validation_command.*500"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_expected_output_too_long_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["expected_output"] = "x" * 4001
    with pytest.raises(ValueError, match="expected_output.*4000"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_non_dict_input_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="must be a dict"):
        create_handoff_note_harness("not a dict", handoff_root=tmp_path)


def test_non_string_title_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["title"] = 42
    with pytest.raises(ValueError, match="title must be a string"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_non_string_context_summary_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["context_summary"] = ["a", "list"]
    with pytest.raises(ValueError, match="context_summary must be a string"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)
