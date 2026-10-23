"""Bounded lecture text import and standalone-image validation from bytes.

No file paths, links, macros, embedded files, JavaScript, or document actions are
opened or executed. The resulting text remains untrusted source material.
Byte/page/text caps are admission controls, not CPU/RAM isolation for pypdf.
"""

from __future__ import annotations

import io
import posixpath
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
import warnings
import xml.etree.ElementTree as ET
import zipfile


MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_OFFICE_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_OFFICE_MEMBERS = 1000
MAX_PAGES_OR_SLIDES = 300
MAX_TEXT_CHARACTERS = 1_000_000
MAX_WORD_UNITS = 10_000
MAX_XML_ELEMENTS = 200_000
MAX_XML_DEPTH = 100
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_DIMENSION = 10_000
EXTRACTOR_VERSION = "1"

TEXT_ONLY_WARNING = (
    "Chỉ trích xuất văn bản; hình ảnh, biểu đồ, công thức và bố cục chưa được "
    "kiểm tra. Không coi bản trích xuất là toàn bộ nội dung bài giảng."
)
BLANK_WARNING = (
    "Không tìm thấy văn bản có thể trích xuất ở vị trí này; có thể cần OCR "
    "hoặc kiểm tra trực quan."
)
IMAGE_WARNING = (
    "Chỉ kiểm tra và giữ ảnh nguồn. Chưa chạy OCR để đọc chữ, chưa diễn giải "
    "sơ đồ, công thức hay ý nghĩa trong ảnh. Cần xem ảnh gốc để đối chiếu."
)


class DocumentExtractionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _fail(code: str, message: str):
    raise DocumentExtractionError(code, message)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class _SafeTreeBuilder(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.depth = 0

    def start(self, tag, attrs):
        self.count += 1
        self.depth += 1
        if self.count > MAX_XML_ELEMENTS or self.depth > MAX_XML_DEPTH:
            _fail("document_limit", "Cấu trúc XML của tài liệu vượt giới hạn xử lý.")
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name, pubid, system):
        _fail("unsafe_xml", "Tài liệu XML chứa DTD hoặc khai báo thực thể không được hỗ trợ.")


class _OfficeArchive:
    def __init__(self, raw: bytes):
        self.archive = zipfile.ZipFile(io.BytesIO(raw))
        members = self.archive.infolist()
        if len(members) > MAX_OFFICE_MEMBERS:
            self.archive.close()
            _fail("document_limit", "Tài liệu Office có quá nhiều thành phần.")
        expanded = 0
        seen = set()
        for member in members:
            name = member.filename
            if (
                name in seen or "\\" in name or name.startswith("/")
                or ".." in PurePosixPath(name).parts
            ):
                self.archive.close()
                _fail("invalid_document", "Tên thành phần trong tài liệu Office không hợp lệ hoặc bị trùng.")
            seen.add(name)
            expanded += member.file_size
            if expanded > MAX_OFFICE_EXPANDED_BYTES:
                self.archive.close()
                _fail("document_limit", "Dung lượng giải nén của tài liệu Office vượt 50 MB.")
            if member.flag_bits & 1:
                self.archive.close()
                _fail("encrypted_document", "Hãy xuất một bản tài liệu không mã hóa để nhập bài giảng.")
        self.names = seen
        self.read_bytes = 0

    def close(self):
        self.archive.close()

    def xml(self, name: str):
        if name not in self.names:
            _fail("invalid_document", f"Tài liệu thiếu thành phần bắt buộc: {name}.")
        remaining = MAX_OFFICE_EXPANDED_BYTES - self.read_bytes
        with self.archive.open(name) as source:
            raw = source.read(remaining + 1)
        self.read_bytes += len(raw)
        if self.read_bytes > MAX_OFFICE_EXPANDED_BYTES:
            _fail("document_limit", "Dung lượng XML được đọc vượt giới hạn xử lý.")
        # Null removal also detects declarations in UTF-16/32 before parsing.
        folded = raw.replace(b"\x00", b"").lower()
        if b"<!doctype" in folded or b"<!entity" in folded:
            _fail("unsafe_xml", "Tài liệu XML chứa DTD hoặc khai báo thực thể không được hỗ trợ.")
        return ET.fromstring(raw, parser=ET.XMLParser(target=_SafeTreeBuilder()))


