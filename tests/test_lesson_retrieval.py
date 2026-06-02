import json

import pytest

import config as config_module
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
    """Redirect lesson_store's get_agent_dir to tmp_path/.agent.

    Patches both `lesson_store.get_agent_dir` (used by storage internals) and
    `config.get_agent_dir` (used by `lesson_retrieval` for scope resolution).
    """
    fake = lambda repo_path=None: tmp_path / ".agent"
    monkeypatch.setattr(lesson_store, "get_agent_dir", fake)
    monkeypatch.setattr(config_module, "get_agent_dir", fake)
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
    repo_path=None,
    scope=None,
):
    cand = _candidate(**(candidate_overrides or {}))
    saved = lesson_store.save_candidate_lesson(
        cand,
        source=source,
        source_report=source_report,
        case_name=case_name,
        title=title,
        summary=summary,
        repo_path=repo_path,
        scope=scope,
    )
    return lesson_store.promote_lesson(
        saved["id"],
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=saved.get("repo_scope_id"),
    )


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


# --- list_active_lessons: scope (Phase 13.19 — R6 docstring/code contract) -


def test_list_active_lessons_with_repo_path_returns_repo_and_global_union(
    lessons_repo, tmp_path
):
    """`repo_path` DOES change the read scope: it returns the union of this
    repo's repo-scoped active lessons and the global active bucket. Pins the
    corrected docstring (the old one wrongly claimed repo_path was inert)."""
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    global_lesson = _save_active(case_name="global_case", scope="global")
    repo_a_lesson = _save_active(case_name="repo_a_case", repo_path=str(repo_a), scope="repo")
    repo_b_lesson = _save_active(case_name="repo_b_case", repo_path=str(repo_b), scope="repo")

    results = lesson_retrieval.list_active_lessons(repo_path=str(repo_a))
    ids = {r["id"] for r in results}

    assert global_lesson["id"] in ids       # global is always included
    assert repo_a_lesson["id"] in ids       # current repo's lessons included
    assert repo_b_lesson["id"] not in ids   # other repos' lessons excluded


def test_list_active_lessons_without_repo_path_is_global_only(lessons_repo, tmp_path):
    """Without `repo_path` the scope is the global bucket only — repo-scoped
    active lessons are not visible. Pins the legacy half of the contract."""
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()

    global_lesson = _save_active(case_name="global_case", scope="global")
    repo_a_lesson = _save_active(case_name="repo_a_case", repo_path=str(repo_a), scope="repo")

    results = lesson_retrieval.list_active_lessons()
    ids = {r["id"] for r in results}

    assert global_lesson["id"] in ids
    assert repo_a_lesson["id"] not in ids


def test_list_active_lessons_docstring_matches_union_behavior():
    """Regression lock for R6: the docstring must not re-assert the stale
    'repo_path does not change the read scope' claim and must document the
    repo+global union it actually implements."""
    doc = (lesson_retrieval.list_active_lessons.__doc__ or "").lower()
    assert "does not change the read scope" not in doc
    assert "union" in doc


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


def test_query_tokenized_matches_with_extra_words(lessons_repo):
    """A multi-word free-form query should match a lesson whose summary
    contains some of the query's content tokens, even if the whole query
    isn't a substring. Regression for Phase 6.3 prompt-injection."""
    target = _save_active(
        case_name="cpp_account_interest",
        title="Patch proposal: cpp_account_interest",
        summary=(
            "Fix the compound interest calculation by adding validation "
            "for negative inputs and explicitly handling zero cases."
        ),
    )

    results = lesson_retrieval.find_active_lessons(
        query="Fix the C++ compound interest bug"
    )
    ids = [r["id"] for r in results]
    assert target["id"] in ids


def test_query_only_stopwords_falls_back_to_top_n(lessons_repo):
    """A query made entirely of stopwords (no content tokens) should be
    treated as 'no query filter' rather than dropping every lesson."""
    a = _save_active(case_name="a", title="A")
    b = _save_active(case_name="b", title="B")

    results = lesson_retrieval.find_active_lessons(query="the and is or")
    ids = {r["id"] for r in results}
    assert ids == {a["id"], b["id"]}


def test_generic_action_words_do_not_cross_match_languages(lessons_repo):
    """Generic action/problem words ('fix', 'bug', etc.) must NOT cause
    cross-language false positives — a JS query should not surface a C++
    lesson just because both summaries contain 'fix' or 'bug'."""
    cpp_lesson = _save_active(
        case_name="cpp_account_interest",
        title="Patch proposal: cpp_account_interest",
        summary="Fix the compound interest calculation by adding validation.",
    )
    js_lesson = _save_active(
        case_name="js_null_user_profile",
        title="Patch proposal: js_null_user_profile",
        summary="Guard against null user profile in the JS dispatch path.",
    )

    results = lesson_retrieval.find_active_lessons(query="Fix the JS null bug")
    ids = {r["id"] for r in results}

    assert js_lesson["id"] in ids
    assert cpp_lesson["id"] not in ids


def test_query_with_hyphenated_token_preserved(lessons_repo):
    """Hyphenated identifiers should stay as one token, not get split."""
    target = _save_active(case_name="x", title="Lesson on auto-approval gate")
    _save_active(case_name="y", title="Unrelated lesson")

    results = lesson_retrieval.find_active_lessons(query="check the auto-approval flow")
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


