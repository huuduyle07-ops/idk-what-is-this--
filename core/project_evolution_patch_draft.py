from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import project_evolution_approval as approval_core


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_patch_draft_package_v1"
SOURCE_PLAN_SCHEMA_VERSION = "migration_plan_dry_run_v1"
APPROVAL_SCHEMA_VERSION = "evolution_plan_review_v1"
PATCH_DRAFTS_DIRNAME = "patch_drafts"
DEFAULT_MAX_FILES = 12


def build_project_evolution_patch_draft_package(
    repo_path: str,
    approval_path: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    draft_title: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    source_plan_load = approval_core.load_latest_project_evolution_plan(str(repo_root))
    if source_plan_load["status"] != "ok" or not source_plan_load.get("source_plan"):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load.get("source_plan_path", ""),
            source_plan_hash="",
            approval_path="",
            approval_hash_or_id="",
            migration_goal="",
            draft_title=draft_title,
            notes=notes,
            message=source_plan_load.get("message", "migration plan is unavailable"),
            code="source_plan_unavailable",
        )

    if max_files < 1:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=source_plan_load["source_plan_hash"],
            approval_path="",
            approval_hash_or_id="",
            migration_goal=source_plan_load["source_plan"].get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message="max_files must be at least 1",
            code="invalid_max_files",
        )

    approval_resolved = _resolve_approval_path(repo_root, approval_path)
    if approval_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=source_plan_load["source_plan_hash"],
            approval_path=str(_resolve_approval_candidate(repo_root, approval_path)),
            approval_hash_or_id=_approval_id_from_path(approval_path),
            migration_goal=source_plan_load["source_plan"].get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message=(
                "approval record must live inside .agent/project_evolution/approvals/"
            ),
            code="approval_path_outside_approvals",
        )

    approval_load = _load_approval_record(approval_resolved)
    if approval_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=source_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            migration_goal=source_plan_load["source_plan"].get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message=approval_load["message"],
            code=approval_load.get("code", "approval_unavailable"),
        )

    approval_record = approval_load["record"]
    current_plan = source_plan_load["source_plan"]
    current_hash = source_plan_load["source_plan_hash"]
    if approval_record.get("decision") != "approve":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            migration_goal=current_plan.get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message="approval decision must be approve before a draft package can be created",
            code="approval_not_approved",
        )

    if approval_record.get("patch_generation_allowed") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            migration_goal=current_plan.get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message="approval record does not allow patch generation",
            code="approval_patch_gate_closed",
        )

    approval_source_hash = str(approval_record.get("source_plan_hash") or "")
    if approval_source_hash != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            migration_goal=current_plan.get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message=(
                "approval source_plan_hash does not match the current normalized migration plan hash"
            ),
            code="approval_source_hash_mismatch",
        )

    if approval_record.get("human_approval_recorded") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=source_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            migration_goal=current_plan.get("migration_goal", ""),
            draft_title=draft_title,
            notes=notes,
            message="approval record is missing the manual approval marker",
            code="approval_not_recorded",
        )

    likely_files = _normalize_plan_files(current_plan.get("likely_affected_files", []), max_files=max_files)
    files_to_read_first = _normalize_plan_files(
        current_plan.get("full_files_to_read_before_patching", []),
        max_files=max_files,
    )
    groups = _build_change_groups(likely_files, files_to_read_first)
    test_requirements = _normalize_string_list(current_plan.get("test_plan", []))
    docs_requirements = _normalize_string_list(current_plan.get("docs_plan", []))
    config_requirements = _build_config_requirements(current_plan)
    rollback_requirements = _normalize_string_list(current_plan.get("rollback_plan", []))
    risks = _normalize_string_list(current_plan.get("risks", []))
    open_questions = _normalize_string_list(current_plan.get("open_questions", []))
    human_next_steps = _build_human_next_steps(
        current_plan=current_plan,
        files_to_read_first=files_to_read_first,
        groups=groups,
    )
    limitations = [
        "This is a draft package only. No patch was generated, applied, or validated.",
        "The package uses the approved migration plan and does not invent exact diffs.",
        "Approval remains valid only while the current migration plan hash matches the approval record.",
        "No model/API calls, patch generation, patch application, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
    ]

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "draft_title": _normalize_text(draft_title) or "Project Evolution Patch Draft Package",
        "notes": _normalize_text(notes),
        "source_plan_path": source_plan_load["source_plan_path"],
        "source_plan_hash": current_hash,
        "approval_path": str(approval_resolved),
        "approval_hash_or_id": _approval_id_from_path(approval_resolved.name),
        "approval_decision": approval_record.get("decision", ""),
        "approval_source_hash_matched": True,
        "migration_goal": current_plan.get("migration_goal", ""),
        "patch_generation_allowed": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "draft_package_only": True,
        "likely_files_to_change": likely_files,
        "files_to_read_first": files_to_read_first,
        "proposed_change_groups": groups,
        "test_requirements": test_requirements,
        "docs_requirements": docs_requirements,
        "config_requirements": config_requirements,
        "rollback_requirements": rollback_requirements,
        "risks": risks,
        "open_questions": open_questions,
        "human_next_steps": human_next_steps,
        "limitations": limitations,
    }


