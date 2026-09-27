"""INPUT.2 — Semantic Waiter model adapter tests.

The adapter turns one model call into a SemanticInterpretation.  It parses
strictly: malformed or authority-claiming output fails closed rather than being
best-effort converted from prose.  No test here touches a network.
"""

from __future__ import annotations

import copy
import json

import pytest

from core.explicit_evidence import extract_explicit_evidence
from core.semantic_waiter import SemanticInterpreter
from core.semantic_waiter_adapter import (
    ADAPTER_NAME,
    ALLOWED_RESPONSE_KEYS,
    FORBIDDEN_RESPONSE_KEYS,
    MAX_SEMANTIC_PROMPT_CHARS,
    SEMANTIC_WAITER_SYSTEM_INSTRUCTION,
    ScriptedSemanticModelClient,
    SemanticModelClient,
    SemanticModelUnavailable,
    SemanticOutputInvalid,
    SemanticWaiterModelAdapter,
    build_interpretation_request,
    build_repair_request,
    parse_semantic_response,
)
from core.task_contract import (
    MAX_SUBJECTS,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    PreservationItem,
    PreservationReport,
    PRESERVATION_FAILED,
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


def _payload(**overrides) -> dict:
    base = {
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
        "requested_output": None,
        "constraints": [],
        "ambiguities": [],
        "missing_information": [],
        "execution_requirements": {"multi_stage": True},
    }
    base.update(overrides)
    return base


def _json(**overrides) -> str:
    return json.dumps(_payload(**overrides))


def _evidence(text: str = DOGFOOD_PROMPT):
    return extract_explicit_evidence(text)


# ══ system instruction ════════════════════════════════════════════════════════

def test_system_instruction_forbids_solving_and_execution():
    text = SEMANTIC_WAITER_SYSTEM_INSTRUCTION.lower()

    assert "do not solve" in text
    assert "do not inspect repositories" in text
    assert "do not choose execution modes" in text
    assert "do not call tools" in text
    assert "do not execute" in text


def test_system_instruction_demands_provenance_separation():
    text = SEMANTIC_WAITER_SYSTEM_INSTRUCTION.lower()

    assert "explicit" in text
    assert "inferred" in text


# ══ request building — intake semantics only ══════════════════════════════════

def test_interpretation_request_carries_the_raw_prompt():
    request = build_interpretation_request(DOGFOOD_PROMPT, _evidence())

    assert "Analyze DeepSeek Harness against C.A.T.T.U.S" in request


def test_interpretation_request_carries_explicit_evidence_verbatim():
    request = build_interpretation_request(DOGFOOD_PROMPT, _evidence())

    for value in RUBRIC:
        assert value in request
    assert "DeepSeek Harness" in request
    assert "C.A.T.T.U.S" in request


def test_interpretation_request_is_bounded_for_a_huge_prompt():
    huge = "x" * (MAX_SEMANTIC_PROMPT_CHARS * 3)
    request = build_interpretation_request(huge, extract_explicit_evidence(huge))

    assert len(request) < MAX_SEMANTIC_PROMPT_CHARS * 2


def test_interpretation_request_never_carries_repository_context():
    request = build_interpretation_request(DOGFOOD_PROMPT, _evidence()).lower()

    for banned in ("project_map", "repository index", "activation graph", "lesson"):
        assert banned not in request


# ══ strict parsing ════════════════════════════════════════════════════════════

def test_valid_payload_parses_into_an_interpretation():
    interpretation = parse_semantic_response(_json())

    assert interpretation.task.type == "comparative_analysis"
    assert [s.value for s in interpretation.subjects] == ["DeepSeek Harness", "C.A.T.T.U.S"]
    assert interpretation.framework.values == tuple(RUBRIC)


def test_fenced_json_parses():
    interpretation = parse_semantic_response("```json\n" + _json() + "\n```")

    assert interpretation.task.type == "comparative_analysis"


def test_prose_without_json_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response("The user wants a comparison between the two systems.")


def test_empty_response_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response("")


def test_json_array_is_not_a_valid_semantic_response():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response("[1, 2, 3]")


def test_missing_task_fails_closed():
    payload = _payload()
    del payload["task"]

    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(json.dumps(payload))


def test_unknown_task_type_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(_json(task={"type": "teleportation"}))


def test_unknown_provenance_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(
            _json(subjects=[{"value": "A", "provenance": "vibes"}])
        )


def test_unknown_top_level_key_fails_closed():
    payload = _payload()
    payload["extra_thoughts"] = "hello"

    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(json.dumps(payload))


@pytest.mark.parametrize("key", list(FORBIDDEN_RESPONSE_KEYS))
def test_authority_claiming_key_fails_closed(key):
    payload = _payload()
    payload[key] = True

    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(json.dumps(payload))


def test_forbidden_and_allowed_key_sets_are_disjoint():
    assert not (set(FORBIDDEN_RESPONSE_KEYS) & set(ALLOWED_RESPONSE_KEYS))


def test_routing_allowed_is_a_forbidden_response_key():
    assert "routing_allowed" in FORBIDDEN_RESPONSE_KEYS
    assert "preservation" in FORBIDDEN_RESPONSE_KEYS
    assert "provider" in FORBIDDEN_RESPONSE_KEYS
    assert "write_authority" in FORBIDDEN_RESPONSE_KEYS


# ══ provenance normalization ══════════════════════════════════════════════════

def test_task_provenance_is_always_inferred_even_if_model_claims_explicit():
    interpretation = parse_semantic_response(
        _json(task={"type": "comparative_analysis", "provenance": "explicit"})
    )

    assert interpretation.task.provenance == PROVENANCE_INFERRED


def test_explicit_subject_confidence_is_stripped_not_rejected():
    interpretation = parse_semantic_response(
        _json(subjects=[{"value": "A", "provenance": "explicit", "confidence": 0.97}])
    )

    assert interpretation.subjects[0].provenance == PROVENANCE_EXPLICIT
    assert interpretation.subjects[0].confidence is None


def test_inferred_subject_keeps_its_confidence():
    interpretation = parse_semantic_response(
        _json(subjects=[{"value": "A", "provenance": "inferred", "confidence": 0.4}])
    )

    assert interpretation.subjects[0].confidence == 0.4


def test_out_of_range_confidence_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(
            _json(subjects=[{"value": "A", "provenance": "inferred", "confidence": 4.2}])
        )


def test_execution_requirements_provenance_is_forced_to_inferred():
    interpretation = parse_semantic_response(
        _json(execution_requirements={"multi_stage": True, "provenance": "explicit"})
    )

    assert interpretation.execution_requirements.provenance == PROVENANCE_INFERRED
    assert interpretation.execution_requirements.multi_stage is True


def test_subject_missing_a_value_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(_json(subjects=[{"provenance": "explicit"}]))


# ══ bounds ════════════════════════════════════════════════════════════════════

def test_too_many_subjects_fails_closed_rather_than_truncating():
    too_many = [
        {"value": f"s{n}", "provenance": "inferred"} for n in range(MAX_SUBJECTS + 1)
    ]

    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(_json(subjects=too_many))


def test_too_many_framework_values_fails_closed():
    with pytest.raises(SemanticOutputInvalid):
        parse_semantic_response(
            _json(
                user_supplied_framework={
                    "type": "rubric",
                    "values": [f"v{n}" for n in range(200)],
                    "provenance": "inferred",
                }
            )
        )


# ══ the adapter itself ════════════════════════════════════════════════════════

def test_adapter_satisfies_the_input_1_interpreter_protocol():
    adapter = SemanticWaiterModelAdapter(ScriptedSemanticModelClient([_json()]))

    assert isinstance(adapter, SemanticInterpreter)


def test_scripted_client_satisfies_the_model_client_protocol():
    assert isinstance(ScriptedSemanticModelClient([_json()]), SemanticModelClient)


def test_adapter_makes_exactly_one_call_per_interpretation():
    client = ScriptedSemanticModelClient([_json()])
    adapter = SemanticWaiterModelAdapter(client)

    adapter.interpret(DOGFOOD_PROMPT, _evidence())

    assert adapter.call_count == 1
    assert len(client.calls) == 1


def test_adapter_reports_the_configured_model():
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([_json()], model_id="test-model-1")
    )

    assert adapter.model_id == "test-model-1"
    assert adapter.name == ADAPTER_NAME


