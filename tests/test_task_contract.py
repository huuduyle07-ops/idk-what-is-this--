"""INPUT.1 — Lossless Task Contract schema tests.

The Task Contract is the canonical intermediate representation for a user
request.  These tests pin the invariants that make it trustworthy: the raw
request survives verbatim, explicit values never masquerade as probabilistic
guesses, and routing stays closed unless preservation passed.
"""

from __future__ import annotations

import json

import pytest

from core.explicit_evidence import ExplicitEvidence
from core.task_contract import (
    CONTRACT_SCHEMA_VERSION,
    MAX_SUBJECTS,
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    PROVENANCES,
    RELATIONSHIP_TYPES,
    TASK_TYPES,
    Constraint,
    ExecutionRequirements,
    PreservationItem,
    PreservationReport,
    RawRequest,
    Relationship,
    RequestedOutput,
    Subject,
    TaskClassification,
    TaskContract,
    UserSuppliedFramework,
    render_task_contract_json,
)


def _contract(**overrides):
    base = {
        "raw_request": RawRequest(text="Compare A against B"),
        "task": TaskClassification(type="comparative_analysis", provenance=PROVENANCE_INFERRED),
        "subjects": (
            Subject(value="A", provenance=PROVENANCE_EXPLICIT),
            Subject(value="B", provenance=PROVENANCE_EXPLICIT),
        ),
        "relationships": (
            Relationship(type="comparison", subjects=("A", "B"), provenance=PROVENANCE_EXPLICIT),
        ),
        "explicit_evidence": ExplicitEvidence(),
        "preservation": PreservationReport(status=PRESERVATION_PASSED),
        "routing_allowed": True,
    }
    base.update(overrides)
    return TaskContract(**base)


# ── raw request ───────────────────────────────────────────────────────────────

def test_raw_request_keeps_text_verbatim():
    original = "  Analyze X against Y\n\n- one\n- two\n"
    request = RawRequest(text=original)

    assert request.text == original


def test_raw_request_reports_length_and_digest():
    request = RawRequest(text="abc")

    assert request.char_count == 3
    assert len(request.sha256) == 64
    assert request.sha256 == RawRequest(text="abc").sha256


def test_raw_request_digest_changes_with_text():
    assert RawRequest(text="abc").sha256 != RawRequest(text="abd").sha256


def test_raw_request_rejects_non_string():
    with pytest.raises(TypeError):
        RawRequest(text=None)  # type: ignore[arg-type]


# ── provenance invariants ─────────────────────────────────────────────────────

def test_provenance_vocabulary_is_explicit_and_inferred():
    assert PROVENANCES == (PROVENANCE_EXPLICIT, PROVENANCE_INFERRED)


def test_explicit_subject_may_not_carry_a_probabilistic_confidence():
    with pytest.raises(ValueError):
        Subject(value="A", provenance=PROVENANCE_EXPLICIT, confidence=0.97)


def test_explicit_subject_confidence_defaults_to_none():
    assert Subject(value="A", provenance=PROVENANCE_EXPLICIT).confidence is None


def test_inferred_subject_may_carry_a_confidence():
    assert Subject(value="A", provenance=PROVENANCE_INFERRED, confidence=0.5).confidence == 0.5


def test_inferred_confidence_must_be_within_zero_and_one():
    with pytest.raises(ValueError):
        Subject(value="A", provenance=PROVENANCE_INFERRED, confidence=1.4)


def test_unknown_provenance_is_rejected():
    with pytest.raises(ValueError):
        Subject(value="A", provenance="guessed")


def test_explicit_constraint_may_not_carry_confidence():
    with pytest.raises(ValueError):
        Constraint(
            kind="prohibition",
            text="do not modify tests",
            provenance=PROVENANCE_EXPLICIT,
            confidence=0.9,
        )


def test_explicit_framework_may_not_carry_confidence_field_semantics():
    framework = UserSuppliedFramework(
        type="framework",
        values=("a", "b"),
        provenance=PROVENANCE_EXPLICIT,
        ordered=True,
    )

    assert framework.provenance == PROVENANCE_EXPLICIT
    assert framework.values == ("a", "b")


# ── bounded vocabularies ──────────────────────────────────────────────────────

def test_task_type_must_be_known():
    with pytest.raises(ValueError):
        TaskClassification(type="teleportation", provenance=PROVENANCE_INFERRED)