def render_project_evolution_patch_draft_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Patch Draft Package",
        "",
        "## Summary",
        f"- Repo path: `{record.get('repo_path', '')}`",
        f"- Mode: `{record.get('mode', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Draft title: {record.get('draft_title', '')}",
        f"- Source plan: `{record.get('source_plan_path', '')}`",
        f"- Source plan hash: `{record.get('source_plan_hash', '')}`",
        f"- Approval path: `{record.get('approval_path', '')}`",
        f"- Approval id: `{record.get('approval_hash_or_id', '')}`",
        "- This is a draft package only. No patch was generated, applied, or validated.",
        "",
        "## Approval Check",
        f"- Decision: `{record.get('approval_decision', '')}`",
        f"- Approval hash/id: `{record.get('approval_hash_or_id', '')}`",
        f"- Source hash matched current plan: `{record.get('approval_source_hash_matched', False)}`",
        f"- Patch generation allowed: `{record.get('patch_generation_allowed', False)}`",
        f"- Patch apply allowed: `{record.get('patch_apply_allowed', False)}`",
        f"- Validation execution allowed: `{record.get('validation_execution_allowed', False)}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Likely Files To Change",
        *_render_file_lines(record.get("likely_files_to_change", [])),
        "",
        "## Files To Read First",
        *_render_file_lines(record.get("files_to_read_first", [])),
        "",
        "## Proposed Change Groups",
        *_render_groups(record.get("proposed_change_groups", [])),
        "",
        "## Test Requirements",
        *_render_string_list(record.get("test_requirements", [])),
        "",
        "## Docs Requirements",
        *_render_string_list(record.get("docs_requirements", [])),
        "",
        "## Config Requirements",
        *_render_string_list(record.get("config_requirements", [])),
        "",
        "## Rollback Requirements",
        *_render_string_list(record.get("rollback_requirements", [])),
        "",
        "## Risks",
        *_render_string_list(record.get("risks", [])),
        "",
        "## Open Questions",
        *_render_string_list(record.get("open_questions", [])),
        "",
        "## Human Next Steps",
        *_render_string_list(record.get("human_next_steps", [])),
        "",
        "## Limitations",
        *_render_string_list(record.get("limitations", [])),
        "",
    ]
    if record.get("status") != "ok" and record.get("error"):
        lines.extend(
            [
                "## Error",
                f"- {record['error']['message']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_project_evolution_patch_draft_artifacts(
    repo_path: str,
    approval_path: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    draft_title: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_patch_draft_package(
        str(repo_root),
        approval_path,
        max_files=max_files,
        draft_title=draft_title,
        notes=notes,
    )
    if record.get("status") != "ok":
        return {"record": record, "json_path": "", "md_path": ""}

    draft_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_patch_draft_package"
    json_path = draft_root / f"{prefix}.json"
    md_path = draft_root / f"{prefix}.md"
    markdown = render_project_evolution_patch_draft_markdown(record)
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _load_approval_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "error",
            "code": "approval_missing",
            "message": f"approval record does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "code": "approval_invalid_json",
            "message": f"approval record is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "code": "approval_unreadable",
            "message": f"approval record could not be read: {path} ({exc})",
        }
    if not isinstance(record, dict) or record.get("schema_version") != APPROVAL_SCHEMA_VERSION:
        return {
            "status": "error",
            "code": "approval_bad_schema",
            "message": f"approval record has an unexpected schema: {path}",
        }
    return {"status": "ok", "record": record}


def _resolve_approval_path(repo_root: Path, approval_path: str) -> Path | None:
    approvals_root = (repo_root / ".agent" / "project_evolution" / "approvals").resolve()
    candidate = Path(approval_path).expanduser()
    resolved = candidate if candidate.is_absolute() else (repo_root / candidate)
    resolved = resolved.resolve()
    try:
        resolved.relative_to(approvals_root)
    except ValueError:
        return None
    return resolved


def _resolve_approval_candidate(repo_root: Path, approval_path: str) -> Path:
    candidate = Path(approval_path).expanduser()
    return candidate if candidate.is_absolute() else (repo_root / candidate)


def _resolve_output_root(repo_root: Path) -> Path:
    resolved = (repo_root / ".agent" / "project_evolution" / PATCH_DRAFTS_DIRNAME).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _build_error_record(
    *,
    repo_root: Path,
    source_plan_path: str,
    source_plan_hash: str,
    approval_path: str,
    approval_hash_or_id: str,
    migration_goal: str,
    draft_title: str | None,
    notes: str | None,
    message: str,
    code: str,
) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
        "draft_title": _normalize_text(draft_title) or "Project Evolution Patch Draft Package",
        "notes": _normalize_text(notes),
        "source_plan_path": source_plan_path,
        "source_plan_hash": source_plan_hash,
        "approval_path": approval_path,
        "approval_hash_or_id": approval_hash_or_id,
        "approval_decision": "",
        "approval_source_hash_matched": False,
        "migration_goal": migration_goal,
        "patch_generation_allowed": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "draft_package_only": False,
        "likely_files_to_change": [],
        "files_to_read_first": [],
        "proposed_change_groups": [],
        "test_requirements": [],
        "docs_requirements": [],
        "config_requirements": [],
        "rollback_requirements": [],
        "risks": [],
        "open_questions": [],
        "human_next_steps": [],
        "limitations": [
            "This is a draft package only. No patch was generated, applied, or validated.",
            "A matching approved migration plan is required before any draft package can be created.",
        ],
    }


