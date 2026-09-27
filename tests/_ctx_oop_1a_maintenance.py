"""Remove only CTX.OOP.1A registry bookkeeping for older frozen receipts."""
from __future__ import annotations


def before_ctx_oop_1a(relative: str, content: bytes) -> bytes:
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "CTX.OOP.1A",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        return content[:content.index(marker)] + b'    }' + content[content.index(tail):]
    if relative == "tests/test_phase_registry.py":
        assert content.count(b'    assert "CTX.OOP.1A" in ids\n') == 1
        content = content.replace(b'    assert "CTX.OOP.1A" in ids\n', b'', 1)
        assert content.count(b'len(data["phases"]) == 202') == 1
        assert content.count(b'"CONTROL": 21') == 1
        return content.replace(b'len(data["phases"]) == 202', b'len(data["phases"]) == 201', 1).replace(
            b'"CONTROL": 21', b'"CONTROL": 20', 1)
    if relative == "tests/test_phase_picker.py":
        assert content.count(b'"complete_or_history": 198') == 1
        assert content.count(b'["complete_or_history"] == 198') == 28
        return content.replace(b'"complete_or_history": 198', b'"complete_or_history": 197').replace(
            b'["complete_or_history"] == 198', b'["complete_or_history"] == 197')
    return content
