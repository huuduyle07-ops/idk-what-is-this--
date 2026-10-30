"""Images and user notes over the actual lecture ownership/auth boundaries."""
import hashlib
import io
import json

from PIL import Image
import pytest

from core.learning import material_library
from tests.integration.test_learning_materials_web import (
    API, BASE, WORD, assert_error, materials, page, upload,
)


def picture(format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (80, 60), (32, 90, 70)).save(output, format=format)
    return output.getvalue()


def import_picture(state, *, format="PNG", filename="diagram.png"):
    client = state.app.test_client()
    csrf = page(client, "/learn/materials")
    raw = picture(format)
    response = upload(client, csrf, paths=[filename], contents=[raw])
    assert response.status_code == 201, response.get_data(as_text=True)
    detail = response.get_json()["collection"]
    source = detail["sources"][0]
    image_url = source["image_url"]
    return client, csrf, detail, source, raw, image_url, image_url.removesuffix("/image") + "/description"


def describe(client, csrf, url, text, revision=0, **kwargs):
    return client.put(url, base_url=BASE, json={"text": text, "expected_revision": revision},
                      headers={"Origin": BASE, "X-CSRF-Token": csrf}, **kwargs)


@pytest.mark.parametrize("filename,format,mime", [("diagram.png", "PNG", "image/png"),
                                                 ("photo.jpg", "JPEG", "image/jpeg"),
                                                 ("photo.jpeg", "JPEG", "image/jpeg")])
def test_image_import_original_bytes_and_review_state(materials, filename, format, mime):
    client, _, detail, source, raw, image_url, _ = import_picture(materials, format=format, filename=filename)
    assert detail["status"] == source["status"] == "needs_visual_review"
    assert not detail["grounding_ready"] and detail["chunk_count"] == 0
    assert detail["units"][0]["locator"] == {"kind": "image", "index": 1}
    assert detail["units"][0]["text"] == ""
    assert source["image"] == {"width": 80, "height": 60, "mime_type": mime}
    assert source["description"] == {"text": "", "revision": 0, "origin": "user"}
    assert source["source_id"] == "sha256:" + hashlib.sha256(raw).hexdigest()
    response = client.get(image_url, base_url=BASE)
    assert response.status_code == 200 and response.data == raw
    assert response.mimetype == mime
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "sandbox" in response.headers["Content-Security-Policy"]


def test_jpg_alias_dedup_and_mixed_source_provenance(materials):
    client = materials.app.test_client()
    csrf = page(client)
    raw = picture("JPEG")
    response = upload(client, csrf, paths=["course/a.jpg", "course/b.jpeg", "course/text.docx"], contents=[raw, raw, WORD])
    assert response.status_code == 201
    detail = response.get_json()["collection"]
    assert detail["status"] == "needs_review" and detail["source_count"] == 2
    images = [source for source in detail["sources"] if "image" in source]
    assert images[0]["original_names"] == ["course/a.jpg", "course/b.jpeg"]
    assert images[0]["upload_paths"] == images[0]["original_names"]
    assert all("image_url" not in source for source in detail["sources"] if source["format"] == "docx")


def test_image_and_notes_are_scoped_to_owner_and_auth(materials, monkeypatch):
    client, csrf, _, _, _, image_url, note_url = import_picture(materials)
    other = materials.app.test_client()
    other_csrf = page(other)
    assert_error(other.get(image_url, base_url=BASE), 404, "not_found")
    assert_error(describe(other, other_csrf, note_url, "not mine"), 404, "not_found")
    assert_error(materials.app.test_client().get(image_url, base_url=BASE), 401, "learner_required")
    monkeypatch.setenv("WEB_AUTH_TOKEN", "image-test-token")
    assert_error(client.get(image_url, base_url=BASE), 401, "auth_required")
    assert describe(client, csrf, note_url, "locked").status_code in {401, 403}
    login = client.post("/auth/login", base_url=BASE, data={"web_auth_token": "image-test-token"},
                        headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert login.status_code == 200
    assert client.get(image_url, base_url=BASE).status_code == 200


def test_notes_require_origin_and_csrf(materials):
    client, csrf, _, _, _, _, note_url = import_picture(materials)
    body = {"text": "new", "expected_revision": 0}
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.put(note_url, base_url=BASE, json=body, headers=headers), 403)
    assert not list(materials.material_root.rglob("annotations.json"))


