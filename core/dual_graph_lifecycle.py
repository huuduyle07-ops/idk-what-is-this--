"""INDEX.1D.1 - pure Dual Graph Lifecycle Contract.

This module defines metadata, lifecycle, freshness, retention, authority, and
storage-separation contracts for three context strategies:

* Direct Context: caller-supplied evidence; no graph artifact.
* Activation Graph: bounded task cache; temporary and never canonical.
* Canonical Incremental Graph: repository intelligence; persistent and gated.

The helpers are advisory and deterministic.  They do not scan a repository,
index code, access a database or manifest, build a graph, call a model, use the
network, run a subprocess, mutate an input record, or delete a filesystem path.
The companion script is the only artifact writer for this phase.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import PurePosixPath
from typing import Any


PHASE_ID = "INDEX.1D.1"
PHASE_TITLE = "Dual Graph Lifecycle Contract"
SCHEMA_VERSION = 1
ARTIFACT_KIND = "cattus_dual_graph_lifecycle_contract"

GRAPH_KIND_DIRECT_CONTEXT = "direct_context"
GRAPH_KIND_ACTIVATION = "activation_graph"
GRAPH_KIND_CANONICAL = "canonical_incremental_graph"
GRAPH_KINDS = (
    GRAPH_KIND_DIRECT_CONTEXT,
    GRAPH_KIND_ACTIVATION,
    GRAPH_KIND_CANONICAL,
)

ACTIVATION_ARTIFACT_KIND = "cattus_activation_graph"
CANONICAL_ARTIFACT_KIND = "cattus_canonical_incremental_graph"

DEFAULT_ACTIVATION_TTL_SECONDS = 72 * 60 * 60
DEFAULT_MAX_GRAPHS_PER_REPOSITORY = 20
DEFAULT_MAX_ACTIVATION_LEASE_SECONDS = 6 * 60 * 60

ACTIVATION_STORAGE_ROOT = ".agent/activation_graphs"
CANONICAL_STORAGE_ROOT = ".agent/repository_intelligence"

ACTIVATION_STATES = (
    "planned",
    "active",
    "stale",
    "expired",
    "cleanup_candidate",
    "deleted",
    "blocked",
)
CANONICAL_STATES = (
    "not_built",
    "initial_confirmation_required",
    "building",
    "current",
    "stale",
    "major_change_confirmation_required",
    "refreshing",
    "degraded",
    "blocked",
    "archived_epoch",
)
FRESHNESS_STATES = (
    "fresh",
    "partially_changed",
    "stale",
    "missing_files",
    "unknown",
)
EXPIRY_DECISIONS = (
    "keep_active",
    "keep_pinned",
    "keep_leased",
    "mark_expired",
    "cleanup_candidate",
    "invalid_metadata",
)
CLEANUP_CLASSIFICATIONS = (
    "keep",
    "cleanup_candidate",
    "invalid_or_unmanaged",
    "blocked_by_pin",
    "blocked_by_lease",
)
CLEANUP_TRIGGERS = (
    "startup",
    "before_activation_create",
    "manual",
    "storage_budget_pressure",
)

ACTIVATION_TRANSITIONS = {
    "planned": ("active", "blocked"),
    "active": ("stale", "expired", "blocked"),
    "stale": ("active", "expired"),
    "expired": ("cleanup_candidate",),
    "cleanup_candidate": ("active", "deleted"),
    "deleted": (),
    "blocked": (),
}
CANONICAL_TRANSITIONS = {
    "not_built": ("initial_confirmation_required",),
    "initial_confirmation_required": ("building", "blocked"),
    "building": ("current", "degraded", "blocked"),
    "current": (
        "stale",
        "major_change_confirmation_required",
        "degraded",
    ),
    "stale": ("refreshing", "degraded", "blocked"),
    "major_change_confirmation_required": (
        "refreshing",
        "archived_epoch",
        "blocked",
    ),
    "refreshing": ("current", "degraded", "blocked"),
    "degraded": ("refreshing", "blocked", "archived_epoch"),
    "blocked": (),
    "archived_epoch": (),
}

CONTRACT_JSON_NAME = "dual_graph_lifecycle_contract.json"
CONTRACT_MD_NAME = "dual_graph_lifecycle_contract.md"

DUAL_GRAPH_GUARDRAIL_NOTE = (
    "INDEX.1D.1 defines contracts only. It does not create, refresh, migrate, "
    "reconcile, persist, or delete either graph system and it does not change "
    "production indexing behavior."
)


@dataclass(frozen=True)
class ExpiryDecision:
    """Pure result of classifying sliding-TTL retention."""

    decision: str
    expired: bool
    protected: bool
    automatic_cleanup_allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FreshnessDecision:
    """Pure fingerprint comparison result."""

    status: str
    reuse_allowed: bool
    bounded_refresh_recommended: bool
    rebuild_required: bool
    changed_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    changed_ratio: float | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["changed_files"] = list(self.changed_files)
        result["missing_files"] = list(self.missing_files)
        return result


@dataclass(frozen=True)
class TransitionDecision:
    """Pure lifecycle-transition verdict."""

    allowed: bool
    current_state: str
    target_state: str
    reason: str
    new_identity_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LeaseDecision:
    """Pure lease-validity and cleanup-protection verdict."""

    valid: bool
    active: bool
    protects_from_cleanup: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphRecommendation:
    """Advisory graph-kind recommendation; never a dispatch instruction."""

    graph_kind: str
    reason: str
    canonical_operation_blocked: bool = False
    human_confirmation_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_aware_timestamp(value: Any) -> datetime | None:
    """Return a UTC-aware datetime, or ``None`` for invalid/naive input."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _stable_text_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    return sorted({str(value) for value in values if str(value)})


