"""INDEX.1E.1 request-scoped shadow delta observation.

This adapter composes the existing manifest classifier and execution planner.
Its outputs are diagnostics only: no value returned here may select, skip, or
dispatch production indexing work.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from core import index_execution, index_manifest
from core.credential_redaction import redact_credentials
from core.index_completion import (
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_EMBEDDED,
    FILE_PERSISTENCE_BLOCKED,
    FILE_PERSISTENCE_EMBEDDING_FAILED,
    FILE_PERSISTENCE_PARSE_FAILED,
    FILE_PERSISTENCE_PENDING,
    FILE_PERSISTENCE_PERSISTED,
    FILE_PERSISTENCE_REPLACEMENT_FAILED,
    PROCESSING_STATUS_PARSE_FAILED,
    PROCESSING_STATUS_PROCESSED,
)
from core.repository_identity import build_repository_identity
from core.repository_identity_state import (
    IDENTITY_STATUS_ARCHIVED,
    IDENTITY_STATUS_BLOCKED,
    IDENTITY_STATUS_CONFIRMED,
    RepositoryIdentityState,
    derive_canonical_identity_permissions,
    load_repository_identity_state,
    validate_repository_identity_state,
)
from core.repository_inventory import (
    RepositoryInventory,
    validate_repository_inventory,
)


SHADOW_SCHEMA_VERSION = 1
SHADOW_MODE = "shadow_only"
MAX_DIAGNOSTIC_PATHS = 200
MAX_WARNING_COUNT = 32
MAX_MESSAGE_LENGTH = 320

STATUS_READY = "ready"
STATUS_READY_WITH_WARNINGS = "ready_with_warnings"
STATUS_COLD_BUILD = "cold_build"
STATUS_MANIFEST_INVALID = "manifest_invalid"
STATUS_IDENTITY_BLOCKED = "identity_blocked"
STATUS_PLANNER_UNAVAILABLE = "planner_unavailable"
STATUS_OBSERVED_MANIFEST_FAILED = "observed_manifest_failed"
STATUS_SHADOW_DISABLED = "shadow_disabled"


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() not in {"0", "false", "no", "off"}


def _bounded_paths(paths: Iterable[str]) -> tuple[list[str], bool]:
    normalized = sorted(
        {
            str(path).replace("\\", "/")
            for path in paths
            if isinstance(path, str) and path
        }
    )
    return normalized[:MAX_DIAGNOSTIC_PATHS], (
        len(normalized) > MAX_DIAGNOSTIC_PATHS
    )


def _safe_message(value: object, *, repo_root: str) -> str:
    try:
        rendered = redact_credentials(value)
    except Exception:
        rendered = "shadow diagnostic unavailable"
    rendered = str(rendered)
    for candidate in {
        repo_root,
        repo_root.replace("\\", "/"),
        repo_root.replace("/", "\\"),
    }:
        if candidate:
            rendered = re.sub(
                re.escape(candidate),
                "<repository>",
                rendered,
                flags=re.IGNORECASE,
            )
    rendered = re.sub(r"[\r\n\t]+", " ", rendered).strip()
    return rendered[:MAX_MESSAGE_LENGTH]


def _warnings(values: Iterable[str]) -> list[str]:
    return sorted(
        {
            str(value)[:MAX_MESSAGE_LENGTH]
            for value in values
            if isinstance(value, str) and value
        }
    )[:MAX_WARNING_COUNT]


def _embedding_compatibility(
    *,
    embedding_enabled: bool,
    manifest_load_status: str,
    previous_signature: index_manifest.EmbeddingSignature | None,
    current_signature: index_manifest.EmbeddingSignature | None,
    evidenced_compatibility: (
        index_execution.EmbeddingCompatibility | None
    ) = None,
) -> tuple[index_execution.EmbeddingCompatibility, str, tuple[str, ...]]:
    if not embedding_enabled:
        return (
            index_execution.EmbeddingCompatibility.OFF,
            "production_embedding_disabled",
            (),
        )

    if isinstance(
        evidenced_compatibility,
        index_execution.EmbeddingCompatibility,
    ) and (
        evidenced_compatibility
        is not index_execution.EmbeddingCompatibility.UNKNOWN
    ):
        return (
            evidenced_compatibility,
            "supplied_signature_evidence",
            (),
        )
    if (
        manifest_load_status == index_manifest.MANIFEST_LOAD_MISSING
        and current_signature is not None
    ):
        return (
            index_execution.EmbeddingCompatibility.COMPATIBLE,
            "cold_build_no_existing_vectors",
            (),
        )
    if previous_signature is None or current_signature is None:
        return (
            index_execution.EmbeddingCompatibility.UNKNOWN,
            "applied_signature_unavailable",
            (
                "embedding_compatibility_unavailable",
                (
                    "current_embedding_signature_unverified"
                    if current_signature is None
                    else "embedding_signature_not_persisted"
                ),
            ),
        )
    if previous_signature.dimension != current_signature.dimension:
        return (
            index_execution.EmbeddingCompatibility.INCOMPATIBLE_DIMENSION,
            "applied_manifest_signature",
            ("embedding_dimension_incompatible",),
        )
    if previous_signature != current_signature:
        return (
            index_execution.EmbeddingCompatibility.SAME_DIMENSION_DRIFT,
            "applied_manifest_signature",
            ("embedding_signature_drift",),
        )
    return (
        index_execution.EmbeddingCompatibility.COMPATIBLE,
        "applied_manifest_signature",
        (),
    )


def _base_shadow(
    *,
    repository_id: str,
    index_scope: str,
    architecture_epoch: int | None,
    identity_status: str,
    persistence_enabled: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "mode": SHADOW_MODE,
        "status": STATUS_READY,
        "authoritative": False,
        "repository_id": repository_id,
        "index_scope": index_scope,
        "architecture_epoch": architecture_epoch,
        "identity_status": identity_status,
        "manifest": {
            "load_status": index_manifest.MANIFEST_LOAD_MISSING,
            "load_reason": "manifest_not_inspected",
            "previous_applied_present": False,
            "artifact_present": False,
            "legacy_binding": False,
            "observed_built": False,
            "policy_changed": False,
            "previous_records_excluded": 0,
            "embedding_signature_status": "not_inspected",
            "baseline_kind": None,
        },
        "identity": {
            "source": "unavailable",
            "valid": False,
            "production_identity_supplied": False,
            "future_execution_allowed": False,
            "future_deletion_allowed": False,
            "production_scope_matches_identity": False,
        },
        "membership": {
            "repository_members": 0,
            "indexable_members": 0,
            "manifest_control_files": 0,
            "non_indexable_retained_metadata": 0,
        },
        "delta": {
            "available": False,
            "added": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "paths_truncated": False,
            "counts": {
                "added": 0,
                "modified": 0,
                "deleted": 0,
                "unchanged": 0,
            },
        },
        "plan": {
            "status": STATUS_PLANNER_UNAVAILABLE,
            "embedding_action": "blocked",
            "embedding_compatibility": "unknown",
            "embedding_compatibility_source": "unavailable",
            "changed_file_actions": 0,
            "parse_actions": 0,
            "embedding_actions": 0,
            "replacement_actions": 0,
            "deleted_file_actions": 0,
            "unchanged_noop_recommendations": 0,
            "full_reembed_required": None,
            "full_reembed_status": "unknown",
            "policy_changed": False,
            "force_full_reindex": False,
            "blocked_reason": "shadow_not_prepared",
            "future_executable_candidate": False,
            "parse_files": [],
            "embedding_files": [],
            "replacement_files": [],
            "deleted_files": [],
            "unchanged_noop_files": [],
            "paths_truncated": False,
        },
        "observed_manifest": {
            "status": "not_started",
            "entries_considered": 0,
            "files_hashed": 0,
            "fingerprints_reused": 0,
            "fingerprints_computed": 0,
            "ignored_entries": 0,
            "invalid_entries": 0,
            "error_category": None,
            "error_message": None,
        },
        "production_execution": {
            "still_full_processing": True,
            "plan_controls_execution": False,
            "manifest_saved": False,
            "manifest_advance_allowed": False,
            "persistence_enabled": bool(persistence_enabled),
            "database_available": None,
            "actual": {
                "parsed_files": 0,
                "embedded_files": 0,
                "replacement_attempts": 0,
                "direct_file_deletions": 0,
                "reconciliation_performed": False,
                "code_units_deleted": 0,
                "dependencies_deleted": 0,
            },
            "comparison": {
                "available": False,
                "matches_shadow_recommendation": None,
                "expected_shadow_only_mismatch": False,
                "shadow_plan_remains_valid": False,
            },
        },
        "warnings": [],
    }


def _identity_observation(
    repo_path: str,
    supplied_state: object,
    production_index_scope: str,
) -> tuple[
    str,
    int | None,
    str,
    bool,
    bool,
    bool,
    str,
    str,
    tuple[str, ...],
]:
    physical_identity = build_repository_identity(repo_path)
    warnings: list[str] = []

    if supplied_state is None:
        loaded = load_repository_identity_state(physical_identity)
        state = loaded.state
        source = (
            "persistent_loaded"
            if loaded.exists
            else "persistent_missing"
        )
        valid = loaded.valid
        if loaded.errors:
            warnings.append("identity_state_load_invalid")
    elif isinstance(supplied_state, RepositoryIdentityState):
        state = supplied_state
        source = "supplied"
        try:
            expected_identity = build_repository_identity(
                repo_path,
                project_tag=state.project_tag,
                architecture_epoch=state.architecture_epoch,
            )
            valid = validate_repository_identity_state(
                state,
                expected_identity=expected_identity,
            ).valid
        except Exception:
            valid = False
    else:
        state = None
        source = "supplied_invalid"
        valid = False
        warnings.append("identity_state_invalid")

    if valid and isinstance(state, RepositoryIdentityState):
        repository_id = state.repository_id
        architecture_epoch = state.architecture_epoch
        index_scope = state.active_index_scope
        identity_status = state.identity_status
        permissions = derive_canonical_identity_permissions(state)
    else:
        repository_id = physical_identity.repository_id
        architecture_epoch = None
        index_scope = physical_identity.index_scope
        identity_status = IDENTITY_STATUS_BLOCKED
        permissions = derive_canonical_identity_permissions(None)

    future_execution_allowed = bool(
        valid
        and identity_status == IDENTITY_STATUS_CONFIRMED
        and (
            permissions.canonical_build_allowed
            or permissions.canonical_refresh_allowed
        )
    )
    future_deletion_allowed = bool(
        future_execution_allowed
        and permissions.reconciliation_allowed
    )
    production_scope_matches = (
        production_index_scope == index_scope
    )
    if not production_scope_matches:
        future_execution_allowed = False
        future_deletion_allowed = False
        warnings.append("production_index_scope_mismatch")
    if identity_status != IDENTITY_STATUS_CONFIRMED:
        warnings.append("identity_confirmation_required")
    if identity_status in {
        IDENTITY_STATUS_ARCHIVED,
        IDENTITY_STATUS_BLOCKED,
    }:
        future_execution_allowed = False
        future_deletion_allowed = False
        warnings.append("identity_state_blocks_future_execution")

    return (
        repository_id,
        architecture_epoch,
        index_scope,
        valid,
        future_execution_allowed,
        future_deletion_allowed,
        source,
        identity_status,
        tuple(warnings),
    )


def build_index_delta_shadow(
    repo_path: str,
    *,
    inventory: RepositoryInventory,
    identity_state: object,
    production_index_scope: str,
    persistence_enabled: bool,
    database_available: bool,
    embedding_enabled: bool,
    index_entries: tuple[tuple[Path, Path], ...] | None = None,
    embedding_compatibility_evidence: (
        index_execution.EmbeddingCompatibility | None
    ) = None,
) -> dict[str, Any]:
    """Build one fail-soft, non-authoritative shadow observation."""
    try:
        root = str(Path(repo_path).expanduser().resolve())
        operation_inventory = validate_repository_inventory(
            root,
            inventory,
        )
        physical_identity = build_repository_identity(root)
    except Exception as exc:
        root = str(repo_path)
        failed = _base_shadow(
            repository_id="",
            index_scope=str(production_index_scope),
            architecture_epoch=None,
            identity_status=IDENTITY_STATUS_BLOCKED,
            persistence_enabled=persistence_enabled,
        )
        failed["status"] = STATUS_OBSERVED_MANIFEST_FAILED
        failed["manifest"]["load_reason"] = _safe_message(
            exc,
            repo_root=root,
        )
        failed["plan"]["blocked_reason"] = "shadow_preparation_failed"
        failed["warnings"] = ["shadow_preparation_failed"]
        return failed

    if not _env_enabled("INDEX_DELTA_SHADOW_ENABLED", True):
        disabled = _base_shadow(
            repository_id=physical_identity.repository_id,
            index_scope=production_index_scope,
            architecture_epoch=None,
            identity_status=IDENTITY_STATUS_BLOCKED,
            persistence_enabled=persistence_enabled,
        )
        disabled["status"] = STATUS_SHADOW_DISABLED
        disabled["plan"]["blocked_reason"] = "shadow_disabled"
        return disabled

    try:
        (
            repository_id,
            architecture_epoch,
            index_scope,
            identity_valid,
            future_execution_allowed,
            future_deletion_allowed,
            identity_source,
            identity_status,
            identity_warnings,
        ) = _identity_observation(
            root,
            identity_state,
            production_index_scope,
        )
        shadow = _base_shadow(
            repository_id=repository_id,
            index_scope=index_scope,
            architecture_epoch=architecture_epoch,
            identity_status=identity_status,
            persistence_enabled=persistence_enabled,
        )
        shadow["production_execution"]["database_available"] = bool(
            database_available
        )
        shadow["identity"] = {
            "source": identity_source,
            "valid": identity_valid,
            "production_identity_supplied": isinstance(
                identity_state,
                RepositoryIdentityState,
            ),
            "future_execution_allowed": future_execution_allowed,
            "future_deletion_allowed": future_deletion_allowed,
            "production_scope_matches_identity": (
                production_index_scope == index_scope
            ),
        }

        canonical_entry_pairs = (
            tuple(index_entries)
            if index_entries is not None
            else operation_inventory.canonical_index_entry_pairs
        )
        control_names = {".gitignore", ".cattusignore"}
        control_count = sum(
            1
            for entry in operation_inventory.entries
            if entry.relative_path.as_posix() in control_names
        )
        shadow["membership"] = {
            "repository_members": len(operation_inventory.entries),
            "indexable_members": len(canonical_entry_pairs),
            "manifest_control_files": control_count,
            "non_indexable_retained_metadata": (
                len(operation_inventory.entries)
                - len(canonical_entry_pairs)
                - control_count
            ),
        }

        load_result = index_manifest.load_repository_manifest_result(
            root,
            repository_id=repository_id,
            architecture_epoch=architecture_epoch,
            index_scope=index_scope,
        )
        shadow["manifest"].update(
            {
                "load_status": load_result.status,
                "load_reason": load_result.reason,
                "previous_applied_present": (
                    load_result.status
                    == index_manifest.MANIFEST_LOAD_LOADED
                ),
                "artifact_present": load_result.present,
                "legacy_binding": load_result.legacy_binding,
                "baseline_kind": (
                    STATUS_COLD_BUILD
                    if load_result.status
                    == index_manifest.MANIFEST_LOAD_MISSING
                    else "previous_applied"
                    if load_result.status
                    == index_manifest.MANIFEST_LOAD_LOADED
                    else None
                ),
            }
        )
        warnings = list(identity_warnings)
        if load_result.legacy_binding:
            warnings.append("legacy_manifest_binding_derived_from_root")

        delta_available = load_result.status in {
            index_manifest.MANIFEST_LOAD_LOADED,
            index_manifest.MANIFEST_LOAD_MISSING,
        }
        previous = (
            load_result.manifest
            if load_result.status
            == index_manifest.MANIFEST_LOAD_LOADED
            else None
        )
        current_embedding_signature = (
            index_manifest.build_current_index_embedding_signature()
            if embedding_enabled
            else None
        )
        try:
            observed, observed_delta = (
                index_manifest.inspect_repository_delta(
                    root,
                    previous=previous if delta_available else None,
                    inventory=operation_inventory,
                    indexable_only=True,
                    repository_id=repository_id,
                    architecture_epoch=architecture_epoch,
                    index_scope=index_scope,
                    index_entries=canonical_entry_pairs,
                    embedding_signature=current_embedding_signature,
                )
            )
            del observed
            shadow["manifest"]["observed_built"] = True
            shadow["manifest"]["previous_records_excluded"] = (
                observed_delta.previous_records_excluded
            )
            if observed_delta.previous_records_excluded:
                warnings.append(
                    "previous_manifest_noncanonical_records_excluded"
                )
            shadow["observed_manifest"].update(
                {
                    "status": "built",
                    "entries_considered": len(
                        canonical_entry_pairs
                    ),
                    "files_hashed": (
                        observed_delta.hashes_computed
                    ),
                    "fingerprints_reused": (
                        observed_delta.hashes_reused
                    ),
                    "fingerprints_computed": (
                        observed_delta.hashes_computed
                    ),
                    "ignored_entries": (
                        len(operation_inventory.indexable_entries)
                        - len(canonical_entry_pairs)
                    ),
                    "invalid_entries": 0,
                }
            )
        except Exception as exc:
            shadow["status"] = STATUS_OBSERVED_MANIFEST_FAILED
            shadow["plan"]["blocked_reason"] = (
                "observed_manifest_failed"
            )
            warnings.append("observed_manifest_failed")
            shadow["warnings"] = _warnings(warnings)
            shadow["observed_manifest"].update(
                {
                    "status": "failed",
                    "entries_considered": len(
                        canonical_entry_pairs
                    ),
                    "ignored_entries": (
                        len(operation_inventory.indexable_entries)
                        - len(canonical_entry_pairs)
                    ),
                    "invalid_entries": 1,
                    "error_category": (
                        "observed_manifest_build_failed"
                    ),
                    "error_message": _safe_message(
                        exc,
                        repo_root=root,
                    ),
                }
            )
            return shadow

        if not delta_available:
            shadow["status"] = STATUS_MANIFEST_INVALID
            shadow["plan"]["blocked_reason"] = "manifest_invalid"
            warnings.append(load_result.reason)
            shadow["warnings"] = _warnings(warnings)
            return shadow

        delta = observed_delta
        delta_paths: dict[str, list[str]] = {}
        truncated = False
        for name in ("added", "modified", "deleted", "unchanged"):
            values, was_truncated = _bounded_paths(
                getattr(delta, name)
            )
            delta_paths[name] = values
            truncated = truncated or was_truncated
        shadow["delta"] = {
            "available": True,
            **delta_paths,
            "paths_truncated": truncated,
            "counts": {
                "added": len(delta.added),
                "modified": len(delta.modified),
                "deleted": len(delta.deleted),
                "unchanged": len(delta.unchanged),
            },
        }
        shadow["manifest"]["policy_changed"] = (
            delta.policy_changed
        )

        compatibility, compatibility_source, embedding_warnings = (
            _embedding_compatibility(
                embedding_enabled=embedding_enabled,
                manifest_load_status=load_result.status,
                previous_signature=(
                    previous.embedding_signature
                    if previous is not None
                    else None
                ),
                current_signature=current_embedding_signature,
                evidenced_compatibility=(
                    embedding_compatibility_evidence
                ),
            )
        )
        warnings.extend(embedding_warnings)
        shadow["manifest"]["embedding_signature_status"] = (
            compatibility_source
        )
        if not persistence_enabled:
            warnings.append("persistence_disabled")
        try:
            plan = index_execution.build_index_execution_plan(
                delta,
                trusted_index_exists=(
                    load_result.status
                    == index_manifest.MANIFEST_LOAD_LOADED
                ),
                database_available=database_available,
                embedding_compatibility=compatibility,
                force_full_reindex=delta.policy_changed,
                force_reindex_reason=(
                    "policy_changed" if delta.policy_changed else ""
                ),
                persistence_enabled=persistence_enabled,
                identity_execution_allowed=future_execution_allowed,
                deletion_execution_allowed=future_deletion_allowed,
                repository_scope=index_scope,
                descriptive_only=True,
            )
        except Exception as exc:
            shadow["status"] = STATUS_PLANNER_UNAVAILABLE
            shadow["plan"].update(
                {
                    "status": STATUS_PLANNER_UNAVAILABLE,
                    "blocked_reason": "planner_failed",
                    "error_category": "planner_failed",
                    "error_message": _safe_message(
                        exc,
                        repo_root=root,
                    ),
                }
            )
            warnings.append("planner_unavailable")
            shadow["warnings"] = _warnings(warnings)
            return shadow
        plan_paths: dict[str, list[str]] = {}
        plan_truncated = False
        for name, paths in (
            ("parse_files", plan.to_parse),
            ("embedding_files", plan.to_embed),
            ("replacement_files", plan.to_replace),
            ("deleted_files", plan.to_delete),
            ("unchanged_noop_files", plan.unchanged_noop),
        ):
            values, was_truncated = _bounded_paths(paths)
            plan_paths[name] = values
            plan_truncated = plan_truncated or was_truncated

        compatibility_unknown = (
            compatibility
            is index_execution.EmbeddingCompatibility.UNKNOWN
        )
        if plan.blocked_reason:
            plan_status = STATUS_PLANNER_UNAVAILABLE
        elif not future_execution_allowed:
            plan_status = STATUS_IDENTITY_BLOCKED
        elif warnings:
            plan_status = STATUS_READY_WITH_WARNINGS
        else:
            plan_status = STATUS_READY
        shadow["plan"] = {
            "status": plan_status,
            "embedding_action": plan.embedding_action.value,
            "embedding_compatibility": compatibility.value,
            "embedding_compatibility_source": (
                compatibility_source
            ),
            "changed_file_actions": len(plan.to_parse),
            "parse_actions": len(plan.to_parse),
            "embedding_actions": len(plan.to_embed),
            "replacement_actions": len(plan.to_replace),
            "deleted_file_actions": len(plan.to_delete),
            "unchanged_noop_recommendations": len(
                plan.unchanged_noop
            ),
            "full_reembed_required": (
                None if compatibility_unknown else bool(plan.to_reembed)
            ),
            "full_reembed_status": (
                "unknown"
                if compatibility_unknown
                else "required"
                if plan.to_reembed
                else "not_required"
            ),
            "policy_changed": delta.policy_changed,
            "force_full_reindex": plan.force_full_reindex,
            "blocked_reason": plan.blocked_reason,
            "future_executable_candidate": (
                plan.executable_candidate
            ),
            **plan_paths,
            "paths_truncated": plan_truncated,
        }

        if plan_status == STATUS_PLANNER_UNAVAILABLE:
            shadow["status"] = STATUS_PLANNER_UNAVAILABLE
        elif plan_status == STATUS_IDENTITY_BLOCKED:
            shadow["status"] = STATUS_IDENTITY_BLOCKED
        elif (
            load_result.status
            == index_manifest.MANIFEST_LOAD_MISSING
        ):
            shadow["status"] = STATUS_COLD_BUILD
        elif warnings:
            shadow["status"] = STATUS_READY_WITH_WARNINGS
        else:
            shadow["status"] = STATUS_READY
        shadow["warnings"] = _warnings(warnings)
        return shadow
    except Exception as exc:
        failed = _base_shadow(
            repository_id=physical_identity.repository_id,
            index_scope=production_index_scope,
            architecture_epoch=None,
            identity_status=IDENTITY_STATUS_BLOCKED,
            persistence_enabled=persistence_enabled,
        )
        failed["status"] = STATUS_OBSERVED_MANIFEST_FAILED
        failed["manifest"]["load_reason"] = _safe_message(
            exc,
            repo_root=root,
        )
        failed["plan"]["blocked_reason"] = "shadow_preparation_failed"
        failed["warnings"] = ["shadow_preparation_failed"]
        return failed


def attach_production_diagnostics(
    shadow: Mapping[str, Any],
    *,
    file_outcomes: Iterable[object],
    reconciliation: Mapping[str, Any],
    database_available: bool | None = None,
    persistence_failure_stage: str | None = None,
) -> dict[str, Any]:
    """Return a copied shadow block with actual full-work counters attached."""
    result = {
        key: value.copy() if isinstance(value, dict) else value
        for key, value in dict(shadow).items()
    }
    result["production_execution"] = dict(
        shadow.get("production_execution", {})
    )
    result["production_execution"]["actual"] = dict(
        result["production_execution"].get("actual", {})
    )
    result["production_execution"]["comparison"] = dict(
        result["production_execution"].get("comparison", {})
    )

    parsed: list[str] = []
    embedded: list[str] = []
    replacements: list[str] = []
    operational_failure = False
    for outcome in tuple(file_outcomes):
        path = getattr(outcome, "file_path", None)
        if not isinstance(path, str):
            continue
        if (
            getattr(outcome, "processing_status", None)
            == PROCESSING_STATUS_PROCESSED
        ):
            parsed.append(path)
        if (
            getattr(outcome, "embedding_status", None)
            == EMBEDDING_STATUS_EMBEDDED
        ):
            embedded.append(path)
        if getattr(outcome, "persistence_status", None) in {
            FILE_PERSISTENCE_PERSISTED,
            FILE_PERSISTENCE_REPLACEMENT_FAILED,
        }:
            replacements.append(path)
        if (
            getattr(outcome, "processing_status", None)
            == PROCESSING_STATUS_PARSE_FAILED
            or getattr(outcome, "embedding_status", None)
            == EMBEDDING_STATUS_FAILED
            or getattr(outcome, "persistence_status", None)
            in {
                FILE_PERSISTENCE_PARSE_FAILED,
                FILE_PERSISTENCE_EMBEDDING_FAILED,
                FILE_PERSISTENCE_REPLACEMENT_FAILED,
                FILE_PERSISTENCE_PENDING,
            }
            or (
                getattr(outcome, "persistence_status", None)
                == FILE_PERSISTENCE_BLOCKED
                and getattr(outcome, "error_category", None)
                != "persistence_disabled"
            )
        ):
            operational_failure = True

    parsed_paths, parsed_truncated = _bounded_paths(parsed)
    embedded_paths, embedded_truncated = _bounded_paths(embedded)
    replacement_paths, replacement_truncated = _bounded_paths(
        replacements
    )
    actual = {
        "parsed_files": len(parsed),
        "embedded_files": len(embedded),
        "replacement_attempts": len(replacements),
        "direct_file_deletions": 0,
        "reconciliation_performed": bool(
            reconciliation.get("performed", False)
        ),
        "code_units_deleted": int(
            reconciliation.get("code_units_deleted", 0) or 0
        ),
        "dependencies_deleted": int(
            reconciliation.get("dependencies_deleted", 0) or 0
        ),
        "parsed_file_paths": parsed_paths,
        "embedded_file_paths": embedded_paths,
        "replacement_file_paths": replacement_paths,
        "paths_truncated": (
            parsed_truncated
            or embedded_truncated
            or replacement_truncated
        ),
    }
    if database_available is not None:
        result["production_execution"]["database_available"] = bool(
            database_available
        )
    reconciliation_failure = str(
        reconciliation.get("skipped_reason", "") or ""
    ).startswith("reconciliation_failed")
    operational_failure = bool(
        operational_failure
        or reconciliation_failure
        or persistence_failure_stage == "initialization"
    )
    plan = shadow.get("plan", {})
    planned_parse = set(plan.get("parse_files", ()))
    planned_embed = set(plan.get("embedding_files", ()))
    planned_replace = set(plan.get("replacement_files", ()))
    planned_delete = set(plan.get("deleted_files", ()))
    comparable = bool(
        shadow.get("delta", {}).get("available", False)
        and plan.get("status") != STATUS_PLANNER_UNAVAILABLE
        and shadow.get("identity", {}).get(
            "production_scope_matches_identity",
            False,
        )
        and not plan.get("paths_truncated", False)
        and not actual["paths_truncated"]
    )
    deletion_path_comparable = not planned_delete
    deletion_strategy_matches = (
        actual["direct_file_deletions"] == 0
        and actual["code_units_deleted"] == 0
        and actual["dependencies_deleted"] == 0
        if deletion_path_comparable
        else None
    )
    action_sets_match = (
        set(parsed) == planned_parse
        and set(embedded) == planned_embed
        and set(replacements) == planned_replace
    )
    matches = (
        False
        if comparable and not action_sets_match
        else bool(deletion_strategy_matches)
        if comparable and deletion_path_comparable
        else None
    )
    expected_mismatch = bool(
        comparable
        and matches is False
    )
    unexpected_divergence = bool(
        comparable
        and operational_failure
    )

    if persistence_failure_stage == "initialization":
        result["status"] = STATUS_PLANNER_UNAVAILABLE
        result["plan"] = dict(result.get("plan", {}))
        result["plan"]["status"] = STATUS_PLANNER_UNAVAILABLE
        result["plan"]["future_executable_candidate"] = False
        result["plan"]["runtime_blocked_reason"] = (
            "database_initialization_failed"
        )
        result["warnings"] = _warnings(
            tuple(result.get("warnings", ()))
            + ("database_initialization_failed",)
        )

    result["production_execution"]["actual"] = actual
    result["production_execution"]["comparison"] = {
        "available": comparable,
        "matches_shadow_recommendation": matches,
        "expected_shadow_only_mismatch": expected_mismatch,
        "unexpected_production_divergence": unexpected_divergence,
        "operational_failure_observed": operational_failure,
        "shadow_plan_remains_valid": (
            True
            if comparable and not operational_failure
            else None
        ),
        "deletion": {
            "planned_files": len(planned_delete),
            "actual_direct_file_deletions": (
                actual["direct_file_deletions"]
            ),
            "reconciliation_performed": (
                actual["reconciliation_performed"]
            ),
            "actual_code_units_deleted": (
                actual["code_units_deleted"]
            ),
            "actual_dependencies_deleted": (
                actual["dependencies_deleted"]
            ),
            "strategy_matches": (
                deletion_strategy_matches
                if comparable
                else None
            ),
            "path_parity_available": bool(
                comparable and deletion_path_comparable
            ),
        },
    }
    if (
        shadow.get("identity", {}).get(
            "production_scope_matches_identity",
            False,
        )
        is False
    ):
        result["production_execution"]["comparison"][
            "unavailable_reason"
        ] = "production_scope_mismatch"
    return result