def test_notes_are_durable_user_data_separate_from_source_and_chunks(materials):
    client, csrf, detail, source, raw, image_url, note_url = import_picture(materials)
    folder = next(materials.material_root.rglob("manifest.json")).parent
    originals = {name: (folder / name).read_bytes() for name in ("manifest.json", "units.jsonl", "chunks.jsonl")}
    text = '<img src=x onerror="alert(1)">\nĐây là ghi chú của tôi, chưa phải OCR.'
    saved = describe(client, csrf, note_url, text)
    assert saved.status_code == 200
    assert saved.get_json()["description"] == {"text": text, "revision": 1, "origin": "user"}
    assert describe(client, csrf, note_url, text).get_json() == saved.get_json()  # Lost acknowledgement retry.
    reloaded = client.get(f"{API}/{detail['id']}", base_url=BASE).get_json()["collection"]
    assert reloaded["sources"][0]["description"] == saved.get_json()["description"]
    assert reloaded["status"] == "needs_visual_review" and not reloaded["grounding_ready"]
    assert all((folder / name).read_bytes() == before for name, before in originals.items())
    assert client.get(image_url, base_url=BASE).data == raw
    assert json.loads((folder / "annotations.json").read_text(encoding="utf-8"))[source["source_id"]]["origin"] == "user"
    assert_error(describe(client, csrf, note_url, "stale tab", 0), 409, "description_conflict")
    assert describe(client, csrf, note_url, "", 1).get_json()["description"] == {"text": "", "revision": 2, "origin": "user"}


@pytest.mark.parametrize("text,revision", [("a" * 4001, 0), (12, 0), ("note", True), ("note", -1), ("note", "0"), ("\ud800", 0)])
def test_invalid_notes_do_not_write(materials, text, revision):
    client, csrf, _, _, _, _, url = import_picture(materials)
    assert_error(describe(client, csrf, url, text, revision), 400, "invalid_description")
    assert not list(materials.material_root.rglob("annotations.json"))


def test_oversized_note_request_is_bounded(materials):
    client, csrf, _, _, _, _, url = import_picture(materials)
    assert_error(describe(client, csrf, url, "x" * 20000), 413)


def test_failed_note_write_keeps_last_saved_revision(materials, monkeypatch):
    client, csrf, detail, _, _, _, url = import_picture(materials)
    assert describe(client, csrf, url, "saved").status_code == 200

    def failed_replace(*args):
        raise OSError("simulated disk error")

    monkeypatch.setattr(material_library.os, "replace", failed_replace)
    assert_error(describe(client, csrf, url, "unsaved", 1), 500, "write_failed")
    source = client.get(f"{API}/{detail['id']}", base_url=BASE).get_json()["collection"]["sources"][0]
    assert source["description"] == {"text": "saved", "revision": 1, "origin": "user"}
    assert not list(materials.material_root.rglob(".annotations-*.tmp"))


def test_tampered_snapshot_is_not_served(materials):
    client, _, _, _, _, image_url, _ = import_picture(materials)
    path = next(materials.material_root.rglob("sources/*.png"))
    path.write_bytes(b"<script>untrusted replacement</script>")
    assert_error(client.get(image_url, base_url=BASE), 500, "invalid_collection")


def test_document_source_cannot_be_served_or_described_as_image(materials):
    client = materials.app.test_client()
    csrf = page(client)
    detail = upload(client, csrf).get_json()["collection"]
    digest = detail["sources"][0]["source_id"][7:]
    prefix = f"{API}/{detail['id']}/sources/{digest}"
    assert_error(client.get(prefix + "/image", base_url=BASE), 404, "not_found")
    assert_error(describe(client, csrf, prefix + "/description", "note"), 404, "not_found")


def test_disguised_image_upload_rejected_before_storage(materials):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=["diagram.png"], contents=[b"<svg onload='alert(1)'/>"]), 400, "invalid_image")
    assert not materials.material_root.exists()