def test_adapter_sends_the_system_instruction():
    client = ScriptedSemanticModelClient([_json()])
    SemanticWaiterModelAdapter(client).interpret(DOGFOOD_PROMPT, _evidence())

    system_instruction, _ = client.calls[0]
    assert system_instruction == SEMANTIC_WAITER_SYSTEM_INSTRUCTION


def test_transport_failure_raises_model_unavailable():
    class Broken:
        model_id = "broken"

        def complete(self, system_instruction, user_message):
            raise ConnectionError("no route to host")

    adapter = SemanticWaiterModelAdapter(Broken())

    with pytest.raises(SemanticModelUnavailable):
        adapter.interpret(DOGFOOD_PROMPT, _evidence())


def test_malformed_model_output_raises_output_invalid():
    adapter = SemanticWaiterModelAdapter(ScriptedSemanticModelClient(["not json at all"]))

    with pytest.raises(SemanticOutputInvalid):
        adapter.interpret(DOGFOOD_PROMPT, _evidence())


def test_adapter_never_mutates_the_supplied_evidence():
    evidence = _evidence()
    snapshot = copy.deepcopy(evidence.as_dict())

    SemanticWaiterModelAdapter(ScriptedSemanticModelClient([_json()])).interpret(
        DOGFOOD_PROMPT, evidence
    )

    assert evidence.as_dict() == snapshot


