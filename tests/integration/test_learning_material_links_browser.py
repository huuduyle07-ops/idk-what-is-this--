"""Concept map links open the precise saved source, without writing labels."""
import hashlib
import uuid

from playwright.sync_api import expect

from core.learning.material_library import MaterialLibrary
from tests.integration.test_learning_materials_browser import browser, live, document


def test_material_link_selects_the_exact_file_unit_and_concept_editor(live):
    page, context, base, state = live
    page.goto(base + "/learn/materials")
    expect(page.locator("#collectionsEmpty")).to_contain_text("Chưa có bộ tài liệu")
    cookie = next(item["value"] for item in context.cookies() if item["name"] == "cattus_learner")
    owner = hashlib.sha256(("cattus-learning-v1:" + cookie).encode("ascii")).hexdigest()
    library = MaterialLibrary(state.material_root)
    collection, _ = library.import_files(owner, uuid.uuid4().hex, "Operating Systems", [
        ("first.docx", document("A process owns an address space.")),
        ("second.docx", document("An interrupt is an event.", "A semaphore is a synchronization primitive.")),
    ])
    target = next(unit for unit in collection["units"] if "semaphore" in unit["text"])
    page.goto(base + "/learn/materials?collection=" + collection["id"] + "&unit=" + target["unit_id"])
    expect(page.locator("#previewHeading")).to_have_text("Operating Systems")
    expect(page.locator("#unitText")).to_have_text(target["text"])
    expect(page.locator("#materialSourceSelect option:checked")).to_have_text("second.docx")
    expect(page.locator("#conceptInput")).to_be_enabled()
    expect(page.locator("#conceptTags")).to_be_empty()
    assert not list(state.material_root.rglob("knowledge.sqlite3"))


def test_invalid_material_link_is_not_followed(live):
    page, _, base, _ = live
    requested = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(base + "/learn/materials?collection=..%2Fprivate&unit=not-a-unit")
    expect(page.locator("#materialsNotice")).to_contain_text("Liên kết tới phần nguồn không hợp lệ")
    assert not any("/api/materials/" in url for url in requested)
