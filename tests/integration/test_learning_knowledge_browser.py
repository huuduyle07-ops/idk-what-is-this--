"""Learning graph links through Chromium, with isolated lecture snapshots."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect

from tests.integration.test_learning_materials_browser import (
    API, browser, collection_details, diagram_image, document,
    expect_loaded_image, live, open_materials, save_description, select_material,
)


ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-knowledge-browser"


def import_course(page, context, base, tmp_path, *, with_image=False):
    lesson = tmp_path / "inheritance.docx"
    lesson.write_bytes(document("Kiểu khai báo của biến.", "Phương thức của lớp đối tượng được gọi khi chạy."))
    paths = [str(lesson)]
    if with_image:
        diagram = tmp_path / "dispatch.png"
        diagram.write_bytes(diagram_image())
        paths.append(str(diagram))
    open_materials(page, base)
    page.locator("#materialsFilesInput").set_input_files(paths)
    page.locator("#materialsTitleInput").fill("Java — Nối các phần bài giảng")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialPreview")).to_be_visible()
    select_material(page, lesson.name)
    expect(page.locator("#conceptInput")).to_be_enabled()
    return collection_details(context, base)[0]


def knowledge_url(detail, unit):
    return f"{API}/{detail['id']}/units/{unit['unit_id']}/knowledge"


def knowledge(context, base, detail, unit):
    response = context.request.get(base + knowledge_url(detail, unit))
    assert response.status == 200
    return response.json()["knowledge"]


def concept_response(page):
    return page.expect_response(lambda response: response.url.endswith("/knowledge/concepts")
                               and response.request.method == "PUT")


def add_concept(page, label):
    expect(page.locator("#conceptInput")).to_be_enabled()
    page.locator("#conceptInput").fill(label)
    with concept_response(page) as saved:
        page.locator("#addConceptButton").click()
    return saved.value


def labels(view):
    return [entry["label"] for entry in view["concepts"]]


def test_concepts_link_exact_document_units_and_images_with_dirty_note_guard(live, tmp_path):
    page, context, base, state = live
    detail = import_course(page, context, base, tmp_path, with_image=True)
    word_id = next(source["source_id"] for source in detail["sources"] if source["format"] == "docx")
    paragraphs = [unit for unit in detail["units"] if unit["source_id"] == word_id]
    image = next(unit for unit in detail["units"] if unit["locator"]["kind"] == "image")
    assert len(paragraphs) == 2
    assert not list(state.material_root.rglob("knowledge.sqlite3"))  # Opening the pane does not persist anything.
    assert add_concept(page, "Kế thừa").status == 200
    expect(page.locator("#conceptTags")).to_contain_text("Kế thừa")
    page.locator("#nextUnitButton").click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 2")
    assert add_concept(page, "Kế thừa").status == 200
    expect(page.locator("#relatedSources button")).to_have_count(1)

    select_material(page, "dispatch.png")
    expect_loaded_image(page)
    assert add_concept(page, "Kế thừa").status == 200
    expect(page.locator("#relatedSources button")).to_have_count(2)
    expect(page.locator("#knowledgeCitation")).to_contain_text("1")
    image_value = page.locator("#materialSourceSelect").input_value()
    note = "Tôi đang đối chiếu chiều mũi tên của sơ đồ."
    page.locator("#imageDescriptionInput").fill(note)
    exact_second = page.locator(f'#relatedSources button[data-unit-id="{paragraphs[1]["unit_id"]}"]')
    exact_second.click()
    expect(page.locator("#materialSourceSelect")).to_have_value(image_value)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    expect(page.locator("#imagePanel")).to_be_visible()
    assert save_description(page).status == 200
    exact_second.click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 2")
    expect(page.locator("#unitText")).to_have_text(paragraphs[1]["text"])
    expect(page.locator("#relatedSources button")).to_have_count(2)
    page.locator(f'#relatedSources button[data-unit-id="{image["unit_id"]}"]').click()
    expect_loaded_image(page)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)

    # The persisted relation is separate from source verification or lesson activation.
    view = knowledge(context, base, detail, image)
    assert labels(view) == ["Kế thừa"]
    assert view["revision"] == 1 and view["grounding_ready"] is False
    assert {row["unit_id"] for row in view["related"]} == {unit["unit_id"] for unit in paragraphs}
    assert collection_details(context, base)[0]["grounding_ready"] is False
    page.reload()
    page.locator("#materialsCollections button").click()
    select_material(page, "dispatch.png")
    expect(page.locator("#conceptTags")).to_contain_text("Kế thừa")
    expect(page.locator("#relatedSources button")).to_have_count(2)

    hostile = '<img src=x onerror="window.__conceptXSS=true">'
    assert add_concept(page, hostile).status == 200
    expect(page.locator("#conceptTags")).to_contain_text(hostile)
    expect(page.locator("#conceptTags img")).to_have_count(0)
    assert page.evaluate("typeof window.__conceptXSS") == "undefined"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.locator("#knowledgePanel").screenshot(path=str(ARTIFACTS / "linked-sources-desktop.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#knowledgePanel")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.locator("#knowledgePanel").screenshot(path=str(ARTIFACTS / "linked-sources-mobile.png"))

    with concept_response(page) as removed:
        page.get_by_role("button", name="Bỏ khái niệm Kế thừa", exact=True).click()
    assert removed.value.status == 200
    expect(page.locator("#relatedSources button")).to_have_count(0)
    assert labels(knowledge(context, base, detail, image)) == [hostile]
    assert knowledge(context, base, detail, paragraphs[0])["related_total"] == 1


def test_concurrent_concept_edit_keeps_draft_until_reviewed_apply(live, tmp_path):
    page, context, base, _ = live
    detail = import_course(page, context, base, tmp_path)
    unit = detail["units"][0]
    peer = context.new_page()
    peer_errors = []
    peer.on("pageerror", lambda error: peer_errors.append(str(error)))
    peer.goto(base + "/learn/materials")
    peer.locator("#materialsCollections button").click()
    expect(peer.locator("#conceptInput")).to_be_enabled()
    page.locator("#conceptInput").fill("Kế thừa")
    assert add_concept(peer, "Đa hình").status == 200
    with concept_response(page) as stale:
        page.locator("#addConceptButton").click()
    assert stale.value.status == 409
    expect(page.locator("#knowledgeConflict")).to_be_visible()
    expect(page.locator("#pendingConceptLabels")).to_contain_text("Kế thừa")
    expect(page.locator("#latestConceptLabels")).to_contain_text("Đa hình")
    expect(page.locator("#conceptInput")).to_have_value("Kế thừa")
    assert labels(knowledge(context, base, detail, unit)) == ["Đa hình"]
    # Only the explicit apply action may replace the newly read server set.
    with concept_response(page) as resolved:
        page.locator("#applyDraftKnowledgeButton").click()
    assert resolved.value.status == 200
    expect(page.locator("#knowledgeConflict")).to_be_hidden()
    expect(page.locator("#conceptTags")).to_contain_text("Kế thừa")
    persisted = knowledge(context, base, detail, unit)
    assert labels(persisted) == ["Kế thừa"] and persisted["revision"] == 2
    peer.reload()
    peer.locator("#materialsCollections button").click()
    expect(peer.locator("#conceptTags")).to_contain_text("Kế thừa")
    assert peer_errors == []
    peer.close()


def test_lost_concept_acknowledgment_retries_exact_payload_once(live, tmp_path):
    page, context, base, _ = live
    detail = import_course(page, context, base, tmp_path)
    unit = detail["units"][0]
    submissions = []

    def lose_first_acknowledgment(route):
        submissions.append(route.request.post_data_json)
        if len(submissions) == 1:
            response = route.fetch()  # The server commits before the browser loses the response.
            assert response.status == 200
            route.abort()
        else:
            route.continue_()

    page.route("**/knowledge/concepts", lose_first_acknowledgment)
    page.locator("#conceptInput").fill("Kế thừa")
    page.locator("#addConceptButton").click()
    expect(page.locator("#retryKnowledgeButton")).to_be_visible()
    expect(page.locator("#conceptInput")).to_have_value("Kế thừa")
    persisted = knowledge(context, base, detail, unit)
    assert labels(persisted) == ["Kế thừa"] and persisted["revision"] == 1
    with concept_response(page) as retried:
        page.locator("#retryKnowledgeButton").click()
    assert retried.value.status == 200
    expect(page.locator("#conceptTags")).to_contain_text("Kế thừa")
    expect(page.locator("#retryKnowledgeButton")).to_be_hidden()
    assert submissions == [{"labels": ["Kế thừa"], "expected_revision": 0}] * 2
    assert knowledge(context, base, detail, unit) == persisted


def test_delayed_unit_read_cannot_replace_newer_selected_unit(live, tmp_path):
    page, context, base, _ = live
    detail = import_course(page, context, base, tmp_path)
    first, second = detail["units"]
    assert add_concept(page, "Kế thừa").status == 200
    page.locator("#nextUnitButton").click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 2")
    assert add_concept(page, "Đa hình").status == 200
    delayed = []
    first_url = base + knowledge_url(detail, first)

    def delay_first_unit(route):
        response = route.fetch()
        assert response.status == 200
        delayed.append((route, response))
        # Keep this read in flight while the learner navigates to another unit.

    page.route(first_url, delay_first_unit)
    with page.expect_request(first_url):
        page.locator("#previousUnitButton").click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 1")
    expect(page.locator("#conceptInput")).to_be_disabled()
    page.locator("#nextUnitButton").click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 2")
    expect(page.locator("#conceptInput")).to_be_enabled()
    expect(page.locator("#conceptTags")).to_contain_text("Đa hình")
    assert len(delayed) == 1
    route, response = delayed[0]
    with page.expect_response(first_url):
        route.fulfill(response=response)
    # Let the stale fetch's promise and a render frame settle before checking.
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    expect(page.locator("#unitText")).to_have_text(second["text"])
    expect(page.locator("#conceptTags")).to_contain_text("Đa hình")
    expect(page.locator("#conceptTags")).not_to_contain_text("Kế thừa")
    assert labels(knowledge(context, base, detail, second)) == ["Đa hình"]
