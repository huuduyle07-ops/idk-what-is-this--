"""SYNTHESIS.1 — Task-Shaped Claim Composition Contract.

This module owns one deliberately narrow transition::

    preserved INPUT.1 task/output structure
        + explicit proposition-to-slot bindings
        + frozen CLAIM.1 assessments
        -> StructuredSynthesis

It attaches existing assessments to predefined slots.  It does not plan
propositions, inspect evidence, read source content, call a model, resolve a
conflict, select a winner, compute a score, or generate final prose.

The module is pure and import-time inert.  Its only project dependencies are
the frozen INPUT.1 and CLAIM.1 data contracts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any

from core.claim_assessment import (
    ASSESSMENT_STATUSES,
    BASIS_ANALYZER_ASSESSED,
    BASIS_NOT_ESTABLISHED,
    CLAIM_INCONSISTENCIES,
    CLAIM_MISSING_REQUIREMENTS,
    STATUS_CONFLICTING,
    STATUS_CONTRADICTED,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT,
    STATUS_SUPPORTED,
    ClaimAssessment,
)
from core.task_contract import (
    CONTRACT_SCHEMA_VERSION,
    CONSTRAINT_KINDS,
    OUTPUT_FORMATS,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    TaskContract,
)


PHASE_ID = "SYNTHESIS.1"

SPECIFICATION_SCHEMA_VERSION = "synthesis_1_specification_v1"
REQUEST_SCHEMA_VERSION = "synthesis_1_request_v1"
RESULT_SCHEMA_VERSION = "synthesis_1_structured_synthesis_v1"
PRESERVATION_SCHEMA_VERSION = "synthesis_1_preservation_v1"


# ── Bounded vocabularies ─────────────────────────────────────────────────────

OUTPUT_SHAPE_SINGLE_SLOT = "single_slot"
OUTPUT_SHAPE_COMPARISON_MATRIX = "comparison_matrix"
OUTPUT_SHAPE_ORDERED_SECTIONS = "ordered_sections"
OUTPUT_SHAPE_KEYED_REPORT = "keyed_report"
OUTPUT_SHAPE_UNSPECIFIED = "unspecified"

OUTPUT_SHAPES: tuple[str, ...] = (
    OUTPUT_SHAPE_SINGLE_SLOT,
    OUTPUT_SHAPE_COMPARISON_MATRIX,
    OUTPUT_SHAPE_ORDERED_SECTIONS,
    OUTPUT_SHAPE_KEYED_REPORT,
)

STATUS_COMPOSED = "composed"
STATUS_COMPOSED_WITH_GAPS = "composed_with_gaps"
STATUS_INCOMPLETE_SPECIFICATION = "incomplete_specification"
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

SYNTHESIS_STATUSES: tuple[str, ...] = (
    STATUS_COMPOSED,
    STATUS_COMPOSED_WITH_GAPS,
    STATUS_INCOMPLETE_SPECIFICATION,
    STATUS_INCONSISTENT_INPUT,
)

SLOT_POPULATED = "populated"
SLOT_UNRESOLVED_CONFLICT = "unresolved_conflict"
SLOT_UNRESOLVED_INSUFFICIENT = "unresolved_insufficient"
SLOT_UNRESOLVED_COVERAGE = "unresolved_coverage"
SLOT_UNRESOLVED_CURRENT_STATE = "unresolved_current_state"
SLOT_INCONSISTENT = "inconsistent"
SLOT_MISSING_CLAIM_ASSESSMENT = "missing_claim_assessment"
SLOT_PROPOSITION_BINDING_REQUIRED = "proposition_binding_required"
SLOT_NOT_APPLICABLE = "not_applicable"
SLOT_MIXED_CLAIM_STATES = "mixed_claim_states"

SLOT_STATUSES: tuple[str, ...] = (
    SLOT_POPULATED,
    SLOT_UNRESOLVED_CONFLICT,
    SLOT_UNRESOLVED_INSUFFICIENT,
    SLOT_UNRESOLVED_COVERAGE,
    SLOT_UNRESOLVED_CURRENT_STATE,
    SLOT_INCONSISTENT,
    SLOT_MISSING_CLAIM_ASSESSMENT,
    SLOT_PROPOSITION_BINDING_REQUIRED,
    SLOT_NOT_APPLICABLE,
    SLOT_MIXED_CLAIM_STATES,
)

BINDING_EXPLICIT_TASK_CONTRACT = "explicit_task_contract"
BINDING_PRESERVED_RUBRIC = "preserved_rubric_binding"
BINDING_UPSTREAM_PROPOSITION_PLAN = "upstream_proposition_plan"

BINDING_PROVENANCES: tuple[str, ...] = (
    BINDING_EXPLICIT_TASK_CONTRACT,
    BINDING_PRESERVED_RUBRIC,
    BINDING_UPSTREAM_PROPOSITION_PLAN,
)

DECISION_NONE = "none"
DECISION_COMPARATIVE_PREFERENCE = "comparative_preference"
DECISION_COMPARATIVE_SELECTION = "comparative_selection"
DECISION_RECOMMENDATION = "recommendation"

DECISION_TYPES: tuple[str, ...] = (
    DECISION_NONE,
    DECISION_COMPARATIVE_PREFERENCE,
    DECISION_COMPARATIVE_SELECTION,
    DECISION_RECOMMENDATION,
)

PRESERVATION_PASSED_STATUS = "passed"
PRESERVATION_FAILED_STATUS = "failed"
SYNTHESIS_PRESERVATION_STATUSES: tuple[str, ...] = (
    PRESERVATION_PASSED_STATUS,
    PRESERVATION_FAILED_STATUS,
)


# Reasons name performed structural work, never a conclusion about a claim.
SYNTHESIS_TASK_CONTRACT_BOUND = "SYNTHESIS_TASK_CONTRACT_BOUND"
SYNTHESIS_INPUT_PRESERVATION_BOUND = "SYNTHESIS_INPUT_PRESERVATION_BOUND"
SYNTHESIS_SPECIFICATION_BOUND = "SYNTHESIS_SPECIFICATION_BOUND"
SYNTHESIS_EXPLICIT_BINDINGS_APPLIED = "SYNTHESIS_EXPLICIT_BINDINGS_APPLIED"
SYNTHESIS_TASK_SHAPE_PRESERVED = "SYNTHESIS_TASK_SHAPE_PRESERVED"
SYNTHESIS_OUTPUT_STRUCTURE_PRESERVED = "SYNTHESIS_OUTPUT_STRUCTURE_PRESERVED"
SYNTHESIS_UNRESOLVED_STATES_PRESERVED = (
    "SYNTHESIS_UNRESOLVED_STATES_PRESERVED"
)
SYNTHESIS_NO_CLAIM_INVENTED = "SYNTHESIS_NO_CLAIM_INVENTED"
SYNTHESIS_NO_DECISION_PERFORMED = "SYNTHESIS_NO_DECISION_PERFORMED"
SYNTHESIS_NO_FINAL_RESPONSE_GENERATED = "SYNTHESIS_NO_FINAL_RESPONSE_GENERATED"

SYNTHESIS_REASONS: tuple[str, ...] = (
    SYNTHESIS_TASK_CONTRACT_BOUND,
    SYNTHESIS_INPUT_PRESERVATION_BOUND,
    SYNTHESIS_SPECIFICATION_BOUND,
    SYNTHESIS_EXPLICIT_BINDINGS_APPLIED,
    SYNTHESIS_TASK_SHAPE_PRESERVED,
    SYNTHESIS_OUTPUT_STRUCTURE_PRESERVED,
    SYNTHESIS_UNRESOLVED_STATES_PRESERVED,
    SYNTHESIS_NO_CLAIM_INVENTED,
    SYNTHESIS_NO_DECISION_PERFORMED,
    SYNTHESIS_NO_FINAL_RESPONSE_GENERATED,
)


# Fatal input inconsistencies.  A legitimate upstream inconsistent assessment
# is not in this vocabulary: it remains visible in its bound slot.
INCONSISTENT_TASK_PRESERVATION = "task_preservation_failed"
INCONSISTENT_TASK_SCHEMA = "task_contract_schema_mismatch"
INCONSISTENT_TASK_STRUCTURE_TRUNCATED = "task_structure_truncated"
INCONSISTENT_TASK_IDENTITY_AMBIGUOUS = "task_identity_ambiguous"
INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS = "task_output_format_ambiguous"
INCONSISTENT_TASK_FINGERPRINT = "task_contract_fingerprint_mismatch"
INCONSISTENT_PRESERVATION_FINGERPRINT = "preservation_fingerprint_mismatch"
INCONSISTENT_SPECIFICATION_FINGERPRINT = (
    "synthesis_specification_fingerprint_mismatch"
)
INCONSISTENT_SUBJECT_DROPPED = "synthesis_subject_dropped"
INCONSISTENT_SUBJECT_ADDED = "synthesis_subject_added"
INCONSISTENT_SUBJECT_RENAMED = "synthesis_subject_renamed"
INCONSISTENT_SUBJECT_REORDERED = "synthesis_subject_reordered"
INCONSISTENT_STRUCTURE_NARROWED = "synthesis_structure_narrowed"
INCONSISTENT_STRUCTURE_WIDENED = "synthesis_structure_widened"
INCONSISTENT_RUBRIC_CHANGED = "synthesis_rubric_changed"
INCONSISTENT_RUBRIC_REORDERED = "synthesis_rubric_reordered"
INCONSISTENT_OUTPUT_FORMAT = "synthesis_output_format_changed"
INCONSISTENT_CONSTRAINTS = "synthesis_constraints_changed"
INCONSISTENT_ASSESSMENT_REPEATED = "claim_assessment_repeated"
INCONSISTENT_ASSESSMENT_FINGERPRINT = "claim_assessment_fingerprint_mismatch"
INCONSISTENT_ASSESSMENT_PROPOSITION = "claim_assessment_proposition_mismatch"
INCONSISTENT_ASSESSMENT_UNBOUND = "unbound_claim_assessment"
INCONSISTENT_UPSTREAM_AUTHORITY = "upstream_claim_authority_asserted"
INCONSISTENT_UPSTREAM_GUARDRAIL = "upstream_claim_guardrail_violated"
INCONSISTENT_OUTPUT_PRESERVATION = "synthesis_output_preservation_failed"

SYNTHESIS_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_TASK_PRESERVATION,
    INCONSISTENT_TASK_SCHEMA,
    INCONSISTENT_TASK_STRUCTURE_TRUNCATED,
    INCONSISTENT_TASK_IDENTITY_AMBIGUOUS,
    INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS,
    INCONSISTENT_TASK_FINGERPRINT,
    INCONSISTENT_PRESERVATION_FINGERPRINT,
    INCONSISTENT_SPECIFICATION_FINGERPRINT,
    INCONSISTENT_SUBJECT_DROPPED,
    INCONSISTENT_SUBJECT_ADDED,
    INCONSISTENT_SUBJECT_RENAMED,
    INCONSISTENT_SUBJECT_REORDERED,
    INCONSISTENT_STRUCTURE_NARROWED,
    INCONSISTENT_STRUCTURE_WIDENED,
    INCONSISTENT_RUBRIC_CHANGED,
    INCONSISTENT_RUBRIC_REORDERED,
    INCONSISTENT_OUTPUT_FORMAT,
    INCONSISTENT_CONSTRAINTS,
    INCONSISTENT_ASSESSMENT_REPEATED,
    INCONSISTENT_ASSESSMENT_FINGERPRINT,
    INCONSISTENT_ASSESSMENT_PROPOSITION,
    INCONSISTENT_ASSESSMENT_UNBOUND,
    INCONSISTENT_UPSTREAM_AUTHORITY,
    INCONSISTENT_UPSTREAM_GUARDRAIL,
    INCONSISTENT_OUTPUT_PRESERVATION,
)


UNRESOLVED_SYNTHESIS_SPECIFICATION = "synthesis_specification_required"
UNRESOLVED_PROPOSITION_BINDING = "proposition_binding_required"
UNRESOLVED_CLAIM_ASSESSMENT = "claim_assessment_required"
UNRESOLVED_CONFLICT = "conflict_resolution_required"
UNRESOLVED_INSUFFICIENCY = "evidence_sufficiency_required"
UNRESOLVED_COVERAGE = "evidence_coverage_required"
UNRESOLVED_CURRENT_STATE = "current_state_establishment_required"
UNRESOLVED_UPSTREAM_INPUT = "upstream_input_correction_required"
UNRESOLVED_MIXED_CLAIMS = "mixed_claim_states_unresolved"
UNRESOLVED_DOWNSTREAM_DECISION = "downstream_decision_required"

SYNTHESIS_UNRESOLVED_REQUIREMENTS: tuple[str, ...] = (
    UNRESOLVED_SYNTHESIS_SPECIFICATION,
    UNRESOLVED_PROPOSITION_BINDING,
    UNRESOLVED_CLAIM_ASSESSMENT,
    UNRESOLVED_CONFLICT,
    UNRESOLVED_INSUFFICIENCY,
    UNRESOLVED_COVERAGE,
    UNRESOLVED_CURRENT_STATE,
    UNRESOLVED_UPSTREAM_INPUT,
    UNRESOLVED_MIXED_CLAIMS,
    UNRESOLVED_DOWNSTREAM_DECISION,
)

SLOT_UNRESOLVED_REASONS: tuple[str, ...] = (
    SLOT_PROPOSITION_BINDING_REQUIRED,
    SLOT_MISSING_CLAIM_ASSESSMENT,
    STATUS_CONFLICTING,
    STATUS_INSUFFICIENT,
    STATUS_COVERAGE_INCOMPLETE,
    STATUS_CURRENT_STATE_UNESTABLISHED,
    STATUS_CURRENT_STATE_INCONSISTENT,
    STATUS_INCONSISTENT_INPUT,
    SLOT_MIXED_CLAIM_STATES,
)


PRESERVATION_SPECIFICATION_MISSING = "synthesis_specification_missing"
PRESERVATION_TASK_BINDING_CHANGED = "task_contract_binding_changed"
PRESERVATION_INPUT_RECEIPT_CHANGED = "input_preservation_binding_changed"
PRESERVATION_SPECIFICATION_BINDING_CHANGED = "specification_binding_changed"
PRESERVATION_OUTPUT_SHAPE_CHANGED = "requested_output_shape_changed"
PRESERVATION_OUTPUT_FORMAT_CHANGED = "requested_output_format_changed"
PRESERVATION_SUBJECTS_CHANGED = "required_subjects_changed"
PRESERVATION_RUBRIC_CHANGED = "required_rubric_changed"
PRESERVATION_CONSTRAINTS_CHANGED = "required_constraints_changed"
PRESERVATION_SLOT_MISSING = "required_slot_missing"
PRESERVATION_SLOT_EXTRA = "synthesis_slot_extra"
PRESERVATION_SLOT_IDENTITY_CHANGED = "synthesis_slot_identity_changed"
PRESERVATION_CLAIM_REFERENCE_UNBOUND = "claim_reference_unbound"
PRESERVATION_CLAIM_REFERENCE_CHANGED = "claim_assessment_reference_changed"
PRESERVATION_CLAIM_INPUT_MISSING = "claim_assessment_input_missing"
PRESERVATION_REQUEST_BINDING_CHANGED = "synthesis_request_binding_changed"
PRESERVATION_RESULT_DERIVATION_CHANGED = "synthesis_result_derivation_changed"
PRESERVATION_MISSING_STATE_HIDDEN = "unresolved_slot_state_hidden"
PRESERVATION_DECISION_REQUIREMENT_CHANGED = "decision_requirement_changed"

SYNTHESIS_PRESERVATION_FAILURES: tuple[str, ...] = (
    PRESERVATION_SPECIFICATION_MISSING,
    PRESERVATION_TASK_BINDING_CHANGED,
    PRESERVATION_INPUT_RECEIPT_CHANGED,
    PRESERVATION_SPECIFICATION_BINDING_CHANGED,
    PRESERVATION_OUTPUT_SHAPE_CHANGED,
    PRESERVATION_OUTPUT_FORMAT_CHANGED,
    PRESERVATION_SUBJECTS_CHANGED,
    PRESERVATION_RUBRIC_CHANGED,
    PRESERVATION_CONSTRAINTS_CHANGED,
    PRESERVATION_SLOT_MISSING,
    PRESERVATION_SLOT_EXTRA,
    PRESERVATION_SLOT_IDENTITY_CHANGED,
    PRESERVATION_CLAIM_REFERENCE_UNBOUND,
    PRESERVATION_CLAIM_REFERENCE_CHANGED,
    PRESERVATION_CLAIM_INPUT_MISSING,
    PRESERVATION_REQUEST_BINDING_CHANGED,
    PRESERVATION_RESULT_DERIVATION_CHANGED,
    PRESERVATION_MISSING_STATE_HIDDEN,
    PRESERVATION_DECISION_REQUIREMENT_CHANGED,
)


# ── Finite bounds ─────────────────────────────────────────────────────────────

MAX_IDENTIFIER_CHARS = 160
MAX_LABEL_CHARS = 240
MAX_SUBJECT_AXES = 16
MAX_SYNTHESIS_SLOTS = 32
MAX_SYNTHESIS_CONSTRAINTS = 32
MAX_PROPOSITIONS_PER_SLOT = 64
MAX_CLAIM_BINDINGS = 512
MAX_CLAIM_ASSESSMENTS = 512
MAX_SLOT_RESULTS = 512


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _bounded_text(value: object, label: str, maximum: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains a control character")


def _bounded_tuple(values: object, maximum: int, label: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")


def _ordered_vocabulary(
    values: tuple[str, ...], vocabulary: tuple[str, ...], label: str
) -> None:
    _bounded_tuple(values, len(vocabulary), label)
    if len(set(values)) != len(values):
        raise ValueError(f"{label} values must be unique")
    position = {value: ordinal for ordinal, value in enumerate(vocabulary)}
    if any(value not in position for value in values):
        raise ValueError(f"{label} contains an unsupported value")
    if tuple(sorted(values, key=position.__getitem__)) != values:
        raise ValueError(f"{label} must use canonical vocabulary order")


def _validate_ordinals(records: tuple[Any, ...], label: str) -> None:
    for expected, record in enumerate(records, start=1):
        if record.ordinal != expected:
            raise ValueError(f"{label} ordinals must be contiguous and preserve order")


def _validate_unique(values: tuple[str, ...], label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{label} values must be unique")


_IGNORED_IDENTITY_CHARACTERS = frozenset(" \t\n.-_/\\'\"`")


def _preserved_identity_key(value: str) -> str:
    """Use INPUT.1's frozen literal identity rule; perform no semantic match."""
    return "".join(
        character
        for character in value.casefold()
        if character not in _IGNORED_IDENTITY_CHARACTERS
    )