def test_relationship_type_must_be_known():
    with pytest.raises(ValueError):
        Relationship(type="rhymes_with", subjects=("A", "B"), provenance=PROVENANCE_EXPLICIT)


def test_comparison_relationship_needs_two_subjects():
    with pytest.raises(ValueError):
        Relationship(type="comparison", subjects=("A",), provenance=PROVENANCE_EXPLICIT)


def test_comparative_analysis_and_comparison_are_in_the_vocabularies():
    assert "comparative_analysis" in TASK_TYPES
    assert "comparison" in RELATIONSHIP_TYPES


def test_subjects_are_bounded():
    too_many = tuple(
        Subject(value=f"s{n}", provenance=PROVENANCE_EXPLICIT) for n in range(MAX_SUBJECTS + 1)
    )
    with pytest.raises(ValueError):
        _contract(subjects=too_many)


# ── preservation / routing invariant ──────────────────────────────────────────

def test_routing_is_allowed_when_preservation_passed():
    assert _contract().routing_allowed is True


def test_routing_may_not_be_allowed_when_preservation_failed():
    failed = PreservationReport(
        status=PRESERVATION_FAILED,
        missing_items=(PreservationItem(kind="subject", value="B"),),
        reasons=("explicit subject 'B' is missing",),
    )
    with pytest.raises(ValueError):
        _contract(preservation=failed, routing_allowed=True)


def test_failed_preservation_with_closed_routing_is_constructible():
    failed = PreservationReport(
        status=PRESERVATION_FAILED,
        missing_items=(PreservationItem(kind="subject", value="B"),),
        reasons=("explicit subject 'B' is missing",),
    )
    contract = _contract(preservation=failed, routing_allowed=False)

    assert contract.routing_allowed is False


def test_preservation_report_exposes_missing_lookups():
    report = PreservationReport(
        status=PRESERVATION_FAILED,
        preserved_items=(PreservationItem(kind="subject", value="A"),),
        missing_items=(PreservationItem(kind="framework_value", value="Orthogonal"),),
        reasons=("rubric value dropped",),
    )

    assert report.has_missing("framework_value") is True
    assert report.has_missing("subject") is False
    assert report.missing_values("framework_value") == ("Orthogonal",)


def test_preservation_failure_requires_a_reason():
    with pytest.raises(ValueError):
        PreservationReport(
            status=PRESERVATION_FAILED,
            missing_items=(PreservationItem(kind="subject", value="B"),),
        )


def test_preservation_pass_may_not_list_missing_items():
    with pytest.raises(ValueError):
        PreservationReport(
            status=PRESERVATION_PASSED,
            missing_items=(PreservationItem(kind="subject", value="B"),),
            reasons=("dropped",),
        )


# ── serialization ─────────────────────────────────────────────────────────────

def test_contract_dict_carries_schema_version_and_raw_text():
    payload = _contract().as_dict()

    assert payload["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert payload["raw_request"]["text"] == "Compare A against B"


def test_contract_dict_declares_no_execution_authority():
    guardrails = _contract().as_dict()["guardrails"]

    for flag in (
        "execution_performed",
        "mode_dispatch_performed",
        "repository_scan_performed",
        "patch_generation_performed",
        "patch_application_performed",
        "validation_run",
        "benchmark_run_performed",
        "dream_run_performed",
        "project_evolution_run_performed",
        "model_call_performed",
        "provider_selected",
        "network_call_performed",
        "read_authority",
        "write_authority",
    ):
        assert guardrails[flag] is False, flag
    assert guardrails["human_approval_required"] is True


def test_contract_json_is_deterministic_and_round_trips():
    contract = _contract()

    first = render_task_contract_json(contract)
    second = render_task_contract_json(contract)

    assert first == second
    assert json.loads(first)["task"]["type"] == "comparative_analysis"


def test_execution_requirements_default_to_false_and_inferred():
    requirements = ExecutionRequirements()

    assert requirements.provenance == PROVENANCE_INFERRED
    assert requirements.multi_stage is False
    assert requirements.external_information_required is False
    assert requirements.repository_inspection_required is False
    assert requirements.local_repository_required is False


def test_requested_output_format_must_be_known():
    with pytest.raises(ValueError):
        RequestedOutput(format="interpretive_dance", provenance=PROVENANCE_EXPLICIT)
