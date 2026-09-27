"""Remove UI.1 presentation seams before older immutable byte receipts."""
from __future__ import annotations


def _once(data: bytes, new: bytes, old: bytes = b"") -> bytes:
    assert data.count(new) == 1, "non-unique waiting presentation reversal hunk"
    return data.replace(new, old, 1)


def before_repair_intent_ui1(relative: str, content: bytes) -> bytes:
    from tests._oop_intent_ui1_maintenance import before_oop_intent_ui1
    from tests._ctx_oop_1a_maintenance import before_ctx_oop_1a
    from tests._ctx_oop_1b_maintenance import before_ctx_oop_1b

    data = before_ctx_oop_1a(relative, before_ctx_oop_1b(
        relative, before_oop_intent_ui1(relative, content)))
    if relative == "web/app.py":
        data = _once(data, b"from flask import Flask, abort, render_template, request, redirect, url_for",
                     b"from flask import Flask, render_template, request, redirect, url_for")
        data = _once(data, b"from web.session_presentation import CorruptWaitingSession, project_session\n")
        data = _once(data,
            b'    if current is None:\n'
            b'        abort(404)\n'
            b'    try:\n'
            b'        presentation = project_session(current)\n'
            b'    except CorruptWaitingSession as exc:\n'
            b'        abort(422, description=str(exc))\n'
            b'    active_web_mode = _normalize_web_mode(current.get("web_mode"))',
            b'    active_web_mode = _normalize_web_mode((current or {}).get("web_mode"))')
        data = _once(data,
            b'        result=current.get("result") if isinstance(current.get("result"), dict) else {},\n'
            b'        presentation=presentation,',
            b'        result=current.get("result", {}) if current else {},')
    elif relative == "web/templates/index.html":
        data = _once(data, b"{% set waiting = (presentation.clarification if presentation is defined and presentation else none) %}\n")
        data = _once(data, b'{{ waiting.question if waiting else result.answer }}', b'{{ result.answer }}')
        data = _once(data,
            b'{% if current and (waiting or (result and result.answer)) %}',
            b'{% if current and result and result.answer %}')
        data = _once(data, b' onclick="showTab(\'patch\')" {% if waiting %}hidden disabled{% endif %}',
                     b' onclick="showTab(\'patch\')"')
        data = _once(data, b' onclick="applyPatch()" {% if waiting %}hidden disabled{% endif %}',
                     b' onclick="applyPatch()"')
        data = _once(data,
            b'{{ waiting.question if waiting else (result.answer if result else "") }}',
            b'{{ result.answer if result else "" }}')
        data = _once(data,
            b'<div id="repairIntentClarification" {% if not waiting %}hidden{% endif %}>\n'
            b'            {% if waiting %}\n'
            b'            <ol id="repairIntentAlternatives" type="A">\n'
            b'              {% for alternative in waiting.alternatives %}<li>{{ alternative }}</li>{% endfor %}\n'
            b'            </ol>\n'
            b'            <p>You can also describe another intended behavior.</p>\n'
            b'            {% endif %}',
            b'<div id="repairIntentClarification" {% if not result or result.status != "waiting_for_clarification" %}hidden{% endif %}>')
        data = _once(data,
            b"${_escapeHtml(s.status || s.result?.status || '')} ${_escapeHtml(s.created_at || '')}",
            b"${_escapeHtml(s.created_at || '')}")
        data = _once(data,
            b'const initialTab = {{ \'true\' if waiting else \'false\' }} ? "answer" : (validTabs.includes(saved) ? saved : "answer");',
            b'const initialTab = validTabs.includes(saved) ? saved : "answer";')
        data = _once(data, b'            setRepairIntentWaitingActions(true);\n')
        data = _once(data,
            b'function setRepairIntentWaitingActions(waiting) {\n'
            b'    for (const handler of [\'applyPatch()\', "showTab(\'patch\')"]) {\n'
            b'        const button = document.querySelector(`button[onclick="${handler}"]`);\n'
            b'        if (button) {\n'
            b'            button.hidden = waiting;\n'
            b'            button.disabled = waiting;\n'
            b'        }\n'
            b'    }\n'
            b'}\n\n')
        data = _once(data, b'                setRepairIntentWaitingActions(false);\n')
        data = _once(data, b'            setRepairIntentWaitingActions(false);\n')
        data = _once(data, b'{% if waiting and current %}',
                     b'{% if result and result.status == "waiting_for_clarification" and current %}')
        data = _once(data, b'sessionId: {{ waiting.session_id | tojson }}',
                     b'sessionId: {{ result.clarification_session_id | tojson }}')
    elif relative == "tests/test_phase_registry.py":
        data = _once(data, b'    assert "REPAIR.INTENT.UI.1" in ids\n')
        data = _once(data, b'len(data["phases"]) == 201', b'len(data["phases"]) == 200')
        data = _once(data, b'"UX": 30', b'"UX": 29')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b'"complete_or_history": 197', b'"complete_or_history": 196')
        data = data.replace(b'["complete_or_history"] == 197', b'["complete_or_history"] == 196')
    elif relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "REPAIR.INTENT.UI.1",'
        end = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(end) == 1
        data = data[:data.index(marker)] + b'    }' + data[data.index(end):]
    return data
