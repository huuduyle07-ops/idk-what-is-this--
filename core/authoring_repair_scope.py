"""PATCH.AUTHOR.SCOPE.1: consume, never select, a measured RepairScope.

This is draft containment, not minimality, verification or write authority.
Only named source reads are used; the BASIS producer owns membership.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path, PurePosixPath

from core.authoritative_binding_context import AuthoritativeBindingContext, build_authoritative_binding_context
from core.repair_scope import (
    MAX_REPAIR_MEMBERS, MAX_REPAIR_SOURCE_BYTES, PHASE_ID as BASIS_PHASE,
    RepairDiagnostic, RepairMember, RepairScope,
)
from core.repository_identity import derive_repository_id
from core.treesitter_parse import structural_definitions


PHASE_ID = "PATCH.AUTHOR.SCOPE.1"
MAX_RENDER_BYTES = 65_536


class AuthoringScopeError(ValueError):
    """A typed refusal before a provider or downstream candidate gate."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _source(root: str, file: str) -> bytes:
    path = PurePosixPath(file)
    if not file or path.is_absolute() or ".." in path.parts or ":" in file or "\\" in file:
        raise AuthoringScopeError("author_scope_cross_file")
    try:
        base = Path(root).resolve()
        target = (base / file).resolve()
        target.relative_to(base)
        return target.read_bytes()
    except (OSError, ValueError) as exc:
        raise AuthoringScopeError("author_scope_source_unavailable") from exc


def _normalized(raw: bytes) -> str:
    # The frozen BASIS snippet representation, never written back to disk.
    return raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True, slots=True)
