"""File metadata CAS, evidence provenance and isolation, with no model calls."""
import copy
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image
import pytest

from core.learning.file_labels import FileLabelStore, validate_labels
from core.learning import file_labels as module
from core.learning.knowledge_graph import LearningKnowledgeGraph
from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError
from tests.learning.test_knowledge_graph import OWNER, OTHER, document


LABELS = {"subject": "Operating Systems", "topics": ["Synchronization"], "role": "lecture", "language": "English"}


@pytest.fixture
def course(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    collection, _ = library.import_files(OWNER, "file-labels-request-1", "OS", [
        ("os.docx", document("Operating Systems lecture: synchronization and interrupts.", "An interrupt service routine handles interrupts.")),
        ("other.docx", document("Other material: relational databases.")),
    ])
    return library, collection, FileLabelStore(library)


def digest(collection):
    return collection["sources"][0]["source_id"][7:]


def proposal(collection):
    unit = collection["units"][0]
    return {"labels": copy.deepcopy(LABELS), "evidence": [
        {"field": field, "unit_id": unit["unit_id"], "locator": dict(unit["locator"]),
         "text": unit["text"], "origin": "extracted"} for field in LABELS],
        "provider": "test", "model": "fixture", "sampled_units": 1,
        "total_units": sum(u["source_id"] == unit["source_id"] for u in collection["units"])}


def files(root):
    return {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def failure(code, function, *args):
    with pytest.raises(MaterialsError) as error:
        function(*args)
    assert error.value.code == code


def test_defaults_and_concept_aggregation_are_read_only_without_tag_propagation(course):
    library, collection, store = course
    before = files(library.root)
    initial = store.list(OWNER, collection["id"])
    assert len(initial) == 2 and all(item["revision"] == 0 and item["status"] == "unclassified" for item in initial)
    assert all(item["suggestion"] is None and item["concepts"] == [] for item in initial)
    assert initial[0]["labels"] == {"subject": "", "topics": [], "role": "unknown", "language": "unknown"}
    assert files(library.root) == before
    graph = LearningKnowledgeGraph(library)
    for unit in collection["units"][:2]:
        graph.set_concepts(OWNER, collection["id"], unit["unit_id"], ["ISR"], 0)
    before = files(library.root)
    current = store.get(OWNER, collection["id"], digest(collection))
    assert current["concepts"] == [{"label": "ISR", "unit_count": 2}]
    assert files(library.root) == before
    saved = store.save(OWNER, collection["id"], digest(collection), LABELS, 0)
    assert saved["labels"] == LABELS and saved["concepts"] == current["concepts"]
    assert all(Path(path).read_bytes() == raw for path, raw in before.items())
    assert set(files(library.root)) - set(before) == {str(library.root / OWNER / collection["id"] / "labels.json")}


def test_manual_save_normalizes_survives_reload_and_retries_safely(course):
    library, collection, store = course
    labels = {**LABELS, "subject": "  Operating   Systems ", "topics": [" ＩＳＲ ", "isr", "Synchronization"]}
    saved = store.save(OWNER, collection["id"], digest(collection), labels, 0)
    assert saved["revision"] == 1 and saved["status"] == "confirmed"
    assert saved["labels"]["subject"] == "Operating Systems" and saved["labels"]["topics"] == ["ISR", "Synchronization"]
    assert store.save(OWNER, collection["id"], digest(collection), labels, 0) == saved
    assert store.save(OWNER, collection["id"], digest(collection), labels, 1) == saved
    assert FileLabelStore(MaterialLibrary(library.root)).get(OWNER, collection["id"], digest(collection)) == saved
    changed = {**LABELS, "role": "exercises"}
    failure("file_labels_conflict", store.save, OWNER, collection["id"], digest(collection), changed, 0)
    assert store.save(OWNER, collection["id"], digest(collection), changed, 1)["revision"] == 2
    failure("file_labels_conflict", store.save, OWNER, collection["id"], digest(collection), labels, 0)


def test_suggestion_requires_manual_confirmation_and_never_replaces_labels(course):
    _, collection, store = course
    cid, sha = collection["id"], digest(collection)
    suggestion = proposal(collection)
    pending = store.save_suggestion(OWNER, cid, sha, suggestion, 0)
    assert pending["revision"] == 1 and pending["status"] == "unclassified"
    assert pending["labels"]["subject"] == "" and pending["suggestion"] == suggestion
    assert store.save_suggestion(OWNER, cid, sha, suggestion, 0) == pending
    confirmed = store.save(OWNER, cid, sha, LABELS, 1)
    assert confirmed["revision"] == 2 and confirmed["suggestion"] is None
    next_proposal = copy.deepcopy(suggestion)
    next_proposal["labels"]["role"] = "reference"
    after = store.save_suggestion(OWNER, cid, sha, next_proposal, 2)
    assert after["revision"] == 3 and after["status"] == "confirmed" and after["labels"] == LABELS
    failure("file_labels_conflict", store.save, OWNER, cid, sha, LABELS, 1)


def test_owner_collection_and_digest_isolation(course):
    library, collection, store = course
    sha = digest(collection)
    store.save(OWNER, collection["id"], sha, LABELS, 0)
    failure("not_found", store.get, OTHER, collection["id"], sha)
    failure("not_found", store.save, OTHER, collection["id"], sha, LABELS, 0)
    other, _ = library.import_files(OWNER, "file-labels-request-2", "Other", [("other.docx", document("Unique content"))])
    failure("not_found", store.get, OWNER, other["id"], sha)
    failure("not_found", store.get, OWNER, collection["id"], "../labels.json")
    failure("not_found", store.get, OWNER, collection["id"], "f" * 64)
    assert store.get(OWNER, collection["id"], collection["sources"][1]["source_id"][7:])["status"] == "unclassified"


@pytest.mark.parametrize("value", [None, True, [], 123])
def test_nonstring_digest_is_rejected_without_storage_creation(course, value):
    library, collection, store = course
    failure("not_found", store.get, OWNER, collection["id"], value)
    assert not list(library.root.rglob("labels.json"))


def test_unknown_only_suggestion_can_abstain_without_evidence(course):
    _, collection, store = course
    value = proposal(collection)
    value["labels"] = {"subject": "", "topics": [], "role": "unknown", "language": "unknown"}
    value["evidence"] = []
    saved = store.save_suggestion(OWNER, collection["id"], digest(collection), value, 0)
    assert saved["status"] == "unclassified" and saved["suggestion"]["evidence"] == []


def test_suggestion_sample_count_is_limited_to_eight(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    collection, _ = library.import_files(OWNER, "file-labels-samples-1", "OS", [("os.docx", document(*[f"Unit {i}" for i in range(10)]))])
    value = proposal(collection)
    value["sampled_units"] = 9
    failure("invalid_label_suggestion", FileLabelStore(library).save_suggestion,
            OWNER, collection["id"], digest(collection), value, 0)


@pytest.mark.parametrize("labels", [
    None, [], {}, {**LABELS, "extra": True}, {**LABELS, "subject": 1},
    {**LABELS, "subject": "x" * 121}, {**LABELS, "subject": "bad\ntext"},
    {**LABELS, "subject": "bad\u200btext"}, {**LABELS, "subject": "bad\ud800"},
    {**LABELS, "topics": "Synchronization"}, {**LABELS, "topics": ["x"] * 6},
    {**LABELS, "topics": [""]}, {**LABELS, "topics": ["x" * 81]}, {**LABELS, "topics": [True]},
    {**LABELS, "role": "Lecture"}, {**LABELS, "role": []},
    {**LABELS, "language": "english"}, {**LABELS, "language": True},
])
def test_invalid_labels_never_create_metadata(course, labels):
    library, collection, store = course
    failure("invalid_file_labels", store.save, OWNER, collection["id"], digest(collection), labels, 0)
    assert not list(library.root.rglob("labels.json"))


@pytest.mark.parametrize("revision", [True, -1, "0", 0.0, None, 2**53])
def test_invalid_revisions_are_not_coerced(course, revision):
    _, collection, store = course
    failure("invalid_file_labels", store.save, OWNER, collection["id"], digest(collection), LABELS, revision)


@pytest.mark.parametrize("damage", ["field", "text", "unit", "foreign_unit", "locator", "origin", "extra", "sample_bool", "sample_zero", "sample_large", "total", "uncovered", "too_long", "too_many"])
def test_suggestion_evidence_is_owned_exact_bounded_and_covers_fields(course, damage):
    library, collection, store = course
    value = proposal(collection)
    item = value["evidence"][0]
    if damage == "field": item["field"] = "difficulty"
    elif damage == "text": item["text"] = "Invented quote"
    elif damage == "unit": item["unit_id"] = "unit-invented"
    elif damage == "foreign_unit":
        item.update(unit_id=collection["units"][-1]["unit_id"], locator=collection["units"][-1]["locator"], text=collection["units"][-1]["text"])
    elif damage == "locator": item["locator"] = {"kind": "page", "index": 1}
    elif damage == "origin": item["origin"] = "user_note"
    elif damage == "extra": item["confidence"] = 1
    elif damage == "sample_bool": value["sampled_units"] = True
    elif damage == "sample_zero": value["sampled_units"] = 0
    elif damage == "sample_large": value["sampled_units"] = 3
    elif damage == "total": value["total_units"] = 99
    elif damage == "uncovered": value["evidence"] = value["evidence"][:1]
    elif damage == "too_long": item["text"] = "x" * 1001
    elif damage == "too_many": value["evidence"] *= 4
    failure("invalid_label_suggestion", store.save_suggestion, OWNER, collection["id"], digest(collection), value, 0)
    assert not list(library.root.rglob("labels.json"))


def test_image_suggestion_tracks_note_revision_and_staleness(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    image = io.BytesIO()
    Image.new("RGB", (10, 10)).save(image, "PNG")
    collection, _ = library.import_files(OWNER, "file-labels-image-01", "OS", [("diagram.png", image.getvalue())])
    sha = digest(collection)
    library.describe_image(OWNER, collection["id"], sha, "Operating systems: interrupt handling diagram.", 0)
    collection = library.get(OWNER, collection["id"])
    value = proposal(collection)
    for item in value["evidence"]:
        item.update(text="interrupt handling diagram", origin="user_note", annotation_revision=1)
    store = FileLabelStore(library)
    saved = store.save_suggestion(OWNER, collection["id"], sha, value, 0)
    assert saved["suggestion_stale"] is False
    library.describe_image(OWNER, collection["id"], sha, "Corrected: memory allocation diagram.", 1)
    stale = store.get(OWNER, collection["id"], sha)
    assert stale["suggestion_stale"] is True and stale["suggestion"] == saved["suggestion"]
    failure("invalid_label_suggestion", store.save_suggestion, OWNER, collection["id"], sha, value, 1)
    assert store.save(OWNER, collection["id"], sha, LABELS, 1)["suggestion"] is None


@pytest.mark.parametrize("damage", ["json", "schema", "duplicate", "unknown_source", "revision", "labels", "evidence", "oversize"])
def test_corrupt_storage_fails_closed_and_is_not_overwritten(course, damage):
    library, collection, store = course
    store.save_suggestion(OWNER, collection["id"], digest(collection), proposal(collection), 0)
    path = library.root / OWNER / collection["id"] / "labels.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    row = data["files"][collection["sources"][0]["source_id"]]
    if damage == "json": raw = b"broken"
    elif damage == "duplicate": raw = b'{"schema_version":"a","schema_version":"b","files":{}}'
    elif damage == "oversize": raw = b" " * (module.MAX_LABELS_BYTES + 1)
    else:
        if damage == "schema": data["schema_version"] = "future"
        elif damage == "unknown_source": data["files"]["sha256:" + "f" * 64] = row
        elif damage == "revision": row["revision"] = True
        elif damage == "labels": row["labels"]["topics"] = "not a list"
        elif damage == "evidence": row["suggestion"]["evidence"][0]["text"] = "wrong quote"
        raw = json.dumps(data).encode()
    path.write_bytes(raw)
    failure("invalid_storage", store.get, OWNER, collection["id"], digest(collection))
    failure("invalid_storage", store.save, OWNER, collection["id"], digest(collection), LABELS, 1)
    assert path.read_bytes() == raw


def test_failed_atomic_replace_preserves_previous_data_and_cleans_temp(course, monkeypatch):
    library, collection, store = course
    saved = store.save(OWNER, collection["id"], digest(collection), LABELS, 0)
    before = files(library.root)
    monkeypatch.setattr(module.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("blocked")))
    failure("write_failed", store.save, OWNER, collection["id"], digest(collection), {**LABELS, "role": "reference"}, 1)
    assert files(library.root) == before
    assert store.get(OWNER, collection["id"], digest(collection)) == saved


def test_storage_byte_limit_rejects_before_publishing_a_file(course, monkeypatch):
    library, collection, store = course
    before = files(library.root)
    monkeypatch.setattr(module, "MAX_LABELS_BYTES", 100)
    failure("file_labels_limit", store.save, OWNER, collection["id"], digest(collection), LABELS, 0)
    assert files(library.root) == before


def test_metadata_path_symlinks_and_directories_are_rejected(course, monkeypatch):
    library, collection, store = course
    path = library.root / OWNER / collection["id"] / "labels.json"
    path.mkdir()
    failure("invalid_storage", store.get, OWNER, collection["id"], digest(collection))
    path.rmdir()
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: True if p == path else original(p))
    failure("invalid_storage", store.save, OWNER, collection["id"], digest(collection), LABELS, 0)
    assert not path.exists()


def test_concurrent_writers_do_not_overwrite_same_revision(course):
    _, collection, store = course
    def save(role):
        try:
            return store.save(OWNER, collection["id"], digest(collection), {**LABELS, "role": role}, 0)["revision"]
        except MaterialsError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, ["reference", "exercises"]))
    assert sorted(map(str, results)) == ["1", "file_labels_conflict"]
