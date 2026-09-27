"""Test-only reversal of SPAN.1; older phase evidence remains immutable."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def before_patch_author_span1(relative: str, content: bytes) -> bytes:
    from tests._repair_intent1_maintenance import before_repair_intent1
    content = before_repair_intent1(relative, content)
    receipt = json.loads((ROOT/'tests/fixtures/patch_author_span1_reversal.json').read_text(encoding='utf-8'))
    record = receipt['files'].get(relative)
    if record is None or hashlib.sha256(content).hexdigest() == record['entry_sha256']:
        return content
    assert hashlib.sha256(content).hexdigest() == record['post_sha256'], relative
    text = content.decode('utf-8')
    for hunk in reversed(record['hunks']):
        assert text.count(hunk['after']) == 1, relative
        text = text.replace(hunk['after'], hunk['before'], 1)
    restored = text.encode('utf-8')
    assert hashlib.sha256(restored).hexdigest() == record['entry_sha256'], relative
    return restored
