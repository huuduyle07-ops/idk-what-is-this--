"""INPUT.2 — semantic evaluation matrix and anti-hallucination tests.

The DeepSeek dogfood sentence is patient zero, not the benchmark.  This module
runs the whole case matrix against a compliant scripted model (no network) and
proves the gate still catches lossy or inventive interpretations.

The same cases run against a real model only when the live smoke is explicitly
enabled; see ``test_live_semantic_waiter_smoke``.
"""

from __future__ import annotations

import json
import os

import pytest

from core.explicit_evidence import extract_explicit_evidence
from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_evals import (
    LIVE_SMOKE_ENV_VAR,
    SEMANTIC_EVAL_CASES,
    SemanticEvalCase,
    evaluate_semantic_case,
    find_eval_case,
    summarize_eval_results,
)
from core.semantic_waiter_runner import (
    SEMANTIC_INTERPRETATION_OK,
    understand_request_semantically,
)


# ══ compliant-model response construction ═════════════════════════════════════

def _echo_evidence(prompt: str) -> dict:
    """The literal half of a compliant answer: copy explicit evidence verbatim.

    A well-behaved model does exactly this with the EXPLICIT EVIDENCE section —
    which is the only way an ``explicit`` label can survive the gate.
    """
    evidence = extract_explicit_evidence(prompt)
    subjects = [
        {"value": value, "provenance": "explicit", "role": "comparison_subject"}
        for value in evidence.comparison_subjects()
    ]
    seen = {s["value"].casefold() for s in subjects}
    for entity in evidence.named_entities:
        if entity.casefold() not in seen:
            subjects.append(
                {"value": entity, "provenance": "explicit", "role": "named_entity"}
            )

    payload: dict = {
        "task": {"type": "unknown"},
        "subjects": subjects,
        "relationships": [
            {
                "type": "comparison",
                "subjects": list(comparison.subjects),
                "provenance": "explicit",
            }
            for comparison in evidence.comparisons
        ],
        "user_supplied_framework": (
            {
                "type": evidence.framework.type,
                "values": list(evidence.framework.values),
                "provenance": "explicit",
                "ordered": evidence.framework.ordered,
            }
            if evidence.framework
            else None
        ),
        "requested_output": (
            {"format": evidence.requested_outputs[0].format, "provenance": "explicit"}
            if evidence.requested_outputs
            else None
        ),
        "constraints": [
            {"kind": item.kind, "text": item.text, "provenance": "explicit"}
            for item in evidence.constraints
        ],
        "ambiguities": [],
        "missing_information": [],
        "execution_requirements": {},
    }
    return payload


def _compliant(case: SemanticEvalCase, **semantic) -> str:
    """Literal echo plus the case's hand-authored semantic conclusions."""
    payload = _echo_evidence(case.prompt)
    for key, value in semantic.items():
        if key == "add_subjects":
            payload["subjects"] = payload["subjects"] + list(value)
        elif key == "add_relationships":
            payload["relationships"] = payload["relationships"] + list(value)
        else:
            payload[key] = value
    return json.dumps(payload)


def _case(case_id: str) -> SemanticEvalCase:
    return find_eval_case(case_id)


