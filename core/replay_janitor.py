"""Read-only replay janitor dry-run planning for Phase 13R.4.

This module inspects replay bundles under ``<repo>/.agent/replays`` and
produces a *dry-run* cleanup plan. It classifies each bundle as ``keep``,
``cleanup_candidate``, or ``invalid_or_unreadable`` and never deletes files,
mutates manifests, runs patching/validation/benchmarks, contacts a model or
API, touches Docker, spawns subprocesses, talks to a database, or makes
network calls. Acting on the plan is intentionally out of scope here.
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from core.replay_recorder import MANIFEST_NAME, read_replay_manifest


REPLAYS_SUBDIR = Path(".agent") / "replays"

CLASS_KEEP = "keep"
CLASS_CLEANUP = "cleanup_candidate"
CLASS_INVALID = "invalid_or_unreadable"

# Phase 13R.5: the exact, case-sensitive token required to actually delete.
CONFIRM_TOKEN = "DELETE_REPLAY_CANDIDATES"

GUARDRAIL_NOTE = (
    "Replay janitor is a read-only dry-run: it never deletes bundles, mutates "
    "manifests, or runs the model, patcher, validation, benchmark, Dream, "
    "Docker, subprocess, database, or network."
)


@dataclass(frozen=True)
class ReplayJanitorEntry:
    replay_id: str
    classification: str
    reason: str
    pinned: bool
    created_at: str | None = None
    run_kind: str | None = None
    age_days: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplayJanitorPlan:
    repo_path: str
    generated_at: str
    max_age_days: float | None
    max_keep: int | None
    include_invalid: bool
    pinned_ids: list[str]
    entries: list[ReplayJanitorEntry] = field(default_factory=list)
    guardrail_note: str = GUARDRAIL_NOTE

    @property
    def keep_count(self) -> int:
        return sum(1 for e in self.entries if e.classification == CLASS_KEEP)

    @property
    def cleanup_count(self) -> int:
        return sum(1 for e in self.entries if e.classification == CLASS_CLEANUP)

    @property
    def invalid_count(self) -> int:
        return sum(1 for e in self.entries if e.classification == CLASS_INVALID)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["entries"] = [entry.to_dict() for entry in self.entries]
        data["keep_count"] = self.keep_count
        data["cleanup_count"] = self.cleanup_count
        data["invalid_count"] = self.invalid_count
        return data


def plan_replay_cleanup(
    repo_path: str | Path,
    *,
    max_age_days: float | None = None,
    max_keep: int | None = None,
    include_invalid: bool = False,
    pinned_ids: Iterable[str] = (),
    now: datetime | None = None,
) -> ReplayJanitorPlan:
    """Build a read-only dry-run cleanup plan for replay bundles.

    Nothing is deleted or modified. Each bundle is classified and the caller
    decides what (if anything) to do with the result in a later phase.
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_path}")
    now_utc = _coerce_utc(now)
    pinned = {_validate_replay_id(pid) for pid in pinned_ids}
    max_age = None if max_age_days is None else max(0.0, float(max_age_days))
    keep_budget = None if max_keep is None else max(0, int(max_keep))

    scanned = _scan_bundles(repo)

    entries: list[ReplayJanitorEntry] = []
    valid_rank = 0
    for record in scanned:
        replay_id = record["replay_id"]
        is_pinned = replay_id in pinned

        if is_pinned:
            entries.append(
                _entry(record, CLASS_KEEP, "pinned", pinned=True)
            )
            if record["valid"]:
                valid_rank += 1
            continue

        if not record["valid"]:
            if include_invalid:
                entries.append(
                    _entry(record, CLASS_CLEANUP, "invalid_included", pinned=False)
                )
            else:
                entries.append(
                    _entry(record, CLASS_INVALID, "unreadable", pinned=False)
                )
            continue

        age_days = _age_days(record["created_at"], now_utc)
        rank = valid_rank
        valid_rank += 1

        if max_age is not None and age_days is not None and age_days > max_age:
            entries.append(
                _entry(record, CLASS_CLEANUP, "too_old", pinned=False, age_days=age_days)
            )
        elif keep_budget is not None and rank >= keep_budget:
            entries.append(
                _entry(
                    record,
                    CLASS_CLEANUP,
                    "beyond_max_keep",
                    pinned=False,
                    age_days=age_days,
                )
            )
        else:
            entries.append(
                _entry(record, CLASS_KEEP, "within_keep", pinned=False, age_days=age_days)
            )

    return ReplayJanitorPlan(
        repo_path=str(repo),
        generated_at=now_utc.isoformat(),
        max_age_days=max_age,
        max_keep=keep_budget,
        include_invalid=include_invalid,
        pinned_ids=sorted(pinned),
        entries=entries,
    )


