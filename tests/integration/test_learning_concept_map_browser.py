"""Owner-scoped concept exploration in Chromium, with no model calls on browse."""
from pathlib import Path
import json
import uuid

import pytest
from playwright.sync_api import expect

from core.learning.knowledge_graph import LearningKnowledgeGraph
from tests.integration.test_learning_chat_browser import chat_live, send_response
from tests.integration.test_learning_chat_grounding_browser import grounded_live
from tests.integration.test_learning_materials_browser import browser, document

ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-concept-map-browser"
HOSTILE = '<img src=x onerror="window.__mapXSS=true">'


@pytest.fixture
def mapped_live(grounded_live):
    live = grounded_live
    live.os, _ = live.library.import_files(live.owner, uuid.uuid4().hex, "Operating systems", [("os.docx", document(
        "A semaphore coordinates access between concurrent tasks.",
        "An ISR handles an interrupt. " + HOSTILE,
        "This passage discusses Semaphore and ISR together."))])
    graph = LearningKnowledgeGraph(live.library)
    for unit, labels in zip(live.os["units"], (["Semaphore", "Synchronization"], ["ISR", HOSTILE], ["Semaphore", "ISR"])):
        graph.set_concepts(live.owner, live.os["id"], unit["unit_id"], labels, 0)
    live.page.locator("#reloadChatButton").click()
    expect(live.page.locator("#chatCollection option")).to_have_count(4)
    return live


def choose(live, cid):
    live.page.locator("#chatCollection").select_option(cid)
    with live.page.expect_response(lambda response: response.url.endswith("/learn/api/chats") and response.request.method == "POST") as created:
        live.page.locator("#chatCollectionStart").click()
    assert created.value.status == 201
    collection = created.value.json()["conversation"]["collection"]
    assert collection["id"] == cid
    expect(live.page.locator("#chatScopeBadge")).to_have_text("Bài giảng · " + collection["title"])
    expect(live.page.locator("#chatCollection")).to_be_enabled()
    expect(live.page.locator("#chatConceptMap")).to_be_visible()


def open_map(live):
    live.page.locator("#chatConceptMap > details > summary").click()
    expect(live.page.get_by_role("button", name="Concept: Semaphore", exact=True)).to_be_visible()


def test_map_lazy_load_selection_filter_draft_preservation_and_keyboard(mapped_live):
    live, page = mapped_live, mapped_live.page
    requests = []
    page.on("request", lambda request: requests.append(request.url) if request.url.endswith("/map") else None)
    choose(live, live.os["id"])
    assert requests == [] and live.responder.calls == []
    open_map(live)
    assert len(requests) == 1 and live.responder.calls == []
    semaphore = page.get_by_role("button", name="Concept: Semaphore", exact=True)
    semaphore.focus(); page.keyboard.press("Enter")
    expect(semaphore).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".concept-map-detail")).to_contain_text("Shares a source passage with")
    expect(page.locator(".map-shared")).to_have_count(2)
    expect(page.get_by_role("button", name="Concept: ISR", exact=True)).to_have_class("concept-map-node map-concept map-connected")
    page.locator(".concept-map-ask").click()
    expect(page.locator("#chatInput")).to_have_value("Explain Semaphore.")
    assert live.responder.calls == []
    page.get_by_role("button", name="Concept: ISR", exact=True).click()
    page.locator(".concept-map-ask").click()
    expect(page.locator("#chatInput")).to_have_value("Explain Semaphore.")
    expect(page.locator("#chatNotice")).to_contain_text("Bản nháp đang có nội dung")
    page.get_by_role("searchbox", name="Find a concept or file").fill("Synchronization")
    expect(page.locator('.concept-map-node[data-node-type="concept"]')).to_have_count(1)
    page.get_by_role("searchbox", name="Find a concept or file").fill("")
    page.get_by_role("button", name="Concept: Semaphore", exact=True).click()
    page.get_by_role("checkbox", name="Related only").check()
    expect(page.locator('.concept-map-node[data-node-type="concept"]')).to_have_count(3)
    expect(page.locator('.concept-map-node[data-node-type="source"]')).to_have_count(0)
    assert live.responder.calls == []