# Each entry is what a compliant model would return for that case. The literal
# parts are echoed; every semantic judgement below is deliberate.
def _responses() -> dict[str, str]:
    dogfood = _case("A_dogfood_original")
    paraphrase = _case("B_paraphrase")
    vietnamese = _case("C_vietnamese")
    code = _case("D_bounded_code_comparison")
    explain = _case("E_explanation_not_comparison")
    ambiguous = _case("F_ambiguous_reference")
    constraint = _case("G_explicit_constraint")
    output = _case("H_output_contract")
    notes = _case("I_notes_are_not_a_rubric")
    inferred = _case("J_inferred_metadata")
    owasp = _case("K_owasp_reference")
    package = _case("L_explain_package")

    return {
        dogfood.case_id: _compliant(
            dogfood, task={"type": "comparative_analysis", "confidence": 0.93}
        ),
        paraphrase.case_id: _compliant(
            paraphrase, task={"type": "comparative_analysis", "confidence": 0.9}
        ),
        # Vietnamese: INPUT.1 cannot literally extract the comparison or the
        # rubric, so a truthful model marks both inferred rather than explicit.
        vietnamese.case_id: _compliant(
            vietnamese,
            task={"type": "comparative_analysis", "confidence": 0.85},
            add_relationships=[
                {
                    "type": "comparison",
                    "subjects": ["DeepSeek Harness", "C.A.T.T.U.S"],
                    "provenance": "inferred",
                    "confidence": 0.85,
                }
            ],
            user_supplied_framework={
                "type": "criteria",
                "values": [
                    "tương đương",
                    "DeepSeek mạnh hơn",
                    "C.A.T.T.U.S mạnh hơn",
                    "độc lập",
                    "không đáng để học theo",
                ],
                "provenance": "inferred",
                "ordered": True,
            },
        ),
        code.case_id: _compliant(
            code,
            task={"type": "comparative_analysis", "confidence": 0.88},
            execution_requirements={
                "multi_stage": False,
                "external_information_required": False,
                "repository_inspection_required": False,
                "local_repository_required": False,
            },
        ),
        explain.case_id: _compliant(
            explain, task={"type": "question", "confidence": 0.8}
        ),
        ambiguous.case_id: _compliant(
            ambiguous,
            task={"type": "comparative_analysis", "confidence": 0.5},
            ambiguities=[
                "'it' and 'the other one' are not identified anywhere in the request"
            ],
            missing_information=["the two things to compare"],
        ),
        constraint.case_id: _compliant(
            constraint,
            task={"type": "analysis", "confidence": 0.8},
        ),
        # INPUT.1 has no literal cue for "return a Markdown table", so the
        # format is honestly inferred rather than claimed as explicit.
        output.case_id: _compliant(
            output,
            task={"type": "comparative_analysis", "confidence": 0.85},
            requested_output={"format": "markdown", "provenance": "inferred", "confidence": 0.8},
        ),
        notes.case_id: _compliant(
            notes, task={"type": "conversation", "confidence": 0.6}
        ),
        inferred.case_id: _compliant(
            inferred,
            task={"type": "comparative_analysis", "confidence": 0.9},
            execution_requirements={
                "multi_stage": True,
                "external_information_required": True,
                "repository_inspection_required": False,
                "local_repository_required": False,
                "confidence": 0.7,
            },
            ambiguities=["scope of 'Harness' could mean the repo or the runner"],
        ),
        owasp.case_id: _compliant(
            owasp,
            task={"type": "review", "confidence": 0.85},
            user_supplied_framework={
                "type": "checklist",
                "values": ["OWASP Top 10"],
                "provenance": "inferred",
                "confidence": 0.8,
                "ordered": False,
            },
        ),
        package.case_id: _compliant(
            package, task={"type": "question", "confidence": 0.8}
        ),
    }


def _run_case(case: SemanticEvalCase, response: str):
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([response, response], model_id="scripted-eval-model")
    )
    return understand_request_semantically(case.prompt, adapter=adapter)


# ══ matrix shape ══════════════════════════════════════════════════════════════

def test_matrix_covers_every_required_case_shape():
    ids = {case.case_id for case in SEMANTIC_EVAL_CASES}

    assert {
        "A_dogfood_original",
        "B_paraphrase",
        "C_vietnamese",
        "D_bounded_code_comparison",
        "E_explanation_not_comparison",
        "F_ambiguous_reference",
        "G_explicit_constraint",
        "H_output_contract",
        "I_notes_are_not_a_rubric",
        "J_inferred_metadata",
    } <= ids


def test_matrix_is_more_than_the_dogfood_sentence():
    assert len(SEMANTIC_EVAL_CASES) >= 10


def test_every_case_has_a_compliant_reference_response():
    assert {case.case_id for case in SEMANTIC_EVAL_CASES} == set(_responses())


def test_case_ids_are_unique():
    ids = [case.case_id for case in SEMANTIC_EVAL_CASES]
    assert len(ids) == len(set(ids))


# ══ a compliant model passes every case ═══════════════════════════════════════

