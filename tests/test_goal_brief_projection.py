"""INPUT.3 — Goal Brief projection tests.

The projection is a *view* of a contract, not a form.  These tests pin that it
invents nothing, keeps provenance and source on every value, asks for a field
only when the deterministic policy asked for it, and leaves a simple request
completely alone.
"""

from __future__ import annotations

import json

import pytest

from core.goal_brief_projection import (
    FIELD_NEEDED_BEFORE_HANDOFF,
    FIELD_NOT_COLLECTED,
    FIELD_PRESENT,
    FIELD_SUGGESTED_FOR_COMPLETION,
    SOURCE_EXPLICIT_EVIDENCE,
    SOURCE_RAW_REQUEST,
    SOURCE_TASK_CONTRACT,
    GoalBriefField,
    GoalBriefValue,
    project_goal_brief,
    render_goal_brief_projection_json,
)
from core.input_understanding import understand_request
from core.intake_completion import (
    GOAL_BRIEF_FIELDS,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    decide_intake_completion,
    present_brief_fields,
)
from core.semantic_waiter import SemanticInterpretation, StaticSemanticInterpreter
from core.task_contract import (
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Constraint,
    ExecutionRequirements,
    RequestedOutput,
    Subject,
    TaskClassification,
)


def _contract(text: str, **kwargs):
    kwargs.setdefault(
        "task", TaskClassification(type="unknown", provenance=PROVENANCE_INFERRED)
    )
    return understand_request(
        text, interpreter=StaticSemanticInterpreter(SemanticInterpretation(**kwargs))
    )


def _broad(text: str, **kwargs):
    kwargs.setdefault(
        "task", TaskClassification(type="implementation", provenance=PROVENANCE_INFERRED)
    )
    kwargs.setdefault(
        "execution_requirements",
        ExecutionRequirements(
            multi_stage=True,
            repository_inspection_required=True,
            local_repository_required=True,
            provenance=PROVENANCE_INFERRED,
        ),
    )
    return _contract(text, **kwargs)


def _project(contract):
    return project_goal_brief(contract, decide_intake_completion(contract))


# ══ shape ═════════════════════════════════════════════════════════════════════

def test_the_projection_always_carries_every_field_in_order():
    projection = _project(_contract("Explain what DeepSeek Harness is."))

    assert tuple(item.field for item in projection.fields) == GOAL_BRIEF_FIELDS
    assert GOAL_BRIEF_FIELDS == (
        "what",
        "why",
        "scope",
        "constraints",
        "stop_conditions",
        "validation",
        "desired_output",
    )


def test_what_is_the_users_own_words_and_never_a_paraphrase():
    prompt = "Explain what DeepSeek Harness is."
    projection = _project(_contract(prompt))

    what = projection.field("what")
    assert what.status == FIELD_PRESENT
    assert what.value == prompt
    assert what.entries[0].provenance == PROVENANCE_EXPLICIT
    assert what.entries[0].source == SOURCE_RAW_REQUEST


def test_scope_comes_from_literal_file_paths():
    projection = _project(_contract("Fix the typo 'teh' to 'the' in README.md."))

    scope = projection.field("scope")
    assert scope.status == FIELD_PRESENT
    assert scope.values == ("README.md",)
    assert scope.entries[0].source == SOURCE_EXPLICIT_EVIDENCE
    assert scope.entries[0].provenance == PROVENANCE_EXPLICIT


def test_constraints_keep_the_provenance_the_contract_gave_them():
    contract = _contract(
        "Analyze this architecture, but do not inspect tests.",
        constraints=(
            Constraint(
                kind="prohibition",
                text="Analyze this architecture, but do not inspect tests",
                provenance=PROVENANCE_EXPLICIT,
            ),
            Constraint(
                kind="requirement",
                text="keep the public API stable",
                provenance=PROVENANCE_INFERRED,
                confidence=0.6,
            ),
        ),
    )

    constraints = _project(contract).field("constraints")

    assert constraints.status == FIELD_PRESENT
    assert [entry.provenance for entry in constraints.entries] == [
        PROVENANCE_EXPLICIT,
        PROVENANCE_INFERRED,
    ]
    assert [entry.source for entry in constraints.entries] == [
        SOURCE_TASK_CONTRACT,
        SOURCE_TASK_CONTRACT,
    ]


def test_desired_output_projects_the_requested_format():
    contract = _contract(
        "Compare the options as a table.",
        requested_output=RequestedOutput(format="table", provenance=PROVENANCE_EXPLICIT),
    )

    desired = _project(contract).field("desired_output")

    assert desired.status == FIELD_PRESENT
    assert desired.value == "table"
    assert desired.entries[0].label == "requested_output"


def test_unsourced_fields_are_never_filled_in():
    """Nothing in the contract records purpose, stop conditions or validation."""
    projection = _project(_broad("Migrate the storage backend to PostgreSQL."))

    assert projection.field("why").entries == ()
    assert projection.field("stop_conditions").entries == ()
    assert projection.field("validation").entries == ()


