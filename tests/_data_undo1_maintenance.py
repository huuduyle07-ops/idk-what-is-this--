"""Test-only DATA.UNDO.1 reversal; preserve earlier immutable phase fixtures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def before_data_undo1(relative: str, content: bytes | None = None) -> bytes:
    current = (ROOT / relative).read_bytes() if content is None else content
    from tests._exec_plan1_maintenance import before_exec_plan1
    current = before_exec_plan1(relative, current)
    fixture = json.loads((ROOT / "tests/fixtures/data_undo1_reversal.json").read_text(encoding="utf-8"))
    record = fixture["files"].get(relative)
    if record is None:
        return current
    assert hashlib.sha256(current).hexdigest() == record["post_sha256"], relative
    text = current.decode("utf-8")
    for hunk in reversed(record["hunks"]):
        assert text.count(hunk["after"]) == 1, relative
        text = text.replace(hunk["after"], hunk["before"], 1)
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
    return restored
