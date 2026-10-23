"""Remove only DETECT.2 additions before earlier frozen byte receipts.

This test-only historical reconstruction keeps prior phase receipts stable.  It
does not alter production behavior or repin any historical digest.
"""
from __future__ import annotations

from tests._oop_intent_continue1_maintenance import before_oop_intent_continue1


def _once(data: bytes, after: bytes, before: bytes = b"") -> bytes:
    assert data.count(after) == 1, "non-unique DETECT.2 reversal hunk"
    return data.replace(after, before, 1)


def before_oop_intent_detect2(relative: str, content: bytes) -> bytes:
    data = before_oop_intent_continue1(relative, content)
    if relative == "web/app.py":
        data = _once(data,
            b'    # OOP.INTENT.DETECT.2 owns applicable future-design semantics before\n'
            b'    # build_control_prompt can construct or expand RepairScope.\n'
            b'    from web.oop_intent_adapter import admit_future_design_control_wait\n'
            b'    task_text = preserved_task_text(control)\n'
            b'    future_wait, future_design_owned = admit_future_design_control_wait(\n'
            b'        control=control, repo_path=repo_path or "", task_text=task_text)\n'
            b'    if future_wait is not None:\n'
            b'        return {**future_wait, "usage": {"patch_author_calls": 0}}\n\n')
        data = _once(data,
            b'    from core.repair_intent_ambiguity import detect_repair_intent_ambiguity\n'
            b'    detection = detect_repair_intent_ambiguity(\n',
            b'    from core.repair_intent_ambiguity import detect_repair_intent_ambiguity\n'
            b'    task_text = preserved_task_text(control)\n'
            b'    detection = detect_repair_intent_ambiguity(\n')
        data = _once(data,
            b'    if not future_design_owned:\n'
            b'        from web.oop_intent_adapter import admit_oop_patch_wait\n'
            b'        oop_wait = admit_oop_patch_wait(\n'
            b'            control=control, repo_path=repo_path or "", task_text=task_text)\n'
            b'        if oop_wait is not None:\n'
            b'            return {**oop_wait, "usage": {"patch_author_calls": 0}}\n',
            b'    from web.oop_intent_adapter import admit_oop_patch_wait\n'
            b'    oop_wait = admit_oop_patch_wait(\n'
            b'        control=control, repo_path=repo_path or "", task_text=task_text)\n'
            b'    if oop_wait is not None:\n'
            b'        return {**oop_wait, "usage": {"patch_author_calls": 0}}\n')
        return _once(data,
            b'    # Future-design intent must settle before any of the three candidate\n'
            b'    # authors receive a prompt or RepairScope can be projected.\n'
            b'    from web.oop_intent_adapter import admit_future_design_control_wait\n'
            b'    task_text = preserved_task_text(control)\n'
            b'    future_wait, _future_design_owned = admit_future_design_control_wait(\n'
            b'        control=control, repo_path=repo_path or "", task_text=task_text)\n'
            b'    if future_wait is not None:\n'
            b'        return {**future_wait, "candidates": [],\n'
            b'                "usage": {"patch_author_calls": 0}}\n\n')
    if relative == "web/runner.py":
        data = _once(data,
            b'        # OOP.INTENT.DETECT.2 owns applicable future-design semantics before\n'
            b'        # prompt preparation can construct or expand RepairScope.\n'
            b'        future_design_owned = False\n'
            b'        if state.interface == "agent" and not live_route.read_only and state.control_result:\n'
            b'            from web.oop_intent_adapter import admit_future_design_control_wait\n'
            b'            future_wait, future_design_owned = admit_future_design_control_wait(\n'
            b'                control=state.control_result, repo_path=state.repo_path or "",\n'
            b'                task_text=query)\n'
            b'            if future_wait is not None:\n'
            b'                return {**future_wait, "project_tag": final_tag,\n'
            b'                        "live_route": live_route_payload, **runtime_state,\n'
            b'                        "runtime_environment_description": runtime_description}\n\n'
            b'        # CONTROL\'s existing prompt preparation may now project RepairScope.\n',
            b'        # CONTROL\'s existing prompt preparation projects RepairScope without\n'
            b'        # invoking the patch author; the detector consumes that measured scope.\n')
        return _once(data,
            b'        if (not future_design_owned and state.interface == "agent"\n'
            b'                and not live_route.read_only and state.control_result):\n',
            b'        if state.interface == "agent" and not live_route.read_only and state.control_result:\n')
    if relative == "main.py":
        return _once(data,
            b'    # OOP.INTENT.DETECT.2: the terminal agent shares the same deterministic\n'
            b'    # pre-author admission as web routes.  A wait/fail-closed result is\n'
            b'    # terminal here; it is also persisted through the frozen OOP UI lifecycle.\n'
            b'    if (state.interface == "agent" and state.is_project_input\n'
            b'            and state.control_result and not route_is_read_only(state.live_route)):\n'
            b'        from web.oop_intent_adapter import admit_future_design_control_wait\n'
            b'        intent_wait, _future_design_owned = admit_future_design_control_wait(\n'
            b'            control=state.control_result, repo_path=state.repo_path or "",\n'
            b'            task_text=state.user_input)\n'
            b'        if intent_wait is not None:\n'
            b'            print(json.dumps(intent_wait, indent=2, ensure_ascii=False))\n'
            b'            return\n\n')
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "OOP.INTENT.DETECT.2",'
        tail = b'\n  ]\n}\n'
        assert data.count(marker) == data.count(tail) == 1
        return data[:data.index(marker)] + b'    }' + data[data.index(tail):]
    if relative == "tests/test_phase_registry.py":
        addition = b'    assert "OOP.INTENT.DETECT.2" in ids\n'
        assert data.count(addition) == 1
        assert data.count(b'len(data["phases"]) == 207') == 1
        assert data.count(b'"CONTROL": 25') == 1
        return data.replace(addition, b'', 1).replace(
            b'len(data["phases"]) == 207', b'len(data["phases"]) == 206', 1).replace(
            b'"CONTROL": 25', b'"CONTROL": 24', 1)
    if relative == "tests/test_phase_picker.py":
        assert data.count(b'"complete_or_history": 203') == 1
        assert data.count(b'["complete_or_history"] == 203') == 28
        return data.replace(b'"complete_or_history": 203', b'"complete_or_history": 202').replace(
            b'["complete_or_history"] == 203', b'["complete_or_history"] == 202')
    return data