def graph_kind_contract(graph_kind: str) -> dict[str, Any]:
    """Return a fresh authority record for one stable context strategy."""
    contracts = {
        GRAPH_KIND_DIRECT_CONTEXT: {
            "scope": "caller-supplied files, snippets, or replay evidence",
            "persistent": False,
            "graph_required": False,
            "repository_scan_required": False,
            "database_write_allowed": False,
            "manifest_required": False,
            "manifest_advancement_allowed": False,
            "reconciliation_allowed": False,
            "human_identity_confirmation_required": False,
            "repository_completeness_claim_allowed": False,
        },
        GRAPH_KIND_ACTIVATION: {
            "scope": "task/run",
            "persistent": False,
            "temporary_cache_only": True,
            "graph_required": True,
            "repository_scan_required": False,
            "bounded_task_scan": True,
            "database_write_allowed": False,
            "manifest_required": False,
            "manifest_advancement_allowed": False,
            "reconciliation_allowed": False,
            "human_identity_confirmation_required": False,
            "repository_completeness_claim_allowed": False,
        },
        GRAPH_KIND_CANONICAL: {
            "scope": "repository + architecture epoch",
            "persistent": True,
            "graph_required": True,
            "initial_repository_scan_required": True,
            "database_write_allowed": True,
            "strict_index_scope_required": True,
            "manifest_required": True,
            "manifest_advancement_allowed": "trusted_completion_only",
            "reconciliation_allowed": "identity_and_persistence_gated",
            "human_identity_confirmation_required": True,
            "repository_completeness_claim_allowed": "trusted_completion_only",
        },
    }
    if graph_kind not in contracts:
        raise ValueError(f"unknown graph kind: {graph_kind!r}")
    return dict(contracts[graph_kind])


def build_activation_metadata(
    *,
    activation_id: str,
    repository_root: str,
    task_id: str,
    created_at: str,
    last_used_at: str | None = None,
    status: str = "planned",
    ttl_seconds: int = DEFAULT_ACTIVATION_TTL_SECONDS,
    pinned: bool = False,
    lease_owner: str | None = None,
    lease_acquired_at: str | None = None,
    lease_expires_at: str | None = None,
    seed_files: Iterable[str] = (),
    activated_files: Iterable[str] = (),
    dependency_depth: int = 0,
    file_budget: int = 30,
    content_byte_budget: int = 0,
    storage_bytes: int = 0,
    freshness_status: str = "unknown",
    freshness_checked_at: str | None = None,
    changed_files: Iterable[str] = (),
) -> dict[str, Any]:
    """Build explicit Activation Graph metadata without reading or writing state."""
    activation_id = str(activation_id)
    if (
        not activation_id
        or "/" in activation_id
        or "\\" in activation_id
        or activation_id in {".", ".."}
    ):
        raise ValueError("activation_id must be one safe path segment")
    if _parse_aware_timestamp(created_at) is None or _parse_aware_timestamp(
        last_used_at or created_at
    ) is None:
        raise ValueError("created_at and last_used_at must be timezone-aware ISO timestamps")
    if status not in ACTIVATION_STATES:
        raise ValueError(f"unknown activation state: {status!r}")
    if freshness_status not in FRESHNESS_STATES:
        raise ValueError(f"unknown freshness state: {freshness_status!r}")
    if _valid_positive_int(ttl_seconds) is None:
        raise ValueError("ttl_seconds must be a positive integer")
    if (
        isinstance(dependency_depth, bool)
        or not isinstance(dependency_depth, int)
        or dependency_depth < 0
        or isinstance(file_budget, bool)
        or not isinstance(file_budget, int)
        or file_budget <= 0
        or isinstance(content_byte_budget, bool)
        or not isinstance(content_byte_budget, int)
        or content_byte_budget < 0
        or isinstance(storage_bytes, bool)
        or not isinstance(storage_bytes, int)
        or storage_bytes < 0
    ):
        raise ValueError("scope and storage budgets must be valid non-negative integers")
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ACTIVATION_ARTIFACT_KIND,
        "graph_kind": GRAPH_KIND_ACTIVATION,
        "activation_id": activation_id,
        "repository_root": str(repository_root),
        "task_id": str(task_id),
        "created_at": str(created_at),
        "last_used_at": str(last_used_at or created_at),
        "status": status,
        "ttl_seconds": ttl_seconds,
        "pinned": bool(pinned),
        "lease": {
            "owner": str(lease_owner) if lease_owner is not None else None,
            "acquired_at": lease_acquired_at,
            "expires_at": lease_expires_at,
        },
        "scope": {
            "seed_files": _stable_text_list(seed_files),
            "activated_files": _stable_text_list(activated_files),
            "dependency_depth": int(dependency_depth),
            "file_budget": int(file_budget),
            "content_byte_budget": int(content_byte_budget),
        },
        "freshness": {
            "status": freshness_status,
            "checked_at": freshness_checked_at,
            "changed_files": _stable_text_list(changed_files),
        },
        "artifact_path": f"{ACTIVATION_STORAGE_ROOT}/{activation_id}",
        "path_is_symlink": False,
        "storage_bytes": storage_bytes,
        "managed_cleanup_allowed": True,
        "persistent_code_index_written": False,
        "canonical_manifest_advanced": False,
        "repository_completeness_claimed": False,
    }


def classify_activation_expiry(
    *,
    last_used_at: Any,
    now: Any,
    ttl_seconds: int = DEFAULT_ACTIVATION_TTL_SECONDS,
    pinned: bool = False,
    lease_expires_at: Any = None,
    status: str | None = None,
) -> ExpiryDecision:
    """Classify sliding expiry from ``last_used_at`` with fail-closed parsing.

    The exact TTL boundary is expired: ``now - last_used_at >= ttl_seconds``.
    Metadata viewing or UI polling must not call a future touch/update operation;
    only actual retrieval/context reuse may produce a new ``last_used_at``.
    """
    now_value = _parse_aware_timestamp(now)
    used_value = _parse_aware_timestamp(last_used_at)
    ttl_value = _valid_positive_int(ttl_seconds)
    lease_value = (
        _parse_aware_timestamp(lease_expires_at)
        if lease_expires_at is not None
        else None
    )
    if (
        now_value is None
        or used_value is None
        or ttl_value is None
        or (lease_expires_at is not None and lease_value is None)
        or (now_value is not None and used_value is not None and used_value > now_value)
    ):
        return ExpiryDecision(
            "invalid_metadata",
            expired=False,
            protected=True,
            automatic_cleanup_allowed=False,
            reason="Invalid, naive, or future timestamp metadata fails closed.",
        )
    expired = (now_value - used_value).total_seconds() >= ttl_value
    if pinned:
        return ExpiryDecision(
            "keep_pinned",
            expired=expired,
            protected=True,
            automatic_cleanup_allowed=False,
            reason="Pinning is a retention preference and blocks automatic cleanup.",
        )
    if lease_value is not None and lease_value > now_value:
        return ExpiryDecision(
            "keep_leased",
            expired=expired,
            protected=True,
            automatic_cleanup_allowed=False,
            reason="A valid active lease blocks automatic cleanup.",
        )
    if expired:
        already_expired = status in {"expired", "cleanup_candidate"}
        return ExpiryDecision(
            "cleanup_candidate" if already_expired else "mark_expired",
            expired=True,
            protected=False,
            automatic_cleanup_allowed=already_expired,
            reason=(
                "The sliding TTL elapsed and the record is already expiry-classified."
                if already_expired
                else "The sliding TTL elapsed; mark expired before cleanup planning."
            ),
        )
    return ExpiryDecision(
        "keep_active",
        expired=False,
        protected=False,
        automatic_cleanup_allowed=False,
        reason="The sliding TTL has not elapsed.",
    )


