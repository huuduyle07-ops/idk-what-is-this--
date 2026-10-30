"""Hidden card answers, durable source pins and observable self-rating schedules."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from core.learning import flashcard_store as module
from core.learning.flashcard_store import FlashcardStore
from core.learning.practice_store import PracticeStore
from core.learning.store import LearningError
from tests.learning.test_practice_store import prepared, bundle

OWNER, OTHER = "a" * 64, "b" * 64
REQUEST = "flashcard-request-00001"
PRACTICE = "e" * 32


def completed(*, image=False):
    generated = bundle(prepared(image=image))
    questions = []
    for index, q in enumerate(generated["questions"]):
        questions.append({"id": q["id"], "question": q["question"], "objective": q["objective"], "options": q["options"],
                          "answer": {key: q[key] for key in ("correct_option", "explanation", "evidence")},
                          "first_try_correct": index == 0, "hint_count": 1 if index == 1 else 0,
                          "solution_viewed": index == 2, "answer_reviewed": False})
    return {"id": PRACTICE, "status": "completed", "title": generated["title"], "scope": generated["scope"],
            "provider": generated["provider"], "model": generated["model"], "questions": questions}


@pytest.fixture
def store(tmp_path):
    return FlashcardStore(tmp_path / "cards" / "flashcards.sqlite3")


def fail(code, method, *args, **kwargs):
    with pytest.raises(LearningError) as caught:
        method(*args, **kwargs)
    assert caught.value.code == code
    return caught.value


def selection():
    return {"practice_id": PRACTICE, "question_ids": ["q1", "q2", "q3"]}


def create(store, *, owner=OWNER, request=REQUEST, practice=None, ids=None):
    return store.create(owner, request, practice or completed(), ["q1", "q2", "q3"] if ids is None else ids)


def act(store, view, action, payload, *, request=None):
    return store.act(OWNER, view["id"], action, payload, view["revision"], request or f"card-action-{view['revision']:06}")


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def test_empty_reads_do_not_create_store(store):
    assert store.list(OWNER) == []
    assert store.lookup_request(OWNER, REQUEST, selection()) is None
    fail("flashcards_not_found", store.get, OWNER, "f" * 32)
    assert not store.path.parent.exists()


def test_create_pins_selected_cards_and_hides_answers_and_choices(store):
    before = completed()
    view = create(store, practice=before, ids=["q3", "q1"])
    assert view["revision"] == 0 and [c["id"] for c in view["cards"]] == ["q1", "q3"]
    assert view["counts"] == {"total": 2, "due": 2, "needs_review": 1}
    assert all(card["answer"] is None and card["choices"] is None and not card["revealed"] for card in view["cards"])
    assert "correct_option" not in json.dumps(view) and "explanation" not in json.dumps(view)
    assert "cards" not in store.list(OWNER)[0]
    assert completed() == before
    assert FlashcardStore(store.path).get(OWNER, view["id"]) == view
    revealed = act(store, view, "reveal", {"card_id": "q3"})
    card = revealed["cards"][1]
    assert card["answer"]["text"] == "Controls access"
    assert card["answer"]["evidence"] == before["questions"][2]["answer"]["evidence"]
    assert card["choices"] is None


def test_creation_retry_returns_current_deck_ignores_snapshot_changes(store):
    first = create(store)
    updated = act(store, first, "choices", {"card_id": "q2"})
    changed = {"id": PRACTICE, "status": "deleted"}
    assert create(store, practice=changed, ids=["q3", "q2", "q1"]) == updated
    assert store.lookup_request(OWNER, REQUEST, selection()) == updated
    assert len(store.list(OWNER)) == 1
    fail("flashcards_conflict", store.lookup_request, OWNER, REQUEST, {"practice_id": PRACTICE, "question_ids": ["q1"]})


@pytest.mark.parametrize("status", ["draft", "active", "generating", "failed"])
def test_only_completed_practice_can_create_cards(store, status):
    practice = completed()
    practice["status"] = status
    assert fail("flashcards_not_completed", create, store, practice=practice).status_code == 409
    assert not store.path.exists()


@pytest.mark.parametrize("ids", [[], ["q1", "q1"], ["q4"], ["../../q1"], "q1", [True], ["q1", "q2", "q3", "q4", "q5", "q1"]])
def test_invalid_selection_never_publishes_deck(store, ids):
    fail("flashcards_invalid", store.create, OWNER, REQUEST, completed(), ids)
    assert not store.path.exists()


@pytest.mark.parametrize("owner", ["other", None, "a" * 63, "../" + "a" * 64])
def test_invalid_owner_never_creates_store(store, owner):
    fail("flashcards_invalid", store.create, owner, REQUEST, completed(), ["q1"])
    assert not store.path.exists()


def test_owner_isolation_and_request_namespaces(store):
    view = create(store)
    other = create(store, owner=OTHER)
    assert other["id"] != view["id"]
    assert [d["id"] for d in store.list(OWNER)] == [view["id"]]
    for method, args in ((store.get, (OTHER, view["id"])), (store.delete, (OTHER, view["id"])),
                         (store.act, (OTHER, view["id"], "reveal", {"card_id": "q1"}, 0, "foreign-action-00001"))):
        assert fail("flashcards_not_found", method, *args).status_code == 404


def test_choices_reveal_hide_and_rating_require_explicit_flip(store):
    view = create(store)
    fail("flashcards_conflict", store.act, OWNER, view["id"], "rate", {"card_id": "q1", "rating": "got_it"}, 0, "unrevealed-rate-001")
    view = act(store, view, "choices", {"card_id": "q1"})
    assert view["cards"][0]["choices"] and view["cards"][0]["answer"] is None
    view = act(store, view, "reveal", {"card_id": "q1"})
    assert view["cards"][0]["revealed"]
    view = act(store, view, "hide", {"card_id": "q1"})
    card = view["cards"][0]
    assert not card["revealed"] and card["answer"] is None and card["choices"] is None and card["review_count"] == 0


def test_simple_schedule_and_due_counts_are_self_rating_observations(store, monkeypatch):
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    view = create(store)
    assert all(stamp(c["due_at"]) == 1000 for c in view["cards"])
    for expected_streak, days in [(1, 1), (2, 3), (3, 7), (4, 7)]:
        view = act(store, view, "reveal", {"card_id": "q1"})
        view = act(store, view, "rate", {"card_id": "q1", "rating": "got_it"})
        card = view["cards"][0]
        assert card["streak"] == expected_streak and card["review_count"] == expected_streak
        assert stamp(card["due_at"]) == 1000 + days * 86400
        assert not card["due"] and not card["needs_review"] and card["answer"] is None
    view = act(store, view, "choices", {"card_id": "q1"})
    view = act(store, view, "reveal", {"card_id": "q1"})
    view = act(store, view, "rate", {"card_id": "q1", "rating": "again"})
    card = view["cards"][0]
    assert card["streak"] == 0 and card["review_count"] == 5 and card["last_rating"] == "again"
    assert stamp(card["due_at"]) == 1600 and card["needs_review"] and not card["due"]
    assert card["answer"] is None and card["choices"] is None
    assert view["counts"]["due"] == 2
    with sqlite3.connect(store.path) as connection:
        events = [json.loads(row[0]) for row in connection.execute("SELECT event_json FROM card_actions ORDER BY rowid")]
    last = events[-1]
    assert last["rating"] == "again" and last["revealed_before"] and last["choices_viewed"]
    monkeypatch.setattr(module.time, "time", lambda: 1600.0)
    assert store.get(OWNER, view["id"])["counts"]["due"] == 3


def test_replay_does_not_rate_twice_and_stale_action_cannot_overwrite(store):
    view = act(store, create(store), "reveal", {"card_id": "q1"})
    args = (OWNER, view["id"], "rate", {"card_id": "q1", "rating": "again"}, view["revision"], "stable-rating-00001")
    rated = store.act(*args)
    assert store.act(*args) == rated and rated["cards"][0]["review_count"] == 1
    assert fail("flashcards_conflict", store.act, OWNER, view["id"], "reveal", {"card_id": "q2"}, view["revision"], "stale-action-00001").status_code == 409
    fail("flashcards_conflict", store.act, OWNER, view["id"], "rate", {"card_id": "q1", "rating": "got_it"}, view["revision"], "stable-rating-00001")


@pytest.mark.parametrize("action,payload,revision", [
    ("rate", {"card_id": "q1", "rating": "easy"}, 0), ("reveal", {"card_id": "q1", "text": "injected"}, 0),
    ("reveal", {"card_id": "q5"}, 0), ("reveal", {"card_id": True}, 0), ("unknown", {}, 0),
    ("hide", [], 0), ("reveal", {"card_id": "q1"}, True), ("reveal", {"card_id": "q1"}, -1),
])
def test_invalid_actions_preserve_cards(store, action, payload, revision):
    view = create(store)
    fail("flashcards_invalid", store.act, OWNER, view["id"], action, payload, revision, "invalid-action-001")
    assert store.get(OWNER, view["id"]) == view


def test_quotas_allow_replay_and_tombstones_prevent_recreating_deleted_request(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_DECKS", 1)
    view = create(store)
    assert create(store) == view
    fail("flashcards_limit", store.create, OWNER, "another-deck-request", completed(), ["q1"])
    store.delete(OWNER, view["id"])
    assert store.list(OWNER) == []
    fail("flashcards_not_found", store.lookup_request, OWNER, REQUEST, selection())
    monkeypatch.setattr(module, "MAX_CREATE_REQUESTS", 1)
    fail("flashcards_limit", store.create, OWNER, "another-deck-request", completed(), ["q1"])


def test_action_quota_keeps_exact_retry_available(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_ACTIONS", 1)
    view = create(store)
    args = (OWNER, view["id"], "reveal", {"card_id": "q1"}, 0, "stable-reveal-00001")
    revealed = store.act(*args)
    assert store.act(*args) == revealed
    fail("flashcards_limit", store.act, OWNER, view["id"], "rate", {"card_id": "q1", "rating": "again"}, 1, "quota-rating-00001")


def test_snapshots_survive_deleted_practice_and_changed_source_note(tmp_path, store):
    original = PracticeStore(tmp_path / "practice.sqlite3")
    snapshot = prepared(image=True)
    claim = original.reserve(OWNER, "practice-request-00001", snapshot)
    practice = original.finish(OWNER, claim["practice"]["id"], "practice-request-00001", bundle(snapshot))
    sequence = 0
    def step(action, payload):
        nonlocal practice, sequence
        sequence += 1
        practice = original.act(OWNER, practice["id"], action, payload, practice["revision"], f"practice-action-{sequence:03}")
    step("start", {})
    for index in range(3):
        step("solution", {"item_id": f"q{index+1}"})
        step("next", {})
    view = create(store, practice=practice, ids=["q1"])
    original.delete(OWNER, practice["id"])
    practice["questions"][0]["answer"]["evidence"][0]["text"] = "Changed note"
    shown = act(store, view, "reveal", {"card_id": "q1"})
    source = shown["cards"][0]["answer"]["evidence"][0]
    assert source["origin"] == "user_note" and source["annotation_revision"] == 2
    assert source["text"] == "A semaphore controls access."


def test_concurrent_create_claims_one_deck_and_one_action_wins_revision(store):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(store), range(2)))
    assert len({view["id"] for view in results}) == 1
    view = results[0]
    def mutate(index):
        try:
            return store.act(OWNER, view["id"], "reveal", {"card_id": f"q{index+1}"}, 0, f"concurrent-reveal-{index}")
        except LearningError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(mutate, range(2)))
    assert sum(isinstance(value, dict) for value in results) == 1
    assert "flashcards_conflict" in results


@pytest.mark.parametrize("mutation", [
    lambda p: p["questions"][0].update(question="\ud800"),
    lambda p: p["questions"][0].update(hint_count=True),
    lambda p: p["questions"][0]["answer"].update(correct_option="e"),
    lambda p: p["questions"][0]["answer"]["evidence"][0]["locator"].update(index=1.0),
    lambda p: p["questions"][0]["answer"]["evidence"][0].update(unit_id="unit-" + "f" * 64),
    lambda p: p["questions"][0]["answer"]["evidence"][0].update(annotation_revision=1),
    lambda p: p["questions"][0].pop("first_try_correct"),
])
def test_invalid_source_snapshots_are_not_published(store, mutation):
    practice = completed()
    mutation(practice)
    fail("flashcards_invalid", store.create, OWNER, REQUEST, practice, ["q1"])
    assert not store.path.exists()


@pytest.mark.parametrize("damage", ["snapshot", "state", "duplicate", "due_type", "rating_state", "revision", "oversize"])
def test_corrupt_storage_fails_closed(store, damage):
    view = create(store)
    with sqlite3.connect(store.path) as connection:
        if damage == "snapshot": connection.execute("UPDATE decks SET snapshot_json='{}'")
        elif damage == "state": connection.execute("UPDATE decks SET state_json='null'")
        elif damage == "duplicate": connection.execute("UPDATE decks SET state_json=?", ('{"cards":{},"cards":{}}',))
        elif damage == "revision": connection.execute("UPDATE decks SET revision=-1")
        elif damage == "oversize": connection.execute("UPDATE decks SET snapshot_json=?", (" " * (128*1024+1),))
        else:
            row = connection.execute("SELECT state_json FROM decks").fetchone()
            state = json.loads(row[0])
            if damage == "due_type": state["cards"]["q1"]["due_at"] = True
            else: state["cards"]["q1"]["review_count"] = 1
            connection.execute("UPDATE decks SET state_json=?", (json.dumps(state),))
    assert fail("flashcards_storage_error", store.get, OWNER, view["id"]).status_code == 500


def test_unrelated_database_and_redirected_sidecar_are_rejected(store, monkeypatch):
    store.path.parent.mkdir(parents=True)
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    fail("flashcards_storage_error", create, store)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: str(path).endswith("-wal") or original(path))
    fail("flashcards_storage_error", store.list, OWNER)


def test_storage_limit_is_checked_before_publication(store, monkeypatch):
    monkeypatch.setattr(module, "MAX_JSON_BYTES", 50)
    fail("flashcards_limit", create, store)
    assert not store.path.exists()
