"""OOP.INTENT.DESIGN.1: read-only future design from preserved input evidence.

This consumer never parses prose, inspects source, calls a provider, opens a
clarification session, or chooses an implementation. Literal extraction belongs
to the existing explicit-evidence/Semantic Waiter boundary. Current-source
facts remain owned by CTX.OOP; a human's explicit absence claim is not a source
inspection result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json

from core.explicit_design_evidence import (
    BehaviorGate,
    EvidenceSpan,
    ExplicitAbsence,
    InheritanceCommitment,
)
from core.requirement_preservation import check_requirement_preservation
from core.semantic_waiter import SemanticInterpretation
from core.task_contract import TaskContract


PHASE_ID = "OOP.INTENT.DESIGN.1"
SCHEMA_VERSION = "oop_intent_design_1_v1"
PROVENANCES = (
    "explicit_human", "current_source_fact", "inferred_semantic_interpretation",
)
MAX_RELATIONSHIPS = 16
MAX_STATE_COMMITMENTS = 16
MAX_BEHAVIOR_GATES = 8
MAX_EXPLICIT_ABSENCES = 8
MAX_UNRESOLVED_DIMENSIONS = 11
MAX_CONFLICTS = 32
MAX_SERIALIZED_BYTES = 65_536
UNRESOLVED_DIMENSIONS = (
    "credential_ownership",
    "credential_source",
    "credential_persistence",
    "credential_verification_mechanism",
    "verification_failure_behavior",
    "verification_lifecycle",
    "account_identity",
    "savings_funding_semantics",
    "savings_interest_semantics",
    "source_layout",
    "subclass_creation_lifecycle",
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _tuple(values: tuple, item_type: type, limit: int, name: str) -> None:
    if (not isinstance(values, tuple) or len(values) > limit
            or any(not isinstance(item, item_type) for item in values)):
        raise ValueError(f"{name} exceeds immutable typed bounds")


def _references(values: tuple[str, ...]) -> None:
    _tuple(values, str, 32, "evidence references")
    if any(not item.startswith("explicit_human:") or len(item) != 79 for item in values):
        raise ValueError("invalid explicit evidence reference")


@dataclass(frozen=True, slots=True)
class ProposedStateCommitment:
    state: str
    owner: str
    evidence: EvidenceSpan
    ownership_constraint: str = "owner_only"
    base_exclusion: str | None = None
    base_exclusion_provenance: str | None = None
    basis: tuple[str, ...] = ()
    state_role: str | None = None
    relationship_kind: str = field(default="state_ownership", init=False)

    def __post_init__(self) -> None:
        _references(self.basis)
        if not isinstance(self.evidence, EvidenceSpan):
            raise TypeError("state commitment requires typed evidence")
        if any(not isinstance(item, str) or not item or len(item) > 120
               for item in (self.state, self.owner)):
            raise ValueError("state commitment needs bounded exact identifiers")
        if self.state_role not in (None, "savings_state"):
            raise ValueError("unsupported state role")
        if self.ownership_constraint not in ("owner_only", "subclass_only"):
            raise ValueError("unsupported state ownership constraint")
        if self.base_exclusion is not None and (
            self.ownership_constraint != "subclass_only"
            or self.base_exclusion_provenance != "inferred_semantic_interpretation"
            or not self.basis
        ):
            raise ValueError("base exclusion requires an explicit inheritance basis")
        if self.base_exclusion is None and (self.ownership_constraint == "subclass_only"
                or self.base_exclusion_provenance is not None or self.basis):
            raise ValueError("subclass semantics require a preserved parent")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class UnresolvedDesignDimension:
    dimension: str
    basis: tuple[str, ...]
    status: str = "unspecified"
    provenance: str = field(default="inferred_semantic_interpretation", init=False)

    def __post_init__(self) -> None:
        _references(self.basis)
        if self.dimension not in UNRESOLVED_DIMENSIONS or not self.basis:
            raise ValueError("an unresolved dimension needs a bounded name and evidence basis")
        if self.status not in ("unspecified", "not_resolved_by_projection"):
            raise ValueError("unsupported unresolved dimension status")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DesignCommitmentConflict:
    kind: str
    evidence: tuple[EvidenceSpan, ...]

    def __post_init__(self) -> None:
        _tuple(self.evidence, EvidenceSpan, 32, "conflict evidence")
        if self.kind not in ("inheritance_prohibited", "incompatible_parents", "incompatible_owners"):
            raise ValueError("unsupported commitment conflict")
        if len(self.evidence) < 2:
            raise ValueError("a conflict must retain both evidence paths")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProposedDesignIntent:
    status: str
    task_contract_fingerprint: str
    raw_request_fingerprint: str
    semantic_interpretation_fingerprint: str
    relationships: tuple[InheritanceCommitment, ...] = ()
    state_commitments: tuple[ProposedStateCommitment, ...] = ()
    behavior_gates: tuple[BehaviorGate, ...] = ()
    explicit_absences: tuple[ExplicitAbsence, ...] = ()
    unresolved_dimensions: tuple[UnresolvedDesignDimension, ...] = ()
    conflicts: tuple[DesignCommitmentConflict, ...] = ()
    evaluative: tuple[EvidenceSpan, ...] = ()
    overflow: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    authority: str = field(default="read_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.status not in ("resolved", "unresolved", "conflict", "unavailable", "bounded"):
            raise ValueError("unsupported proposed design status")
        for name, item_type, limit in (
            ("relationships", InheritanceCommitment, MAX_RELATIONSHIPS),
            ("state_commitments", ProposedStateCommitment, MAX_STATE_COMMITMENTS),
            ("behavior_gates", BehaviorGate, MAX_BEHAVIOR_GATES),
            ("explicit_absences", ExplicitAbsence, MAX_EXPLICIT_ABSENCES),
            ("unresolved_dimensions", UnresolvedDesignDimension, MAX_UNRESOLVED_DIMENSIONS),
            ("conflicts", DesignCommitmentConflict, MAX_CONFLICTS),
            ("evaluative", EvidenceSpan, 16),
            ("overflow", str, 10),
            ("reasons", str, 8),
        ):
            _tuple(getattr(self, name), item_type, limit, name)
        for fingerprint in (self.task_contract_fingerprint, self.raw_request_fingerprint,
                            self.semantic_interpretation_fingerprint):
            if (not isinstance(fingerprint, str) or len(fingerprint) != 64
                    or any(char not in "0123456789abcdef" for char in fingerprint)):
                raise ValueError("projection fingerprints must be SHA-256 values")
        if self.conflicts and self.status != "conflict":
            raise ValueError("conflicting commitments cannot be resolved")
        if self.overflow and self.status != "bounded":
            raise ValueError("overflow must be explicit")
        if len(self.to_json().encode("utf-8")) > MAX_SERIALIZED_BYTES:
            raise ValueError("serialized_bytes exceeds projection bound")

    def as_dict(self) -> dict:
        value = asdict(self)
        for name in ("relationships", "state_commitments", "behavior_gates",
                     "explicit_absences", "unresolved_dimensions", "conflicts", "evaluative"):
            value[name] = [item.as_dict() for item in getattr(self, name)]
        value["phase_id"] = PHASE_ID
        value["provenance_vocabulary"] = list(PROVENANCES)
        value["current_source_status"] = "not_acquired_by_projection"
        value["temporal_scope"] = {
            "relationships": "desired_future_design",
            "state_commitments": "desired_future_design",
            "behavior_gates": "desired_future_design",
            "explicit_absences": "human_assertion_about_current_state",
        }
        return json.loads(_json(value))

    def to_json(self) -> str:
        return _json(self.as_dict())

    @property
    def fingerprint(self) -> str:
        return sha256(self.to_json().encode("utf-8")).hexdigest()


def _contract_interpretation(contract: TaskContract) -> SemanticInterpretation:
    """Reconstruct only the interpretation fields retained by INPUT.1."""
    return SemanticInterpretation(
        task=contract.task, subjects=contract.subjects,
        relationships=contract.relationships, framework=contract.user_supplied_framework,
        requested_output=contract.requested_output, constraints=contract.constraints,
        behavioral_expectations=contract.behavioral_expectations,
        design_evidence=contract.design_evidence,
        ambiguities=contract.ambiguities, missing_information=contract.missing_information,
        execution_requirements=contract.execution_requirements, notes=contract.notes,
    )


def _ref(span: EvidenceSpan) -> str:
    return "explicit_human:" + _fingerprint(span.as_dict())


def project_proposed_design_intent(
    contract: TaskContract,
    *,
    interpretation: SemanticInterpretation | None = None,
) -> ProposedDesignIntent:
    """Project a preserved contract; supplied interpretations must match it.

    ``resolved`` means explicit decisions have been typed, not that a complete
    implementation design exists. Unresolved dimensions are evidence, never
    admission gates, questions, defaults, or authoring permission.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("a TaskContract is required")
    reconstructed = _contract_interpretation(contract)
    binding = dict(
        task_contract_fingerprint=_fingerprint(contract.as_dict()),
        raw_request_fingerprint=contract.raw_request.sha256,
        semantic_interpretation_fingerprint=_fingerprint(reconstructed.as_dict()),
    )
    if interpretation is not None and (
        not isinstance(interpretation, SemanticInterpretation)
        or interpretation.as_dict() != reconstructed.as_dict()
    ):
        return ProposedDesignIntent(status="unavailable", **binding,
            reasons=("semantic_interpretation_binding_mismatch",))

    evidence = contract.design_evidence
    if evidence.overflow:
        return ProposedDesignIntent(status="bounded", **binding,
            overflow=evidence.overflow, reasons=("design_evidence_overflow",))
    if (not contract.preservation.passed
            or not check_requirement_preservation(contract.explicit_evidence, reconstructed).passed):
        return ProposedDesignIntent(status="unavailable", **binding,
            reasons=("requirement_preservation_failed",))

    spans = tuple(item.evidence for group in (
        evidence.relationships, evidence.state_commitments,
        evidence.behavior_gates, evidence.explicit_absences,
    ) for item in group) + evidence.inheritance_prohibitions + evidence.evaluative
    if any(span.provenance != "explicit_human"
           or contract.raw_request.text[span.source_start:span.source_end] != span.source_text
           for span in spans):
        return ProposedDesignIntent(status="unavailable", **binding,
            reasons=("explicit_evidence_binding_mismatch",))

    conflicts: list[DesignCommitmentConflict] = []
    if evidence.relationships and evidence.inheritance_prohibitions:
        conflicts.append(DesignCommitmentConflict("inheritance_prohibited",
            tuple(item.evidence for item in evidence.relationships)
            + evidence.inheritance_prohibitions))
    parents: dict[str, list[InheritanceCommitment]] = {}
    for item in evidence.relationships:
        parents.setdefault(item.child, []).append(item)
    for items in parents.values():
        if len({item.parent for item in items}) > 1:
            conflicts.append(DesignCommitmentConflict("incompatible_parents",
                tuple(item.evidence for item in items)))
    owners: dict[str, list] = {}
    for item in evidence.state_commitments:
        owners.setdefault(item.state, []).append(item)
    for items in owners.values():
        if len({item.owner for item in items}) > 1:
            conflicts.append(DesignCommitmentConflict("incompatible_owners",
                tuple(item.evidence for item in items)))

    states = []
    for item in evidence.state_commitments:
        inherited = parents.get(item.owner, [])
        base = inherited[0].parent if len({rel.parent for rel in inherited}) == 1 else None
        if evidence.inheritance_prohibitions:
            base = None
        states.append(ProposedStateCommitment(
            state=item.state, owner=item.owner, evidence=item.evidence,
            ownership_constraint="subclass_only" if base else "owner_only",
            base_exclusion=base,
            base_exclusion_provenance="inferred_semantic_interpretation" if base else None,
            basis=tuple(_ref(rel.evidence) for rel in inherited) if base else (),
            state_role=item.state_role,
        ))

    dimensions: list[UnresolvedDesignDimension] = []
    # Unknown clauses may already contain a human decision outside this closed
    # vocabulary. Never confuse a limit of our projection with human omission.
    dimension_status = ("not_resolved_by_projection" if evidence.unclassified_clauses_present
                        else "unspecified")
    gates = tuple(_ref(item.evidence) for item in evidence.behavior_gates)
    if gates:
        dimensions.extend(UnresolvedDesignDimension(name, gates, dimension_status)
            for name in UNRESOLVED_DIMENSIONS[:7])
    savings_gates = tuple(_ref(item.evidence) for item in evidence.behavior_gates
        if item.gated_behavior.casefold() in ("savings functionality", "savings behavior"))
    savings_states = tuple(_ref(item.evidence) for item in states if item.state_role == "savings_state")
    if savings_gates and savings_states:
        basis = savings_gates + savings_states
        dimensions.extend(UnresolvedDesignDimension(name, basis, dimension_status)
            for name in ("savings_funding_semantics", "savings_interest_semantics"))
    if evidence.relationships:
        basis = tuple(_ref(item.evidence) for item in evidence.relationships)
        dimensions.extend(UnresolvedDesignDimension(name, basis, dimension_status)
            for name in ("source_layout", "subclass_creation_lifecycle"))

    status = "resolved" if (evidence.relationships or states or gates or evidence.explicit_absences) else "unavailable"
    if evidence.evaluative and status == "unavailable":
        status = "unresolved"
    if conflicts:
        status = "conflict"
    try:
        return ProposedDesignIntent(
            status=status, **binding, relationships=evidence.relationships,
            state_commitments=tuple(states), behavior_gates=evidence.behavior_gates,
            explicit_absences=evidence.explicit_absences,
            unresolved_dimensions=tuple(dimensions), conflicts=tuple(conflicts),
            evaluative=evidence.evaluative,
            reasons=("no_supported_explicit_commitments",) if status == "unavailable" else (),
        )
    except ValueError as error:
        if "bound" not in str(error):
            raise
        return ProposedDesignIntent(status="bounded", **binding,
            overflow=("projection_bounds",), reasons=(str(error),))
