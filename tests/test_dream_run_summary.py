"""Tests for core.dream_artifacts.write_dream_run_summary (Phase 11-prep-cleanup-a)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from core import dream_artifacts


def _make_item(idx=1, kind="bug", title="Slow case", status="planned_no_patch",
               hint="", item_dir_name="", summary=""):
    return {"idx": idx, "kind": kind, "title": title, "status": status,
            "hint": hint, "item_dir_name": item_dir_name, "summary": summary}


def test_write_dream_run_summary_creates_md_file(tmp_path):
    """Output file must be dream_run_summary.md — not morning_report.txt."""
    p = dream_artifacts.write_dream_run_summary(tmp_path, [_make_item()])
    assert p.name == "dream_run_summary.md"
    assert (tmp_path / "dream_run_summary.md").is_file()
    assert not (tmp_path / "morning_report.txt").is_file()


def test_dream_run_summary_content_sections(tmp_path):
    """File must contain the required top-level headings."""
    items = [_make_item(status="planned_no_patch")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "# Dream run summary" in text
    assert "## Summary" in text
    assert "## Items" in text
    assert "## Next steps" in text


def test_dream_run_summary_includes_root_cause_from_hint(tmp_path):
    """A non-empty hint must appear under 'suspected root cause'."""
    items = [_make_item(hint="off-by-one in loop condition")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "suspected root cause" in text
    assert "off-by-one in loop condition" in text


def test_dream_run_summary_includes_candidate_lesson_text(tmp_path):
    """lesson_notes kwarg must produce a ## Candidate lessons section."""
    items = [_make_item()]
    dream_artifacts.write_dream_run_summary(
        tmp_path, items, lesson_notes=["always validate loop bounds"]
    )
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "## Candidate lessons" in text
    assert "always validate loop bounds" in text


def test_dream_run_summary_includes_evidence_link(tmp_path):
    """item_dir_name must produce a Markdown link, not a bare backtick string."""
    items = [_make_item(item_dir_name="01-slow-case")]
    dream_artifacts.write_dream_run_summary(tmp_path, items)
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "[01-slow-case/](./01-slow-case/)" in text


def test_dream_run_summary_no_candidate_lessons_section_when_empty(tmp_path):
    """No ## Candidate lessons section when lesson_notes is None or []."""
    dream_artifacts.write_dream_run_summary(tmp_path, [_make_item()])
    text = (tmp_path / "dream_run_summary.md").read_text(encoding="utf-8")
    assert "## Candidate lessons" not in text


def test_read_report_falls_back_to_morning_report_txt(tmp_path):
    """Legacy dirs that only have morning_report.txt must still load."""
    (tmp_path / "morning_report.txt").write_text("# Legacy report\n", encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    data = dream_artifacts.read_report(tmp_path)
    assert data["morning_report"] == "# Legacy report\n"


def test_read_report_prefers_dream_run_summary_md(tmp_path):
    """When both files exist, dream_run_summary.md takes precedence."""
    (tmp_path / "morning_report.txt").write_text("OLD", encoding="utf-8")
    (tmp_path / "dream_run_summary.md").write_text("NEW", encoding="utf-8")
    (tmp_path / "list.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    data = dream_artifacts.read_report(tmp_path)
    assert data["morning_report"] == "NEW"