def _ordered_codes(codes: set[str], vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in vocabulary if value in codes)


def task_contract_fingerprint(contract: TaskContract) -> str:
    if type(contract) is not TaskContract:
        raise TypeError("task_contract_fingerprint requires an exact TaskContract")
    return _fingerprint(contract.as_dict())


def task_preservation_fingerprint(contract: TaskContract) -> str:
    if type(contract) is not TaskContract:
        raise TypeError("task_preservation_fingerprint requires an exact TaskContract")
    return _fingerprint(contract.preservation.as_dict())


def _claim_identity(assessment: ClaimAssessment) -> dict[str, Any]:
    """Rebuild CLAIM.1 identity without trusting a caller serialization."""
    return {
        "schema_version": assessment.schema_version,
        "phase_id": "CLAIM.1",
        "assessment_status": assessment.assessment_status,
        "proposition_id": assessment.proposition_id,
        "proposition_sha256": assessment.proposition_sha256,
        "proposition_text": assessment.proposition_text,
        "proposition_type": assessment.proposition_type,
        "proposition_scope": assessment.proposition_scope,
        "evidence_set_fingerprint": assessment.evidence_set_fingerprint,
        "evidence_set_request_fingerprint": assessment.evidence_set_request_fingerprint,
        "request_fingerprint": assessment.request_fingerprint,
        "semantic_basis": assessment.semantic_basis,
        "assessment_basis": assessment.assessment_basis,
        "conflict_status": assessment.conflict_status,
        "role_coverage_status": assessment.role_coverage_status,
        "scope_coverage": assessment.scope_coverage,
        "negative_claim_coverage": assessment.negative_claim_coverage,
        "current_state_coverage": assessment.current_state_coverage,
        "corroboration_status": assessment.corroboration_status,
        "directional_record_refs": list(assessment.directional_record_refs),
        "non_directional_record_refs": list(assessment.non_directional_record_refs),
        "lineage_group_refs": list(assessment.lineage_group_refs),
        "missing_requirements": list(assessment.missing_requirements),
        "reasons": list(assessment.reasons),
        "inconsistencies": list(assessment.inconsistencies),
    }


def rederive_claim_assessment_fingerprint(assessment: ClaimAssessment) -> str:
    if type(assessment) is not ClaimAssessment:
        raise TypeError(
            "rederive_claim_assessment_fingerprint requires an exact ClaimAssessment"
        )
    return _fingerprint(_claim_identity(assessment))


# ── Specification records ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SynthesisSubject:
    subject_id: str
    label: str
    ordinal: int

    def __post_init__(self) -> None:
        _bounded_text(self.subject_id, "subject_id", MAX_IDENTIFIER_CHARS)
        _bounded_text(self.label, "subject label", MAX_LABEL_CHARS)
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise TypeError("subject ordinal must be an integer")
        if self.ordinal < 1:
            raise ValueError("subject ordinal must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "label": self.label,
            "ordinal": self.ordinal,
        }


