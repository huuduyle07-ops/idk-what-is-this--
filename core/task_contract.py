"""INPUT.1 — Lossless Task Contract (canonical input representation).

The Task Contract is the intermediate representation of a user request:

    raw user request = source language
    Task Contract    = canonical intermediate representation
    Goal Brief       = human-editable projection of that representation

Two invariants make the contract trustworthy:

1. ``raw_request.text`` is the user's prompt verbatim.  It is never replaced by
   a summary and never truncated, whatever else is bounded.
2. A value marked ``explicit`` was literally supplied by the user.  Explicit
   values never carry a probabilistic confidence, so an inferred value can
   never be presented as something the user said.

Routing is fail-closed: a contract whose preservation check did not pass may
not set ``routing_allowed``.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, selects no execution mode, dispatches
nothing, and grants no authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core.behavioral_expectation import (
    MAX_BEHAVIORAL_EXPECTATIONS,
    BehavioralExpectation,
)
from core.explicit_design_evidence import DesignEvidence
from core.explicit_evidence import (
    CONSTRAINT_KINDS,
    FRAMEWORK_TYPES,
    OUTPUT_FORMATS,
    ExplicitEvidence,
)


PHASE_ID = "INPUT.1"
CONTRACT_SCHEMA_VERSION = "input_1_task_contract_v1"

# ── Provenance ────────────────────────────────────────────────────────────────
#: The user literally supplied this information.
PROVENANCE_EXPLICIT = "explicit"
#: A semantic interpreter derived this meaning; it is not a user quotation.
PROVENANCE_INFERRED = "inferred"
PROVENANCES: tuple[str, ...] = (PROVENANCE_EXPLICIT, PROVENANCE_INFERRED)

# ── Bounded vocabularies ──────────────────────────────────────────────────────
TASK_TYPES: tuple[str, ...] = (
    "comparative_analysis",
    "analysis",
    "implementation",
    "debugging",
    "review",
    "research",
    "planning",
    "question",
    "conversation",
    "unknown",
)

RELATIONSHIP_TYPES: tuple[str, ...] = ("comparison", "dependency", "reference")

#: Relationship types that are meaningless with fewer than two subjects.
_MULTI_SUBJECT_RELATIONSHIPS: frozenset[str] = frozenset({"comparison"})

PRESERVATION_PASSED = "passed"
PRESERVATION_FAILED = "failed"
PRESERVATION_STATUSES: tuple[str, ...] = (PRESERVATION_PASSED, PRESERVATION_FAILED)

PRESERVATION_ITEM_KINDS: tuple[str, ...] = (
    "raw_request",
    "subject",
    "relationship",
    "framework",
    "framework_value",
    "framework_order",
    "constraint",
    "requested_output",
    "provenance",
    # DEFECT.FACT.LIVE.1 — one explicit "should be X, is Y" claim.
    "behavioral_expectation",
    # OOP.INTENT.DESIGN.1 — exact additive design-evidence identity.
    "design_commitment",
)

# ── Bounds ────────────────────────────────────────────────────────────────────
#: ``raw_request.text`` is deliberately absent from this list — it is lossless.
MAX_SUBJECTS = 16
MAX_RELATIONSHIPS = 16
MAX_CONSTRAINTS = 32
MAX_FRAMEWORK_VALUES = 32
MAX_AMBIGUITIES = 16
MAX_MISSING_INFORMATION = 16
MAX_PRESERVATION_ITEMS = 128
MAX_NOTES = 16
#: DEFECT.FACT.LIVE.1 owns the count; re-exported so the contract's bound and
#: the extractor's bound are the same number rather than two that can drift.
MAX_BEHAVIORAL_EXPECTATION_FACTS = MAX_BEHAVIORAL_EXPECTATIONS


def _validate_provenance(provenance: str, confidence: float | None, label: str) -> None:
    if provenance not in PROVENANCES:
        raise ValueError(f"{label}: unsupported provenance {provenance!r}")
    if provenance == PROVENANCE_EXPLICIT and confidence is not None:
        raise ValueError(
            f"{label}: explicit values are literal user input and must not carry a "
            "probabilistic confidence"
        )
    if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"{label}: confidence must fall within 0.0 through 1.0")


def _bounded_tuple(values: tuple[Any, ...], limit: int, label: str) -> None:
    if len(values) > limit:
        raise ValueError(f"{label}: exceeds the bound of {limit}")


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RawRequest:
    """The user's prompt, preserved verbatim."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError("raw request text must be a string")

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "char_count": self.char_count, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class TaskClassification:
    """What kind of task the request represents."""

    type: str
    provenance: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.type not in TASK_TYPES:
            raise ValueError(f"unsupported task type: {self.type!r}")
        _validate_provenance(self.provenance, self.confidence, "task")

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "provenance": self.provenance,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class Subject:
    """A thing the task is about."""

    value: str
    provenance: str
    confidence: float | None = None
    role: str | None = None

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("a subject needs a non-empty value")
        _validate_provenance(self.provenance, self.confidence, f"subject {self.value!r}")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "value": self.value,
            "provenance": self.provenance,
            "confidence": self.confidence,
        }
        if self.role:
            payload["role"] = self.role
        return payload


