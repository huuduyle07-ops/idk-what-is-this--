"""Concept connections across lecture formats through the real web boundary."""
from __future__ import annotations

import pytest

from tests.integration.test_learning_materials_web import (
    API, BASE, WORD, assert_error, materials, page, upload,
)
from tests.learning.test_document_extractors import pdf, presentation
from tests.integration.test_learning_images_web import picture


def knowledge_url(collection, unit):
    return f"{API}/{collection['id']}/units/{unit['unit_id']}/knowledge"


def link(client, csrf, url, labels, revision=0):
    return client.put(url + "/concepts", base_url=BASE,
                      json={"labels": labels, "expected_revision": revision},
                      headers={"Origin": BASE, "X-CSRF-Token": csrf})


def imported(state):
    client = state.app.test_client()
    csrf = page(client, "/learn/materials")
    response = upload(client, csrf, paths=["oop/lecture.docx", "oop/reading.pdf", "oop/slides.pptx", "oop/diagram.png"],
                      contents=[WORD, pdf(), presentation(), picture()])
    assert response.status_code == 201
    collection = response.get_json()["collection"]
    return client, csrf, collection


def test_connections_link_exact_word_pdf_slide_and_image_without_changing_sources(materials):
    client, csrf, collection = imported(materials)
    originals = {path: path.read_bytes() for path in materials.material_root.rglob("*") if path.is_file()}
    selected = [next(unit for unit in collection["units"] if unit["locator"] == locator) for locator in (
        {"kind": "paragraph", "index": 1}, {"kind": "page", "index": 3},
        {"kind": "slide", "index": 2}, {"kind": "image", "index": 1},
    )]
    for unit in selected:
        response = link(client, csrf, knowledge_url(collection, unit), ["Kế thừa"])
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()["knowledge"]["revision"] == 1
    response = client.get(knowledge_url(collection, selected[0]), base_url=BASE)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    view = response.get_json()["knowledge"]
    assert view["grounding_ready"] is False
    assert view["related_total"] == 3 and not view["related_truncated"]
    assert {row["unit_id"] for row in view["related"]} == {unit["unit_id"] for unit in selected[1:]}
    source_by_id = {source["source_id"]: source for source in collection["sources"]}
    for row in view["related"]:
        original = next(unit for unit in selected if unit["unit_id"] == row["unit_id"])
        assert row["source_id"] == original["source_id"]
        assert row["locator"] == original["locator"]
        assert row["source_name"] in source_by_id[row["source_id"]]["original_names"]
        assert row["concepts"] == view["concepts"]
        assert row["excerpt"] == original["text"][:300]
    node_ids = {node["id"] for node in view["graph"]["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in view["graph"]["edges"])
    assert all(path.read_bytes() == before for path, before in originals.items())
    assert client.get(f"{API}/{collection['id']}", base_url=BASE).get_json()["collection"] == collection


def test_reads_do_not_create_graph_and_links_survive_new_requests(materials):
    client, csrf, collection = imported(materials)
    url = knowledge_url(collection, collection["units"][0])
    before = {path for path in materials.material_root.rglob("*")}
    view = client.get(url, base_url=BASE).get_json()["knowledge"]
    assert view["revision"] == 0 and view["concepts"] == [] and view["related"] == []
    assert set(materials.material_root.rglob("*")) == before
    saved = link(client, csrf, url, ["Kế thừa"]).get_json()["knowledge"]
    assert client.get(url, base_url=BASE).get_json()["knowledge"] == saved
    assert len(list(materials.material_root.rglob("knowledge.sqlite3"))) == 1
    assert len(client.get(API, base_url=BASE).get_json()["collections"]) == 1


def test_knowledge_requires_owner_auth_origin_and_csrf(materials, monkeypatch):
    client, csrf, collection = imported(materials)
    url = knowledge_url(collection, collection["units"][0])
    other = materials.app.test_client()
    other_csrf = page(other)
    assert_error(other.get(url, base_url=BASE), 404, "not_found")
    assert_error(link(other, other_csrf, url, ["private"]), 404, "not_found")
    assert_error(materials.app.test_client().get(url, base_url=BASE), 401, "learner_required")
    for headers in ({"Origin": BASE}, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}):
        assert_error(client.put(url + "/concepts", base_url=BASE,
                                json={"labels": ["blocked"], "expected_revision": 0}, headers=headers), 403)
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))
    monkeypatch.setenv("WEB_AUTH_TOKEN", "knowledge-test-token")
    assert_error(client.get(url, base_url=BASE), 401, "auth_required")
    assert link(client, csrf, url, ["locked"]).status_code in {401, 403}


