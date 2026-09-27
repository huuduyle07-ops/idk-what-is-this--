"""CHECK.LIVE.1 — shadow post-run reconciliation wiring.

This module turns facts a real execution already possesses into the typed inputs
CHECK.1 requires, invokes the frozen CHECK.1 public API, and records the answer
as a bounded shadow receipt.  It is deliberately powerless:

* **shadow only.**  The authoritative run result is computed, returned and
  persisted exactly as before.  A CHECK.1 status of ``blocked`` beside an
  authoritative ``success`` is surfaced, not resolved — that disagreement is the
  entire point of dogfooding this phase before promoting it.
* **no reconciliation policy here.**  There is no ``if forbidden_path: blocked``
  anywhere in the live wiring.  Producers produce; CHECK.1 decides.  One
  reconciliation policy, in one frozen module.
* **failure isolated.**  Any producer or checker failure is recorded as a
  bounded category and the original execution outcome survives untouched.  A
  shadow checker may never hide an application failure, a validation failure or
  a worker failure.
* **nothing new is executed.**  No extra validation run, no extra patch
  application, no model call, no network call, and no new repository traversal:
  every fact is either already held by the apply path or read from a bounded set
  of paths that path already named.

Default: **off**.  The environment flag ``POST_RUN_RECONCILIATION_SHADOW``
enables it for dogfood and development.  Off means byte-identical behaviour to
before this phase, which is the strongest possible preservation guarantee while
the checker is unproven.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.live_change_observation import (
    LiveObservationBoundError,
    LiveObservedChangeSet,
    LivePathDigests,
    RENAME_DETECTION_SUPPORTED,
    canonical_relative_path,
    canonical_relative_paths,
    derive_observed_change_records,
    digest_known_paths,
    observed_change_state_fingerprint,
    subtract_change_records,
)
from core.live_execution_authorization import (
    LiveAuthorityInputError,
    LiveAuthorityWideningError,
    build_live_execution_authorization,
    live_authorization_fingerprint,
    upstream_authority_from_patch_safety,
)
from core.live_validation_receipt import (
    LIVE_VALIDATION_ID,
    LIVE_VALIDATION_KIND,
    LiveValidationInputError,
    build_live_validation_expectation,
    build_live_validation_receipt,
    live_validation_receipt_fingerprint,
    live_validation_target_scope,
)
from core.live_worker_declaration import (
    DECLARATION_SOURCE_INDEPENDENT,
    DECLARATION_SOURCE_LEGACY_PLAN_DERIVED,
    DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
    DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
    DECLARATION_SOURCE_UNAVAILABLE,
    DECLARATION_STAGE_COMPLETED,
    DECLARATION_STAGE_PRE_EXECUTION_INTENT,
    LiveWorkerDeclarationInputError,
    WorkerChangeDeclaration,
    worker_change_declaration_from_mapping,
)
from core.pre_execution_change_intent import (
    INTENT_OBSERVED_UNAVAILABLE,
    INTENT_PLAN_AGREEMENTS,
    INTENT_PLAN_UNAVAILABLE,
    compare_intent_with_observed_changes,
)
from core.worker_patch_envelope import PreExecutionChangeIntent
from core.live_worker_report import (
    LiveWorkerReportInputError,
    build_live_worker_report,
    declared_changes_from_patch_plan,
    declared_changes_from_worker_declaration,
    declared_status_from_apply_outcome,
    declared_status_from_worker_declaration,
    declared_validation_action,
    declared_validation_actions_from_worker_declaration,
    live_worker_report_fingerprint,
)
from core.post_run_observation import (
    build_observed_post_run_facts,
    observed_changes_from_records,
)
from core.post_run_reconciliation import (
    PostRunReconciliationRequest,
    STATUS_BLOCKED,
    STATUS_INCOMPLETE,
    STATUS_INCONSISTENT_INPUT,
    STATUS_RECONCILED,
    STATUS_RECONCILED_WITH_WARNINGS,
    STATUS_SUSPICIOUS,
    observed_post_run_facts_fingerprint,
    reconcile_post_run,
)
from core.repository_identity import derive_repository_id


PHASE_ID = "CHECK.LIVE.1"
RECEIPT_KIND = "shadow_post_run_check_receipt"
RECEIPT_SCHEMA_VERSION = "check_live_1_shadow_post_run_check_v1"

#: Default-off feature flag.  Enabling it adds observation only.
ENVIRONMENT_FLAG = "POST_RUN_RECONCILIATION_SHADOW"

#: Name of the additive artifact written into the existing replay bundle.
SHADOW_ARTIFACT_NAME = "post_run_reconciliation_shadow.json"

#: Additive, non-authoritative keys the apply result may carry when the shadow
#: is enabled.  Their meaning never changes an existing key's meaning.
RESULT_AVAILABLE_KEY = "post_run_reconciliation_available"
RESULT_STATUS_KEY = "post_run_reconciliation_status"
RESULT_COMPLETENESS_KEY = "post_run_reconciliation_producer_completeness"
RESULT_AUTHORITATIVE_EFFECT_KEY = "post_run_reconciliation_authoritative_effect"

RESULT_METADATA_KEYS: tuple[str, ...] = (
    RESULT_AVAILABLE_KEY,
    RESULT_STATUS_KEY,
    RESULT_COMPLETENESS_KEY,
    RESULT_AUTHORITATIVE_EFFECT_KEY,
)


# ── Bounded vocabularies ──────────────────────────────────────────────────────

#: The existing run's own terminal category, carried verbatim and never
#: rewritten.  ``not_reached`` means the execution ended before the post-run
#: boundary, not that it succeeded or failed differently.
RUN_STATUS_SUCCESS = "success"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_BLOCKED = "blocked"
RUN_STATUS_NOT_REACHED = "not_reached"

AUTHORITATIVE_RUN_STATUSES: tuple[str, ...] = (
    RUN_STATUS_SUCCESS,
    RUN_STATUS_FAILED,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_NOT_REACHED,
)

#: What the shadow observer itself managed to do.
SHADOW_DISABLED = "disabled"
SHADOW_EVALUATED = "evaluated"
SHADOW_NOT_REACHED = "not_reached"
SHADOW_PRODUCER_UNAVAILABLE = "producer_unavailable"
SHADOW_CHECKER_ERROR = "checker_error"

SHADOW_OUTCOMES: tuple[str, ...] = (
    SHADOW_DISABLED,
    SHADOW_EVALUATED,
    SHADOW_NOT_REACHED,
    SHADOW_PRODUCER_UNAVAILABLE,
    SHADOW_CHECKER_ERROR,
)

#: How much of CHECK.1's required input the live path could actually produce.
#: Three explicit bands, never a numeric score.
COMPLETENESS_COMPLETE = "complete"
COMPLETENESS_PARTIAL = "partial"
COMPLETENESS_UNAVAILABLE = "unavailable"

PRODUCER_COMPLETENESS: tuple[str, ...] = (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_PARTIAL,
    COMPLETENESS_UNAVAILABLE,
)

#: Which CHECK.1 input the live path could not supply.
MISSING_EXECUTION_AUTHORIZATION = "execution_authorization_missing"
MISSING_WORKER_REPORT = "worker_report_missing"
MISSING_OBSERVED_CHANGE_IDENTITY = "observed_change_identity_missing"
INCOMPLETE_OBSERVED_CHANGE_IDENTITY = "observed_change_identity_incomplete"
MISSING_VALIDATION_EXPECTATION = "validation_expectation_missing"
MISSING_VALIDATION_RECEIPT = "validation_receipt_missing"
MISSING_FINAL_STATE_BINDING = "final_state_binding_missing"
MISSING_EXECUTION_RUN_IDENTITY = "execution_run_identity_missing"
MISSING_REPOSITORY_IDENTITY = "repository_identity_missing"
MISSING_TASK_CONTRACT = "task_contract_unavailable"
MISSING_WORKER_OWNERSHIP = "worker_ownership_unavailable"
MISSING_TYPED_WORKER_FACT = "typed_worker_fact_unavailable"
MISSING_SIDE_EFFECT_OBSERVATION = "validation_side_effect_observation_unavailable"

MISSING_LIVE_FACTS: tuple[str, ...] = (
    MISSING_EXECUTION_AUTHORIZATION,
    MISSING_WORKER_REPORT,
    MISSING_OBSERVED_CHANGE_IDENTITY,
    INCOMPLETE_OBSERVED_CHANGE_IDENTITY,
    MISSING_VALIDATION_EXPECTATION,
    MISSING_VALIDATION_RECEIPT,
    MISSING_FINAL_STATE_BINDING,
    MISSING_EXECUTION_RUN_IDENTITY,
    MISSING_REPOSITORY_IDENTITY,
    MISSING_TASK_CONTRACT,
    MISSING_WORKER_OWNERSHIP,
    MISSING_TYPED_WORKER_FACT,
    MISSING_SIDE_EFFECT_OBSERVATION,
)

#: Facts whose absence means the fact set could not be built at all.
_FATAL_MISSING_FACTS: frozenset[str] = frozenset(
    {
        MISSING_EXECUTION_AUTHORIZATION,
        MISSING_WORKER_REPORT,
        MISSING_OBSERVED_CHANGE_IDENTITY,
        MISSING_FINAL_STATE_BINDING,
        MISSING_EXECUTION_RUN_IDENTITY,
        MISSING_REPOSITORY_IDENTITY,
    }
)

#: Absences that no CHECK.LIVE.1 producer could repair, because the upstream
#: contract that would supply them does not exist yet.  They are reported so a
#: reader can see them, but they do not make an otherwise complete live fact set
#: look like a producer gap:
#:
#: * no phase currently projects an ``INPUT.1`` TaskContract into the apply
#:   path, so the live task-shape binding is the only one available;
#: * the apply path runs one execution unit with no per-worker path ownership,
#:   which CHECK.1 already reports honestly as
#:   ``worker_scope_ownership_unavailable``.
_STRUCTURAL_UPSTREAM_ABSENCES: frozenset[str] = frozenset(
    {MISSING_TASK_CONTRACT, MISSING_WORKER_OWNERSHIP}
)

#: Why the shadow observer itself failed.  Bounded categories only: no
#: traceback, no source, no command text and no environment value is ever
#: serialized into a run artifact.
ERROR_PRODUCER_INPUT = "producer_input_error"
ERROR_PRODUCER_BOUND = "producer_bound_exceeded"
ERROR_AUTHORITY_WIDENING_REFUSED = "authority_widening_refused"
ERROR_RECONCILIATION_CONTRACT = "reconciliation_contract_error"
ERROR_ARTIFACT_PERSISTENCE = "artifact_persistence_failed"
ERROR_UNEXPECTED = "unexpected_shadow_error"

SHADOW_ERROR_CATEGORIES: tuple[str, ...] = (
    ERROR_PRODUCER_INPUT,
    ERROR_PRODUCER_BOUND,
    ERROR_AUTHORITY_WIDENING_REFUSED,
    ERROR_RECONCILIATION_CONTRACT,
    ERROR_ARTIFACT_PERSISTENCE,
    ERROR_UNEXPECTED,
)

#: Why the shadow could not reach a post-run reconciliation at all.
NOT_REACHED_BOUNDARY = "execution_did_not_reach_post_run_boundary"

#: How the shadow checker and the existing executor compare.  Nothing here
#: decides anything: a disagreement is a measurement.
DISAGREEMENT_NONE = "none"
DISAGREEMENT_CHECKER_STRICTER = "checker_stricter_than_run"
DISAGREEMENT_CHECKER_WEAKER = "checker_weaker_than_run"
DISAGREEMENT_NOT_COMPARABLE = "not_comparable"

DISAGREEMENT_KINDS: tuple[str, ...] = (
    DISAGREEMENT_NONE,
    DISAGREEMENT_CHECKER_STRICTER,
    DISAGREEMENT_CHECKER_WEAKER,
    DISAGREEMENT_NOT_COMPARABLE,
)

_CLEAN_RECONCILIATION_STATUSES: frozenset[str] = frozenset(
    {STATUS_RECONCILED, STATUS_RECONCILED_WITH_WARNINGS}
)
_ADVERSE_RECONCILIATION_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_INCOMPLETE,
        STATUS_SUSPICIOUS,
        STATUS_BLOCKED,
        STATUS_INCONSISTENT_INPUT,
    }
)

MAX_REPORTED_PATHS = 64
MAX_DISAGREEMENT_REASONS = 32

SHADOW_NOTICE = (
    "Shadow post-run reconciliation is observation only. It does not change "
    "the authoritative run outcome, cannot block or permit a patch, and leaves "
    "semantic goal review and human review outstanding."
)


def is_post_run_reconciliation_shadow_enabled(value: Any = None) -> bool:
    """Missing configuration is disabled; only an explicit truthy value enables."""
    raw = os.getenv(ENVIRONMENT_FLAG) if value is None else value
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


# ── Live observation input ────────────────────────────────────────────────────

@dataclass(frozen=True)
class LiveExecutionObservation:
    """Facts the live apply path already holds at its post-run boundary.

    Everything here is either a value the apply path computed for its own
    purposes, or a bounded digest of paths it already named.  Nothing is
    discovered, inferred from prose, or re-executed to populate it.
    """

    project_root: str
    execution_run_id: str
    authoritative_run_status: str
    plan: tuple[Mapping[str, Any], ...] = ()
    patch_safety_verdict: Mapping[str, Any] = field(default_factory=dict)
    pre_apply_digests: LivePathDigests | None = None
    reached_post_run_boundary: bool = True
    apply_succeeded: bool = False
    rollback_performed: bool = False
    blocked: bool = False
    validation_requested: bool = False
    validation_executed: bool = False
    validation_passed: bool | None = None
    validation_blocked: bool = False
    validation_crashed: bool = False
    #: OPS.VALIDATE.2 - the validation was attempted and the runtime stopped it
    #: at its own budget.  Carried alongside ``validation_inconclusive`` rather
    #: than instead of it: the receipt result becomes CHECK.1's existing
    #: ``timed_out`` (a failing result, so a required expectation is still not
    #: discharged) while the worker's declared action stays ``not_run``.  Both
    #: words are already in CHECK.1's frozen vocabulary; nothing is redesigned.
    validation_timed_out: bool = False
    #: OPS.VALIDATE.1 - the validation ran but established neither a pass nor a
    #: failure (no tests collected, runner unavailable).  Carried separately
    #: from ``validation_passed`` so a receipt never reports a red test suite
    #: for a run in which no test existed.
    validation_inconclusive: bool = False
    validation_side_effects: Mapping[str, Any] = field(default_factory=dict)
    worker_id: str | None = None
    worker_declaration: WorkerChangeDeclaration | Mapping[str, Any] | None = None
    pre_execution_change_intent: PreExecutionChangeIntent | None = None
    intent_plan_agreement: str = INTENT_PLAN_UNAVAILABLE


# ── Shadow receipt ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ShadowPostRunCheckReceipt:
    """One bounded record of a shadow CHECK.1 invocation.

    ``authoritative_effect`` is a constant ``False``.  It is not a field a
    caller may set, because there is no state of this phase in which the shadow
    check may affect the run it observed.
    """

    execution_run_id: str
    repository_id: str
    authoritative_run_status: str
    shadow_outcome: str
    producer_completeness: str
    missing_live_facts: tuple[str, ...] = ()
    reconciliation_status: str | None = None
    reconciliation_fingerprint: str | None = None
    disagreement: str = DISAGREEMENT_NOT_COMPARABLE
    disagreement_reasons: tuple[str, ...] = ()
    shadow_error_category: str | None = None
    not_reached_reason: str | None = None
    observation: Mapping[str, Any] = field(default_factory=dict)
    reconciliation: Mapping[str, Any] | None = None
    worker_declaration_source: str | None = None
    worker_declaration_invalid: bool = False
    declaration_stage: str | None = None
    intent_plan_agreement: str = INTENT_PLAN_UNAVAILABLE
    intent_observed_diagnostic: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.intent_plan_agreement not in INTENT_PLAN_AGREEMENTS:
            raise ValueError("unsupported intent-plan agreement")
        if self.worker_declaration_source == DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT:
            if self.declaration_stage != DECLARATION_STAGE_PRE_EXECUTION_INTENT:
                raise ValueError("pre-execution intent source requires its explicit stage")
        elif self.worker_declaration_source in {
            DECLARATION_SOURCE_INDEPENDENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
        }:
            if self.declaration_stage not in {None, DECLARATION_STAGE_COMPLETED}:
                raise ValueError("post-execution declaration source has the wrong stage")
        elif self.declaration_stage is not None:
            raise ValueError("a derived or unavailable declaration has no native stage")

    @property
    def authoritative_effect(self) -> bool:
        """The shadow check never affects the run it observed."""
        return False

    @property
    def reconciliation_available(self) -> bool:
        return self.reconciliation_status is not None

    @property
    def independent_worker_declaration_missing(self) -> bool:
        return self.worker_declaration_source != DECLARATION_SOURCE_INDEPENDENT

    @property
    def channel_provenance(self) -> str:
        if self.worker_declaration_source in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }:
            return "independently_declared_channel"
        return "unavailable"

    @property
    def intent_fidelity_measurable(self) -> bool:
        return self.worker_declaration_source in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }

    @property
    def self_report_fidelity_measurable(self) -> bool:
        return self.worker_declaration_source in {
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }

    @property
    def intent_observed_relation(self) -> str:
        relation = self.intent_observed_diagnostic.get("relation")
        return relation if isinstance(relation, str) else INTENT_OBSERVED_UNAVAILABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "receipt_kind": RECEIPT_KIND,
            "phase_id": PHASE_ID,
            "execution_run_id": self.execution_run_id,
            "repository_id": self.repository_id,
            "authoritative_run_status": self.authoritative_run_status,
            "authoritative_effect": self.authoritative_effect,
            "shadow_outcome": self.shadow_outcome,
            "reconciliation_available": self.reconciliation_available,
            "reconciliation_status": self.reconciliation_status,
            "reconciliation_fingerprint": self.reconciliation_fingerprint,
            "producer_completeness": self.producer_completeness,
            "missing_live_facts": list(self.missing_live_facts),
            "disagreement": self.disagreement,
            "disagreement_reasons": list(self.disagreement_reasons),
            "shadow_error_category": self.shadow_error_category,
            "not_reached_reason": self.not_reached_reason,
            "worker_declaration_source": self.worker_declaration_source,
            "worker_declaration_invalid": self.worker_declaration_invalid,
            "declaration_stage": self.declaration_stage,
            "channel_provenance": self.channel_provenance,
            "intent_fidelity_measurable": self.intent_fidelity_measurable,
            "self_report_fidelity_measurable": self.self_report_fidelity_measurable,
            "same_model_channel_is_independent_evidence": False,
            "intent_plan_agreement": self.intent_plan_agreement,
            "intent_observed_relation": self.intent_observed_relation,
            "intent_observed_diagnostic": dict(self.intent_observed_diagnostic),
            "check_1_stage_interpretation": (
                "pre_execution_intent_not_completion"
                if self.declaration_stage == DECLARATION_STAGE_PRE_EXECUTION_INTENT
                else "post_execution_declaration_or_legacy_projection"
            ),
            "independent_worker_declaration_missing": (
                self.independent_worker_declaration_missing
            ),
            "observation": dict(self.observation),
            "reconciliation": (
                dict(self.reconciliation)
                if self.reconciliation is not None
                else None
            ),
            "check_2_handoff": check_2_handoff_readiness(self),
            "guardrails": shadow_guardrails(),
            "notice": SHADOW_NOTICE,
        }

    def result_metadata(self) -> dict[str, Any]:
        """The minimal additive summary an existing run response may carry."""
        return {
            RESULT_AVAILABLE_KEY: self.reconciliation_available,
            RESULT_STATUS_KEY: self.reconciliation_status,
            RESULT_COMPLETENESS_KEY: self.producer_completeness,
            RESULT_AUTHORITATIVE_EFFECT_KEY: False,
        }


def shadow_guardrails() -> dict[str, bool]:
    """Every power the shadow wiring declines to exercise."""
    return {
        "shadow_only": True,
        "authoritative_effect": False,
        "authoritative_run_status_changed": False,
        "run_blocked_by_checker": False,
        "patch_applied": False,
        "patch_refused": False,
        "patch_rolled_back": False,
        "validation_executed": False,
        "validation_re_executed": False,
        "repository_traversed": False,
        "repository_indexed": False,
        "prose_parsed": False,
        "model_called": False,
        "network_call_performed": False,
        "git_stash_invoked": False,
        "git_reset_invoked": False,
        "git_clean_invoked": False,
        "reconciliation_policy_reimplemented": False,
        "check_2_invoked": False,
        "check_3_implemented": False,
        "semantic_goal_review_performed": False,
        "human_approval_required": True,
    }


def check_2_handoff_readiness(
    receipt: "ShadowPostRunCheckReceipt",
) -> dict[str, bool]:
    """Which future CHECK.2 inputs the live path can already produce.

    Nothing missing here is manufactured.  A false value is a statement that no
    producer exists yet, not an invitation to invent one.
    """
    reconciliation = receipt.reconciliation or {}
    preservation = reconciliation.get("preservation_findings") or []
    return {
        "task_contract_available": False,
        "preservation_obligations_available": bool(preservation),
        "final_state_identity_available": bool(
            receipt.reconciliation_fingerprint
        ),
        "execution_run_identity_available": bool(receipt.execution_run_id),
        "requirement_ledger_available": False,
        "goal_proposition_binding_available": False,
        "claim_assessment_available": False,
        "check_2_invoked": False,
    }


def shadow_disagreement(
    authoritative_run_status: str,
    reconciliation_status: str | None,
) -> str:
    """Compare the existing terminal outcome with the shadow checker's."""
    if reconciliation_status is None:
        return DISAGREEMENT_NOT_COMPARABLE
    if authoritative_run_status == RUN_STATUS_NOT_REACHED:
        return DISAGREEMENT_NOT_COMPARABLE
    if authoritative_run_status == RUN_STATUS_SUCCESS:
        return (
            DISAGREEMENT_CHECKER_STRICTER
            if reconciliation_status in _ADVERSE_RECONCILIATION_STATUSES
            else DISAGREEMENT_NONE
        )
    return (
        DISAGREEMENT_CHECKER_WEAKER
        if reconciliation_status in _CLEAN_RECONCILIATION_STATUSES
        else DISAGREEMENT_NONE
    )


