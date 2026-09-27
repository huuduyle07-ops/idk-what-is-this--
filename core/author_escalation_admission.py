"""REPAIR.INTENT.ADMIT.1: deterministic admission of author escalation.

This is an author-output boundary, before candidate span, scope, minimality or
verification.  A model may report why it cannot safely author; it cannot make
an escalated candidate actionable by returning candidate bytes alongside it.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping


PHASE_ID = "REPAIR.INTENT.ADMIT.1"
REASON_NONE = "none"
REASON_SEMANTIC = "semantic_intent_required"
NONSEMANTIC_REASONS = frozenset({
    "missing_context", "insufficient_evidence", "unsupported_scope",
    "author_output_invalid", "other_bounded_reason",
})
REASONS = frozenset({REASON_NONE, REASON_SEMANTIC, *NONSEMANTIC_REASONS})

ADMITTED = "candidate_admitted"
SEMANTIC = "semantic_intent_required"
TYPED = "author_escalation_required"
UNCLASSIFIED = "author_escalation_unclassified"
INCONSISTENT = "author_output_inconsistent"


def _fingerprint(value: Any) -> str:
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        return ""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorEscalationAdmission:
    status: str
    reason: str
    candidate_present: bool
    candidate_fingerprint: str
    raw_candidate: Any
    raw_patch_plan: Any
    raw_author_response: str

    @property
    def admitted(self) -> bool:
        return self.status == ADMITTED

    @property
    def semantic(self) -> bool:
        return self.status == SEMANTIC

    def quarantine_receipt(self) -> dict[str, Any]:
        """Retain authorship as evidence, never under actionable patch keys."""
        return {
            "phase_id": PHASE_ID,
            "status": self.status,
            "escalation_reason": self.reason,
            "quarantine_reason": self.status,
            "candidate_present": self.candidate_present,
            "candidate_with_escalation": self.candidate_present and not self.admitted,
            "candidate_fingerprint": self.candidate_fingerprint,
            "raw_candidate": self.raw_candidate,
            "raw_patch_plan": self.raw_patch_plan,
            "raw_author_response": self.raw_author_response,
            "raw_author_response_fingerprint": hashlib.sha256(
                self.raw_author_response.encode("utf-8", errors="replace")
            ).hexdigest(),
            "write_authority": False,
            "execution_authorized": False,
        }


def admit_author_escalation(
    author: Mapping[str, Any], *, raw_response: str = ""
) -> AuthorEscalationAdmission:
    """Classify the structured flags only; prose and confidence grant nothing.

    Compatibility: omitted ``needs_escalation`` means false, and an omitted
    reason with false means ``none``.  An omitted reason with true never gets a
    default.  Explicit wrong types fail closed.
    """
    candidate = author.get("patch_candidate")
    plan = author.get("patch_plan")
    present = candidate is not None or plan not in (None, [])
    fingerprint = _fingerprint({"patch_candidate": candidate, "patch_plan": plan}) if present else ""
    flag = author.get("needs_escalation", False)
    raw_reason = author.get("escalation_reason")
    reason = REASON_NONE if raw_reason is None and flag is False else raw_reason
    if type(flag) is not bool or not isinstance(reason, str) or reason not in REASONS:
        status = UNCLASSIFIED
    elif flag is False:
        status = ADMITTED if reason == REASON_NONE else INCONSISTENT
    elif reason == REASON_SEMANTIC:
        status = SEMANTIC
    elif reason in NONSEMANTIC_REASONS:
        status = TYPED
    else:
        status = UNCLASSIFIED
    return AuthorEscalationAdmission(
        status=status, reason=reason if isinstance(reason, str) else "",
        candidate_present=present, candidate_fingerprint=fingerprint,
        raw_candidate=candidate, raw_patch_plan=plan,
        raw_author_response=raw_response if isinstance(raw_response, str) else "",
    )
