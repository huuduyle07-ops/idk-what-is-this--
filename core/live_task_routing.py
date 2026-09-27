"""WAITER.LIVE.1 — the live routing boundary, in front of CONTROL.

WAITER.1 already knew how to route.  It was never wired anywhere, and the
reason is recorded here rather than worked around silently:

    ``core.execution_waiter.route_execution_workflow`` consumes an INPUT.3
    ``CompletionDecision``, and ``core.waiter_receipt.check_handoff_eligibility``
    refuses one whose INPUT.2 semantic receipt does not attest to at least one
    model call.  INPUT.2's model-backed Semantic Waiter is not live, so the
    frozen entry point cannot be reached from production without adding the very
    model call this phase forbids.

That is the whole mismatch, and the adapter around it is deliberately small.
Everything else WAITER.1 owns is reused unchanged: the Task Shape derivation,
the Capability Requirement derivation, the deterministic workflow rule table in
:func:`~core.execution_waiter.select_workflow`, and the authority and guardrail
blocks in :mod:`core.waiter_receipt`.  Only the handoff gate — the one part that
demands evidence live production cannot produce — is replaced, by INPUT.1's own
fail-closed preservation verdict.

    resolved user task
        -> LiveTaskShape                       [core.live_task_shape]
        -> live workflow policy                [here]
        -> LiveRouteReceipt                    [here]
        -> production entry points             [web/runner, cli, main, web/app]

The boundary sits *before* repository indexing, preflight validation and
CONTROL patch-localization, because that ordering is the fix.  An architecture
comparison that never reaches CONTROL cannot be told that it is missing a
replacement snippet.

What a route decides, and what it emphatically does not:

**It decides which workflow runs.**  Analysis answers, defect repair localizes,
an explicit change plans against acquired source, an unreadable order asks.

**It decides nothing about authority.**  ``write_authority`` and
``patch_application_authority`` are false on every route, in every shape,
including ``explicit_change``.  A route cannot raise them and no downstream
component may widen them: they are supplied, if ever, by patch safety,
CTX.PATCH/CTX.APPLY, ``AUTO_PATCH_ENABLED`` and human approval, none of which
this module can reach.

**It establishes no defect.**  ``change_need_source=explicit_user_request`` says
the user asked for a change.  It is not defect evidence, it is not a failing
test, and it does not make ``defect_established`` true anywhere.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, indexes nothing, and grants no
authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.behavioral_expectation import BehavioralExpectation
from core.execution_waiter import (
    WORKFLOW_TARGETS,
    select_workflow,
)
from core.live_task_shape import (
    CHANGE_NEED_EXPLICIT_USER_REQUEST,
    CHANGE_NEED_GROUNDED_DEFECT,
    CHANGE_NEED_NONE,
    CHANGE_NEED_SOURCES,
    CHANGE_NEED_UNRESOLVED,
    LIVE_TASK_SHAPES,
    SHAPE_ANALYSIS_ONLY,
    SHAPE_DEFECT_REPAIR,
    SHAPE_EXPLICIT_CHANGE,
    SHAPE_NEEDS_CLARIFICATION,
    LiveTaskShape,
    derive_live_task_shape,
)
from core.waiter_receipt import waiter_authority, waiter_guardrails


PHASE_ID = "WAITER.LIVE.1"
LIVE_ROUTE_SCHEMA_VERSION = "waiter_live_1_route_receipt_v1"

#: The one field name production reads this route off, everywhere.
ROUTE_STATE_KEY = "live_route"

# ── Live workflows ────────────────────────────────────────────────────────────
#: The workflows the live runtime actually has, named for what they produce.

#: Repository evidence in, a user-readable answer out.  No patch localization,
#: no replacement snippet, no write.
WORKFLOW_ANALYSIS_ANSWER = "analysis_answer"
#: The proven defect road: preflight, OPS.VALIDATE.1 facts, CONTROL
#: localization, defect grounding, exact source, patch safety, apply, validate.
WORKFLOW_DEFECT_REPAIR = "defect_repair_patch"
#: Change-oriented planning against acquired source.  The user's request is why;
#: exact source, patch safety and authorization remain how.
WORKFLOW_EXPLICIT_CHANGE = "explicit_change_patch"
#: Read-only, and it asks.  Never a write workflow.
WORKFLOW_CLARIFICATION = "clarification"

LIVE_WORKFLOWS: tuple[str, ...] = (
    WORKFLOW_ANALYSIS_ANSWER,
    WORKFLOW_DEFECT_REPAIR,
    WORKFLOW_EXPLICIT_CHANGE,
    WORKFLOW_CLARIFICATION,
)

#: ``live task shape -> live workflow``.  Total, and the only mapping there is.
_SHAPE_WORKFLOWS: dict[str, str] = {
    SHAPE_ANALYSIS_ONLY: WORKFLOW_ANALYSIS_ANSWER,
    SHAPE_DEFECT_REPAIR: WORKFLOW_DEFECT_REPAIR,
    SHAPE_EXPLICIT_CHANGE: WORKFLOW_EXPLICIT_CHANGE,
    SHAPE_NEEDS_CLARIFICATION: WORKFLOW_CLARIFICATION,
}

#: Workflows allowed to enter CONTROL's patch-localization machinery at all.
_PATCH_LOCALIZATION_WORKFLOWS: frozenset[str] = frozenset(
    {WORKFLOW_DEFECT_REPAIR, WORKFLOW_EXPLICIT_CHANGE}
)

# ── Source-grounding vocabulary ───────────────────────────────────────────────
#: How a workflow must be grounded in real source before it may propose an edit.

#: Nothing is being edited; evidence is read to answer a question.
GROUNDING_NONE = "none"
#: CONTROL must supply an exact replacement snippet for the localized target.
GROUNDING_CONTROL_EXACT_SOURCE = "control_exact_source_snippet"
#: Every operation must quote acquired source verbatim; the change scope may
#: span more than one file, and every quote is still checked against the file.
GROUNDING_ACQUIRED_SOURCE_QUOTE = "acquired_source_verbatim_quote"

SOURCE_GROUNDING_MODES: tuple[str, ...] = (
    GROUNDING_NONE,
    GROUNDING_CONTROL_EXACT_SOURCE,
    GROUNDING_ACQUIRED_SOURCE_QUOTE,
)


@dataclass(frozen=True, slots=True)
class LiveRouteReceipt:
    """One deterministic routing decision, and everything needed to debug it.

    Bounded on purpose.  There is no confidence, no score and no hidden
    reasoning: a route is a rule, and every rule has a shape it fired on.
    """

    task_shape: str
    change_requested: bool
    defect_claim_present: bool
    change_need_source: str
    selected_workflow: str
    patch_localization_allowed: bool
    preflight_validation_required: bool
    repository_indexing_allowed: bool
    source_grounding: str
    repository_available: bool = False
    reasons: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    #: WAITER.1's own recommendation over the same shape, recorded so the live
    #: route and the frozen rule table can be compared rather than assumed to
    #: agree.  It selects nothing here.
    waiter_workflow: str | None = None
    shape: LiveTaskShape | None = None
    schema_version: str = LIVE_ROUTE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.task_shape not in LIVE_TASK_SHAPES:
            raise ValueError(f"unsupported live task shape: {self.task_shape!r}")
        if self.selected_workflow not in LIVE_WORKFLOWS:
            raise ValueError(f"unsupported live workflow: {self.selected_workflow!r}")
        if self.change_need_source not in CHANGE_NEED_SOURCES:
            raise ValueError(
                f"unsupported change-need source: {self.change_need_source!r}"
            )
        if self.source_grounding not in SOURCE_GROUNDING_MODES:
            raise ValueError(f"unsupported source grounding: {self.source_grounding!r}")
        if self.waiter_workflow is not None and self.waiter_workflow not in WORKFLOW_TARGETS:
            raise ValueError(f"unsupported waiter workflow: {self.waiter_workflow!r}")
        if _SHAPE_WORKFLOWS[self.task_shape] != self.selected_workflow:
            raise ValueError(
                "the selected workflow must be the one this task shape maps to"
            )
        if self.patch_localization_allowed and (
            self.selected_workflow not in _PATCH_LOCALIZATION_WORKFLOWS
        ):
            raise ValueError(
                "patch localization is reachable only from the defect-repair and "
                f"explicit-change workflows, not {self.selected_workflow!r}"
            )
        if not self.change_requested and self.patch_localization_allowed:
            raise ValueError(
                "an order that requested no change may never enter patch localization"
            )
        if self.change_need_source == CHANGE_NEED_GROUNDED_DEFECT:
            raise ValueError(
                "routing never establishes a grounded defect; only executed failure "
                "evidence bound to exact source may do that"
            )
        if not self.change_requested and self.source_grounding != GROUNDING_NONE:
            raise ValueError("an order that requested no change grounds no source")

    # ── authority: false on every route, in every shape ─────────────────────
    @property
    def write_authority(self) -> bool:
        """Always false.  Task shape never grants write authority."""
        return False

    @property
    def patch_application_authority(self) -> bool:
        """Always false.  Applying remains CTX.APPLY's and human approval's."""
        return False

    @property
    def defect_established(self) -> bool:
        """Always false.  A route reports a claim, never a verified defect."""
        return False

    @property
    def human_approval_required(self) -> bool:
        return True

    # ── derived, authority-free facts ───────────────────────────────────────
    @property
    def analysis_only(self) -> bool:
        return self.selected_workflow == WORKFLOW_ANALYSIS_ANSWER

    @property
    def clarification(self) -> bool:
        return self.selected_workflow == WORKFLOW_CLARIFICATION

    @property
    def read_only(self) -> bool:
        """Does this route produce an answer rather than an operation?"""
        return not self.change_requested

    @property
    def control_source_snippet_required(self) -> bool:
        """Must CONTROL hand over an exact replacement snippet before patching?

        True only for defect repair.  This is the flag whose unconditional
        truth produced *cannot safely generate patch because CONTROL did not
        provide an exact source snippet* in answer to an architecture question.
        """
        return self.source_grounding == GROUNDING_CONTROL_EXACT_SOURCE

    @property
    def structured_patch_output_expected(self) -> bool:
        """Should the runtime insist on a structured patch payload?"""
        return self.change_requested

    # ── what the user named, carried through for bounded acquisition ────────
    @property
    def requested_paths(self) -> tuple[str, ...]:
        """Repository paths the user literally typed, in INPUT.1's extraction."""
        contract = getattr(self.shape, "contract", None)
        if contract is None:
            return ()
        return tuple(contract.explicit_evidence.file_paths)

    @property
    def subjects(self) -> tuple[str, ...]:
        """The things the order is about, as INPUT.1 preserved them."""
        contract = getattr(self.shape, "contract", None)
        if contract is None:
            return ()
        return contract.subject_values()

    @property
    def behavioral_expectations(self) -> tuple[BehavioralExpectation, ...]:
        """DEFECT.FACT.LIVE.1's typed claims, read off the shape that carries them.

        The route transports them; it never authors, edits or reorders one.  A
        consumer downstream of this receipt reads these records instead of
        re-reading the user's sentence, which is the whole point of the phase.
        """
        return tuple(getattr(self.shape, "behavioral_expectations", ()) or ())

    @property
    def obligation_preservation(self) -> dict[str, Any]:
        """INPUT.PRESERVE.LIVE.1's bounded receipt for ``obligations``.

        Read off the same authoritative set this receipt's ``obligations`` came
        from, so the facts describe the list that actually shipped.
        """
        obligation_set = getattr(self.shape, "obligation_set", None)
        if obligation_set is None:
            return {}
        # No preview here: ``obligations`` above already carries the full text,
        # and an abbreviation of it would be a second copy in the same receipt.
        return obligation_set.as_dict(include_preview=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_shape": self.task_shape,
            "change_requested": self.change_requested,
            "defect_claim_present": self.defect_claim_present,
            "defect_established": self.defect_established,
            "change_need_source": self.change_need_source,
            "selected_workflow": self.selected_workflow,
            "patch_localization_allowed": self.patch_localization_allowed,
            "preflight_validation_required": self.preflight_validation_required,
            "repository_indexing_allowed": self.repository_indexing_allowed,
            "source_grounding": self.source_grounding,
            "control_source_snippet_required": self.control_source_snippet_required,
            "repository_available": self.repository_available,
            # INPUT.1's fail-closed verdict is exposed so a later deterministic
            # adapter can prove that its literal task facts were preserved.
            # This remains descriptive and grants no execution authority.
            "preservation_passed": bool(
                self.shape is not None and self.shape.preservation_passed
            ),
            "reasons": list(self.reasons),
            "obligations": list(self.obligations),
            # INPUT.PRESERVE.LIVE.1.  Bounded preservation facts about the list
            # directly above it: how many commitments were accepted, how many
            # reached this receipt, and whether anything was abbreviated. Counts
            # and flags, never a second copy of the user's text.
            "obligation_preservation": self.obligation_preservation,
            # DEFECT.FACT.LIVE.1.  Typed, not a preview string: the values a
            # probe contract is built from survive this serialization intact and
            # no consumer has to re-parse prose to recover them.
            "behavioral_expectations": [
                fact.as_dict() for fact in self.behavioral_expectations
            ],
            "requested_paths": list(self.requested_paths),
            "subjects": list(self.subjects),
            "waiter_workflow": self.waiter_workflow,
            "write_authority": self.write_authority,
            "patch_application_authority": self.patch_application_authority,
            "human_approval_required": self.human_approval_required,
            "authority": waiter_authority(),
            "guardrails": waiter_guardrails(),
            "authority_source": (
                "existing patch safety, CTX.PATCH/CTX.APPLY, AUTO_PATCH_ENABLED, "
                "runtime authorization and human approval where required"
            ),
        }


