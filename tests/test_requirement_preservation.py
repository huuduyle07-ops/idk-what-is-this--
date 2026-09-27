"""INPUT.1 — deterministic Requirement Preservation Gate tests.

The gate compares explicit user commitments against the resulting semantic
interpretation.  It is deliberately deaf to model confidence: an interpreter
that reports 0.97 while dropping an explicitly named subject still fails.
"""

from __future__ import annotations

import dataclasses

from core.explicit_evidence import extract_explicit_evidence
from core.requirement_preservation import check_requirement_preservation
from core.semantic_waiter import ExplicitEvidenceInterpreter, SemanticInterpretation
from core.task_contract import (
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Constraint,
    ExecutionRequirements,
    Relationship,
    RequestedOutput,
    Subject,
    TaskClassification,
    UserSuppliedFramework,
)


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

RUBRIC = (
    "Equivalent",
    "DeepSeek stronger",
    "C.A.T.T.U.S stronger",
    "Orthogonal",
    "Not worth adopting",
)


def _evidence(text: str = DOGFOOD_PROMPT):
    return extract_explicit_evidence(text)


def _faithful(text: str = DOGFOOD_PROMPT) -> SemanticInterpretation:
    return ExplicitEvidenceInterpreter().interpret(text, extract_explicit_evidence(text))


def _check(interpretation: SemanticInterpretation, text: str = DOGFOOD_PROMPT):
    return check_requirement_preservation(extract_explicit_evidence(text), interpretation)


# ── the faithful path ─────────────────────────────────────────────────────────

def test_faithful_interpretation_passes():
    report = _check(_faithful())

    assert report.status == PRESERVATION_PASSED
    assert report.missing_items == ()
    assert report.passed is True


def test_passing_report_lists_what_it_verified():
    report = _check(_faithful())

    preserved = {item.key for item in report.preserved_items}
    assert "subject:DeepSeek Harness" in preserved
    assert "subject:C.A.T.T.U.S" in preserved
    assert "framework_value:Orthogonal" in preserved


def test_conversational_input_passes_with_nothing_to_preserve():
    text = "hey, how are you?"
    report = _check(_faithful(text), text)

    assert report.status == PRESERVATION_PASSED
    assert report.missing_items == ()


def test_gate_is_deterministic():
    first = _check(_faithful())
    second = _check(_faithful())

    assert first.as_dict() == second.as_dict()


# ── dropped subjects ──────────────────────────────────────────────────────────

