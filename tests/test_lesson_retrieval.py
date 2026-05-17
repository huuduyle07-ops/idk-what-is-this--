import json

import pytest

from core import lesson_retrieval, lesson_store


def _candidate(**overrides):
    base = {
        "validation_ok": True,
        "touched_forbidden_files": [],
        "missing_expected_files": [],
        "patch_kind": "patch_candidate",
        "rollback_happened": False,
        "changed_files": ["src/app.py"],
        "diff_stats": {"added": 4, "removed": 2},
    }
    base.update(overrides)
    return base


@pytest.fixture
def lessons_repo(tmp_path, monkeypatch):
    """Redirect lesson_store's get_agent_dir to tmp_path/.agent."""
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    return tmp_path


def _save_active(
    *,
    case_name=None,
    source="manual",
    source_report=None,
    title=None,
    summary="",
    candidate_overrides=None,
):
    cand = _candidate(**(candidate_overrides or {}))
    saved = lesson_store.save_candidate_lesson(
        cand,
        source=source,
        source_report=source_report,
        case_name=case_name,
        title=title,
        summary=summary,
    )
    return lesson_store.promote_lesson(saved["id"])


def _save_candidate_only(*, case_name=None, title=None, summary=""):
    return lesson_store.save_candidate_lesson(
        _candidate(),
        source="manual",
        case_name=case_name,
        title=title,
        summary=summary,
    )


def _save_blocked(*, case_name=None, title=None, summary=""):
    return lesson_store.save_candidate_lesson(
        _candidate(touched_forbidden_files=["secrets.env"]),
        source="manual",
        case_name=case_name,
        title=title,
        summary=summary,
    )


# --- list_active_lessons --------------------------------------------------


def test_list_active_lessons_empty_when_no_lessons(lessons_repo):
    assert lesson_retrieval.list_active_lessons() == []


def test_list_active_lessons_returns_only_active(lessons_repo):
    active = _save_active(case_name="active_case")
    candidate = _save_candidate_only(case_name="candidate_case")
    blocked = _save_blocked(case_name="blocked_case")

    results = lesson_retrieval.list_active_lessons()
    ids = [r["id"] for r in results]

    assert active["id"] in ids
    assert candidate["id"] not in ids
    assert blocked["id"] not in ids


def test_active_lesson_with_flag_false_filtered_out(lessons_repo):
    legit = _save_active(case_name="legit_case")

    tampered_id = "20990101_000000_000001"
    tampered = {
        "id": tampered_id,
        "status": "active",
        "created_at": "2099-01-01T00:00:00+00:00",
        "updated_at": "2099-01-01T00:00:00+00:00",
        "source": "tampered",
        "source_report": None,
        "case_name": "tampered_case",
        "title": "Tampered lesson",
        "summary": "should not be retrievable",
        "candidate": {},
        "evaluation": {
            "promotion": "auto_approved",
            "active_knowledge_allowed": True,
            "score": 1.0,
            "reasons": [],
        },
        "active_knowledge_allowed": False,
    }
    active_path = lessons_repo / ".agent" / "lessons" / "active" / f"{tampered_id}.json"
    active_path.write_text(json.dumps(tampered), encoding="utf-8")

    results = lesson_retrieval.list_active_lessons()
    ids = [r["id"] for r in results]

    assert legit["id"] in ids
    assert tampered_id not in ids


# --- find_active_lessons: safety filters ----------------------------------


def test_candidate_lessons_not_returned_by_find(lessons_repo):
    cand = _save_candidate_only(case_name="some_case", title="Looking for X")

    results = lesson_retrieval.find_active_lessons(query="Looking")
    assert all(r["id"] != cand["id"] for r in results)


def test_blocked_lessons_not_returned_by_find(lessons_repo):
    blocked = _save_blocked(case_name="some_case", title="Looking for X")

    results = lesson_retrieval.find_active_lessons(query="Looking")
    assert all(r["id"] != blocked["id"] for r in results)


# --- find_active_lessons: scoring -----------------------------------------


