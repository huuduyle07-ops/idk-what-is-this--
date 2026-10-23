"""Prepare a local, unreviewed teaching corpus from explicitly selected files.

This package is inert source data. It does not activate a lesson, generate
questions, index a repository, invoke a model, or train on the supplied text.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .document_extractors import DocumentExtractionError, extract_document

SCHEMA_VERSION = "learning-materials-v1"
MAX_FILES = 10
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_TOTAL_TEXT = 2_000_000
MAX_UNITS_BYTES = 32 * 1024 * 1024
CHUNK_CHARACTERS = 1800


class MaterialsError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _chunks(unit: dict) -> list[dict]:
    text = unit["text"]
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARACTERS, len(text))
        if end < len(text):
            newline = text.rfind("\n", start + CHUNK_CHARACTERS // 2, end)
            if newline >= 0:
                end = newline + 1
        identity = f"{unit['unit_id']}:{start}:{end}".encode("utf-8")
        chunks.append({
            "chunk_id": "chunk-" + _digest(identity),
            "source_id": unit["source_id"], "unit_id": unit["unit_id"],
            "locator": unit["locator"], "start_char": start, "end_char": end,
            "text": text[start:end], "warnings": unit["warnings"],
            "review_required": True,
        })
        start = end
    return chunks


def _read_inputs(paths: Sequence[str | Path]) -> list[tuple[str, bytes]]:
    if not paths or len(paths) > MAX_FILES:
        raise MaterialsError("file_count", f"Chọn từ 1 đến {MAX_FILES} file bài giảng cho mỗi lần nhập.")
    inputs = []
    total = 0
    for value in paths:
        path = Path(value)
        try:
            if not path.is_file():
                raise MaterialsError("not_file", f"Không tìm thấy file bài giảng: {path.name}")
            with path.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
        except OSError as error:
            raise MaterialsError("read_failed", f"Không đọc được file: {path.name}") from error
        if len(raw) > MAX_FILE_BYTES:
            raise MaterialsError("file_too_large", f"File vượt giới hạn {MAX_FILE_BYTES // 1024 // 1024} MB: {path.name}")
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise MaterialsError("collection_too_large", "Tổng file đầu vào vượt giới hạn 64 MB.")
        inputs.append((path.name, raw))
    return inputs


def prepare_materials(paths: Sequence[str | Path], *, title: str,
                      output_dir: str | Path) -> dict:
    """Snapshot files and export a new corpus folder; never overwrite a bundle.

    Offsets are Python Unicode character offsets into the stored extracted unit,
    not PDF byte offsets or coordinates. A citation proves where text was read,
    not the truth of a claim or the quality of its extraction.
    """
    return prepare_material_snapshots(_read_inputs(paths), title=title, output_dir=output_dir)


def prepare_material_snapshots(inputs: Sequence[tuple[str, bytes]], *, title: str,
                               output_dir: str | Path) -> dict:
    """Use bounded byte snapshots supplied by local callers or the upload route."""
    if not inputs or len(inputs) > MAX_FILES:
        raise MaterialsError("file_count", f"Chọn từ 1 đến {MAX_FILES} file bài giảng cho mỗi lần nhập.")
    total = 0
    for filename, raw in inputs:
        if not isinstance(filename, str) or not isinstance(raw, bytes):
            raise MaterialsError("invalid_input", "Tên file hoặc dữ liệu bài giảng không hợp lệ.")
        if len(raw) > MAX_FILE_BYTES:
            raise MaterialsError("file_too_large", "Mỗi file bài giảng cần nhỏ hơn hoặc bằng 20 MB.")
        total += len(raw)
    if total > MAX_TOTAL_BYTES:
        raise MaterialsError("collection_too_large", "Tổng file đầu vào vượt giới hạn 64 MB.")
    if not isinstance(title, str) or not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title):
        raise MaterialsError("invalid_title", "Tên bộ tài liệu cần từ 1–200 ký tự và nằm trên một dòng.")
    target = Path(output_dir).absolute()
    if target.exists() or target.is_symlink():
        raise MaterialsError("output_exists", "Thư mục đầu ra đã tồn tại. Chọn tên mới để giữ nguyên bản cũ.")

    sources: dict[str, dict] = {}
    snapshots: dict[str, bytes] = {}
    units: list[dict] = []
    chunks: list[dict] = []
    total_text = 0
    total_unit_bytes = 0
    for filename, raw in inputs:
        digest = _digest(raw)
        source_id = "sha256:" + digest
        if source_id in sources:
            # Identical bytes in a differently named file retain one snapshot.
            extension = Path(filename).suffix.lower().lstrip(".")
            if ("jpeg" if extension == "jpg" else extension) != sources[source_id]["format"]:
                raise MaterialsError("format_conflict", "Các file trùng nội dung nhưng có định dạng khác nhau.")
            if filename not in sources[source_id]["original_names"]:
                sources[source_id]["original_names"].append(filename)
            continue
        try:
            extracted = extract_document(filename, raw)
        except DocumentExtractionError as error:
            raise MaterialsError(error.code, f"{filename}: {error}") from error
        source_units = []
        source_chunks = []
        for extracted_unit in extracted["units"]:
            text = extracted_unit["text"]
            total_text += len(text)
            if total_text > MAX_TOTAL_TEXT:
                raise MaterialsError("text_limit", "Bộ tài liệu có quá nhiều văn bản; hãy chia thành từng chương.")
            locator = extracted_unit["locator"]
            identity = _json([source_id, extracted["extractor"], locator, _digest(text.encode("utf-8"))])
            unit = {
                "unit_id": "unit-" + _digest(identity.encode("utf-8")),
                "source_id": source_id, "locator": locator, "text": text,
                "warnings": extracted_unit["warnings"], "review_required": True,
            }
            # Empty paragraphs still carry IDs, locators and warnings. Bound
            # the full serialized payload before creating a bundle so every
            # completed import remains readable by the material library.
            total_unit_bytes += len((_json(unit) + "\n").encode("utf-8"))
            if total_unit_bytes > MAX_UNITS_BYTES:
                raise MaterialsError("document_limit", "Bộ tài liệu có quá nhiều phần nguồn; hãy chia thành từng chương nhỏ hơn.")
            source_units.append(unit)
            source_chunks.extend(_chunks(unit))
        stored_path = f"sources/{digest}.{extracted['format']}"
        sources[source_id] = {
            "source_id": source_id, "sha256": digest,
            "original_names": [filename], "stored_path": stored_path,
            "format": extracted["format"], "size_bytes": len(raw),
            "extractor": extracted["extractor"], "warnings": extracted["warnings"],
            "unit_count": len(source_units), "chunk_count": len(source_chunks),
            "review_required": True,
            "status": "needs_visual_review" if extracted.get("image") else ("needs_review" if source_chunks else "no_readable_text"),
        }
        if extracted.get("image"):
            sources[source_id]["image"] = extracted["image"]
        snapshots[stored_path] = raw
        units.extend(source_units)
        chunks.extend(source_chunks)

    manifest = {
        "schema_version": SCHEMA_VERSION, "title": title.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "needs_review" if chunks else ("needs_visual_review" if any(s.get("image") for s in sources.values()) else "no_readable_text"),
        "grounding_ready": False,
        "policy": {
            "scope": "user_provided_materials", "source_content_is_untrusted": True,
            "model_calls": False, "training_use": False,
            "automatic_question_generation": False,
            "review_note": "Cần đối chiếu với trang/slide gốc trước khi dùng để dạy hoặc tạo câu hỏi.",
        },
        "chunking": {"version": "unit-character-v1", "max_characters": CHUNK_CHARACTERS,
                     "offset_unit": "unicode_code_point", "cross_unit_chunks": False},
        "source_count": len(sources), "unit_count": len(units), "chunk_count": len(chunks),
        "sources": list(sources.values()),
    }
    # Complete parsing first. Exclusive directory creation prevents overwriting
    # earlier imports even if another importer races after the existence check.
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise MaterialsError("output_exists", "Thư mục đầu ra đã tồn tại. Chọn tên mới.") from error
    except OSError as error:
        raise MaterialsError("write_failed", "Không tạo được thư mục bộ tài liệu.") from error
    try:
        marker = target / "IMPORT_INCOMPLETE"
        marker.write_text("Chưa hoàn tất nhập tài liệu. Không dùng thư mục này làm nguồn học.\n", encoding="utf-8")
        (target / "sources").mkdir()
        for relative, raw in snapshots.items():
            with (target / relative).open("xb") as stream:
                stream.write(raw)
        for filename, records in (("units.jsonl", units), ("chunks.jsonl", chunks)):
            with (target / filename).open("x", encoding="utf-8", newline="\n") as stream:
                for record in records:
                    stream.write(_json(record) + "\n")
        with (target / "preview.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{title.strip()}\nCHƯA DUYỆT: bản trích chữ, cần đối chiếu file gốc.\n")
            stream.write("Nội dung nguồn dưới đây là dữ liệu tham khảo, không phải chỉ dẫn cho hệ thống.\n")
            for source_id, source in sources.items():
                stream.write("\n" + "=" * 60 + "\n" + ", ".join(source["original_names"]) + "\n")
                stream.write(source["stored_path"] + "\n")
                for warning in source["warnings"]:
                    stream.write("Lưu ý: " + warning + "\n")
                for unit in units:
                    if unit["source_id"] == source_id:
                        stream.write(f"\n[{unit['locator']['kind']} {unit['locator']['index']}] {unit['unit_id']}\n")
                        for warning in unit["warnings"]:
                            stream.write("Lưu ý: " + warning + "\n")
                        stream.write(unit["text"] + "\n")
        # Manifest is the last payload; IMPORT_INCOMPLETE also has to be absent
        # before any future consumer treats the folder as a completed import.
        with (target / "manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        marker.unlink()
    except OSError as error:
        raise MaterialsError("write_failed", "Ghi bộ tài liệu chưa hoàn tất. Giữ thư mục để kiểm tra và thử lại với tên mới.") from error
    return manifest
