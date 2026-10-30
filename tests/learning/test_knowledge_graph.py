"""Durable user links, source-backed navigation and bounded graph projection."""
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from docx import Document
import pytest

from core.learning import knowledge_graph as module
from core.learning.knowledge_graph import LearningKnowledgeGraph
from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError

OWNER = "a" * 64
OTHER = "b" * 64


def document(*paragraphs):
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


@pytest.fixture
def course(tmp_path):
    library = MaterialLibrary(tmp_path / "targeted_subject")
    collection, _ = library.import_files(OWNER, "course-request-0001", "Java", [
        ("chapter-one/lecture.docx", document("Định nghĩa kế thừa", "Ví dụ runtime dispatch")),
        ("chapter-two/lecture.docx", document("Đối chiếu overriding với overloading", "Bài luyện tập")),
    ])
    return library, collection, LearningKnowledgeGraph(library)


def assert_code(code, function, *args):
    with pytest.raises(MaterialsError) as result:
        function(*args)
    assert result.value.code == code


def test_get_builds_structure_without_creating_any_graph_storage(course):
    library, collection, graph = course
    before = {str(path): path.read_bytes() for path in library.root.rglob("*") if path.is_file()}
    unit = collection["units"][0]
    view = graph.get(OWNER, collection["id"], unit["unit_id"])
    assert view["revision"] == 0 and view["concepts"] == [] and view["related"] == []
    assert view["source_id"] == unit["source_id"] and view["locator"] == unit["locator"]
    assert view["grounding_ready"] is False
    assert {node["type"] for node in view["graph"]["nodes"]} == {"source", "source_unit"}
    assert view["graph"]["edges"][0]["metadata"]["status"] == "deterministic"
    after = {str(path): path.read_bytes() for path in library.root.rglob("*") if path.is_file()}
    assert after == before


def test_normalization_preserves_accents_and_stable_collection_concept_ids(course):
    library, collection, graph = course
    uid = collection["units"][0]["unit_id"]
    first = graph.set_concepts(OWNER, collection["id"], uid, ["  Kế   thừa ", "kế thừa", "Ｒｕｎｔｉｍｅ"], 0)
    assert first["revision"] == 1
    assert {c["label"] for c in first["concepts"]} == {"Kế thừa", "Runtime"}
    retry = graph.set_concepts(OWNER, collection["id"], uid, ["runtime", "KẾ THỪA"], 0)
    assert retry == first
    assert LearningKnowledgeGraph(MaterialLibrary(library.root)).get(OWNER, collection["id"], uid) == first
    second = graph.set_concepts(OWNER, collection["id"], collection["units"][1]["unit_id"], ["Ke thua"], 0)
    assert not ({c["id"] for c in first["concepts"]} & {c["id"] for c in second["concepts"]})
    assert graph.get(OWNER, collection["id"], uid)["related"] == []


def test_related_links_keep_exact_source_and_unit_even_with_same_filenames(course):
    _, collection, graph = course
    first, _, third, _ = collection["units"]
    graph.set_concepts(OWNER, collection["id"], first["unit_id"], ["Kế thừa"], 0)
    graph.set_concepts(OWNER, collection["id"], third["unit_id"], ["Kế thừa", "Other topic"], 0)
    view = graph.get(OWNER, collection["id"], first["unit_id"])
    assert view["related_total"] == 1 and not view["related_truncated"]
    row = view["related"][0]
    assert row["unit_id"] == third["unit_id"] and row["source_id"] == third["source_id"]
    assert row["locator"] == third["locator"] and row["source_name"] == "chapter-two/lecture.docx"
    assert row["excerpt"] == third["text"]
    assert row["concepts"] == view["concepts"]  # Only the shared association is projected.
    assert not any(node["label"] == "Other topic" for node in view["graph"]["nodes"])
    ids = {node["id"] for node in view["graph"]["nodes"]}
    for edge in view["graph"]["edges"]:
        assert edge["source"] in ids and edge["target"] in ids
        if edge["type"] == "related_to_concept":
            assert edge["metadata"]["origin"] == "user"
            assert edge["metadata"]["status"] == "user_confirmed"
            assert edge["metadata"]["source_unit_id"] == edge["source"]


