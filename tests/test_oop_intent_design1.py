"""OOP.INTENT.DESIGN.1: explicit future intent without implementation authority."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import io
import json
import os
import socket
import subprocess

import pytest

from core.explicit_design_evidence import (
    DesignEvidence, EvidenceSpan, InheritanceCommitment,
    MAX_DESIGN_EVIDENCE_BYTES, MAX_DESIGN_ITEMS, MAX_DESIGN_SCAN_CHARS,
    extract_design_evidence,
)
from core.explicit_evidence import extract_explicit_evidence
from core.input_understanding import understand_request
from core.proposed_design_intent import project_proposed_design_intent
from core.requirement_preservation import check_requirement_preservation
from core.semantic_waiter import ExplicitEvidenceInterpreter, StaticSemanticInterpreter
from core.task_contract import RawRequest


BANK2_TASK = """SavingAccount extends BankAccount.

savingBalance should belong only to SavingAccount,
because not every BankAccount needs savings state.

Using the savings functionality should depend on the user
entering the correct password.

The current code does not yet contain password/authentication support."""


def _interpret(text=BANK2_TASK):
    return ExplicitEvidenceInterpreter().interpret(text, extract_explicit_evidence(text))


def _project(text=BANK2_TASK):
    return project_proposed_design_intent(understand_request(text))


def _commitments(projection):
    return (projection.relationships + projection.state_commitments
            + projection.behavior_gates + projection.explicit_absences)


def test_bank2_exact_task_has_all_four_explicit_commitments():
    contract = understand_request(BANK2_TASK)
    projection = project_proposed_design_intent(contract)
    assert contract.raw_request.text == BANK2_TASK
    assert contract.preservation.passed
    assert projection.status == "resolved"
    assert len(projection.relationships) == 1
    assert len(projection.state_commitments) == 1
    assert len(projection.behavior_gates) == 1
    assert len(projection.explicit_absences) == 1
    relation = projection.relationships[0]
    assert (relation.child, relation.parent) == ("SavingAccount", "BankAccount")
    assert relation.as_dict()["relationship_kind"] == "inheritance"
    state = projection.state_commitments[0]
    assert (state.state, state.owner) == ("savingBalance", "SavingAccount")
    assert state.ownership_constraint == "subclass_only"
    assert state.base_exclusion == "BankAccount"
    gate = projection.behavior_gates[0]
    assert gate.gated_behavior == "savings functionality"
    assert gate.condition == "successful_password_verification"
    assert projection.explicit_absences[0].subject == "authentication_support"


def test_every_bank2_commitment_preserves_exact_human_span_and_provenance():
    projection = _project()
    for record in _commitments(projection):
        evidence = record.evidence
        assert evidence.provenance == "explicit_human"
        assert BANK2_TASK[evidence.source_start:evidence.source_end] == evidence.source_text
    assert projection.state_commitments[0].base_exclusion_provenance == "inferred_semantic_interpretation"


@pytest.mark.parametrize(("text", "field"), [
    ("SavingAccount extends BankAccount.", "relationships"),
    ("savingBalance belongs only to SavingAccount.", "state_commitments"),
    ("savings functionality requires correct password verification.", "behavior_gates"),
    ("The current code does not yet contain password/authentication support.", "explicit_absences"),
])
def test_individual_explicit_commitments_survive_intake(text, field):
    projection = _project(text)
    assert len(getattr(projection, field)) == 1
    assert len(_commitments(projection)) == 1


def test_subclass_only_state_does_not_guess_a_base_without_relationship():
    projection = _project("savingBalance belongs only to SavingAccount.")
    assert projection.state_commitments[0].base_exclusion is None
    assert not projection.relationships


def test_exact_identifier_case_is_preserved():
    projection = _project("savingACCOUNT extends BANKaccount. savingBALANCE belongs only to savingACCOUNT.")
    assert (projection.relationships[0].child, projection.relationships[0].parent) == ("savingACCOUNT", "BANKaccount")
    assert (projection.state_commitments[0].state, projection.state_commitments[0].owner) == ("savingBALANCE", "savingACCOUNT")
    assert projection.state_commitments[0].base_exclusion == "BANKaccount"


@pytest.mark.parametrize("text", [
    "Would inheritance make sense here?",
    "Should SavingAccount extend BankAccount?",
    "Could SavingAccount extend BankAccount?",
    "BankAccount should contain a Savings component.",
    "SavingAccount extends.",
    "extends BankAccount.",
    "The password reset help text needs a spelling correction.",
    "Do not make SavingAccount extend BankAccount.",
    "SavingAccount must not extend BankAccount.",
    "Maybe SavingAccount should extend BankAccount.",
    "If SavingAccount extends BankAccount, what would happen?",
    "A tutorial says 'SavingAccount extends BankAccount'. Evaluate this example.",
    "savings functionality does not require correct password verification.",
    "Do not require correct password verification.",
    "Do not require correct password verification for savings functionality.",
])
def test_questions_composition_negation_and_mentions_are_not_commitments(text):
    assert not _commitments(_project(text))


def test_inheritance_discussion_is_evaluative_not_a_decision():
    projection = _project("Would inheritance make sense here?")
    assert projection.status == "unresolved"
    assert projection.evaluative
    assert not projection.relationships


@pytest.mark.parametrize("text", [
    "class SavingAccount extends BankAccount {}",
    "Existing source:\nclass SavingAccount extends BankAccount {}",
    "```java\nclass SavingAccount extends BankAccount {}\n```",
    "```text\nSavingAccount extends BankAccount.\n```",
])
def test_source_declarations_and_fenced_examples_are_not_future_intent(text):
    assert not _commitments(_project(text))


def test_current_and_desired_state_are_explicitly_separate():
    payload = _project().as_dict()
    assert payload["current_source_status"] == "not_acquired_by_projection"
    assert payload["temporal_scope"] == {
        "relationships": "desired_future_design",
        "state_commitments": "desired_future_design",
        "behavior_gates": "desired_future_design",
        "explicit_absences": "human_assertion_about_current_state",
    }


@pytest.mark.parametrize("text", [
    "SavingAccount extends BankAccount. Do not use inheritance.",
    "SavingAccount extends BankAccount. SavingAccount extends OtherAccount.",
    "savingBalance belongs only to SavingAccount. savingBalance belongs only to OtherAccount.",
])
def test_contradictions_retain_both_evidence_paths_without_choosing(text):
    projection = _project(text)
    assert projection.status == "conflict"
    assert projection.conflicts
    assert len(projection.conflicts[0].evidence) >= 2
    assert projection.authority == "read_only"


def test_bank2_unresolved_dimensions_are_relevant_and_have_no_selected_values():
    dimensions = {item.dimension: item for item in _project().unresolved_dimensions}
    assert {
        "credential_ownership", "credential_source", "credential_persistence",
        "credential_verification_mechanism", "verification_failure_behavior",
        "verification_lifecycle", "savings_funding_semantics", "savings_interest_semantics",
        "source_layout",
    } <= set(dimensions)
    for dimension in dimensions.values():
        assert dimension.status == "unspecified"
        assert dimension.basis
        assert dimension.provenance == "inferred_semantic_interpretation"
        assert not hasattr(dimension, "value")
    assert not {"oauth_provider", "database", "hash_algorithm"}.intersection(dimensions)


def test_irrelevant_task_does_not_get_speculative_design_dimensions():
    projection = _project("Correct the documentation spelling.")
    assert not _commitments(projection)
    assert not projection.unresolved_dimensions


def test_commitment_records_have_no_implementation_defaults():
    projection = _project()
    forbidden_fields = {
        "storage", "database", "hash_algorithm", "salts", "retry_policy", "lockout",
        "password_owner", "session", "constructor", "filename", "package", "visibility",
        "initializer", "type", "transfer", "interest_rate", "creation_timing",
    }
    for record in _commitments(projection):
        assert not forbidden_fields.intersection(field.name for field in fields(record))
    assert "SavingAccount.java" not in projection.to_json()
    assert "savingsBalance" not in projection.to_json()


def test_raw_contract_and_interpretation_are_unchanged_by_projection():
    interpretation = _interpret()
    contract = understand_request(BANK2_TASK, interpreter=StaticSemanticInterpreter(interpretation))
    before_contract, before_interpretation = contract.as_dict(), interpretation.as_dict()
    assert _commitments(project_proposed_design_intent(contract, interpretation=interpretation))
    assert contract.as_dict() == before_contract
    assert interpretation.as_dict() == before_interpretation
    assert contract.raw_request.text == BANK2_TASK


def test_projection_is_deterministic_and_bound_to_raw_contract_and_interpretation():
    interpretation = _interpret()
    contract = understand_request(BANK2_TASK, interpreter=StaticSemanticInterpreter(interpretation))
    first = project_proposed_design_intent(contract, interpretation=interpretation)
    second = project_proposed_design_intent(contract, interpretation=interpretation)
    assert first == second
    assert first.to_json() == second.to_json()
    assert first.fingerprint == second.fingerprint
    assert first.raw_request_fingerprint == hashlib.sha256(BANK2_TASK.encode("utf-8")).hexdigest()
    assert len(first.task_contract_fingerprint) == 64
    assert len(first.semantic_interpretation_fingerprint) == 64
    assert first.fingerprint == hashlib.sha256(first.to_json().encode("utf-8")).hexdigest()
    changed = project_proposed_design_intent(replace(contract, notes=contract.notes + ("extra semantic note",)))
    assert changed.task_contract_fingerprint != first.task_contract_fingerprint
    assert changed.fingerprint != first.fingerprint


def test_projection_and_nested_collections_are_immutable():
    projection = _project()
    with pytest.raises(FrozenInstanceError):
        projection.status = "conflict"
    with pytest.raises(FrozenInstanceError):
        projection.relationships[0].child = "Other"
    with pytest.raises(FrozenInstanceError):
        projection.relationships[0].evidence.provenance = "current_source_fact"
    for field in ("relationships", "state_commitments", "behavior_gates", "unresolved_dimensions"):
        assert isinstance(getattr(projection, field), tuple)
    detached = projection.as_dict()
    detached["relationships"][0]["child"] = "Other"
    assert projection.relationships[0].child == "SavingAccount"


def test_preservation_rejects_dropped_rewritten_and_invented_design_evidence():
    evidence, interpretation = extract_explicit_evidence(BANK2_TASK), _interpret()
    dropped = replace(interpretation, design_evidence=DesignEvidence())
    assert not check_requirement_preservation(evidence, dropped).passed
    relation = interpretation.design_evidence.relationships[0]
    rewritten = replace(interpretation, design_evidence=replace(
        interpretation.design_evidence, relationships=(replace(relation, child="OtherAccount"),),
    ))
    assert not check_requirement_preservation(evidence, rewritten).passed
    plain_evidence = extract_explicit_evidence("Review the design.")
    invented = replace(_interpret("Review the design."), design_evidence=interpretation.design_evidence)
    assert not check_requirement_preservation(plain_evidence, invented).passed


def test_failed_preservation_has_no_projected_commitments():
    dropped = replace(_interpret(), design_evidence=DesignEvidence())
    contract = understand_request(BANK2_TASK, interpreter=StaticSemanticInterpreter(dropped))
    assert not contract.preservation.passed
    assert not contract.routing_allowed
    projection = project_proposed_design_intent(contract)
    assert projection.status == "unavailable"
    assert not _commitments(projection)


def test_projection_refuses_mismatched_optional_interpretation():
    projection = project_proposed_design_intent(understand_request(BANK2_TASK), interpretation=_interpret("Other extends Parent."))
    assert projection.status == "unavailable"
    assert not _commitments(projection)


def test_rebinding_the_raw_request_invalidates_existing_evidence():
    contract = replace(understand_request(BANK2_TASK), raw_request=RawRequest("A different request."))
    projection = project_proposed_design_intent(contract)
    assert projection.status == "unavailable"
    assert not _commitments(projection)


def test_extractor_bounds_report_overflow_without_claiming_complete_evidence():
    text = "\n".join(f"Child{i} extends Parent{i}." for i in range(MAX_DESIGN_ITEMS + 1))
    evidence = extract_design_evidence(text)
    assert "relationships" in evidence.overflow
    assert len(evidence.relationships) <= MAX_DESIGN_ITEMS
    projection = _project(text)
    assert projection.status == "bounded"
    assert not _commitments(projection)
    assert len(json.dumps(evidence.as_dict()).encode("utf-8")) <= MAX_DESIGN_EVIDENCE_BYTES


def test_scan_bounds_preserve_the_entire_raw_request():
    text = "SavingAccount extends BankAccount.\n" + "x" * MAX_DESIGN_SCAN_CHARS
    evidence = extract_design_evidence(text)
    baseline = understand_request("Review the design.")
    contract = replace(baseline, raw_request=RawRequest(text), design_evidence=evidence,
                       explicit_evidence=replace(baseline.explicit_evidence, design_evidence=evidence))
    assert contract.raw_request.text == text
    assert "scanned_text" in contract.design_evidence.overflow
    projection = project_proposed_design_intent(contract)
    assert projection.status == "bounded"
    assert not _commitments(projection)


def test_projection_consumes_typed_boundary_without_reextracting(monkeypatch):
    import core.explicit_design_evidence as design_extractor
    import core.explicit_evidence as explicit_extractor
    contract = understand_request(BANK2_TASK)

    def forbidden(*args, **kwargs):
        raise AssertionError("the projection must consume the already typed contract")

    monkeypatch.setattr(design_extractor, "extract_design_evidence", forbidden)
    monkeypatch.setattr(explicit_extractor, "extract_explicit_evidence", forbidden)
    assert len(_commitments(project_proposed_design_intent(contract))) == 4


def test_projection_has_zero_filesystem_network_execution_or_model_side_effects(monkeypatch):
    from core.semantic_waiter_adapter import SemanticWaiterModelAdapter
    contract = understand_request(BANK2_TASK)

    def forbidden(*args, **kwargs):
        raise AssertionError("design projection cannot acquire context, execute, or call a model")

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr(io, "open", forbidden)
        guard.setattr(os, "walk", forbidden)
        guard.setattr(os, "scandir", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(subprocess, "run", forbidden)
        guard.setattr(SemanticWaiterModelAdapter, "_complete", forbidden)
        projection = project_proposed_design_intent(contract)
    assert len(_commitments(projection)) == 4
    assert projection.authority == "read_only"
    for name in ("write_authority", "execution_authority", "apply_authority", "repair_scope_authority"):
        assert getattr(projection, name) is False
        with pytest.raises((TypeError, ValueError)):
            replace(projection, **{name: True})


def test_unsupported_extra_design_decision_is_not_claimed_to_be_unspecified():
    task = BANK2_TASK + "\nDo not persist credentials across runs."
    contract = understand_request(task)
    assert contract.design_evidence.unclassified_clauses_present
    projection = project_proposed_design_intent(contract)
    assert len(_commitments(projection)) == 4
    dimensions = {item.dimension: item for item in projection.unresolved_dimensions}
    assert dimensions["credential_persistence"].status == "not_resolved_by_projection"
    assert contract.raw_request.text == task


def test_unrelated_state_does_not_invent_savings_funding_or_interest_dimensions():
    task = ("SavingAccount extends BankAccount. auditCount belongs only to SavingAccount. "
            "savings functionality requires correct password verification.")
    projection = _project(task)
    assert projection.state_commitments[0].state_role is None
    dimensions = {item.dimension for item in projection.unresolved_dimensions}
    assert "credential_verification_mechanism" in dimensions
    assert not {"savings_funding_semantics", "savings_interest_semantics"}.intersection(dimensions)


def test_model_adapter_carries_intake_design_without_an_extra_model_call():
    from core.semantic_waiter_adapter import (
        ALLOWED_RESPONSE_KEYS, ScriptedSemanticModelClient, SemanticWaiterModelAdapter,
    )
    expected = _interpret()
    payload = expected.as_dict()
    payload["user_supplied_framework"] = payload.pop("framework")
    response = json.dumps({key: value for key, value in payload.items() if key in ALLOWED_RESPONSE_KEYS})
    client = ScriptedSemanticModelClient([response, response])
    adapter = SemanticWaiterModelAdapter(client)
    evidence = extract_explicit_evidence(BANK2_TASK)
    interpretation = adapter.interpret(BANK2_TASK, evidence)
    assert adapter.call_count == len(client.calls) == 1
    assert interpretation.design_evidence is evidence.design_evidence
    contract = understand_request(BANK2_TASK, interpreter=StaticSemanticInterpreter(interpretation))
    assert contract.preservation.passed
    projection = project_proposed_design_intent(contract, interpretation=interpretation)
    assert len(_commitments(projection)) == 4
    assert adapter.call_count == len(client.calls) == 1
    repaired = adapter.repair(BANK2_TASK, evidence, contract.preservation)
    assert repaired.design_evidence is evidence.design_evidence
    assert adapter.call_count == len(client.calls) == 2
    assert "design_evidence" not in ALLOWED_RESPONSE_KEYS


def test_live_interpreter_carries_design_and_projection_does_not_change_execution_needs():
    from core.live_task_shape import LiveTaskFieldsInterpreter
    evidence = extract_explicit_evidence(BANK2_TASK)
    interpreter = LiveTaskFieldsInterpreter(repository_available=True)
    interpretation = interpreter.interpret(BANK2_TASK, evidence)
    assert interpretation.design_evidence is evidence.design_evidence
    contract = understand_request(BANK2_TASK, interpreter=interpreter)
    before = contract.execution_requirements.as_dict()
    assert len(_commitments(project_proposed_design_intent(contract))) == 4
    assert contract.execution_requirements.as_dict() == before
    assert contract.execution_requirements.repository_inspection_required


@pytest.mark.parametrize("provenance", ["current_source_fact", "inferred_semantic_interpretation"])
def test_nonhuman_evidence_cannot_be_laundered_as_a_human_commitment(provenance):
    contract = understand_request("SavingAccount extends BankAccount.")
    relation = contract.design_evidence.relationships[0]
    evidence = replace(contract.design_evidence, relationships=(replace(
        relation, evidence=replace(relation.evidence, provenance=provenance)),))
    contract = replace(contract, design_evidence=evidence,
                       explicit_evidence=replace(contract.explicit_evidence, design_evidence=evidence))
    projection = project_proposed_design_intent(contract)
    assert projection.status == "unavailable"
    assert not _commitments(projection)
    assert "explicit_evidence_binding_mismatch" in projection.reasons


def test_projection_byte_bound_fails_closed_instead_of_truncating(monkeypatch):
    import core.proposed_design_intent as projection_module
    monkeypatch.setattr(projection_module, "MAX_SERIALIZED_BYTES", 4096)
    projection = _project()
    assert projection.status == "bounded"
    assert not _commitments(projection)
    assert projection.overflow
    assert len(projection.to_json().encode("utf-8")) <= 4096


@pytest.mark.parametrize(("field", "limit"), [
    ("relationships", 16), ("state_commitments", 16), ("behavior_gates", 8),
    ("explicit_absences", 8), ("unresolved_dimensions", 11),
])
def test_projection_collection_bounds_cannot_silently_drop_items(field, limit):
    projection = _project()
    with pytest.raises(ValueError, match="bound"):
        replace(projection, **{field: (getattr(projection, field)[0],) * (limit + 1)})


def test_evidence_serialized_byte_bound_rejects_an_oversized_record():
    from core.explicit_design_evidence import BehaviorGate, ExplicitAbsence, StateOwnershipCommitment
    span = EvidenceSpan("x" * 600, 0, 600)
    with pytest.raises(ValueError, match="serialized byte bound"):
        DesignEvidence(
            relationships=(InheritanceCommitment("Child", "Parent", span),) * MAX_DESIGN_ITEMS,
            state_commitments=(StateOwnershipCommitment("value", "Child", span),) * MAX_DESIGN_ITEMS,
            behavior_gates=(BehaviorGate("savings functionality", "successful_password_verification", span),) * MAX_DESIGN_ITEMS,
            explicit_absences=(ExplicitAbsence("authentication_support", span),) * MAX_DESIGN_ITEMS,
        )


@pytest.mark.parametrize("text", [
    "Existing savings functionality requires correct password verification.",
    "Current savings functionality requires correct password verification.",
    "savings functionality already requires correct password verification.",
])
def test_assertions_about_current_behavior_do_not_become_future_gates(text):
    assert not _project(text).behavior_gates


def test_nested_mutable_evidence_and_basis_collections_are_rejected():
    projection = _project()
    with pytest.raises((TypeError, ValueError)):
        replace(projection.state_commitments[0], basis=["mutable"])
    with pytest.raises((TypeError, ValueError)):
        replace(projection.unresolved_dimensions[0], basis=["mutable"])
    conflict = _project("SavingAccount extends BankAccount. Do not use inheritance.").conflicts[0]
    with pytest.raises((TypeError, ValueError)):
        replace(conflict, evidence=list(conflict.evidence))
    with pytest.raises((TypeError, ValueError)):
        replace(projection, reasons=["mutable"])
    with pytest.raises((TypeError, ValueError)):
        replace(projection, relationships=list(projection.relationships))


def test_raw_design_words_cannot_replace_missing_typed_semantic_evidence():
    baseline = understand_request("Review the design.")
    contract = replace(baseline, raw_request=RawRequest(BANK2_TASK))
    projection = project_proposed_design_intent(contract)
    assert projection.status == "unavailable"
    assert not _commitments(projection)
    assert not projection.unresolved_dimensions


@pytest.mark.parametrize("text", [
    "\n".join(f"value{i} belongs only to Owner{i}." for i in range(MAX_DESIGN_ITEMS + 1)),
    "\n".join(f"operation{i} requires correct password verification." for i in range(9)),
])
def test_runtime_state_and_gate_overflow_return_bounded_projection(text):
    projection = _project(text)
    assert projection.status == "bounded"
    assert projection.overflow
    assert not _commitments(projection)


def test_additive_transport_reconstructs_unchanged_historical_receipts():
    from pathlib import Path
    from tests._oop_intent_design1_maintenance import before_oop_intent_design1

    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/oop_intent_design1_reversal.json").read_text(encoding="utf-8"))
    frozen = json.loads((root / "tests/fixtures/data_undo1_frozen_boundaries.json").read_text(encoding="utf-8"))["sha256"]
    for record in receipt["reversals"]:
        relative = record["path"]
        reconstructed = before_oop_intent_design1(relative, (root / relative).read_bytes())
        assert hashlib.sha256(reconstructed).hexdigest() == frozen[relative]
