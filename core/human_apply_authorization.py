"""EXEC.APPROVAL.LIVE.1 — exact-candidate human Apply authorization.

This module joins an explicit human Apply action to the immutable review state
that was shown to that human.  It is deliberately a pre-execution boundary:
it reads only the bounded paths named by the review receipt, reuses the
existing repository identity and path-digest primitives, consumes the existing
patch-safety verdict, and returns a typed authorization decision before any
executor is entered.

Eligibility, approval, authorization, execution and persistence remain
separate facts.  In particular, bounded evidence eligibility is never treated
as approval, and approval is denied authority when any candidate, receipt,
repository, source-state or patch-safety binding is stale.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from core.candidate_sandbox_validation import (
    candidate_plan_from_payload,
    patch_plan_fingerprint,
)
from core.execution_eligibility_policy import (
    ELIGIBLE,
    INCONSISTENT_INPUT,
    INELIGIBLE,
    INSUFFICIENT_EVIDENCE,
    LEGACY_UNASSESSED,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    execution_eligibility_status_of_payload,
)
from core.execution_outcome_telemetry import (
    AUTHORITY_SOURCE_MANUAL_APPLY,
    AUTHORITY_SOURCE_NONE,
)
from core.live_change_observation import LivePathDigests, digest_known_paths
from core.repository_identity import derive_repository_id


PHASE_ID = "EXEC.APPROVAL.LIVE.1"
REVIEW_SCHEMA_VERSION = "exec_approval_live_1_review_v1"
AUTHORIZATION_SCHEMA_VERSION = "exec_approval_live_1_authorization_v1"

PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW = "explicit_change_manual_review"
MANUAL_REVIEW_PROFILES: tuple[str, ...] = (
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
)

HUMAN_ACTION_APPLY = "apply"
HUMAN_ACTION_REVIEW_AND_APPLY = "review_and_apply"
HUMAN_ACTION_CLI_CONFIRMATION = "cli_confirmation"
HUMAN_ACTION_KINDS: tuple[str, ...] = (
    HUMAN_ACTION_APPLY,
    HUMAN_ACTION_REVIEW_AND_APPLY,
    HUMAN_ACTION_CLI_CONFIRMATION,
)

FRESHNESS_CURRENT = "current"
FRESHNESS_STALE = "stale"
FRESHNESS_INCOMPLETE = "incomplete"
FRESHNESS_STATUSES: tuple[str, ...] = (
    FRESHNESS_CURRENT,
    FRESHNESS_STALE,
    FRESHNESS_INCOMPLETE,
)

AUTHORIZATION_NOT_REQUESTED = "not_requested"
AUTHORIZATION_AUTHORIZED = "authorized"
AUTHORIZATION_DENIED = "denied"
AUTHORIZATION_STATUSES: tuple[str, ...] = (
    AUTHORIZATION_NOT_REQUESTED,
    AUTHORIZATION_AUTHORIZED,
    AUTHORIZATION_DENIED,
)

DENIAL_NONE = ""
DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE = "not_human_review_eligible"
DENIAL_APPROVAL_MISSING = "approval_missing"
DENIAL_CANDIDATE_MISMATCH = "candidate_mismatch"
DENIAL_ELIGIBILITY_RECEIPT_STALE = "eligibility_receipt_stale"
DENIAL_SOURCE_STATE_STALE = "source_state_stale"
DENIAL_PATCH_SAFETY_MISMATCH = "patch_safety_mismatch"
DENIAL_REPOSITORY_IDENTITY_MISMATCH = "repository_identity_mismatch"
DENIAL_POLICY_PROFILE_MISMATCH = "policy_profile_mismatch"
DENIAL_INCONSISTENT_INPUT = "inconsistent_input"
DENIAL_REASONS: tuple[str, ...] = (
    DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE,
    DENIAL_APPROVAL_MISSING,
    DENIAL_CANDIDATE_MISMATCH,
    DENIAL_ELIGIBILITY_RECEIPT_STALE,
    DENIAL_SOURCE_STATE_STALE,
    DENIAL_PATCH_SAFETY_MISMATCH,
    DENIAL_REPOSITORY_IDENTITY_MISMATCH,
    DENIAL_POLICY_PROFILE_MISMATCH,
    DENIAL_INCONSISTENT_INPUT,
)

_ELIGIBILITY_FAILURE_STATUSES = frozenset(
    {INELIGIBLE, INSUFFICIENT_EVIDENCE, INCONSISTENT_INPUT}
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _normalized_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _candidate_paths(plan: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                path
                for path in (
                    _normalized_path(op.get("relative_path") or op.get("file"))
                    for op in plan
                )
                if path
            }
        )
    )


def _review_source_paths(
    payload: Mapping[str, Any],
    plan: Sequence[Mapping[str, Any]],
    additional_paths: Sequence[str],
) -> tuple[str, ...]:
    paths = set(_candidate_paths(plan))
    paths.update(
        path for path in (_normalized_path(item) for item in additional_paths) if path
    )
    for assessment in payload.get("check_oracle_assessments") or ():
        if isinstance(assessment, Mapping):
            path = _normalized_path(assessment.get("check_path"))
            if path:
                paths.add(path)
    return tuple(sorted(paths))


def eligibility_assessment_fingerprint(assessment: Any) -> str:
    """Recompute the immutable EXEC.POLICY assessment identity."""
    if not isinstance(assessment, Mapping):
        return ""
    material = {
        str(key): value
        for key, value in assessment.items()
        if str(key) != "assessment_fingerprint"
    }
    return _fingerprint(material)


def patch_safety_binding_fingerprint(
    *,
    candidate_fingerprint: str,
    repository_identity: str,
    target_paths: Sequence[str],
    patch_safety_verdict: Mapping[str, Any],
) -> str:
    """Bind the existing safety verdict to one candidate/repository/path set."""
    blocked: list[dict[str, str]] = []
    for item in patch_safety_verdict.get("blocked_paths") or ():
        if not isinstance(item, Mapping):
            continue
        blocked.append(
            {
                "path": _normalized_path(item.get("path")),
                "category": str(item.get("category") or ""),
            }
        )
    return _fingerprint(
        {
            "kind": "exec_approval_live_1_patch_safety_binding_v1",
            "candidate_fingerprint": candidate_fingerprint,
            "repository_identity": repository_identity,
            "target_paths": sorted({_normalized_path(path) for path in target_paths}),
            "ok": patch_safety_verdict.get("ok") is True,
            "blocked_paths": sorted(
                blocked, key=lambda item: (item["path"], item["category"])
            ),
        }
    )


def source_state_fingerprint(
    *, repository_identity: str, source_state: LivePathDigests
) -> str:
    return _fingerprint(
        {
            "kind": "exec_approval_live_1_known_source_state_v1",
            "repository_identity": repository_identity,
            "source_state": source_state.as_dict(),
        }
    )


@dataclass(frozen=True, slots=True)
class HumanApplyReviewReceipt:
    """The exact candidate/evidence/source state presented for review."""

    candidate_fingerprint: str
    eligibility_receipt_fingerprint: str
    policy_profile: str
    repository_identity: str
    source_state: LivePathDigests
    source_state_fingerprint: str
    patch_safety_binding: str
    probe_fingerprint: str = ""
    targeted_validation_fingerprint: str = ""
    schema_version: str = REVIEW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _is_sha256(self.candidate_fingerprint):
            raise ValueError("candidate_fingerprint must be a SHA-256 digest")
        if self.policy_profile not in MANUAL_REVIEW_PROFILES:
            raise ValueError(f"unsupported manual review profile: {self.policy_profile!r}")
        if not self.repository_identity:
            raise ValueError("repository_identity must be non-empty")
        if not _is_sha256(self.source_state_fingerprint):
            raise ValueError("source_state_fingerprint must be a SHA-256 digest")
        if not _is_sha256(self.patch_safety_binding):
            raise ValueError("patch_safety_binding must be a SHA-256 digest")
        if self.policy_profile == PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW:
            if not _is_sha256(self.eligibility_receipt_fingerprint):
                raise ValueError(
                    "bounded review requires an eligibility receipt fingerprint"
                )

    @property
    def freshness_established(self) -> bool:
        return not (
            self.source_state.unreadable_paths or self.source_state.oversized_paths
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "candidate_fingerprint": self.candidate_fingerprint,
            "eligibility_receipt_fingerprint": self.eligibility_receipt_fingerprint,
            "policy_profile": self.policy_profile,
            "repository_identity": self.repository_identity,
            "source_state": self.source_state.as_dict(),
            "source_state_fingerprint": self.source_state_fingerprint,
            "patch_safety_binding": self.patch_safety_binding,
            "probe_fingerprint": self.probe_fingerprint,
            "targeted_validation_fingerprint": (
                self.targeted_validation_fingerprint
            ),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.identity_payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "review_receipt_fingerprint": self.fingerprint}

    def as_payload_fields(self) -> dict[str, Any]:
        return {
            "human_apply_review": self.as_dict(),
            "human_apply_review_receipt_fingerprint": self.fingerprint,
            "human_approval_received": False,
            "approved_candidate_fingerprint": "",
            "human_apply_authorization_status": AUTHORIZATION_NOT_REQUESTED,
        }


def _parse_source_state(value: Any) -> LivePathDigests:
    block = _mapping(value)
    digests: list[tuple[str, str | None]] = []
    for item in block.get("digests") or ():
        if not isinstance(item, Mapping):
            raise ValueError("source-state digest entries must be mappings")
        path = _normalized_path(item.get("path"))
        digest = item.get("sha256")
        if not path or (digest is not None and not _is_sha256(digest)):
            raise ValueError("source-state digest entry is invalid")
        digests.append((path, digest))
    return LivePathDigests(
        digests=tuple(digests),
        unreadable_paths=tuple(
            _normalized_path(path) for path in block.get("unreadable_paths") or ()
        ),
        oversized_paths=tuple(
            _normalized_path(path) for path in block.get("oversized_paths") or ()
        ),
    )


def parse_human_apply_review_receipt(value: Any) -> HumanApplyReviewReceipt:
    block = _mapping(value)
    receipt = HumanApplyReviewReceipt(
        candidate_fingerprint=str(block.get("candidate_fingerprint") or ""),
        eligibility_receipt_fingerprint=str(
            block.get("eligibility_receipt_fingerprint") or ""
        ),
        policy_profile=str(block.get("policy_profile") or ""),
        repository_identity=str(block.get("repository_identity") or ""),
        source_state=_parse_source_state(block.get("source_state")),
        source_state_fingerprint=str(block.get("source_state_fingerprint") or ""),
        patch_safety_binding=str(block.get("patch_safety_binding") or ""),
        probe_fingerprint=str(block.get("probe_fingerprint") or ""),
        targeted_validation_fingerprint=str(
            block.get("targeted_validation_fingerprint") or ""
        ),
        schema_version=str(block.get("schema_version") or ""),
    )
    if receipt.schema_version != REVIEW_SCHEMA_VERSION:
        raise ValueError("unsupported human Apply review receipt schema")
    if str(block.get("review_receipt_fingerprint") or "") != receipt.fingerprint:
        raise ValueError("human Apply review receipt fingerprint mismatch")
    if (
        source_state_fingerprint(
            repository_identity=receipt.repository_identity,
            source_state=receipt.source_state,
        )
        != receipt.source_state_fingerprint
    ):
        raise ValueError("human Apply review source-state fingerprint mismatch")
    return receipt


def build_human_apply_review_receipt(
    *,
    payload: Mapping[str, Any],
    repo_path: str | Path,
    patch_safety_verdict: Mapping[str, Any],
    policy_profile: str,
    additional_source_paths: Sequence[str] = (),
) -> HumanApplyReviewReceipt:
    """Freeze one candidate immediately before it is presented to a human."""
    plan = candidate_plan_from_payload(payload)
    candidate = patch_plan_fingerprint(plan)
    repository_identity = derive_repository_id(repo_path)
    paths = _review_source_paths(payload, plan, additional_source_paths)
    source_state = digest_known_paths(repo_path, list(paths))

    eligibility_receipt = ""
    probe = ""
    targeted = ""
    if policy_profile == PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW:
        profiles = _mapping(payload.get("execution_eligibility_profiles"))
        assessment = _mapping(profiles.get(policy_profile))
        recorded = str(assessment.get("assessment_fingerprint") or "")
        if (
            assessment.get("eligibility_status") != ELIGIBLE
            or recorded != eligibility_assessment_fingerprint(assessment)
            or str(assessment.get("candidate_fingerprint") or "") != candidate
        ):
            raise ValueError("bounded review requires one current eligible assessment")
        eligibility_receipt = recorded
        probe = str(assessment.get("probe_fingerprint") or "")
        targeted = str(assessment.get("targeted_validation_fingerprint") or "")

    source_fingerprint = source_state_fingerprint(
        repository_identity=repository_identity, source_state=source_state
    )
    return HumanApplyReviewReceipt(
        candidate_fingerprint=candidate,
        eligibility_receipt_fingerprint=eligibility_receipt,
        policy_profile=policy_profile,
        repository_identity=repository_identity,
        source_state=source_state,
        source_state_fingerprint=source_fingerprint,
        patch_safety_binding=patch_safety_binding_fingerprint(
            candidate_fingerprint=candidate,
            repository_identity=repository_identity,
            target_paths=paths,
            patch_safety_verdict=patch_safety_verdict,
        ),
        probe_fingerprint=probe,
        targeted_validation_fingerprint=targeted,
    )


@dataclass(frozen=True, slots=True)
class HumanApplyAuthorization:
    """Pre-mutation result of one explicit, exact-candidate Apply action."""

    candidate_fingerprint: str
    approved_candidate_fingerprint: str
    eligibility_receipt_fingerprint: str
    approved_eligibility_receipt_fingerprint: str
    policy_profile: str
    human_action_kind: str
    human_approval_received: bool
    freshness_status: str
    patch_safety_binding: str
    source_state_fingerprint: str
    repository_identity: str
    authorization_status: str
    denial_reason: str
    authority_source: str
    review_receipt_fingerprint: str = ""
    timings: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    legacy_compatibility: bool = False
    schema_version: str = AUTHORIZATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.freshness_status not in FRESHNESS_STATUSES:
            raise ValueError(f"unsupported freshness status: {self.freshness_status!r}")
        if self.authorization_status not in AUTHORIZATION_STATUSES:
            raise ValueError(
                f"unsupported authorization status: {self.authorization_status!r}"
            )
        if self.authorization_status == AUTHORIZATION_AUTHORIZED:
            if not self.human_approval_received:
                raise ValueError("authorization requires explicit human approval")
            if self.denial_reason:
                raise ValueError("authorized receipt carries no denial reason")
            if self.authority_source != AUTHORITY_SOURCE_MANUAL_APPLY:
                raise ValueError("manual Apply authorization must reuse its authority source")
            if self.freshness_status != FRESHNESS_CURRENT:
                raise ValueError("stale or incomplete review state cannot authorize")
        elif self.authorization_status == AUTHORIZATION_DENIED:
            if self.denial_reason not in DENIAL_REASONS:
                raise ValueError("denied authorization requires a closed denial reason")
            if self.authority_source != AUTHORITY_SOURCE_NONE:
                raise ValueError("denied authorization has no authority source")
        else:
            if self.human_approval_received or self.denial_reason:
                raise ValueError("not-requested authorization carries no action or denial")
            if self.authority_source != AUTHORITY_SOURCE_NONE:
                raise ValueError("not-requested authorization has no authority source")

    @property
    def authorized(self) -> bool:
        return self.authorization_status == AUTHORIZATION_AUTHORIZED

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "candidate_fingerprint": self.candidate_fingerprint,
            "approved_candidate_fingerprint": self.approved_candidate_fingerprint,
            "eligibility_receipt_fingerprint": self.eligibility_receipt_fingerprint,
            "approved_eligibility_receipt_fingerprint": (
                self.approved_eligibility_receipt_fingerprint
            ),
            "policy_profile": self.policy_profile,
            "human_action_kind": self.human_action_kind,
            "human_approval_received": self.human_approval_received,
            "freshness_status": self.freshness_status,
            "patch_safety_binding": self.patch_safety_binding,
            "source_state_fingerprint": self.source_state_fingerprint,
            "repository_identity": self.repository_identity,
            "authorization_status": self.authorization_status,
            "denial_reason": self.denial_reason,
            "authority_source": self.authority_source,
            "review_receipt_fingerprint": self.review_receipt_fingerprint,
            "timings": {key: value for key, value in self.timings},
            "legacy_compatibility": self.legacy_compatibility,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.identity_payload())

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "authorization_receipt_fingerprint": self.fingerprint,
        }

    def as_payload_fields(self) -> dict[str, Any]:
        return {
            "human_approval_received": self.human_approval_received,
            "approved_candidate_fingerprint": self.approved_candidate_fingerprint,
            "approved_eligibility_receipt_fingerprint": (
                self.approved_eligibility_receipt_fingerprint
            ),
            "human_apply_authorization_status": self.authorization_status,
            "human_apply_authorization_denial_reason": self.denial_reason,
            "human_apply_authorization": self.as_dict(),
            "human_apply_authorization_fingerprint": self.fingerprint,
        }


def _decision(
    *,
    candidate: str,
    approved_candidate: str,
    eligibility_receipt: str,
    approved_eligibility_receipt: str,
    policy_profile: str,
    human_action_kind: str,
    approval_received: bool,
    freshness: str,
    patch_safety_binding: str,
    source_fingerprint: str,
    repository_identity: str,
    denial_reason: str = "",
    review_receipt_fingerprint: str = "",
    started: float,
    freshness_seconds: float,
    legacy_compatibility: bool = False,
) -> HumanApplyAuthorization:
    authorized = not denial_reason
    return HumanApplyAuthorization(
        candidate_fingerprint=candidate,
        approved_candidate_fingerprint=approved_candidate,
        eligibility_receipt_fingerprint=eligibility_receipt,
        approved_eligibility_receipt_fingerprint=approved_eligibility_receipt,
        policy_profile=policy_profile,
        human_action_kind=human_action_kind,
        human_approval_received=approval_received,
        freshness_status=freshness,
        patch_safety_binding=patch_safety_binding,
        source_state_fingerprint=source_fingerprint,
        repository_identity=repository_identity,
        authorization_status=(
            AUTHORIZATION_AUTHORIZED if authorized else AUTHORIZATION_DENIED
        ),
        denial_reason=denial_reason,
        authority_source=(
            AUTHORITY_SOURCE_MANUAL_APPLY if authorized else AUTHORITY_SOURCE_NONE
        ),
        review_receipt_fingerprint=review_receipt_fingerprint,
        timings=(
            ("freshness_revalidation_seconds", round(freshness_seconds, 6)),
            ("authorization_total_seconds", round(time.perf_counter() - started, 6)),
        ),
        legacy_compatibility=legacy_compatibility,
    )


def authorize_human_apply(
    *,
    payload: Mapping[str, Any],
    repo_path: str | Path,
    patch_safety_verdict: Mapping[str, Any],
    human_action_kind: str,
    approved_candidate_fingerprint: str,
    approved_eligibility_receipt_fingerprint: str = "",
    allow_legacy_explicit_change: bool = False,
) -> HumanApplyAuthorization:
    """Revalidate one explicit Apply request and decide authority.

    ``patch_safety_verdict`` must be the existing gate's Apply-time result.
    This function does not run validation, probing, retrieval, models, network
    calls or repository traversal.
    """
    started = time.perf_counter()
    plan = candidate_plan_from_payload(payload)
    candidate = patch_plan_fingerprint(plan)
    approved_candidate = str(approved_candidate_fingerprint or "")
    approved_eligibility = str(approved_eligibility_receipt_fingerprint or "")
    action = str(human_action_kind or "")
    approval_received = action in HUMAN_ACTION_KINDS
    repository_identity = ""
    try:
        repository_identity = derive_repository_id(repo_path)
    except (OSError, ValueError):
        pass

    def deny(
        reason: str,
        *,
        profile: str = PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
        eligibility: str = "",
        freshness: str = FRESHNESS_INCOMPLETE,
        safety_binding: str = "",
        source_fingerprint: str = "",
        review_fingerprint: str = "",
    ) -> HumanApplyAuthorization:
        return _decision(
            candidate=candidate,
            approved_candidate=approved_candidate,
            eligibility_receipt=eligibility,
            approved_eligibility_receipt=approved_eligibility,
            policy_profile=profile,
            human_action_kind=action,
            approval_received=approval_received,
            freshness=freshness,
            patch_safety_binding=safety_binding,
            source_fingerprint=source_fingerprint,
            repository_identity=repository_identity,
            denial_reason=reason,
            review_receipt_fingerprint=review_fingerprint,
            started=started,
            freshness_seconds=0.0,
        )

    if not approval_received:
        return deny(DENIAL_APPROVAL_MISSING)
    if not plan or not _is_sha256(candidate):
        return deny(DENIAL_INCONSISTENT_INPUT)
    if not _is_sha256(approved_candidate) or approved_candidate != candidate:
        return deny(DENIAL_CANDIDATE_MISMATCH)

    current_status = execution_eligibility_status_of_payload(payload)
    if current_status in _ELIGIBILITY_FAILURE_STATUSES:
        return deny(DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE)

    raw_review = payload.get("human_apply_review")
    if not isinstance(raw_review, Mapping):
        if (
            allow_legacy_explicit_change
            and str(payload.get("patch_basis") or "") != "grounded_defect"
        ):
            targets = _candidate_paths(plan)
            safety_binding = patch_safety_binding_fingerprint(
                candidate_fingerprint=candidate,
                repository_identity=repository_identity,
                target_paths=targets,
                patch_safety_verdict=patch_safety_verdict,
            )
            if patch_safety_verdict.get("ok") is not True:
                return deny(
                    DENIAL_PATCH_SAFETY_MISMATCH,
                    profile=PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
                    freshness=FRESHNESS_CURRENT,
                    safety_binding=safety_binding,
                )
            return _decision(
                candidate=candidate,
                approved_candidate=approved_candidate,
                eligibility_receipt="",
                approved_eligibility_receipt="",
                policy_profile=PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
                human_action_kind=action,
                approval_received=True,
                freshness=FRESHNESS_CURRENT,
                patch_safety_binding=safety_binding,
                source_fingerprint="",
                repository_identity=repository_identity,
                started=started,
                freshness_seconds=0.0,
                legacy_compatibility=True,
            )
        return deny(
            DENIAL_ELIGIBILITY_RECEIPT_STALE
            if current_status == LEGACY_UNASSESSED
            else DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE
        )

    try:
        review = parse_human_apply_review_receipt(raw_review)
    except (TypeError, ValueError):
        return deny(DENIAL_INCONSISTENT_INPUT)

    common = {
        "profile": review.policy_profile,
        "eligibility": review.eligibility_receipt_fingerprint,
        "safety_binding": review.patch_safety_binding,
        "source_fingerprint": review.source_state_fingerprint,
        "review_fingerprint": review.fingerprint,
    }
    if review.candidate_fingerprint != candidate:
        return deny(DENIAL_CANDIDATE_MISMATCH, **common)
    if repository_identity != review.repository_identity:
        return deny(DENIAL_REPOSITORY_IDENTITY_MISMATCH, **common)

    if review.policy_profile == PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW:
        if current_status != ELIGIBLE or payload.get("human_review_eligible") is not True:
            return deny(DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE, **common)
        profiles = _mapping(payload.get("execution_eligibility_profiles"))
        assessment = _mapping(profiles.get(review.policy_profile))
        recorded = str(assessment.get("assessment_fingerprint") or "")
        if (
            recorded != review.eligibility_receipt_fingerprint
            or recorded != approved_eligibility
            or recorded != eligibility_assessment_fingerprint(assessment)
            or str(assessment.get("candidate_fingerprint") or "") != candidate
            or str(assessment.get("probe_fingerprint") or "")
            != review.probe_fingerprint
            or str(assessment.get("targeted_validation_fingerprint") or "")
            != review.targeted_validation_fingerprint
        ):
            return deny(DENIAL_ELIGIBILITY_RECEIPT_STALE, **common)
        if str(assessment.get("patch_safety_binding") or "") != candidate:
            return deny(DENIAL_PATCH_SAFETY_MISMATCH, **common)
    elif review.policy_profile == PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW:
        if str(payload.get("patch_basis") or "") != "explicit_change_request":
            return deny(DENIAL_POLICY_PROFILE_MISMATCH, **common)
    else:  # pragma: no cover - parser rejects this first
        return deny(DENIAL_POLICY_PROFILE_MISMATCH, **common)

    paths = review.source_state.observed_paths
    current_safety_binding = patch_safety_binding_fingerprint(
        candidate_fingerprint=candidate,
        repository_identity=repository_identity,
        target_paths=paths,
        patch_safety_verdict=patch_safety_verdict,
    )
    if (
        patch_safety_verdict.get("ok") is not True
        or current_safety_binding != review.patch_safety_binding
    ):
        return deny(
            DENIAL_PATCH_SAFETY_MISMATCH,
            **{**common, "safety_binding": current_safety_binding},
        )

    freshness_started = time.perf_counter()
    current_source = digest_known_paths(repo_path, list(paths))
    freshness_seconds = time.perf_counter() - freshness_started
    current_source_fingerprint = source_state_fingerprint(
        repository_identity=repository_identity, source_state=current_source
    )
    if (
        not review.freshness_established
        or current_source.unreadable_paths
        or current_source.oversized_paths
    ):
        return _decision(
            candidate=candidate,
            approved_candidate=approved_candidate,
            eligibility_receipt=review.eligibility_receipt_fingerprint,
            approved_eligibility_receipt=approved_eligibility,
            policy_profile=review.policy_profile,
            human_action_kind=action,
            approval_received=True,
            freshness=FRESHNESS_INCOMPLETE,
            patch_safety_binding=current_safety_binding,
            source_fingerprint=current_source_fingerprint,
            repository_identity=repository_identity,
            denial_reason=DENIAL_SOURCE_STATE_STALE,
            review_receipt_fingerprint=review.fingerprint,
            started=started,
            freshness_seconds=freshness_seconds,
        )
    if current_source_fingerprint != review.source_state_fingerprint:
        return _decision(
            candidate=candidate,
            approved_candidate=approved_candidate,
            eligibility_receipt=review.eligibility_receipt_fingerprint,
            approved_eligibility_receipt=approved_eligibility,
            policy_profile=review.policy_profile,
            human_action_kind=action,
            approval_received=True,
            freshness=FRESHNESS_STALE,
            patch_safety_binding=current_safety_binding,
            source_fingerprint=current_source_fingerprint,
            repository_identity=repository_identity,
            denial_reason=DENIAL_SOURCE_STATE_STALE,
            review_receipt_fingerprint=review.fingerprint,
            started=started,
            freshness_seconds=freshness_seconds,
        )

    return _decision(
        candidate=candidate,
        approved_candidate=approved_candidate,
        eligibility_receipt=review.eligibility_receipt_fingerprint,
        approved_eligibility_receipt=approved_eligibility,
        policy_profile=review.policy_profile,
        human_action_kind=action,
        approval_received=True,
        freshness=FRESHNESS_CURRENT,
        patch_safety_binding=current_safety_binding,
        source_fingerprint=current_source_fingerprint,
        repository_identity=repository_identity,
        review_receipt_fingerprint=review.fingerprint,
        started=started,
        freshness_seconds=freshness_seconds,
    )


def describe_human_apply_authorization(
    authorization: HumanApplyAuthorization,
) -> str:
    if authorization.authorized:
        return (
            "You approved this exact candidate. It was authorized under the "
            "manual Apply authority path after bounded freshness revalidation."
        )
    if authorization.human_approval_received and authorization.denial_reason in {
        DENIAL_SOURCE_STATE_STALE,
        DENIAL_ELIGIBILITY_RECEIPT_STALE,
    }:
        return (
            "Approval was received, but the reviewed candidate/evidence is stale. "
            "Nothing was applied."
        )
    if authorization.denial_reason == DENIAL_CANDIDATE_MISMATCH:
        return (
            "Approval was received, but it does not target this exact candidate. "
            "Nothing was applied."
        )
    if authorization.denial_reason == DENIAL_PATCH_SAFETY_MISMATCH:
        return (
            "Patch blocked by safety gate. Human Apply did not override patch "
            "safety; nothing was applied."
        )
    if authorization.denial_reason == DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE:
        return (
            "This candidate is not eligible for the evidence-bounded human-review "
            "path. Nothing was applied."
        )
    if authorization.denial_reason == DENIAL_APPROVAL_MISSING:
        return "Explicit human approval is missing. Nothing was applied."
    return "Human Apply authorization was denied. Nothing was applied."


def human_apply_guardrails() -> dict[str, bool]:
    return {
        "exact_candidate_binding": True,
        "eligibility_receipt_binding": True,
        "known_path_source_freshness": True,
        "repository_identity_revalidated": True,
        "patch_safety_revalidated": True,
        "authorization_created_before_mutation": True,
        "eligibility_is_approval": False,
        "approval_is_authorization": False,
        "approval_is_defect_evidence": False,
        "approval_implies_persistence": False,
        "bounded_auto_apply_added": False,
        "validation_generated": False,
        "repository_traversed": False,
        "model_called": False,
        "network_called": False,
    }


__all__ = [
    "PHASE_ID",
    "REVIEW_SCHEMA_VERSION",
    "AUTHORIZATION_SCHEMA_VERSION",
    "PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW",
    "MANUAL_REVIEW_PROFILES",
    "HUMAN_ACTION_APPLY",
    "HUMAN_ACTION_REVIEW_AND_APPLY",
    "HUMAN_ACTION_CLI_CONFIRMATION",
    "HUMAN_ACTION_KINDS",
    "FRESHNESS_CURRENT",
    "FRESHNESS_STALE",
    "FRESHNESS_INCOMPLETE",
    "AUTHORIZATION_NOT_REQUESTED",
    "AUTHORIZATION_AUTHORIZED",
    "AUTHORIZATION_DENIED",
    "DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE",
    "DENIAL_APPROVAL_MISSING",
    "DENIAL_CANDIDATE_MISMATCH",
    "DENIAL_ELIGIBILITY_RECEIPT_STALE",
    "DENIAL_SOURCE_STATE_STALE",
    "DENIAL_PATCH_SAFETY_MISMATCH",
    "DENIAL_REPOSITORY_IDENTITY_MISMATCH",
    "DENIAL_POLICY_PROFILE_MISMATCH",
    "DENIAL_INCONSISTENT_INPUT",
    "DENIAL_REASONS",
    "HumanApplyReviewReceipt",
    "HumanApplyAuthorization",
    "eligibility_assessment_fingerprint",
    "patch_safety_binding_fingerprint",
    "source_state_fingerprint",
    "parse_human_apply_review_receipt",
    "build_human_apply_review_receipt",
    "authorize_human_apply",
    "describe_human_apply_authorization",
    "human_apply_guardrails",
]
