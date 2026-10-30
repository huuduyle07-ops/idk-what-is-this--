"""Saved seeded tests preserve drafts, hidden keys and explicit submission."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from core.learning import test_maker_store as module
from core.learning.test_maker_store import TestMakerStore as Store
from core.learning.test_maker import build_test, catalog
from core.learning.store import LearningError

OWNER, OTHER = "a" * 64, "b" * 64
REQUEST = "test-maker-request-001"
SEED = 12345


def topics(*kinds):
    return [next(item["id"] for item in catalog() if item["kind"] == kind) for kind in kinds]


def selection(ids=None, seed=SEED):
    return {"topic_ids": topics("numeric", "essay") if ids is None else ids, "seed": seed}


def create(store, ids=None, seed=SEED, owner=OWNER, request=REQUEST):
    value = selection(ids, seed)
    return store.create(owner, request, value["topic_ids"], seed)


def key_answers(snapshot):
    answers = {}
    for question in snapshot["questions"]:
        key = question["answer_key"]
        if question["kind"] == "numeric":
            answers[question["id"]] = key["value"]
        elif question["kind"] == "matrix":
            answers[question["id"]] = deepcopy(key["cells"])
        elif question["kind"] == "diagram":
            answers[question["id"]] = {slot: values[0] for slot, values in key["slots"].items()}
        else:
            answers[question["id"]] = key["model_answer"]
    return answers


def act(store, view, action, answers, request=None):
    return store.act(OWNER, view["id"], action, {"answers": answers}, view["revision"], request or f"test-action-{view['revision']:06}")


def error(code, method, *args, **kwargs):
    with pytest.raises(LearningError) as caught:
        method(*args, **kwargs)
    assert caught.value.code == code
    return caught.value


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "tests" / "test_maker.sqlite3")


def test_empty_reads_do_not_create_database(store):
    assert store.list(OWNER) == []
    assert store.lookup_request(OWNER, REQUEST, selection()) is None
    error("test_maker_not_found", store.get, OWNER, "f" * 32)
    assert not store.path.parent.exists()


def test_seeded_creation_is_once_only_hidden_and_order_independent(store):
    ids = topics("numeric", "essay")
    first = create(store, ids)
    assert first["status"] == "active" and first["revision"] == 0 and first["seed"] == SEED
    assert first["answers"] == {} and first["results"] is None
    assert len(first["questions"]) == 2
    for question in first["questions"]:
        assert not {"answer_key", "explanation", "rubric"} & question.keys()
    assert Store(store.path).get(OWNER, first["id"]) == first
    assert create(store, list(reversed(ids))) == first
    assert store.lookup_request(OWNER, REQUEST, selection(ids)) == first
    summary = store.list(OWNER)[0]
    assert summary["question_count"] == 2 and "questions" not in summary and "answers" not in summary and "results" not in summary
    assert len(store.list(OWNER)) == 1


@pytest.mark.parametrize("change", [{"topic_ids": []}, {"seed": True}, {"seed": -1}, {"seed": 2**31},
                                   {"seed": 3.0}, {"topic_ids": ["unknown"]}, {"topic_ids": [None]}])
def test_invalid_selection_never_creates_store(store, change):
    value = {**selection(), **change}
    error("test_maker_invalid", store.create, OWNER, REQUEST, value["topic_ids"], value["seed"])
    assert not store.path.exists()


def test_duplicate_topics_and_changed_request_selection_are_rejected(store):
    ids = topics("numeric", "essay")
    error("test_maker_invalid", store.create, OWNER, REQUEST, [ids[0], ids[0]], SEED)
    first = create(store, ids)
    error("test_maker_conflict", store.lookup_request, OWNER, REQUEST, selection(ids, SEED + 1))
    error("test_maker_conflict", create, store, ids[:1])
    assert create(store, ids) == first


@pytest.mark.parametrize("owner", [None, "person", "a" * 63, "../" + "a" * 64])
def test_invalid_owner_does_not_publish_database(store, owner):
    error("test_maker_invalid", create, store, owner=owner)
    assert not store.path.exists()


def test_owner_isolation_and_separate_request_namespaces(store):
    first = create(store)
    second = create(store, owner=OTHER)
    assert second["id"] != first["id"]
    assert [item["id"] for item in store.list(OWNER)] == [first["id"]]
    for method, args in ((store.get, (OTHER, first["id"])), (store.delete, (OTHER, first["id"])),
                         (store.act, (OTHER, first["id"], "save", {"answers": {}}, 0, "foreign-action-001"))):
        assert error("test_maker_not_found", method, *args).status_code == 404


def test_save_partial_merge_never_grades_and_submit_uses_saved_answers(store, monkeypatch):
    ids = topics("numeric", "essay")
    view = create(store, ids)
    private = build_test(ids, SEED)
    answers = key_answers(private)
    q_numeric = next(q for q in private["questions"] if q["kind"] == "numeric")
    q_essay = next(q for q in private["questions"] if q["kind"] == "essay")
    original_grade = module.grade_question
    monkeypatch.setattr(module, "grade_question", lambda *args: pytest.fail("draft save cannot grade or reveal keys"))
    view = act(store, view, "save", {q_numeric["id"]: answers[q_numeric["id"]]})
    view = act(store, view, "save", {q_essay["id"]: "My argument with assumptions and an example."})
    assert len(view["answers"]) == 2 and view["results"] is None
    view = act(store, view, "save", {})
    assert len(view["answers"]) == 2
    monkeypatch.setattr(module, "grade_question", original_grade)
    submitted = act(store, view, "submit", {})
    assert submitted["status"] == "submitted"
    assert submitted["results"]["auto"] == {"earned": q_numeric["points"], "possible": q_numeric["points"]}
    assert submitted["results"]["essay"] == {"answered": 1, "pending": 1, "total": 1}
    essay_grade = next(item for item in submitted["results"]["items"] if item["question_id"] == q_essay["id"])
    assert essay_grade["status"] == "pending_review" and essay_grade["earned"] is None
    assert submitted["results"]["items"][0]["expected"] is not None
    assert all("answer_key" not in q for q in submitted["questions"])
    assert Store(store.path).get(OWNER, submitted["id"]) == submitted


def test_all_supported_answer_types_roundtrip_and_essays_never_enter_auto_score(store):
    ids = [item["id"] for item in catalog()]
    private = build_test(ids, SEED)
    answers = key_answers(private)
    view = act(store, create(store, ids), "save", answers)
    assert view["answers"] == answers
    view = act(store, view, "submit", {})
    results = view["results"]
    possible = sum(q["points"] for q in private["questions"] if q["kind"] != "essay")
    assert results["auto"] == {"earned": possible, "possible": possible}
    essays = sum(q["kind"] == "essay" for q in private["questions"])
    assert results["essay"] == {"answered": essays, "pending": essays, "total": essays}
    assert not {"overall", "grade", "mastery"} & results.keys()


def test_invalid_numeric_syntax_is_saved_then_graded_incorrect_without_execution(store):
    ids = topics("numeric")
    view = create(store, ids)
    qid = view["questions"][0]["id"]
    malicious = "__import__('os').system('echo unsafe')"
    view = act(store, view, "save", {qid: malicious})
    assert view["answers"][qid] == malicious and view["results"] is None
    view = act(store, view, "submit", {})
    result = view["results"]["items"][0]
    assert result["earned"] == 0 and result["correct"] is False


def test_blank_submission_counts_unanswered_and_no_auto_points_for_essays(store):
    view = act(store, create(store), "submit", {})
    assert all(result["status"] == "unanswered" for result in view["results"]["items"])
    assert view["results"]["auto"]["earned"] == 0
    assert view["results"]["essay"] == {"answered": 0, "pending": 0, "total": 1}
    essay_only = create(store, topics("essay"), request="essay-only-request-001")
    essay_only = act(store, essay_only, "submit", {essay_only["questions"][0]["id"]: "A substantive argument."})
    assert essay_only["results"]["auto"] == {"earned": 0, "possible": 0}


def test_exact_action_replay_does_not_submit_or_save_twice(store):
    initial = create(store)
    args = (OWNER, initial["id"], "save", {"answers": {}}, 0, "stable-save-request")
    saved = store.act(*args)
    assert store.act(*args) == saved and saved["revision"] == 1
    error("test_maker_conflict", store.act, OWNER, initial["id"], "submit", {"answers": {}}, 0, "new-stale-request")
    submitted = act(store, saved, "submit", {}, request="stable-submit-request")
    assert store.act(OWNER, initial["id"], "submit", {"answers": {}}, 1, "stable-submit-request") == submitted
    assert store.act(*args) == submitted
    error("test_maker_conflict", act, store, submitted, "save", {})
    error("test_maker_conflict", act, store, submitted, "submit", {})


@pytest.mark.parametrize("action,payload,revision", [("unknown", {"answers": {}}, 0), ("save", {}, 0),
    ("save", {"answers": {}, "extra": True}, 0), ("save", {"answers": []}, 0),
    ("save", {"answers": {"q99": "wrong question"}}, 0), ("save", {"answers": {}}, True),
    ("save", {"answers": {}}, -1), ("save", {"answers": {}}, 0.0)])
def test_invalid_action_cannot_modify_draft(store, action, payload, revision):
    view = create(store)
    error("test_maker_invalid", store.act, OWNER, view["id"], action, payload, revision, "invalid-action-001")
    assert store.get(OWNER, view["id"]) == view


@pytest.mark.parametrize("kind,answer", [("numeric", True), ("numeric", "x" * 101), ("numeric", "\ud800"),
                                      ("matrix", [["1"]]), ("diagram", {"unknown": "x"}), ("essay", "x" * 4001)])
def test_answer_type_and_size_limits_are_checked_before_save(store, kind, answer):
    view = create(store, topics(kind))
    qid = view["questions"][0]["id"]
    error("test_maker_invalid", act, store, view, "save", {qid: answer})
    assert store.get(OWNER, view["id"]) == view


def test_delete_preserves_request_tombstone_and_quotas(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_TESTS", 1)
    view = create(store)
    assert create(store) == view
    error("test_maker_limit", create, store, request="different-request-001")
    store.delete(OWNER, view["id"])
    assert store.list(OWNER) == []
    error("test_maker_not_found", create, store)
    error("test_maker_not_found", store.lookup_request, OWNER, REQUEST, selection())
    monkeypatch.setattr(module, "MAX_CREATE_REQUESTS", 1)
    error("test_maker_limit", create, store, request="different-request-001")


def test_action_quota_still_allows_successful_request_replay(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_ACTIONS", 1)
    view = create(store)
    saved = act(store, view, "save", {}, request="quota-save-request")
    assert store.act(OWNER, view["id"], "save", {"answers": {}}, 0, "quota-save-request") == saved
    error("test_maker_limit", act, store, saved, "submit", {})


def test_concurrent_creation_and_compare_and_swap_have_one_winner(store):
    with ThreadPoolExecutor(max_workers=2) as executor:
        views = list(executor.map(lambda _: create(store), range(2)))
    assert views[0]["id"] == views[1]["id"] and len(store.list(OWNER)) == 1
    def save(index):
        try:
            return act(store, views[0], "save", {}, request=f"concurrent-save-{index}")
        except LearningError as exception:
            return exception.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1 and "test_maker_conflict" in results


@pytest.mark.parametrize("damage", ["snapshot", "seed_type", "answers", "duplicate", "score", "status", "revision", "oversize"])
def test_corrupt_snapshot_answers_or_score_fail_closed(store, damage):
    view = act(store, create(store), "submit", {})
    with sqlite3.connect(store.path) as connection:
        if damage == "snapshot": connection.execute("UPDATE tests SET snapshot_json='{}'")
        elif damage == "answers": connection.execute("UPDATE tests SET answers_json='[]'")
        elif damage == "duplicate": connection.execute("UPDATE tests SET answers_json=?", ('{"q1":"a","q1":"b"}',))
        elif damage == "status": connection.execute("UPDATE tests SET status='active'")
        elif damage == "revision": connection.execute("UPDATE tests SET revision=-1")
        elif damage == "oversize": connection.execute("UPDATE tests SET snapshot_json=?", (" " * (128*1024+1),))
        else:
            column = "snapshot_json" if damage == "seed_type" else "results_json"
            data = json.loads(connection.execute(f"SELECT {column} FROM tests").fetchone()[0])
            if damage == "seed_type": data["seed"] = True
            else: data["auto"]["earned"] = 999999
            connection.execute(f"UPDATE tests SET {column}=?", (json.dumps(data),))
    assert error("test_maker_storage_error", store.get, OWNER, view["id"]).status_code == 500


def test_unrelated_database_and_symlink_sidecars_are_rejected(store, monkeypatch):
    store.path.parent.mkdir(parents=True)
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    error("test_maker_storage_error", create, store)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: str(path).endswith("-wal") or original(path))
    error("test_maker_storage_error", store.list, OWNER)


def test_oversized_snapshots_fail_before_publication(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_JSON_BYTES", 100)
    error("test_maker_limit", create, store)
    assert not store.path.exists()
