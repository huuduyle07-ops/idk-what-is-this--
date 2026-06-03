import pytest
from core import lesson_merge, lesson_store


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        lesson_store, "get_agent_dir", lambda repo_path=None: tmp_path / ".agent"
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    return tmp_path


def _saved(lessons_repo, **kwargs):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": [],
    }
    return lesson_store.save_candidate_lesson(candidate, **kwargs)


# ── preview_merge ─────────────────────────────────────────────────────────────

def test_preview_merge_returns_candidate_shaped_dict(lessons_repo):
    a = _saved(lessons_repo, title="Lesson A", summary="summary A")
    b = _saved(lessons_repo, title="Lesson B", summary="summary B")
    record, warnings = lesson_merge.preview_merge([a, b])
    assert record["status"] == "candidate"
    assert record["active_knowledge_allowed"] is False
    assert record["source"] == "merge"


def test_preview_merge_has_no_id(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    assert "id" not in record


def test_preview_merge_writes_no_files(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    before = set((lessons_repo / ".agent" / "lessons").rglob("*.json"))
    lesson_merge.preview_merge([a, b])
    after = set((lessons_repo / ".agent" / "lessons").rglob("*.json"))
    assert before == after


def test_preview_merge_unions_tags(lessons_repo):
    a = _saved(lessons_repo, tags=["python", "loops"])
    b = _saved(lessons_repo, tags=["python", "strings"])
    record, _ = lesson_merge.preview_merge([a, b])
    assert set(record["tags"]) == {"python", "loops", "strings"}


def test_preview_merge_accepts_explicit_tags(lessons_repo):
    a = _saved(lessons_repo, tags=["python"])
    b = _saved(lessons_repo, tags=["go"])
    record, _ = lesson_merge.preview_merge([a, b], tags=["custom-tag"])
    assert record["tags"] == ["custom-tag"]


def test_preview_merge_sets_merge_sources(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    assert record["merge_sources"] == [a["id"], b["id"]]
    assert record["supersedes"] == [a["id"], b["id"]]


def test_preview_merge_preserves_sources_data(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    record, _ = lesson_merge.preview_merge([a, b])
    ids_in_data = {e["id"] for e in record["merge_sources_data"]}
    assert ids_in_data == {a["id"], b["id"]}
    for entry in record["merge_sources_data"]:
        assert "candidate" in entry
        assert "evaluation" in entry


def test_preview_merge_warns_about_active_source(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.promote_lesson(a["id"])
    a_active = lesson_store.get_lesson_by_id(a["id"])
    _, warnings = lesson_merge.preview_merge([a_active, b])
    assert any("active" in w for w in warnings)


def test_preview_merge_warns_about_mixed_kinds(lessons_repo):
    a = _saved(lessons_repo)
    b = _saved(lessons_repo)
    lesson_store.patch_lesson_fields(b["id"], {"kind": "anti_lesson"})
    b_patched = lesson_store.get_lesson_by_id(b["id"])
    _, warnings = lesson_merge.preview_merge([a, b_patched])
    assert any("kind" in w for w in warnings)


def test_preview_merge_requires_at_least_two(lessons_repo):
    a = _saved(lessons_repo)
    with pytest.raises(ValueError, match="at least 2"):
        lesson_merge.preview_merge([a])


def test_preview_merge_accepts_explicit_title_and_summary(lessons_repo):
    a = _saved(lessons_repo, title="Original A", summary="summary A")
    b = _saved(lessons_repo, title="Original B", summary="summary B")
    record, _ = lesson_merge.preview_merge([a, b], title="Custom title", summary="Custom summary")
    assert record["title"] == "Custom title"
    assert record["summary"] == "Custom summary"
