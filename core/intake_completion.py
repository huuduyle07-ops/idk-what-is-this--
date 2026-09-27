"""INPUT.3 — deterministic intake completion policy.

INPUT.1 preserved what the user said.  INPUT.2 understood what the user meant.
INPUT.3 answers one further question and stops:

    is that understood request complete enough for a future execution waiter
    to inspect?

    TaskContract + semantic status
        -> deterministic completion policy
        -> CompletionDecision

Every decision here is deterministic.  No model participates: the optional
local Intake Assistant (``core.intake_assistant``) may only rephrase what this
module already decided.  Turning that model off changes wording and nothing
else.

    Local AI may improve the words.  It may not change the decision.

``ready_for_future_handoff`` is deliberately *not* ``routing_allowed``,
``execution_allowed`` or a selected mode.  It is true only for a READY
completion with a passed preservation gate and verified INPUT.2 semantic
evidence.  READY itself grants no authority of any kind; see
:func:`intake_authority`.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, selects no execution mode or provider,
and grants no authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.semantic_waiter_runner import (
    ATTEMPT_OK,
    ATTEMPT_PRESERVATION_FAILED,
    SEMANTIC_DETERMINISTIC_FALLBACK,
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_OUTPUT_INVALID,
    SemanticWaiterOutcome,
    SemanticWaiterReceipt,
)
from core.task_contract import (
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    TaskContract,
)


PHASE_ID = "INPUT.3"
COMPLETION_DECISION_SCHEMA_VERSION = "input_3_completion_decision_v2"

# ── Completion states ─────────────────────────────────────────────────────────
#: Intake semantics are sufficient for a future execution-routing layer to
#: inspect.  Not "execute now", not a mode, not an approval.
STATE_READY = "ready"
#: Meaning is clear; useful operational detail is missing on a broad task.
STATE_GOAL_BRIEF_ASSIST = "goal_brief_assist"
#: The meaning itself could not be resolved safely.
STATE_ASK_CLARIFICATION = "ask_clarification"
#: The user's own explicit commitments conflict with each other.
STATE_BLOCKED_CONTRADICTION = "blocked_contradiction"
#: The interpreter or its infrastructure failed.  Never the user's fault.
STATE_SEMANTIC_SYSTEM_FAILURE = "semantic_system_failure"

COMPLETION_STATES: tuple[str, ...] = (
    STATE_READY,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_ASK_CLARIFICATION,
    STATE_BLOCKED_CONTRADICTION,
    STATE_SEMANTIC_SYSTEM_FAILURE,
)

# ── Ownership ─────────────────────────────────────────────────────────────────
#: Who owns the unresolved problem.  Deterministic; never model-assigned.
OWNER_USER_MEANING_AMBIGUITY = "user_meaning_ambiguity"
OWNER_OPERATIONAL_DETAIL_MISSING = "operational_detail_missing"
OWNER_SEMANTIC_SYSTEM_FAILURE = "semantic_system_failure"
OWNER_EXPLICIT_CONSTRAINT_CONFLICT = "explicit_constraint_conflict"

COMPLETION_OWNERS: tuple[str, ...] = (
    OWNER_USER_MEANING_AMBIGUITY,
    OWNER_OPERATIONAL_DETAIL_MISSING,
    OWNER_SEMANTIC_SYSTEM_FAILURE,
    OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
)

#: The one owner each non-READY state may carry.
_STATE_OWNERS: dict[str, str] = {
    STATE_GOAL_BRIEF_ASSIST: OWNER_OPERATIONAL_DETAIL_MISSING,
    STATE_ASK_CLARIFICATION: OWNER_USER_MEANING_AMBIGUITY,
    STATE_BLOCKED_CONTRADICTION: OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
    STATE_SEMANTIC_SYSTEM_FAILURE: OWNER_SEMANTIC_SYSTEM_FAILURE,
}

# ── Semantic status ───────────────────────────────────────────────────────────
#: No semantic model ran: the contract came from INPUT.1's deterministic
#: interpreter.  That is a healthy preview path, not a failure, but it is not
#: execution-bound handoff evidence.
SEMANTIC_STATUS_NOT_RUN = "semantic_interpretation_not_run"

#: Statuses under which the interpretation may be trusted as understanding.
HEALTHY_SEMANTIC_STATUSES: frozenset[str] = frozenset({
    SEMANTIC_STATUS_NOT_RUN,
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
})

#: A completion preview may proceed without a semantic run, but a future
#: execution-bound handoff cannot.  These are the only INPUT.2 outcomes whose
#: receipts attest to an accepted semantic interpretation.
HANDOFF_VALID_SEMANTIC_STATUSES: frozenset[str] = frozenset({
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
})

#: Statuses that mean the model or its infrastructure failed.  A deterministic
#: fallback belongs here: INPUT.2 records it as a substitution for a model
#: failure, not as semantic understanding.
FAILED_SEMANTIC_STATUSES: frozenset[str] = frozenset({
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_OUTPUT_INVALID,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_DETERMINISTIC_FALLBACK,
})

# ── Handoff evidence ─────────────────────────────────────────────────────────
#: A receipt is retained only as INPUT.2 evidence; INPUT.3 does not create a
#: second semantic truth system.  The values below are deterministic summaries
#: of that receipt for callers and serialized inspection.
SEMANTIC_EVIDENCE_VALID = "semantic_receipt_valid"
SEMANTIC_EVIDENCE_MISSING = "semantic_receipt_missing"
SEMANTIC_EVIDENCE_INVALID = "semantic_receipt_invalid"

SEMANTIC_EVIDENCE_STATUSES: tuple[str, ...] = (
    SEMANTIC_EVIDENCE_VALID,
    SEMANTIC_EVIDENCE_MISSING,
    SEMANTIC_EVIDENCE_INVALID,
)

#: Bounded, derived explanations for why a completed intake is not eligible for
#: a future execution waiter.  They grant no authority and do not change the
#: completion state.
HANDOFF_BLOCKER_COMPLETION_NOT_READY = "completion_not_ready"
HANDOFF_BLOCKER_CONTRACT_MISSING = "contract_missing"
HANDOFF_BLOCKER_PRESERVATION_FAILED = "preservation_failed"
HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING = SEMANTIC_EVIDENCE_MISSING
HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID = SEMANTIC_EVIDENCE_INVALID

HANDOFF_BLOCKERS: tuple[str, ...] = (
    HANDOFF_BLOCKER_COMPLETION_NOT_READY,
    HANDOFF_BLOCKER_CONTRACT_MISSING,
    HANDOFF_BLOCKER_PRESERVATION_FAILED,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING,
    HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID,
)

# ── Reason codes ──────────────────────────────────────────────────────────────
REASON_SEMANTIC_STATUS_FAILED = "semantic_status_failed"
REASON_SEMANTIC_STATUS_UNRECOGNISED = "semantic_status_unrecognised"
REASON_NO_CONTRACT = "semantic_interpretation_produced_no_contract"
REASON_PRESERVATION_FAILED = "requirement_preservation_failed"
REASON_EXPLICIT_CONSTRAINT_CONFLICT = "explicit_constraint_conflict"
REASON_CONFLICTING_OUTPUT_FORMATS = "conflicting_explicit_output_formats"
REASON_UNRESOLVED_MEANING = "unresolved_meaning_ambiguity"
REASON_OPERATIONAL_DETAIL_MISSING = "operational_detail_missing"
REASON_INTAKE_SUFFICIENT = "intake_semantics_sufficient"
#: The gate failed only because INPUT.1 carries one requested output and the
#: user named two shapes that compose ("as a table in markdown").  Nothing the
#: user said was lost; the contract simply has one slot for it.
REASON_OUTPUT_REPRESENTATION_LIMIT = "output_format_representation_limit"

COMPLETION_REASONS: tuple[str, ...] = (
    REASON_SEMANTIC_STATUS_FAILED,
    REASON_SEMANTIC_STATUS_UNRECOGNISED,
    REASON_NO_CONTRACT,
    REASON_PRESERVATION_FAILED,
    REASON_EXPLICIT_CONSTRAINT_CONFLICT,
    REASON_CONFLICTING_OUTPUT_FORMATS,
    REASON_UNRESOLVED_MEANING,
    REASON_OPERATIONAL_DETAIL_MISSING,
    REASON_INTAKE_SUFFICIENT,
    REASON_OUTPUT_REPRESENTATION_LIMIT,
)

# ── Clarification vocabulary ──────────────────────────────────────────────────
NEED_REPORTED_AMBIGUITY = "reported_ambiguity"
NEED_DANGLING_SUBJECT_REFERENCE = "dangling_subject_reference"
NEED_CONFLICTING_OUTPUT_FORMATS = "conflicting_output_formats"

CLARIFICATION_KINDS: tuple[str, ...] = (
    NEED_REPORTED_AMBIGUITY,
    NEED_DANGLING_SUBJECT_REFERENCE,
    NEED_CONFLICTING_OUTPUT_FORMATS,
)

# ── Goal Brief field vocabulary ───────────────────────────────────────────────
BRIEF_FIELD_WHAT = "what"
BRIEF_FIELD_WHY = "why"
BRIEF_FIELD_SCOPE = "scope"
BRIEF_FIELD_CONSTRAINTS = "constraints"
BRIEF_FIELD_STOP_CONDITIONS = "stop_conditions"
BRIEF_FIELD_VALIDATION = "validation"
BRIEF_FIELD_DESIRED_OUTPUT = "desired_output"
#: A gap the interpreter named that does not map onto a canonical brief field.
BRIEF_FIELD_UNSPECIFIED = "unspecified"

GOAL_BRIEF_FIELDS: tuple[str, ...] = (
    BRIEF_FIELD_WHAT,
    BRIEF_FIELD_WHY,
    BRIEF_FIELD_SCOPE,
    BRIEF_FIELD_CONSTRAINTS,
    BRIEF_FIELD_STOP_CONDITIONS,
    BRIEF_FIELD_VALIDATION,
    BRIEF_FIELD_DESIRED_OUTPUT,
)

MISSING_REQUIREMENT_FIELDS: tuple[str, ...] = GOAL_BRIEF_FIELDS + (BRIEF_FIELD_UNSPECIFIED,)

#: Soft fields offered as suggestions while already assisting, never as
#: blockers, and never on a task that is not broad-operational.
#:
#: ``why`` and ``desired_output`` are deliberately absent.  They are the two
#: fields that turn structured assistance into an interview, and neither of
#: them changes whether broad work can be planned safely.
_SUGGESTION_CANDIDATES: tuple[str, ...] = (
    BRIEF_FIELD_CONSTRAINTS,
    BRIEF_FIELD_VALIDATION,
    BRIEF_FIELD_STOP_CONDITIONS,
)

SEVERITY_REQUIRED = "required_before_handoff"
SEVERITY_SUGGESTED = "suggested_for_completion"
MISSING_SEVERITIES: tuple[str, ...] = (SEVERITY_REQUIRED, SEVERITY_SUGGESTED)

# ── Operational breadth ───────────────────────────────────────────────────────
#: Task types whose missing operational details materially affect downstream
#: planning.  A question, an explanation, or a bounded comparison is not here:
#: complexity is not incompleteness, and a conversational task must never be
#: pushed through a coding-project interview.
OPERATIONAL_TASK_TYPES: tuple[str, ...] = ("implementation", "debugging", "planning")

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_CLARIFICATION_NEEDS = 4
MAX_MISSING_REQUIREMENTS = 8
MAX_CONTRADICTION_REASONS = 8
MAX_DECISION_REASONS = 8
MAX_DETAIL_CHARS = 240

#: Explicit output formats that serialize a whole answer.  Asking for two of
#: these, or for one of these plus a prose-shaped format, is a conflict about
#: what the answer *is*, not about how it is decorated.
SERIALIZATION_OUTPUT_FORMATS: frozenset[str] = frozenset({"json", "yaml", "csv"})

#: Characters ignored when comparing two literals, mirroring the INPUT.1
#: preservation gate so identity means the same thing in both layers.
_IGNORED_KEY_CHARS: frozenset[str] = frozenset(" \t\n.-_/\\'\"`")


def intake_authority() -> dict[str, bool]:
    """Every authority INPUT.3 declines to hold, in every completion state.

    No completion state changes any of these.  READY does not grant authority.
    """
    return {
        "routing_authority": False,
        "execution_authority": False,
        "repository_read_authority": False,
        "repository_write_authority": False,
        "patch_authority": False,
        "validation_authority": False,
        "benchmark_authority": False,
        "work" + "er_launch_authority": False,
        "provider_selection_authority": False,
        "model_escalation_authority": False,
        "dream_authority": False,
        "project_evolution_authority": False,
        "mode_selection_authority": False,
        "human_approval_required": True,
    }


def _key(value: str) -> str:
    return "".join(char for char in value.casefold() if char not in _IGNORED_KEY_CHARS)


def _short(value: str) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= MAX_DETAIL_CHARS else text[:MAX_DETAIL_CHARS]


def _is_valid_handoff_receipt(
    semantic_status: str,
    receipt: SemanticWaiterReceipt,
) -> bool:
    """Does this existing INPUT.2 receipt attest to an accepted semantic run?

    This checks receipt coherence only; it never re-interprets the request or
    creates a second semantic verdict.  The success shapes mirror INPUT.2's
    bounded one-attempt / one-repair protocol, so a hand-built status string or
    zero-call receipt cannot impersonate evidence that the semantic stage ran.
    """
    if (
        semantic_status not in HANDOFF_VALID_SEMANTIC_STATUSES
        or receipt.final_status != semantic_status
        or not receipt.structured_output_valid
        or receipt.fallback_used
        or receipt.attempt_count < 1
        or receipt.model_call_count < 1
    ):
        return False
    if semantic_status == SEMANTIC_INTERPRETATION_OK:
        return (
            receipt.first_attempt_status == ATTEMPT_OK
            and receipt.attempt_count == 1
            and not receipt.repair_attempted
            and receipt.repair_status is None
        )
    return (
        receipt.first_attempt_status == ATTEMPT_PRESERVATION_FAILED
        and receipt.attempt_count == 2
        and receipt.model_call_count >= 2
        and receipt.repair_attempted
        and receipt.repair_status == ATTEMPT_OK
    )


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ClarificationNeed:
    """One genuinely unresolved meaning question, stated deterministically.

    ``index`` is this need's position in the decision, not a per-kind counter,
    so ``need_id`` is unique and short.  Short matters: the id is the anchor a
    small local model has to copy back character for character, and every extra
    separator is one more thing for it to drop.
    """

    kind: str
    index: int
    detail: str
    subject: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in CLARIFICATION_KINDS:
            raise ValueError(f"unsupported clarification kind: {self.kind!r}")
        if self.index < 1:
            raise ValueError("clarification index is one-based")
        if not self.detail.strip():
            raise ValueError("a clarification need requires a detail")

    @property
    def need_id(self) -> str:
        return f"ambiguity_{self.index}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "kind": self.kind,
            "detail": self.detail,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class MissingRequirement:
    """One operational detail the contract does not carry.

    ``index`` is this requirement's position in the decision, so ``need_id``
    stays unique even when several unmapped gaps are reported.
    """

    field: str
    index: int
    reason: str
    severity: str = SEVERITY_REQUIRED

    def __post_init__(self) -> None:
        if self.field not in MISSING_REQUIREMENT_FIELDS:
            raise ValueError(f"unsupported brief field: {self.field!r}")
        if self.index < 1:
            raise ValueError("missing-requirement index is one-based")
        if self.severity not in MISSING_SEVERITIES:
            raise ValueError(f"unsupported severity: {self.severity!r}")
        if not self.reason.strip():
            raise ValueError("a missing requirement requires a reason")

    @property
    def need_id(self) -> str:
        return f"missing_{self.index}"

    @property
    def required(self) -> bool:
        return self.severity == SEVERITY_REQUIRED

    def as_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "field": self.field,
            "reason": self.reason,
            "severity": self.severity,
        }


@dataclass(frozen=True, slots=True)
class CompletionDecision:
    """The deterministic verdict on whether an understood order is complete.

    ``ready_for_future_handoff`` is derived from completion state, INPUT.1
    preservation, contract presence, and INPUT.2 receipt evidence rather than
    stored, so no caller — and no model — can set it independently of policy.
    A standalone INPUT.3 preview may still be ``READY`` without being eligible
    for an execution-bound future handoff.
    """

    state: str
    owner: str | None = None
    reasons: tuple[str, ...] = ()
    ambiguities: tuple[ClarificationNeed, ...] = ()
    missing_requirements: tuple[MissingRequirement, ...] = ()
    contradiction_reasons: tuple[str, ...] = ()
    semantic_status: str = SEMANTIC_STATUS_NOT_RUN
    preservation_status: str = PRESERVATION_PASSED
    #: Whether the policy was given an actual INPUT.1 TaskContract.  This is a
    #: source fact, not a mutable handoff flag; only the no-contract INPUT.2
    #: failure path sets it false.
    contract_present: bool = False
    #: The existing INPUT.2 receipt, retained as evidence rather than copied
    #: into a new semantic-truth schema.  Direct INPUT.3 preview callers may
    #: omit it.
    semantic_receipt: SemanticWaiterReceipt | None = None
    schema_version: str = COMPLETION_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.state not in COMPLETION_STATES:
            raise ValueError(f"unsupported completion state: {self.state!r}")
        if self.preservation_status not in (PRESERVATION_PASSED, PRESERVATION_FAILED):
            raise ValueError(f"unsupported preservation status: {self.preservation_status!r}")
        if not isinstance(self.contract_present, bool):
            raise TypeError("contract_present must be a bool")
        if self.semantic_receipt is not None and not isinstance(
            self.semantic_receipt, SemanticWaiterReceipt
        ):
            raise TypeError("semantic_receipt must be a SemanticWaiterReceipt or None")
        for reason in self.reasons:
            if reason not in COMPLETION_REASONS:
                raise ValueError(f"unsupported completion reason: {reason!r}")
        if len(self.ambiguities) > MAX_CLARIFICATION_NEEDS:
            raise ValueError("clarification needs exceed the supported bound")
        if len(self.missing_requirements) > MAX_MISSING_REQUIREMENTS:
            raise ValueError("missing requirements exceed the supported bound")
        if len(self.contradiction_reasons) > MAX_CONTRADICTION_REASONS:
            raise ValueError("contradiction reasons exceed the supported bound")
        if len(self.reasons) > MAX_DECISION_REASONS:
            raise ValueError("decision reasons exceed the supported bound")

        if self.state == STATE_READY:
            if self.owner is not None:
                raise ValueError("a ready intake has no unresolved owner")
            if self.ambiguities:
                raise ValueError("a ready intake may not carry unresolved ambiguities")
            if self.required_before_handoff:
                raise ValueError("a ready intake may not require anything before handoff")
            if self.contradiction_reasons:
                raise ValueError("a ready intake may not carry a contradiction")
        else:
            expected = _STATE_OWNERS[self.state]
            if self.owner != expected:
                raise ValueError(
                    f"state {self.state!r} must be owned by {expected!r}, got {self.owner!r}"
                )
            if not self.reasons:
                raise ValueError(f"state {self.state!r} must state at least one reason")

        need_ids = self.need_ids()
        if len(set(need_ids)) != len(need_ids):
            raise ValueError("every need must carry a distinct anchor id")

        if self.state == STATE_ASK_CLARIFICATION and not self.ambiguities:
            raise ValueError("asking for clarification requires at least one need")
        if self.state == STATE_BLOCKED_CONTRADICTION and not self.contradiction_reasons:
            raise ValueError("a blocked contradiction requires at least one reason")
        if self.state == STATE_GOAL_BRIEF_ASSIST and not self.required_before_handoff:
            raise ValueError(
                "goal brief assistance requires at least one field needed before handoff"
            )

    # ── derived, authority-free facts ────────────────────────────────────────
    @property
    def ready_for_future_handoff(self) -> bool:
        """Whether a future execution waiter may inspect this intake.

        This is not ``routing_allowed``, ``execution_allowed``, ``apply_allowed``
        or a selected mode.  It grants nothing.
        """
        return not self.handoff_blockers

    @property
    def semantic_evidence_status(self) -> str:
        """A deterministic summary of the existing INPUT.2 receipt.

        INPUT.3 can classify a bare contract for previews and tests, but only a
        receipt for an accepted, structured, non-fallback INPUT.2
        interpretation proves the semantic stage needed for future handoff.
        """
        receipt = self.semantic_receipt
        if receipt is None:
            return SEMANTIC_EVIDENCE_MISSING
        if _is_valid_handoff_receipt(self.semantic_status, receipt):
            return SEMANTIC_EVIDENCE_VALID
        return SEMANTIC_EVIDENCE_INVALID

    @property
    def semantic_evidence_valid(self) -> bool:
        """Whether INPUT.2 supplied valid semantic evidence for handoff."""
        return self.semantic_evidence_status == SEMANTIC_EVIDENCE_VALID

    @property
    def handoff_blockers(self) -> tuple[str, ...]:
        """Every unmet, deterministic prerequisite for future handoff.

        This remains derived rather than stored so it cannot diverge from the
        state, preservation gate, contract source fact, or receipt evidence.
        """
        blockers: list[str] = []
        if self.state != STATE_READY:
            blockers.append(HANDOFF_BLOCKER_COMPLETION_NOT_READY)
        if not self.contract_present:
            blockers.append(HANDOFF_BLOCKER_CONTRACT_MISSING)
        if self.preservation_status != PRESERVATION_PASSED:
            blockers.append(HANDOFF_BLOCKER_PRESERVATION_FAILED)
        if self.semantic_evidence_status == SEMANTIC_EVIDENCE_MISSING:
            blockers.append(HANDOFF_BLOCKER_SEMANTIC_RECEIPT_MISSING)
        elif self.semantic_evidence_status == SEMANTIC_EVIDENCE_INVALID:
            blockers.append(HANDOFF_BLOCKER_SEMANTIC_RECEIPT_INVALID)
        return tuple(blockers)

    @property
    def required_before_handoff(self) -> tuple[str, ...]:
        return tuple(item.field for item in self.missing_requirements if item.required)

    @property
    def optional_improvements(self) -> tuple[str, ...]:
        return tuple(item.field for item in self.missing_requirements if not item.required)

    @property
    def blocked_on_user(self) -> bool:
        return self.owner in (
            OWNER_USER_MEANING_AMBIGUITY,
            OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
        )

    def need_ids(self) -> tuple[str, ...]:
        """Every anchor an assistant may attach a question to."""
        return tuple(item.need_id for item in self.ambiguities) + tuple(
            item.need_id for item in self.missing_requirements
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "state": self.state,
            "owner": self.owner,
            "ready_for_future_handoff": self.ready_for_future_handoff,
            "handoff_blockers": list(self.handoff_blockers),
            "reasons": list(self.reasons),
            "ambiguities": [item.as_dict() for item in self.ambiguities],
            "missing_requirements": [item.as_dict() for item in self.missing_requirements],
            "required_before_handoff": list(self.required_before_handoff),
            "optional_improvements": list(self.optional_improvements),
            "contradiction_reasons": list(self.contradiction_reasons),
            "semantic_status": self.semantic_status,
            "semantic_evidence_status": self.semantic_evidence_status,
            "semantic_evidence_valid": self.semantic_evidence_valid,
            "preservation_status": self.preservation_status,
            "contract_present": self.contract_present,
            "authority": intake_authority(),
        }


# ── Deterministic detectors ───────────────────────────────────────────────────

def is_broad_operational_task(contract: TaskContract) -> bool:
    """Is this a task whose missing operational details matter downstream?

    Complexity is not incompleteness.  A comparative analysis, an explanation
    and a question are never broad-operational, however hard they are; a
    single-file typo fix is operational but carries its own scope.
    """
    if contract.task.type not in OPERATIONAL_TASK_TYPES:
        return False
    requirements = contract.execution_requirements
    return bool(
        requirements.multi_stage
        or requirements.repository_inspection_required
        or requirements.local_repository_required
    )


def _explicit_output_formats(contract: TaskContract) -> tuple[str, ...]:
    seen: list[str] = []
    for requested in contract.explicit_evidence.requested_outputs:
        if requested.format not in seen:
            seen.append(requested.format)
    return tuple(seen)


def _output_formats_conflict(formats: tuple[str, ...]) -> bool:
    """Do these explicitly requested formats disagree about what the answer is?

    ``markdown`` + ``table`` compose into a Markdown table.  ``json`` +
    ``markdown`` do not compose: one of them is not going to happen.
    """
    if len(formats) < 2:
        return False
    serializations = [fmt for fmt in formats if fmt in SERIALIZATION_OUTPUT_FORMATS]
    if len(serializations) >= 2:
        return True
    return bool(serializations) and len(formats) > len(serializations)


def _exclusivity_marker(contract: TaskContract, formats: tuple[str, ...]) -> str | None:
    """Return an explicit ``only``-style restriction that pins one format.

    Purely literal: the user's own restriction text must contain the user's own
    output cue text.  No language model and no language-specific grammar.
    """
    cues = [
        requested.evidence_text
        for requested in contract.explicit_evidence.requested_outputs
        if requested.format in formats and requested.evidence_text.strip()
    ]
    for constraint in contract.explicit_evidence.constraints:
        if constraint.kind != "restriction":
            continue
        haystack = constraint.text.casefold()
        for cue in cues:
            if cue.casefold() in haystack:
                return constraint.text
    return None


#: Polarity markers INPUT.1 recognises, longest first so ``must not`` is
#: stripped before ``must``.
_POLARITY_MARKERS: tuple[str, ...] = (
    "must not",
    "may not",
    "should not",
    "cannot",
    "can not",
    "do not",
    "don't",
    "never",
    "required to",
    "must",
    "shall",
)


def _constraint_residual(text: str) -> tuple[str, ...]:
    """The constraint's object, with its polarity marker removed.

    Two constraints of opposing polarity whose residuals are identical are
    saying the opposite thing about exactly the same object.
    """
    lowered = text.casefold()
    for marker in _POLARITY_MARKERS:
        if marker in lowered:
            lowered = lowered.replace(marker, " ")
    tokens = [_key(token) for token in lowered.split()]
    return tuple(token for token in tokens if token)


def detect_explicit_contradictions(contract: TaskContract) -> tuple[str, ...]:
    """Contradictions supported directly by the user's literal commitments.

    Conservative by construction: it reads only INPUT.1 explicit evidence, uses
    no model, and performs no logical inference beyond an exact residual match
    between an explicit requirement and an explicit prohibition.  When
    uncertain it finds nothing, and the uncertainty is preserved as ambiguity
    elsewhere rather than invented as conflict here.
    """
    found: list[str] = []
    constraints = contract.explicit_evidence.constraints

    prohibitions = [item for item in constraints if item.kind == "prohibition"]
    for requirement in (item for item in constraints if item.kind == "requirement"):
        residual = _constraint_residual(requirement.text)
        if not residual:
            continue
        for prohibition in prohibitions:
            if _constraint_residual(prohibition.text) != residual:
                continue
            reason = (
                f"explicit requirement {_short(requirement.text)!r} contradicts explicit "
                f"prohibition {_short(prohibition.text)!r}"
            )
            if reason not in found:
                found.append(reason)

    formats = _explicit_output_formats(contract)
    if _output_formats_conflict(formats):
        marker = _exclusivity_marker(contract, formats)
        if marker is not None:
            reason = (
                f"explicitly requested output formats {', '.join(formats)} cannot both "
                f"hold under the explicit restriction {_short(marker)!r}"
            )
            if reason not in found:
                found.append(reason)

    return tuple(found[:MAX_CONTRADICTION_REASONS])


def _preservation_is_only_output_surplus(contract: TaskContract) -> bool:
    """Did preservation fail solely because the user asked for two formats?

    INPUT.1 carries exactly one requested output, so a genuinely two-format
    order cannot survive the gate.  That failure belongs to the order, not to
    the interpreter, and must not be reported as a system fault.
    """
    missing = contract.preservation.missing_items
    if not missing:
        return False
    return all(item.kind == "requested_output" for item in missing)


def _covered(value: str, known: set[str]) -> bool:
    target = _key(value)
    if not target:
        return True
    return any(target == item or target in item or item in target for item in known)


def _dangling_relationship_subjects(contract: TaskContract) -> tuple[str, ...]:
    """Relationship subjects the contract never lists as subjects.

    A structural incoherence, not a reading of the prompt: the interpretation
    asserts a relation over something it did not name.
    """
    known = {_key(value) for value in contract.subject_values() if value.strip()}
    found: list[str] = []
    for relationship in contract.relationships:
        for value in relationship.subjects:
            if not _covered(value, known) and value not in found:
                found.append(value)
    return tuple(found)


def collect_clarification_needs(contract: TaskContract) -> tuple[ClarificationNeed, ...]:
    """Every genuinely unresolved meaning question, deterministically derived.

    Sources, in order: what the interpreter itself reported as ambiguous, a
    structural dangling reference, and an explicit output-format collision with
    no exclusivity marker to settle it.

    INPUT.3 never re-reads the raw prompt hunting for pronouns.  Deciding
    whether "it" has a referent is a *meaning* question and belongs to the
    Semantic Waiter; its report is honoured here rather than second-guessed,
    which is also what keeps this policy language-independent.
    """
    found: list[tuple[str, str, str | None]] = []

    for text in contract.ambiguities:
        if text.strip():
            found.append((NEED_REPORTED_AMBIGUITY, _short(text), None))

    for value in _dangling_relationship_subjects(contract):
        found.append(
            (
                NEED_DANGLING_SUBJECT_REFERENCE,
                f"the interpretation relates {_short(value)!r} to something else but "
                "never names it as a subject",
                _short(value),
            )
        )

    formats = _explicit_output_formats(contract)
    if _output_formats_conflict(formats) and _exclusivity_marker(contract, formats) is None:
        found.append(
            (
                NEED_CONFLICTING_OUTPUT_FORMATS,
                f"the request asks for more than one output format: {', '.join(formats)}",
                None,
            )
        )

    return tuple(
        ClarificationNeed(kind=kind, index=position, detail=detail, subject=subject)
        for position, (kind, detail, subject) in enumerate(
            found[:MAX_CLARIFICATION_NEEDS], start=1
        )
    )


def _scope_is_supplied(contract: TaskContract) -> bool:
    if contract.explicit_evidence.file_paths:
        return True
    return any(item.kind == "restriction" for item in contract.explicit_evidence.constraints)


def present_brief_fields(contract: TaskContract) -> frozenset[str]:
    """Brief fields the contract already carries a value for."""
    present = {BRIEF_FIELD_WHAT}
    if _scope_is_supplied(contract):
        present.add(BRIEF_FIELD_SCOPE)
    if contract.constraints:
        present.add(BRIEF_FIELD_CONSTRAINTS)
    if contract.requested_output is not None:
        present.add(BRIEF_FIELD_DESIRED_OUTPUT)
    return frozenset(present)


def collect_missing_requirements(contract: TaskContract) -> tuple[MissingRequirement, ...]:
    """Operational details a broad task is missing, or none at all.

    Returns an empty tuple for anything that is not broad-operational.  A
    question, an explanation, a bounded comparison and a single-file edit are
    never interviewed for validation commands, allowed files or risk tolerance.
    """
    if not is_broad_operational_task(contract):
        return ()

    present = present_brief_fields(contract)
    required: list[tuple[str, str]] = []

    if BRIEF_FIELD_SCOPE not in present:
        required.append(
            (
                BRIEF_FIELD_SCOPE,
                "the request describes broad work but names no file, module or "
                "boundary it may touch",
            )
        )

    for text in contract.missing_information:
        if text.strip():
            required.append((BRIEF_FIELD_UNSPECIFIED, _short(text)))

    required = required[:MAX_MISSING_REQUIREMENTS]
    if not required:
        # Nothing blocks handoff, so nothing is offered either: a complete
        # request is not an invitation to interview the user.
        return ()

    suggested: list[tuple[str, str]] = []
    room = MAX_MISSING_REQUIREMENTS - len(required)
    for name in _SUGGESTION_CANDIDATES:
        if len(suggested) >= room:
            break
        if name in present:
            continue
        suggested.append(
            (name, f"{name} would help a downstream planner, but does not block handoff")
        )

    entries = [(field, reason, SEVERITY_REQUIRED) for field, reason in required]
    entries += [(field, reason, SEVERITY_SUGGESTED) for field, reason in suggested]

    return tuple(
        MissingRequirement(field=field, index=position, reason=reason, severity=severity)
        for position, (field, reason, severity) in enumerate(entries, start=1)
    )


# ── Policy ────────────────────────────────────────────────────────────────────

def _resolve_semantic_status(semantic_status: str | None) -> str:
    if semantic_status is None:
        return SEMANTIC_STATUS_NOT_RUN
    if not isinstance(semantic_status, str):
        raise TypeError("semantic_status must be a string or None")
    return semantic_status


def _system_failure(
    semantic_status: str,
    preservation_status: str,
    reason: str,
    *,
    semantic_receipt: SemanticWaiterReceipt | None = None,
    contract_present: bool = True,
) -> CompletionDecision:
    return CompletionDecision(
        state=STATE_SEMANTIC_SYSTEM_FAILURE,
        owner=OWNER_SEMANTIC_SYSTEM_FAILURE,
        reasons=(reason,),
        semantic_status=semantic_status,
        preservation_status=preservation_status,
        contract_present=contract_present,
        semantic_receipt=semantic_receipt,
    )


def decide_intake_completion(
    contract: TaskContract,
    *,
    semantic_status: str | None = None,
    semantic_receipt: SemanticWaiterReceipt | None = None,
) -> CompletionDecision:
    """Classify whether an understood order is complete for intake.

    ``semantic_status`` is INPUT.2's reported status, or ``None`` when no
    semantic model ran.  Nothing here re-interprets the raw prompt, calls a
    model, or consults a confidence score.  A contract with no receipt remains
    useful for deterministic preview and inspection, but cannot become
    execution-bound handoff-ready.

    Precedence::

        1. semantic / system failure           -> SEMANTIC_SYSTEM_FAILURE
        2. explicit conflict in the user's      -> BLOCKED_CONTRADICTION
           own literal commitments              /  ASK_CLARIFICATION
        3. preservation failure                 -> SEMANTIC_SYSTEM_FAILURE
        4. unresolved meaning ambiguity         -> ASK_CLARIFICATION
        5. operational incompleteness           -> GOAL_BRIEF_ASSIST
        6. otherwise                            -> READY

    Step 2 sits above step 3 on purpose, and only reaches over it when the
    preservation failure is *entirely* explained by the user naming more than
    one output format — which INPUT.1's single-output contract cannot represent
    by construction.  Reporting a self-contradictory order as "my interpreter
    failed" would blame the system for the user's words and would leave the
    user nothing to fix.  A preservation failure with any wider footprint is a
    system failure and is reported as one.

    The same single-slot limit has a benign half.  "as a table in markdown"
    names two shapes that compose into one answer, so the gate's complaint is
    about the contract's one output field rather than about a lost commitment.
    That case continues through the policy carrying
    :data:`REASON_OUTPUT_REPRESENTATION_LIMIT`, and ``preservation_status``
    still reports ``failed`` so nothing is hidden.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("decide_intake_completion requires a TaskContract")
    if semantic_receipt is not None and not isinstance(semantic_receipt, SemanticWaiterReceipt):
        raise TypeError("semantic_receipt must be a SemanticWaiterReceipt or None")

    status = _resolve_semantic_status(semantic_status)
    preservation_status = contract.preservation.status

    # 1 ── the interpreter or its infrastructure failed.  Never the user.
    if status in FAILED_SEMANTIC_STATUSES:
        return _system_failure(
            status,
            preservation_status,
            REASON_SEMANTIC_STATUS_FAILED,
            semantic_receipt=semantic_receipt,
        )
    if status not in HEALTHY_SEMANTIC_STATUSES:
        return _system_failure(
            status,
            preservation_status,
            REASON_SEMANTIC_STATUS_UNRECOGNISED,
            semantic_receipt=semantic_receipt,
        )

    contradictions = detect_explicit_contradictions(contract)
    needs = collect_clarification_needs(contract)
    preservation_ok = contract.preservation.passed
    output_surplus_only = _preservation_is_only_output_surplus(contract)
    user_owned_preservation = preservation_ok or output_surplus_only

    # 2 ── the user's own explicit commitments disagree.
    if contradictions and user_owned_preservation:
        return CompletionDecision(
            state=STATE_BLOCKED_CONTRADICTION,
            owner=OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
            reasons=(REASON_EXPLICIT_CONSTRAINT_CONFLICT,),
            ambiguities=needs,
            contradiction_reasons=contradictions,
            semantic_status=status,
            preservation_status=preservation_status,
            contract_present=True,
            semantic_receipt=semantic_receipt,
        )

    format_conflict = any(need.kind == NEED_CONFLICTING_OUTPUT_FORMATS for need in needs)
    if format_conflict and user_owned_preservation:
        return CompletionDecision(
            state=STATE_ASK_CLARIFICATION,
            owner=OWNER_USER_MEANING_AMBIGUITY,
            reasons=(REASON_CONFLICTING_OUTPUT_FORMATS,),
            ambiguities=needs,
            semantic_status=status,
            preservation_status=preservation_status,
            contract_present=True,
            semantic_receipt=semantic_receipt,
        )

    # 3 ── the interpretation lost something the user said.
    carried: tuple[str, ...] = ()
    if not preservation_ok:
        if not output_surplus_only:
            return _system_failure(
                status,
                preservation_status,
                REASON_PRESERVATION_FAILED,
                semantic_receipt=semantic_receipt,
            )
        # Composable shapes into a one-slot field: a representation limit, not
        # a lost commitment.  Recorded rather than swallowed.
        carried = (REASON_OUTPUT_REPRESENTATION_LIMIT,)

    # 4 ── the meaning itself is unresolved.
    if needs:
        return CompletionDecision(
            state=STATE_ASK_CLARIFICATION,
            owner=OWNER_USER_MEANING_AMBIGUITY,
            reasons=carried + (REASON_UNRESOLVED_MEANING,),
            ambiguities=needs,
            semantic_status=status,
            preservation_status=preservation_status,
            contract_present=True,
            semantic_receipt=semantic_receipt,
        )

    # 5 ── meaning is clear; a broad task is missing operational detail.
    missing = collect_missing_requirements(contract)
    if any(item.required for item in missing):
        return CompletionDecision(
            state=STATE_GOAL_BRIEF_ASSIST,
            owner=OWNER_OPERATIONAL_DETAIL_MISSING,
            reasons=carried + (REASON_OPERATIONAL_DETAIL_MISSING,),
            missing_requirements=missing,
            semantic_status=status,
            preservation_status=preservation_status,
            contract_present=True,
            semantic_receipt=semantic_receipt,
        )

    # 6 ── intake information appears complete.  Derived handoff eligibility
    # additionally checks preservation and receipt evidence.  Nothing acts here.
    return CompletionDecision(
        state=STATE_READY,
        reasons=carried + (REASON_INTAKE_SUFFICIENT,),
        semantic_status=status,
        preservation_status=preservation_status,
        contract_present=True,
        semantic_receipt=semantic_receipt,
    )


def decide_from_semantic_outcome(outcome: SemanticWaiterOutcome) -> CompletionDecision:
    """Decide completion for a finished INPUT.2 run.

    A run that produced no contract at all is a system failure, stated as one.
    """
    if not isinstance(outcome, SemanticWaiterOutcome):
        raise TypeError("decide_from_semantic_outcome requires a SemanticWaiterOutcome")
    if outcome.contract is None:
        return CompletionDecision(
            state=STATE_SEMANTIC_SYSTEM_FAILURE,
            owner=OWNER_SEMANTIC_SYSTEM_FAILURE,
            reasons=(REASON_NO_CONTRACT,),
            semantic_status=outcome.status,
            preservation_status=PRESERVATION_FAILED,
            contract_present=False,
            semantic_receipt=outcome.receipt,
        )
    return decide_intake_completion(
        outcome.contract,
        semantic_status=outcome.status,
        semantic_receipt=outcome.receipt,
    )


def render_completion_decision_json(decision: CompletionDecision) -> str:
    """Render a decision as deterministic JSON."""
    return json.dumps(decision.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)
