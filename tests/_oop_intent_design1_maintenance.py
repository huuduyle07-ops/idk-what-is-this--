"""Remove only DESIGN.1 additions before earlier frozen byte receipts.

This test-only historical reconstruction never changes production semantics or
repins any historical receipt.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tests._oop_intent_detect2_maintenance import before_oop_intent_detect2


_SOURCE_FILES = frozenset((
    "core/explicit_evidence.py", "core/semantic_waiter.py",
    "core/semantic_waiter_adapter.py", "core/live_task_shape.py",
    "core/input_understanding.py", "core/task_contract.py",
    "core/requirement_preservation.py", "tests/test_input_understanding.py",
))


def _before_source_transport(relative: str, content: bytes) -> bytes:
    receipt = json.loads((Path(__file__).parent / "fixtures" /
        "oop_intent_design1_reversal.json").read_text(encoding="utf-8"))
    records = [item for item in receipt["reversals"] if item["path"] == relative]
    assert len(records) == 1, (relative, "unique DESIGN.1 source receipt")
    record = records[0]
    text = content.decode("utf-8").replace("\r\n", "\n")
    assert sha256(text.encode("utf-8")).hexdigest() == record["post_normalized_sha256"], relative
    for hunk in reversed(record["hunks"]):
        assert text.count(hunk["post"]) == 1, (relative, "non-unique DESIGN.1 source hunk")
        text = text.replace(hunk["post"], hunk["pre"], 1)
    assert sha256(text.encode("utf-8")).hexdigest() == record["pre_normalized_sha256"], relative
    if record["historical_newline"] == "CRLF":
        text = text.replace("\n", "\r\n")
    elif record["historical_newline"] == "mixed":
        lf_lines = frozenset(record["historical_lf_lines"])
        text = "".join(line if index in lf_lines else line.replace("\n", "\r\n")
                       for index, line in enumerate(text.splitlines(keepends=True)))
    restored = text.encode("utf-8")
    assert sha256(restored).hexdigest() == record["historical_sha256"], relative
    return restored


def before_oop_intent_design1(relative: str, content: bytes) -> bytes:
    content = before_oop_intent_detect2(relative, content)
    if relative in _SOURCE_FILES:
        return _before_source_transport(relative, content)
    data = content
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "OOP.INTENT.DESIGN.1",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative == "tests/test_phase_registry.py":
        addition = b'    assert "OOP.INTENT.DESIGN.1" in ids\n'
        assert data.count(addition) == 1
        assert data.count(b'len(data["phases"]) == 206') == 1
        assert data.count(b'"CONTROL": 24') == 1
        return data.replace(addition, b'', 1).replace(
            b'len(data["phases"]) == 206', b'len(data["phases"]) == 205', 1).replace(
            b'"CONTROL": 24', b'"CONTROL": 23', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 202') == 1
        assert data.count(b'["complete_or_history"] == 202') == 28
        return data.replace(b'"complete_or_history": 202', b'"complete_or_history": 201').replace(
            b'["complete_or_history"] == 202', b'["complete_or_history"] == 201')
    return data
