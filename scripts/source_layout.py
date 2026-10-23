"""Resolve recorded relocations when reading immutable historical source evidence.

Production modules never use this helper. Historical checks still compare their
original hashes: only the exact reviewed layout edits can be reversed, and any
other source change fails the recorded after-hash check.
"""
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/architecture/source_relocations.json"


def _records():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def _record(relative):
    value = str(relative).replace("\\", "/")
    return next((row for row in _records()
                 if value in (row["previous"], row["current"])), None)


def previous_path(relative):
    """Return the key used in pre-organization evidence, not a live file path."""
    row = _record(relative)
    return row["previous"] if row else str(relative).replace("\\", "/")


def source_path(relative, *, root=ROOT):
    """Locate current source without changing or projecting its contents."""
    root = Path(root).resolve()
    row = _record(relative) if root == ROOT else None
    path = (root / (row["current"] if row else relative)).resolve()
    if not path.is_relative_to(root):
        raise ValueError("source path must stay inside the repository")
    return path


def read_preorganization_source(relative, *, root=ROOT):
    """Undo exact layout-only edits for an explicitly historical hash check."""
    row = _record(relative) if Path(root).resolve() == ROOT else None
    current = source_path(relative, root=root).read_bytes()
    if row is None:
        return current
    if sha256(current).hexdigest() != row["after_sha256"]:
        raise ValueError(f"source changed after recorded relocation: {relative}")
    lines = current.decode("utf-8").splitlines(keepends=True)
    for edit in reversed(row["edits"]):
        start, end = edit["after_start"], edit["after_end"]
        if "".join(lines[start:end]) != edit["after"]:
            raise ValueError(f"relocation edit does not match: {relative}")
        lines[start:end] = edit["before"].splitlines(keepends=True)
    original = "".join(lines).encode("utf-8")
    if sha256(original).hexdigest() != row["before_sha256"]:
        raise ValueError(f"historical source reconstruction failed: {relative}")
    return original
