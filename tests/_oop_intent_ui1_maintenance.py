"""Remove OOP.INTENT.UI.1 additions before older frozen byte receipts.

This is test-only historical attribution. The frozen receipts remain unchanged.
"""
from __future__ import annotations


def _once(data: bytes, new: bytes, old: bytes = b"") -> bytes:
    assert data.count(new) == 1, "non-unique OOP UI reversal hunk"
    return data.replace(new, old, 1)


def _between(data: bytes, start: bytes, end: bytes) -> bytes:
    assert data.count(start) == 1 and end in data[data.index(start):], "non-unique OOP UI boundary"
    return data[:data.index(start)] + data[data.index(end, data.index(start)):]


def before_oop_intent_ui1(relative: str, content: bytes) -> bytes:
    from tests._oop_intent_design1_maintenance import before_oop_intent_design1

    data = before_oop_intent_design1(relative, content)
    if relative == "web/app.py":
        data = _between(data, b'        from web.oop_intent_adapter import admit_oop_review_wait\n',
                        b'        evidence_block = (')
        data = _once(data,
            b'            existing_oop_wait = (\n'
            b'                find_session(result.get("clarification_session_id", ""))\n'
            b'                if result.get("clarification_kind") == "oop_intent" else None)\n'
            b'            current = existing_oop_wait or save_session(',
            b'            current = save_session(')
        data = _once(data, b'    presentation = project_session(current) if current else None\n\n')
        data = _once(data, b'        result=result,\n        presentation=presentation,\n        error=error,',
                     b'        result=result,\n        error=error,')
        data = _between(data, b'    from web.oop_intent_adapter import admit_oop_patch_wait\n',
                        b'    if (control.get("repair_scope") or {}).get("status") == "complete":')
        data = _between(data, b'@app.route("/oop_intent/answer", methods=["POST"])\n',
                        b'@app.route("/undo_patch", methods=["POST"])')
    elif relative == "web/runner.py":
        data = _between(data, b'        from web.oop_intent_adapter import admit_oop_review_wait\n',
                        b'    elif is_project_input:')
        data = _between(data,
            b'        if state.interface == "agent" and not live_route.read_only and state.control_result:\n'
            b'            from web.oop_intent_adapter import admit_oop_patch_wait\n',
            b'        draft = run_draft_pipeline(state)')
    elif relative == "web/session_store.py":
        data = _between(data, b'def create_oop_intent_wait(', b'def update_repair_intent_wait(')
    elif relative == "web/templates/index.html":
        data = _once(data,
            b'<div id="repairIntentClarification" {% if not waiting or presentation.clarification_kind != \'repair_intent\' %}hidden{% endif %}>',
            b'<div id="repairIntentClarification" {% if not waiting %}hidden{% endif %}>')
        data = _once(data,
            b"{% if waiting and presentation.clarification_kind == 'repair_intent' %}",
            b'{% if waiting %}')
        data = _between(data, b'          <div id="oopIntentClarification"',
                        b'          <pre id="context"')
        data = _once(data,
            b'            if (data.clarification_kind === "oop_intent" && data.clarification_session_id) {\n'
            b'                window.location.assign(`/session/${encodeURIComponent(data.clarification_session_id)}`);\n'
            b'                return;\n'
            b'            }\n')
        data = _once(data,
            b"{% if waiting and current and presentation.clarification_kind == 'repair_intent' %}",
            b'{% if waiting and current %}')
        data = _between(data,
            b"{% if waiting and current and presentation.clarification_kind == 'oop_intent' %}\n",
            b'function submitRepairIntent(decline) {')
    elif relative == "core/phase_registry.py":
        data = _once(data, b'    "OOP",\n')
    elif relative == "tests/test_phase_registry.py":
        data = _once(data, b'    assert "OOP.INTENT.UI.1" in ids\n')
        data = _once(data, b'len(data["phases"]) == 205', b'len(data["phases"]) == 204')
        data = _once(data, b'"UX": 31', b'"UX": 30')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b'"complete_or_history": 201', b'"complete_or_history": 200')
        data = data.replace(b'["complete_or_history"] == 201', b'["complete_or_history"] == 200')
    elif relative == "docs/roadmap/phase_registry.json":
        start = b'    },\n    {\n      "phase_id": "OOP.INTENT.UI.1",'
        end = b'\n  ]\n}\n'
        assert data.count(start) == data.count(end) == 1
        data = data[:data.index(start)] + b'    }' + data[data.index(end):]
    return data
