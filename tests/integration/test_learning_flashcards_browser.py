"""Real browser flashcard review with completed Practice and isolated stores."""
from __future__ import annotations

from pathlib import Path
import uuid

import pytest
from playwright.sync_api import expect

from tests.integration.test_learning_materials_browser import browser, live, document, open_materials, collection_details
from tests.integration.test_learning_practice_web import PracticeResponder

API = "/learn/api/flashcards"
PRACTICE = "/learn/api/practice"
ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-flashcards-browser"


def post(context, base, csrf, path, body):
    response = context.request.post(base + path, data=body, headers={"Origin": base, "X-CSRF-Token": csrf})
    assert response.status in (200, 201), response.text()
    return response.json()


def practice_action(context, base, csrf, value, name, payload=None):
    return post(context, base, csrf, PRACTICE + "/" + value["id"] + "/actions", {
        "action": name, "payload": payload or {}, "expected_revision": value["revision"], "request_id": uuid.uuid4().hex,
    })["practice"]


@pytest.fixture
def flash_live(live, tmp_path, monkeypatch):
    page, context, base, state = live
    state.responder = PracticeResponder()
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", state.responder)
    monkeypatch.setitem(state.app.config, "LEARNING_PRACTICE_STORE_PATH", tmp_path / "practice.sqlite3")
    monkeypatch.setitem(state.app.config, "LEARNING_FLASHCARD_STORE_PATH", tmp_path / "flashcards.sqlite3")
    open_materials(page, base)
    payload = '<img src=x onerror="window.__flashXSS=1">'
    page.locator("#materialsFilesInput").set_input_files({"name": "inheritance.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": document("Inheritance lesson. " + payload)})
    page.locator("#materialsTitleInput").fill("Java review sources")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#previewHeading")).to_have_text("Java review sources")
    state.collection = collection_details(context, base)[0]
    state.csrf = page.locator('meta[name="cattus-csrf-token"]').get_attribute("content")
    body = {"request_id": uuid.uuid4().hex, "collection_id": state.collection["id"], "unit_ids": [state.collection["units"][0]["unit_id"]], "count": 3}
    value = post(context, base, state.csrf, PRACTICE, body)["practice"]
    value = practice_action(context, base, state.csrf, value, "start")
    value = practice_action(context, base, state.csrf, value, "answer", {"item_id": "q1", "option_id": "b", "reflection": "My first guess"})
    value = practice_action(context, base, state.csrf, value, "hint", {"item_id": "q1"})
    value = practice_action(context, base, state.csrf, value, "answer", {"item_id": "q1", "option_id": "a", "reflection": "After comparing"})
    value = practice_action(context, base, state.csrf, value, "next")
    value = practice_action(context, base, state.csrf, value, "solution", {"item_id": "q2"})
    value = practice_action(context, base, state.csrf, value, "next")
    value = practice_action(context, base, state.csrf, value, "answer", {"item_id": "q3", "option_id": "a", "reflection": ""})
    value = practice_action(context, base, state.csrf, value, "next")
    assert value["status"] == "completed"
    state.practice = value
    state.responder.available = False
    state.flash_url = base + "/learn/flashcards?practice=" + value["id"]
    page.goto(state.flash_url)
    expect(page.locator("#createFlashcardsButton")).to_be_enabled()
    yield page, context, base, state
    assert len(state.responder.calls) == 1


def create(page):
    with page.expect_response(lambda response: response.url.endswith(API) and response.request.method == "POST") as response:
        page.locator("#createFlashcardsButton").click()
    assert response.value.status in (200, 201), response.value.text()
    expect(page.locator("#flashcardDeck")).to_be_visible()
    return response.value.json()["deck"]


def action(page, name):
    with page.expect_response(lambda response: response.url.endswith("/actions")) as response:
        page.get_by_role("button", name=name, exact=True).click()
    assert response.value.status == 200, response.value.text()
    return response.value.json()["deck"]


def saved(context, base, identifier):
    return context.request.get(base + API + "/" + identifier).json()["deck"]


def test_completed_source_defaults_flip_rate_schedule_resume_and_delete(flash_live):
    page, context, base, state = flash_live
    expect(page.locator("#flashcardQuestions input:checked")).to_have_count(2)
    expect(page.locator("#flashcardQuestions input[value=q3]")).not_to_be_checked()
    deck = create(page)
    assert all(card["answer"] is None and card["choices"] is None for card in deck["cards"])
    expect(page.locator("#flashcardAnswer")).to_have_count(0)
    action(page, "Show original choices")
    expect(page.locator(".flash-choices li")).to_have_count(4)
    expect(page.locator("#flashcardAnswer")).to_have_count(0)
    action(page, "Reveal answer")
    expect(page.locator(".flash-answer-text")).to_have_text("Inheritance lesson")
    page.locator(".flash-answer-source summary").click()
    expect(page.locator(".flash-answer-source blockquote")).to_have_text(state.collection["units"][0]["text"])
    expect(page.locator(".flash-answer-source a")).to_have_attribute("target", "_blank")
    rated = action(page, "Got it · ôn sau")
    assert rated["cards"][0]["review_count"] == 1
    expect(page.locator(".flash-review-card")).to_have_attribute("data-card-id", "q2")
    action(page, "Reveal answer")
    again = action(page, "Again · 10 min")
    assert again["counts"]["due"] == 0
    expect(page.locator("#flashcardContent")).to_contain_text("Chưa có thẻ đến hạn")
    expect(page.locator("#flashcardEmptyTitle")).to_be_focused()
    page.locator("#flashcardFilter").select_option("needs_review")
    expect(page.locator(".flash-review-card")).to_have_attribute("data-card-id", "q2")
    expect(page.locator("#flashcardAnswer")).to_have_count(0)
    page.reload()
    page.locator(f'[data-deck-id="{deck["id"]}"]').click()
    expect(page.locator("#flashcardContent")).to_contain_text("Chưa có thẻ đến hạn")
    page.locator("#deleteFlashcardDeck").click()
    expect(page.locator("#flashcardDeleteConfirm")).to_be_visible()
    page.locator("#confirmFlashcardDelete").click()
    expect(page.locator("#flashcardDeck")).to_be_hidden()
    assert context.request.get(base + PRACTICE + "/" + state.practice["id"]).json()["practice"]["status"] == "completed"


