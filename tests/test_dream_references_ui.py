"""Template contract checks for Dream research reference import UI."""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"


def test_dream_research_reference_import_controls_are_present():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    styles = STYLE_SHEET.read_text(encoding="utf-8")

    assert "Research References" in template
    assert 'id="dreamResearchTopic"' in template
    assert 'id="dreamResearchSourceType"' in template
    assert 'id="dreamResearchRawInput"' in template
    assert 'onclick="importDreamReference()"' in template
    assert 'onclick="refreshDreamReferences(true)"' in template
    assert "useDreamReferenceMarkdown" in template
    assert "/dream/references/import" in template
    assert "/dream/references/list" in template
    assert ".dream-references-section" in styles

