"""Concept maps share the existing private material-library access boundary."""
from tests.integration.test_learning_materials_web import BASE, API, materials, page, upload, assert_error
from tests.integration.test_learning_knowledge_web import knowledge_url, link


def test_map_reads_owner_concepts_and_source_positions_without_side_effects(materials):
    client = materials.app.test_client()
    csrf = page(client, "/learn/chat")
    collection = upload(client, csrf, title="Operating systems").get_json()["collection"]
    url = f"{API}/{collection['id']}/map"
    first = client.get(url, base_url=BASE)
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "no-store"
    assert first.headers["X-Content-Type-Options"] == "nosniff"
    assert first.get_json()["map"]["concept_count"] == 0
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))
    unit = collection["units"][0]
    assert link(client, csrf, knowledge_url(collection, unit), ["Semaphore", "Synchronization"]).status_code == 200
    before = {path: path.read_bytes() for path in materials.material_root.rglob("*") if path.is_file()}
    result = client.get(url, base_url=BASE)
    view = result.get_json()["map"]
    assert view["collection"] == {"id": collection["id"], "title": "Operating systems"}
    assert view["concept_count"] == 2 and view["grounding_ready"] is False
    concept = next(node for node in view["graph"]["nodes"] if node["type"] == "concept")
    assert concept["metadata"]["units"][0]["unit_id"] == unit["unit_id"]
    assert concept["metadata"]["units"][0]["locator"] == unit["locator"]
    assert any(edge["type"] == "shared_source" for edge in view["graph"]["edges"])
    assert all(path.read_bytes() == value for path, value in before.items())
    assert client.get(url, base_url=BASE).get_json() == result.get_json()


def test_map_requires_owner_auth_and_never_exposes_foreign_collection(materials, monkeypatch):
    client = materials.app.test_client()
    csrf = page(client)
    collection = upload(client, csrf).get_json()["collection"]
    url = f"{API}/{collection['id']}/map"
    other = materials.app.test_client()
    page(other)
    assert_error(other.get(url, base_url=BASE), 404, "not_found")
    assert_error(materials.app.test_client().get(url, base_url=BASE), 401, "learner_required")
    monkeypatch.setenv("WEB_AUTH_TOKEN", "map-test-token")
    assert_error(client.get(url, base_url=BASE), 401, "auth_required")
    assert not list(materials.material_root.rglob("knowledge.sqlite3"))
