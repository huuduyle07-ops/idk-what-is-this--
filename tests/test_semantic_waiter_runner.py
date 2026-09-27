"""INPUT.2 — bounded repair loop, outcome statuses, and telemetry tests.

The runner never lets the model build the Task Contract: it converts the
model's semantic structure through the frozen deterministic INPUT.1 path and
then gates it.  At most two semantic model calls happen per request, ever.
"""

from __future__ import annotations

import json

import pytest

from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_runner import (
    ATTEMPT_MODEL_UNAVAILABLE,
    ATTEMPT_OK,
    ATTEMPT_OUTPUT_INVALID,
    ATTEMPT_PRESERVATION_FAILED,
    MAX_SEMANTIC_MODEL_CALLS,
    SEMANTIC_DETERMINISTIC_FALLBACK,
    SEMANTIC_INTERPRETATION_FAILED,
    SEMANTIC_INTERPRETATION_OK,
    SEMANTIC_INTERPRETATION_REPAIRED,
    SEMANTIC_MODEL_UNAVAILABLE,
    SEMANTIC_OUTPUT_INVALID,
    SEMANTIC_WAITER_STATUSES,
    understand_request_semantically,
)


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

RUBRIC = [
    "Equivalent",
    "DeepSeek stronger",
    "C.A.T.T.U.S stronger",
    "Orthogonal",
    "Not worth adopting",
]


#: The literal constraint text INPUT.1 extracts and hands to the model. A
#: compliant model copies it back character for character, colon included.
FRAMEWORK_CONSTRAINT_TEXT = (
    "Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:"
)


def _good(**overrides) -> str:
    payload = {
        "task": {"type": "comparative_analysis", "confidence": 0.9},
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
            "values": list(RUBRIC),
            "provenance": "explicit",
            "ordered": True,
        },
        "constraints": [
            {
                "kind": "framework_reference",
                "text": FRAMEWORK_CONSTRAINT_TEXT,
                "provenance": "explicit",
            }
        ],
        "execution_requirements": {"multi_stage": True},
    }
    payload.update(overrides)
    return json.dumps(payload)


def _drops_cattus() -> str:
    return _good(
        subjects=[{"value": "DeepSeek Harness", "provenance": "explicit"}],
        relationships=[],
    )


def _drops_rubric_item_confidently() -> str:
    return _good(
        task={"type": "comparative_analysis", "confidence": 0.99},
        user_supplied_framework={
            "type": "framework",
            "values": [v for v in RUBRIC if v != "Orthogonal"],
            "provenance": "explicit",
            "ordered": True,
        },
    )


def _run(responses, **kwargs):
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient(responses, model_id="test-semantic-model")
    )
    return understand_request_semantically(DOGFOOD_PROMPT, adapter=adapter, **kwargs)


# ══ statuses ══════════════════════════════════════════════════════════════════

def test_status_vocabulary_is_stable():
    assert SEMANTIC_WAITER_STATUSES == (
        SEMANTIC_INTERPRETATION_OK,
        SEMANTIC_INTERPRETATION_REPAIRED,
        SEMANTIC_INTERPRETATION_FAILED,
        SEMANTIC_OUTPUT_INVALID,
        SEMANTIC_MODEL_UNAVAILABLE,
        SEMANTIC_DETERMINISTIC_FALLBACK,
    )


def test_call_budget_is_two():
    assert MAX_SEMANTIC_MODEL_CALLS == 2


# ══ first attempt succeeds ════════════════════════════════════════════════════

def test_faithful_first_attempt_is_ok_with_one_call():
    outcome = _run([_good()])

    assert outcome.status == SEMANTIC_INTERPRETATION_OK
    assert outcome.receipt.model_call_count == 1
    assert outcome.receipt.repair_attempted is False
    assert outcome.receipt.first_attempt_status == ATTEMPT_OK
    assert outcome.contract.routing_allowed is True


def test_successful_outcome_preserves_the_raw_request_verbatim():
    outcome = _run([_good()])

    assert outcome.contract.raw_request.text == DOGFOOD_PROMPT


