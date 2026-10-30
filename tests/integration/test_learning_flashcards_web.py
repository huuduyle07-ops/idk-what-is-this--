"""Completed Practice -> source-backed review cards through real HTTP gates."""
from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
import uuid

import pytest

from tests.integration.test_learning_materials_web import BASE, materials, page, assert_error
from tests.integration.test_learning_practice_web import (
    API as PRACTICE_API, practice, generated, action as practice_action,
)

API = "/learn/api/flashcards"


def post(client, csrf, url, body):
    return client.post(url, base_url=BASE, json=body, headers={"Origin": BASE, "X-CSRF-Token": csrf})


def act(client, csrf, deck, name, payload, request_id=None):
    return post(client, csrf, f"{API}/{deck['id']}/actions", {
        "action": name, "payload": payload, "expected_revision": deck["revision"],
        "request_id": request_id or uuid.uuid4().hex,
    })


def finish_practice(state):
    client, csrf, _, responder, _ = state
    view = generated(state)
    view = practice_action(client, csrf, view, "start").get_json()["practice"]
    view = practice_action(client, csrf, view, "answer", {"item_id": "q1", "option_id": "b", "reflection": "My first prediction"}).get_json()["practice"]
    view = practice_action(client, csrf, view, "hint", {"item_id": "q1"}).get_json()["practice"]
    view = practice_action(client, csrf, view, "answer", {"item_id": "q1", "option_id": "a", "reflection": "After a hint"}).get_json()["practice"]
    view = practice_action(client, csrf, view, "next").get_json()["practice"]
    view = practice_action(client, csrf, view, "solution", {"item_id": "q2"}).get_json()["practice"]
    view = practice_action(client, csrf, view, "next").get_json()["practice"]
    view = practice_action(client, csrf, view, "answer", {"item_id": "q3", "option_id": "a", "reflection": ""}).get_json()["practice"]
    view = practice_action(client, csrf, view, "next").get_json()["practice"]
    assert view["status"] == "completed"
    assert len(responder.calls) == 1
    return view


@pytest.fixture
def flashcards(practice, tmp_path, monkeypatch, materials):
    monkeypatch.setitem(materials.app.config, "LEARNING_FLASHCARD_STORE_PATH", tmp_path / "flashcards.sqlite3")
    client, csrf, _, responder, _ = practice
    source = finish_practice(practice)
    responder.available = False  # Card creation/review needs no available model.
    body = {"request_id": uuid.uuid4().hex, "practice_id": source["id"], "question_ids": ["q1", "q2", "q3"]}
    return client, csrf, source, responder, body


def create(state):
    client, csrf, _, _, body = state
    response = post(client, csrf, API, body)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["deck"]


def test_completed_practice_becomes_hidden_cards_without_model_and_sources_stay_pinned(flashcards):
    client, csrf, source, responder, body = flashcards
    deck = create(flashcards)
    assert len(deck["cards"]) == 3 and deck["counts"] == {"total": 3, "due": 3, "needs_review": 2}
    assert all(card["answer"] is None and card["choices"] is None for card in deck["cards"])
    assert "correct_option" not in json.dumps(deck) and '"explanation"' not in json.dumps(deck)
    assert post(client, csrf, API, {**body, "question_ids": list(reversed(body["question_ids"]))}).get_json()["deck"] == deck
    response = client.get(f"{API}/{deck['id']}", base_url=BASE)
    assert response.headers["Cache-Control"] == "no-store" and response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.get_json()["deck"] == deck
    choices = act(client, csrf, deck, "choices", {"card_id": "q1"}).get_json()["deck"]
    assert choices["cards"][0]["choices"] == source["questions"][0]["options"]
    assert choices["cards"][0]["answer"] is None
    revealed = act(client, csrf, choices, "reveal", {"card_id": "q1"}).get_json()["deck"]
    answer = revealed["cards"][0]["answer"]
    original = source["questions"][0]["answer"]
    assert answer["text"] == "Inheritance lesson" and answer["explanation"] == original["explanation"]
    assert answer["evidence"] == original["evidence"]
    assert len(responder.calls) == 1


def test_rating_requires_reveal_replay_and_conflicts_never_count_twice(flashcards):
    client, csrf, _, responder, _ = flashcards
    deck = create(flashcards)
    assert_error(act(client, csrf, deck, "rate", {"card_id": "q1", "rating": "got_it"}), 409)
    revealed = act(client, csrf, deck, "reveal", {"card_id": "q1"}).get_json()["deck"]
    rid = uuid.uuid4().hex
    rating = act(client, csrf, revealed, "rate", {"card_id": "q1", "rating": "again"}, rid)
    assert rating.status_code == 200
    rated = rating.get_json()["deck"]
    card = rated["cards"][0]
    assert card["review_count"] == 1 and card["last_rating"] == "again" and card["needs_review"] is True
    assert card["answer"] is None and card["choices"] is None and not card["due"]
    assert act(client, csrf, revealed, "rate", {"card_id": "q1", "rating": "again"}, rid).get_json()["deck"] == rated
    assert_error(act(client, csrf, revealed, "reveal", {"card_id": "q2"}), 409)
    assert client.get(f"{API}/{deck['id']}", base_url=BASE).get_json()["deck"] == rated
    assert len(responder.calls) == 1


