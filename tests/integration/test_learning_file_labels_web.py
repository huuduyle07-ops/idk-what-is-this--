"""File-label review through actual ownership, mutation and model boundaries."""
from __future__ import annotations

import json

import pytest

from tests.integration.test_learning_materials_web import (
    API, BASE, assert_error, materials, page, upload,
)
from core.learning.store import LearningError


LABELS = {"subject": "Computer Science", "topics": ["Inheritance"],
          "role": "lecture", "language": "English"}


class Classifier:
    def __init__(self):
        self.calls = []
        self.effect = None

    def public_config(self):
        return {"available": True, "provider": "ollama", "model": "fixture", "reason": ""}

    def classify_file(self, excerpts):
        self.calls.append(excerpts)
        if self.effect:
            self.effect()
        return json.dumps({"labels": LABELS, "evidence": [
            {"field": key, "excerpt_id": excerpts[0]["excerpt_id"], "quote": excerpts[0]["text"]}
            for key in LABELS
        ]})


@pytest.fixture
def labeled(materials, monkeypatch):
    client = materials.app.test_client()
    csrf = page(client, "/learn/materials")
    collection = upload(client, csrf).get_json()["collection"]
    responder = Classifier()
    monkeypatch.setitem(materials.app.config, "LEARNING_CHAT_RESPONDER", responder)
    url = f"{API}/{collection['id']}/sources/{collection['sources'][0]['source_id'][7:]}/labels"
    listing = f"{API}/{collection['id']}/labels"
    return client, csrf, collection, responder, url, listing


def mutate(client, csrf, url, body, method="put"):
    return getattr(client, method)(url, base_url=BASE, json=body,
                                   headers={"Origin": BASE, "X-CSRF-Token": csrf})


def test_suggestion_review_confirmation_and_reload_keep_sources_immutable(materials, labeled):
    client, csrf, collection, responder, url, listing = labeled
    before = {path: path.read_bytes() for path in materials.material_root.rglob("*") if path.is_file()}
    response = client.get(listing, base_url=BASE)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    initial = response.get_json()["files"][0]
    assert initial["status"] == "unclassified" and initial["revision"] == 0
    assert responder.calls == []
    proposal = mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post")
    assert proposal.status_code == 200, proposal.get_data(as_text=True)
    record = proposal.get_json()["file"]
    assert record["status"] == "unclassified" and record["labels"] != LABELS
    assert record["suggestion"]["labels"] == LABELS
    assert record["revision"] == 1 and len(responder.calls) == 1
    assert all(e["unit_id"] == collection["units"][0]["unit_id"] for e in record["suggestion"]["evidence"])
    assert client.get(listing, base_url=BASE).get_json()["files"][0] == record
    assert_error(mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post"), 409)
    assert len(responder.calls) == 1
    saved = mutate(client, csrf, url, {"labels": LABELS, "expected_revision": 1})
    assert saved.status_code == 200
    confirmed = saved.get_json()["file"]
    assert confirmed["status"] == "confirmed" and confirmed["labels"] == LABELS
    assert confirmed["suggestion"] is None and confirmed["revision"] == 2
    assert mutate(client, csrf, url, {"labels": LABELS, "expected_revision": 1}).get_json() == saved.get_json()
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))
    assert client.get(f"{API}/{collection['id']}", base_url=BASE).get_json()["collection"] == collection


def test_labels_keep_owner_auth_origin_and_csrf_boundaries(materials, labeled, monkeypatch):
    client, csrf, collection, responder, url, listing = labeled
    other = materials.app.test_client()
    other_csrf = page(other)
    assert_error(other.get(listing, base_url=BASE), 404)
    for endpoint, method, body in ((url, "put", {"labels": LABELS, "expected_revision": 0}),
                                   (url + "/suggest", "post", {"expected_revision": 0})):
        assert_error(mutate(other, other_csrf, endpoint, body, method), 404)
        for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
            assert_error(getattr(client, method)(endpoint, base_url=BASE, json=body, headers=headers), 403)
    assert_error(materials.app.test_client().get(listing, base_url=BASE), 401)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "labels-test-token")
    assert_error(client.get(listing, base_url=BASE), 401)
    assert mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post").status_code in {401, 403}
    assert responder.calls == []
    assert not list(materials.material_root.rglob("labels.json"))


@pytest.mark.parametrize("body", [{}, {"expected_revision": True}, {"expected_revision": -1},
                                  {"expected_revision": 0, "text": "injected source"},
                                  {"expected_revision": "0"}, {"expected_revision": None}])
def test_invalid_suggestion_requests_never_call_model(labeled, body):
    client, csrf, _, responder, url, _ = labeled
    assert_error(mutate(client, csrf, url + "/suggest", body, "post"), 400)
    assert responder.calls == []


def test_save_during_model_call_wins_over_late_suggestion(labeled):
    client, csrf, _, responder, url, listing = labeled
    edited = {**LABELS, "role": "reference"}
    def edit():
        response = mutate(client, csrf, url, {"labels": edited, "expected_revision": 0})
        assert response.status_code == 200
    responder.effect = edit
    assert_error(mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post"), 409)
    record = client.get(listing, base_url=BASE).get_json()["files"][0]
    assert record["labels"] == edited and record["suggestion"] is None


def test_busy_and_failure_release_slot_without_writing(materials, labeled):
    from web.routes.learning_material_routes import _LABEL_SUGGESTION_SLOT
    client, csrf, _, responder, url, listing = labeled
    assert _LABEL_SUGGESTION_SLOT.acquire(blocking=False)
    try:
        assert_error(mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post"), 429, "labels_busy")
    finally:
        _LABEL_SUGGESTION_SLOT.release()
    assert responder.calls == []
    def fail():
        raise LearningError("label_suggestion_provider_error", "Model unavailable", 502)
    responder.effect = fail
    assert_error(mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post"), 502)
    assert client.get(listing, base_url=BASE).get_json()["files"][0]["revision"] == 0
    assert not list(materials.material_root.rglob("labels.json"))
    responder.effect = None
    assert mutate(client, csrf, url + "/suggest", {"expected_revision": 0}, "post").status_code == 200


def test_unknown_file_and_large_body_never_call_provider(labeled):
    client, csrf, collection, responder, url, _ = labeled
    foreign = f"{API}/{collection['id']}/sources/{'f' * 64}/labels/suggest"
    assert_error(mutate(client, csrf, foreign, {"expected_revision": 0}, "post"), 404)
    assert_error(mutate(client, csrf, url, {"labels": {**LABELS, "subject": "x" * 20000}, "expected_revision": 0}), 413)
    assert responder.calls == []
