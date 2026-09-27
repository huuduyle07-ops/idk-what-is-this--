"""Test-only reversal of the additive PATCH.AUTHOR.SCOPE.1 seams."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def before_patch_author_scope1(relative: str, content: bytes) -> bytes:
    from tests._patch_author_span1_maintenance import before_patch_author_span1

    content = before_patch_author_span1(relative, content)
    receipt = json.loads((ROOT/'tests/fixtures/patch_author_scope1_reversal.json').read_text(encoding='utf-8'))
    record = receipt['files'].get(relative)
    if record is None:
        return content
    if hashlib.sha256(content).hexdigest() == record['entry_sha256']:
        return content
    assert hashlib.sha256(content).hexdigest() == record['post_sha256'], relative
    text = content.decode('utf-8')
    for hunk in reversed(record['hunks']):
        assert text.count(hunk['after']) == 1, (relative, 'non-unique author scope reversal')
        text = text.replace(hunk['after'], hunk['before'], 1)
    restored = text.encode('utf-8')
    assert hashlib.sha256(restored).hexdigest() == record['entry_sha256'], relative
    return restored
