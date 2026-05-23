"""Phase 7.1 — unit tests for core/handoff_notes.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import handoff_notes


def test_module_constants_are_correct():
    assert handoff_notes.VALID_WORKERS == {"codex", "claude-code", "gemini", "other"}
    assert handoff_notes.VALID_TASK_TYPES == {
        "proposal_only",
        "review_only",
        "explain_only",
        "benchmark_case",
        "research",
    }
    assert handoff_notes.VALID_STATUSES == {"draft", "ran", "failed", "archived"}
    assert "proposal only" in handoff_notes.DEFAULT_SAFETY_RULES
    assert "do not commit" in handoff_notes.DEFAULT_SAFETY_RULES
    assert ".env" in handoff_notes.DEFAULT_FORBIDDEN_FILES
    assert ".agent" in handoff_notes.DEFAULT_FORBIDDEN_FILES


def test_slug_alphanumeric():
    assert handoff_notes._slug("Fix Flaky Fixtures!") == "fix-flaky-fixtures"


def test_slug_collapses_separators():
    assert handoff_notes._slug("foo___bar---baz") == "foo-bar-baz"


def test_slug_truncates_to_60_chars():
    long = "a" * 200
    assert len(handoff_notes._slug(long)) == 60


def test_slug_fallback_when_empty():
    assert handoff_notes._slug("!!!") == "handoff"


@pytest.fixture
def handoff_root(tmp_path: Path) -> Path:
    return tmp_path / "handoffs"


def test_create_handoff_note_writes_file_with_expected_metadata(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="Fix flaky fixtures",
        intended_worker="codex",
        task_type="proposal_only",
        repo_path=None,
        allowed_files=["core/foo.py"],
        validation_command="python -m pytest tests/test_foo.py -v",
        context_summary="The foo module fixtures are flaky.",
        expected_output="proposal.md and patch_plan.json",
        handoff_root=handoff_root,
    )

    assert result["meta"]["title"] == "Fix flaky fixtures"
    assert result["meta"]["intended_worker"] == "codex"
    assert result["meta"]["task_type"] == "proposal_only"
    assert result["meta"]["status"] == "draft"
    assert result["meta"]["owner"] == "human"
    assert result["meta"]["allowed_files"] == ["core/foo.py"]

    path = Path(result["path"])
    assert path.is_file()
    assert path.parent == handoff_root
    assert path.suffix == ".md"
    assert "fix-flaky-fixtures" in path.name


def test_create_handoff_note_includes_default_safety_rules(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=handoff_root,
    )
    rules = result["meta"]["safety_rules"]
    for required in handoff_notes.DEFAULT_SAFETY_RULES:
        assert required in rules


def test_create_handoff_note_merges_default_forbidden_files(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        forbidden_files=["my_secrets.txt"],
        handoff_root=handoff_root,
    )
    forbidden = set(result["meta"]["forbidden_files"])
    assert "my_secrets.txt" in forbidden
    for d in handoff_notes.DEFAULT_FORBIDDEN_FILES:
        assert d in forbidden


def test_create_handoff_note_records_safety_override_when_allowed_overlaps(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        allowed_files=["tests/test_foo.py"],
        handoff_root=handoff_root,
    )
    assert "tests/test_foo.py" in result["meta"]["safety_overrides"]
    assert "tests" in result["meta"]["safety_overrides"]
    assert "tests" not in result["meta"]["forbidden_files"]


def test_create_handoff_note_rejects_unknown_worker(handoff_root):
    with pytest.raises(ValueError, match="intended_worker"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="nope",
            task_type="proposal_only",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_unknown_task_type(handoff_root):
    with pytest.raises(ValueError, match="task_type"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="codex",
            task_type="bogus",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_empty_title(handoff_root):
    with pytest.raises(ValueError, match="title"):
        handoff_notes.create_handoff_note(
            title="   ",
            intended_worker="codex",
            task_type="proposal_only",
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_unsafe_allowed_file(handoff_root):
    with pytest.raises(ValueError, match="allowed_files"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="codex",
            task_type="proposal_only",
            allowed_files=["../escape.txt"],
            handoff_root=handoff_root,
        )


def test_create_handoff_note_rejects_unsafe_forbidden_file(handoff_root):
    with pytest.raises(ValueError, match="forbidden_files"):
        handoff_notes.create_handoff_note(
            title="t",
            intended_worker="codex",
            task_type="proposal_only",
            forbidden_files=["../escape.txt"],
            handoff_root=handoff_root,
        )


def test_create_handoff_note_body_contains_context_summary(handoff_root):
    result = handoff_notes.create_handoff_note(
        title="t",
        intended_worker="codex",
        task_type="proposal_only",
        context_summary="A unique context phrase ABC123",
        handoff_root=handoff_root,
    )
    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "A unique context phrase ABC123" in text
    assert "## Context summary" in text
    assert "HANDOFF_META" in text


def _create(handoff_root, *, title="t", **kwargs):
    return handoff_notes.create_handoff_note(
        title=title,
        intended_worker="codex",
        task_type="proposal_only",
        handoff_root=handoff_root,
        **kwargs,
    )


def test_list_handoff_notes_returns_newest_first(handoff_root):
    import time

    a = _create(handoff_root, title="first")
    time.sleep(1.1)  # ensure distinct YYYYMMDD_HHMMSS prefix
    b = _create(handoff_root, title="second")
    listing = handoff_notes.list_handoff_notes(handoff_root=handoff_root)
    assert len(listing) == 2
    assert listing[0]["path"] == b["path"]
    assert listing[1]["path"] == a["path"]


def test_list_handoff_notes_excludes_archived_by_default(handoff_root):
    a = _create(handoff_root, title="keep")
    b = _create(handoff_root, title="archived")
    handoff_notes.update_handoff_status(b["path"], "archived", handoff_root=handoff_root)
    visible = handoff_notes.list_handoff_notes(handoff_root=handoff_root)
    paths = [item["path"] for item in visible]
    assert a["path"] in paths
    assert b["path"] not in paths

    everything = handoff_notes.list_handoff_notes(
        handoff_root=handoff_root, include_archived=True
    )
    paths = [item["path"] for item in everything]
    assert b["path"] in paths


def test_read_handoff_note_returns_meta_and_body(handoff_root):
    result = _create(handoff_root, title="readme", context_summary="hello")
    parsed = handoff_notes.read_handoff_note(result["path"], handoff_root=handoff_root)
    assert parsed["meta"]["title"] == "readme"
    assert "hello" in parsed["body"]


def test_read_handoff_note_blocks_path_traversal(handoff_root, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("not a handoff", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        handoff_notes.read_handoff_note(str(outside), handoff_root=handoff_root)


def test_update_handoff_status_writes_new_meta(handoff_root):
    result = _create(handoff_root, title="status-test")
    handoff_notes.update_handoff_status(result["path"], "ran", handoff_root=handoff_root)
    parsed = handoff_notes.read_handoff_note(result["path"], handoff_root=handoff_root)
    assert parsed["meta"]["status"] == "ran"


def test_update_handoff_status_rejects_unknown_status(handoff_root):
    result = _create(handoff_root, title="status-bad")
    with pytest.raises(ValueError, match="status"):
        handoff_notes.update_handoff_status(result["path"], "weird", handoff_root=handoff_root)

# ---------------------------------------------------------------------------
# resolve_handoff_note tests
# ---------------------------------------------------------------------------

def test_resolve_handoff_note_filename(tmp_path):
    root = tmp_path / "handoffs"
    root.mkdir()
    note = root / "20260522_183942_foo.md"
    note.write_text("x", encoding="utf-8")
    result = handoff_notes.resolve_handoff_note("20260522_183942_foo.md", handoff_root=root)
    assert result == note.resolve()


def test_resolve_handoff_note_absolute_inside(tmp_path):
    root = tmp_path / "handoffs"
    root.mkdir()
    note = root / "foo.md"
    note.write_text("x", encoding="utf-8")
    result = handoff_notes.resolve_handoff_note(str(note), handoff_root=root)
    assert result == note.resolve()


def test_resolve_handoff_note_absolute_outside_rejected(tmp_path):
    root = tmp_path / "handoffs"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        handoff_notes.resolve_handoff_note(str(outside), handoff_root=root)


def test_resolve_handoff_note_traversal_rejected(tmp_path):
    root = tmp_path / "handoffs"
    root.mkdir()
    with pytest.raises(ValueError):
        handoff_notes.resolve_handoff_note("../../etc/passwd", handoff_root=root)


def test_resolve_handoff_note_empty_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        handoff_notes.resolve_handoff_note("")


def test_resolve_handoff_note_not_found(tmp_path):
    root = tmp_path / "handoffs"
    root.mkdir()
    with pytest.raises(FileNotFoundError):
        handoff_notes.resolve_handoff_note("nonexistent.md", handoff_root=root)


def test_list_handoff_notes_includes_handoff_id(tmp_path):
    root = tmp_path / "handoffs"
    result = _create(root, title="id-check")
    listing = handoff_notes.list_handoff_notes(handoff_root=root)
    assert len(listing) == 1
    item = listing[0]
    assert "handoff_id" in item
    # handoff_id must be just the filename — no path separators
    assert "/" not in item["handoff_id"]
    assert "\\" not in item["handoff_id"]
    assert item["handoff_id"].endswith(".md")
    assert item["handoff_id"] == Path(result["path"]).name


def test_create_handoff_cli_writes_a_note(tmp_path, monkeypatch, capsys):
    from scripts import create_handoff_note as cli

    monkeypatch.setattr(handoff_notes, "DEFAULT_HANDOFF_ROOT", tmp_path / "handoffs")
    monkeypatch.setattr(
        "sys.argv",
        [
            "create_handoff_note.py",
            "--title", "CLI test",
            "--worker", "codex",
            "--task-type", "proposal_only",
            "--context-summary", "from CLI",
            "--validation-command", "echo ok",
            "--allowed-file", "core/foo.py",
            "--allowed-file", "tests/test_foo.py",
        ],
    )
    rc = cli.main()
    assert rc == 0

    listing = handoff_notes.list_handoff_notes(handoff_root=tmp_path / "handoffs")
    assert len(listing) == 1
    assert listing[0]["title"] == "CLI test"
    captured = capsys.readouterr()
    assert "handoffs" in captured.out


# ---------------------------------------------------------------------------
# Output-contract tests
# ---------------------------------------------------------------------------

def test_handoff_note_body_contains_proposal_md_requirement(handoff_root):
    """The generated handoff note must mention proposal.md as a required file."""
    result = _create(handoff_root, title="contract-test")
    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "proposal.md" in text


def test_handoff_note_body_contains_patch_plan_json_requirement(handoff_root):
    """The generated handoff note must mention patch_plan.json as a required file."""
    result = _create(handoff_root, title="contract-test-2")
    text = Path(result["path"]).read_text(encoding="utf-8")
    assert "patch_plan.json" in text


def test_handoff_note_body_warns_against_stdout_only(handoff_root):
    """The generated handoff note must explicitly instruct the worker not to
    print the proposal to stdout only."""
    result = _create(handoff_root, title="contract-test-3")
    text = Path(result["path"]).read_text(encoding="utf-8")
    # The exact phrasing lives in _OUTPUT_CONTRACT_LINES; check the key words.
    assert "stdout" in text.lower()
    assert "Do NOT only print" in text or "do not only print" in text.lower()