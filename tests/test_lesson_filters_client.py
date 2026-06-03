"""Tests for lesson filter UI and data shape (Phase 11-prep-cleanup-a)."""
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"


def test_lesson_filter_language_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterLanguage"' in tpl


def test_lesson_filter_source_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterSource"' in tpl


def test_lesson_filter_category_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterCategory"' in tpl


def test_lesson_filter_difficulty_dropdown_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert 'id="lessonFilterDifficulty"' in tpl


def test_apply_lesson_filters_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_applyLessonFilters" in tpl


def test_populate_lesson_filter_dropdowns_function_present():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "_populateLessonFilterDropdowns" in tpl


def test_lesson_card_has_data_lesson_id_attribute():
    tpl = INDEX_TEMPLATE.read_text(encoding="utf-8")
    assert "data-lesson-id" in tpl


@pytest.fixture
def client():
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_lessons_list_route_returns_source_field(client):
    """The /lessons/list response records must include 'source' and 'candidate' keys."""
    resp = client.get("/lessons/list")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("ok") is True
    for lesson in data.get("lessons", []):
        assert "source" in lesson
        assert "candidate" in lesson or "tags" in lesson
