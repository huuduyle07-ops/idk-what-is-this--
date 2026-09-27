"""INPUT.3 — end-to-end intake completion tests.

Two things are proved here.

The **behaviour matrix**: a simple request passes straight through, a broad one
is offered structured assistance, a genuinely ambiguous one is asked exactly one
question, and a model failure is reported as the system's problem rather than
the user's.

The **zero-model equivalence**: the same contract run with and without a local
intake assistant produces byte-identical canonical results.  If a local model
can flip READY into ASK_CLARIFICATION, INPUT.3 has failed regardless of how
friendly the wording became.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from core.input_completion import (
    INTAKE_COMPLETION_STAGES,
    IntakeCompletionOutcome,
    canonical_intake_fingerprint,
    complete_intake,
    complete_intake_from_semantic_outcome,
    render_intake_completion_json,
)
from core.input_understanding import understand_request
from core.intake_assistant import (
    ASSISTANCE_STATUS_NOT_CONFIGURED,
    ASSISTANCE_STATUS_OK,
    ASSISTANCE_STATUS_REJECTED,
    ASSISTANCE_STATUS_UNAVAILABLE,
    IntakeAssistance,
)
from core.intake_completion import (
    OWNER_EXPLICIT_CONSTRAINT_CONFLICT,
    OWNER_OPERATIONAL_DETAIL_MISSING,
    OWNER_SEMANTIC_SYSTEM_FAILURE,
    OWNER_USER_MEANING_AMBIGUITY,
    STATE_ASK_CLARIFICATION,
    STATE_BLOCKED_CONTRADICTION,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    STATE_SEMANTIC_SYSTEM_FAILURE,
)
from core.local_intake_assistant import (
    LocalModelIntakeAssistant,
    ScriptedIntakeAssistantClient,
)
from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_runner import (
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_MODEL_UNAVAILABLE,
    SemanticWaiterOutcome,
    understand_request_semantically,
)
from core.task_contract import PRESERVATION_FAILED, PreservationReport


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

BROAD_EXECUTION = {
    "multi_stage": True,
    "repository_inspection_required": True,
    "local_repository_required": True,
}


class _DeadSemanticClient:
    """A configured model that cannot be reached."""

    model_id = "unreachable-model"

    def complete(self, system_instruction, user_message):
        raise TimeoutError("the semantic model did not answer")


def _semantic(prompt: str, *payloads: dict):
    """Run one request through INPUT.2 with a scripted model."""
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([json.dumps(item) for item in payloads])
    )
    return understand_request_semantically(prompt, adapter=adapter)


def _assistant(payload: dict | str):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return LocalModelIntakeAssistant(ScriptedIntakeAssistantClient([raw]))


def _healthy_dogfood_interpretation() -> dict:
    return {
        "task": {"type": "comparative_analysis", "provenance": "inferred"},
        "subjects": [
            {"value": "DeepSeek Harness", "provenance": "explicit"},
            {"value": "C.A.T.T.U.S", "provenance": "explicit"},
        ],
        "relationships": [
            {
                "type": "comparison",
                "subjects": ["DeepSeek Harness", "C.A.T.T.U.S"],
                "provenance": "explicit",
            }
        ],
        "user_supplied_framework": {
            "type": "framework",
            "values": [
                "Equivalent",
                "DeepSeek stronger",
                "C.A.T.T.U.S stronger",
                "Orthogonal",
                "Not worth adopting",
            ],
            "provenance": "explicit",
            "ordered": True,
        },
        "constraints": [
            {
                "kind": "framework_reference",
                "text": "Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:",
                "provenance": "explicit",
            }
        ],
        "execution_requirements": {"multi_stage": True},
    }


def _without_authority(value):
    """Strip the authority blocks, which name powers in order to deny them."""
    if isinstance(value, dict):
        return {
            key: _without_authority(item)
            for key, item in value.items()
            if key != "authority"
        }
    if isinstance(value, list):
        return [_without_authority(item) for item in value]
    return value


# ══ A — a simple explanation passes straight through ══════════════════════════

def test_case_a_simple_explanation_is_ready_with_no_questions():
    outcome = complete_intake(understand_request("Explain what DeepSeek Harness is."))

    assert outcome.state == STATE_READY
    assert outcome.owner is None
    assert outcome.ready_for_future_handoff is False
    assert outcome.decision.handoff_blockers == ("semantic_receipt_missing",)
    assert outcome.goal_brief_offered is False
    assert outcome.questions() == ()


def test_case_a_holds_under_a_model_backed_interpretation():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Explain what DeepSeek Harness is.",
            {
                "task": {"type": "question", "provenance": "inferred"},
                "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
            },
        )
    )

    assert outcome.state == STATE_READY
    assert outcome.decision.semantic_status == SEMANTIC_INTERPRETATION_OK
    assert outcome.decision.semantic_evidence_valid is True
    assert outcome.ready_for_future_handoff is True


# ══ B — a simple edit is not interviewed ══════════════════════════════════════

def test_case_b_a_typo_fix_is_ready_and_never_interviewed():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Fix the typo 'teh' to 'the' in README.md.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [{"value": "README.md", "provenance": "explicit"}],
                "execution_requirements": {
                    "repository_inspection_required": True,
                    "local_repository_required": True,
                },
            },
        )
    )

    assert outcome.state == STATE_READY
    assert outcome.questions() == ()
    assert outcome.decision.required_before_handoff == ()
    assert outcome.decision.optional_improvements == ()


def test_case_b_handoff_readiness_authorizes_nothing():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Fix the typo 'teh' to 'the' in README.md.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [{"value": "README.md", "provenance": "explicit"}],
                "execution_requirements": {
                    "repository_inspection_required": True,
                    "local_repository_required": True,
                },
            },
        )
    )
    authority = outcome.as_dict()["authority"]

    assert outcome.ready_for_future_handoff is True
    assert authority["execution_authority"] is False
    assert authority["patch_authority"] is False
    assert authority["repository_write_authority"] is False
    assert authority["routing_authority"] is False


# ══ C — a broad understood task is offered assistance ═════════════════════════

def test_case_c_a_broad_migration_is_offered_a_goal_brief():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Migrate the storage backend to PostgreSQL.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [{"value": "PostgreSQL", "provenance": "explicit"}],
                "execution_requirements": BROAD_EXECUTION,
                "missing_information": ["which compatibility guarantee to keep"],
            },
        )
    )

    assert outcome.state == STATE_GOAL_BRIEF_ASSIST
    assert outcome.owner == OWNER_OPERATIONAL_DETAIL_MISSING
    assert outcome.goal_brief_offered is True
    assert "scope" in outcome.decision.required_before_handoff
    assert outcome.questions()


def test_case_c_offers_assistance_without_choosing_any_workflow():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Migrate the storage backend to PostgreSQL.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "execution_requirements": BROAD_EXECUTION,
            },
        )
    )

    # The authority block names these powers precisely to deny them, so it is
    # excluded: what must not appear is a *selection*, not a denial.
    rendered = json.dumps(_without_authority(outcome.as_dict())).lower()
    for forbidden in (
        "commander",
        "instant run",
        "project evolution",
        "mixed mode",
        "dream",
        "mode_selected",
        "route_to",
        "provider",
    ):
        assert forbidden not in rendered, forbidden


# ══ D — a genuine ambiguity is asked about, once ══════════════════════════════

def test_case_d_an_unresolvable_reference_asks_for_clarification():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Replace it with the other one.",
            {
                "task": {"type": "unknown", "provenance": "inferred"},
                "ambiguities": ["'it' has no resolvable referent in the supplied context"],
            },
        )
    )

    assert outcome.state == STATE_ASK_CLARIFICATION
    assert outcome.owner == OWNER_USER_MEANING_AMBIGUITY
    assert len(outcome.questions()) == 1
    assert outcome.ready_for_future_handoff is False


def test_case_d_does_not_guess_the_referent():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Replace it with the other one.",
            {
                "task": {"type": "unknown", "provenance": "inferred"},
                "ambiguities": ["'it' has no resolvable referent in the supplied context"],
            },
        )
    )

    assert outcome.projection.subjects == ()
    assert outcome.projection.field("what").value == "Replace it with the other one."


# ══ E — a model timeout is the system's problem ═══════════════════════════════

def test_case_e_a_semantic_timeout_is_never_blamed_on_the_user():
    adapter = SemanticWaiterModelAdapter(_DeadSemanticClient())
    semantic = understand_request_semantically(
        "Explain what DeepSeek Harness is.", adapter=adapter
    )

    outcome = complete_intake_from_semantic_outcome(semantic)

    assert semantic.status == SEMANTIC_MODEL_UNAVAILABLE
    assert outcome.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert outcome.owner == OWNER_SEMANTIC_SYSTEM_FAILURE
    assert outcome.state != STATE_ASK_CLARIFICATION
    assert outcome.questions() == ()
    assert "semantic interpreter failed" in outcome.assistance.summary


def test_case_e_without_a_contract_there_is_nothing_to_project():
    adapter = SemanticWaiterModelAdapter(_DeadSemanticClient())
    semantic = understand_request_semantically(
        "Explain what DeepSeek Harness is.", adapter=adapter
    )

    outcome = complete_intake_from_semantic_outcome(semantic)

    assert semantic.contract is None
    assert outcome.projection is None
    assert outcome.goal_brief_offered is False


# ══ F — a lost rubric is the system's problem ═════════════════════════════════

def test_case_f_a_preservation_failure_after_repair_is_a_system_failure():
    lossy = {
        "task": {"type": "analysis", "provenance": "inferred"},
        "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
    }
    semantic = _semantic(DOGFOOD_PROMPT, lossy, lossy)

    outcome = complete_intake_from_semantic_outcome(semantic)

    assert semantic.status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert outcome.owner == OWNER_SEMANTIC_SYSTEM_FAILURE
    assert outcome.decision.preservation_status == "failed"


def test_case_f_does_not_ask_the_user_to_restate_a_clear_request():
    lossy = {
        "task": {"type": "analysis", "provenance": "inferred"},
        "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
    }
    outcome = complete_intake_from_semantic_outcome(_semantic(DOGFOOD_PROMPT, lossy, lossy))

    summary = outcome.assistance.summary.lower()
    assert "unclear" not in summary
    assert "clarify" not in summary
    assert "rephrase" not in summary


def test_deepseek_dogfood_handoff_requires_every_independent_prerequisite():
    semantic = _semantic(DOGFOOD_PROMPT, _healthy_dogfood_interpretation())
    healthy = complete_intake_from_semantic_outcome(semantic)

    assert semantic.status == SEMANTIC_INTERPRETATION_OK
    assert semantic.contract is not None
    assert healthy.state == STATE_READY
    assert healthy.ready_for_future_handoff is True

    # A direct INPUT.3 inspection remains useful, but the absent INPUT.2
    # receipt means it is only a preview.
    receipt_missing = complete_intake(semantic.contract, semantic_status=semantic.status)

    failed_preservation_contract = dataclasses.replace(
        semantic.contract,
        preservation=PreservationReport(
            status=PRESERVATION_FAILED,
            reasons=("dogfood mutation: preservation failed",),
        ),
        routing_allowed=False,
    )
    preservation_failed = complete_intake_from_semantic_outcome(
        SemanticWaiterOutcome(
            status=semantic.status,
            receipt=semantic.receipt,
            contract=failed_preservation_contract,
        )
    )

    semantic_failed = complete_intake_from_semantic_outcome(
        SemanticWaiterOutcome(
            status=SEMANTIC_INTERPRETATION_FAILED,
            receipt=dataclasses.replace(
                semantic.receipt,
                final_status=SEMANTIC_INTERPRETATION_FAILED,
                structured_output_valid=False,
            ),
            contract=dataclasses.replace(semantic.contract, routing_allowed=False),
        )
    )

    assert receipt_missing.state == STATE_READY
    assert receipt_missing.ready_for_future_handoff is False
    assert receipt_missing.decision.handoff_blockers == ("semantic_receipt_missing",)
    assert preservation_failed.decision.preservation_status == PRESERVATION_FAILED
    assert preservation_failed.ready_for_future_handoff is False
    assert semantic_failed.state == STATE_SEMANTIC_SYSTEM_FAILURE
    assert semantic_failed.ready_for_future_handoff is False
    for outcome in (receipt_missing, preservation_failed, semantic_failed):
        rendered = json.dumps(_without_authority(outcome.as_dict())).lower()
        assert "mode_selected" not in rendered
        assert "execution_mode" not in rendered


# ══ G / H — bounded comparisons stay bounded ══════════════════════════════════

def test_case_g_a_bounded_snippet_comparison_is_ready():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Compare these two pasted functions for readability.",
            {
                "task": {"type": "comparative_analysis", "provenance": "inferred"},
                "relationships": [
                    {
                        "type": "comparison",
                        "subjects": ["the first pasted function", "the second pasted function"],
                        "provenance": "inferred",
                    }
                ],
                "subjects": [
                    {"value": "the first pasted function", "provenance": "inferred"},
                    {"value": "the second pasted function", "provenance": "inferred"},
                ],
            },
        )
    )

    assert outcome.state == STATE_READY
    assert outcome.goal_brief_offered is False
    assert outcome.questions() == ()


def test_case_g_complexity_is_not_incompleteness():
    """Even flagged as multi-stage, a comparison is not a broad operational task."""
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Compare these two pasted functions for readability.",
            {
                "task": {"type": "comparative_analysis", "provenance": "inferred"},
                "execution_requirements": BROAD_EXECUTION,
            },
        )
    )

    assert outcome.state == STATE_READY


def test_case_h_a_requested_markdown_table_is_ready():
    outcome = complete_intake(understand_request("Compare A and B and return a Markdown table."))

    assert outcome.state == STATE_READY
    assert outcome.questions() == ()
    assert outcome.decision.preservation_status == "passed"
    assert outcome.ready_for_future_handoff is False
    assert outcome.decision.handoff_blockers == ("semantic_receipt_missing",)


# ══ I — a broad task with its details supplied is ready ═══════════════════════

def test_case_i_a_broad_migration_with_details_is_ready():
    prompt = (
        "Migrate the storage backend in storage/db.py to PostgreSQL, keep the existing "
        "API, only touch storage/, and verify with pytest."
    )
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            prompt,
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [
                    {"value": "PostgreSQL", "provenance": "explicit"},
                    {"value": "storage/db.py", "provenance": "explicit"},
                ],
                "constraints": [
                    {
                        "kind": "restriction",
                        "text": prompt.rstrip("."),
                        "provenance": "explicit",
                    }
                ],
                "execution_requirements": BROAD_EXECUTION,
            },
        )
    )

    assert outcome.state == STATE_READY
    assert outcome.decision.required_before_handoff == ()
    assert outcome.goal_brief_offered is False


# ══ J — an explicit contradiction blocks ══════════════════════════════════════

def test_case_j_contradictory_explicit_constraints_block():
    outcome = complete_intake(
        understand_request("You must modify the tests. You must not modify the tests.")
    )

    assert outcome.state == STATE_BLOCKED_CONTRADICTION
    assert outcome.owner == OWNER_EXPLICIT_CONSTRAINT_CONFLICT
    assert outcome.ready_for_future_handoff is False
    assert outcome.decision.contradiction_reasons


# ══ K — the policy is not English-only ════════════════════════════════════════

def test_case_k_a_vietnamese_request_can_be_ready():
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Giải thích DeepSeek Harness là gì.",
            {
                "task": {"type": "question", "provenance": "inferred"},
                "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
            },
        )
    )

    assert outcome.state == STATE_READY
    assert outcome.questions() == ()


def test_case_k_a_vietnamese_ambiguity_asks_in_the_users_terms():
    detail = "'nó' và 'cái kia' không có đối tượng xác định trong ngữ cảnh"
    outcome = complete_intake_from_semantic_outcome(
        _semantic(
            "Thay nó bằng cái kia giúp mình.",
            {"task": {"type": "unknown", "provenance": "inferred"}, "ambiguities": [detail]},
        )
    )

    assert outcome.state == STATE_ASK_CLARIFICATION
    assert outcome.owner == OWNER_USER_MEANING_AMBIGUITY
    assert detail in outcome.questions()[0]


def test_the_policy_reads_structure_rather_than_language():
    """The same structure in two languages decides the same way."""
    english = complete_intake_from_semantic_outcome(
        _semantic(
            "Explain what DeepSeek Harness is.",
            {
                "task": {"type": "question", "provenance": "inferred"},
                "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
            },
        )
    )
    vietnamese = complete_intake_from_semantic_outcome(
        _semantic(
            "Giải thích DeepSeek Harness là gì.",
            {
                "task": {"type": "question", "provenance": "inferred"},
                "subjects": [{"value": "DeepSeek Harness", "provenance": "explicit"}],
            },
        )
    )

    assert english.state == vietnamese.state
    assert english.decision.reasons == vietnamese.decision.reasons


# ══ zero-model equivalence ════════════════════════════════════════════════════

def _equivalence_contracts():
    """One contract per decision state that has a contract at all."""
    return {
        "ready": understand_request("Explain what DeepSeek Harness is."),
        "goal_brief_assist": _semantic(
            "Migrate the storage backend to PostgreSQL.",
            {
                "task": {"type": "implementation", "provenance": "inferred"},
                "subjects": [{"value": "PostgreSQL", "provenance": "explicit"}],
                "execution_requirements": BROAD_EXECUTION,
                "missing_information": ["which compatibility guarantee to keep"],
            },
        ).contract,
        "ask_clarification": _semantic(
            "Replace it with the other one.",
            {
                "task": {"type": "unknown", "provenance": "inferred"},
                "ambiguities": ["'it' has no resolvable referent"],
            },
        ).contract,
        "blocked_contradiction": understand_request(
            "You must modify the tests. You must not modify the tests."
        ),
    }


def _talkative_assistant(decision):
    """An assistant that rewrites every question it is allowed to answer."""
    payload = {
        "summary": "Here is what I think you are after, in friendlier words.",
        "questions": [
            {"need_id": need_id, "text": f"Could you tell me a bit more about {need_id}?"}
            for need_id in decision.need_ids()
        ],
    }
    return _assistant(payload)


@pytest.mark.parametrize("label", sorted(_equivalence_contracts()))
def test_a_local_assistant_never_changes_the_canonical_decision(label):
    contract = _equivalence_contracts()[label]

    baseline = complete_intake(contract)
    assisted = complete_intake(
        contract, assistant=_talkative_assistant(baseline.decision)
    )

    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_the_assistant_only_changes_the_words():
    contract = _equivalence_contracts()["ask_clarification"]

    baseline = complete_intake(contract)
    assisted = complete_intake(contract, assistant=_talkative_assistant(baseline.decision))

    assert assisted.assistance_status == ASSISTANCE_STATUS_OK
    assert assisted.model_assisted is True
    assert assisted.questions() != baseline.questions()
    assert assisted.assistance.summary != baseline.assistance.summary
    assert assisted.state == baseline.state


def test_an_assistant_cannot_promote_a_clarification_into_readiness():
    contract = _equivalence_contracts()["ask_clarification"]
    baseline = complete_intake(contract)

    for attempt in (
        {"summary": "All clear, nothing to ask.", "state": "ready"},
        {"summary": "Ready to go.", "ready_for_future_handoff": True},
        {"summary": "Resolved it myself.", "resolved": ["ambiguity:reported_ambiguity_1"]},
        {"summary": "It means the database.", "questions": []},
    ):
        assisted = complete_intake(contract, assistant=_assistant(attempt))

        assert assisted.state == STATE_ASK_CLARIFICATION
        assert assisted.ready_for_future_handoff is False
        assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_an_assistant_cannot_promote_a_receiptless_ready_preview_into_handoff():
    contract = _equivalence_contracts()["ready"]
    baseline = complete_intake(contract)
    assisted = complete_intake(
        contract,
        assistant=_assistant(
            {
                "summary": "The order is ready for handoff.",
                "ready_for_future_handoff": True,
                "semantic_evidence_valid": True,
            }
        ),
    )

    assert baseline.state == assisted.state == STATE_READY
    assert baseline.ready_for_future_handoff is False
    assert assisted.ready_for_future_handoff is False
    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_an_assistant_cannot_resolve_a_missing_field():
    contract = _equivalence_contracts()["goal_brief_assist"]
    baseline = complete_intake(contract)

    assisted = complete_intake(
        contract,
        assistant=_assistant(
            {
                "summary": "I filled the scope in for you.",
                "field_suggestions": [
                    {"field": "scope", "suggested_value": "storage/ and database/"}
                ],
            }
        ),
    )

    assert "scope" in assisted.decision.required_before_handoff
    assert assisted.projection.field("scope").entries == ()
    assert assisted.assistance.field_suggestions[0].as_dict()["canonical"] is False
    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_a_missing_local_model_leaves_everything_but_the_wording_intact():
    contract = _equivalence_contracts()["ask_clarification"]

    class Dead:
        model_id = "dead"

        def complete(self, system_instruction, user_message):
            raise OSError("no local model installed")

    baseline = complete_intake(contract)
    assisted = complete_intake(contract, assistant=LocalModelIntakeAssistant(Dead()))

    assert assisted.assistance_status == ASSISTANCE_STATUS_UNAVAILABLE
    assert assisted.questions() == baseline.questions()
    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_an_assistant_that_raises_is_survived():
    contract = _equivalence_contracts()["ready"]

    class Broken:
        name = "broken"

        def assist(self, contract, decision, projection):
            raise RuntimeError("assistant exploded")

    baseline = complete_intake(contract)
    assisted = complete_intake(contract, assistant=Broken())

    assert assisted.assistance_status == ASSISTANCE_STATUS_UNAVAILABLE
    assert canonical_intake_fingerprint(baseline) == canonical_intake_fingerprint(assisted)


def test_an_assistant_returning_the_wrong_type_is_survived():
    contract = _equivalence_contracts()["ready"]

    class Confused:
        name = "confused"

        def assist(self, contract, decision, projection):
            return {"state": "ready"}

    assisted = complete_intake(contract, assistant=Confused())

    assert assisted.assistance_status == ASSISTANCE_STATUS_REJECTED
    assert assisted.state == STATE_READY


def test_the_decision_object_handed_to_the_assistant_is_the_one_returned():
    contract = _equivalence_contracts()["ask_clarification"]
    seen: list = []

    class Observer:
        name = "observer"

        def assist(self, contract, decision, projection):
            seen.append((decision, projection))
            return IntakeAssistance(assistant_name="observer", summary="noted")

    outcome = complete_intake(contract, assistant=Observer())

    assert seen[0][0] is outcome.decision
    assert seen[0][1] is outcome.projection


# ══ orchestration ═════════════════════════════════════════════════════════════

def test_the_stage_list_stops_before_workflow_selection():
    assert INTAKE_COMPLETION_STAGES == (
        "deterministic_completion_policy",
        "goal_brief_projection",
        "optional_intake_assistance",
    )


def test_no_assistant_still_produces_usable_assistance():
    outcome = complete_intake(
        understand_request("You must modify the tests. You must not modify the tests.")
    )

    assert outcome.assistance_status == ASSISTANCE_STATUS_NOT_CONFIGURED
    assert outcome.model_assisted is False
    assert outcome.assistance.summary


def test_a_goal_brief_is_never_required():
    for contract in _equivalence_contracts().values():
        payload = complete_intake(contract).as_dict()
        assert payload["goal_brief_required"] is False


def test_the_outcome_serializes_with_its_authority_block():
    outcome = complete_intake(understand_request("Explain what DeepSeek Harness is."))

    payload = json.loads(render_intake_completion_json(outcome))

    assert payload["phase_id"] == "INPUT.3"
    assert payload["decision"]["state"] == STATE_READY
    assert payload["authority"]["execution_authority"] is False
    assert payload["authority"]["provider_selection_authority"] is False
    assert payload["authority"]["model_escalation_authority"] is False


def test_an_outcome_without_a_projection_must_be_a_system_failure():
    ready = complete_intake(understand_request("Explain what DeepSeek Harness is."))

    with pytest.raises(ValueError, match="only a system failure"):
        IntakeCompletionOutcome(decision=ready.decision, projection=None)


def test_input_3_never_touches_the_contracts_own_routing_flag():
    contract = understand_request("Explain what DeepSeek Harness is.")
    before = contract.routing_allowed

    complete_intake(contract, assistant=_assistant({"summary": "hello"}))

    assert contract.routing_allowed is before
