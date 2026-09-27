"""CHECK.LIVE.1 — ExecutionAuthorization producer for the live apply path.

The live apply path already has exactly one authority record: the verdict the
frozen ``core.patch_safety`` gate returns for the paths a patch plan names,
evaluated against the real project root immediately before any write.  This
module translates that verdict into CHECK.1's typed
:class:`~core.post_run_reconciliation.ExecutionAuthorization`.

Its single hard invariant is *monotonicity*:

    a producer may translate authority; it may never widen it.

Translation is therefore two-sided.  A caller states what the upstream authority
record says, and separately what it wants represented; anything stronger than
upstream fails closed with :class:`LiveAuthorityWideningError` rather than being
silently emitted.  The bucketed result is then handed to the frozen
``core.post_run_observation.classify_authorized_paths`` adapter, which re-runs
the apply-time gate and demotes anything it blocks — so even a caller that
believes a path is writable cannot launder a protected, env, test or
benchmark-validation path into CHECK.1.

The producer performs no traversal, no source read, no validation execution, no
patch application, no model call and no network call, and it grants nothing: an
``ExecutionAuthorization`` is a description of permission that already existed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from core.post_run_observation import classify_authorized_paths
from core.post_run_reconciliation import (
    FORBIDDEN_OTHER,
    FORBIDDEN_REASONS,
    MAX_AUTHORIZED_PATHS,
    MAX_VALIDATION_EXPECTATIONS,
    PATH_AUTHORITY_FORBIDDEN,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
    PATH_AUTHORITY_WRITABLE,
    PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
    ExecutionAuthorization,
    PreservationObligation,
    ValidationExpectation,
    execution_authorization_fingerprint,
)


PHASE_ID = "CHECK.LIVE.1"
PRODUCER_KIND = "live_execution_authorization"

AUTHORITY_FINGERPRINT_KIND = "check_live_1_upstream_patch_authority_v1"
AUTHORIZATION_ID_PREFIX = "live-auth"

#: How much power each authority carries.  Read authority and execute authority
#: sit on the same rung deliberately: neither is write authority, and neither
#: may be traded for the other.
_AUTHORITY_RANK: dict[str, int] = {
    PATH_AUTHORITY_FORBIDDEN: 0,
    PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY: 1,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY: 1,
    PATH_AUTHORITY_WRITABLE_WITH_REVIEW: 2,
    PATH_AUTHORITY_WRITABLE: 3,
}

TRANSLATABLE_AUTHORITIES: tuple[str, ...] = tuple(_AUTHORITY_RANK)


class LiveAuthorityWideningError(ValueError):
    """Raised when a producer is asked to emit more authority than upstream."""


class LiveAuthorityInputError(ValueError):
    """Raised when the supplied upstream authority record is unusable."""


def upstream_authority_from_patch_safety(
    target_paths: Sequence[str],
    patch_safety_verdict: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str], str]:
    """Translate one live patch-safety verdict into an upstream authority map.

    Returns ``(authority_by_path, forbidden_reason_by_path, fingerprint)``.

    Every path the gate blocked becomes ``forbidden`` carrying the gate's own
    category; every other named path is what the live apply path actually
    treats as writable.  Nothing else is inferred, and no path the gate never
    saw is added.
    """
    if not isinstance(patch_safety_verdict, Mapping):
        raise LiveAuthorityInputError("patch safety verdict must be a mapping")

    ordered = tuple(sorted({str(path) for path in target_paths}))
    blocked: dict[str, str] = {}
    raw_blocked = patch_safety_verdict.get("blocked_paths") or []
    if not isinstance(raw_blocked, Sequence):
        raise LiveAuthorityInputError("blocked_paths must be a sequence")
    for entry in raw_blocked:
        if not isinstance(entry, Mapping):
            raise LiveAuthorityInputError("each blocked path must be a mapping")
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        category = entry.get("category")
        blocked[path] = (
            category if category in FORBIDDEN_REASONS else FORBIDDEN_OTHER
        )

    authority: dict[str, str] = {}
    forbidden_reasons: dict[str, str] = {}
    for path in ordered:
        reason = blocked.get(path)
        if reason is not None:
            authority[path] = PATH_AUTHORITY_FORBIDDEN
            forbidden_reasons[path] = reason
        else:
            authority[path] = PATH_AUTHORITY_WRITABLE

    fingerprint = _fingerprint(
        {
            "kind": AUTHORITY_FINGERPRINT_KIND,
            "phase_id": PHASE_ID,
            "gate_ok": bool(patch_safety_verdict.get("ok")),
            "paths": list(ordered),
            "authority": [
                {
                    "path": path,
                    "authority": authority[path],
                    "forbidden_reason": forbidden_reasons.get(path),
                }
                for path in ordered
            ],
        }
    )
    return authority, forbidden_reasons, fingerprint


def assert_authority_not_widened(
    upstream_authority: Mapping[str, str],
    requested_authority: Mapping[str, str],
) -> None:
    """Fail closed when a request carries more power than upstream granted."""
    for path, requested in requested_authority.items():
        if requested not in _AUTHORITY_RANK:
            raise LiveAuthorityInputError(
                f"unsupported requested authority for {path!r}: {requested!r}"
            )
        if path not in upstream_authority:
            raise LiveAuthorityWideningError(
                f"path {path!r} has no upstream authority record"
            )
        granted = upstream_authority[path]
        if granted not in _AUTHORITY_RANK:
            raise LiveAuthorityInputError(
                f"unsupported upstream authority for {path!r}: {granted!r}"
            )
        if _AUTHORITY_RANK[requested] > _AUTHORITY_RANK[granted]:
            raise LiveAuthorityWideningError(
                f"path {path!r} may not be widened from {granted!r} to "
                f"{requested!r}"
            )
        if (
            _AUTHORITY_RANK[requested] == _AUTHORITY_RANK[granted]
            and requested != granted
        ):
            # Same rung, different power: read authority is not execute
            # authority and vice versa.
            raise LiveAuthorityWideningError(
                f"path {path!r} may not be re-labelled from {granted!r} to "
                f"{requested!r}"
            )


def live_authorization_id(
    *,
    execution_run_id: str,
    repository_id: str,
    upstream_authority_fingerprint: str,
) -> str:
    """Deterministic identity bound to the run and the upstream authority."""
    digest = _fingerprint(
        {
            "kind": "check_live_1_authorization_identity_v1",
            "execution_run_id": str(execution_run_id),
            "repository_id": str(repository_id),
            "upstream_authority_fingerprint": str(upstream_authority_fingerprint),
        }
    )
    return f"{AUTHORIZATION_ID_PREFIX}-{digest[:32]}"


def build_live_execution_authorization(
    *,
    execution_run_id: str,
    repository_id: str,
    task_contract_fingerprint: str,
    pre_execution_state_fingerprint: str,
    upstream_authority: Mapping[str, str],
    upstream_forbidden_reasons: Mapping[str, str] | None = None,
    upstream_authority_fingerprint: str,
    requested_authority: Mapping[str, str] | None = None,
    validation_expectations: Sequence[ValidationExpectation] = (),
    preservation_obligations: Sequence[PreservationObligation] = (),
    worker_ownership: Mapping[str, str] | None = None,
    worker_id: str | None = None,
) -> ExecutionAuthorization:
    """Produce one typed ExecutionAuthorization from live upstream authority.

    ``requested_authority`` defaults to the upstream record verbatim.  Supplying
    a different one is how a caller narrows scope; widening it is refused.
    """
    if not isinstance(upstream_authority, Mapping):
        raise LiveAuthorityInputError("upstream_authority must be a mapping")
    requested = dict(
        upstream_authority if requested_authority is None else requested_authority
    )
    assert_authority_not_widened(upstream_authority, requested)

    reasons = dict(upstream_forbidden_reasons or {})
    buckets: dict[str, list[str]] = {
        PATH_AUTHORITY_WRITABLE: [],
        PATH_AUTHORITY_WRITABLE_WITH_REVIEW: [],
        PATH_AUTHORITY_SUPPORTING_READ_ONLY: [],
        PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY: [],
    }
    forbidden: dict[str, str] = {}
    for path, authority in sorted(requested.items()):
        if authority == PATH_AUTHORITY_FORBIDDEN:
            reason = reasons.get(path, FORBIDDEN_OTHER)
            forbidden[path] = (
                reason if reason in FORBIDDEN_REASONS else FORBIDDEN_OTHER
            )
            continue
        buckets[authority].append(path)

    if len(requested) > MAX_AUTHORIZED_PATHS:
        raise LiveAuthorityInputError(
            "live authorized path set exceeds its finite bound"
        )

    authorized_paths = classify_authorized_paths(
        writable_paths=tuple(buckets[PATH_AUTHORITY_WRITABLE]),
        writable_with_review_paths=tuple(
            buckets[PATH_AUTHORITY_WRITABLE_WITH_REVIEW]
        ),
        supporting_read_only_paths=tuple(
            buckets[PATH_AUTHORITY_SUPPORTING_READ_ONLY]
        ),
        validation_execute_only_paths=tuple(
            buckets[PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY]
        ),
        forbidden_paths=forbidden,
        worker_ownership=dict(worker_ownership) if worker_ownership else None,
    )

    expectations = tuple(validation_expectations)
    if len(expectations) > MAX_VALIDATION_EXPECTATIONS:
        raise LiveAuthorityInputError(
            "live validation expectations exceed their finite bound"
        )

    return ExecutionAuthorization(
        authorization_id=live_authorization_id(
            execution_run_id=execution_run_id,
            repository_id=repository_id,
            upstream_authority_fingerprint=upstream_authority_fingerprint,
        ),
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        task_contract_fingerprint=task_contract_fingerprint,
        pre_execution_state_fingerprint=pre_execution_state_fingerprint,
        authorized_paths=authorized_paths,
        validation_expectations=expectations,
        preservation_obligations=tuple(preservation_obligations),
        path_expansion_receipts=(),
        worker_id=worker_id,
    )


def live_authorization_fingerprint(
    authorization: ExecutionAuthorization,
) -> str:
    """Re-expose the frozen fingerprint so callers need no second import."""
    return execution_authorization_fingerprint(authorization)


def live_authorization_guardrails() -> dict[str, bool]:
    """Every power the authorization producer declines to exercise."""
    return {
        "patch_safety_gate_reused": True,
        "authority_translated_not_granted": True,
        "authority_widening_possible": False,
        "path_expansion_receipt_minted": False,
        "human_approval_required": True,
        "repository_traversed": False,
        "source_content_read": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "network_call_performed": False,
        "model_called": False,
        "authoritative_effect": False,
    }


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "PHASE_ID",
    "PRODUCER_KIND",
    "AUTHORITY_FINGERPRINT_KIND",
    "AUTHORIZATION_ID_PREFIX",
    "TRANSLATABLE_AUTHORITIES",
    "LiveAuthorityWideningError",
    "LiveAuthorityInputError",
    "upstream_authority_from_patch_safety",
    "assert_authority_not_widened",
    "live_authorization_id",
    "build_live_execution_authorization",
    "live_authorization_fingerprint",
    "live_authorization_guardrails",
]
