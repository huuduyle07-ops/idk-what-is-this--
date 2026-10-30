"""Source selection, reviewed model drafts and durable practice via HTTP gates."""
from __future__ import annotations

import copy
import json
import uuid

import pytest

from tests.integration.test_learning_materials_web import API as MATERIALS, BASE, assert_error, materials, page, upload
from tests.integration.test_learning_images_web import picture

API = "/learn/api/practice"


class PracticeResponder:
    def __init__(self):
        self.calls = []
        self.effect = None
        self.available = True

    def public_config(self):
        return {"available": self.available, "provider": "ollama", "model": "practice-fixture", "reason": "" if self.available else "Configure a model"}

    def generate_practice(self, excerpts, *, count=3):
        self.calls.append(copy.deepcopy(excerpts))
        if self.effect:
            self.effect()
        return json.dumps({"title": "Practice the selected passage", "questions": [
            {"objective": f"Recall the selected concept, question {i+1}",
             "question": f"Which statement follows the selected passage? ({i+1})",
             "options": [{"id": "a", "text": "Inheritance lesson"}, {"id": "b", "text": "An unrelated statement"},
                         {"id": "c", "text": "No concept is discussed"}, {"id": "d", "text": "None of these statements"}],
             "correct_option": "a", "explanation": "The selected passage explicitly discusses the lesson.",
             "hints": ["Read the named concept.", "Compare the passage to each option."],
             "evidence": [{"excerpt_id": excerpts[0]["excerpt_id"], "quote": excerpts[0]["text"][:600]}]}
            for i in range(count)]})


@pytest.fixture
def practice(materials, tmp_path, monkeypatch):
    monkeypatch.setitem(materials.app.config, "LEARNING_PRACTICE_STORE_PATH", tmp_path / "practice.sqlite3")
    responder = PracticeResponder()
    monkeypatch.setitem(materials.app.config, "LEARNING_CHAT_RESPONDER", responder)
    client = materials.app.test_client()
    csrf = page(client, "/learn/practice")
    collection = upload(client, csrf).get_json()["collection"]
    body = {"request_id": uuid.uuid4().hex, "collection_id": collection["id"],
            "unit_ids": [collection["units"][0]["unit_id"]], "count": 3}
    return client, csrf, collection, responder, body


def post(client, csrf, path, body):
    return client.post(path, base_url=BASE, json=body, headers={"Origin": BASE, "X-CSRF-Token": csrf})


def action(client, csrf, view, name, payload=None, request_id=None):
    return post(client, csrf, f"{API}/{view['id']}/actions", {
        "action": name, "payload": {} if payload is None else payload,
        "expected_revision": view["revision"], "request_id": request_id or uuid.uuid4().hex,
    })


def generated(state):
    client, csrf, _, _, body = state
    response = post(client, csrf, API, body)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["practice"]


def test_generate_review_practice_resume_and_finish_with_pinned_sources(practice):
    client, csrf, collection, responder, body = practice
    assert client.get(API, base_url=BASE).get_json()["practices"] == []
    view = generated(practice)
    assert view["status"] == "draft" and len(view["questions"]) == 3
    assert len(responder.calls) == 1
    assert set(responder.calls[0][0]) == {"excerpt_id", "text", "origin"}
    assert all(q["answer"] is None and q["hints"] == [] for q in view["questions"])
    assert "correct_option" not in json.dumps(view)
    assert post(client, csrf, API, body).get_json()["practice"] == view
    reviewed = action(client, csrf, view, "review_answer", {"item_id": "q1"}).get_json()["practice"]
    answer = reviewed["questions"][0]["answer"]
    assert answer["correct_option"] == "a"
    assert answer["evidence"][0]["unit_id"] == collection["units"][0]["unit_id"]
    assert answer["evidence"][0]["text"] == collection["units"][0]["text"]
    view = action(client, csrf, reviewed, "start").get_json()["practice"]
    assert view["status"] == "active" and view["summary"]["answers_reviewed_before_start"] == 1
    view = action(client, csrf, view, "answer", {"item_id": "q1", "option_id": "a", "reflection": "My explanation"}).get_json()["practice"]
    assert view["questions"][0]["feedback"]["correct"] is True
    view = action(client, csrf, view, "next").get_json()["practice"]
    view = action(client, csrf, view, "answer", {"item_id": "q2", "option_id": "b", "reflection": "Unsure"}).get_json()["practice"]
    assert view["questions"][1]["answer"] is None
    assert view["questions"][1]["feedback"]["correct"] is False
    assert action(client, csrf, view, "next").status_code == 409
    view = action(client, csrf, view, "hint", {"item_id": "q2"}).get_json()["practice"]
    assert len(view["questions"][1]["hints"]) == 1
    view = action(client, csrf, view, "answer", {"item_id": "q2", "option_id": "a", "reflection": "After hint"}).get_json()["practice"]
    assert view["questions"][1]["first_try_correct"] is False
    assert client.get(f"{API}/{view['id']}", base_url=BASE).get_json()["practice"] == view
    view = action(client, csrf, view, "next").get_json()["practice"]
    view = action(client, csrf, view, "solution", {"item_id": "q3"}).get_json()["practice"]
    view = action(client, csrf, view, "next").get_json()["practice"]
    assert view["status"] == "completed" and view["summary"]["answered_count"] == 2
    assert len(responder.calls) == 1