def _source_grounding(shape: str) -> str:
    if shape == SHAPE_DEFECT_REPAIR:
        return GROUNDING_CONTROL_EXACT_SOURCE
    if shape == SHAPE_EXPLICIT_CHANGE:
        return GROUNDING_ACQUIRED_SOURCE_QUOTE
    return GROUNDING_NONE


def route_from_live_shape(
    shape: LiveTaskShape,
    *,
    repository_available: bool = False,
) -> LiveRouteReceipt:
    """Apply the live workflow policy to one already-derived shape.

    Pure and total over the four shapes.  The rules, in full:

    ``analysis_only``
        answer workflow; no patch localization, no preflight validation, no
        replacement snippet, no indexing for the sake of classification.

    ``defect_repair``
        the unchanged proven path — preflight, OPS.VALIDATE.1 facts, CONTROL
        localization, defect grounding, exact source, patch safety.

    ``explicit_change``
        change-oriented planning.  CONTROL localization is allowed because the
        change still needs a concrete target; baseline validation is allowed
        because repository health is useful; neither its passing nor its failing
        may change the task shape.

    ``needs_clarification``
        read-only.  It asks, and it never falls back to patching.
    """
    if not isinstance(shape, LiveTaskShape):
        raise TypeError("route_from_live_shape requires a LiveTaskShape")

    workflow = _SHAPE_WORKFLOWS[shape.task_shape]
    change_requested = shape.change_requested
    localization = bool(change_requested and repository_available)

    waiter_workflow: str | None = None
    if shape.waiter_task_shape is not None and shape.capability_requirements is not None:
        waiter_workflow, _, _ = select_workflow(
            shape.waiter_task_shape, shape.capability_requirements
        )

    return LiveRouteReceipt(
        task_shape=shape.task_shape,
        change_requested=change_requested,
        defect_claim_present=shape.defect_claim_present,
        change_need_source=shape.change_need_source,
        selected_workflow=workflow,
        patch_localization_allowed=localization,
        # Validation is run where it is relevant: to establish a defect, or to
        # record baseline repository health before a requested change.  An
        # architecture comparison does not need a test suite executed at it.
        preflight_validation_required=bool(change_requested and repository_available),
        # Indexing is a patch-localization cost.  Nothing is indexed in order to
        # decide what kind of task this is, and an answer does not pay for a
        # call graph it will not read.
        repository_indexing_allowed=localization,
        source_grounding=_source_grounding(shape.task_shape),
        repository_available=bool(repository_available),
        reasons=shape.reasons,
        obligations=shape.obligations,
        waiter_workflow=waiter_workflow,
        shape=shape,
    )


