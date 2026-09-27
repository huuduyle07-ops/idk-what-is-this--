"""PATCH.BASIS.SCOPE.1 — measured, same-file repair scope.

This module turns one already-authoritative PREFLIGHT.REQUEST.1 compiler
receipt into a bounded set of structural definitions.  It does not discover
files, interpret model text, choose a primary target, or grant patch authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from core.repository_identity import derive_repository_id
from core.treesitter_parse import structural_definitions


PHASE_ID = "PATCH.BASIS.SCOPE.1"
PREFLIGHT_EVIDENCE_SOURCE = "PREFLIGHT.REQUEST.1"

REPAIR_SCOPE_NOT_APPLICABLE = "not_applicable"
REPAIR_SCOPE_COMPLETE = "complete"
REPAIR_SCOPE_INCOMPLETE = "repair_scope_incomplete"
REPAIR_SCOPE_CROSS_FILE_REQUIRED = "cross_file_scope_required"
REPAIR_SCOPE_BUDGET_EXCEEDED = "repair_scope_budget_exceeded"

MAX_REPAIR_MEMBERS = 8
MAX_REPAIR_SOURCE_BYTES = 16_384


def _normal_path(value: object) -> str:
    return str(value or "").replace("\\", "/").lstrip("./")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


@dataclass(frozen=True, slots=True)
class RepairDiagnostic:
    """One immutable, typed compiler diagnostic associated with one member."""

    file: str
    line: int
    column: int | None
    severity: str
    kind: str
    message: str

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> "RepairDiagnostic":
        return cls(
            file=_normal_path(item.get("file")),
            line=int(item.get("line") or 0),
            column=(int(item["col"]) if isinstance(item.get("col"), int) else None),
            severity=str(item.get("severity") or ""),
            kind=str(item.get("kind") or ""),
            message=str(item.get("message") or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.column,
            "severity": self.severity,
            "kind": self.kind,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class RepairMember:
    """A structurally grounded, exact-source definition in the repair set."""

    file: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    source_snippet: str
    diagnostics: tuple[RepairDiagnostic, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "symbol": self.symbol,
            "kind": self.kind,
            "span": {"start_line": self.start_line, "end_line": self.end_line},
            "source_snippet": self.source_snippet,
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class RepairScope:
    """The additive evidence record; primary localization remains separate."""

    status: str
    primary_file: str
    primary_symbol: str
    members: tuple[RepairMember, ...] = ()
    evidence_fingerprint: str = ""
    source_fingerprint: str = ""
    repository_id: str = ""
    control_fingerprint: str = ""
    reason: str = ""

    @property
    def is_complete(self) -> bool:
        return self.status == REPAIR_SCOPE_COMPLETE

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "status": self.status,
            "reason": self.reason,
            "primary_target": {
                "file": self.primary_file,
                "symbol": self.primary_symbol,
            },
            "members": [item.as_dict() for item in self.members],
            "evidence_fingerprint": self.evidence_fingerprint,
            "source_fingerprint": self.source_fingerprint,
            "repository_id": self.repository_id,
            "control_fingerprint": self.control_fingerprint,
            "authority": {
                "write_authority": False,
                "execution_authorized": False,
                "auto_apply": False,
            },
        }


def _not_applicable(primary_file: str, primary_symbol: str) -> RepairScope:
    return RepairScope(
        REPAIR_SCOPE_NOT_APPLICABLE, primary_file, primary_symbol,
        reason="no supported authoritative compiler receipt",
    )


def _refusal(
    status: str,
    primary_file: str,
    primary_symbol: str,
    *,
    preflight: Mapping[str, Any],
    reason: str,
) -> RepairScope:
    return RepairScope(
        status=status,
        primary_file=primary_file,
        primary_symbol=primary_symbol,
        evidence_fingerprint=str(preflight.get("receipt_fingerprint") or ""),
        repository_id=str(preflight.get("repository_id") or ""),
        control_fingerprint=str(preflight.get("control_sha256") or ""),
        reason=reason,
    )


def _source_fingerprints(preflight: Mapping[str, Any]) -> dict[str, str] | None:
    rows = preflight.get("source_fingerprints")
    if not isinstance(rows, list):
        return None
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        path, digest = _normal_path(row.get("path")), str(row.get("sha256") or "")
        if not path or not _is_sha256(digest):
            return None
        result[path] = digest
    return result


def _owned_definitions(
    definitions: list[dict[str, Any]],
    diagnostic: RepairDiagnostic,
    *,
    eligible_kind: str,
) -> list[dict[str, Any]]:
    """Return structural owners only; location proximity never participates."""
    return [
        item
        for item in definitions
        if item.get("kind") == eligible_kind
        and int(item.get("start_line") or 0) <= diagnostic.line <= int(item.get("end_line") or 0)
    ]


def build_repair_scope(
    *,
    repo_path: str | Path | None,
    primary_file: str | None,
    primary_symbol: str | None,
    primary_kind: str | None,
    language: str | None,
    preflight: Mapping[str, Any] | None,
    receipt_control_fingerprint: str | None,
) -> RepairScope:
    """Build a scope from one current PREFLIGHT.REQUEST.1 handoff.

    The caller supplies the CONTROL fingerprint *before* the handoff has been
    enriched by later CONTROL bookkeeping.  A different fingerprint is an
    explicit provenance refusal, not a cue to reuse a stale receipt.
    """
    file = _normal_path(primary_file)
    symbol = str(primary_symbol or "").strip()
    kind = str(primary_kind or "").strip()
    if not isinstance(preflight, Mapping) or not file or not symbol or not kind:
        return _not_applicable(file, symbol)
    if (
        preflight.get("evidence_source") != PREFLIGHT_EVIDENCE_SOURCE
        or preflight.get("evidence_kind") != "compile_evidence"
        or preflight.get("measured") is not True
        or preflight.get("ran") is not True
        or preflight.get("category") != "build_error"
    ):
        return _not_applicable(file, symbol)

    receipt_fingerprint = str(preflight.get("receipt_fingerprint") or "")
    control_fingerprint = str(preflight.get("control_sha256") or "")
    if not _is_sha256(receipt_fingerprint) or not _is_sha256(control_fingerprint):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="receipt_binding_unavailable")
    if receipt_control_fingerprint != control_fingerprint:
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="control_fingerprint_mismatch")

    source_fingerprints = _source_fingerprints(preflight)
    if source_fingerprints is None or file not in source_fingerprints:
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="source_fingerprint_unavailable")
    try:
        root = Path(repo_path).resolve()
        current_repository_id = derive_repository_id(root)
        path = (root / file).resolve()
        path.relative_to(root)
        raw_source = path.read_bytes()
    except (OSError, ValueError):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="grounded_source_unavailable")
    if current_repository_id != str(preflight.get("repository_id") or ""):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="repository_identity_mismatch")
    current_source_fingerprint = _sha256_bytes(raw_source)
    if current_source_fingerprint != source_fingerprints[file]:
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="source_fingerprint_mismatch")

    try:
        source = raw_source.decode("utf-8", errors="replace")
        structural = structural_definitions(source, str(language or ""))
    except (UnicodeError, ValueError):
        structural = {"available": False, "definitions": []}
    if not structural.get("available"):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="structural_definitions_unavailable")

    locations = preflight.get("locations")
    if not isinstance(locations, list):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="typed_diagnostics_unavailable")
    diagnostics: list[RepairDiagnostic] = []
    for item in locations:
        if not isinstance(item, Mapping):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="malformed_typed_diagnostic")
        try:
            diagnostic = RepairDiagnostic.from_mapping(item)
        except (TypeError, ValueError):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="malformed_typed_diagnostic")
        if diagnostic.severity != "error" or diagnostic.kind != "compiler_error":
            continue
        if not diagnostic.file or diagnostic.line < 1:
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="unscoped_compiler_diagnostic")
        if diagnostic.file != file:
            return _refusal(REPAIR_SCOPE_CROSS_FILE_REQUIRED, file, symbol, preflight=preflight,
                            reason="compiler_error_in_another_file")
        diagnostics.append(diagnostic)
    if not diagnostics:
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="no_primary_file_compiler_errors")

    target_error_count = None
    for target in preflight.get("targets") or []:
        if not isinstance(target, Mapping):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="malformed_preflight_target")
        errors = target.get("errors")
        if not isinstance(errors, int):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="malformed_preflight_target_errors")
        target_file = _normal_path(target.get("path"))
        if errors and target_file != file:
            return _refusal(REPAIR_SCOPE_CROSS_FILE_REQUIRED, file, symbol, preflight=preflight,
                            reason="compiler_errors_in_another_file")
        if target_file == file:
            target_error_count = errors
    if not isinstance(target_error_count, int) or target_error_count != len(diagnostics):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="incomplete_typed_compiler_diagnostics")

    grouped: dict[tuple[str, int, int], tuple[dict[str, Any], list[RepairDiagnostic]]] = {}
    for diagnostic in diagnostics:
        try:
            owners = _owned_definitions(
                list(structural.get("definitions") or ()), diagnostic, eligible_kind=kind,
            )
        except (TypeError, ValueError):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="structural_definition_invalid")
        if not owners:
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="unscoped_compiler_diagnostic")
        if len(owners) != 1:
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="ambiguous_compiler_diagnostic")
        definition = owners[0]
        key = (str(definition.get("name") or ""), int(definition.get("start_line") or 0),
               int(definition.get("end_line") or 0))
        if not key[0] or key[1] < 1 or key[2] < key[1] or not definition.get("content"):
            return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                            reason="structural_definition_invalid")
        if key not in grouped:
            grouped[key] = (definition, [])
        grouped[key][1].append(diagnostic)

    ordered = sorted(grouped.values(), key=lambda item: (int(item[0]["start_line"]), int(item[0]["end_line"]),
                                                           str(item[0]["name"])))
    if len(ordered) > MAX_REPAIR_MEMBERS:
        return _refusal(REPAIR_SCOPE_BUDGET_EXCEEDED, file, symbol, preflight=preflight,
                        reason="definition_count_budget_exceeded")
    members = tuple(
        RepairMember(
            file=file,
            symbol=str(definition["name"]),
            kind=str(definition["kind"]),
            start_line=int(definition["start_line"]),
            end_line=int(definition["end_line"]),
            # The primary target has historically passed through universal newline
            # handling. Keep every member in that same author-facing form.
            source_snippet=str(definition.get("content") or "").replace("\r\n", "\n").replace("\r", "\n"),
            diagnostics=tuple(items),
        )
        for definition, items in ordered
    )
    aggregate_source_bytes = sum(len(item.source_snippet.encode("utf-8")) for item in members)
    if aggregate_source_bytes > MAX_REPAIR_SOURCE_BYTES:
        return _refusal(REPAIR_SCOPE_BUDGET_EXCEEDED, file, symbol, preflight=preflight,
                        reason="aggregate_source_budget_exceeded")
    if not any(item.file == file and item.symbol == symbol for item in members):
        return _refusal(REPAIR_SCOPE_INCOMPLETE, file, symbol, preflight=preflight,
                        reason="primary_target_excluded")

    return RepairScope(
        status=REPAIR_SCOPE_COMPLETE,
        primary_file=file,
        primary_symbol=symbol,
        members=members,
        evidence_fingerprint=receipt_fingerprint,
        source_fingerprint=current_source_fingerprint,
        repository_id=current_repository_id,
        control_fingerprint=control_fingerprint,
        reason="source_definition_order",
    )


def render_repair_scope_prompt(scope: RepairScope) -> str:
    """Render the additive authoring section; one-member inputs retain old meaning."""
    if not scope.is_complete or len(scope.members) <= 1:
        return ""
    return "[MEASURED REPAIR SCOPE — authoritative compiler evidence]\n" + json.dumps(
        scope.as_dict(), ensure_ascii=False, sort_keys=True, indent=2,
    )


__all__ = [
    "MAX_REPAIR_MEMBERS",
    "MAX_REPAIR_SOURCE_BYTES",
    "PHASE_ID",
    "PREFLIGHT_EVIDENCE_SOURCE",
    "REPAIR_SCOPE_BUDGET_EXCEEDED",
    "REPAIR_SCOPE_COMPLETE",
    "REPAIR_SCOPE_CROSS_FILE_REQUIRED",
    "REPAIR_SCOPE_INCOMPLETE",
    "REPAIR_SCOPE_NOT_APPLICABLE",
    "RepairDiagnostic",
    "RepairMember",
    "RepairScope",
    "build_repair_scope",
    "render_repair_scope_prompt",
]