def test_case_name_match_ranks_first(lessons_repo):
    a = _save_active(case_name="python_off_by_one_pagination", title="Pagination fix")
    b = _save_active(case_name="ts_inventory_restock", title="Pagination thoughts")
    c = _save_active(case_name="rust_cart_reservation", title="Pagination")

    results = lesson_retrieval.find_active_lessons(case_name="python_off_by_one_pagination")

    assert results, "expected at least one match"
    assert results[0]["id"] == a["id"]
    assert results[0]["_match_score"] >= 100


def test_query_matches_title(lessons_repo):
    target = _save_active(case_name="x", title="Unique slug TITLE_TOKEN here", summary="")
    _save_active(case_name="y", title="Unrelated lesson", summary="nothing to see")

    results = lesson_retrieval.find_active_lessons(query="title_token")
    ids = [r["id"] for r in results]
    assert target["id"] in ids


def test_query_matches_summary(lessons_repo):
    target = _save_active(case_name="x", title="t", summary="A long summary with KEY_PHRASE inside")
    _save_active(case_name="y", title="t", summary="completely different content")

    results = lesson_retrieval.find_active_lessons(query="key_phrase")
    ids = [r["id"] for r in results]
    assert target["id"] in ids


def test_query_matches_evaluation_reasons(lessons_repo):
    # The default candidate auto-approves with the reason
    # "all auto-approval checks passed", which lives in evaluation.reasons.
    target = _save_active(case_name="x", title="t", summary="s")

    results = lesson_retrieval.find_active_lessons(query="auto-approval checks passed")
    ids = [r["id"] for r in results]
    assert target["id"] in ids


def test_language_match_from_case_name_prefix(lessons_repo):
    py = _save_active(case_name="python_off_by_one")
    rs = _save_active(case_name="rust_cart_reservation")

    results = lesson_retrieval.find_active_lessons(language="python")
    ids = [r["id"] for r in results]

    assert py["id"] in ids
    assert rs["id"] not in ids


def test_no_filter_returns_recent_active_lessons(lessons_repo):
    saved_ids = []
    for i in range(3):
        rec = _save_active(case_name=f"case_{i}", title=f"Lesson {i}")
        saved_ids.append(rec["id"])

    results = lesson_retrieval.find_active_lessons()

    assert len(results) == 3
    assert {r["id"] for r in results} == set(saved_ids)


# --- find_active_lessons: clamping ----------------------------------------


def test_limit_is_clamped_low(lessons_repo):
    for i in range(3):
        _save_active(case_name=f"case_{i}")

    results = lesson_retrieval.find_active_lessons(limit=0)
    assert len(results) == 1

    results_neg = lesson_retrieval.find_active_lessons(limit=-5)
    assert len(results_neg) == 1


def test_limit_is_clamped_high(lessons_repo):
    for i in range(25):
        _save_active(case_name=f"case_{i}")

    results = lesson_retrieval.find_active_lessons(limit=100)
    assert len(results) == 20


# --- format_lessons_for_prompt --------------------------------------------


def test_format_empty_returns_empty_string():
    assert lesson_retrieval.format_lessons_for_prompt([]) == ""
    assert lesson_retrieval.format_lessons_for_prompt(None) == ""


def test_format_contains_compact_fields_not_candidate(lessons_repo):
    lesson = _save_active(
        case_name="python_off_by_one_pagination",
        source="benchmark",
        title="Pagination off-by-one fix",
        summary="Fixed an off-by-one in the pagination logic",
    )

    text = lesson_retrieval.format_lessons_for_prompt([lesson])

    assert "Pagination off-by-one fix" in text
    assert "python_off_by_one_pagination" in text
    assert "benchmark" in text
    assert "Fixed an off-by-one in the pagination logic" in text
    # Compact: must NOT dump raw candidate payload (changed_files etc.)
    assert "diff_stats" not in text
    assert "touched_forbidden_files" not in text
    assert "patch_kind" not in text


def test_format_caps_output_at_max_chars(lessons_repo):
    lessons = []
    for i in range(20):
        lessons.append(
            _save_active(
                case_name=f"case_{i}",
                title=f"Long lesson title {i} " + ("padding " * 50),
                summary="x" * 500,
            )
        )

    text = lesson_retrieval.format_lessons_for_prompt(lessons, max_chars=500)

    assert len(text) <= 500
    assert text.endswith("…")
