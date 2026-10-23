from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from core.learning import LearningError, LearningStore
from core.learning.lesson import ITEMS


@pytest.fixture
def store(tmp_path):
    return LearningStore(tmp_path / "learning.sqlite3")


def act(store, session, action, payload=None, request_id=None):
    return store.act("learner", session["id"], action, payload or {}, session["revision"],
                     request_id or f"request-{session['revision']}")


def test_new_session_does_not_expose_rubric_or_future_hints(store):
    session = store.create("learner")
    assert session["revision"] == 0
    assert session["item"]["hints"] == []
    assert session["item"]["feedback"] is None
    assert session["item"]["solution"] is None
    exported = store.export("learner", session["id"])
    raw = json.dumps(exported, ensure_ascii=False)
    assert "correct_option" not in raw
    assert "explanation" not in raw
    for item in ITEMS:
        assert item["explanation"] not in raw
        for hint in item["hints"]:
            assert hint not in raw
    assert len(session["items"]) == 3
    assert session["summary"]["answered_count"] == 0


def test_unaided_success_and_ungraded_reflection_are_recorded(store):
    session = store.create("learner")
    session = act(store, session, "answer", {"option_id": "b", "reflection": "Vì pet trỏ đến Cat."})
    assert session["items"][0]["independent_result"] == "success"
    assert session["summary"]["independent_successes"] == 1
    assert session["item"]["feedback"]["assistance"] == "none"
    assert session["item"]["reflection"] == "Vì pet trỏ đến Cat."
    event = store.export("learner", session["id"])["events"][-1]
    assert event["observation"]["reflection_assessed"] is False
    assert event["lesson_version"] and event["rubric_version"] and event["content_version"]
    assert event["timestamp"].endswith("Z")


def test_wrong_first_then_correct_is_never_upgraded_to_independent_success(store):
    session = store.create("learner")
    session = act(store, session, "answer", {"option_id": "a"})
    assert session["items"][0]["independent_result"] == "failure"
    session = act(store, session, "answer", {"option_id": "b"})
    assert session["items"][0]["independent_result"] == "failure"
    assert session["item"]["feedback"]["assistance"] == "feedback"
    assert session["summary"]["independent_successes"] == 0
    assert session["summary"]["independent_failures"] == 1
    assert session["summary"]["assisted_successes"] == 1


@pytest.mark.parametrize("help_action", ["hint", "solution"])
def test_help_before_answer_means_independent_outcome_is_unobserved(store, help_action):
    session = act(store, store.create("learner"), help_action)
    session = act(store, session, "answer", {"option_id": "a"})
    assert session["items"][0]["independent_result"] == "not_observed"
    assert session["summary"]["independent_failures"] == 0
    session = act(store, session, "answer", {"option_id": "b"})
    assert session["summary"]["assisted_successes"] == 1
    assert session["summary"]["independent_successes"] == 0


def test_solution_is_not_an_answer_and_does_not_taint_next_transfer(store):
    session = act(store, store.create("learner"), "solution")
    assert not session["item"]["answered"]
    assert session["summary"]["answered_count"] == 0
    session = act(store, session, "next")
    assert session["current_index"] == 1
    assert session["item"]["hints"] == []
    assert session["item"]["solution"] is None
    session = act(store, session, "answer", {"option_id": "c"})
    assert session["items"][1]["independent_result"] == "success"
    assert session["summary"]["answered_count"] == 1


def test_complete_session_keeps_final_item_for_review(store):
    session = store.create("learner")
    for option in ("b", "c", "a"):
        session = act(store, session, "answer", {"option_id": option})
        session = act(store, session, "next")
    assert session["status"] == "completed"
    assert session["current_index"] == 2
    assert session["item"]["id"] == "formatter-transfer"
    assert session["summary"]["independent_successes"] == 3
    with pytest.raises(LearningError) as error:
        act(store, session, "answer", {"option_id": "a"})
    assert error.value.code == "session_completed"


def test_viewing_all_solutions_reports_no_observed_answers(store):
    session = store.create("learner")
    for _ in range(3):
        session = act(store, session, "solution")
        session = act(store, session, "next")
    assert session["status"] == "completed"
    assert session["summary"]["answered_count"] == 0
    assert session["summary"]["independent_successes"] == 0
    assert session["summary"]["assisted_successes"] == 0


def test_retry_returns_original_response_without_duplicate_events(store):
    session = store.create("learner")
    first = act(store, session, "answer", {"option_id": "b"}, request_id="stable")
    advanced = act(store, first, "next")
    retry = act(store, session, "answer", {"option_id": "b"}, request_id="stable")
    assert retry == first
    assert store.get("learner", session["id"]) == advanced
    assert len(store.export("learner", session["id"])["events"]) == 3


def test_request_collision_and_stale_revision_do_not_change_state(store):
    session = store.create("learner")
    first = act(store, session, "answer", {"option_id": "b"}, request_id="stable")
    with pytest.raises(LearningError) as collision:
        act(store, session, "answer", {"option_id": "a"}, request_id="stable")
    assert collision.value.code == "request_collision"
    assert collision.value.status_code == 409
    with pytest.raises(LearningError) as revision:
        act(store, session, "hint", request_id="other")
    assert revision.value.code == "revision_conflict"
    assert revision.value.status_code == 409
    assert store.get("learner", session["id"]) == first


