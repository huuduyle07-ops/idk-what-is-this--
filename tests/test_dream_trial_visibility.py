"""Phase 5P.1 — Structured Trial Reports panel visibility.

The Structured Trial Reports panel only makes sense for research/study/
report-only Dream work. For normal bug/debt Dream modes it is clutter, so the
panel is now a collapsed ``<details>`` disclosure ("Research / Trial reports")
that JS expands only when the selected Work type / Action level is relevant.

These are template-contract checks (the established pattern in
``test_dream_reference_files_ui.py``): the panel must stay in the DOM with all
IDs/handlers intact — it is collapsed, never deleted — so routes and tests that
reference those controls keep working.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _trials_details_open_tag(tpl: str) -> str:
    m = re.search(
        r'<details[^>]*data-ui-group="dream-structured-trials"[^>]*>', tpl
    )
    assert m, "Structured Trial Reports panel is not a <details> disclosure"
    return m.group(0)


# ---------------------------------------------------------------------------
# The panel is collapsible and NOT primary/always-expanded (normal bug/debt).
# ---------------------------------------------------------------------------

def test_trials_panel_is_a_details_disclosure():
    tpl = _template()
    assert 'data-ui-group="dream-structured-trials"' in tpl
    # IA-freeze convention: a closing HTML-comment anchor for the group.
    assert "<!-- /dream-structured-trials -->" in tpl


def test_trials_panel_is_collapsed_by_default():
    """For normal bug/debt modes the panel must not be statically expanded."""
    open_tag = _trials_details_open_tag(_template())
    assert " open" not in open_tag, (
        "Structured Trial Reports panel must default to collapsed, not open"
    )


def test_trials_panel_summary_is_reachable():
    tpl = _template()
    # A disclosure summary keeps the panel reachable for research/study modes.
    assert "<summary" in tpl
    assert "Research / Trial reports" in tpl


# ---------------------------------------------------------------------------
# Nothing is deleted — IDs, handlers, and routes are preserved.
# ---------------------------------------------------------------------------

def test_trials_panel_preserves_ids_and_handlers():
    tpl = _template()
    for needle in (
        'id="dreamTrialCreateBtn"',
        'onclick="createDreamTrial()"',
        'onclick="refreshDreamTrials()"',
        'id="dreamTrialsStatus"',
        'id="dreamTrialsList"',
        'id="dreamTrialViewer"',
        'id="dreamTrialsUnavailableNote"',
    ):
        assert needle in tpl, f"trial control disappeared: {needle}"


# ---------------------------------------------------------------------------
# Relevance toggle is wired to Work type + Action level.
# ---------------------------------------------------------------------------

def test_visibility_toggle_function_is_wired():
    tpl = _template()
    assert "_updateTrialPanelVisibility" in tpl
    # Called on initial load and whenever Work type / Action level changes.
    assert tpl.count("_updateTrialPanelVisibility(") >= 2


def test_relevance_predicate_covers_research_and_report_only():
    tpl = _template()
    # The relevant action levels per the Phase 5P.1 spec.
    assert "report_only" in tpl
    assert "case_idea_research" in tpl


def test_relevance_note_explains_research_workflow():
    tpl = _template()
    # Suggested copy guiding the user toward a research/report-only action level.
    assert "research/study workflows" in tpl


def test_trials_panel_has_disclosure_styles():
    styles = STYLE_SHEET.read_text(encoding="utf-8")
    assert ".dream-trials-summary" in styles
