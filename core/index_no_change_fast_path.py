"""Pure production gate for the INDEX.1E.2 verified no-change fast path."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.repository_identity_state import (
    RepositoryIdentityState,
    derive_canonical_identity_permissions,
    validate_repository_identity_state,
)


@dataclass(frozen=True)
class NoChangeFastPathDecision:
    eligible: bool
    status: str
    reasons: tuple[str, ...]
    fallback_required: bool
    manifest_valid: bool
    identity_confirmed: bool
    embedding_compatible: bool
    policy_unchanged: bool
    delta_empty: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "status": self.status,
            "reasons": list(self.reasons),
            "fallback_required": self.fallback_required,
            "manifest_valid": self.manifest_valid,
            "identity_confirmed": self.identity_confirmed,
            "embedding_compatible": self.embedding_compatible,
            "policy_unchanged": self.policy_unchanged,
            "delta_empty": self.delta_empty,
        }


def evaluate_no_change_fast_path(
    *,
    identity_state: object,
    manifest_load: Mapping[str, Any],
    delta_shadow: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    embedding_runtime: Mapping[str, Any],
    persistence_mode: Mapping[str, Any],
) -> NoChangeFastPathDecision:
    """Fail closed unless all independently represented evidence agrees."""
    identity = delta_shadow.get("identity", {})
    delta = delta_shadow.get("delta", {})
    counts = delta.get("counts", {})
    status = "eligible"

    structurally_valid_identity = bool(
        isinstance(identity_state, RepositoryIdentityState)
        and validate_repository_identity_state(identity_state).valid
        and type(identity_state.state_revision) is int
        and identity_state.state_revision >= 0
    )
    permissions = derive_canonical_identity_permissions(
        identity_state if structurally_valid_identity else None
    )
    identity_confirmed = bool(
        structurally_valid_identity
        and delta_shadow.get("identity_status") == "confirmed"
        and identity.get("valid") is True
        and identity.get("future_execution_allowed") is True
        and identity.get("production_scope_matches_identity") is True
        and permissions.canonical_refresh_allowed is True
        and delta_shadow.get("repository_id")
        == identity_state.repository_id
        and delta_shadow.get("index_scope")
        == identity_state.active_index_scope
        and delta_shadow.get("architecture_epoch")
        == identity_state.architecture_epoch
    )
    load_status = manifest_load.get("load_status")
    manifest_valid = bool(
        load_status == "loaded"
        and manifest_load.get("previous_applied_present") is True
        and manifest_load.get("observed_built") is True
        and manifest_load.get("previous_records_excluded") == 0
    )
    policy_unchanged = manifest_load.get("policy_changed") is False
    delta_empty = bool(
        delta.get("available") is True
        and all(
            type(counts.get(key)) is int and counts[key] == 0
            for key in ("added", "modified", "deleted")
        )
        and type(counts.get("unchanged")) is int
        and counts["unchanged"] >= 0
    )
    embedding_enabled = embedding_runtime.get("enabled") is True
    compatibility = execution_plan.get("embedding_compatibility")
    embedding_compatible = (
        compatibility == "compatible" if embedding_enabled
        else compatibility == "off"
    )
    evidence_consistent = bool(
        (
            not delta_empty
            or all(
                not delta.get(name)
                for name in ("added", "modified", "deleted")
            )
        )
        and manifest_load.get("policy_changed")
        == execution_plan.get("policy_changed", False)
    )

    if (
        persistence_mode.get("enabled") is not True
        or persistence_mode.get("available") is not True
    ):
        status = "persistence_disabled"
    elif not identity_confirmed:
        status = "identity_blocked"
    elif load_status == "missing":
        status = "manifest_missing"
    elif load_status != "loaded":
        status = (
            "binding_mismatch"
            if load_status
            in {
                "root_mismatch",
                "repository_mismatch",
                "scope_mismatch",
                "epoch_mismatch",
            }
            else "manifest_invalid"
        )
    elif not manifest_valid:
        status = "invalid_evidence"
    elif not evidence_consistent:
        status = "invalid_evidence"
    elif (
        embedding_enabled
        and manifest_load.get("embedding_signature_status")
        == "applied_signature_unavailable"
    ):
        status = "embedding_signature_missing"
    elif (
        execution_plan.get("status") == "planner_unavailable"
        or execution_plan.get("blocked_reason")
    ):
        status = "planner_unavailable"
    elif not embedding_compatible:
        status = "embedding_incompatible"
    elif not policy_unchanged:
        status = "policy_changed"
    elif not delta_empty:
        status = "delta_not_empty"
    elif (
        execution_plan.get("parse_actions") != 0
        or execution_plan.get("replacement_actions") != 0
        or execution_plan.get("deleted_file_actions") != 0
    ):
        status = "invalid_evidence"

    eligible = status == "eligible"
    return NoChangeFastPathDecision(
        eligible=eligible,
        status=status,
        reasons=() if eligible else (status,),
        fallback_required=not eligible,
        manifest_valid=manifest_valid,
        identity_confirmed=identity_confirmed,
        embedding_compatible=embedding_compatible,
        policy_unchanged=policy_unchanged,
        delta_empty=delta_empty,
    )
