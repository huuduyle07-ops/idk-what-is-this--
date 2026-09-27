"""Reconstruct historical phase bytes before the explicit harness remediation.

This is a test-only reversal, never an import hook or runtime code path. Earlier
fixtures remain unchanged; the separate maintenance receipt pins current bytes,
exact reversible hunks, and the bytes they reconstruct. Pipeline's pre hash also
matches the original black-box audit snapshot. LIVE.2's fixture describes a
concurrent snapshot, so its three authoring hunks are reversed only after this
maintenance, and LIVE.1's exact digest remains the historical proof.

Receipts recorded after the remediation (``LATER_RECEIPTS``) are undone
first, newest first, each asserting its own post and pre digests, because a
pin taken before the remediation is older than every one of them.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/2026-09-10-harness-remediation-reversal.json"
#: Reversal receipts recorded after the remediation, newest first.
LATER_RECEIPTS = (
    ROOT / "tests/fixtures/patch_author_live3_reversal.json",
    ROOT / "tests/fixtures/patch_minimal_live3_reversal.json",
    ROOT / "tests/fixtures/indent_runtime1_reversal.json",
    ROOT / "tests/fixtures/indent_semantics1_reversal.json",
    ROOT / "tests/fixtures/answer_coherence_live1_reversal.json",
)


def before_later_receipts(
    relative: str, content: bytes, *, newer_than: Path | None = None
) -> bytes:
    # Hunks apply to the raw decoded text: these receipts keep each file's own
    # line endings, and core/agent_state.py mixes CRLF with LF.
    # ``newer_than`` stops at that receipt: a phase that pins *current* bytes
    # undoes only the receipts recorded after its own, never its own or older.
    # The newer governance phases have their own exact test-only chain.  Undo
    # them before entering this older receipt format and chronology.
    from tests._data_undo1_maintenance import before_data_undo1

    content = before_data_undo1(relative, content)
    sec_receipt = json.loads(
        (ROOT / "tests/fixtures/sec_ui1_reversal.json").read_text(encoding="utf-8")
    )
    sec_record = sec_receipt["files"].get(relative)
    if sec_record is not None:
        text = content.decode("utf-8")
        for hunk in reversed(sec_record["hunks"]):
            assert text.count(hunk["after"]) == 1, (
                relative,
                "sec_ui1_reversal.json",
                "non-unique hunk",
            )
            text = text.replace(hunk["after"], hunk["before"], 1)
        content = text.encode("utf-8")
        assert hashlib.sha256(content).hexdigest() == sec_record["entry_sha256"], (
            relative,
            "sec_ui1_reversal.json",
        )
    for path in LATER_RECEIPTS:
        if newer_than is not None and path == newer_than:
            break
        receipt = json.loads(path.read_text(encoding="utf-8"))
        reversal = next((item for item in receipt["reversals"] if item["path"] == relative), None)
        if reversal is None:
            continue
        assert hashlib.sha256(content).hexdigest() == reversal["post_sha256"], (relative, path.name)
        text = content.decode("utf-8")
        for hunk in reversal["hunks"]:
            assert text.count(hunk["post"]) == 1, (relative, path.name, "non-unique hunk")
            text = text.replace(hunk["post"], hunk["pre"], 1)
        if reversal.get("pre_newline") == "CRLF":
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        content = text.encode("utf-8")
        assert hashlib.sha256(content).hexdigest() == reversal["pre_sha256"], (relative, path.name)
    return content


def before_harness_remediation(relative: str, content: bytes | None = None) -> bytes:
    current = (ROOT / relative).read_bytes() if content is None else content
    current = before_later_receipts(relative, current)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    reversal = next((item for item in fixture["reversals"] if item["path"] == relative), None)
    if reversal is None:
        return current
    assert hashlib.sha256(current).hexdigest() == reversal["post_sha256"], relative
    text = current.decode("utf-8").replace("\r\n", "\n")
    for hunk in reversal["hunks"]:
        assert text.count(hunk["post"]) == 1, (relative, "non-unique maintenance hunk")
        text = text.replace(hunk["post"], hunk["pre"], 1)
    if reversal["pre_newline"] == "CRLF":
        text = text.replace("\n", "\r\n")
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == reversal["pre_sha256"], relative
    return restored


def before_author_live3_prompt(prompt: str, source_snippet: str) -> str:
    """Test-only projection to the measured LIVE.2 prompt, preserving its hash.

    Use only in historical Round-10 prompt tests. Current-oracle tests must
    inspect the full scope and concrete inputs instead.
    """
    import re
    import sys
    import types
    from core.patch_authoring_contract import render_patch_authoring_contract

    receipt = ROOT / "tests/fixtures/patch_minimal_live3_reversal.json"
    raw = before_later_receipts("core/patch_authoring_contract.py",
                               (ROOT/"core/patch_authoring_contract.py").read_bytes(),
                               newer_than=receipt)
    name = "_historical_author_live2_contract"
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(raw, name, "exec"), module.__dict__)
        old = module.render_patch_authoring_contract(style="safe_minimal", source_snippet=source_snippet)
    finally:
        sys.modules.pop(name, None)
    current = render_patch_authoring_contract(style="safe_minimal", source_snippet=source_snippet)
    prompt = prompt.replace(current.text, old.text, 1)
    if "AUTHORITATIVE AUTHORING SCOPE:\n" in prompt:
        start = prompt.index("AUTHORITATIVE AUTHORING SCOPE:\n")
        value_start = start + len("AUTHORITATIVE AUTHORING SCOPE:\n")
        _, consumed = json.JSONDecoder().raw_decode(prompt[value_start:])
        prompt = prompt[:start] + prompt[value_start + consumed + 2:]
    return re.sub(r"\ninput_language=[^\n]*\ncase_probe_fingerprint=[^\n]*\nINPUT \([0-9]+ UTF-8 bytes\):\n.*?\nEND INPUT", "", prompt, flags=re.S)
