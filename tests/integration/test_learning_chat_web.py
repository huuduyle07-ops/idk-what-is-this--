"""General chat through owner/auth/CSRF gates, using an isolated scripted model."""
from __future__ import annotations

import copy
import uuid

import pytest

from tests.integration.test_learning_materials_web import BASE, assert_error, page
from tests.test_auth_web1 import configure_offline_web

API = "/learn/api/chats"


class Responder:
    def __init__(self):
        self.calls = []
        self.available = True
        self.error = None

    def public_config(self):
        return {"available": self.available, "provider": "test", "model": "scripted",
                "reason": "Cần cấu hình model." if not self.available else "", "grounding": "general"}

    def respond(self, messages):
        self.calls.append(copy.deepcopy(messages))
        if self.error:
            raise self.error
        return "Đây là ví dụ, chưa chạy code.\n\n```java\nAnimal pet = new Cat();\n```"


@pytest.fixture
def chat(tmp_path, monkeypatch):
    state = configure_offline_web(tmp_path, monkeypatch)
    state.responder = Responder()
    state.chat_path = tmp_path / "chats.sqlite3"
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_STORE_PATH", state.chat_path)
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", state.responder)
    yield state
    assert state.calls == []  # No coding/tool/retrieval transport.
    assert not list(state.repo.iterdir())


def create(client, csrf, request_id=None):
    return client.post(API, base_url=BASE, json={"request_id": request_id or uuid.uuid4().hex},
                       headers={"Origin": BASE, "X-CSRF-Token": csrf})


def send(client, csrf, cid, text="Giải thích kế thừa.", *, revision=0, request_id=None):
    return client.post(f"{API}/{cid}/messages", base_url=BASE,
                       json={"text": text, "expected_revision": revision, "request_id": request_id or uuid.uuid4().hex},
                       headers={"Origin": BASE, "X-CSRF-Token": csrf})


def opened(state):
    client = state.app.test_client()
    csrf = page(client, "/learn/chat")
    response = create(client, csrf)
    assert response.status_code == 201
    return client, csrf, response.get_json()["conversation"]


def test_open_config_and_list_do_not_call_model_or_create_database(chat):
    client = chat.app.test_client()
    page(client, "/learn/chat")
    config = client.get("/learn/api/chat/config", base_url=BASE)
    assert config.get_json()["config"]["grounding"] == "general"
    assert config.headers["Cache-Control"] == "no-store"
    assert config.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get(API, base_url=BASE).get_json() == {"ok": True, "conversations": []}
    assert chat.responder.calls == [] and not chat.chat_path.exists()


def test_chat_round_trip_keeps_context_and_exact_retries_spend_one_call(chat):
    client, csrf, conversation = opened(chat)
    cid = conversation["id"]
    rid = uuid.uuid4().hex
    first = send(client, csrf, cid, request_id=rid)
    assert first.status_code == 200
    first_view = first.get_json()["conversation"]
    assert first_view["grounding"] == "general" and first_view["revision"] == 2
    assert first_view["pending"] is None and first_view["last_error"] is None
    assert [item["role"] for item in first_view["messages"]] == ["user", "assistant"]
    assert chat.responder.calls == [[{"role": "user", "content": "Giải thích kế thừa."}]]
    assert send(client, csrf, cid, request_id=rid).get_json() == first.get_json()
    assert len(chat.responder.calls) == 1
    second = send(client, csrf, cid, "Cho ví dụ khác.", revision=2)
    assert second.status_code == 200
    assert [item["role"] for item in chat.responder.calls[-1]] == ["user", "assistant", "user"]
    assert chat.responder.calls[-1][1]["content"] == first_view["messages"][1]["content"]
    assert client.get(f"{API}/{cid}", base_url=BASE).get_json() == second.get_json()
    assert len(client.get(API, base_url=BASE).get_json()["conversations"]) == 1


def test_chat_create_is_idempotent_and_new_chat_has_no_old_context(chat):
    client = chat.app.test_client()
    csrf = page(client, "/learn/chat")
    rid = uuid.uuid4().hex
    first = create(client, csrf, rid).get_json()["conversation"]
    assert create(client, csrf, rid).get_json()["conversation"] == first
    assert send(client, csrf, first["id"], "old private text").status_code == 200
    second = create(client, csrf).get_json()["conversation"]
    assert send(client, csrf, second["id"], "new question").status_code == 200
    assert chat.responder.calls[-1] == [{"role": "user", "content": "new question"}]


def test_chat_owner_and_auth_boundaries(chat, monkeypatch):
    client, csrf, conversation = opened(chat)
    cid = conversation["id"]
    other = chat.app.test_client()
    other_csrf = page(other, "/learn/chat")
    assert client.get(API, base_url=BASE).get_json()["conversations"]
    assert other.get(API, base_url=BASE).get_json()["conversations"] == []
    assert_error(other.get(f"{API}/{cid}", base_url=BASE), 404, "conversation_not_found")
    assert_error(send(other, other_csrf, cid), 404, "conversation_not_found")
    assert_error(other.delete(f"{API}/{cid}", base_url=BASE, headers={"Origin": BASE, "X-CSRF-Token": other_csrf}), 404)
    assert_error(chat.app.test_client().get(API, base_url=BASE), 401, "learner_required")
    monkeypatch.setenv("WEB_AUTH_TOKEN", "chat-test-token")
    assert_error(client.get(f"{API}/{cid}", base_url=BASE), 401, "auth_required")
    assert send(client, csrf, cid).status_code in {401, 403}
    assert chat.responder.calls == []


