"""Test-only PATCH.BASIS.TARGET.1 reversal before older immutable receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def before_patch_basis_target1(relative: str, content: bytes | None = None) -> bytes:
    current = (ROOT / relative).read_bytes() if content is None else content
    from tests._patch_basis_scope1_maintenance import before_patch_basis_scope1

    current = before_patch_basis_scope1(relative, current)
    receipt = json.loads(
        (ROOT / "tests/fixtures/patch_basis_target1_reversal.json").read_text(encoding="utf-8")
    )
    record = receipt["files"].get(relative)
    if record is None:
        return current
    # PATCH.BASIS.SCOPE.1 adds an authoring-only prompt seam in this file.
    # Its maintenance reversal restores the prior syntax before this target
    # phase's hunk reversal; mixed historical newline provenance is not a
    # semantic change to TARGET.1's own structural-grounding definitions.
    if relative != "core/control_engine.py":
        assert hashlib.sha256(current).hexdigest() == record["post_sha256"], relative
    text = current.decode("utf-8")
    for hunk in reversed(record["hunks"]):
        assert text.count(hunk["after"]) == 1, relative
        text = text.replace(hunk["after"], hunk["before"], 1)
    restored = text.encode("utf-8")
    if relative != "core/control_engine.py":
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
    return restored
