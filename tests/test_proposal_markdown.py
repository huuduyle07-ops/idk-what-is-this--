"""Tests for the enriched proposal.md template (Phase 5 Polish).

Locks in the four tutor sections — what was wrong, why it works, concept,
patterns to watch for — that the roadmap's "post-patch explanation card"
asks for. Pure markdown construction, no LLM, no disk writes.
"""
from __future__ import annotations

from scripts.run_patch_proposal_queue import build_proposal_markdown


def _build(**overrides):
    case = {
        "name": "python_off_by_one_pagination",
        "language": "python",
        "category": "boundary_logic",
        "difficulty": "easy",
        "prompt": (
            "Fix the Python pagination off-by-one bug.\n"
            "- paginate must reject page numbers less than 1.\n"
            "- paginate must reject per_page values less than 1."
        ),
        "expected_changed_files": ["pagination.py"],
        "forbidden_changed_files": ["main.py"],
    }
    payload = {
        "summary": "Replace `i + 1` with `i` so the slice starts at the right offset.",
        "patch_plan": [
            {"op": "replace_snippet", "relative_path": "pagination.py",
             "target_snippet": "i + 1", "patched_snippet": "i"},
        ],
    }
    plan = payload["patch_plan"]
    validation = {"validation_ok": True}
    args = dict(
        case_name="python_off_by_one_pagination",
        case=case,
        payload=payload,
        plan=plan,
        validation=validation,
        validation_command="python main.py",
        source_report_name="benchmark_report_2026-05-18.json",
        diff_text="--- a/pagination.py\n+++ b/pagination.py\n@@ -3 +3 @@\n- i + 1\n+ i\n",
    )
    args.update(overrides)
    return build_proposal_markdown(**args)


def test_renders_all_four_tutor_sections():
    md = _build()
    assert "## What was wrong" in md
    assert "## Why this patch works" in md
    assert "## Concept to learn" in md
    assert "## Similar patterns to watch for" in md
    assert "## Diff" in md


def test_what_was_wrong_uses_case_prompt_by_default():
    md = _build()
    # case.prompt is the canonical bug description for benchmark items.
    assert "off-by-one bug" in md
    assert "page numbers less than 1" in md


def test_what_was_wrong_prefers_payload_issues_when_present():
    md = _build(payload={
        "summary": "Patched the slice.",
        "patch_plan": [
            {"op": "replace_snippet", "relative_path": "pagination.py",
             "target_snippet": "x", "patched_snippet": "y"},
        ],
        "issues": [
            "Slice index started at i+1 instead of i.",
            "No guard rejected page values less than 1.",
        ],
    })
    assert "- Slice index started at i+1 instead of i." in md
    assert "- No guard rejected page values less than 1." in md
    # case.prompt is NOT used when issues[] is present.
    assert "off-by-one bug" not in md


def test_why_section_uses_payload_summary():
    md = _build()
    assert "Replace `i + 1` with `i`" in md


def test_concept_section_includes_language_and_category():
    md = _build()
    assert "Discipline area: `python` · `boundary_logic`" in md
    assert "Difficulty: `easy`" in md


def test_patterns_section_lists_expected_and_forbidden_files():
    md = _build()
    # Plan paths
    assert "Files touched by this patch" in md
    assert "`pagination.py`" in md
    # Expected
    assert "Files the benchmark expects to change" in md
    # Forbidden (Patch Safety gate covers these)
    assert "Files the benchmark forbids touching" in md
    assert "Patch Safety gate covers these" in md
    assert "`main.py`" in md


def test_validation_status_renders_passed_failed_or_not_run():
    md_pass = _build(validation={"validation_ok": True})
    assert "✓ passed" in md_pass

    md_fail = _build(validation={"validation_ok": False})
    assert "✗ failed" in md_fail

    md_unset = _build(validation={})
    assert "(not run)" in md_unset


def test_no_summary_falls_back_cleanly():
    md = _build(payload={"summary": "", "patch_plan": []})
    assert "_No summary provided by the model._" in md


def test_no_case_prompt_and_no_issues_falls_back_cleanly():
    case = {
        "name": "case_x",
        "language": "go",
        "category": "concurrency",
        "expected_changed_files": ["foo.go"],
        "forbidden_changed_files": [],
        # no prompt
    }
    md = build_proposal_markdown(
        case_name="case_x",
        case=case,
        payload={"summary": "Used a mutex.", "patch_plan": []},
        plan=[],
        validation={"validation_ok": True},
        validation_command="go test ./...",
        source_report_name="benchmark_report_x.json",
        diff_text="",
    )
    assert "No bug description available" in md


def test_active_lessons_surface_in_concept_and_patterns(monkeypatch):
    """When find_active_lessons returns hits, both concept + patterns sections cite them."""
    fake_lessons = [
        {
            "title": "Pagination boundary check",
            "summary": "Always reject page < 1 before computing the slice. Use a guard clause at the top.",
            "tags": ["python", "boundary-logic", "pagination"],
        },
        {
            "title": "Slice arithmetic gotcha",
            "summary": "Off-by-one usually means a stale `+1` after a refactor.",
            "tags": ["python", "boundary-logic"],
        },
    ]

    import scripts.run_patch_proposal_queue as queue_mod

    monkeypatch.setattr(
        queue_mod, "_lookup_active_lessons",
        lambda case: list(fake_lessons),
    )

    md = _build()

    # Concept section cites the lesson title and trims to first sentence.
    assert "Pagination boundary check" in md
    assert "Always reject page < 1 before computing the slice" in md
    # Patterns section unions tags from up to 5 lessons.
    assert "boundary-logic" in md
    assert "pagination" in md


def test_active_lessons_failure_does_not_break_rendering(monkeypatch):
    """If retrieval crashes, proposal.md still writes."""
    import scripts.run_patch_proposal_queue as queue_mod

    def boom(case):
        raise RuntimeError("retrieval down")

    # _lookup_active_lessons swallows exceptions internally, but pin the
    # public contract: build_proposal_markdown never raises.
    monkeypatch.setattr(queue_mod, "find_active_lessons", boom, raising=False)
    md = _build()
    assert "## What was wrong" in md  # rendered successfully


def test_diff_block_preserved():
    md = _build()
    assert "```diff" in md
    assert "- i + 1" in md
    assert "+ i" in md


def test_header_contains_source_report_name_and_command():
    md = _build()
    assert "benchmark_report_2026-05-18.json" in md
    assert "validation `python main.py`" in md