@pytest.mark.parametrize("case", SEMANTIC_EVAL_CASES, ids=lambda c: c.case_id)
def test_compliant_model_passes_the_case(case):
    outcome = _run_case(case, _responses()[case.case_id])
    result = evaluate_semantic_case(case, outcome)

    assert result.passed, f"{case.case_id}: {result.failures}"


@pytest.mark.parametrize("case", SEMANTIC_EVAL_CASES, ids=lambda c: c.case_id)
def test_compliant_model_survives_preservation(case):
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.status == SEMANTIC_INTERPRETATION_OK
    assert outcome.contract.routing_allowed is True


@pytest.mark.parametrize("case", SEMANTIC_EVAL_CASES, ids=lambda c: c.case_id)
def test_raw_request_survives_every_case(case):
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.contract.raw_request.text == case.prompt


def test_summary_reports_all_green_for_compliant_responses():
    results = [
        evaluate_semantic_case(case, _run_case(case, _responses()[case.case_id]))
        for case in SEMANTIC_EVAL_CASES
    ]
    summary = summarize_eval_results(results)

    assert summary["total"] == len(SEMANTIC_EVAL_CASES)
    assert summary["failed"] == 0
    assert summary["passed"] == summary["total"]


# ══ named expectations from the spec ══════════════════════════════════════════

