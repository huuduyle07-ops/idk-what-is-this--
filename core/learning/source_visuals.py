"""Bounded source visuals, with exact locators and no OCR or model calls.

An image is evidence of the source's appearance, not an interpretation of it.
DOCX image extraction deliberately does not invent page numbers or layout.
Office rendering accepts only preflighted, local, inert OOXML snapshots.
"""
from __future__ import annotations

import copy
import io
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

from .document_extractors import (
    DocumentExtractionError, MAX_INPUT_BYTES, MAX_PAGES_OR_SLIDES,
    _OfficeArchive, _local, _word_blocks, extract_document,
)
from .materials import MaterialsError

VERSION = "source-visuals-v1"
MAX_EDGE = 1800
MAX_VISUALS = 12
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
RENDER_TIMEOUT = 30
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_FULL_REGION = [0.0, 0.0, 1.0, 1.0]
_VISUAL_WARNING = "Hình giữ nội dung nguồn để đối chiếu; chưa chạy OCR hoặc xác nhận ý nghĩa sơ đồ."
_PARTIAL_WARNING = "Chỉ lấy ảnh nhúng; chữ, hình vector, đường nối và bố cục của phần nguồn chưa được render đầy đủ."


def _fail(code, message):
    raise MaterialsError(code, message)


def _validate(raw, source_format, locator):
    if not isinstance(raw, bytes) or not raw:
        _fail("visual_invalid", "Cần bản nguồn không rỗng dạng bytes.")
    if len(raw) > MAX_INPUT_BYTES:
        _fail("visual_limit", "Nguồn hình vượt giới hạn 20 MiB.")
    if source_format not in {"pdf", "pptx", "docx", "png", "jpeg", "jpg"}:
        _fail("visual_invalid", "Định dạng nguồn hình không được hỗ trợ.")
    if (not isinstance(locator, dict) or set(locator) != {"kind", "index"}
            or type(locator["index"]) is not int or locator["index"] < 1):
        _fail("visual_invalid", "Vị trí nguồn phải có loại và chỉ số nguyên bắt đầu từ 1.")
    allowed = {"pdf": {"page"}, "pptx": {"slide"}, "docx": {"paragraph", "table"},
               "png": {"image"}, "jpeg": {"image"}, "jpg": {"image"}}
    if locator["kind"] not in allowed[source_format]:
        _fail("visual_invalid", "Loại vị trí không khớp định dạng nguồn.")
    if source_format in {"png", "jpeg", "jpg"} and locator["index"] != 1:
        _fail("visual_invalid", "Ảnh nguồn chỉ có một vị trí ảnh.")


def _asset(raw, extension, kind, locator, *, native_part=None, bbox=None):
    """Validate fully before decoding/resizing; preserve source bytes if small."""
    info = extract_document("visual." + extension, raw)
    image_info = info["image"]
    width, height = image_info["width"], image_info["height"]
    notes = []
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as original:
        orientation = original.getexif().get(274, 1)
        normalize = orientation in {2, 3, 4, 5, 6, 7, 8}
        if normalize or max(width, height) > MAX_EDGE:
            image = ImageOps.exif_transpose(original)
            before_resize = image.size
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if info["format"] == "jpeg":
                image.convert("RGB").save(output, "JPEG", quality=90)
            else:
                image.save(output, "PNG")
            raw = output.getvalue()
            width, height = image.size
            if normalize:
                notes.append("Ảnh xem trước đã áp dụng hướng EXIF; bản nguồn đã nhập không thay đổi.")
            if image.size != before_resize:
                notes.append("Ảnh xem trước được thu nhỏ; bản nguồn đã nhập không thay đổi.")
    if len(raw) > MAX_BUNDLE_BYTES:
        _fail("visual_limit", "Một ảnh xem trước vượt giới hạn 16 MiB.")
    return {"kind": kind, "mime_type": image_info["mime_type"], "bytes": raw,
            "width": width, "height": height, "locator": copy.deepcopy(locator),
            "native_part": native_part, "bbox": copy.deepcopy(bbox), "warnings": notes}