def route_live_task(
    raw_text: str,
    *,
    repository_available: bool = False,
    external_information_available: bool = False,
) -> LiveRouteReceipt:
    """Route one live user task, deterministically, before any repository work.

    This is the production entry point.  It costs no model call, no network
    call, no repository traversal and no index build, which is what makes it
    safe to run first — and running it first is the fix.
    """
    shape = derive_live_task_shape(
        raw_text,
        repository_available=repository_available,
        external_information_available=external_information_available,
    )
    return route_from_live_shape(shape, repository_available=repository_available)


def safe_route_live_task(
    raw_text: str,
    *,
    repository_available: bool = False,
    external_information_available: bool = False,
) -> LiveRouteReceipt:
    """Route, and fail closed to clarification rather than to patching.

    Routing metadata that cannot be produced is not a licence to guess.  A
    request that raises here is unreadable, and an unreadable request is the
    last one that should be allowed to select a patch target, so the fallback
    is the read-only route.
    """
    try:
        return route_live_task(
            raw_text,
            repository_available=repository_available,
            external_information_available=external_information_available,
        )
    except Exception:
        return LiveRouteReceipt(
            task_shape=SHAPE_NEEDS_CLARIFICATION,
            change_requested=False,
            defect_claim_present=False,
            change_need_source=CHANGE_NEED_UNRESOLVED,
            selected_workflow=WORKFLOW_CLARIFICATION,
            patch_localization_allowed=False,
            preflight_validation_required=False,
            repository_indexing_allowed=False,
            source_grounding=GROUNDING_NONE,
            repository_available=bool(repository_available),
            reasons=("no_determinable_obligation",),
        )


