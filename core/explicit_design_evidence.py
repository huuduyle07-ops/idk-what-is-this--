"""OOP.INTENT.DESIGN.1 — bounded literal design evidence owned by intake.

This is an additive extractor in the existing explicit-evidence pass.  It
recognizes a closed set of declarative commitment forms, preserving their exact
source spans.  Semantic Waiter and the preservation gate carry these records;
the OOP projection never parses prose.  No source reads or model calls occur.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


PHASE_ID = "OOP.INTENT.DESIGN.1"
DESIGN_EVIDENCE_SCHEMA_VERSION = "oop_intent_design_1_explicit_evidence_v1"
PROVENANCE_EXPLICIT_HUMAN = "explicit_human"
PROVENANCE_CURRENT_SOURCE_FACT = "current_source_fact"
PROVENANCE_INFERRED_SEMANTIC = "inferred_semantic_interpretation"
PROVENANCES = (
    PROVENANCE_EXPLICIT_HUMAN,
    PROVENANCE_CURRENT_SOURCE_FACT,
    PROVENANCE_INFERRED_SEMANTIC,
)
MAX_DESIGN_ITEMS = 16
MAX_DESIGN_SOURCE_CHARS = 600
MAX_DESIGN_IDENTIFIER_CHARS = 120
MAX_DESIGN_SCAN_CHARS = 100_000
MAX_DESIGN_EVIDENCE_BYTES = 32_768
DESIGN_FIELDS = (
    "relationships", "state_commitments", "behavior_gates", "explicit_absences",
    "inheritance_prohibitions", "evaluative",
)
OVERFLOW_FIELDS = DESIGN_FIELDS + ("scanned_text", "source_text", "serialized_bytes")


def _label(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_DESIGN_IDENTIFIER_CHARS:
        raise ValueError(f"{name} must be a bounded nonempty string")


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    source_text: str
    source_start: int
    source_end: int
    provenance: str = PROVENANCE_EXPLICIT_HUMAN

    def __post_init__(self) -> None:
        if not isinstance(self.source_text, str) or not self.source_text or len(self.source_text) > MAX_DESIGN_SOURCE_CHARS:
            raise ValueError("design evidence needs a bounded literal source span")
        if (type(self.source_start) is not int or type(self.source_end) is not int
                or self.source_start < 0 or self.source_end <= self.source_start
                or self.source_end - self.source_start != len(self.source_text)):
            raise ValueError("design evidence offsets must identify its literal text")
        if self.provenance not in PROVENANCES:
            raise ValueError("unsupported design evidence provenance")

    def as_dict(self) -> dict[str, Any]:
        return {"source_text": self.source_text, "source_start": self.source_start,
                "source_end": self.source_end, "provenance": self.provenance}


@dataclass(frozen=True, slots=True)
class InheritanceCommitment:
    child: str
    parent: str
    evidence: EvidenceSpan

    def __post_init__(self) -> None:
        _label(self.child, "child")
        _label(self.parent, "parent")
        if not isinstance(self.evidence, EvidenceSpan):
            raise TypeError("inheritance evidence must be an EvidenceSpan")

    def as_dict(self) -> dict[str, Any]:
        return {"relationship_kind": "inheritance", "child": self.child,
                "parent": self.parent, "evidence": self.evidence.as_dict()}


@dataclass(frozen=True, slots=True)
class StateOwnershipCommitment:
    state: str
    owner: str
    evidence: EvidenceSpan
    state_role: str | None = None

    def __post_init__(self) -> None:
        _label(self.state, "state")
        _label(self.owner, "owner")
        if not isinstance(self.evidence, EvidenceSpan):
            raise TypeError("state evidence must be an EvidenceSpan")
        if self.state_role not in (None, "savings_state"):
            raise ValueError("unsupported state role")

    def as_dict(self) -> dict[str, Any]:
        return {"relationship_kind": "state_ownership", "state": self.state,
                "owner": self.owner, "ownership_constraint": "exclusive_owner",
                "state_role": self.state_role,
                "evidence": self.evidence.as_dict()}


@dataclass(frozen=True, slots=True)
class BehaviorGate:
    gated_behavior: str
    condition: str
    evidence: EvidenceSpan

    def __post_init__(self) -> None:
        _label(self.gated_behavior, "gated behavior")
        if self.condition not in ("successful_password_verification", "successful_credential_verification"):
            raise ValueError("unsupported design gate condition")
        if not isinstance(self.evidence, EvidenceSpan):
            raise TypeError("gate evidence must be an EvidenceSpan")

    def as_dict(self) -> dict[str, Any]:
        return {"relationship_kind": "behavior_gate", "gated_behavior": self.gated_behavior,
                "condition": self.condition, "evidence": self.evidence.as_dict()}


@dataclass(frozen=True, slots=True)
class ExplicitAbsence:
    subject: str
    evidence: EvidenceSpan

    def __post_init__(self) -> None:
        if self.subject != "authentication_support":
            raise ValueError("unsupported explicit design absence")
        if not isinstance(self.evidence, EvidenceSpan):
            raise TypeError("absence evidence must be an EvidenceSpan")

    def as_dict(self) -> dict[str, Any]:
        return {"relationship_kind": "explicit_absence", "subject": self.subject,
                "evidence": self.evidence.as_dict()}


@dataclass(frozen=True, slots=True)
class DesignEvidence:
    relationships: tuple[InheritanceCommitment, ...] = ()
    state_commitments: tuple[StateOwnershipCommitment, ...] = ()
    behavior_gates: tuple[BehaviorGate, ...] = ()
    explicit_absences: tuple[ExplicitAbsence, ...] = ()
    inheritance_prohibitions: tuple[EvidenceSpan, ...] = ()
    evaluative: tuple[EvidenceSpan, ...] = ()
    overflow: tuple[str, ...] = ()
    unclassified_clauses_present: bool = False

    def __post_init__(self) -> None:
        if type(self.unclassified_clauses_present) is not bool:
            raise TypeError("design coverage must be a boolean")
        types = (InheritanceCommitment, StateOwnershipCommitment, BehaviorGate,
                 ExplicitAbsence, EvidenceSpan, EvidenceSpan)
        for name, item_type in zip(DESIGN_FIELDS, types):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) > MAX_DESIGN_ITEMS:
                raise ValueError(f"design {name} exceeds immutable collection bounds")
            if any(not isinstance(value, item_type) for value in values):
                raise TypeError(f"design {name} contains an invalid record")
        if (not isinstance(self.overflow, tuple) or len(set(self.overflow)) != len(self.overflow)
                or any(value not in OVERFLOW_FIELDS for value in self.overflow)):
            raise ValueError("invalid design evidence overflow fields")
        if len(json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")) > MAX_DESIGN_EVIDENCE_BYTES:
            raise ValueError("design evidence exceeds its serialized byte bound")

    def is_empty(self) -> bool:
        return not self.overflow and not any(getattr(self, name) for name in DESIGN_FIELDS)

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": DESIGN_EVIDENCE_SCHEMA_VERSION,
                **{name: [item.as_dict() for item in getattr(self, name)] for name in DESIGN_FIELDS},
                "overflow": list(self.overflow),
                "unclassified_clauses_present": self.unclassified_clauses_present}


_ID = r"[A-Za-z_$][A-Za-z0-9_$]{0,119}"
_INHERITANCE = re.compile(
    rf"(?P<child>{_ID})\s+(?:extends|(?:should|must|shall|will)\s+extend|"
    rf"(?:should|must|shall|will)\s+(?:be|become)\s+(?:a\s+)?subclass\s+of|"
    rf"(?:is|becomes)\s+(?:a\s+)?subclass\s+of)\s+(?P<parent>{_ID})", re.I)
_STATE = re.compile(
    rf"(?P<state>{_ID})\s+(?:(?:should|must|shall)\s+)?belongs?\s+only\s+to\s+"
    rf"(?P<owner>{_ID})(?:\s*,?\s+because\s+not\s+every\s+{_ID}\s+needs\s+"
    rf"(?P<role>savings\s+state))?", re.I)
_GATE = re.compile(
    r"(?:Using\s+)?(?:the\s+)?(?P<behavior>[A-Za-z][A-Za-z0-9_ -]{0,119}?)\s+"
    r"(?:(?:should|must|shall)\s+)?(?:requires?|depends?\s+on|depend\s+on)\s+"
    r"(?:(?:the\s+)?user\s+(?:entering|providing)\s+(?:the\s+)?(?:correct|valid)\s+"
    r"(?P<entered>password|credentials?)|(?:correct|successful|valid)\s+"
    r"(?P<verified>password|credential)\s+verification)", re.I)
_ABSENCE = re.compile(
    r"(?:The\s+)?current\s+(?:code|source|implementation)\s+"
    r"(?:does\s+not\s+(?:yet\s+)?(?:contain|have|include)|has\s+no|lacks)\s+"
    r"(?:any\s+)?(?:password/authentication|authentication/password|password|authentication|auth)\s+"
    r"(?:support|mechanism|functionality)", re.I)
_PROHIBITION = re.compile(r"(?:do\s+not|don't|never)\s+use\s+inheritance", re.I)
_EVALUATIVE = re.compile(r"(?:would|should|could|can|might|consider|evaluate|discuss)\b.*"
                         r"\b(?:inheritance|extends?|subclass)\b.*", re.I)
_NONCOMMITTAL_GATE = re.compile(
    r"\b(?:not|never|no|neither|nor|don't|doesn't|shouldn't|mustn't|cannot|can't|would|could|might|"
    r"if|suppose|consider|evaluate|discuss|example|current|existing|already|"
    r"mentions?|says?|reported|describes?)\b", re.I)
_FENCE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[^\n]*(?:\n|$)")
_CLAUSE = re.compile(r"[^.!?;]+[.!?;]?")


def extract_design_evidence(raw_text: str) -> DesignEvidence:
    """Extract bounded literal forms once, before Semantic Waiter interpretation.

    Unrecognized phrasing stays raw evidence.  It is never repaired by guessing.
    Overflow is explicit and makes preservation fail closed downstream.
    """
    if not isinstance(raw_text, str):
        raise TypeError("design extraction requires text")
    if len(raw_text) > MAX_DESIGN_SCAN_CHARS:
        return DesignEvidence(overflow=("scanned_text",))
    # Mask source fences without shifting offsets.  Bare declarations also fail
    # the full-clause grammar because they start with `class`, not an identifier.
    scan = _FENCE.sub(lambda match: " " * len(match.group()), raw_text)
    buckets: dict[str, list[Any]] = {name: [] for name in DESIGN_FIELDS}
    overflow: list[str] = []
    unclassified = False

    def add(name: str, value: Any) -> None:
        if len(buckets[name]) == MAX_DESIGN_ITEMS:
            if name not in overflow:
                overflow.append(name)
        else:
            buckets[name].append(value)

    for match in _CLAUSE.finditer(scan):
        text = match.group().strip()
        if not text:
            continue
        offset = match.start() + len(match.group()) - len(match.group().lstrip())
        literal = raw_text[offset:offset + len(text)]
        clause = " ".join(text.rstrip(".!?;").split())
        evaluative = bool(_EVALUATIVE.fullmatch(clause))
        if text.endswith("?") or evaluative:
            if evaluative and len(literal) <= MAX_DESIGN_SOURCE_CHARS:
                add("evaluative", EvidenceSpan(literal, offset, offset + len(literal)))
            elif evaluative:
                if "source_text" not in overflow:
                    overflow.append("source_text")
            else:
                unclassified = True
            continue
        relation = _INHERITANCE.fullmatch(clause)
        state = _STATE.fullmatch(clause)
        gate = _GATE.fullmatch(clause)
        if gate and _NONCOMMITTAL_GATE.search(gate["behavior"]):
            gate = None
        absence = _ABSENCE.fullmatch(clause)
        prohibition = _PROHIBITION.fullmatch(clause)
        if not any((relation, state, gate, absence, prohibition)):
            unclassified = True
            continue
        if len(literal) > MAX_DESIGN_SOURCE_CHARS:
            if "source_text" not in overflow:
                overflow.append("source_text")
            continue
        evidence = EvidenceSpan(literal, offset, offset + len(literal))
        if relation:
            add("relationships", InheritanceCommitment(relation["child"], relation["parent"], evidence))
        elif state:
            add("state_commitments", StateOwnershipCommitment(state["state"], state["owner"], evidence,
                state_role="savings_state" if state["role"] else None))
        elif gate:
            condition = gate["entered"] or gate["verified"]
            canonical = ("successful_password_verification" if condition.casefold() == "password"
                         else "successful_credential_verification")
            add("behavior_gates", BehaviorGate(gate["behavior"], canonical, evidence))
        elif absence:
            add("explicit_absences", ExplicitAbsence("authentication_support", evidence))
        elif prohibition:
            add("inheritance_prohibitions", evidence)
    try:
        return DesignEvidence(**{name: tuple(values) for name, values in buckets.items()},
                              overflow=tuple(overflow),
                              unclassified_clauses_present=unclassified if any(buckets.values()) else False)
    except ValueError as error:
        if "serialized byte bound" not in str(error):
            raise
        return DesignEvidence(overflow=tuple(dict.fromkeys((*overflow, "serialized_bytes"))))
