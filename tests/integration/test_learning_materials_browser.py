"""Real Chromium file/folder upload and retry checks with isolated local state."""
from __future__ import annotations

import base64
import io
from pathlib import Path
import re

from docx import Document
from PIL import Image, ImageDraw
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.test_auth_web1 import configure_offline_web
from tests.test_auth_web1_browser import _Listener


ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-materials-browser"
API = "/learn/api/materials"


def document(*paragraphs):
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    target = io.BytesIO()
    doc.save(target)
    return target.getvalue()


def diagram_image(image_format="PNG", *, size=(640, 320)):
    """Small geometric fixture; the pixels exercise real browser decoding."""
    image = Image.new("RGB", size, "#f7f5ee")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 90, 220, 220), fill="#d4ebe1", outline="#245d4e", width=3)
    draw.rectangle((420, 90, 590, 220), fill="#fff0bf", outline="#8c6821", width=3)
    draw.line((225, 155, 405, 155), fill="#245d4e", width=4)
    draw.polygon(((405, 155), (388, 143), (388, 167)), fill="#245d4e")
    draw.text((100, 145), "Animal", fill="#173c33")
    draw.text((475, 145), "Cat", fill="#173c33")
    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


def select_material(page, name):
    page.locator("#materialSourceSelect").select_option(label=name)


def expect_loaded_image(page, *, width=640):
    expect(page.locator("#imagePanel")).to_be_visible()
    page.wait_for_function("""(width) => {
        const image = document.getElementById('materialImage');
        return image && image.complete && image.naturalWidth === width;
    }""", arg=width)


def save_description(page):
    with page.expect_response(lambda response: "/sources/" in response.url
                              and response.url.endswith("/description")
                              and response.request.method == "PUT") as saved:
        page.locator("#saveDescriptionButton").click()
    return saved.value


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as driver:
        instance = driver.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def live(tmp_path, monkeypatch, browser):
    state = configure_offline_web(tmp_path, monkeypatch, allow_loopback=True)
    state.material_root = tmp_path / "targeted_subject"
    monkeypatch.setitem(state.app.config, "TARGETED_SUBJECT_ROOT", state.material_root)
    listener = _Listener(state.app)
    base = f"http://127.0.0.1:{listener.port}"
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    try:
        yield page, context, base, state
        assert errors == []
        assert state.calls == []
        assert not list(state.repo.iterdir())
    finally:
        context.close()
        listener.close()


def open_materials(page, base):
    page.goto(base + "/learn/materials")
    expect(page.locator("#collectionsEmpty")).to_contain_text("Chưa có bộ tài liệu")
    expect(page.locator("#chooseFilesButton")).to_be_enabled()


def collection_details(context, base):
    collections = context.request.get(base + API).json()["collections"]
    return [context.request.get(base + API + "/" + row["id"]).json()["collection"] for row in collections]


def test_file_picker_preview_is_plain_text_reload_and_mobile(live, tmp_path):
    page, context, base, state = live
    open_materials(page, base)
    page.screenshot(path=str(ARTIFACTS / "desktop-empty.png"), full_page=True)
    payload = '<img src=x onerror="window.__lectureXSS = true">'
    explanation = "Kế thừa: kiểu của biến và lớp của đối tượng có thể khác nhau."
    code = "Animal pet = new Cat();\npet.speak(); // Phương thức nào được gọi khi chạy?"
    source = tmp_path / "ke-thua.docx"
    source.write_bytes(document(explanation, payload, code))
    with page.expect_file_chooser() as chooser:
        page.locator("#chooseFilesButton").click()
    chooser.value.set_files(str(source))
    expect(page.locator("#selectionMessage")).to_contain_text("1 file")
    expect(page.locator("#selectionMessage")).to_contain_text("Chưa gửi")
    assert not state.material_root.exists()
    page.locator("#materialsTitleInput").fill("Java — Hiểu kế thừa")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialPreview")).to_be_visible()
    expect(page.locator("#previewHeading")).to_have_text("Java — Hiểu kế thừa")
    expect(page.locator("#unitText")).to_have_text(explanation)
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 1")
    page.locator("#nextUnitButton").click()
    expect(page.locator("#unitText")).to_have_text(payload)
    expect(page.locator("#unitText img")).to_have_count(0)
    assert page.evaluate("typeof window.__lectureXSS") == "undefined"
    page.locator("#nextUnitButton").click()
    expect(page.locator("#unitCitation")).to_have_text("Đoạn Word 3")
    expect(page.locator("#unitText")).to_have_text(code)
    expect(page.locator("#nextUnitButton")).to_be_disabled()
    page.screenshot(path=str(ARTIFACTS / "desktop-preview.png"), full_page=True)
    page.reload()
    expect(page.locator("#materialsCollections button")).to_have_count(1)
    page.locator("#materialsCollections button").click()
    expect(page.locator("#unitText")).to_have_text(explanation)
    page.locator("#unitNumberInput").fill("3")
    page.locator("#unitNumberInput").press("Tab")
    expect(page.locator("#unitText")).to_have_text(code)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "mobile-preview.png"), full_page=True)
    assert len(collection_details(context, base)) == 1


