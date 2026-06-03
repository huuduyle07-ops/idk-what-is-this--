"""Phase 11-prep-cleanup-b2b: Lesson Merge/Dedupe UI contract tests.

Read-only: parses index.html as text. Imports nothing from the application.
"""
from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
_TMPL = TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Merge select button exists
# ---------------------------------------------------------------------------

def test_merge_select_button_exists():
    assert 'id="mergeSelectToggle"' in _TMPL


# ---------------------------------------------------------------------------
# 2. Duplicate hints panel exists
# ---------------------------------------------------------------------------

def test_duplicate_hints_panel_exists():
    assert 'id="duplicateHintsPanel"' in _TMPL


# ---------------------------------------------------------------------------
# 3. Preview merge modal fields exist
# ---------------------------------------------------------------------------

def test_preview_merge_modal_fields_exist():
    assert 'id="mergePreviewTitle"' in _TMPL
    assert 'id="mergePreviewSummary"' in _TMPL


# ---------------------------------------------------------------------------
# 4. Create merged candidate button exists
# ---------------------------------------------------------------------------

def test_create_merged_candidate_button_exists():
    assert 'id="mergeCreateBtn"' in _TMPL


# ---------------------------------------------------------------------------
# 5. Show archived toggle exists
# ---------------------------------------------------------------------------

def test_show_archived_toggle_exists():
    assert 'id="showArchivedLessons"' in _TMPL


# ---------------------------------------------------------------------------
# 6. Show superseded toggle exists
# ---------------------------------------------------------------------------

def test_show_superseded_toggle_exists():
    assert 'id="showSupersededLessons"' in _TMPL


# ---------------------------------------------------------------------------
# 7. Archive button function defined
# ---------------------------------------------------------------------------

def test_archive_lesson_function_defined():
    assert "function archiveLessonById(" in _TMPL


# ---------------------------------------------------------------------------
# 8. Active archive blocked in UI contract
# ---------------------------------------------------------------------------

def test_active_archive_blocked_in_ui():
    assert "Active lessons cannot be archived" in _TMPL


# ---------------------------------------------------------------------------
# 9. JS calls b2a lesson routes
# ---------------------------------------------------------------------------

def test_js_calls_b2a_lesson_routes():
    assert "/lessons/duplicates" in _TMPL
    assert "/lessons/merge/preview" in _TMPL
    assert "/lessons/merge/create" in _TMPL
    assert "/lessons/archive" in _TMPL


# ---------------------------------------------------------------------------
# 10. Merge JS section does not call forbidden routes
# ---------------------------------------------------------------------------

def test_js_merge_section_does_not_call_forbidden_routes():
    FORBIDDEN = [
        "/benchmarks/run",
        "/dream/run",
        "/generate_patch",
        "/apply_patch",
    ]
    start_marker = "function loadDuplicateHints("
    end_marker = "function loadProposalRuns("
    assert start_marker in _TMPL, "loadDuplicateHints must be defined"
    start = _TMPL.index(start_marker)
    end = _TMPL.index(end_marker, start) if end_marker in _TMPL[start:] else len(_TMPL)
    section = _TMPL[start:end]
    for forbidden in FORBIDDEN:
        assert forbidden not in section, (
            f"Forbidden route {forbidden!r} found in lesson merge JS section"
        )


# ---------------------------------------------------------------------------
# 11. confirm_supersede_active is explicit, not automatic
# ---------------------------------------------------------------------------

def test_confirm_supersede_active_is_explicit_not_automatic():
    assert 'id="mergeConfirmSupersede"' in _TMPL
    assert "confirm_supersede_active: true" not in _TMPL
    assert "confirm_supersede_active:true" not in _TMPL


# ---------------------------------------------------------------------------
# 12. No unsafe inline onclick injection for lesson title/summary
# ---------------------------------------------------------------------------

def test_no_unsafe_inline_onclick_injection():
    # createMergedCandidate reads DOM — called with no args
    assert "createMergedCandidate()" in _TMPL
    # title/summary are never passed as inline onclick string params
    assert "createMergedCandidate('" not in _TMPL


# ---------------------------------------------------------------------------
# 13. AST self-guard: this module imports nothing heavy
# ---------------------------------------------------------------------------

def test_audit_module_has_no_forbidden_imports():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    allowed_top = {"ast", "pathlib", "__future__"}
    for imp in imported:
        top = imp.split(".")[0]
        assert top in allowed_top, f"unexpected import in b2b UI audit: {imp}"