@dataclass(frozen=True, slots=True)
class SynthesisConstraint:
    kind: str
    text: str
    ordinal: int

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(f"unsupported synthesis constraint kind: {self.kind!r}")
        _bounded_text(self.text, "constraint text", MAX_LABEL_CHARS)
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise TypeError("constraint ordinal must be an integer")
        if self.ordinal < 1:
            raise ValueError("constraint ordinal must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "text": self.text, "ordinal": self.ordinal}


@dataclass(frozen=True, slots=True)
class SynthesisSlot:
    """One predefined answer position, never a prose-generation instruction."""

    slot_id: str
    label: str
    ordinal: int
    required_proposition_ids: tuple[str, ...]
    required: bool = True
    subject_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_text(self.slot_id, "slot_id", MAX_IDENTIFIER_CHARS)
        _bounded_text(self.label, "slot label", MAX_LABEL_CHARS)
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise TypeError("slot ordinal must be an integer")
        if self.ordinal < 1:
            raise ValueError("slot ordinal must be positive")
        if not isinstance(self.required, bool):
            raise TypeError("slot required must be a bool")
        if self.subject_id is not None:
            _bounded_text(self.subject_id, "slot subject_id", MAX_IDENTIFIER_CHARS)
        _bounded_tuple(
            self.required_proposition_ids,
            MAX_PROPOSITIONS_PER_SLOT,
            "required proposition ids",
        )
        for proposition_id in self.required_proposition_ids:
            _bounded_text(
                proposition_id,
                "required proposition_id",
                MAX_IDENTIFIER_CHARS,
            )
        if tuple(sorted(self.required_proposition_ids)) != self.required_proposition_ids:
            raise ValueError("required proposition ids must be canonically ordered")
        _validate_unique(self.required_proposition_ids, "required proposition ids")

    def as_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "label": self.label,
            "ordinal": self.ordinal,
            "subject_id": self.subject_id,
            "required_proposition_ids": list(self.required_proposition_ids),
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class ClaimSlotBinding:
    """An exact, upstream-supplied proposition/assessment-to-slot binding."""

    slot_id: str
    proposition_id: str
    expected_assessment_fingerprint: str
    provenance: str
    subject_id: str | None = None

    def __post_init__(self) -> None:
        _bounded_text(self.slot_id, "binding slot_id", MAX_IDENTIFIER_CHARS)
        _bounded_text(
            self.proposition_id,
            "binding proposition_id",
            MAX_IDENTIFIER_CHARS,
        )
        _require_sha256(
            self.expected_assessment_fingerprint,
            "expected claim assessment fingerprint",
        )
        if self.provenance not in BINDING_PROVENANCES:
            raise ValueError(f"unsupported claim-slot provenance: {self.provenance!r}")
        if self.subject_id is not None:
            _bounded_text(self.subject_id, "binding subject_id", MAX_IDENTIFIER_CHARS)

    def as_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "subject_id": self.subject_id,
            "proposition_id": self.proposition_id,
            "expected_assessment_fingerprint": (
                self.expected_assessment_fingerprint
            ),
            "provenance": self.provenance,
        }


@dataclass(frozen=True, slots=True)
class DecisionRequirement:
    requested: bool = False
    type: str = DECISION_NONE
    provenance: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.requested, bool):
            raise TypeError("decision requested must be a bool")
        if self.type not in DECISION_TYPES:
            raise ValueError(f"unsupported decision requirement type: {self.type!r}")
        if self.requested and self.type == DECISION_NONE:
            raise ValueError("a requested decision needs a bounded decision type")
        if not self.requested and self.type != DECISION_NONE:
            raise ValueError("an unrequested decision must have type 'none'")
        if self.requested:
            if self.provenance not in BINDING_PROVENANCES:
                raise ValueError("a requested decision states bounded provenance")
        elif self.provenance is not None:
            raise ValueError("an unrequested decision has no provenance")

    @property
    def decision_performed(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested,
            "type": self.type,
            "provenance": self.provenance,
            "decision_performed": self.decision_performed,
        }


@dataclass(frozen=True, slots=True)
class SynthesisSpecification:
    """The authoritative output skeleton and explicit claim bindings."""

    task_contract_fingerprint: str
    preservation_fingerprint: str
    output_shape: str
    preserved_output_format: str | None
    ordered_subjects: tuple[SynthesisSubject, ...]
    ordered_slots: tuple[SynthesisSlot, ...]
    constraints: tuple[SynthesisConstraint, ...]
    claim_bindings: tuple[ClaimSlotBinding, ...]
    decision_requirement: DecisionRequirement = field(default_factory=DecisionRequirement)
    schema_version: str = SPECIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _require_sha256(self.preservation_fingerprint, "preservation fingerprint")
        if self.output_shape not in OUTPUT_SHAPES:
            raise ValueError(f"unsupported synthesis output shape: {self.output_shape!r}")
        if (
            self.preserved_output_format is not None
            and self.preserved_output_format not in OUTPUT_FORMATS
        ):
            raise ValueError("unsupported preserved output format")
        _bounded_tuple(self.ordered_subjects, MAX_SUBJECT_AXES, "subject axes")
        _bounded_tuple(self.ordered_slots, MAX_SYNTHESIS_SLOTS, "synthesis slots")
        _bounded_tuple(
            self.constraints,
            MAX_SYNTHESIS_CONSTRAINTS,
            "synthesis constraints",
        )
        _bounded_tuple(self.claim_bindings, MAX_CLAIM_BINDINGS, "claim bindings")
        if not all(type(item) is SynthesisSubject for item in self.ordered_subjects):
            raise TypeError("ordered_subjects must contain SynthesisSubject records")
        if not all(type(item) is SynthesisSlot for item in self.ordered_slots):
            raise TypeError("ordered_slots must contain SynthesisSlot records")
        if not all(type(item) is SynthesisConstraint for item in self.constraints):
            raise TypeError("constraints must contain SynthesisConstraint records")
        if not all(type(item) is ClaimSlotBinding for item in self.claim_bindings):
            raise TypeError("claim_bindings must contain ClaimSlotBinding records")
        if type(self.decision_requirement) is not DecisionRequirement:
            raise TypeError("decision_requirement must be a DecisionRequirement")
        _validate_ordinals(self.ordered_subjects, "subject")
        _validate_ordinals(self.ordered_slots, "slot")
        _validate_ordinals(self.constraints, "constraint")
        _validate_unique(
            tuple(item.subject_id for item in self.ordered_subjects),
            "subject_id",
        )
        _validate_unique(
            tuple(item.label for item in self.ordered_subjects),
            "subject label",
        )
        _validate_unique(
            tuple(
                _preserved_identity_key(item.label)
                for item in self.ordered_subjects
            ),
            "normalized subject identity",
        )
        _validate_unique(
            tuple(item.slot_id for item in self.ordered_slots),
            "slot_id",
        )
        _validate_unique(
            tuple(item.label for item in self.ordered_slots),
            "slot label",
        )

        if not self.ordered_slots:
            raise ValueError("a synthesis specification needs at least one slot")
        if self.output_shape == OUTPUT_SHAPE_SINGLE_SLOT and self.ordered_slots[1:]:
            raise ValueError("single_slot output contains exactly one slot")
        if (
            self.output_shape == OUTPUT_SHAPE_COMPARISON_MATRIX
            and not self.ordered_subjects[1:]
        ):
            raise ValueError("a comparison matrix needs at least two subjects")

        slot_by_id = {item.slot_id: item for item in self.ordered_slots}
        subject_ids = {item.subject_id for item in self.ordered_subjects}
        for slot in self.ordered_slots:
            if self.output_shape == OUTPUT_SHAPE_COMPARISON_MATRIX:
                if slot.subject_id is not None:
                    raise ValueError("matrix row slots do not bind one subject")
            elif slot.subject_id is not None and slot.subject_id not in subject_ids:
                raise ValueError("a slot names an unknown subject")
        binding_keys: list[tuple[str, str | None, str]] = []
        for binding in self.claim_bindings:
            slot = slot_by_id.get(binding.slot_id)
            if slot is None:
                raise ValueError("a claim binding names an unknown slot")
            if binding.proposition_id not in slot.required_proposition_ids:
                raise ValueError(
                    "a claim binding proposition must be declared by its slot"
                )
            if self.output_shape == OUTPUT_SHAPE_COMPARISON_MATRIX:
                if binding.subject_id not in subject_ids:
                    raise ValueError("a matrix binding names an unknown subject")
            else:
                if binding.subject_id != slot.subject_id:
                    raise ValueError(
                        "a non-matrix binding uses its slot's exact subject binding"
                    )
            binding_keys.append(
                (binding.slot_id, binding.subject_id, binding.proposition_id)
            )
        if len(set(binding_keys)) != len(binding_keys):
            raise ValueError("a claim-slot-subject binding appears exactly once")
        if self.schema_version != SPECIFICATION_SCHEMA_VERSION:
            raise ValueError("unsupported synthesis specification schema version")

    def _binding_sort_key(
        self, binding: ClaimSlotBinding
    ) -> tuple[int, int, str, str]:
        slot_ordinals = {item.slot_id: item.ordinal for item in self.ordered_slots}
        subject_ordinals = {
            item.subject_id: item.ordinal for item in self.ordered_subjects
        }
        return (
            slot_ordinals[binding.slot_id],
            subject_ordinals.get(binding.subject_id, 0),
            binding.proposition_id,
            binding.expected_assessment_fingerprint,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "preservation_fingerprint": self.preservation_fingerprint,
            "output_shape": self.output_shape,
            "preserved_output_format": self.preserved_output_format,
            "ordered_subjects": [item.as_dict() for item in self.ordered_subjects],
            "ordered_slots": [item.as_dict() for item in self.ordered_slots],
            "constraints": [item.as_dict() for item in self.constraints],
            "claim_bindings": [
                item.as_dict()
                for item in sorted(self.claim_bindings, key=self._binding_sort_key)
            ],
            "decision_requirement": self.decision_requirement.as_dict(),
            "proposition_planning_performed": False,
            "prose_generation_instructions_supplied": False,
        }


def synthesis_specification_fingerprint(
    specification: SynthesisSpecification,
) -> str:
    if type(specification) is not SynthesisSpecification:
        raise TypeError(
            "synthesis_specification_fingerprint requires a SynthesisSpecification"
        )
    return _fingerprint(specification.as_dict())


@dataclass(frozen=True, slots=True)
class SynthesisRequest:
    task_contract: TaskContract
    specification: SynthesisSpecification | None
    claim_assessments: tuple[ClaimAssessment, ...]
    expected_synthesis_specification_fingerprint: str | None
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.task_contract) is not TaskContract:
            raise TypeError("a synthesis request requires an exact TaskContract")
        if self.specification is not None and type(
            self.specification
        ) is not SynthesisSpecification:
            raise TypeError("specification must be a SynthesisSpecification or None")
        _bounded_tuple(
            self.claim_assessments,
            MAX_CLAIM_ASSESSMENTS,
            "claim assessments",
        )
        if not all(type(item) is ClaimAssessment for item in self.claim_assessments):
            raise TypeError("claim_assessments must contain exact ClaimAssessment records")
        if self.specification is None:
            if self.expected_synthesis_specification_fingerprint is not None:
                raise ValueError("a missing specification has no expected fingerprint")
        else:
            _require_sha256(
                self.expected_synthesis_specification_fingerprint,
                "expected synthesis specification fingerprint",
            )
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported synthesis request schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_contract_fingerprint": task_contract_fingerprint(
                self.task_contract
            ),
            "preservation_fingerprint": task_preservation_fingerprint(
                self.task_contract
            ),
            "synthesis_specification_fingerprint": (
                None
                if self.specification is None
                else synthesis_specification_fingerprint(self.specification)
            ),
            "expected_synthesis_specification_fingerprint": (
                self.expected_synthesis_specification_fingerprint
            ),
            "claim_assessment_fingerprints": sorted(
                rederive_claim_assessment_fingerprint(item)
                for item in self.claim_assessments
            ),
            "source_content_supplied": False,
            "additional_propositions_supplied": False,
        }