def test_server_clock_controls_due_queue_without_mutating_revision(flashcards, monkeypatch):
    from core.learning import flashcard_store as module
    client, csrf, _, _, _ = flashcards
    clock = SimpleNamespace(now=1000.0)
    # Isolate the scheduler clock; auth cookies must keep their real clock.
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: clock.now))
    deck = create(flashcards)
    revealed = act(client, csrf, deck, "reveal", {"card_id": "q1"}).get_json()["deck"]
    rated = act(client, csrf, revealed, "rate", {"card_id": "q1", "rating": "got_it"}).get_json()["deck"]
    assert datetime.fromisoformat(rated["cards"][0]["due_at"].replace("Z", "+00:00")).timestamp() == 87400.0
    assert rated["counts"]["due"] == 2 and not rated["cards"][0]["needs_review"]
    clock.now = 87400.0
    due = client.get(f"{API}/{deck['id']}", base_url=BASE).get_json()["deck"]
    assert due["revision"] == rated["revision"] and due["counts"]["due"] == 3


def test_source_practice_delete_does_not_change_cards_or_creation_retry(flashcards):
    client, csrf, source, responder, body = flashcards
    deck = create(flashcards)
    response = client.delete(f"{PRACTICE_API}/{source['id']}", base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert post(client, csrf, API, body).get_json()["deck"] == deck
    assert_error(post(client, csrf, API, {**body, "request_id": uuid.uuid4().hex}), 404)
    revealed = act(client, csrf, deck, "reveal", {"card_id": "q2"}).get_json()["deck"]
    assert revealed["cards"][1]["answer"]["evidence"] == source["questions"][1]["answer"]["evidence"]
    assert len(responder.calls) == 1


def test_foreign_owners_and_invalid_origin_cannot_create_or_review(materials, flashcards, monkeypatch):
    client, csrf, _, responder, body = flashcards
    deck = create(flashcards)
    other = materials.app.test_client()
    other_csrf = page(other, "/learn/flashcards")
    path = f"{API}/{deck['id']}"
    assert_error(other.get(path, base_url=BASE), 404)
    assert other.get(API, base_url=BASE).get_json()["decks"] == []
    assert_error(post(other, other_csrf, API, body), 404)
    assert_error(act(other, other_csrf, deck, "reveal", {"card_id": "q1"}), 404)
    assert_error(other.delete(path, base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": other_csrf}), 404)
    assert_error(materials.app.test_client().get(path, base_url=BASE), 401)
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.post(API, base_url=BASE, json=body, headers=headers), 403)
        assert_error(client.post(path + "/actions", base_url=BASE, json={"action": "reveal", "payload": {"card_id": "q1"}, "request_id": uuid.uuid4().hex, "expected_revision": 0}, headers=headers), 403)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "flashcard-web-token")
    assert_error(client.get(path, base_url=BASE), 401)
    assert len(responder.calls) == 1


@pytest.mark.parametrize("patch", [
    {"question_ids": []}, {"question_ids": ["q9"]}, {"question_ids": ["q1", "q1"]},
    {"question_ids": "q1"}, {"request_id": "short"}, {"front": "injected source"},
])
def test_invalid_creation_never_changes_decks(flashcards, patch):
    client, csrf, _, _, body = flashcards
    assert_error(post(client, csrf, API, {**body, **patch}), 400)
    assert client.get(API, base_url=BASE).get_json()["decks"] == []


def test_draft_practice_cannot_expose_answers_via_flashcard_creation(materials, practice, tmp_path, monkeypatch):
    monkeypatch.setitem(materials.app.config, "LEARNING_FLASHCARD_STORE_PATH", tmp_path / "cards.sqlite3")
    client, csrf, _, responder, _ = practice
    source = generated(practice)
    body = {"request_id": uuid.uuid4().hex, "practice_id": source["id"], "question_ids": ["q1"]}
    assert_error(post(client, csrf, API, body), 409, "flashcards_conflict")
    assert client.get(API, base_url=BASE).get_json()["decks"] == []
    assert len(responder.calls) == 1


def test_deleted_deck_creation_request_stays_deleted(flashcards):
    client, csrf, _, responder, body = flashcards
    deck = create(flashcards)
    assert client.delete(f"{API}/{deck['id']}", base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": csrf}).status_code == 200
    assert_error(post(client, csrf, API, body), 404)
    assert client.get(API, base_url=BASE).get_json()["decks"] == []
    assert len(responder.calls) == 1
