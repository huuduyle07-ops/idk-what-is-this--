"""Browser-owner scoped, local lecture bundles; no teaching activation occurs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from threading import RLock
import tempfile

from .materials import MaterialsError, prepare_material_snapshots, MAX_FILES, MAX_TOTAL_BYTES, MAX_FILE_BYTES, MAX_UNITS_BYTES

MAX_COLLECTIONS = 20
MAX_OWNER_BYTES = 256 * 1024 * 1024
_IMPORT_LOCK = RLock()
_OWNER = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[a-f0-9]{32}\Z")
_REQUEST = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_IMAGE_TYPES = {"png": "image/png", "jpeg": "image/jpeg"}
MAX_DESCRIPTION = 4000


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 500:
        raise MaterialsError("invalid_path", "Đường dẫn file không hợp lệ.")
    if any(ord(char) < 32 for char in value) or "\\" in value or ":" in value:
        raise MaterialsError("invalid_path", "Chỉ chấp nhận đường dẫn tương đối bên trong thư mục đã chọn.")
    parts = value.split("/")
    if len(parts) > 12 or any(part in {"", ".", ".."} for part in parts):
        raise MaterialsError("invalid_path", "Đường dẫn file đi ra ngoài thư mục hoặc quá sâu.")
    if PurePosixPath(value).suffix.lower() not in {".pdf", ".pptx", ".docx", ".png", ".jpg", ".jpeg"}:
        raise MaterialsError("unsupported_format", "Chỉ nhập PDF, PowerPoint .pptx, Word .docx và ảnh PNG/JPEG.")
    return value


def _read_json(path: Path, max_bytes=128 * 1024):
    with path.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("oversize metadata")
    return json.loads(raw)


class MaterialLibrary:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _owner_dir(self, owner: str) -> Path:
        if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
            raise MaterialsError("invalid_owner", "Định danh người học không hợp lệ.")
        folder = self.root / owner
        if folder.is_symlink() or folder.resolve().parent != self.root:
            raise MaterialsError("invalid_storage", "Thư mục lưu bài giảng không hợp lệ.")
        return folder

    def _folder(self, owner: str, collection_id: str) -> Path:
        base = self._owner_dir(owner)
        if not isinstance(collection_id, str) or not _ID.fullmatch(collection_id):
            raise MaterialsError("not_found", "Không tìm thấy bộ tài liệu.")
        folder = base / collection_id
        if folder.is_symlink() or folder.resolve().parent != base.resolve():
            raise MaterialsError("not_found", "Không tìm thấy bộ tài liệu.")
        return folder

    def _metadata(self, folder: Path) -> tuple[dict, dict]:
        if not folder.is_dir() or (folder / "IMPORT_INCOMPLETE").exists():
            raise MaterialsError("not_found", "Không tìm thấy bộ tài liệu đã nhập hoàn tất.")
        try:
            for name in ("manifest.json", "web.json"):
                if (folder / name).is_symlink():
                    raise ValueError("symlink metadata")
            manifest = _read_json(folder / "manifest.json")
            web = _read_json(folder / "web.json")
            if manifest["schema_version"] != "learning-materials-v1" or web["id"] != folder.name:
                raise ValueError("schema")
            return manifest, web
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise MaterialsError("not_found", "Không tìm thấy bộ tài liệu đã nhập hoàn tất.") from error

    @staticmethod
    def _summary(manifest: dict, web: dict) -> dict:
        return {"id": web["id"], **{key: manifest[key] for key in
                ("title", "created_at", "source_count", "chunk_count", "status")},
                "grounding_ready": False}

    def list(self, owner: str) -> list[dict]:
        base = self._owner_dir(owner)
        if not base.exists():
            return []
        results = []
        for child in base.iterdir():
            if not _ID.fullmatch(child.name) or child.is_symlink() or child.resolve().parent != base.resolve():
                continue
            try:
                manifest, web = self._metadata(child)
                results.append(self._summary(manifest, web))
            except MaterialsError:
                continue
        return sorted(results, key=lambda row: row["created_at"], reverse=True)

    def get(self, owner: str, collection_id: str) -> dict:
        folder = self._folder(owner, collection_id)
        manifest, web = self._metadata(folder)
        try:
            path = folder / "units.jsonl"
            if path.is_symlink():
                raise ValueError("symlink units")
            with path.open("rb") as stream:
                raw = stream.read(MAX_UNITS_BYTES + 1)
            if len(raw) > MAX_UNITS_BYTES:
                raise ValueError("oversize units")
            units = [json.loads(line) for line in raw.splitlines()]
            sources = []
            descriptions = self._descriptions(folder)
            for source in manifest["sources"]:
                sources.append({key: source[key] for key in
                                ("source_id", "original_names", "format", "unit_count", "chunk_count", "warnings", "status")})
                sources[-1]["upload_paths"] = web["upload_paths"][source["source_id"]]
                if source.get("image") and source["format"] in _IMAGE_TYPES:
                    sources[-1]["image"] = source["image"]
                    sources[-1]["description"] = descriptions.get(source["source_id"], self._empty_description())
            return {**self._summary(manifest, web), "sources": sources, "units": units}
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise MaterialsError("invalid_collection", "Bản trích xuất không đọc được; hãy nhập lại với tên bộ tài liệu mới.") from error

    @staticmethod
    def _empty_description():
        return {"text": "", "revision": 0, "origin": "user"}

    def _descriptions(self, folder: Path) -> dict:
        path = folder / "annotations.json"
        if not path.exists() and not path.is_symlink():
            return {}
        try:
            if path.is_symlink():
                raise ValueError("symlink annotations")
            data = _read_json(path, 256 * 1024)
            if not isinstance(data, dict) or len(data) > MAX_FILES:
                raise ValueError("invalid annotations")
            for key, value in data.items():
                if (not key.startswith("sha256:") or not _DIGEST.fullmatch(key[7:])
                        or not isinstance(value, dict) or value.get("origin") != "user"
                        or not isinstance(value.get("text"), str) or len(value["text"]) > MAX_DESCRIPTION
                        or type(value.get("revision")) is not int or value["revision"] < 1):
                    raise ValueError("invalid description")
            return data
        except (OSError, ValueError, TypeError) as error:
            raise MaterialsError("invalid_collection", "Không đọc được ghi chú đã lưu; hãy kiểm tra bộ tài liệu trước khi sửa.") from error

    def _image_source(self, owner: str, collection_id: str, digest: str):
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise MaterialsError("not_found", "Không tìm thấy ảnh trong bộ tài liệu.")
        folder = self._folder(owner, collection_id)
        manifest, _ = self._metadata(folder)
        source = next((s for s in manifest.get("sources", []) if s.get("source_id") == "sha256:" + digest), None)
        if not source or source.get("format") not in _IMAGE_TYPES or not source.get("image"):
            raise MaterialsError("not_found", "Không tìm thấy ảnh trong bộ tài liệu.")
        return folder, source

    def image(self, owner: str, collection_id: str, digest: str) -> tuple[bytes, str]:
        folder, source = self._image_source(owner, collection_id, digest)
        # Derive a confined filename from the validated digest and format. Never
        # serve client filenames or an arbitrary path found in metadata.
        directory = folder / "sources"
        path = directory / (digest + "." + source["format"])
        try:
            if (directory.is_symlink() or directory.resolve().parent != folder.resolve()
                    or path.is_symlink() or path.resolve().parent != directory.resolve()):
                raise ValueError("invalid source path")
            with path.open("rb") as stream:
                raw = stream.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES or hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("source snapshot changed")
        except (OSError, ValueError) as error:
            raise MaterialsError("invalid_collection", "Ảnh gốc không còn khớp bản đã nhập; hãy kiểm tra bộ tài liệu.") from error
        return raw, _IMAGE_TYPES[source["format"]]

    def describe_image(self, owner: str, collection_id: str, digest: str, text: str, expected_revision: int) -> dict:
        if (not isinstance(text, str) or len(text) > MAX_DESCRIPTION
                or any(ord(c) < 32 and c not in "\n\r\t" for c in text)
                or type(expected_revision) is not int or expected_revision < 0):
            raise MaterialsError("invalid_description", "Ghi chú cần tối đa 4.000 ký tự và phiên bản hợp lệ.")
        try:
            text.encode("utf-8")
        except UnicodeError as error:
            raise MaterialsError("invalid_description", "Ghi chú có ký tự không hợp lệ.") from error
        with _IMPORT_LOCK:
            folder, source = self._image_source(owner, collection_id, digest)
            notes = self._descriptions(folder)
            key = source["source_id"]
            current = notes.get(key, self._empty_description())
            # An exact retry after a lost acknowledgement is safe; older tabs
            # cannot replace a newer, different note.
            if text == current["text"] and expected_revision in {current["revision"], current["revision"] - 1}:
                return current
            if expected_revision != current["revision"]:
                raise MaterialsError("description_conflict", "Ghi chú đã thay đổi ở lượt khác. Xem bản đã lưu trước khi lưu tiếp.")
            updated = {"text": text, "revision": current["revision"] + 1, "origin": "user"}
            notes[key] = updated
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="wb", dir=folder, prefix=".annotations-", suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(_json_bytes(notes))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, folder / "annotations.json")
            except OSError as error:
                raise MaterialsError("write_failed", "Chưa lưu được ghi chú. Nội dung cũ vẫn được giữ; hãy thử lại.") from error
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return updated

    def import_files(self, owner: str, request_id: str, title: str,
                     uploads: list[tuple[str, bytes]]) -> tuple[dict, bool]:
        base = self._owner_dir(owner)
        if not isinstance(request_id, str) or not _REQUEST.fullmatch(request_id):
            raise MaterialsError("invalid_request", "Mã lần nhập không hợp lệ.")
        if not isinstance(title, str) or not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title):
            raise MaterialsError("invalid_title", "Tên bộ tài liệu cần từ 1–200 ký tự và nằm trên một dòng.")
        if not uploads or len(uploads) > MAX_FILES:
            raise MaterialsError("file_count", "Chọn từ 1 đến 10 file cho mỗi lần nhập.")
        upload_paths: dict[str, list[str]] = {}
        items = []
        seen = set()
        total = 0
        for relative, raw in uploads:
            relative = _relative_path(relative)
            if relative.casefold() in seen:
                raise MaterialsError("duplicate_path", "Danh sách có đường dẫn file trùng nhau.")
            seen.add(relative.casefold())
            if not isinstance(raw, bytes):
                raise MaterialsError("invalid_input", "Dữ liệu file không hợp lệ.")
            if len(raw) > MAX_FILE_BYTES:
                raise MaterialsError("file_too_large", "Mỗi file được nhập tối đa 20 MB.")
            total += len(raw)
            if total > MAX_TOTAL_BYTES:
                raise MaterialsError("collection_too_large", "Tổng file được nhập tối đa 64 MB.")
            digest = hashlib.sha256(raw).hexdigest()
            upload_paths.setdefault("sha256:" + digest, []).append(relative)
            items.append({"path": relative, "sha256": digest})
        fingerprint = hashlib.sha256(_json_bytes({"title": title.strip(), "files": items})).hexdigest()
        collection_id = hashlib.sha256(request_id.encode("ascii")).hexdigest()[:32]
        folder = self._folder(owner, collection_id)
        with _IMPORT_LOCK:
            if folder.exists():
                try:
                    _, web = self._metadata(folder)
                except MaterialsError as error:
                    raise MaterialsError("import_incomplete", "Lần nhập trước chưa hoàn tất. Kiểm tra thư mục lưu hoặc chọn lại file để tạo lần nhập mới.") from error
                if web["fingerprint"] != fingerprint:
                    raise MaterialsError("request_collision", "Mã lần nhập đã dùng cho nội dung khác; hãy chọn lại file.")
                return self.get(owner, collection_id), False
            if base.exists():
                folders = [p for p in base.iterdir() if p.is_dir()]
                if len(folders) >= MAX_COLLECTIONS:
                    raise MaterialsError("library_limit", "Đã đạt giới hạn 20 bộ tài liệu trong trình duyệt này.")
                # Count retained snapshots, including incomplete imports.
                stored = 0
                for previous in folders:
                    source_dir = previous / "sources"
                    if previous.is_symlink() or source_dir.is_symlink():
                        continue
                    if source_dir.is_dir():
                        stored += sum(p.stat().st_size for p in source_dir.iterdir() if p.is_file() and not p.is_symlink())
                if stored + total > MAX_OWNER_BYTES:
                    raise MaterialsError("library_limit", "Kho tài liệu của trình duyệt này vượt giới hạn 256 MB.")
            manifest = prepare_material_snapshots(uploads, title=title, output_dir=folder)
            web = {"id": collection_id, "fingerprint": fingerprint, "upload_paths": upload_paths}
            try:
                with (folder / "web.json").open("x", encoding="utf-8") as stream:
                    json.dump(web, stream, ensure_ascii=False)
            except OSError as error:
                raise MaterialsError("write_failed", "Chưa ghi xong thông tin bộ tài liệu; không gửi lại với nội dung khác.") from error
            return self.get(owner, collection_id), True
