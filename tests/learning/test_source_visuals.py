"""Source pixels/provenance and bounded failure paths; no model calls."""
from __future__ import annotations

import copy
import io
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

from PIL import Image
import pypdf
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest

from core.learning import source_visuals as engine
from core.learning.materials import MaterialsError

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"


@pytest.fixture(autouse=True)
def temporary_files_stay_in_test_directory(monkeypatch, tmp_path):
    # Some managed Windows temp roots permit mkdir but not child-file writes.
    monkeypatch.setattr(engine.tempfile, "tempdir", str(tmp_path))


def picture(size=(30, 20), format="PNG", color=(230, 20, 30)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format)
    return output.getvalue()


def package(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def relationships(items):
    return f'<Relationships xmlns="{PR}">{items}</Relationships>'


def image_ref(identity):
    return f'<w:r><w:drawing><a:blip r:embed="{identity}"/></w:drawing></w:r>'


def document(body, *, images=None, extra=None, relation_text=None):
    images = images or {}
    relations = relation_text if relation_text is not None else "".join(
        f'<Relationship Id="{key}" Type="{R}/image" Target="media/{key}.png"/>' for key in images)
    entries = {"word/document.xml": f'<w:document xmlns:w="{W}" xmlns:a="{A}" xmlns:r="{R}"><w:body>{body}</w:body></w:document>',
               "word/_rels/document.xml.rels": relationships(relations)}
    entries.update({f"word/media/{key}.png": value for key, value in images.items()})
    entries.update(extra or {})
    return package(entries)


def presentation(*, picture_bytes=None, extra=None, slide_extra=""):
    entries = {
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
        '<p:sldId id="256" r:id="second"/><p:sldId id="257" r:id="first"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": relationships(
            f'<Relationship Id="first" Type="{R}/slide" Target="slides/slide1.xml"/>'
            f'<Relationship Id="second" Type="{R}/slide" Target="slides/slide2.xml"/>'),
    }
    for number in (1, 2):
        image = '<p:pic><p:blipFill><a:blip r:embed="image"/></p:blipFill></p:pic>' if picture_bytes and number == 2 else ""
        entries[f"ppt/slides/slide{number}.xml"] = f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>' \
            f'<p:sp><p:txBody><a:p><a:r><a:t>CPU {number}</a:t></a:r></a:p></p:txBody></p:sp>' \
            f'<p:cxnSp/><p:sp><p:txBody><a:p><a:r><a:t>Memory</a:t></a:r></a:p></p:txBody></p:sp>{image}{slide_extra}' \
            '</p:spTree></p:cSld></p:sld>'
    if picture_bytes:
        entries["ppt/slides/_rels/slide2.xml.rels"] = relationships(f'<Relationship Id="image" Type="{R}/image" Target="../media/diagram.png"/>')
        entries["ppt/media/diagram.png"] = picture_bytes
    entries.update(extra or {})
    return package(entries)


