"""INPUT.1 — input-understanding pipeline.

Assembles the four INPUT.1 stages into one pure call:

    user prompt
        -> deterministic explicit extractor      (core.explicit_evidence)
        -> Semantic Waiter boundary              (core.semantic_waiter)
        -> deterministic preservation gate       (core.requirement_preservation)
        -> lossless Task Contract                (core.task_contract)

The pipeline stops there, on purpose.  The Execution Waiter, the mode router
and the kitchen are later phases; ``routing_allowed`` is a fact recorded on the
contract, never an action taken by it.

Nothing here executes a task, dispatches a mode, scans or indexes a repository,
generates or applies a patch, runs validation or benchmarks, launches a worker,
starts Dream or Project Evolution, selects a provider or model, contacts a
network service, or grants read or write authority.

A Goal Brief is never required: a messy one-line request produces a small,
valid contract.
"""

from __future__ import annotations

from core.explicit_evidence import extract_explicit_evidence
from core.requirement_preservation import check_requirement_preservation
from core.semantic_waiter import (
    ExplicitEvidenceInterpreter,
    SemanticInterpretation,
    SemanticInterpreter,
)
from core.task_contract import RawRequest, TaskContract


PHASE_ID = "INPUT.1"

#: The stages INPUT.1 owns, in order.  Execution-mode selection is deliberately
#: absent — it belongs to the future Execution Waiter (WAITER.1).
INPUT_UNDERSTANDING_STAGES: tuple[str, ...] = (
    "extract_explicit_evidence",
    "semantic_interpretation",
    "requirement_preservation_gate",
    "task_contract_assembly",
)


def understand_request(
    raw_text: str,
    *,
    interpreter: SemanticInterpreter | None = None,
) -> TaskContract:
    """Turn a raw user request into a lossless Task Contract.

    ``interpreter`` is the Semantic Waiter.  It defaults to the deterministic
    :class:`~core.semantic_waiter.ExplicitEvidenceInterpreter`; no model
    adapter is wired in this phase.

    Routing is fail-closed: ``routing_allowed`` is true only when the
    deterministic preservation gate confirms every explicit commitment
    survived.  Model confidence has no vote.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    evidence = extract_explicit_evidence(raw_text)

    waiter = interpreter if interpreter is not None else ExplicitEvidenceInterpreter()
    interpretation = waiter.interpret(raw_text, evidence)
    if not isinstance(interpretation, SemanticInterpretation):
        raise TypeError(
            "a Semantic Waiter must return a SemanticInterpretation, got "
            f"{type(interpretation).__name__}"
        )

    preservation = check_requirement_preservation(evidence, interpretation)

    return TaskContract(
        raw_request=RawRequest(text=raw_text),
        task=interpretation.task,
        subjects=interpretation.subjects,
        relationships=interpretation.relationships,
        user_supplied_framework=interpretation.framework,
        requested_output=interpretation.requested_output,
        constraints=interpretation.constraints,
        behavioral_expectations=interpretation.behavioral_expectations,
        design_evidence=interpretation.design_evidence,
        ambiguities=interpretation.ambiguities,
        missing_information=interpretation.missing_information,
        execution_requirements=interpretation.execution_requirements,
        explicit_evidence=evidence,
        preservation=preservation,
        notes=interpretation.notes,
        routing_allowed=preservation.passed,
    )
