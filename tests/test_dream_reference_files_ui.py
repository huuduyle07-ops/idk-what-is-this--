"""Template contract checks for Dream reference markdown file input."""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"


def test_dream_reference_files_accept_picker_and_drop_paths():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    styles = STYLE_SHEET.read_text(encoding="utf-8")

    assert 'id="dreamReferenceFileInput"' in template
    assert 'accept=".md,.markdown,text/markdown"' in template
    assert 'dreamReferenceFiles.addEventListener("dblclick"' in template
    assert 'dreamReferenceFiles.addEventListener("drop"' in template
    assert "appendDreamReferenceFilePaths" in template
    assert "dreamReferenceFileInput.addEventListener(\"change\"" in template
    assert ".dream-reference-files--dragover" in styles
