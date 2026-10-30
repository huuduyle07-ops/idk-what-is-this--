"""File classification stays explicit and grounded while Materials remains usable."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.integration.test_learning_materials_browser import (
    API, browser, live, document, diagram_image, collection_details, open_materials,
)
from tests.integration.test_learning_file_labels_web import Classifier, LABELS


ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-file-labels-browser"


@pytest.fixture
def labels_live(live, monkeypatch):
    page, context, base, state = live
    classifier = Classifier()
    monkeypatch.setitem(state.app.config, "LEARNING_CHAT_RESPONDER", classifier)
    open_materials(page, base)
    page.locator("#materialsFilesInput").set_input_files([
        {"name": "os.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": document("Operating systems use semaphores for synchronization.", "Interrupt handlers respond to interrupts.")},
        {"name": "java.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": document("Java inheritance selects the overridden instance method at runtime.")},
        {"name": "diagram.png", "mimeType": "image/png", "buffer": diagram_image()},
    ])
    page.locator("#materialsTitleInput").fill("Course library")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#previewHeading")).to_have_text("Course library")
    page.locator("#fileLabelsPanel > summary").click()
    expect(page.locator("#fileLabelSubject")).to_be_enabled()
    page.locator("#materialSourceSelect").select_option(label="os.docx")
    collection = collection_details(context, base)[0]
    state.collection = collection
    state.classifier = classifier
    state.listing = base + API + "/" + collection["id"] + "/labels"
    yield page, context, base, state


def records(context, state):
    return context.request.get(state.listing).json()["files"]


def current_record(context, state, filename="os.docx"):
    source = next(s for s in state.collection["sources"] if filename in s["original_names"])
    return next(row for row in records(context, state) if row["source_id"] == source["source_id"])


def suggest(page):
    with page.expect_response(lambda response: response.url.endswith("/labels/suggest")) as response:
        page.locator("#suggestFileLabels").click()
    assert response.value.status == 200
    expect(page.locator("#fileLabelSuggestion")).to_be_visible()


def confirm(page):
    with page.expect_response(lambda response: response.url.endswith("/labels") and response.request.method == "PUT") as response:
        page.locator("#confirmFileLabels").click()
    assert response.value.status == 200
    expect(page.locator("#fileLabelsBadge")).to_contain_text("Confirmed")


def test_explicit_suggest_review_use_confirm_and_confirmed_filter(labels_live):
    page, context, _, state = labels_live
    assert not state.classifier.calls
    expect(page.locator("#suggestFileLabels")).to_be_enabled()
    expect(page.locator("#fileLabelModel")).to_contain_text("ollama · fixture")
    suggest(page)
    assert len(state.classifier.calls) == 1
    record = current_record(context, state)
    assert record["status"] == "unclassified" and record["labels"]["subject"] == ""
    expect(page.locator("#fileLabelSubject")).to_have_value("")
    expect(page.locator("#fileLabelSuggestionInfo")).to_contain_text("Sampled 2 / 2")
    page.locator("#fileLabelEvidence summary").first.click()
    expect(page.locator("#fileLabelEvidence blockquote").first).to_contain_text("Operating systems")
    page.locator("#materialFileFilter").fill("Computer Science")
    expect(page.locator("#materialFileFilterStatus")).to_contain_text("0 / 3")
    page.locator("#useFileLabelSuggestion").click()
    expect(page.locator("#fileLabelSubject")).to_have_value(LABELS["subject"])
    assert current_record(context, state)["status"] == "unclassified"
    page.locator("#fileLabelSubject").fill("Operating Systems")
    confirm(page)
    saved = current_record(context, state)
    assert saved["labels"]["subject"] == "Operating Systems" and saved["suggestion"] is None
    page.locator("#materialFileFilter").fill("Operating Systems")
    expect(page.locator("#materialFileFilterStatus")).to_contain_text("1 / 3")
    expect(page.locator("#materialSourceSelect option")).to_have_count(1)
    assert len(state.classifier.calls) == 1


def test_draft_guard_manual_confirmation_reload_and_mobile_safe_text(labels_live):
    page, context, base, state = labels_live
    payload = '<img src=x onerror="window.__labelsXSS=1">'
    page.locator("#fileLabelSubject").fill(payload)
    page.locator("#fileLabelTopics").fill("Concurrency\nSynchronization")
    page.locator("#fileLabelRole").select_option("lecture")
    page.locator("#fileLabelLanguage").select_option("English")
    expect(page.locator("#suggestFileLabels")).to_be_disabled()
    selected = page.locator("#materialSourceSelect").input_value()
    page.locator("#materialSourceSelect").select_option(label="java.docx")
    expect(page.locator("#materialSourceSelect")).to_have_value(selected)
    expect(page.locator("#fileLabelSubject")).to_have_value(payload)
    expect(page.locator("#materialsNoticeText")).to_contain_text("bản nháp")
    confirm(page)
    assert current_record(context, state)["labels"]["topics"] == ["Concurrency", "Synchronization"]
    page.reload()
    page.locator(".collection-button").click()
    page.locator("#fileLabelsPanel > summary").click()
    expect(page.locator("#fileLabelSubject")).to_have_value(payload)
    expect(page.locator("#confirmFileLabels")).to_be_disabled()
    assert not state.classifier.calls
    assert page.evaluate("typeof window.__labelsXSS") == "undefined"
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("#fileLabelsPanel").scroll_into_view_if_needed()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / "labels-mobile.png"), full_page=True)


def test_unknown_suggest_result_requires_reload_without_second_model_call(labels_live):
    page, context, _, state = labels_live
    def lose_response(route):
        response = route.fetch()
        assert response.status == 200
        route.abort()
    page.route("**/labels/suggest", lose_response)
    page.locator("#suggestFileLabels").click()
    expect(page.locator("#fileLabelsStatus")).to_contain_text("Reload labels")
    expect(page.locator("#suggestFileLabels")).to_be_disabled()
    expect(page.locator("#confirmFileLabels")).to_be_disabled()
    assert len(state.classifier.calls) == 1
    assert current_record(context, state)["suggestion"] is not None
    page.locator("#reloadFileLabels").click()
    expect(page.locator("#fileLabelsConflict")).to_be_visible()
    page.locator("#useSavedFileLabels").click()
    expect(page.locator("#fileLabelSuggestion")).to_be_visible()
    expect(page.locator("#useFileLabelSuggestion")).to_be_enabled()
    assert len(state.classifier.calls) == 1


def test_conflict_reload_preserves_draft_and_explicit_choice(labels_live):
    page, _, _, state = labels_live
    page.locator("#fileLabelSubject").fill("My draft")
    def conflict(route):
        route.fulfill(status=409, json={"ok": False, "error": "Labels changed", "error_code": "label_conflict"})
    page.route("**/sources/*/labels", conflict)
    page.locator("#confirmFileLabels").click()
    expect(page.locator("#fileLabelsStatus")).to_contain_text("Reload labels")
    page.locator("#reloadFileLabels").click()
    expect(page.locator("#fileLabelsConflict")).to_be_visible()
    expect(page.locator("#fileLabelSubject")).to_have_value("My draft")
    page.locator("#keepDraftFileLabels").click()
    expect(page.locator("#fileLabelsConflict")).to_be_hidden()
    expect(page.locator("#fileLabelSubject")).to_have_value("My draft")
    page.unroute("**/sources/*/labels", conflict)
    confirm(page)
    assert not state.classifier.calls


def test_concepts_refresh_and_image_note_invalidates_suggestion(labels_live):
    page, context, _, state = labels_live
    page.locator("#conceptInput").fill("Semaphore")
    page.locator("#addConceptButton").click()
    expect(page.locator("#fileConceptSummary")).to_contain_text("Semaphore")
    page.locator("#materialSourceSelect").select_option(label="diagram.png")
    page.locator("#imageDescriptionInput").fill("Operating systems diagram showing semaphores.")
    page.locator("#saveDescriptionButton").click()
    expect(page.locator("#suggestFileLabels")).to_be_enabled()
    suggest(page)
    expect(page.locator("#fileLabelEvidence")).to_contain_text("Your image note")
    page.locator("#imageDescriptionInput").fill("Updated diagram: interrupt handlers.")
    page.locator("#saveDescriptionButton").click()
    expect(page.locator("#fileLabelStale")).to_be_visible()
    expect(page.locator("#useFileLabelSuggestion")).to_be_disabled()
    assert current_record(context, state, "diagram.png")["suggestion_stale"] is True
    assert len(state.classifier.calls) == 1


def test_labels_unavailable_keeps_source_reading_and_manual_reload(labels_live):
    page, _, _, state = labels_live
    page.route("**/materials/*/labels", lambda route: route.fulfill(status=503, json={"ok": False, "error": "Metadata unavailable"}))
    page.reload()
    page.locator(".collection-button").click()
    page.locator("#fileLabelsPanel > summary").click()
    expect(page.locator("#fileLabelsStatus")).to_contain_text("Metadata unavailable")
    page.locator("#materialSourceSelect").select_option(label="java.docx")
    expect(page.locator("#unitText")).to_contain_text("Java inheritance")
    expect(page.locator("#fileLabelSubject")).to_be_disabled()
    page.unroute("**/materials/*/labels")
    page.locator("#reloadFileLabels").click()
    expect(page.locator("#fileLabelSubject")).to_be_enabled()
    assert not state.classifier.calls


def test_late_metadata_response_cannot_change_selected_collection(labels_live):
    page, context, base, state = labels_live
    held = []
    page.route("**/materials/*/labels", lambda route: held.append(route))
    page.locator("#reloadFileLabels").click()
    expect(page.locator("#fileLabelSubject")).to_be_disabled()
    page.locator("#materialsFilesInput").set_input_files({"name": "new.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "buffer": document("Korean language basics")})
    page.locator("#materialsTitleInput").fill("Second library")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#previewHeading")).to_have_text("Second library")
    page.wait_for_function("document.getElementById('materialPreview').getAttribute('aria-busy') !== 'true'")
    page.wait_for_timeout(100)
    assert len(held) == 2
    held[1].continue_()
    expect(page.locator("#fileLabelSubject")).to_be_enabled()
    page.locator("#fileLabelSubject").fill("Second collection draft")
    held[0].continue_()
    expect(page.locator("#fileLabelSubject")).to_have_value("Second collection draft")
    expect(page.locator("#unitText")).to_have_text("Korean language basics")
    assert len(collection_details(context, base)) == 2
    assert not state.classifier.calls
