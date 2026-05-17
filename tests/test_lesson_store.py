import json
from pathlib import Path

import pytest

from core import lesson_store


def _valid_candidate(**overrides):
    candidate = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": ["src/app.py"],
        "diff_stats": {"added": 4, "removed": 2},
    }
    candidate.update(overrides)
    return candidate


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    """Redirect lesson_store.get_agent_dir to tmp_path/.agent and reset flag."""
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    return tmp_path


def _bucket_dir(tmp_path: Path, bucket: str) -> Path:
    return tmp_path / ".agent" / "lessons" / bucket


def test_save_auto_approved_lands_in_candidate_by_default(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())

    assert saved["status"] == "candidate"
    # Top-level mirrors the bucket: candidate => false, even though the guard
    # would auto-approve. Guard verdict is preserved in `evaluation`.
    assert saved["active_knowledge_allowed"] is False
    assert saved["evaluation"]["active_knowledge_allowed"] is True
    assert saved["evaluation"]["promotion"] == "auto_approved"

    on_disk = _bucket_dir(lessons_repo, "candidate") / f"{saved['id']}.json"
    assert on_disk.is_file()
    assert not (_bucket_dir(lessons_repo, "active") / f"{saved['id']}.json").exists()


def test_save_auto_approved_with_flag_lands_in_active(lessons_repo, monkeypatch):
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", True)

    saved = lesson_store.save_candidate_lesson(_valid_candidate())

    assert saved["status"] == "active"
    assert saved["active_knowledge_allowed"] is True

    assert (_bucket_dir(lessons_repo, "active") / f"{saved['id']}.json").is_file()
    assert not (_bucket_dir(lessons_repo, "candidate") / f"{saved['id']}.json").exists()


def test_save_needs_human_review_lands_in_candidate(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(patch_kind="unknown")
    )

    assert saved["status"] == "candidate"
    assert saved["active_knowledge_allowed"] is False
    assert saved["evaluation"]["promotion"] == "needs_human_review"


