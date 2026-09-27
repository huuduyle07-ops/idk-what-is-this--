"""INPUT.3 — progressive intake completion, assembled.

One pure call over the frozen INPUT.1 / INPUT.2 products:

    TaskContract (+ INPUT.2 semantic status)
        -> deterministic completion policy      [core.intake_completion]
        -> Goal Brief projection                [core.goal_brief_projection]
        -> optional presentation assistance     [core.intake_assistant]

The order matters and is the whole safety argument.  The decision and the
projection are finished *before* any assistant is consulted, are handed to the
assistant as read-only inputs, and are the same objects that come back out.  An
assistant can therefore change how the result reads and nothing about what it
says.

    Local AI may improve the words.  It may not change the decision.

INPUT.3 stops here.  It does not choose a workflow, a mode, a provider or a
model; it does not read the repository, plan, patch, validate, benchmark, or
execute; and no completion state grants any authority.  ``READY`` means intake
information appears complete.  Future handoff additionally requires a passed
preservation gate and valid INPUT.2 semantic receipt.

The module is stdlib-only and pure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.goal_brief_projection import GoalBriefProjection, project_goal_brief
from core.intake_assistant import (
    ASSISTANCE_STATUS_NOT_CONFIGURED,
    ASSISTANCE_STATUS_REJECTED,
    ASSISTANCE_STATUS_UNAVAILABLE,
    DETERMINISTIC_ASSISTANT_NAME,
    DeterministicIntakeAssistant,
    IntakeAssistance,
    IntakeAssistanceRejected,
    IntakeAssistant,
    enforce_assistance_boundary,
    state_headline,
)
from core.intake_completion import (
    PHASE_ID,
    STATE_SEMANTIC_SYSTEM_FAILURE,
    CompletionDecision,
    decide_from_semantic_outcome,
    decide_intake_completion,
    intake_authority,
)
from core.semantic_waiter_runner import SemanticWaiterOutcome, SemanticWaiterReceipt
from core.task_contract import TaskContract


INTAKE_COMPLETION_SCHEMA_VERSION = "input_3_intake_completion_v2"

#: The stages INPUT.3 owns, in order.  Workflow selection is deliberately
#: absent — it belongs to the future Execution Waiter (WAITER.1).
INTAKE_COMPLETION_STAGES: tuple[str, ...] = (
    "deterministic_completion_policy",
    "goal_brief_projection",
    "optional_intake_assistance",
)


@dataclass(frozen=True, slots=True)
class IntakeCompletionOutcome:
    """The finished intake verdict plus the words used to present it."""

    decision: CompletionDecision
    projection: GoalBriefProjection | None = None
    assistance: IntakeAssistance | None = None
    schema_version: str = INTAKE_COMPLETION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.projection is None and self.decision.state != STATE_SEMANTIC_SYSTEM_FAILURE:
            raise ValueError("only a system failure may lack a goal brief projection")

    @property
    def state(self) -> str:
        return self.decision.state

    @property
    def owner(self) -> str | None:
        return self.decision.owner

    @property
    def ready_for_future_handoff(self) -> bool:
        return self.decision.ready_for_future_handoff

    @property
    def goal_brief_offered(self) -> bool:
        return bool(self.projection and self.projection.goal_brief_offered)

    @property
    def assistance_status(self) -> str:
        return self.assistance.status if self.assistance else ASSISTANCE_STATUS_NOT_CONFIGURED

    @property
    def model_assisted(self) -> bool:
        return bool(self.assistance and self.assistance.generated_by_model)

    def questions(self) -> tuple[str, ...]:
        return self.assistance.question_texts() if self.assistance else ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "stages": list(INTAKE_COMPLETION_STAGES),
            "decision": self.decision.as_dict(),
            "goal_brief_projection": (
                self.projection.as_dict() if self.projection else None
            ),
            "assistance": self.assistance.as_dict() if self.assistance else None,
            "goal_brief_required": False,
            "authority": intake_authority(),
        }


def _system_failure_assistance(decision: CompletionDecision) -> IntakeAssistance:
    """Wording for a run that produced no contract to project."""
    return IntakeAssistance(
        assistant_name=DETERMINISTIC_ASSISTANT_NAME,
        summary=state_headline(decision.state),
        questions=(),
        field_suggestions=(),
        generated_by_model=False,
        status=ASSISTANCE_STATUS_NOT_CONFIGURED,
    )


def _assist(
    contract: TaskContract,
    decision: CompletionDecision,
    projection: GoalBriefProjection,
    assistant: IntakeAssistant | None,
) -> IntakeAssistance:
    """Run the optional assistant, falling back to deterministic wording.

    The fallback is not an error path so much as the normal one: a machine with
    no local model must still get usable questions.
    """
    baseline = DeterministicIntakeAssistant().assist(contract, decision, projection)
    if assistant is None:
        return baseline

    try:
        assistance = assistant.assist(contract, decision, projection)
    except Exception:
        return _tagged(baseline, ASSISTANCE_STATUS_UNAVAILABLE)

    try:
        return enforce_assistance_boundary(decision, projection, assistance)
    except IntakeAssistanceRejected:
        return _tagged(baseline, ASSISTANCE_STATUS_REJECTED)


def _tagged(assistance: IntakeAssistance, status: str) -> IntakeAssistance:
    return IntakeAssistance(
        assistant_name=assistance.assistant_name,
        summary=assistance.summary,
        questions=assistance.questions,
        field_suggestions=assistance.field_suggestions,
        generated_by_model=False,
        status=status,
    )


def complete_intake(
    contract: TaskContract,
    *,
    semantic_status: str | None = None,
    semantic_receipt: SemanticWaiterReceipt | None = None,
    assistant: IntakeAssistant | None = None,
) -> IntakeCompletionOutcome:
    """Decide intake completion for one contract and dress the result.

    ``assistant`` is optional in the strongest sense: omitting it, or handing in
    one whose model is unreachable, changes only wording.  The decision, the
    ownership, the ambiguity set, the required fields, the contradiction state
    and every canonical Goal Brief value are identical either way.  Omitting
    ``semantic_receipt`` keeps the direct path useful as a deterministic
    preview, but it cannot make the result future-handoff-ready.
    """
    decision = decide_intake_completion(
        contract,
        semantic_status=semantic_status,
        semantic_receipt=semantic_receipt,
    )
    projection = project_goal_brief(contract, decision)
    assistance = _assist(contract, decision, projection, assistant)
    return IntakeCompletionOutcome(
        decision=decision, projection=projection, assistance=assistance
    )


def complete_intake_from_semantic_outcome(
    outcome: SemanticWaiterOutcome,
    *,
    assistant: IntakeAssistant | None = None,
) -> IntakeCompletionOutcome:
    """Decide intake completion for a finished INPUT.2 run.

    When the semantic run produced no contract at all there is nothing to
    project and nothing to ask the user: the failure is the system's, and it is
    reported as the system's.
    """
    decision = decide_from_semantic_outcome(outcome)
    if outcome.contract is None:
        return IntakeCompletionOutcome(
            decision=decision,
            projection=None,
            assistance=_system_failure_assistance(decision),
        )
    projection = project_goal_brief(outcome.contract, decision)
    assistance = _assist(outcome.contract, decision, projection, assistant)
    return IntakeCompletionOutcome(
        decision=decision, projection=projection, assistance=assistance
    )


def canonical_intake_fingerprint(outcome: IntakeCompletionOutcome) -> dict[str, Any]:
    """Everything a local model is forbidden to change.

    Two runs over the same contract — one deterministic-only, one with a local
    assistant — must produce equal fingerprints.  Wording, friendly
    explanation, suggested phrasing and clarification prose are all outside it
    on purpose.
    """
    decision = outcome.decision
    return {
        "state": decision.state,
        "owner": decision.owner,
        "ready_for_future_handoff": decision.ready_for_future_handoff,
        "handoff_blockers": list(decision.handoff_blockers),
        "reasons": list(decision.reasons),
        "ambiguities": [item.as_dict() for item in decision.ambiguities],
        "missing_requirements": [item.as_dict() for item in decision.missing_requirements],
        "required_before_handoff": list(decision.required_before_handoff),
        "optional_improvements": list(decision.optional_improvements),
        "contradiction_reasons": list(decision.contradiction_reasons),
        "semantic_status": decision.semantic_status,
        "semantic_evidence_status": decision.semantic_evidence_status,
        "semantic_evidence_valid": decision.semantic_evidence_valid,
        "preservation_status": decision.preservation_status,
        "contract_present": decision.contract_present,
        "goal_brief_offered": outcome.goal_brief_offered,
        "goal_brief_canonical_values": (
            outcome.projection.canonical_values() if outcome.projection else None
        ),
        "authority": intake_authority(),
    }


def render_intake_completion_json(outcome: IntakeCompletionOutcome) -> str:
    """Render an intake completion outcome as deterministic JSON."""
    return json.dumps(outcome.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)