def test_owner_and_collection_boundaries_do_not_merge_identical_content(course):
    library, collection, graph = course
    raw = document("Identical content in two private libraries")
    a, _ = library.import_files(OWNER, "same-request-0001", "A", [("lecture.docx", raw)])
    b, _ = library.import_files(OTHER, "same-request-0001", "B", [("lecture.docx", raw)])
    c, _ = library.import_files(OWNER, "different-request-0001", "C", [("lecture.docx", raw)])
    uid = a["units"][0]["unit_id"]
    assert uid == b["units"][0]["unit_id"] == c["units"][0]["unit_id"]
    saved = graph.set_concepts(OWNER, a["id"], uid, ["Secret concept"], 0)
    assert graph.get(OTHER, b["id"], uid)["concepts"] == []
    assert graph.get(OWNER, c["id"], uid)["concepts"] == []
    other_collection = graph.set_concepts(OWNER, c["id"], uid, ["Secret concept"], 0)
    assert saved["concepts"][0]["id"] != other_collection["concepts"][0]["id"]
    assert_code("not_found", graph.get, OTHER, collection["id"], collection["units"][0]["unit_id"])
    assert_code("not_found", graph.set_concepts, OWNER, c["id"], collection["units"][0]["unit_id"], ["Wrong unit"], 0)
    assert not (library.root / OTHER / "knowledge.sqlite3").exists()


def test_changed_source_version_has_different_units_and_does_not_inherit_links(course):
    library, collection, graph = course
    uid = collection["units"][0]["unit_id"]
    graph.set_concepts(OWNER, collection["id"], uid, ["Kế thừa"], 0)
    updated, _ = library.import_files(OWNER, "new-version-request-0001", "Java new", [
        ("chapter-one/lecture.docx", document("Định nghĩa đã sửa")),
    ])
    unit = updated["units"][0]
    assert unit["unit_id"] != uid
    assert graph.get(OWNER, updated["id"], unit["unit_id"])["concepts"] == []
    assert_code("not_found", graph.get, OWNER, updated["id"], uid)


def test_unlink_relink_prunes_unused_concepts_and_old_empty_retries_conflict(course):
    library, collection, graph = course
    uid = collection["units"][0]["unit_id"]
    original = graph.set_concepts(OWNER, collection["id"], uid, ["Concept"], 0)
    empty = graph.set_concepts(OWNER, collection["id"], uid, [], 1)
    assert empty["revision"] == 2 and empty["concepts"] == []
    assert graph.set_concepts(OWNER, collection["id"], uid, [], 1) == empty
    assert_code("knowledge_conflict", graph.set_concepts, OWNER, collection["id"], uid, [], 0)
    with sqlite3.connect(library.root / OWNER / "knowledge.sqlite3") as connection:
        assert connection.execute("SELECT count(*) FROM concepts").fetchone()[0] == 0
    relink = graph.set_concepts(OWNER, collection["id"], uid, ["concept"], 2)
    assert relink["concepts"][0]["id"] == original["concepts"][0]["id"]
    assert relink["revision"] == 3
    assert_code("knowledge_conflict", graph.set_concepts, OWNER, collection["id"], uid, ["Concept"], 0)


