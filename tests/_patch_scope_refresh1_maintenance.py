"""Remove only REFRESH.1 bookkeeping before frozen historical receipts.

No historical receipt changes. This exact reversal keeps older phase byte and
registry expectations anchored at their original revision.
"""
from __future__ import annotations


def before_patch_scope_refresh1(relative: str, content: bytes) -> bytes:
    from tests._patch_scope_approve1_maintenance import before_patch_scope_approve1
    data = before_patch_scope_approve1(relative, content)
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.SCOPE.REFRESH.1",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative in ("tests/test_phase_registry.py", "tests/test_phase_picker.py"):
        start = b'\n\n# PATCH.SCOPE.REFRESH.1 bookkeeping boundary.\n'
        end = b'# End PATCH.SCOPE.REFRESH.1 bookkeeping boundary.\n'
        assert data.count(start) == data.count(end) == 1
        begin = data.index(start)
        finish = data.index(end) + len(end)
        data = data[:begin] + data[finish:]
    if relative == "tests/test_phase_registry.py":
        data = data.replace(b'    assert "PATCH.SCOPE.REFRESH.1" in ids\n', b'')
        assert data.count(b'len(data["phases"]) == 211') == 1
        assert data.count(b'"CONTROL": 29') == 1
        return data.replace(b'len(data["phases"]) == 211', b'len(data["phases"]) == 210', 1).replace(
            b'"CONTROL": 29', b'"CONTROL": 28', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 207') == 1
        assert data.count(b'["complete_or_history"] == 207') == 29
        return data.replace(b'"complete_or_history": 207', b'"complete_or_history": 206').replace(
            b'["complete_or_history"] == 207', b'["complete_or_history"] == 206')
    return data