def test_actual_directory_picker_keeps_nested_paths_and_reports_ignored_files(live, tmp_path):
    page, context, base, state = live
    folder = tmp_path / "Java-course"
    nested = folder / "chapter-2"
    nested.mkdir(parents=True)
    (folder / "intro.docx").write_bytes(document("Introduction"))
    (nested / "inheritance.docx").write_bytes(document("Dynamic dispatch"))
    (nested / "readme.txt").write_text("Unsupported lecture format", encoding="utf-8")
    open_materials(page, base)
    page.locator("#materialsFolderInput").set_input_files(str(folder))
    expect(page.locator("#selectedFiles > li")).to_have_count(2)
    expect(page.locator("#selectedFiles")).to_contain_text("Java-course/chapter-2/inheritance.docx")
    expect(page.locator("#selectionMessage")).to_contain_text("Đã bỏ qua 1 file không hỗ trợ")
    expect(page.locator("#materialsTitleInput")).to_have_value("Java-course")
    assert not state.material_root.exists()
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialPreview")).to_be_visible()
    details = collection_details(context, base)
    assert len(details) == 1
    assert {path for source in details[0]["sources"] for path in source["upload_paths"]} == {
        "Java-course/intro.docx", "Java-course/chapter-2/inheritance.docx",
    }
    expect(page.locator("#materialSourceSelect option")).to_have_count(2)


def test_folder_drop_reads_all_batches_and_lost_response_retry_is_idempotent(live):
    page, context, base, state = live
    open_materials(page, base)
    first = base64.b64encode(document("First dropped lesson")).decode("ascii")
    second = base64.b64encode(document("Nested dropped lesson")).decode("ascii")
    page.evaluate("""({first, second}) => {
        window.__directoryReads = {};
        function fileEntry(name, encoded) {
            return {name, isFile: true, isDirectory: false, file(success) {
                const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
                queueMicrotask(() => success(new File([bytes], name, {type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'})));
            }};
        }
        function folder(name, batches) {
            return {name, isFile: false, isDirectory: true, createReader() {
                let index = 0;
                return {readEntries(success) {
                    window.__directoryReads[name] = (window.__directoryReads[name] || 0) + 1;
                    const batch = batches[index++] || [];
                    queueMicrotask(() => success(batch));
                }};
            }};
        }
        const nested = folder('chapter-2', [[fileEntry('second.docx', second)], []]);
        const root = folder('Dropped-course', [[fileEntry('first.docx', first)], [nested], []]);
        const event = new Event('drop', {bubbles: true, cancelable: true});
        Object.defineProperty(event, 'dataTransfer', {value: {
            items: [{kind: 'file', webkitGetAsEntry: () => root}], files: []
        }});
        document.getElementById('materialsDropzone').dispatchEvent(event);
    }""", {"first": first, "second": second})
    expect(page.locator("#selectedFiles > li")).to_have_count(2)
    expect(page.locator("#selectedFiles")).to_contain_text("Dropped-course/chapter-2/second.docx")
    assert page.evaluate("window.__directoryReads") == {"Dropped-course": 3, "chapter-2": 2}
    assert not state.material_root.exists()
    request_ids = []

    def lose_first_response(route):
        raw = route.request.post_data_buffer
        match = re.search(rb'name="request_id"\r\n\r\n([^\r\n]+)', raw)
        assert match is not None
        request_ids.append(match.group(1))
        if len(request_ids) == 1:
            response = route.fetch()  # Commit succeeds; only its response is lost.
            assert response.status == 201
            route.abort()
        else:
            route.continue_()

    page.route("**/learn/api/materials", lose_first_response)
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialsNoticeText")).to_contain_text("Chưa nhận được xác nhận")
    expect(page.locator("#selectedFiles > li")).to_have_count(2)
    expect(page.locator("#materialsTitleInput")).to_have_value("Dropped-course")
    expect(page.locator("#importMaterialsButton")).to_be_enabled()
    assert len(collection_details(context, base)) == 1
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialPreview")).to_be_visible()
    assert len(request_ids) == 2 and request_ids[0] == request_ids[1]
    details = collection_details(context, base)
    assert len(details) == 1 and details[0]["source_count"] == 2
    assert len(list(state.material_root.rglob("manifest.json"))) == 1
    expect(page.locator("#materialsCollections button")).to_have_count(1)


