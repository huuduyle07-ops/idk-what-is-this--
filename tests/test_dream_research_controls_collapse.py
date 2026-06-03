"""Structural tests for Dream research controls collapse (Phase 11-prep-cleanup-a)."""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def test_research_section_has_no_inline_hidden_attribute():
    """The .dream-references-section must start visible — JS hides it, not HTML."""
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    idx = tpl.find("dream-references-section")
    assert idx != -1, "dream-references-section not found in template"
    snippet = tpl[max(0, idx - 50) : idx + 60]
    assert "hidden" not in snippet


def test_trials_section_is_details_element():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert '<details id="dreamTrialsSection"' in tpl


def test_research_controls_collapse_js_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_updateDreamResearchControlsVisibility" in tpl


def test_research_controls_collapse_targets_bug_investigation():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "bug_investigation" in tpl


def test_dream_taxonomy_route_returns_bug_investigation(client):
    resp = client.get("/dream/taxonomy")
    assert resp.status_code == 200
    data = resp.get_json()
    dream_types = data.get("dream_types") or []
    assert "bug_investigation" in dream_types


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
