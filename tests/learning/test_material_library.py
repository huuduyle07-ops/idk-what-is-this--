import io
import json

from docx import Document
import pytest

from core.learning import material_library as library_module
from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError

OWNER = "a" * 64
OTHER = "b" * 64
REQUEST = "first-request-0001"


def source_bytes(text="Một bài giảng để đọc và đối chiếu."):
    document = Document()
    document.add_paragraph(text)
    target = io.BytesIO()
    document.save(target)
    return target.getvalue()


def test_owner_scoped_import_preserves_relative_paths_and_survives_reload(tmp_path):
    library = MaterialLibrary(tmp_path / "targeted_subject")
    raw = source_bytes()
    collection, created = library.import_files(OWNER, REQUEST, "Java cơ bản", [("Java/Chương 1/bài.docx", raw)])
    assert created and collection["status"] == "needs_review"
    assert collection["grounding_ready"] is False
    assert collection["sources"][0]["upload_paths"] == ["Java/Chương 1/bài.docx"]
    assert collection["units"][0]["text"].startswith("Một bài giảng")
    reloaded = MaterialLibrary(library.root)
    assert reloaded.get(OWNER, collection["id"]) == collection
    assert reloaded.list(OWNER)[0]["id"] == collection["id"]
    assert reloaded.list(OTHER) == []
    with pytest.raises(MaterialsError) as missing:
        reloaded.get(OTHER, collection["id"])
    assert missing.value.code == "not_found"
    assert not (library.root / "Java").exists()  # Client paths never choose server destinations.


def test_exact_retry_returns_one_collection_and_changed_payload_rejected(tmp_path):
    library = MaterialLibrary(tmp_path)
    uploads = [("java.docx", source_bytes())]
    first, created = library.import_files(OWNER, REQUEST, "Java", uploads)
    again, created_again = library.import_files(OWNER, REQUEST, "Java", uploads)
    assert created and not created_again and again == first
    assert len(library.list(OWNER)) == 1
    with pytest.raises(MaterialsError) as collision:
        library.import_files(OWNER, REQUEST, "Different title", uploads)
    assert collision.value.code == "request_collision"
    assert len(library.list(OWNER)) == 1


@pytest.mark.parametrize("path", ["../escape.docx", "/outside.docx", "C:/outside.docx", "folder\\file.docx", "folder//file.docx", "./file.docx"])
def test_client_paths_cannot_escape_selected_folder(tmp_path, path):
    library = MaterialLibrary(tmp_path / "targeted_subject")
    with pytest.raises(MaterialsError) as invalid:
        library.import_files(OWNER, REQUEST, "Java", [(path, source_bytes())])
    assert invalid.value.code == "invalid_path"
    assert not library.root.exists()


def test_duplicate_paths_rejected_but_duplicate_bytes_preserve_both_references(tmp_path):
    library = MaterialLibrary(tmp_path)
    raw = source_bytes()
    with pytest.raises(MaterialsError) as invalid:
        library.import_files(OWNER, REQUEST, "Java", [("a.docx", raw), ("A.docx", raw)])
    assert invalid.value.code == "duplicate_path"
    collection, _ = library.import_files(OWNER, REQUEST, "Java", [("a.docx", raw), ("copy/a.docx", raw)])
    assert collection["source_count"] == 1
    assert collection["sources"][0]["upload_paths"] == ["a.docx", "copy/a.docx"]


def test_import_failure_has_no_list_entry_and_does_not_replace_old_collection(tmp_path):
    library = MaterialLibrary(tmp_path)
    first, _ = library.import_files(OWNER, REQUEST, "Good", [("ok.docx", source_bytes())])
    with pytest.raises(MaterialsError):
        library.import_files(OWNER, "second-request-0002", "Broken", [("bad.pdf", b"broken")])
    assert [item["id"] for item in library.list(OWNER)] == [first["id"]]
    folder = library.root / OWNER / first["id"]
    (folder / "IMPORT_INCOMPLETE").write_text("interrupted", encoding="utf-8")
    assert library.list(OWNER) == []
    with pytest.raises(MaterialsError) as failure:
        library.import_files(OWNER, REQUEST, "Good", [("ok.docx", source_bytes())])
    assert failure.value.code == "import_incomplete"


def test_library_quota_allows_exact_retry_and_blocks_new_import(tmp_path, monkeypatch):
    library = MaterialLibrary(tmp_path)
    uploads = [("a.docx", source_bytes())]
    first, _ = library.import_files(OWNER, REQUEST, "Java", uploads)
    monkeypatch.setattr(library_module, "MAX_COLLECTIONS", 1)
    assert library.import_files(OWNER, REQUEST, "Java", uploads) == (first, False)
    with pytest.raises(MaterialsError) as limit:
        library.import_files(OWNER, "second-request-0002", "Java", uploads)
    assert limit.value.code == "library_limit"


def test_new_collection_keeps_original_snapshot_when_input_changes(tmp_path):
    library = MaterialLibrary(tmp_path)
    first_raw, second_raw = source_bytes("Version one"), source_bytes("Version two")
    first, _ = library.import_files(OWNER, REQUEST, "Java", [("a.docx", first_raw)])
    second, _ = library.import_files(OWNER, "second-request-0002", "Java", [("a.docx", second_raw)])
    assert first["sources"][0]["source_id"] != second["sources"][0]["source_id"]
    first_folder = library.root / OWNER / first["id"]
    manifest = json.loads((first_folder / "manifest.json").read_text(encoding="utf-8"))
    assert (first_folder / manifest["sources"][0]["stored_path"]).read_bytes() == first_raw