# ══ repair request ════════════════════════════════════════════════════════════

def _failed_report() -> PreservationReport:
    return PreservationReport(
        status=PRESERVATION_FAILED,
        preserved_items=(PreservationItem(kind="subject", value="DeepSeek Harness"),),
        missing_items=(
            PreservationItem(kind="subject", value="C.A.T.T.U.S"),
            PreservationItem(kind="framework_value", value="Orthogonal"),
        ),
        reasons=("explicit subject 'C.A.T.T.U.S' is absent from the interpretation",),
    )


def test_repair_request_names_the_missing_items():
    request = build_repair_request(DOGFOOD_PROMPT, _evidence(), _failed_report())

    assert "C.A.T.T.U.S" in request
    assert "Orthogonal" in request


def test_repair_request_repeats_the_do_not_solve_boundary():
    request = build_repair_request(DOGFOOD_PROMPT, _evidence(), _failed_report()).lower()

    assert "do not solve" in request


def test_repair_request_is_not_a_vague_try_again():
    request = build_repair_request(DOGFOOD_PROMPT, _evidence(), _failed_report()).lower()

    assert "try again" not in request
    assert "think harder" not in request
    assert "preservation" in request


def test_repair_request_lists_every_explicit_item_that_must_remain():
    request = build_repair_request(DOGFOOD_PROMPT, _evidence(), _failed_report())

    for value in RUBRIC:
        assert value in request


def test_repair_uses_one_further_model_call():
    client = ScriptedSemanticModelClient([_json(), _json()])
    adapter = SemanticWaiterModelAdapter(client)

    adapter.interpret(DOGFOOD_PROMPT, _evidence())
    adapter.repair(DOGFOOD_PROMPT, _evidence(), _failed_report())

    assert adapter.call_count == 2


def test_scripted_client_runs_out_of_responses_loudly():
    adapter = SemanticWaiterModelAdapter(ScriptedSemanticModelClient([_json()]))
    adapter.interpret(DOGFOOD_PROMPT, _evidence())

    with pytest.raises(SemanticModelUnavailable):
        adapter.interpret(DOGFOOD_PROMPT, _evidence())