def test_successful_outcome_keeps_both_subjects_and_the_rubric():
    outcome = _run([_good()])

    assert set(outcome.contract.subject_values()) >= {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert list(outcome.contract.user_supplied_framework.values) == RUBRIC


# ══ bounded repair ════════════════════════════════════════════════════════════

def test_dropped_subject_repaired_on_the_single_retry():
    outcome = _run([_drops_cattus(), _good()])

    assert outcome.status == SEMANTIC_INTERPRETATION_REPAIRED
    assert outcome.receipt.repair_attempted is True
    assert outcome.receipt.model_call_count == 2
    assert outcome.receipt.first_attempt_status == ATTEMPT_PRESERVATION_FAILED
    assert outcome.contract.routing_allowed is True


def test_repair_prompt_names_the_missing_subject():
    client = ScriptedSemanticModelClient([_drops_cattus(), _good()])
    adapter = SemanticWaiterModelAdapter(client)

    understand_request_semantically(DOGFOOD_PROMPT, adapter=adapter)

    _, repair_message = client.calls[1]
    assert "C.A.T.T.U.S" in repair_message
    assert "preservation" in repair_message.lower()


def test_repair_that_still_drops_the_subject_fails():
    outcome = _run([_drops_cattus(), _drops_cattus()])

    assert outcome.status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.receipt.model_call_count == 2
    assert outcome.contract.routing_allowed is False
    assert "C.A.T.T.U.S" in outcome.contract.preservation.missing_values("subject")


def test_model_calls_never_exceed_the_budget():
    outcome = _run([_drops_cattus(), _drops_cattus(), _good(), _good()])

    assert outcome.receipt.model_call_count <= MAX_SEMANTIC_MODEL_CALLS
    assert outcome.status == SEMANTIC_INTERPRETATION_FAILED


def test_high_confidence_cannot_rescue_a_dropped_rubric_value():
    outcome = _run([_drops_rubric_item_confidently(), _drops_rubric_item_confidently()])

    assert outcome.status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.contract.routing_allowed is False
    assert "Orthogonal" in outcome.contract.preservation.missing_values("framework_value")


def test_rewritten_explicit_constraint_fails_preservation():
    rewritten = _good(
        constraints=[
            {
                "kind": "framework_reference",
                "text": "Analyze DeepSeek Harness against C.A.T.T.U.S however you like",
                "provenance": "explicit",
            }
        ]
    )
    outcome = _run([rewritten, rewritten])

    assert outcome.status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.contract.routing_allowed is False
    assert outcome.contract.preservation.has_missing("constraint") is True


# ══ malformed / unavailable ═══════════════════════════════════════════════════

def test_malformed_output_fails_closed_without_a_repair_call():
    outcome = _run(["I think the user wants a comparison."])

    assert outcome.status == SEMANTIC_OUTPUT_INVALID
    assert outcome.receipt.model_call_count == 1
    assert outcome.receipt.repair_attempted is False
    assert outcome.receipt.structured_output_valid is False
    assert outcome.contract is None


def test_authority_claiming_output_fails_closed():
    payload = json.loads(_good())
    payload["routing_allowed"] = True
    outcome = _run([json.dumps(payload)])

    assert outcome.status == SEMANTIC_OUTPUT_INVALID
    assert outcome.contract is None


def test_unreachable_model_is_reported_honestly():
    class Broken:
        model_id = "unreachable-model"

        def complete(self, system_instruction, user_message):
            raise ConnectionError("no route to host")

    outcome = understand_request_semantically(
        DOGFOOD_PROMPT, adapter=SemanticWaiterModelAdapter(Broken())
    )

    assert outcome.status == SEMANTIC_MODEL_UNAVAILABLE
    assert outcome.receipt.first_attempt_status == ATTEMPT_MODEL_UNAVAILABLE
    assert outcome.contract is None


def test_repair_output_invalid_still_ends_in_failure():
    outcome = _run([_drops_cattus(), "sorry, here is prose instead"])

    assert outcome.status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.receipt.repair_attempted is True
    assert outcome.receipt.repair_status == ATTEMPT_OUTPUT_INVALID


# ══ deterministic fallback — honest, never authoritative ══════════════════════

def test_fallback_is_off_by_default():
    outcome = _run(["nonsense"])

    assert outcome.receipt.fallback_used is False
    assert outcome.contract is None


def test_fallback_reports_itself_as_a_fallback_not_as_understanding():
    outcome = _run(["nonsense"], allow_deterministic_fallback=True)

    assert outcome.status == SEMANTIC_DETERMINISTIC_FALLBACK
    assert outcome.receipt.fallback_used is True
    assert outcome.status != SEMANTIC_INTERPRETATION_OK


def test_fallback_grants_no_routing_authority():
    outcome = _run(["nonsense"], allow_deterministic_fallback=True)

    assert outcome.contract is not None
    assert outcome.contract.routing_allowed is False


def test_fallback_still_runs_preservation_and_keeps_the_raw_request():
    outcome = _run(["nonsense"], allow_deterministic_fallback=True)

    assert outcome.contract.preservation is not None
    assert outcome.contract.raw_request.text == DOGFOOD_PROMPT


def test_fallback_records_the_model_failure_it_replaced():
    outcome = _run(["nonsense"], allow_deterministic_fallback=True)

    assert outcome.receipt.model_status == SEMANTIC_OUTPUT_INVALID


def test_fallback_after_a_failed_repair_is_still_a_fallback():
    outcome = _run(
        [_drops_cattus(), _drops_cattus()], allow_deterministic_fallback=True
    )

    assert outcome.status == SEMANTIC_DETERMINISTIC_FALLBACK
    assert outcome.receipt.model_status == SEMANTIC_INTERPRETATION_FAILED
    assert outcome.contract.routing_allowed is False


def test_successful_interpretation_never_uses_the_fallback():
    outcome = _run([_good()], allow_deterministic_fallback=True)

    assert outcome.status == SEMANTIC_INTERPRETATION_OK
    assert outcome.receipt.fallback_used is False


# ══ telemetry ═════════════════════════════════════════════════════════════════

def test_receipt_records_the_adapter_and_configured_model():
    receipt = _run([_good()]).receipt

    assert receipt.adapter_name == "semantic_waiter_model_adapter"
    assert receipt.configured_model == "test-semantic-model"


def test_receipt_records_preservation_failure_reasons():
    receipt = _run([_drops_cattus(), _drops_cattus()]).receipt

    assert receipt.preservation_failure_reasons
    assert any("C.A.T.T.U.S" in reason for reason in receipt.preservation_failure_reasons)


def test_receipt_declares_zero_authority():
    guardrails = _run([_good()]).receipt.as_dict()["authority"]

    for flag in (
        "repository_read_authority",
        "repository_write_authority",
        "patch_authority",
        "validation_authority",
        "benchmark_authority",
        "routing_authority",
        "provider_selection_authority",
        "execution_authority",
    ):
        assert guardrails[flag] is False, flag


def test_receipt_is_bounded_and_holds_no_raw_provider_payload():
    receipt = _run([_good()]).receipt
    text = json.dumps(receipt.as_dict())

    assert "api_key" not in text.lower()
    assert len(text) < 8_000


def test_receipt_serializes_deterministically():
    first = _run([_good()]).receipt.as_dict()
    second = _run([_good()]).receipt.as_dict()

    assert first == second


def test_receipt_notes_a_truncated_prompt():
    huge = "Compare A against B. " + ("padding " * 3_000)
    adapter = SemanticWaiterModelAdapter(ScriptedSemanticModelClient([_good()]))

    outcome = understand_request_semantically(huge, adapter=adapter)

    assert outcome.receipt.prompt_truncated is True


# ══ the model never holds authority ═══════════════════════════════════════════

def test_routing_comes_from_the_gate_not_from_the_model():
    outcome = _run([_good()])
    guardrails = outcome.contract.as_dict()["guardrails"]

    assert outcome.contract.routing_allowed == outcome.contract.preservation.passed
    assert guardrails["provider_selected"] is False
    assert guardrails["mode_dispatch_performed"] is False
    assert guardrails["write_authority"] is False


def test_adapter_is_required():
    with pytest.raises(TypeError):
        understand_request_semantically(DOGFOOD_PROMPT)  # type: ignore[call-arg]


def test_non_string_prompt_is_rejected():
    adapter = SemanticWaiterModelAdapter(ScriptedSemanticModelClient([_good()]))

    with pytest.raises(TypeError):
        understand_request_semantically(None, adapter=adapter)  # type: ignore[arg-type]