def synthesis_request_fingerprint(request: SynthesisRequest) -> str:
    if type(request) is not SynthesisRequest:
        raise TypeError("synthesis_request_fingerprint requires a SynthesisRequest")
    return _fingerprint(request.as_dict())


# ── Result records ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ClaimAssessmentReference:
    assessment_fingerprint: str
    proposition_id: str
    proposition_sha256: str
    assessment_status: str
    semantic_basis: str
    missing_requirements: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_sha256(self.assessment_fingerprint, "claim assessment fingerprint")
        _bounded_text(
            self.proposition_id,
            "claim reference proposition_id",
            MAX_IDENTIFIER_CHARS,
        )
        _require_sha256(self.proposition_sha256, "claim proposition fingerprint")
        if self.assessment_status not in ASSESSMENT_STATUSES:
            raise ValueError("unsupported referenced claim status")
        if self.semantic_basis not in (
            BASIS_ANALYZER_ASSESSED,
            BASIS_NOT_ESTABLISHED,
        ):
            raise ValueError("unsupported referenced semantic basis")
        _ordered_vocabulary(
            self.missing_requirements,
            CLAIM_MISSING_REQUIREMENTS,
            "claim reference missing requirements",
        )
        _ordered_vocabulary(
            self.inconsistencies,
            CLAIM_INCONSISTENCIES,
            "claim reference inconsistencies",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "assessment_fingerprint": self.assessment_fingerprint,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "assessment_status": self.assessment_status,
            "semantic_basis": self.semantic_basis,
            "missing_requirements": list(self.missing_requirements),
            "inconsistencies": list(self.inconsistencies),
        }


@dataclass(frozen=True, slots=True)
class SynthesisSlotResult:
    slot_id: str
    label: str
    ordinal: int
    subject_id: str | None
    subject_label: str | None
    subject_ordinal: int | None
    claim_assessment_refs: tuple[ClaimAssessmentReference, ...]
    missing_proposition_ids: tuple[str, ...]
    slot_status: str
    claim_statuses: tuple[str, ...]
    unresolved_reasons: tuple[str, ...]
    semantic_basis: str
    binding_provenances: tuple[str, ...]

    def __post_init__(self) -> None:
        _bounded_text(self.slot_id, "result slot_id", MAX_IDENTIFIER_CHARS)
        _bounded_text(self.label, "result slot label", MAX_LABEL_CHARS)
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise TypeError("result slot ordinal must be an integer")
        if self.ordinal < 1:
            raise ValueError("result slot ordinal must be positive")
        if self.subject_id is None:
            if self.subject_label is not None or self.subject_ordinal is not None:
                raise ValueError("an unbound slot has no subject metadata")
        else:
            _bounded_text(self.subject_id, "result subject_id", MAX_IDENTIFIER_CHARS)
            _bounded_text(self.subject_label, "result subject label", MAX_LABEL_CHARS)
            if not isinstance(self.subject_ordinal, int) or isinstance(
                self.subject_ordinal, bool
            ):
                raise TypeError("result subject ordinal must be an integer")
            if self.subject_ordinal < 1:
                raise ValueError("result subject ordinal must be positive")
        _bounded_tuple(
            self.claim_assessment_refs,
            MAX_PROPOSITIONS_PER_SLOT,
            "claim assessment refs",
        )
        if not all(
            type(item) is ClaimAssessmentReference
            for item in self.claim_assessment_refs
        ):
            raise TypeError(
                "claim_assessment_refs must contain ClaimAssessmentReference records"
            )
        reference_keys = tuple(
            (item.proposition_id, item.assessment_fingerprint)
            for item in self.claim_assessment_refs
        )
        if tuple(sorted(reference_keys)) != reference_keys:
            raise ValueError("claim assessment references must be canonically ordered")
        _validate_unique(
            tuple(item.assessment_fingerprint for item in self.claim_assessment_refs),
            "claim assessment reference",
        )
        _bounded_tuple(
            self.missing_proposition_ids,
            MAX_PROPOSITIONS_PER_SLOT,
            "missing proposition ids",
        )
        if tuple(sorted(self.missing_proposition_ids)) != self.missing_proposition_ids:
            raise ValueError("missing proposition ids must be canonically ordered")
        _validate_unique(self.missing_proposition_ids, "missing proposition ids")
        if self.slot_status not in SLOT_STATUSES:
            raise ValueError(f"unsupported synthesis slot status: {self.slot_status!r}")
        _bounded_tuple(
            self.claim_statuses,
            MAX_PROPOSITIONS_PER_SLOT,
            "claim statuses",
        )
        if self.claim_statuses != tuple(
            item.assessment_status for item in self.claim_assessment_refs
        ):
            raise ValueError("claim statuses mirror the ordered assessment references")
        _ordered_vocabulary(
            self.unresolved_reasons,
            SLOT_UNRESOLVED_REASONS,
            "slot unresolved reasons",
        )
        if self.semantic_basis not in (
            BASIS_ANALYZER_ASSESSED,
            BASIS_NOT_ESTABLISHED,
        ):
            raise ValueError("unsupported slot semantic basis")
        _ordered_vocabulary(
            self.binding_provenances,
            BINDING_PROVENANCES,
            "binding provenances",
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "label": self.label,
            "ordinal": self.ordinal,
            "subject_binding": (
                None
                if self.subject_id is None
                else {
                    "subject_id": self.subject_id,
                    "label": self.subject_label,
                    "ordinal": self.subject_ordinal,
                }
            ),
            "claim_assessment_refs": [
                item.as_dict() for item in self.claim_assessment_refs
            ],
            "missing_proposition_ids": list(self.missing_proposition_ids),
            "slot_status": self.slot_status,
            "claim_statuses": list(self.claim_statuses),
            "unresolved_reasons": list(self.unresolved_reasons),
            "semantic_basis": self.semantic_basis,
            "binding_provenances": list(self.binding_provenances),
        }


@dataclass(frozen=True, slots=True)
class SynthesisPreservationReport:
    status: str
    result_identity_fingerprint: str
    failures: tuple[str, ...] = ()
    schema_version: str = PRESERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in SYNTHESIS_PRESERVATION_STATUSES:
            raise ValueError("unsupported synthesis preservation status")
        _require_sha256(
            self.result_identity_fingerprint,
            "preserved synthesis result identity fingerprint",
        )
        _ordered_vocabulary(
            self.failures,
            SYNTHESIS_PRESERVATION_FAILURES,
            "synthesis preservation failures",
        )
        if self.status == PRESERVATION_PASSED_STATUS and self.failures:
            raise ValueError("a passed synthesis preservation report has no failures")
        if self.status == PRESERVATION_FAILED_STATUS and not self.failures:
            raise ValueError("a failed synthesis preservation report states a failure")
        if self.schema_version != PRESERVATION_SCHEMA_VERSION:
            raise ValueError("unsupported synthesis preservation schema version")

    @property
    def passed(self) -> bool:
        return self.status == PRESERVATION_PASSED_STATUS

    @property
    def preservation_fingerprint(self) -> str:
        return _fingerprint(self._identity())

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "result_identity_fingerprint": self.result_identity_fingerprint,
            "failures": list(self.failures),
        }

    def as_dict(self) -> dict[str, Any]:
        payload = self._identity()
        payload["preservation_fingerprint"] = self.preservation_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class StructuredSynthesis:
    status: str
    task_contract_fingerprint: str
    preservation_fingerprint: str
    synthesis_specification_fingerprint: str | None
    request_fingerprint: str
    output_shape: str
    preserved_output_format: str | None
    ordered_subjects: tuple[SynthesisSubject, ...]
    ordered_slots: tuple[SynthesisSlot, ...]
    preserved_constraints: tuple[SynthesisConstraint, ...]
    slot_results: tuple[SynthesisSlotResult, ...]
    decision_requirement: DecisionRequirement
    unresolved_requirements: tuple[str, ...]
    reasons: tuple[str, ...]
    inconsistencies: tuple[str, ...]
    semantic_basis: str
    preservation: SynthesisPreservationReport | None = None
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in SYNTHESIS_STATUSES:
            raise ValueError(f"unsupported structured synthesis status: {self.status!r}")
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _require_sha256(self.preservation_fingerprint, "preservation fingerprint")
        _require_sha256(
            self.synthesis_specification_fingerprint,
            "synthesis specification fingerprint",
            optional=True,
        )
        _require_sha256(self.request_fingerprint, "synthesis request fingerprint")
        if self.output_shape not in (*OUTPUT_SHAPES, OUTPUT_SHAPE_UNSPECIFIED):
            raise ValueError("unsupported structured synthesis output shape")
        if (
            self.preserved_output_format is not None
            and self.preserved_output_format not in OUTPUT_FORMATS
        ):
            raise ValueError("unsupported structured synthesis output format")
        _bounded_tuple(self.ordered_subjects, MAX_SUBJECT_AXES, "result subjects")
        _bounded_tuple(self.ordered_slots, MAX_SYNTHESIS_SLOTS, "result slots")
        _bounded_tuple(
            self.preserved_constraints,
            MAX_SYNTHESIS_CONSTRAINTS,
            "result constraints",
        )
        _bounded_tuple(self.slot_results, MAX_SLOT_RESULTS, "slot results")
        if not all(type(item) is SynthesisSubject for item in self.ordered_subjects):
            raise TypeError("result subjects must be SynthesisSubject records")
        if not all(type(item) is SynthesisSlot for item in self.ordered_slots):
            raise TypeError("result slots must be SynthesisSlot records")
        if not all(
            type(item) is SynthesisConstraint for item in self.preserved_constraints
        ):
            raise TypeError("result constraints must be SynthesisConstraint records")
        if not all(type(item) is SynthesisSlotResult for item in self.slot_results):
            raise TypeError("slot_results must contain SynthesisSlotResult records")
        if type(self.decision_requirement) is not DecisionRequirement:
            raise TypeError("result decision_requirement must be a DecisionRequirement")
        _ordered_vocabulary(
            self.unresolved_requirements,
            SYNTHESIS_UNRESOLVED_REQUIREMENTS,
            "unresolved requirements",
        )
        _ordered_vocabulary(self.reasons, SYNTHESIS_REASONS, "synthesis reasons")
        _ordered_vocabulary(
            self.inconsistencies,
            SYNTHESIS_INCONSISTENCIES,
            "synthesis inconsistencies",
        )
        if self.semantic_basis not in (
            BASIS_ANALYZER_ASSESSED,
            BASIS_NOT_ESTABLISHED,
        ):
            raise ValueError("aggregation may not upgrade semantic basis")
        if self.preservation is not None and type(
            self.preservation
        ) is not SynthesisPreservationReport:
            raise TypeError("preservation must be a SynthesisPreservationReport or None")
        if self.status == STATUS_INCONSISTENT_INPUT and not self.inconsistencies:
            raise ValueError("inconsistent synthesis input states an inconsistency")
        if self.status == STATUS_INCOMPLETE_SPECIFICATION and not any(
            item
            in {
                UNRESOLVED_SYNTHESIS_SPECIFICATION,
                UNRESOLVED_PROPOSITION_BINDING,
            }
            for item in self.unresolved_requirements
        ):
            raise ValueError("incomplete specification states the missing dependency")
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported structured synthesis schema version")

    @property
    def preservation_current(self) -> bool:
        return (
            self.preservation is not None
            and self.preservation.passed
            and self.preservation.result_identity_fingerprint
            == _result_identity_before_preservation(self)
        )

    @property
    def structured_synthesis_authority(self) -> bool:
        return (
            self.status in {STATUS_COMPOSED, STATUS_COMPOSED_WITH_GAPS}
            and self.preservation_current
        )

    @property
    def final_response_authority(self) -> bool:
        return False

    @property
    def final_claim_authority(self) -> bool:
        return False

    @property
    def decision_authority(self) -> bool:
        return False

    @property
    def recommendation_authority(self) -> bool:
        return False

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "preservation_fingerprint": self.preservation_fingerprint,
            "synthesis_specification_fingerprint": (
                self.synthesis_specification_fingerprint
            ),
            "request_fingerprint": self.request_fingerprint,
            "output_shape": self.output_shape,
            "preserved_output_format": self.preserved_output_format,
            "ordered_subjects": [item.as_dict() for item in self.ordered_subjects],
            "ordered_slots": [item.as_dict() for item in self.ordered_slots],
            "preserved_constraints": [
                item.as_dict() for item in self.preserved_constraints
            ],
            "slot_results": [item.as_dict() for item in self.slot_results],
            "decision_requirement": self.decision_requirement.as_dict(),
            "unresolved_requirements": list(self.unresolved_requirements),
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
            "semantic_basis": self.semantic_basis,
            "preservation": (
                None if self.preservation is None else self.preservation.as_dict()
            ),
        }

    @property
    def synthesis_fingerprint(self) -> str:
        return _fingerprint(self._identity())

    def as_dict(self) -> dict[str, Any]:
        payload = self._identity()
        payload["synthesis_fingerprint"] = self.synthesis_fingerprint
        payload["authority"] = synthesis_authority(
            structured_synthesis_authority=self.structured_synthesis_authority
        )
        payload["guardrails"] = synthesis_guardrails(
            claim_assessments_composed=any(
                item.claim_assessment_refs for item in self.slot_results
            ),
            task_shape_preserved=self.preservation_current,
            output_structure_preserved=self.preservation_current,
            unresolved_states_preserved=self.preservation_current,
        )
        return payload