def classify_activation_freshness(
    stored_file_fingerprints: Mapping[str, Any] | None,
    current_file_fingerprints: Mapping[str, Any] | None,
    *,
    changed_file_limit: int,
    changed_ratio_limit: float,
    seed_files: Iterable[str] | None = None,
) -> FreshnessDecision:
    """Compare supplied fingerprints without reading source files."""
    if (
        not isinstance(stored_file_fingerprints, Mapping)
        or not isinstance(current_file_fingerprints, Mapping)
        or not stored_file_fingerprints
        or isinstance(changed_file_limit, bool)
        or not isinstance(changed_file_limit, int)
        or changed_file_limit < 0
        or isinstance(changed_ratio_limit, bool)
        or not isinstance(changed_ratio_limit, (int, float))
        or not 0 <= float(changed_ratio_limit) <= 1
    ):
        return FreshnessDecision(
            "unknown", False, False, False, (), (), None,
            "Missing or invalid fingerprint metadata cannot establish freshness.",
        )

    stored = {str(key): value for key, value in stored_file_fingerprints.items()}
    current = {str(key): value for key, value in current_file_fingerprints.items()}
    if any(value is None or value == "" for value in stored.values()) or any(
        value is None or value == "" for value in current.values()
    ):
        return FreshnessDecision(
            "unknown", False, False, False, (), (), None,
            "Unverifiable fingerprints cannot establish freshness.",
        )

    missing = tuple(sorted(path for path in stored if path not in current))
    required_seeds = {str(path) for path in (seed_files or ())}
    missing_seeds = tuple(sorted(path for path in required_seeds if path not in current))
    changed = tuple(
        sorted(
            path
            for path, stored_value in stored.items()
            if path in current and current[path] != stored_value
        )
    )
    all_missing = tuple(sorted(set(missing) | set(missing_seeds)))
    ratio = (len(changed) + len(all_missing)) / len(stored)
    if all_missing:
        reason = (
            "One or more seed files are missing; rebuild the Activation Graph."
            if missing_seeds
            else "One or more activated files are missing; rebuild the Activation Graph."
        )
        return FreshnessDecision(
            "missing_files", False, False, True, changed, all_missing, ratio, reason
        )
    if not changed:
        return FreshnessDecision(
            "fresh", True, False, False, (), (), 0.0,
            "All stored fingerprints match; reuse is allowed.",
        )
    if len(changed) <= changed_file_limit and ratio <= float(changed_ratio_limit):
        return FreshnessDecision(
            "partially_changed",
            False,
            True,
            False,
            changed,
            (),
            ratio,
            "A small bounded change set may be refreshed before reuse.",
        )
    return FreshnessDecision(
        "stale",
        False,
        False,
        True,
        changed,
        (),
        ratio,
        "The change count or ratio exceeds the bounded refresh threshold; rebuild.",
    )


def validate_activation_transition(
    current_state: str,
    target_state: str,
    *,
    freshness_succeeded: bool = False,
) -> TransitionDecision:
    """Reject forbidden Activation Graph state transitions."""
    if current_state not in ACTIVATION_STATES or target_state not in ACTIVATION_STATES:
        return TransitionDecision(
            False, current_state, target_state, "Unknown activation lifecycle state."
        )
    if target_state not in ACTIVATION_TRANSITIONS[current_state]:
        return TransitionDecision(
            False,
            current_state,
            target_state,
            "Transition is not in the Activation Graph lifecycle.",
            new_identity_required=current_state in {"deleted", "blocked"},
        )
    if (
        current_state in {"stale", "cleanup_candidate"}
        and target_state == "active"
        and not freshness_succeeded
    ):
        return TransitionDecision(
            False,
            current_state,
            target_state,
            "Reactivation requires a successful bounded freshness check or refresh.",
        )
    return TransitionDecision(
        True, current_state, target_state, "Transition is allowed by the contract."
    )


def validate_activation_lease(
    *,
    owner: Any,
    acquired_at: Any,
    expires_at: Any,
    now: Any,
    max_duration_seconds: int = DEFAULT_MAX_ACTIVATION_LEASE_SECONDS,
) -> LeaseDecision:
    """Validate a bounded lease; expired leases never protect cleanup."""
    owner_value = str(owner or "").strip()
    acquired_value = _parse_aware_timestamp(acquired_at)
    expires_value = _parse_aware_timestamp(expires_at)
    now_value = _parse_aware_timestamp(now)
    max_duration = _valid_positive_int(max_duration_seconds)
    if (
        not owner_value
        or acquired_value is None
        or expires_value is None
        or now_value is None
        or max_duration is None
        or expires_value <= acquired_value
        or (expires_value - acquired_value).total_seconds() > max_duration
    ):
        return LeaseDecision(
            False, False, False, "Lease metadata is invalid or exceeds the bounded duration."
        )
    active = expires_value > now_value
    return LeaseDecision(
        True,
        active,
        active,
        "The lease is active." if active else "The lease expired and provides no protection.",
    )


def can_release_activation_lease(
    lease: Mapping[str, Any] | None,
    *,
    owner: str,
    now: Any,
) -> bool:
    """Return true only when ``owner`` matches a currently active lease."""
    if not isinstance(lease, Mapping):
        return False
    decision = validate_activation_lease(
        owner=lease.get("owner"),
        acquired_at=lease.get("acquired_at"),
        expires_at=lease.get("expires_at"),
        now=now,
    )
    return decision.active and str(lease.get("owner")) == str(owner)


