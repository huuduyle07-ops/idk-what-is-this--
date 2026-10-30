"""Generation reservations, source pins and observable practice state."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from core.learning import practice_store as module
from core.learning.practice_store import PracticeStore
from core.learning.store import LearningError

OWNER, OTHER = "a" * 64, "b" * 64
REQUEST = "generation-request-001"
COLLECTION = "c" * 32
UNIT = "unit-" + "d" * 64
SOURCE = "sha256:" + "e" * 64


def prepared(*, image=False, count=3):
    excerpt = {"excerpt_id": "E1", "unit_id": UNIT, "source_id": SOURCE,
               "source_name": "lesson.png" if image else "lesson.pdf",
               "locator": {"kind": "image" if image else "page", "index": 1},
               "text": "A semaphore controls access. Interrupt handlers respond to interrupts.",
               "origin": "user_note" if image else "extracted"}
    if image:
        excerpt["annotation_revision"] = 2
    return {"scope": {"collection_id": COLLECTION, "collection_title": "Operating systems",
                      "unit_ids": [UNIT], "count": count}, "excerpts": [excerpt]}


def bundle(snapshot=None):
    snapshot = snapshot or prepared()
    quote = {key: deepcopy(value) for key, value in snapshot["excerpts"][0].items() if key != "excerpt_id"}
    quote["text"] = "A semaphore controls access."
    return {"title": "Operating systems practice", "scope": deepcopy(snapshot["scope"]),
            "provider": "ollama", "model": "test-model", "questions": [
                {"id": f"q{index + 1}", "objective": "Identify synchronization concepts",
                 "question": f"Which option describes semaphore behavior in example {index + 1}?",
                 "options": [{"id": key, "text": text} for key, text in zip("abcd", ["Controls access", "Renders images", "Deletes programs", "Stores passwords"])],
                 "correct_option": "a", "explanation": "The source says a semaphore controls access.",
                 "hints": ["Think about shared resources.", "Look for access control."], "evidence": [deepcopy(quote)]}
                for index in range(snapshot["scope"]["count"])]}


@pytest.fixture
def store(tmp_path):
    return PracticeStore(tmp_path / "practice" / "practice.sqlite3")


def error(code, method, *args):
    with pytest.raises(LearningError) as raised:
        method(*args)
    assert raised.value.code == code
    return raised.value


def draft(store, snapshot=None, owner=OWNER, request=REQUEST):
    snapshot = snapshot or prepared()
    claim = store.reserve(owner, request, snapshot)
    return store.finish(owner, claim["practice"]["id"], request, bundle(snapshot))


def act(store, practice, action, payload=None, request=None):
    return store.act(OWNER, practice["id"], action, payload or {}, practice["revision"], request or f"action-request-{practice['revision']:04}")


def selection(snapshot=None):
    return {key: (snapshot or prepared())["scope"][key] for key in ("collection_id", "unit_ids", "count")}


def test_empty_reads_do_not_create_database(store):
    assert store.list(OWNER) == []
    assert store.lookup_request(OWNER, REQUEST, selection()) is None
    error("practice_not_found", store.get, OWNER, "f" * 32)
    assert not store.path.parent.exists()


def test_reserve_is_durable_once_and_draft_hides_private_fields(store):
    first = store.reserve(OWNER, REQUEST, prepared())
    assert first["claimed"] and first["practice"]["status"] == "generating"
    assert first["practice"]["revision"] == 0 and first["practice"]["questions"] == []
    retry = PracticeStore(store.path).reserve(OWNER, REQUEST, prepared())
    assert not retry["claimed"] and retry["practice"] == first["practice"]
    result = store.finish(OWNER, first["practice"]["id"], REQUEST, bundle())
    assert result["status"] == "draft" and result["revision"] == 1
    for question in result["questions"]:
        assert question["answer"] is None and question["hints"] == []
        assert not {"correct_option", "explanation", "evidence"} & set(question)
    assert store.finish(OWNER, result["id"], REQUEST, bundle()) == result
    assert store.lookup_request(OWNER, REQUEST, selection()) == result
    assert "questions" not in store.list(OWNER)[0]


def test_reservation_ignores_mutable_title_and_snapshot_on_retry(store):
    first = store.reserve(OWNER, REQUEST, prepared(image=True))
    changed = prepared(image=True)
    changed["scope"]["collection_title"] = "New title"
    changed["excerpts"][0].update(text="Changed user note.", annotation_revision=3)
    retry = store.reserve(OWNER, REQUEST, changed)
    assert not retry["claimed"] and retry["practice"] == first["practice"]
    result = store.finish(OWNER, first["practice"]["id"], REQUEST, bundle(prepared(image=True)))
    result = act(store, result, "review_answer", {"item_id": "q1"})
    evidence = result["questions"][0]["answer"]["evidence"][0]
    assert evidence["annotation_revision"] == 2 and evidence["origin"] == "user_note"


@pytest.mark.parametrize("field,value", [("collection_id", "f" * 32), ("unit_ids", ["unit-" + "f" * 64]), ("count", 4)])
def test_request_reuse_with_different_selection_conflicts(store, field, value):
    store.reserve(OWNER, REQUEST, prepared())
    changed = selection()
    changed[field] = value
    assert error("practice_conflict", store.lookup_request, OWNER, REQUEST, changed).status_code == 409


def test_owner_isolation_and_request_namespaces(store):
    item = draft(store)
    other = draft(store, owner=OTHER)
    assert other["id"] != item["id"]
    assert [row["id"] for row in store.list(OWNER)] == [item["id"]]
    for method, args in ((store.get, (OTHER, item["id"])), (store.delete, (OTHER, item["id"])),
                         (store.finish, (OTHER, item["id"], REQUEST, bundle())),
                         (store.fail, (OTHER, item["id"], REQUEST)),
                         (store.act, (OTHER, item["id"], "start", {}, 1, "start-request-001"))):
        error("practice_not_found", method, *args)


@pytest.mark.parametrize("owner", [None, "a", "A" * 64, "../owner", True, [OWNER]])
def test_invalid_owner_does_not_create_storage(store, owner):
    error("practice_invalid", store.reserve, owner, REQUEST, prepared())
    assert not store.path.exists()


def test_expired_request_fails_once_and_late_model_cannot_restore_it(store, monkeypatch):
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    claim = store.reserve(OWNER, REQUEST, prepared())
    monkeypatch.setattr(module.time, "time", lambda: 1181.0)
    failed = store.lookup_request(OWNER, REQUEST, selection())
    assert failed["status"] == "failed" and failed["revision"] == 1
    assert failed["error"]["code"] == "practice_generation_failed"
    assert store.finish(OWNER, claim["practice"]["id"], REQUEST, bundle()) == failed
    assert not store.reserve(OWNER, REQUEST, prepared())["claimed"]
    assert store.fail(OWNER, failed["id"], REQUEST) == failed


def test_failure_is_sanitized_and_cannot_be_regenerated(store):
    claim = store.reserve(OWNER, REQUEST, prepared())
    result = store.fail(OWNER, claim["practice"]["id"], REQUEST)
    assert result["status"] == "failed" and set(result["error"]) == {"code", "message"}
    assert store.finish(OWNER, result["id"], REQUEST, bundle()) == result
    assert not store.reserve(OWNER, REQUEST, prepared())["claimed"]
    assert store.reserve(OWNER, "generation-request-002", prepared())["claimed"]


def test_finish_wrong_generation_request_and_changed_bundle_conflict(store):
    item = draft(store)
    error("practice_conflict", store.finish, OWNER, item["id"], "different-request-001", bundle())
    changed = bundle()
    changed["title"] = "Different generated result"
    error("practice_conflict", store.finish, OWNER, item["id"], REQUEST, changed)
    assert store.fail(OWNER, item["id"], REQUEST) == item


@pytest.mark.parametrize("field,value", [
    ("unit_id", "unit-" + "f" * 64), ("source_id", "sha256:" + "f" * 64),
    ("source_name", "other.pdf"), ("locator", {"kind": "page", "index": 99}),
    ("text", "Invented exact quote"), ("origin", "user_note"), ("annotation_revision", 2),
])
def test_finish_rejects_forged_source_evidence_without_publishing(store, field, value):
    claim = store.reserve(OWNER, REQUEST, prepared())
    changed = bundle()
    changed["questions"][0]["evidence"][0][field] = value
    error("practice_invalid", store.finish, OWNER, claim["practice"]["id"], REQUEST, changed)
    assert store.get(OWNER, claim["practice"]["id"])["status"] == "generating"


def test_finish_rejects_wrong_note_revision_and_question_count(store):
    snapshot = prepared(image=True)
    claim = store.reserve(OWNER, REQUEST, snapshot)
    changed = bundle(snapshot)
    changed["questions"][0]["evidence"][0]["annotation_revision"] = 3
    error("practice_invalid", store.finish, OWNER, claim["practice"]["id"], REQUEST, changed)
    changed = bundle(snapshot)
    changed["questions"].pop()
    error("practice_invalid", store.finish, OWNER, claim["practice"]["id"], REQUEST, changed)


def test_draft_review_persists_without_claiming_independent_results(store):
    item = act(store, draft(store), "review_answer", {"item_id": "q2"})
    assert item["questions"][1]["answer"]["correct_option"] == "a"
    assert item["questions"][0]["answer"] is None
    item = act(store, item, "start")
    assert item["summary"]["answers_reviewed_before_start"] == 1
    assert item["questions"][1]["answer_reviewed"]
    assert "do not establish independent performance or mastery" in item["summary"]["message"]
    error("practice_conflict", store.act, OWNER, item["id"], "review_answer", {"item_id": "q1"}, item["revision"], "review-active-001")


def test_wrong_answer_then_hints_then_correct_does_not_expose_early_answer(store):
    item = act(store, draft(store), "start")
    error("practice_conflict", store.act, OWNER, item["id"], "next", {}, item["revision"], "early-next-000001")
    item = act(store, item, "answer", {"item_id": "q1", "option_id": "b", "reflection": "My initial guess"})
    question = item["questions"][0]
    assert question["feedback"]["correct"] is False and question["answer"] is None
    assert question["first_try_correct"] is False and question["attempts"] == 1
    error("practice_conflict", store.act, OWNER, item["id"], "next", {}, item["revision"], "wrong-next-000001")
    item = act(store, item, "hint", {"item_id": "q1"})
    assert item["questions"][0]["hints"] == ["Think about shared resources."]
    assert item["questions"][0]["answer"] is None
    item = act(store, item, "hint", {"item_id": "q1"})
    assert len(item["questions"][0]["hints"]) == 2
    error("practice_conflict", store.act, OWNER, item["id"], "hint", {"item_id": "q1"}, item["revision"], "extra-hint-000001")
    item = act(store, item, "answer", {"item_id": "q1", "option_id": "a", "reflection": "It controls access"})
    assert item["questions"][0]["answer"]["correct_option"] == "a"
    assert item["summary"]["correct_after_help"] == 1 and item["summary"]["first_try_correct"] == 0
    item = act(store, item, "next")
    assert item["current_index"] == 1 and item["questions"][1]["answer"] is None


def test_solution_allows_progress_and_completion_without_fabricated_attempt(store):
    item = act(store, draft(store), "start")
    for index in range(3):
        item = act(store, item, "solution", {"item_id": f"q{index + 1}"})
        assert item["questions"][index]["answer"] is not None
        item = act(store, item, "next")
    assert item["status"] == "completed" and item["summary"]["answered_count"] == 0
    assert item["summary"]["first_try_correct"] == 0
    error("practice_conflict", store.act, OWNER, item["id"], "start", {}, item["revision"], "restart-request-01")


def test_correct_first_try_and_reviewed_correct_are_observations(store):
    item = act(store, draft(store), "review_answer", {"item_id": "q2"})
    item = act(store, item, "start")
    for index in range(2):
        item = act(store, item, "answer", {"item_id": f"q{index + 1}", "option_id": "a", "reflection": ""})
        item = act(store, item, "next")
    assert item["summary"]["first_try_correct"] == 2
    assert item["summary"]["correct_after_help"] == 1


def test_lost_action_response_replay_returns_current_state_without_duplicate_action(store):
    initial = draft(store)
    item = act(store, initial, "start", request="stable-start-request")
    later = act(store, item, "hint", {"item_id": "q1"})
    replay = store.act(OWNER, item["id"], "start", {}, initial["revision"], "stable-start-request")
    assert replay == later
    error("practice_conflict", store.act, OWNER, item["id"], "next", {}, initial["revision"], "stable-start-request")
    error("practice_conflict", store.act, OWNER, item["id"], "hint", {"item_id": "q1"}, item["revision"], "different-stale-request")


@pytest.mark.parametrize("action,payload", [
    ("answer", {"item_id": "q2", "option_id": "a", "reflection": ""}),
    ("hint", {"item_id": "q2"}), ("solution", {"item_id": "q2"}),
])
def test_actions_cannot_skip_to_future_item(store, action, payload):
    item = act(store, draft(store), "start")
    error("practice_conflict", store.act, OWNER, item["id"], action, payload, item["revision"], "skip-request-00001")


@pytest.mark.parametrize("action,payload,revision", [
    ("start", {"extra": True}, 1), ("unknown", {}, 1), ("start", [], 1),
    ("answer", {"item_id": "q1", "option_id": "e", "reflection": ""}, 1),
    ("answer", {"item_id": "q1", "option_id": "a", "reflection": "x" * 1601}, 1),
    ("answer", {"item_id": "q1", "option_id": "a", "reflection": "\ud800"}, 1),
    ("start", {}, True), ("start", {}, -1), ("start", {}, 1.0),
])
def test_invalid_actions_do_not_mutate(store, action, payload, revision):
    item = draft(store)
    error("practice_invalid", store.act, OWNER, item["id"], action, payload, revision, "bad-action-request")
    assert store.get(OWNER, item["id"]) == item


def test_quotas_and_delete_tombstone_preserve_once_only_generation(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_PRACTICES", 1)
    item = draft(store)
    assert error("practice_limit", store.reserve, OWNER, "generation-request-002", prepared()).status_code == 429
    assert not store.reserve(OWNER, REQUEST, prepared())["claimed"]
    assert store.delete(OWNER, item["id"]) == {"id": item["id"], "deleted": True}
    assert store.list(OWNER) == []
    error("practice_not_found", store.lookup_request, OWNER, REQUEST, selection())
    error("practice_not_found", store.reserve, OWNER, REQUEST, prepared())
    assert store.reserve(OWNER, "generation-request-002", prepared())["claimed"]


def test_action_quota_allows_replay_but_blocks_new_mutation(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_ACTIONS", 1)
    initial = draft(store)
    item = act(store, initial, "start", request="stable-start-request")
    assert store.act(OWNER, item["id"], "start", {}, 1, "stable-start-request") == item
    error("practice_limit", store.act, OWNER, item["id"], "hint", {"item_id": "q1"}, item["revision"], "extra-action-00001")


def test_pending_generation_can_only_be_deleted_after_expiry(store, monkeypatch):
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    item = store.reserve(OWNER, REQUEST, prepared())["practice"]
    error("practice_conflict", store.delete, OWNER, item["id"])
    assert store.get(OWNER, item["id"])["status"] == "generating"
    monkeypatch.setattr(module.time, "time", lambda: 1181.0)
    assert store.delete(OWNER, item["id"])["deleted"] is True
    error("practice_not_found", store.lookup_request, OWNER, REQUEST, selection())


def test_deleted_sets_cannot_reset_generation_request_history_quota(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_GENERATION_REQUESTS", 1)
    item = draft(store)
    store.delete(OWNER, item["id"])
    assert store.list(OWNER) == []
    failure = error("practice_limit", store.reserve, OWNER, "generation-request-002", prepared())
    assert failure.status_code == 429
    error("practice_not_found", store.reserve, OWNER, REQUEST, prepared())


def test_concurrent_generation_claims_once(store):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.reserve(OWNER, REQUEST, prepared()), range(2)))
    assert sum(result["claimed"] for result in results) == 1
    assert len({result["practice"]["id"] for result in results}) == 1


def test_concurrent_actions_have_one_cas_winner(store):
    item = draft(store)
    def attempt(index):
        try:
            return store.act(OWNER, item["id"], "review_answer", {"item_id": f"q{index + 1}"}, item["revision"], f"concurrent-request-{index}")
        except LearningError as exception:
            return exception.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "practice_conflict" in results


@pytest.mark.parametrize("column,value", [
    ("prepared_json", '{"scope":{},"scope":{},"excerpts":[]}'),
    ("bundle_json", "{}"), ("state_json", "{broken"), ("state_json", "null"),
    ("revision", -1), ("status", "unexpected"), ("created_at", -1),
    ("prepared_json", " " * (128 * 1024 + 1)),
], ids=["duplicate-json", "empty-bundle", "broken-state", "null-state", "negative-revision", "unknown-status", "negative-time", "oversized-json"])
def test_corrupt_saved_state_fails_closed(store, column, value):
    item = draft(store)
    with sqlite3.connect(store.path) as connection:
        connection.execute(f"UPDATE practices SET {column}=? WHERE id=?", (value, item["id"]))
    assert error("practice_storage_error", store.get, OWNER, item["id"]).status_code == 500


def test_existing_unrelated_database_is_not_adopted(store):
    store.path.parent.mkdir(parents=True)
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    error("practice_storage_error", store.reserve, OWNER, REQUEST, prepared())
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("unrelated",)]


def test_storage_cap_rejects_payload_before_publishing(store, monkeypatch):
    claim = store.reserve(OWNER, REQUEST, prepared())
    monkeypatch.setattr(module, "MAX_JSON_BYTES", 2000)
    error("practice_limit", store.finish, OWNER, claim["practice"]["id"], REQUEST, bundle())
    assert store.get(OWNER, claim["practice"]["id"])["status"] == "generating"


def test_redirected_database_and_sidecars_are_rejected(store, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: str(path).endswith("-wal") or original(path))
    error("practice_storage_error", store.reserve, OWNER, REQUEST, prepared())
    assert not store.path.exists()