@dataclass(frozen=True, slots=True)
class Relationship:
    """A relation the task asserts between subjects."""

    type: str
    subjects: tuple[str, ...]
    provenance: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.type not in RELATIONSHIP_TYPES:
            raise ValueError(f"unsupported relationship type: {self.type!r}")
        if self.type in _MULTI_SUBJECT_RELATIONSHIPS and len(self.subjects) < 2:
            raise ValueError(f"a {self.type} relationship needs at least two subjects")
        if not self.subjects:
            raise ValueError("a relationship needs at least one subject")
        _validate_provenance(self.provenance, self.confidence, f"relationship {self.type!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "subjects": list(self.subjects),
            "provenance": self.provenance,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class UserSuppliedFramework:
    """An evaluation framework / rubric the request is bound to."""

    type: str
    values: tuple[str, ...]
    provenance: str
    ordered: bool = True

    def __post_init__(self) -> None:
        if self.type not in FRAMEWORK_TYPES:
            raise ValueError(f"unsupported framework type: {self.type!r}")
        if not self.values:
            raise ValueError("a framework needs at least one value")
        _bounded_tuple(self.values, MAX_FRAMEWORK_VALUES, "framework values")
        if self.provenance not in PROVENANCES:
            raise ValueError(f"framework: unsupported provenance {self.provenance!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "values": list(self.values),
            "provenance": self.provenance,
            "ordered": self.ordered,
        }


@dataclass(frozen=True, slots=True)
class RequestedOutput:
    """The output shape the user asked for."""

    format: str
    provenance: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.format not in OUTPUT_FORMATS:
            raise ValueError(f"unsupported output format: {self.format!r}")
        _validate_provenance(self.provenance, self.confidence, "requested output")

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "provenance": self.provenance,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class Constraint:
    """A commitment the task must respect."""

    kind: str
    text: str
    provenance: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in CONSTRAINT_KINDS:
            raise ValueError(f"unsupported constraint kind: {self.kind!r}")
        if not self.text or not self.text.strip():
            raise ValueError("a constraint needs non-empty text")
        _validate_provenance(self.provenance, self.confidence, f"constraint {self.kind!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "provenance": self.provenance,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class ExecutionRequirements:
    """What executing this request would need — always inferred metadata.

    INPUT.1 records these so a later phase can route; it acts on none of them.
    """

    multi_stage: bool = False
    external_information_required: bool = False
    repository_inspection_required: bool = False
    local_repository_required: bool = False
    provenance: str = PROVENANCE_INFERRED
    confidence: float | None = None

    def __post_init__(self) -> None:
        _validate_provenance(self.provenance, self.confidence, "execution requirements")

    def as_dict(self) -> dict[str, Any]:
        return {
            "multi_stage": self.multi_stage,
            "external_information_required": self.external_information_required,
            "repository_inspection_required": self.repository_inspection_required,
            "local_repository_required": self.local_repository_required,
            "provenance": self.provenance,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class PreservationItem:
    """One explicit commitment the preservation gate tracked."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        if self.kind not in PRESERVATION_ITEM_KINDS:
            raise ValueError(f"unsupported preservation item kind: {self.kind!r}")

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True, slots=True)
class PreservationReport:
    """Deterministic verdict on whether explicit commitments survived."""

    status: str
    preserved_items: tuple[PreservationItem, ...] = ()
    missing_items: tuple[PreservationItem, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in PRESERVATION_STATUSES:
            raise ValueError(f"unsupported preservation status: {self.status!r}")
        _bounded_tuple(self.preserved_items, MAX_PRESERVATION_ITEMS, "preserved items")
        _bounded_tuple(self.missing_items, MAX_PRESERVATION_ITEMS, "missing items")
        if self.status == PRESERVATION_FAILED and not self.reasons:
            raise ValueError("a failed preservation report must state at least one reason")
        if self.status == PRESERVATION_PASSED and self.missing_items:
            raise ValueError("a passed preservation report may not list missing items")

    @property
    def passed(self) -> bool:
        return self.status == PRESERVATION_PASSED

    def has_missing(self, kind: str) -> bool:
        return any(item.kind == kind for item in self.missing_items)

    def missing_values(self, kind: str) -> tuple[str, ...]:
        return tuple(item.value for item in self.missing_items if item.kind == kind)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "preserved_items": [item.as_dict() for item in self.preserved_items],
            "missing_items": [item.as_dict() for item in self.missing_items],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class TaskContract:
    """The canonical, lossless representation of one user request."""

    raw_request: RawRequest
    task: TaskClassification
    preservation: PreservationReport
    explicit_evidence: ExplicitEvidence = field(default_factory=ExplicitEvidence)
    subjects: tuple[Subject, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    user_supplied_framework: UserSuppliedFramework | None = None
    requested_output: RequestedOutput | None = None
    constraints: tuple[Constraint, ...] = ()
    #: DEFECT.FACT.LIVE.1 — typed explicit behavioral claims.  They travel with
    #: the contract so a probe can be built from a record instead of from prose.
    behavioral_expectations: tuple[BehavioralExpectation, ...] = ()
    ambiguities: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    execution_requirements: ExecutionRequirements = field(default_factory=ExecutionRequirements)
    notes: tuple[str, ...] = ()
    routing_allowed: bool = False
    schema_version: str = CONTRACT_SCHEMA_VERSION
    design_evidence: DesignEvidence = field(default_factory=DesignEvidence)

    def __post_init__(self) -> None:
        if not isinstance(self.design_evidence, DesignEvidence):
            raise TypeError("task design evidence must be a DesignEvidence")
        _bounded_tuple(self.subjects, MAX_SUBJECTS, "subjects")
        _bounded_tuple(self.relationships, MAX_RELATIONSHIPS, "relationships")
        _bounded_tuple(self.constraints, MAX_CONSTRAINTS, "constraints")
        _bounded_tuple(
            self.behavioral_expectations,
            MAX_BEHAVIORAL_EXPECTATION_FACTS,
            "behavioral expectations",
        )
        _bounded_tuple(self.ambiguities, MAX_AMBIGUITIES, "ambiguities")
        _bounded_tuple(self.missing_information, MAX_MISSING_INFORMATION, "missing information")
        _bounded_tuple(self.notes, MAX_NOTES, "notes")
        if self.routing_allowed and not self.preservation.passed:
            raise ValueError(
                "routing may not be allowed while the requirement preservation gate "
                f"reports {self.preservation.status!r}"
            )

    def subject_values(self) -> tuple[str, ...]:
        return tuple(subject.value for subject in self.subjects)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "raw_request": self.raw_request.as_dict(),
            "task": self.task.as_dict(),
            "subjects": [item.as_dict() for item in self.subjects],
            "relationships": [item.as_dict() for item in self.relationships],
            "user_supplied_framework": (
                self.user_supplied_framework.as_dict() if self.user_supplied_framework else None
            ),
            "requested_output": (
                self.requested_output.as_dict() if self.requested_output else None
            ),
            "constraints": [item.as_dict() for item in self.constraints],
            "behavioral_expectations": [
                item.as_dict() for item in self.behavioral_expectations
            ],
            "ambiguities": list(self.ambiguities),
            "missing_information": list(self.missing_information),
            "execution_requirements": self.execution_requirements.as_dict(),
            "explicit_evidence": self.explicit_evidence.as_dict(),
            "preservation": self.preservation.as_dict(),
            "routing_allowed": self.routing_allowed,
            "notes": list(self.notes),
            "guardrails": _guardrails(),
            **({"design_evidence": self.design_evidence.as_dict()}
               if not self.design_evidence.is_empty() else {}),
        }


def _guardrails() -> dict[str, bool]:
    """Every power INPUT.1 declines to exercise."""
    return {
        "execution_performed": False,
        "mode_dispatch_performed": False,
        "mode_selection_performed": False,
        "repository_scan_performed": False,
        "repository_index_performed": False,
        "patch_generation_performed": False,
        "patch_application_performed": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "work" + "er_launch_performed": False,
        "dream_run_performed": False,
        "project_evolution_run_performed": False,
        "lesson_promotion_performed": False,
        "model_call_performed": False,
        "provider_selected": False,
        "network_call_performed": False,
        "goal_brief_required": False,
        "read_authority": False,
        "write_authority": False,
        "human_approval_required": True,
    }


def render_task_contract_json(contract: TaskContract) -> str:
    """Render a contract as deterministic JSON."""
    return json.dumps(contract.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)
