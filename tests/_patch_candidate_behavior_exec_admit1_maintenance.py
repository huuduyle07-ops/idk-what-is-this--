"""Reverse only EXEC.ADMIT.1 bookkeeping; preserve every frozen receipt hash."""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_candidate_behavior_exec_admit1(relative: str, content: bytes) -> bytes:
    from tests._preflight_runtime1_maintenance import before_preflight_runtime1
    content = before_preflight_runtime1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_candidate_behavior_exec_admit1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed execution-admission change")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.\n'
        end = b'# End PATCH.CANDIDATE.BEHAVIOR.EXEC.ADMIT.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 221') == restored.count(b'"CONTROL": 39') == 1
            restored = restored.replace(b'len(data["phases"]) == 221', b'len(data["phases"]) == 220', 1)
            restored = restored.replace(b'"CONTROL": 39', b'"CONTROL": 38', 1)
        else:
            assert restored.count(b'"complete_or_history": 217') == 1
            assert restored.count(b'["complete_or_history"] == 217') == 38
            restored = restored.replace(b'"complete_or_history": 217', b'"complete_or_history": 216')
            restored = restored.replace(b'["complete_or_history"] == 217', b'["complete_or_history"] == 216')
    else:
        addition = (b'    from tests._patch_candidate_behavior_exec_admit1_maintenance import before_patch_candidate_behavior_exec_admit1\n'
                    b'    content = before_patch_candidate_behavior_exec_admit1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "execution-admission reversal differs")
    return restored
