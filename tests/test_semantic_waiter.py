"""INPUT.1 — Semantic Waiter boundary tests.

The Semantic Waiter understands the meaning of the order and nothing else.  It
takes the raw prompt plus explicit evidence and returns an interpretation.  It
never solves the task, never touches the repository, never picks a mode, and
never picks a model.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from core.explicit_evidence import extract_explicit_evidence
from core.semantic_waiter import (
    SEMANTIC_WAITER_FORBIDDEN_ACTIONS,
    SEMANTIC_WAITER_RESPONSIBILITY,
    ExplicitEvidenceInterpreter,
    SemanticInterpretation,
    SemanticInterpreter,
    StaticSemanticInterpreter,
)
from core.task_contract import (
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Subject,
    TaskClassification,
)


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "semantic_waiter.py"


def _interpret(text: str) -> SemanticInterpretation:
    return ExplicitEvidenceInterpreter().interpret(text, extract_explicit_evidence(text))


# ── the boundary itself ───────────────────────────────────────────────────────

def test_default_interpreter_satisfies_the_interpreter_protocol():
    assert isinstance(ExplicitEvidenceInterpreter(), SemanticInterpreter)


def test_static_interpreter_satisfies_the_interpreter_protocol():
    interpretation = _interpret("hello")
    assert isinstance(StaticSemanticInterpreter(interpretation), SemanticInterpreter)


def test_responsibility_is_stated():
    assert "meaning" in SEMANTIC_WAITER_RESPONSIBILITY.lower()


def test_forbidden_actions_cover_the_documented_boundary():
    forbidden = set(SEMANTIC_WAITER_FORBIDDEN_ACTIONS)

    assert "solve_the_task" in forbidden
    assert "inspect_the_repository" in forbidden
    assert "select_execution_mode" in forbidden
    assert "select_provider_or_model" in forbidden
    assert "patch_files" in forbidden
    assert "run_validation" in forbidden
    assert "start_benchmarks" in forbidden
    assert "start_dream" in forbidden
    assert "start_project_evolution" in forbidden
    assert "authorize_writes" in forbidden


def test_module_imports_stay_inert():
    source = MODULE_PATH.read_text(encoding="utf-8")
    allowed_top = {"__future__", "dataclasses", "typing", "core"}

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in allowed_top, f"unexpected import: {node.module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed_top, f"unexpected import: {alias.name!r}"


def test_module_source_contains_no_execution_or_provider_tokens():
    source = MODULE_PATH.read_text(encoding="utf-8")

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
        "DeepSeek",
        "apply_patch",
        "generate_patch",
        "run_benchmarks",
        "git push",
    ):
        assert token not in source, f"forbidden token in semantic waiter: {token}"


# ── default deterministic interpreter ─────────────────────────────────────────

def test_comparison_subjects_are_marked_explicit():
    interpretation = _interpret(DOGFOOD_PROMPT)

    by_value = {subject.value: subject for subject in interpretation.subjects}
    assert "DeepSeek Harness" in by_value
    assert "C.A.T.T.U.S" in by_value
    assert by_value["C.A.T.T.U.S"].provenance == PROVENANCE_EXPLICIT
    assert by_value["C.A.T.T.U.S"].confidence is None


def test_comparison_relationship_is_explicit():
    interpretation = _interpret(DOGFOOD_PROMPT)

    assert len(interpretation.relationships) == 1
    relationship = interpretation.relationships[0]
    assert relationship.type == "comparison"
    assert set(relationship.subjects) == {"DeepSeek Harness", "C.A.T.T.U.S"}
    assert relationship.provenance == PROVENANCE_EXPLICIT


def test_task_type_is_comparative_analysis_and_stays_inferred():
    interpretation = _interpret(DOGFOOD_PROMPT)

    assert interpretation.task.type == "comparative_analysis"
    assert interpretation.task.provenance == PROVENANCE_INFERRED


def test_rubric_is_carried_in_supplied_order_and_marked_explicit():
    interpretation = _interpret(DOGFOOD_PROMPT)

    framework = interpretation.framework
    assert framework is not None
    assert framework.provenance == PROVENANCE_EXPLICIT
    assert framework.values == (
        "Equivalent",
        "DeepSeek stronger",
        "C.A.T.T.U.S stronger",
        "Orthogonal",
        "Not worth adopting",
    )


def test_entity_subsumed_by_a_longer_subject_is_not_repeated():
    interpretation = _interpret(DOGFOOD_PROMPT)

    assert "DeepSeek" not in interpretation.subjects_by_value()


def test_explicit_constraints_are_carried_through():
    interpretation = _interpret("Fix the parser. Do not modify tests.")

    kinds = {(item.kind, item.text, item.provenance) for item in interpretation.constraints}
    assert ("prohibition", "Do not modify tests", PROVENANCE_EXPLICIT) in kinds


def test_requested_output_is_explicit_when_literally_asked_for():
    interpretation = _interpret("Compare Redis with Memcached as a table.")

    assert interpretation.requested_output is not None
    assert interpretation.requested_output.format == "table"
    assert interpretation.requested_output.provenance == PROVENANCE_EXPLICIT


def test_conversational_input_stays_small():
    interpretation = _interpret("hey, how are you?")

    assert interpretation.task.type == "question"
    assert interpretation.subjects == ()
    assert interpretation.framework is None
    assert interpretation.constraints == ()
    assert interpretation.missing_information == ()


def test_plain_statement_with_no_evidence_is_conversation():
    interpretation = _interpret("thanks, that helped a lot")

    assert interpretation.task.type == "conversation"


def test_default_interpreter_invents_no_ambiguities():
    interpretation = _interpret(DOGFOOD_PROMPT)

    assert interpretation.ambiguities == ()
    assert interpretation.missing_information == ()


# ── execution requirements stay inferred metadata ─────────────────────────────

def test_execution_requirements_are_inferred_not_explicit():
    interpretation = _interpret(DOGFOOD_PROMPT)

    assert interpretation.execution_requirements.provenance == PROVENANCE_INFERRED


def test_file_path_evidence_marks_repository_inspection_required():
    interpretation = _interpret("Fix core/router.py")

    assert interpretation.execution_requirements.repository_inspection_required is True
    assert interpretation.execution_requirements.local_repository_required is True


def test_url_evidence_marks_external_information_required():
    interpretation = _interpret("Read https://example.com/spec and summarise it")

    assert interpretation.execution_requirements.external_information_required is True


def test_bare_prompt_requires_nothing():
    requirements = _interpret("hello there").execution_requirements

    assert requirements.repository_inspection_required is False
    assert requirements.external_information_required is False


# ── static test double ────────────────────────────────────────────────────────

def test_static_interpreter_returns_the_supplied_interpretation():
    supplied = SemanticInterpretation(
        task=TaskClassification(type="analysis", provenance=PROVENANCE_INFERRED),
        subjects=(Subject(value="only-one", provenance=PROVENANCE_INFERRED),),
    )
    interpreter = StaticSemanticInterpreter(supplied)

    result = interpreter.interpret(DOGFOOD_PROMPT, extract_explicit_evidence(DOGFOOD_PROMPT))

    assert result is supplied


def test_static_interpreter_records_what_the_boundary_received():
    supplied = SemanticInterpretation(
        task=TaskClassification(type="analysis", provenance=PROVENANCE_INFERRED)
    )
    interpreter = StaticSemanticInterpreter(supplied)
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    interpreter.interpret(DOGFOOD_PROMPT, evidence)

    assert len(interpreter.calls) == 1
    assert interpreter.calls[0][0] == DOGFOOD_PROMPT
    assert interpreter.calls[0][1] is evidence


# ── immutability / determinism ────────────────────────────────────────────────

def test_interpretation_is_immutable():
    interpretation = _interpret(DOGFOOD_PROMPT)

    with pytest.raises(dataclasses.FrozenInstanceError):
        interpretation.subjects = ()  # type: ignore[misc]


def test_default_interpreter_is_deterministic():
    first = _interpret(DOGFOOD_PROMPT)
    second = _interpret(DOGFOOD_PROMPT)

    assert first == second