def route_receipt_from_dict(payload: Any) -> dict[str, Any]:
    """Read a serialised route back, tolerantly, for a downstream consumer.

    Returns the payload when it is a route receipt dict and an empty mapping
    otherwise.  Consumers treat an empty mapping as "no route was recorded" and
    fail closed on their own terms; nothing here reconstructs a route it was
    not given.
    """
    if isinstance(payload, dict) and payload.get("phase_id") == PHASE_ID:
        return payload
    return {}


def route_allows_patch_localization(payload: Any) -> bool:
    """Did a recorded route allow patch localization?  Absent route -> False.

    The conservative direction is deliberate and is the hard invariant of this
    phase: no recorded route means no patch localization, never "carry on as
    before".
    """
    receipt = route_receipt_from_dict(payload)
    return bool(receipt.get("patch_localization_allowed"))


def route_change_need_source(payload: Any) -> str:
    """The recorded change-need source, or ``unresolved`` when none was."""
    receipt = route_receipt_from_dict(payload)
    value = receipt.get("change_need_source")
    return value if value in CHANGE_NEED_SOURCES else CHANGE_NEED_UNRESOLVED


def route_is_explicit_change(payload: Any) -> bool:
    """Is this an explicit change request grounded in the user's own words?"""
    receipt = route_receipt_from_dict(payload)
    return bool(
        receipt.get("task_shape") == SHAPE_EXPLICIT_CHANGE
        and receipt.get("change_need_source") == CHANGE_NEED_EXPLICIT_USER_REQUEST
    )


