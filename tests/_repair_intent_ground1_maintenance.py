"""Test-only reversal of GROUND.1 before immutable earlier-phase receipts."""
from __future__ import annotations


def _once(data: bytes, new: bytes, old: bytes = b"") -> bytes:
    assert data.count(new) == 1, "non-unique grounding reversal hunk"
    return data.replace(new, old, 1)


def before_repair_intent_ground1(relative: str, content: bytes) -> bytes:
    data = content
    if relative == "core/pipeline.py":
        data = _once(data,
            b'author_escalation_directive(state.control_result["repair_scope"])',
            b'author_escalation_directive()')
    elif relative == "web/app.py":
        data = _once(data, b'from core.repair_intent_evidence_refs import EvidenceRefError\n')
        data = _once(data, b'author_escalation_directive(control["repair_scope"])',
                     b'author_escalation_directive()')
        data = _once(data,
            b'            try:\n'
            b'                gap = admit_gap(\n'
            b'                    author=author_for_gap, task_text=task_text, control=control,\n'
            b'                    scope=scope, repo_path=repo_path or "",\n'
            b'                ) if task_text and scope else None\n'
            b'            except EvidenceRefError:\n'
            b'                return {**common, "status": "needs_clarification",\n'
            b'                        "code": "semantic_gap_evidence_unresolved",\n'
            b'                        "error": "The semantic evidence reference did not resolve."}\n',
            b'            gap = admit_gap(\n'
            b'                author=author_for_gap, task_text=task_text, control=control,\n'
            b'                scope=scope, repo_path=repo_path or "",\n'
            b'            ) if task_text and scope else None\n')
    elif relative == "web/runner.py":
        data = _once(data, b'from core.repair_intent_evidence_refs import EvidenceRefError\n')
        data = _once(data,
            b'                    try:\n'
            b'                        gap = admit_gap(\n'
            b'                            author=author_for_gap, task_text=query,\n'
            b'                            control=state.control_result or {}, scope=scope,\n'
            b'                            repo_path=state.repo_path or "",\n'
            b'                        ) if scope else None\n'
            b'                    except EvidenceRefError:\n'
            b'                        return {**common,\n'
            b'                                "answer": "The semantic evidence reference did not resolve.",\n'
            b'                                "status": "needs_clarification",\n'
            b'                                "code": "semantic_gap_evidence_unresolved"}\n',
            b'                    gap = admit_gap(\n'
            b'                        author=author_for_gap, task_text=query,\n'
            b'                        control=state.control_result or {}, scope=scope,\n'
            b'                        repo_path=state.repo_path or "",\n'
            b'                    ) if scope else None\n')
    elif relative == "docs/roadmap/phase_registry.json":
        start = b'    },\n    {\n      "phase_id": "REPAIR.INTENT.GROUND.1",'
        end = b'\n  ]\n}\n'
        assert data.count(start) == 1 and data.count(end) == 1
        left = data.index(start)
        right = data.index(end, left)
        data = data[:left] + b'    }' + data[right:]
    elif relative == "tests/test_phase_registry.py":
        data = _once(data, b'len(data["phases"]) == 199', b'len(data["phases"]) == 198')
        data = _once(data, b'"CONTROL": 19', b'"CONTROL": 18')
    elif relative == "tests/test_phase_picker.py":
        data = data.replace(b'"complete_or_history": 195', b'"complete_or_history": 194')
        data = data.replace(b'["complete_or_history"] == 195',
                            b'["complete_or_history"] == 194')
    return data