def test_concurrent_actions_with_same_revision_only_apply_once(store):
    session = store.create("learner")

    def answer(request_id):
        try:
            return act(store, session, "answer", {"option_id": "b"}, request_id=request_id)
        except LearningError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(answer, ["one", "two"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert [result.code for result in results if isinstance(result, LearningError)] == ["revision_conflict"]
    assert len(store.export("learner", session["id"])["events"]) == 2


def test_owner_isolation_covers_reads_writes_export_delete_and_lists(store):
    session = store.create("learner")
    calls = [
        lambda: store.get("other", session["id"]),
        lambda: store.act("other", session["id"], "hint", {}, 0, "foreign"),
        lambda: store.export("other", session["id"]),
        lambda: store.delete("other", session["id"]),
    ]
    for call in calls:
        with pytest.raises(LearningError) as error:
            call()
        assert error.value.status_code == 404
        assert error.value.code == "not_found"
    assert store.latest("other") is None
    assert store.list_recent("other") == []
    assert store.get("learner", session["id"]) == session


def test_persists_across_instances_and_deletes_event_history(tmp_path):
    path = tmp_path / "learning.sqlite3"
    store = LearningStore(path)
    session = act(store, store.create("learner"), "answer", {"option_id": "b", "reflection": "private reflection"})
    reopened = LearningStore(path)
    assert reopened.get("learner", session["id"]) == session
    assert reopened.latest("learner") == session
    reopened.delete("learner", session["id"])
    assert reopened.latest("learner") is None
    with pytest.raises(LearningError) as error:
        reopened.export("learner", session["id"])
    assert error.value.status_code == 404
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT count(*) FROM learning_events").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM learning_sessions").fetchone()[0] == 0
    assert b"private reflection" not in path.read_bytes()


@pytest.mark.parametrize("action,payload", [
    ("next", {}), ("answer", {"option_id": "wrong"}),
    ("answer", {"option_id": "b", "reflection": "x" * 4001}),
    ("answer", {"option_id": "b", "reflection": None}),
    ("answer", {"option_id": "b", "reflection": "\ud800"}),
    ("answer", {}), ("hint", {"unexpected": True}), ("unknown", {}),
])
def test_invalid_actions_do_not_write_partial_state(store, action, payload):
    session = store.create("learner")
    with pytest.raises(LearningError) as error:
        act(store, session, action, payload)
    assert error.value.status_code == 400
    assert store.get("learner", session["id"]) == session
    assert len(store.export("learner", session["id"])["events"]) == 1


def test_hints_reveal_one_at_a_time_and_cannot_exceed_authored_count(store):
    session = act(store, store.create("learner"), "hint")
    assert len(session["item"]["hints"]) == 1
    assert session["item"]["solution"] is None
    session = act(store, session, "hint")
    assert len(session["item"]["hints"]) == session["item"]["total_hints"] == 2
    with pytest.raises(LearningError) as error:
        act(store, session, "hint")
    assert error.value.code == "no_more_hints"


@pytest.mark.parametrize("revision", [True, -1, "0", 1.5, None])
def test_revision_requires_nonnegative_integer(store, revision):
    session = store.create("learner")
    with pytest.raises(LearningError):
        store.act("learner", session["id"], "hint", {}, revision, "key")


def test_memory_store_retains_state_across_connections():
    store = LearningStore(":memory:")
    session = store.create("learner")
    assert store.get("learner", session["id"]) == session


def test_recent_sessions_are_owner_scoped_and_ordered_by_activity(store):
    first = store.create("learner")
    second = store.create("learner")
    store.create("other")
    assert store.latest("learner")["id"] == second["id"]
    first = act(store, first, "hint")
    assert [session["id"] for session in store.list_recent("learner")] == [first["id"], second["id"]]
    with pytest.raises(LearningError):
        store.list_recent("learner", 0)


def test_evidence_lines_reference_real_relevant_source_lines():
    for item in ITEMS:
        lines = item["code"].splitlines()
        assert len(set(option["id"] for option in item["options"])) == len(item["options"])
        assert item["correct_option"] in {option["id"] for option in item["options"]}
        assert all(1 <= number <= len(lines) for number in item["evidence_lines"])
        referenced = "\n".join(lines[number - 1] for number in item["evidence_lines"])
        assert "return" in referenced
        assert "new " in referenced


def test_existing_session_pins_content_rubric_and_event_versions(store, monkeypatch):
    import core.learning.store as module

    session = store.create("learner")
    replacement = dict(ITEMS[0], correct_option="a", code="changed after the session began")
    monkeypatch.setattr(module, "ITEMS", (replacement, *ITEMS[1:]))
    monkeypatch.setattr(module, "CONTENT_VERSION", "new-version")
    assert store.get("learner", session["id"])["item"]["code"] == session["item"]["code"]
    session = act(store, session, "answer", {"option_id": "b"})
    assert session["item"]["feedback"]["correct"]
    export = store.export("learner", session["id"])
    assert export["events"][0]["content_version"] == export["events"][1]["content_version"]
    assert export["events"][1]["content_version"] != "new-version"
    assert store.create("learner")["item"]["code"] == replacement["code"]


def test_session_and_action_limits_preserve_existing_data_and_retries(store, monkeypatch):
    import core.learning.store as module

    monkeypatch.setattr(module, "MAX_SESSIONS_PER_OWNER", 1)
    monkeypatch.setattr(module, "MAX_ACTIONS_PER_SESSION", 1)
    session = store.create("learner")
    with pytest.raises(LearningError) as error:
        store.create("learner")
    assert error.value.code == "session_limit"
    store.create("other")
    first = act(store, session, "hint")
    assert act(store, session, "hint") == first
    with pytest.raises(LearningError) as error:
        act(store, first, "hint")
    assert error.value.code == "action_limit"
    assert len(store.export("learner", session["id"])["events"]) == 2
    store.delete("learner", session["id"])
    assert store.create("learner")["revision"] == 0
