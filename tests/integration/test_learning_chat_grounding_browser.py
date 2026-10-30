"""Lecture-scoped chat through Chromium with isolated files and scripted models."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import uuid

import pytest
from playwright.sync_api import expect

from core.learning.material_library import MaterialLibrary
from tests.integration.test_learning_chat_browser import chat_live, open_chat, send
from tests.integration.test_learning_materials_browser import browser, document, diagram_image


ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-chat-grounding-browser"
SOURCE = 'Inheritance lets Cat extend Animal. <img src=x onerror="window.__sourceXSS=true">'


class GroundedResponder:
    def __init__(self):
        self.calls = []
        self.reply = "Cat inherits from Animal [S1]. Another claim [S99]."

    def public_config(self):
        return {"available": True, "provider": "test", "model": "scripted-chat-fixture",
                "reason": "", "grounding": "general"}

    def respond(self, messages, *, grounding=None):
        self.calls.append({"messages": copy.deepcopy(messages), "grounding": copy.deepcopy(grounding)})
        return self.reply


@pytest.fixture
def grounded_live(chat_live, tmp_path, monkeypatch):
    live = chat_live
    root = tmp_path / "materials"
    monkeypatch.setitem(live.state.app.config, "TARGETED_SUBJECT_ROOT", root)
    live.responder = GroundedResponder()
    monkeypatch.setitem(live.state.app.config, "LEARNING_CHAT_RESPONDER", live.responder)
    open_chat(live.page, live.base)
    cookie = next(item["value"] for item in live.context.cookies() if item["name"] == "cattus_learner")
    owner = hashlib.sha256(("cattus-learning-v1:" + cookie).encode("ascii")).hexdigest()
    library = MaterialLibrary(root)
    live.first, _ = library.import_files(owner, uuid.uuid4().hex, "Java · Inheritance",
                                          [("inheritance.docx", document(SOURCE))])
    live.second, _ = library.import_files(owner, uuid.uuid4().hex, "Operating systems",
                                           [("processes.docx", document("A process has its own address space."))])
    live.library, live.owner = library, owner
    live.page.locator("#reloadChatButton").click()
    expect(live.page.locator("#chatCollection option")).to_have_count(3)
    expect(live.page.locator("#chatCollection")).to_be_enabled()
    return live


def test_material_selection_sources_reload_and_fixed_scope(grounded_live):
    live, page = grounded_live, grounded_live.page
    page.locator("#chatCollection").select_option(live.first["id"])
    first = send(page, "Explain inheritance")
    assert first["collection"]["id"] == live.first["id"]
    expect(page.locator("#chatScopeBadge")).to_have_text("Bài giảng · Java · Inheritance")
    expect(page.locator(".chat-source-card")).to_have_count(1)
    expect(page.locator(".source-card-badge")).to_have_text("AI có trích dẫn")
    page.locator(".chat-source-card summary").click()
    expect(page.locator(".source-excerpt")).to_have_text(SOURCE)
    expect(page.locator(".chat-evidence")).to_contain_text("mã nguồn không hợp lệ")
    expect(page.locator("#chatMessages img, #chatMessages script, #chatMessages a")).to_have_count(0)
    assert page.evaluate("typeof window.__sourceXSS") == "undefined"
    assert live.responder.calls[-1]["grounding"]["collection"]["id"] == live.first["id"]

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "chat-sources-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "chat-sources-mobile.png"), full_page=True)
    page.reload()
    expect(page.locator("#chatScopeBadge")).to_have_text("Bài giảng · Java · Inheritance")
    expect(page.locator(".chat-source-card")).to_have_count(1)

    # Choosing a different source only affects a new conversation.
    page.locator("#chatCollection").select_option(live.second["id"])
    again = send(page, "Explain inheritance further")
    assert again["id"] == first["id"] and again["collection"]["id"] == live.first["id"]
    assert live.responder.calls[-1]["grounding"]["collection"]["id"] == live.first["id"]
    page.locator("#chatCollectionStart").click()
    expect(page.locator("#chatScopeBadge")).to_have_text("Bài giảng · Operating systems")
    expect(page.locator(".chat-source-card")).to_have_count(0)
    second = send(page, "Explain process address space")
    assert second["id"] != first["id"]
    assert live.responder.calls[-1]["grounding"]["collection"]["id"] == live.second["id"]
    assert live.responder.calls[-1]["messages"] == [{"role": "user", "content": "Explain process address space"}]


def test_no_match_and_missing_citation_are_explicit(grounded_live):
    live, page = grounded_live, grounded_live.page
    page.locator("#chatCollection").select_option(live.first["id"])
    response = send(page, "photosynthesis chloroplast")
    assert response["messages"][-1]["evidence"]["status"] == "no_match"
    expect(page.locator(".chat-evidence")).to_contain_text("Chưa tìm thấy đoạn phù hợp")
    expect(page.locator(".chat-source-card")).to_have_count(0)
    assert live.responder.calls == []
    live.responder.reply = "This is an explanation without a source marker."
    send(page, "Summarize this lecture")
    expect(page.locator(".chat-evidence").last).to_contain_text("chưa bao quát toàn bộ tài liệu")
    expect(page.locator(".chat-evidence").last).to_contain_text("AI chưa chỉ rõ đoạn nào")
    expect(page.locator(".source-card-badge")).to_have_text("Đoạn đã cung cấp")


def test_lost_creation_ack_preserves_selected_collection(grounded_live):
    live, page = grounded_live, grounded_live.page
    page.locator("#chatCollection").select_option(live.first["id"])
    payloads = []

    def lose_first_ack(route):
        if route.request.method != "POST":
            route.continue_()
            return
        payloads.append(route.request.post_data_json)
        if len(payloads) == 1:
            result = route.fetch()
            assert result.status == 201
            route.abort()
        else:
            route.continue_()

    page.route("**/api/chats", lose_first_ack)
    page.locator("#chatCollectionStart").click()
    expect(page.locator("#chatNotice")).to_be_visible()
    expect(page.locator("#chatCollection")).to_be_disabled()
    expect(page.locator("#chatCollectionStart")).to_be_enabled()
    page.locator("#chatCollectionStart").click()
    expect(page.locator("#chatScopeBadge")).to_have_text("Bài giảng · Java · Inheritance")
    assert payloads[0] == payloads[1]
    assert payloads[0]["collection_id"] == live.first["id"]
    assert len(live.context.request.get(live.base + "/learn/api/chats").json()["conversations"]) == 1
    assert live.responder.calls == []


def test_image_note_shows_its_origin_and_version(grounded_live):
    live, page = grounded_live, grounded_live.page
    image, _ = live.library.import_files(live.owner, uuid.uuid4().hex, "My inheritance diagram",
                                           [("inheritance.png", diagram_image())])
    digest = image["sources"][0]["source_id"][7:]
    live.library.describe_image(live.owner, image["id"], digest,
                                "Inheritance diagram: Cat extends Animal.", 0)
    page.locator("#reloadChatButton").click()
    expect(page.locator("#chatCollection option")).to_have_count(4)
    page.locator("#chatCollection").select_option(image["id"])
    send(page, "Explain inheritance diagram")
    page.locator(".chat-source-card summary").click()
    expect(page.locator(".chat-source-card")).to_contain_text("Ghi chú ảnh do bạn viết")
    expect(page.locator(".chat-source-card")).to_contain_text("Phiên bản ghi chú: 1")
    expect(page.locator(".source-excerpt")).to_have_text("Inheritance diagram: Cat extends Animal.")


def test_unconfirmed_new_material_chat_never_sends_draft_to_old_general_chat(grounded_live):
    live, page = grounded_live, grounded_live.page
    general = send(page, "Hello")
    assert live.responder.calls[-1]["grounding"] is None
    page.locator("#chatCollection").select_option(live.first["id"])
    still_general = send(page, "A general question")
    assert still_general["id"] == general["id"]
    assert still_general["collection"] is None
    assert live.responder.calls[-1]["grounding"] is None
    payloads = []

    def lose_first_ack(route):
        if route.request.method != "POST":
            route.continue_()
            return
        payloads.append(route.request.post_data_json)
        if len(payloads) == 1:
            result = route.fetch()
            assert result.status == 201
            route.abort()
        else:
            route.continue_()

    page.route("**/api/chats", lose_first_ack)
    page.locator("#chatCollectionStart").click()
    expect(page.locator("#chatNotice")).to_be_visible()
    expect(page.locator("#chatCollection")).to_be_disabled()
    material = send(page, "Explain inheritance")
    assert payloads[0] == payloads[1]
    assert material["id"] != general["id"]
    assert material["collection"]["id"] == live.first["id"]
    old = live.context.request.get(live.base + "/learn/api/chats/" + general["id"]).json()["conversation"]
    assert len(old["messages"]) == 4
    assert live.responder.calls[-1]["grounding"]["collection"]["id"] == live.first["id"]
