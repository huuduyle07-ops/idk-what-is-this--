"""Reverse only SPEC.1 bookkeeping; preserve every frozen prerequisite receipt."""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_candidate_behavior_spec1(relative: str, content: bytes) -> bytes:
    from tests._patch_candidate_behavior_exec_plan1_maintenance import before_patch_candidate_behavior_exec_plan1
    content = before_patch_candidate_behavior_exec_plan1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_candidate_behavior_spec1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed behavior-spec change")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.CANDIDATE.BEHAVIOR.SPEC.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.\n'
        end = b'# End PATCH.CANDIDATE.BEHAVIOR.SPEC.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 218') == restored.count(b'"CONTROL": 36') == 1
            restored = restored.replace(b'len(data["phases"]) == 218', b'len(data["phases"]) == 217', 1)
            restored = restored.replace(b'"CONTROL": 36', b'"CONTROL": 35', 1)
        else:
            assert restored.count(b'"complete_or_history": 214') == 1
            assert restored.count(b'["complete_or_history"] == 214') == 35
            restored = restored.replace(b'"complete_or_history": 214', b'"complete_or_history": 213')
            restored = restored.replace(b'["complete_or_history"] == 214', b'["complete_or_history"] == 213')
    else:
        addition = (b'    from tests._patch_candidate_behavior_spec1_maintenance import before_patch_candidate_behavior_spec1\n'
                    b'    content = before_patch_candidate_behavior_spec1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "behavior-spec reversal differs")
    return restored
