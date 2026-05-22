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


@pytest.fixture(autouse=True)
def _mute_audit_writes(monkeypatch):
    """Harness tests should not write the real .agent audit ledger."""
    from mcp_server import artifact_write

    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **_kwargs: None,
        raising=False,
    )


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


# ---- audit ledger ----------------------------------------------------------


def test_success_records_audit_event(tmp_path: Path, monkeypatch):
    from mcp_server import artifact_write

    events = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )

    result = artifact_write.create_handoff_note_harness(
        _valid_input(),
        handoff_root=tmp_path,
    )

    assert len(events) == 1
    assert events[0]["tool_name"] == "create_handoff_note"
    assert events[0]["capability_mode"] == "artifact_write"
    assert events[0]["allowed"] is True
    assert result["handoff_path"] in events[0]["artifacts"]


def test_failed_validation_records_blocked_audit_event(tmp_path: Path, monkeypatch):
    from mcp_server import artifact_write

    events = []
    monkeypatch.setattr(
        artifact_write,
        "record_mcp_invocation",
        lambda **kwargs: events.append(kwargs),
    )
    inp = _valid_input()
    inp["title"] = ""

    with pytest.raises(ValueError, match="title"):
        artifact_write.create_handoff_note_harness(inp, handoff_root=tmp_path)

    assert len(events) == 1
    assert events[0]["allowed"] is False
    assert events[0]["result_summary"] is None
    assert events[0]["artifacts"] == []
    assert "title" in events[0]["error"]


def test_audit_write_failure_does_not_change_success(tmp_path: Path, monkeypatch):
    from mcp_server import artifact_write

    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)

    result = artifact_write.create_handoff_note_harness(
        _valid_input(),
        handoff_root=tmp_path,
    )

    assert result["ok"] is True
    assert attempts["count"] == 1


def test_audit_write_failure_keeps_validation_error(tmp_path: Path, monkeypatch):
    from mcp_server import artifact_write

    attempts = {"count": 0}

    def _raise_audit_error(**_kwargs):
        attempts["count"] += 1
        raise OSError("audit offline")

    monkeypatch.setattr(artifact_write, "record_mcp_invocation", _raise_audit_error)
    inp = _valid_input()
    inp["title"] = ""

    with pytest.raises(ValueError, match="title"):
        artifact_write.create_handoff_note_harness(inp, handoff_root=tmp_path)
    assert attempts["count"] == 1


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


# ---- path safety: allowed_files / forbidden_files --------------------------


def test_allowed_files_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["../../etc/passwd"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_absolute_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["/etc/passwd"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_windows_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["..\\windows\\system32"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_forbidden_files_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["forbidden_files"] = ["../../secret"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_forbidden_files_absolute_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["forbidden_files"] = ["/etc/shadow"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_not_a_list_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = "src/main.py"  # string, not list
    with pytest.raises(ValueError, match="must be a list"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_non_string_entry_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = [123]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_allowed_files_single_dot_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["allowed_files"] = ["."]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


def test_forbidden_files_windows_traversal_rejected(tmp_path: Path):
    inp = _valid_input()
    inp["forbidden_files"] = ["..\\windows\\notepad.exe"]
    with pytest.raises(ValueError, match="safe relative path"):
        create_handoff_note_harness(inp, handoff_root=tmp_path)


# ---- isolation guarantees --------------------------------------------------


def test_harness_does_not_invoke_subprocess(tmp_path: Path, monkeypatch):
    """Tripwire: harness must never call subprocess.run / Popen / os.system."""
    import os
    import subprocess

    tripped = {"hit": False}

    def _trip(*_args, **_kwargs):
        tripped["hit"] = True
        raise AssertionError("harness must not invoke subprocess")

    monkeypatch.setattr(subprocess, "run", _trip)
    monkeypatch.setattr(subprocess, "Popen", _trip)
    monkeypatch.setattr(os, "system", _trip)

    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    assert result["ok"] is True
    assert tripped["hit"] is False


def test_harness_does_not_write_outside_handoff_root(tmp_path: Path):
    """After a valid call, exactly one new file exists under tmp_path and
    nothing else on disk was touched (within the test's observable surface)."""
    before = set(tmp_path.rglob("*"))
    result = create_handoff_note_harness(_valid_input(), handoff_root=tmp_path)
    after = set(tmp_path.rglob("*"))
    new = after - before
    # Exactly one new file (the .md note). No incidental dirs/files.
    new_files = {p for p in new if p.is_file()}
    assert len(new_files) == 1
    written = next(iter(new_files))
    assert written == Path(result["handoff_path"])
    # And the file is strictly inside tmp_path.
    written.resolve().relative_to(tmp_path.resolve())


def test_repo_path_not_written_to(tmp_path: Path):
    """repo_path is accepted as a string but the harness must never write
    to it. We point repo_path at a sibling directory and snapshot it
    before/after the call.
    """
    repo_dir = tmp_path / "fake_repo"
    repo_dir.mkdir()
    (repo_dir / "interest.cpp").write_text("// sentinel\n", encoding="utf-8")

    handoff_dir = tmp_path / "handoffs"
    handoff_dir.mkdir()

    snapshot_before = {
        p.relative_to(repo_dir): p.read_bytes()
        for p in repo_dir.rglob("*") if p.is_file()
    }

    inp = _valid_input()
    inp["repo_path"] = str(repo_dir)
    result = create_handoff_note_harness(inp, handoff_root=handoff_dir)
    assert result["ok"] is True

    snapshot_after = {
        p.relative_to(repo_dir): p.read_bytes()
        for p in repo_dir.rglob("*") if p.is_file()
    }
    assert snapshot_before == snapshot_after, "harness wrote to repo_path"
