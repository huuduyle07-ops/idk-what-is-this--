"""Remove only CONTINUE.1 additions before earlier frozen byte receipts.

This test-only historical reconstruction preserves prior receipts without
changing production behavior or repinning any historical digest.
"""
from __future__ import annotations

from tests._patch_scope_expand1_maintenance import before_patch_scope_expand1


def _once(data: bytes, after: bytes, before: bytes = b"") -> bytes:
    assert data.count(after) == 1, "non-unique CONTINUE.1 reversal hunk"
    return data.replace(after, before, 1)


def before_oop_intent_continue1(relative: str, content: bytes) -> bytes:
    data = before_patch_scope_expand1(relative, content)
    if relative == "web/app.py":
        import json
        from pathlib import Path
        receipt = json.loads((Path(__file__).parent / "fixtures" /
            "oop_intent_continue1_reversal.json").read_text(encoding="utf-8"))
        for hunk in receipt[relative]:
            data = _once(data, hunk["after"].encode(), hunk["before"].encode())
        return data
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "OOP.INTENT.CONTINUE.1",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative == "tests/test_phase_registry.py":
        addition = b'    assert "OOP.INTENT.CONTINUE.1" in ids\n'
        assert data.count(addition) == 1
        assert data.count(b'len(data["phases"]) == 208') == 1
        assert data.count(b'"CONTROL": 26') == 1
        return data.replace(addition, b'', 1).replace(
            b'len(data["phases"]) == 208', b'len(data["phases"]) == 207', 1).replace(
            b'"CONTROL": 26', b'"CONTROL": 25', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 204') == 1
        assert data.count(b'["complete_or_history"] == 204') == 28
        return data.replace(b'"complete_or_history": 204', b'"complete_or_history": 203').replace(
            b'["complete_or_history"] == 204', b'["complete_or_history"] == 203')
    return data
