"""Mixed-format authored Test Maker journeys in real Chromium."""
from __future__ import annotations

from pathlib import Path
import uuid

import pytest
from playwright.sync_api import expect

from core.learning.test_maker import build_test
from tests.integration.test_learning_materials_browser import browser, live
from tests.integration.test_learning_test_maker_web import solution_answers

API = "/learn/api/test-maker"
ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-test-maker-browser"


@pytest.fixture
def maker_live(live, tmp_path, monkeypatch):
    page, context, base, state = live
    monkeypatch.setitem(state.app.config, "LEARNING_TEST_MAKER_STORE_PATH", tmp_path / "test_maker.sqlite3")
    class NoModel:
        def public_config(self):
            pytest.fail("Test Maker must not consult a model")
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", NoModel())
    page.goto(base + "/learn/test-maker")
    expect(page.locator("#testTopics input")).to_have_count(11)
    state.csrf = page.locator('meta[name="cattus-csrf-token"]').get_attribute("content")
    yield page, context, base, state


def select_topics(page, topics, seed=42):
    page.locator("#clearTestTopics").click()
    for topic in topics:
        page.locator(f'#testTopics input[value="{topic}"]').check()
    page.locator("#testSeed").fill(str(seed))


def create(page):
    with page.expect_response(lambda response: response.url.endswith(API) and response.request.method == "POST") as response:
        page.locator("#createTestButton").click()
    assert response.value.status in (200, 201), response.value.text()
    expect(page.locator("#testSession")).to_be_visible()
    return response.value.json()["test"]


def question(page, identifier):
    page.locator(f'#testQuestionNav button[data-question-id="{identifier}"]').click()
    expect(page.locator(".tm-question")).to_have_attribute("data-question-id", identifier)


def save(page):
    with page.expect_response(lambda response: response.url.endswith("/actions")) as response:
        page.locator("#saveTestDraft").click()
    assert response.value.status == 200, response.value.text()
    expect(page.locator("#testStatus")).to_contain_text("Đã lưu bản nháp")
    return response.value.json()["test"]


def submit(page):
    page.locator("#reviewTestSubmit").click()
    expect(page.locator("#testSubmitConfirm")).to_be_visible()
    with page.expect_response(lambda response: response.url.endswith("/actions")) as response:
        page.locator("#confirmTestSubmit").click()
    assert response.value.status == 200, response.value.text()
    expect(page.locator("#testSessionState")).to_contain_text("ĐÃ NỘP")
    return response.value.json()["test"]


def api_action(context, base, csrf, view, name, answers):
    response = context.request.post(base + API + "/" + view["id"] + "/actions", data={
        "action": name, "payload": {"answers": answers}, "expected_revision": view["revision"], "request_id": uuid.uuid4().hex,
    }, headers={"Origin": base, "X-CSRF-Token": csrf})
    assert response.status == 200, response.text()
    return response.json()["test"]


def test_numeric_matrix_diagram_and_essay_save_resume_submit_and_delete(maker_live):
    page, context, base, _ = maker_live
    expect(page.locator("#testTopics input:checked")).to_have_count(11)
    topics = ["ml_mse", "la_matrix_product", "ml_training_diagram", "os_deadlock"]
    select_topics(page, topics)
    view = create(page)
    answers = solution_answers(build_test(topics, 42))
    assert view["results"] is None and all(not ({"answer_key", "explanation", "rubric"} & q.keys()) for q in view["questions"])
    page.locator("#testAnswerInput").fill(answers["q1"])
    question(page, "q2")
    for row, values in enumerate(answers["q2"]):
        for col, value in enumerate(values):
            page.get_by_role("textbox", name=f"Row {row+1}, column {col+1}", exact=True).fill(value)
    question(page, "q3")
    for slot, value in answers["q3"].items():
        page.locator(f'.tm-diagram-input[data-slot-id="{slot}"]').fill(value)
    question(page, "q4")
    payload = '<img src=x onerror="window.__testMakerXSS=1"> I will explain the Coffman conditions.'
    page.locator("#testEssayInput").fill(payload)
    saved = save(page)
    assert saved["answers"]["q2"] == answers["q2"] and saved["results"] is None
    page.reload()
    page.locator(f'[data-test-id="{view["id"]}"]').click()
    question(page, "q3")
    for slot, value in answers["q3"].items():
        expect(page.locator(f'.tm-diagram-input[data-slot-id="{slot}"]')).to_have_value(value)
    question(page, "q4")
    expect(page.locator("#testEssayInput")).to_have_value(payload)
    final = submit(page)
    assert final["results"]["auto"]["earned"] == final["results"]["auto"]["possible"]
    assert final["results"]["essay"] == {"answered": 1, "pending": 1, "total": 1}
    expect(page.locator('.tm-result[data-status="pending_review"]')).to_contain_text("PENDING HUMAN REVIEW")
    expect(page.locator('.tm-result[data-status="pending_review"] .tm-rubric li')).to_have_count(4)
    expect(page.locator("#testContent img")).to_have_count(0)
    assert page.evaluate("typeof window.__testMakerXSS") == "undefined"
    page.locator("#deleteTestButton").click()
    page.locator("#confirmTestDelete").click()
    expect(page.locator("#testSession")).to_be_hidden()
    assert context.request.get(base + API).json()["tests"] == []


