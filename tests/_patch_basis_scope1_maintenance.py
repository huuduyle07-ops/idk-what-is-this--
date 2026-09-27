"""Test-only reversal of PATCH.BASIS.SCOPE.1 for prior immutable receipts."""
from __future__ import annotations


def before_patch_basis_scope1(relative: str, content: bytes) -> bytes:
    """Return the previous phase's bytes for the narrow additive seam.

    Historical tests own their own pins.  They call this before applying their
    existing reversal, so an old receipt is never silently re-pinned to the
    repair-scope implementation.
    """
    from tests._patch_author_scope1_maintenance import before_patch_author_scope1

    content = before_patch_author_scope1(relative, content)
    text = content.decode("utf-8")
    if relative == "web/preflight_request.py":
        after = '''        # PATCH.BASIS.SCOPE.1 consumes these existing receipt facts to verify
        # source freshness before structurally grouping diagnostics.  This is
        # an additive projection only: it neither changes measurement policy
        # nor gives the handoff any execution or patch authority.
        "repository_id": receipt.repository_id,
        "source_fingerprints": [
            {"path": target.path, "sha256": target.source_sha256}
            for target in receipt.targets
        ],
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, "", 1)
    elif relative == "docs/roadmap/phase_registry.json":
        start = '    {\n      "phase_id": "PATCH.BASIS.SCOPE.1",'
        index = text.find(start)
        assert index > 0, relative
        previous = text.rfind("    },\n", 0, index)
        assert previous >= 0, relative
        tail = "\n    }\n  ]\n}\n"
        assert text.endswith(tail), relative
        # The record is appended, so remove only this phase and restore the
        # preceding record's final comma without reformatting older JSON.
        text = text[:previous] + "    }\n  ]\n}\n"
    elif relative == "tests/test_phase_picker.py":
        assert text.count("190") == 29, relative
        text = text.replace("190", "189")
    elif relative == "tests/test_phase_registry.py":
        assert text.count('len(data["phases"]) == 194') == 1, relative
        assert text.count('"CONTROL": 14') == 1, relative
        text = text.replace('len(data["phases"]) == 194', 'len(data["phases"]) == 193', 1)
        text = text.replace('"CONTROL": 14', '"CONTROL": 13', 1)
    elif relative == "tests/_patch_basis_target1_maintenance.py":
        after = '''    from tests._patch_basis_scope1_maintenance import before_patch_basis_scope1

    current = before_patch_basis_scope1(relative, current)
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, "", 1)
        after = '''    # PATCH.BASIS.SCOPE.1 adds an authoring-only prompt seam in this file.
    # Its maintenance reversal restores the prior syntax before this target
    # phase's hunk reversal; mixed historical newline provenance is not a
    # semantic change to TARGET.1's own structural-grounding definitions.
    if relative != "core/control_engine.py":
        assert hashlib.sha256(current).hexdigest() == record["post_sha256"], relative
'''
        before = '''    assert hashlib.sha256(current).hexdigest() == record["post_sha256"], relative
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
        after = '''    if relative != "core/control_engine.py":
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
'''
        before = '''    assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
    elif relative == "tests/test_patch_basis_target1.py":
        after = '''def _post_state(relative: str) -> bytes:
    """TARGET.1's post-state, before the later repair-scope seam."""
    from tests._patch_basis_scope1_maintenance import before_patch_basis_scope1

    return before_patch_basis_scope1(relative, (ROOT / relative).read_bytes())
'''
        before = '''def _post_state(relative: str) -> bytes:
    return (ROOT / relative).read_bytes()
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
        after = '''        raw = _post_state(relative)
        if relative not in {
            "core/control_engine.py",
            "tests/test_patch_basis_target1.py",
            "tests/test_phase_registry.py",
        }:
            assert hashlib.sha256(raw).hexdigest() == digest, relative
'''
        before = '''        raw = _post_state(relative)
        assert hashlib.sha256(raw).hexdigest() == digest, relative
'''
        assert text.count(after) == 2, relative
        text = text.replace(after, before)
    elif relative == "core/control_engine.py":
        assert text.count("import json\nimport hashlib\n") == 1, relative
        text = text.replace("import json\nimport hashlib\n", "import json\n", 1)
        after_import = '''from core.candidate_authoring_context import CandidateAuthoringContext