class _Units:
    def __init__(self):
        self.values = []
        self.characters = 0

    def add(self, kind: str, index: int, text: str, warnings=None):
        self.characters += len(text)
        if self.characters > MAX_TEXT_CHARACTERS:
            _fail("document_limit", "Văn bản trích xuất vượt giới hạn 1.000.000 ký tự.")
        notes = list(warnings or [])
        if not text.strip():
            notes.append(BLANK_WARNING)
        self.values.append({"locator": {"kind": kind, "index": index}, "text": text, "warnings": notes})


def _pdf(raw: bytes) -> dict:
    try:
        import pypdf
    except ImportError:
        _fail("extractor_unavailable", "Chưa có bộ đọc PDF (pypdf) trong môi trường chạy.")
    reader = pypdf.PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        _fail("encrypted_document", "PDF được mã hóa; hãy xuất một bản không mã hóa để nhập bài giảng.")
    if len(reader.pages) > MAX_PAGES_OR_SLIDES:
        _fail("document_limit", "PDF vượt giới hạn 300 trang.")
    units = _Units()
    for index, page in enumerate(reader.pages, 1):
        units.add("page", index, (page.extract_text() or "").strip("\r\n"))
    if not units.values:
        _fail("invalid_document", "PDF không có trang nào.")
    return {
        "format": "pdf",
        "extractor": {"name": "pypdf", "version": f"{pypdf.__version__}/adapter-{EXTRACTOR_VERSION}"},
        "units": units.values,
        "warnings": [TEXT_ONLY_WARNING, "Không chạy OCR. Thứ tự đọc, bảng và công thức trong PDF có thể bị mất cấu trúc; chú thích và tệp đính kèm bị bỏ qua."],
    }


def _reject_animated_png(raw: bytes) -> None:
    """Reject APNG, including an animation that declares only one frame."""
    offset = 8  # PNG signature was checked by the caller.
    while offset + 12 <= len(raw):
        length = int.from_bytes(raw[offset:offset + 4], "big")
        end = offset + length + 12
        if end > len(raw):
            _fail("invalid_image", "Ảnh PNG bị thiếu dữ liệu hoặc không hợp lệ.")
        kind = raw[offset + 4:offset + 8]
        if kind == b"acTL":
            _fail("invalid_image", "Chỉ hỗ trợ ảnh tĩnh PNG/JPEG; hãy xuất một khung hình của ảnh động.")
        if kind == b"IEND":
            return
        offset = end


def _image(raw: bytes, extension: str) -> dict:
    expected = "PNG" if extension == ".png" else "JPEG"
    signature_matches = raw.startswith(b"\x89PNG\r\n\x1a\n") if expected == "PNG" else raw.startswith(b"\xff\xd8\xff")
    if not signature_matches:
        _fail("invalid_image", "Nội dung ảnh không khớp với đuôi PNG/JPEG. Hãy xuất lại ảnh đúng định dạng.")
    if expected == "PNG":
        _reject_animated_png(raw)
    try:
        import PIL
        from PIL import Image
    except ImportError:
        _fail("extractor_unavailable", "Chưa có bộ kiểm tra ảnh Pillow trong môi trường chạy.")

    def check_header(image):
        if image.format != expected:
            _fail("invalid_image", "Nội dung ảnh không khớp với đuôi PNG/JPEG.")
        width, height = image.size
        if width < 1 or height < 1:
            _fail("invalid_image", "Kích thước ảnh không hợp lệ.")
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS:
            _fail("document_limit", "Ảnh vượt giới hạn 12 triệu pixel hoặc 10.000 pixel mỗi chiều. Hãy giảm kích thước ảnh.")
        if getattr(image, "n_frames", 1) != 1 or getattr(image, "is_animated", False):
            _fail("invalid_image", "Chỉ hỗ trợ ảnh tĩnh PNG/JPEG; hãy xuất một khung hình của ảnh động.")
        return width, height

    try:
        # Keep Pillow's own bomb protections enabled; elevate their warnings
        # locally instead of changing its global pixel limit or decoder flags.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=[expected]) as image:
                width, height = check_header(image)
                image.verify()
            # verify() checks the container. A fresh open+load also proves that
            # the pixels decode, and catches e.g. truncated JPEG scan data.
            with Image.open(io.BytesIO(raw), formats=[expected]) as image:
                check_header(image)
                image.load()
    except DocumentExtractionError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise DocumentExtractionError("document_limit", "Ảnh vượt giới hạn kích thước an toàn. Hãy giảm kích thước ảnh.") from error
    except Exception as error:
        raise DocumentExtractionError("invalid_image", "Không đọc được ảnh PNG/JPEG hoàn chỉnh. Hãy xuất lại một ảnh tĩnh hợp lệ.") from error
    return {
        "format": "png" if expected == "PNG" else "jpeg",
        "extractor": {"name": "pillow-image-validation", "version": f"{PIL.__version__}/adapter-{EXTRACTOR_VERSION}"},
        "image": {"width": width, "height": height, "mime_type": "image/png" if expected == "PNG" else "image/jpeg"},
        "units": [{"locator": {"kind": "image", "index": 1}, "text": "",
                   "warnings": ["Ảnh chưa có văn bản OCR hoặc mô tả đã được kiểm chứng."]}],
        "warnings": [IMAGE_WARNING],
    }