def _result_identity_before_preservation(result: StructuredSynthesis) -> str:
    """Bind a preservation receipt to every result field except the receipt."""
    payload = result._identity()
    payload["preservation"] = None
    return _fingerprint(payload)


# ── Authority and guardrails ──────────────────────────────────────────────────

def synthesis_authority(
    *, structured_synthesis_authority: bool
) -> dict[str, bool]:
    return {
        "structured_synthesis_authority": structured_synthesis_authority,
        "final_response_authority": False,
        "final_claim_authority": False,
        "decision_authority": False,
        "recommendation_authority": False,
        "evidence_verification_authority": False,
        "evidence_acquisition_authority": False,
        "repository_read_authority": False,
        "network_authority": False,
        "model_selection_authority": False,
        "provider_selection_authority": False,
        "execution_authority": False,
        "patch_authority": False,
        "write_authority": False,
        "human_approval_required": True,
    }


def synthesis_guardrails(
    *,
    claim_assessments_composed: bool,
    task_shape_preserved: bool,
    output_structure_preserved: bool,
    unresolved_states_preserved: bool,
) -> dict[str, bool]:
    return {
        "claim_assessments_composed": claim_assessments_composed,
        "task_shape_preserved": task_shape_preserved,
        "output_structure_preserved": output_structure_preserved,
        "unresolved_states_preserved": unresolved_states_preserved,
        "model_called": False,
        "repository_read": False,
        "evidence_acquired": False,
        "evidence_reverified": False,
        "claim_invented": False,
        "claim_reinterpreted": False,
        "conflict_resolved": False,
        "decision_performed": False,
        "winner_selected": False,
        "confidence_computed": False,
        "score_computed": False,
        "final_response_generated": False,
    }


# ── Binding and preservation gates ────────────────────────────────────────────

def _authoritative_subject_labels(contract: TaskContract) -> tuple[str, ...]:
    explicit = contract.explicit_evidence.comparison_subjects()
    if explicit:
        return explicit
    explicitly_named = tuple(
        item.value
        for item in contract.subjects
        if item.provenance == PROVENANCE_EXPLICIT
    )
    return explicitly_named or contract.subject_values()


def _authoritative_rubric_labels(contract: TaskContract) -> tuple[str, ...]:
    if contract.explicit_evidence.framework is not None:
        return contract.explicit_evidence.framework.values
    if contract.user_supplied_framework is not None:
        return contract.user_supplied_framework.values
    return ()


def _authoritative_output_format(contract: TaskContract) -> str | None:
    supplied = contract.explicit_evidence.requested_outputs
    if supplied:
        return supplied[0].format
    if contract.requested_output is not None:
        return contract.requested_output.format
    return None


def _authoritative_constraints(
    contract: TaskContract,
) -> tuple[tuple[str, str], ...]:
    supplied = contract.explicit_evidence.constraints
    if supplied:
        return tuple((item.kind, item.text) for item in supplied)
    explicit = tuple(
        (item.kind, item.text)
        for item in contract.constraints
        if item.provenance == PROVENANCE_EXPLICIT
    )
    return explicit or tuple((item.kind, item.text) for item in contract.constraints)


def _task_contract_inconsistencies(contract: TaskContract) -> set[str]:
    """Re-derive fatal INPUT.1 validity without needing a synthesis spec."""
    inconsistencies: set[str] = set()
    if contract.preservation.status != PRESERVATION_PASSED:
        inconsistencies.add(INCONSISTENT_TASK_PRESERVATION)
    if contract.schema_version != CONTRACT_SCHEMA_VERSION:
        inconsistencies.add(INCONSISTENT_TASK_SCHEMA)
    if contract.explicit_evidence.truncated_fields:
        inconsistencies.add(INCONSISTENT_TASK_STRUCTURE_TRUNCATED)

    subject_keys = tuple(
        _preserved_identity_key(item) for item in _authoritative_subject_labels(contract)
    )
    if len(set(subject_keys)) != len(subject_keys):
        inconsistencies.add(INCONSISTENT_TASK_IDENTITY_AMBIGUOUS)

    explicit_output_formats = tuple(
        item.format for item in contract.explicit_evidence.requested_outputs
    )
    if len(set(explicit_output_formats)) > 1:
        inconsistencies.add(INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS)
    if (
        explicit_output_formats
        and contract.requested_output is not None
        and contract.requested_output.provenance == PROVENANCE_EXPLICIT
        and contract.requested_output.format not in set(explicit_output_formats)
    ):
        inconsistencies.add(INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS)
    return inconsistencies


def _sequence_change_codes(
    expected: tuple[str, ...], actual: tuple[str, ...], *, subject: bool
) -> set[str]:
    if expected == actual:
        return set()
    expected_set = set(expected)
    actual_set = set(actual)
    missing = expected_set - actual_set
    extra = actual_set - expected_set
    if subject:
        if missing and extra:
            return {INCONSISTENT_SUBJECT_RENAMED}
        if missing:
            return {INCONSISTENT_SUBJECT_DROPPED}
        if extra:
            return {INCONSISTENT_SUBJECT_ADDED}
        return {INCONSISTENT_SUBJECT_REORDERED}
    if missing and extra:
        return {INCONSISTENT_RUBRIC_CHANGED}
    if missing:
        return {INCONSISTENT_STRUCTURE_NARROWED}
    if extra:
        return {INCONSISTENT_STRUCTURE_WIDENED}
    return {INCONSISTENT_RUBRIC_REORDERED}


def _contract_specification_inconsistencies(
    contract: TaskContract, specification: SynthesisSpecification
) -> set[str]:
    inconsistencies = _task_contract_inconsistencies(contract)
    actual_task_fingerprint = task_contract_fingerprint(contract)
    actual_preservation_fingerprint = task_preservation_fingerprint(contract)
    if specification.task_contract_fingerprint != actual_task_fingerprint:
        inconsistencies.add(INCONSISTENT_TASK_FINGERPRINT)
    if specification.preservation_fingerprint != actual_preservation_fingerprint:
        inconsistencies.add(INCONSISTENT_PRESERVATION_FINGERPRINT)

    expected_subjects = _authoritative_subject_labels(contract)
    actual_subjects = tuple(item.label for item in specification.ordered_subjects)
    inconsistencies.update(
        _sequence_change_codes(expected_subjects, actual_subjects, subject=True)
    )

    expected_rubric = _authoritative_rubric_labels(contract)
    if expected_rubric:
        actual_rubric = tuple(item.label for item in specification.ordered_slots)
        inconsistencies.update(
            _sequence_change_codes(expected_rubric, actual_rubric, subject=False)
        )

    if specification.preserved_output_format != _authoritative_output_format(contract):
        inconsistencies.add(INCONSISTENT_OUTPUT_FORMAT)

    expected_constraints = _authoritative_constraints(contract)
    actual_constraints = tuple(
        (item.kind, item.text) for item in specification.constraints
    )
    if actual_constraints != expected_constraints:
        inconsistencies.add(INCONSISTENT_CONSTRAINTS)
    return inconsistencies


def _subject_for(
    specification: SynthesisSpecification, subject_id: str | None
) -> SynthesisSubject | None:
    if subject_id is None:
        return None
    return next(
        item for item in specification.ordered_subjects if item.subject_id == subject_id
    )


def _targets(
    specification: SynthesisSpecification,
) -> tuple[tuple[SynthesisSlot, SynthesisSubject | None], ...]:
    targets: list[tuple[SynthesisSlot, SynthesisSubject | None]] = []
    for slot in specification.ordered_slots:
        if specification.output_shape == OUTPUT_SHAPE_COMPARISON_MATRIX:
            for subject in specification.ordered_subjects:
                targets.append((slot, subject))
        else:
            targets.append((slot, _subject_for(specification, slot.subject_id)))
    return tuple(targets)


def _binding_target_key(binding: ClaimSlotBinding) -> tuple[str, str | None]:
    return (binding.slot_id, binding.subject_id)