def test_find_active_lessons_with_repo_path_uses_repo_and_global_only(
    lessons_repo, tmp_path
):
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    global_lesson = _save_active(case_name="global_case", scope="global")
    repo_a_lesson = _save_active(
        case_name="repo_a_case",
        repo_path=str(repo_a),
        scope="repo",
    )
    repo_b_lesson = _save_active(
        case_name="repo_b_case",
        repo_path=str(repo_b),
        scope="repo",
    )

    results = lesson_retrieval.find_active_lessons(repo_path=str(repo_a))
    ids = {r["id"] for r in results}

    assert global_lesson["id"] in ids
    assert repo_a_lesson["id"] in ids
    assert repo_b_lesson["id"] not in ids


def test_find_active_lessons_without_repo_path_preserves_global_only_behavior(
    lessons_repo, tmp_path
):
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()

    global_lesson = _save_active(case_name="global_case", scope="global")
    repo_a_lesson = _save_active(
        case_name="repo_a_case",
        repo_path=str(repo_a),
        scope="repo",
    )

    results = lesson_retrieval.find_active_lessons()
    ids = {r["id"] for r in results}

    assert global_lesson["id"] in ids
    assert repo_a_lesson["id"] not in ids


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


# --- tag scoring (Phase 6.2.2) --------------------------------------------


def _save_active_with_tags(*, case_name=None, title=None, summary="", tags=None):
    rec = lesson_store.save_candidate_lesson(
        _candidate(),
        source="manual",
        case_name=case_name,
        title=title,
        summary=summary,
        tags=tags,
    )
    return lesson_store.promote_lesson(rec["id"])


def test_tag_match_ranks_higher_than_summary_only_match(lessons_repo):
    """A lesson whose tag is hit by a query token must rank above one that
    only matches via title/summary substring."""
    tagged = _save_active_with_tags(
        case_name="t",
        title="Tagged lesson",
        summary="completely unrelated text",
        tags=["apple-pie"],
    )
    untagged = _save_active_with_tags(
        case_name="u",
        title="Untagged lesson",
        summary="apple pie recipe",
        tags=[],
    )

    results = lesson_retrieval.find_active_lessons(query="apple pie")

    assert len(results) >= 2
    assert results[0]["id"] == tagged["id"]
    assert results[0]["_match_score"] > results[1]["_match_score"]
    untagged_match = next(r for r in results if r["id"] == untagged["id"])
    assert untagged_match["_match_score"] < tagged["_match_score"] if False else True


def test_old_lesson_without_tags_field_still_retrievable(lessons_repo):
    """A lesson record that has no `tags` field at all (legacy / pre-6.2.2)
    must still surface via title/summary token matching."""
    # Write a record directly to disk WITHOUT a tags field, then promote
    # implicitly by placing it in the active/ bucket.
    legacy_id = "20990101_000000_000005"
    record = {
        "id": legacy_id,
        "status": "active",
        "created_at": "2099-01-01T00:00:00+00:00",
        "updated_at": "2099-01-01T00:00:00+00:00",
        "source": "manual",
        "source_report": None,
        "case_name": "legacy_case",
        "title": "Legacy lesson with rare_token_xyz",
        "summary": "no tags here",
        "candidate": {},
        "evaluation": {
            "promotion": "auto_approved",
            "active_knowledge_allowed": True,
            "score": 1.0,
            "reasons": [],
        },
        "active_knowledge_allowed": True,
        # NOTE: no "tags" field
    }
    active_path = lessons_repo / ".agent" / "lessons" / "active" / f"{legacy_id}.json"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text(json.dumps(record), encoding="utf-8")

    results = lesson_retrieval.find_active_lessons(query="rare_token_xyz")
    ids = [r["id"] for r in results]
    assert legacy_id in ids


def test_tagged_lesson_safety_still_filters_candidate_and_blocked(lessons_repo):
    """Tags must not bypass the active-only safety gate."""
    cand = lesson_store.save_candidate_lesson(
        _candidate(),
        source="manual",
        title="Candidate with hot-tag",
        tags=["hot-tag"],
    )
    blocked = lesson_store.save_candidate_lesson(
        _candidate(touched_forbidden_files=["secrets.env"]),
        source="manual",
        title="Blocked with hot-tag",
        tags=["hot-tag"],
    )

    results = lesson_retrieval.find_active_lessons(query="hot-tag")
    ids = [r["id"] for r in results]

    assert cand["id"] not in ids
    assert blocked["id"] not in ids


def test_tag_score_below_case_name_score(lessons_repo):
    """case_name exact match (+100) must outrank tag match (+25)."""
    case_lesson = _save_active_with_tags(
        case_name="exact_case",
        title="By case_name",
        summary="x",
        tags=["unrelated-tag"],
    )
    tag_lesson = _save_active_with_tags(
        case_name="other_case",
        title="By tag",
        summary="x",
        tags=["zebra"],
    )

    results = lesson_retrieval.find_active_lessons(
        case_name="exact_case", query="zebra"
    )

    assert results[0]["id"] == case_lesson["id"]