# ── Producers ─────────────────────────────────────────────────────────────────

def plan_target_paths(plan: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Canonical target paths of a patch plan, as the apply path names them."""
    return canonical_relative_paths(
        (op.get("relative_path") or op.get("file") or "")
        for op in plan
        if isinstance(op, Mapping)
    )


def live_task_shape_fingerprint(
    repository_id: str,
    plan: Sequence[Mapping[str, Any]],
) -> str:
    """A deterministic identity for the live execution's task shape.

    This is **not** an ``INPUT.1`` TaskContract fingerprint and never pretends
    to be one: the live apply path is handed a patch plan, not a preserved user
    request.  Callers record ``task_contract_unavailable`` alongside it so no
    consumer reads it as a preserved-requirement binding.
    """
    shape = sorted(
        {
            (
                str(op.get("op") or ""),
                canonical_relative_path(
                    op.get("relative_path") or op.get("file") or ""
                ),
            )
            for op in plan
            if isinstance(op, Mapping)
        }
    )
    return _fingerprint(
        {
            "kind": "check_live_1_task_shape_v1",
            "phase_id": PHASE_ID,
            "repository_id": str(repository_id),
            "operations": [
                {"op": op_type, "path": path} for op_type, path in shape
            ],
        }
    )


def side_effect_paths(
    validation_side_effects: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
    """Read the existing validation side-effect report.

    Returns ``(created, modified, deleted, supported)`` as canonical paths.  No
    new observation happens here: this collector already ran inside the apply
    path, around the validation it was measuring.
    """
    if not isinstance(validation_side_effects, Mapping):
        return (), (), (), False
    supported = bool(validation_side_effects.get("supported"))

    def _paths(key: str) -> tuple[str, ...]:
        entries = validation_side_effects.get(key) or []
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            return ()
        return canonical_relative_paths(
            entry.get("path") for entry in entries if isinstance(entry, Mapping)
        )

    return _paths("created"), _paths("modified"), _paths("deleted"), supported


def observe_final_change_set(
    observation: LiveExecutionObservation,
) -> tuple[LiveObservedChangeSet, LivePathDigests, tuple[str, ...]]:
    """Derive the actual final change set at the post-run boundary.

    Actual facts outrank the intended patch: the observed set is the difference
    between the pre-apply identity of the paths the plan named and the identity
    of those paths *plus* whatever the existing validation side-effect collector
    reported, read once, at the end.

    Returns ``(change_set, after_digests, validation_window_paths)``.
    """
    if observation.pre_apply_digests is None:
        raise LiveObservationBoundError("pre-apply digests were not observed")

    root = Path(observation.project_root)
    created, modified, deleted, _supported = side_effect_paths(
        observation.validation_side_effects
    )
    validation_window = tuple(sorted(set(created) | set(modified) | set(deleted)))

    before_map = dict(observation.pre_apply_digests.digests)
    # A path the authoritative side-effect collector reports as *created* during
    # validation was absent when validation started, and the patch engine writes
    # only plan paths, so it was absent before the apply too.  That is an
    # observation, not a guess.
    for path in created:
        before_map.setdefault(path, None)

    before = LivePathDigests(
        digests=tuple(sorted(before_map.items())),
        unreadable_paths=observation.pre_apply_digests.unreadable_paths,
        oversized_paths=observation.pre_apply_digests.oversized_paths,
    )

    after_paths = tuple(sorted(set(before.observed_paths) | set(validation_window)))
    after = digest_known_paths(root, after_paths)
    change_set = derive_observed_change_records(before, after)
    return change_set, after, validation_window


def _reconciliation_projection(result: Any) -> dict[str, Any]:
    """Serialize CHECK.1's own result, unaltered and unabridged.

    CHECK.1 already carries only bounded identity data — paths, change kinds,
    digests, bounded reason codes — and its boundary suite proves no diff, patch
    body or source content can appear in it, so the whole result is safe to
    persist and is the most useful dogfood record available.
    """
    return dict(result.as_dict())


# ── Orchestration ─────────────────────────────────────────────────────────────

def _resolve_worker_declaration(
    raw: WorkerChangeDeclaration | Mapping[str, Any] | None,
) -> tuple[WorkerChangeDeclaration | None, bool]:
    """Resolve structured declaration input and record invalid attempts."""
    if raw is None:
        return None, False
    if type(raw) is WorkerChangeDeclaration:
        return raw, False
    if isinstance(raw, Mapping):
        try:
            return worker_change_declaration_from_mapping(raw), False
        except LiveWorkerDeclarationInputError:
            return None, True
    return None, True


def not_reached_receipt(
    *,
    execution_run_id: str,
    repository_id: str,
    authoritative_run_status: str,
    reason: str = NOT_REACHED_BOUNDARY,
) -> ShadowPostRunCheckReceipt:
    """An honest 'no reconciliation' record for a run that ended early.

    No empty successful reconciliation is fabricated: CHECK.1 was never given a
    fact set, so it has no opinion, and the receipt says so.
    """
    return ShadowPostRunCheckReceipt(
        execution_run_id=str(execution_run_id or ""),
        repository_id=str(repository_id or ""),
        authoritative_run_status=authoritative_run_status,
        shadow_outcome=SHADOW_NOT_REACHED,
        producer_completeness=COMPLETENESS_UNAVAILABLE,
        missing_live_facts=(
            MISSING_EXECUTION_AUTHORIZATION,
            MISSING_WORKER_REPORT,
            MISSING_OBSERVED_CHANGE_IDENTITY,
            MISSING_FINAL_STATE_BINDING,
        ),
        disagreement=DISAGREEMENT_NOT_COMPARABLE,
        not_reached_reason=reason,
        observation={"reached_post_run_boundary": False},
    )


def run_shadow_post_run_reconciliation(
    observation: LiveExecutionObservation,
) -> ShadowPostRunCheckReceipt:
    """Produce CHECK.1 inputs from live facts and invoke the frozen checker.

    This function raises on a genuine producer or contract error; use
    :func:`safe_run_shadow_post_run_reconciliation` from a live path so an
    unexpected failure can never displace the authoritative run result.
    """
    if not isinstance(observation, LiveExecutionObservation):
        raise TypeError(
            "run_shadow_post_run_reconciliation requires a "
            "LiveExecutionObservation"
        )
    if observation.authoritative_run_status not in AUTHORITATIVE_RUN_STATUSES:
        raise ValueError(
            "unsupported authoritative run status: "
            f"{observation.authoritative_run_status!r}"
        )

    missing: set[str] = {MISSING_TASK_CONTRACT}

    execution_run_id = str(observation.execution_run_id or "").strip()
    try:
        repository_id = derive_repository_id(observation.project_root)
    except (NotADirectoryError, OSError, ValueError):
        repository_id = ""

    if not execution_run_id:
        missing.add(MISSING_EXECUTION_RUN_IDENTITY)
    if not repository_id or len(repository_id) > 160:
        missing.add(MISSING_REPOSITORY_IDENTITY)
        repository_id = repository_id or ""

    if not observation.reached_post_run_boundary:
        return not_reached_receipt(
            execution_run_id=execution_run_id,
            repository_id=repository_id,
            authoritative_run_status=observation.authoritative_run_status,
        )

    declaration, worker_declaration_invalid = _resolve_worker_declaration(
        observation.worker_declaration
    )
    worker_declaration_source = (
        declaration.source_provenance
        if declaration is not None
        else (
            DECLARATION_SOURCE_LEGACY_PLAN_DERIVED
            if observation.plan
            else DECLARATION_SOURCE_UNAVAILABLE
        )
    )
    declaration_stage = declaration.declaration_stage if declaration is not None else None

    if missing & _FATAL_MISSING_FACTS:
        return ShadowPostRunCheckReceipt(
            execution_run_id=execution_run_id,
            repository_id=repository_id,
            authoritative_run_status=observation.authoritative_run_status,
            shadow_outcome=SHADOW_PRODUCER_UNAVAILABLE,
            producer_completeness=COMPLETENESS_UNAVAILABLE,
            missing_live_facts=_ordered_missing(missing),
            disagreement=DISAGREEMENT_NOT_COMPARABLE,
            worker_declaration_source=worker_declaration_source,
            worker_declaration_invalid=worker_declaration_invalid,
            declaration_stage=declaration_stage,
            intent_plan_agreement=observation.intent_plan_agreement,
            observation={"reached_post_run_boundary": True},
        )

    # ── observed change facts ────────────────────────────────────────────────
    change_set, after_digests, validation_window = observe_final_change_set(
        observation
    )
    if change_set.observation_incomplete:
        missing.add(INCOMPLETE_OBSERVED_CHANGE_IDENTITY)
    if observation.rollback_performed:
        # The patched state existed between apply and rollback and was never
        # digested, so the observed identity of this run is honestly partial.
        missing.add(INCOMPLETE_OBSERVED_CHANGE_IDENTITY)
    _created, _modified, _deleted, side_effects_supported = side_effect_paths(
        observation.validation_side_effects
    )
    if observation.validation_executed and not side_effects_supported:
        missing.add(MISSING_SIDE_EFFECT_OBSERVATION)

    base_digests = observation.pre_apply_digests
    if base_digests is None:  # pragma: no cover - guarded above
        raise LiveObservationBoundError("pre-apply digests were not observed")

    pre_state = observed_change_state_fingerprint(repository_id, base_digests, ())
    final_state = observed_change_state_fingerprint(
        repository_id, base_digests, change_set.records
    )
    validated_records = subtract_change_records(
        change_set.records, validation_window
    )
    validated_state = observed_change_state_fingerprint(
        repository_id, base_digests, validated_records
    )

    # ── execution authorization ──────────────────────────────────────────────
    targets = plan_target_paths(observation.plan)
    upstream_authority, upstream_reasons, upstream_fingerprint = (
        upstream_authority_from_patch_safety(
            targets, observation.patch_safety_verdict
        )
    )

    expectation, expectation_unavailable = build_live_validation_expectation(
        validation_requested=observation.validation_requested,
        target_scope=targets,
    )
    if expectation is None:
        missing.add(MISSING_VALIDATION_EXPECTATION)

    authorization = build_live_execution_authorization(
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        task_contract_fingerprint=live_task_shape_fingerprint(
            repository_id, observation.plan
        ),
        pre_execution_state_fingerprint=pre_state,
        upstream_authority=upstream_authority,
        upstream_forbidden_reasons=upstream_reasons,
        upstream_authority_fingerprint=upstream_fingerprint,
        validation_expectations=() if expectation is None else (expectation,),
        worker_id=observation.worker_id,
    )
    if not authorization.declares_worker_ownership:
        missing.add(MISSING_WORKER_OWNERSHIP)

    # ── worker report ────────────────────────────────────────────────────────
    if declaration is not None:
        declared_changes, untranslated = (
            declared_changes_from_worker_declaration(declaration)
        )
        declared_status = declared_status_from_worker_declaration(declaration)
        declared_validation_actions = (
            declared_validation_actions_from_worker_declaration(declaration)
        )
        declared_limitations = declaration.limitations
        declared_unresolved_items = declaration.unresolved_items
        report_worker_id = declaration.worker_id
    else:
        declared_changes, untranslated = declared_changes_from_patch_plan(
            observation.plan
        )
        declared_status = declared_status_from_apply_outcome(
            apply_succeeded=observation.apply_succeeded,
            rollback_performed=observation.rollback_performed,
            blocked=observation.blocked,
        )
        action = declared_validation_action(
            validation_id=LIVE_VALIDATION_ID if expectation is not None else None,
            validation_kind=LIVE_VALIDATION_KIND,
            executed=observation.validation_executed,
            passed=observation.validation_passed,
            inconclusive=observation.validation_inconclusive,
        )
        declared_validation_actions = () if action is None else (action,)
        declared_limitations = ()
        declared_unresolved_items = ()
        report_worker_id = observation.worker_id
    if untranslated:
        missing.add(MISSING_TYPED_WORKER_FACT)
    report = build_live_worker_report(
        execution_run_id=execution_run_id,
        declared_status=declared_status,
        declared_changes=declared_changes,
        declared_validation_actions=declared_validation_actions,
        declared_limitations=declared_limitations,
        declared_unresolved_items=declared_unresolved_items,
        worker_id=report_worker_id,
    )

    # ── validation receipt ───────────────────────────────────────────────────
    # A target scope too large to bind is a *missing* receipt, never a raised
    # error and never a fabricated result: the worker's typed validation claim
    # then stands unverified, which is exactly what CHECK.1 should see.
    receipt = (
        None
        if live_validation_target_scope(targets) is None
        else build_live_validation_receipt(
            execution_run_id=execution_run_id,
            repository_id=repository_id,
            validated_state_fingerprint=validated_state,
            target_scope=targets,
            executed=observation.validation_executed,
            passed=observation.validation_passed,
            blocked=observation.validation_blocked,
            crashed=observation.validation_crashed,
            timed_out=observation.validation_timed_out,
            inconclusive=observation.validation_inconclusive,
        )
    )
    if receipt is None:
        missing.add(MISSING_VALIDATION_RECEIPT)

    facts = build_observed_post_run_facts(
        facts_id=f"live-facts-{final_state[:32]}",
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        pre_execution_state_fingerprint=pre_state,
        post_execution_state_fingerprint=final_state,
        post_validation_state_fingerprint=final_state,
        final_state_fingerprint=final_state,
        observed_changes=observed_changes_from_records(change_set.records),
        validation_receipts=() if receipt is None else (receipt,),
        rename_detection_supported=RENAME_DETECTION_SUPPORTED,
    )

    request = PostRunReconciliationRequest(
        authorization=authorization,
        worker_report=report,
        observed_facts=facts,
        expected_task_contract_fingerprint=(
            authorization.task_contract_fingerprint
        ),
        expected_authorization_fingerprint=live_authorization_fingerprint(
            authorization
        ),
        expected_worker_report_fingerprint=live_worker_report_fingerprint(report),
        expected_observed_facts_fingerprint=observed_post_run_facts_fingerprint(
            facts
        ),
        expected_validation_receipt_fingerprints=(
            ()
            if receipt is None
            else (live_validation_receipt_fingerprint(receipt),)
        ),
    )

    result = reconcile_post_run(request)
    intent_observed = compare_intent_with_observed_changes(
        observation.pre_execution_change_intent,
        change_set.records,
    )

    completeness = (
        COMPLETENESS_COMPLETE
        if not (missing - _STRUCTURAL_UPSTREAM_ABSENCES)
        else COMPLETENESS_PARTIAL
    )
    reasons = tuple(result.inconsistencies)[:MAX_DISAGREEMENT_REASONS]

    return ShadowPostRunCheckReceipt(
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        authoritative_run_status=observation.authoritative_run_status,
        shadow_outcome=SHADOW_EVALUATED,
        producer_completeness=completeness,
        missing_live_facts=_ordered_missing(missing),
        reconciliation_status=result.status,
        reconciliation_fingerprint=result.reconciliation_fingerprint,
        disagreement=shadow_disagreement(
            observation.authoritative_run_status, result.status
        ),
        disagreement_reasons=reasons,
        worker_declaration_source=worker_declaration_source,
        worker_declaration_invalid=worker_declaration_invalid,
        declaration_stage=declaration_stage,
        intent_plan_agreement=observation.intent_plan_agreement,
        intent_observed_diagnostic=intent_observed.as_dict(),
        observation={
            "reached_post_run_boundary": True,
            "declared_change_paths": [
                item.path for item in declared_changes
            ][:MAX_REPORTED_PATHS],
            "observed_change_paths": list(
                change_set.changed_paths[:MAX_REPORTED_PATHS]
            ),
            "observed_change_set_empty": change_set.is_empty,
            "observed_change_identity_incomplete": (
                change_set.observation_incomplete
            ),
            "untyped_observed_paths": list(
                change_set.untyped_paths[:MAX_REPORTED_PATHS]
            ),
            "validation_window_paths": list(
                validation_window[:MAX_REPORTED_PATHS]
            ),
            "validation_expectation_unavailable_reason": (
                expectation_unavailable or None
            ),
            "validation_receipt_result": (
                receipt.result if receipt is not None else None
            ),
            "validated_state_is_final_state": validated_state == final_state,
            "observed_path_count": len(after_digests.digests),
            "repository_traversal_performed": False,
        },
        reconciliation=_reconciliation_projection(result),
    )


def safe_run_shadow_post_run_reconciliation(
    observation: LiveExecutionObservation,
) -> ShadowPostRunCheckReceipt:
    """Run the shadow check, converting any failure into a bounded record.

    A shadow checker failure must never hide or replace an authoritative
    application failure, validation failure or worker failure, so nothing
    propagates out of here.
    """
    try:
        return run_shadow_post_run_reconciliation(observation)
    except LiveAuthorityWideningError:
        category = ERROR_AUTHORITY_WIDENING_REFUSED
    except LiveObservationBoundError:
        category = ERROR_PRODUCER_BOUND
    except (
        LiveAuthorityInputError,
        LiveValidationInputError,
        LiveWorkerReportInputError,
    ):
        category = ERROR_PRODUCER_INPUT
    except (TypeError, ValueError):
        category = ERROR_RECONCILIATION_CONTRACT
    except Exception:  # noqa: BLE001 - a shadow failure is isolated by design
        category = ERROR_UNEXPECTED

    run_status = getattr(observation, "authoritative_run_status", "")
    return ShadowPostRunCheckReceipt(
        execution_run_id=str(getattr(observation, "execution_run_id", "") or ""),
        repository_id="",
        authoritative_run_status=(
            run_status if run_status in AUTHORITATIVE_RUN_STATUSES
            else RUN_STATUS_NOT_REACHED
        ),
        shadow_outcome=SHADOW_CHECKER_ERROR,
        producer_completeness=COMPLETENESS_UNAVAILABLE,
        missing_live_facts=_ordered_missing(
            {
                MISSING_EXECUTION_AUTHORIZATION,
                MISSING_WORKER_REPORT,
                MISSING_OBSERVED_CHANGE_IDENTITY,
                MISSING_FINAL_STATE_BINDING,
            }
        ),
        disagreement=DISAGREEMENT_NOT_COMPARABLE,
        shadow_error_category=category,
        observation={"reached_post_run_boundary": True},
    )


# ── Persistence ───────────────────────────────────────────────────────────────

def persist_shadow_post_run_check(
    bundle: Any,
    receipt: ShadowPostRunCheckReceipt,
) -> str:
    """Attach the receipt to the existing run artifact bundle.

    No second run-history store is created: the receipt is one additive JSON
    artifact inside the replay bundle the run already produced, bound to that
    run's identity.  Returns a bounded error category, or ``""`` on success.
    """
    if bundle is None:
        return ERROR_ARTIFACT_PERSISTENCE
    try:
        from core.replay_recorder import write_replay_json

        write_replay_json(bundle, SHADOW_ARTIFACT_NAME, receipt.as_dict())
    except Exception:  # noqa: BLE001 - persistence failure is isolated
        return ERROR_ARTIFACT_PERSISTENCE
    return ""


def load_shadow_post_run_check(replay_dir: str | Path) -> dict[str, Any]:
    """Read a persisted shadow receipt, tolerating runs that predate it.

    A legacy bundle is not corrupt; it simply has no reconciliation.  The loader
    says so instead of failing.
    """
    path = Path(replay_dir) / SHADOW_ARTIFACT_NAME
    unavailable = {
        "reconciliation_available": False,
        "reconciliation_status": None,
        "producer_completeness": COMPLETENESS_UNAVAILABLE,
        "authoritative_effect": False,
        "worker_declaration_source": None,
        "worker_declaration_invalid": False,
        "declaration_stage": None,
        "channel_provenance": "unavailable",
        "intent_fidelity_measurable": False,
        "self_report_fidelity_measurable": False,
        "same_model_channel_is_independent_evidence": False,
        "intent_plan_agreement": INTENT_PLAN_UNAVAILABLE,
        "intent_observed_relation": INTENT_OBSERVED_UNAVAILABLE,
        "intent_observed_diagnostic": {},
        "independent_worker_declaration_missing": True,
        "legacy_run": True,
    }
    try:
        if not path.is_file():
            return unavailable
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return unavailable
    if not isinstance(payload, dict):
        return unavailable
    payload.setdefault("legacy_run", False)
    payload.setdefault("worker_declaration_source", None)
    payload.setdefault("worker_declaration_invalid", False)
    payload.setdefault("declaration_stage", None)
    source = payload.get("worker_declaration_source")
    payload.setdefault(
        "channel_provenance",
        "independently_declared_channel"
        if source in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        }
        else "unavailable",
    )
    payload.setdefault(
        "intent_fidelity_measurable",
        source in {
            DECLARATION_SOURCE_PRE_EXECUTION_WORKER_INTENT,
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        },
    )
    payload.setdefault(
        "self_report_fidelity_measurable",
        source in {
            DECLARATION_SOURCE_POST_EXECUTION_WORKER_DECLARATION,
            DECLARATION_SOURCE_INDEPENDENT,
        },
    )
    payload["same_model_channel_is_independent_evidence"] = False
    payload.setdefault("intent_plan_agreement", INTENT_PLAN_UNAVAILABLE)
    payload.setdefault("intent_observed_relation", INTENT_OBSERVED_UNAVAILABLE)
    payload.setdefault("intent_observed_diagnostic", {})
    payload.setdefault(
        "independent_worker_declaration_missing",
        payload.get("worker_declaration_source") != DECLARATION_SOURCE_INDEPENDENT,
    )
    payload["authoritative_effect"] = False
    return payload


def summarize_shadow_post_run_checks(
    replay_dirs: Sequence[str | Path],
) -> dict[str, Any]:
    """Offline dogfood view over already-persisted shadow receipts.

    This exists to make one question answerable: *across real runs, how often
    would CHECK.1 have disagreed with the current executor?*  It is a read-only
    aggregation of artifacts that already exist, it runs no execution of any
    kind, and the counts it returns are operational measurements — they decide
    nothing about whether any individual run was correct.
    """
    runs = 0
    legacy = 0
    by_run_status: dict[str, int] = {}
    by_reconciliation_status: dict[str, int] = {}
    by_shadow_outcome: dict[str, int] = {}
    by_completeness: dict[str, int] = {}
    by_disagreement: dict[str, int] = {}
    by_missing_fact: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    by_worker_declaration_source: dict[str, int] = {}
    by_declaration_stage: dict[str, int] = {}
    by_intent_plan_agreement: dict[str, int] = {}
    by_intent_observed_relation: dict[str, int] = {}
    worker_declaration_invalid_runs = 0

    def _tally(bucket: dict[str, int], key: object) -> None:
        if isinstance(key, str) and key:
            bucket[key] = bucket.get(key, 0) + 1

    for replay_dir in replay_dirs:
        payload = load_shadow_post_run_check(replay_dir)
        if payload.get("legacy_run"):
            legacy += 1
            continue
        runs += 1
        _tally(by_run_status, payload.get("authoritative_run_status"))
        _tally(by_reconciliation_status, payload.get("reconciliation_status"))
        _tally(by_shadow_outcome, payload.get("shadow_outcome"))
        _tally(by_completeness, payload.get("producer_completeness"))
        _tally(by_disagreement, payload.get("disagreement"))
        _tally(
            by_worker_declaration_source,
            payload.get("worker_declaration_source"),
        )
        _tally(by_declaration_stage, payload.get("declaration_stage"))
        _tally(by_intent_plan_agreement, payload.get("intent_plan_agreement"))
        _tally(
            by_intent_observed_relation,
            payload.get("intent_observed_relation"),
        )
        if payload.get("worker_declaration_invalid") is True:
            worker_declaration_invalid_runs += 1
        for code in payload.get("missing_live_facts") or []:
            _tally(by_missing_fact, code)
        for code in payload.get("disagreement_reasons") or []:
            _tally(by_reason, code)

    return {
        "phase_id": PHASE_ID,
        "report_kind": "shadow_post_run_dogfood_summary",
        "runs_with_receipt": runs,
        "legacy_runs_without_receipt": legacy,
        "authoritative_run_status_counts": dict(sorted(by_run_status.items())),
        "reconciliation_status_counts": dict(
            sorted(by_reconciliation_status.items())
        ),
        "shadow_outcome_counts": dict(sorted(by_shadow_outcome.items())),
        "producer_completeness_counts": dict(sorted(by_completeness.items())),
        "disagreement_counts": dict(sorted(by_disagreement.items())),
        "missing_live_fact_counts": dict(sorted(by_missing_fact.items())),
        "disagreement_reason_counts": dict(sorted(by_reason.items())),
        "worker_declaration_source_counts": dict(
            sorted(by_worker_declaration_source.items())
        ),
        "declaration_stage_counts": dict(sorted(by_declaration_stage.items())),
        "intent_plan_agreement_counts": dict(
            sorted(by_intent_plan_agreement.items())
        ),
        "intent_observed_relation_counts": dict(
            sorted(by_intent_observed_relation.items())
        ),
        "worker_declaration_invalid_runs": worker_declaration_invalid_runs,
        "authoritative_effect": False,
        "counts_decide_nothing": True,
        "notice": SHADOW_NOTICE,
    }


def _ordered_missing(codes: set[str]) -> tuple[str, ...]:
    return tuple(code for code in MISSING_LIVE_FACTS if code in codes)


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "PHASE_ID",
    "RECEIPT_KIND",
    "RECEIPT_SCHEMA_VERSION",
    "ENVIRONMENT_FLAG",
    "SHADOW_ARTIFACT_NAME",
    "RESULT_METADATA_KEYS",
    "RESULT_AVAILABLE_KEY",
    "RESULT_STATUS_KEY",
    "RESULT_COMPLETENESS_KEY",
    "RESULT_AUTHORITATIVE_EFFECT_KEY",
    "AUTHORITATIVE_RUN_STATUSES",
    "RUN_STATUS_SUCCESS",
    "RUN_STATUS_FAILED",
    "RUN_STATUS_BLOCKED",
    "RUN_STATUS_NOT_REACHED",
    "SHADOW_OUTCOMES",
    "SHADOW_DISABLED",
    "SHADOW_EVALUATED",
    "SHADOW_NOT_REACHED",
    "SHADOW_PRODUCER_UNAVAILABLE",
    "SHADOW_CHECKER_ERROR",
    "PRODUCER_COMPLETENESS",
    "COMPLETENESS_COMPLETE",
    "COMPLETENESS_PARTIAL",
    "COMPLETENESS_UNAVAILABLE",
    "MISSING_LIVE_FACTS",
    "SHADOW_ERROR_CATEGORIES",
    "NOT_REACHED_BOUNDARY",
    "DISAGREEMENT_KINDS",
    "DISAGREEMENT_NONE",
    "DISAGREEMENT_CHECKER_STRICTER",
    "DISAGREEMENT_CHECKER_WEAKER",
    "DISAGREEMENT_NOT_COMPARABLE",
    "SHADOW_NOTICE",
    "LiveExecutionObservation",
    "ShadowPostRunCheckReceipt",
    "is_post_run_reconciliation_shadow_enabled",
    "plan_target_paths",
    "live_task_shape_fingerprint",
    "side_effect_paths",
    "observe_final_change_set",
    "not_reached_receipt",
    "run_shadow_post_run_reconciliation",
    "safe_run_shadow_post_run_reconciliation",
    "persist_shadow_post_run_check",
    "load_shadow_post_run_check",
    "summarize_shadow_post_run_checks",
    "shadow_disagreement",
    "shadow_guardrails",
    "check_2_handoff_readiness",
]