def _word_paragraph(element) -> str:
    pieces = []

    def visit(node):
        kind = _local(node.tag)
        if kind in {"drawing", "pict", "object", "del", "instrText"}:
            return
        if kind == "t":
            pieces.append(node.text or "")
        elif kind == "tab":
            pieces.append("\t")
        elif kind in {"br", "cr"}:
            pieces.append("\n")
        else:
            for child in node:
                visit(child)

    visit(element)
    return "".join(pieces)


def _word_blocks(parent):
    for child in parent:
        kind = _local(child.tag)
        if kind in {"p", "tbl"}:
            yield child
        elif kind in {"sdt", "sdtContent", "customXml", "ins"}:
            yield from _word_blocks(child)


def _word_table(table) -> str:
    rows = []
    for row in table:
        if _local(row.tag) != "tr":
            continue
        cells = []
        for cell in row:
            if _local(cell.tag) != "tc":
                continue
            cells.append("\n".join(
                _word_paragraph(block) if _local(block.tag) == "p" else _word_table(block)
                for block in _word_blocks(cell)
            ))
        rows.append("\t".join(cells))
    return "\n".join(rows)


def _docx(archive: _OfficeArchive) -> dict:
    root = archive.xml("word/document.xml")
    if _local(root.tag) != "document":
        _fail("invalid_document", "Không tìm thấy nội dung tài liệu Word hợp lệ.")
    body = next((child for child in root if _local(child.tag) == "body"), None)
    if body is None:
        _fail("invalid_document", "Tài liệu Word thiếu phần nội dung chính.")
    units = _Units()
    counts = {"paragraph": 0, "table": 0}
    for block in _word_blocks(body):
        if len(units.values) >= MAX_WORD_UNITS:
            _fail("document_limit", "Tài liệu Word có quá nhiều đoạn hoặc bảng.")
        kind = "paragraph" if _local(block.tag) == "p" else "table"
        counts[kind] += 1
        text = _word_paragraph(block) if kind == "paragraph" else _word_table(block)
        warnings = ["Bảng được chuyển thành văn bản theo hàng/ô; ô gộp và định dạng cần kiểm tra lại."] if kind == "table" else []
        units.add(kind, counts[kind], text, warnings)
    if not units.values:
        _fail("invalid_document", "Không tìm thấy đoạn văn hoặc bảng trong nội dung chính của Word.")
    return {
        "format": "docx", "extractor": {"name": "office-xml", "version": EXTRACTOR_VERSION},
        "units": units.values,
        "warnings": [TEXT_ONLY_WARNING, "Tham chiếu Word dùng thứ tự đoạn/bảng, không suy đoán số trang. Đầu/chân trang, chú thích, ghi chú cuối trang/cuối tài liệu, hộp văn bản và nội dung bị xóa trong Track Changes bị bỏ qua."],
    }


def _slide_target(target: str) -> str:
    decoded = unquote(target)
    parts = urlsplit(decoded)
    if parts.scheme or parts.netloc or parts.query or parts.fragment or "\\" in decoded:
        _fail("unsafe_relationship", "Liên kết slide phải trỏ tới nội dung nội bộ của tài liệu.")
    # Office relationships can use an absolute package path or a relative URI.
    path = posixpath.normpath(decoded.lstrip("/") if decoded.startswith("/") else "ppt/" + decoded)
    if not path.startswith("ppt/slides/") or not path.endswith(".xml"):
        _fail("unsafe_relationship", "Liên kết slide nằm ngoài vùng nội dung slide được hỗ trợ.")
    return path