def _path_parts(value: Any) -> tuple[bool, tuple[str, ...]] | None:
    raw = str(value or "").replace("\\", "/")
    if not raw:
        return None
    path = PurePosixPath(raw)
    if ".." in path.parts:
        return None
    parts = tuple(part for part in path.parts if part not in ("", ".", "/"))
    return (path.is_absolute(), parts)


def _managed_activation_path(
    record: Mapping[str, Any],
    activation_root: str,
) -> tuple[bool, str]:
    """Lexically validate an asserted, non-symlinked managed artifact path."""
    activation_id = str(record.get("activation_id") or "")
    if (
        not activation_id
        or "/" in activation_id
        or "\\" in activation_id
        or record.get("path_is_symlink") is not False
    ):
        return False, "Missing identity or symlink validation."
    root_parts = _path_parts(activation_root)
    artifact_parts = _path_parts(record.get("artifact_path"))
    if root_parts is None or artifact_parts is None:
        return False, "Missing or invalid managed path."
    root_absolute, root_values = root_parts
    artifact_absolute, artifact_values = artifact_parts
    expected = root_values + (activation_id,)
    if root_absolute != artifact_absolute or tuple(
        value.casefold() for value in artifact_values
    ) != tuple(value.casefold() for value in expected):
        return False, "Artifact path is outside the Activation Graph root."
    return True, "Marker and managed path are valid."


def _cleanup_sort_timestamp(value: Any) -> str:
    parsed = _parse_aware_timestamp(value)
    return parsed.isoformat() if parsed is not None else "9999-12-31T23:59:59+00:00"


