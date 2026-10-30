"""Local Chromium practice journeys, with a deterministic model and isolated state."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.integration.test_learning_materials_browser import (
    browser, live, document, collection_details, open_materials,
)
from tests.integration.test_learning_practice_web import PracticeResponder


API = "/learn/api/practice"
ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-practice-browser"


@pytest.fixture
def practice_live(live, tmp_path, monkeypatch):
    page, context, base, state = live
    state.responder = PracticeResponder()
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", state.responder)
    monkeypatch.setitem(state.app.config, "LEARNING_PRACTICE_STORE_PATH", tmp_path / "practice.sqlite3")
    open_materials(page, base)
    payload = '<img src=x onerror="window.__practiceXSS=1">'
    page.locator("#materialsFilesInput").set_input_files({"name": "inheritance.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": document("Inheritance lets a subclass override an instance method.", payload + " Source markup is plain text.")})
    page.locator("#materialsTitleInput").fill("Java sources")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#previewHeading")).to_have_text("Java sources")
    state.collection = collection_details(context, base)[0]
    state.unit = state.collection["units"][0]
    state.practice_url = base + "/learn/practice?collection=" + state.collection["id"] + "&unit=" + state.unit["unit_id"]
    page.goto(state.practice_url)
    expect(page.locator("#generatePracticeButton")).to_be_enabled()
    yield page, context, base, state


def generate(page):
    with page.expect_response(lambda response: response.url.endswith(API) and response.request.method == "POST") as response:
        page.locator("#generatePracticeButton").click()
    assert response.value.status in (200, 201)
    expect(page.locator("#practiceSession")).to_be_visible()
    return response.value.json()["practice"]


def action(page, name):
    with page.expect_response(lambda response: response.url.endswith("/actions")) as response:
        page.get_by_role("button", name=name, exact=True).click()
    assert response.value.status == 200, response.value.text()
    return response.value.json()["practice"]


def answer(page, option="a", reflection="Because the source names this concept."):
    page.locator(f'input[name="practice-option"][value="{option}"]').check()
    page.locator("#practiceReflection").fill(reflection)
    return action(page, "Submit answer")


def test_review_start_answer_resume_finish_and_delete(practice_live):
    page, context, base, state = practice_live
    assert not state.responder.calls
    expect(page.locator("#practiceCount")).to_have_value("3")
    expect(page.locator("#practiceModel")).to_contain_text("ollama · practice-fixture")
    expect(page.locator("#practiceUnits input:checked")).to_have_count(1)
    view = generate(page)
    assert len(state.responder.calls) == 1
    assert all(item["answer"] is None for item in view["questions"])
    expect(page.locator(".practice-answer")).to_have_count(0)
    page.locator('[data-item-id="q1"]').get_by_role("button", name="Review answer & source").click()
    expect(page.locator('.practice-answer[data-item-id="q1"]')).to_be_visible()
    page.locator(".practice-answer-source summary").click()
    expect(page.locator(".practice-answer-source blockquote")).to_have_text(state.unit["text"])
    expect(page.locator(".practice-answer-source a")).to_have_attribute("target", "_blank")
    assert "unit=" + state.unit["unit_id"] in page.locator(".practice-answer-source a").get_attribute("href")
    action(page, "Start practice")
    expect(page.locator(".practice-progress")).to_contain_text("answer reviewed before start")
    answer(page)
    action(page, "Next question →")
    expect(page.locator(".practice-progress")).to_contain_text("Question 2 / 3")
    answer(page, "b", "My first idea")
    expect(page.locator(".practice-answer")).to_have_count(0)
    action(page, "Hint (0/2)")
    answer(page, "a", "I compared the source after the hint")
    page.reload()
    page.locator(f'[data-practice-id="{view["id"]}"]').click()
    expect(page.locator("#practiceContent")).to_contain_text("I compared the source after the hint")
    action(page, "Next question →")
    action(page, "Show solution & source")
    finished = action(page, "Finish practice")
    assert finished["status"] == "completed"
    assert finished["summary"]["answers_reviewed_before_start"] == 1
    assert finished["summary"]["first_try_correct"] == 1
    expect(page.locator("#practiceSessionState")).to_have_text("Đã hoàn thành")
    assert len(state.responder.calls) == 1
    page.locator("#deletePracticeButton").click()
    expect(page.locator("#practiceDeleteConfirm")).to_be_visible()
    page.locator("#confirmPracticeDelete").click()
    expect(page.locator("#practiceSession")).to_be_hidden()
    assert context.request.get(base + API).json()["practices"] == []
    assert collection_details(context, base)[0]["id"] == state.collection["id"]


def test_lost_generation_response_reuses_request_without_second_model_call(practice_live):
    page, _, _, state = practice_live
    requests = []
    def lose_first(route):
        if route.request.method != "POST":
            route.continue_()
            return
        requests.append(route.request.post_data_json)
        response = route.fetch()
        if len(requests) == 1:
            assert response.status == 201
            route.abort()
        else:
            route.fulfill(response=response)
    page.route("**/learn/api/practice", lose_first)
    page.locator("#generatePracticeButton").click()
    expect(page.locator("#retryPracticeRequest")).to_be_visible()
    expect(page.locator("#generatePracticeButton")).to_be_disabled()
    assert len(state.responder.calls) == 1
    page.locator("#retryPracticeRequest").click()
    expect(page.locator("#practiceSessionState")).to_have_text("Xem trước")
    assert requests[0] == requests[1]
    assert len(state.responder.calls) == 1


def test_conflict_keeps_answer_draft_until_explicit_reload(practice_live):
    page, _, _, state = practice_live
    generate(page)
    action(page, "Start practice")
    page.locator('input[name="practice-option"][value="b"]').check()
    page.locator("#practiceReflection").fill("Keep my reasoning")
    def conflict(route):
        route.fulfill(status=409, json={"ok": False, "error": "Practice changed", "error_code": "practice_conflict"})
    page.route("**/actions", conflict)
    page.locator("#submitPracticeAnswer").click()
    expect(page.locator("#practiceNoticeText")).to_contain_text("Bản nháp vẫn được giữ")
    expect(page.locator("#practiceReflection")).to_have_value("Keep my reasoning")
    expect(page.locator("#submitPracticeAnswer")).to_be_disabled()
    page.unroute("**/actions", conflict)
    page.locator("#reloadPracticeButton").click()
    expect(page.locator("#submitPracticeAnswer")).to_be_enabled()
    expect(page.locator('input[name="practice-option"][value="b"]')).to_be_checked()
    expect(page.locator("#practiceReflection")).to_have_value("Keep my reasoning")
    view = action(page, "Submit answer")
    assert view["questions"][0]["reflection"] == "Keep my reasoning"
    assert view["questions"][0]["attempts"] == 1
    assert len(state.responder.calls) == 1


def test_hint_preserves_draft_wrong_answer_hides_key_and_next_is_explicit(practice_live):
    page, _, _, state = practice_live
    generate(page)
    action(page, "Start practice")
    page.locator('input[name="practice-option"][value="b"]').check()
    page.locator("#practiceReflection").fill("An unfinished thought")
    action(page, "Hint (0/2)")
    expect(page.locator("#practiceReflection")).to_have_value("An unfinished thought")
    expect(page.locator('input[name="practice-option"][value="b"]')).to_be_checked()
    action(page, "Submit answer")
    expect(page.locator(".practice-answer")).to_have_count(0)
    expect(page.get_by_role("button", name="Next question →", exact=True)).to_have_count(0)
    expect(page.locator("#practiceContent")).not_to_contain_text("The selected passage explicitly")
    action(page, "Show solution & source")
    expect(page.locator(".practice-answer")).to_be_visible()
    page.locator("#practiceReflection").fill("A note I have not submitted")
    page.get_by_role("button", name="Next question →", exact=True).click()
    expect(page.locator("#practiceNoticeText")).to_contain_text("bản nháp")
    expect(page.locator(".practice-progress")).to_contain_text("Question 1 / 3")
    page.get_by_role("button", name="Bỏ bản nháp", exact=True).click()
    action(page, "Next question →")
    expect(page.locator(".practice-progress")).to_contain_text("Question 2 / 3")
    assert len(state.responder.calls) == 1


def test_lost_hint_ack_preserves_draft_when_another_tab_advanced(practice_live):
    page, context, base, state = practice_live
    generate(page)
    action(page, "Start practice")
    page.locator('input[name="practice-option"][value="b"]').check()
    page.locator("#practiceReflection").fill("My unfinished reasoning for question one")
    requests = []
    def lose_hint_ack(route):
        requests.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 200
        if len(requests) == 1:
            route.abort()
        else:
            route.fulfill(response=response)
    page.route("**/actions", lose_hint_ack)
    page.get_by_role("button", name="Hint (0/2)", exact=True).click()
    expect(page.locator("#retryPracticeRequest")).to_be_visible()
    other = context.new_page()
    other.goto(base + "/learn/practice")
    other.locator("#practiceHistory button").click()
    expect(other.locator(".practice-progress")).to_contain_text("Question 1 / 3")
    action(other, "Show solution & source")
    action(other, "Next question →")
    expect(other.locator(".practice-progress")).to_contain_text("Question 2 / 3")
    page.locator("#retryPracticeRequest").click()
    expect(page.locator(".practice-progress")).to_contain_text("Question 2 / 3")
    expect(page.locator("#practiceNoticeText")).to_contain_text("câu khác")
    expect(page.locator("#practiceContent")).to_contain_text("My unfinished reasoning for question one")
    expect(page.locator("#practiceReflection")).to_have_value("")
    expect(page.locator('input[name="practice-option"]:checked')).to_have_count(0)
    assert requests[0] == requests[1]
    assert page.evaluate("""() => {
        const event = new Event('beforeunload', {cancelable: true});
        window.dispatchEvent(event); return event.defaultPrevented;
    }""")
    page.locator("#newPracticeButton").click()
    expect(page.locator("#practiceSession")).to_be_visible()
    page.get_by_role("button", name="Bỏ bản nháp của q1", exact=True).click()
    page.locator("#newPracticeButton").click()
    expect(page.locator("#practiceCreate")).to_be_visible()
    assert len(state.responder.calls) == 1
    other.close()


def test_multiple_cross_tab_advances_keep_each_unsubmitted_draft(practice_live):
    page, context, base, state = practice_live
    generate(page)
    action(page, "Start practice")
    other = context.new_page()
    other.goto(base + "/learn/practice")
    other.locator("#practiceHistory button").click()
    expect(other.locator(".practice-progress")).to_contain_text("Question 1 / 3")
    for index, reasoning in ((1, "Unsubmitted reasoning for question one"), (2, "Unsubmitted reasoning for question two")):
        page.locator('input[name="practice-option"][value="b"]').check()
        page.locator("#practiceReflection").fill(reasoning)
        action(other, "Show solution & source")
        action(other, "Next question →")
        page.get_by_role("button", name="Hint (0/2)", exact=True).click()
        expect(page.locator("#practiceNoticeText")).to_contain_text("Bản nháp vẫn được giữ")
        page.locator("#reloadPracticeButton").click()
        expect(page.locator(".practice-progress")).to_contain_text(f"Question {index + 1} / 3")
        expect(page.locator(f'[data-draft-item-id="q{index}"]')).to_contain_text(reasoning)
    expect(page.locator('[data-draft-item-id="q1"]')).to_contain_text("Unsubmitted reasoning for question one")
    expect(page.locator('[data-draft-item-id="q2"]')).to_contain_text("Unsubmitted reasoning for question two")
    expect(page.locator("#practiceReflection")).to_have_value("")
    assert page.evaluate("""() => {
        const event = new Event('beforeunload', {cancelable: true});
        window.dispatchEvent(event); return event.defaultPrevented;
    }""")
    page.get_by_role("button", name="Bỏ bản nháp của q1", exact=True).click()
    expect(page.locator('[data-draft-item-id="q2"]')).to_contain_text("Unsubmitted reasoning for question two")
    page.locator("#newPracticeButton").click()
    expect(page.locator("#practiceSession")).to_be_visible()
    page.get_by_role("button", name="Bỏ bản nháp của q2", exact=True).click()
    page.locator("#newPracticeButton").click()
    expect(page.locator("#practiceCreate")).to_be_visible()
    assert len(state.responder.calls) == 1
    other.close()


def test_source_text_is_safe_and_mobile_stays_within_viewport(practice_live):
    page, _, _, state = practice_live
    page.locator("#practiceUnits input").first.uncheck()
    page.locator("#practiceUnits input").nth(1).check()
    page.locator("#practiceUnits summary").nth(1).click()
    expect(page.locator("#practiceUnits img")).to_have_count(0)
    generate(page)
    page.locator('[data-item-id="q1"]').get_by_role("button", name="Review answer & source").click()
    page.locator(".practice-answer-source summary").click()
    expect(page.locator(".practice-answer-source blockquote")).to_contain_text("<img src=x")
    expect(page.locator(".practice-answer-source img")).to_have_count(0)
    assert page.evaluate("typeof window.__practiceXSS") == "undefined"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "practice-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(ARTIFACTS / "practice-mobile.png"), full_page=True)
    overflow = page.evaluate("""() => Array.from(document.querySelectorAll('body *')).map(el => {
        const rect = el.getBoundingClientRect();
        return {element: el.tagName.toLowerCase(), id: el.id, className: el.className,
                left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width)};
    }).filter(rect => rect.width && (rect.left < -1 || rect.right > window.innerWidth + 1))""")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), overflow
    assert len(state.responder.calls) == 1


def test_generation_failure_is_durable_and_never_retries_automatically(practice_live):
    page, context, base, state = practice_live
    def fail():
        raise RuntimeError("private provider detail")
    state.responder.effect = fail
    view = generate(page)
    assert view["status"] == "failed"
    expect(page.locator("#practiceSessionState")).to_have_text("Chưa tạo được")
    expect(page.locator("#practiceContent")).not_to_contain_text("private provider detail")
    assert len(state.responder.calls) == 1
    page.reload()
    page.locator(f'[data-practice-id="{view["id"]}"]').click()
    expect(page.locator("#practiceSessionState")).to_have_text("Chưa tạo được")
    assert len(context.request.get(base + API).json()["practices"]) == 1
    assert len(state.responder.calls) == 1


def test_material_unit_entry_opens_exact_source_without_losing_draft(practice_live):
    page, _, base, state = practice_live
    page.goto(base + "/learn/materials?collection=" + state.collection["id"] + "&unit=" + state.unit["unit_id"])
    expect(page.locator("#conceptInput")).to_be_enabled()
    page.locator("#conceptInput").fill("My unsaved concept")
    page.locator("#practiceFromUnit").click()
    expect(page.locator("#materialsNoticeText")).to_contain_text("thay đổi chưa xác nhận")
    expect(page.locator("#conceptInput")).to_have_value("My unsaved concept")
    page.locator("#conceptInput").fill("")
    with page.expect_popup() as popup:
        page.locator("#practiceFromUnit").click()
    child = popup.value
    expect(child.locator("#generatePracticeButton")).to_be_enabled()
    expect(child.locator("#practiceUnits input:checked")).to_have_value(state.unit["unit_id"])
    expect(page.locator("#unitText")).to_have_text(state.unit["text"])
    assert len(state.responder.calls) == 0
    child.close()
