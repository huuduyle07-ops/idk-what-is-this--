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
    assert "tests/test_foo.py" not in [
        p for p in result["meta"]["forbidden_files"] if p == "tests/test_foo.py"
    ]


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