def test_ownership_origin_csrf_and_auth_protect_generation_and_attempts(materials, practice, monkeypatch):
    client, csrf, _, responder, body = practice
    view = generated(practice)
    path = f"{API}/{view['id']}"
    other = materials.app.test_client()
    other_csrf = page(other, "/learn/practice")
    assert_error(other.get(path, base_url=BASE), 404)
    assert other.get(API, base_url=BASE).get_json()["practices"] == []
    assert_error(post(other, other_csrf, API, body), 404)
    assert_error(action(other, other_csrf, view, "start"), 404)
    assert_error(other.delete(path, base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": other_csrf}), 404)
    assert_error(materials.app.test_client().get(path, base_url=BASE), 401)
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.post(API, base_url=BASE, json=body, headers=headers), 403)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "practice-web-token")
    assert_error(client.get(path, base_url=BASE), 401)
    assert len(responder.calls) == 1


def test_failed_generation_is_saved_and_same_request_never_calls_model_again(practice):
    client, csrf, _, responder, body = practice
    responder.effect = lambda: (_ for _ in ()).throw(RuntimeError("secret API key /private/source/path"))
    view = generated(practice)
    assert view["status"] == "failed" and view["error"]["message"]
    assert "secret" not in json.dumps(view) and "/private" not in json.dumps(view)
    assert post(client, csrf, API, body).get_json()["practice"] == view
    responder.available = False
    assert post(client, csrf, API, body).status_code == 200
    assert len(responder.calls) == 1


def test_review_and_action_retry_does_not_repeat_or_overwrite(practice):
    client, csrf, _, responder, _ = practice
    before = generated(practice)
    request_id = uuid.uuid4().hex
    first = action(client, csrf, before, "review_answer", {"item_id": "q1"}, request_id)
    assert first.status_code == 200
    assert action(client, csrf, before, "review_answer", {"item_id": "q1"}, request_id).get_json() == first.get_json()
    assert action(client, csrf, before, "start").status_code == 409
    assert len(responder.calls) == 1


@pytest.mark.parametrize("patch", [
    {"count": True}, {"count": 2}, {"count": 6}, {"unit_ids": []},
    {"unit_ids": ["../../other"]}, {"request_id": "short"}, {"excerpts": [{"text": "injection"}]},
])
def test_invalid_selection_does_not_call_model(practice, patch):
    client, csrf, _, responder, body = practice
    assert_error(post(client, csrf, API, {**body, **patch}), 400)
    assert responder.calls == []


def test_generation_in_progress_replay_and_busy_requests_never_duplicate(practice):
    client, csrf, _, responder, body = practice
    from web.routes.learning_practice_routes import _GENERATION_SLOT
    observed = []
    def during():
        replay = post(client, csrf, API, body)
        observed.append(replay)
        assert replay.status_code == 202
        assert_error(post(client, csrf, API, {**body, "request_id": uuid.uuid4().hex}), 429, "practice_busy")
    responder.effect = during
    view = generated(practice)
    assert observed[0].get_json()["practice"]["id"] == view["id"]
    assert len(responder.calls) == 1
    assert _GENERATION_SLOT.acquire(blocking=False)
    _GENERATION_SLOT.release()


def test_replay_uses_original_image_note_after_source_edit(materials, practice):
    client, csrf, _, responder, _ = practice
    collection = upload(client, csrf, paths=["diagram.png"], contents=[picture()]).get_json()["collection"]
    digest = collection["sources"][0]["source_id"][7:]
    note_url = f"{MATERIALS}/{collection['id']}/sources/{digest}/description"
    def note(text, revision):
        return client.put(note_url, base_url=BASE, json={"text": text, "expected_revision": revision}, headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert note("Inheritance lesson", 0).status_code == 200
    body = {"request_id": uuid.uuid4().hex, "collection_id": collection["id"], "unit_ids": [collection["units"][0]["unit_id"]], "count": 3}
    view = post(client, csrf, API, body).get_json()["practice"]
    assert view["status"] == "draft"
    assert note("", 1).status_code == 200
    assert post(client, csrf, API, body).get_json()["practice"] == view
    reviewed = action(client, csrf, view, "review_answer", {"item_id": "q1"}).get_json()["practice"]
    evidence = reviewed["questions"][0]["answer"]["evidence"][0]
    assert evidence["origin"] == "user_note" and evidence["annotation_revision"] == 1
    assert evidence["text"] == "Inheritance lesson"
    assert len(responder.calls) == 1


def test_delete_tombstone_prevents_reusing_generation_request(practice):
    client, csrf, _, responder, body = practice
    view = generated(practice)
    assert client.delete(f"{API}/{view['id']}", base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": csrf}).status_code == 200
    assert_error(post(client, csrf, API, body), 404)
    assert client.get(API, base_url=BASE).get_json()["practices"] == []
    assert len(responder.calls) == 1
