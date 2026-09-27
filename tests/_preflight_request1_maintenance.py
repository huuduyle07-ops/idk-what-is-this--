"""Test-only PREFLIGHT.REQUEST.1 reversal before older immutable receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def before_preflight_request1(relative: str, content: bytes | None = None) -> bytes:
    current = (ROOT / relative).read_bytes() if content is None else content
    # Later PATCH.BASIS.TARGET.1 is reversed first so PREFLIGHT.REQUEST.1's immutable
    # post-state remains the input to this historical reversal.
    from tests._patch_basis_target1_maintenance import before_patch_basis_target1

    current = before_patch_basis_target1(relative, current)
    receipt = json.loads(
        (ROOT / "tests/fixtures/preflight_request1_reversal.json").read_text(encoding="utf-8")
    )
    record = receipt["files"].get(relative)
    if record is None:
        return current
    assert hashlib.sha256(current).hexdigest() == record["post_sha256"], relative
    text = current.decode("utf-8")
    for hunk in reversed(record["hunks"]):
        assert text.count(hunk["after"]) == 1, relative
        text = text.replace(hunk["after"], hunk["before"], 1)
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
    return restored
