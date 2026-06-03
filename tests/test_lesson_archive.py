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


def test_archive_candidate_sets_flag(lessons_repo):
    saved = _saved(lessons_repo)
    updated = lesson_merge.archive_lesson(saved["id"])
    assert updated["archived"] is True
    # File still in candidate bucket
    bucket = (
        lessons_repo / ".agent" / "lessons" / "candidate" / f"{saved['id']}.json"
    )
    assert bucket.is_file()


def test_archive_blocked_sets_flag(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_store.block_lesson(saved["id"])
    updated = lesson_merge.archive_lesson(saved["id"])
    assert updated["archived"] is True
    # File still in blocked bucket
    bucket = (
        lessons_repo / ".agent" / "lessons" / "blocked" / f"{saved['id']}.json"
    )
    assert bucket.is_file()


def test_archive_active_raises(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_store.promote_lesson(saved["id"])
    with pytest.raises(ValueError, match="cannot archive an active lesson"):
        lesson_merge.archive_lesson(saved["id"])


def test_archive_idempotent(lessons_repo):
    saved = _saved(lessons_repo)
    lesson_merge.archive_lesson(saved["id"])
    updated2 = lesson_merge.archive_lesson(saved["id"])
    assert updated2["archived"] is True


def test_archive_unknown_raises(lessons_repo):
    with pytest.raises(LookupError):
        lesson_merge.archive_lesson("20240101_000000_000000")
