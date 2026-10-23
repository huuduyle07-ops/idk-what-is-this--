"""INPUT.1 — end-to-end input-understanding tests.

Includes the DeepSeek Harness dogfood regression: the run where the comparative
nature of the request was lost, C.A.T.T.U.S disappeared as a comparison
subject, and the supplied rubric was not preserved.  INPUT.1 must represent
that order faithfully and must refuse to declare routing safe when it cannot.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from core.explicit_evidence import extract_explicit_evidence
from core.input_understanding import INPUT_UNDERSTANDING_STAGES, understand_request
from core.semantic_waiter import (
    ExplicitEvidenceInterpreter,
    SemanticInterpretation,
    StaticSemanticInterpreter,
)
from core.task_contract import (
    PRESERVATION_FAILED,
    PRESERVATION_PASSED,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Constraint,
    Subject,
    TaskClassification,
    UserSuppliedFramework,
    render_task_contract_json,
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_1_MODULES = (
    "explicit_evidence",
    "task_contract",
    "semantic_waiter",
    "requirement_preservation",
    "input_understanding",
    # DEFECT.FACT.LIVE.1 types explicit behavioral claims at this same boundary
    # and is consumed by the extractor above, so it lives under the same import,
    # stdlib and provider-token rules the rest of INPUT.1 does.
    "behavioral_expectation",
    # OOP.INTENT.DESIGN.1 adds bounded literal design evidence at intake and
    # inherits the same purity and authority checks as the frozen boundary.
    "explicit_design_evidence",
)


# ══ the DeepSeek Harness dogfood regression ═══════════════════════════════════

def test_dogfood_raw_request_survives_verbatim():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.raw_request.text == DOGFOOD_PROMPT


def test_dogfood_task_is_representable_as_comparative_analysis():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.task.type == "comparative_analysis"


def test_dogfood_keeps_deepseek_harness_as_a_subject():
    contract = understand_request(DOGFOOD_PROMPT)

    assert "DeepSeek Harness" in contract.subject_values()


def test_dogfood_keeps_cattus_as_a_subject():
    contract = understand_request(DOGFOOD_PROMPT)

    assert "C.A.T.T.U.S" in contract.subject_values()


def test_dogfood_keeps_the_comparison_relationship_between_both_subjects():
    contract = understand_request(DOGFOOD_PROMPT)

    comparisons = [rel for rel in contract.relationships if rel.type == "comparison"]
    assert len(comparisons) == 1
    assert set(comparisons[0].subjects) == {"DeepSeek Harness", "C.A.T.T.U.S"}


def test_dogfood_recognises_the_supplied_list_as_an_evaluation_framework():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.user_supplied_framework is not None
    assert contract.user_supplied_framework.type == "framework"


def test_dogfood_retains_exactly_the_five_rubric_values():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.user_supplied_framework.values == RUBRIC
    assert len(contract.user_supplied_framework.values) == 5


def test_dogfood_retains_the_supplied_rubric_order():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.user_supplied_framework.ordered is True
    assert list(contract.user_supplied_framework.values) == list(RUBRIC)


def test_dogfood_marks_user_supplied_values_explicit_not_inferred():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.user_supplied_framework.provenance == PROVENANCE_EXPLICIT
    for subject in contract.subjects:
        if subject.value in {"DeepSeek Harness", "C.A.T.T.U.S"}:
            assert subject.provenance == PROVENANCE_EXPLICIT
            assert subject.confidence is None


def test_dogfood_passes_preservation_and_permits_routing():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.preservation.status == PRESERVATION_PASSED
    assert contract.routing_allowed is True


def test_dogfood_contract_performs_no_execution():
    guardrails = understand_request(DOGFOOD_PROMPT).as_dict()["guardrails"]

    for flag in (
        "execution_performed",
        "mode_dispatch_performed",
        "mode_selection_performed",
        "repository_scan_performed",
        "repository_index_performed",
        "patch_generation_performed",
        "patch_application_performed",
        "validation_run",
        "benchmark_run_performed",
        "dream_run_performed",
        "project_evolution_run_performed",
        "lesson_promotion_performed",
        "model_call_performed",
        "provider_selected",
        "network_call_performed",
        "read_authority",
        "write_authority",
    ):
        assert guardrails[flag] is False, flag


def test_dogfood_contract_serializes_losslessly():
    contract = understand_request(DOGFOOD_PROMPT)
    payload = json.loads(render_task_contract_json(contract))

    assert payload["raw_request"]["text"] == DOGFOOD_PROMPT
    assert payload["user_supplied_framework"]["values"] == list(RUBRIC)
    assert payload["routing_allowed"] is True


# ══ negative cases: the gate must catch a lossy interpreter ═══════════════════

def _lossy(interpretation: SemanticInterpretation):
    return StaticSemanticInterpreter(interpretation)


def _faithful_interpretation(text: str = DOGFOOD_PROMPT) -> SemanticInterpretation:
    return ExplicitEvidenceInterpreter().interpret(text, extract_explicit_evidence(text))


def test_interpreter_that_drops_cattus_blocks_routing():
    faithful = _faithful_interpretation()
    dropped = dataclasses.replace(
        faithful,
        subjects=tuple(s for s in faithful.subjects if s.value != "C.A.T.T.U.S"),
        relationships=(),
    )

    contract = understand_request(DOGFOOD_PROMPT, interpreter=_lossy(dropped))

    assert contract.preservation.status == PRESERVATION_FAILED
    assert contract.routing_allowed is False
    assert "C.A.T.T.U.S" in contract.preservation.missing_values("subject")


def test_interpreter_that_keeps_subjects_but_drops_a_rubric_item_blocks_routing():
    faithful = _faithful_interpretation()
    dropped = dataclasses.replace(
        faithful,
        framework=UserSuppliedFramework(
            type="framework",
            values=tuple(v for v in RUBRIC if v != "Orthogonal"),
            provenance=PROVENANCE_EXPLICIT,
        ),
    )

    contract = understand_request(DOGFOOD_PROMPT, interpreter=_lossy(dropped))

    assert set(contract.subject_values()) >= {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert contract.preservation.status == PRESERVATION_FAILED
    assert contract.routing_allowed is False
    assert "Orthogonal" in contract.preservation.missing_values("framework_value")


def test_interpreter_that_rewrites_a_do_not_constraint_blocks_routing():
    text = "Improve the parser. Do not modify tests."
    faithful = _faithful_interpretation(text)
    rewritten = dataclasses.replace(
        faithful,
        constraints=(
            Constraint(
                kind="prohibition",
                text="Do not modify tests unless necessary",
                provenance=PROVENANCE_EXPLICIT,
            ),
        ),
    )

    contract = understand_request(text, interpreter=_lossy(rewritten))

    assert contract.preservation.status == PRESERVATION_FAILED
    assert contract.routing_allowed is False
    assert "Do not modify tests" in contract.preservation.missing_values("constraint")


def test_interpreter_adding_inferred_metadata_may_still_pass():
    faithful = _faithful_interpretation()
    enriched = dataclasses.replace(
        faithful,
        subjects=faithful.subjects
        + (
            Subject(
                value="harness evaluation methodology",
                provenance=PROVENANCE_INFERRED,
                confidence=0.55,
            ),
        ),
        ambiguities=("'Harness' may mean the repo or the runner",),
        missing_information=("no local checkout of DeepSeek Harness was supplied",),
    )

    contract = understand_request(DOGFOOD_PROMPT, interpreter=_lossy(enriched))

    assert contract.preservation.status == PRESERVATION_PASSED
    assert contract.routing_allowed is True
    assert contract.ambiguities
    assert contract.missing_information


def test_confident_interpreter_that_loses_a_subject_still_blocks_routing():
    overconfident = SemanticInterpretation(
        task=TaskClassification(
            type="analysis", provenance=PROVENANCE_INFERRED, confidence=0.97
        ),
        subjects=(Subject(value="DeepSeek Harness", provenance=PROVENANCE_EXPLICIT),),
        framework=UserSuppliedFramework(
            type="framework", values=RUBRIC, provenance=PROVENANCE_EXPLICIT
        ),
    )

    contract = understand_request(DOGFOOD_PROMPT, interpreter=_lossy(overconfident))

    assert contract.routing_allowed is False
    assert contract.task.confidence == 0.97


# ══ conversational input stays small and never demands a Goal Brief ═══════════

def test_simple_conversational_input_yields_a_small_valid_contract():
    contract = understand_request("thanks, that helped a lot")

    assert contract.raw_request.text == "thanks, that helped a lot"
    assert contract.task.type == "conversation"
    assert contract.subjects == ()
    assert contract.relationships == ()
    assert contract.user_supplied_framework is None
    assert contract.constraints == ()
    assert contract.routing_allowed is True


def test_conversational_input_does_not_demand_a_goal_brief():
    contract = understand_request("hey, how are you?")

    assert contract.as_dict()["guardrails"]["goal_brief_required"] is False
    assert contract.missing_information == ()


def test_empty_request_is_representable():
    contract = understand_request("")

    assert contract.raw_request.text == ""
    assert contract.preservation.status == PRESERVATION_PASSED


# ══ pipeline shape ════════════════════════════════════════════════════════════

def test_pipeline_stages_stop_before_the_execution_waiter():
    assert INPUT_UNDERSTANDING_STAGES == (
        "extract_explicit_evidence",
        "semantic_interpretation",
        "requirement_preservation_gate",
        "task_contract_assembly",
    )


def test_pipeline_hands_the_waiter_the_raw_prompt_and_the_evidence():
    interpreter = StaticSemanticInterpreter(_faithful_interpretation())

    understand_request(DOGFOOD_PROMPT, interpreter=interpreter)

    assert len(interpreter.calls) == 1
    raw_prompt, evidence = interpreter.calls[0]
    assert raw_prompt == DOGFOOD_PROMPT
    assert evidence.framework.values == RUBRIC


def test_contract_carries_the_explicit_evidence_it_was_built_from():
    contract = understand_request(DOGFOOD_PROMPT)

    assert contract.explicit_evidence.framework.values == RUBRIC
    assert contract.explicit_evidence.comparisons[0].subjects == (
        "DeepSeek Harness",
        "C.A.T.T.U.S",
    )


def test_non_string_input_is_rejected():
    with pytest.raises(TypeError):
        understand_request(None)  # type: ignore[arg-type]


def test_interpreter_returning_the_wrong_type_is_rejected():
    class Rogue:
        def interpret(self, raw_prompt, explicit_evidence):
            return {"task": "whatever"}

    with pytest.raises(TypeError):
        understand_request(DOGFOOD_PROMPT, interpreter=Rogue())


def test_understanding_is_deterministic():
    first = understand_request(DOGFOOD_PROMPT)
    second = understand_request(DOGFOOD_PROMPT)

    assert first.as_dict() == second.as_dict()


# ══ INPUT.1 stays inert: no execution surface is reachable ════════════════════

def _module_source(name: str) -> str:
    return (PROJECT_ROOT / "core" / f"{name}.py").read_text(encoding="utf-8")


def test_input_1_modules_import_no_execution_subsystem():
    allowed_core = set(INPUT_1_MODULES)
    for name in INPUT_1_MODULES:
        tree = ast.parse(_module_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("core."):
                    assert module.split(".", 1)[1] in allowed_core, (
                        f"{name} imports outside INPUT.1: {module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("core."), (
                        f"{name} imports outside INPUT.1: {alias.name}"
                    )


def test_input_1_modules_use_only_inert_stdlib():
    allowed_top = {"__future__", "dataclasses", "hashlib", "json", "re", "typing", "core"}
    for name in INPUT_1_MODULES:
        tree = ast.parse(_module_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                assert top in allowed_top, f"{name}: unexpected import {node.module!r}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top in allowed_top, f"{name}: unexpected import {alias.name!r}"


def test_input_1_modules_contain_no_execution_or_provider_tokens():
    for name in INPUT_1_MODULES:
        source = _module_source(name)
        for token in (
            "subprocess",
            "Popen",
            "os.system",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "OpenAI",
            "Anthropic",
            "Gemini",
            "apply_patch",
            "generate_patch",
            "run_benchmarks",
            "mode_router",
            "git push",
        ):
            assert token not in source, f"forbidden token {token!r} in core/{name}.py"
