from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.index_manifest import RepositoryDelta

class EmbeddingCompatibility(str, Enum):
    COMPATIBLE = "compatible"
    SAME_DIMENSION_DRIFT = "same_dimension_drift"
    OFF = "off"
    INCOMPATIBLE_DIMENSION = "incompatible_dimension"
    UNKNOWN = "unknown"

class EmbeddingAction(str, Enum):
    REUSE = "reuse"
    COMPUTE_CHANGED = "compute_changed"
    REEMBED_UNCHANGED = "reembed_unchanged"
    COMPUTE_CHANGED_AND_REEMBED_UNCHANGED = (
        "compute_changed_and_reembed_unchanged"
    )
    DISABLED = "disabled"
    BLOCKED = "blocked"

@dataclass(frozen=True)
class IndexExecutionPlan:
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    unchanged: tuple[str, ...]

    to_parse: tuple[str, ...]
    to_delete: tuple[str, ...]
    to_reembed: tuple[str, ...]
    to_embed: tuple[str, ...]
    to_replace: tuple[str, ...]
    unchanged_noop: tuple[str, ...]

    embedding_action: EmbeddingAction

    force_full_reindex: bool
    reset_index_scope: bool
    force_reindex_reason: str
    blocked_reason: str

    source_state_changed: bool
    persistence_enabled: bool
    identity_execution_allowed: bool
    deletion_execution_allowed: bool
    repository_scope: str
    executable_candidate: bool

