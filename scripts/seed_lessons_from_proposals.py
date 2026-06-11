#!/usr/bin/env python
"""Phase 6.4c: seed lesson candidates from validated proposal artifacts.

Reads existing `.agent/proposals/<run>/<item>/` directories and creates lesson
candidates only through the existing lesson_store / lesson_quality path. This
script never runs benchmarks, models, patch executors, validation commands, or
retrieval, and it never mutates source proposal artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PROPOSALS_ROOT = PROJECT_ROOT / ".agent" / "proposals"
DEFAULT_REPORTS_ROOT = PROJECT_ROOT / ".agent" / "reports"
SOURCE = "proposal_artifact"
_MAX_TEXT_CHARS = 600

_REQUIRED_ARTIFACTS = (
    "item.json",
    "case.json",
    "patch_proposal.json",
    "apply_result.json",
    "validation.json",
)


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _truncate(value: Any, limit: int = _MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path.name}: {e}") from e
    except OSError as e:
        raise ValueError(f"could not read {path.name}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def _missing_artifacts(proposal_dir: Path) -> list[str]:
    return [name for name in _REQUIRED_ARTIFACTS if not (proposal_dir / name).is_file()]


def _safe_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_proposal_ref(
    raw: str | Path,
    *,
    proposals_root: str | Path | None = None,
) -> Path:
    root = Path(proposals_root or DEFAULT_PROPOSALS_ROOT).resolve()
    text = _as_str(str(raw))
    if not text:
        raise ValueError("proposal ref is empty")
    if any(part == ".." for part in text.replace("\\", "/").split("/")):
        raise ValueError("proposal ref path traversal is not allowed")

    raw_path = Path(text).expanduser()
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    elif len(raw_path.parts) >= 2 and raw_path.parts[0] == ".agent" and raw_path.parts[1] == "proposals":
        candidate = (PROJECT_ROOT / raw_path).resolve()
    else:
        cwd_candidate = (Path.cwd() / raw_path).resolve()
        try:
            cwd_candidate.relative_to(root)
            if cwd_candidate.is_dir():
                candidate = cwd_candidate
            else:
                candidate = (root / raw_path).resolve()
        except ValueError:
            candidate = (root / raw_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(f"proposal ref is outside {root}: {candidate}") from e
    if not candidate.is_dir():
        raise ValueError(f"proposal ref does not exist or is not a directory: {candidate}")
    return candidate


def _resolve_run_dir(
    run_id: str,
    *,
    proposals_root: str | Path | None = None,
) -> Path:
    text = _as_str(run_id)
    if not text or "/" in text or "\\" in text or ".." in Path(text).parts:
        raise ValueError("run id must be a single proposal run directory name")
    root = Path(proposals_root or DEFAULT_PROPOSALS_ROOT).resolve()
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise ValueError(f"run id escapes proposal root: {text}") from e
    if not path.is_dir():
        raise ValueError(f"proposal run not found: {path}")
    return path


def _latest_run_dir(proposals_root: str | Path | None = None) -> Path:
    root = Path(proposals_root or DEFAULT_PROPOSALS_ROOT).resolve()
    if not root.is_dir():
        raise ValueError(f"proposal root not found: {root}")
    runs = [path for path in root.iterdir() if path.is_dir()]
    if not runs:
        raise ValueError(f"no proposal runs found in {root}")
    return max(runs, key=lambda p: (p.stat().st_mtime, p.name))


def _proposal_dirs_in_run(run_dir: Path) -> list[Path]:
    try:
        return sorted(path for path in run_dir.iterdir() if path.is_dir())
    except OSError:
        return []


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _proposal_source_hash(
    proposal: dict[str, Any],
    changed_files: list[str],
    validation: dict[str, Any],
) -> tuple[str, str, dict[str, str], str]:
    if proposal.get("patch_plan") is not None or proposal.get("patch_candidate") is not None:
        patch_hash = _hash_payload(
            {
                "patch_plan": proposal.get("patch_plan"),
                "patch_candidate": proposal.get("patch_candidate"),
            }
        )
        return (
            "patch_hash",
            patch_hash,
            {"patch_hash": patch_hash},
            f"patch_hash:{patch_hash}",
        )

    changed_files_hash = _hash_payload(sorted(changed_files))
    validation_hash = _hash_payload(validation)
    return (
        "changed_files_hash",
        changed_files_hash,
        {
            "changed_files_hash": changed_files_hash,
            "validation_hash": validation_hash,
        },
        f"changed_files_hash:{changed_files_hash}:validation_hash:{validation_hash}",
    )


def _load_optional_metadata(proposal_dir: Path) -> dict[str, Any]:
    path = proposal_dir / "source_metadata.json"
    if not path.is_file():
        return {}
    try:
        return _read_json(path)
    except ValueError:
        return {}


def _first_metadata_value(
    key: str,
    *sources: dict[str, Any],
) -> str:
    for source in sources:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _project_tag_for_repo(repo_path: str) -> str:
    if not repo_path:
        return ""
    try:
        from core.project_tag import build_project_tag

        return build_project_tag(repo_path)
    except Exception:
        return ""


def _resolve_scope(
    *,
    explicit_repo_path: str | None,
    global_candidate: bool,
    item: dict[str, Any],
    case: dict[str, Any],
    proposal: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if global_candidate:
        return {"scope": "global", "repo_path": None, "project_tag": None}, None

    repo_path = _as_str(explicit_repo_path) or _first_metadata_value(
        "repo_path",
        item,
        metadata,
        case,
        proposal,
    )
    project_tag = _first_metadata_value(
        "project_tag",
        item,
        metadata,
        case,
        proposal,
    )
    if repo_path and not project_tag:
        project_tag = _project_tag_for_repo(repo_path)

    if repo_path or project_tag:
        if not repo_path:
            return None, "missing_repo_path"
        return {
            "scope": "repo",
            "repo_path": repo_path or None,
            "project_tag": project_tag or None,
        }, None
    return None, "missing_repo_scope"


def _validation_ok(validation: dict[str, Any]) -> bool:
    return validation.get("validation_ok") is True or validation.get("ok") is True


def _apply_success(apply_result: dict[str, Any]) -> bool:
    return apply_result.get("success") is True


def _validation_summary(validation: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "validation_ok": validation.get("validation_ok"),
        "ok": validation.get("ok"),
        "command": validation.get("command"),
        "duration_sec": validation.get("duration_sec"),
    }
    output = _truncate(validation.get("output"))
    if output:
        summary["output_tail"] = output
    error = _truncate(validation.get("error"))
    if error:
        summary["error"] = error
    return summary


def _apply_summary(apply_result: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "success": apply_result.get("success"),
        "rollback_performed": apply_result.get("rollback_performed"),
        "applied_ops_count": len(apply_result.get("applied_ops") or []),
    }
    error = _truncate(apply_result.get("error"))
    if error:
        summary["error"] = error
    return summary


def _existing_source_keys(
    *,
    repo_path: str | None = None,
    scope: str = "global",
) -> set[str]:
    from core.lesson_store import list_lessons

    keys: set[str] = set()
    if scope == "repo":
        lessons = list_lessons(
            repo_path=repo_path,
            include_global=False,
            scope="repo",
        )
    else:
        lessons = list_lessons(scope="global")
    for lesson in lessons:
        candidate = lesson.get("candidate")
        if isinstance(candidate, dict):
            key = candidate.get("source_key")
            if isinstance(key, str) and key.strip():
                keys.add(key)
    return keys


def _build_seed_candidate(
    proposal_dir: Path,
    *,
    proposal_ref: str,
    explicit_repo_path: str | None,
    global_candidate: bool,
    include_failed: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    missing = _missing_artifacts(proposal_dir)
    if missing:
        return None, "missing_artifacts"

    from scripts import create_lesson_from_proposal as proposal_lesson

    try:
        artifacts = proposal_lesson._load_artifacts(proposal_dir)
        candidate = proposal_lesson._build_candidate(artifacts)
    except (FileNotFoundError, ValueError):
        return None, "missing_artifacts"

    item = artifacts["item.json"]
    case = artifacts["case.json"]
    proposal = artifacts["patch_proposal.json"]
    apply_result = artifacts["apply_result.json"]
    validation = artifacts["validation.json"]
    metadata = _load_optional_metadata(proposal_dir)

    scope_data, scope_error = _resolve_scope(
        explicit_repo_path=explicit_repo_path,
        global_candidate=global_candidate,
        item=item,
        case=case,
        proposal=proposal,
        metadata=metadata,
    )
    if scope_data is None:
        return None, scope_error or "missing_repo_scope"

    apply_success = _apply_success(apply_result)
    validation_ok = _validation_ok(validation)
    if (not apply_success or not validation_ok) and not include_failed:
        return None, "failed_or_incomplete_evidence"

    changed_files = _as_str_list(candidate.get("changed_files"))
    hash_kind, source_hash, hash_fields, source_key_tail = _proposal_source_hash(
        proposal,
        changed_files,
        validation,
    )
    source_key = f"{proposal_ref}:{source_key_tail}"
    patch_summary = _truncate(proposal.get("summary") or candidate.get("summary"))
    worker_run_id = _first_metadata_value(
        "worker_run_id",
        item,
        metadata,
        proposal,
    ) or _first_metadata_value(
        "source_run_id",
        item,
        metadata,
        proposal,
    )

    candidate.update(
        {
            "source": SOURCE,
            "proposal_ref": proposal_ref,
            "source_key": source_key,
            hash_kind: source_hash,
            "scope": scope_data["scope"],
            "repo_path": scope_data.get("repo_path"),
            "project_tag": scope_data.get("project_tag"),
            "worker_run_id": worker_run_id or None,
            "apply_success": apply_success,
            "patch_summary": patch_summary,
            "validation_summary": _validation_summary(validation),
            "apply_summary": _apply_summary(apply_result),
        }
    )
    candidate.update(hash_fields)
    if include_failed and (not apply_success or not validation_ok):
        candidate["needs_human_review"] = True
        reasons = []
        if not apply_success:
            reasons.append("apply_result.success is false")
        if not validation_ok:
            reasons.append("validation_ok is false")
        candidate["review_evidence"] = "; ".join(reasons)
    return candidate, None


def _quality_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    from core.lesson_quality import evaluate_lesson_candidate

    return evaluate_lesson_candidate(candidate)


def _quality_status(evaluation: dict[str, Any]) -> str:
    return "blocked" if evaluation.get("promotion") == "blocked" else "candidate"


def _save_candidate(
    candidate: dict[str, Any],
    *,
    repo_path: str | None,
) -> dict[str, Any]:
    from core import lesson_store

    case_name = candidate.get("case_name") or None
    title = f"Proposal artifact lesson: {case_name or candidate.get('proposal_ref')}"
    summary = candidate.get("patch_summary") or candidate.get("summary") or ""
    tags = lesson_store.derive_lesson_tags(
        candidate,
        case_name=case_name,
        title=title,
        summary=summary,
    )

    previous_auto_active = getattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    lesson_store.config.LESSON_AUTO_ACTIVE = False
    try:
        return lesson_store.save_candidate_lesson(
            candidate,
            source=SOURCE,
            source_report=candidate.get("proposal_ref"),
            case_name=case_name,
            title=title,
            summary=summary,
            tags=tags,
            repo_path=repo_path,
            scope=candidate.get("scope"),
        )
    finally:
        lesson_store.config.LESSON_AUTO_ACTIVE = previous_auto_active


def _new_summary(*, dry_run: bool) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "dry_run": dry_run,
        "counts": {
            "created": 0,
            "blocked": 0,
            "skipped": 0,
            "duplicates": 0,
            "dry_run": 0,
        },
        "created": [],
        "blocked": [],
        "skipped": [],
        "duplicates": [],
        "dry_run_items": [],
        "summary_files": {},
    }


def _skip(summary: dict[str, Any], proposal_ref: str, reason: str) -> None:
    summary["counts"]["skipped"] += 1
    summary["skipped"].append({"proposal_ref": proposal_ref, "reason": reason})


def _append_lesson_summary(summary: dict[str, Any], lesson: dict[str, Any]) -> None:
    candidate = lesson.get("candidate") if isinstance(lesson.get("candidate"), dict) else {}
    entry = {
        "proposal_ref": candidate.get("proposal_ref"),
        "lesson_id": lesson.get("id"),
        "status": lesson.get("status"),
        "promotion": (lesson.get("evaluation") or {}).get("promotion"),
        "source_key": candidate.get("source_key"),
        "scope": lesson.get("scope") or candidate.get("scope"),
        "repo_scope_id": lesson.get("repo_scope_id"),
    }
    if lesson.get("status") == "blocked":
        summary["counts"]["blocked"] += 1
        summary["blocked"].append(entry)
    else:
        summary["counts"]["created"] += 1
        summary["created"].append(entry)


def seed_lessons_from_proposals(
    *,
    proposal_refs: list[str | Path],
    repo_path: str | None = None,
    dry_run: bool = False,
    include_failed: bool = False,
    global_candidate: bool = False,
    limit: int | None = None,
    proposals_root: str | Path | None = None,
    write_json_summary: bool = False,
    write_markdown_summary: bool = False,
    reports_root: str | Path | None = None,
) -> dict[str, Any]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be >= 0")

    root = Path(proposals_root or DEFAULT_PROPOSALS_ROOT).resolve()
    dirs = [_resolve_proposal_ref(ref, proposals_root=root) for ref in proposal_refs]
    if limit is not None:
        dirs = dirs[:limit]

    summary = _new_summary(dry_run=dry_run)
    existing_keys_by_scope: dict[tuple[str, str | None], set[str]] = {}

    for proposal_dir in dirs:
        proposal_ref = _safe_relative(proposal_dir, root)
        candidate, skip_reason = _build_seed_candidate(
            proposal_dir,
            proposal_ref=proposal_ref,
            explicit_repo_path=repo_path,
            global_candidate=global_candidate,
            include_failed=include_failed,
        )
        if candidate is None:
            _skip(summary, proposal_ref, skip_reason or "invalid_candidate")
            continue

        lesson_repo_path = candidate.get("repo_path") if candidate.get("scope") == "repo" else None
        cache_key = (str(candidate.get("scope") or "global"), lesson_repo_path)
        existing_keys = existing_keys_by_scope.get(cache_key)
        if existing_keys is None:
            existing_keys = _existing_source_keys(
                repo_path=lesson_repo_path,
                scope=str(candidate.get("scope") or "global"),
            )
            existing_keys_by_scope[cache_key] = existing_keys

        source_key = candidate.get("source_key")
        if isinstance(source_key, str) and source_key in existing_keys:
            summary["counts"]["duplicates"] += 1
            summary["duplicates"].append(
                {
                    "proposal_ref": proposal_ref,
                    "source_key": source_key,
                }
            )
            continue

        # A.12: compat check — detect lessons created by P1/P2/P3 paths (which
        # use source='patch_proposal' and source_report rather than source_key).
        # Old records may have no source_key so the check above misses them.
        from core.lesson_store import find_lesson_by_source_report as _find_by_sr

        compat_existing = _find_by_sr("patch_proposal", str(proposal_dir))
        if compat_existing:
            summary["counts"]["duplicates"] += 1
            summary["duplicates"].append(
                {
                    "proposal_ref": proposal_ref,
                    "source_key": source_key,
                    "compatibility_duplicate": True,
                }
            )
            continue

        evaluation = _quality_evaluation(candidate)
        candidate["lesson_quality"] = evaluation
        if include_failed and (
            not candidate.get("apply_success")
            or candidate.get("validation_ok") is not True
        ):
            promotion = evaluation.get("promotion")
            if promotion not in {"blocked", "needs_human_review"}:
                _skip(summary, proposal_ref, "failed_evidence_not_quality_gated")
                continue

        if dry_run:
            summary["counts"]["dry_run"] += 1
            summary["dry_run_items"].append(
                {
                    "proposal_ref": proposal_ref,
                    "source_key": source_key,
                    "would_status": _quality_status(evaluation),
                    "promotion": evaluation.get("promotion"),
                    "scope": candidate.get("scope"),
                }
            )
            continue

        lesson = _save_candidate(candidate, repo_path=lesson_repo_path)
        _append_lesson_summary(summary, lesson)
        if isinstance(source_key, str):
            existing_keys.add(source_key)

    if write_json_summary or write_markdown_summary:
        written = write_summary_files(
            summary,
            reports_root=reports_root or DEFAULT_REPORTS_ROOT,
            output_json=write_json_summary,
            output_markdown=write_markdown_summary,
        )
        summary["summary_files"].update(written)

    return summary


def _summary_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def render_markdown_summary(summary: dict[str, Any]) -> str:
    counts = summary.get("counts") or {}
    lines = [
        "# Proposal Lesson Seed Report",
        "",
        f"- Dry run: {bool(summary.get('dry_run'))}",
        f"- Created: {counts.get('created', 0)}",
        f"- Blocked: {counts.get('blocked', 0)}",
        f"- Skipped: {counts.get('skipped', 0)}",
        f"- Duplicates: {counts.get('duplicates', 0)}",
        f"- Dry-run candidates: {counts.get('dry_run', 0)}",
        "",
    ]
    for section, title in (
        ("created", "Created"),
        ("blocked", "Blocked"),
        ("duplicates", "Duplicates"),
        ("skipped", "Skipped"),
        ("dry_run_items", "Dry Run"),
    ):
        items = summary.get(section) or []
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for item in items:
            ref = item.get("proposal_ref") or "(unknown)"
            detail = item.get("lesson_id") or item.get("reason") or item.get("would_status")
            lines.append(f"- `{ref}`: {detail}")
        lines.append("")
    return "\n".join(lines)


def write_summary_files(
    summary: dict[str, Any],
    *,
    reports_root: str | Path = DEFAULT_REPORTS_ROOT,
    output_json: bool = False,
    output_markdown: bool = False,
) -> dict[str, str]:
    root = Path(reports_root)
    root.mkdir(parents=True, exist_ok=True)
    ts = _summary_timestamp()
    written: dict[str, str] = {}
    if output_json:
        path = root / f"proposal_lesson_seed_report_{ts}.json"
        path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written["json"] = str(path)
    if output_markdown:
        path = root / f"proposal_lesson_seed_report_{ts}.md"
        path.write_text(render_markdown_summary(summary), encoding="utf-8")
        written["markdown"] = str(path)
    return written


def print_summary(summary: dict[str, Any]) -> None:
    counts = summary.get("counts") or {}
    print(f"Created: {counts.get('created', 0)}")
    print(f"Blocked: {counts.get('blocked', 0)}")
    print(f"Skipped: {counts.get('skipped', 0)}")
    print(f"Duplicates: {counts.get('duplicates', 0)}")
    if summary.get("dry_run"):
        print(f"Dry-run candidates: {counts.get('dry_run', 0)}")

    for key, label in (
        ("created", "created"),
        ("blocked", "blocked"),
        ("duplicates", "duplicate"),
        ("skipped", "skipped"),
        ("dry_run_items", "dry-run"),
    ):
        for item in summary.get(key) or []:
            ref = item.get("proposal_ref") or "(unknown)"
            detail = (
                item.get("lesson_id")
                or item.get("reason")
                or item.get("would_status")
                or item.get("source_key")
                or ""
            )
            print(f"  {label}: {ref} {detail}".rstrip())

    files = summary.get("summary_files") or {}
    if files.get("json"):
        print(f"JSON summary: {files['json']}")
    if files.get("markdown"):
        print(f"Markdown summary: {files['markdown']}")


def _refs_from_args(args: argparse.Namespace) -> list[Path]:
    if args.latest:
        return _proposal_dirs_in_run(_latest_run_dir())
    if args.run:
        return _proposal_dirs_in_run(_resolve_run_dir(args.run))
    assert args.proposal_ref
    return [_resolve_proposal_ref(args.proposal_ref)]


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create lesson candidates from existing proposal artifacts.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--latest", action="store_true", help="Use the newest proposal run.")
    source.add_argument("--proposal-ref", help="Proposal item ref under .agent/proposals/.")
    source.add_argument("--run", help="Proposal run id under .agent/proposals/.")
    parser.add_argument("--limit", type=int, help="Seed at most N proposal item dirs.")
    parser.add_argument("--repo-path", help="Repo path for repo-scoped candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write lessons.")
    parser.add_argument(
        "--include-failed",
        action="store_true",
        help="Include failed apply/validation evidence; lesson_quality must gate it.",
    )
    parser.add_argument(
        "--global-candidate",
        action="store_true",
        help=(
            "SCARY: create global candidates instead of repo-scoped candidates. "
            "This still never promotes to active."
        ),
    )
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--markdown-summary", action="store_true")
    args = parser.parse_args(argv)

    try:
        refs = _refs_from_args(args)
        summary = seed_lessons_from_proposals(
            proposal_refs=refs,
            repo_path=args.repo_path,
            dry_run=args.dry_run,
            include_failed=args.include_failed,
            global_candidate=args.global_candidate,
            limit=args.limit,
            write_json_summary=args.json_summary,
            write_markdown_summary=args.markdown_summary,
        )
    except ValueError as e:
        print(f"[proposal_lesson_seed] error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(
            f"[proposal_lesson_seed] unexpected {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