def build_activation_cleanup_plan(
    activation_records: Sequence[Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    *,
    now: Any,
    max_graphs_per_repo: int = DEFAULT_MAX_GRAPHS_PER_REPOSITORY,
    max_total_bytes: int | None = None,
    activation_root: str = ACTIVATION_STORAGE_ROOT,
    trigger: str = "manual",
) -> dict[str, Any]:
    """Build a deterministic dry-run cleanup plan; never delete an artifact.

    A future caller must independently establish the no-symlink fact before
    supplying records.  Missing markers, missing validation, canonical kinds,
    traversal, and out-of-root paths fail closed as ``invalid_or_unmanaged``.
    """
    if trigger not in CLEANUP_TRIGGERS:
        raise ValueError(f"unsupported cleanup trigger: {trigger!r}")
    root_parts = _path_parts(activation_root)
    canonical_parts = _path_parts(CANONICAL_STORAGE_ROOT)
    if root_parts is None or canonical_parts is None:
        raise ValueError("activation_root must be a valid managed path")
    _, root_values = root_parts
    _, canonical_values = canonical_parts
    folded_root = tuple(value.casefold() for value in root_values)
    folded_canonical = tuple(value.casefold() for value in canonical_values)
    canonical_sequence_present = any(
        folded_root[index : index + len(folded_canonical)] == folded_canonical
        for index in range(len(folded_root) - len(folded_canonical) + 1)
    )
    if canonical_sequence_present:
        raise ValueError("canonical storage root cannot be used for activation cleanup")
    if _valid_positive_int(max_graphs_per_repo) is None:
        raise ValueError("max_graphs_per_repo must be a positive integer")
    if (
        max_total_bytes is not None
        and (
            isinstance(max_total_bytes, bool)
            or not isinstance(max_total_bytes, int)
            or max_total_bytes < 0
        )
    ):
        raise ValueError("max_total_bytes must be a non-negative integer or None")

    prepared: list[dict[str, Any]] = []
    for source_index, source_record in enumerate(list(activation_records)):
        if not isinstance(source_record, Mapping):
            prepared.append(
                {
                    "source_index": source_index,
                    "activation_id": f"(invalid-{source_index})",
                    "repository_root": "",
                    "status": "",
                    "classification": "invalid_or_unmanaged",
                    "reason": "Record is not a metadata mapping.",
                    "tier": 99,
                    "last_used_at": "",
                    "storage_bytes": 0,
                }
            )
            continue
        record = dict(source_record)
        activation_id = str(record.get("activation_id") or f"(invalid-{source_index})")
        base = {
            "source_index": source_index,
            "activation_id": activation_id,
            "repository_root": str(record.get("repository_root") or ""),
            "status": str(record.get("status") or ""),
            "classification": "keep",
            "reason": "Managed record is retained.",
            "tier": 99,
            "last_used_at": str(record.get("last_used_at") or ""),
            "storage_bytes": 0,
        }
        size = record.get("storage_bytes", 0)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            base.update(
                classification="invalid_or_unmanaged",
                reason="storage_bytes must be a non-negative integer.",
            )
            prepared.append(base)
            continue
        base["storage_bytes"] = size
        marker_kind = record.get("artifact_kind")
        managed_marker = record.get("managed_cleanup_allowed") is True
        path_ok, path_reason = _managed_activation_path(record, activation_root)
        if (
            marker_kind != ACTIVATION_ARTIFACT_KIND
            or not managed_marker
            or not path_ok
        ):
            base.update(
                classification="invalid_or_unmanaged",
                reason=(
                    "Canonical artifacts are isolated from Activation Graph cleanup."
                    if marker_kind == CANONICAL_ARTIFACT_KIND
                    or record.get("graph_kind") == GRAPH_KIND_CANONICAL
                    else path_reason
                    if not path_ok
                    else "Activation cleanup marker is missing or invalid."
                ),
            )
            prepared.append(base)
            continue

        lease = record.get("lease")
        lease_expires_at = lease.get("expires_at") if isinstance(lease, Mapping) else None
        if isinstance(lease, Mapping) and any(
            lease.get(field) is not None
            for field in ("owner", "acquired_at", "expires_at")
        ):
            lease_decision = validate_activation_lease(
                owner=lease.get("owner"),
                acquired_at=lease.get("acquired_at"),
                expires_at=lease.get("expires_at"),
                now=now,
            )
            if not lease_decision.valid:
                base.update(
                    classification="invalid_or_unmanaged",
                    reason=lease_decision.reason,
                )
                prepared.append(base)
                continue
        expiry = classify_activation_expiry(
            last_used_at=record.get("last_used_at"),
            now=now,
            ttl_seconds=record.get("ttl_seconds", DEFAULT_ACTIVATION_TTL_SECONDS),
            pinned=record.get("pinned") is True,
            lease_expires_at=lease_expires_at,
            status=base["status"],
        )
        if expiry.decision == "invalid_metadata":
            base.update(
                classification="invalid_or_unmanaged",
                reason=expiry.reason,
            )
        elif expiry.decision == "keep_pinned":
            base.update(classification="blocked_by_pin", reason=expiry.reason)
        elif expiry.decision == "keep_leased":
            base.update(classification="blocked_by_lease", reason=expiry.reason)
        elif base["status"] in {"expired", "cleanup_candidate"} or expiry.expired:
            base.update(
                classification="cleanup_candidate",
                reason="Expired, unpinned, unleased managed Activation Graph.",
                tier=0,
            )
        elif base["status"] == "stale":
            base.update(
                classification="cleanup_candidate",
                reason="Stale, unpinned, unleased managed Activation Graph.",
                tier=1,
            )
        prepared.append(base)

    selected_indices = {
        item["source_index"]
        for item in prepared
        if item["classification"] == "cleanup_candidate"
    }

    # Count budgets are repository-scoped. Base expired/stale candidates are
    # credited first, then active records are selected in stable LRU order.
    repositories = sorted(
        {
            item["repository_root"]
            for item in prepared
            if item["classification"] != "invalid_or_unmanaged"
        }
    )
    for repository_root in repositories:
        managed = [
            item
            for item in prepared
            if item["repository_root"] == repository_root
            and item["classification"] != "invalid_or_unmanaged"
            and item["status"] != "deleted"
        ]
        remaining = len(
            [item for item in managed if item["source_index"] not in selected_indices]
        )
        excess = max(0, remaining - max_graphs_per_repo)
        active_lru = sorted(
            (
                item
                for item in managed
                if item["classification"] == "keep"
                and item["status"] == "active"
                and item["source_index"] not in selected_indices
            ),
            key=lambda item: (
                _cleanup_sort_timestamp(item["last_used_at"]),
                item["activation_id"],
                item["source_index"],
            ),
        )
        for item in active_lru[:excess]:
            item.update(
                classification="cleanup_candidate",
                reason="LRU active graph selected because repository count budget is exceeded.",
                tier=2,
            )
            selected_indices.add(item["source_index"])

    if max_total_bytes is not None:
        remaining_bytes = sum(
            item["storage_bytes"]
            for item in prepared
            if item["classification"] != "invalid_or_unmanaged"
            and item["status"] != "deleted"
            and item["source_index"] not in selected_indices
        )
        active_lru = sorted(
            (
                item
                for item in prepared
                if item["classification"] == "keep"
                and item["status"] == "active"
                and item["source_index"] not in selected_indices
            ),
            key=lambda item: (
                _cleanup_sort_timestamp(item["last_used_at"]),
                item["repository_root"],
                item["activation_id"],
                item["source_index"],
            ),
        )
        for item in active_lru:
            if remaining_bytes <= max_total_bytes:
                break
            item.update(
                classification="cleanup_candidate",
                reason="LRU active graph selected because total storage budget is exceeded.",
                tier=2,
            )
            selected_indices.add(item["source_index"])
            remaining_bytes -= item["storage_bytes"]

    ordered_candidates = sorted(
        (
            item
            for item in prepared
            if item["classification"] == "cleanup_candidate"
        ),
        key=lambda item: (
            item["tier"],
            _cleanup_sort_timestamp(item["last_used_at"]),
            item["repository_root"],
            item["activation_id"],
            item["source_index"],
        ),
    )
    candidates = [
        {
            "activation_id": item["activation_id"],
            "repository_root": item["repository_root"],
            "status": item["status"],
            "reason": item["reason"],
            "storage_bytes": item["storage_bytes"],
        }
        for item in ordered_candidates
    ]
    records = [
        {
            "activation_id": item["activation_id"],
            "repository_root": item["repository_root"],
            "status": item["status"],
            "classification": item["classification"],
            "reason": item["reason"],
            "storage_bytes": item["storage_bytes"],
        }
        for item in sorted(
            prepared,
            key=lambda item: (
                item["repository_root"],
                item["activation_id"],
                item["source_index"],
            ),
        )
    ]
    classification_counts = {
        name: sum(item["classification"] == name for item in records)
        for name in CLEANUP_CLASSIFICATIONS
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "graph_kind": GRAPH_KIND_ACTIVATION,
        "trigger": trigger,
        "dry_run": True,
        "deletion_performed": False,
        "activation_root": activation_root,
        "canonical_root_received_as_candidate": False,
        "max_graphs_per_repo": max_graphs_per_repo,
        "max_total_bytes": max_total_bytes,
        "records": records,
        "cleanup_order": candidates,
        "classification_counts": classification_counts,
    }


def validate_canonical_transition(
    current_state: str,
    target_state: str,
    *,
    human_confirmation: bool = False,
    trusted_completion: bool = False,
) -> TransitionDecision:
    """Enforce canonical confirmation and trusted-completion boundaries."""
    if current_state not in CANONICAL_STATES or target_state not in CANONICAL_STATES:
        return TransitionDecision(
            False, current_state, target_state, "Unknown canonical lifecycle state."
        )
    if target_state not in CANONICAL_TRANSITIONS[current_state]:
        return TransitionDecision(
            False, current_state, target_state,
            "Transition is not in the Canonical Incremental Graph lifecycle.",
        )
    if (
        (current_state, target_state)
        in {
            ("initial_confirmation_required", "building"),
            ("major_change_confirmation_required", "refreshing"),
            ("major_change_confirmation_required", "archived_epoch"),
        }
        and not human_confirmation
    ):
        return TransitionDecision(
            False, current_state, target_state,
            "Explicit human confirmation is required for this transition.",
        )
    if target_state == "current" and current_state in {"building", "refreshing"}:
        if not trusted_completion:
            return TransitionDecision(
                False, current_state, target_state,
                "Trusted completion is required before canonical state becomes current.",
            )
    return TransitionDecision(
        True, current_state, target_state, "Transition is allowed by the contract."
    )


def build_canonical_operation_authority(
    *,
    status: str,
    identity_confirmed: bool,
    successful_persistence: bool,
    trusted_completion: bool,
    major_change_pending: bool,
) -> dict[str, Any]:
    """Return canonical mutation/claim gates without performing an operation."""
    if status not in CANONICAL_STATES:
        raise ValueError(f"unknown canonical state: {status!r}")
    operating = status in {"building", "refreshing"}
    common_gate = (
        operating
        and bool(identity_confirmed)
        and bool(successful_persistence)
        and bool(trusted_completion)
        and not bool(major_change_pending)
    )
    return {
        "graph_kind": GRAPH_KIND_CANONICAL,
        "status": status,
        "major_change_candidate_is_advisory_only": True,
        "human_confirmation_required": bool(major_change_pending) or not bool(identity_confirmed),
        "strict_index_scope_required": True,
        "database_write_allowed": (
            operating and bool(identity_confirmed) and not bool(major_change_pending)
        ),
        "scope_reconciliation_allowed": common_gate,
        "manifest_advancement_allowed": common_gate,
        "trusted_architecture_epoch_replacement_allowed": common_gate,
        "repository_current_claim_allowed": (
            status == "current"
            and bool(identity_confirmed)
            and bool(trusted_completion)
            and not bool(major_change_pending)
        ),
    }


def recommend_graph_kind(
    *,
    known_files: bool | Sequence[str],
    requested_mode: str,
    scope_breadth: str,
    architecture_change: bool,
    canonical_status: str,
) -> GraphRecommendation:
    """Recommend context strategy without dispatching or touching state."""
    has_known_files = (
        bool(known_files)
        if isinstance(known_files, bool)
        else bool(list(known_files))
    )
    mode = str(requested_mode or "").casefold().replace("-", "_").replace(" ", "_")
    breadth = str(scope_breadth or "").casefold()
    major_pending = canonical_status == "major_change_confirmation_required"
    broad_request = (
        breadth in {"broad", "repository", "repository_wide"}
        or mode in {"project_evolution", "architecture_audit", "repository_intelligence"}
        or bool(architecture_change)
    )
    if major_pending and not broad_request:
        return GraphRecommendation(
            GRAPH_KIND_ACTIVATION,
            "Narrow tasks may continue independently while canonical confirmation is pending.",
            canonical_operation_blocked=True,
            human_confirmation_required=True,
        )
    if broad_request:
        return GraphRecommendation(
            GRAPH_KIND_CANONICAL,
            "Broad repository intelligence requires the explicit canonical lifecycle.",
            canonical_operation_blocked=major_pending,
            human_confirmation_required=major_pending
            or canonical_status in {"not_built", "initial_confirmation_required"},
        )
    if has_known_files and breadth in {"narrow", "file", "files", "bounded"}:
        return GraphRecommendation(
            GRAPH_KIND_DIRECT_CONTEXT,
            "Known files provide sufficient direct evidence for a narrow task.",
        )
    return GraphRecommendation(
        GRAPH_KIND_ACTIVATION,
        "A bounded dependency search is appropriate without canonical persistence.",
    )


def _authority_matrix() -> list[dict[str, str]]:
    return [
        {
            "capability": "Full repository scan required",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Initial build only",
        },
        {
            "capability": "Bounded task scan",
            GRAPH_KIND_DIRECT_CONTEXT: "Optional",
            GRAPH_KIND_ACTIVATION: "Yes",
            GRAPH_KIND_CANONICAL: "Not primary purpose",
        },
        {
            "capability": "Persistent DB writes",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Yes, strict index_scope",
        },
        {
            "capability": "Embeddings",
            GRAPH_KIND_DIRECT_CONTEXT: "None/selected only",
            GRAPH_KIND_ACTIVATION: "Optional bounded",
            GRAPH_KIND_CANONICAL: "Optional incremental",
        },
        {
            "capability": "Manifest required",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Yes",
        },
        {
            "capability": "Reconciliation allowed",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Yes, identity + persistence gated",
        },
        {
            "capability": "Human identity confirmation",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Yes",
        },
        {
            "capability": "TTL cleanup",
            GRAPH_KIND_DIRECT_CONTEXT: "N/A",
            GRAPH_KIND_ACTIVATION: "Yes",
            GRAPH_KIND_CANONICAL: "No",
        },
        {
            "capability": "Pin/lease lifecycle",
            GRAPH_KIND_DIRECT_CONTEXT: "N/A",
            GRAPH_KIND_ACTIVATION: "Yes",
            GRAPH_KIND_CANONICAL: "No",
        },
        {
            "capability": "Repository completeness claim",
            GRAPH_KIND_DIRECT_CONTEXT: "No",
            GRAPH_KIND_ACTIVATION: "No",
            GRAPH_KIND_CANONICAL: "Trusted completion only",
        },
        {
            "capability": "Suitable for narrow Debug task",
            GRAPH_KIND_DIRECT_CONTEXT: "Yes",
            GRAPH_KIND_ACTIVATION: "Yes",
            GRAPH_KIND_CANONICAL: "Usually unnecessary",
        },
        {
            "capability": "Suitable for Project Evolution",
            GRAPH_KIND_DIRECT_CONTEXT: "Insufficient",
            GRAPH_KIND_ACTIVATION: "Sometimes insufficient",
            GRAPH_KIND_CANONICAL: "Yes",
        },
    ]


def _command_contract() -> list[dict[str, Any]]:
    return [
        {
            "command": "cattus context activate",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": True,
            "human_confirmation_required": False,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus context status",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": False,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus context pin",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": True,
            "human_confirmation_required": True,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus context unpin",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": True,
            "human_confirmation_required": True,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus context cleanup --dry-run",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": False,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus context cleanup",
            "graph_kind": GRAPH_KIND_ACTIVATION,
            "temporary_artifact_mutation": True,
            "human_confirmation_required": True,
            "trusted_completion_required": False,
            "canonical_storage_allowed": False,
        },
        {
            "command": "cattus intelligence build",
            "graph_kind": GRAPH_KIND_CANONICAL,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": True,
            "trusted_completion_required": True,
            "canonical_storage_allowed": True,
        },
        {
            "command": "cattus intelligence refresh",
            "graph_kind": GRAPH_KIND_CANONICAL,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": "major_change_only",
            "trusted_completion_required": True,
            "canonical_storage_allowed": True,
        },
        {
            "command": "cattus intelligence status",
            "graph_kind": GRAPH_KIND_CANONICAL,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": False,
            "trusted_completion_required": False,
            "canonical_storage_allowed": "read_only",
        },
        {
            "command": "cattus intelligence rebuild",
            "graph_kind": GRAPH_KIND_CANONICAL,
            "temporary_artifact_mutation": False,
            "human_confirmation_required": True,
            "trusted_completion_required": True,
            "canonical_storage_allowed": True,
        },
    ]


def build_dual_graph_lifecycle_contract() -> dict[str, Any]:
    """Build the complete deterministic INDEX.1D.1 contract artifact."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "phase": {
            "phase_id": PHASE_ID,
            "title": PHASE_TITLE,
            "contract_only": True,
            "production_runtime_wired": False,
        },
        "architecture": {
            "ordinary_narrow_task": [
                GRAPH_KIND_DIRECT_CONTEXT,
                GRAPH_KIND_ACTIVATION,
            ],
            "explicit_repository_intelligence_operation": GRAPH_KIND_CANONICAL,
            "activation_is_disposable_context_cache": True,
            "canonical_is_durable_repository_intelligence": True,
            "destructive_lifecycle_shared": False,
        },
        "graph_kinds": {
            graph_kind: graph_kind_contract(graph_kind)
            for graph_kind in GRAPH_KINDS
        },
        "activation_graph": {
            "artifact_kind": ACTIVATION_ARTIFACT_KIND,
            "states": list(ACTIVATION_STATES),
            "transitions": {
                state: list(targets)
                for state, targets in ACTIVATION_TRANSITIONS.items()
            },
            "deleted_or_blocked_identity_is_terminal": True,
            "stale_recovery": "rebuild_or_bounded_refresh_never_canonical_migration",
            "expiry": {
                "ttl_seconds": DEFAULT_ACTIVATION_TTL_SECONDS,
                "sliding_from": "last_used_at",
                "exact_boundary_is_expired": True,
                "metadata_view_updates_last_used_at": False,
                "actual_context_reuse_may_update_last_used_at": True,
                "decisions": list(EXPIRY_DECISIONS),
                "helper_performs_deletion": False,
            },
            "cleanup": {
                "continuous_background_janitor": False,
                "triggers": list(CLEANUP_TRIGGERS),
                "dry_run_first": True,
                "classifications": list(CLEANUP_CLASSIFICATIONS),
                "default_max_graphs_per_repo": DEFAULT_MAX_GRAPHS_PER_REPOSITORY,
                "ordering": [
                    "expired_unpinned_unleased",
                    "stale_unpinned_unleased",
                    "lru_active_only_when_hard_budget_exceeded",
                ],
                "planner_performs_deletion": False,
            },
            "freshness": {
                "states": list(FRESHNESS_STATES),
                "ttl_alone_sufficient": False,
                "fresh": "reuse_allowed",
                "partially_changed": "bounded_refresh_recommended",
                "stale": "rebuild_activation_graph",
                "missing_files": "rebuild_activation_graph",
                "unknown": "never_claim_fresh",
                "canonical_reconciliation_semantics_allowed": False,
            },
            "lease": {
                "fields": ["owner", "acquired_at", "expires_at"],
                "default_max_duration_seconds": DEFAULT_MAX_ACTIVATION_LEASE_SECONDS,
                "expired_lease_protects_cleanup": False,
                "matching_owner_required_to_release_active_lease": True,
                "creates_canonical_authority": False,
            },
            "pin": {
                "meaning": "retention_preference",
                "automatic_cleanup_excluded": True,
                "freshness_warning_excluded": False,
                "creates_canonical_authority": False,
                "allows_manifest_advancement": False,
                "allows_persistent_index_writes": False,
                "allows_reconciliation": False,
            },
            "forbidden": [
                "repository_wide_completeness_claim",
                "persistent_database_write",
                "canonical_manifest_advancement",
                "scope_reconciliation",
                "full_repository_embeddings",
            ],
        },
        "canonical_incremental_graph": {
            "artifact_kind": CANONICAL_ARTIFACT_KIND,
            "states": list(CANONICAL_STATES),
            "transitions": {
                state: list(targets)
                for state, targets in CANONICAL_TRANSITIONS.items()
            },
            "initial_build_human_confirmation_required": True,
            "major_change_human_confirmation_required": True,
            "building_to_current_requires_trusted_completion": True,
            "refreshing_to_current_requires_trusted_completion": True,
            "major_change_candidate_is_advisory_evidence": True,
            "automatic_new_project_conclusion_allowed": False,
            "while_major_change_confirmation_pending": {
                "scope_reconciliation_allowed": False,
                "manifest_advancement_allowed": False,
                "trusted_epoch_replacement_allowed": False,
                "repository_current_claim_allowed": False,
                "independent_activation_graphs_allowed": True,
            },
            "major_change_signals": [
                "primary_entrypoint_family_change",
                "primary_surface_change",
                "high_added_deleted_file_ratio",
                "major_framework_or_dependency_manifest_shift",
                "dominant_project_structure_change",
            ],
        },
        "authority_matrix": _authority_matrix(),
        "command_contract": {
            "future_interface_only": True,
            "implemented_in_this_phase": False,
            "ambiguous_index_command_forbidden": True,
            "commands": _command_contract(),
        },
        "storage_separation": {
            "activation_root": f"{ACTIVATION_STORAGE_ROOT}/<activation_id>/",
            "canonical_root": (
                f"{CANONICAL_STORAGE_ROOT}/<repository_id>/<epoch>/"
            ),
            "activation_cleanup_may_receive_canonical_root": False,
            "required_cleanup_marker": {
                "artifact_kind": ACTIVATION_ARTIFACT_KIND,
                "managed_cleanup_allowed": True,
            },
            "automatic_cleanup_forbidden_path_conditions": [
                "invalid",
                "missing_marker",
                "symlinked",
                "traversal",
                "outside_activation_root",
                "canonical_artifact",
                "unknown_or_unmanaged",
            ],
        },
        "forbidden_interactions": [
            "change_index_repository_behavior",
            "remove_current_web_indexing_call",
            "create_real_activation_graph",
            "wire_production_cli_or_web_route",
            "write_code_index_database",
            "load_or_save_production_manifest",
            "modify_graph_builder",
            "modify_repository_identity",
            "add_background_worker_or_scheduler",
            "delete_graph_artifact",
            "call_model_or_api",
            "run_embedding",
            "run_repository_indexing",
            "modify_benchmark_scoring_or_cases",
            "modify_patch_validation_lesson_dream_commander_or_project_evolution",
        ],
        "next_recommended_phases": [
            "INDEX.1D.2 - Canonical Identity & Trusted Completion",
            "INDEX.1D.3 - Traversal Budget Closure",
            "INDEX.1E - Canonical Delta Execution Wiring",
            "INDEX.1F - Activation Graph Fast Path",
        ],
        "guardrail_note": DUAL_GRAPH_GUARDRAIL_NOTE,
    }


def render_dual_graph_lifecycle_json(contract: Mapping[str, Any]) -> str:
    """Render stable, sorted JSON."""
    return json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_dual_graph_lifecycle_markdown(contract: Mapping[str, Any]) -> str:
    """Render the contract as deterministic operator-facing Markdown."""
    phase = contract["phase"]
    activation = contract["activation_graph"]
    canonical = contract["canonical_incremental_graph"]
    storage = contract["storage_separation"]
    lines = [
        f"# {phase['phase_id']} - {phase['title']}",
        "",
        f"> {contract['guardrail_note']}",
        "",
        "## Architecture",
        "",
        "- Ordinary narrow task -> Direct Context or Activation Graph.",
        "- Explicit repository-intelligence operation -> Canonical Incremental Graph.",
        "- Activation Graph is a disposable context cache.",
        "- Canonical Incremental Graph is a durable repository-intelligence asset.",
        "- The two graph systems never share destructive lifecycle behavior.",
        "",
        "## Graph kinds",
        "",
    ]
    for graph_kind in GRAPH_KINDS:
        details = contract["graph_kinds"][graph_kind]
        lines += [f"### `{graph_kind}`", ""]
        for key in sorted(details):
            lines.append(f"- **{_md(key)}:** {_md(details[key])}")
        lines.append("")

    lines += [
        "## Activation Graph lifecycle",
        "",
        f"- States: {', '.join(f'`{state}`' for state in activation['states'])}.",
        f"- Sliding TTL: {activation['expiry']['ttl_seconds']} seconds from `last_used_at`.",
        "- Exactly at the TTL boundary is expired.",
        "- Metadata viewing and UI polling do not update `last_used_at`.",
        "- Actual retrieval/context reuse may update `last_used_at`.",
        "- Pinned and actively leased records are excluded from automatic cleanup.",
        "- Stale graphs are rebuilt or bounded-refreshed; they are never canonically migrated.",
        "- No continuous background janitor; every cleanup plan is dry-run-first.",
        "",
        "### Allowed transitions",
        "",
    ]
    for state, targets in activation["transitions"].items():
        rendered = ", ".join(f"`{target}`" for target in targets) or "_terminal_"
        lines.append(f"- `{state}` -> {rendered}")

    lines += [
        "",
        "## Activation freshness",
        "",
        "| State | Contract action |",
        "| --- | --- |",
        "| `fresh` | Reuse allowed |",
        "| `partially_changed` | Bounded refresh recommended before reuse |",
        "| `stale` | Rebuild Activation Graph |",
        "| `missing_files` | Rebuild Activation Graph |",
        "| `unknown` | Never claim freshness |",
        "",
        "## Canonical Incremental Graph lifecycle",
        "",
        f"- States: {', '.join(f'`{state}`' for state in canonical['states'])}.",
        "- Initial build and major architecture changes require human confirmation.",
        "- `building -> current` and `refreshing -> current` require trusted completion.",
        "- Major-change signals are advisory evidence, never an automatic new-project decision.",
        "- Pending major-change confirmation blocks reconciliation, manifest advancement, "
        "trusted epoch replacement, and current/completeness claims.",
        "- Activation Graph work may continue independently while confirmation is pending.",
        "",
        "## Authority matrix",
        "",
        "| Capability | Direct Context | Activation Graph | Canonical Graph |",
        "| --- | --- | --- | --- |",
    ]
    for row in contract["authority_matrix"]:
        lines.append(
            "| {capability} | {direct} | {activation} | {canonical} |".format(
                capability=_md(row["capability"]),
                direct=_md(row[GRAPH_KIND_DIRECT_CONTEXT]),
                activation=_md(row[GRAPH_KIND_ACTIVATION]),
                canonical=_md(row[GRAPH_KIND_CANONICAL]),
            )
        )

    lines += [
        "",
        "## Future command contract",
        "",
        "| Command | Graph kind | Temporary mutation | Human confirmation | "
        "Trusted completion | Canonical storage |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for command in contract["command_contract"]["commands"]:
        lines.append(
            "| `{command}` | `{kind}` | {temporary} | {human} | {trusted} | {canonical} |".format(
                command=_md(command["command"]),
                kind=_md(command["graph_kind"]),
                temporary=_md(command["temporary_artifact_mutation"]),
                human=_md(command["human_confirmation_required"]),
                trusted=_md(command["trusted_completion_required"]),
                canonical=_md(command["canonical_storage_allowed"]),
            )
        )

    lines += [
        "",
        "## Storage separation",
        "",
        f"- Activation root: `{storage['activation_root']}`",
        f"- Canonical root: `{storage['canonical_root']}`",
        "- Activation cleanup must never receive the canonical root as a deletion candidate.",
        "- Future cleanup requires both the Activation marker and managed-cleanup flag.",
        "- Invalid, missing-marker, symlinked, traversal, out-of-root, canonical, "
        "and unknown paths are unmanaged and never automatically deleted.",
        "",
        "## Forbidden interactions in INDEX.1D.1",
        "",
    ]
    lines.extend(f"- `{item}`" for item in contract["forbidden_interactions"])
    lines += ["", "## Recommended next phases", ""]
    lines.extend(f"- {item}" for item in contract["next_recommended_phases"])
    return "\n".join(lines) + "\n"
