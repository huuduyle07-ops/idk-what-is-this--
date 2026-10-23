"""Real Chromium pilot checks against isolated local Flask and SQLite state."""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.test_auth_web1 import configure_offline_web
from tests.test_auth_web1_browser import _Listener

ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-browser"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def live(tmp_path, monkeypatch, browser):
    state = configure_offline_web(tmp_path, monkeypatch, allow_loopback=True)
    monkeypatch.setitem(state.app.config, "LEARNING_STORE_PATH", tmp_path / "learning.sqlite3")
    listener = _Listener(state.app)
    base = f"http://127.0.0.1:{listener.port}"
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    yield page, context, base, state
    assert errors == []
    assert state.calls == []
    context.close()
    listener.close()


def open_lesson(page, base):
    page.goto(base + "/learn")
    expect(page.locator("#startButton")).to_be_enabled()
    page.locator("#startButton").click()
    expect(page.locator("#questionCard")).to_be_visible()


def test_first_learner_flow_reload_hints_transfer_and_summary(live):
    page, context, base, _ = live
    page.goto(base + "/learn")
    expect(page.locator("#startButton")).to_be_enabled()
    page.screenshot(path=str(ARTIFACTS / "desktop-welcome.png"), full_page=True)
    page.locator("#startButton").click()
    expect(page.locator("#questionCard")).to_be_visible()
    page.locator("#reflectionDetails summary").click()
    reflection = '<img src=x onerror="alert(1)"> Tôi nhìn vào kiểu biến.'
    page.locator("#reflectionInput").fill(reflection)
    page.locator('input[name="answerOption"][value="a"]').check()
    page.locator("#answerButton").click()
    expect(page.locator("#feedbackHeading")).to_have_text("Chưa đúng ở lần thử này")
    expect(page.locator("#feedbackBody")).not_to_contain_text("meow")
    page.reload()
    expect(page.locator("#reflectionInput")).to_have_value(reflection)
    expect(page.locator('input[name="answerOption"][value="a"]')).to_be_checked()
    page.locator("#hintButton").click()
    expect(page.locator("#hintsCard")).to_be_visible()
    page.locator('input[name="answerOption"][value="b"]').check()
    page.locator("#answerButton").click()
    expect(page.locator("#feedbackHeading")).to_have_text("Đúng với bài này")
    expect(page.locator(".code-line.evidence")).to_have_count(3)
    page.screenshot(path=str(ARTIFACTS / "desktop-feedback.png"), full_page=True)
    page.locator("#nextButton").click()
    expect(page.locator("#lessonBadge")).to_have_text("Tình huống 2 / 3")
    page.locator('input[name="answerOption"][value="c"]').check()
    page.locator("#answerButton").click()
    expect(page.locator("#feedbackHeading")).to_have_text("Đúng với bài này")
    page.locator("#nextButton").click()
    expect(page.locator("#lessonBadge")).to_have_text("Tình huống 3 / 3")
    page.locator("#solutionButton").click()
    expect(page.locator("#solutionBody")).to_contain_text("[LOUD]")
    page.locator("#nextButton").click()
    expect(page.locator("#summaryCard")).to_be_visible()
    expect(page.locator("#independentSuccesses")).to_have_text("1")
    expect(page.locator("#independentFailures")).to_have_text("1")
    expect(page.locator("#assistedSuccesses")).to_have_text("1")
    result = context.request.get(base + "/learn/api/session").json()["session"]
    assert result["summary"]["answered_count"] == 2  # Revealing is not an answer.
    with page.expect_download() as download:
        page.locator("#exportButton").click()
    assert download.value.suggested_filename.endswith(".json")
    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("#deleteButton").click()
    expect(page.locator("#startButton")).to_be_enabled()
    expect(page.locator("#welcomeCard")).to_be_visible()
    assert context.request.get(base + "/learn/api/session").json()["session"] is None


def test_mobile_layout_and_keyboard_answer(live):
    page, _, base, _ = live
    page.set_viewport_size({"width": 390, "height": 844})
    open_lesson(page, base)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.locator('input[name="answerOption"][value="b"]').focus()
    page.keyboard.press("Space")
    expect(page.locator('input[name="answerOption"][value="b"]')).to_be_checked()
    page.locator("#answerButton").press("Enter")
    expect(page.locator("#feedbackHeading")).to_have_text("Đúng với bài này")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    feedback_bounds = page.locator("#feedbackHeading").bounding_box()
    assert feedback_bounds["y"] < 844 and feedback_bounds["y"] + feedback_bounds["height"] > 0
    page.screenshot(path=str(ARTIFACTS / "mobile-feedback.png"), full_page=True)


def test_lost_response_retry_does_not_double_record_or_discard_draft(live):
    page, context, base, _ = live
    open_lesson(page, base)
    page.locator("#reflectionDetails summary").click()
    page.locator("#reflectionInput").fill("Bản nháp phải còn khi mất phản hồi.")
    sent = []

    def lose_first_response(route):
        sent.append(route.request.post_data)
        if len(sent) == 1:
            route.fetch()  # The server commits, but the response is lost.
            route.abort()
        else:
            route.continue_()

    page.route("**/learn/api/sessions/*/actions", lose_first_response)
    page.locator("#hintButton").click()
    expect(page.locator("#retryButton")).to_be_visible()
    expect(page.locator("#reflectionInput")).to_have_value("Bản nháp phải còn khi mất phản hồi.")
    page.locator("#retryButton").click()
    expect(page.locator("#hintsCard")).to_be_visible()
    assert len(sent) == 2 and sent[0] == sent[1]
    current = context.request.get(base + "/learn/api/session").json()["session"]
    assert current["revision"] == 1 and current["item"]["hint_count"] == 1
    expect(page.locator("#reflectionInput")).to_have_value("Bản nháp phải còn khi mất phản hồi.")