def _target_key(
    slot: SynthesisSlot, subject: SynthesisSubject | None
) -> tuple[str, str | None]:
    return (slot.slot_id, None if subject is None else subject.subject_id)


def _bindings_by_target(
    specification: SynthesisSpecification,
) -> dict[tuple[str, str | None], tuple[ClaimSlotBinding, ...]]:
    collected: dict[tuple[str, str | None], list[ClaimSlotBinding]] = {}
    for binding in specification.claim_bindings:
        collected.setdefault(_binding_target_key(binding), []).append(binding)
    return {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    item.proposition_id,
                    item.expected_assessment_fingerprint,
                ),
            )
        )
        for key, values in collected.items()
    }


def _specification_gap_targets(
    specification: SynthesisSpecification,
) -> set[tuple[str, str | None]]:
    bindings = _bindings_by_target(specification)
    gaps: set[tuple[str, str | None]] = set()
    for slot, subject in _targets(specification):
        key = _target_key(slot, subject)
        target_bindings = bindings.get(key, ())
        if slot.required and not target_bindings:
            gaps.add(key)
    for slot in specification.ordered_slots:
        bound_propositions = {
            binding.proposition_id
            for binding in specification.claim_bindings
            if binding.slot_id == slot.slot_id
        }
        if set(slot.required_proposition_ids) - bound_propositions:
            already_missing_target = any(
                key[0] == slot.slot_id for key in gaps
            )
            if (
                specification.output_shape == OUTPUT_SHAPE_COMPARISON_MATRIX
                and not already_missing_target
            ):
                for subject in specification.ordered_subjects:
                    gaps.add((slot.slot_id, subject.subject_id))
            elif specification.output_shape != OUTPUT_SHAPE_COMPARISON_MATRIX:
                gaps.add((slot.slot_id, slot.subject_id))
    return gaps


def _upstream_declaration_inconsistencies(
    assessment: ClaimAssessment,
) -> set[str]:
    payload = assessment.as_dict()
    authority = payload.get("authority", {})
    guardrails = payload.get("guardrails", {})
    inconsistencies: set[str] = set()
    if (
        payload.get("final_claim_authority")
        or payload.get("objective_truth_asserted")
        or payload.get("response_synthesis_performed")
        or authority.get("response_synthesis_authority")
        or authority.get("final_claim_authority")
    ):
        inconsistencies.add(INCONSISTENT_UPSTREAM_AUTHORITY)
    for key in (
        "relations_reinterpreted",
        "semantic_status_upgraded",
        "source_content_read",
        "evidence_acquired",
        "model_called",
        "majority_vote_computed",
        "confidence_computed",
        "evidence_weighted",
        "conflict_resolved",
        "objective_truth_determined",
        "final_claim_emitted",
        "final_response_synthesized",
        "multiple_propositions_combined",
    ):
        if guardrails.get(key):
            inconsistencies.add(INCONSISTENT_UPSTREAM_GUARDRAIL)
    return inconsistencies


def _assessment_gate(
    request: SynthesisRequest,
) -> tuple[set[str], dict[str, ClaimAssessment]]:
    specification = request.specification
    if specification is None:
        return set(), {}
    inconsistencies: set[str] = set()
    by_fingerprint: dict[str, ClaimAssessment] = {}
    for assessment in request.claim_assessments:
        rederived = rederive_claim_assessment_fingerprint(assessment)
        if rederived != assessment.assessment_fingerprint:
            inconsistencies.add(INCONSISTENT_ASSESSMENT_FINGERPRINT)
        if rederived in by_fingerprint:
            inconsistencies.add(INCONSISTENT_ASSESSMENT_REPEATED)
        else:
            by_fingerprint[rederived] = assessment
        inconsistencies.update(_upstream_declaration_inconsistencies(assessment))

    expected = {
        binding.expected_assessment_fingerprint
        for binding in specification.claim_bindings
    }
    for fingerprint, assessment in by_fingerprint.items():
        if fingerprint not in expected:
            inconsistencies.add(INCONSISTENT_ASSESSMENT_UNBOUND)
        for binding in specification.claim_bindings:
            if binding.expected_assessment_fingerprint != fingerprint:
                continue
            if binding.proposition_id != assessment.proposition_id:
                inconsistencies.add(INCONSISTENT_ASSESSMENT_PROPOSITION)
    return inconsistencies, by_fingerprint


def check_synthesis_preservation(
    task_contract: TaskContract,
    synthesis_specification: SynthesisSpecification | None,
    synthesis_result: StructuredSynthesis,
    claim_assessments: tuple[ClaimAssessment, ...] | None = None,
) -> SynthesisPreservationReport:
    """Re-derive that the requested structure and frozen claim refs survived.

    This gate does not decide whether a proposition or assessment is correct.
    Supplying the frozen assessments is mandatory whenever the specification
    contains claim bindings; an opaque assessment fingerprint alone cannot
    prove that a result preserved status, semantic basis, or gap metadata.
    """
    if type(task_contract) is not TaskContract:
        raise TypeError("check_synthesis_preservation requires an exact TaskContract")
    if synthesis_specification is not None and type(
        synthesis_specification
    ) is not SynthesisSpecification:
        raise TypeError("synthesis_specification has the wrong type")
    if type(synthesis_result) is not StructuredSynthesis:
        raise TypeError("synthesis_result must be a StructuredSynthesis")
    if claim_assessments is not None:
        if not isinstance(claim_assessments, tuple):
            raise TypeError("claim_assessments must be a tuple or None")
        _bounded_tuple(
            claim_assessments,
            MAX_CLAIM_ASSESSMENTS,
            "preservation claim assessments",
        )
        if not all(type(item) is ClaimAssessment for item in claim_assessments):
            raise TypeError("claim_assessments must contain exact ClaimAssessment records")

    failures: set[str] = set()
    result_identity_fingerprint = _result_identity_before_preservation(
        synthesis_result
    )
    task_issues = _task_contract_inconsistencies(task_contract)
    if task_issues & {
        INCONSISTENT_TASK_PRESERVATION,
        INCONSISTENT_TASK_SCHEMA,
        INCONSISTENT_TASK_STRUCTURE_TRUNCATED,
        INCONSISTENT_TASK_IDENTITY_AMBIGUOUS,
        INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS,
    }:
        failures.add(PRESERVATION_TASK_BINDING_CHANGED)
    if INCONSISTENT_TASK_PRESERVATION in task_issues:
        failures.add(PRESERVATION_INPUT_RECEIPT_CHANGED)

    if synthesis_specification is None:
        failures.add(PRESERVATION_SPECIFICATION_MISSING)
        return SynthesisPreservationReport(
            status=PRESERVATION_FAILED_STATUS,
            result_identity_fingerprint=result_identity_fingerprint,
            failures=_ordered_codes(failures, SYNTHESIS_PRESERVATION_FAILURES),
        )

    specification_fingerprint = synthesis_specification_fingerprint(
        synthesis_specification
    )
    if synthesis_result.task_contract_fingerprint != task_contract_fingerprint(
        task_contract
    ):
        failures.add(PRESERVATION_TASK_BINDING_CHANGED)
    if synthesis_result.preservation_fingerprint != task_preservation_fingerprint(
        task_contract
    ):
        failures.add(PRESERVATION_INPUT_RECEIPT_CHANGED)
    if (
        synthesis_result.synthesis_specification_fingerprint
        != specification_fingerprint
    ):
        failures.add(PRESERVATION_SPECIFICATION_BINDING_CHANGED)
    if synthesis_result.output_shape != synthesis_specification.output_shape:
        failures.add(PRESERVATION_OUTPUT_SHAPE_CHANGED)
    if (
        synthesis_result.preserved_output_format
        != synthesis_specification.preserved_output_format
    ):
        failures.add(PRESERVATION_OUTPUT_FORMAT_CHANGED)
    if synthesis_result.ordered_subjects != synthesis_specification.ordered_subjects:
        failures.add(PRESERVATION_SUBJECTS_CHANGED)
    if synthesis_result.ordered_slots != synthesis_specification.ordered_slots:
        failures.add(PRESERVATION_RUBRIC_CHANGED)
    if synthesis_result.preserved_constraints != synthesis_specification.constraints:
        failures.add(PRESERVATION_CONSTRAINTS_CHANGED)
    if (
        synthesis_result.decision_requirement
        != synthesis_specification.decision_requirement
    ):
        failures.add(PRESERVATION_DECISION_REQUIREMENT_CHANGED)

    contract_specification_issues = _contract_specification_inconsistencies(
        task_contract, synthesis_specification
    )
    if contract_specification_issues & {
        INCONSISTENT_TASK_PRESERVATION,
        INCONSISTENT_TASK_SCHEMA,
        INCONSISTENT_TASK_STRUCTURE_TRUNCATED,
        INCONSISTENT_TASK_IDENTITY_AMBIGUOUS,
        INCONSISTENT_TASK_OUTPUT_FORMAT_AMBIGUOUS,
        INCONSISTENT_TASK_FINGERPRINT,
    }:
        failures.add(PRESERVATION_TASK_BINDING_CHANGED)
    if INCONSISTENT_PRESERVATION_FINGERPRINT in contract_specification_issues:
        failures.add(PRESERVATION_INPUT_RECEIPT_CHANGED)
    if INCONSISTENT_OUTPUT_FORMAT in contract_specification_issues:
        failures.add(PRESERVATION_OUTPUT_FORMAT_CHANGED)
    if INCONSISTENT_CONSTRAINTS in contract_specification_issues:
        failures.add(PRESERVATION_CONSTRAINTS_CHANGED)

    supplied_assessments = claim_assessments
    has_result_references = any(
        result.claim_assessment_refs for result in synthesis_result.slot_results
    )
    if supplied_assessments is None and (
        synthesis_specification.claim_bindings or has_result_references
    ):
        failures.add(PRESERVATION_CLAIM_INPUT_MISSING)
    if supplied_assessments is None:
        supplied_assessments = ()

    preservation_request = SynthesisRequest(
        task_contract=task_contract,
        specification=synthesis_specification,
        claim_assessments=supplied_assessments,
        expected_synthesis_specification_fingerprint=specification_fingerprint,
    )
    if (
        synthesis_result.request_fingerprint
        != synthesis_request_fingerprint(preservation_request)
    ):
        failures.add(PRESERVATION_REQUEST_BINDING_CHANGED)
    assessment_issues, assessments_by_fingerprint = _assessment_gate(
        preservation_request
    )
    if INCONSISTENT_ASSESSMENT_UNBOUND in assessment_issues:
        failures.add(PRESERVATION_CLAIM_REFERENCE_UNBOUND)
    if any(
        issue != INCONSISTENT_ASSESSMENT_UNBOUND
        for issue in assessment_issues
    ):
        failures.add(PRESERVATION_CLAIM_REFERENCE_CHANGED)

    expected_targets = {
        _target_key(slot, subject): (slot, subject)
        for slot, subject in _targets(synthesis_specification)
    }
    actual_targets: dict[tuple[str, str | None], SynthesisSlotResult] = {}
    actual_target_order: list[tuple[str, str | None]] = []
    for result in synthesis_result.slot_results:
        key = (result.slot_id, result.subject_id)
        actual_target_order.append(key)
        if key in actual_targets:
            failures.add(PRESERVATION_SLOT_EXTRA)
        actual_targets[key] = result
    if set(expected_targets) - set(actual_targets):
        failures.add(PRESERVATION_SLOT_MISSING)
    if set(actual_targets) - set(expected_targets):
        failures.add(PRESERVATION_SLOT_EXTRA)
    if tuple(actual_target_order) != tuple(expected_targets):
        failures.add(PRESERVATION_SLOT_IDENTITY_CHANGED)

    bindings = _bindings_by_target(synthesis_specification)
    gap_targets = _specification_gap_targets(synthesis_specification)
    for key, (slot, subject) in expected_targets.items():
        result = actual_targets.get(key)
        if result is None:
            continue
        if (
            result.label != slot.label
            or result.ordinal != slot.ordinal
            or result.subject_label
            != (None if subject is None else subject.label)
            or result.subject_ordinal
            != (None if subject is None else subject.ordinal)
        ):
            failures.add(PRESERVATION_SLOT_IDENTITY_CHANGED)

        target_bindings = bindings.get(key, ())
        binding_by_proposition = {
            item.proposition_id: item for item in target_bindings
        }
        for reference in result.claim_assessment_refs:
            binding = binding_by_proposition.get(reference.proposition_id)
            if binding is None:
                failures.add(PRESERVATION_CLAIM_REFERENCE_UNBOUND)
            elif (
                reference.assessment_fingerprint
                != binding.expected_assessment_fingerprint
            ):
                failures.add(PRESERVATION_CLAIM_REFERENCE_CHANGED)
        represented = {
            item.proposition_id for item in result.claim_assessment_refs
        } | set(result.missing_proposition_ids)
        expected_propositions = {item.proposition_id for item in target_bindings}
        if expected_propositions - represented:
            failures.add(PRESERVATION_MISSING_STATE_HIDDEN)
        if represented - expected_propositions:
            failures.add(PRESERVATION_CLAIM_REFERENCE_UNBOUND)
        if key in gap_targets and result.slot_status not in {
            SLOT_PROPOSITION_BINDING_REQUIRED,
            SLOT_NOT_APPLICABLE,
        }:
            failures.add(PRESERVATION_MISSING_STATE_HIDDEN)
        expected_provenances = _ordered_codes(
            {item.provenance for item in target_bindings}, BINDING_PROVENANCES
        )
        if result.binding_provenances != expected_provenances:
            failures.add(PRESERVATION_CLAIM_REFERENCE_CHANGED)

    claim_inputs_available = claim_assessments is not None or not (
        synthesis_specification.claim_bindings or has_result_references
    )
    valid_derivation_inputs = (
        claim_inputs_available
        and not contract_specification_issues
        and not assessment_issues
    )
    if valid_derivation_inputs:
        expected_slot_results = _compose_slot_results(
            synthesis_specification,
            assessments_by_fingerprint,
            gap_targets,
        )
        if synthesis_result.slot_results != expected_slot_results:
            failures.add(PRESERVATION_CLAIM_REFERENCE_CHANGED)
            failures.add(PRESERVATION_RESULT_DERIVATION_CHANGED)
        expected_unresolved = _top_unresolved(
            expected_slot_results,
            synthesis_specification.decision_requirement,
            specification_missing=False,
            binding_gaps=bool(gap_targets),
        )
        if gap_targets:
            expected_top_status = STATUS_INCOMPLETE_SPECIFICATION
        elif expected_unresolved:
            expected_top_status = STATUS_COMPOSED_WITH_GAPS
        else:
            expected_top_status = STATUS_COMPOSED
        expected_semantic_basis = _semantic_basis(
            tuple(
                reference
                for slot_result in expected_slot_results
                for reference in slot_result.claim_assessment_refs
            )
        )
        expected_reasons = _result_reasons(
            specification_present=True,
            composed=expected_top_status
            in {STATUS_COMPOSED, STATUS_COMPOSED_WITH_GAPS},
            preserved=True,
        )
        if (
            synthesis_result.status != expected_top_status
            or synthesis_result.unresolved_requirements != expected_unresolved
            or synthesis_result.semantic_basis != expected_semantic_basis
            or synthesis_result.inconsistencies
            or synthesis_result.reasons != expected_reasons
        ):
            failures.add(PRESERVATION_RESULT_DERIVATION_CHANGED)

    failures.update(
        {
            PRESERVATION_SUBJECTS_CHANGED
            for item in contract_specification_issues
            if item
            in {
                INCONSISTENT_SUBJECT_DROPPED,
                INCONSISTENT_SUBJECT_ADDED,
                INCONSISTENT_SUBJECT_RENAMED,
                INCONSISTENT_SUBJECT_REORDERED,
            }
        }
    )
    failures.update(
        {
            PRESERVATION_RUBRIC_CHANGED
            for item in contract_specification_issues
            if item
            in {
                INCONSISTENT_STRUCTURE_NARROWED,
                INCONSISTENT_STRUCTURE_WIDENED,
                INCONSISTENT_RUBRIC_CHANGED,
                INCONSISTENT_RUBRIC_REORDERED,
            }
        }
    )
    if failures:
        return SynthesisPreservationReport(
            status=PRESERVATION_FAILED_STATUS,
            result_identity_fingerprint=result_identity_fingerprint,
            failures=_ordered_codes(failures, SYNTHESIS_PRESERVATION_FAILURES),
        )
    return SynthesisPreservationReport(
        status=PRESERVATION_PASSED_STATUS,
        result_identity_fingerprint=result_identity_fingerprint,
    )


