"""Chat through Chromium; scripted replies stay inside isolated test fixtures."""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect

from tests.integration.test_learning_materials_browser import browser
from tests.test_auth_web1 import configure_offline_web
from tests.test_auth_web1_browser import _Listener


API = "/learn/api/chats"
ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-chat-browser"
RICH_REPLY = """## Hai cách nhìn một đối tượng

Kiểu biến giúp kiểm tra lời gọi; lớp của đối tượng quyết định method bị override khi chạy.

```java
Animal pet = new Cat();
pet.speak();
```

| Thời điểm | Xem kiểu nào? |
| --- | --- |
| Biên dịch | Kiểu khai báo |
| Chạy | Lớp đối tượng |
"""
HOSTILE_REPLY = '<img src=x onerror="window.__chatXSS=true">\n\n<script>window.__chatXSS=true</script>'


class ScriptedResponder:
    provider = "test"
    model = "scripted-chat-fixture"

    def __init__(self):
        self.calls = []
        self.replies = [RICH_REPLY]

    def public_config(self):
        return {"available": True, "provider": self.provider, "model": self.model,
                "reason": "", "grounding": "general"}

    def respond(self, messages):
        self.calls.append(copy.deepcopy(messages))
        reply = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def chat_live(tmp_path, monkeypatch, browser):
    state = configure_offline_web(tmp_path, monkeypatch, allow_loopback=True)
    responder = ScriptedResponder()
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_STORE_PATH", tmp_path / "chat.sqlite3")
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", responder)
    listener = _Listener(state.app)
    base = f"http://127.0.0.1:{listener.port}"
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
    page = context.new_page()
    errors = []
    context.on("page", lambda opened: opened.on("pageerror", lambda error: errors.append(str(error))))
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        yield SimpleNamespace(page=page, context=context, base=base, state=state, responder=responder)
        assert errors == []
        assert state.calls == []
        assert not list(state.repo.iterdir())
    finally:
        context.close()
        listener.close()


def open_chat(page, base):
    page.goto(base + "/learn/chat")
    expect(page.locator("#configStatus")).to_contain_text("scripted-chat-fixture")
    expect(page.locator("#chatInput")).to_be_enabled()


def send_response(page):
    return page.expect_response(lambda response: "/api/chats/" in response.url
                                and response.url.endswith("/messages")
                                and response.request.method == "POST")


def send(page, text):
    expect(page.locator("#chatInput")).to_be_enabled()
    page.locator("#chatInput").fill(text)
    with send_response(page) as sent:
        page.locator("#sendChatButton").click()
    assert sent.value.status == 200
    expect(page.locator("#chatInput")).to_have_value("")
    return sent.value.json()["conversation"]


def conversations(live):
    response = live.context.request.get(live.base + API)
    assert response.status == 200
    return response.json()["conversations"]


def conversation(live, cid):
    response = live.context.request.get(live.base + API + "/" + cid)
    assert response.status == 200
    return response.json()["conversation"]