def build_index_execution_plan(
    delta: RepositoryDelta,
    *,
    trusted_index_exists: bool,
    database_available: bool,
    embedding_compatibility: EmbeddingCompatibility,
    force_full_reindex: bool = False,
    force_reindex_reason: str = "",
    persistence_enabled: bool | None = None,
    identity_execution_allowed: bool = True,
    deletion_execution_allowed: bool = True,
    repository_scope: str = "",
    descriptive_only: bool = False,
) -> IndexExecutionPlan:
    added = tuple(sorted(delta.added))
    modified = tuple(sorted(delta.modified))
    deleted = tuple(sorted(delta.deleted))
    unchanged = tuple(sorted(delta.unchanged))

    current_files = tuple(
        sorted(set(added) | set(modified) | set(unchanged))
    )

    source_state_changed = bool(
        added or modified or deleted
    )
    persistence_is_enabled = (
        database_available
        if persistence_enabled is None
        else bool(persistence_enabled)
    )
    identity_candidate = bool(identity_execution_allowed)
    deletion_candidate = bool(deletion_execution_allowed)
    scope = str(repository_scope)

    if not database_available and not descriptive_only:
        return IndexExecutionPlan(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            to_parse=(),
            to_delete=(),
            to_reembed=(),
            to_embed=(),
            to_replace=(),
            unchanged_noop=unchanged,
            embedding_action=EmbeddingAction.BLOCKED,
            force_full_reindex=False,
            reset_index_scope=False,
            force_reindex_reason="",
            blocked_reason="database_unavailable",
            source_state_changed=source_state_changed,
            persistence_enabled=persistence_is_enabled,
            identity_execution_allowed=identity_candidate,
            deletion_execution_allowed=deletion_candidate,
            repository_scope=scope,
            executable_candidate=False,
        )

    if embedding_compatibility is EmbeddingCompatibility.UNKNOWN:
        baseline_required = (
            force_full_reindex
            or not trusted_index_exists
        )
        to_parse = (
            current_files
            if baseline_required
            else tuple(sorted(set(added) | set(modified)))
        )
        reason = (
            force_reindex_reason.strip()
            or (
                "explicit_force_reindex"
                if force_full_reindex
                else "trusted_index_missing"
                if not trusted_index_exists
                else ""
            )
        )
        return IndexExecutionPlan(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            to_parse=to_parse,
            to_delete=deleted,
            to_reembed=(),
            # Changed files are embedding/replacement candidates regardless
            # of whether unchanged vectors can be reused. Unknown signature
            # compatibility only blocks claims about unchanged-file reuse.
            to_embed=to_parse,
            to_replace=(
                to_parse if persistence_is_enabled else ()
            ),
            # Source parsing and changed-file replacement are unnecessary for
            # unchanged files. Whether their embeddings can also be reused is
            # explicitly unresolved by the UNKNOWN compatibility status.
            unchanged_noop=unchanged,
            embedding_action=EmbeddingAction.BLOCKED,
            force_full_reindex=baseline_required,
            reset_index_scope=baseline_required,
            force_reindex_reason=reason,
            blocked_reason="embedding_compatibility_unknown",
            source_state_changed=source_state_changed,
            persistence_enabled=persistence_is_enabled,
            identity_execution_allowed=identity_candidate,
            deletion_execution_allowed=deletion_candidate,
            repository_scope=scope,
            executable_candidate=False,
        )

    if (
        embedding_compatibility
        is EmbeddingCompatibility.INCOMPATIBLE_DIMENSION
    ):
        return IndexExecutionPlan(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            to_parse=(),
            to_delete=(),
            to_reembed=(),
            to_embed=(),
            to_replace=(),
            unchanged_noop=unchanged,
            embedding_action=EmbeddingAction.BLOCKED,
            force_full_reindex=False,
            reset_index_scope=False,
            force_reindex_reason="",
            blocked_reason="embedding_dimension_incompatible",
            source_state_changed=source_state_changed,
            persistence_enabled=persistence_is_enabled,
            identity_execution_allowed=identity_candidate,
            deletion_execution_allowed=deletion_candidate,
            repository_scope=scope,
            executable_candidate=False,
        )

    baseline_required = (
        force_full_reindex
        or not trusted_index_exists
    )

    if baseline_required:
        reason = (
            force_reindex_reason.strip()
            or (
                "explicit_force_reindex"
                if force_full_reindex
                else "trusted_index_missing"
            )
        )

        action = (
            EmbeddingAction.DISABLED
            if embedding_compatibility
            is EmbeddingCompatibility.OFF
            else EmbeddingAction.COMPUTE_CHANGED
        )
        to_embed = (
            ()
            if action is EmbeddingAction.DISABLED
            else current_files
        )

        return IndexExecutionPlan(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            to_parse=current_files,
            to_delete=deleted,
            to_reembed=(),
            to_embed=to_embed,
            to_replace=(
                current_files
                if persistence_is_enabled
                else ()
            ),
            unchanged_noop=(),
            embedding_action=action,
            force_full_reindex=True,
            reset_index_scope=True,
            force_reindex_reason=reason,
            blocked_reason="",
            source_state_changed=source_state_changed,
            persistence_enabled=persistence_is_enabled,
            identity_execution_allowed=identity_candidate,
            deletion_execution_allowed=deletion_candidate,
            repository_scope=scope,
            executable_candidate=(
                identity_candidate
                and (not deleted or deletion_candidate)
                and persistence_is_enabled
            ),
        )

    to_parse = tuple(
        sorted(set(added) | set(modified))
    )

    if (
        embedding_compatibility
        is EmbeddingCompatibility.SAME_DIMENSION_DRIFT
    ):
        to_reembed = unchanged

        return IndexExecutionPlan(
            added=added,
            modified=modified,
            deleted=deleted,
            unchanged=unchanged,
            to_parse=to_parse,
            to_delete=deleted,
            to_reembed=to_reembed,
            to_embed=tuple(
                sorted(set(to_parse) | set(to_reembed))
            ),
            to_replace=(
                tuple(sorted(set(to_parse) | set(to_reembed)))
                if persistence_is_enabled
                else ()
            ),
            unchanged_noop=(),
            embedding_action=_select_embedding_action(
                to_parse=to_parse,
                to_reembed=to_reembed,
                embeddings_off=False,
            ),
            force_full_reindex=False,
            reset_index_scope=False,
            force_reindex_reason="",
            blocked_reason="",
            source_state_changed=source_state_changed,
            persistence_enabled=persistence_is_enabled,
            identity_execution_allowed=identity_candidate,
            deletion_execution_allowed=deletion_candidate,
            repository_scope=scope,
            executable_candidate=(
                identity_candidate
                and (not deleted or deletion_candidate)
                and persistence_is_enabled
            ),
        )

    embedding_action = _select_embedding_action(
        to_parse=to_parse,
        to_reembed=(),
        embeddings_off=(
            embedding_compatibility
            is EmbeddingCompatibility.OFF
        ),
    )

    return IndexExecutionPlan(
        added=added,
        modified=modified,
        deleted=deleted,
        unchanged=unchanged,
        to_parse=to_parse,
        to_delete=deleted,
        to_reembed=(),
        to_embed=(
            ()
            if embedding_action is EmbeddingAction.DISABLED
            else to_parse
        ),
        to_replace=(
            to_parse if persistence_is_enabled else ()
        ),
        unchanged_noop=unchanged,
        embedding_action=embedding_action,
        force_full_reindex=False,
        reset_index_scope=False,
        force_reindex_reason="",
        blocked_reason="",
        source_state_changed=source_state_changed,
        persistence_enabled=persistence_is_enabled,
        identity_execution_allowed=identity_candidate,
        deletion_execution_allowed=deletion_candidate,
        repository_scope=scope,
        executable_candidate=(
            identity_candidate
            and (not deleted or deletion_candidate)
            and persistence_is_enabled
        ),
    )

def _select_embedding_action(
    *,
    to_parse: tuple[str, ...],
    to_reembed: tuple[str, ...],
    embeddings_off: bool,
) -> EmbeddingAction:
    if embeddings_off:
        return EmbeddingAction.DISABLED

    if to_parse and to_reembed:
        return (
            EmbeddingAction
            .COMPUTE_CHANGED_AND_REEMBED_UNCHANGED
        )

    if to_reembed:
        return EmbeddingAction.REEMBED_UNCHANGED

    if to_parse:
        return EmbeddingAction.COMPUTE_CHANGED

    return EmbeddingAction.REUSE
