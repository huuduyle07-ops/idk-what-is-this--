"""CHECK.1 observation adapter — fact shaping, never fact collection.

The CHECK.1 reconciliation core is pure: it compares supplied facts against a
supplied contract.  This adapter is the one narrow place where already-collected
repository facts and the *existing* path-safety gate are shaped into those
CHECK.1 records.

It is deliberately observation-only:

* it never runs ``git``, a subprocess, a validation command, or a test;
* it never traverses a directory, reads file content, or resolves a symlink;
* it never applies, reverts, resets, cleans, or stages anything;
* it collects nothing itself — change records must already have been observed
  by a trusted upstream collector and are passed in verbatim.

Its one substantive job is reuse: ``core.patch_safety`` remains the single
source of truth for which repository paths may be written, so a caller cannot
launder a protected, env, test or benchmark-validation path into CHECK.1 by
listing it as writable.  Any write-bearing path that the existing gate blocks is
demoted to ``forbidden`` carrying the gate's own category.

Non-write authorities are passed through unchanged.  A supporting file that may
be read, and a validation file that may be executed, are already non-writable;
collapsing them into ``forbidden`` would lose a distinction the upstream patch
contracts deliberately make.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from core.patch_safety import evaluate_patch_safety
from core.post_run_reconciliation import (
    CHANGE_KINDS,
    FORBIDDEN_OTHER,
    FORBIDDEN_REASONS,
    MAX_AUTHORIZED_PATHS,
    MAX_OBSERVED_CHANGES,
    MAX_VALIDATION_RECEIPTS,
    PATH_AUTHORITY_FORBIDDEN,
    PATH_AUTHORITY_SUPPORTING_READ_ONLY,
    PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
    PATH_AUTHORITY_WRITABLE,
    PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
    WRITE_BEARING_AUTHORITIES,
    AuthorizedPath,
    ObservedChange,
    ObservedPostRunFacts,
    ValidationReceipt,
)


PHASE_ID = "CHECK.1"
ADAPTER_KIND = "post_run_observation"

#: Keys one supplied observed-change record may carry.  An unknown key is an
#: error rather than a silently ignored field.
OBSERVED_CHANGE_FIELDS: frozenset[str] = frozenset(
    {"path", "change_kind", "before_sha256", "after_sha256", "from_path"}
)

#: ``core.patch_safety`` categories, mapped onto CHECK.1 forbidden reasons.
#: Both vocabularies are frozen, so the mapping is identity for every category
#: the gate emits today; the fallback keeps a future category honest instead of
#: silently dropping it.
_PATCH_SAFETY_CATEGORIES: frozenset[str] = frozenset(FORBIDDEN_REASONS)


def _forbidden_reason_for_category(category: object) -> str:
    text = category if isinstance(category, str) else ""
    return text if text in _PATCH_SAFETY_CATEGORIES else FORBIDDEN_OTHER


def _unique_sequence(values: object, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{label} must be a sequence of paths")
    rendered = tuple(values)
    if not all(isinstance(item, str) for item in rendered):
        raise TypeError(f"{label} must contain string paths")
    if len(set(rendered)) != len(rendered):
        raise ValueError(f"{label} must not repeat a path")
    return rendered


def patch_safety_forbidden_categories(
    paths: Sequence[str],
) -> dict[str, str]:
    """Ask the existing apply-time gate which of these paths it blocks.

    The gate is called without a project root, so the check is lexical: no
    filesystem is consulted and no path is resolved.
    """

    verdict = evaluate_patch_safety(list(paths))
    blocked: dict[str, str] = {}
    for entry in verdict.get("blocked_paths", []):
        path = entry.get("path")
        if isinstance(path, str):
            blocked[path] = _forbidden_reason_for_category(entry.get("category"))
    return blocked


def classify_authorized_paths(
    *,
    writable_paths: Sequence[str] = (),
    writable_with_review_paths: Sequence[str] = (),
    supporting_read_only_paths: Sequence[str] = (),
    validation_execute_only_paths: Sequence[str] = (),
    forbidden_paths: Mapping[str, str] | None = None,
    worker_ownership: Mapping[str, str] | None = None,
) -> tuple[AuthorizedPath, ...]:
    """Shape an authorized path set, re-checking every write against the gate.

    A path the caller declares writable but ``core.patch_safety`` blocks comes
    back ``forbidden``, carrying the gate's own category.  A path declared
    forbidden stays forbidden with the supplied reason and is never re-checked
    into a weaker state.
    """

    buckets: tuple[tuple[str, tuple[str, ...]], ...] = (
        (PATH_AUTHORITY_WRITABLE, _unique_sequence(writable_paths, "writable paths")),
        (
            PATH_AUTHORITY_WRITABLE_WITH_REVIEW,
            _unique_sequence(
                writable_with_review_paths, "writable with review paths"
            ),
        ),
        (
            PATH_AUTHORITY_SUPPORTING_READ_ONLY,
            _unique_sequence(
                supporting_read_only_paths, "supporting read-only paths"
            ),
        ),
        (
            PATH_AUTHORITY_VALIDATION_EXECUTE_ONLY,
            _unique_sequence(
                validation_execute_only_paths, "validation execute-only paths"
            ),
        ),
    )

    declared_forbidden: dict[str, str] = {}
    if forbidden_paths is not None:
        if not isinstance(forbidden_paths, Mapping):
            raise TypeError("forbidden_paths must map a path to a bounded reason")
        for path, reason in forbidden_paths.items():
            if not isinstance(path, str):
                raise TypeError("forbidden_paths keys must be string paths")
            if reason not in FORBIDDEN_REASONS:
                raise ValueError(f"unsupported forbidden reason: {reason!r}")
            declared_forbidden[path] = reason

    ownership: dict[str, str] = {}
    if worker_ownership is not None:
        if not isinstance(worker_ownership, Mapping):
            raise TypeError("worker_ownership must map a path to a worker id")
        for path, worker_id in worker_ownership.items():
            if not isinstance(path, str) or not isinstance(worker_id, str):
                raise TypeError("worker_ownership entries must be strings")
            ownership[path] = worker_id

    assignments: dict[str, str] = {}
    for authority, paths in buckets:
        for path in paths:
            if path in assignments or path in declared_forbidden:
                raise ValueError(
                    f"path {path!r} is classified more than once"
                )
            assignments[path] = authority

    write_bearing = [
        path
        for path, authority in assignments.items()
        if authority in WRITE_BEARING_AUTHORITIES
    ]
    gate_blocked = patch_safety_forbidden_categories(sorted(write_bearing))

    records: list[AuthorizedPath] = []
    for path, reason in declared_forbidden.items():
        records.append(
            AuthorizedPath(
                path=path,
                authority=PATH_AUTHORITY_FORBIDDEN,
                forbidden_reason=reason,
                worker_id=ownership.get(path),
            )
        )
    for path, authority in assignments.items():
        blocked_reason = gate_blocked.get(path)
        if blocked_reason is not None:
            records.append(
                AuthorizedPath(
                    path=path,
                    authority=PATH_AUTHORITY_FORBIDDEN,
                    forbidden_reason=blocked_reason,
                    worker_id=ownership.get(path),
                )
            )
            continue
        records.append(
            AuthorizedPath(
                path=path,
                authority=authority,
                worker_id=ownership.get(path),
            )
        )

    if len(records) > MAX_AUTHORIZED_PATHS:
        raise ValueError("authorized path set exceeds its finite bound")
    return tuple(sorted(records, key=lambda item: item.path))


def observed_changes_from_records(
    records: Sequence[Mapping[str, Any]],
) -> tuple[ObservedChange, ...]:
    """Convert already-observed change records into CHECK.1 change facts.

    The records must come from a trusted upstream collector.  This function
    observes nothing itself: it validates shape and hands the facts on.
    """

    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise TypeError("observed change records must be a sequence of mappings")
    if len(records) > MAX_OBSERVED_CHANGES:
        raise ValueError("observed change records exceed their finite bound")

    changes: list[ObservedChange] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise TypeError("each observed change record must be a mapping")
        unknown = set(record) - OBSERVED_CHANGE_FIELDS
        if unknown:
            raise ValueError(
                "unsupported observed change fields: " + ", ".join(sorted(unknown))
            )
        change_kind = record.get("change_kind")
        if change_kind not in CHANGE_KINDS:
            raise ValueError(f"unsupported observed change kind: {change_kind!r}")
        changes.append(
            ObservedChange(
                path=record.get("path"),
                change_kind=change_kind,
                before_sha256=record.get("before_sha256"),
                after_sha256=record.get("after_sha256"),
                from_path=record.get("from_path"),
            )
        )
    return tuple(sorted(changes, key=lambda item: item.path))


def build_observed_post_run_facts(
    *,
    facts_id: str,
    execution_run_id: str,
    repository_id: str,
    pre_execution_state_fingerprint: str,
    post_execution_state_fingerprint: str,
    final_state_fingerprint: str,
    observed_changes: Sequence[ObservedChange] = (),
    validation_receipts: Sequence[ValidationReceipt] = (),
    post_validation_state_fingerprint: str | None = None,
    rename_detection_supported: bool = False,
) -> ObservedPostRunFacts:
    """Assemble one observed fact set, marked as externally collected.

    ``facts_collected_externally`` is always true for anything this adapter
    produces: the reconciliation core did not and could not observe it.
    """

    if len(validation_receipts) > MAX_VALIDATION_RECEIPTS:
        raise ValueError("validation receipts exceed their finite bound")
    return ObservedPostRunFacts(
        facts_id=facts_id,
        execution_run_id=execution_run_id,
        repository_id=repository_id,
        pre_execution_state_fingerprint=pre_execution_state_fingerprint,
        post_execution_state_fingerprint=post_execution_state_fingerprint,
        final_state_fingerprint=final_state_fingerprint,
        observed_changes=tuple(
            sorted(observed_changes, key=lambda item: item.path)
        ),
        validation_receipts=tuple(
            sorted(validation_receipts, key=lambda item: item.receipt_id)
        ),
        post_validation_state_fingerprint=post_validation_state_fingerprint,
        rename_detection_supported=rename_detection_supported,
        facts_collected_externally=True,
    )


def observation_guardrails() -> dict[str, bool]:
    """Every power the observation adapter declines to exercise."""
    return {
        "facts_collected_externally": True,
        "path_safety_gate_reused": True,
        "repository_traversed": False,
        "repository_read": False,
        "source_content_read": False,
        "symlink_resolved": False,
        "git_invoked": False,
        "subprocess_invoked": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "worktree_cleaned": False,
        "repository_reset": False,
        "network_call_performed": False,
        "model_called": False,
        "human_approval_required": True,
    }


__all__ = [
    "PHASE_ID",
    "ADAPTER_KIND",
    "OBSERVED_CHANGE_FIELDS",
    "patch_safety_forbidden_categories",
    "classify_authorized_paths",
    "observed_changes_from_records",
    "build_observed_post_run_facts",
    "observation_guardrails",
]
