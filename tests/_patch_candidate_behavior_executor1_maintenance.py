"""Reverse additive blocked EXECUTOR.1 bookkeeping without repinning history."""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_candidate_behavior_executor1(relative: str, content: bytes) -> bytes:
    from tests._runtime_sandbox1_maintenance import before_runtime_sandbox1
    content = before_runtime_sandbox1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_candidate_behavior_executor1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed runtime-executor change")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.\n'
        end = b'# End PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 223') == restored.count(b'"CONTROL": 41') == 1
            restored = restored.replace(b'len(data["phases"]) == 223', b'len(data["phases"]) == 222', 1)
            restored = restored.replace(b'"CONTROL": 41', b'"CONTROL": 40', 1)
        else:
            assert restored.count(b'"blocked": 1') == 1
            restored = restored.replace(b'"blocked": 1', b'"blocked": 0', 1)
    else:
        addition = (b'    from tests._patch_candidate_behavior_executor1_maintenance import before_patch_candidate_behavior_executor1\n'
                    b'    content = before_patch_candidate_behavior_executor1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "runtime-executor reversal differs")
    return restored
