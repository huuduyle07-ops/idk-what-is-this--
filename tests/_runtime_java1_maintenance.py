"""Authenticate and reverse only additive RUNTIME.JAVA.1 registry bookkeeping.

Historical receipt files and their exact frozen tests remain unchanged. This
helper is used explicitly by the Java-owned frozen-regression pytest plugin;
current Java governance tests always inspect the current registry.
"""
from hashlib import sha256
import json
from pathlib import Path


def before_runtime_java1(relative: str, content: bytes) -> bytes:
    if relative != "docs/roadmap/phase_registry.json":
        return content
    fixture = Path(__file__).parent / "fixtures/runtime_java1_reversal.json"
    receipt = json.loads(fixture.read_text(encoding="utf-8"))
    assert receipt["phase_id"] == "RUNTIME.JAVA.1"
    record, = receipt["reversals"]
    assert record["path"] == relative
    assert sha256(content).hexdigest() == record["post_sha256"], (
        relative, "unattributed runtime-java change")
    marker = b'    },\n    {\n      "phase_id": "RUNTIME.JAVA.1",'
    tail = b'\n  ]\n}\n'
    assert content.count(marker) == content.count(tail) == 1
    restored = content[:content.index(marker)] + b'    }' + tail
    assert sha256(restored).hexdigest() == record["entry_sha256"], (
        relative, "runtime-java reversal differs")
    return restored
