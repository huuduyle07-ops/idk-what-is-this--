"""Remove only EXPAND.1 bookkeeping before frozen historical receipts.

Existing receipts and implementation behavior are unchanged. This function
reverses only this phase's registry entry, counts and bounded registry tests.
"""
from __future__ import annotations

from tests._patch_scope_recheck1_maintenance import before_patch_scope_recheck1


def before_patch_scope_expand1(relative: str, content: bytes) -> bytes:
    data = before_patch_scope_recheck1(relative, content)
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.SCOPE.EXPAND.1",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative in ("tests/test_phase_registry.py", "tests/test_phase_picker.py"):
        start = b'\n\n# PATCH.SCOPE.EXPAND.1 bookkeeping boundary.\n'
        end = b'# End PATCH.SCOPE.EXPAND.1 bookkeeping boundary.\n'
        assert data.count(start) == data.count(end) == 1
        begin = data.index(start)
        finish = data.index(end) + len(end)
        data = data[:begin] + data[finish:]
    if relative == "tests/test_phase_registry.py":
        addition = b'    assert "PATCH.SCOPE.EXPAND.1" in ids\n'
        assert data.count(addition) == 1
        assert data.count(b'len(data["phases"]) == 209') == 1
        assert data.count(b'"CONTROL": 27') == 1
        return data.replace(addition, b'', 1).replace(
            b'len(data["phases"]) == 209', b'len(data["phases"]) == 208', 1).replace(
            b'"CONTROL": 27', b'"CONTROL": 26', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 205') == 1
        assert data.count(b'["complete_or_history"] == 205') == 28
        return data.replace(b'"complete_or_history": 205', b'"complete_or_history": 204').replace(
            b'["complete_or_history"] == 205', b'["complete_or_history"] == 204')
    return data