def test_dropping_an_explicitly_named_subject_fails():
    faithful = _faithful()
    lossy = dataclasses.replace(
        faithful,
        subjects=tuple(s for s in faithful.subjects if "C.A.T.T.U.S" not in s.value),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("subject") is True
    assert "C.A.T.T.U.S" in report.missing_values("subject")
    assert report.reasons


def test_high_model_confidence_cannot_rescue_a_dropped_subject():
    """A confident interpreter that loses a subject must still fail."""
    lossy = SemanticInterpretation(
        task=TaskClassification(
            type="analysis", provenance=PROVENANCE_INFERRED, confidence=0.97
        ),
        subjects=(Subject(value="DeepSeek Harness", provenance=PROVENANCE_EXPLICIT),),
        framework=UserSuppliedFramework(
            type="framework", values=RUBRIC, provenance=PROVENANCE_EXPLICIT
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert "C.A.T.T.U.S" in report.missing_values("subject")


def test_dropping_the_comparison_relationship_fails():
    lossy = dataclasses.replace(_faithful(), relationships=())

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("relationship") is True


def test_acronym_spelling_variant_still_counts_as_preserved():
    faithful = _faithful()
    respelled = tuple(
        dataclasses.replace(s, value="CATTUS") if "C.A.T.T.U.S" == s.value else s
        for s in faithful.subjects
    )
    variant = dataclasses.replace(
        faithful,
        subjects=respelled,
        relationships=(
            Relationship(
                type="comparison",
                subjects=("DeepSeek Harness", "CATTUS"),
                provenance=PROVENANCE_EXPLICIT,
            ),
        ),
    )

    assert _check(variant).status == PRESERVATION_PASSED


# ── rubric / framework ────────────────────────────────────────────────────────

def test_dropping_one_rubric_value_fails():
    faithful = _faithful()
    lossy = dataclasses.replace(
        faithful,
        framework=UserSuppliedFramework(
            type="framework",
            values=tuple(v for v in RUBRIC if v != "Orthogonal"),
            provenance=PROVENANCE_EXPLICIT,
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert "Orthogonal" in report.missing_values("framework_value")


def test_both_subjects_kept_but_a_rubric_item_dropped_still_fails():
    faithful = _faithful()
    lossy = dataclasses.replace(
        faithful,
        framework=UserSuppliedFramework(
            type="framework", values=RUBRIC[:4], provenance=PROVENANCE_EXPLICIT
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert {s.value for s in lossy.subjects} >= {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert "Not worth adopting" in report.missing_values("framework_value")


def test_dropping_the_whole_framework_fails():
    lossy = dataclasses.replace(_faithful(), framework=None)

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("framework") is True


def test_reordering_a_supplied_rubric_fails():
    reordered = (RUBRIC[1], RUBRIC[0]) + RUBRIC[2:]
    lossy = dataclasses.replace(
        _faithful(),
        framework=UserSuppliedFramework(
            type="framework", values=reordered, provenance=PROVENANCE_EXPLICIT
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("framework_order") is True


def test_adding_an_invented_rubric_value_fails():
    lossy = dataclasses.replace(
        _faithful(),
        framework=UserSuppliedFramework(
            type="framework",
            values=RUBRIC + ("Needs more study",),
            provenance=PROVENANCE_EXPLICIT,
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("provenance") is True


# ── constraints ───────────────────────────────────────────────────────────────

def test_changing_an_explicit_constraint_fails():
    text = "Fix the parser. Do not modify tests."
    faithful = _faithful(text)
    lossy = dataclasses.replace(
        faithful,
        constraints=(
            Constraint(
                kind="prohibition",
                text="Do not modify tests unless it helps",
                provenance=PROVENANCE_EXPLICIT,
            ),
        ),
    )

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED
    assert "Do not modify tests" in report.missing_values("constraint")


def test_dropping_an_explicit_constraint_fails():
    text = "Fix the parser. Do not modify tests."
    lossy = dataclasses.replace(_faithful(text), constraints=())

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("constraint") is True


def test_flipping_a_constraint_kind_fails():
    text = "Fix the parser. Do not modify tests."
    lossy = dataclasses.replace(
        _faithful(text),
        constraints=(
            Constraint(
                kind="requirement",
                text="Do not modify tests",
                provenance=PROVENANCE_EXPLICIT,
            ),
        ),
    )

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED


# ── requested output ──────────────────────────────────────────────────────────

def test_dropping_a_requested_output_format_fails():
    text = "Compare Redis with Memcached as a table."
    lossy = dataclasses.replace(_faithful(text), requested_output=None)

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED
    assert "table" in report.missing_values("requested_output")


def test_changing_a_requested_output_format_fails():
    text = "Compare Redis with Memcached as a table."
    lossy = dataclasses.replace(
        _faithful(text),
        requested_output=RequestedOutput(format="json", provenance=PROVENANCE_EXPLICIT),
    )

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED


# ── provenance integrity ──────────────────────────────────────────────────────

def test_marking_an_invented_subject_explicit_fails():
    faithful = _faithful()
    lossy = dataclasses.replace(
        faithful,
        subjects=faithful.subjects
        + (Subject(value="Kubernetes", provenance=PROVENANCE_EXPLICIT),),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert "Kubernetes" in report.missing_values("provenance")


def test_marking_an_invented_framework_explicit_fails():
    text = "Compare Redis with Memcached."
    lossy = dataclasses.replace(
        _faithful(text),
        framework=UserSuppliedFramework(
            type="rubric", values=("speed", "cost"), provenance=PROVENANCE_EXPLICIT
        ),
    )

    report = _check(lossy, text)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("provenance") is True


def test_marking_an_invented_constraint_explicit_fails():
    lossy = dataclasses.replace(
        _faithful(),
        constraints=(
            Constraint(
                kind="prohibition",
                text="Do not use the network",
                provenance=PROVENANCE_EXPLICIT,
            ),
        ),
    )

    report = _check(lossy)

    assert report.status == PRESERVATION_FAILED
    assert report.has_missing("provenance") is True


# ── inferred additions are welcome ────────────────────────────────────────────

def test_adding_inferred_subjects_is_allowed():
    faithful = _faithful()
    enriched = dataclasses.replace(
        faithful,
        subjects=faithful.subjects
        + (
            Subject(
                value="harness benchmarking",
                provenance=PROVENANCE_INFERRED,
                confidence=0.6,
            ),
        ),
    )

    assert _check(enriched).status == PRESERVATION_PASSED


def test_adding_inferred_execution_metadata_is_allowed():
    enriched = dataclasses.replace(
        _faithful(),
        execution_requirements=ExecutionRequirements(
            multi_stage=True,
            external_information_required=True,
            repository_inspection_required=True,
            local_repository_required=True,
            provenance=PROVENANCE_INFERRED,
            confidence=0.8,
        ),
    )

    assert _check(enriched).status == PRESERVATION_PASSED


def test_adding_inferred_ambiguities_and_gaps_is_allowed():
    enriched = dataclasses.replace(
        _faithful(),
        ambiguities=("scope of 'Harness' is unclear",),
        missing_information=("no local copy of DeepSeek Harness supplied",),
    )

    assert _check(enriched).status == PRESERVATION_PASSED


def test_adding_an_inferred_constraint_is_allowed():
    faithful = _faithful()
    enriched = dataclasses.replace(
        faithful,
        constraints=faithful.constraints
        + (
            Constraint(
                kind="restriction",
                text="stay within the supplied rubric",
                provenance=PROVENANCE_INFERRED,
                confidence=0.7,
            ),
        ),
    )

    assert _check(enriched).status == PRESERVATION_PASSED


# ── report shape ──────────────────────────────────────────────────────────────

def test_failure_reason_names_the_lost_requirement():
    lossy = dataclasses.replace(_faithful(), framework=None)

    report = _check(lossy)

    assert any("framework" in reason for reason in report.reasons)