def format_replay_janitor_markdown(plan: ReplayJanitorPlan) -> str:
    """Render a dry-run plan as read-only markdown."""
    lines = [
        "# Replay Janitor Dry-Run",
        "",
        f"- Repo: {plan.repo_path}",
        f"- Generated: {plan.generated_at}",
        f"- Max age (days): {plan.max_age_days if plan.max_age_days is not None else 'unset'}",
        f"- Max keep: {plan.max_keep if plan.max_keep is not None else 'unset'}",
        f"- Include invalid: {plan.include_invalid}",
        f"- Pinned: {', '.join(plan.pinned_ids) if plan.pinned_ids else 'none'}",
        f"- Keep: {plan.keep_count}; "
        f"Cleanup candidates: {plan.cleanup_count}; "
        f"Invalid/unreadable: {plan.invalid_count}",
        "",
        f"> {plan.guardrail_note}",
        "",
        "_Dry-run only: no bundle is deleted and no manifest is modified._",
        "",
        "## Bundles",
    ]
    if not plan.entries:
        lines.extend(["", "_No replay bundles found._"])
        return "\n".join(lines) + "\n"

    for entry in plan.entries:
        pinned_marker = " (pinned)" if entry.pinned else ""
        age = "unknown" if entry.age_days is None else f"{entry.age_days:.2f}"
        lines.extend(
            [
                "",
                f"### {entry.replay_id}{pinned_marker}",
                "",
                f"- Classification: {entry.classification}",
                f"- Reason: {entry.reason}",
                f"- Created: {entry.created_at or 'unknown'}",
                f"- Run kind: {entry.run_kind or 'unknown'}",
                f"- Age (days): {age}",
            ]
        )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ReplayCleanupResult:
    confirmed: bool
    confirm_token_required: str
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    plan_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_replay_cleanup(
    repo_path: str | Path,
    *,
    confirm: str | None = None,
    max_age_days: float | None = None,
    max_keep: int | None = None,
    pinned_ids: Iterable[str] = (),
    now: datetime | None = None,
) -> ReplayCleanupResult:
    """Confirmation-gated deletion of ``cleanup_candidate`` replay bundles.

    The deletion plan is produced by the read-only :func:`plan_replay_cleanup`
    with ``include_invalid=False`` so invalid/unreadable bundles are *never*
    deletion targets in this phase. Only bundles classified
    ``cleanup_candidate`` (never ``keep``, never pinned, never invalid) are
    eligible, and nothing is deleted unless ``confirm`` exactly equals
    :data:`CONFIRM_TOKEN`.
    """
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_path}")

    plan = plan_replay_cleanup(
        repo,
        max_age_days=max_age_days,
        max_keep=max_keep,
        include_invalid=False,
        pinned_ids=pinned_ids,
        now=now,
    )

    candidates = [
        entry.replay_id
        for entry in plan.entries
        if entry.classification == CLASS_CLEANUP
    ]
    non_candidates = [
        entry.replay_id
        for entry in plan.entries
        if entry.classification != CLASS_CLEANUP
    ]
    plan_summary = plan.to_dict()

    if confirm != CONFIRM_TOKEN:
        return ReplayCleanupResult(
            confirmed=False,
            confirm_token_required=CONFIRM_TOKEN,
            deleted=[],
            skipped=non_candidates,
            blocked=candidates,
            errors=[],
            plan_summary=plan_summary,
        )

    replays_root = (repo / REPLAYS_SUBDIR).resolve()
    deleted: list[str] = []
    errors: list[dict[str, str]] = []
    for replay_id in candidates:
        try:
            safe_id = _validate_replay_id(replay_id)
            bundle_dir = (replays_root / safe_id).resolve()
            if not bundle_dir.exists():
                # Already gone (idempotent re-run); nothing to do.
                continue
            _rmtree_contained(replays_root, bundle_dir)
            deleted.append(safe_id)
        except (ValueError, OSError) as exc:
            errors.append({"replay_id": replay_id, "error": str(exc)})

    return ReplayCleanupResult(
        confirmed=True,
        confirm_token_required=CONFIRM_TOKEN,
        deleted=deleted,
        skipped=non_candidates,
        blocked=[],
        errors=errors,
        plan_summary=plan_summary,
    )


