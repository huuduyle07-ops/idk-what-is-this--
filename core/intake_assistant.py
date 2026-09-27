"""INPUT.3 — the Intake Assistant boundary.

An Intake Assistant turns a finished :class:`~core.intake_completion.CompletionDecision`
into words a person can read:

    contract + decision + projection -> IntakeAssistance

It writes clarification questions, phrases Goal Brief assistance, summarizes
what was understood, and may suggest candidate wording for a field the contract
does not carry.  That is the whole job.

An assistant may not:

- change the completion state or its owner
- mark anything ready, resolved, or complete
- resolve an ambiguity by guessing
- turn a suggestion into an explicit user fact
- modify the canonical Task Contract or the projection's canonical values
- select a mode, a provider, or a model
- execute anything

Those limits are structural, not advisory.  :class:`IntakeAssistance` has no
state, owner, readiness, or resolution field to write, so an assistant that
wants to promote ASK_CLARIFICATION to READY has nowhere to put the claim.
:func:`enforce_assistance_boundary` rejects the remaining ways to overreach —
inventing a question anchor, contradicting a need's severity, or writing over a
value the contract already supplies.

:class:`DeterministicIntakeAssistant` is always available and needs no model.
It is the baseline every model-backed assistant falls back to.

The module is stdlib-only and pure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from core.goal_brief_projection import FIELD_PRESENT, GoalBriefProjection
from core.intake_completion import (
    BRIEF_FIELD_CONSTRAINTS,
    BRIEF_FIELD_DESIRED_OUTPUT,
    BRIEF_FIELD_SCOPE,
    BRIEF_FIELD_STOP_CONDITIONS,
    BRIEF_FIELD_UNSPECIFIED,
    BRIEF_FIELD_VALIDATION,
    BRIEF_FIELD_WHAT,
    BRIEF_FIELD_WHY,
    GOAL_BRIEF_FIELDS,
    MAX_CLARIFICATION_NEEDS,
    MAX_MISSING_REQUIREMENTS,
    NEED_CONFLICTING_OUTPUT_FORMATS,
    NEED_DANGLING_SUBJECT_REFERENCE,
    NEED_REPORTED_AMBIGUITY,
    STATE_ASK_CLARIFICATION,
    STATE_BLOCKED_CONTRADICTION,
    STATE_GOAL_BRIEF_ASSIST,
    STATE_READY,
    STATE_SEMANTIC_SYSTEM_FAILURE,
    CompletionDecision,
    intake_authority,
)
from core.task_contract import TaskContract


PHASE_ID = "INPUT.3"
INTAKE_ASSISTANCE_SCHEMA_VERSION = "input_3_intake_assistance_v1"

DETERMINISTIC_ASSISTANT_NAME = "deterministic_intake_assistant"

# ── Assistance provenance ─────────────────────────────────────────────────────
#: Written by the deterministic assistant from policy facts.
ASSISTANCE_DETERMINISTIC = "deterministic"
#: Written by an optional model.  Never a user fact, never canonical.
ASSISTANCE_GENERATED = "generated_assistance"

ASSISTANCE_PROVENANCES: tuple[str, ...] = (ASSISTANCE_DETERMINISTIC, ASSISTANCE_GENERATED)

# ── Assistance status ─────────────────────────────────────────────────────────
#: Bounded, non-authoritative telemetry: which presentation path produced the
#: wording.  None of these values can change a completion decision.
ASSISTANCE_STATUS_NOT_CONFIGURED = "intake_assistant_not_configured"
ASSISTANCE_STATUS_OK = "intake_assistant_ok"
ASSISTANCE_STATUS_UNAVAILABLE = "intake_assistant_unavailable"
ASSISTANCE_STATUS_INVALID = "intake_assistance_invalid"
ASSISTANCE_STATUS_REJECTED = "intake_assistance_rejected"

ASSISTANCE_STATUSES: tuple[str, ...] = (
    ASSISTANCE_STATUS_NOT_CONFIGURED,
    ASSISTANCE_STATUS_OK,
    ASSISTANCE_STATUS_UNAVAILABLE,
    ASSISTANCE_STATUS_INVALID,
    ASSISTANCE_STATUS_REJECTED,
)

# ── Bounds ────────────────────────────────────────────────────────────────────
MAX_ASSISTANCE_QUESTIONS = MAX_CLARIFICATION_NEEDS + MAX_MISSING_REQUIREMENTS
MAX_QUESTION_CHARS = 240
MAX_SUMMARY_CHARS = 400
MAX_FIELD_SUGGESTIONS = 8
MAX_SUGGESTION_CHARS = 240


class IntakeAssistanceRejected(Exception):
    """Assistance overstepped the boundary and was refused.

    The caller falls back to deterministic assistance; the decision itself is
    never affected either way.
    """


@dataclass(frozen=True, slots=True)
class AssistanceQuestion:
    """One question, anchored to a need the deterministic policy raised."""

    need_id: str
    text: str
    provenance: str = ASSISTANCE_DETERMINISTIC
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.need_id.strip():
            raise ValueError("a question must be anchored to a need id")
        if not self.text.strip():
            raise ValueError("a question needs text")
        if len(self.text) > MAX_QUESTION_CHARS:
            raise ValueError("question text exceeds the supported bound")
        if self.provenance not in ASSISTANCE_PROVENANCES:
            raise ValueError(f"unsupported assistance provenance: {self.provenance!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "need_id": self.need_id,
            "text": self.text,
            "provenance": self.provenance,
            "optional": self.optional,
        }


@dataclass(frozen=True, slots=True)
class FieldSuggestion:
    """Candidate wording for a field the contract does not carry.

    A suggestion is never a user fact.  Its provenance may only be
    ``deterministic`` or ``generated_assistance``; ``explicit`` is rejected at
    construction, because only INPUT.1 evidence can make something explicit.
    """

    field: str
    suggested_value: str
    provenance: str = ASSISTANCE_GENERATED

    def __post_init__(self) -> None:
        if self.field not in GOAL_BRIEF_FIELDS:
            raise ValueError(f"unsupported goal brief field: {self.field!r}")
        if not self.suggested_value.strip():
            raise ValueError("a suggestion needs a value")
        if len(self.suggested_value) > MAX_SUGGESTION_CHARS:
            raise ValueError("suggested value exceeds the supported bound")
        if self.provenance not in ASSISTANCE_PROVENANCES:
            raise ValueError(
                f"a suggestion may not claim provenance {self.provenance!r}; only "
                f"{' or '.join(ASSISTANCE_PROVENANCES)} is permitted"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "suggested_value": self.suggested_value,
            "provenance": self.provenance,
            "canonical": False,
        }


@dataclass(frozen=True, slots=True)
class IntakeAssistance:
    """Presentation for one completion decision.

    Deliberately carries no state, owner, readiness or resolution field: there
    is nowhere here to record a decision, so none can be made.
    """

    assistant_name: str
    summary: str = ""
    questions: tuple[AssistanceQuestion, ...] = ()
    field_suggestions: tuple[FieldSuggestion, ...] = ()
    generated_by_model: bool = False
    status: str = ASSISTANCE_STATUS_NOT_CONFIGURED
    schema_version: str = INTAKE_ASSISTANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.assistant_name.strip():
            raise ValueError("assistance must name its assistant")
        if self.status not in ASSISTANCE_STATUSES:
            raise ValueError(f"unsupported assistance status: {self.status!r}")
        if self.generated_by_model and self.status != ASSISTANCE_STATUS_OK:
            raise ValueError(
                "assistance may only claim a model wrote it when the model succeeded"
            )
        if len(self.summary) > MAX_SUMMARY_CHARS:
            raise ValueError("assistance summary exceeds the supported bound")
        if len(self.questions) > MAX_ASSISTANCE_QUESTIONS:
            raise ValueError("assistance questions exceed the supported bound")
        if len(self.field_suggestions) > MAX_FIELD_SUGGESTIONS:
            raise ValueError("field suggestions exceed the supported bound")
        if self.field_suggestions and not self.generated_by_model:
            for suggestion in self.field_suggestions:
                if suggestion.provenance == ASSISTANCE_GENERATED:
                    raise ValueError(
                        "generated suggestions require assistance a model actually wrote"
                    )

    def question_texts(self) -> tuple[str, ...]:
        return tuple(item.text for item in self.questions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "assistant_name": self.assistant_name,
            "generated_by_model": self.generated_by_model,
            "status": self.status,
            "summary": self.summary,
            "questions": [item.as_dict() for item in self.questions],
            "field_suggestions": [item.as_dict() for item in self.field_suggestions],
            "authority": intake_authority(),
        }


@runtime_checkable
class IntakeAssistant(Protocol):
    """The optional presentation layer over a finished completion decision."""

    @property
    def name(self) -> str:
        """A stable name for telemetry."""
        ...

    def assist(
        self,
        contract: TaskContract,
        decision: CompletionDecision,
        projection: GoalBriefProjection,
    ) -> IntakeAssistance:
        """Return wording for ``decision`` — never a different decision."""
        ...


# ── Boundary enforcement ──────────────────────────────────────────────────────

def _severity_by_need(decision: CompletionDecision) -> dict[str, bool]:
    """need_id -> whether the need is optional."""
    optional: dict[str, bool] = {}
    for need in decision.ambiguities:
        optional[need.need_id] = False
    for item in decision.missing_requirements:
        optional[item.need_id] = not item.required
    return optional


def enforce_assistance_boundary(
    decision: CompletionDecision,
    projection: GoalBriefProjection,
    assistance: IntakeAssistance,
) -> IntakeAssistance:
    """Return ``assistance`` unchanged, or refuse it.

    Refusal is total rather than partial: assistance that invented an anchor,
    contradicted a need's severity, or tried to overwrite a canonical value has
    misunderstood its role, and silently keeping the rest of it would make the
    boundary hard to reason about.  The caller falls back to deterministic
    assistance and records that it did.
    """
    if not isinstance(assistance, IntakeAssistance):
        raise IntakeAssistanceRejected(
            f"an assistant must return IntakeAssistance, got {type(assistance).__name__}"
        )

    optional_by_need = _severity_by_need(decision)
    seen: set[str] = set()
    for question in assistance.questions:
        if question.need_id not in optional_by_need:
            raise IntakeAssistanceRejected(
                f"question is anchored to unknown need {question.need_id!r}"
            )
        if question.need_id in seen:
            raise IntakeAssistanceRejected(
                f"need {question.need_id!r} was asked about more than once"
            )
        seen.add(question.need_id)
        if question.optional != optional_by_need[question.need_id]:
            raise IntakeAssistanceRejected(
                f"question for {question.need_id!r} disagrees with the policy severity"
            )

    fields: set[str] = set()
    for suggestion in assistance.field_suggestions:
        if suggestion.field in fields:
            raise IntakeAssistanceRejected(
                f"field {suggestion.field!r} was suggested more than once"
            )
        fields.add(suggestion.field)
        if projection.status(suggestion.field) == FIELD_PRESENT:
            raise IntakeAssistanceRejected(
                f"field {suggestion.field!r} already carries a canonical value and may "
                "not be overwritten by a suggestion"
            )

    return assistance


# ── Deterministic assistant ───────────────────────────────────────────────────

_STATE_HEADLINES: dict[str, str] = {
    STATE_READY: "The request is understood and complete enough to hand off.",
    STATE_GOAL_BRIEF_ASSIST: (
        "The request is understood; some operational detail would make it safer to plan."
    ),
    STATE_ASK_CLARIFICATION: "The request cannot be resolved safely as written.",
    STATE_BLOCKED_CONTRADICTION: "The request states two commitments that cannot both hold.",
    STATE_SEMANTIC_SYSTEM_FAILURE: (
        "I could not reliably interpret this request because the semantic interpreter "
        "failed. This is not a problem with how you wrote it."
    ),
}

_READY_PREVIEW_HEADLINE = (
    "The request appears complete for intake preview, but is not eligible for future handoff yet."
)

_FIELD_QUESTIONS: dict[str, str] = {
    BRIEF_FIELD_WHY: "State why this change is needed.",
    BRIEF_FIELD_SCOPE: "Name the files, modules or areas this work may touch.",
    BRIEF_FIELD_CONSTRAINTS: "State anything the work must not change.",
    BRIEF_FIELD_STOP_CONDITIONS: "State the boundary at which the work should stop.",
    BRIEF_FIELD_VALIDATION: "State how the result should be checked.",
    BRIEF_FIELD_DESIRED_OUTPUT: "State the shape the answer should take.",
    BRIEF_FIELD_WHAT: "State what should change.",
}


def state_headline(state: str) -> str:
    """The canonical plain-language line for a completion state.

    A system failure says so in the first person and never asks the user to
    restate a request that was perfectly clear.
    """
    return _STATE_HEADLINES[state]


def _need_question(kind: str, detail: str, subject: str | None) -> str:
    if kind == NEED_DANGLING_SUBJECT_REFERENCE:
        text = f"Name the subject referred to as {subject!r}."
    elif kind == NEED_CONFLICTING_OUTPUT_FORMATS:
        text = "State which single output format the answer must use."
    elif kind == NEED_REPORTED_AMBIGUITY:
        text = f"Clarify: {detail}"
    else:  # pragma: no cover - the vocabulary is closed
        text = f"Clarify: {detail}"
    return text[:MAX_QUESTION_CHARS]


def _deterministic_summary(contract: TaskContract, decision: CompletionDecision) -> str:
    headline = _STATE_HEADLINES[decision.state]
    if decision.state == STATE_SEMANTIC_SYSTEM_FAILURE:
        return headline[:MAX_SUMMARY_CHARS]
    if decision.state == STATE_READY and not decision.ready_for_future_handoff:
        headline = _READY_PREVIEW_HEADLINE

    subjects = contract.subject_values()
    if subjects:
        understood = f"Understood: {contract.task.type} — {', '.join(subjects)}."
    else:
        understood = f"Understood: {contract.task.type} — no named subject."

    if decision.state == STATE_BLOCKED_CONTRADICTION and decision.contradiction_reasons:
        # A blocked contradiction raises no question, so the conflict itself has
        # to be in the words or the user is told "no" without being told why.
        return f"{understood} {headline} {decision.contradiction_reasons[0]}"[
            :MAX_SUMMARY_CHARS
        ]
    return f"{understood} {headline}"[:MAX_SUMMARY_CHARS]


def build_deterministic_questions(
    decision: CompletionDecision,
) -> tuple[AssistanceQuestion, ...]:
    """One canonical question per unresolved need, in policy order."""
    questions: list[AssistanceQuestion] = []

    for need in decision.ambiguities:
        questions.append(
            AssistanceQuestion(
                need_id=need.need_id,
                text=_need_question(need.kind, need.detail, need.subject),
                provenance=ASSISTANCE_DETERMINISTIC,
                optional=False,
            )
        )

    for item in decision.missing_requirements:
        if item.field == BRIEF_FIELD_UNSPECIFIED:
            text = f"Supply the missing detail: {item.reason}"
        else:
            text = _FIELD_QUESTIONS[item.field]
        questions.append(
            AssistanceQuestion(
                need_id=item.need_id,
                text=text[:MAX_QUESTION_CHARS],
                provenance=ASSISTANCE_DETERMINISTIC,
                optional=not item.required,
            )
        )

    return tuple(questions[:MAX_ASSISTANCE_QUESTIONS])


class DeterministicIntakeAssistant:
    """The always-available assistant.  No model, no network, no guessing.

    Its wording is plain rather than warm, and that is the point: it is the
    floor INPUT.3 guarantees when no local model is installed, and the baseline
    a model-backed assistant is compared against.
    """

    name = DETERMINISTIC_ASSISTANT_NAME

    def assist(
        self,
        contract: TaskContract,
        decision: CompletionDecision,
        projection: GoalBriefProjection,
    ) -> IntakeAssistance:
        del projection  # canonical values are never restated as assistance
        return IntakeAssistance(
            assistant_name=self.name,
            summary=_deterministic_summary(contract, decision),
            questions=build_deterministic_questions(decision),
            field_suggestions=(),
            generated_by_model=False,
            status=ASSISTANCE_STATUS_NOT_CONFIGURED,
        )


def render_intake_assistance_json(assistance: IntakeAssistance) -> str:
    """Render assistance as deterministic JSON."""
    return json.dumps(assistance.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)
