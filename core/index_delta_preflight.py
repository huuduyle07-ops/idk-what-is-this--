"""INDEX.1E.0 deterministic delta-integration preflight helpers.

This module is deliberately outside the production indexing call path.  It
normalizes a captured pytest failure set, classifies readiness, and renders
audit artifacts.  It never walks a repository, loads or saves an index
manifest, builds an execution plan, accesses a database, or dispatches
indexing work.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import string
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
PHASE = "INDEX.1E.0"
REPORT_KIND = "index_delta_integration_preflight"

PHASE_STATUS_COMPLETE = "INDEX_1E_0_COMPLETE"
PHASE_STATUS_COMPLETE_WITH_WARNINGS = (
    "INDEX_1E_0_COMPLETE_WITH_WARNINGS"
)
PHASE_STATUS_BLOCKED = "INDEX_1E_0_BLOCKED"

READINESS_READY = "ready"
READINESS_READY_WITH_WARNINGS = "ready_with_warnings"
READINESS_BLOCKED_INDEX = "blocked_by_index_failures"
READINESS_BLOCKED_UNCLASSIFIED = "blocked_by_unclassified_failures"
READINESS_BLOCKED_PREREQUISITE = "blocked_by_missing_prerequisite"
READINESS_BLOCKED_CONTRACT = "blocked_by_contract_mismatch"

READINESS_STATUSES = (
    READINESS_READY,
    READINESS_READY_WITH_WARNINGS,
    READINESS_BLOCKED_INDEX,
    READINESS_BLOCKED_UNCLASSIFIED,
    READINESS_BLOCKED_PREREQUISITE,
    READINESS_BLOCKED_CONTRACT,
)

FAILURE_AUTHORITATIVE_INDEX = "authoritative_index_runtime"
FAILURE_INDEX_ADJACENT = "index_adjacent_contract"
FAILURE_STALE_ROADMAP = "stale_roadmap_expectation"
FAILURE_MISSING_ARTIFACT = "missing_generated_artifact"
FAILURE_MIRROR_OR_HARDENING = "mirror_tunnel_or_hardening"
FAILURE_UNRELATED_PRODUCT = "unrelated_product_feature"
FAILURE_ENVIRONMENT = "environment_or_platform"
FAILURE_THIRD_PARTY = "third_party"
FAILURE_UNCLASSIFIED = "unclassified"

FAILURE_CATEGORIES = (
    FAILURE_AUTHORITATIVE_INDEX,
    FAILURE_INDEX_ADJACENT,
    FAILURE_STALE_ROADMAP,
    FAILURE_MISSING_ARTIFACT,
    FAILURE_MIRROR_OR_HARDENING,
    FAILURE_UNRELATED_PRODUCT,
    FAILURE_ENVIRONMENT,
    FAILURE_THIRD_PARTY,
    FAILURE_UNCLASSIFIED,
)

PREREQUISITE_NAMES = (
    "inventory",
    "identity",
    "identity_state",
    "manifest",
    "delta_classifier",
    "execution_planner",
    "completion",
    "applied_manifest_receipt",
)

GUARDRAIL_KEYS = (
    "production_file_skipping_changed",
    "production_manifest_load_for_dispatch",
    "manifest_saved_or_advanced",
    "db_behavior_changed",
    "reconciliation_changed",
    "activation_graph_runtime_added",
    "background_worker_added",
    "legacy_namespace_migrated",
    "model_api_or_embedding_execution_added",
    "tests_weakened_or_xfailed",
)

RETRIEVAL_DIRECT_SCOPE_PATHS = (
    "core.retriever.search_safe_code_units",
    "core.retriever.search_dependencies",
    "core.retriever.trace_call_chain",
    "core.retriever.retrieve_context",
)

RETRIEVAL_TRANSITIVE_SCOPE_PATHS = (
    "core.retriever.trace_execution_flow",
    "core.retriever.search_global_symbols",
    "core.retriever.pick_seed_symbols",
)

RETRIEVAL_BOUNDARY_PATHS = (
    "core.pipeline.maybe_retrieve_context",
    "core.control_engine.run_control_structured",
    "web.app._run_mode",
)

RETRIEVAL_SCOPE_PATHS = (
    *RETRIEVAL_DIRECT_SCOPE_PATHS,
    *RETRIEVAL_TRANSITIVE_SCOPE_PATHS,
    *RETRIEVAL_BOUNDARY_PATHS,
)

DEFAULT_BASELINE_JSON = (
    Path(".agent")
    / "audits"
    / "index-1e-preflight-known-failures.json"
)
DEFAULT_PREFLIGHT_JSON = (
    Path(".agent")
    / "audits"
    / "index-1e-delta-integration-preflight.json"
)
DEFAULT_BASELINE_MARKDOWN = (
    Path("docs")
    / "audits"
    / "2026-07-28-index-1e-preflight-known-failures.md"
)
DEFAULT_PREFLIGHT_MARKDOWN = (
    Path("docs")
    / "audits"
    / "2026-07-28-index-1e-delta-integration-preflight.md"
)


def _exact_nonnegative_int(value: Any, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonblank text")
    return value.strip()


def _text_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of text values")
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(
            _required_text(item, field=f"{field}[{index}]")
        )
    return sorted(set(normalized))


def _normalize_summary(
    summary: Mapping[str, Any],
    *,
    field: str,
) -> dict[str, int]:
    if not isinstance(summary, Mapping):
        raise ValueError(f"{field} must be an object")
    return {
        key: _exact_nonnegative_int(
            summary.get(key),
            field=f"{field}.{key}",
        )
        for key in ("passed", "skipped", "failed")
    }


def _normalize_diagnostic_output(
    value: Mapping[str, Any] | None,
    *,
    expected_collected: int,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("diagnostic_output must be an object")
    digest = _required_text(
        value.get("sha256"),
        field="diagnostic_output.sha256",
    ).lower()
    if (
        len(digest) != 64
        or any(character not in string.hexdigits for character in digest)
    ):
        raise ValueError(
            "diagnostic_output.sha256 must be a 64-character hex digest"
        )
    duration = value.get("duration_seconds")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise ValueError(
            "diagnostic_output.duration_seconds must be finite and "
            "non-negative"
        )
    collected = _exact_nonnegative_int(
        value.get("collected"),
        field="diagnostic_output.collected",
    )
    if collected != expected_collected:
        raise ValueError(
            "diagnostic_output.collected does not match the summary totals"
        )
    return {
        "path": _required_text(
            value.get("path"),
            field="diagnostic_output.path",
        ).replace("\\", "/"),
        "sha256": digest,
        "exit_code": _exact_nonnegative_int(
            value.get("exit_code"),
            field="diagnostic_output.exit_code",
        ),
        "duration_seconds": duration,
        "collected": collected,
        "warnings": _exact_nonnegative_int(
            value.get("warnings"),
            field="diagnostic_output.warnings",
        ),
        "python_version": _required_text(
            value.get("python_version"),
            field="diagnostic_output.python_version",
        ),
        "pytest_version": _required_text(
            value.get("pytest_version"),
            field="diagnostic_output.pytest_version",
        ),
    }


def _normalize_failure(
    failure: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(failure, Mapping):
        raise ValueError("every known failure must be an object")
    node_id = _required_text(
        failure.get("node_id"),
        field="known_failure.node_id",
    )
    category = _required_text(
        failure.get("category"),
        field=f"known_failure[{node_id}].category",
    )
    if category not in FAILURE_CATEGORIES:
        raise ValueError(
            f"known_failure[{node_id}].category is not stable: "
            f"{category!r}"
        )
    intersection = failure.get("index_path_intersection")
    if type(intersection) is not bool:
        raise ValueError(
            f"known_failure[{node_id}].index_path_intersection "
            "must be a boolean"
        )
    if (
        category
        in {FAILURE_AUTHORITATIVE_INDEX, FAILURE_INDEX_ADJACENT}
        and not intersection
    ):
        raise ValueError(
            f"known_failure[{node_id}] is INDEX-classified but marked "
            "as non-intersecting"
        )
    if (
        category
        not in {FAILURE_AUTHORITATIVE_INDEX, FAILURE_INDEX_ADJACENT}
        and intersection
    ):
        raise ValueError(
            f"known_failure[{node_id}] intersects INDEX but has "
            f"non-INDEX category {category!r}"
        )
    return {
        "node_id": node_id,
        "category": category,
        "index_path_intersection": intersection,
        "reason": _required_text(
            failure.get("reason"),
            field=f"known_failure[{node_id}].reason",
        ),
        "evidence": _text_list(
            failure.get("evidence", []),
            field=f"known_failure[{node_id}].evidence",
        ),
    }


def _failure_set_digest(
    failures: Iterable[Mapping[str, Any]],
) -> str:
    stable = [
        {
            "node_id": item["node_id"],
            "category": item["category"],
            "index_path_intersection": item[
                "index_path_intersection"
            ],
        }
        for item in failures
    ]
    encoded = json.dumps(
        stable,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _baseline_comparison(
    *,
    observed_summary: Mapping[str, int],
    reported_summary: Mapping[str, int] | None,
    reported_node_ids: Iterable[str] | None,
    observed_node_ids: Iterable[str],
) -> dict[str, Any]:
    if reported_summary is None:
        return {
            "reported_baseline_available": False,
            "summary_matches": None,
            "passed_delta": None,
            "skipped_delta": None,
            "failed_delta": None,
            "node_id_comparison": "unavailable",
            "added_node_ids": None,
            "removed_node_ids": None,
            "changed_node_ids": None,
            "unchanged_node_ids": None,
            "note": "No earlier machine-readable baseline was available.",
        }

    prior = _normalize_summary(
        reported_summary,
        field="reported_baseline.summary",
    )
    deltas = {
        f"{key}_delta": observed_summary[key] - prior[key]
        for key in ("passed", "skipped", "failed")
    }
    summary_matches = all(value == 0 for value in deltas.values())
    if reported_node_ids is None:
        return {
            "reported_baseline_available": True,
            "summary_matches": summary_matches,
            **deltas,
            "node_id_comparison": "unavailable",
            "added_node_ids": None,
            "removed_node_ids": None,
            "changed_node_ids": None,
            "unchanged_node_ids": None,
            "note": (
                "The earlier diagnostic supplied aggregate totals only; "
                "additions, removals, and renamed node IDs cannot be "
                "reconstructed honestly."
            ),
        }

    prior_ids = {
        _required_text(value, field="reported_baseline.node_id")
        for value in reported_node_ids
    }
    current_ids = set(observed_node_ids)
    return {
        "reported_baseline_available": True,
        "summary_matches": summary_matches,
        **deltas,
        "node_id_comparison": "available",
        "added_node_ids": sorted(current_ids - prior_ids),
        "removed_node_ids": sorted(prior_ids - current_ids),
        "changed_node_ids": [],
        "unchanged_node_ids": sorted(current_ids & prior_ids),
        "note": "Node IDs were compared as exact pytest node IDs.",
    }


def build_known_failure_baseline(
    *,
    command: str,
    collection_timestamp: str,
    worktree_state: Mapping[str, Any],
    summary: Mapping[str, Any],
    known_failures: Iterable[Mapping[str, Any]],
    reported_summary: Mapping[str, Any] | None = None,
    reported_node_ids: Iterable[str] | None = None,
    diagnostic_output: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate the deterministic repository failure baseline."""
    normalized_summary = _normalize_summary(
        summary,
        field="summary",
    )
    if not isinstance(worktree_state, Mapping):
        raise ValueError("worktree_state must be an object")
    dirty = worktree_state.get("dirty")
    if type(dirty) is not bool:
        raise ValueError("worktree_state.dirty must be a boolean")

    normalized_failures = sorted(
        (_normalize_failure(item) for item in known_failures),
        key=lambda item: item["node_id"],
    )
    node_ids = [item["node_id"] for item in normalized_failures]
    duplicates = sorted(
        node_id
        for node_id, count in Counter(node_ids).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            "duplicate known-failure node IDs: "
            + ", ".join(duplicates)
        )
    if normalized_summary["failed"] != len(normalized_failures):
        raise ValueError(
            "summary.failed does not match the known-failure record count"
        )

    categories = Counter(
        item["category"] for item in normalized_failures
    )
    authoritative = categories[FAILURE_AUTHORITATIVE_INDEX]
    adjacent = categories[FAILURE_INDEX_ADJACENT]
    unclassified = categories[FAILURE_UNCLASSIFIED]
    unrelated = (
        len(normalized_failures)
        - authoritative
        - adjacent
        - unclassified
    )
    reported: dict[str, Any] | None = None
    if reported_summary is not None:
        reported = {
            "summary": _normalize_summary(
                reported_summary,
                field="reported_baseline.summary",
            ),
            "node_ids_available": reported_node_ids is not None,
        }
        if reported_node_ids is not None:
            reported["node_ids"] = sorted(
                {
                    _required_text(
                        value,
                        field="reported_baseline.node_id",
                    )
                    for value in reported_node_ids
                }
            )

    result = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "command": _required_text(command, field="command"),
        "collection_timestamp": _required_text(
            collection_timestamp,
            field="collection_timestamp",
        ),
        "worktree_state": {
            "commit": _required_text(
                worktree_state.get("commit"),
                field="worktree_state.commit",
            ),
            "dirty": dirty,
        },
        "summary": normalized_summary,
        "reported_baseline": reported,
        "comparison": _baseline_comparison(
            observed_summary=normalized_summary,
            reported_summary=reported_summary,
            reported_node_ids=reported_node_ids,
            observed_node_ids=node_ids,
        ),
        "failure_set_digest": _failure_set_digest(
            normalized_failures
        ),
        "known_failures": normalized_failures,
        "failure_category_counts": {
            category: categories[category]
            for category in FAILURE_CATEGORIES
        },
        "index_intersection_summary": {
            "authoritative_index_failures": authoritative,
            "index_adjacent_failures": adjacent,
            "unrelated_failures": unrelated,
            "unclassified_failures": unclassified,
        },
    }
    normalized_diagnostic = _normalize_diagnostic_output(
        diagnostic_output,
        expected_collected=sum(normalized_summary.values()),
    )
    if normalized_diagnostic is not None:
        result["diagnostic_output"] = normalized_diagnostic
    return result


