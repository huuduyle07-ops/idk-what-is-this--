"""CHECK.LIVE.1 — bounded live change observation.

This is the narrowest possible observed-change collector, added only because the
live apply path does not already publish before/after content identity for the
paths it writes.  It is deliberately *not* a repository indexer:

* it never walks a directory — no ``os.walk``, ``glob``, ``rglob`` or
  ``iterdir`` appears here, and none may;
* it reads only paths a caller already named, and only inside the repository
  root it was given;
* it never writes, applies, reverts, resets, cleans, stages, or stashes;
* it runs no subprocess, no ``git``, no validation and no model;
* it opens no network connection.

Its two products are:

``derive_observed_change_records``
    already-observed change facts in the exact record shape
    ``core.post_run_observation.observed_changes_from_records`` accepts.

``observed_change_state_fingerprint``
    the canonical *observed-change-state* identity CHECK.1 uses for validation
    freshness.  It is a fingerprint over a bounded base identity plus the
    observed change set, never a hash of the whole repository: adding a
    repository-wide content hash here would reintroduce exactly the traversal
    cost the index phases removed.

Because the fingerprint is derived from the observed change set, two facts hold
by construction, and CHECK.1 depends on both:

* an empty observed change set fingerprints identically to the pre-execution
  state, so a genuine no-op run does not break CHECK.1's state chain;
* any difference in the observed change set — a new path, a different change
  kind, a different content digest — changes the state identity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.repository_path_policy import is_safe_repository_relative_path


PHASE_ID = "CHECK.LIVE.1"
OBSERVER_KIND = "live_change_observation"

#: Identity of the fingerprint shape, so a future change to the derivation is
#: a visible schema change rather than a silent drift.
STATE_FINGERPRINT_KIND = "check_live_1_observed_change_state_v1"

#: Finite bounds.  They mirror CHECK.1's own observed-change bound so a fact
#: set this observer produces can always be carried by the frozen contract.
MAX_OBSERVED_PATHS = 256
MAX_DIGEST_BYTES = 8 * 1024 * 1024
_DIGEST_CHUNK_BYTES = 65536

CHANGE_ADDED = "added"
CHANGE_DELETED = "deleted"
CHANGE_MODIFIED = "modified"

#: This observer never claims a rename.  A rename is a relation between two
#: paths, and nothing in the live apply path authoritatively reports one; a
#: delete plus an add is reported as a delete plus an add.
RENAME_DETECTION_SUPPORTED = False


class LiveObservationBoundError(ValueError):
    """Raised when a caller asks the observer to exceed a finite bound."""


def canonical_relative_path(value: object) -> str:
    """Return one canonical repository-relative spelling, or ``""``.

    Purely lexical: no filesystem is consulted, nothing is resolved, and a path
    that is absolute, escapes the repository, or is otherwise not a canonical
    repository-relative spelling comes back empty rather than repaired.
    """
    if not isinstance(value, str):
        return ""
    text = value.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text or text.startswith("/"):
        return ""
    if not is_safe_repository_relative_path(text):
        return ""
    return text


def canonical_relative_paths(values: Iterable[object]) -> tuple[str, ...]:
    """Canonicalise, drop unusable spellings, deduplicate and sort."""
    canonical = {
        candidate
        for candidate in (canonical_relative_path(value) for value in values)
        if candidate
    }
    return tuple(sorted(canonical))


@dataclass(frozen=True, slots=True)
class LivePathDigests:
    """Content identity of a bounded, explicitly named set of paths.

    ``digests`` carries one entry per requested path.  ``None`` means the path
    was genuinely absent at observation time — which is different from a path
    that could not be read, and different again from a path nobody asked about.
    """

    digests: tuple[tuple[str, str | None], ...] = ()
    unreadable_paths: tuple[str, ...] = ()
    oversized_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.digests, tuple):
            raise TypeError("digests must be a tuple")
        if len(self.digests) > MAX_OBSERVED_PATHS:
            raise LiveObservationBoundError(
                "observed path digests exceed their finite bound"
            )
        seen: set[str] = set()
        for entry in self.digests:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("each digest entry must be a (path, digest) pair")
            path, digest = entry
            if not isinstance(path, str) or path in seen:
                raise ValueError("digest entries must carry unique string paths")
            seen.add(path)
            if digest is not None and not _is_sha256(digest):
                raise ValueError("a digest must be a lowercase SHA-256 or None")

    @property
    def mapping(self) -> dict[str, str | None]:
        return {path: digest for path, digest in self.digests}

    @property
    def observed_paths(self) -> tuple[str, ...]:
        return tuple(path for path, _digest in self.digests)

    def as_dict(self) -> dict[str, Any]:
        return {
            "digests": [
                {"path": path, "sha256": digest} for path, digest in self.digests
            ],
            "unreadable_paths": list(self.unreadable_paths),
            "oversized_paths": list(self.oversized_paths),
        }


@dataclass(frozen=True, slots=True)
class LiveObservedChangeSet:
    """Typed change records plus an honest account of what stayed untyped."""

    records: tuple[dict[str, Any], ...] = ()
    untyped_paths: tuple[str, ...] = ()
    unreadable_paths: tuple[str, ...] = ()
    oversized_paths: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.records

    @property
    def observation_incomplete(self) -> bool:
        return bool(
            self.untyped_paths or self.unreadable_paths or self.oversized_paths
        )

    @property
    def changed_paths(self) -> tuple[str, ...]:
        return tuple(sorted(str(record["path"]) for record in self.records))

    def as_dict(self) -> dict[str, Any]:
        return {
            "records": [dict(record) for record in self.records],
            "untyped_paths": list(self.untyped_paths),
            "unreadable_paths": list(self.unreadable_paths),
            "oversized_paths": list(self.oversized_paths),
        }


def digest_known_paths(
    project_root: str | Path,
    paths: Sequence[str],
) -> LivePathDigests:
    """Digest exactly the named paths.  Nothing is discovered here.

    A path is read only when it canonicalises, stays inside ``project_root``,
    is a regular file, is not a symlink, and is within the byte bound.  Every
    other outcome is recorded rather than guessed.
    """
    canonical = canonical_relative_paths(paths)
    if len(canonical) > MAX_OBSERVED_PATHS:
        raise LiveObservationBoundError(
            "observed path set exceeds its finite bound"
        )

    root = Path(project_root).resolve()
    digests: list[tuple[str, str | None]] = []
    unreadable: list[str] = []
    oversized: list[str] = []

    for relative in canonical:
        target = _contained_path(root, relative)
        if target is None:
            unreadable.append(relative)
            continue
        try:
            if target.is_symlink():
                unreadable.append(relative)
                continue
            if not target.exists():
                digests.append((relative, None))
                continue
            if not target.is_file():
                unreadable.append(relative)
                continue
            size = target.stat().st_size
        except OSError:
            unreadable.append(relative)
            continue
        if size > MAX_DIGEST_BYTES:
            oversized.append(relative)
            continue
        digest = _file_digest(target)
        if digest is None:
            unreadable.append(relative)
            continue
        digests.append((relative, digest))

    return LivePathDigests(
        digests=tuple(digests),
        unreadable_paths=tuple(sorted(unreadable)),
        oversized_paths=tuple(sorted(oversized)),
    )


def derive_observed_change_records(
    before: LivePathDigests,
    after: LivePathDigests,
) -> LiveObservedChangeSet:
    """Compare two bounded digest observations into CHECK.1 change records.

    Only a path observed in *both* windows can be typed: without a before
    identity there is no honest way to say whether a present file was added or
    modified.  Such a path is reported as untyped rather than assumed.
    """
    if not isinstance(before, LivePathDigests) or not isinstance(
        after, LivePathDigests
    ):
        raise TypeError("change derivation requires two LivePathDigests")

    before_map = before.mapping
    after_map = after.mapping
    records: list[dict[str, Any]] = []
    untyped: list[str] = []

    for path in sorted(after_map):
        after_digest = after_map[path]
        if path not in before_map:
            if after_digest is not None:
                untyped.append(path)
            continue
        before_digest = before_map[path]
        if before_digest == after_digest:
            continue
        if before_digest is None:
            records.append(
                {
                    "path": path,
                    "change_kind": CHANGE_ADDED,
                    "before_sha256": None,
                    "after_sha256": after_digest,
                }
            )
            continue
        if after_digest is None:
            records.append(
                {
                    "path": path,
                    "change_kind": CHANGE_DELETED,
                    "before_sha256": before_digest,
                    "after_sha256": None,
                }
            )
            continue
        records.append(
            {
                "path": path,
                "change_kind": CHANGE_MODIFIED,
                "before_sha256": before_digest,
                "after_sha256": after_digest,
            }
        )

    for path in sorted(set(before_map) - set(after_map)):
        untyped.append(path)

    if len(records) > MAX_OBSERVED_PATHS:
        raise LiveObservationBoundError(
            "observed change records exceed their finite bound"
        )

    return LiveObservedChangeSet(
        records=tuple(records),
        untyped_paths=tuple(sorted(set(untyped))),
        unreadable_paths=tuple(
            sorted(set(before.unreadable_paths) | set(after.unreadable_paths))
        ),
        oversized_paths=tuple(
            sorted(set(before.oversized_paths) | set(after.oversized_paths))
        ),
    )


def subtract_change_records(
    records: Sequence[Mapping[str, Any]],
    paths: Iterable[str],
) -> tuple[dict[str, Any], ...]:
    """Return the change set without the named paths, order preserved.

    Used to reconstruct the state a validation actually validated: the final
    change set minus whatever the authoritative validation side-effect
    collector attributes to the validation window.
    """
    removed = {canonical_relative_path(value) for value in paths}
    removed.discard("")
    return tuple(
        dict(record)
        for record in records
        if str(record.get("path", "")) not in removed
    )


def observed_change_state_fingerprint(
    repository_id: str,
    base_digests: LivePathDigests,
    change_records: Sequence[Mapping[str, Any]] = (),
) -> str:
    """Canonical identity of one observed change state.

    The identity is bound to the repository, to the pre-execution content
    identity of the observed path set, and to the observed change set.  It is
    deterministic over that content alone: no clock, no run id, no random
    value and no machine state takes part, so the same actual state always
    fingerprints identically and any change to it does not.
    """
    if not isinstance(repository_id, str) or not repository_id.strip():
        raise ValueError("repository_id must be non-empty text")
    if not isinstance(base_digests, LivePathDigests):
        raise TypeError("base_digests must be LivePathDigests")

    payload = {
        "state_kind": STATE_FINGERPRINT_KIND,
        "phase_id": PHASE_ID,
        "repository_id": repository_id,
        "base": [
            {"path": path, "sha256": digest}
            for path, digest in sorted(base_digests.digests)
        ],
        "changes": sorted(
            (
                {
                    "path": str(record.get("path", "")),
                    "change_kind": str(record.get("change_kind", "")),
                    "before_sha256": record.get("before_sha256"),
                    "after_sha256": record.get("after_sha256"),
                }
                for record in change_records
            ),
            key=lambda item: item["path"],
        ),
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def live_change_observation_guardrails() -> dict[str, bool]:
    """Every power this observer declines to exercise."""
    return {
        "reads_only_explicitly_named_paths": True,
        "repository_traversed": False,
        "repository_indexed": False,
        "directory_listed": False,
        "glob_expanded": False,
        "symlink_followed": False,
        "source_content_retained": False,
        "diff_generated": False,
        "git_invoked": False,
        "git_stash_invoked": False,
        "git_reset_invoked": False,
        "git_clean_invoked": False,
        "subprocess_invoked": False,
        "validation_executed": False,
        "patch_applied": False,
        "files_modified": False,
        "worktree_mutated": False,
        "network_call_performed": False,
        "model_called": False,
        "authoritative_effect": False,
        "human_approval_required": True,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _contained_path(root: Path, relative: str) -> Path | None:
    """Resolve one relative path inside ``root``, or ``None`` when it escapes."""
    try:
        candidate = (root / relative).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _file_digest(target: Path) -> str | None:
    """SHA-256 of one already-identified regular file, or ``None`` on error."""
    digest = hashlib.sha256()
    read = 0
    try:
        with target.open("rb") as handle:
            while True:
                chunk = handle.read(_DIGEST_CHUNK_BYTES)
                if not chunk:
                    break
                read += len(chunk)
                if read > MAX_DIGEST_BYTES:
                    return None
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


__all__ = [
    "PHASE_ID",
    "OBSERVER_KIND",
    "STATE_FINGERPRINT_KIND",
    "MAX_OBSERVED_PATHS",
    "MAX_DIGEST_BYTES",
    "RENAME_DETECTION_SUPPORTED",
    "CHANGE_ADDED",
    "CHANGE_DELETED",
    "CHANGE_MODIFIED",
    "LiveObservationBoundError",
    "LivePathDigests",
    "LiveObservedChangeSet",
    "canonical_relative_path",
    "canonical_relative_paths",
    "digest_known_paths",
    "derive_observed_change_records",
    "subtract_change_records",
    "observed_change_state_fingerprint",
    "live_change_observation_guardrails",
]