class AuthoringRepairScope:
    measured: RepairScope
    repo_path: str
    language: str
    source: str
    member_ranges: tuple[tuple[int, int], ...]
    member_bindings: tuple[AuthoritativeBindingContext | None, ...]
    preflight_json: str

    def assert_current(self, preflight: dict | None = None) -> None:
        scope = self.measured
        if derive_repository_id(Path(self.repo_path).resolve()) != scope.repository_id:
            raise AuthoringScopeError("author_scope_repository_mismatch")
        if _digest(_source(self.repo_path, scope.primary_file)) != scope.source_fingerprint:
            raise AuthoringScopeError("author_scope_stale_source")
        if preflight is not None and _canonical(preflight) != self.preflight_json:
            raise AuthoringScopeError("author_scope_receipt_mismatch")
        for member, context in zip(scope.members, self.member_bindings):
            if context is not None and not context.is_current_for(
                authoritative_source=self.source, source_path=member.file,
                target_symbol=member.symbol, target_snippet=member.source_snippet,
            ):
                raise AuthoringScopeError("author_scope_stale_binding")

    @property
    def replacement_source(self) -> str:
        return self.source[self.member_ranges[0][0]:self.member_ranges[-1][1]]

    def as_dict(self) -> dict:
        # Reuse LIVE.3's binding projection independently for every member.
        from core.candidate_authoring_context import CandidateAuthoringContext
        from core.patch_authoring_contract import render_patch_authoring_contract

        self.assert_current()
        members = []
        for member, bindings in zip(self.measured.members, self.member_bindings):
            context = CandidateAuthoringContext(
                contract=render_patch_authoring_contract(style="safe_minimal", source_snippet=member.source_snippet),
                source_path=member.file, target_symbol=member.symbol,
                source_snippet=member.source_snippet, binding_context=bindings,
                authoritative_source=self.source,
            )
            text = context.scope_text
            if not text.startswith("AUTHORITATIVE AUTHORING SCOPE:\n"):
                raise AuthoringScopeError("author_scope_budget_exceeded")
            members.append({**member.as_dict(), "bindings": json.loads(text.split("\n", 1)[1])})
        result = {
            "phase_id": PHASE_ID,
            "file": self.measured.primary_file,
            "primary_symbol": self.measured.primary_symbol,
            "members": members,
            "evidence_source": BASIS_PHASE,
            "evidence_fingerprint": self.measured.evidence_fingerprint,
            "source_fingerprint": self.measured.source_fingerprint,
            "repository_id": self.measured.repository_id,
            "control_fingerprint": self.measured.control_fingerprint,
            "replacement_source": self.replacement_source,
            "write_authority": False, "execution_authorized": False,
            "auto_apply": False, "human_approval_required": True,
        }
        if len(_canonical(result).encode("utf-8")) > MAX_RENDER_BYTES:
            raise AuthoringScopeError("author_scope_budget_exceeded")
        return result

    def validate_candidate(self, block: dict) -> tuple[str, ...]:
        """Reject outside edits, ambiguous quotes and overlapping operations.

        Multiple replacements use the existing patch_plan shape if supplied;
        this does not make that shape acceptable to the frozen style gates.
        One patch_candidate can quote a bounded envelope with readonly gaps.
        """
        self.assert_current()
        candidate, plan = block.get("patch_candidate"), block.get("patch_plan")
        if candidate is not None and plan:
            raise AuthoringScopeError("author_scope_conflicting_candidate_shapes")
        operations = [candidate] if isinstance(candidate, dict) else plan
        if not isinstance(operations, list) or not operations or len(operations) > MAX_REPAIR_MEMBERS:
            raise AuthoringScopeError("author_scope_invalid_candidate")
        ranges, touched = [], set()
        replacements = []
        member_changes = {i: [] for i in range(len(self.member_ranges))}
        for op in operations:
            if not isinstance(op, dict) or op.get("op", "replace_snippet") != "replace_snippet":
                raise AuthoringScopeError("author_scope_invalid_operation")
            paths = [op[key] for key in ("file", "relative_path") if key in op]
            if not paths or any(path != self.measured.primary_file for path in paths):
                raise AuthoringScopeError("author_scope_cross_file")
            for key in ("target_node_name", "target_symbol"):
                if key in op and op[key] != self.measured.primary_symbol:
                    raise AuthoringScopeError("author_scope_primary_target_mismatch")
            old, new = op.get("target_snippet"), op.get("patched_snippet")
            if not isinstance(old, str) or not old or not isinstance(new, str):
                raise AuthoringScopeError("author_scope_invalid_candidate")
            if max(len(old.encode("utf-8")), len(new.encode("utf-8"))) > MAX_REPAIR_SOURCE_BYTES:
                raise AuthoringScopeError("author_scope_budget_exceeded")
            if len(self.measured.members) > 1:
                from core.candidate_replacement_span import validate_replacement_span
                start, end = validate_replacement_span(self, old, new)
            else:
                if self.source.count(old) != 1:
                    raise AuthoringScopeError("author_scope_ambiguous_quote")
                start = self.source.index(old)
                end = start + len(old)
                if start < self.member_ranges[0][0] or end > self.member_ranges[-1][1]:
                    raise AuthoringScopeError("authoring_scope_violation")
            if any(start < stop and begin < end for begin, stop in ranges):
                raise AuthoringScopeError("author_scope_overlapping_operations")
            ranges.append((start, end))
            for tag, a, b, c, d in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
                if tag == "equal":
                    continue
                owners = [i for i, (begin, stop) in enumerate(self.member_ranges)
                          if (begin <= start+a < start+b <= stop if a != b
                              else begin < start+a < stop)]
                if len(owners) != 1:
                    if len(self.measured.members) > 1:
                        from core.candidate_replacement_span import ReplacementSpanError
                        raise ReplacementSpanError("readonly_gap_modified", "authoring_scope_violation")
                    raise AuthoringScopeError("authoring_scope_violation")
                touched.add(owners[0])
                member_changes[owners[0]].append((start+a, start+b, new[c:d]))
            replacements.append((start, end, new))
        candidate_source = self.source
        for start, end, new in sorted(replacements, reverse=True):
            candidate_source = candidate_source[:start] + new + candidate_source[end:]
        before = structural_definitions(self.source, self.language)
        after = structural_definitions(candidate_source, self.language)
        # Braces/indentation cannot smuggle a new definition or swallow a sibling.
        identity = lambda result: Counter((d["kind"], d["name"]) for d in result["definitions"])
        if not after["available"] or identity(before) != identity(after):
            raise AuthoringScopeError("author_scope_definition_change")
        for i, member in enumerate(self.measured.members):
            begin, _ = self.member_ranges[i]
            expected = member.source_snippet
            for a, b, text in sorted(member_changes[i], reverse=True):
                expected = expected[:a-begin] + text + expected[b-begin:]
            if not any(d["kind"] == member.kind and d["name"] == member.symbol
                       and d["content"] == expected for d in after["definitions"]):
                raise AuthoringScopeError("author_scope_definition_change")
        for definition in before["definitions"]:
            start = len(self.source.encode("utf-8")[:definition["start"]].decode("utf-8"))
            end = len(self.source.encode("utf-8")[:definition["end"]].decode("utf-8"))
            if any(begin <= start and end <= stop for begin, stop in self.member_ranges):
                continue
            # Enclosing classes may contain the measured members; all other
            # definitions must retain their exact content and identity.
            if any(start <= begin and stop <= end for begin, stop in self.member_ranges):
                continue
            if not any(d["kind"] == definition["kind"] and d["name"] == definition["name"]
                       and d["content"] == definition["content"] for d in after["definitions"]):
                raise AuthoringScopeError("authoring_scope_violation")
        return tuple(self.measured.members[i].symbol for i in sorted(touched))


