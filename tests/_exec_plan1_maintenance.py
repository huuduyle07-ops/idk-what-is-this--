"""Test-only exact EXEC.PLAN.1 reversal, before older immutable receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def before_exec_plan1(relative: str, content: bytes | None = None) -> bytes:
    current = (ROOT / relative).read_bytes() if content is None else content
    from tests._auth_dream1_maintenance import before_auth_dream1
    current = before_auth_dream1(relative, current)
    receipt = json.loads((ROOT / 'tests/fixtures/exec_plan1_reversal.json').read_text(encoding='utf-8'))
    record = receipt['files'].get(relative)
    if record is None:
        return current
    assert hashlib.sha256(current).hexdigest() == record['post_sha256'], relative
    text = current.decode('utf-8')
    for hunk in reversed(record['hunks']):
        assert text.count(hunk['after']) == 1, relative
        text = text.replace(hunk['after'], hunk['before'], 1)
    restored = text.encode('utf-8')
    assert hashlib.sha256(restored).hexdigest() == record['entry_sha256'], relative
    return restored