# ── Deterministic composition ─────────────────────────────────────────────────

_SLOT_STATUS_BY_CLAIM_STATUS: dict[str, str] = {
    STATUS_SUPPORTED: SLOT_POPULATED,
    STATUS_CONTRADICTED: SLOT_POPULATED,
    STATUS_CONFLICTING: SLOT_UNRESOLVED_CONFLICT,
    STATUS_INSUFFICIENT: SLOT_UNRESOLVED_INSUFFICIENT,
    STATUS_COVERAGE_INCOMPLETE: SLOT_UNRESOLVED_COVERAGE,
    STATUS_CURRENT_STATE_UNESTABLISHED: SLOT_UNRESOLVED_CURRENT_STATE,
    STATUS_CURRENT_STATE_INCONSISTENT: SLOT_UNRESOLVED_CURRENT_STATE,
    STATUS_INCONSISTENT_INPUT: SLOT_INCONSISTENT,
}


def _all_same(values: tuple[str, ...]) -> bool:
    if not values:
        return True
    first = values[0]
    return all(value == first for value in values[1:])


def _reference(assessment: ClaimAssessment) -> ClaimAssessmentReference:
    return ClaimAssessmentReference(
        assessment_fingerprint=rederive_claim_assessment_fingerprint(assessment),
        proposition_id=assessment.proposition_id,
        proposition_sha256=assessment.proposition_sha256,
        assessment_status=assessment.assessment_status,
        semantic_basis=assessment.semantic_basis,
        missing_requirements=assessment.missing_requirements,
        inconsistencies=assessment.inconsistencies,
    )


def _slot_unresolved_reasons(
    references: tuple[ClaimAssessmentReference, ...],
    *,
    missing: bool,
    binding_required: bool,
) -> tuple[str, ...]:
    reasons: set[str] = set()
    if binding_required:
        reasons.add(SLOT_PROPOSITION_BINDING_REQUIRED)
    if missing:
        reasons.add(SLOT_MISSING_CLAIM_ASSESSMENT)
    for reference in references:
        if reference.assessment_status not in {
            STATUS_SUPPORTED,
            STATUS_CONTRADICTED,
        }:
            reasons.add(reference.assessment_status)
    statuses = tuple(item.assessment_status for item in references)
    if statuses and not _all_same(statuses):
        reasons.add(SLOT_MIXED_CLAIM_STATES)
    return _ordered_codes(reasons, SLOT_UNRESOLVED_REASONS)


def _slot_status(
    references: tuple[ClaimAssessmentReference, ...],
    *,
    missing: bool,
    binding_required: bool,
    applicable: bool,
) -> str:
    if binding_required:
        return SLOT_PROPOSITION_BINDING_REQUIRED
    if missing:
        return SLOT_MISSING_CLAIM_ASSESSMENT
    if not applicable:
        return SLOT_NOT_APPLICABLE
    statuses = tuple(item.assessment_status for item in references)
    if not statuses:
        return SLOT_MISSING_CLAIM_ASSESSMENT
    if not _all_same(statuses):
        return SLOT_MIXED_CLAIM_STATES
    return _SLOT_STATUS_BY_CLAIM_STATUS[statuses[0]]


def _semantic_basis(references: tuple[ClaimAssessmentReference, ...]) -> str:
    if not references or any(
        item.semantic_basis != BASIS_ANALYZER_ASSESSED for item in references
    ):
        return BASIS_NOT_ESTABLISHED
    return BASIS_ANALYZER_ASSESSED


def _compose_slot_results(
    specification: SynthesisSpecification,
    assessments: dict[str, ClaimAssessment],
    gap_targets: set[tuple[str, str | None]],
) -> tuple[SynthesisSlotResult, ...]:
    bindings = _bindings_by_target(specification)
    results: list[SynthesisSlotResult] = []
    for slot, subject in _targets(specification):
        key = _target_key(slot, subject)
        target_bindings = bindings.get(key, ())
        references: list[ClaimAssessmentReference] = []
        missing: list[str] = []
        provenances: set[str] = set()
        for binding in target_bindings:
            provenances.add(binding.provenance)
            assessment = assessments.get(binding.expected_assessment_fingerprint)
            if assessment is None:
                missing.append(binding.proposition_id)
            else:
                references.append(_reference(assessment))
        ordered_references = tuple(
            sorted(
                references,
                key=lambda item: (
                    item.proposition_id,
                    item.assessment_fingerprint,
                ),
            )
        )
        missing_ids = tuple(sorted(set(missing)))
        binding_required = key in gap_targets
        applicable = bool(target_bindings) or slot.required
        status = _slot_status(
            ordered_references,
            missing=bool(missing_ids),
            binding_required=binding_required,
            applicable=applicable,
        )
        results.append(
            SynthesisSlotResult(
                slot_id=slot.slot_id,
                label=slot.label,
                ordinal=slot.ordinal,
                subject_id=None if subject is None else subject.subject_id,
                subject_label=None if subject is None else subject.label,
                subject_ordinal=None if subject is None else subject.ordinal,
                claim_assessment_refs=ordered_references,
                missing_proposition_ids=missing_ids,
                slot_status=status,
                claim_statuses=tuple(
                    item.assessment_status for item in ordered_references
                ),
                unresolved_reasons=_slot_unresolved_reasons(
                    ordered_references,
                    missing=bool(missing_ids),
                    binding_required=binding_required,
                ),
                semantic_basis=_semantic_basis(ordered_references),
                binding_provenances=_ordered_codes(
                    provenances, BINDING_PROVENANCES
                ),
            )
        )
    return tuple(results)


