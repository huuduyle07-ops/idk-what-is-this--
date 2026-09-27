"""PATCH.AUTHOR.SPAN.1: exact replacement intervals, never repair membership.

Consumes AUTHOR.SCOPE's normalized source and measured ranges. No traversal,
source rebasing, provider calls, compilation or mutation authority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from typing import TYPE_CHECKING, Literal, get_args

from core.authoring_repair_scope import AuthoringScopeError
from core.treesitter_parse import structural_definitions

if TYPE_CHECKING:
    from core.authoring_repair_scope import AuthoringRepairScope

PHASE_ID = "PATCH.AUTHOR.SPAN.1"
SpanRejection = Literal[
    "target_not_unique", "outside_authoring_envelope", "replacement_span_mismatch",
    "readonly_gap_modified", "duplicate_definition_risk", "missing_definition_risk",
]

SPAN_REJECTION_REASONS = get_args(SpanRejection)


class ReplacementSpanError(AuthoringScopeError):
    """Specific output validity plus the frozen containment classification."""

    def __init__(self, reason: SpanRejection, scope_reason: str):
        super().__init__(reason)
        self.scope_reason = scope_reason


def _unique_start(source: str, target: str) -> int:
    start = source.find(target)
    # Unlike str.count, this also detects overlapping exact matches.
    if not target or start < 0 or source.find(target, start + 1) >= 0:
        raise ReplacementSpanError("target_not_unique", "author_scope_ambiguous_quote")
    return start


def canonical_replacement_envelope(scope: AuthoringRepairScope) -> dict:
    """Project the existing authoritative interval; never infer one from output."""
    scope.assert_current()
    start, end = scope.member_ranges[0][0], scope.member_ranges[-1][1]
    original = scope.replacement_source
    if _unique_start(scope.source, original) != start:
        raise ReplacementSpanError("replacement_span_mismatch", "authoring_scope_violation")
    return {
        "phase_id": PHASE_ID,
        "file": scope.measured.primary_file,
        "source_representation": "authoring_normalized_utf8",
        "span": {"start": start, "end": end, "unit": "unicode_codepoints", "end_exclusive": True},
        "utf8_span": {"start": len(scope.source[:start].encode("utf-8")),
                      "end": len(scope.source[:end].encode("utf-8")), "end_exclusive": True},
        "source_fingerprint": scope.measured.source_fingerprint,
        "evidence_fingerprint": scope.measured.evidence_fingerprint,
        "original_snippet": original,
        "original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "editable_members": [member.symbol for member in scope.measured.members],
        "intervening_source_readonly": True,
    }


def validate_replacement_span(scope: AuthoringRepairScope, old: str, new: str) -> tuple[int, int]:
    """Resolve an exact interval and reject definition injection/loss before diff.

    A historical exact sub-envelope is valid only with the same definitions
    still present once after replacement. The existing member-diff and structural
    containment checks remain mandatory after this preliminary alignment check.
    """
    _unique_start(scope.source, scope.replacement_source)
    start = _unique_start(scope.source, old)
    end = start + len(old)
    if start < scope.member_ranges[0][0] or end > scope.member_ranges[-1][1]:
        raise ReplacementSpanError("outside_authoring_envelope", "authoring_scope_violation")
    before = structural_definitions(scope.source, scope.language)
    after = structural_definitions(scope.source[:start] + new + scope.source[end:], scope.language)
    if not before["available"] or not after["available"]:
        raise ReplacementSpanError("replacement_span_mismatch", "author_scope_definition_change")
    identity = lambda result: Counter((d["kind"], d["name"]) for d in result["definitions"])
    baseline, proposed = identity(before), identity(after)
    if any(count > baseline[key] for key, count in proposed.items() if key in baseline):
        raise ReplacementSpanError("duplicate_definition_risk", "author_scope_definition_change")
    if baseline - proposed:
        raise ReplacementSpanError("missing_definition_risk", "author_scope_definition_change")
    if proposed != baseline:
        raise ReplacementSpanError("replacement_span_mismatch", "author_scope_definition_change")
    return start, end