def _pptx(archive: _OfficeArchive) -> dict:
    presentation = archive.xml("ppt/presentation.xml")
    relations = archive.xml("ppt/_rels/presentation.xml.rels")
    if _local(presentation.tag) != "presentation" or _local(relations.tag) != "Relationships":
        _fail("invalid_document", "Không tìm thấy cấu trúc PowerPoint hợp lệ.")
    mapping = {}
    for relation in relations:
        if _local(relation.tag) != "Relationship":
            continue
        key = relation.get("Id")
        if not key or key in mapping:
            _fail("invalid_document", "Định danh liên kết PowerPoint bị thiếu hoặc bị trùng.")
        mapping[key] = relation
        if relation.get("Type", "").endswith("/slide") and relation.get("TargetMode", "Internal") != "Internal":
            _fail("unsafe_relationship", "Không nhập slide trỏ ra tài liệu hoặc địa chỉ bên ngoài.")
    slide_list = next((child for child in presentation if _local(child.tag) == "sldIdLst"), None)
    slide_ids = [] if slide_list is None else [child for child in slide_list if _local(child.tag) == "sldId"]
    if not slide_ids:
        _fail("invalid_document", "PowerPoint không có slide nào.")
    if len(slide_ids) > MAX_PAGES_OR_SLIDES:
        _fail("document_limit", "PowerPoint vượt giới hạn 300 slide.")
    units = _Units()
    seen_slide_relations = set()
    for index, slide_id in enumerate(slide_ids, 1):
        relation_id = next((value for key, value in slide_id.attrib.items() if key.startswith("{") and _local(key) == "id"), None)
        if relation_id in seen_slide_relations:
            _fail("invalid_document", "Danh sách trình chiếu tham chiếu trùng một liên kết slide.")
        seen_slide_relations.add(relation_id)
        relation = mapping.get(relation_id)
        if relation is None or not relation.get("Type", "").endswith("/slide") or not relation.get("Target"):
            _fail("invalid_document", "Không tìm thấy liên kết nội dung cho một slide.")
        slide = archive.xml(_slide_target(relation.get("Target")))
        if _local(slide.tag) != "sld":
            _fail("invalid_document", "Thành phần slide không có cấu trúc hợp lệ.")
        paragraphs = []
        for paragraph in slide.iter():
            if _local(paragraph.tag) != "p":
                continue
            pieces = []
            for child in paragraph.iter():
                kind = _local(child.tag)
                if kind == "t":
                    pieces.append(child.text or "")
                elif kind == "br":
                    pieces.append("\n")
            paragraphs.append("".join(pieces))
        units.add("slide", index, "\n".join(paragraphs))
    return {
        "format": "pptx", "extractor": {"name": "office-xml", "version": EXTRACTOR_VERSION},
        "units": units.values,
        "warnings": [TEXT_ONLY_WARNING, "Giữ thứ tự slide của bản trình chiếu, kể cả slide ẩn. Văn bản trong từng slide theo cấu trúc XML, có thể khác thứ tự nhìn. Ghi chú thuyết trình, bình luận, slide master/layout, biểu đồ và nội dung nhúng bị bỏ qua."],
    }


def extract_document(filename: str, raw: bytes) -> dict:
    """Extract one local snapshot; fail rather than silently truncate content."""
    if not isinstance(filename, str) or not filename or not isinstance(raw, bytes):
        _fail("invalid_input", "Cần tên tệp và nội dung tệp dạng bytes.")
    extension = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if extension in {".doc", ".ppt"}:
        _fail("legacy_format", "Hãy chuyển tệp .doc/.ppt sang .docx/.pptx hoặc xuất PDF trước khi nhập.")
    image_extension = extension in {".png", ".jpg", ".jpeg"}
    if extension not in {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}:
        _fail("unsupported_format", "Chỉ hỗ trợ PDF, Word .docx, PowerPoint .pptx và ảnh tĩnh PNG/JPEG.")
    if not raw:
        _fail("invalid_image" if image_extension else "invalid_document", "Tệp bài giảng đang trống.")
    if len(raw) > MAX_INPUT_BYTES:
        _fail("document_limit", "Tệp bài giảng vượt giới hạn 20 MB.")
    archive = None
    try:
        if image_extension:
            return _image(raw, extension)
        if extension == ".pdf":
            return _pdf(raw)
        archive = _OfficeArchive(raw)
        return _docx(archive) if extension == ".docx" else _pptx(archive)
    except DocumentExtractionError:
        raise
    except Exception as error:
        # Library exceptions can contain source snippets or implementation paths;
        # expose a bounded, stable message rather than the exception's contents.
        raise DocumentExtractionError("invalid_document", "Không đọc được cấu trúc tài liệu; hãy xuất lại thành PDF, DOCX hoặc PPTX hợp lệ.") from error
    finally:
        if archive is not None:
            archive.close()
