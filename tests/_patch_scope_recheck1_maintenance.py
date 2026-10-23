"""Remove only RECHECK.1 additions before frozen historical receipts.

Historical receipts are unchanged. Only this phase's bounded additions and
registry bookkeeping are reversed before the existing EXPAND.1 reconstruction.
"""
from __future__ import annotations

from tests._patch_scope_refresh1_maintenance import before_patch_scope_refresh1


def before_patch_scope_recheck1(relative: str, content: bytes) -> bytes:
    data = before_patch_scope_refresh1(relative, content)
    if relative == "web/app.py":
        addition = (
            b'    if ((session.get("oop_intent_gap") or {}).get("scope_recheck_schema") is not None\n'
            b'            or (session.get("oop_intent_gap") or {}).get("dimension") == "existing_savings_transition"\n'
            b'            or (session.get("result") or {}).get("scope_recheck_inputs") is not None):\n'
            b'        # Scope-discovered semantics return through the existing OOP lifecycle.\n'
            b'        from web.scope_semantic_recheck import project_stored_scope_transition_answer\n'
            b'        return project_stored_scope_transition_answer(\n'
            b'            session_id, answer_text=request.form.get("answer") or "",\n'
            b'            gap_id=request.form.get("gap_id"), decline=request.form.get("decline") == "true")\n'
        )
        assert data.count(addition) == 1, "non-unique RECHECK.1 app reversal hunk"
        return data.replace(addition, b'', 1)
    if relative == "web/session_presentation.py":
        addition = (
            b'                if (gap.get("scope_recheck_schema") is not None\n'
            b'                        or gap.get("dimension") == "existing_savings_transition"\n'
            b'                        or result.get("scope_recheck_inputs") is not None):\n'
            b'                    from web.scope_semantic_recheck import validate_scope_transition_wait\n'
            b'                    gap = validate_scope_transition_wait(session)\n'
        )
        assert data.count(addition) == 1, "non-unique RECHECK.1 presentation reversal hunk"
        return data.replace(addition, b'', 1)
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.SCOPE.RECHECK.1",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative in ("tests/test_phase_registry.py", "tests/test_phase_picker.py"):
        start = b'\n\n# PATCH.SCOPE.RECHECK.1 bookkeeping boundary.\n'
        end = b'# End PATCH.SCOPE.RECHECK.1 bookkeeping boundary.\n'
        assert data.count(start) == data.count(end) == 1
        begin = data.index(start)
        finish = data.index(end) + len(end)
        data = data[:begin] + data[finish:]
    if relative == "tests/test_phase_registry.py":
        addition = b'    assert "PATCH.SCOPE.RECHECK.1" in ids\n'
        assert data.count(addition) == 1
        assert data.count(b'len(data["phases"]) == 210') == 1
        assert data.count(b'"CONTROL": 28') == 1
        return data.replace(addition, b'', 1).replace(
            b'len(data["phases"]) == 210', b'len(data["phases"]) == 209', 1).replace(
            b'"CONTROL": 28', b'"CONTROL": 27', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 206') == 1
        assert data.count(b'["complete_or_history"] == 206') == 28
        return data.replace(b'"complete_or_history": 206', b'"complete_or_history": 205').replace(
            b'["complete_or_history"] == 206', b'["complete_or_history"] == 205')
    return data
