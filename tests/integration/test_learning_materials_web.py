"""Lecture uploads over the real Flask owner/auth/origin/CSRF boundaries."""
from __future__ import annotations

import io
import json
import re
import uuid

import pytest
from werkzeug.datastructures import MultiDict

from tests.learning.test_document_extractors import pdf, presentation, word
from tests.test_auth_web1 import configure_offline_web


BASE = "http://localhost:5000"
API = "/learn/api/materials"
CSRF = re.compile(r'<meta name="cattus-csrf-token" content="([A-Za-z0-9_-]{43})">')
WORD = word("<w:p><w:r><w:t>Inheritance lesson</w:t></w:r></w:p>")


@pytest.fixture
def materials(tmp_path, monkeypatch):
    state = configure_offline_web(tmp_path, monkeypatch)
    state.material_root = tmp_path / "targeted_subject"
    monkeypatch.setitem(state.app.config, "TARGETED_SUBJECT_ROOT", state.material_root)
    yield state
    assert state.calls == []
    assert not list(state.repo.iterdir())


def page(client, path="/learn"):
    response = client.get(path, base_url=BASE)
    assert response.status_code == 200, response.get_data(as_text=True)
    return CSRF.search(response.get_data(as_text=True)).group(1)


def upload(client, csrf, *, paths=None, contents=None, request_id=None, title="Java lecture", fields=None, origin=BASE):
    paths = ["course/chapter1/lecture.docx"] if paths is None else paths
    contents = [WORD] if contents is None else contents
    body = MultiDict([
        ("title", title), ("request_id", request_id or uuid.uuid4().hex),
        ("paths", json.dumps(paths)),
    ])
    for path, content in zip(paths, contents):
        body.add("files", (io.BytesIO(content), path.rsplit("/", 1)[-1]))
    for key, value in fields or []:
        body.add(key, value)
    headers = {"Origin": origin}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    return client.post(API, base_url=BASE, headers=headers, data=body, content_type="multipart/form-data")


def assert_error(response, status, code=None):
    assert response.status_code == status, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is False
    assert isinstance(payload["error"], str) and payload["error"]
    if code is not None:
        assert payload["error_code"] == code
    return payload


def test_materials_page_sets_durable_learner_cookie_and_private_headers(materials):
    client = materials.app.test_client()
    page(client, "/learn/materials")
    response = client.get(API, base_url=BASE)
    assert response.get_json() == {"ok": True, "collections": []}
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    cookie = client.get_cookie("cattus_learner", domain="localhost", path="/learn")
    assert cookie.http_only and cookie.same_site == "Strict"


def test_upload_real_word_pdf_powerpoint_preserves_locators_and_folder_paths(materials):
    client = materials.app.test_client()
    csrf = page(client)
    paths = ["course/chapter1/lecture.docx", "course/chapter2/slides.pptx", "course/reading.pdf"]
    response = upload(client, csrf, paths=paths, contents=[WORD, presentation(), pdf()])
    assert response.status_code == 201, response.get_data(as_text=True)
    detail = response.get_json()["collection"]
    assert detail["grounding_ready"] is False
    assert detail["status"] == "needs_review"
    assert detail["source_count"] == 3
    assert {path for source in detail["sources"] for path in source["upload_paths"]} == set(paths)
    units = detail["units"]
    assert any(unit["text"] == "Inheritance lesson" and unit["locator"] == {"kind": "paragraph", "index": 1} for unit in units)
    assert any(unit["text"] == "Second file" and unit["locator"] == {"kind": "slide", "index": 1} for unit in units)
    assert any(unit["text"] == "Last page" and unit["locator"] == {"kind": "page", "index": 3} for unit in units)
    assert client.get(f"{API}/{detail['id']}", base_url=BASE).get_json()["collection"] == detail
    listing = client.get(API, base_url=BASE).get_json()["collections"]
    assert len(listing) == 1 and listing[0]["id"] == detail["id"]
    assert "units" not in listing[0]
    assert len(list(materials.material_root.rglob("manifest.json"))) == 1


def test_retry_returns_same_collection_without_duplicate_and_collision_is_conflict(materials):
    client = materials.app.test_client()
    csrf = page(client)
    request_id = uuid.uuid4().hex
    first = upload(client, csrf, request_id=request_id)
    second = upload(client, csrf, request_id=request_id)
    assert first.status_code == 201 and second.status_code == 200
    assert second.get_json() == first.get_json()
    assert_error(upload(client, csrf, request_id=request_id, title="Different lecture"), 409, "request_collision")
    assert len(client.get(API, base_url=BASE).get_json()["collections"]) == 1
    assert len(list(materials.material_root.rglob("manifest.json"))) == 1


def test_many_blank_units_fail_before_publishing_an_unreadable_bundle(materials, monkeypatch):
    from core.learning import materials as corpus

    # Blank units use storage despite contributing no text to the text budget.
    # Lower only the byte budget to exercise this boundary without giant fixtures.
    monkeypatch.setattr(corpus, "MAX_UNITS_BYTES", 1000)
    client = materials.app.test_client()
    csrf = page(client)
    request_id = uuid.uuid4().hex
    for _ in range(2):
        response = upload(client, csrf, contents=[word("<w:p/>" * 20)], request_id=request_id)
        assert_error(response, 413, "document_limit")
        assert client.get(API, base_url=BASE).get_json()["collections"] == []
        assert not materials.material_root.exists()


