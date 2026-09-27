"""WAITER.1 — deterministic Capability Requirement derivation.

Task Shape says what the order *is*.  Capability Requirements answer the only
question a workflow router actually needs:

    what must a workflow be able to do in order to take this order?

    TaskShape + TaskContract
        -> CapabilityRequirements

Two properties matter more than the vocabulary itself.

**These are requirements, not permissions.**  ``repository_read_required=True``
says a future workflow would have to read the repository.  It does not grant
``repository_read_authority``, it does not open a file, and it does not mean
WAITER.1 read anything.  The authority block is separate, is always false, and
lives in :mod:`core.waiter_receipt`.

**Every requirement carries its provenance.**  Each capability records the
structured facts it was derived from, drawn from a bounded vocabulary of INPUT
field paths and Task Shape fields.  A derived requirement is never dressed up
as something the user said: the reason for a repository read is
``task_contract.execution_requirements.repository_inspection_required=true``,
not "the user requested repository traversal".

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, plans nothing, selects no workflow,
provider or model, and grants no authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.task_contract import TaskContract
from core.task_shape import (
    ANSWER_FAMILIES,
    CHANGE_NONE,
    EVIDENCE_DIRECT_CONTEXT,
    INTERACTION_MULTI_STAGE,
    REPOSITORY_SCOPES,
    TaskShape,
)


PHASE_ID = "WAITER.1"
CAPABILITY_REQUIREMENTS_SCHEMA_VERSION = "waiter_1_capability_requirements_v1"

# ── Capability vocabulary ─────────────────────────────────────────────────────
#: Deliberately compact.  A capability earns its place only by changing what a
#: workflow must be able to do, never by describing the request more finely.
CAPABILITY_CONVERSATIONAL_RESPONSE = "conversational_response_required"
CAPABILITY_DIRECT_CONTEXT_ANALYSIS = "direct_context_analysis_required"
CAPABILITY_REPOSITORY_READ = "repository_read_required"
CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE = "broad_repository_reconnaissance_required"
CAPABILITY_EXTERNAL_INFORMATION = "external_information_required"
CAPABILITY_CROSS_SOURCE_SYNTHESIS = "cross_source_synthesis_required"
CAPABILITY_COMPARISON = "comparison_required"
CAPABILITY_CODE_CHANGE = "code_change_required"
CAPABILITY_VALIDATION = "validation_required"
CAPABILITY_MULTI_STAGE_COORDINATION = "multi_stage_coordination_required"
CAPABILITY_PERSISTENT_PROJECT_CONTEXT = "persistent_project_context_required"

CAPABILITY_NAMES: tuple[str, ...] = (
    CAPABILITY_CONVERSATIONAL_RESPONSE,
    CAPABILITY_DIRECT_CONTEXT_ANALYSIS,
    CAPABILITY_REPOSITORY_READ,
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
    CAPABILITY_EXTERNAL_INFORMATION,
    CAPABILITY_CROSS_SOURCE_SYNTHESIS,
    CAPABILITY_COMPARISON,
    CAPABILITY_CODE_CHANGE,
    CAPABILITY_VALIDATION,
    CAPABILITY_MULTI_STAGE_COORDINATION,
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
)

# ── Provenance vocabulary ─────────────────────────────────────────────────────
#: The only structured facts a capability may cite.  Each reason serialises as
#: ``"<source>=<value>"``; the source half must appear here.
SOURCE_TASK_FAMILY = "task_shape.task_family"
SOURCE_INTERACTION_SHAPE = "task_shape.interaction_shape"
SOURCE_EVIDENCE_SCOPE = "task_shape.evidence_scope"
SOURCE_CHANGE_SHAPE = "task_shape.change_shape"
SOURCE_ANALYSIS_SHAPE = "task_shape.analysis_shape"
SOURCE_HORIZON = "task_shape.horizon"
SOURCE_BROAD_REPOSITORY_SCOPE = "task_shape.broad_repository_scope"
SOURCE_EXPLICIT_PROJECT_EVOLUTION = "task_shape.explicit_project_evolution"
SOURCE_CONTRACT_TASK_TYPE = "task_contract.task.type"
SOURCE_CONTRACT_COMPARISON_RELATIONSHIP = "task_contract.relationships.comparison"
SOURCE_CONTRACT_MULTI_STAGE = "task_contract.execution_requirements.multi_stage"
SOURCE_CONTRACT_REPOSITORY_INSPECTION = (
    "task_contract.execution_requirements.repository_inspection_required"
)
SOURCE_CONTRACT_LOCAL_REPOSITORY = (
    "task_contract.execution_requirements.local_repository_required"
)
SOURCE_CONTRACT_EXTERNAL_INFORMATION = (
    "task_contract.execution_requirements.external_information_required"
)

CAPABILITY_REASON_SOURCES: tuple[str, ...] = (
    SOURCE_TASK_FAMILY,
    SOURCE_INTERACTION_SHAPE,
    SOURCE_EVIDENCE_SCOPE,
    SOURCE_CHANGE_SHAPE,
    SOURCE_ANALYSIS_SHAPE,
    SOURCE_HORIZON,
    SOURCE_BROAD_REPOSITORY_SCOPE,
    SOURCE_EXPLICIT_PROJECT_EVOLUTION,
    SOURCE_CONTRACT_TASK_TYPE,
    SOURCE_CONTRACT_COMPARISON_RELATIONSHIP,
    SOURCE_CONTRACT_MULTI_STAGE,
    SOURCE_CONTRACT_REPOSITORY_INSPECTION,
    SOURCE_CONTRACT_LOCAL_REPOSITORY,
    SOURCE_CONTRACT_EXTERNAL_INFORMATION,
)

_REASON_SEPARATOR = "="

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_CAPABILITY_REASONS = 6


def _reason(source: str, value: Any) -> str:
    """Render one provenance reason as ``source=value``."""
    if source not in CAPABILITY_REASON_SOURCES:
        raise ValueError(f"unsupported capability reason source: {source!r}")
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    else:
        rendered = str(value)
    return f"{source}{_REASON_SEPARATOR}{rendered}"


# ── Records ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """One capability a future workflow would need, and why.

    A requirement that is not needed carries no reasons: provenance explains a
    demand, and there is nothing to explain about a capability nobody asked for.
    """

    name: str
    value: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in CAPABILITY_NAMES:
            raise ValueError(f"unsupported capability: {self.name!r}")
        if not isinstance(self.value, bool):
            raise TypeError(f"capability {self.name!r} must carry a bool")
        if len(self.reasons) > MAX_CAPABILITY_REASONS:
            raise ValueError(f"capability {self.name!r} exceeds the reason bound")
        for reason in self.reasons:
            source, separator, _ = reason.partition(_REASON_SEPARATOR)
            if not separator or source not in CAPABILITY_REASON_SOURCES:
                raise ValueError(f"unsupported capability reason: {reason!r}")
        if self.value and not self.reasons:
            raise ValueError(
                f"capability {self.name!r} is required but names no structured fact "
                "it was derived from"
            )
        if not self.value and self.reasons:
            raise ValueError(
                f"capability {self.name!r} is not required and may not carry reasons"
            )

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "reasons": list(self.reasons)}


@dataclass(frozen=True, slots=True)
class CapabilityRequirements:
    """Everything a workflow must be able to do to take one order.

    The record is total over :data:`CAPABILITY_NAMES` and immutable, so a
    caller can neither add a capability the vocabulary does not contain nor
    silently drop one it does.
    """

    requirements: tuple[CapabilityRequirement, ...]
    schema_version: str = CAPABILITY_REQUIREMENTS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.requirements)
        if names != CAPABILITY_NAMES:
            raise ValueError(
                "capability requirements must list every capability exactly once, in "
                "the canonical order"
            )

    def __contains__(self, name: str) -> bool:
        return self.requires(name)

    def requires(self, name: str) -> bool:
        """Is this capability required?  Unknown names are a programming error."""
        for item in self.requirements:
            if item.name == name:
                return item.value
        raise KeyError(f"unsupported capability: {name!r}")

    def reasons_for(self, name: str) -> tuple[str, ...]:
        for item in self.requirements:
            if item.name == name:
                return item.reasons
        raise KeyError(f"unsupported capability: {name!r}")

    def required_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.requirements if item.value)

    @property
    def any_execution_capability_required(self) -> bool:
        """Would this order need machinery beyond answering in place?"""
        return any(
            self.requires(name)
            for name in (
                CAPABILITY_REPOSITORY_READ,
                CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
                CAPABILITY_CODE_CHANGE,
                CAPABILITY_VALIDATION,
                CAPABILITY_MULTI_STAGE_COORDINATION,
                CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "requirements": [item.as_dict() for item in self.requirements],
            "required": list(self.required_names()),
            "note": (
                "These are capability requirements, not permissions. A required "
                "capability describes what a future workflow would need; it grants "
                "nothing and nothing here was performed."
            ),
        }


# ── Deterministic derivation ──────────────────────────────────────────────────

def derive_capability_requirements(
    shape: TaskShape,
    contract: TaskContract,
) -> CapabilityRequirements:
    """Derive what a workflow must be able to do, from structured facts only.

    The contract is read for the execution-requirement flags and the surviving
    comparison relationship — the same fields INPUT already established.  The
    raw request is not consulted.
    """
    if not isinstance(shape, TaskShape):
        raise TypeError("derive_capability_requirements requires a TaskShape")
    if not isinstance(contract, TaskContract):
        raise TypeError("derive_capability_requirements requires a TaskContract")

    requirements = contract.execution_requirements
    repository_required = shape.evidence_scope in REPOSITORY_SCOPES
    external_required = bool(requirements.external_information_required)

    built: list[CapabilityRequirement] = []

    def add(name: str, value: bool, reasons: tuple[str, ...]) -> None:
        built.append(
            CapabilityRequirement(name=name, value=value, reasons=reasons if value else ())
        )

    # ── answering ─────────────────────────────────────────────────────────────
    add(
        CAPABILITY_CONVERSATIONAL_RESPONSE,
        shape.task_family in ANSWER_FAMILIES,
        (
            _reason(SOURCE_TASK_FAMILY, shape.task_family),
            _reason(SOURCE_CHANGE_SHAPE, shape.change_shape),
        ),
    )
    add(
        CAPABILITY_DIRECT_CONTEXT_ANALYSIS,
        shape.evidence_scope == EVIDENCE_DIRECT_CONTEXT,
        (_reason(SOURCE_EVIDENCE_SCOPE, shape.evidence_scope),),
    )

    # ── evidence acquisition (required, never authorized) ─────────────────────
    repository_reasons: list[str] = [_reason(SOURCE_EVIDENCE_SCOPE, shape.evidence_scope)]
    if requirements.repository_inspection_required:
        repository_reasons.append(_reason(SOURCE_CONTRACT_REPOSITORY_INSPECTION, True))
    if requirements.local_repository_required:
        repository_reasons.append(_reason(SOURCE_CONTRACT_LOCAL_REPOSITORY, True))
    add(CAPABILITY_REPOSITORY_READ, repository_required, tuple(repository_reasons))

    recon_reasons: list[str] = [
        _reason(SOURCE_BROAD_REPOSITORY_SCOPE, True),
        _reason(SOURCE_TASK_FAMILY, shape.task_family),
    ]
    if requirements.multi_stage:
        recon_reasons.append(_reason(SOURCE_CONTRACT_MULTI_STAGE, True))
    add(
        CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
        shape.broad_repository_scope,
        tuple(recon_reasons),
    )

    add(
        CAPABILITY_EXTERNAL_INFORMATION,
        external_required,
        (_reason(SOURCE_CONTRACT_EXTERNAL_INFORMATION, True),),
    )
    add(
        CAPABILITY_CROSS_SOURCE_SYNTHESIS,
        repository_required and external_required,
        (
            _reason(SOURCE_EVIDENCE_SCOPE, shape.evidence_scope),
            _reason(SOURCE_CONTRACT_EXTERNAL_INFORMATION, True),
        ),
    )

    # ── reasoning over what was gathered ──────────────────────────────────────
    comparison_reasons: list[str] = []
    if any(item.type == "comparison" for item in contract.relationships):
        comparison_reasons.append(_reason(SOURCE_CONTRACT_COMPARISON_RELATIONSHIP, True))
    if contract.task.type == "comparative_analysis":
        comparison_reasons.append(_reason(SOURCE_CONTRACT_TASK_TYPE, contract.task.type))
    if shape.comparison_present and not comparison_reasons:
        comparison_reasons.append(_reason(SOURCE_ANALYSIS_SHAPE, shape.analysis_shape))
    add(CAPABILITY_COMPARISON, shape.comparison_present, tuple(comparison_reasons))

    # ── change and its validation ─────────────────────────────────────────────
    change_reasons = (
        _reason(SOURCE_CHANGE_SHAPE, shape.change_shape),
        _reason(SOURCE_TASK_FAMILY, shape.task_family),
    )
    change_required = shape.change_shape != CHANGE_NONE
    add(CAPABILITY_CODE_CHANGE, change_required, change_reasons)
    # A change nobody can check is not a capability a workflow may claim, so
    # validation follows change rather than being asked for separately.
    add(CAPABILITY_VALIDATION, change_required, change_reasons)

    # ── coordination and horizon ──────────────────────────────────────────────
    add(
        CAPABILITY_MULTI_STAGE_COORDINATION,
        shape.interaction_shape == INTERACTION_MULTI_STAGE,
        (
            _reason(SOURCE_CONTRACT_MULTI_STAGE, True),
            _reason(SOURCE_INTERACTION_SHAPE, shape.interaction_shape),
        ),
    )
    add(
        CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
        shape.explicit_project_evolution,
        (
            _reason(SOURCE_EXPLICIT_PROJECT_EVOLUTION, True),
            _reason(SOURCE_HORIZON, shape.horizon),
        ),
    )

    return CapabilityRequirements(requirements=tuple(built))
