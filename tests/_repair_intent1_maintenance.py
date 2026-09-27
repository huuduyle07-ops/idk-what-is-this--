"""Test-only reversal of REPAIR.INTENT.1 before older frozen byte receipts.

Each removal targets a unique additive seam. Production never imports this.
The old receipts remain the authority for the reconstructed bytes.
"""
from __future__ import annotations


def _replace_once(data: bytes, after: bytes, before: bytes = b"") -> bytes:
    assert data.count(after) == 1, "non-unique repair-intent reversal hunk"
    return data.replace(after, before, 1)


def _remove_between(data: bytes, start: bytes, end: bytes) -> bytes:
    assert data.count(start) == 1, "non-unique repair-intent boundary"
    left = data.index(start)
    right = data.index(end, left)
    return data[:left] + data[right:]


def before_repair_intent1(relative: str, content: bytes) -> bytes:
    from tests._repair_intent_ui1_maintenance import before_repair_intent_ui1
    from tests._repair_intent_ground1_maintenance import before_repair_intent_ground1
    from tests._repair_intent_detect1_maintenance import before_repair_intent_detect1
    data = before_repair_intent_admit1(relative, before_repair_intent_ground1(
        relative, before_repair_intent_detect1(relative,
            before_repair_intent_ui1(relative, content))))
    if relative == "core/phase_registry.py":
        data = _replace_once(data, b'    "REPAIR",\n')
        data = _replace_once(data, b'    "PATCH",\n', b'    "PATCH",\r\n')
    elif relative == "tests/test_phase_registry.py":
        data = _replace_once(data,
            b'    assert "REPAIR.INTENT.1" in ids\n    assert len(data["phases"]) == 197\n',
            b'    assert len(data["phases"]) == 196\n')
        data = _replace_once(data, b'            "CONTROL": 17,\n',
                             b'            "CONTROL": 16,\n')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b'"complete_or_history": 193',
                            b'"complete_or_history": 192')
        data = data.replace(b'["complete_or_history"] == 193',
                            b'["complete_or_history"] == 192')
        data = _replace_once(data, b'        "complete_or_history": 192,\n',
                             b'        "complete_or_history": 192,\r\n')
    elif relative == "tests/test_control_bootstrap1.py":
        data = _replace_once(data,
            b'    from tests._repair_intent1_maintenance import before_repair_intent1\n'
            b'    post = before_repair_intent1(TEMPLATE, (ROOT / TEMPLATE).read_bytes()).decode("utf-8")\n',
            b'    post = (ROOT / TEMPLATE).read_bytes().decode("utf-8")\n')
    elif relative == "tests/test_ux_state1.py":
        data = _replace_once(data,
            b'    from tests._repair_intent1_maintenance import before_repair_intent1\n'
            b'    template = before_repair_intent1("web/templates/index.html", TEMPLATE.read_bytes()).decode("utf-8")\n',
            b'    template = _template()\n')
        data = _replace_once(data,
            b'    from tests._repair_intent1_maintenance import before_repair_intent1\n'
            b'    entry = _entry_template()\n'
            b'    current = before_repair_intent1("web/templates/index.html", TEMPLATE.read_bytes()).decode("utf-8")\n',
            b'    entry, current = _entry_template(), _template()\n')
    elif relative == "tests/test_patch_author_scope1.py":
        data = _replace_once(data,
            b'    from tests._repair_intent1_maintenance import before_repair_intent1\n')
        data = _replace_once(data,
            b'        assert hashlib.sha256(before_repair_intent1(path, (root/path).read_bytes())).hexdigest()==digest,path\n',
            b'        assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path\n')
    elif relative == "core/prompter.py":
        start = data.index(b"REVIEWER_SCHEMA =")
        end = data.index(b"PLANNER_SCHEMA =", start)
        block = data[start:end]
        block = _replace_once(block, b'"patch_candidate": null | {',
                              b'"patch_candidate": {')
        block = _replace_once(block,
            b'  "needs_escalation": false,\n'
            b'  "escalation_reason": "none|semantic_intent_required|missing_context|insufficient_evidence|unsupported_scope|author_output_invalid|other_bounded_reason"\n'
            b'}\nWhen needs_escalation=true, select a non-none escalation_reason and set\n'
            b'patch_candidate=null. Otherwise use escalation_reason="none"."""\n',
            b'  "needs_escalation": false\n}"""\n')
        data = data[:start] + block.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") + data[end:]
    elif relative == "core/pipeline.py":
        data = _remove_between(data,
            b'            if (state.control_result.get("repair_scope") or {}).get("status") == "complete":',
            b'            if state.control_result.get("repair_scope"):')
        data = _replace_once(data,
            b'            prompt = build_control_prompt(\n'
            b'                control_result=state.control_result,\n'
            b'                user_query=state.user_input,\n'
            b'                repo_path=state.repo_path,\n'
            b'                authoring_context=state.candidate_authoring_context,\n'
            b'            )\n',
            b'            prompt = build_control_prompt(\n'
            b'                control_result=state.control_result,\r\n'
            b'                user_query=state.user_input,\r\n'
            b'                repo_path=state.repo_path,\n'
            b'                authoring_context=state.candidate_authoring_context,\n'
            b'            )\r\n')
    elif relative == "docs/roadmap/phase_registry.json":
        start = b'    },\n    {\n      "phase_id": "REPAIR.INTENT.1",'
        end = b'  ]\n}\n'
        assert data.count(start) == 1 and data.count(end) == 1
        left = data.index(start)
        right = data.index(end, left)
        data = data[:left] + b'    }\n' + data[right:]
    elif relative == "web/app.py":
        data = _remove_between(data, b'from core.repair_intent import (',
                               b'from core.validation_command import')
        data = _replace_once(data,
            b'from web.session_store import (\n    load_sessions, save_sessions, find_session, create_repair_intent_wait,\n    update_repair_intent_wait,\n)\n',
            b'from web.session_store import load_sessions, save_sessions, find_session\n')
        data = _remove_between(data, b'    task_text = preserved_task_text(control)',
                               b'    from core.anti_lesson_control_injection import')
        data = _remove_between(data, b'    scope = control.get("repair_scope") or {}',
                               b'    enforce_control_grounding_on_payload(control, patch)')
        data = _remove_between(data, b'@app.route("/repair_intent/answer", methods=["POST"])',
                               b'@app.route("/undo_patch", methods=["POST"])')
        data = _replace_once(data,
            b'    )\n    from core.anti_lesson_control_injection',
            b'    )\n\n    from core.anti_lesson_control_injection')
        data = _replace_once(data, b'\n\n\n@app.route("/undo_patch",',
                             b'\n\n@app.route("/undo_patch",')
        data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    elif relative == "web/runner.py":
        data = _replace_once(data, b'from core.json_utils import extract_json_block\n')
        data = _replace_once(data, b'from core.repair_intent import SEMANTIC_INTENT_REQUIRED, admit_gap, render_question\n')
        data = _replace_once(data, b'from web.session_store import create_repair_intent_wait\n')
        data = _remove_between(data, b'        scope = (state.control_result or {}).get("repair_scope") or {}',
                               b'        _maybe_update_run_progress_snapshot_shadow(')
        data = _replace_once(data, b'from core.agent_state import AgentState\n',
                             b'from core.agent_state import AgentState\r\n')
        data = _replace_once(data, b'        draft = run_draft_pipeline(state)\n',
                             b'        draft = run_draft_pipeline(state)\r\n')
    elif relative == "web/session_store.py":
        data = _replace_once(data, b'import uuid\n')
        data = _remove_between(data, b'def create_repair_intent_wait(', b'def list_sessions(')
        data = _replace_once(data,
            b'def find_session(session_id: str) -> dict | None:\n',
            b'def find_session(session_id: str) -> dict | None:\r\n')
        data = _replace_once(data, b'    return None\n\n\n',
                             b'    return None\r\n\r\n\r\n')
    elif relative == "web/templates/index.html":
        data = _remove_between(data, b'          <div id="repairIntentClarification"',
                               b'          <pre id="context"')
        data = _remove_between(data, b'        if (data.status === "waiting_for_clarification") {',
                               b'        const settled = WorkbenchState.settle(ticket, WorkbenchState.generateOutcome(data));')
        data = _remove_between(data, b'{% if result and result.status == "waiting_for_clarification" and current %}',
                               b'function undoPatch()')
        data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return data


