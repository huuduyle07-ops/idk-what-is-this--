"""Resolve semantic-gap references against one already measured repair scope.

References name only objects in the current scope. Model quotes are never used
to locate source; the scope's normalized structural snippet is mapped back to
the fingerprinted raw file without reparsing or searching other files.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


PHASE_ID = "REPAIR.INTENT.GROUND.1"
UNRESOLVED = "semantic_gap_evidence_unresolved"
MAX_REFS = 8
MAX_ANCHOR_BYTES = 16_384


class EvidenceRefError(ValueError):
    def __init__(self):
        super().__init__(UNRESOLVED)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _projection(raw: bytes) -> tuple[str, str, list[int]]:
    source = raw.decode("utf-8", errors="strict")
    normalized = []
    offsets = [0]
    index = 0
    while index < len(source):
        if source[index:index + 2] == "\r\n":
            normalized.append("\n")
            index += 2
        elif source[index] == "\r":
            normalized.append("\n")
            index += 1
        else:
            normalized.append(source[index])
            index += 1
        offsets.append(index)
    return source, "".join(normalized), offsets


def _anchor(*, ref: str, kind: str, scope: Mapping[str, Any], file: str,
            owner: str, raw: bytes, source: str, begin: int, end: int,
            fact: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not 0 <= begin < end <= len(source):
        raise EvidenceRefError()
    exact = source[begin:end]
    start_byte = len(source[:begin].encode("utf-8"))
    end_byte = start_byte + len(exact.encode("utf-8"))
    body = {"ref": ref, "kind": kind, "repository_id": scope["repository_id"],
            "file": file, "structural_owner": owner,
            "source_fingerprint": scope["source_fingerprint"],
            "span": {"start_byte": start_byte, "end_byte": end_byte},
            "exact_text": exact, "provenance": "measured_repair_scope",
            "fact": dict(fact or {})}
    identity = _sha(json.dumps(body, sort_keys=True, ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8"))
    return {"anchor_id": identity, **body}


def available_repair_intent_refs(scope: Mapping[str, Any]) -> tuple[str, ...]:
    """Closed request-local IDs shown to the author with the existing prompt."""
    refs = []
    file = (scope.get("primary_target") or {}).get("file")
    for member in scope.get("members") or ():
        if not isinstance(member, Mapping) or member.get("file") != file:
            continue
        owner = member.get("symbol")
        if not isinstance(owner, str) or not owner:
            continue
        refs.append(f"member:{file}::{owner}")
        for index, _ in enumerate(member.get("diagnostics") or (), 1):
            refs.append(f"diagnostic:{file}::{owner}::{index}")
        binding_context = member.get("bindings") or {}
        if not isinstance(binding_context, Mapping) or not binding_context.get("source_sha256"):
            continue
        for binding in binding_context.get("available_baseline_bindings") or ():
            if isinstance(binding, Mapping) and isinstance(binding.get("name"), str):
                refs.append(f"binding:{file}::{owner}::{binding['name']}")
    return tuple(refs)


def resolve_repair_intent_evidence_refs(*, refs: list[str] | tuple[str, ...],
                                        scope: Mapping[str, Any], raw: bytes) -> tuple[dict[str, Any], ...]:
    if not isinstance(refs, (tuple, list)) or not 1 <= len(refs) <= MAX_REFS:
        raise EvidenceRefError()
    if _sha(raw) != scope.get("source_fingerprint"):
        raise EvidenceRefError()
    file = (scope.get("primary_target") or {}).get("file")
    if not isinstance(file, str) or not file:
        raise EvidenceRefError()
    source, normalized, offsets = _projection(raw)
    lines = normalized.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    anchors = []
    seen = set()
    total = 0
    for ref in refs:
        if not isinstance(ref, str) or len(ref) > 300 or ref not in available_repair_intent_refs(scope):
            raise EvidenceRefError()
        if ref in seen:
            continue
        seen.add(ref)
        parts = ref.split(":", 1)
        kind, identity = parts[0], parts[1]
        tokens = identity.split("::")
        if len(tokens) not in (2, 3) or tokens[0] != file:
            raise EvidenceRefError()
        owners = [m for m in scope.get("members") or () if m.get("file") == file
                  and m.get("symbol") == tokens[1]]
        if len(owners) != 1:
            raise EvidenceRefError()
        member = owners[0]
        span = member.get("span") or {}
        first, last = span.get("start_line"), span.get("end_line")
        if not isinstance(first, int) or not isinstance(last, int) or not 1 <= first <= last <= len(lines):
            raise EvidenceRefError()
        line_start, line_end = starts[first - 1], starts[last]
        snippet = member.get("source_snippet")
        if not isinstance(snippet, str) or not snippet:
            raise EvidenceRefError()
        segment = normalized[line_start:line_end]
        if segment.count(snippet) != 1:
            raise EvidenceRefError()
        member_start = line_start + segment.index(snippet)
        member_end = member_start + len(snippet)
        fact = None
        if kind == "member" and len(tokens) == 2:
            begin, end = member_start, member_end
        elif kind == "diagnostic" and len(tokens) == 3:
            diagnostics = member.get("diagnostics") or ()
            try:
                index = int(tokens[2]) - 1
                diagnostic = diagnostics[index]
                line = diagnostic["line"]
            except (ValueError, IndexError, KeyError, TypeError):
                raise EvidenceRefError() from None
            if not 0 <= index < len(diagnostics) or diagnostic.get("file") != file or not first <= line <= last:
                raise EvidenceRefError()
            begin, end = starts[line - 1], starts[line]
            fact = diagnostic
        elif kind == "binding" and len(tokens) == 3:
            context = member.get("bindings") or {}
            if not isinstance(context, Mapping) or (context.get("source_path") != file
                    or context.get("target_symbol") != tokens[1]
                    or context.get("source_sha256") != _sha(normalized.encode("utf-8"))
                    or context.get("target_source_sha256") != _sha(snippet.encode("utf-8"))):
                raise EvidenceRefError()
            bindings = [b for b in context.get("available_baseline_bindings") or ()
                        if isinstance(b, Mapping) and b.get("name") == tokens[2]]
            if len(bindings) != 1:
                raise EvidenceRefError()
            begin, end = member_start, member_end
            fact = bindings[0]
        else:
            raise EvidenceRefError()
        anchor = _anchor(ref=ref, kind=kind, scope=scope, file=file, owner=tokens[1],
                         raw=raw, source=source, begin=offsets[begin], end=offsets[end], fact=fact)
        total += len(anchor["exact_text"].encode("utf-8"))
        if total > MAX_ANCHOR_BYTES:
            raise EvidenceRefError()
        anchors.append(anchor)
    return tuple(anchors)
