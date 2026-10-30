"""Explicit visual preparation through real learner/auth/source boundaries."""
import hashlib
import io
import shutil
import tempfile

from PIL import Image, ImageDraw
import pytest

from core.learning.materials import MaterialsError
from tests.integration.test_learning_materials_web import BASE, assert_error, materials, page, upload
from tests.learning.test_document_extractors import pdf


def picture():
    image = Image.new("RGB", (640, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 60, 180, 170), outline="black", width=3)
    draw.rectangle((420, 60, 600, 170), outline="black", width=3)
    draw.line((180, 115, 420, 115), fill="black", width=3)
    draw.text((70, 110), "Input", fill="black")
    draw.text((470, 110), "Model", fill="black")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def visuals(materials, monkeypatch):
    calls = []
    raw_image = picture()

    def renderer(raw, source_format, locator):
        calls.append((hashlib.sha256(raw).hexdigest(), source_format, locator))
        return {"version": "source-visuals-v1", "status": "ready", "warnings": ["Not interpreted by AI."],
                "visuals": [{"kind": "page_render", "mime_type": "image/png", "bytes": raw_image,
                             "width": 640, "height": 240, "locator": locator, "native_part": None,
                             "bbox": [0, 0, 1, 1], "warnings": []}]}

    monkeypatch.setitem(materials.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", renderer)
    client = materials.app.test_client()
    csrf = page(client, "/learn/materials")
    response = upload(client, csrf, paths=["ml/lesson.pdf"], contents=[pdf(("First page", "Second page"))])
    assert response.status_code == 201
    collection = response.get_json()["collection"]
    unit = collection["units"][0]
    endpoint = f"/learn/api/materials/{collection['id']}/units/{unit['unit_id']}/visuals"
    return materials, client, csrf, collection, unit, endpoint, calls, raw_image


def prepare(state, body=None, headers=None):
    _, client, csrf, _, _, endpoint, _, _ = state
    return client.post(endpoint, base_url=BASE, json={} if body is None else body,
                       headers={"Origin": BASE, "X-CSRF-Token": csrf} if headers is None else headers)


def test_read_is_inert_prepare_is_cached_and_image_has_exact_provenance(visuals):
    state, client, _, collection, unit, endpoint, calls, raw = visuals
    folder = next(state.material_root.rglob("manifest.json")).parent
    originals = {name: (folder / name).read_bytes() for name in ("manifest.json", "units.jsonl", "chunks.jsonl")}
    response = client.get(endpoint, base_url=BASE)
    assert response.status_code == 200
    assert response.get_json()["record"]["status"] == "unprepared"
    assert not calls and not (folder / "visuals").exists()
    response = prepare(visuals)
    assert response.status_code == 200, response.get_data(as_text=True)
    record = response.get_json()["record"]
    assert record["source_id"] == unit["source_id"] and record["unit_id"] == unit["unit_id"]
    assert record["locator"] == {"kind": "page", "index": 1}
    assert record["status"] == "ready" and len(record["visuals"]) == 1
    assert len(calls) == 1 and calls[0][1:] == ("pdf", unit["locator"])
    assert prepare(visuals).get_json()["record"] == record
    assert client.get(endpoint, base_url=BASE).get_json()["record"] == record and len(calls) == 1
    visual = record["visuals"][0]
    assert "bytes" not in visual and "path" not in visual
    image = client.get(visual["image_url"], base_url=BASE)
    assert image.status_code == 200 and image.data == raw and image.mimetype == "image/png"
    assert image.headers["Cache-Control"] == "no-store"
    assert image.headers["X-Content-Type-Options"] == "nosniff"
    assert "inline" in image.headers["Content-Disposition"]
    assert all((folder / name).read_bytes() == content for name, content in originals.items())
    assert not (folder / "annotations.json").exists()


def test_visual_records_and_bytes_are_isolated_by_owner_and_auth(visuals, monkeypatch):
    state, client, _, _, _, endpoint, _, _ = visuals
    record = prepare(visuals).get_json()["record"]
    image_url = record["visuals"][0]["image_url"]
    other = state.app.test_client()
    other_csrf = page(other, "/learn/materials")
    for url in (endpoint, image_url):
        assert_error(other.get(url, base_url=BASE), 404)
        assert_error(state.app.test_client().get(url, base_url=BASE), 401)
    assert_error(other.post(endpoint, base_url=BASE, json={}, headers={"Origin": BASE, "X-CSRF-Token": other_csrf}), 404)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "visual-test-only-token")
    assert_error(client.get(endpoint, base_url=BASE), 401, "auth_required")
    assert_error(client.get(image_url, base_url=BASE), 401, "auth_required")