def normalize_known_failure_baseline(
    baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild a loaded baseline and reject inconsistent derived totals."""
    if not isinstance(baseline, Mapping):
        raise ValueError("known-failure baseline must be an object")
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("known-failure baseline schema_version mismatch")
    if baseline.get("phase") != PHASE:
        raise ValueError("known-failure baseline phase mismatch")
    reported = baseline.get("reported_baseline")
    reported_summary = (
        reported.get("summary")
        if isinstance(reported, Mapping)
        else None
    )
    reported_node_ids = (
        reported.get("node_ids")
        if (
            isinstance(reported, Mapping)
            and reported.get("node_ids_available") is True
        )
        else None
    )
    normalized = build_known_failure_baseline(
        command=baseline.get("command"),
        collection_timestamp=baseline.get("collection_timestamp"),
        worktree_state=baseline.get("worktree_state"),
        summary=baseline.get("summary"),
        known_failures=baseline.get("known_failures", ()),
        reported_summary=reported_summary,
        reported_node_ids=reported_node_ids,
        diagnostic_output=baseline.get("diagnostic_output"),
    )
    for derived_field in (
        "comparison",
        "failure_set_digest",
        "failure_category_counts",
        "index_intersection_summary",
    ):
        if baseline.get(derived_field) != normalized[derived_field]:
            raise ValueError(
                f"known-failure baseline has stale {derived_field}"
            )
    return normalized


def default_prerequisite_audit() -> dict[str, dict[str, Any]]:
    """Return the frozen INDEX.1D reachability findings."""
    return {
        "inventory": {
            "status": "ready",
            "symbols": [
                "core.repository_inventory.RepositoryInventory",
                "core.repository_inventory.create_repository_inventory",
                "core.repository_inventory.validate_repository_inventory",
            ],
            "evidence": (
                "index_repository owns one immutable operation inventory; "
                "a supplied inventory is root-validated and adds no walk"
            ),
        },
        "identity": {
            "status": "ready",
            "symbols": [
                "core.repository_identity.build_repository_identity",
                "core.repository_identity.build_code_index_scope",
            ],
            "evidence": (
                "canonical_root, repository_id, storage key, and strict "
                "index_scope are path-derived; project_tag is semantic only"
            ),
        },
        "identity_state": {
            "status": "ready",
            "symbols": [
                (
                    "core.repository_identity_state."
                    "load_repository_identity_state"
                ),
                (
                    "core.repository_identity_state."
                    "derive_canonical_identity_permissions"
                ),
            ],
            "evidence": (
                "identity status, architecture epoch, state revision, "
                "active scope, and mutation/reconciliation/manifest "
                "permissions are available without auto-confirmation"
            ),
        },
        "manifest": {
            "status": "ready",
            "symbols": [
                "core.index_manifest.load_repository_manifest",
                "core.index_manifest.inspect_repository_delta",
                "core.index_manifest.save_repository_manifest",
            ],
            "evidence": (
                "stable path and root/schema/policy validation exist; "
                "inspection reuses metadata/SHA evidence and returns an "
                "observed manifest without saving it"
            ),
            "integration_gap": (
                "delta inspection currently fingerprints default inventory "
                "membership, which is broader than indexable membership"
            ),
        },
        "delta_classifier": {
            "status": "ready",
            "symbols": [
                "core.index_manifest.RepositoryDelta",
                "core.index_manifest.inspect_repository_delta",
            ],
            "evidence": (
                "added, modified, deleted, unchanged, hash reuse, and "
                "policy-change classification are represented"
            ),
        },
        "execution_planner": {
            "status": "ready",
            "symbols": [
                "core.index_execution.IndexExecutionPlan",
                "core.index_execution.build_index_execution_plan",
            ],
            "evidence": (
                "pure planning covers database availability, embedding off, "
                "same-dimension drift, incompatible dimensions, changed "
                "files, deletion, and full-baseline/reset cases"
            ),
            "integration_gap": (
                "production has no authoritative adapter for "
                "trusted_index_exists or EmbeddingCompatibility, and the "
                "planner does not carry RepositoryDelta.policy_changed"
            ),
        },
        "completion": {
            "status": "ready",
            "symbols": [
                "core.index_completion.classify_index_completion",
                "core.index_completion.may_advance_applied_manifest",
            ],
            "evidence": (
                "processing, per-file persistence, reconciliation, trusted "
                "completion, and manifest-advance eligibility are distinct"
            ),
        },
        "applied_manifest_receipt": {
            "status": "ready",
            "symbols": [
                "core.index_completion.AppliedManifestEvidence",
                (
                    "core.index_completion."
                    "may_claim_repository_intelligence_current"
                ),
            ],
            "evidence": (
                "the pure current-claim gate requires matching committed "
                "run, repository, epoch, scope, revision, and state IDs"
            ),
            "integration_gap": (
                "no production observed-state ID generator or successful "
                "manifest-save-to-AppliedManifestEvidence receipt builder "
                "exists yet"
            ),
        },
    }


def default_contract_mismatches() -> list[str]:
    """Return current contradictions that block starting delta dispatch."""
    return [
        (
            "retriever_epoch_scope_mismatch: core.retriever._index_scope_for "
            "ignores a supplied architecture-epoch scope whenever repo_path "
            "is valid, so an epoch writer and ordinary retrieval resolve "
            "different scopes"
        ),
        (
            "empty_repository_deletion_gap: index_repository rejects a "
            "repository with zero indexable files before a delta can delete "
            "previous rows, and canonical reconciliation also rejects an "
            "empty current_files set"
        ),
    ]


def default_deferred_integration_requirements() -> list[str]:
    """Return seam work intentionally owned by the future INDEX.1E.1."""
    return [
        (
            "identity_authority_is_post_hoc: index_repository derives and "
            "mutates the baseline path scope before identity permissions are "
            "classified, so confirmed epoch authority cannot safely control "
            "current writes or reconciliation"
        ),
        (
            "manifest_indexable_membership_mismatch: delta inspection "
            "fingerprints default inventory entries while production parses "
            "inventory.indexable_entries; a raw plan may put non-indexable "
            "paths such as .gitignore into to_parse"
        ),
        (
            "planner_input_adapter_missing: production has no trustworthy "
            "derivation for trusted_index_exists or EmbeddingCompatibility"
        ),
        (
            "planner_policy_change_gap: RepositoryDelta.policy_changed is "
            "not represented by IndexExecutionPlan or source_state_changed"
        ),
        (
            "applied_receipt_bridge_missing: no production observed_state_id "
            "generator or successful manifest-save receipt builder binds "
            "repository, epoch, scope, revision, run, and applied state"
        ),
        (
            "typed_completion_gate_boundary: the manifest-advance gate "
            "requires the in-process IndexCompletionDecision, but "
            "index_repository exposes only its serialized dictionary"
        ),
        (
            "incremental_auxiliary_coupling: the per-file parse loop also "
            "builds the full summaries used by Project Map and Phantom Limb; "
            "filtering it directly would make auxiliary outputs partial"
        ),
    ]


def classify_readiness(
    *,
    baseline: Mapping[str, Any],
    prerequisites: Mapping[str, Mapping[str, Any]],
    warnings: Iterable[str] = (),
    contract_mismatches: Iterable[str] = (),
) -> dict[str, Any]:
    """Return the stable fail-closed INDEX.1E.0 readiness decision."""
    normalized = normalize_known_failure_baseline(baseline)
    intersection = normalized["index_intersection_summary"]
    warning_list = sorted(
        {
            _required_text(value, field="warning")
            for value in warnings
        }
    )
    mismatches = sorted(
        {
            _required_text(value, field="contract_mismatch")
            for value in contract_mismatches
        }
    )
    missing = sorted(
        name
        for name in PREREQUISITE_NAMES
        if (
            name not in prerequisites
            or prerequisites[name].get("status") != "ready"
        )
    )

    if (
        intersection["authoritative_index_failures"] > 0
        or intersection["index_adjacent_failures"] > 0
    ):
        status = READINESS_BLOCKED_INDEX
    elif intersection["unclassified_failures"] > 0:
        status = READINESS_BLOCKED_UNCLASSIFIED
    elif missing:
        status = READINESS_BLOCKED_PREREQUISITE
    elif mismatches:
        status = READINESS_BLOCKED_CONTRACT
    elif warning_list:
        status = READINESS_READY_WITH_WARNINGS
    else:
        status = READINESS_READY

    next_phase_allowed = status in {
        READINESS_READY,
        READINESS_READY_WITH_WARNINGS,
    }
    return {
        "status": status,
        "phase_status": (
            PHASE_STATUS_COMPLETE
            if status == READINESS_READY
            else (
                PHASE_STATUS_COMPLETE_WITH_WARNINGS
                if status == READINESS_READY_WITH_WARNINGS
                else PHASE_STATUS_BLOCKED
            )
        ),
        "index_runtime_failures": (
            intersection["authoritative_index_failures"]
        ),
        "index_adjacent_failures": (
            intersection["index_adjacent_failures"]
        ),
        "unclassified_failures": (
            intersection["unclassified_failures"]
        ),
        "prerequisites": {
            name: (
                prerequisites[name].get("status", "missing")
                if name in prerequisites
                else "missing"
            )
            for name in PREREQUISITE_NAMES
        },
        "missing_prerequisites": missing,
        "contract_mismatches": mismatches,
        "production_behavior": "full_reprocessing_characterized",
        "next_phase_allowed": next_phase_allowed,
        "warnings": warning_list,
    }


def _production_entrypoints() -> list[dict[str, Any]]:
    common_no_delta = {
        "manifest_load_behavior": "none",
        "delta_planner_behavior": "not called",
        "result_compatibility_expectations": (
            "existing fields remain; completion metadata is additive"
        ),
    }
    return [
        {
            "caller": "core.indexer.index_repository",
            "mode_or_trigger": (
                "authoritative synchronous canonical indexing operation"
            ),
            "inventory_source": (
                "validates a supplied RepositoryInventory or creates one"
            ),
            "identity_source": (
                "canonical path-derived index_scope; optional identity_state "
                "is consumed only by completion classification"
            ),
            "project_tag_behavior": (
                "optional semantic display metadata; never DB authority"
            ),
            "index_scope_source": (
                "core.repository_identity.build_code_index_scope(repo_path)"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "full per-file replacement followed by one scope "
                "reconciliation when persistence remains healthy"
            ),
            "completion_metadata_consumption": (
                "returns additive result['completion']; does not commit a "
                "manifest or assert a trusted-current claim"
            ),
        },
        {
            "caller": "web.runner.run_agent_web",
            "mode_or_trigger": (
                "automatic inline indexing for project-directory requests "
                "that reach the full web execution path"
            ),
            "inventory_source": (
                "creates one inventory at the request boundary and supplies "
                "it to index_repository and downstream consumers"
            ),
            "identity_source": (
                "does not load or pass confirmed identity state"
            ),
            "project_tag_behavior": (
                "build_project_tag produces semantic metadata only"
            ),
            "index_scope_source": (
                "index_repository derives scope from the repository path"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits synchronous full replacement/reconciliation"
            ),
            "completion_metadata_consumption": (
                "completion is not copied to the current web/session payload"
            ),
        },
        {
            "caller": "cli.interactive.create_agent_state",
            "mode_or_trigger": (
                "automatic indexing when the interactive input is one "
                "project directory"
            ),
            "inventory_source": (
                "index_repository creates the operation inventory"
            ),
            "identity_source": "does not load or pass identity state",
            "project_tag_behavior": (
                "passes a semantic project tag; it is not authority"
            ),
            "index_scope_source": (
                "index_repository derives scope from the repository path"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits full replacement/reconciliation"
            ),
            "completion_metadata_consumption": (
                "legacy flow consumes phantom-limb data, not completion"
            ),
        },
        {
            "caller": "main.main --index",
            "mode_or_trigger": "explicit command-line --index mode",
            "inventory_source": (
                "index_repository creates the operation inventory"
            ),
            "identity_source": "does not load or pass identity state",
            "project_tag_behavior": "none by default",
            "index_scope_source": (
                "index_repository derives scope from the repository path"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits full replacement/reconciliation"
            ),
            "completion_metadata_consumption": "return value is ignored",
        },
        {
            "caller": "core.indexer.__main__",
            "mode_or_trigger": "direct module/script invocation",
            "inventory_source": (
                "index_repository creates the operation inventory"
            ),
            "identity_source": "does not load or pass identity state",
            "project_tag_behavior": "none by default",
            "index_scope_source": (
                "index_repository derives scope from the repository path"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits full replacement/reconciliation"
            ),
            "completion_metadata_consumption": "return value is ignored",
        },
        {
            "caller": "web.app.index (POST /, full mode)",
            "mode_or_trigger": (
                "form submission selects full mode, then _run_mode calls "
                "web.runner.run_agent_web"
            ),
            "inventory_source": (
                "the web runner creates one request inventory and forwards "
                "it to index_repository and downstream consumers"
            ),
            "identity_source": (
                "the route creates a semantic project tag but does not load "
                "confirmed identity state"
            ),
            "project_tag_behavior": (
                "semantic display metadata only; never DB authority"
            ),
            "index_scope_source": (
                "index_repository derives scope from the repository path"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits synchronous full replacement/reconciliation"
            ),
            "completion_metadata_consumption": (
                "the current session payload does not retain completion"
            ),
        },
        {
            "caller": "benchmarks.run_benchmarks.main (run mode)",
            "mode_or_trigger": (
                "normal benchmark execution reaches run_agent_web through "
                "_run_case_with_capture; --check performs no agent call"
            ),
            "inventory_source": (
                "run_agent_web creates one inventory for each benchmark "
                "case repository"
            ),
            "identity_source": (
                "does not load or pass confirmed identity state"
            ),
            "project_tag_behavior": (
                "case-level semantic metadata only"
            ),
            "index_scope_source": (
                "index_repository derives scope from each case repository"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits full replacement/reconciliation per executed case"
            ),
            "completion_metadata_consumption": (
                "benchmark scoring consumes the broader web result, not an "
                "applied-manifest receipt"
            ),
        },
        {
            "caller": "web.app.benchmarks_run_route (POST /benchmarks/run)",
            "mode_or_trigger": (
                "starts the existing benchmark worker; each selected case "
                "reaches run_agent_web through core.benchmark_web"
            ),
            "inventory_source": (
                "run_agent_web creates one inventory for each benchmark "
                "case repository"
            ),
            "identity_source": (
                "does not load or pass confirmed identity state"
            ),
            "project_tag_behavior": (
                "case-level semantic metadata only"
            ),
            "index_scope_source": (
                "index_repository derives scope from each case repository"
            ),
            **common_no_delta,
            "db_persistence_behavior": (
                "inherits full replacement/reconciliation per executed case"
            ),
            "completion_metadata_consumption": (
                "benchmark reports do not establish trusted-current state"
            ),
        },
    ]


def _current_behavior() -> dict[str, Any]:
    counters = {
        "repository_walks": 1,
        "content_reads": 3,
        "parsed_files": 3,
        "graph_parsed_files": 3,
        "embedded_files": 3,
        "replacement_calls": 3,
        "deletion_calls": 0,
        "manifest_loads": 0,
        "manifests_saved": 0,
        "delta_plans_built": 0,
        "reconciliation_calls": 1,
    }
    return {
        "fixture": (
            "three deterministic Python files; counting fakes for DB, "
            "embedding, and parsing; no network or real database"
        ),
        "run_a": deepcopy(counters),
        "run_b": deepcopy(counters),
        "conclusion": (
            "an unchanged second run repeats all current processing, "
            "embedding, and replacement work"
        ),
        "characterization_test": (
            "tests/test_index_production_readiness_audit.py"
        ),
    }


def build_index_delta_preflight(
    baseline: Mapping[str, Any],
    *,
    prerequisites: Mapping[str, Mapping[str, Any]] | None = None,
    warnings: Iterable[str] | None = None,
    contract_mismatches: Iterable[str] | None = None,
    deferred_integration_requirements: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build the frozen INDEX.1E.0 production-integration preflight."""
    known = normalize_known_failure_baseline(baseline)
    prerequisite_audit = deepcopy(
        prerequisites
        if prerequisites is not None
        else default_prerequisite_audit()
    )
    unrelated_count = known["index_intersection_summary"][
        "unrelated_failures"
    ]
    default_warnings = [
        (
            "Current direct, CLI, and web callers do not load and enforce "
            "confirmed identity permissions before canonical mutations; "
            "that dispatcher wiring is deferred to INDEX.1E.1."
        ),
        (
            "The web request keeps canonical indexing synchronous and does "
            "not expose completion metadata in its session payload."
        ),
    ]
    if unrelated_count:
        default_warnings.append(
            f"{unrelated_count} pre-existing proven-unrelated "
            "repository-wide failures remain frozen in the baseline."
        )
    warning_values = (
        default_warnings if warnings is None else list(warnings)
    )
    mismatch_values = (
        default_contract_mismatches()
        if contract_mismatches is None
        else list(contract_mismatches)
    )
    deferred_requirement_values = _text_list(
        (
            default_deferred_integration_requirements()
            if deferred_integration_requirements is None
            else list(deferred_integration_requirements)
        ),
        field="deferred_integration_requirements",
    )
    readiness = classify_readiness(
        baseline=known,
        prerequisites=prerequisite_audit,
        warnings=warning_values,
        contract_mismatches=mismatch_values,
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "phase": PHASE,
        "collection_timestamp": known["collection_timestamp"],
        "worktree_state": deepcopy(known["worktree_state"]),
        "known_failure_baseline": {
            "path": DEFAULT_BASELINE_JSON.as_posix(),
            "command": known["command"],
            "summary": deepcopy(known["summary"]),
            "reported_baseline": deepcopy(
                known["reported_baseline"]
            ),
            "comparison": deepcopy(known["comparison"]),
            "failure_set_digest": known["failure_set_digest"],
            "failure_category_counts": deepcopy(
                known["failure_category_counts"]
            ),
            "index_intersection_summary": deepcopy(
                known["index_intersection_summary"]
            ),
            **(
                {
                    "diagnostic_output": deepcopy(
                        known["diagnostic_output"]
                    )
                }
                if "diagnostic_output" in known
                else {}
            ),
        },
        "production_entrypoints": _production_entrypoints(),
        "retrieval_scope": {
            "writer": (
                "database.code_index requires a strict canonical "
                "index_scope for replacement, deletion, and reconciliation"
            ),
            "retriever": (
                "core.retriever derives the same path-based scope or "
                "validates an explicit strict index_scope"
            ),
            "retrieval_paths": list(RETRIEVAL_SCOPE_PATHS),
            "direct_scope_resolvers": list(
                RETRIEVAL_DIRECT_SCOPE_PATHS
            ),
            "transitive_consumers": list(
                RETRIEVAL_TRANSITIVE_SCOPE_PATHS
            ),
            "production_boundaries": list(RETRIEVAL_BOUNDARY_PATHS),
            "baseline_scope_compatible": True,
            "architecture_epoch_scope_compatible": False,
            "compatible": False,
            "project_tag_is_authority": False,
            "blocking_reason": (
                "_index_scope_for(repo_path, explicit_epoch_scope) ignores "
                "the validated epoch scope, while trace_execution_flow, "
                "search_global_symbols, and current production retrieval "
                "boundaries do not load or propagate an active epoch scope"
            ),
        },
        "current_production_behavior": _current_behavior(),
        "prerequisite_reachability": prerequisite_audit,
        "integration_seams": [
            {
                "module": "core.indexer",
                "function": "index_repository",
                "location": (
                    "after shared operation_inventory acquisition and "
                    "confirmed identity-permission validation, before DB "
                    "initialization and the repo_entries processing loop"
                ),
                "owns_shared_inventory": True,
                "uses_confirmed_identity_permissions": True,
                "derives_authority_from_project_tag": False,
                "reused_objects": [
                    "RepositoryInventory",
                    "RepositoryIdentityState and derived permissions",
                    "RepositoryManifest and RepositoryDelta",
                    "IndexExecutionPlan",
                    "IndexCompletionDecision",
                    "AppliedManifestEvidence",
                ],
                "observed_vs_applied": (
                    "inspect_repository_delta builds observed state; only "
                    "a separately gated successful commit may become applied"
                ),
                "future_controlled_loops": [
                    (
                        "a decoupled canonical parse/embed/replace dispatcher "
                        "will consume translated indexable plan.to_parse"
                    ),
                    (
                        "file deletion will consume plan.to_delete before "
                        "the existing authoritative reconciliation"
                    ),
                ],
                "legacy_fallback": (
                    "missing or unusable applied state must fail closed or "
                    "use an explicitly characterized full-refresh path"
                ),
                "additive_result_metadata": [
                    "delta summary",
                    "execution-plan summary",
                    "applied-manifest receipt/current-claim decision",
                ],
                "actual_dispatch_deferred": True,
            }
        ],
        "blocking_contract_mismatches": list(
            readiness["contract_mismatches"]
        ),
        "deferred_integration_requirements": (
            deferred_requirement_values
        ),
        "integration_contract_gaps": sorted(
            set(readiness["contract_mismatches"])
            | set(deferred_requirement_values)
        ),
        "db_disabled_behavior": {
            "processing_can_succeed": True,
            "persistent_canonical_indexing_succeeded": False,
            "completion_status": "persistence_disabled",
            "trusted_completion": False,
            "manifest_advance_allowed": False,
            "trusted_current_claim_allowed": False,
            "fake_applied_state_claim": False,
            "label": "processing-only / persistence-disabled",
        },
        "web_request_boundary": {
            "invocation": (
                "web.runner.run_agent_web full-mode project-input branch "
                "calls index_repository inline"
            ),
            "identity_confirmation_enforced": False,
            "completion_metadata_reaches_payload": False,
            "credential_redaction_preserved": True,
            "shared_inventory": True,
            "latency_and_compatibility": (
                "today every request repeats full work; INDEX.1E.1 may "
                "reduce unchanged-request work but must preserve the "
                "synchronous result shape and explicit degraded errors"
            ),
            "activation_graph_deferred": True,
        },
        "guardrails": {key: False for key in GUARDRAIL_KEYS},
        "readiness": readiness,
        "warnings": list(readiness["warnings"]),
        "deferred_work": [
            "production applied-manifest load and observed-state build",
            "delta-plan-controlled parse/embed/replace/delete dispatch",
            "confirmed identity permission enforcement at every caller",
            "manifest commit and applied-manifest receipt creation",
            "web propagation of additive completion/delta metadata",
            "Activation Graph runtime and legacy namespace migration",
        ],
        "recommended_next_phase": (
            "INDEX.1E.1 — Manifest Load and Delta Plan Dispatch"
            if readiness["next_phase_allowed"]
            else (
                "BLOCKED — resolve identified INDEX prerequisite/failure "
                "first"
            )
        ),
    }
    errors = validate_index_delta_preflight(report)
    if errors:
        raise ValueError(
            "invalid INDEX.1E.0 preflight: " + "; ".join(errors)
        )
    return report


def validate_index_delta_preflight(
    report: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate the report's deterministic readiness and guardrail shape."""
    errors: list[str] = []
    if not isinstance(report, Mapping):
        return ("preflight report must be an object",)
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if report.get("report_kind") != REPORT_KIND:
        errors.append("report_kind mismatch")
    if report.get("phase") != PHASE:
        errors.append("phase mismatch")

    retrieval_scope = report.get("retrieval_scope")
    if not isinstance(retrieval_scope, Mapping):
        errors.append("retrieval scope audit is required")
    else:
        if retrieval_scope.get("retrieval_paths") != list(
            RETRIEVAL_SCOPE_PATHS
        ):
            errors.append(
                "retrieval scope audit must name every canonical consumer"
            )
        if retrieval_scope.get("compatible") is not False:
            errors.append(
                "architecture-epoch retrieval mismatch must fail closed"
            )

    intersection: Mapping[str, Any] = {}
    baseline = report.get("known_failure_baseline")
    if not isinstance(baseline, Mapping):
        errors.append("known failure baseline summary is required")
    else:
        candidate = baseline.get("index_intersection_summary")
        if not isinstance(candidate, Mapping):
            errors.append("INDEX intersection summary is required")
        else:
            intersection = candidate
        summary = baseline.get("summary")
        if not isinstance(summary, Mapping):
            errors.append("known failure summary is required")
        elif isinstance(candidate, Mapping):
            counts = [
                candidate.get(key)
                for key in (
                    "authoritative_index_failures",
                    "index_adjacent_failures",
                    "unrelated_failures",
                    "unclassified_failures",
                )
            ]
            if any(type(value) is not int or value < 0 for value in counts):
                errors.append(
                    "INDEX intersection counts must be non-negative integers"
                )
            elif type(summary.get("failed")) is not int:
                errors.append(
                    "known failure summary failed count must be an integer"
                )
            elif sum(counts) != summary["failed"]:
                errors.append(
                    "INDEX intersection counts do not match failed total"
                )

    seams = report.get("integration_seams")
    if not isinstance(seams, list) or len(seams) != 1:
        errors.append("exactly one integration seam is required")
    else:
        seam = seams[0]
        if not isinstance(seam, Mapping):
            errors.append("integration seam must be an object")
        else:
            if seam.get("owns_shared_inventory") is not True:
                errors.append("integration seam must own shared inventory")
            if (
                seam.get("uses_confirmed_identity_permissions")
                is not True
            ):
                errors.append(
                    "integration seam must use confirmed identity permissions"
                )
            if seam.get("derives_authority_from_project_tag") is not False:
                errors.append(
                    "integration seam cannot derive authority from project_tag"
                )
            if seam.get("actual_dispatch_deferred") is not True:
                errors.append("INDEX.1E.0 must defer actual dispatch")
            observed = seam.get("observed_vs_applied")
            if (
                not isinstance(observed, str)
                or "observed" not in observed
                or "applied" not in observed
            ):
                errors.append(
                    "integration seam must distinguish observed and applied"
                )

    prerequisite_statuses: dict[str, str] = {}
    missing_prerequisites: list[str] = []
    prerequisites = report.get("prerequisite_reachability")
    if not isinstance(prerequisites, Mapping):
        errors.append("prerequisite reachability audit is required")
    else:
        for name in PREREQUISITE_NAMES:
            item = prerequisites.get(name)
            if not isinstance(item, Mapping):
                prerequisite_statuses[name] = "missing"
                missing_prerequisites.append(name)
                continue
            status = item.get("status", "missing")
            prerequisite_statuses[name] = status
            if status != "ready":
                missing_prerequisites.append(name)
        missing_prerequisites.sort()

    contract_mismatches = report.get("blocking_contract_mismatches")
    if (
        not isinstance(contract_mismatches, list)
        or any(
            not isinstance(value, str) or not value.strip()
            for value in contract_mismatches
        )
    ):
        errors.append(
            "blocking contract mismatches must be nonblank text"
        )
        normalized_mismatches: list[str] = []
    else:
        normalized_mismatches = sorted(
            {value.strip() for value in contract_mismatches}
        )
        if contract_mismatches != normalized_mismatches:
            errors.append(
                "blocking contract mismatches must be sorted and unique"
            )

    deferred_requirements = report.get(
        "deferred_integration_requirements"
    )
    if (
        not isinstance(deferred_requirements, list)
        or any(
            not isinstance(value, str) or not value.strip()
            for value in deferred_requirements
        )
    ):
        errors.append(
            "deferred integration requirements must be nonblank text"
        )
        normalized_deferred: list[str] = []
    else:
        normalized_deferred = sorted(
            {value.strip() for value in deferred_requirements}
        )
        if deferred_requirements != normalized_deferred:
            errors.append(
                "deferred integration requirements must be sorted and unique"
            )

    integration_gaps = report.get("integration_contract_gaps")
    expected_gaps = sorted(
        set(normalized_mismatches) | set(normalized_deferred)
    )
    if integration_gaps != expected_gaps:
        errors.append(
            "integration contract gaps must equal blocking and deferred gaps"
        )

    report_warnings = report.get("warnings")
    if (
        not isinstance(report_warnings, list)
        or any(
            not isinstance(value, str) or not value.strip()
            for value in report_warnings
        )
    ):
        errors.append("warnings must be nonblank text")
        normalized_warnings: list[str] = []
    else:
        normalized_warnings = sorted(
            {value.strip() for value in report_warnings}
        )
        if report_warnings != normalized_warnings:
            errors.append("warnings must be sorted and unique")

    index_runtime_failures = intersection.get(
        "authoritative_index_failures"
    )
    index_adjacent_failures = intersection.get(
        "index_adjacent_failures"
    )
    unclassified_failures = intersection.get("unclassified_failures")
    if (
        type(index_runtime_failures) is int
        and type(index_adjacent_failures) is int
        and (index_runtime_failures > 0 or index_adjacent_failures > 0)
    ):
        expected_status = READINESS_BLOCKED_INDEX
    elif (
        type(unclassified_failures) is int
        and unclassified_failures > 0
    ):
        expected_status = READINESS_BLOCKED_UNCLASSIFIED
    elif missing_prerequisites:
        expected_status = READINESS_BLOCKED_PREREQUISITE
    elif normalized_mismatches:
        expected_status = READINESS_BLOCKED_CONTRACT
    elif normalized_warnings:
        expected_status = READINESS_READY_WITH_WARNINGS
    else:
        expected_status = READINESS_READY
    expected_next_allowed = expected_status in {
        READINESS_READY,
        READINESS_READY_WITH_WARNINGS,
    }
    expected_phase_status = (
        PHASE_STATUS_COMPLETE
        if expected_status == READINESS_READY
        else (
            PHASE_STATUS_COMPLETE_WITH_WARNINGS
            if expected_status == READINESS_READY_WITH_WARNINGS
            else PHASE_STATUS_BLOCKED
        )
    )

    readiness = report.get("readiness")
    if not isinstance(readiness, Mapping):
        errors.append("readiness decision is required")
    else:
        status = readiness.get("status")
        if status not in READINESS_STATUSES:
            errors.append("readiness status is not stable")
        elif status != expected_status:
            errors.append(
                "readiness status contradicts the embedded evidence"
            )
        if readiness.get("phase_status") != expected_phase_status:
            errors.append(
                "phase status contradicts the readiness decision"
            )
        next_allowed = readiness.get("next_phase_allowed")
        if type(next_allowed) is not bool:
            errors.append("next_phase_allowed must be a boolean")
        elif next_allowed != expected_next_allowed:
            errors.append(
                "next_phase_allowed contradicts the readiness decision"
            )
        expected_readiness_fields = {
            "index_runtime_failures": index_runtime_failures,
            "index_adjacent_failures": index_adjacent_failures,
            "unclassified_failures": unclassified_failures,
            "prerequisites": prerequisite_statuses,
            "missing_prerequisites": missing_prerequisites,
            "contract_mismatches": normalized_mismatches,
            "warnings": normalized_warnings,
            "production_behavior": "full_reprocessing_characterized",
        }
        for field, expected in expected_readiness_fields.items():
            if readiness.get(field) != expected:
                errors.append(
                    f"readiness.{field} contradicts embedded evidence"
                )

    guardrails = report.get("guardrails")
    if not isinstance(guardrails, Mapping):
        errors.append("guardrail decisions are required")
    else:
        if set(guardrails) != set(GUARDRAIL_KEYS):
            errors.append("guardrail decisions must use the exact key set")
        if any(value is not False for value in guardrails.values()):
            errors.append(
                "INDEX.1E.0 guardrails record an unauthorized change"
            )

    recommended = report.get("recommended_next_phase")
    if not isinstance(recommended, str):
        errors.append("recommended next phase is required")
    elif expected_next_allowed != recommended.startswith("INDEX.1E.1"):
        errors.append(
            "recommended next phase contradicts the readiness decision"
        )
    return tuple(errors)


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_known_failure_markdown(
    baseline: Mapping[str, Any],
) -> str:
    known = normalize_known_failure_baseline(baseline)
    summary = known["summary"]
    intersection = known["index_intersection_summary"]
    lines = [
        "# INDEX.1E.0 Known-Failure Baseline",
        "",
        f"- Phase: `{PHASE}`",
        f"- Command: `{known['command']}`",
        f"- Collected: `{known['collection_timestamp']}`",
        f"- Commit: `{known['worktree_state']['commit']}`",
        f"- Dirty worktree: `{str(known['worktree_state']['dirty']).lower()}`",
        f"- Failure-set digest: `{known['failure_set_digest']}`",
        (
            f"- Result: **{summary['passed']} passed, "
            f"{summary['skipped']} skipped, {summary['failed']} failed**"
        ),
    ]
    if "diagnostic_output" in known:
        diagnostic = known["diagnostic_output"]
        lines.extend(
            [
                f"- Raw output: `{diagnostic['path']}`",
                f"- Raw output SHA-256: `{diagnostic['sha256']}`",
                (
                    f"- Runtime: {diagnostic['duration_seconds']} seconds; "
                    f"{diagnostic['warnings']} warnings; "
                    f"Python {diagnostic['python_version']}; "
                    f"pytest {diagnostic['pytest_version']}"
                ),
            ]
        )
    lines.extend(
        [
        "",
        "## Comparison with the reported diagnostic",
        "",
        known["comparison"]["note"],
        "",
        "| Metric | Delta |",
        "|---|---:|",
        f"| Passed | {known['comparison']['passed_delta']} |",
        f"| Skipped | {known['comparison']['skipped_delta']} |",
        f"| Failed | {known['comparison']['failed_delta']} |",
        "",
        "## INDEX intersection",
        "",
        "| Classification | Count |",
        "|---|---:|",
        (
            "| Authoritative INDEX runtime | "
            f"{intersection['authoritative_index_failures']} |"
        ),
        (
            "| INDEX-adjacent contract | "
            f"{intersection['index_adjacent_failures']} |"
        ),
        f"| Unrelated | {intersection['unrelated_failures']} |",
        f"| Unclassified | {intersection['unclassified_failures']} |",
        "",
        "## Frozen failures",
        "",
        "| Pytest node ID | Category | INDEX path | Reason | Evidence |",
        "|---|---|---:|---|---|",
        ]
    )
    for item in known["known_failures"]:
        evidence = "<br>".join(
            _md_cell(value) for value in item["evidence"]
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item["node_id"]),
                    _md_cell(item["category"]),
                    (
                        "yes"
                        if item["index_path_intersection"]
                        else "no"
                    ),
                    _md_cell(item["reason"]),
                    evidence,
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            (
                "This artifact freezes pre-existing failures; it does not "
                "skip, xfail, weaken, or repair them."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_index_delta_preflight_markdown(
    report: Mapping[str, Any],
) -> str:
    errors = validate_index_delta_preflight(report)
    if errors:
        raise ValueError(
            "cannot render invalid preflight: " + "; ".join(errors)
        )
    baseline = report["known_failure_baseline"]
    summary = baseline["summary"]
    intersection = baseline["index_intersection_summary"]
    behavior = report["current_production_behavior"]
    readiness = report["readiness"]
    diagnostic_lines: list[str] = []
    if "diagnostic_output" in baseline:
        diagnostic = baseline["diagnostic_output"]
        diagnostic_lines = [
            (
                f"Raw output `{diagnostic['path']}` is retained with "
                f"SHA-256 `{diagnostic['sha256']}` "
                f"({diagnostic['duration_seconds']} seconds, "
                f"{diagnostic['warnings']} warnings)."
            ),
            "",
        ]
    lines = [
        "# INDEX.1E.0 — Delta Integration Preflight",
        "",
        f"- Phase: `{report['phase']}`",
        f"- Status: `{readiness['phase_status']}`",
        f"- Readiness: `{readiness['status']}`",
        f"- Commit: `{report['worktree_state']['commit']}`",
        (
            "- Dirty worktree: "
            f"`{str(report['worktree_state']['dirty']).lower()}`"
        ),
        (
            f"- Baseline: **{summary['passed']} passed, "
            f"{summary['skipped']} skipped, {summary['failed']} failed**"
        ),
        "",
        "## 1. Test baseline and failure categories",
        "",
        (
            f"The repository-wide command was `{baseline['command']}`. "
            f"The frozen failure-set digest is "
            f"`{baseline['failure_set_digest']}`."
        ),
        "",
        baseline["comparison"]["note"],
        "",
        *diagnostic_lines,
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in baseline[
        "failure_category_counts"
    ].items():
        lines.append(f"| {_md_cell(category)} | {count} |")
    lines.extend(
        [
            "",
            "## 2. INDEX intersection analysis",
            "",
            (
                f"- Authoritative INDEX runtime failures: "
                f"**{intersection['authoritative_index_failures']}**"
            ),
            (
                f"- INDEX-adjacent contract failures: "
                f"**{intersection['index_adjacent_failures']}**"
            ),
            (
                f"- Unclassified failures: "
                f"**{intersection['unclassified_failures']}**"
            ),
            (
                f"- Proven unrelated failures: "
                f"**{intersection['unrelated_failures']}**"
            ),
            "",
            "## 3. Production entrypoints",
            "",
            (
                "| Caller | Trigger | Inventory | Identity/scope | "
                "Manifest/delta | Persistence | Completion |"
            ),
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in report["production_entrypoints"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(item["caller"]),
                    _md_cell(item["mode_or_trigger"]),
                    _md_cell(item["inventory_source"]),
                    _md_cell(
                        item["identity_source"]
                        + "; "
                        + item["index_scope_source"]
                        + "; "
                        + item["project_tag_behavior"]
                    ),
                    _md_cell(
                        item["manifest_load_behavior"]
                        + "; "
                        + item["delta_planner_behavior"]
                    ),
                    _md_cell(item["db_persistence_behavior"]),
                    _md_cell(
                        item["completion_metadata_consumption"]
                    ),
                ]
            )
            + " |"
        )
    retrieval = report["retrieval_scope"]
    lines.extend(
        [
            "",
            (
                "Concrete retrieval consumers of code-index scope: "
                + ", ".join(
                    f"`{path}`"
                    for path in retrieval["retrieval_paths"]
                )
                + "."
            ),
            (
                "Baseline path scope compatibility is "
                f"`{str(retrieval['baseline_scope_compatible']).lower()}`; "
                "architecture-epoch scope compatibility is "
                f"`{str(retrieval['architecture_epoch_scope_compatible']).lower()}`."
            ),
        ]
    )
    lines.extend(
        [
            "",
            "## 4. Current Run A / Run B characterization",
            "",
            behavior["conclusion"] + ".",
            "",
            "| Counter | Run A (cold) | Run B (unchanged) |",
            "|---|---:|---:|",
        ]
    )
    for key in behavior["run_a"]:
        lines.append(
            f"| {_md_cell(key)} | {behavior['run_a'][key]} | "
            f"{behavior['run_b'][key]} |"
        )
    lines.extend(
        [
            "",
            "## 5. Prerequisite reachability",
            "",
            "| Primitive | Status | Reachable symbols | Evidence |",
            "|---|---|---|---|",
        ]
    )
    for name in PREREQUISITE_NAMES:
        item = report["prerequisite_reachability"][name]
        evidence = item["evidence"]
        if item.get("integration_gap"):
            evidence += "; gap: " + item["integration_gap"]
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(name),
                    _md_cell(item["status"]),
                    "<br>".join(
                        _md_cell(value)
                        for value in item["symbols"]
                    ),
                    _md_cell(evidence),
                ]
            )
            + " |"
        )
    seam = report["integration_seams"][0]
    lines.extend(
        [
            "",
            "## 6. Recommended integration seam",
            "",
            (
                f"Exactly one seam is recommended: "
                f"`{seam['module']}.{seam['function']}` "
                f"{seam['location']}."
            ),
            "",
            seam["observed_vs_applied"] + ".",
            "",
            "Future controlled loops:",
            "",
        ]
    )
    lines.extend(f"- {value}" for value in seam["future_controlled_loops"])
    lines.extend(
        [
            "",
            (
                f"Legacy fallback: {seam['legacy_fallback']}. Actual "
                "dispatch is deferred."
            ),
            "",
            "## 7. DB-disabled behavior",
            "",
            (
                "Processing-only success is not persistent canonical "
                "success. The current completion classifier reports "
                f"`{report['db_disabled_behavior']['completion_status']}`, "
                "denies trusted completion, manifest advancement, and a "
                "trusted-current claim, and creates no fake applied receipt."
            ),
            "",
            "## 8. Web-request boundary",
            "",
        ]
    )
    web = report["web_request_boundary"]
    lines.extend(
        [
            f"- Invocation: {web['invocation']}.",
            (
                "- Confirmed identity enforcement: "
                f"`{str(web['identity_confirmation_enforced']).lower()}`."
            ),
            (
                "- Completion metadata reaches payload: "
                f"`{str(web['completion_metadata_reaches_payload']).lower()}`."
            ),
            (
                "- Credential redaction preserved: "
                f"`{str(web['credential_redaction_preserved']).lower()}`."
            ),
            (
                "- One shared inventory: "
                f"`{str(web['shared_inventory']).lower()}`."
            ),
            f"- Latency/compatibility: {web['latency_and_compatibility']}.",
            "",
            "## 9. Guardrails",
            "",
        ]
    )
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## 10. Readiness decision",
            "",
            f"- Status: `{readiness['status']}`",
            f"- Phase status: `{readiness['phase_status']}`",
            (
                "- Next phase allowed: "
                f"`{str(readiness['next_phase_allowed']).lower()}`"
            ),
            (
                "- Production behavior: "
                f"`{readiness['production_behavior']}`"
            ),
            "",
            "Blocking contract mismatches:",
            "",
        ]
    )
    if readiness["contract_mismatches"]:
        lines.extend(
            f"- {value}"
            for value in readiness["contract_mismatches"]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## 11. Warnings and deferred work",
            "",
        ]
    )
    lines.extend(f"- Warning: {value}" for value in report["warnings"])
    lines.extend(
        f"- Deferred seam requirement: {value}"
        for value in report["deferred_integration_requirements"]
    )
    lines.extend(f"- Deferred: {value}" for value in report["deferred_work"])
    lines.extend(
        [
            "",
            "## 12. Recommended next phase",
            "",
            report["recommended_next_phase"],
            "",
            (
                "No production indexing behavior was changed by this "
                "preflight."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_index_delta_preflight(
    *,
    repo_root: str | Path,
    baseline: Mapping[str, Any],
    baseline_json_path: str | Path = DEFAULT_BASELINE_JSON,
    preflight_json_path: str | Path = DEFAULT_PREFLIGHT_JSON,
    baseline_markdown_path: str | Path = DEFAULT_BASELINE_MARKDOWN,
    preflight_markdown_path: str | Path = DEFAULT_PREFLIGHT_MARKDOWN,
) -> dict[str, Any]:
    """Write canonical JSON/Markdown artifacts beneath ``repo_root``."""
    root = Path(repo_root).expanduser().resolve()
    known = normalize_known_failure_baseline(baseline)
    preflight = build_index_delta_preflight(known)
    destinations = {
        "baseline_json_path": root / Path(baseline_json_path),
        "preflight_json_path": root / Path(preflight_json_path),
        "baseline_markdown_path": root / Path(
            baseline_markdown_path
        ),
        "preflight_markdown_path": root / Path(
            preflight_markdown_path
        ),
    }
    for label, path in destinations.items():
        resolved = path.resolve()
        if root != resolved and root not in resolved.parents:
            raise ValueError(f"{label} must remain beneath repo_root")

    _write_json(destinations["baseline_json_path"], known)
    _write_json(destinations["preflight_json_path"], preflight)
    destinations["baseline_markdown_path"].parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destinations["baseline_markdown_path"].write_text(
        render_known_failure_markdown(known),
        encoding="utf-8",
        newline="\n",
    )
    destinations["preflight_markdown_path"].parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    destinations["preflight_markdown_path"].write_text(
        render_index_delta_preflight_markdown(preflight),
        encoding="utf-8",
        newline="\n",
    )
    return {
        **{
            label: str(path)
            for label, path in destinations.items()
        },
        "baseline": known,
        "report": preflight,
    }
