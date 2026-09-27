"""INPUT.3 — Intake Assistant boundary tests.

An assistant writes words.  These tests pin that the record it returns has
nowhere to put a decision, that the deterministic implementation always works
with no model at all, and that the boundary check refuses the remaining ways an
assistant could overstep.
"""

from __future__ import annotations

import json

import pytest

from core.goal_brief_projection import project_goal_brief
from core.input_understanding import understand_request
from core.intake_assistant import (
    ASSISTANCE_DETERMINISTIC,
    ASSISTANCE_GENERATED,
    ASSISTANCE_STATUS_NOT_CONFIGURED,
    ASSISTANCE_STATUS_OK,
    ASSISTANCE_STATUSES,
    DETERMINISTIC_ASSISTANT_NAME,
    MAX_ASSISTANCE_QUESTIONS,
    AssistanceQuestion,
    DeterministicIntakeAssistant,
    FieldSuggestion,
    IntakeAssistance,
    IntakeAssistanceRejected,
    IntakeAssistant,
    build_deterministic_questions,
    enforce_assistance_boundary,
    render_intake_assistance_json,
    state_headline,
)
from core.intake_completion import (
    STATE_ASK_CLARIFICATION,
    STATE_BLOCKED_CONTRADICTION,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    STATE_SEMANTIC_SYSTEM_FAILURE,
    decide_intake_completion,
)
from core.semantic_waiter import SemanticInterpretation, StaticSemanticInterpreter
from core.semantic_waiter_runner import SEMANTIC_MODEL_UNAVAILABLE
from core.task_contract import (
    PROVENANCE_INFERRED,
    ExecutionRequirements,
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


def _bundle(contract, semantic_status=None):
    decision = decide_intake_completion(contract, semantic_status=semantic_status)
    return contract, decision, project_goal_brief(contract, decision)


# ══ the record cannot hold a decision ═════════════════════════════════════════

def test_assistance_has_no_field_that_could_change_a_decision():
    names = set(IntakeAssistance.__dataclass_fields__)

    assert names.isdisjoint(
        {
            "state",
            "owner",
            "ready",
            "ready_for_future_handoff",
            "resolved",
            "routing_allowed",
            "required_before_handoff",
            "missing_requirements",
            "ambiguities",
            "preservation_status",
        }
    )


def test_a_suggestion_may_never_claim_to_be_something_the_user_said():
    with pytest.raises(ValueError, match="may not claim provenance"):
        FieldSuggestion(field="validation", suggested_value="pytest", provenance="explicit")


def test_a_suggestion_is_serialized_as_explicitly_non_canonical():
    payload = FieldSuggestion(field="validation", suggested_value="pytest").as_dict()

    assert payload["provenance"] == ASSISTANCE_GENERATED
    assert payload["canonical"] is False


def test_assistance_may_not_claim_a_model_wrote_it_unless_one_did():
    with pytest.raises(ValueError, match="only claim a model wrote it"):
        IntakeAssistance(
            assistant_name="x",
            generated_by_model=True,
            status=ASSISTANCE_STATUS_NOT_CONFIGURED,
        )


def test_generated_suggestions_require_assistance_a_model_actually_wrote():
    with pytest.raises(ValueError, match="require assistance a model actually wrote"):
        IntakeAssistance(
            assistant_name="x",
            field_suggestions=(FieldSuggestion(field="validation", suggested_value="pytest"),),
            generated_by_model=False,
        )


def test_the_assistance_status_vocabulary_is_bounded():
    assert ASSISTANCE_STATUSES == (
        "intake_assistant_not_configured",
        "intake_assistant_ok",
        "intake_assistant_unavailable",
        "intake_assistance_invalid",
        "intake_assistance_rejected",
    )


# ══ deterministic assistant ═══════════════════════════════════════════════════

def test_the_deterministic_assistant_satisfies_the_protocol():
    assert isinstance(DeterministicIntakeAssistant(), IntakeAssistant)


def test_a_ready_request_is_asked_nothing():
    assistance = DeterministicIntakeAssistant().assist(
        *_bundle(_contract("Explain what DeepSeek Harness is."))
    )

    assert assistance.questions == ()
    assert assistance.field_suggestions == ()
    assert "intake preview" in assistance.summary


def test_a_simple_edit_is_not_interviewed():
    """No why, no where, no when, no how, no risk tolerance."""
    assistance = DeterministicIntakeAssistant().assist(
        *_bundle(_contract("Fix the typo 'teh' to 'the' in README.md."))
    )

    assert assistance.questions == ()


def test_an_ambiguity_yields_one_question_per_need():
    contract, decision, projection = _bundle(
        _contract(
            "Replace it with the other one.",
            ambiguities=("'it' has no resolvable referent", "'the other one' is unnamed"),
        )
    )
    assistance = DeterministicIntakeAssistant().assist(contract, decision, projection)

    assert decision.state == STATE_ASK_CLARIFICATION
    assert len(assistance.questions) == 2
    assert all(item.provenance == ASSISTANCE_DETERMINISTIC for item in assistance.questions)
    assert all(item.optional is False for item in assistance.questions)


def test_a_broad_task_gets_needed_questions_before_optional_ones():
    contract, decision, projection = _bundle(_broad("Migrate the storage backend."))
    assistance = DeterministicIntakeAssistant().assist(contract, decision, projection)

    assert decision.state == STATE_GOAL_BRIEF_ASSIST
    flags = [item.optional for item in assistance.questions]
    assert flags == sorted(flags)
    assert flags[0] is False


def test_a_system_failure_never_asks_the_user_to_restate_a_clear_request():
    contract, decision, projection = _bundle(
        _contract("Explain what DeepSeek Harness is."),
        semantic_status=SEMANTIC_MODEL_UNAVAILABLE,
    )
    assistance = DeterministicIntakeAssistant().assist(contract, decision, projection)

    assert decision.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert assistance.questions == ()
    assert "semantic interpreter failed" in assistance.summary
    assert "unclear" not in assistance.summary.lower()
    assert "clarify" not in assistance.summary.lower()


def test_a_blocked_contradiction_says_what_the_conflict_is():
    contract, decision, projection = _bundle(
        understand_request("You must modify the tests. You must not modify the tests.")
    )
    assistance = DeterministicIntakeAssistant().assist(contract, decision, projection)

    assert decision.state == STATE_BLOCKED_CONTRADICTION
    assert "cannot both hold" in assistance.summary
    assert "modify the tests" in assistance.summary


def test_every_state_has_an_honest_headline():
    for state in (
        STATE_READY,
        STATE_GOAL_BRIEF_ASSIST,
        STATE_ASK_CLARIFICATION,
        STATE_BLOCKED_CONTRADICTION,
        STATE_SEMANTIC_SYSTEM_FAILURE,
    ):
        assert state_headline(state)


def test_deterministic_questions_stay_within_the_bound():
    contract, decision, _ = _bundle(
        _broad("Migrate everything.", missing_information=tuple(f"g{i}" for i in range(8)))
    )

    assert len(build_deterministic_questions(decision)) <= MAX_ASSISTANCE_QUESTIONS


# ══ boundary enforcement ══════════════════════════════════════════════════════

def _ask_bundle():
    return _bundle(
        _contract("Replace it with the other one.", ambiguities=("'it' is unresolved",))
    )


def test_well_formed_assistance_passes_through_unchanged():
    _, decision, projection = _ask_bundle()
    assistance = IntakeAssistance(
        assistant_name="friendly",
        summary="Which component did you mean?",
        questions=(
            AssistanceQuestion(
                need_id=decision.ambiguities[0].need_id,
                text="When you say 'it', which component do you mean?",
                provenance=ASSISTANCE_GENERATED,
            ),
        ),
        generated_by_model=True,
        status=ASSISTANCE_STATUS_OK,
    )

    assert enforce_assistance_boundary(decision, projection, assistance) is assistance


def test_a_question_anchored_to_an_invented_need_is_refused():
    _, decision, projection = _ask_bundle()
    assistance = IntakeAssistance(
        assistant_name="friendly",
        questions=(AssistanceQuestion(need_id="missing:budget_1", text="What budget?"),),
    )

    with pytest.raises(IntakeAssistanceRejected, match="unknown need"):
        enforce_assistance_boundary(decision, projection, assistance)


def test_downgrading_a_needed_field_to_optional_is_refused():
    _, decision, projection = _bundle(_broad("Migrate the storage backend."))
    needed = decision.missing_requirements[0]
    assert needed.required

    assistance = IntakeAssistance(
        assistant_name="friendly",
        questions=(
            AssistanceQuestion(need_id=needed.need_id, text="Where?", optional=True),
        ),
    )

    with pytest.raises(IntakeAssistanceRejected, match="disagrees with the policy severity"):
        enforce_assistance_boundary(decision, projection, assistance)


def test_overwriting_a_canonical_value_is_refused():
    _, decision, projection = _bundle(_broad("Migrate the storage backend."))
    assistance = IntakeAssistance(
        assistant_name="friendly",
        field_suggestions=(
            FieldSuggestion(field="what", suggested_value="migrate the database"),
        ),
        generated_by_model=True,
        status=ASSISTANCE_STATUS_OK,
    )

    with pytest.raises(IntakeAssistanceRejected, match="already carries a canonical value"):
        enforce_assistance_boundary(decision, projection, assistance)


def test_asking_about_the_same_need_twice_is_refused():
    _, decision, projection = _ask_bundle()
    need_id = decision.ambiguities[0].need_id
    assistance = IntakeAssistance(
        assistant_name="friendly",
        questions=(
            AssistanceQuestion(need_id=need_id, text="Which one?"),
            AssistanceQuestion(need_id=need_id, text="Really, which one?"),
        ),
    )

    with pytest.raises(IntakeAssistanceRejected, match="more than once"):
        enforce_assistance_boundary(decision, projection, assistance)


def test_a_non_assistance_return_value_is_refused():
    _, decision, projection = _ask_bundle()

    with pytest.raises(IntakeAssistanceRejected, match="must return IntakeAssistance"):
        enforce_assistance_boundary(decision, projection, {"summary": "ready!"})


def test_suggesting_a_field_the_contract_lacks_is_allowed():
    _, decision, projection = _bundle(_broad("Migrate the storage backend."))
    assistance = IntakeAssistance(
        assistant_name="friendly",
        field_suggestions=(
            FieldSuggestion(field="validation", suggested_value="run the storage tests"),
        ),
        generated_by_model=True,
        status=ASSISTANCE_STATUS_OK,
    )

    assert enforce_assistance_boundary(decision, projection, assistance) is assistance


# ══ serialization ═════════════════════════════════════════════════════════════

def test_assistance_serializes_with_its_authority_block():
    assistance = DeterministicIntakeAssistant().assist(
        *_bundle(_broad("Migrate the storage backend."))
    )

    payload = json.loads(render_intake_assistance_json(assistance))

    assert payload["assistant_name"] == DETERMINISTIC_ASSISTANT_NAME
    assert payload["generated_by_model"] is False
    assert payload["status"] == ASSISTANCE_STATUS_NOT_CONFIGURED
    assert payload["authority"]["execution_authority"] is False
    assert "state" not in payload