def _rmtree_contained(replays_root: Path, target: Path) -> None:
    """Delete ``target`` only when it is a real directory strictly inside
    ``replays_root``. This is the sole deletion primitive in this module."""
    root = replays_root.resolve()
    resolved = target.resolve()
    if resolved == root:
        raise ValueError(f"refusing to delete replays root: {resolved}")
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"deletion target escapes replays dir: {resolved}"
        ) from exc
    if not resolved.is_dir():
        raise ValueError(f"deletion target is not a directory: {resolved}")
    shutil.rmtree(resolved)


def _scan_bundles(repo: Path) -> list[dict[str, Any]]:
    root = (repo / REPLAYS_SUBDIR).resolve()
    if not root.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for bundle_dir in root.iterdir():
        if not bundle_dir.is_dir():
            continue
        replay_id = bundle_dir.name
        try:
            safe_id = _validate_replay_id(replay_id)
        except ValueError:
            # A directory name that is not a legal replay id is unreadable.
            records.append(
                {
                    "replay_id": replay_id,
                    "valid": False,
                    "created_at": None,
                    "run_kind": None,
                }
            )
            continue

        manifest = _read_manifest_safely(repo, safe_id, bundle_dir)
        if manifest is None:
            records.append(
                {
                    "replay_id": safe_id,
                    "valid": False,
                    "created_at": None,
                    "run_kind": None,
                }
            )
            continue

        records.append(
            {
                "replay_id": safe_id,
                "valid": True,
                "created_at": _string_or_none(manifest.get("created_at")),
                "run_kind": _string_or_none(manifest.get("run_kind")),
            }
        )

    records.sort(
        key=lambda item: (
            str(item.get("created_at") or ""),
            str(item.get("replay_id") or ""),
        ),
        reverse=True,
    )
    return records


def _read_manifest_safely(
    repo: Path,
    safe_id: str,
    bundle_dir: Path,
) -> dict[str, Any] | None:
    if not (bundle_dir / MANIFEST_NAME).is_file():
        return None
    try:
        return read_replay_manifest(repo, safe_id)
    except (ValueError, OSError):
        return None


def _entry(
    record: dict[str, Any],
    classification: str,
    reason: str,
    *,
    pinned: bool,
    age_days: float | None = None,
) -> ReplayJanitorEntry:
    return ReplayJanitorEntry(
        replay_id=record["replay_id"],
        classification=classification,
        reason=reason,
        pinned=pinned,
        created_at=record.get("created_at"),
        run_kind=record.get("run_kind"),
        age_days=age_days,
    )


def _age_days(created_at: str | None, now_utc: datetime) -> float | None:
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = now_utc - created.astimezone(timezone.utc)
    return delta.total_seconds() / 86400.0


def _coerce_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _validate_replay_id(replay_id: str) -> str:
    if not replay_id or replay_id != Path(replay_id).name:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if "/" in replay_id or "\\" in replay_id:
        raise ValueError(f"invalid replay id: {replay_id!r}")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in replay_id):
        raise ValueError(f"invalid replay id: {replay_id!r}")
    return replay_id


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
