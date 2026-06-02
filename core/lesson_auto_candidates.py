"""Phase 6.4e: optional, gated creation of repo-scoped lesson CANDIDATES from
Dream/proposal artifacts.

Closes the deferred Phase 6.4 follow-up while preserving the manual-safe memory
contract:

    * Auto-CREATE candidate lessons is allowed.
    * Auto-PROMOTE to active lessons is NOT allowed.

Every public function is an EXACT no-op unless ``enabled=True`` is passed by an
explicit operator action (web button / CLI / config flag). When enabled, lesson
candidates are created ONLY through ``core.lesson_store`` /
``core.lesson_quality`` so the existing lesson_quality gate stays the routing
authority, and ``LESSON_AUTO_ACTIVE`` is forced off around every write so a
candidate can never land in ``active/``.

This module deliberately never:
    * runs benchmarks, models, patch executors, validation commands, or Dream
      execution (it only READS already-written artifacts),
    * imports the Dream runner ``core.sleeping_consultant`` (which pulls in the
      patch executor and model clients),
    * mutates the source Dream/proposal artifacts,
    * writes directly to ``active/``,
    * enables ``LESSON_RETRIEVAL_ENABLED``,
    * touches the CONTROL prompt.

The proposal path delegates entirely to ``scripts.seed_lessons_from_proposals``
so dedup, scope resolution, ``include_failed`` routing, byte-safety, and
lesson_quality gating are byte-for-byte identical to that seeder. The Dream path
reads the ``patch_revalidation_pass{N}.json`` artifact that the Dream
revalidation pass already wrote (it embeds a ready-made ``lesson_candidate``).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Uniform result statuses returned by every public function.
STATUS_DISABLED = "disabled"
STATUS_CREATED = "created"
STATUS_BLOCKED = "blocked"
STATUS_DUPLICATE = "duplicate"
STATUS_SKIPPED = "skipped"

PROPOSAL_SOURCE = "proposal_artifact"
DREAM_SOURCE = "dream_artifact"

_MAX_TEXT_CHARS = 600

# Mirror core.sleeping_consultant._LESSON_FORBIDDEN_PATH_PARTS WITHOUT importing
# that module (importing it would pull in the patch executor + model clients).
_DREAM_FORBIDDEN_PATH_PARTS = {".agent", ".git", "node_modules", "target"}

_REVALIDATION_RE = re.compile(r"^patch_revalidation_pass(\d+)\.json$")


# ---------------------------------------------------------------------------
# Uniform result helpers
# ---------------------------------------------------------------------------
def _result(
    status: str,
    *,
    source: str | None = None,
    scope: str | None = None,
    source_key: str | None = None,
    lesson_id: str | None = None,
    promotion: str | None = None,
    reason: str | None = None,
    active_knowledge_allowed: bool = False,
    repo_scope_id: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "scope": scope,
        "source_key": source_key,
        "lesson_id": lesson_id,
        "promotion": promotion,
        "reason": reason,
        "active_knowledge_allowed": active_knowledge_allowed,
        "repo_scope_id": repo_scope_id,
    }


def _disabled(source: str) -> dict[str, Any]:
    return _result(STATUS_DISABLED, source=source, reason="auto_candidate_creation_disabled")


# ===========================================================================
# Proposal path — delegate to the existing proposal seeder.
# ===========================================================================
def maybe_create_lesson_candidate_from_proposal(
    proposal_dir: str | Path,
    repo_path: str | None = None,
    *,
    enabled: bool = False,
    global_candidate: bool = False,
    include_failed: bool = False,
    proposals_root: str | Path | None = None,
) -> dict[str, Any]:
    """Optionally create a lesson candidate from one proposal artifact dir.

    Exact no-op unless ``enabled=True``. Repo-scoped by default when
    ``repo_path`` is given; ``global_candidate=True`` is required to create a
    global candidate. Never promotes to active. Returns a uniform result dict
    with ``status`` in {disabled, created, blocked, duplicate, skipped}.
    """
    if not enabled:
        return _disabled(PROPOSAL_SOURCE)

    # Lazy import keeps the disabled path an exact no-op and keeps this module's
    # import surface tiny (the AST guard depends on that).
    from scripts import seed_lessons_from_proposals as seeder

    root = Path(proposals_root) if proposals_root else Path(seeder.DEFAULT_PROPOSALS_ROOT)
    try:
        summary = seeder.seed_lessons_from_proposals(
            proposal_refs=[proposal_dir],
            repo_path=repo_path,
            include_failed=include_failed,
            global_candidate=global_candidate,
            proposals_root=root,
        )
    except ValueError as e:
        # Bad ref / path traversal / outside-root → friendly skip, never a crash.
        return _result(STATUS_SKIPPED, source=PROPOSAL_SOURCE, reason=str(e))

    return _summary_to_result(summary, source=PROPOSAL_SOURCE)


def _summary_to_result(summary: dict[str, Any], *, source: str) -> dict[str, Any]:
    """Translate a single-ref seeder summary into the uniform result dict."""
    counts = summary.get("counts") or {}

    if counts.get("created"):
        entry = (summary.get("created") or [{}])[0]
        return _result(
            STATUS_CREATED,
            source=source,
            scope=entry.get("scope"),
            source_key=entry.get("source_key"),
            lesson_id=entry.get("lesson_id"),
            promotion=entry.get("promotion"),
            reason="created_candidate",
            active_knowledge_allowed=False,
            repo_scope_id=entry.get("repo_scope_id"),
        )
    if counts.get("blocked"):
        entry = (summary.get("blocked") or [{}])[0]
        return _result(
            STATUS_BLOCKED,
            source=source,
            scope=entry.get("scope"),
            source_key=entry.get("source_key"),
            lesson_id=entry.get("lesson_id"),
            promotion=entry.get("promotion"),
            reason="blocked_by_lesson_quality",
            active_knowledge_allowed=False,
            repo_scope_id=entry.get("repo_scope_id"),
        )
    if counts.get("duplicates"):
        entry = (summary.get("duplicates") or [{}])[0]
        return _result(
            STATUS_DUPLICATE,
            source=source,
            source_key=entry.get("source_key"),
            reason="duplicate_source_key",
        )
    if counts.get("skipped"):
        entry = (summary.get("skipped") or [{}])[0]
        return _result(STATUS_SKIPPED, source=source, reason=entry.get("reason") or "skipped")
    if counts.get("dry_run"):
        entry = (summary.get("dry_run_items") or [{}])[0]
        return _result(
            STATUS_SKIPPED, source=source, source_key=entry.get("source_key"), reason="dry_run"
        )
    return _result(STATUS_SKIPPED, source=source, reason="no_candidate")


# ===========================================================================
# Dream path — read an already-written ready_to_apply revalidation artifact.
# ===========================================================================
def maybe_create_lesson_candidate_from_dream_item(
    dream_item: str | Path | dict[str, Any],
    repo_path: str | None = None,
    *,
    enabled: bool = False,
    global_candidate: bool = False,
    include_failed: bool = False,
    dreams_root: str | Path | None = None,
) -> dict[str, Any]:
    """Optionally create a lesson candidate from one Dream ``ready_to_apply``
    item that has a ``patch_revalidation_pass{N}.json`` artifact.

    ``dream_item`` may be the item directory (str/Path) or a Dream item record
    dict carrying ``item_dir`` / ``item_dir_path``. Exact no-op unless
    ``enabled=True``. Repo-scoped by default; never promotes to active.
    """
    if not enabled:
        return _disabled(DREAM_SOURCE)

    try:
        item_dir, record, dream_ref = _resolve_dream_item(dream_item, repo_path, dreams_root)
    except ValueError as e:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason=str(e))

    artifact_path = _latest_revalidation_artifact(item_dir)
    if artifact_path is None:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason="no_revalidation_evidence")

    try:
        artifact = _read_json_object(artifact_path)
    except ValueError:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason="invalid_revalidation_artifact")

    candidate = _dream_candidate_from_artifact(artifact)
    if candidate is None:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason="incomplete_evidence")

    apply_success = bool(artifact.get("success"))
    validation_ok = candidate.get("validation_ok") is True
    if (not apply_success or not validation_ok) and not include_failed:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason="failed_or_incomplete_evidence")

    scope_data, scope_err = _resolve_dream_scope(repo_path, global_candidate, record)
    if scope_data is None:
        return _result(STATUS_SKIPPED, source=DREAM_SOURCE, reason=scope_err)

    source_key = _dream_source_key(dream_ref, item_dir, candidate)
    _enrich_dream_candidate(
        candidate,
        record=record,
        dream_ref=dream_ref,
        source_key=source_key,
        scope_data=scope_data,
        apply_success=apply_success,
        validation_ok=validation_ok,
        include_failed=include_failed,
    )

    lesson_repo_path = scope_data["repo_path"] if scope_data["scope"] == "repo" else None

    # Dedup by source_key against existing lessons in the same scope. Reuses the
    # proposal seeder's helper so behavior is identical across sources.
    from scripts.seed_lessons_from_proposals import _existing_source_keys

    existing = _existing_source_keys(repo_path=lesson_repo_path, scope=scope_data["scope"])
    if source_key in existing:
        return _result(
            STATUS_DUPLICATE,
            source=DREAM_SOURCE,
            scope=scope_data["scope"],
            source_key=source_key,
            reason="duplicate_source_key",
        )

    # Mirror the proposal seeder's failed-evidence quality gate: only persist
    # failed evidence when lesson_quality routes it to blocked / needs review.
    from core.lesson_quality import evaluate_lesson_candidate

    evaluation = evaluate_lesson_candidate(candidate)
    candidate["lesson_quality"] = evaluation
    if include_failed and (not apply_success or not validation_ok):
        if evaluation.get("promotion") not in {"blocked", "needs_human_review"}:
            return _result(
                STATUS_SKIPPED, source=DREAM_SOURCE, reason="failed_evidence_not_quality_gated"
            )

    lesson = _save_dream_candidate(candidate, scope_data=scope_data)
    status = STATUS_BLOCKED if lesson.get("status") == "blocked" else STATUS_CREATED
    return _result(
        status,
        source=DREAM_SOURCE,
        scope=lesson.get("scope"),
        source_key=source_key,
        lesson_id=lesson.get("id"),
        promotion=(lesson.get("evaluation") or {}).get("promotion"),
        reason="blocked_by_lesson_quality" if status == STATUS_BLOCKED else "created_candidate",
        active_knowledge_allowed=lesson.get("active_knowledge_allowed") is True,
        repo_scope_id=lesson.get("repo_scope_id"),
    )


# ---------------------------------------------------------------------------
# Dream helpers (read-only; never mutate artifacts)
# ---------------------------------------------------------------------------
def _coerce_dir_ref(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("dream item ref is empty")
    if any(part == ".." for part in text.replace("\\", "/").split("/")):
        raise ValueError("dream item ref path traversal is not allowed")
    return text


def _resolve_dream_item(
    dream_item: str | Path | dict[str, Any],
    repo_path: str | None,
    dreams_root: str | Path | None,
) -> tuple[Path, dict[str, Any], str]:
    record: dict[str, Any] = {}
    if isinstance(dream_item, dict):
        record = dream_item
        raw = record.get("item_dir") or record.get("item_dir_path") or ""
        if not raw:
            raise ValueError("dream item record has no item_dir")
    else:
        raw = dream_item

    text = _coerce_dir_ref(raw)
    item_dir = Path(text).expanduser()

    root: Path | None = None
    if dreams_root is not None:
        root = Path(dreams_root).resolve()
    elif repo_path:
        try:
            from core.dream_artifacts import dreams_root as _dreams_root

            root = _dreams_root(repo_path).resolve()
        except Exception:
            root = None

    if not item_dir.is_absolute() and root is not None:
        item_dir = root / item_dir
    item_dir = item_dir.resolve()

    if root is not None:
        try:
            item_dir.relative_to(root)
        except ValueError as e:
            raise ValueError(f"dream item ref is outside {root}") from e

    if not item_dir.is_dir():
        raise ValueError(f"dream item dir does not exist: {item_dir}")

    dream_ref = item_dir.relative_to(root).as_posix() if root is not None else item_dir.name
    return item_dir, record, dream_ref


def _latest_revalidation_artifact(item_dir: Path) -> Path | None:
    best: tuple[int, Path] | None = None
    for path in item_dir.glob("patch_revalidation_pass*.json"):
        match = _REVALIDATION_RE.match(path.name)
        if not match:
            continue
        pass_num = int(match.group(1))
        if best is None or pass_num > best[0]:
            best = (pass_num, path)
    return best[1] if best is not None else None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"could not read {path.name}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def _dream_candidate_from_artifact(artifact: dict[str, Any]) -> dict[str, Any] | None:
    embedded = artifact.get("lesson_candidate")
    if isinstance(embedded, dict) and embedded:
        candidate = dict(embedded)  # copy; never mutate the source artifact dict
    else:
        changed_files = artifact.get("changed_files")
        if not isinstance(changed_files, list):
            return None
        files = [str(f) for f in changed_files if str(f).strip()]
        candidate = {
            "validation_ok": artifact.get("validation_ok"),
            "touched_forbidden_files": _touched_forbidden_files(files),
            "missing_expected_files": [],
            "patch_kind": "patch_plan",
            "rollback_happened": bool(artifact.get("rollback_performed")),
            "changed_files": files,
            "diff": artifact.get("diff") or "",
            "diffs": artifact.get("diffs") or [],
        }

    files = candidate.get("changed_files")
    if not isinstance(files, list) or not [str(f) for f in files if str(f).strip()]:
        return None
    return candidate


def _touched_forbidden_files(changed_files: list[str]) -> list[str]:
    forbidden: list[str] = []
    for path in changed_files:
        norm = str(path or "").strip().replace("\\", "/")
        parts = [p for p in norm.lower().split("/") if p]
        if any(p in _DREAM_FORBIDDEN_PATH_PARTS for p in parts):
            forbidden.append(norm)
            continue
        if any(p == ".env" or p.startswith(".env.") for p in parts):
            forbidden.append(norm)
    return forbidden


def _resolve_dream_scope(
    repo_path: str | None,
    global_candidate: bool,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if global_candidate:
        return {"scope": "global", "repo_path": None, "project_tag": None}, None

    rp = repo_path.strip() if isinstance(repo_path, str) else None
    if not rp:
        candidate_rp = record.get("repo_path") if isinstance(record, dict) else None
        if isinstance(candidate_rp, str) and candidate_rp.strip():
            rp = candidate_rp.strip()
    if not rp:
        return None, "missing_repo_path"

    return {"scope": "repo", "repo_path": rp, "project_tag": _project_tag_for_repo(rp)}, None


def _project_tag_for_repo(repo_path: str | None) -> str | None:
    if not repo_path:
        return None
    try:
        from core.project_tag import build_project_tag

        return build_project_tag(repo_path)
    except Exception:
        return None


def _dream_source_key(dream_ref: str, item_dir: Path, candidate: dict[str, Any]) -> str:
    plan_path = item_dir / "patch_plan.json"
    if plan_path.is_file():
        try:
            raw = plan_path.read_text(encoding="utf-8")
            digest = hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()[:16]
            return f"dream:{dream_ref}:patch_hash:{digest}"
        except OSError:
            pass
    payload = json.dumps(
        sorted(str(f) for f in (candidate.get("changed_files") or [])),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"dream:{dream_ref}:changed_files_hash:{digest}"


def _truncate(value: Any, limit: int = _MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _first_str(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key) if isinstance(record, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _enrich_dream_candidate(
    candidate: dict[str, Any],
    *,
    record: dict[str, Any],
    dream_ref: str,
    source_key: str,
    scope_data: dict[str, Any],
    apply_success: bool,
    validation_ok: bool,
    include_failed: bool,
) -> None:
    candidate.update(
        {
            "source": DREAM_SOURCE,
            "dream_ref": dream_ref,
            "source_key": source_key,
            "scope": scope_data["scope"],
            "repo_path": scope_data.get("repo_path"),
            "project_tag": scope_data.get("project_tag"),
            "case_name": _first_str(record, "case_name") or None,
            "language": _first_str(record, "language"),
            "category": _first_str(record, "category"),
            "patch_summary": _truncate(_first_str(record, "summary", "title", "hint")),
            "apply_success": apply_success,
        }
    )
    if include_failed and (not apply_success or not validation_ok):
        candidate["needs_human_review"] = True
        reasons: list[str] = []
        if not apply_success:
            reasons.append("dream revalidation apply failed")
        if not validation_ok:
            reasons.append("dream revalidation validation_ok is not true")
        candidate["review_evidence"] = "; ".join(reasons)


def _save_dream_candidate(candidate: dict[str, Any], *, scope_data: dict[str, Any]) -> dict[str, Any]:
    from core import lesson_store

    case_name = candidate.get("case_name") or None
    title = f"Dream artifact lesson: {case_name or candidate.get('dream_ref')}"
    summary = candidate.get("patch_summary") or ""
    tags = lesson_store.derive_lesson_tags(
        candidate, case_name=case_name, title=title, summary=summary
    )
    lesson_repo_path = scope_data["repo_path"] if scope_data["scope"] == "repo" else None

    # Force LESSON_AUTO_ACTIVE off so a dream candidate can never auto-promote to
    # active/, even if an operator left the flag on. Mirrors the seeders.
    previous_auto_active = getattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    lesson_store.config.LESSON_AUTO_ACTIVE = False
    try:
        return lesson_store.save_candidate_lesson(
            candidate,
            source=DREAM_SOURCE,
            source_report=candidate.get("dream_ref"),
            case_name=case_name,
            title=title,
            summary=summary,
            tags=tags,
            repo_path=lesson_repo_path,
            scope=scope_data["scope"],
        )
    finally:
        lesson_store.config.LESSON_AUTO_ACTIVE = previous_auto_active
