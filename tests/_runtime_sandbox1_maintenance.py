"""Reverse additive SANDBOX.1 bookkeeping without repinning frozen history."""
from hashlib import sha256
import json
from pathlib import Path


def before_runtime_sandbox1(relative: str, content: bytes) -> bytes:
    receipt = json.loads((Path(__file__).parent / "fixtures" /
                          "runtime_sandbox1_reversal.json").read_text(encoding="utf-8"))
    record = next((row for row in receipt["reversals"] if row["path"] == relative), None)
    if record is None:
        return content
    assert sha256(content).hexdigest() == record["post_sha256"], (relative, "unattributed runtime-sandbox change")
    if relative == "docs/roadmap/phase_registry.json":
        marker = b'    },\n    {\n      "phase_id": "RUNTIME.SANDBOX.1",'
        tail = b'\n  ]\n}\n'
        assert content.count(marker) == content.count(tail) == 1
        restored = content[:content.index(marker)] + b'    }' + tail
    elif relative in {"tests/test_phase_registry.py", "tests/test_phase_picker.py"}:
        start = b'\n\n# RUNTIME.SANDBOX.1 bookkeeping boundary.\n'
        end = b'# End RUNTIME.SANDBOX.1 bookkeeping boundary.\n'
        assert content.count(start) == content.count(end) == 1
        restored = content[:content.index(start)] + content[content.index(end) + len(end):]
        if relative == "tests/test_phase_registry.py":
            assert restored.count(b'len(data["phases"]) == 224') == restored.count(b'"CONTROL": 42') == 1
            restored = restored.replace(b'len(data["phases"]) == 224', b'len(data["phases"]) == 223', 1)
            restored = restored.replace(b'"CONTROL": 42', b'"CONTROL": 41', 1)
        else:
            assert restored.count(b'"complete_or_history": 219') == 1
            assert restored.count(b'["complete_or_history"] == 219') == 41
            restored = restored.replace(b'"complete_or_history": 219', b'"complete_or_history": 218', 1)
            restored = restored.replace(b'["complete_or_history"] == 219', b'["complete_or_history"] == 218')
    elif relative == "core/phase_registry.py":
        addition = (b'    # RUNTIME.* names runtime-infrastructure capability inside CONTROL.\n'
                    b'    # It is an ID namespace only; sandbox capability grants no authority.\n'
                    b'    "RUNTIME",\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    else:
        addition = (b'    from tests._runtime_sandbox1_maintenance import before_runtime_sandbox1\n'
                    b'    content = before_runtime_sandbox1(relative, content)\n')
        assert content.count(addition) == 1
        restored = content.replace(addition, b'', 1)
    assert sha256(restored).hexdigest() == record["entry_sha256"], (relative, "runtime-sandbox reversal differs")
    return restored