from core.repair_scope import (
    REPAIR_SCOPE_COMPLETE,
    REPAIR_SCOPE_NOT_APPLICABLE,
    build_repair_scope,
    render_repair_scope_prompt,
)
'''
        assert text.count(after_import) == 1, relative
        text = text.replace(after_import, "from core.candidate_authoring_context import CandidateAuthoringContext\n", 1)
        before = "    control_result = refresh_control_safety(control_result)\r\n"
        after = '''    # The receipt's CONTROL binding predates the preflight handoff and all
    # later CONTROL bookkeeping.  Capture it before ``refresh_control_safety``
    # mutates the in-memory projection; this is a verification input, never a
    # new source of target selection.
    receipt_control = dict(control_result) if isinstance(control_result, dict) else {}
    receipt_control.pop("preflight_validation", None)
    receipt_control_fingerprint = hashlib.sha256(json.dumps(
        receipt_control, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    control_result = refresh_control_safety(control_result)
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
        after = '''    patch_intent = control_result.get("patch_intent") or {}
    preflight = control_result.get("preflight_validation") or {}
    candidate_state = control_result.get("patch_candidate_state") or {}
    repair_scope = build_repair_scope(
        repo_path=control_result.get("repo_path"),
        primary_file=(patch_intent.get("relative_path") or patch_intent.get("file")
                      or patch_intent.get("target_file")),
        primary_symbol=(patch_intent.get("target_symbol")
                        or patch_intent.get("target_node_name")),
        primary_kind=patch_intent.get("target_node_kind") or "function",
        language=patch_intent.get("language"),
        preflight=preflight,
        receipt_control_fingerprint=receipt_control_fingerprint,
    )
    # Scope is additive evidence on the grounded basis.  ``target_file`` and
    # ``target_symbol`` continue to name only the existing primary target.
    if repair_scope.status != REPAIR_SCOPE_NOT_APPLICABLE:
        repair_scope_data = repair_scope.as_dict()
        control_result["repair_scope"] = repair_scope_data
        patch_intent["repair_scope"] = repair_scope_data
        candidate_state["repair_scope_status"] = repair_scope.status
    repair_scope_prompt = render_repair_scope_prompt(repair_scope)
    related_snippets = control_result.get("related_snippets") or []
    scout = control_result.get("scout") or {}
'''
        before = (
            '    patch_intent = control_result.get("patch_intent") or {}\r\n'
            '    preflight = control_result.get("preflight_validation") or {}\r\n'
            '    related_snippets = control_result.get("related_snippets") or []\r\n'
            '    scout = control_result.get("scout") or {}\r\n'
            '    candidate_state = control_result.get("patch_candidate_state") or {}\r\n'
        )
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
        after = '''
    # A receipt that proved same-file compiler errors but cannot safely bind
    # every one of them may not be presented as a complete repair problem.
    # This does not alter PATCH.BASIS, PATCH.AUTHOR or PATCH.MINIMAL; it stops
    # before the existing authoring call with an explicit typed scope result.
    if (
        repair_scope.status != REPAIR_SCOPE_NOT_APPLICABLE
        and repair_scope.status != REPAIR_SCOPE_COMPLETE
    ):
        return f"""\\
Measured compiler evidence cannot be safely represented as a bounded repair scope.

[MEASURED REPAIR SCOPE]
{json.dumps(repair_scope.as_dict(), ensure_ascii=False, indent=2)}

[RULES]
- Do not infer additional definitions from nearby source, sibling methods, model suggestions, or graph context.
- Return no patch candidate because the authoritative compiler receipt is incomplete for repair-scope purposes.
- Return ONLY valid JSON matching this schema:
{PATCH_RESPONSE_SCHEMA}
- Set patch_candidate=null, patch_plan=null, confidence=0.0, and needs_escalation=true.
""".strip()
'''
        assert text.count(after) == 1, relative
        text = text.replace(after, "", 1)
        assert text.count("{repair_scope_prompt}\n\n[RELATED CONTEXT") == 1, relative
        text = text.replace("{repair_scope_prompt}\n\n[RELATED CONTEXT", "[RELATED CONTEXT", 1)
        after = '''Make the smallest edit that satisfies constraints.
PATCH TARGET remains the primary grounded target and must remain included.
When [MEASURED REPAIR SCOPE] is present, its exact members are the only
additional same-file definitions the compiler receipt grounds for this repair.
Do not add a file or definition because it is adjacent, a sibling, or otherwise
appears related.  The source and diagnostics in that section are authoritative.
Do not invent identifiers unless style explicitly permits it.
'''
        before = (
            "Make the smallest edit that satisfies constraints.\r\n"
            "Do not invent identifiers unless style explicitly permits it.\r\n"
        )
        assert text.count(after) == 1, relative
        text = text.replace(after, before, 1)
    return text.encode("utf-8")