def test_prepare_requires_csrf_and_same_origin_before_rendering(visuals):
    _, _, csrf, _, _, _, calls, _ = visuals
    for headers in ({"Origin": BASE}, {"Origin": "https://example.invalid", "X-CSRF-Token": csrf}):
        assert_error(prepare(visuals, headers=headers), 403)
    assert not calls


@pytest.mark.parametrize("body", [{"source_path": "C:/private.pdf"}, {"model": "cloud"}, {"bbox": [0, 0, 1, 1]}, [], False])
def test_client_cannot_choose_files_models_or_inject_geometry(visuals, body):
    assert_error(prepare(visuals, body=body), 400)
    assert visuals[6] == []


def test_body_size_limit_precedes_preparation(visuals):
    assert_error(prepare(visuals, body={"text": "x" * 2048}), 413)
    assert visuals[6] == []


def test_unknown_unit_and_visual_never_open_unrelated_source(visuals):
    _, client, csrf, collection, _, endpoint, calls, _ = visuals
    unknown = f"/learn/api/materials/{collection['id']}/units/unit-{'f' * 64}/visuals"
    assert_error(client.get(unknown, base_url=BASE), 404)
    assert_error(client.post(unknown, base_url=BASE, json={}, headers={"Origin": BASE, "X-CSRF-Token": csrf}), 404)
    assert_error(client.get(endpoint + "/" + "f" * 64 + "/image", base_url=BASE), 404)
    assert not calls


def test_missing_renderer_does_not_publish_partial_data_or_retry_implicitly(visuals, monkeypatch):
    state, client, _, _, _, endpoint, calls, _ = visuals
    def unavailable(*args):
        raise MaterialsError("visual_unavailable", "Renderer missing.")
    monkeypatch.setitem(state.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", unavailable)
    assert_error(prepare(visuals), 503, "visual_unavailable")
    assert client.get(endpoint, base_url=BASE).get_json()["record"]["status"] == "unprepared"
    assert not calls and not list(state.material_root.rglob("record.json"))


def test_changed_source_invalidates_cached_visual_access(visuals):
    state, client, _, _, _, endpoint, _, _ = visuals
    record = prepare(visuals).get_json()["record"]
    original = next(state.material_root.rglob("sources/*.pdf"))
    original.write_bytes(b"changed source")
    assert_error(client.get(endpoint, base_url=BASE), 409, "visual_source_changed")
    assert_error(client.get(record["visuals"][0]["image_url"], base_url=BASE), 409, "visual_source_changed")
    assert_error(prepare(visuals), 409, "visual_source_changed")


def test_partial_visuals_do_not_claim_document_has_been_understood(visuals, monkeypatch):
    state, _, _, _, _, _, _, _ = visuals
    monkeypatch.setitem(state.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", lambda *args: {
        "version": "source-visuals-v1", "status": "partial",
        "warnings": ["No complete page render is available; no OCR or interpretation was performed."], "visuals": []})
    response = prepare(visuals)
    assert response.status_code == 200
    record = response.get_json()["record"]
    assert record["status"] == "partial" and record["visuals"] == [] and record["warnings"]


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler renderer not installed")
def test_real_pdf_renderer_passes_store_and_http_provenance_checks(visuals, monkeypatch, tmp_path):
    state, client, csrf, collection, _, _, _, _ = visuals
    monkeypatch.setitem(state.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", None)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    unit = collection["units"][1]
    endpoint = f"/learn/api/materials/{collection['id']}/units/{unit['unit_id']}/visuals"
    response = client.post(endpoint, base_url=BASE, json={}, headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert response.status_code == 200, response.get_data(as_text=True)
    record = response.get_json()["record"]
    assert record["status"] == "ready" and record["locator"] == {"kind": "page", "index": 2}
    visual = record["visuals"][0]
    assert visual["kind"] == "page_render" and visual["bbox"] == [0, 0, 1, 1]
    image = client.get(visual["image_url"], base_url=BASE)
    assert image.status_code == 200
    with Image.open(io.BytesIO(image.data)) as result:
        assert result.format == "PNG" and result.size == (visual["width"], visual["height"])


def test_real_standalone_image_uses_original_source_and_no_model(visuals, monkeypatch):
    state, client, csrf, _, _, _, calls, raw = visuals
    monkeypatch.setitem(state.app.config, "LEARNING_SOURCE_VISUAL_RENDERER", None)
    response = upload(client, csrf, paths=["images/architecture.png"], contents=[raw])
    collection = response.get_json()["collection"]
    unit = collection["units"][0]
    endpoint = f"/learn/api/materials/{collection['id']}/units/{unit['unit_id']}/visuals"
    response = client.post(endpoint, base_url=BASE, json={}, headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert response.status_code == 200, response.get_data(as_text=True)
    record = response.get_json()["record"]
    assert record["visuals"][0]["kind"] == "source_image"
    assert client.get(record["visuals"][0]["image_url"], base_url=BASE).data == raw
    assert calls == []
