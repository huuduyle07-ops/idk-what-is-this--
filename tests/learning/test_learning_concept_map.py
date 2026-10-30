"""Collection map is a bounded read-only view of explicit source associations."""
import sqlite3

import pytest

from core.learning.knowledge_graph import LearningKnowledgeGraph
from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError
from tests.learning.test_knowledge_graph import OWNER, OTHER, course, document, assert_code
from tests.integration.test_learning_images_web import picture


def nodes(view, kind):
    return [node for node in view["graph"]["nodes"] if node["type"] == kind]


def snapshot(root):
    return {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_empty_concepts_map_shows_source_structure_without_creating_storage(course):
    library, collection, graph = course
    before = snapshot(library.root)
    view = graph.collection_map(OWNER, collection["id"])
    assert view["collection"] == {"id": collection["id"], "title": "Java"}
    assert view["concept_count"] == 0 and view["source_count"] == 2
    assert view["grounding_ready"] is False and view["truncated"] is False
    assert len(nodes(view, "collection")) == 1 and len(nodes(view, "source")) == 2
    assert {edge["type"] for edge in view["graph"]["edges"]} == {"contains_source"}
    first = nodes(view, "source")[0]["metadata"]["units"][0]
    unit = collection["units"][0]
    assert first == {"unit_id": unit["unit_id"], "source_id": unit["source_id"],
                     "source_name": "chapter-one/lecture.docx", "locator": unit["locator"],
                     "excerpt": unit["text"], "origin": "extracted"}
    assert snapshot(library.root) == before


def test_shared_edges_require_same_exact_unit_not_same_file_or_root(course):
    library, collection, graph = course
    first, second, third, _ = collection["units"]
    graph.set_concepts(OWNER, collection["id"], first["unit_id"], ["Semaphore", "Synchronization"], 0)
    graph.set_concepts(OWNER, collection["id"], second["unit_id"], ["ISR"], 0)
    graph.set_concepts(OWNER, collection["id"], third["unit_id"], ["Semaphore"], 0)
    before = snapshot(library.root)
    view = graph.collection_map(OWNER, collection["id"])
    concepts = {node["label"]: node for node in nodes(view, "concept")}
    assert list(concepts) == ["ISR", "Semaphore", "Synchronization"]
    shared = [edge for edge in view["graph"]["edges"] if edge["type"] == "shared_source"]
    assert len(shared) == 1
    assert {shared[0]["source"], shared[0]["target"]} == {concepts["Semaphore"]["id"], concepts["Synchronization"]["id"]}
    assert shared[0]["metadata"] == {"origin": "user", "status": "derived_from_user_links",
                                     "unit_count": 1, "unit_ids": [first["unit_id"]], "units_truncated": False}
    assert concepts["Semaphore"]["metadata"]["unit_count"] == 2
    assert {row["unit_id"] for row in concepts["Semaphore"]["metadata"]["units"]} == {first["unit_id"], third["unit_id"]}
    assert {edge["type"] for edge in view["graph"]["edges"]} <= {"contains_source", "has_concept", "shared_source"}
    assert snapshot(library.root) == before


def test_same_content_never_carries_concepts_across_owners_or_collections(course):
    library, collection, graph = course
    raw = document("same content")
    first, _ = library.import_files(OWNER, "map-same-request-0001", "First", [("same.docx", raw)])
    second, _ = library.import_files(OWNER, "map-other-request-0001", "Second", [("same.docx", raw)])
    other, _ = library.import_files(OTHER, "map-same-request-0001", "Other owner", [("same.docx", raw)])
    graph.set_concepts(OWNER, first["id"], first["units"][0]["unit_id"], ["Private"], 0)
    assert graph.collection_map(OWNER, first["id"])["concept_count"] == 1
    assert graph.collection_map(OWNER, second["id"])["concept_count"] == 0
    assert graph.collection_map(OTHER, other["id"])["concept_count"] == 0
    assert_code("not_found", graph.collection_map, OTHER, collection["id"])
    assert not (library.root / OTHER / "knowledge.sqlite3").exists()


def test_map_bounds_concepts_edges_previews_and_preserves_truncation(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    collection, _ = library.import_files(OWNER, "bounded-map-request-1", "OS", [
        ("os.docx", document(*[("Text " + str(i) + " ") * 200 for i in range(10)]))])
    graph = LearningKnowledgeGraph(library)
    for i, unit in enumerate(collection["units"]):
        labels = [f"A-{j:02d}" for j in range(12)] if i == 0 else [f"Z-{i}-{j}" for j in range(4)]
        graph.set_concepts(OWNER, collection["id"], unit["unit_id"], labels, 0)
    view = graph.collection_map(OWNER, collection["id"])
    assert view["concept_count"] == 48 and len(nodes(view, "concept")) == 30
    assert len([edge for edge in view["graph"]["edges"] if edge["type"] == "shared_source"]) == 60
    assert view["truncated"] is True
    source = nodes(view, "source")[0]["metadata"]
    assert source["unit_count"] == 10 and source["units_truncated"] is True
    for node in view["graph"]["nodes"]:
        assert len(node["metadata"].get("units", [])) <= 5
        assert all(len(unit["excerpt"]) <= 500 for unit in node["metadata"].get("units", []))
    ids = {node["id"] for node in view["graph"]["nodes"]}
    assert all(edge["source"] in ids and edge["target"] in ids for edge in view["graph"]["edges"])


def test_image_preview_is_user_note_with_revision_not_vision(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    collection, _ = library.import_files(OWNER, "image-map-request-01", "Diagrams", [("isr.png", picture())])
    source = collection["sources"][0]
    library.describe_image(OWNER, collection["id"], source["source_id"][7:], "An interrupt handler returns control.", 0)
    graph = LearningKnowledgeGraph(library)
    graph.set_concepts(OWNER, collection["id"], collection["units"][0]["unit_id"], ["ISR"], 0)
    view = graph.collection_map(OWNER, collection["id"])
    note = nodes(view, "concept")[0]["metadata"]["units"][0]
    assert note["origin"] == "user_note" and note["annotation_revision"] == 1
    assert note["excerpt"] == "An interrupt handler returns control."
    assert note["locator"] == {"kind": "image", "index": 1}


def test_stale_orphan_links_do_not_create_phantom_nodes(course):
    library, collection, graph = course
    first = collection["units"][0]
    saved = graph.set_concepts(OWNER, collection["id"], first["unit_id"], ["Current"], 0)
    cid = saved["concepts"][0]["id"]
    with sqlite3.connect(library.root / OWNER / "knowledge.sqlite3") as connection:
        connection.execute("INSERT INTO unit_concepts VALUES (?,?,?)", (collection["id"], "removed-unit", cid))
        connection.execute("INSERT INTO unit_concepts VALUES (?,?,?)", (collection["id"], first["unit_id"], "removed-concept"))
    view = graph.collection_map(OWNER, collection["id"])
    assert view["concept_count"] == 1
    assert nodes(view, "concept")[0]["metadata"]["unit_count"] == 1
    assert all(node["id"] != "removed-concept" for node in view["graph"]["nodes"])


@pytest.mark.parametrize("damage", ["bytes", "schema", "label"])
def test_malformed_graph_fails_closed_without_overwriting_storage(course, damage):
    library, collection, graph = course
    graph.set_concepts(OWNER, collection["id"], collection["units"][0]["unit_id"], ["Current"], 0)
    path = library.root / OWNER / "knowledge.sqlite3"
    if damage == "bytes":
        path.write_bytes(b"not a sqlite database")
    else:
        with sqlite3.connect(path) as connection:
            if damage == "schema":
                connection.execute("PRAGMA user_version=99")
            else:
                connection.execute("UPDATE concepts SET label='wrong normalized label'")
    before = snapshot(library.root)
    assert_code("invalid_storage", graph.collection_map, OWNER, collection["id"])
    assert snapshot(library.root) == before


def test_concept_links_are_read_only_owner_scoped_and_remove_orphans(course):
    library, collection, graph = course
    before = snapshot(library.root)
    assert graph.concept_links(OWNER, collection["id"]) == []
    assert snapshot(library.root) == before
    uid = collection["units"][0]["unit_id"]
    view = graph.set_concepts(OWNER, collection["id"], uid, ["ISR"], 0)
    with sqlite3.connect(library.root / OWNER / "knowledge.sqlite3") as db:
        db.execute("INSERT INTO unit_concepts VALUES (?,?,?)", (collection["id"], "removed-unit", view["concepts"][0]["id"]))
    before = snapshot(library.root)
    assert graph.concept_links(OWNER, collection["id"]) == [{"label": "ISR", "unit_ids": [uid]}]
    assert_code("not_found", graph.concept_links, OTHER, collection["id"])
    assert snapshot(library.root) == before


def test_concept_links_keep_all_labels_beyond_visual_map_cap(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    collection, _ = library.import_files(OWNER, "all-links-map-request", "OS", [
        ("os.docx", document(*[f"Source unit {index}" for index in range(4)]))])
    graph = LearningKnowledgeGraph(library)
    for index, unit in enumerate(collection["units"]):
        graph.set_concepts(OWNER, collection["id"], unit["unit_id"], [f"C{index}-{n:02d}" for n in range(12)], 0)
    result = graph.concept_links(OWNER, collection["id"])
    assert len(result) == 48 and result[-1]["label"] == "C3-11"
    assert result[-1]["unit_ids"] == [collection["units"][-1]["unit_id"]]
    assert len(result) <= 500 and sum(len(row["unit_ids"]) for row in result) <= 5000


def test_concept_links_fail_closed_at_storage_quota(course):
    library, collection, graph = course
    graph.set_concepts(OWNER, collection["id"], collection["units"][0]["unit_id"], ["Current"], 0)
    with sqlite3.connect(library.root / OWNER / "knowledge.sqlite3") as db:
        db.executemany("INSERT INTO concepts VALUES (?,?,?,?)", [
            (collection["id"], f"orphan-{i}", f"orphan-{i}", f"Orphan {i}") for i in range(500)])
    before = snapshot(library.root)
    assert_code("invalid_storage", graph.concept_links, OWNER, collection["id"])
    assert snapshot(library.root) == before
