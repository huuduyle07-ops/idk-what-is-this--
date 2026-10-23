"""Reverse only APPROVE.1 changes before frozen historical byte assertions.

Existing historical receipts are never repinned. This phase's exact hunks have
their own attribution record; unexpected shared-file changes fail closed.
"""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_scope_approve1(relative: str, content: bytes) -> bytes:
    from tests._patch_scope_plan1_maintenance import before_patch_scope_plan1
    content = before_patch_scope_plan1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_scope_approve1_reversal.json").read_text(encoding="utf-8"))
    record = next((x for x in receipt["reversals"] if x["path"] == relative), None)
    if record is None:
        return content
    text = content.decode("utf-8").replace("\r\n", "\n")
    assert sha256(text.encode()).hexdigest() == record["post_normalized_sha256"], relative
    for hunk in reversed(record["hunks"]):
        assert text.count(hunk["post"]) == 1, (relative, "non-unique APPROVE.1 hunk")
        text = text.replace(hunk["post"], hunk["pre"], 1)
    assert sha256(text.encode()).hexdigest() == record["pre_normalized_sha256"], relative
    lf_lines = frozenset(record["historical_lf_lines"])
    text = "".join(line if index in lf_lines else line.replace("\n", "\r\n")
                   for index, line in enumerate(text.splitlines(keepends=True)))
    restored = text.encode("utf-8")
    assert sha256(restored).hexdigest() == record["historical_sha256"], relative
    return restored