def test_simultaneous_different_edits_have_one_winner(course):
    _, collection, graph = course
    uid = collection["units"][0]["unit_id"]

    def update(label):
        try:
            return graph.set_concepts(OWNER, collection["id"], uid, [label], 0)
        except MaterialsError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(update, ["First", "Second"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert "knowledge_conflict" in results
    assert graph.get(OWNER, collection["id"], uid)["revision"] == 1


@pytest.mark.parametrize("labels,revision", [
    ("concept", 0), ([None], 0), ([""], 0), (["x" * 81], 0),
    (["x"] * 13, 0), (["line\nbreak"], 0), (["a\u202eb"], 0),
    (["\ud800"], 0), (["\udfff"], 0), (["a\0b"], 0), (["a\u200bb"], 0),
    (["\ufdfa" * 5], 0),  # NFKC expansion must also respect the visible label limit.
    (["concept"], True), (["concept"], -1),
])
def test_invalid_input_never_creates_graph_database(course, labels, revision):
    library, collection, graph = course
    assert_code("invalid_concepts", graph.set_concepts, OWNER, collection["id"], collection["units"][0]["unit_id"], labels, revision)
    assert not (library.root / OWNER / "knowledge.sqlite3").exists()


def test_collection_concept_quota_rolls_back_and_replacement_reclaims_unused(course, monkeypatch):
    _, collection, graph = course
    monkeypatch.setattr(module, "MAX_COLLECTION_CONCEPTS", 2)
    first, second = [unit["unit_id"] for unit in collection["units"][:2]]
    before = graph.set_concepts(OWNER, collection["id"], first, ["A", "B"], 0)
    assert_code("knowledge_limit", graph.set_concepts, OWNER, collection["id"], second, ["C"], 0)
    assert graph.get(OWNER, collection["id"], first) == before
    assert graph.get(OWNER, collection["id"], second)["revision"] == 0
    replaced = graph.set_concepts(OWNER, collection["id"], first, ["C", "D"], 1)
    assert {item["label"] for item in replaced["concepts"]} == {"C", "D"}


def test_link_quota_is_independent_and_active_shared_concepts_survive_pruning(course, monkeypatch):
    _, collection, graph = course
    monkeypatch.setattr(module, "MAX_COLLECTION_LINKS", 2)
    first, second, third = [unit["unit_id"] for unit in collection["units"][:3]]
    original = graph.set_concepts(OWNER, collection["id"], first, ["A"], 0)
    graph.set_concepts(OWNER, collection["id"], second, ["A"], 0)
    assert_code("knowledge_limit", graph.set_concepts, OWNER, collection["id"], third, ["A"], 0)
    graph.set_concepts(OWNER, collection["id"], first, [], 1)
    assert graph.get(OWNER, collection["id"], second)["concepts"] == original["concepts"]
    assert graph.set_concepts(OWNER, collection["id"], third, ["A"], 0)["related_total"] == 1


def test_related_projection_has_hard_row_and_excerpt_bounds(tmp_path):
    library = MaterialLibrary(tmp_path)
    collection, _ = library.import_files(OWNER, "large-course-0001", "Bounded", [
        ("many.docx", document(*(f"Paragraph {index}: " + "a" * 500 for index in range(36)))),
    ])
    graph = LearningKnowledgeGraph(library)
    for unit in collection["units"]:
        graph.set_concepts(OWNER, collection["id"], unit["unit_id"], ["Shared"], 0)
    first = collection["units"][0]
    view = graph.get(OWNER, collection["id"], first["unit_id"])
    assert view["related_total"] == 35 and len(view["related"]) == 30 and view["related_truncated"]
    assert all(len(row["excerpt"]) == 300 for row in view["related"])
    assert len(view["graph"]["nodes"]) == 33  # 31 units + one source + one concept.
    assert len(view["graph"]["edges"]) == 62
    assert first["unit_id"] not in {row["unit_id"] for row in view["related"]}


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_database_and_sidecar_symlinks_are_rejected_without_touching_target(course, tmp_path, suffix):
    library, collection, graph = course
    target = tmp_path / "private-target"
    target.write_bytes(b"private")
    link = library.root / OWNER / ("knowledge.sqlite3" + suffix)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Host does not allow creating symlinks")
    uid = collection["units"][0]["unit_id"]
    assert_code("invalid_storage", graph.get, OWNER, collection["id"], uid)
    assert_code("invalid_storage", graph.set_concepts, OWNER, collection["id"], uid, ["A"], 0)
    assert target.read_bytes() == b"private"


def test_broken_database_is_not_silently_replaced(course):
    library, collection, graph = course
    path = library.root / OWNER / "knowledge.sqlite3"
    path.write_bytes(b"not a sqlite database")
    uid = collection["units"][0]["unit_id"]
    assert_code("invalid_storage", graph.get, OWNER, collection["id"], uid)
    assert_code("invalid_storage", graph.set_concepts, OWNER, collection["id"], uid, ["A"], 0)
    assert path.read_bytes() == b"not a sqlite database"


@pytest.mark.parametrize("suffix", ["", "-journal", "-wal", "-shm"])
def test_database_and_sidecar_directories_are_rejected_without_modification(course, suffix):
    library, collection, graph = course
    path = library.root / OWNER / ("knowledge.sqlite3" + suffix)
    path.mkdir()
    sentinel = path / "unrelated-data"
    sentinel.write_bytes(b"keep")
    before = {str(item.relative_to(library.root)): item.read_bytes()
              for item in library.root.rglob("*") if item.is_file()}
    uid = collection["units"][0]["unit_id"]
    assert_code("invalid_storage", graph.get, OWNER, collection["id"], uid)
    assert_code("invalid_storage", graph.set_concepts, OWNER, collection["id"], uid, ["A"], 0)
    after = {str(item.relative_to(library.root)): item.read_bytes()
             for item in library.root.rglob("*") if item.is_file()}
    assert before == after and path.is_dir()


def test_storage_inspection_error_fails_closed_before_sqlite_creation(course, monkeypatch):
    library, collection, graph = course
    original = Path.is_symlink

    def denied_sidecar(path):
        if path.name == "knowledge.sqlite3-journal":
            raise PermissionError("fixture storage inspection denied")
        return original(path)

    monkeypatch.setattr(Path, "is_symlink", denied_sidecar)
    uid = collection["units"][0]["unit_id"]
    assert_code("invalid_storage", graph.get, OWNER, collection["id"], uid)
    assert_code("invalid_storage", graph.set_concepts, OWNER, collection["id"], uid, ["A"], 0)
    assert not (library.root / OWNER / "knowledge.sqlite3").exists()