# ══ status ════════════════════════════════════════════════════════════════════

def test_a_simple_request_asks_for_nothing():
    projection = _project(_contract("Explain what DeepSeek Harness is."))

    assert projection.needed_before_handoff() == ()
    for name in ("why", "stop_conditions", "validation"):
        assert projection.status(name) == FIELD_NOT_COLLECTED
    assert projection.goal_brief_offered is False


def test_a_broad_task_marks_scope_needed_and_the_soft_fields_suggested():
    contract = _broad("Migrate the storage backend to PostgreSQL.")
    decision = decide_intake_completion(contract)
    projection = project_goal_brief(contract, decision)

    assert decision.state == STATE_GOAL_BRIEF_ASSIST
    assert projection.status("scope") == FIELD_NEEDED_BEFORE_HANDOFF
    assert projection.status("validation") == FIELD_SUGGESTED_FOR_COMPLETION
    assert projection.status("stop_conditions") == FIELD_SUGGESTED_FOR_COMPLETION
    assert projection.status("why") == FIELD_NOT_COLLECTED
    assert projection.goal_brief_offered is True


def test_a_goal_brief_is_offered_and_never_required():
    projection = _project(_broad("Migrate the storage backend to PostgreSQL."))

    payload = projection.as_dict()
    assert payload["goal_brief_offered"] is True
    assert payload["goal_brief_required"] is False


def test_presence_agrees_with_the_policys_own_view():
    for contract in (
        _contract("Explain what DeepSeek Harness is."),
        _contract("Fix the typo 'teh' to 'the' in README.md."),
        _broad("Migrate the storage backend to PostgreSQL."),
    ):
        projection = _project(contract)
        present = {
            item.field for item in projection.fields if item.status == FIELD_PRESENT
        }
        assert present == set(present_brief_fields(contract))


def test_reported_gaps_are_carried_without_being_forced_into_a_field():
    contract = _broad(
        "Migrate the storage backend in storage/db.py.",
        missing_information=("which compatibility guarantee to keep",),
    )

    projection = _project(contract)

    assert projection.reported_gaps == ("which compatibility guarantee to keep",)
    assert projection.status("scope") == FIELD_PRESENT


# ══ invariants ════════════════════════════════════════════════════════════════

def test_a_field_may_not_hold_values_while_claiming_to_be_missing():
    value = GoalBriefValue(
        text="README.md", provenance=PROVENANCE_EXPLICIT, source=SOURCE_EXPLICIT_EVIDENCE
    )

    with pytest.raises(ValueError, match="carries values but is marked"):
        GoalBriefField(field="scope", status=FIELD_NEEDED_BEFORE_HANDOFF, entries=(value,))


def test_a_field_may_not_claim_presence_with_nothing_in_it():
    with pytest.raises(ValueError, match="marked present but carries no value"):
        GoalBriefField(field="scope", status=FIELD_PRESENT)


def test_a_value_may_not_invent_a_provenance():
    with pytest.raises(ValueError, match="unsupported provenance"):
        GoalBriefValue(text="x", provenance="guessed", source=SOURCE_TASK_CONTRACT)


def test_the_projection_rejects_a_foreign_decision_type():
    with pytest.raises(TypeError):
        project_goal_brief(_contract("hello"), "ready")  # type: ignore[arg-type]


# ══ serialization ═════════════════════════════════════════════════════════════

def test_the_projection_serializes_with_its_authority_block():
    projection = _project(_contract("Explain what DeepSeek Harness is."))

    payload = json.loads(render_goal_brief_projection_json(projection))

    assert payload["phase_id"] == "INPUT.3"
    assert payload["authority"]["execution_authority"] is False
    assert payload["authority"]["repository_write_authority"] is False
    assert len(payload["fields"]) == len(GOAL_BRIEF_FIELDS)


def test_canonical_values_expose_every_field_and_the_subjects():
    contract = _contract(
        "Analyze DeepSeek Harness.",
        subjects=(Subject(value="DeepSeek Harness", provenance=PROVENANCE_EXPLICIT),),
        task=TaskClassification(type="analysis", provenance=PROVENANCE_INFERRED),
    )

    canonical = _project(contract).canonical_values()

    assert canonical["task_type"] == "analysis"
    assert canonical["subjects"] == ["DeepSeek Harness"]
    assert set(canonical["fields"]) == set(GOAL_BRIEF_FIELDS)


def test_a_ready_projection_carries_no_asks_at_all():
    projection = _project(_contract("Explain what DeepSeek Harness is."))
    decision = decide_intake_completion(_contract("Explain what DeepSeek Harness is."))

    assert decision.state == STATE_READY
    statuses = {item.status for item in projection.fields}
    assert FIELD_NEEDED_BEFORE_HANDOFF not in statuses
    assert FIELD_SUGGESTED_FOR_COMPLETION not in statuses
