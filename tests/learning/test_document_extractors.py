from __future__ import annotations

import io
import struct
import warnings
import zipfile
import zlib

import pypdf
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import pytest

from core.learning import document_extractors as extractors
from core.learning.document_extractors import DocumentExtractionError, extract_document


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


def office(entries):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return target.getvalue()


def word(content):
    return office({"word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{content}</w:body></w:document>'})


def presentation(order=("r2", "r1"), *, relations=None, slides=None):
    if relations is None:
        relations = (
            f'<Relationship Id="r1" Type="{R}/slide" Target="slides/slide1.xml"/>'
            f'<Relationship Id="r2" Type="{R}/slide" Target="slides/slide2.xml"/>'
        )
    if slides is None:
        slides = {"slide1.xml": "First file", "slide2.xml": "Second file"}
    entries = {
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
        + "".join(f'<p:sldId id="{index + 256}" r:id="{item}"/>' for index, item in enumerate(order))
        + "</p:sldIdLst></p:presentation>",
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{PR}">{relations}</Relationships>',
    }
    entries.update({
        f"ppt/slides/{name}": f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
        f'<p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>'
        "</p:spTree></p:cSld></p:sld>"
        for name, text in slides.items()
    })
    return office(entries)


def pdf(pages=("First page", None, "Last page"), *, encrypted=False):
    writer = pypdf.PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=200, height=200)
        if text is None:
            continue
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        })
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("password")
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


def error_code(filename, raw):
    with pytest.raises(DocumentExtractionError) as error:
        extract_document(filename, raw)
    assert str(error.value)
    return error.value.code


def test_pdf_keeps_real_page_numbers_including_blank_pages():
    result = extract_document("lecture.PDF", pdf())
    assert result["format"] == "pdf"
    assert result["extractor"]["name"] == "pypdf"
    assert pypdf.__version__ in result["extractor"]["version"]
    assert [unit["locator"] for unit in result["units"]] == [
        {"kind": "page", "index": 1}, {"kind": "page", "index": 2}, {"kind": "page", "index": 3},
    ]
    assert [unit["text"] for unit in result["units"]] == ["First page", "", "Last page"]
    assert result["units"][1]["warnings"] == [extractors.BLANK_WARNING]
    assert any("OCR" in warning for warning in result["warnings"])


def test_encrypted_pdf_is_rejected_without_trying_to_guess_password():
    assert error_code("private.pdf", pdf(encrypted=True)) == "encrypted_document"


