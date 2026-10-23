"""The source relocation bridge must preserve evidence and reject new drift."""
import ast
from hashlib import sha256
import json

import pytest

from scripts import source_layout as layout


def test_every_relocation_is_unique_and_reconstructs_its_original_source():
    rows = layout._records()
    assert len({row["previous"] for row in rows}) == len(rows)
    assert len({row["current"] for row in rows}) == len(rows)
    for row in rows:
        assert layout.source_path(row["previous"]) == layout.source_path(row["current"])
        original = layout.read_preorganization_source(row["previous"])
        assert sha256(original).hexdigest() == row["before_sha256"]
        if row["previous"] != row["current"]:
            assert not (layout.ROOT / row["previous"]).exists()


def test_runtime_changes_are_only_import_relocations():
    for row in layout._records():
        if not row["previous"].startswith("core/"):
            continue
        old = ast.parse(layout.read_preorganization_source(row["previous"]))
        new = ast.parse(layout.source_path(row["previous"]).read_bytes())
        for node in ast.walk(new):
            if isinstance(node, ast.ImportFrom) and node.module == "core.runtime.synthetic":
                node.module = "core"
        assert ast.dump(new) == ast.dump(old), row["current"]


@pytest.fixture
def small_layout(tmp_path, monkeypatch):
    original = b"from core import example\nVALUE = 1\n"
    current = b"from core.group import example\nVALUE = 1\n"
    target = tmp_path / "group/example.py"
    target.parent.mkdir()
    target.write_bytes(current)
    row = {"previous": "example.py", "current": "group/example.py",
           "before_sha256": sha256(original).hexdigest(),
           "after_sha256": sha256(current).hexdigest(),
           "edits": [{"after_start": 0, "after_end": 1,
                      "before": "from core import example\n",
                      "after": "from core.group import example\n"}]}
    manifest = tmp_path / "relocations.json"
    manifest.write_text(json.dumps({"files": [row]}), encoding="utf-8")
    monkeypatch.setattr(layout, "ROOT", tmp_path)
    monkeypatch.setattr(layout, "MANIFEST", manifest)
    return tmp_path, target, original, row


def test_unrecorded_code_change_is_never_hidden_by_historical_projection(small_layout):
    root, target, original, _ = small_layout
    assert layout.read_preorganization_source("example.py", root=root) == original
    target.write_bytes(target.read_bytes().replace(b"VALUE = 1", b"VALUE = 2"))
    with pytest.raises(ValueError, match="source changed after recorded relocation"):
        layout.read_preorganization_source("example.py", root=root)


def test_modified_reversal_must_still_match_original_hash(small_layout):
    root, _, _, row = small_layout
    row["edits"][0]["before"] = "from attacker import example\n"
    layout.MANIFEST.write_text(json.dumps({"files": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="historical source reconstruction failed"):
        layout.read_preorganization_source("example.py", root=root)


def test_source_resolution_rejects_paths_outside_repository(small_layout):
    root, _, _, _ = small_layout
    with pytest.raises(ValueError, match="inside the repository"):
        layout.source_path("../outside.py", root=root)