def test_chat_safe_rich_reply_history_draft_navigation_and_explicit_delete(chat_live):
    live = chat_live
    page = live.page
    live.responder.replies = [RICH_REPLY, HOSTILE_REPLY]
    open_chat(page, live.base)
    assert live.responder.calls == []
    question = "Tại sao kiểu biến và lớp đối tượng khác nhau?"
    first = send(page, question)
    expect(page.locator('#chatMessages [data-role="user"]')).to_have_count(1)
    expect(page.locator('#chatMessages [data-role="assistant"]')).to_have_count(1)
    expect(page.locator("#chatMessages pre code")).to_have_text("Animal pet = new Cat();\npet.speak();")
    expect(page.locator("#chatMessages .copy-code")).to_have_count(1)
    expect(page.locator("#chatMessages table")).to_have_count(1)
    expect(page.locator("#chatMessages table")).to_contain_text("Biên dịch")
    assert first["grounding"] == "general"
    assert live.responder.calls[0] == [{"role": "user", "content": question}]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "chat-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#chatInput")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "chat-mobile.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})

    send(page, "Giải thích kỹ hơn bằng ví dụ.")
    for literal in HOSTILE_REPLY.split("\n\n"):
        expect(page.locator("#chatMessages")).to_contain_text(literal)
    expect(page.locator("#chatMessages img, #chatMessages script")).to_have_count(0)
    assert page.evaluate("typeof window.__chatXSS") == "undefined"
    assert [message["role"] for message in live.responder.calls[1]] == ["user", "assistant", "user"]
    assert live.responder.calls[1][1]["content"] == RICH_REPLY
    assert len(conversation(live, first["id"])["messages"]) == 4
    page.reload()
    expect(page.locator("#chatMessages")).to_contain_text(question)
    for literal in HOSTILE_REPLY.split("\n\n"):
        expect(page.locator("#chatMessages")).to_contain_text(literal)
    assert len(live.responder.calls) == 2

    draft = "Câu hỏi tôi chưa gửi"
    page.locator("#chatInput").fill(draft)
    page.locator("#newChatButton").click()
    expect(page.locator("#chatInput")).to_have_value(draft)
    assert len(conversations(live)) == 1
    page.locator("#discardChatDraftButton").click()
    expect(page.locator("#chatInput")).to_have_value("")
    page.locator("#newChatButton").click()
    expect(page.locator('#chatMessages [data-role="assistant"]')).to_have_count(0)
    second = send(page, "Một cuộc trò chuyện mới")
    assert second["id"] != first["id"]
    assert live.responder.calls[-1] == [{"role": "user", "content": "Một cuộc trò chuyện mới"}]
    expect(page.locator("#chatConversations button")).to_have_count(2)
    page.locator("#chatConversations button").filter(has_text=question).click()
    expect(page.locator("#chatMessages")).to_contain_text(question)
    expect(page.locator("#chatMessages")).not_to_contain_text("Một cuộc trò chuyện mới")
    page.locator("#deleteChatButton").click()
    expect(page.locator("#deleteChatConfirm")).to_be_visible()
    assert len(conversations(live)) == 2  # Opening confirmation is not deletion.
    page.locator("#cancelDeleteChatButton").click()
    assert len(conversations(live)) == 2
    page.locator("#deleteChatButton").click()
    with page.expect_response(lambda response: response.request.method == "DELETE") as removed:
        page.locator("#confirmDeleteChatButton").click()
    assert removed.value.status == 200
    assert [row["id"] for row in conversations(live)] == [second["id"]]
    assert len(live.responder.calls) == 3


def test_lost_chat_reply_retries_same_turn_without_second_model_call(chat_live):
    live = chat_live
    page = live.page
    open_chat(page, live.base)
    submissions = []

    def lose_acknowledgment(route):
        submissions.append(route.request.post_data_json)
        if len(submissions) == 1:
            response = route.fetch()
            assert response.status == 200  # Reply and user message are already durable.
            route.abort()
        else:
            route.continue_()

    page.route("**/api/chats/*/messages", lose_acknowledgment)
    question = "Cho tôi ví dụ về kế thừa."
    page.locator("#chatInput").fill(question)
    page.locator("#sendChatButton").click()
    expect(page.locator("#retryChatButton")).to_be_visible()
    expect(page.locator("#chatInput")).to_have_value(question)
    stored = conversation(live, conversations(live)[0]["id"])
    assert len(stored["messages"]) == 2 and stored["pending"] is None
    assert len(live.responder.calls) == 1
    with send_response(page) as retried:
        page.locator("#retryChatButton").click()
    assert retried.value.status == 200
    expect(page.locator("#chatInput")).to_have_value("")
    expect(page.locator('#chatMessages [data-role="assistant"]')).to_have_count(1)
    assert len(submissions) == 2 and submissions[0] == submissions[1]
    assert conversation(live, stored["id"]) == stored
    assert len(live.responder.calls) == 1