def route_is_read_only(payload: Any) -> bool:
    """Is this an answer route — analysis or clarification?"""
    receipt = route_receipt_from_dict(payload)
    if not receipt:
        return False
    return not bool(receipt.get("change_requested"))


def render_live_route_json(receipt: LiveRouteReceipt) -> str:
    """Render a route receipt as deterministic JSON."""
    return json.dumps(receipt.as_dict(), indent=2, ensure_ascii=False, sort_keys=False)


__all__ = [
    "CHANGE_NEED_EXPLICIT_USER_REQUEST",
    "CHANGE_NEED_GROUNDED_DEFECT",
    "CHANGE_NEED_NONE",
    "CHANGE_NEED_UNRESOLVED",
    "GROUNDING_ACQUIRED_SOURCE_QUOTE",
    "GROUNDING_CONTROL_EXACT_SOURCE",
    "GROUNDING_NONE",
    "LIVE_ROUTE_SCHEMA_VERSION",
    "LIVE_WORKFLOWS",
    "LiveRouteReceipt",
    "PHASE_ID",
    "ROUTE_STATE_KEY",
    "SOURCE_GROUNDING_MODES",
    "WORKFLOW_ANALYSIS_ANSWER",
    "WORKFLOW_CLARIFICATION",
    "WORKFLOW_DEFECT_REPAIR",
    "WORKFLOW_EXPLICIT_CHANGE",
    "render_live_route_json",
    "route_allows_patch_localization",
    "route_change_need_source",
    "route_from_live_shape",
    "route_is_explicit_change",
    "route_is_read_only",
    "route_live_task",
    "route_receipt_from_dict",
    "safe_route_live_task",
]
