"""Reverse ADMIT.1 bookkeeping only; never repin a historical frozen receipt."""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_scope_admit1(relative: str, content: bytes) -> bytes:
    from tests._patch_author_structural1_maintenance import before_patch_author_structural1
    content = before_patch_author_structural1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_scope_admit1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed change after ADMIT.1")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.SCOPE.ADMIT.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.SCOPE.ADMIT.1 bookkeeping boundary.\n'
        end = b'# End PATCH.SCOPE.ADMIT.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 214') == 1
            assert restored.count(b'"CONTROL": 32') == 1
            restored = restored.replace(b'len(data["phases"]) == 214', b'len(data["phases"]) == 213', 1).replace(
                b'"CONTROL": 32', b'"CONTROL": 31', 1)
        else:
            assert restored.count(b'"complete_or_history": 210') == 1
            assert restored.count(b'["complete_or_history"] == 210') == 31
            restored = restored.replace(b'"complete_or_history": 210', b'"complete_or_history": 209').replace(
                b'["complete_or_history"] == 210', b'["complete_or_history"] == 209')
    else:
        addition = (b'    from tests._patch_scope_admit1_maintenance import before_patch_scope_admit1\n'
                    b'    content = before_patch_scope_admit1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "ADMIT.1 reversal differs from entry")
    return restored