def test_collection_namespace_and_foreign_unit_are_enforced(materials):
    client, csrf, first = imported(materials)
    first_unit = first["units"][0]
    first_url = knowledge_url(first, first_unit)
    first_view = link(client, csrf, first_url, ["Kế thừa"]).get_json()["knowledge"]
    second = upload(client, csrf, title="Another course").get_json()["collection"]
    second_unit = second["units"][0]
    second_view = link(client, csrf, knowledge_url(second, second_unit), ["Kế thừa"]).get_json()["knowledge"]
    assert first_view["concepts"][0]["id"] != second_view["concepts"][0]["id"]
    assert client.get(first_url, base_url=BASE).get_json()["knowledge"]["related"] == []
    foreign_unit = next(unit for unit in first["units"] if unit["locator"]["kind"] == "image")
    foreign_url = knowledge_url(second, foreign_unit)
    assert_error(client.get(foreign_url, base_url=BASE), 404, "not_found")
    assert_error(link(client, csrf, foreign_url, ["no"]), 404, "not_found")


def test_retry_conflict_and_unlink_keep_revisions_without_stale_overwrite(materials):
    client, csrf, collection = imported(materials)
    url = knowledge_url(collection, collection["units"][0])
    saved = link(client, csrf, url, ["Kế thừa"])
    assert saved.status_code == 200
    assert link(client, csrf, url, ["  KẾ THỪA  "]).get_json() == saved.get_json()
    assert_error(link(client, csrf, url, ["Đa hình"]), 409, "knowledge_conflict")
    cleared = link(client, csrf, url, [], 1).get_json()["knowledge"]
    assert cleared["revision"] == 2 and cleared["concepts"] == []
    assert_error(link(client, csrf, url, [], 0), 409, "knowledge_conflict")
    assert client.get(url, base_url=BASE).get_json()["knowledge"] == cleared


@pytest.mark.parametrize("body", [
    {}, {"labels": []}, {"labels": [], "expected_revision": 0, "approved": True},
    {"labels": "concept", "expected_revision": 0},
    {"labels": ["a"], "expected_revision": True},
    {"labels": ["\ud800"], "expected_revision": 0},
])
def test_invalid_concept_request_does_not_create_graph(materials, body):
    client, csrf, collection = imported(materials)
    url = knowledge_url(collection, collection["units"][0]) + "/concepts"
    assert_error(client.put(url, base_url=BASE, json=body,
                            headers={"Origin": BASE, "X-CSRF-Token": csrf}), 400)
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))


def test_knowledge_body_is_bounded(materials):
    client, csrf, collection = imported(materials)
    assert_error(link(client, csrf, knowledge_url(collection, collection["units"][0]), ["x" * 20000]), 413)
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))


def test_graph_storage_errors_are_private_and_do_not_change_corpus(materials):
    client, csrf, collection = imported(materials)
    folder = next(materials.material_root.rglob("manifest.json")).parent
    (folder.parent / "knowledge.sqlite3").write_bytes(b"invalid database")
    url = knowledge_url(collection, collection["units"][0])
    for response in (client.get(url, base_url=BASE), link(client, csrf, url, ["test"])):
        body = assert_error(response, 500, "invalid_storage")
        assert str(materials.material_root) not in str(body)
    assert client.get(f"{API}/{collection['id']}", base_url=BASE).get_json()["collection"] == collection