def test_map_source_text_is_inert_mobile_and_materials_link(mapped_live):
    live, page = mapped_live, mapped_live.page
    choose(live, live.os["id"]); open_map(live)
    page.get_by_role("button", name="Concept: ISR", exact=True).click()
    expect(page.locator(".concept-map-detail")).to_contain_text(HOSTILE)
    expect(page.locator("#chatConceptMap img, #chatConceptMap script")).to_have_count(0)
    assert page.evaluate("typeof window.__mapXSS") == "undefined"
    link = page.locator(".concept-map-source-link").first
    assert link.get_attribute("href") == "/learn/materials?collection=" + live.os["id"] + "&unit=" + live.os["units"][1]["unit_id"]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "concept-map-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "concept-map-mobile.png"), full_page=True)
    # A draft cannot be discarded by following a dynamically-created source link.
    page.locator("#chatInput").fill("Keep my draft")
    link.click()
    assert page.url.endswith("/learn/chat")
    expect(page.locator("#chatInput")).to_have_value("Keep my draft")


def test_map_empty_concepts_retry_and_collection_switch(mapped_live):
    live, page = mapped_live, mapped_live.page
    choose(live, live.first["id"])
    failed = []
    def fail_first(route):
        if not failed:
            failed.append(True); route.fulfill(status=503, content_type="application/json", body=json.dumps({"ok": False})); return
        route.continue_()
    page.route("**/api/materials/" + live.first["id"] + "/map", fail_first)
    page.locator("#chatConceptMap > details > summary").click()
    expect(page.locator(".concept-map-status")).to_contain_text("Chưa đọc được bản đồ")
    page.get_by_role("button", name="Refresh map", exact=True).click()
    expect(page.locator(".concept-map-detail")).to_contain_text("Chưa có nhãn khái niệm")
    expect(page.locator('.concept-map-node[data-node-type="source"]')).to_have_count(1)
    choose(live, live.os["id"])
    expect(page.locator("#chatConceptMap > details")).not_to_have_attribute("open", "")
    open_map(live)
    expect(page.locator(".concept-map-detail h3")).to_have_text("Operating systems")
    assert live.responder.calls == []
    page.locator("#chatCollection").select_option("")
    page.locator("#chatCollectionStart").click()
    expect(page.locator("#chatConceptMap")).to_be_hidden()
    expect(page.locator(".concept-map-node")).to_have_count(0)


def test_map_rejects_response_for_different_collection(mapped_live):
    live, page = mapped_live, mapped_live.page
    # A successful HTTP response cannot display a different collection's map.
    first_map = live.context.request.get(live.base + "/learn/api/materials/" + live.os["id"] + "/map").json()
    choose(live, live.first["id"])
    page.route("**/api/materials/" + live.first["id"] + "/map", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(first_map)))
    page.locator("#chatConceptMap > details > summary").click()
    expect(page.locator(".concept-map-status")).to_contain_text("Chưa đọc được bản đồ")
    expect(page.get_by_role("button", name="Concept: Semaphore", exact=True)).to_have_count(0)
    assert live.responder.calls == []


def test_map_discards_late_valid_response_after_navigation(mapped_live):
    live, page = mapped_live, mapped_live.page
    old_map = live.context.request.get(live.base + "/learn/api/materials/" + live.os["id"] + "/map").json()
    old_url = "/learn/api/materials/" + live.os["id"] + "/map"
    page.evaluate("""({url, payload}) => {
        const original = window.fetch.bind(window);
        window.fetch = (input, options) => {
            if (input === url) return new Promise((resolve) => {
                // Deliberately ignore abort: simulate a response completing
                // just as the user navigates to a different conversation.
                window.releaseOldMap = () => resolve(new Response(JSON.stringify(payload),
                    {status: 200, headers: {'Content-Type': 'application/json'}}));
            });
            return original(input, options);
        };
    }""", {"url": old_url, "payload": old_map})
    choose(live, live.os["id"])
    page.locator("#chatConceptMap > details > summary").click()
    page.wait_for_function("typeof window.releaseOldMap === 'function'")
    choose(live, live.first["id"])
    page.locator("#chatConceptMap > details > summary").click()
    expect(page.locator(".concept-map-detail h3")).to_have_text("Java · Inheritance")
    page.evaluate("window.releaseOldMap()")
    expect(page.locator(".concept-map-detail h3")).to_have_text("Java · Inheritance")
    expect(page.get_by_role("button", name="Concept: Semaphore", exact=True)).to_have_count(0)
    assert live.responder.calls == []