def test_mixed_images_decode_zoom_and_description_survives_reload(live, tmp_path):
    page, context, base, state = live
    lesson = tmp_path / "inheritance.docx"
    lesson.write_bytes(document("Compare the variable type with the object type."))
    diagram = tmp_path / "inheritance.PNG"
    diagram.write_bytes(diagram_image())
    photograph = tmp_path / "example.jpg"
    photograph.write_bytes(diagram_image("JPEG", size=(720, 360)))
    alternate = tmp_path / "another.jpeg"
    alternate.write_bytes(diagram_image("JPEG", size=(800, 400)))
    open_materials(page, base)
    page.locator("#materialsFilesInput").set_input_files([
        str(lesson), str(diagram), str(photograph), str(alternate),
    ])
    expect(page.locator("#selectedFiles > li")).to_have_count(4)
    assert not state.material_root.exists()
    page.locator("#materialsTitleInput").fill("Java — Hình minh họa kế thừa")
    page.locator("#importMaterialsButton").click()
    expect(page.locator("#materialPreview")).to_be_visible()
    expect(page.locator("#materialSourceSelect option")).to_have_count(4)
    select_material(page, lesson.name)
    expect(page.locator("#unitText")).to_have_text("Compare the variable type with the object type.")
    expect(page.locator("#imagePanel")).to_be_hidden()
    select_material(page, diagram.name)
    expect_loaded_image(page)
    expect(page.locator("#imageDimensions")).to_contain_text("640")
    expect(page.locator("#imageZoomButton")).to_have_attribute("aria-pressed", "false")
    page.locator("#imageZoomButton").click()
    expect(page.locator("#imageZoomButton")).to_have_attribute("aria-pressed", "true")
    page.locator("#imageZoomButton").click()
    expect(page.locator("#imageZoomButton")).to_have_attribute("aria-pressed", "false")

    note = 'Cat kế thừa Animal. Cần đối chiếu chiều mũi tên. <img src=x onerror="window.__imageNoteXSS = true">'
    page.locator("#imageDescriptionInput").fill(note)
    image_value = page.locator("#materialSourceSelect").input_value()
    # A source change must not silently lose an unfinished explanation.
    select_material(page, lesson.name)
    expect(page.locator("#materialSourceSelect")).to_have_value(image_value)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    expect(page.locator("#imagePanel")).to_be_visible()
    assert save_description(page).status == 200
    expect(page.locator("#descriptionStatus")).to_contain_text("Đã lưu mô tả")
    expect(page.locator("#saveDescriptionButton")).to_be_disabled()
    details = collection_details(context, base)
    source = next(source for source in details[0]["sources"] if diagram.name in source["original_names"])
    assert source["description"] == {"text": note, "revision": 1, "origin": "user"}
    assert details[0]["grounding_ready"] is False
    assert page.evaluate("typeof window.__imageNoteXSS") == "undefined"

    select_material(page, photograph.name)
    expect_loaded_image(page, width=720)
    select_material(page, alternate.name)
    expect_loaded_image(page, width=800)
    page.reload()
    expect(page.locator("#materialsCollections button")).to_have_count(1)
    page.locator("#materialsCollections button").click()
    select_material(page, diagram.name)
    expect_loaded_image(page)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    assert page.evaluate("typeof window.__imageNoteXSS") == "undefined"
    # Capture a normal learner note after checking hostile-looking text remains data.
    page.locator("#imageDescriptionInput").fill("Cat kế thừa Animal. Tôi muốn hiểu khi nào phương thức của Cat được gọi.")
    assert save_description(page).status == 200
    page.locator("#materialPreview").scroll_into_view_if_needed()
    page.locator("#materialPreview").screenshot(path=str(ARTIFACTS / "image-panel.png"))
    page.screenshot(path=str(ARTIFACTS / "image-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(ARTIFACTS / "image-mobile.png"), full_page=True)
    fit_width = page.locator("#materialImage").bounding_box()["width"]
    assert fit_width < 390
    page.locator("#imageZoomButton").click()
    expect(page.locator("#imageZoomButton")).to_have_attribute("aria-pressed", "true")
    assert page.locator("#materialImage").bounding_box()["width"] == 640
    assert page.locator("#imageViewport").evaluate("element => element.scrollWidth > element.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert len(details) == 1 and details[0]["source_count"] == 4


def test_image_description_concurrent_edit_preserves_draft_until_explicit_merge(live, tmp_path):
    page, context, base, _ = live
    diagram = tmp_path / "dispatch.png"
    diagram.write_bytes(diagram_image())
    open_materials(page, base)
    page.locator("#materialsFilesInput").set_input_files(str(diagram))
    page.locator("#importMaterialsButton").click()
    expect_loaded_image(page)
    peer = context.new_page()
    peer_errors = []
    peer.on("pageerror", lambda error: peer_errors.append(str(error)))
    peer.goto(base + "/learn/materials")
    expect(peer.locator("#materialsCollections button")).to_have_count(1)
    peer.locator("#materialsCollections button").click()
    expect_loaded_image(peer)
    draft = "Bản đang viết: cần thêm ví dụ về dynamic dispatch."
    saved_text = 'Bản từ tab khác: <svg onload="window.__descriptionXSS = true"></svg>'
    page.locator("#imageDescriptionInput").fill(draft)
    peer.locator("#imageDescriptionInput").fill(saved_text)
    assert save_description(peer).status == 200
    assert save_description(page).status == 409
    expect(page.locator("#imageDescriptionInput")).to_have_value(draft)
    expect(page.locator("#reloadDescriptionButton")).to_be_visible()
    page.locator("#reloadDescriptionButton").click()
    expect(page.locator("#latestDescriptionText")).to_have_text(saved_text)
    expect(page.locator("#latestDescriptionText svg")).to_have_count(0)
    expect(page.locator("#imageDescriptionInput")).to_have_value(draft)
    assert page.evaluate("typeof window.__descriptionXSS") == "undefined"
    page.locator("#keepDraftDescriptionButton").click()
    expect(page.locator("#imageDescriptionInput")).to_have_value(draft)
    # Adopting the newer revision alone must not write over another tab's text.
    assert collection_details(context, base)[0]["sources"][0]["description"]["text"] == saved_text
    assert save_description(page).status == 200
    result = collection_details(context, base)[0]["sources"][0]["description"]
    assert result == {"text": draft, "revision": 2, "origin": "user"}
    peer.reload()
    peer.locator("#materialsCollections button").click()
    expect(peer.locator("#imageDescriptionInput")).to_have_value(draft)
    assert peer_errors == []
    peer.close()


def test_image_description_lost_acknowledgment_retries_without_new_revision(live, tmp_path):
    page, context, base, _ = live
    diagram = tmp_path / "lost-response.png"
    diagram.write_bytes(diagram_image())
    open_materials(page, base)
    page.locator("#materialsFilesInput").set_input_files(str(diagram))
    page.locator("#importMaterialsButton").click()
    expect_loaded_image(page)
    note = "Giải thích của tôi: lớp con có thể thay đổi hành vi được kế thừa."
    page.locator("#imageDescriptionInput").fill(note)
    submissions = []

    def lose_first_acknowledgment(route):
        submissions.append(route.request.post_data_json)
        if len(submissions) == 1:
            response = route.fetch()  # Persist succeeds before its acknowledgment is lost.
            assert response.status == 200
            route.abort()
        else:
            route.continue_()

    page.route("**/sources/*/description", lose_first_acknowledgment)
    page.locator("#saveDescriptionButton").click()
    expect(page.locator("#descriptionStatus")).to_contain_text("Chưa nhận được xác nhận")
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    expect(page.locator("#saveDescriptionButton")).to_be_enabled()
    persisted = collection_details(context, base)[0]["sources"][0]["description"]
    assert persisted == {"text": note, "revision": 1, "origin": "user"}
    assert save_description(page).status == 200
    expect(page.locator("#descriptionStatus")).to_contain_text("Đã lưu mô tả")
    expect(page.locator("#saveDescriptionButton")).to_be_disabled()
    assert submissions == [{"text": note, "expected_revision": 0}] * 2
    assert collection_details(context, base)[0]["sources"][0]["description"] == persisted
    page.reload()
    page.locator("#materialsCollections button").click()
    expect_loaded_image(page)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
