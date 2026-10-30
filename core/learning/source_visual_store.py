"""Immutable, owner-scoped visual derivatives of existing lecture snapshots.

Only ``prepare`` writes. Neither the imported corpus nor its annotations are
changed, and source bytes are rechecked even when returning a cached capture.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from threading import RLock
import uuid
import warnings

from PIL import Image

from .material_library import MaterialLibrary
from .materials import MaterialsError, MAX_FILE_BYTES

VERSION = "source-visuals-v1"
MAX_UNIT_BYTES = 16 * 1024 * 1024
MAX_COLLECTION_BYTES = 64 * 1024 * 1024
MAX_OWNER_BYTES = 128 * 1024 * 1024
MAX_RECORD_BYTES = 256 * 1024
MAX_VISUALS = 12
_MAX_CAPTURE_BYTES = 16 * 1024 * 1024
_LOCK = RLock()
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_UNIT = re.compile(r"unit-[a-f0-9]{64}\Z")
_COLLECTION = re.compile(r"[a-f0-9]{32}\Z")
_FORMATS = {"pdf": {"page"}, "pptx": {"slide"}, "docx": {"paragraph", "table"},
            "png": {"image"}, "jpeg": {"image"}}
_KINDS = {"page_render": {"pdf"}, "slide_render": {"pptx"},
          "embedded_image": {"docx", "pptx"}, "source_image": {"png", "jpeg"}}
_MIMES = {"image/png": ("png", "PNG"), "image/jpeg": ("jpeg", "JPEG")}
_VISUAL_KEYS = {"id", "kind", "mime_type", "width", "height", "locator", "native_part", "bbox", "warnings",
                "asset_sha256", "size_bytes"}
_ENGINE_VISUAL_KEYS = (_VISUAL_KEYS - {"id", "asset_sha256", "size_bytes"}) | {"bytes"}
_RECORD_KEYS = {"version", "status", "source_id", "unit_id", "source_format", "source_size_bytes",
                "locator", "created_at", "warnings", "visuals"}


def _fail(code="visual_storage_error", message="Không đọc được bản hình đã lưu; hãy kiểm tra bộ tài liệu."):
    return MaterialsError(code, message)


def _resolved(path: Path) -> Path:
    value = str(path.resolve())
    if os.name == "nt":
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
    return Path(value)


def _checked(path: Path, parent: Path, *, directory=False, missing=False):
    """Reject links, special files and paths whose resolved parent escaped."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing and _resolved(path).parent == _resolved(parent):
            return None
        raise _fail()
    if (stat.S_ISLNK(info.st_mode) or _resolved(path).parent != _resolved(parent)
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise _fail()
    return info


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("nonfinite JSON")


def _text(value, maximum=500):
    if (not isinstance(value, str) or not value or len(value) > maximum
            or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError("invalid text")
    return value


def _notes(value):
    if not isinstance(value, list) or len(value) > 40:
        raise ValueError("invalid warnings")
    return [_text(note, 1000) for note in value]


def _locator(value, source_format):
    if (not isinstance(value, dict) or set(value) != {"kind", "index"}
            or value["kind"] not in _FORMATS[source_format]
            or type(value["index"]) is not int or not 1 <= value["index"] <= 1_000_000
            or source_format in {"png", "jpeg"} and value["index"] != 1):
        raise ValueError("invalid source locator")
    return dict(value)


def _geometry(value):
    if value is None:
        return None
    if (not isinstance(value, list) or len(value) != 4
            or any(type(n) not in (int, float) or not math.isfinite(n) for n in value)):
        raise ValueError("invalid bounding box")
    x, y, width, height = value
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError("bounding box outside source unit")
    return list(value)


def _raster(raw, mime, width, height):
    if (not isinstance(raw, bytes) or not raw or len(raw) > _MAX_CAPTURE_BYTES
            or mime not in _MIMES or type(width) is not int or type(height) is not int
            or not 1 <= width <= 1800 or not 1 <= height <= 1800):
        raise ValueError("invalid raster")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as picture:
                if picture.format != _MIMES[mime][1] or picture.size != (width, height) or getattr(picture, "n_frames", 1) != 1:
                    raise ValueError("raster metadata mismatch")
                picture.verify()
            with Image.open(io.BytesIO(raw)) as picture:
                picture.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("invalid raster encoding") from error


def _metadata(value, source_format, locator):
    if (not isinstance(value, dict) or value.get("kind") not in _KINDS
            or source_format not in _KINDS[value["kind"]] or value.get("mime_type") not in _MIMES
            or _locator(value.get("locator"), source_format) != locator):
        raise ValueError("visual provenance mismatch")
    part = value.get("native_part")
    if part is not None:
        _text(part, 500)
        if ("\\" in part or ":" in part or part.startswith("/")
                or any(p in {"", ".", ".."} for p in part.split("/"))
                or PurePosixPath(part).is_absolute()):
            raise ValueError("invalid native part")
        prefix = "word/" if source_format == "docx" else "ppt/" if source_format == "pptx" else None
        if prefix is None or not part.startswith(prefix):
            raise ValueError("native part format mismatch")
    if value["kind"] == "embedded_image" and part is None:
        raise ValueError("missing native image provenance")
    geometry = _geometry(value.get("bbox"))
    if value["kind"] in {"page_render", "slide_render", "source_image"} and geometry != [0, 0, 1, 1]:
        raise ValueError("whole-unit capture must cover the unit")
    if source_format == "docx" and geometry is not None:
        raise ValueError("Word image has no verified page coordinates")
    return {"kind": value["kind"], "mime_type": value["mime_type"], "width": value.get("width"),
            "height": value.get("height"), "locator": dict(locator), "native_part": part,
            "bbox": geometry, "warnings": _notes(value.get("warnings"))}


def _visual_id(metadata, digest):
    # Include occurrence provenance: the same asset may occur twice on a slide.
    return hashlib.sha256(_json({**metadata, "asset_sha256": digest})).hexdigest()


def _public(record):
    fields = ("version", "status", "source_id", "unit_id", "locator", "created_at", "warnings")
    return {**{key: record[key] for key in fields if key in record},
            "visuals": [{key: value for key, value in visual.items()
                         if key not in {"asset_sha256", "size_bytes"}} for visual in record["visuals"]]}


class SourceVisualStore:
    def __init__(self, library: MaterialLibrary, renderer=None):
        self.library = library
        self.renderer = renderer

    def _source(self, owner, collection_id, unit_id):
        if not isinstance(unit_id, str) or not _UNIT.fullmatch(unit_id):
            raise _fail("visual_not_found", "Không tìm thấy phần nguồn này.")
        try:
            folder = self.library._folder(owner, collection_id)
            manifest, _ = self.library._metadata(folder)
            collection = self.library.get(owner, collection_id)
        except MaterialsError as error:
            code = "visual_not_found" if error.code == "not_found" else "visual_invalid" if error.code == "invalid_owner" else "visual_storage_error"
            raise _fail(code) from error
        try:
            units = [u for u in collection["units"] if u.get("unit_id") == unit_id]
            if not units:
                raise _fail("visual_not_found", "Không tìm thấy phần nguồn trong bộ tài liệu này.")
            if len(units) != 1:
                raise ValueError("duplicate unit")
            unit = units[0]
            sid = unit["source_id"]
            if not isinstance(sid, str) or not sid.startswith("sha256:") or not _DIGEST.fullmatch(sid[7:]):
                raise ValueError("invalid source digest")
            sources = [s for s in manifest["sources"] if s.get("source_id") == sid]
            if len(sources) != 1:
                raise ValueError("source not unique")
            source = sources[0]
            fmt = source["format"]
            if (fmt not in _FORMATS or source.get("sha256") != sid[7:]
                    or type(source.get("size_bytes")) is not int or not 1 <= source["size_bytes"] <= MAX_FILE_BYTES
                    or source.get("stored_path") != f"sources/{sid[7:]}.{fmt}"):
                raise ValueError("invalid source metadata")
            locator = _locator(unit["locator"], fmt)
            text = unit["text"]
            if not isinstance(text, str) or len(text) > 2_000_000:
                raise ValueError("invalid unit text")
            extractor = source["extractor"]
            if not isinstance(extractor, dict) or set(extractor) != {"name", "version"}:
                raise ValueError("invalid extractor provenance")
            for value in extractor.values():
                _text(value, 100)
            identity = json.dumps([sid, extractor, locator,
                                   hashlib.sha256(text.encode("utf-8")).hexdigest()], ensure_ascii=False, sort_keys=True)
            if unit_id != "unit-" + hashlib.sha256(identity.encode("utf-8")).hexdigest():
                raise ValueError("unit provenance changed")
            directory = folder / "sources"
            _checked(directory, folder, directory=True)
            path = directory / f"{sid[7:]}.{fmt}"
            info = _checked(path, directory, missing=True)
            if info is None or info.st_size != source["size_bytes"]:
                raise _fail("visual_source_changed", "File gốc không còn khớp bản đã nhập; hãy kiểm tra bộ tài liệu.")
            with path.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw) != source["size_bytes"] or hashlib.sha256(raw).hexdigest() != sid[7:]:
                raise _fail("visual_source_changed", "File gốc không còn khớp bản đã nhập; hãy kiểm tra bộ tài liệu.")
            return folder, source, unit_id, locator, raw
        except MaterialsError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise _fail() from error

    def _read(self, context):
        folder, source, unit_id, locator, _ = context
        directory = folder / "visuals"
        if _checked(directory, folder, directory=True, missing=True) is None:
            return None
        target = directory / unit_id
        if _checked(target, directory, directory=True, missing=True) is None:
            return None
        try:
            record_path = target / "record.json"
            info = _checked(record_path, target)
            if info.st_size > MAX_RECORD_BYTES:
                raise ValueError("oversize record")
            with record_path.open("rb") as stream:
                raw = stream.read(MAX_RECORD_BYTES + 1)
            if len(raw) > MAX_RECORD_BYTES:
                raise ValueError("oversize record")
            record = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
            if (not isinstance(record, dict) or set(record) != _RECORD_KEYS or record["version"] != VERSION
                    or record["status"] not in {"ready", "partial"} or record["source_id"] != source["source_id"]
                    or record["source_format"] != source["format"] or record["source_size_bytes"] != source["size_bytes"]
                    or type(record["source_size_bytes"]) is not int or record["unit_id"] != unit_id
                    or _locator(record["locator"], source["format"]) != locator):
                raise ValueError("invalid capture record")
            _text(record["created_at"], 40)
            created = datetime.fromisoformat(record["created_at"])
            if created.tzinfo is None or created.utcoffset().total_seconds() != 0:
                raise ValueError("capture time must be UTC")
            _notes(record["warnings"])
            if not isinstance(record["visuals"], list) or len(record["visuals"]) > MAX_VISUALS:
                raise ValueError("invalid visuals")
            names, seen, size = {"record.json"}, set(), len(raw)
            for visual in record["visuals"]:
                if not isinstance(visual, dict) or set(visual) != _VISUAL_KEYS:
                    raise ValueError("invalid visual fields")
                metadata = _metadata(visual, source["format"], locator)
                digest = visual["asset_sha256"]
                if (not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
                        or type(visual["size_bytes"]) is not int or not 1 <= visual["size_bytes"] <= _MAX_CAPTURE_BYTES
                        or visual["id"] != _visual_id(metadata, digest) or visual["id"] in seen):
                    raise ValueError("invalid visual identity")
                seen.add(visual["id"])
                name = digest + "." + _MIMES[visual["mime_type"]][0]
                path = target / name
                info = _checked(path, target)
                if info.st_size != visual["size_bytes"]:
                    raise ValueError("asset size changed")
                with path.open("rb") as stream:
                    asset = stream.read(_MAX_CAPTURE_BYTES + 1)
                if len(asset) != visual["size_bytes"] or hashlib.sha256(asset).hexdigest() != digest:
                    raise ValueError("asset changed")
                _raster(asset, visual["mime_type"], visual["width"], visual["height"])
                if name not in names:
                    size += len(asset)
                names.add(name)
            if size > _MAX_CAPTURE_BYTES or {p.name for p in target.iterdir()} != names:
                raise ValueError("capture contents changed")
            return record
        except MaterialsError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as error:
            raise _fail() from error

    def get(self, owner, collection_id, unit_id):
        try:
            context = self._source(owner, collection_id, unit_id)
            record = self._read(context)
            if record is not None:
                return _public(record)
            return {"version": VERSION, "status": "unprepared", "source_id": context[1]["source_id"],
                    "unit_id": unit_id, "locator": context[3], "warnings": [], "visuals": []}
        except OSError as error:
            raise _fail() from error

    def _usage(self, owner, collection_id, unit_id):
        base = self.library._owner_dir(owner)
        collection_total = owner_total = unit_total = files = 0

        def scan(path, parent, depth=0):
            nonlocal files
            _checked(path, parent, directory=True)
            if depth > 4:
                raise _fail()
            total = 0
            for child in path.iterdir():
                info = child.lstat()
                files += 1
                if files > 20_000:
                    raise _fail("visual_limit", "Kho hình đã có quá nhiều file; hãy kiểm tra trước khi tạo thêm.")
                if stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode):
                    total += scan(child, path, depth + 1)
                else:
                    total += _checked(child, path).st_size
            return total

        for collection in base.iterdir():
            if not _COLLECTION.fullmatch(collection.name):
                continue
            _checked(collection, base, directory=True)
            directory = collection / "visuals"
            if _checked(directory, collection, directory=True, missing=True) is None:
                continue
            total = scan(directory, collection)
            owner_total += total
            if collection.name == collection_id:
                collection_total = total
                for child in directory.iterdir():
                    if child.name == unit_id or child.name.startswith(".stage-" + unit_id + "-"):
                        unit_total += scan(child, directory)
        return unit_total, collection_total, owner_total

    def prepare(self, owner, collection_id, unit_id):
        if not _LOCK.acquire(timeout=5):
            raise _fail("visual_busy", "Đang chuẩn bị hình khác; hãy thử lại sau ít giây.")
        staging = None
        try:
            context = self._source(owner, collection_id, unit_id)
            existing = self._read(context)
            if existing is not None:
                return _public(existing)
            folder, source, _, locator, raw = context
            usage = self._usage(owner, collection_id, unit_id)
            if any(used >= limit for used, limit in zip(usage, (MAX_UNIT_BYTES, MAX_COLLECTION_BYTES, MAX_OWNER_BYTES))):
                raise _fail("visual_limit", "Kho hình đã đầy; hãy kiểm tra các bộ tài liệu trước khi tạo thêm.")
            try:
                renderer = self.renderer
                if renderer is None:
                    from .source_visuals import prepare_visuals
                    renderer = prepare_visuals
                bundle = renderer(raw, source["format"], dict(locator))
            except MaterialsError:
                raise
            except Exception as error:
                raise _fail("visual_render_failed", "Chưa thể chuẩn bị hình từ phần nguồn này; file gốc vẫn được giữ.") from error
            try:
                if (not isinstance(bundle, dict) or set(bundle) != {"version", "status", "warnings", "visuals"}
                        or bundle["version"] != VERSION or bundle["status"] not in {"ready", "partial"}
                        or not isinstance(bundle["visuals"], list) or len(bundle["visuals"]) > MAX_VISUALS):
                    raise ValueError("invalid renderer result")
                visuals, assets, seen = [], {}, set()
                for item in bundle["visuals"]:
                    if not isinstance(item, dict) or set(item) != _ENGINE_VISUAL_KEYS:
                        raise ValueError("invalid renderer visual")
                    metadata = _metadata(item, source["format"], locator)
                    _raster(item["bytes"], metadata["mime_type"], metadata["width"], metadata["height"])
                    digest = hashlib.sha256(item["bytes"]).hexdigest()
                    visual_id = _visual_id(metadata, digest)
                    if visual_id in seen:
                        continue
                    seen.add(visual_id)
                    visuals.append({"id": visual_id, **metadata, "asset_sha256": digest, "size_bytes": len(item["bytes"])})
                    assets[digest + "." + _MIMES[metadata["mime_type"]][0]] = item["bytes"]
                record = {"version": VERSION, "status": bundle["status"], "source_id": source["source_id"],
                          "unit_id": unit_id, "source_format": source["format"], "source_size_bytes": source["size_bytes"],
                          "locator": dict(locator), "created_at": datetime.now(timezone.utc).isoformat(),
                          "warnings": _notes(bundle["warnings"]), "visuals": visuals}
                record_bytes = _json(record)
                if len(record_bytes) > MAX_RECORD_BYTES:
                    raise ValueError("record too large")
            except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
                raise _fail("visual_render_failed", "Bản hình trả về không hợp lệ; chưa lưu thay đổi nào.") from error
            size = len(record_bytes) + sum(map(len, assets.values()))
            usage = self._usage(owner, collection_id, unit_id)
            if any(used + size > limit for used, limit in zip(usage, (MAX_UNIT_BYTES, MAX_COLLECTION_BYTES, MAX_OWNER_BYTES))):
                raise _fail("visual_limit", "Bản hình vượt dung lượng cho phần nguồn hoặc kho tài liệu.")
            # Re-read after rendering so a changed/deleted original cannot be
            # published alongside a derivative of an older snapshot.
            after = self._source(owner, collection_id, unit_id)
            if after[1] != source or after[3] != locator or after[4] != raw:
                raise _fail("visual_source_changed", "Nguồn đã thay đổi trong khi chuẩn bị hình.")
            directory = folder / "visuals"
            if _checked(directory, folder, directory=True, missing=True) is None:
                directory.mkdir()
            _checked(directory, folder, directory=True)
            target = directory / unit_id
            if _checked(target, directory, directory=True, missing=True) is not None:
                # A second process may have published while this process rendered.
                return _public(self._read(after))
            staging = directory / (".stage-" + unit_id + "-" + uuid.uuid4().hex)
            staging.mkdir()
            _checked(staging, directory, directory=True)
            for name, data in {**assets, "record.json": record_bytes}.items():
                _checked(staging, directory, directory=True)
                with (staging / name).open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            final_source = self._source(owner, collection_id, unit_id)
            if final_source[1] != source or final_source[3] != locator or final_source[4] != raw:
                raise _fail("visual_source_changed", "Nguồn đã thay đổi trong khi lưu hình.")
            try:
                staging.rename(target)
            except FileExistsError:
                return _public(self._read(after))
            staging = None
            return _public(self._read(after))
        except MaterialsError:
            raise
        except (OSError, ValueError, TypeError) as error:
            raise _fail() from error
        finally:
            if staging is not None:
                try:
                    # Only remove this request's freshly allocated, confined dir.
                    _checked(staging, staging.parent, directory=True)
                    for child in staging.iterdir():
                        _checked(child, staging)
                    shutil.rmtree(staging)
                except (OSError, MaterialsError):
                    pass  # Unremoved bytes remain visible to the next quota scan.
            _LOCK.release()

    def image(self, owner, collection_id, unit_id, visual_id):
        if not isinstance(visual_id, str) or not _DIGEST.fullmatch(visual_id):
            raise _fail("visual_not_found", "Không tìm thấy hình này.")
        try:
            context = self._source(owner, collection_id, unit_id)
            record = self._read(context)
            visual = next((v for v in record["visuals"] if v["id"] == visual_id), None) if record else None
            if visual is None:
                raise _fail("visual_not_found", "Không tìm thấy hình này.")
            target = context[0] / "visuals" / unit_id
            path = target / (visual["asset_sha256"] + "." + _MIMES[visual["mime_type"]][0])
            _checked(path, target)
            with path.open("rb") as stream:
                raw = stream.read(_MAX_CAPTURE_BYTES + 1)
            if len(raw) != visual["size_bytes"] or hashlib.sha256(raw).hexdigest() != visual["asset_sha256"]:
                raise _fail()
            return raw, visual["mime_type"]
        except OSError as error:
            raise _fail() from error