def _bundle(visuals, *, partial=False, notes=()):
    if len(visuals) > MAX_VISUALS or sum(len(item["bytes"]) for item in visuals) > MAX_BUNDLE_BYTES:
        _fail("visual_limit", "Phần nguồn vượt giới hạn 12 hình hoặc 16 MiB hình xem trước.")
    return {"version": VERSION, "status": "partial" if partial else "ready",
            "warnings": list(dict.fromkeys([_VISUAL_WARNING, *notes])), "visuals": visuals}


def _run(command, *, unavailable_codes=()):
    """Never invoke a shell; do not expose document paths or renderer stderr."""
    options = {"check": False, "timeout": RENDER_TIMEOUT, "stdin": subprocess.DEVNULL,
               "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "shell": False}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(command, **options)
    except subprocess.TimeoutExpired:
        _fail("visual_render_failed", "Bộ render nguồn vượt thời gian chờ 30 giây.")
    except (OSError, ValueError):
        _fail("visual_unavailable", "Chưa chạy được bộ render nguồn trong môi trường hiện tại.")
    if result.returncode in unavailable_codes:
        _fail("visual_unavailable", "Chưa có PowerPoint riêng để render an toàn; ứng dụng có thể đang mở ở lượt khác.")
    if result.returncode != 0:
        _fail("visual_render_failed", "Bộ render không tạo được hình xem trước của phần nguồn.")


def _read_render(path):
    try:
        if not path.is_file():
            _fail("visual_render_failed", "Bộ render không trả về hình xem trước.")
        with path.open("rb") as stream:
            raw = stream.read(MAX_BUNDLE_BYTES + 1)
    except OSError:
        _fail("visual_render_failed", "Không đọc được hình xem trước vừa render.")
    if len(raw) > MAX_BUNDLE_BYTES:
        _fail("visual_limit", "Hình render vượt giới hạn 16 MiB.")
    return raw


def _pdf(raw, locator):
    try:
        import pypdf
    except ImportError:
        _fail("visual_unavailable", "Chưa có bộ đọc PDF để kiểm tra vị trí trang.")
    try:
        reader = pypdf.PdfReader(io.BytesIO(raw), strict=True)
    except (pypdf.errors.PyPdfError, NotImplementedError):
        _fail("visual_invalid", "Không đọc được cấu trúc PDF hợp lệ.")
    if reader.is_encrypted:
        _fail("visual_invalid", "Không render PDF đang mã hóa.")
    if len(reader.pages) > MAX_PAGES_OR_SLIDES:
        _fail("visual_limit", "Nguồn PDF vượt giới hạn 300 trang.")
    if locator["index"] > len(reader.pages):
        _fail("visual_invalid", "Số trang được chọn không tồn tại trong PDF.")
    executable = shutil.which("pdftoppm")
    if not executable:
        _fail("visual_unavailable", "Chưa có pdftoppm để render trang PDF.")
    with tempfile.TemporaryDirectory(prefix="learning-visual-") as directory:
        folder = Path(directory)
        source, prefix = folder / "source.pdf", folder / "page"
        source.write_bytes(raw)
        number = str(locator["index"])
        _run([executable, "-f", number, "-l", number, "-singlefile", "-scale-to", str(MAX_EDGE),
              "-png", str(source), str(prefix)])
        visual = _asset(_read_render(folder / "page.png"), "png", "page_render", locator, bbox=_FULL_REGION)
    return _bundle([visual])


def _target(part, target):
    """Resolve a package URI without ever following it outside the archive."""
    if not isinstance(target, str) or not target:
        _fail("visual_invalid", "Tài liệu chứa liên kết nguồn rỗng hoặc không hợp lệ.")
    decoded = unquote(target)
    parts = urlsplit(decoded)
    if (parts.scheme or parts.netloc or parts.query or parts.fragment or "\\" in decoded
            or any(ord(char) < 32 for char in decoded)):
        _fail("visual_invalid", "Không xử lý nguồn Office có liên kết tài nguyên bên ngoài.")
    resolved = posixpath.normpath(decoded.lstrip("/") if decoded.startswith("/")
                                 else posixpath.join(posixpath.dirname(part), decoded))
    if (resolved in {"", ".", ".."} or resolved.startswith("../") or ":" in resolved
            or len(resolved) > 500):
        _fail("visual_invalid", "Liên kết Office vượt phạm vi gói tài liệu.")
    return resolved


class _Office:
    """Validated OOXML trees and relationships; never execute package members."""
    def __init__(self, raw, *, active_renderer):
        self.archive = _OfficeArchive(raw)
        self.trees = {}
        self.active_renderer = active_renderer
        try:
            for name in sorted(self.archive.names):
                folded = name.lower()
                if active_renderer and (any(marker in "/" + folded for marker in
                        ("/embeddings/", "/activex/", "/externallinks/", "/customui/"))
                        or "vbaproject" in folded or folded.endswith((".exe", ".dll", ".js", ".vbs", ".html", ".htm", ".svg"))):
                    _fail("visual_invalid", "Nguồn Office chứa thành phần chủ động hoặc nhúng chưa được hỗ trợ.")
                if folded.endswith((".xml", ".rels")):
                    tree = self.archive.xml(name)
                    self.trees[name] = tree
                    # Passive DOCX extraction does not evaluate fields, macros,
                    # objects or unrelated links. Only selected image relations
                    # are resolved below, without ever opening Word.
                    if not active_renderer:
                        continue
                    for node in tree.iter():
                        tag = _local(node.tag)
                        for attribute, value in node.attrib.items():
                            # Legacy VML can reference a file directly rather than
                            # through an OOXML relationship. Do not let Office fetch it.
                            attribute_name = _local(attribute).lower()
                            if attribute_name in {"src", "href"} and value:
                                _fail("visual_invalid", "Nguồn Office có tham chiếu tài nguyên trực tiếp chưa được hỗ trợ.")
                            if attribute_name == "action" and any(marker in value.lower() for marker in ("ppaction://macro", "ppaction://program")):
                                _fail("visual_invalid", "Không render nguồn Office có hành động chạy chương trình hoặc macro.")
                        if tag.lower() in {"oleobject", "object", "control", "instrtext", "fldsimple", "fldchar", "altchunk"}:
                            _fail("visual_invalid", "Nguồn Office chứa đối tượng chủ động hoặc lệnh trường chưa được hỗ trợ.")
                        if tag == "fld" and (node.tag != "{http://schemas.openxmlformats.org/drawingml/2006/main}fld"
                                or node.get("type", "").lower() not in {"slidenum", "datetime", "datetimefigureout", *[f"datetime{i}" for i in range(1, 14)]}):
                            _fail("visual_invalid", "Nguồn Office chứa lệnh trường chưa được hỗ trợ.")
                        if tag == "Override" or tag == "Default":
                            content_type = node.get("ContentType", "").lower()
                            if any(value in content_type for value in ("macroenabled", "vbaproject", "oleobject", "activex")):
                                _fail("visual_invalid", "Không render nguồn Office có macro hoặc đối tượng chủ động.")
                        if tag == "Relationship":
                            if node.get("TargetMode", "Internal").lower() != "internal":
                                _fail("visual_invalid", "Không xử lý nguồn Office có tài nguyên bên ngoài.")
                            relation_type = node.get("Type", "").lower()
                            relation_kind = relation_type.rsplit("/", 1)[-1]
                            if relation_kind in {"oleobject", "vbaproject", "control", "ctrlprop", "package", "attachedtemplate", "activexcontrol"}:
                                _fail("visual_invalid", "Không render nguồn Office có nội dung chủ động hoặc mẫu liên kết.")
                            # Validate even unused relationships before Office sees them.
                            self._resolve_relationship(name, node.get("Target"))
        except BaseException:
            self.archive.close()
            raise

    def close(self):
        self.archive.close()

    def tree(self, name):
        if name not in self.trees:
            _fail("visual_invalid", "Nguồn Office thiếu thành phần nội dung cần đọc.")
        return self.trees[name]

    @staticmethod
    def _resolve_relationship(name, target):
        if name == "_rels/.rels":
            return _target("", target)
        parent, filename = posixpath.split(name)
        if posixpath.basename(parent) != "_rels" or not filename.endswith(".rels"):
            _fail("visual_invalid", "Vị trí liên kết Office không hợp lệ.")
        part = posixpath.join(posixpath.dirname(parent), filename[:-5])
        return _target(part, target)

    def relationships(self, part):
        parent, filename = posixpath.split(part)
        rel_name = posixpath.join(parent, "_rels", filename + ".rels")
        if rel_name not in self.trees:
            return {}
        root = self.tree(rel_name)
        if _local(root.tag) != "Relationships":
            _fail("visual_invalid", "Cấu trúc liên kết Office không hợp lệ.")
        result = {}
        for item in root:
            if _local(item.tag) != "Relationship":
                continue
            identity = item.get("Id")
            if not identity or identity in result:
                _fail("visual_invalid", "Liên kết Office thiếu định danh hoặc bị trùng.")
            relation_type = item.get("Type", "")
            external = item.get("TargetMode", "Internal").lower() != "internal"
            target = None
            if not external and (self.active_renderer or relation_type.endswith("/image")):
                target = _target(part, item.get("Target"))
            result[identity] = {"type": relation_type, "part": target, "external": external}
        return result

    def images(self, part, element, locator):
        relationships = self.relationships(part)
        references = []

        def visit(node):
            if _local(node.tag) in {"del", "object"}:
                return
            for key, value in node.attrib.items():
                if (key == "{" + _REL_NS + "}embed"
                        or (_local(node.tag) == "blip" and key == "{" + _REL_NS + "}link")
                        or (_local(node.tag) == "imagedata" and key == "{" + _REL_NS + "}id")):
                    references.append(value)
            for child in node:
                visit(child)

        visit(element)
        seen, visuals, notes = set(), [], []
        for identity in references:
            relation = relationships.get(identity)
            if not relation or not relation["type"].endswith("/image"):
                _fail("visual_invalid", "Không tìm thấy liên kết ảnh nhúng trong phần nguồn.")
            if relation["external"]:
                notes.append("Bỏ qua ảnh liên kết ngoài; hệ thống không tải tài nguyên ngoài tài liệu.")
                continue
            target = relation["part"]
            if target in seen:
                continue
            seen.add(target)
            if target not in self.archive.names:
                _fail("visual_invalid", "Ảnh nhúng được tham chiếu không có trong tài liệu.")
            extension = PurePosixPath(target).suffix.lower().lstrip(".")
            if extension not in {"png", "jpg", "jpeg"}:
                notes.append("Có ảnh nhúng chưa hỗ trợ; hiện chỉ lấy PNG/JPEG.")
                continue
            if len(visuals) >= MAX_VISUALS:
                _fail("visual_limit", "Phần nguồn có quá 12 ảnh nhúng.")
            with self.archive.archive.open(target) as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
            if len(raw) > MAX_INPUT_BYTES:
                _fail("visual_limit", "Ảnh nhúng vượt giới hạn 20 MiB.")
            visuals.append(_asset(raw, extension, "embedded_image", locator, native_part=target))
            if sum(len(item["bytes"]) for item in visuals) > MAX_BUNDLE_BYTES:
                _fail("visual_limit", "Tổng ảnh nhúng vượt giới hạn 16 MiB.")
        return visuals, notes


def _slide(office, locator):
    presentation = office.tree("ppt/presentation.xml")
    if _local(presentation.tag) != "presentation":
        _fail("visual_invalid", "Nguồn PowerPoint không hợp lệ.")
    relationships = office.relationships("ppt/presentation.xml")
    listing = next((node for node in presentation if _local(node.tag) == "sldIdLst"), None)
    entries = [] if listing is None else [node for node in listing if _local(node.tag) == "sldId"]
    if len(entries) > MAX_PAGES_OR_SLIDES:
        _fail("visual_limit", "Nguồn PowerPoint vượt giới hạn 300 slide.")
    if locator["index"] > len(entries):
        _fail("visual_invalid", "Slide được chọn không tồn tại trong bản trình chiếu.")
    ids = [node.get("{" + _REL_NS + "}id") for node in entries]
    if None in ids or len(set(ids)) != len(ids):
        _fail("visual_invalid", "Định danh slide bị thiếu hoặc trùng trong bản trình chiếu.")
    relation = relationships.get(ids[locator["index"] - 1])
    if not relation or not relation["type"].endswith("/slide") or not relation["part"].startswith("ppt/slides/"):
        _fail("visual_invalid", "Không tìm thấy nội dung slide được chọn.")
    part = relation["part"]
    element = office.tree(part)
    if _local(element.tag) != "sld":
        _fail("visual_invalid", "Phần nguồn slide không hợp lệ.")
    return part, element


def _office_slide_render(raw, locator, part):
    if os.name != "nt":
        _fail("visual_unavailable", "Chưa có bộ render PowerPoint trên môi trường này.")
    executable = shutil.which("powershell")
    helper = Path(__file__).resolve().parents[2] / "scripts" / "render_learning_office.ps1"
    if not executable or not helper.is_file():
        _fail("visual_unavailable", "Chưa có bộ render PowerPoint trong môi trường hiện tại.")
    # A timed-out COM server can retain a file lock. Preserve the original error
    # instead of turning cleanup failure into a misleading invalid-input error.
    with tempfile.TemporaryDirectory(prefix="learning-slide-", ignore_cleanup_errors=True) as directory:
        folder = Path(directory)
        source, output = folder / "source.pptx", folder / "slide.png"
        source.write_bytes(raw)
        _run([executable, "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-File", str(helper),
              "-InputPath", str(source), "-OutputPath", str(output), "-SlideIndex", str(locator["index"]), "-MaxEdge", str(MAX_EDGE)],
             unavailable_codes=(3,))
        return _asset(_read_render(output), "png", "slide_render", locator, native_part=part, bbox=_FULL_REGION)


def _office(raw, source_format, locator):
    office = _Office(raw, active_renderer=source_format == "pptx")
    try:
        if source_format == "pptx":
            part, element = _slide(office, locator)
            try:
                return _bundle([_office_slide_render(raw, locator, part)])
            except MaterialsError as error:
                if error.code not in {"visual_unavailable", "visual_render_failed"}:
                    raise
                visuals, notes = office.images(part, element, locator)
                if not visuals:
                    raise error
                return _bundle(visuals, partial=True, notes=[_PARTIAL_WARNING, str(error), *notes])
        root = office.tree("word/document.xml")
        body = next((node for node in root if _local(node.tag) == "body"), None)
        if _local(root.tag) != "document" or body is None:
            _fail("visual_invalid", "Nguồn Word không có phần nội dung chính hợp lệ.")
        wanted = "p" if locator["kind"] == "paragraph" else "tbl"
        blocks = [block for block in _word_blocks(body) if _local(block.tag) == wanted]
        if locator["index"] > len(blocks):
            _fail("visual_invalid", "Đoạn hoặc bảng được chọn không tồn tại trong nguồn Word.")
        visuals, notes = office.images("word/document.xml", blocks[locator["index"] - 1], locator)
        return _bundle(visuals, partial=True, notes=[_PARTIAL_WARNING,
            "Không suy đoán số trang Word hoặc vị trí ảnh trên trang từ thứ tự đoạn/bảng.", *notes])
    finally:
        office.close()


def prepare_visuals(raw: bytes, source_format: str, locator: dict) -> dict:
    """Return source assets only. Callers pin the original source hash/revision.

    Errors use MaterialsError: visual_invalid (400), visual_limit (413),
    visual_unavailable (503), visual_render_failed (422).
    """
    try:
        _validate(raw, source_format, locator)
        locator = copy.deepcopy(locator)
        if source_format in {"png", "jpeg", "jpg"}:
            return _bundle([_asset(raw, source_format, "source_image", locator, bbox=_FULL_REGION)])
        if source_format == "pdf":
            return _pdf(raw, locator)
        return _office(raw, source_format, locator)
    except MaterialsError:
        raise
    except DocumentExtractionError as error:
        code = "visual_limit" if error.code == "document_limit" else "visual_invalid"
        if error.code == "extractor_unavailable":
            code = "visual_unavailable"
        raise MaterialsError(code, "Không đọc được nguồn hình trong giới hạn xử lý hiện tại.") from None
    except ImportError:
        raise MaterialsError("visual_unavailable", "Chưa có bộ đọc nguồn hình cần thiết.") from None
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, OverflowError, ET.ParseError):
        raise MaterialsError("visual_invalid", "Nguồn hình hoặc vị trí nguồn không hợp lệ.") from None
