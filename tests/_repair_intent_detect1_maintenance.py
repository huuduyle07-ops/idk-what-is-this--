"""Test-only reversal of DETECT.1 before older immutable receipts."""
from __future__ import annotations


def _remove_between(data: bytes, start: bytes, end: bytes) -> bytes:
    assert data.count(start) == 1 and data.count(end) == 1
    left = data.index(start)
    right = data.index(end, left)
    return data[:left] + data[right:]


def before_repair_intent_detect1(relative: str, content: bytes) -> bytes:
    data = content
    if relative == "web/app.py":
        data = _remove_between(
            data, b'    # CONTROL has now projected the measured RepairScope.',
            b'    if (control.get("repair_scope") or {}).get("status") == "complete":')
        marker = b'    if (control.get("repair_scope") or {}).get("status") == "complete":'
        assert data.count(marker) == 1
        data = data.replace(marker, b'    task_text = preserved_task_text(control)\n' + marker, 1)
    elif relative == "web/runner.py":
        control_import = b'    build_control_prompt,\n'
        assert data.count(control_import) == 1
        data = data.replace(control_import, b'', 1)
        line = b'from core.repair_intent_ambiguity import detect_repair_intent_ambiguity\n'
        assert data.count(line) == 1
        data = data.replace(line, b'', 1)
        data = _remove_between(data, b'        # CONTROL\'s existing prompt preparation',
                               b'        draft = run_draft_pipeline(state)')
    elif relative == "docs/roadmap/phase_registry.json":
        data = _remove_between(data,
            b'    },\n    {\n      "phase_id": "REPAIR.INTENT.DETECT.1",',
            b'  ]\n}\n')
        data = data.replace(b'  ]\n}\n', b'    }\n  ]\n}\n', 1)
    elif relative == "tests/test_phase_registry.py":
        data = data.replace(b'len(data["phases"]) == 200',
                            b'len(data["phases"]) == 199')
        data = data.replace(b'"CONTROL": 20', b'"CONTROL": 19')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b'"complete_or_history": 196',
                            b'"complete_or_history": 195')
        data = data.replace(b'["complete_or_history"] == 196',
                            b'["complete_or_history"] == 195')
    return data