def _build_change_groups(
    likely_files: list[dict[str, Any]],
    files_to_read_first: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets = [
        {
            "key": "provider",
            "title": "Provider abstraction changes",
            "summary": "Likely provider, embedding, and adapter surfaces that should stay compatible during the migration.",
            "files": [],
            "rationale": "These files look like the highest-risk provider abstraction and runtime wiring surfaces.",
        },
        {
            "key": "config",
            "title": "Config/env changes",
            "summary": "Configuration, environment, and dependency contract surfaces that can affect startup and runtime behavior.",
            "files": [],
            "rationale": "These files may need review for provider IDs, secrets, defaults, or dependency compatibility.",
        },
        {
            "key": "retrieval",
            "title": "Retrieval/indexing changes",
            "summary": "Retrieval, indexing, and graph-adjacent surfaces that can influence search or evidence flow.",
            "files": [],
            "rationale": "These files are likely to shape retrieval or index output after the migration.",
        },
        {
            "key": "graph",
            "title": "Graph/search integration changes",
            "summary": "Graph and search integration surfaces that may affect ranking or evidence ordering.",
            "files": [],
            "rationale": "These files may need careful review to keep ranking and graph evidence stable.",
        },
        {
            "key": "tests",
            "title": "Tests",
            "summary": "Regression coverage for migration-sensitive behavior.",
            "files": [],
            "rationale": "These tests should be updated or expanded before any patch work starts.",
        },
        {
            "key": "docs",
            "title": "Documentation",
            "summary": "Docs and migration notes that explain the new contract and rollout boundaries.",
            "files": [],
            "rationale": "These docs should stay aligned with the approved migration plan and its operator expectations.",
        },
        {
            "key": "rollback",
            "title": "Rollback/compatibility",
            "summary": "Entrypoints, compatibility shims, and other surfaces that should remain safe to revert.",
            "files": [],
            "rationale": "These files are the most likely rollback or compatibility anchors for the later patch phase.",
        },
    ]

    combined = _unique_file_entries([*likely_files, *files_to_read_first])
    seen_paths: set[str] = set()
    for item in combined:
        path = item["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        bucket = _group_key_for_path(path)
        _bucket_by_key(buckets, bucket)["files"].append(item)

    return [
        {
            "title": bucket["title"],
            "summary": bucket["summary"],
            "files": bucket["files"],
            "rationale": bucket["rationale"],
        }
        for bucket in buckets
        if bucket["files"]
    ]


def _group_key_for_path(path: str) -> str:
    lowered = path.lower()
    name = Path(path).name.lower()
    if lowered.startswith("tests/") or "/tests/" in lowered or "test_" in name:
        return "tests"
    if lowered.startswith("docs/") or lowered.endswith(".md"):
        return "docs"
    if (
        lowered in {"config.py", "settings.py", ".env.example", "requirements.txt", "pyproject.toml", "package.json", "pytest.ini"}
        or "config" in lowered
        or "settings" in lowered
        or ".env" in lowered
        or lowered.endswith((".toml", ".yaml", ".yml", ".json", ".ini"))
    ):
        return "config"
    if "retrieval" in lowered or "indexer" in lowered:
        return "retrieval"
    if "graph" in lowered or "weights" in lowered or "search" in lowered:
        return "graph"
    if "provider" in lowered or "embedding" in lowered or "model2vec" in lowered or "gemini" in lowered or "semble" in lowered:
        return "provider"
    return "rollback"


def _bucket_by_key(buckets: list[dict[str, Any]], key: str) -> dict[str, Any]:
    for bucket in buckets:
        if bucket["key"] == key:
            return bucket
    return buckets[-1]


def _build_config_requirements(plan: dict[str, Any]) -> list[str]:
    requirements = _normalize_string_list(plan.get("dependency_or_config_changes", []))
    for item in plan.get("likely_affected_files", []):
        path = str(item.get("path") or "")
        lowered = path.lower()
        if (
            lowered in {"config.py", "settings.py", ".env.example", "requirements.txt", "pyproject.toml", "package.json", "pytest.ini"}
            or "config" in lowered
            or "settings" in lowered
            or ".env" in lowered
        ):
            requirements.append(f"Confirm configuration compatibility for {path}.")
    return _unique_strings(requirements)


def _build_human_next_steps(
    *,
    current_plan: dict[str, Any],
    files_to_read_first: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> list[str]:
    steps = [
        "Read the files listed under Files To Read First before drafting any patch phase.",
        "Confirm the approved migration goal still matches the plan hash before any later work.",
        "Use the proposed change groups as the work order for the next patch-drafting phase, not as an exact diff.",
    ]
    if files_to_read_first:
        steps.append(
            f"Start with {files_to_read_first[0]['path']} and continue through the selected review set in order."
        )
    if current_plan.get("risk_tolerance"):
        steps.append(f"Keep the stated risk tolerance in view: {current_plan['risk_tolerance']}.")
    if groups:
        steps.append("Resolve config, provider, retrieval, graph, tests, docs, and rollback concerns in that order unless the approver says otherwise.")
    return _unique_strings(steps)


def _normalize_plan_files(items: list[Any], *, max_files: int) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items[:max_files]:
        if not isinstance(item, dict):
            continue
        path = _clean_rel_path(str(item.get("path") or ""))
        if not path:
            continue
        normalized.append(
            {
                "path": path,
                "category": _normalize_text(str(item.get("category") or "")),
                "reason": _normalize_text(str(item.get("reason") or "")),
                "confidence": _clamp_confidence(item.get("confidence", 0.0)),
            }
        )
    return normalized


def _normalize_string_list(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalize_text(str(value))
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _unique_file_entries(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        path = item.get("path", "")
        if path in seen:
            continue
        seen.add(path)
        unique.append(item)
    return unique


def _render_file_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- `{item.get('path', '')}`"
            + (f" - {item.get('category', '')}" if item.get("category") else "")
            + (f" - {item.get('reason', '')}" if item.get("reason") else "")
        )
    return lines


def _render_groups(groups: list[dict[str, Any]]) -> list[str]:
    if not groups:
        return ["- None"]
    lines: list[str] = []
    for group in groups:
        lines.append(f"- **{group.get('title', '')}**")
        if group.get("summary"):
            lines.append(f"  - {group['summary']}")
        for item in group.get("files", []):
            lines.append(f"  - `{item.get('path', '')}`")
        if group.get("rationale"):
            lines.append(f"  - {group['rationale']}")
    return lines


def _render_string_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]


def _resolve_approval_id(value: str) -> str:
    return Path(value).stem


def _approval_id_from_path(value: str) -> str:
    return Path(value).stem if value else ""


def _clean_rel_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return ""
    parts = []
    for part in candidate.parts:
        if part in {"..", "."}:
            return ""
        parts.append(part)
    return Path(*parts).as_posix() if parts else ""


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_timestamp(value: str) -> str:
    cleaned = value.replace(":", "").replace("-", "").replace("Z", "Z")
    return cleaned or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