def test_collection_is_private_to_learner_cookie(materials):
    first = materials.app.test_client()
    first_csrf = page(first)
    detail = upload(first, first_csrf).get_json()["collection"]
    other = materials.app.test_client()
    page(other)
    assert other.get(API, base_url=BASE).get_json()["collections"] == []
    assert_error(other.get(f"{API}/{detail['id']}", base_url=BASE), 404, "not_found")
    anonymous = materials.app.test_client()
    assert_error(anonymous.get(API, base_url=BASE), 401, "learner_required")


def test_mutations_retain_origin_and_csrf_checks(materials):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, None), 403)
    assert_error(upload(client, csrf, origin="http://localhost:7999"), 403)
    assert_error(upload(client, "bad-token"), 403)
    assert client.get(API, base_url=BASE).get_json()["collections"] == []
    assert not materials.material_root.exists()


def test_configured_auth_protects_uploads_and_reads(materials, monkeypatch):
    client = materials.app.test_client()
    csrf = page(client)
    detail = upload(client, csrf).get_json()["collection"]
    monkeypatch.setenv("WEB_AUTH_TOKEN", "lecture-test-token")
    for path in (API, f"{API}/{detail['id']}"):
        assert_error(client.get(path, base_url=BASE), 401, "auth_required")
    denied = upload(client, csrf)
    assert denied.status_code in {401, 403}
    login = client.post("/auth/login", base_url=BASE,
                        headers={"Origin": BASE, "X-CSRF-Token": csrf},
                        data={"web_auth_token": "lecture-test-token"})
    assert login.status_code == 200
    assert client.get(f"{API}/{detail['id']}", base_url=BASE).status_code == 200
    csrf = page(client)
    assert upload(client, csrf).status_code == 201


@pytest.mark.parametrize("relative", ["../outside.docx", "/absolute.docx", "C:/private.docx", "course/../private.docx", "course\\private.docx", "course//lecture.docx"])
def test_unsafe_relative_paths_are_rejected_without_writes(materials, relative):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=[relative]), 400, "invalid_path")
    assert not materials.material_root.exists()


def test_duplicate_paths_are_rejected(materials):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=["lecture.docx", "LECTURE.docx"], contents=[WORD, WORD]), 400, "duplicate_path")
    assert not materials.material_root.exists()


@pytest.mark.parametrize("relative,code", [("notes.exe", "unsupported_format"), ("old.doc", "legacy_format"), ("old.ppt", "legacy_format")])
def test_unsupported_uploads_have_actionable_errors(materials, relative, code):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=[relative]), 400, code)
    assert not materials.material_root.exists()


@pytest.mark.parametrize("extra", [[("unexpected", "value")], [("title", "second title")], [("paths", "[]")]])
def test_unknown_and_duplicate_form_fields_rejected(materials, extra):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, fields=extra), 400, "invalid_request")


def test_mismatched_paths_and_files_rejected(materials):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=["one.docx", "two.docx"], contents=[WORD]), 400, "invalid_request")


def test_more_than_ten_files_rejected(materials):
    client = materials.app.test_client()
    csrf = page(client)
    assert_error(upload(client, csrf, paths=[f"{number}.docx" for number in range(11)], contents=[WORD] * 11), 400, "invalid_request")


def test_actual_file_and_total_byte_limits_are_checked(materials, monkeypatch):
    from web.routes import learning_material_routes as routes
    client = materials.app.test_client()
    csrf = page(client)
    monkeypatch.setattr(routes, "MAX_FILE_BYTES", len(WORD) - 1)
    assert_error(upload(client, csrf), 413, "request_too_large")
    monkeypatch.setattr(routes, "MAX_FILE_BYTES", len(WORD))
    monkeypatch.setattr(routes, "MAX_TOTAL_BYTES", len(WORD))
    assert_error(upload(client, csrf, paths=["first.docx", "second.docx"], contents=[WORD, WORD]), 413, "request_too_large")
    assert not materials.material_root.exists()


class UnreadableStream:
    def read(self, *args, **kwargs):
        raise AssertionError("Rejected body must not be read before the guard")

    def readinto(self, *args, **kwargs):
        raise AssertionError("Rejected body must not be read before the guard")


@pytest.mark.parametrize("length,status,code", [
    (str(65 * 1024 * 1024 + 1), 413, "request_too_large"),
    ("999999999999999999999999", 413, "request_too_large"),
    ("", 411, "length_required"),
    ("-1", 400, "invalid_request"),
])
def test_body_boundary_rejects_before_global_csrf_form_parsing(materials, length, status, code):
    client = materials.app.test_client()
    page(client)
    response = client.post(API, base_url=BASE, headers={"Origin": BASE},
                           content_type="multipart/form-data; boundary=test",
                           environ_overrides={"CONTENT_LENGTH": length, "wsgi.input": UnreadableStream()})
    assert_error(response, status, code)
    assert response.headers["Cache-Control"] == "no-store"
    assert not materials.material_root.exists()


def test_body_guard_also_covers_slash_normalized_upload_path(materials):
    client = materials.app.test_client()
    response = client.post(API + "/", base_url=BASE,
                           headers={"Origin": BASE}, content_type="multipart/form-data; boundary=test",
                           environ_overrides={"CONTENT_LENGTH": str(65 * 1024 * 1024 + 1), "wsgi.input": UnreadableStream()})
    assert_error(response, 413, "request_too_large")


def test_unrelated_json_learning_endpoint_keeps_its_existing_contract(materials, monkeypatch):
    monkeypatch.setitem(materials.app.config, "LEARNING_STORE_PATH", materials.root / "lesson.sqlite3")
    client = materials.app.test_client()
    csrf = page(client)
    response = client.post("/learn/api/sessions", base_url=BASE, json={},
                           headers={"Origin": BASE, "X-CSRF-Token": csrf})
    assert response.status_code == 201
    assert response.get_json()["session"]["total_items"] == 3
