import copy
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
from threading import Barrier, Lock
import time

from docx import Document
from PIL import Image
import pytest

from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError
from core.learning import source_visual_store as module
from core.learning.source_visual_store import SourceVisualStore

OWNER = "a" * 64
OTHER = "b" * 64


def png(color="red"):
    output = io.BytesIO()
    Image.new("RGB", (20, 12), color).save(output, "PNG")
    return output.getvalue()


def docx():
    output = io.BytesIO()
    document = Document()
    document.add_paragraph("A diagram in a lecture about synchronization.")
    document.add_paragraph("The next section.")
    document.save(output)
    return output.getvalue()


def capture(raw=None, *, locator=None, kind="source_image", part=None, bbox=None, status="ready"):
    return {"version": module.VERSION, "status": status, "warnings": ["Check the original source."],
            "visuals": [{"kind": kind, "mime_type": "image/png", "bytes": raw or png(),
                         "width": 20, "height": 12, "locator": locator or {"kind": "image", "index": 1},
                         "native_part": part, "bbox": [0, 0, 1, 1] if bbox is None and kind != "embedded_image" else bbox,
                         "warnings": []}]}


@pytest.fixture
def source(tmp_path):
    library = MaterialLibrary(tmp_path / "materials")
    raw = png()
    collection, _ = library.import_files(OWNER, "source-request-0001", "Synchronization", [("diagram.png", raw)])
    unit = collection["units"][0]
    folder = library.root / OWNER / collection["id"]
    return library, collection["id"], unit["unit_id"], folder, raw


def prepared(source):
    library, collection, unit, folder, raw = source
    store = SourceVisualStore(library, lambda *_: capture(raw))
    record = store.prepare(OWNER, collection, unit)
    return store, record, folder / "visuals" / unit


def expect_error(code, function, *args):
    with pytest.raises(MaterialsError) as raised:
        function(*args)
    assert raised.value.code == code


