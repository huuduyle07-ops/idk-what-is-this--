"""Reverse only attributed PLAN.1 bookkeeping for frozen historical assertions.

No historical receipt is repinned. The new receipt pins both sides of this
phase's four shared-file changes; unexpected changes fail closed.
"""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_scope_plan1(relative: str, content: bytes) -> bytes:
    from tests._patch_scope_admit1_maintenance import before_patch_scope_admit1
    content = before_patch_scope_admit1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_scope_plan1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed change after PLAN.1")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.SCOPE.PLAN.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.SCOPE.PLAN.1 bookkeeping boundary.\n'
        end = b'# End PATCH.SCOPE.PLAN.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 213') == 1
            assert restored.count(b'"CONTROL": 31') == 1
            restored = restored.replace(b'len(data["phases"]) == 213', b'len(data["phases"]) == 212', 1).replace(
                b'"CONTROL": 31', b'"CONTROL": 30', 1)
            declaration = (b'        # PLAN.1 exposes one already-authorized planner call and no author call.\n'
                           b'        "PATCH.SCOPE.PLAN.1",\n')
            assert restored.count(declaration) == 1
            restored = restored.replace(declaration, b'', 1)
        else:
            assert restored.count(b'"complete_or_history": 209') == 1
            assert restored.count(b'["complete_or_history"] == 209') == 30
            restored = restored.replace(b'"complete_or_history": 209', b'"complete_or_history": 208').replace(
                b'["complete_or_history"] == 209', b'["complete_or_history"] == 208')
    else:
        addition = (b'    from tests._patch_scope_plan1_maintenance import before_patch_scope_plan1\n'
                    b'    content = before_patch_scope_plan1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "PLAN.1 reversal differs from entry")
    return restored
