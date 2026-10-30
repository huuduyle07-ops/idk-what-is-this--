"""Mixed-format assessments through the real owner/auth/CSRF boundaries."""
from __future__ import annotations

import copy
from fractions import Fraction
import uuid

import pytest

from core.learning.test_maker import build_test, catalog
from tests.integration.test_learning_materials_web import BASE, materials, page, assert_error

API = "/learn/api/test-maker"


@pytest.fixture
def maker(materials, tmp_path, monkeypatch):
    monkeypatch.setitem(materials.app.config, "LEARNING_TEST_MAKER_STORE_PATH", tmp_path / "test_maker.sqlite3")
    class NoModel:
        def public_config(self):
            pytest.fail("Test Maker must not consult a model")
    monkeypatch.setitem(materials.app.config, "LEARNING_CHAT_RESPONDER", NoModel())
    client = materials.app.test_client()
    csrf = page(client, "/learn/test-maker")
    body = {"request_id": uuid.uuid4().hex, "topic_ids": [topic["id"] for topic in catalog()], "seed": 42}
    return client, csrf, body


def post(client, csrf, path, body):
    return client.post(path, base_url=BASE, json=body, headers={"Origin": BASE, "X-CSRF-Token": csrf})


def create(state):
    client, csrf, body = state
    response = post(client, csrf, API, body)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["test"]


def act(client, csrf, view, name, answers, request_id=None):
    return post(client, csrf, f"{API}/{view['id']}/actions", {
        "action": name, "payload": {"answers": answers}, "expected_revision": view["revision"],
        "request_id": request_id or uuid.uuid4().hex,
    })


def solution_answers(bundle):
    answers = {}
    for question in bundle["questions"]:
        key = question["answer_key"]
        if question["kind"] == "numeric":
            value = key["value"]
            if question["topic_id"] == "ml_tpr":
                value = str(float(Fraction(value) * 100)) + "%"
            elif question["topic_id"] == "os_paging":
                value = hex(int(Fraction(value)))
            answers[question["id"]] = value
        elif question["kind"] == "matrix":
            answers[question["id"]] = copy.deepcopy(key["cells"])
        elif question["kind"] == "diagram":
            answers[question["id"]] = {slot: labels[0] for slot, labels in key["slots"].items()}
        else:
            answers[question["id"]] = "My explanation and reasoning, which still needs a rubric-based review."
    return answers


def test_all_requested_topics_are_available_and_create_hides_keys_until_submission(maker):
    client, csrf, body = maker
    response = client.get(API + "/catalog", base_url=BASE)
    assert response.status_code == 200 and len(response.get_json()["topics"]) == 11
    view = create(maker)
    assert {q["kind"] for q in view["questions"]} == {"numeric", "matrix", "diagram", "essay"}
    assert view["status"] == "active" and view["results"] is None
    assert all(not ({"answer_key", "explanation", "rubric"} & q.keys()) for q in view["questions"])
    assert post(client, csrf, API, {**body, "topic_ids": list(reversed(body["topic_ids"]))}).get_json()["test"] == view
    response = client.get(f"{API}/{view['id']}", base_url=BASE)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.get_json()["test"] == view
    private = build_test(body["topic_ids"], body["seed"])
    answers = solution_answers(private)
    saved = act(client, csrf, view, "save", answers)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    view = saved.get_json()["test"]
    assert view["answers"] == answers and view["results"] is None
    assert all("answer_key" not in q for q in view["questions"])
    rid = uuid.uuid4().hex
    result = act(client, csrf, view, "submit", answers, rid)
    assert result.status_code == 200, result.get_data(as_text=True)
    submitted = result.get_json()["test"]
    assert submitted["status"] == "submitted"
    score = submitted["results"]
    assert score["auto"]["earned"] == score["auto"]["possible"]
    assert score["auto"]["possible"] == sum(q["points"] for q in private["questions"] if q["kind"] != "essay")
    assert score["essay"] == {"answered": 4, "pending": 4, "total": 4}
    for item, question in zip(score["items"], private["questions"]):
        if question["kind"] == "essay":
            assert item["status"] == "pending_review" and item["earned"] is None and item["correct"] is None
            assert item["rubric"] and item["expected"]
        else:
            assert item["correct"] is True
    assert act(client, csrf, view, "submit", answers, rid).get_json() == result.get_json()
    assert_error(act(client, csrf, submitted, "save", answers), 409)