def test_dogfood_keeps_both_subjects_and_five_ordered_rubric_values():
    case = _case("A_dogfood_original")
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.contract.task.type == "comparative_analysis"
    assert set(outcome.contract.subject_values()) >= {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert len(outcome.contract.user_supplied_framework.values) == 5
    assert outcome.contract.user_supplied_framework.values[3] == "Orthogonal"


def test_paraphrase_keeps_both_subjects():
    case = _case("B_paraphrase")
    outcome = _run_case(case, _responses()[case.case_id])
    keys = " ".join(outcome.contract.subject_values()).casefold()

    assert "c.a.t.t.u.s" in keys
    assert "deepseek harness" in keys
    assert outcome.contract.task.type == "comparative_analysis"


def test_vietnamese_keeps_both_systems_and_marks_inference_honestly():
    case = _case("C_vietnamese")
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.contract.task.type == "comparative_analysis"
    assert set(outcome.contract.subject_values()) >= {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert outcome.contract.user_supplied_framework is not None
    assert len(outcome.contract.user_supplied_framework.values) == 5
    # INPUT.1 cannot literally back a Vietnamese comparison, so it must be
    # inferred rather than dressed up as the user's own words.
    assert outcome.contract.user_supplied_framework.provenance == "inferred"


def test_vietnamese_claiming_explicit_without_literal_backing_fails():
    case = _case("C_vietnamese")
    dishonest = json.loads(_responses()[case.case_id])
    dishonest["user_supplied_framework"]["provenance"] = "explicit"

    outcome = _run_case(case, json.dumps(dishonest))

    assert outcome.status != SEMANTIC_INTERPRETATION_OK
    assert outcome.contract.routing_allowed is False


def test_explicit_constraint_is_preserved_verbatim():
    case = _case("G_explicit_constraint")
    outcome = _run_case(case, _responses()[case.case_id])
    texts = [item.text for item in outcome.contract.constraints]

    assert any("do not inspect tests" in text for text in texts)


def test_output_contract_is_carried():
    case = _case("H_output_contract")
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.contract.requested_output is not None
    assert outcome.contract.requested_output.format in {"markdown", "table"}


def test_plain_notes_list_is_not_promoted_to_a_rubric():
    case = _case("I_notes_are_not_a_rubric")
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.contract.user_supplied_framework is None


def test_inferred_metadata_does_not_block_a_pass():
    case = _case("J_inferred_metadata")
    outcome = _run_case(case, _responses()[case.case_id])

    assert outcome.status == SEMANTIC_INTERPRETATION_OK
    assert outcome.contract.execution_requirements.multi_stage is True
    assert outcome.contract.execution_requirements.provenance == "inferred"


# ══ anti-hallucination ════════════════════════════════════════════════════════

def test_explanation_request_must_not_invent_a_comparison():
    case = _case("E_explanation_not_comparison")
    inventive = json.loads(_responses()[case.case_id])
    inventive["task"] = {"type": "comparative_analysis", "confidence": 0.9}
    inventive["subjects"].append({"value": "C.A.T.T.U.S", "provenance": "inferred"})
    inventive["relationships"] = [
        {
            "type": "comparison",
            "subjects": ["DeepSeek Harness", "C.A.T.T.U.S"],
            "provenance": "inferred",
        }
    ]

    result = evaluate_semantic_case(case, _run_case(case, json.dumps(inventive)))

    assert result.passed is False
    assert any("comparison" in failure for failure in result.failures)


def test_explanation_request_must_not_invent_a_rubric():
    case = _case("E_explanation_not_comparison")
    inventive = json.loads(_responses()[case.case_id])
    inventive["user_supplied_framework"] = {
        "type": "rubric",
        "values": ["Equivalent", "Stronger", "Orthogonal"],
        "provenance": "inferred",
    }

    result = evaluate_semantic_case(case, _run_case(case, json.dumps(inventive)))

    assert result.passed is False


def test_explain_package_must_not_invent_repository_or_benchmark_work():
    case = _case("L_explain_package")
    inventive = json.loads(_responses()[case.case_id])
    inventive["execution_requirements"] = {
        "repository_inspection_required": True,
        "local_repository_required": True,
        "multi_stage": True,
    }

    result = evaluate_semantic_case(case, _run_case(case, json.dumps(inventive)))

    assert result.passed is False
    assert any("repository_inspection_required" in failure for failure in result.failures)


def test_snippet_comparison_must_not_invent_repository_inspection():
    case = _case("D_bounded_code_comparison")
    inventive = json.loads(_responses()[case.case_id])
    inventive["execution_requirements"] = {
        "repository_inspection_required": True,
        "external_information_required": True,
    }

    result = evaluate_semantic_case(case, _run_case(case, json.dumps(inventive)))

    assert result.passed is False


def test_ambiguous_reference_must_not_guess_the_entities():
    case = _case("F_ambiguous_reference")
    guessing = json.loads(_responses()[case.case_id])
    guessing["ambiguities"] = []
    guessing["subjects"] = [
        {"value": "DeepSeek Harness", "provenance": "inferred", "confidence": 0.4},
        {"value": "C.A.T.T.U.S", "provenance": "inferred", "confidence": 0.4},
    ]

    result = evaluate_semantic_case(case, _run_case(case, json.dumps(guessing)))

    assert result.passed is False


def test_owasp_review_may_infer_security_review_but_must_keep_the_reference():
    case = _case("K_owasp_reference")
    outcome = _run_case(case, _responses()[case.case_id])
    texts = " ".join(item.text for item in outcome.contract.constraints)

    assert "OWASP Top 10" in texts
    assert outcome.contract.task.type == "review"


def test_owasp_review_dropping_the_reference_fails_preservation():
    case = _case("K_owasp_reference")
    dropped = json.loads(_responses()[case.case_id])
    dropped["constraints"] = []

    outcome = _run_case(case, json.dumps(dropped))

    assert outcome.status != SEMANTIC_INTERPRETATION_OK
    assert outcome.contract.routing_allowed is False


# ══ live provider smoke — opt-in only, never required ═════════════════════════

def test_live_smoke_is_opt_in_and_off_by_default():
    assert LIVE_SMOKE_ENV_VAR == "RUN_LIVE_SEMANTIC_WAITER_TESTS"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_SEMANTIC_WAITER_TESTS") != "1",
    reason="live semantic waiter smoke is opt-in; set RUN_LIVE_SEMANTIC_WAITER_TESTS=1",
)
def test_live_semantic_waiter_smoke():
    from core.semantic_waiter_client import build_live_semantic_adapter

    adapter = build_live_semantic_adapter()
    case = _case("A_dogfood_original")

    outcome = understand_request_semantically(case.prompt, adapter=adapter)
    result = evaluate_semantic_case(case, outcome)

    print(
        f"\nlive semantic smoke: model={outcome.receipt.configured_model} "
        f"status={outcome.status} calls={outcome.receipt.model_call_count} "
        f"eval_passed={result.passed} failures={result.failures}"
    )
    assert outcome.receipt.model_call_count <= 2
    assert outcome.receipt.as_dict()["authority"]["execution_authority"] is False