def consume_repair_scope(data: dict, *, repo_path: str, primary_file: str,
                         primary_symbol: str, primary_source: str,
                         preflight: dict, language: str) -> AuthoringRepairScope:
    """Validate the BASIS projection without discovering or adding members."""
    try:
        if data["phase_id"] != BASIS_PHASE or data["status"] != "complete":
            raise AuthoringScopeError("author_scope_incomplete")
        target = data["primary_target"]
        if target != {"file": primary_file, "symbol": primary_symbol}:
            raise AuthoringScopeError("author_scope_primary_target_mismatch")
        rows = data["members"]
        if not rows or len(rows) > MAX_REPAIR_MEMBERS:
            raise AuthoringScopeError("author_scope_budget_exceeded")
        members = tuple(RepairMember(
            row["file"], row["symbol"], row["kind"], row["span"]["start_line"],
            row["span"]["end_line"], row["source_snippet"],
            tuple(RepairDiagnostic.from_mapping(d) for d in row["diagnostics"]),
        ) for row in rows)
        scope = RepairScope(
            status="complete", primary_file=primary_file, primary_symbol=primary_symbol,
            members=members, evidence_fingerprint=data["evidence_fingerprint"],
            source_fingerprint=data["source_fingerprint"], repository_id=data["repository_id"],
            control_fingerprint=data["control_fingerprint"], reason=str(data.get("reason") or ""),
        )
        if sum(len(m.source_snippet.encode("utf-8")) for m in members) > MAX_REPAIR_SOURCE_BYTES:
            raise AuthoringScopeError("author_scope_budget_exceeded")
        if (preflight.get("evidence_source") != "PREFLIGHT.REQUEST.1"
                or preflight.get("evidence_kind") != "compile_evidence"
                or preflight.get("measured") is not True or preflight.get("ran") is not True
                or preflight.get("category") != "build_error"
                or scope.evidence_fingerprint != preflight.get("receipt_fingerprint")
                or scope.control_fingerprint != preflight.get("control_sha256")
                or scope.repository_id != preflight.get("repository_id")
                or {"path": primary_file, "sha256": scope.source_fingerprint}
                not in preflight.get("source_fingerprints", [])):
            raise AuthoringScopeError("author_scope_receipt_mismatch")
        for fingerprint in (scope.evidence_fingerprint, scope.control_fingerprint, scope.source_fingerprint):
            if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise AuthoringScopeError("author_scope_receipt_mismatch")
        raw = _source(repo_path, primary_file)
        if _digest(raw) != scope.source_fingerprint:
            raise AuthoringScopeError("author_scope_stale_source")
        source = _normalized(raw)
        structural = structural_definitions(source, language)
        if not structural["available"]:
            raise AuthoringScopeError("author_scope_ambiguous")
        ranges, bindings, diagnostics = [], [], []
        for member in members:
            if member.file != primary_file:
                raise AuthoringScopeError("author_scope_cross_file")
            matches = [d for d in structural["definitions"] if
                       (d["name"], d["kind"], d["start_line"], d["end_line"], d["content"])
                       == (member.symbol, member.kind, member.start_line, member.end_line, member.source_snippet)]
            if len(matches) != 1 or not member.diagnostics:
                raise AuthoringScopeError("author_scope_ambiguous")
            definition = matches[0]
            start = len(source.encode("utf-8")[:definition["start"]].decode("utf-8"))
            end = len(source.encode("utf-8")[:definition["end"]].decode("utf-8"))
            if ranges and start < ranges[-1][1]:
                raise AuthoringScopeError("author_scope_overlapping_members")
            ranges.append((start, end))
            for diagnostic in member.diagnostics:
                if (diagnostic.file != primary_file or diagnostic.severity != "error"
                        or diagnostic.kind != "compiler_error"
                        or not member.start_line <= diagnostic.line <= member.end_line):
                    raise AuthoringScopeError("author_scope_diagnostic_mismatch")
                diagnostics.append(_canonical(diagnostic.as_dict()))
            bindings.append(build_authoritative_binding_context(
                repo_root=repo_path, source_path=primary_file,
                target_symbol=member.symbol, authoritative_source=source,
            ))
        measured_diagnostics = [RepairDiagnostic.from_mapping(d) for d in preflight["locations"]
                                if d.get("severity") == "error" and d.get("kind") == "compiler_error"]
        if Counter(diagnostics) != Counter(_canonical(d.as_dict()) for d in measured_diagnostics):
            raise AuthoringScopeError("author_scope_incomplete")
        targets = preflight.get("targets", [])
        if (sum(t["errors"] for t in targets) != len(diagnostics)
                or any(t["errors"] and t["path"] != primary_file for t in targets)):
            raise AuthoringScopeError("author_scope_incomplete")
        primary = [m for m in members if m.symbol == primary_symbol]
        if len(primary) != 1 or not primary_source or primary_source not in primary[0].source_snippet:
            raise AuthoringScopeError("author_scope_primary_target_mismatch")
        result = AuthoringRepairScope(scope, str(Path(repo_path).resolve()), language, source,
                                      tuple(ranges), tuple(bindings), _canonical(preflight))
        if len(result.replacement_source.encode("utf-8")) > MAX_REPAIR_SOURCE_BYTES:
            raise AuthoringScopeError("author_scope_budget_exceeded")
        result.assert_current(preflight)
        return result
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, AuthoringScopeError):
            raise
        raise AuthoringScopeError("author_scope_malformed") from exc


def enforce_authoring_scope(context, block: dict) -> bool:
    """A passing draft still requires every existing downstream gate."""
    repair = context.authoring_repair_scope
    if repair is None or not (block.get("patch_candidate") or block.get("patch_plan")):
        return True
    from core.candidate_sandbox_validation import candidate_fingerprint_from_payload

    fingerprint = candidate_fingerprint_from_payload(block)
    try:
        touched = repair.validate_candidate(block)
    except AuthoringScopeError as exc:
        block.update(patch_candidate=None, patch_plan=None, needs_escalation=True,
                     authoring_scope_status=getattr(exc, "scope_reason", exc.reason),
                     authoring_scope_candidate_fingerprint=fingerprint)
        if len(repair.measured.members) > 1:
            block["author_output_status"] = exc.reason
        return False
    if len(repair.measured.members) > 1:
        block["author_output_status"] = "valid_replacement_span"
    block.update(authoring_scope_status="within_measured_repair_scope",
                 authoring_scope_touched_definitions=list(touched),
                 authoring_scope_candidate_fingerprint=fingerprint)
    return True