def _top_unresolved(
    slot_results: tuple[SynthesisSlotResult, ...],
    decision_requirement: DecisionRequirement,
    *,
    specification_missing: bool,
    binding_gaps: bool,
) -> tuple[str, ...]:
    unresolved: set[str] = set()
    if specification_missing:
        unresolved.add(UNRESOLVED_SYNTHESIS_SPECIFICATION)
    if binding_gaps:
        unresolved.add(UNRESOLVED_PROPOSITION_BINDING)
    for result in slot_results:
        if result.slot_status == SLOT_MISSING_CLAIM_ASSESSMENT:
            unresolved.add(UNRESOLVED_CLAIM_ASSESSMENT)
        elif result.slot_status == SLOT_UNRESOLVED_CONFLICT:
            unresolved.add(UNRESOLVED_CONFLICT)
        elif result.slot_status == SLOT_UNRESOLVED_INSUFFICIENT:
            unresolved.add(UNRESOLVED_INSUFFICIENCY)
        elif result.slot_status == SLOT_UNRESOLVED_COVERAGE:
            unresolved.add(UNRESOLVED_COVERAGE)
        elif result.slot_status == SLOT_UNRESOLVED_CURRENT_STATE:
            unresolved.add(UNRESOLVED_CURRENT_STATE)
        elif result.slot_status == SLOT_INCONSISTENT:
            unresolved.add(UNRESOLVED_UPSTREAM_INPUT)
        elif result.slot_status == SLOT_MIXED_CLAIM_STATES:
            unresolved.add(UNRESOLVED_MIXED_CLAIMS)
        elif result.slot_status == SLOT_PROPOSITION_BINDING_REQUIRED:
            unresolved.add(UNRESOLVED_PROPOSITION_BINDING)
    if decision_requirement.requested:
        unresolved.add(UNRESOLVED_DOWNSTREAM_DECISION)
    return _ordered_codes(unresolved, SYNTHESIS_UNRESOLVED_REQUIREMENTS)


def _result_reasons(
    *, specification_present: bool, composed: bool, preserved: bool
) -> tuple[str, ...]:
    reasons = {
        SYNTHESIS_TASK_CONTRACT_BOUND,
        SYNTHESIS_INPUT_PRESERVATION_BOUND,
        SYNTHESIS_NO_CLAIM_INVENTED,
        SYNTHESIS_NO_DECISION_PERFORMED,
        SYNTHESIS_NO_FINAL_RESPONSE_GENERATED,
    }
    if specification_present:
        reasons.add(SYNTHESIS_SPECIFICATION_BOUND)
    if composed:
        reasons.add(SYNTHESIS_EXPLICIT_BINDINGS_APPLIED)
        reasons.add(SYNTHESIS_UNRESOLVED_STATES_PRESERVED)
    if preserved:
        reasons.add(SYNTHESIS_TASK_SHAPE_PRESERVED)
        reasons.add(SYNTHESIS_OUTPUT_STRUCTURE_PRESERVED)
    return _ordered_codes(reasons, SYNTHESIS_REASONS)


def _new_result(
    request: SynthesisRequest,
    *,
    status: str,
    slot_results: tuple[SynthesisSlotResult, ...],
    unresolved_requirements: tuple[str, ...],
    inconsistencies: tuple[str, ...],
) -> StructuredSynthesis:
    specification = request.specification
    anticipated_preservation = specification is not None and not inconsistencies
    result = StructuredSynthesis(
        status=status,
        task_contract_fingerprint=task_contract_fingerprint(request.task_contract),
        preservation_fingerprint=task_preservation_fingerprint(
            request.task_contract
        ),
        synthesis_specification_fingerprint=(
            None
            if specification is None
            else synthesis_specification_fingerprint(specification)
        ),
        request_fingerprint=synthesis_request_fingerprint(request),
        output_shape=(
            OUTPUT_SHAPE_UNSPECIFIED
            if specification is None
            else specification.output_shape
        ),
        preserved_output_format=(
            None if specification is None else specification.preserved_output_format
        ),
        ordered_subjects=(
            () if specification is None else specification.ordered_subjects
        ),
        ordered_slots=(() if specification is None else specification.ordered_slots),
        preserved_constraints=(
            () if specification is None else specification.constraints
        ),
        slot_results=slot_results,
        decision_requirement=(
            DecisionRequirement()
            if specification is None
            else specification.decision_requirement
        ),
        unresolved_requirements=unresolved_requirements,
        reasons=_result_reasons(
            specification_present=specification is not None,
            composed=status in {STATUS_COMPOSED, STATUS_COMPOSED_WITH_GAPS},
            preserved=anticipated_preservation,
        ),
        inconsistencies=inconsistencies,
        semantic_basis=_semantic_basis(
            tuple(
                reference
                for slot_result in slot_results
                for reference in slot_result.claim_assessment_refs
            )
        ),
    )
    preservation = check_synthesis_preservation(
        request.task_contract,
        specification,
        result,
        request.claim_assessments,
    )
    final_status = result.status
    final_inconsistencies = set(result.inconsistencies)
    if (
        not preservation.passed
        and result.status in {STATUS_COMPOSED, STATUS_COMPOSED_WITH_GAPS}
    ):
        final_status = STATUS_INCONSISTENT_INPUT
        final_inconsistencies.add(INCONSISTENT_OUTPUT_PRESERVATION)
    final_candidate = replace(
        result,
        status=final_status,
        inconsistencies=_ordered_codes(
            final_inconsistencies, SYNTHESIS_INCONSISTENCIES
        ),
        reasons=_result_reasons(
            specification_present=specification is not None,
            composed=final_status in {STATUS_COMPOSED, STATUS_COMPOSED_WITH_GAPS},
            preserved=preservation.passed,
        ),
        preservation=None,
    )
    final_preservation = check_synthesis_preservation(
        request.task_contract,
        specification,
        final_candidate,
        request.claim_assessments,
    )
    return replace(final_candidate, preservation=final_preservation)


def compose_structured_synthesis(request: SynthesisRequest) -> StructuredSynthesis:
    """Populate only explicitly bound slots with frozen claim references."""
    if type(request) is not SynthesisRequest:
        raise TypeError("compose_structured_synthesis requires a SynthesisRequest")

    specification = request.specification
    task_issues = _task_contract_inconsistencies(request.task_contract)
    if task_issues:
        return _new_result(
            request,
            status=STATUS_INCONSISTENT_INPUT,
            slot_results=(),
            unresolved_requirements=(),
            inconsistencies=_ordered_codes(
                task_issues, SYNTHESIS_INCONSISTENCIES
            ),
        )
    if specification is None:
        return _new_result(
            request,
            status=STATUS_INCOMPLETE_SPECIFICATION,
            slot_results=(),
            unresolved_requirements=(UNRESOLVED_SYNTHESIS_SPECIFICATION,),
            inconsistencies=(),
        )

    inconsistencies = _contract_specification_inconsistencies(
        request.task_contract, specification
    )
    actual_specification_fingerprint = synthesis_specification_fingerprint(
        specification
    )
    if (
        request.expected_synthesis_specification_fingerprint
        != actual_specification_fingerprint
    ):
        inconsistencies.add(INCONSISTENT_SPECIFICATION_FINGERPRINT)
    assessment_inconsistencies, assessments = _assessment_gate(request)
    inconsistencies.update(assessment_inconsistencies)

    if inconsistencies:
        return _new_result(
            request,
            status=STATUS_INCONSISTENT_INPUT,
            slot_results=(),
            unresolved_requirements=(),
            inconsistencies=_ordered_codes(
                inconsistencies, SYNTHESIS_INCONSISTENCIES
            ),
        )

    gap_targets = _specification_gap_targets(specification)
    slot_results = _compose_slot_results(specification, assessments, gap_targets)
    unresolved = _top_unresolved(
        slot_results,
        specification.decision_requirement,
        specification_missing=False,
        binding_gaps=bool(gap_targets),
    )
    if gap_targets:
        status = STATUS_INCOMPLETE_SPECIFICATION
    elif unresolved:
        status = STATUS_COMPOSED_WITH_GAPS
    else:
        status = STATUS_COMPOSED
    return _new_result(
        request,
        status=status,
        slot_results=slot_results,
        unresolved_requirements=unresolved,
        inconsistencies=(),
    )


def render_structured_synthesis_json(result: StructuredSynthesis) -> str:
    """Serialize structured data only; this is not RESPONSE.1."""
    if type(result) is not StructuredSynthesis:
        raise TypeError(
            "render_structured_synthesis_json requires a StructuredSynthesis"
        )
    return json.dumps(result.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "BINDING_EXPLICIT_TASK_CONTRACT",
    "BINDING_PRESERVED_RUBRIC",
    "BINDING_PROVENANCES",
    "BINDING_UPSTREAM_PROPOSITION_PLAN",
    "DECISION_COMPARATIVE_PREFERENCE",
    "DECISION_COMPARATIVE_SELECTION",
    "DECISION_NONE",
    "DECISION_RECOMMENDATION",
    "DECISION_TYPES",
    "OUTPUT_SHAPE_COMPARISON_MATRIX",
    "OUTPUT_SHAPE_KEYED_REPORT",
    "OUTPUT_SHAPE_ORDERED_SECTIONS",
    "OUTPUT_SHAPE_SINGLE_SLOT",
    "OUTPUT_SHAPES",
    "PHASE_ID",
    "SLOT_INCONSISTENT",
    "SLOT_MISSING_CLAIM_ASSESSMENT",
    "SLOT_MIXED_CLAIM_STATES",
    "SLOT_NOT_APPLICABLE",
    "SLOT_POPULATED",
    "SLOT_PROPOSITION_BINDING_REQUIRED",
    "SLOT_STATUSES",
    "SLOT_UNRESOLVED_CONFLICT",
    "SLOT_UNRESOLVED_COVERAGE",
    "SLOT_UNRESOLVED_CURRENT_STATE",
    "SLOT_UNRESOLVED_INSUFFICIENT",
    "STATUS_COMPOSED",
    "STATUS_COMPOSED_WITH_GAPS",
    "STATUS_INCOMPLETE_SPECIFICATION",
    "STATUS_INCONSISTENT_INPUT",
    "SYNTHESIS_INCONSISTENCIES",
    "SYNTHESIS_STATUSES",
    "SYNTHESIS_UNRESOLVED_REQUIREMENTS",
    "ClaimAssessmentReference",
    "ClaimSlotBinding",
    "DecisionRequirement",
    "StructuredSynthesis",
    "SynthesisConstraint",
    "SynthesisPreservationReport",
    "SynthesisRequest",
    "SynthesisSlot",
    "SynthesisSlotResult",
    "SynthesisSpecification",
    "SynthesisSubject",
    "check_synthesis_preservation",
    "compose_structured_synthesis",
    "rederive_claim_assessment_fingerprint",
    "render_structured_synthesis_json",
    "synthesis_authority",
    "synthesis_guardrails",
    "synthesis_request_fingerprint",
    "synthesis_specification_fingerprint",
    "task_contract_fingerprint",
    "task_preservation_fingerprint",
]
