"""INPUT.3 — deterministic Goal Brief projection.

A Goal Brief is a human-editable *projection* of the Task Contract, never a
form the user must fill in first:

    raw user request = source language
    Task Contract    = canonical intermediate representation
    Goal Brief       = human-editable projection of that representation

This module renders that projection from facts that already exist:

    TaskContract + CompletionDecision -> GoalBriefProjection

Nothing is invented.  Every value carries the provenance the contract gave it
and the source it came from, so a reader can always tell a user quotation from
an interpreter's conclusion.  Values an optional model suggests never enter
here — they live on :class:`~core.intake_assistant.IntakeAssistance` and stay
separate from canonical truth.

A field is only marked ``needed_before_handoff`` or ``suggested_for_completion``
because the deterministic policy said so.  When the policy says READY, every
absent field is ``not_collected`` and no question is raised at all.

The module is stdlib-only and pure: no file access, no service, no model, no
repository inspection, no authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.intake_completion import (
    BRIEF_FIELD_CONSTRAINTS,
    BRIEF_FIELD_DESIRED_OUTPUT,
    BRIEF_FIELD_SCOPE,
    BRIEF_FIELD_STOP_CONDITIONS,
    BRIEF_FIELD_VALIDATION,
    BRIEF_FIELD_WHAT,
    BRIEF_FIELD_WHY,
    GOAL_BRIEF_FIELDS,
    STATE_GOAL_BRIEF_ASSIST,
    CompletionDecision,
    intake_authority,
)
from core.task_contract import PROVENANCE_EXPLICIT, PROVENANCES, TaskContract


PHASE_ID = "INPUT.3"
GOAL_BRIEF_PROJECTION_SCHEMA_VERSION = "input_3_goal_brief_projection_v1"

# ── Field status ──────────────────────────────────────────────────────────────
#: The contract carries a value for this field.
FIELD_PRESENT = "present"
#: The deterministic policy needs this before a future handoff.
FIELD_NEEDED_BEFORE_HANDOFF = "needed_before_handoff"
#: Useful, offered while assisting, never blocking.
FIELD_SUGGESTED_FOR_COMPLETION = "suggested_for_completion"
#: Absent and not being asked for.  Simple tasks stay here.
FIELD_NOT_COLLECTED = "not_collected"

FIELD_STATUSES: tuple[str, ...] = (
    FIELD_PRESENT,
    FIELD_NEEDED_BEFORE_HANDOFF,
    FIELD_SUGGESTED_FOR_COMPLETION,
    FIELD_NOT_COLLECTED,
)

# ── Value sources ─────────────────────────────────────────────────────────────
SOURCE_RAW_REQUEST = "raw_request"
SOURCE_EXPLICIT_EVIDENCE = "explicit_evidence"
SOURCE_TASK_CONTRACT = "task_contract"

VALUE_SOURCES: tuple[str, ...] = (
    SOURCE_RAW_REQUEST,
    SOURCE_EXPLICIT_EVIDENCE,
    SOURCE_TASK_CONTRACT,
)

MAX_FIELD_VALUES = 16


@dataclass(frozen=True, slots=True)
class GoalBriefValue:
    """One canonical value, with where it came from and how it was obtained."""

    text: str
    provenance: str
    source: str
    label: str | None = None

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("a goal brief value needs text")
        if self.provenance not in PROVENANCES:
            raise ValueError(f"unsupported provenance: {self.provenance!r}")
        if self.source not in VALUE_SOURCES:
            raise ValueError(f"unsupported value source: {self.source!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provenance": self.provenance,
            "source": self.source,
            "label": self.label,
        }


@dataclass(frozen=True, slots=True)
class GoalBriefField:
    """One projected Goal Brief field."""

    field: str
    status: str
    entries: tuple[GoalBriefValue, ...] = ()

    def __post_init__(self) -> None:
        if self.field not in GOAL_BRIEF_FIELDS:
            raise ValueError(f"unsupported goal brief field: {self.field!r}")
        if self.status not in FIELD_STATUSES:
            raise ValueError(f"unsupported field status: {self.status!r}")
        if len(self.entries) > MAX_FIELD_VALUES:
            raise ValueError("goal brief field values exceed the supported bound")
        if self.entries and self.status != FIELD_PRESENT:
            raise ValueError(
                f"field {self.field!r} carries values but is marked {self.status!r}"
            )
        if not self.entries and self.status == FIELD_PRESENT:
            raise ValueError(f"field {self.field!r} is marked present but carries no value")

    @property
    def value(self) -> str | None:
        """The single value, for fields that hold at most one."""
        return self.entries[0].text if self.entries else None

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(entry.text for entry in self.entries)

    def as_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "status": self.status,
            "value": self.value,
            "entries": [entry.as_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class GoalBriefProjection:
    """A Goal Brief-shaped view of one Task Contract.

    ``goal_brief_offered`` records that assistance is being *offered*, not
    required.  Nothing downstream may treat a Goal Brief as mandatory.
    """

    fields: tuple[GoalBriefField, ...]
    task_type: str
    subjects: tuple[str, ...] = ()
    reported_gaps: tuple[str, ...] = ()
    goal_brief_offered: bool = False
    schema_version: str = GOAL_BRIEF_PROJECTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        names = tuple(item.field for item in self.fields)
        if names != GOAL_BRIEF_FIELDS:
            raise ValueError("a projection must carry every goal brief field, in order")

    def field(self, name: str) -> GoalBriefField:
        for item in self.fields:
            if item.field == name:
                return item
        raise KeyError(name)

    def status(self, name: str) -> str:
        return self.field(name).status

    def needed_before_handoff(self) -> tuple[str, ...]:
        return tuple(
            item.field for item in self.fields if item.status == FIELD_NEEDED_BEFORE_HANDOFF
        )

    def canonical_values(self) -> dict[str, Any]:
        """The authoritative half of the projection.

        This is what may never differ between a zero-model run and a
        model-assisted one.
        """
        return {
            "task_type": self.task_type,
            "subjects": list(self.subjects),
            "fields": {item.field: item.as_dict() for item in self.fields},
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_type": self.task_type,
            "subjects": list(self.subjects),
            "fields": [item.as_dict() for item in self.fields],
            "reported_gaps": list(self.reported_gaps),
            "goal_brief_offered": self.goal_brief_offered,
            "goal_brief_required": False,
            "authority": intake_authority(),
        }


# ── Field derivation ──────────────────────────────────────────────────────────

def _what(contract: TaskContract) -> tuple[GoalBriefValue, ...]:
    """The request itself, verbatim.

    A short paraphrase would be more readable and would also be invented text.
    The canonical value stays the user's own words; a friendlier summary is the
    optional assistant's job and stays labelled as assistance.
    """
    text = contract.raw_request.text.strip()
    if not text:
        return ()
    return (
        GoalBriefValue(
            text=text,
            provenance=PROVENANCE_EXPLICIT,
            source=SOURCE_RAW_REQUEST,
            label=contract.task.type,
        ),
    )


def _scope(contract: TaskContract) -> tuple[GoalBriefValue, ...]:
    entries: list[GoalBriefValue] = []
    for path in contract.explicit_evidence.file_paths:
        entries.append(
            GoalBriefValue(
                text=path,
                provenance=PROVENANCE_EXPLICIT,
                source=SOURCE_EXPLICIT_EVIDENCE,
                label="file_path",
            )
        )
    for constraint in contract.explicit_evidence.constraints:
        if constraint.kind != "restriction":
            continue
        entries.append(
            GoalBriefValue(
                text=constraint.text,
                provenance=PROVENANCE_EXPLICIT,
                source=SOURCE_EXPLICIT_EVIDENCE,
                label=constraint.kind,
            )
        )
    return tuple(entries[:MAX_FIELD_VALUES])


def _constraints(contract: TaskContract) -> tuple[GoalBriefValue, ...]:
    return tuple(
        GoalBriefValue(
            text=constraint.text,
            provenance=constraint.provenance,
            source=SOURCE_TASK_CONTRACT,
            label=constraint.kind,
        )
        for constraint in contract.constraints[:MAX_FIELD_VALUES]
    )


def _desired_output(contract: TaskContract) -> tuple[GoalBriefValue, ...]:
    requested = contract.requested_output
    if requested is None:
        return ()
    return (
        GoalBriefValue(
            text=requested.format,
            provenance=requested.provenance,
            source=SOURCE_TASK_CONTRACT,
            label="requested_output",
        ),
    )


#: Fields the contract cannot supply.  They are never invented, only offered.
_UNSOURCED_FIELDS: frozenset[str] = frozenset(
    {BRIEF_FIELD_WHY, BRIEF_FIELD_STOP_CONDITIONS, BRIEF_FIELD_VALIDATION}
)

_DERIVERS = {
    BRIEF_FIELD_WHAT: _what,
    BRIEF_FIELD_SCOPE: _scope,
    BRIEF_FIELD_CONSTRAINTS: _constraints,
    BRIEF_FIELD_DESIRED_OUTPUT: _desired_output,
}


def project_goal_brief(
    contract: TaskContract,
    decision: CompletionDecision,
) -> GoalBriefProjection:
    """Project a Task Contract into a Goal Brief-shaped, editable view.

    The projection invents nothing: a field is ``present`` only when the
    contract already carries the value, and is asked for only when the
    deterministic policy asked for it.
    """
    if not isinstance(contract, TaskContract):
        raise TypeError("project_goal_brief requires a TaskContract")
    if not isinstance(decision, CompletionDecision):
        raise TypeError("project_goal_brief requires a CompletionDecision")

    required = set(decision.required_before_handoff)
    suggested = set(decision.optional_improvements)

    fields: list[GoalBriefField] = []
    for name in GOAL_BRIEF_FIELDS:
        entries = () if name in _UNSOURCED_FIELDS else _DERIVERS[name](contract)
        if entries:
            status = FIELD_PRESENT
        elif name in required:
            status = FIELD_NEEDED_BEFORE_HANDOFF
        elif name in suggested:
            status = FIELD_SUGGESTED_FOR_COMPLETION
        else:
            status = FIELD_NOT_COLLECTED
        fields.append(GoalBriefField(field=name, status=status, entries=entries))

    reported = tuple(
        item.reason for item in decision.missing_requirements if item.field not in GOAL_BRIEF_FIELDS
    )

    return GoalBriefProjection(
        fields=tuple(fields),
        task_type=contract.task.type,
        subjects=contract.subject_values(),
        reported_gaps=reported,
        goal_brief_offered=decision.state == STATE_GOAL_BRIEF_ASSIST,
    )


def render_goal_brief_projection_json(projection: GoalBriefProjection) -> str:
    """Render a projection as deterministic JSON."""
    return json.dumps(projection.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)