def test_percentage_hex_and_unanswered_essay_results_disclose_grading_boundaries(maker_live):
    page, _, _, _ = maker_live
    topics = ["ml_gini", "ml_tpr", "os_paging", "os_deadlock"]
    select_topics(page, topics, seed=19)
    view = create(page)
    answers = solution_answers(build_test(topics, 19))
    del answers["q4"]
    for item in view["questions"]:
        if item["kind"] == "essay": continue
        question(page, item["id"])
        page.locator("#testAnswerInput").fill(answers[item["id"]])
    saved = save(page)
    assert saved["answers"] == answers
    final = submit(page)
    assert final["results"]["auto"]["earned"] == 6
    blank = page.locator('.tm-result[data-question-id="q4"]')
    expect(blank).to_contain_text("NO ANSWER SUBMITTED · no automatic essay grade")
    expect(blank.get_by_text("0 / 4 points", exact=True)).to_have_count(0)
    expect(blank.get_by_role("heading", name="Model answer for human comparison", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Scoring criteria", exact=True)).to_have_count(3)


def test_both_diagrams_have_editable_nodes_and_mobile_internal_scroll(maker_live):
    page, _, _, _ = maker_live
    topics = ["ml_training_diagram", "os_producer_consumer_diagram"]
    select_topics(page, topics)
    view = create(page)
    answers = solution_answers(build_test(topics, 42))
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for item in view["questions"]:
        question(page, item["id"])
        assert all("slot_id" in node or "text" in node for node in item["data"]["nodes"])
        drawing = page.locator(".tm-diagram-canvas svg")
        assert drawing.evaluate("el => el.namespaceURI") == "http://www.w3.org/2000/svg"
        assert drawing.bounding_box()["width"] == item["data"]["width"]
        assert drawing.bounding_box()["height"] == item["data"]["height"]
        assert drawing.locator("rect").first.bounding_box()["width"] > 100
        assert drawing.locator("line").first.evaluate("el => el.getTotalLength()") >= 20
        assert drawing.locator(".tm-diagram-text").first.bounding_box()["width"] > 30
        for caption, node in zip(drawing.locator(".tm-diagram-text").all(), [node for node in item["data"]["nodes"] if "text" in node]):
            assert caption.bounding_box()["width"] <= node["width"] - 12
        expect(page.locator(".tm-diagram-input")).to_have_count(len(item["input"]["slots"]))
        assert all(value == "" for value in page.locator(".tm-diagram-input").evaluate_all("els => els.map(el => el.value)"))
        for slot, value in answers[item["id"]].items():
            page.locator(f'.tm-diagram-input[data-slot-id="{slot}"]').fill(value)
        page.screenshot(path=str(ARTIFACTS / (item["topic_id"] + "-desktop.png")), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(ARTIFACTS / (item["topic_id"] + "-mobile.png")), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator(".tm-diagram-scroll").evaluate("el => el.scrollWidth > el.clientWidth")
        last_slot = item["input"]["slots"][-1]["id"]
        last_input = page.locator(f'.tm-diagram-input[data-slot-id="{last_slot}"]')
        last_input.fill(answers[item["id"]][last_slot])
        last_input.scroll_into_view_if_needed()
        assert last_input.evaluate("el => { const box=el.getBoundingClientRect(), rail=el.closest('.tm-diagram-scroll').getBoundingClientRect(); return box.left >= rail.left && box.right <= rail.right; }")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(ARTIFACTS / (item["topic_id"] + "-mobile-last-node.png")), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
    final = submit(page)
    assert final["results"]["auto"]["earned"] == 8


def test_lost_create_and_submit_reply_reuses_exact_requests(maker_live):
    page, context, base, _ = maker_live
    select_topics(page, ["ml_mse"])
    creates = []
    def lose_create(route):
        if route.request.method != "POST": route.continue_(); return
        creates.append(route.request.post_data_json)
        response = route.fetch()
        if len(creates) == 1: route.abort()
        else: route.fulfill(response=response)
    page.route("**/learn/api/test-maker", lose_create)
    page.locator("#createTestButton").click()
    expect(page.locator("#retryTestRequest")).to_be_visible()
    page.locator("#retryTestRequest").click()
    expect(page.locator("#testSession")).to_be_visible()
    assert creates[0] == creates[1]
    assert len(context.request.get(base + API).json()["tests"]) == 1
    answer = solution_answers(build_test(["ml_mse"], 42))["q1"]
    page.locator("#testAnswerInput").fill(answer)
    submissions = []
    def lose_submit(route):
        body = route.request.post_data_json
        if body["action"] != "submit": route.continue_(); return
        submissions.append(body)
        response = route.fetch()
        if len(submissions) == 1: route.abort()
        else: route.fulfill(response=response)
    page.route("**/actions", lose_submit)
    page.locator("#reviewTestSubmit").click()
    page.locator("#confirmTestSubmit").click()
    expect(page.locator("#retryTestRequest")).to_be_visible()
    page.locator("#retryTestRequest").click()
    expect(page.locator("#testSessionState")).to_contain_text("ĐÃ NỘP")
    assert submissions[0] == submissions[1]
    identifier = context.request.get(base + API).json()["tests"][0]["id"]
    assert context.request.get(base + API + "/" + identifier).json()["test"]["revision"] == 1


def test_stale_draft_is_kept_until_explicit_saved_or_local_choice(maker_live):
    page, context, base, state = maker_live
    select_topics(page, ["ml_mse"])
    view = create(page)
    page.locator("#testAnswerInput").fill("123/7")
    page.locator("#newTestButton").click()
    expect(page.locator("#testNoticeText")).to_contain_text("chưa được lưu")
    assert page.locator("#testAnswerInput").input_value() == "123/7"
    latest = api_action(context, base, state.csrf, view, "save", {"q1": "0"})
    page.locator("#saveTestDraft").click()
    expect(page.locator("#testNoticeText")).to_contain_text("Đọc bản đã lưu")
    page.locator("#reloadTestButton").click()
    expect(page.locator("#testConflict")).to_be_visible()
    expect(page.locator("#testAnswerInput")).to_have_value("123/7")
    expect(page.locator("#testSavedComparison")).to_contain_text('"0"')
    page.locator("#keepDraftTest").click()
    expect(page.locator("#testConflict")).to_be_hidden()
    expect(page.locator("#testAnswerInput")).to_have_value("123/7")
    saved = save(page)
    assert saved["answers"] == {"q1": "123/7"} and saved["revision"] == latest["revision"] + 1
    page.locator("#testAnswerInput").fill("unsaved")
    page.locator("#newTestButton").click()
    page.locator("#reloadTestButton").click()
    expect(page.locator("#testConflict")).to_be_visible()
    page.locator("#useSavedTest").click()
    expect(page.locator("#testAnswerInput")).to_have_value("123/7")


@pytest.mark.parametrize("later_submit", [False, True], ids=["later-draft", "later-submission"])
def test_lost_save_reply_does_not_replace_local_answers_with_newer_tab(maker_live, later_submit):
    page, context, base, state = maker_live
    select_topics(page, ["ml_mse"])
    view = create(page)
    local = "123/7"
    page.locator("#testAnswerInput").fill(local)
    requests = []
    def lose_save(route):
        requests.append(route.request.post_data_json)
        response = route.fetch()
        if len(requests) == 1: route.abort()
        else: route.fulfill(response=response)
    page.route("**/actions", lose_save)
    page.locator("#saveTestDraft").click()
    expect(page.locator("#retryTestRequest")).to_be_visible()
    acknowledged = context.request.get(base + API + "/" + view["id"]).json()["test"]
    assert acknowledged["answers"] == {"q1": local}
    latest = api_action(context, base, state.csrf, acknowledged, "save", {"q1": "0"})
    if later_submit:
        latest = api_action(context, base, state.csrf, latest, "submit", {"q1": "0"})
    page.locator("#retryTestRequest").click()
    expect(page.locator("#testConflict")).to_be_visible()
    assert requests[0] == requests[1]
    expect(page.locator("#testAnswerInput")).to_have_value(local)
    expect(page.locator("#testDraftComparison")).to_contain_text(local)
    expect(page.locator("#testSavedComparison")).to_contain_text('"0"')
    current = context.request.get(base + API + "/" + view["id"]).json()["test"]
    assert current["revision"] == latest["revision"] and current["answers"] == {"q1": "0"}
    if later_submit:
        expect(page.locator("#keepDraftTest")).to_be_disabled()
        page.locator("#useSavedTest").click()
        expect(page.locator("#testSessionState")).to_contain_text("ĐÃ NỘP")
        expect(page.locator(".tm-result[data-status='incorrect']")).to_have_count(1)
        expect(page.locator("#testDraftActions")).to_be_hidden()
    else:
        page.locator("#keepDraftTest").click()
        expect(page.locator("#testAnswerInput")).to_have_value(local)
        final = save(page)
        assert final["revision"] == latest["revision"] + 1 and final["answers"] == {"q1": local}
