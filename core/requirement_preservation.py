"""INPUT.1 — deterministic Requirement Preservation Gate.

The gate answers one question:

    Did every explicit commitment the user made survive interpretation?

It compares :class:`~core.explicit_evidence.ExplicitEvidence` (what the user
literally typed) against a :class:`~core.semantic_waiter.SemanticInterpretation`
(what the interpreter claims it means).  Anything literal that disappeared, was
reordered, was rewritten, or was invented and then labelled ``explicit`` fails
the gate.

The gate never consults model confidence.  An interpreter reporting 0.97 while
dropping one of two explicitly named subjects fails exactly as hard as one
reporting 0.1.  Failure is fail-closed: the caller must refuse downstream
routing.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, and grants no authority.
"""

from __future__ import annotations

from core.explicit_evidence import ExplicitEvidence
from core.semantic_waiter import SemanticInterpretation
from core.task_contract import (
    MAX_PRESERVATION_ITEMS,
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PreservationItem,
    PreservationReport,
)


PHASE_ID = "INPUT.1"

#: Characters ignored when deciding whether two literals are the same thing.
#: This lets ``C.A.T.T.U.S`` and ``CATTUS`` match while keeping the comparison
#: deterministic and free of any semantic judgement.
_IGNORED_KEY_CHARS: frozenset[str] = frozenset(" \t\n.-_/\\'\"`")

_MAX_REASON_VALUE_CHARS = 120


def _key(value: str) -> str:
    """Normalize a literal for identity comparison."""
    return "".join(char for char in value.casefold() if char not in _IGNORED_KEY_CHARS)


def _short(value: str) -> str:
    return value if len(value) <= _MAX_REASON_VALUE_CHARS else value[:_MAX_REASON_VALUE_CHARS]


def _literal_support(evidence: ExplicitEvidence) -> set[str]:
    """Every literal the user actually typed, as identity keys."""
    values: list[str] = []
    values.extend(evidence.comparison_subjects())
    values.extend(evidence.named_entities)
    values.extend(evidence.quoted_terms)
    values.extend(evidence.file_paths)
    values.extend(evidence.urls)
    values.extend(evidence.list_items)
    if evidence.framework is not None:
        values.extend(evidence.framework.values)
    return {_key(value) for value in values if value.strip()}


class _Ledger:
    """Accumulates the gate's verdict without letting it grow unbounded."""

    def __init__(self) -> None:
        self.preserved: list[PreservationItem] = []
        self.missing: list[PreservationItem] = []
        self.reasons: list[str] = []
        self._seen_missing: set[str] = set()
        self._seen_preserved: set[str] = set()

    def keep(self, kind: str, value: str) -> None:
        item = PreservationItem(kind=kind, value=value)
        if item.key not in self._seen_preserved:
            self._seen_preserved.add(item.key)
            self.preserved.append(item)

    def lose(self, kind: str, value: str, reason: str) -> None:
        item = PreservationItem(kind=kind, value=value)
        if item.key not in self._seen_missing:
            self._seen_missing.add(item.key)
            self.missing.append(item)
        if reason not in self.reasons:
            self.reasons.append(reason)


