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
