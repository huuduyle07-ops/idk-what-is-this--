"""Reverse only AUTHOR.STRUCTURAL.1 bookkeeping; historical receipts stay pinned."""
from hashlib import sha256
import json
from pathlib import Path


def before_patch_author_structural1(relative: str, content: bytes) -> bytes:
    from tests._patch_candidate_materialize1_maintenance import before_patch_candidate_materialize1
    content = before_patch_candidate_materialize1(relative, content)
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "patch_author_structural1_reversal.json").read_text(encoding="utf-8"))
    record = next((r for r in receipt["reversals"] if r["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed structural author change")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "PATCH.AUTHOR.STRUCTURAL.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.\n'
        end = b'# End PATCH.AUTHOR.STRUCTURAL.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 215') == restored.count(b'"CONTROL": 33') == 1
            restored = restored.replace(b'len(data["phases"]) == 215', b'len(data["phases"]) == 214', 1)
            restored = restored.replace(b'"CONTROL": 33', b'"CONTROL": 32', 1)
            addition = (b'        # AUTHOR.STRUCTURAL.1 permits one injected read-only author call.\n'
                        b'        "PATCH.AUTHOR.STRUCTURAL.1",\n')
            assert restored.count(addition) == 1
            restored = restored.replace(addition, b'', 1)
        else:
            assert restored.count(b'"complete_or_history": 211') == 1
            assert restored.count(b'["complete_or_history"] == 211') == 32
            restored = restored.replace(b'"complete_or_history": 211', b'"complete_or_history": 210')
            restored = restored.replace(b'["complete_or_history"] == 211', b'["complete_or_history"] == 210')
    else:
        addition = (b'    from tests._patch_author_structural1_maintenance import before_patch_author_structural1\n'
                    b'    content = before_patch_author_structural1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "structural author reversal differs")
    return restored