def test_map_ask_then_explicit_send_uses_linked_alias_source(mapped_live):
    live, page = mapped_live, mapped_live.page
    source_text = "An interrupt service routine handles a hardware interrupt and returns control after servicing the device."
    assert "ISR" not in source_text
    lecture, _ = live.library.import_files(live.owner, uuid.uuid4().hex, "Interrupts", [("interrupts.docx", document(source_text))])
    LearningKnowledgeGraph(live.library).set_concepts(live.owner, lecture["id"], lecture["units"][0]["unit_id"], ["ISR"], 0)
    page.locator("#reloadChatButton").click()
    expect(page.locator("#chatCollection option")).to_have_count(5)
    choose(live, lecture["id"])
    page.locator("#chatConceptMap > details > summary").click()
    page.get_by_role("button", name="Concept: ISR", exact=True).click()
    page.locator(".concept-map-ask").click()
    expect(page.locator("#chatInput")).to_have_value("Explain ISR.")
    assert live.responder.calls == []
    live.responder.reply = "An interrupt service routine handles a hardware interrupt. [S1]"
    with send_response(page) as response:
        page.locator("#sendChatButton").click()
    assert response.value.status == 200
    answer = response.value.json()["conversation"]["messages"][-1]
    assert answer["evidence"]["status"] == "matched"
    assert answer["evidence"]["selection"] == "concept_link"
    assert answer["evidence"]["sources"][0]["unit_id"] == lecture["units"][0]["unit_id"]
    assert answer["evidence"]["sources"][0]["text"] == source_text
    assert len(live.responder.calls) == 1
    expect(page.locator(".chat-source-card")).to_have_count(1)
    expect(page.locator(".chat-evidence")).to_contain_text("nhãn khái niệm bạn đã gắn")


def test_source_opens_exact_unit_in_new_tab_and_neighbor_keeps_keyboard_focus(mapped_live):
    live, page = mapped_live, mapped_live.page
    # Return to an older chat, then inspect a source. Opening Materials must not
    # replace this chat with the most recently-created chat on browser Back.
    choose(live, live.os["id"])
    choose(live, live.first["id"])
    page.locator("#chatConversations button").filter(has_text="Operating systems").click()
    open_map(live)
    page.get_by_role("button", name="Concept: Semaphore", exact=True).click()
    neighbor = page.locator(".concept-map-neighbors").get_by_role("button", name="ISR", exact=True)
    neighbor.focus(); page.keyboard.press("Enter")
    expect(page.locator(".concept-map-detail h3")).to_have_text("ISR")
    expect(page.locator(".concept-map-detail h3")).to_be_focused()
    link = page.locator(".concept-map-source-link").first
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", "noopener")
    with page.expect_popup() as popup:
        link.click()
    materials_page = popup.value
    materials_page.wait_for_load_state()
    assert "collection=" + live.os["id"] in materials_page.url
    assert "unit=" + live.os["units"][1]["unit_id"] in materials_page.url
    expect(materials_page.locator("#knowledgePanel")).to_be_focused()
    expect(materials_page.locator("#conceptInput")).to_be_enabled()
    expect(page.locator("#chatScopeBadge")).to_have_text("Bài giảng · Operating systems")
    expect(page.locator(".concept-map-detail h3")).to_have_text("ISR")
    materials_page.close()
    assert live.responder.calls == []
