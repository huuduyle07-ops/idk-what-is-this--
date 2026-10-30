"""Source visual journeys over real owner routes and immutable local storage."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pytest
from playwright.sync_api import expect

from core.learning.materials import MaterialsError
from tests.integration.test_learning_materials_browser import browser, live, document
from tests.learning.test_document_extractors import pdf, presentation

API = "/learn/api/materials"
ARTIFACTS = Path(__file__).resolve().parents[2] / ".tmp" / "teacher-source-visuals-browser"


def source_picture(label="Source visual — page or native part"):
    image = Image.new("RGB", (1200, 650), "#f7f5ee")
    draw = ImageDraw.Draw(image)
    try: font = ImageFont.truetype("arial.ttf", 28)
    except OSError: font = ImageFont.load_default()
    draw.text((50, 35), label, fill="#173c33", font=font)
    draw.rectangle((70, 175, 430, 440), fill="#d4ebe1", outline="#245d4e", width=4)
    draw.rectangle((770, 175, 1130, 440), fill="#fff0bf", outline="#8c6821", width=4)
    draw.line((440, 305, 750, 305), fill="#245d4e", width=7)
    draw.polygon(((750, 305), (720, 283), (720, 327)), fill="#245d4e")
    draw.text((175, 285), "Producer", fill="#173c33", font=font)
    draw.text((875, 285), "Consumer", fill="#173c33", font=font)
    draw.text((50, 555), "Review the original source; no visual interpretation.", fill="#173c33", font=font)
    target = io.BytesIO(); image.save(target, "PNG"); return target.getvalue()


class Renderer:
    def __init__(self):
        self.calls = []
        self.fail_once = False
        self.empty = False

    def __call__(self, raw, source_format, locator):
        assert isinstance(raw, bytes) and raw
        self.calls.append((source_format, dict(locator)))
        if self.fail_once:
            self.fail_once = False
            raise MaterialsError("visual_unavailable", "Office renderer unavailable for this fixture.")
        office = source_format in {"docx", "pptx"}
        kind = "embedded_image" if office else "page_render" if source_format == "pdf" else "source_image"
        native = ("word/media/image1.png" if source_format == "docx" else "ppt/media/image1.png") if office else None
        notes = ["Only embedded images are available; vector shapes and connections were not rendered."] if office else []
        notes.append('<img src=x onerror="window.__visualXSS=1"> is plain source warning text.')
        visual = {"kind": kind, "mime_type": "image/png", "width": 1200, "height": 650,
                  "bytes": source_picture(f"{source_format.upper()} {locator['kind']} {locator['index']}"),
                  "locator": dict(locator), "native_part": native, "bbox": None if source_format == "docx" else [0, 0, 1, 1], "warnings": []}
        return {"version": "source-visuals-v1", "status": "partial" if office else "ready", "warnings": notes, "visuals": [] if self.empty else [visual]}


@pytest.fixture
def visuals(live, monkeypatch):
    page, context, base, state = live
    renderer = Renderer()
    monkeypatch.setitem(state.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", renderer)
    page.goto(base + "/learn/materials")
    expect(page.locator("#collectionsEmpty")).to_contain_text("Chưa có bộ tài liệu")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    yield page, context, base, state, renderer


def upload(page, contents, title="Visual lecture"):
    page.locator("#materialsFilesInput").set_input_files([
        {"name": name, "mimeType": mime, "buffer": raw} for name, mime, raw in contents
    ])
    page.locator("#materialsTitleInput").fill(title)
    with page.expect_response(lambda response: response.url.endswith(API) and response.request.method == "POST") as response:
        page.locator("#importMaterialsButton").click()
    assert response.value.status == 201, response.value.text()
    expect(page.locator("#prepareSourceVisuals")).to_be_enabled()
    return response.value.json()["collection"]


def prepare(page):
    with page.expect_response(lambda response: response.url.endswith("/visuals") and response.request.method == "POST") as response:
        page.locator("#prepareSourceVisuals").click()
    assert response.value.status == 200, response.value.text()
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(1)
    page.wait_for_function("""() => { const image=document.querySelector('#sourceVisualsGallery img'); return image && image.complete && image.naturalWidth === 1200; }""")
    return response.value.json()["record"]


def test_selection_reads_only_explicit_prepare_and_cached_resume_are_owner_scoped(visuals, browser):
    page, context, base, _, renderer = visuals
    requests = []
    page.on("request", lambda request: requests.append(request) if request.url.endswith("/visuals") else None)
    collection = upload(page, [("lesson.pdf", "application/pdf", pdf(("First page", "Second page")))])
    assert renderer.calls == [] and all(request.method == "GET" for request in requests)
    record = prepare(page)
    assert len(renderer.calls) == 1
    expect(page.locator("#sourceVisualsCitation")).to_contain_text("Trang PDF 1")
    expect(page.locator("#sourceVisualsGallery .source-visual-position")).to_have_text("Trang PDF 1")
    expect(page.locator(".source-visual-coverage")).to_have_text("Toàn bộ trang PDF nguồn")
    assert page.locator(".source-visual-details").evaluate("el => el.open") is False
    expect(page.locator(".source-visual-native")).to_be_hidden()
    expect(page.locator("#sourceVisualsWarnings img")).to_have_count(0)
    assert page.evaluate("typeof window.__visualXSS") == "undefined"
    page.screenshot(path=str(ARTIFACTS / "pdf-desktop.png"), full_page=True)
    page.locator("#sourceVisualsPanel").screenshot(path=str(ARTIFACTS / "pdf-panel-desktop.png"))
    page.reload()
    page.locator(f'[data-collection-id="{collection["id"]}"]').click()
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(1)
    expect(page.locator("#prepareSourceVisuals")).to_be_disabled()
    assert len(renderer.calls) == 1 and sum(request.method == "POST" for request in requests) == 1
    other = browser.new_context()
    try:
        other.request.get(base + "/learn/materials")
        prefix = base + API + "/" + collection["id"] + "/units/" + record["unit_id"] + "/visuals"
        assert other.request.get(prefix).status == 404
        assert other.request.get(base + record["visuals"][0]["image_url"]).status == 404
    finally: other.close()
    page.locator("#nextUnitButton").click()
    expect(page.locator("#sourceVisualsCitation")).to_contain_text("Trang PDF 2")
    expect(page.locator("#prepareSourceVisuals")).to_be_enabled()
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(0)
    assert len(renderer.calls) == 1


def test_office_partial_images_keep_native_positions_and_never_invent_word_pages(visuals):
    page, _, _, _, renderer = visuals
    upload(page, [("lesson.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", document("Word source paragraph")),
                  ("slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", presentation())])
    prepare(page)
    expect(page.locator("#sourceVisualsCitation")).to_contain_text("Đoạn Word 1")
    expect(page.locator("#sourceVisualsGallery .source-visual-position")).to_have_text("Đoạn Word 1")
    expect(page.locator("#sourceVisualsGallery .source-visual-native")).to_have_text("Vị trí trong file gốc: word/media/image1.png")
    expect(page.locator("#sourceVisualsGallery .source-visual-native")).to_be_hidden()
    page.locator(".source-visual-details summary").click()
    expect(page.locator("#sourceVisualsGallery .source-visual-native")).to_be_visible()
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Chỉ có một phần")
    expect(page.locator("#sourceVisualsWarnings")).to_contain_text("vector shapes and connections were not rendered")
    assert "Trang" not in page.locator("#sourceVisualsGallery").inner_text()
    page.locator("#materialSourceSelect").select_option(label="slides.pptx")
    expect(page.locator("#prepareSourceVisuals")).to_be_enabled()
    prepare(page)
    expect(page.locator("#sourceVisualsGallery .source-visual-position")).to_have_text("Slide 1")
    expect(page.locator("#sourceVisualsGallery")).to_contain_text("ppt/media/image1.png")
    assert renderer.calls == [("docx", {"kind": "paragraph", "index": 1}), ("pptx", {"kind": "slide", "index": 1})]


def test_late_prepare_reply_cannot_replace_another_unit(visuals):
    page, _, _, _, renderer = visuals
    collection = upload(page, [("lesson.pdf", "application/pdf", pdf(("First page", "Second page")))])
    unit = collection["units"][0]
    held = []
    def hold(route):
        if route.request.method == "POST": held.append(route)
        else: route.continue_()
    page.route("**/units/" + unit["unit_id"] + "/visuals", hold)
    with page.expect_request(lambda request: request.url.endswith(unit["unit_id"] + "/visuals") and request.method == "POST"):
        page.locator("#prepareSourceVisuals").click()
    page.locator("#nextUnitButton").click()
    expect(page.locator("#sourceVisualsCitation")).to_contain_text("Trang PDF 2")
    expect(page.locator("#prepareSourceVisuals")).to_be_enabled()
    assert len(held) == 1 and renderer.calls == []
    result = held[0].fetch()
    assert result.status == 200 and len(renderer.calls) == 1
    with page.expect_request_finished(lambda request: request.url.endswith(unit["unit_id"] + "/visuals") and request.method == "POST"):
        held[0].fulfill(response=result)
    expect(page.locator("#sourceVisualsCitation")).to_contain_text("Trang PDF 2")
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(0)
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Chỉ đang đọc trạng thái")
    page.locator("#previousUnitButton").click()
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(1)
    assert len(renderer.calls) == 1


def test_lost_prepare_reply_recovers_with_get_without_second_render(visuals):
    page, _, _, _, renderer = visuals
    upload(page, [("lesson.pdf", "application/pdf", pdf(("First page",)))])
    posts = []
    def lose(route):
        if route.request.method == "POST":
            posts.append(route.request.post_data_json); route.fetch(); route.abort()
        else: route.continue_()
    page.route("**/visuals", lose)
    page.locator("#prepareSourceVisuals").click()
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Đã tìm thấy bản hình đã lưu sau khi mất phản hồi")
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(1)
    expect(page.locator("#prepareSourceVisuals")).to_be_disabled()
    page.locator("#reloadSourceVisuals").click()
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Đã có 1 hình nguồn")
    assert len(renderer.calls) == 1 and posts == [{}]


def test_failed_prepare_requires_explicit_retry_after_unprepared_get(visuals):
    page, _, _, _, renderer = visuals
    upload(page, [("lesson.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", document("Source paragraph"))])
    renderer.fail_once = True
    with page.expect_response(lambda response: response.url.endswith("/visuals") and response.request.method == "POST") as response:
        page.locator("#prepareSourceVisuals").click()
    assert response.value.status == 503 and response.value.json()["error_code"] == "visual_unavailable"
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Máy chủ chưa có bản hình đã lưu")
    expect(page.locator("#sourceVisualsStatus")).to_contain_text("Office renderer unavailable for this fixture.")
    expect(page.locator("#prepareSourceVisuals")).to_have_text("Thử chuẩn bị hình lần nữa")
    expect(page.locator("#prepareSourceVisuals")).to_be_enabled()
    assert len(renderer.calls) == 1
    prepare(page)
    assert len(renderer.calls) == 2


def test_mobile_original_zoom_preserves_existing_image_note(visuals):
    page, _, _, _, renderer = visuals
    upload(page, [("source.png", "image/png", source_picture())])
    note = "My own note about the synchronization diagram."
    page.locator("#imageDescriptionInput").fill(note)
    prepare(page)
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    expect(page.locator("#sourceVisualsGallery .source-visual-position")).to_have_text("Ảnh 1")
    page.set_viewport_size({"width": 390, "height": 844})
    viewport = page.locator(".source-visual-viewport")
    viewport.scroll_into_view_if_needed()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert viewport.evaluate("el => el.scrollWidth <= el.clientWidth")
    page.locator("#sourceVisualsGallery button").click()
    expect(page.locator("#sourceVisualsGallery button")).to_have_attribute("aria-pressed", "true")
    assert viewport.evaluate("el => el.scrollWidth > el.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    viewport.evaluate("el => { el.scrollLeft = el.scrollWidth; }")
    page.screenshot(path=str(ARTIFACTS / "original-mobile.png"), full_page=True)
    page.locator("#sourceVisualsPanel").screenshot(path=str(ARTIFACTS / "original-panel-mobile.png"))
    page.locator("#sourceVisualsGallery button").click()
    expect(page.locator("#sourceVisualsGallery button")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#imageDescriptionInput")).to_have_value(note)
    page.screenshot(path=str(ARTIFACTS / "fit-mobile.png"), full_page=True)
    page.locator("#sourceVisualsPanel").screenshot(path=str(ARTIFACTS / "fit-panel-mobile.png"))
    assert len(renderer.calls) == 1


def test_empty_capture_is_explicit_and_does_not_claim_understanding(visuals):
    page, _, _, _, renderer = visuals
    upload(page, [("lesson.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", document("Only text"))])
    renderer.empty = True
    page.locator("#prepareSourceVisuals").click()
    expect(page.locator("#sourceVisualsEmpty")).to_contain_text("Không có hình để hiển thị")
    expect(page.locator("#sourceVisualsEmpty")).to_contain_text("không phải xác nhận nội dung đã được AI hiểu")
    expect(page.locator("#sourceVisualsGallery img")).to_have_count(0)
    expect(page.locator("#prepareSourceVisuals")).to_be_disabled()
    assert len(renderer.calls) == 1