def pdf():
    writer = pypdf.PdfWriter()
    for color in ("1 0 0", "0 0 1"):
        page = writer.add_blank_page(width=240, height=120)
        stream = DecodedStreamObject()
        stream.set_data(f"{color} rg 0 0 240 120 re f".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        page[NameObject("/Resources")] = DictionaryObject()
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def error_code(raw, format, locator):
    with pytest.raises(MaterialsError) as error:
        engine.prepare_visuals(raw, format, locator)
    return error.value.code


def unavailable(*args, **kwargs):
    raise MaterialsError("visual_unavailable", "PowerPoint unavailable.")


@pytest.mark.parametrize("format,extension,mime", [("PNG", "png", "image/png"), ("JPEG", "jpeg", "image/jpeg"), ("JPEG", "jpg", "image/jpeg")])
def test_source_image_retains_bytes_and_provenance(format, extension, mime):
    raw, locator = picture(format=format), {"kind": "image", "index": 1}
    result = engine.prepare_visuals(raw, extension, locator)
    visual = result["visuals"][0]
    assert result["version"] == "source-visuals-v1" and result["status"] == "ready"
    assert visual == {"kind": "source_image", "mime_type": mime, "bytes": raw, "width": 30, "height": 20,
                      "locator": locator, "native_part": None, "bbox": [0, 0, 1, 1], "warnings": []}
    locator["index"] = 99
    assert visual["locator"]["index"] == 1


def test_large_image_is_bounded_without_changing_input():
    raw = picture((2400, 1200))
    result = engine.prepare_visuals(raw, "png", {"kind": "image", "index": 1})
    visual = result["visuals"][0]
    assert (visual["width"], visual["height"]) == (1800, 900)
    assert visual["bytes"] != raw and visual["warnings"]
    assert Image.open(io.BytesIO(raw)).size == (2400, 1200)


@pytest.mark.parametrize("size,expected_size", [((60, 40), (40, 60)), ((2400, 1200), (900, 1800))])
def test_jpeg_exif_orientation_normalized_before_resizing(size, expected_size):
    source = Image.new("RGB", size, "red")
    source.paste("blue", (size[0] // 2, 0, size[0], size[1]))
    exif = Image.Exif()
    exif[274] = 6
    buffer = io.BytesIO()
    source.save(buffer, "JPEG", quality=95, exif=exif)
    raw = buffer.getvalue()
    visual = engine.prepare_visuals(raw, "jpeg", {"kind": "image", "index": 1})["visuals"][0]
    assert (visual["width"], visual["height"]) == expected_size
    assert visual["mime_type"] == "image/jpeg" and visual["warnings"]
    with Image.open(io.BytesIO(visual["bytes"])) as rendered:
        assert rendered.size == expected_size and rendered.getexif().get(274, 1) == 1
        width, height = rendered.size
        top = rendered.getpixel((width // 2, height // 4))
        bottom = rendered.getpixel((width // 2, 3 * height // 4))
        assert top[0] > 200 and top[2] < 40 and bottom[2] > 200 and bottom[0] < 40
    with Image.open(io.BytesIO(raw)) as original:
        assert original.size == size and original.getexif()[274] == 6


@pytest.mark.parametrize("format,locator", [
    ("pdf", {"kind": "slide", "index": 1}), ("pptx", {"kind": "page", "index": 1}),
    ("png", {"kind": "image", "index": 2}), ("png", {"kind": "image", "index": True}),
    ("docx", {"kind": "paragraph", "index": 0}), ("docx", {"kind": "paragraph", "index": 1, "page": 3}),
    ("svg", {"kind": "image", "index": 1}), ("png", {"kind": ["image"], "index": 1}),
])
def test_wrong_locator_and_format_rejected_before_subprocess(monkeypatch, format, locator):
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: pytest.fail("Must not render invalid locator"))
    assert error_code(picture(), format, locator) == "visual_invalid"


def test_pdf_page_bounds_checked_without_renderer(monkeypatch):
    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: pytest.fail("Out-of-range PDF page"))
    assert error_code(pdf(), "pdf", {"kind": "page", "index": 3}) == "visual_invalid"
    assert error_code(b"invalid PDF", "pdf", {"kind": "page", "index": 1}) == "visual_invalid"


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm not installed")
def test_real_pdf_renders_exact_selected_page():
    result = engine.prepare_visuals(pdf(), "pdf", {"kind": "page", "index": 2})
    visual = result["visuals"][0]
    assert visual["kind"] == "page_render" and visual["locator"] == {"kind": "page", "index": 2}
    assert (visual["width"], visual["height"]) == (1800, 900)
    assert visual["native_part"] is None and visual["bbox"] == [0, 0, 1, 1]
    with Image.open(io.BytesIO(visual["bytes"])) as image:
        assert image.getpixel((900, 450))[:3] == (0, 0, 255)


def test_pdf_timeout_has_stable_error_and_removes_temporary_files(monkeypatch):
    captured = []
    monkeypatch.setattr(engine.shutil, "which", lambda name: "renderer")
    def timeout(command, **options):
        captured.append(Path(command[-2]))
        assert options["shell"] is False and options["timeout"] == 30
        assert options["stdin"] == subprocess.DEVNULL
        raise subprocess.TimeoutExpired(command, 30)
    monkeypatch.setattr(engine.subprocess, "run", timeout)
    assert error_code(pdf(), "pdf", {"kind": "page", "index": 1}) == "visual_render_failed"
    assert captured and not captured[0].exists()


def test_pdf_missing_renderer_is_unavailable(monkeypatch):
    monkeypatch.setattr(engine.shutil, "which", lambda name: None)
    assert error_code(pdf(), "pdf", {"kind": "page", "index": 1}) == "visual_unavailable"


def test_docx_selected_paragraph_excludes_nested_table_paragraphs_and_other_images():
    raw = document(f'<w:p>{image_ref("first")}</w:p><w:tbl><w:tr><w:tc><w:p>{image_ref("table")}</w:p></w:tc></w:tr></w:tbl>'
                   f'<w:sdt><w:sdtContent><w:p>{image_ref("second")}</w:p></w:sdtContent></w:sdt>',
                   images={"first": picture(color="red"), "table": picture(color="green"), "second": picture(color="blue")})
    result = engine.prepare_visuals(raw, "docx", {"kind": "paragraph", "index": 2})
    assert result["status"] == "partial" and len(result["visuals"]) == 1
    visual = result["visuals"][0]
    assert visual["native_part"] == "word/media/second.png" and visual["bbox"] is None
    assert visual["locator"] == {"kind": "paragraph", "index": 2}
    assert visual["bytes"] == picture(color="blue")
    table = engine.prepare_visuals(raw, "docx", {"kind": "table", "index": 1})["visuals"][0]
    assert table["native_part"] == "word/media/table.png" and table["bbox"] is None


def test_docx_never_invents_page_and_ignores_deleted_images():
    raw = document(f'<w:p><w:del>{image_ref("old")}</w:del><w:r><w:t>Text</w:t></w:r></w:p>', images={"old": picture()})
    result = engine.prepare_visuals(raw, "docx", {"kind": "paragraph", "index": 1})
    assert result["status"] == "partial" and result["visuals"] == []
    assert any("số trang Word" in note for note in result["warnings"])
    assert error_code(raw, "docx", {"kind": "paragraph", "index": 2}) == "visual_invalid"
    assert error_code(raw, "docx", {"kind": "table", "index": 1}) == "visual_invalid"


def test_pptx_selected_slide_native_shapes_reach_whole_slide_renderer(monkeypatch):
    captured = []
    raw = presentation(extra={"_rels/.rels": relationships(
        '<Relationship Id="core" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'),
        "docProps/core.xml": "<coreProperties/>"})
    def render(actual, locator, part):
        captured.append((actual, copy.deepcopy(locator), part))
        return engine._asset(picture(), "png", "slide_render", locator, native_part=part, bbox=[0, 0, 1, 1])
    monkeypatch.setattr(engine, "_office_slide_render", render)
    result = engine.prepare_visuals(raw, "pptx", {"kind": "slide", "index": 1})
    assert captured == [(raw, {"kind": "slide", "index": 1}, "ppt/slides/slide2.xml")]
    assert result["status"] == "ready" and result["visuals"][0]["kind"] == "slide_render"


def test_pptx_fallback_is_explicitly_partial_and_only_selected_images(monkeypatch):
    monkeypatch.setattr(engine, "_office_slide_render", unavailable)
    raw = presentation(picture_bytes=picture())
    result = engine.prepare_visuals(raw, "pptx", {"kind": "slide", "index": 1})
    assert result["status"] == "partial" and len(result["visuals"]) == 1
    assert result["visuals"][0]["native_part"] == "ppt/media/diagram.png"
    assert result["visuals"][0]["kind"] == "embedded_image" and result["visuals"][0]["bbox"] is None
    assert any("hình vector" in text for text in result["warnings"])
    assert error_code(raw, "pptx", {"kind": "slide", "index": 2}) == "visual_unavailable"


@pytest.mark.parametrize("extra", [
    {"ppt/vbaProject.bin": b"macro"}, {"ppt/embeddings/object.bin": b"embedded"},
    {"ppt/activeX/control.xml": "<control/>"}, {"ppt/media/vector.svg": '<svg/>'},
    {"ppt/slides/_rels/slide1.xml.rels": relationships(f'<Relationship Id="remote" Type="{R}/image" Target="https://example.org/image.png" TargetMode="External"/>')},
    {"ppt/slides/_rels/slide1.xml.rels": relationships(f'<Relationship Id="remote" Type="{R}/image" Target="file:///C:/private.png"/>')},
    {"ppt/slides/_rels/slide1.xml.rels": relationships(f'<Relationship Id="escape" Type="{R}/image" Target="../../../../outside.png"/>')},
    {"ppt/slides/_rels/slide1.xml.rels": relationships(f'<Relationship Id="template" Type="{R}/attachedTemplate" Target="../template.xml"/>')},
    {"ppt/slides/slide1.xml": '<!DOCTYPE s [<!ENTITY x SYSTEM "file:///private">]><s/>'},
    {"ppt/slides/slide1.xml": '<broken>'},
    {"ppt/slides/slide1.xml": '<s><imagedata src="https://example.org/image.png"/></s>'},
    {"ppt/slides/slide1.xml": '<s><hlinkClick action="ppaction://program?file=tool.exe"/></s>'},
    {"[Content_Types].xml": '<Types><Override ContentType="application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml"/></Types>'},
])
def test_active_external_or_malformed_office_rejected_before_render(monkeypatch, extra):
    monkeypatch.setattr(engine, "_office_slide_render", lambda *a: pytest.fail("Unsafe source reached Office"))
    assert error_code(presentation(extra=extra), "pptx", {"kind": "slide", "index": 1}) == "visual_invalid"


@pytest.mark.parametrize("field", ["<w:fldSimple w:instr='INCLUDEPICTURE https://example.org/x'/>",
    "<w:r><w:instrText>DDEAUTO</w:instrText></w:r>", "<w:r><w:fldChar w:fldCharType='begin'/></w:r>"])
def test_word_fields_are_not_evaluated_by_passive_reader_but_rejected_before_office(monkeypatch, field):
    raw = document(f"<w:p>{field}{image_ref('local')}</w:p>", images={"local": picture()})
    result = engine.prepare_visuals(raw, "docx", {"kind": "paragraph", "index": 1})
    assert result["status"] == "partial" and len(result["visuals"]) == 1
    monkeypatch.setattr(engine, "_office_slide_render", lambda *a: pytest.fail("Field instructions reached Office"))
    raw = presentation(extra={"ppt/notesSlides/notesSlide1.xml": f'<w:p xmlns:w="{W}">{field}</w:p>'})
    assert error_code(raw, "pptx", {"kind": "slide", "index": 1}) == "visual_invalid"


def test_real_docx_image_with_page_field_and_unrelated_external_hyperlink():
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE
    doc = Document()
    paragraph = doc.add_paragraph()
    raw_image = picture(color="blue")
    paragraph.add_run().add_picture(io.BytesIO(raw_image))
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    doc.sections[0].header.paragraphs[0]._p.append(field)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), doc.part.relate_to("https://example.org/lecture", RELATIONSHIP_TYPE.HYPERLINK, is_external=True))
    doc.add_paragraph()._p.append(hyperlink)
    output = io.BytesIO()
    doc.save(output)
    result = engine.prepare_visuals(output.getvalue(), "docx", {"kind": "paragraph", "index": 1})
    assert result["status"] == "partial" and result["visuals"][0]["bytes"] == raw_image
    assert result["visuals"][0]["native_part"] == "word/media/image1.png"


def test_docx_external_image_is_skipped_without_fetching_or_hiding_local_image():
    relations = (f'<Relationship Id="local" Type="{R}/image" Target="media/local.png"/>'
                 f'<Relationship Id="remote" Type="{R}/image" Target="https://example.org/image.png" TargetMode="External"/>')
    raw = document(f'<w:p>{image_ref("local")}<w:r><w:drawing><a:blip r:link="remote"/></w:drawing></w:r></w:p>',
                   images={"local": picture()}, relation_text=relations)
    result = engine.prepare_visuals(raw, "docx", {"kind": "paragraph", "index": 1})
    assert len(result["visuals"]) == 1 and any("liên kết ngoài" in note for note in result["warnings"])


def test_known_slide_number_field_is_inert_but_unknown_field_rejected(monkeypatch):
    monkeypatch.setattr(engine, "_office_slide_render", unavailable)
    raw = presentation(picture_bytes=picture(), slide_extra='<a:fld type="slidenum"/>')
    assert engine.prepare_visuals(raw, "pptx", {"kind": "slide", "index": 1})["status"] == "partial"
    raw = presentation(picture_bytes=picture(), slide_extra='<a:fld type="INCLUDEPICTURE https://example.org/x"/>')
    assert error_code(raw, "pptx", {"kind": "slide", "index": 1}) == "visual_invalid"
    raw = presentation(picture_bytes=picture(), slide_extra='<a:fld type="datetimeFigureOut"/>')
    assert engine.prepare_visuals(raw, "pptx", {"kind": "slide", "index": 1})["status"] == "partial"


def test_embedded_count_and_bundle_byte_limits_are_not_silently_truncated(monkeypatch):
    raw = document('<w:p>' + ''.join(image_ref(f"i{i}") for i in range(13)) + '</w:p>',
                   images={f"i{i}": picture() for i in range(13)})
    assert error_code(raw, "docx", {"kind": "paragraph", "index": 1}) == "visual_limit"
    monkeypatch.setattr(engine, "MAX_BUNDLE_BYTES", 20)
    assert error_code(picture(), "png", {"kind": "image", "index": 1}) == "visual_limit"


def test_source_byte_cap_and_corrupt_images(monkeypatch):
    assert error_code(b"not png", "png", {"kind": "image", "index": 1}) == "visual_invalid"
    monkeypatch.setattr(engine, "MAX_INPUT_BYTES", 10)
    assert error_code(picture(), "png", {"kind": "image", "index": 1}) == "visual_limit"


def test_office_helper_uses_hidden_readonly_export_and_never_quits_shared_app():
    helper = Path(engine.__file__).resolve().parents[2] / "scripts" / "render_learning_office.ps1"
    source = helper.read_text(encoding="utf-8")
    assert "AutomationSecurity = 3" in source
    assert "Presentations.Open($InputPath, -1, 0, 0)" in source
    assert ".Save" not in source
    assert "$presentation.Close()" in source
    assert "DisplayAlerts =" not in source
    assert source.index("Get-Process -Name POWERPNT") < source.index("New-Object -ComObject")
    assert "if ($ownedApplication)" in source
    assert "$application.Visible -eq 0 -and $application.Presentations.Count -eq 0" in source


def test_office_busy_or_com_unavailable_code_is_not_misreported_as_invalid(monkeypatch):
    monkeypatch.setattr(engine.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 3))
    with pytest.raises(MaterialsError) as error:
        engine._run(["renderer"], unavailable_codes=(3,))
    assert error.value.code == "visual_unavailable"


@pytest.mark.skipif(os.name != "nt" or os.environ.get("SOURCE_VISUALS_OFFICE_SMOKE") != "1",
                    reason="Opt-in local PowerPoint integration smoke")
def test_real_office_renders_shape_only_slide_without_embedded_raster(tmp_path):
    fixture = tmp_path / "shape-only.pptx"
    creator = tmp_path / "create-trusted-fixture.ps1"
    creator.write_text(r'''param([string]$Destination)
$ErrorActionPreference = 'Stop'
$app = $null
$pres = $null
$owned = $false
$code = 1
try {
    if (Get-Process -Name POWERPNT -ErrorAction SilentlyContinue) { throw 'PowerPoint already running.' }
    $app = New-Object -ComObject PowerPoint.Application
    if ($app.Visible -ne 0 -or $app.Presentations.Count -ne 0) { throw 'PowerPoint is in use.' }
    $owned = $true
    $pres = $app.Presentations.Add(0)
    $pres.PageSetup.SlideWidth = 960
    $pres.PageSetup.SlideHeight = 540
    $slide = $pres.Slides.Add(1, 12)
    $left = $slide.Shapes.AddShape(1, 80, 120, 220, 100)
    $left.Fill.ForeColor.RGB = 0xDC5014
    $left.TextFrame.TextRange.Text = 'CPU'
    $right = $slide.Shapes.AddShape(1, 500, 120, 220, 100)
    $right.Fill.ForeColor.RGB = 0x32B43C
    $right.TextFrame.TextRange.Text = 'Memory'
    $connector = $slide.Shapes.AddConnector(1, 300, 170, 500, 170)
    $connector.Line.ForeColor.RGB = 0
    $connector.Line.EndArrowheadStyle = 3
    $pres.SaveAs($Destination, 24)
    $code = 0
} catch {
    [Console]::Error.WriteLine($_.Exception.GetType().Name + ': ' + $_.Exception.HResult)
} finally {
    foreach ($child in @($connector, $right, $left, $slide)) {
        if ($null -ne $child) {
            try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($child) } catch {}
        }
    }
    $connector = $null
    $right = $null
    $left = $null
    $slide = $null
    if ($null -ne $pres) {
        try { $pres.Close() } catch {}
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($pres)
    }
    if ($null -ne $app) {
        if ($owned) {
            try { if ($app.Visible -eq 0 -and $app.Presentations.Count -eq 0) { $app.Quit() } } catch {}
        }
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
    }
    $pres = $null
    $app = $null
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
exit $code
''', encoding="utf-8")
    result = subprocess.run([shutil.which("powershell"), "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass",
                             "-File", str(creator), "-Destination", str(fixture)],
                            capture_output=True, timeout=30, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    raw = fixture.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert not any(name.startswith("ppt/media/") for name in archive.namelist())
        slide = archive.read("ppt/slides/slide1.xml")
        assert b"cxnSp" in slide and b"CPU" in slide and b"Memory" in slide
    for iteration in (1, 2):
        bundle = engine.prepare_visuals(raw, "pptx", {"kind": "slide", "index": 1})
        assert bundle["status"] == "ready" and len(bundle["visuals"]) == 1
        visual = bundle["visuals"][0]
        assert visual["kind"] == "slide_render" and visual["native_part"] == "ppt/slides/slide1.xml"
        (tmp_path / f"rendered-shape{iteration}.png").write_bytes(visual["bytes"])
        with Image.open(io.BytesIO(visual["bytes"])) as image:
            width, height = image.size
            blue = image.getpixel((round(100 * width / 960), round(140 * height / 540)))[:3]
            green = image.getpixel((round(520 * width / 960), round(140 * height / 540)))[:3]
            assert blue[2] > blue[0] + 80 and green[1] > green[0] + 40
            line_y, line_x = round(170 * height / 540), round(400 * width / 960)
            assert any(max(image.getpixel((line_x, y))[:3]) < 80 for y in range(line_y - 2, line_y + 3))