def _check_subjects(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    interpreted = {_key(subject.value) for subject in interpretation.subjects}
    for subject in evidence.comparison_subjects():
        if _key(subject) in interpreted:
            ledger.keep("subject", subject)
        else:
            ledger.lose(
                "subject",
                subject,
                f"explicit subject {_short(subject)!r} is absent from the interpretation",
            )


def _check_relationships(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    comparisons = [
        {_key(value) for value in relationship.subjects}
        for relationship in interpretation.relationships
        if relationship.type == "comparison"
    ]
    for comparison in evidence.comparisons:
        wanted = {_key(value) for value in comparison.subjects}
        label = " | ".join(comparison.subjects)
        if any(wanted <= found for found in comparisons):
            ledger.keep("relationship", label)
        else:
            ledger.lose(
                "relationship",
                label,
                f"explicit comparison between {_short(label)!r} is absent from the "
                "interpretation",
            )


def _check_framework(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    supplied = evidence.framework
    if supplied is None:
        return

    label = supplied.type
    interpreted = interpretation.framework
    if interpreted is None:
        ledger.lose(
            "framework",
            label,
            f"the user-supplied {label} was dropped from the interpretation",
        )
        for value in supplied.values:
            ledger.lose(
                "framework_value",
                value,
                f"{label} value {_short(value)!r} was dropped with its framework",
            )
        return

    ledger.keep("framework", label)
    interpreted_keys = [_key(value) for value in interpreted.values]
    interpreted_set = set(interpreted_keys)

    lost_value = False
    for value in supplied.values:
        if _key(value) in interpreted_set:
            ledger.keep("framework_value", value)
        else:
            lost_value = True
            ledger.lose(
                "framework_value",
                value,
                f"{label} value {_short(value)!r} was dropped from the interpretation",
            )

    if lost_value or not supplied.ordered:
        return

    supplied_keys = [_key(value) for value in supplied.values]
    supplied_set = set(supplied_keys)
    backed_order = [key for key in interpreted_keys if key in supplied_set]
    if backed_order != supplied_keys:
        order = " | ".join(supplied.values)
        ledger.lose(
            "framework_order",
            order,
            f"the supplied {label} order was not retained",
        )


def _check_constraints(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    interpreted = {(item.kind, _key(item.text)) for item in interpretation.constraints}
    for constraint in evidence.constraints:
        if (constraint.kind, _key(constraint.text)) in interpreted:
            ledger.keep("constraint", constraint.text)
        else:
            ledger.lose(
                "constraint",
                constraint.text,
                f"explicit {constraint.kind} constraint {_short(constraint.text)!r} was "
                "dropped or rewritten",
            )


def _check_requested_output(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    if not evidence.requested_outputs:
        return
    interpreted = (
        interpretation.requested_output.format if interpretation.requested_output else None
    )
    for requested in evidence.requested_outputs:
        if requested.format == interpreted:
            ledger.keep("requested_output", requested.format)
        else:
            ledger.lose(
                "requested_output",
                requested.format,
                f"explicitly requested output format {requested.format!r} is not carried "
                "by the interpretation",
            )


def _check_behavioral_expectations(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    """DEFECT.FACT.LIVE.1 — a typed behavioral claim survives, exactly.

    ``expected`` and ``observed`` are compared as an ordered pair rather than
    as a set, so an interpreter that swaps them fails the gate instead of
    quietly turning "should be 2space, is 4space" into its opposite.  That
    inversion is the failure this check exists to make unrepresentable.
    """
    interpreted = {
        (
            fact.subject_kind,
            fact.expected_value,
            fact.observed_value,
            fact.relation,
        )
        for fact in interpretation.behavioral_expectations
    }
    for fact in evidence.behavioral_expectations:
        label = fact.behavior_key
        key = (
            fact.subject_kind,
            fact.expected_value,
            fact.observed_value,
            fact.relation,
        )
        if key in interpreted:
            ledger.keep("behavioral_expectation", label)
        else:
            ledger.lose(
                "behavioral_expectation",
                label,
                f"explicit behavioral expectation {_short(label)!r} was dropped, "
                "rewritten or inverted by the interpretation",
            )


def _check_provenance(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
    ledger: _Ledger,
) -> None:
    """No value may claim to be the user's words unless the user typed it."""
    support = _literal_support(evidence)

    for subject in interpretation.subjects:
        if subject.provenance == PROVENANCE_EXPLICIT and _key(subject.value) not in support:
            ledger.lose(
                "provenance",
                subject.value,
                f"subject {_short(subject.value)!r} is marked explicit but the user never "
                "supplied it",
            )

    for relationship in interpretation.relationships:
        if relationship.provenance != PROVENANCE_EXPLICIT:
            continue
        keys = {_key(value) for value in relationship.subjects}
        covered = any(
            {_key(value) for value in comparison.subjects} <= keys
            for comparison in evidence.comparisons
        )
        if not covered or not keys <= support:
            label = " | ".join(relationship.subjects)
            ledger.lose(
                "provenance",
                label,
                f"{relationship.type} relationship {_short(label)!r} is marked explicit but "
                "the user never stated it",
            )

    framework = interpretation.framework
    if framework is not None and framework.provenance == PROVENANCE_EXPLICIT:
        supplied_keys = (
            {_key(value) for value in evidence.framework.values}
            if evidence.framework is not None
            else set()
        )
        for value in framework.values:
            if _key(value) not in supplied_keys:
                ledger.lose(
                    "provenance",
                    value,
                    f"{framework.type} value {_short(value)!r} is marked explicit but the "
                    "user never supplied it",
                )

    supplied_constraints = {(item.kind, _key(item.text)) for item in evidence.constraints}
    for constraint in interpretation.constraints:
        if constraint.provenance != PROVENANCE_EXPLICIT:
            continue
        if (constraint.kind, _key(constraint.text)) not in supplied_constraints:
            ledger.lose(
                "provenance",
                constraint.text,
                f"constraint {_short(constraint.text)!r} is marked explicit but the user "
                "never stated it that way",
            )

    # DEFECT.FACT.LIVE.1.  A behavioral expectation may only ever carry
    # explicit user provenance, so every one an interpretation reports must be
    # backed by a span the user actually typed.  This is the rule that stops a
    # model-proposed or source-derived value becoming a probe expectation.
    supplied_behaviors = {
        (fact.subject_kind, fact.expected_value, fact.observed_value)
        for fact in evidence.behavioral_expectations
    }
    for fact in interpretation.behavioral_expectations:
        identity = (fact.subject_kind, fact.expected_value, fact.observed_value)
        if identity in supplied_behaviors:
            continue
        ledger.lose(
            "provenance",
            fact.behavior_key,
            f"behavioral expectation {_short(fact.behavior_key)!r} is marked "
            "explicit but the user never stated it",
        )

    requested = interpretation.requested_output
    if requested is not None and requested.provenance == PROVENANCE_EXPLICIT:
        supplied_formats = {item.format for item in evidence.requested_outputs}
        if requested.format not in supplied_formats:
            ledger.lose(
                "provenance",
                requested.format,
                f"output format {requested.format!r} is marked explicit but the user never "
                "requested it",
            )


def check_requirement_preservation(
    evidence: ExplicitEvidence,
    interpretation: SemanticInterpretation,
) -> PreservationReport:
    """Compare explicit commitments against an interpretation, fail-closed.

    Returns a :class:`~core.task_contract.PreservationReport`.  A ``failed``
    status means the interpretation mistranscribed the order and must not be
    routed downstream, whatever confidence the interpreter reported.
    """
    ledger = _Ledger()

    _check_subjects(evidence, interpretation, ledger)
    _check_relationships(evidence, interpretation, ledger)
    _check_framework(evidence, interpretation, ledger)
    _check_constraints(evidence, interpretation, ledger)
    _check_behavioral_expectations(evidence, interpretation, ledger)
    _check_requested_output(evidence, interpretation, ledger)
    _check_provenance(evidence, interpretation, ledger)

    preserved = ledger.preserved
    missing = ledger.missing
    reasons = ledger.reasons

    if len(preserved) > MAX_PRESERVATION_ITEMS:
        preserved = preserved[:MAX_PRESERVATION_ITEMS]
    if len(missing) > MAX_PRESERVATION_ITEMS:
        missing = missing[:MAX_PRESERVATION_ITEMS]
        reasons = reasons + ["missing-item list was truncated at the supported bound"]

    if missing:
        return PreservationReport(
            status=PRESERVATION_FAILED,
            preserved_items=tuple(preserved),
            missing_items=tuple(missing),
            reasons=tuple(reasons),
        )

    return PreservationReport(
        status=PRESERVATION_PASSED,
        preserved_items=tuple(preserved),
        reasons=tuple(reasons),
    )