def before_repair_intent_admit1(relative: str, content: bytes) -> bytes:
    """Remove this phase's additive seams before older frozen byte receipts."""
    data = content
    if relative == "core/candidate_revision.py":
        data = _replace_once(data, b"from core.author_escalation_admission import admit_author_escalation\n")
        data = _replace_once(data, b'OUTPUT_AUTHOR_ESCALATION = "revision_author_escalation_quarantined"\n')
        data = _replace_once(data, b"    OUTPUT_AUTHOR_ESCALATION,\n")
        data = _replace_once(data, b"    quarantine_receipt: dict[str, Any] | None = None\n")
        data = _remove_between(data,
            b"    admission = admit_author_escalation(block, raw_response=text)",
            b'    candidate = block.get("patch_candidate")')
        data = _replace_once(data,
            b'    "patch_candidate field, whose target_snippet field holds the bytes you "',
            b'    "patch_candidate object, whose target_snippet field holds the bytes you "')
        data = _replace_once(data,
            b'    "is read. If you cannot safely author, return a null candidate with "\n'
            b'    "needs_escalation=true and exactly one non-none escalation_reason from "\n'
            b'    "the shared contract. Return that JSON object and nothing else."',
            b'    "is read. Return that JSON object and nothing else."')
        data = _replace_once(data,
            b'    "INSTRUCTION. Produce one revised patch candidate, if the evidence supports "\n'
            b'    "a safe fix, that addresses the "\n',
            b'    "INSTRUCTION. Produce one revised patch candidate that addresses the "\r\n')
        data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    elif relative == "core/patch_authoring_contract.py":
        data = _replace_once(data, b"patch_authoring_contract_v3",
                             b"patch_authoring_contract_v2")
        data = _replace_once(data,
            b'  "needs_escalation": false,\n'
            b'  "escalation_reason": "none|semantic_intent_required|missing_context|insufficient_evidence|unsupported_scope|author_output_invalid|other_bounded_reason"\n'
            b'}\n\nSelect exactly one escalation_reason from the listed values. When\n'
            b'needs_escalation=false, use "none". When needs_escalation=true, use one\n'
            b'non-none reason and set patch_candidate=null and patch_plan=null. If source\n'
            b'and evidence permit materially different observable behaviors without an\n'
            b'authoritative user/task choice, use "semantic_intent_required" and report a\n'
            b'source-grounded semantic_gap as instructed by the semantic intent handoff.\n'
            b'Never return a candidate alongside an unresolved escalation.\n"""',
            b'  "needs_escalation": false\n}\n"""')
    elif relative == "core/pipeline.py":
        data = _replace_once(data, b"from core.author_escalation_admission import admit_author_escalation\n")
        data = _remove_between(
            data,
            b"    # An unresolved author escalation is terminal for candidate review.",
            b"    if control_missing_source_snippet(state):",
        )
        data = _remove_between(
            data,
            b"    # REPAIR.INTENT.ADMIT.1: an author-requested escalation is terminal for",
            b"    reject_schema_drift(state)",
        )
        data = _remove_between(
            data,
            b"        if revised.quarantine_receipt is not None:",
            b"        print(",
        )
    elif relative == "tests/test_phase_registry.py":
        data = _replace_once(
            data,
            b'    assert "REPAIR.INTENT.ADMIT.1" in ids\n    assert len(data["phases"]) == 198\n',
            b'    assert len(data["phases"]) == 197\n',
        )
        data = _replace_once(data, b'            "CONTROL": 18,\n', b'            "CONTROL": 17,\n')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b"complete_or_history\": 194", b"complete_or_history\": 193")
        data = data.replace(b'["complete_or_history"] == 194', b'["complete_or_history"] == 193')
    elif relative == "tests/test_patch_authoring_context_live3.py":
        data = _replace_once(data,
            b"authoring.contract.version == 'patch_authoring_contract_v3'",
            b"authoring.contract.version == 'patch_authoring_contract_v2'")
    elif relative == "web/app.py":
        data = _replace_once(data, b"from core.author_escalation_admission import admit_author_escalation\n")
        data = _replace_once(data,
            b"    if not isinstance(patch, dict) or not patch:\n",
            b"    if not patch:\n")
        data = _remove_between(
            data,
            b"    # REPAIR.INTENT.ADMIT.1: a candidate accompanying author uncertainty is",
            b"    enforce_control_grounding_on_payload(control, patch)",
        )
        data = data.replace(
            b"    enforce_control_grounding_on_payload(control, patch)",
            b"    scope = control.get(\"repair_scope\") or {}\n"
            b"    enforce_control_grounding_on_payload(control, patch)", 1)
    elif relative == "web/runner.py":
        data = _replace_once(data, b"from core.author_escalation_admission import admit_author_escalation\n")
        data = _replace_once(data,
            b"from core.repair_intent import admit_gap, render_question\n",
            b"from core.repair_intent import SEMANTIC_INTENT_REQUIRED, admit_gap, render_question\n")
    return data