def rewrite(path, function):
    value = json.loads(path.read_bytes())
    function(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_unprepared_get_is_read_only_and_old_collections_need_no_reimport(source):
    library, collection, unit, folder, _ = source
    before = {p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    record = SourceVisualStore(library).get(OWNER, collection, unit)
    assert record == {"version": module.VERSION, "status": "unprepared", "source_id": library.get(OWNER, collection)["sources"][0]["source_id"],
                      "unit_id": unit, "locator": {"kind": "image", "index": 1}, "warnings": [], "visuals": []}
    assert not (folder / "visuals").exists()
    assert before == {p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def test_prepare_is_immutable_cached_and_pins_public_provenance_without_paths(source):
    library, collection, unit, folder, raw = source
    original = {name: (folder / name).read_bytes() for name in ("manifest.json", "units.jsonl", "web.json")}
    calls = []

    def renderer(received, fmt, locator):
        calls.append((received, fmt, locator))
        return capture(raw)

    store = SourceVisualStore(library, renderer)
    first = store.prepare(OWNER, collection, unit)
    assert first["status"] == "ready"
    assert len(first["visuals"]) == 1
    visual = first["visuals"][0]
    assert set(first) == {"version", "status", "source_id", "unit_id", "locator", "created_at", "warnings", "visuals"}
    assert set(visual) == {"id", "kind", "mime_type", "width", "height", "locator", "native_part", "bbox", "warnings"}
    assert store.get(OWNER, collection, unit) == first
    assert store.prepare(OWNER, collection, unit) == first
    reloaded = SourceVisualStore(MaterialLibrary(library.root), lambda *_: pytest.fail("cache rerendered"))
    assert reloaded.prepare(OWNER, collection, unit) == first
    assert reloaded.image(OWNER, collection, unit, visual["id"]) == (raw, "image/png")
    assert calls == [(raw, "png", {"kind": "image", "index": 1})]
    assert original == {name: (folder / name).read_bytes() for name in original}
    assert not (folder / "annotations.json").exists()


def test_default_renderer_can_prepare_existing_image_source(source):
    library, collection, unit, _, raw = source
    store = SourceVisualStore(library)
    record = store.prepare(OWNER, collection, unit)
    assert record["status"] == "ready"
    assert store.image(OWNER, collection, unit, record["visuals"][0]["id"]) == (raw, "image/png")


def test_owner_collection_unit_and_image_are_all_scoped(source):
    library, collection, unit, _, _ = source
    store, record, _ = prepared(source)
    visual = record["visuals"][0]["id"]
    for action, args in ((store.get, (OTHER, collection, unit)), (store.prepare, (OTHER, collection, unit)),
                         (store.image, (OTHER, collection, unit, visual)),
                         (store.get, (OWNER, "c" * 32, unit)), (store.get, (OWNER, collection, "unit-" + "c" * 64)),
                         (store.image, (OWNER, collection, unit, "c" * 64))):
        expect_error("visual_not_found", action, *args)
    second, _ = library.import_files(OWNER, "source-request-0002", "Other", [("other.png", png("blue"))])
    expect_error("visual_not_found", store.get, OWNER, second["id"], unit)


@pytest.mark.parametrize("unit", [None, True, "../escape", "unit-" + "A" * 64, "unit-" + "a" * 63])
def test_invalid_unit_ids_never_choose_paths(source, unit):
    library, collection, _, folder, _ = source
    expect_error("visual_not_found", SourceVisualStore(library).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()


@pytest.mark.parametrize("change", ["same_size", "shorter", "deleted"])
@pytest.mark.parametrize("action", ["get", "prepare", "image"])
def test_original_snapshot_is_reverified_for_every_read_and_retry(source, change, action):
    store, record, target = prepared(source)
    _, collection, unit, folder, raw = source
    original = next((folder / "sources").iterdir())
    if change == "deleted":
        original.unlink()
    else:
        original.write_bytes(b"x" * (len(raw) if change == "same_size" else len(raw) - 1))
    before = (target / "record.json").read_bytes()
    args = [OWNER, collection, unit]
    if action == "image":
        args.append(record["visuals"][0]["id"])
    expect_error("visual_source_changed", getattr(store, action), *args)
    assert (target / "record.json").read_bytes() == before


def test_corrupt_unit_locator_is_not_trusted_even_without_capture(source):
    library, collection, unit, folder, _ = source
    path = folder / "units.jsonl"
    entry = json.loads(path.read_bytes())
    entry["locator"]["index"] = 2
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    expect_error("visual_storage_error", SourceVisualStore(library).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()


@pytest.mark.parametrize("mutation", [
    lambda b: b.update(version="future"),
    lambda b: b.update(status="unprepared"),
    lambda b: b.update(extra=True),
    lambda b: b.update(warnings=["\ud800"]),
    lambda b: b["visuals"][0].update(bytes=b"not an image"),
    lambda b: b["visuals"][0].update(mime_type="image/svg+xml"),
    lambda b: b["visuals"][0].update(width=True),
    lambda b: b["visuals"][0].update(height=1801),
    lambda b: b["visuals"][0].update(width=19),
    lambda b: b["visuals"][0].update(locator={"kind": "image", "index": 2}),
    lambda b: b["visuals"][0].update(bbox=[0, 0, 2, 1]),
    lambda b: b["visuals"][0].update(bbox=[False, 0, 1, 1]),
    lambda b: b["visuals"][0].update(bbox=[float("nan"), 0, 1, 1]),
    lambda b: b["visuals"][0].update(native_part="../../outside"),
    lambda b: b["visuals"][0].update(kind="embedded_image"),
    lambda b: b.update(visuals=b["visuals"] * 13),
])
def test_invalid_renderer_output_is_rejected_before_cache_write(source, mutation):
    library, collection, unit, folder, _ = source
    bundle = capture()
    mutation(bundle)
    expect_error("visual_render_failed", SourceVisualStore(library, lambda *_: bundle).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()


def test_partial_empty_result_is_cached_explicitly_not_presented_as_full_layout(source):
    library, collection, unit, _, _ = source
    renderer = lambda *_: {"version": module.VERSION, "status": "partial", "warnings": ["No supported embedded images."], "visuals": []}
    store = SourceVisualStore(library, renderer)
    result = store.prepare(OWNER, collection, unit)
    assert result["status"] == "partial" and not result["visuals"]
    assert store.get(OWNER, collection, unit) == result


def test_docx_occurrences_share_asset_storage_but_keep_distinct_provenance(tmp_path):
    library = MaterialLibrary(tmp_path)
    collection, _ = library.import_files(OWNER, "word-source-00001", "Word", [("lecture.docx", docx())])
    unit = collection["units"][0]
    bundle = capture(locator=unit["locator"], kind="embedded_image", part="word/media/image1.png", status="partial")
    duplicate = copy.deepcopy(bundle["visuals"][0])
    duplicate["native_part"] = "word/media/image2.png"
    bundle["visuals"].append(duplicate)
    store = SourceVisualStore(library, lambda *_: bundle)
    result = store.prepare(OWNER, collection["id"], unit["unit_id"])
    assert result["status"] == "partial"
    assert len({v["id"] for v in result["visuals"]}) == 2
    assert all(v["bbox"] is None for v in result["visuals"])
    target = library.root / OWNER / collection["id"] / "visuals" / unit["unit_id"]
    assert len(list(target.glob("*.png"))) == 1
    assert store.image(OWNER, collection["id"], unit["unit_id"], result["visuals"][0]["id"])[0] == png()


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(version="other"),
    lambda r: r.update(source_id="sha256:" + "f" * 64),
    lambda r: r.update(source_size_bytes=True),
    lambda r: r.update(locator={"kind": "image", "index": 2}),
    lambda r: r.update(extra="not allowed"),
    lambda r: r.update(created_at="2026-01-01T00:00:00"),
    lambda r: r["visuals"][0].update(asset_sha256="f" * 64),
    lambda r: r["visuals"][0].update(id="f" * 64),
    lambda r: r["visuals"][0].update(width=True),
    lambda r: r["visuals"][0].update(bbox=[0, 0, -1, 1]),
    lambda r: r["visuals"][0].update(extra="not allowed"),
    lambda r: r["visuals"].append(copy.deepcopy(r["visuals"][0])),
])
def test_corrupt_saved_record_fails_closed_without_repair_or_rerender(source, mutation):
    store, _, target = prepared(source)
    _, collection, unit, _, _ = source
    path = target / "record.json"
    rewrite(path, mutation)
    corrupt = path.read_bytes()
    store.renderer = lambda *_: pytest.fail("corruption must never trigger an overwrite")
    expect_error("visual_storage_error", store.get, OWNER, collection, unit)
    expect_error("visual_storage_error", store.prepare, OWNER, collection, unit)
    assert path.read_bytes() == corrupt


@pytest.mark.parametrize("content", [b"{", b'{"version":"x","version":"y"}', b"[" * 1100, b"x" * (module.MAX_RECORD_BYTES + 1)],
                         ids=["broken", "duplicate", "deep", "oversize"])
def test_invalid_saved_json_is_bounded_and_fail_closed(source, content):
    store, _, target = prepared(source)
    (target / "record.json").write_bytes(content)
    expect_error("visual_storage_error", store.get, OWNER, source[1], source[2])


@pytest.mark.parametrize("change", ["modify", "remove", "extra"])
def test_asset_tampering_or_untracked_files_fail_closed(source, change):
    store, record, target = prepared(source)
    asset = next(target.glob("*.png"))
    if change == "modify":
        asset.write_bytes(b"x" * asset.stat().st_size)
    elif change == "remove":
        asset.unlink()
    else:
        (target / "untracked.bin").write_bytes(b"untracked")
    for function, args in ((store.get, (OWNER, source[1], source[2])),
                           (store.image, (OWNER, source[1], source[2], record["visuals"][0]["id"]))):
        expect_error("visual_storage_error", function, *args)


@pytest.mark.parametrize("level", ["unit", "collection", "owner"])
def test_all_byte_quotas_include_orphaned_staging_files(source, monkeypatch, level):
    library, collection, unit, folder, _ = source
    owner_folder = folder.parent
    if level == "owner":
        other = owner_folder / ("c" * 32)
        (other / "visuals" / "orphan").mkdir(parents=True)
        (other / "visuals" / "orphan" / "bytes.bin").write_bytes(b"x" * 2000)
        monkeypatch.setattr(module, "MAX_OWNER_BYTES", 2000)
    else:
        stage = folder / "visuals" / (".stage-" + unit + "-interrupted")
        stage.mkdir(parents=True)
        (stage / "partial.bin").write_bytes(b"x" * 2000)
        monkeypatch.setattr(module, "MAX_UNIT_BYTES" if level == "unit" else "MAX_COLLECTION_BYTES", 2000)
    store = SourceVisualStore(library, lambda *_: pytest.fail("full quota should stop before rendering"))
    expect_error("visual_limit", store.prepare, OWNER, collection, unit)
    assert not (folder / "visuals" / unit).exists()


def test_new_capture_is_checked_against_quota_after_render(source, monkeypatch):
    library, collection, unit, folder, _ = source
    monkeypatch.setattr(module, "MAX_UNIT_BYTES", 100)
    expect_error("visual_limit", SourceVisualStore(library, lambda *_: capture()).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()


def test_exact_cached_retry_needs_no_new_quota_even_after_limits_are_lowered(source, monkeypatch):
    store, record, _ = prepared(source)
    for name in ("MAX_UNIT_BYTES", "MAX_COLLECTION_BYTES", "MAX_OWNER_BYTES"):
        monkeypatch.setattr(module, name, 1)
    store.renderer = lambda *_: pytest.fail("cached retry must not render again")
    assert store.prepare(OWNER, source[1], source[2]) == record
    assert store.get(OWNER, source[1], source[2]) == record


def test_renderer_exception_keeps_sources_and_creates_no_cache(source):
    library, collection, unit, folder, raw = source
    def fail(*_):
        raise RuntimeError("private renderer details")
    expect_error("visual_render_failed", SourceVisualStore(library, fail).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()
    assert next((folder / "sources").iterdir()).read_bytes() == raw


def test_source_changed_during_render_never_publishes_capture(source):
    library, collection, unit, folder, raw = source
    def renderer(*_):
        next((folder / "sources").iterdir()).write_bytes(b"x" * len(raw))
        return capture()
    expect_error("visual_source_changed", SourceVisualStore(library, renderer).prepare, OWNER, collection, unit)
    assert not (folder / "visuals").exists()


def test_atomic_publish_failure_cleans_only_own_stage_and_keeps_old_files(source, monkeypatch):
    library, collection, unit, folder, raw = source
    original = Path.rename
    def fail(path, target):
        if path.name.startswith(".stage-"):
            raise OSError("simulated publish failure")
        return original(path, target)
    monkeypatch.setattr(Path, "rename", fail)
    expect_error("visual_storage_error", SourceVisualStore(library, lambda *_: capture()).prepare, OWNER, collection, unit)
    assert not list((folder / "visuals").iterdir())
    assert next((folder / "sources").iterdir()).read_bytes() == raw


def test_concurrent_first_prepare_is_one_capture_with_identical_retry_results(source):
    library, collection, unit, _, _ = source
    barrier, lock, calls = Barrier(2), Lock(), []
    def renderer(*_):
        with lock:
            calls.append(1)
        time.sleep(0.03)
        return capture()
    def prepare(_):
        barrier.wait(timeout=3)
        return SourceVisualStore(library, renderer).prepare(OWNER, collection, unit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(prepare, range(2)))
    assert results[0] == results[1] and len(calls) == 1


@pytest.mark.parametrize("name", ["visuals", "unit", "record", "asset", "source"])
def test_symlinked_storage_is_not_read_or_overwritten(source, tmp_path, name):
    store, _, target = prepared(source)
    library, collection, unit, folder, _ = source
    if name == "visuals":
        path = folder / "visuals"
    elif name == "unit":
        path = target
    elif name == "record":
        path = target / "record.json"
    elif name == "asset":
        path = next(target.glob("*.png"))
    else:
        path = next((folder / "sources").iterdir())
    outside = tmp_path / ("outside-" + name)
    path.rename(outside)
    try:
        path.symlink_to(outside, target_is_directory=outside.is_dir())
    except OSError:
        pytest.skip("Creating symlinks requires Windows developer mode or permission")
    expect_error("visual_storage_error", store.get, OWNER, collection, unit)
    expect_error("visual_storage_error", store.prepare, OWNER, collection, unit)
    assert path.is_symlink()


@pytest.mark.parametrize("name", ["visuals", "unit"])
def test_directory_positions_cannot_be_regular_files(source, name):
    library, collection, unit, folder, _ = source
    path = folder / "visuals"
    if name == "unit":
        path.mkdir()
        path = path / unit
    path.write_bytes(b"must not overwrite")
    expect_error("visual_storage_error", SourceVisualStore(library).get, OWNER, collection, unit)
    expect_error("visual_storage_error", SourceVisualStore(library).prepare, OWNER, collection, unit)
    assert path.read_bytes() == b"must not overwrite"
