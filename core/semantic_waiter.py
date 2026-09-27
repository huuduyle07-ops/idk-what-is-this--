"""INPUT.1 — Semantic Waiter boundary.

The Semantic Waiter is the seam between a raw order and its canonical meaning:

    (raw prompt, explicit evidence) -> SemanticInterpretation

It is responsible for understanding the meaning of the order and nothing else.
It never solves the task, inspects the repository, selects an execution mode,
chooses a provider or model, patches files, runs validation, starts benchmarks,
launches workers, starts Dream, starts Project Evolution, or authorizes writes.

INPUT.1 defines the interface and ships two deterministic implementations:

``ExplicitEvidenceInterpreter``
    The default.  It promotes literal evidence into an interpretation and
    infers nothing it cannot derive deterministically, so it can never drop a
    user commitment.

``StaticSemanticInterpreter``
    A test double that returns a supplied interpretation verbatim, used to
    simulate a lossy interpreter against the preservation gate.

No model adapter exists yet — that is INPUT.2.  This module is stdlib-only and
pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from core.behavioral_expectation import BehavioralExpectation
from core.explicit_evidence import ExplicitEvidence
from core.task_contract import (
    MAX_SUBJECTS,
    PROVENANCE_EXPLICIT,
    PROVENANCE_INFERRED,
    Constraint,
    ExecutionRequirements,
    Relationship,
    RequestedOutput,
    Subject,
    TaskClassification,
    UserSuppliedFramework,
)


PHASE_ID = "INPUT.1"

SEMANTIC_WAITER_RESPONSIBILITY = (
    "Understand the meaning of the order. The Semantic Waiter takes the order; "
    "it never cooks it."
)

#: Everything a Semantic Waiter implementation is forbidden to do, in any phase.
SEMANTIC_WAITER_FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "solve_the_task",
    "inspect_the_repository",
    "index_the_repository",
    "select_execution_mode",
    "select_provider_or_model",
    "patch_files",
    "run_validation",
    "start_benchmarks",
    "launch_" + "work" + "ers",
    "start_dream",
    "start_project_evolution",
    "authorize_writes",
)

#: Roles a subject can hold in an interpretation.
SUBJECT_ROLE_COMPARISON = "comparison_subject"
SUBJECT_ROLE_NAMED_ENTITY = "named_entity"


@dataclass(frozen=True, slots=True)
class SemanticInterpretation:
    """What a Semantic Waiter understood the order to mean."""

    task: TaskClassification
    subjects: tuple[Subject, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    framework: UserSuppliedFramework | None = None
    requested_output: RequestedOutput | None = None
    constraints: tuple[Constraint, ...] = ()
    #: DEFECT.FACT.LIVE.1 — the explicit behavioral claims INPUT.1 typed,
    #: carried through unchanged.  An interpreter may not author one, may not
    #: rewrite one, and may not drop one: the preservation gate checks all three.
    behavioral_expectations: tuple[BehavioralExpectation, ...] = ()
    ambiguities: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    execution_requirements: ExecutionRequirements = field(default_factory=ExecutionRequirements)
    notes: tuple[str, ...] = ()

    def subjects_by_value(self) -> dict[str, Subject]:
        return {subject.value: subject for subject in self.subjects}

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.as_dict(),
            "subjects": [item.as_dict() for item in self.subjects],
            "relationships": [item.as_dict() for item in self.relationships],
            "framework": self.framework.as_dict() if self.framework else None,
            "requested_output": (
                self.requested_output.as_dict() if self.requested_output else None
            ),
            "constraints": [item.as_dict() for item in self.constraints],
            "behavioral_expectations": [
                item.as_dict() for item in self.behavioral_expectations
            ],
            "ambiguities": list(self.ambiguities),
            "missing_information": list(self.missing_information),
            "execution_requirements": self.execution_requirements.as_dict(),
            "notes": list(self.notes),
        }


@runtime_checkable
class SemanticInterpreter(Protocol):
    """The Semantic Waiter interface.

    An implementation reads the order and reports what it means.  It receives
    no repository handle, no tool registry, and no execution authority, and it
    must return promptly with a pure value.
    """

    def interpret(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
    ) -> SemanticInterpretation:
        """Return the meaning of ``raw_prompt`` — never a solution to it."""
        ...


def _task_type(raw_prompt: str, evidence: ExplicitEvidence) -> str:
    if evidence.comparisons:
        return "comparative_analysis"
    if raw_prompt.rstrip().endswith("?"):
        return "question"
    if evidence.is_empty():
        return "conversation"
    return "unknown"


def _subjects(evidence: ExplicitEvidence) -> tuple[Subject, ...]:
    subjects: list[Subject] = []
    seen: list[str] = []

    def _add(value: str, role: str) -> None:
        key = value.casefold()
        if any(key == existing or key in existing for existing in seen):
            return
        seen.append(key)
        subjects.append(Subject(value=value, provenance=PROVENANCE_EXPLICIT, role=role))

    for value in evidence.comparison_subjects():
        _add(value, SUBJECT_ROLE_COMPARISON)
    for value in evidence.named_entities:
        _add(value, SUBJECT_ROLE_NAMED_ENTITY)

    return tuple(subjects[:MAX_SUBJECTS])


def _execution_requirements(evidence: ExplicitEvidence) -> ExecutionRequirements:
    touches_repository = bool(evidence.file_paths)
    return ExecutionRequirements(
        multi_stage=False,
        external_information_required=bool(evidence.urls),
        repository_inspection_required=touches_repository,
        local_repository_required=touches_repository,
        provenance=PROVENANCE_INFERRED,
    )


class ExplicitEvidenceInterpreter:
    """Deterministic Semantic Waiter: literal evidence in, interpretation out.

    This interpreter never guesses.  Everything the user typed is carried
    through and marked ``explicit``; the only inferred values are the task
    classification and the execution requirements, both derived by fixed rules
    rather than by a model.
    """

    def interpret(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
    ) -> SemanticInterpretation:
        framework = None
        if explicit_evidence.framework is not None:
            framework = UserSuppliedFramework(
                type=explicit_evidence.framework.type,
                values=explicit_evidence.framework.values,
                provenance=PROVENANCE_EXPLICIT,
                ordered=explicit_evidence.framework.ordered,
            )

        requested_output = None
        if explicit_evidence.requested_outputs:
            requested_output = RequestedOutput(
                format=explicit_evidence.requested_outputs[0].format,
                provenance=PROVENANCE_EXPLICIT,
            )

        return SemanticInterpretation(
            task=TaskClassification(
                type=_task_type(raw_prompt, explicit_evidence),
                provenance=PROVENANCE_INFERRED,
            ),
            subjects=_subjects(explicit_evidence),
            relationships=tuple(
                Relationship(
                    type="comparison",
                    subjects=comparison.subjects,
                    provenance=PROVENANCE_EXPLICIT,
                )
                for comparison in explicit_evidence.comparisons
            ),
            framework=framework,
            requested_output=requested_output,
            constraints=tuple(
                Constraint(
                    kind=item.kind,
                    text=item.text,
                    provenance=PROVENANCE_EXPLICIT,
                )
                for item in explicit_evidence.constraints
            ),
            # DEFECT.FACT.LIVE.1 — promoted verbatim.  These are already typed
            # and already user-sourced; there is nothing here left to interpret.
            behavioral_expectations=explicit_evidence.behavioral_expectations,
            execution_requirements=_execution_requirements(explicit_evidence),
        )


class StaticSemanticInterpreter:
    """Test double returning a fixed interpretation, recording what it saw.

    Used to prove the preservation gate catches a lossy interpreter without
    wiring any model.
    """

    def __init__(self, interpretation: SemanticInterpretation) -> None:
        self._interpretation = interpretation
        self._calls: list[tuple[str, ExplicitEvidence]] = []

    @property
    def calls(self) -> tuple[tuple[str, ExplicitEvidence], ...]:
        return tuple(self._calls)

    def interpret(
        self,
        raw_prompt: str,
        explicit_evidence: ExplicitEvidence,
    ) -> SemanticInterpretation:
        self._calls.append((raw_prompt, explicit_evidence))
        return self._interpretation