def test_chat_origin_csrf_and_stale_revision_reject_before_model(chat):
    client, csrf, conversation = opened(chat)
    cid = conversation["id"]
    body = {"request_id": uuid.uuid4().hex, "text": "blocked", "expected_revision": 0}
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.post(f"{API}/{cid}/messages", base_url=BASE, json=body, headers=headers), 403)
    assert chat.responder.calls == []
    assert send(client, csrf, cid).status_code == 200
    assert_error(send(client, csrf, cid, "stale tab", revision=0), 409, "chat_conflict")
    assert len(chat.responder.calls) == 1
    assert len(client.get(f"{API}/{cid}", base_url=BASE).get_json()["conversation"]["messages"]) == 2


def test_unconfigured_model_preserves_draft_without_reserving_a_turn(chat):
    client, csrf, conversation = opened(chat)
    chat.responder.available = False
    assert_error(send(client, csrf, conversation["id"]), 503, "chat_not_configured")
    assert client.get(f"{API}/{conversation['id']}", base_url=BASE).get_json()["conversation"] == conversation
    assert chat.responder.calls == []


def test_provider_failure_is_saved_sanitized_and_exact_retry_does_not_call_again(chat):
    client, csrf, conversation = opened(chat)
    cid, rid = conversation["id"], uuid.uuid4().hex
    chat.responder.error = RuntimeError("secret-key=do-not-show /private/file question body")
    failure = send(client, csrf, cid, request_id=rid)
    assert_error(failure, 502, "chat_provider_error")
    assert "do-not-show" not in failure.get_data(as_text=True)
    view = client.get(f"{API}/{cid}", base_url=BASE).get_json()["conversation"]
    assert view["messages"][0]["status"] == "failed" and view["last_error"]["code"] == "chat_provider_error"
    assert send(client, csrf, cid, request_id=rid).get_json()["conversation"] == view
    assert len(chat.responder.calls) == 1
    chat.responder.error = None
    assert send(client, csrf, cid, "Try a new turn", revision=view["revision"]).status_code == 200
    assert chat.responder.calls[-1] == [{"role": "user", "content": "Try a new turn"}]


def test_pending_retry_returns_status_without_second_model_call(chat):
    client, csrf, conversation = opened(chat)
    cid, rid = conversation["id"], uuid.uuid4().hex
    original = chat.responder.respond

    def during_generation(messages):
        pending = client.get(f"{API}/{cid}", base_url=BASE).get_json()["conversation"]
        assert pending["pending"]["request_id"] == rid
        replay = send(client, csrf, cid, request_id=rid)
        assert replay.status_code == 202
        assert replay.get_json()["conversation"] == pending
        assert_error(client.delete(f"{API}/{cid}", base_url=BASE,
                                   headers={"Origin": BASE, "X-CSRF-Token": csrf}), 409, "chat_busy")
        return original(messages)

    chat.responder.respond = during_generation
    assert send(client, csrf, cid, request_id=rid).status_code == 200
    assert len(chat.responder.calls) == 1


@pytest.mark.parametrize("extra", [{"role": "system"}, {"sources": ["private.pdf"]}, {"tools": ["shell"]}])
def test_browser_cannot_supply_model_roles_sources_or_tools(chat, extra):
    client, csrf, conversation = opened(chat)
    body = {"request_id": uuid.uuid4().hex, "text": "a", "expected_revision": 0, **extra}
    assert_error(client.post(f"{API}/{conversation['id']}/messages", base_url=BASE, json=body,
                            headers={"Origin": BASE, "X-CSRF-Token": csrf}), 400)
    assert chat.responder.calls == []


@pytest.mark.parametrize("text", ["", "a" * 8001, "\ud800", 42])
def test_invalid_messages_do_not_invoke_model(chat, text):
    client, csrf, conversation = opened(chat)
    assert_error(send(client, csrf, conversation["id"], text), 400)
    assert chat.responder.calls == []


def test_unicode_message_budget_and_oversized_body(chat):
    client, csrf, conversation = opened(chat)
    assert send(client, csrf, conversation["id"], "ế" * 8000).status_code == 200
    assert_error(send(client, csrf, conversation["id"], "x" * 52000, revision=2), 413)
    assert len(chat.responder.calls) == 1


def test_delete_removes_history_without_touching_other_conversation(chat):
    client, csrf, first = opened(chat)
    send(client, csrf, first["id"])
    second = create(client, csrf).get_json()["conversation"]
    removed = client.delete(f"{API}/{first['id']}", base_url=BASE,
                            headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert removed.status_code == 200
    assert_error(client.get(f"{API}/{first['id']}", base_url=BASE), 404)
    assert client.get(f"{API}/{second['id']}", base_url=BASE).get_json()["conversation"] == second