def test_draft_save_partial_merge_conflict_and_retry_preserve_student_work(maker):
    client, csrf, _ = maker
    initial = create(maker)
    question_id = initial["questions"][0]["id"]
    rid = uuid.uuid4().hex
    first = act(client, csrf, initial, "save", {question_id: "I am still calculating"}, rid)
    assert first.status_code == 200
    saved = first.get_json()["test"]
    assert saved["answers"][question_id] == "I am still calculating"
    assert act(client, csrf, initial, "save", {question_id: "I am still calculating"}, rid).get_json() == first.get_json()
    assert_error(act(client, csrf, initial, "save", {question_id: "A stale answer"}), 409)
    second_id = initial["questions"][1]["id"]
    merged = act(client, csrf, saved, "save", {second_id: "1/2"}).get_json()["test"]
    assert merged["answers"] == {question_id: "I am still calculating", second_id: "1/2"}
    assert client.get(f"{API}/{initial['id']}", base_url=BASE).get_json()["test"] == merged


def test_invalid_numeric_expressions_are_student_answers_and_never_executed(maker):
    client, csrf, _ = maker
    view = create(maker)
    question = next(q for q in view["questions"] if q["topic_id"] == "ml_mse")
    expression = "__import__('os').system('touch do-not-run')"
    result = act(client, csrf, view, "submit", {question["id"]: expression})
    assert result.status_code == 200
    test = result.get_json()["test"]
    item = next(item for item in test["results"]["items"] if item["question_id"] == question["id"])
    assert item["correct"] is False and item["earned"] == 0
    assert test["answers"][question["id"]] == expression


def test_owner_auth_origin_and_csrf_protect_mixed_test_content(materials, maker, monkeypatch):
    client, csrf, body = maker
    view = create(maker)
    path = f"{API}/{view['id']}"
    other = materials.app.test_client()
    other_csrf = page(other, "/learn/test-maker")
    assert_error(other.get(path, base_url=BASE), 404)
    assert other.get(API, base_url=BASE).get_json()["tests"] == []
    assert_error(act(other, other_csrf, view, "submit", {}), 404)
    assert_error(other.delete(path, base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": other_csrf}), 404)
    assert_error(materials.app.test_client().get(path, base_url=BASE), 401)
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.post(API, base_url=BASE, json=body, headers=headers), 403)
        assert_error(client.post(path + "/actions", base_url=BASE, json={"action": "submit", "payload": {"answers": {}}, "expected_revision": 0, "request_id": uuid.uuid4().hex}, headers=headers), 403)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "test-maker-web-token")
    assert_error(client.get(path, base_url=BASE), 401)


@pytest.mark.parametrize("patch", [
    {"topic_ids": []}, {"topic_ids": ["not-a-topic"]}, {"topic_ids": ["ml_mse", "ml_mse"]},
    {"seed": True}, {"seed": -1}, {"seed": 2**31}, {"request_id": "short"},
    {"answer_key": {"expected": "client-injected"}},
])
def test_invalid_creation_cannot_publish_a_test(maker, patch):
    client, csrf, body = maker
    assert_error(post(client, csrf, API, {**body, **patch}), 400)
    assert client.get(API, base_url=BASE).get_json()["tests"] == []


def test_bad_question_ids_and_oversize_answers_preserve_revision(maker):
    client, csrf, _ = maker
    view = create(maker)
    assert_error(act(client, csrf, view, "save", {"q99": "injected"}), 400)
    essay = next(q for q in view["questions"] if q["kind"] == "essay")
    assert_error(act(client, csrf, view, "save", {essay["id"]: "x" * 4001}), 400)
    assert_error(act(client, csrf, view, "save", {essay["id"]: "x" * 150000}), 413)
    assert client.get(f"{API}/{view['id']}", base_url=BASE).get_json()["test"] == view


def test_delete_and_seed_replay_do_not_recreate_old_test(maker):
    client, csrf, body = maker
    view = create(maker)
    assert client.delete(f"{API}/{view['id']}", base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": csrf}).status_code == 200
    assert_error(post(client, csrf, API, body), 404)
    assert client.get(API, base_url=BASE).get_json()["tests"] == []