def test_two_tabs_keep_stale_draft_until_explicit_resend(chat_live):
    live = chat_live
    page = live.page
    open_chat(page, live.base)
    first = send(page, "Tôi muốn hiểu đa hình.")
    peer = live.context.new_page()
    open_chat(peer, live.base)
    expect(peer.locator("#chatMessages")).to_contain_text("Tôi muốn hiểu đa hình.")
    draft = "Kiểu nào quyết định method được gọi?"
    page.locator("#chatInput").fill(draft)
    send(peer, "Lấy thêm ví dụ về method overriding.")
    with send_response(page) as stale:
        page.locator("#sendChatButton").click()
    assert stale.value.status == 409
    expect(page.locator("#chatInput")).to_have_value(draft)
    expect(page.locator("#chatMessages")).to_contain_text("Lấy thêm ví dụ về method overriding.")
    assert len(live.responder.calls) == 2
    assert all(message["content"] != draft for message in conversation(live, first["id"])["messages"])
    with send_response(page) as reviewed:
        page.locator("#sendChatButton").click()
    assert reviewed.value.status == 200
    expect(page.locator("#chatInput")).to_have_value("")
    assert len(live.responder.calls) == 3
    assert live.responder.calls[-1][-1] == {"role": "user", "content": draft}
    assert len(conversation(live, first["id"])["messages"]) == 6
    peer.close()


def test_provider_failure_preserves_question_until_explicit_new_turn(chat_live):
    live = chat_live
    page = live.page
    live.responder.replies = [RuntimeError("synthetic private transport failure"), RICH_REPLY]
    open_chat(page, live.base)
    submissions = []
    page.on("request", lambda request: submissions.append(request.post_data_json)
            if request.method == "POST" and request.url.endswith("/messages") else None)
    question = "Giúp tôi hiểu cách gọi method."
    page.locator("#chatInput").fill(question)
    with send_response(page) as failed:
        page.locator("#sendChatButton").click()
    assert failed.value.status == 502
    expect(page.locator("#chatInput")).to_have_value(question)
    expect(page.locator("#chatInput")).to_be_enabled()
    expect(page.locator('#chatMessages [data-role="assistant"]')).to_have_count(0)
    expect(page.locator("#chatMessages")).not_to_contain_text("synthetic private transport failure")
    assert len(live.responder.calls) == 1
    saved = conversation(live, conversations(live)[0]["id"])
    assert saved["pending"] is None and saved["last_error"]["code"] == "chat_provider_error"
    assert [item["role"] for item in saved["messages"]] == ["user"]
    page.locator("#reloadChatButton").click()
    expect(page.locator("#chatInput")).to_have_value(question)
    expect(page.locator("#sendChatButton")).to_be_enabled()
    with send_response(page) as retried:
        page.locator("#sendChatButton").click()
    assert retried.value.status == 200
    expect(page.locator('#chatMessages [data-role="assistant"]')).to_have_count(1)
    expect(page.locator("#chatInput")).to_have_value("")
    assert len(live.responder.calls) == 2 and len(submissions) == 2
    assert submissions[0]["request_id"] != submissions[1]["request_id"]
    assert live.responder.calls[1] == [{"role": "user", "content": question}]


def test_lost_failure_response_keeps_draft_when_replay_reads_saved_error(chat_live):
    live = chat_live
    page = live.page
    live.responder.replies = [RuntimeError("private fixture error"), RICH_REPLY]
    open_chat(page, live.base)
    submissions = []

    def lose_failure(route):
        submissions.append(route.request.post_data_json)
        if len(submissions) == 1:
            response = route.fetch()
            assert response.status == 502
            route.abort()
        else:
            route.continue_()

    page.route("**/api/chats/*/messages", lose_failure)
    question = "Giải thích giúp tôi một ví dụ nhỏ."
    page.locator("#chatInput").fill(question)
    page.locator("#sendChatButton").click()
    expect(page.locator("#retryChatButton")).to_be_visible()
    with send_response(page) as replay:
        page.locator("#retryChatButton").click()
    assert replay.value.status == 200
    expect(page.locator("#chatInput")).to_have_value(question)
    expect(page.locator("#sendChatButton")).to_be_enabled()
    expect(page.locator("#chatMessages")).to_contain_text("Lượt này chưa nhận được câu trả lời")
    assert len(live.responder.calls) == 1 and submissions[0] == submissions[1]
    with send_response(page) as new_turn:
        page.locator("#sendChatButton").click()
    assert new_turn.value.status == 200
    expect(page.locator("#chatInput")).to_have_value("")
    assert len(live.responder.calls) == 2
    assert submissions[2]["request_id"] != submissions[0]["request_id"]