def test_lost_creation_and_rating_replay_keep_exact_request_and_single_review(flash_live):
    page, context, base, state = flash_live
    requests = []
    def lose_first(route):
        if route.request.method != "POST":
            route.continue_()
            return
        requests.append(route.request.post_data_json)
        response = route.fetch()
        if len(requests) == 1: route.abort()
        else: route.fulfill(response=response)
    page.route("**/learn/api/flashcards", lose_first)
    page.locator("#createFlashcardsButton").click()
    expect(page.locator("#retryFlashcardRequest")).to_be_visible()
    page.locator("#retryFlashcardRequest").click()
    expect(page.locator("#flashcardDeck")).to_be_visible()
    assert requests[0] == requests[1]
    assert len(context.request.get(base + API).json()["decks"]) == 1
    deck = context.request.get(base + API).json()["decks"][0]
    action(page, "Reveal answer")
    ratings = []
    def lose_rating(route):
        body = route.request.post_data_json
        if body["action"] != "rate":
            route.continue_()
            return
        ratings.append(body)
        response = route.fetch()
        if len(ratings) == 1: route.abort()
        else: route.fulfill(response=response)
    page.route("**/actions", lose_rating)
    page.get_by_role("button", name="Got it · ôn sau", exact=True).click()
    expect(page.locator("#retryFlashcardRequest")).to_be_visible()
    current = saved(context, base, deck["id"])
    assert current["cards"][0]["review_count"] == 1
    page.locator("#retryFlashcardRequest").click()
    expect(page.locator(".flash-review-card")).to_have_attribute("data-card-id", "q2")
    assert ratings[0] == ratings[1]
    assert saved(context, base, deck["id"])["cards"][0]["review_count"] == 1


def test_stale_rating_reload_never_applies_to_another_card(flash_live):
    page, context, base, state = flash_live
    deck = create(page)
    action(page, "Reveal answer")
    latest = saved(context, base, deck["id"])
    updated = post(context, base, state.csrf, API + "/" + deck["id"] + "/actions", {
        "action": "rate", "payload": {"card_id": "q1", "rating": "again"}, "expected_revision": latest["revision"], "request_id": uuid.uuid4().hex,
    })["deck"]
    page.get_by_role("button", name="Got it · ôn sau", exact=True).click()
    expect(page.locator("#flashcardNoticeText")).to_contain_text("Đọc bộ đã lưu")
    expect(page.locator("#flashcardFilter")).to_be_disabled()
    page.locator("#reloadFlashcardDeck").click()
    expect(page.locator(".flash-review-card")).to_have_attribute("data-card-id", "q2")
    assert saved(context, base, deck["id"])["cards"][0]["last_rating"] == "again"
    assert saved(context, base, deck["id"])["cards"][1]["review_count"] == 0
    expect(page.locator("#flashcardAnswer")).to_have_count(0)


def test_source_markup_is_inert_mobile_layout_and_cards_survive_practice_deletion(flash_live):
    page, context, base, state = flash_live
    deck = create(page)
    response = context.request.delete(base + PRACTICE + "/" + state.practice["id"], headers={"Origin": base, "X-CSRF-Token": state.csrf})
    assert response.status == 200
    action(page, "Reveal answer")
    page.locator(".flash-answer-source summary").click()
    expect(page.locator(".flash-answer-source blockquote")).to_contain_text("<img src=x")
    expect(page.locator(".flash-answer-source img")).to_have_count(0)
    assert page.evaluate("typeof window.__flashXSS") == "undefined"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "flashcards-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ARTIFACTS / "flashcards-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert saved(context, base, deck["id"])["cards"][0]["answer"]["evidence"][0]["text"] == state.collection["units"][0]["text"]


def test_completed_practice_entry_opens_exact_source_set_in_new_tab(flash_live):
    page, context, base, state = flash_live
    page.goto(base + "/learn/practice")
    page.locator(f'[data-practice-id="{state.practice["id"]}"]').click()
    link = page.locator("#createPracticeFlashcards")
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("href", "/learn/flashcards?practice=" + state.practice["id"])
    with context.expect_page() as opened:
        link.click()
    target = opened.value
    expect(target.locator("#flashcardPractice")).to_have_value(state.practice["id"])
    expect(target.locator("#flashcardQuestions input:checked")).to_have_count(2)


def test_lost_delete_response_is_recovered_by_read(flash_live):
    page, context, base, _ = flash_live
    create(page)
    def lose_delete(route):
        if route.request.method != "DELETE": route.continue_(); return
        response = route.fetch()
        assert response.status == 200
        route.abort()
    page.route("**/flashcards/*", lose_delete)
    page.locator("#deleteFlashcardDeck").click()
    page.locator("#confirmFlashcardDelete").click()
    expect(page.locator("#flashcardNoticeText")).to_contain_text("Đọc bộ đã lưu")
    page.locator("#reloadFlashcardDeck").click()
    expect(page.locator("#flashcardDeck")).to_be_hidden()
    assert context.request.get(base + API).json()["decks"] == []