def test_pdf_page_limit_fails_the_whole_import(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_PAGES_OR_SLIDES", 2)
    assert error_code("long.pdf", pdf()) == "document_limit"


def test_word_preserves_mixed_body_order_and_does_not_invent_pages():
    result = extract_document("lecture.docx", word(
        '<w:p><w:r><w:t xml:space="preserve">  before</w:t><w:tab/><w:t>code</w:t><w:br/><w:t>line</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p><w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        '<w:sdt><w:sdtContent><w:p><w:r><w:t>Sau bảng</w:t></w:r></w:p></w:sdtContent></w:sdt>'
    ))
    assert [unit["locator"] for unit in result["units"]] == [
        {"kind": "paragraph", "index": 1}, {"kind": "table", "index": 1}, {"kind": "paragraph", "index": 2},
    ]
    assert [unit["text"] for unit in result["units"]] == ["  before\tcode\nline", "A\tB\nC", "Sau bảng"]
    assert result["units"][1]["warnings"]
    assert any("không suy đoán số trang" in warning for warning in result["warnings"])


def test_word_ignores_deleted_and_embedded_text_and_warns_about_omissions():
    result = extract_document("lecture.docx", word(
        '<w:p><w:del><w:r><w:t>deleted</w:t></w:r></w:del>'
        '<w:r><w:drawing><w:t>shape</w:t></w:drawing><w:t>current</w:t></w:r></w:p>'
    ))
    assert result["units"][0]["text"] == "current"
    assert any("Track Changes" in warning for warning in result["warnings"])


def test_powerpoint_uses_presentation_relationship_order_not_filenames():
    result = extract_document("lecture.pptx", presentation())
    assert [unit["text"] for unit in result["units"]] == ["Second file", "First file"]
    assert [unit["locator"] for unit in result["units"]] == [
        {"kind": "slide", "index": 1}, {"kind": "slide", "index": 2},
    ]
    assert any("Ghi chú thuyết trình" in warning for warning in result["warnings"])


def test_blank_powerpoint_slide_is_kept_and_flagged():
    result = extract_document("lecture.pptx", presentation(order=("r1",), slides={"slide1.xml": ""}))
    assert result["units"][0]["text"] == ""
    assert extractors.BLANK_WARNING in result["units"][0]["warnings"]


def test_powerpoint_accepts_absolute_package_path():
    result = extract_document("lecture.pptx", presentation(
        order=("r1",), relations=f'<Relationship Id="r1" Type="{R}/slide" Target="/ppt/slides/slide1.xml"/>',
    ))
    assert result["units"][0]["text"] == "First file"


@pytest.mark.parametrize("target", ["https://example.org/slide.xml", "file:///secret.xml", "../word/document.xml", "../../secret.xml", "%2e%2e/word/document.xml", "slides/slide1.xml#part", "slides\\slide1.xml"])
def test_unsafe_powerpoint_slide_targets_are_rejected(target):
    raw = presentation(order=("r1",), relations=f'<Relationship Id="r1" Type="{R}/slide" Target="{target}"/>')
    assert error_code("lecture.pptx", raw) == "unsafe_relationship"


def test_even_an_unused_external_slide_relation_is_rejected():
    raw = presentation(order=("r1",), relations=(
        f'<Relationship Id="r1" Type="{R}/slide" Target="slides/slide1.xml"/>'
        f'<Relationship Id="r2" Type="{R}/slide" Target="https://example.org/slide.xml" TargetMode="External"/>'
    ))
    assert error_code("lecture.pptx", raw) == "unsafe_relationship"


def test_duplicate_powerpoint_relationship_ids_are_rejected():
    raw = presentation(order=("r1",), relations=(
        f'<Relationship Id="r1" Type="{R}/slide" Target="slides/slide1.xml"/>'
        f'<Relationship Id="r1" Type="{R}/slide" Target="slides/slide2.xml"/>'
    ))
    assert error_code("lecture.pptx", raw) == "invalid_document"


def test_repeated_slide_relationship_in_presentation_is_rejected():
    assert error_code("lecture.pptx", presentation(order=("r1", "r1"))) == "invalid_document"


@pytest.mark.parametrize("raw", [
    presentation(order=("missing",)),
    presentation(order=("r1",), relations=f'<Relationship Id="r1" Type="{R}/slide" Target="slides/absent.xml"/>'),
    presentation(order=("r1",), relations=f'<Relationship Id="r1" Type="{R}/image" Target="slides/slide1.xml"/>'),
    presentation(order=("r1",), relations=f'<Relationship Id="r1" Type="{R}/slide"/>'),
])
def test_missing_or_wrong_slide_relationship_fails_instead_of_skipping(raw):
    assert error_code("lecture.pptx", raw) == "invalid_document"


def test_powerpoint_slide_limit_fails_the_whole_import(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_PAGES_OR_SLIDES", 1)
    assert error_code("long.pptx", presentation()) == "document_limit"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_dtd_and_entities_rejected_before_xml_expansion(encoding):
    xml = f'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY boom "expanded">]><w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>&boom;</w:t></w:r></w:p></w:body></w:document>'
    assert error_code("lecture.docx", office({"word/document.xml": xml.encode(encoding)})) == "unsafe_xml"


def test_unneeded_office_parts_are_not_parsed_or_executed():
    document = f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>Lesson</w:t></w:r></w:p></w:body></w:document>'
    result = extract_document("lecture.docx", office({
        "word/document.xml": document,
        "word/embeddings/script.xml": b"<!DOCTYPE unsafe [<!ENTITY x SYSTEM 'https://example.org'>]>",
        "word/vbaProject.bin": b"not executable",
        "word/header1.xml": b"not even XML",
    }))
    assert result["units"][0]["text"] == "Lesson"


@pytest.mark.parametrize("filename,code", [
    ("old.doc", "legacy_format"), ("old.ppt", "legacy_format"),
    ("macro.docm", "unsupported_format"), ("macro.pptm", "unsupported_format"),
    ("image.gif", "unsupported_format"), ("lecture", "unsupported_format"),
])
def test_unsupported_extensions_give_stable_actionable_errors(filename, code):
    assert error_code(filename, b"irrelevant") == code


@pytest.mark.parametrize("filename,raw", [("bad.pdf", b"bad"), ("bad.docx", b"not zip"), ("bad.pptx", b""), ("bad.docx", office({"word/document.xml": "<broken>"}))])
def test_malformed_files_fail_with_controlled_error(filename, raw):
    assert error_code(filename, raw) == "invalid_document"


def test_input_and_expanded_size_limits_cover_ignored_members(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_INPUT_BYTES", 10)
    assert error_code("lecture.pdf", b"x" * 11) == "document_limit"
    monkeypatch.setattr(extractors, "MAX_INPUT_BYTES", 1024 * 1024)
    monkeypatch.setattr(extractors, "MAX_OFFICE_EXPANDED_BYTES", 100)
    assert error_code("lecture.docx", office({"ignored.txt": "x" * 101})) == "document_limit"


def test_member_count_limit(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_OFFICE_MEMBERS", 1)
    assert error_code("lecture.docx", office({"a": "", "b": ""})) == "document_limit"


@pytest.mark.parametrize("filename,raw", [
    ("lecture.pdf", pdf(("one", "two"))),
    ("lecture.docx", word("<w:p><w:r><w:t>one</w:t></w:r></w:p><w:p><w:r><w:t>two</w:t></w:r></w:p>")),
    ("lecture.pptx", presentation()),
])
def test_total_text_limit_applies_to_all_formats_without_partial_result(monkeypatch, filename, raw):
    monkeypatch.setattr(extractors, "MAX_TEXT_CHARACTERS", 5)
    assert error_code(filename, raw) == "document_limit"


def test_word_unit_and_xml_depth_limits(monkeypatch):
    monkeypatch.setattr(extractors, "MAX_WORD_UNITS", 1)
    assert error_code("lecture.docx", word("<w:p/><w:p/>")) == "document_limit"
    monkeypatch.setattr(extractors, "MAX_XML_DEPTH", 3)
    assert error_code("lecture.docx", word("<w:p><w:r><w:t>too deep</w:t></w:r></w:p>")) == "document_limit"


def test_duplicate_zip_names_rejected():
    target = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("word/document.xml", "first")
            archive.writestr("word/document.xml", "second")
    assert error_code("lecture.docx", target.getvalue()) == "invalid_document"


def test_zip_traversal_names_rejected_without_extracting_files():
    assert error_code("lecture.docx", office({"../outside.xml": "bad"})) == "invalid_document"


def raster(format="PNG", size=(13, 7)):
    from PIL import Image

    target = io.BytesIO()
    with Image.new("RGB", size, (25, 150, 90)) as image:
        image.save(target, format=format)
    return target.getvalue()


@pytest.mark.parametrize("filename,format,normalized,mime", [
    ("figure.png", "PNG", "png", "image/png"),
    ("figure.jpeg", "JPEG", "jpeg", "image/jpeg"),
    ("figure.JPG", "JPEG", "jpeg", "image/jpeg"),
])
def test_standalone_images_validate_without_inventing_text_or_semantics(filename, format, normalized, mime):
    result = extract_document(filename, raster(format))
    assert result["format"] == normalized
    assert result["image"] == {"width": 13, "height": 7, "mime_type": mime}
    assert result["extractor"]["name"] == "pillow-image-validation"
    assert result["extractor"]["version"]
    assert len(result["units"]) == 1
    assert result["units"][0]["locator"] == {"kind": "image", "index": 1}
    assert result["units"][0]["text"] == ""
    assert any("OCR" in warning for warning in result["units"][0]["warnings"])
    assert any("chưa diễn giải" in warning for warning in result["warnings"])
    assert extractors.TEXT_ONLY_WARNING not in result["warnings"]
    assert extractors.BLANK_WARNING not in result["units"][0]["warnings"]


@pytest.mark.parametrize("filename,actual_format", [("figure.png", "JPEG"), ("figure.jpg", "PNG"), ("figure.jpeg", "PNG"), ("figure.png", "GIF")])
def test_image_extension_must_match_actual_signature(filename, actual_format):
    assert error_code(filename, raster(actual_format)) == "invalid_image"


@pytest.mark.parametrize("filename,raw", [
    ("empty.png", b""),
    ("fake.png", b"<svg xmlns='http://www.w3.org/2000/svg'/>") ,
    ("fake.jpg", b"not a JPEG"),
    ("corrupt.png", b"\x89PNG\r\n\x1a\ninvalid data"),
    ("corrupt.jpeg", b"\xff\xd8\xffinvalid data"),
])
def test_invalid_images_have_stable_errors_without_decoder_internals(filename, raw):
    assert error_code(filename, raw) == "invalid_image"


def test_truncated_jpeg_pixels_are_rejected_even_when_header_opens():
    raw = raster("JPEG", size=(128, 128))
    assert error_code("truncated.jpg", raw[:-30]) == "invalid_image"


def test_corrupted_png_checksum_is_rejected():
    raw = bytearray(raster())
    raw[29] ^= 1  # Corrupt the IHDR CRC while preserving its dimensions.
    assert error_code("corrupt.png", bytes(raw)) == "invalid_image"


def test_image_dimension_cap_is_checked_before_pixel_decoding(monkeypatch):
    from PIL import Image

    raw = raster(size=(10_001, 1))

    def forbidden_load(*args, **kwargs):
        raise AssertionError("Oversize image must not reach pixel decoding")

    monkeypatch.setattr(Image.Image, "load", forbidden_load)
    assert error_code("wide.png", raw) == "document_limit"


def test_image_pixel_cap_applies_even_when_each_dimension_is_small(monkeypatch):
    raw = raster(size=(13, 7))
    monkeypatch.setattr(extractors, "MAX_IMAGE_PIXELS", 90)
    assert error_code("dense.png", raw) == "document_limit"


def test_image_input_bytes_use_existing_document_limit(monkeypatch):
    raw = raster()
    monkeypatch.setattr(extractors, "MAX_INPUT_BYTES", len(raw) - 1)
    assert error_code("large.png", raw) == "document_limit"


def _png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def test_extreme_png_header_gets_controlled_limit_error():
    # Tiny synthetic container; no huge pixel allocation occurs in this test.
    ihdr = struct.pack(">IIBBBBB", 100_000, 100_000, 8, 2, 0, 0, 0)
    raw = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(b"")) + _png_chunk(b"IEND", b"")
    assert error_code("bomb.png", raw) == "document_limit"


def test_apng_multiple_frames_are_rejected():
    from PIL import Image

    target = io.BytesIO()
    with Image.new("RGB", (4, 4), "red") as first, Image.new("RGB", (4, 4), "blue") as second:
        first.save(target, format="PNG", save_all=True, append_images=[second], duration=100, loop=0)
    raw = target.getvalue()
    assert b"acTL" in raw
    assert error_code("animated.png", raw) == "invalid_image"


def test_apng_declaring_one_frame_is_also_rejected():
    # A valid static container gains an APNG animation declaration. Even a
    # single declared frame is out of scope; do not treat it as a static PNG.
    raw = raster()
    end_ihdr = 8 + 12 + 13
    declared_animation = raw[:end_ihdr] + _png_chunk(b"acTL", struct.pack(">II", 1, 0)) + raw[end_ihdr:]
    assert error_code("single-frame-apng.png", declared_animation) == "invalid_image"


def test_multiframe_mpo_disguised_as_jpeg_is_rejected():
    from PIL import Image

    target = io.BytesIO()
    with Image.new("RGB", (4, 4), "red") as first, Image.new("RGB", (4, 4), "blue") as second:
        first.save(target, format="MPO", save_all=True, append_images=[second])
    assert error_code("multiple.jpg", target.getvalue()) == "invalid_image"


def test_image_validation_does_not_weaken_pillow_global_safety():
    from PIL import Image, ImageFile

    before = (Image.MAX_IMAGE_PIXELS, ImageFile.LOAD_TRUNCATED_IMAGES)
    extract_document("figure.png", raster())
    assert (Image.MAX_IMAGE_PIXELS, ImageFile.LOAD_TRUNCATED_IMAGES) == before