def test_save_blocked_lands_in_blocked(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    assert saved["status"] == "blocked"
    assert saved["active_knowledge_allowed"] is False
    assert saved["evaluation"]["promotion"] == "blocked"

    assert (_bucket_dir(lessons_repo, "blocked") / f"{saved['id']}.json").is_file()


def test_lesson_record_has_all_13_fields(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(),
        source="benchmark",
        source_report="background_report_20260517_153000.json",
        case_name="python_off_by_one_pagination",
        title="Pagination off-by-one fix",
        summary="Caller-provided summary",
    )

    expected_keys = {
        "id",
        "status",
        "created_at",
        "updated_at",
        "source",
        "source_report",
        "case_name",
        "title",
        "summary",
        "tags",
        "candidate",
        "evaluation",
        "active_knowledge_allowed",
    }
    assert set(saved.keys()) == expected_keys

    assert saved["source"] == "benchmark"
    assert saved["source_report"] == "background_report_20260517_153000.json"
    assert saved["case_name"] == "python_off_by_one_pagination"
    assert saved["title"] == "Pagination off-by-one fix"
    assert saved["summary"] == "Caller-provided summary"
    assert saved["created_at"] == saved["updated_at"]
    assert isinstance(saved["tags"], list)

    on_disk = _bucket_dir(lessons_repo, "candidate") / f"{saved['id']}.json"
    on_disk_record = json.loads(on_disk.read_text(encoding="utf-8"))
    assert set(on_disk_record.keys()) == expected_keys


def test_save_auto_derives_tags_when_omitted(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(language="python", category="logic_validation"),
        source="benchmark",
        case_name="python_off_by_one_pagination",
        title="Pagination off-by-one fix",
        summary="Fix off-by-one in paginator iteration boundary.",
    )

    tags = saved["tags"]
    assert "python" in tags
    assert "logic-validation" in tags
    assert "python-off-by-one-pagination" in tags
    # File basename ("src/app.py" → "app") should appear
    assert "app" in tags


def test_save_explicit_tags_override_auto_derive(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(language="python"),
        source="manual",
        case_name="python_off_by_one_pagination",
        tags=["custom-only", "another-tag"],
    )

    assert saved["tags"] == ["custom-only", "another-tag"]
    # Auto-derive would have produced "python" — explicit list wins
    assert "python" not in saved["tags"]


def test_save_explicit_empty_tags_kept_empty(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(language="python"),
        source="manual",
        case_name="python_off_by_one_pagination",
        tags=[],
    )

    assert saved["tags"] == []


def test_derive_lesson_tags_basic_shape():
    candidate = {
        "language": "cpp",
        "category": "logic_validation",
        "changed_files": ["interest.cpp"],
    }
    tags = lesson_store.derive_lesson_tags(
        candidate,
        case_name="cpp_account_interest",
        title="Patch proposal: cpp_account_interest",
        summary="Fix the compound interest calculation by adding validation.",
    )

    assert "cpp" in tags
    assert "logic-validation" in tags
    assert "cpp-account-interest" in tags
    assert "interest" in tags
    # At least one content token (e.g., "compound", "calculation", "validation")
    assert any(t in tags for t in ("compound", "calculation", "validation"))
    # Stopword-only inputs shouldn't sneak in
    assert "fix" not in tags
    assert "the" not in tags
    # Deduped
    assert len(tags) == len(set(tags))


def test_list_lessons_returns_all_when_no_status(lessons_repo):
    a = lesson_store.save_candidate_lesson(_valid_candidate())
    b = lesson_store.save_candidate_lesson(_valid_candidate(patch_kind="unknown"))
    c = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    listed = lesson_store.list_lessons()
    listed_ids = [r["id"] for r in listed]

    assert set(listed_ids) == {a["id"], b["id"], c["id"]}
    created_ats = [r["created_at"] for r in listed]
    assert created_ats == sorted(created_ats, reverse=True)


def test_list_lessons_filters_by_status(lessons_repo):
    a = lesson_store.save_candidate_lesson(_valid_candidate())
    b = lesson_store.save_candidate_lesson(_valid_candidate(patch_kind="unknown"))
    c = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    candidates = lesson_store.list_lessons(status="candidate")
    blocked = lesson_store.list_lessons(status="blocked")
    actives = lesson_store.list_lessons(status="active")

    assert {r["id"] for r in candidates} == {a["id"], b["id"]}
    assert {r["id"] for r in blocked} == {c["id"]}
    assert actives == []


def test_promote_lesson_moves_candidate_to_active(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    candidate_path = _bucket_dir(lessons_repo, "candidate") / f"{saved['id']}.json"
    active_path = _bucket_dir(lessons_repo, "active") / f"{saved['id']}.json"
    assert candidate_path.is_file()

    promoted = lesson_store.promote_lesson(saved["id"])

    assert promoted["status"] == "active"
    assert promoted["active_knowledge_allowed"] is True
    assert promoted["updated_at"] >= promoted["created_at"]
    assert promoted["evaluation"] == saved["evaluation"]

    assert active_path.is_file()
    assert not candidate_path.exists()

    actives = lesson_store.list_lessons(status="active")
    candidates = lesson_store.list_lessons(status="candidate")
    assert [r["id"] for r in actives] == [saved["id"]]
    assert candidates == []


def test_promote_lesson_idempotent_when_already_active(lessons_repo):
    saved = lesson_store.save_candidate_lesson(_valid_candidate())
    first = lesson_store.promote_lesson(saved["id"])
    second = lesson_store.promote_lesson(saved["id"])

    assert second["status"] == "active"
    assert second["updated_at"] == first["updated_at"]


def test_promote_blocked_lesson_raises(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    with pytest.raises(ValueError):
        lesson_store.promote_lesson(saved["id"])


def test_promote_unknown_lesson_raises(lessons_repo):
    with pytest.raises(LookupError):
        lesson_store.promote_lesson("20990101_000000_000000")


def test_block_lesson_moves_any_to_blocked(lessons_repo):
    a = lesson_store.save_candidate_lesson(_valid_candidate())
    b = lesson_store.save_candidate_lesson(_valid_candidate())
    lesson_store.promote_lesson(b["id"])

    blocked_a = lesson_store.block_lesson(a["id"])
    blocked_b = lesson_store.block_lesson(b["id"])

    for rec in (blocked_a, blocked_b):
        assert rec["status"] == "blocked"
        assert rec["active_knowledge_allowed"] is False

    blocked_dir = _bucket_dir(lessons_repo, "blocked")
    assert (blocked_dir / f"{a['id']}.json").is_file()
    assert (blocked_dir / f"{b['id']}.json").is_file()

    assert not (_bucket_dir(lessons_repo, "candidate") / f"{a['id']}.json").exists()
    assert not (_bucket_dir(lessons_repo, "active") / f"{b['id']}.json").exists()


def test_block_lesson_idempotent_when_already_blocked(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )
    first = lesson_store.block_lesson(saved["id"])
    second = lesson_store.block_lesson(saved["id"])

    assert second["status"] == "blocked"
    assert second["updated_at"] == first["updated_at"]


def test_blocked_lesson_not_active(lessons_repo):
    saved = lesson_store.save_candidate_lesson(
        _valid_candidate(touched_forbidden_files=["secrets.env"])
    )

    actives = lesson_store.list_lessons(status="active")
    assert all(r["id"] != saved["id"] for r in actives)

    active_dir = _bucket_dir(lessons_repo, "active")
    assert not any(p.stem == saved["id"] for p in active_dir.glob("*.json"))


def test_lesson_id_path_traversal_rejected(lessons_repo):
    for bad_id in (
        "../../etc/passwd",
        "foo/bar",
        "..\\..\\etc",
        "",
        "not-an-id",
        "20260517_153012",
    ):
        with pytest.raises(ValueError):
            lesson_store.promote_lesson(bad_id)
        with pytest.raises(ValueError):
            lesson_store.block_lesson(bad_id)
