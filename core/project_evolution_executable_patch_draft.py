from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import project_evolution_approval as approval_core


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_executable_patch_draft_v1"
APPROVAL_SCHEMA_VERSION = "evolution_plan_review_v1"
DRAFT_PACKAGE_SCHEMA_VERSION = "evolution_patch_draft_package_v1"
CANDIDATES_SCHEMA_VERSION = "evolution_patch_candidates_v1"
TEXT_DRAFT_SCHEMA_VERSION = "evolution_patch_text_draft_v1"
EXECUTABLE_PATCH_DRAFTS_DIRNAME = "executable_patch_drafts"


def build_project_evolution_executable_patch_draft(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    patch_text_draft_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    current_plan_load = approval_core.load_latest_project_evolution_plan(str(repo_root))
    if current_plan_load["status"] != "ok" or not current_plan_load.get("source_plan"):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash="",
            approval_path="",
            patch_draft_package_path="",
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal="",
            message=current_plan_load.get("message", "migration plan is unavailable"),
            code="source_plan_unavailable",
        )

    current_hash = current_plan_load["source_plan_hash"]
    current_goal = current_plan_load["source_plan"].get("migration_goal", "")

    approval_resolved = _resolve_artifact_path(repo_root, approval_path, "approvals")
    if approval_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(_resolve_candidate_path(repo_root, approval_path)),
            patch_draft_package_path="",
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal=current_goal,
            message="approval record must live inside .agent/project_evolution/approvals/",
            code="approval_path_outside_approvals",
        )

    draft_resolved = _resolve_artifact_path(repo_root, patch_draft_package_path, "patch_drafts")
    if draft_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(_resolve_candidate_path(repo_root, patch_draft_package_path)),
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal=current_goal,
            message="patch draft package must live inside .agent/project_evolution/patch_drafts/",
            code="draft_path_outside_patch_drafts",
        )

    candidates_resolved = _resolve_artifact_path(repo_root, patch_candidates_path, "patch_candidates")
    if candidates_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(_resolve_candidate_path(repo_root, patch_candidates_path)),
            patch_text_draft_path="",
            migration_goal=current_goal,
            message="patch candidates must live inside .agent/project_evolution/patch_candidates/",
            code="candidates_path_outside_patch_candidates",
        )

    text_resolved = _resolve_artifact_path(repo_root, patch_text_draft_path, "patch_text_drafts")
    if text_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(_resolve_candidate_path(repo_root, patch_text_draft_path)),
            migration_goal=current_goal,
            message="patch text draft must live inside .agent/project_evolution/patch_text_drafts/",
            code="text_draft_path_outside_patch_text_drafts",
        )

    approval_load = _load_json_record(approval_resolved, APPROVAL_SCHEMA_VERSION, "approval")
    if approval_load["status"] != "ok":
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            approval_load["message"],
            approval_load["code"],
        )

    draft_load = _load_json_record(draft_resolved, DRAFT_PACKAGE_SCHEMA_VERSION, "patch draft package")
    if draft_load["status"] != "ok":
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            draft_load["message"],
            draft_load["code"],
        )

    candidates_load = _load_json_record(candidates_resolved, CANDIDATES_SCHEMA_VERSION, "patch candidates")
    if candidates_load["status"] != "ok":
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            candidates_load["message"],
            candidates_load["code"],
        )

    text_load = _load_json_record(text_resolved, TEXT_DRAFT_SCHEMA_VERSION, "patch text draft")
    if text_load["status"] != "ok":
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            text_load["message"],
            text_load["code"],
        )

    approval_record = approval_load["record"]
    draft_record = draft_load["record"]
    candidates_record = candidates_load["record"]
    text_record = text_load["record"]
    approval_id = _approval_id_from_path(approval_resolved.name)

    chain_error = _verify_chain(
        repo_root=repo_root,
        current_hash=current_hash,
        current_goal=current_goal,
        approval_resolved=approval_resolved,
        draft_resolved=draft_resolved,
        candidates_resolved=candidates_resolved,
        text_resolved=text_resolved,
        approval_record=approval_record,
        draft_record=draft_record,
        candidates_record=candidates_record,
        text_record=text_record,
        approval_id=approval_id,
    )
    if chain_error is not None:
        return chain_error

    allowed_paths = _approved_file_paths(
        current_plan=current_plan_load["source_plan"],
        draft_record=draft_record,
        candidates_record=candidates_record,
    )
    text_paths = _text_draft_file_paths(text_record)
    unapproved_text_paths = sorted(path for path in text_paths if path not in allowed_paths)
    if unapproved_text_paths:
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            f"patch text draft target files are not approved by the plan/draft/candidate chain: {', '.join(unapproved_text_paths)}",
            "text_target_file_not_approved",
        )

    target_files = _build_target_files(text_record, allowed_paths)
    edit_units = _build_executable_edit_units(text_record, allowed_paths)
    if not edit_units:
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            "patch text draft does not contain any approved target files for executable edit units",
            "executable_edit_units_missing",
        )

    tests_required_later = _normalize_string_list(
        [
            *draft_record.get("test_requirements", []),
            *candidates_record.get("tests_required", []),
            *text_record.get("tests_required_later", []),
        ]
    )
    rollback_notes = _normalize_string_list(
        [
            *draft_record.get("rollback_requirements", []),
            *candidates_record.get("rollback_notes", []),
            *text_record.get("rollback_notes", []),
        ]
    )
    risks = _normalize_string_list(
        [
            *draft_record.get("risks", []),
            *candidates_record.get("risks", []),
            *text_record.get("risks", []),
        ]
    )
    limitations = [
        "This is an executable patch draft format only. No patch was generated, applied, validated, or committed.",
        "Edit units intentionally contain placeholder old_text, new_text, and unified_diff values until a later full-file-read phase grounds them.",
        "Target files are constrained to files already present in the approved migration plan, patch draft package, or patch candidates package.",
        "No model/API calls, source mutation, patch apply, validation execution, benchmark execution, Docker/subprocess behavior, route changes, Debug Mode wiring, or lesson mutation occurs here.",
    ]

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "migration_goal": current_goal,
        "source_plan_hash": current_hash,
        "approval_path": str(approval_resolved),
        "patch_draft_package_path": str(draft_resolved),
        "patch_candidates_path": str(candidates_resolved),
        "patch_text_draft_path": str(text_resolved),
        "approval_verified": True,
        "approval_decision": approval_record.get("decision", ""),
        "executable_patch_draft_only": True,
        "source_files_mutated": False,
        "real_repo_apply_allowed": False,
        "sandbox_apply_allowed_later": True,
        "validation_execution_allowed": False,
        "requires_patch_safety_before_apply": True,
        "requires_sandbox_before_validation": True,
        "target_files": target_files,
        "executable_edit_units": edit_units,
        "tests_required_later": tests_required_later,
        "rollback_notes": rollback_notes,
        "risks": risks,
        "limitations": limitations,
        "human_next_steps": _build_human_next_steps(edit_units, text_record),
    }


def render_project_evolution_executable_patch_draft_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Executable Patch Draft",
        "",
        "## Summary",
        f"- Repo path: `{record.get('repo_path', '')}`",
        f"- Mode: `{record.get('mode', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Source plan hash: `{record.get('source_plan_hash', '')}`",
        f"- Target file count: `{len(record.get('target_files', []))}`",
        f"- Edit unit count: `{len(record.get('executable_edit_units', []))}`",
        "- No patch was generated, applied, validated, or committed.",
        "",
        "## Approval Verification",
        f"- Approval verified: `{record.get('approval_verified', False)}`",
        f"- Approval path: `{record.get('approval_path', '')}`",
        f"- Patch draft package: `{record.get('patch_draft_package_path', '')}`",
        f"- Patch candidates: `{record.get('patch_candidates_path', '')}`",
        f"- Patch text draft: `{record.get('patch_text_draft_path', '')}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Gates",
        f"- Executable patch draft only: `{record.get('executable_patch_draft_only', False)}`",
        f"- Source files mutated: `{record.get('source_files_mutated', True)}`",
        f"- Real repo apply allowed: `{record.get('real_repo_apply_allowed', True)}`",
        f"- Sandbox apply allowed later: `{record.get('sandbox_apply_allowed_later', False)}`",
        f"- Validation execution allowed: `{record.get('validation_execution_allowed', True)}`",
        f"- Requires patch safety before apply: `{record.get('requires_patch_safety_before_apply', False)}`",
        f"- Requires sandbox before validation: `{record.get('requires_sandbox_before_validation', False)}`",
        "",
        "## Target Files",
        *_render_file_lines(record.get("target_files", [])),
        "",
        "## Executable Edit Units",
        *_render_edit_units(record.get("executable_edit_units", [])),
        "",
        "## Tests Required Later",
        *_render_string_list(record.get("tests_required_later", [])),
        "",
        "## Rollback Notes",
        *_render_string_list(record.get("rollback_notes", [])),
        "",
        "## Risks",
        *_render_string_list(record.get("risks", [])),
        "",
        "## Human Next Steps",
        *_render_string_list(record.get("human_next_steps", [])),
        "",
        "## Limitations",
        *_render_string_list(record.get("limitations", [])),
        "",
    ]
    if record.get("status") != "ok" and record.get("error"):
        lines.extend(["## Error", f"- {record['error']['message']}", ""])
    return "\n".join(lines)


def write_project_evolution_executable_patch_draft_artifacts(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    patch_text_draft_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_executable_patch_draft(
        str(repo_root),
        approval_path,
        patch_draft_package_path,
        patch_candidates_path,
        patch_text_draft_path,
    )
    if record.get("status") != "ok":
        return {"record": record, "json_path": "", "md_path": ""}

    output_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_executable_patch_draft"
    json_path = output_root / f"{prefix}.json"
    md_path = output_root / f"{prefix}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_project_evolution_executable_patch_draft_markdown(record), encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def _verify_chain(
    *,
    repo_root: Path,
    current_hash: str,
    current_goal: str,
    approval_resolved: Path,
    draft_resolved: Path,
    candidates_resolved: Path,
    text_resolved: Path,
    approval_record: dict[str, Any],
    draft_record: dict[str, Any],
    candidates_record: dict[str, Any],
    text_record: dict[str, Any],
    approval_id: str,
) -> dict[str, Any] | None:
    checks = [
        (
            approval_record.get("decision") == "approve",
            "approval decision must be approve before executable patch drafting can begin",
            "approval_not_approved",
        ),
        (
            str(approval_record.get("source_plan_hash") or "") == current_hash,
            "approval source_plan_hash does not match the current normalized migration plan hash",
            "approval_source_hash_mismatch",
        ),
        (
            str(draft_record.get("source_plan_hash") or "") == current_hash,
            "patch draft package source_plan_hash does not match the current normalized migration plan hash",
            "draft_source_hash_mismatch",
        ),
        (
            str(candidates_record.get("source_plan_hash") or "") == current_hash,
            "patch candidates source_plan_hash does not match the current normalized migration plan hash",
            "candidates_source_hash_mismatch",
        ),
        (
            str(text_record.get("source_plan_hash") or "") == current_hash,
            "patch text draft source_plan_hash does not match the current normalized migration plan hash",
            "text_source_hash_mismatch",
        ),
        (
            str(draft_record.get("approval_hash_or_id") or "") == approval_id,
            "patch draft package approval id does not match the selected approval record",
            "draft_approval_id_mismatch",
        ),
        (
            str(candidates_record.get("approval_hash_or_id") or "") == approval_id,
            "patch candidates approval id does not match the selected approval record",
            "candidates_approval_id_mismatch",
        ),
        (
            str(draft_record.get("approval_path") or "") == str(approval_resolved),
            "patch draft package was not created from the selected approval record",
            "draft_approval_mismatch",
        ),
        (
            str(candidates_record.get("approval_path") or "") == str(approval_resolved),
            "patch candidates were not created from the selected approval record",
            "candidates_approval_mismatch",
        ),
        (
            str(candidates_record.get("patch_draft_package_path") or "") == str(draft_resolved),
            "patch candidates were not created from the selected patch draft package",
            "candidates_draft_mismatch",
        ),
        (
            str(text_record.get("approval_path") or "") == str(approval_resolved),
            "patch text draft was not created from the selected approval record",
            "text_approval_mismatch",
        ),
        (
            str(text_record.get("patch_draft_package_path") or "") == str(draft_resolved),
            "patch text draft was not created from the selected patch draft package",
            "text_draft_mismatch",
        ),
        (
            str(text_record.get("patch_candidates_path") or "") == str(candidates_resolved),
            "patch text draft was not created from the selected patch candidates package",
            "text_candidates_mismatch",
        ),
        (
            draft_record.get("draft_package_only") is True,
            "patch draft package is not marked as draft_package_only",
            "draft_not_draft_only",
        ),
        (
            candidates_record.get("candidate_draft_only") is True,
            "patch candidates record is not marked as candidate_draft_only",
            "candidates_not_draft_only",
        ),
        (
            candidates_record.get("approval_verified") is True,
            "patch candidates record is missing approval verification",
            "candidates_not_verified",
        ),
        (
            text_record.get("patch_text_draft_only") is True,
            "patch text draft is not marked as patch_text_draft_only",
            "text_not_read_only",
        ),
        (
            text_record.get("patch_apply_allowed") is False,
            "patch text draft unexpectedly allows patch application",
            "text_apply_gate_open",
        ),
        (
            text_record.get("validation_execution_allowed") is False,
            "patch text draft unexpectedly allows validation execution",
            "text_validation_gate_open",
        ),
        (
            text_record.get("real_repo_apply_allowed") is False,
            "patch text draft unexpectedly allows real repository application",
            "text_real_repo_gate_open",
        ),
    ]
    for ok, message, code in checks:
        if ok:
            continue
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            message,
            code,
        )

    selected_ids = set(_normalize_string_list(text_record.get("selected_candidate_ids", [])))
    candidate_ids = set(_candidate_ids(candidates_record.get("candidates", [])))
    missing_ids = sorted(candidate_id for candidate_id in selected_ids if candidate_id not in candidate_ids)
    if missing_ids:
        return _chain_error(
            repo_root,
            current_hash,
            approval_resolved,
            draft_resolved,
            candidates_resolved,
            text_resolved,
            current_goal,
            f"patch text draft references candidate ids that are not present in patch candidates: {', '.join(missing_ids)}",
            "text_candidate_id_mismatch",
        )
    return None


def _approved_file_paths(
    *,
    current_plan: dict[str, Any],
    draft_record: dict[str, Any],
    candidates_record: dict[str, Any],
) -> set[str]:
    allowed: set[str] = set()
    for collection in (
        current_plan.get("likely_affected_files", []),
        current_plan.get("full_files_to_read_before_patching", []),
        draft_record.get("likely_files_to_change", []),
        draft_record.get("files_to_read_first", []),
    ):
        for item in _normalize_file_entries(collection):
            allowed.add(item["path"])
    for candidate in candidates_record.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        for item in _normalize_file_entries(candidate.get("target_files", [])):
            allowed.add(item["path"])
    return {path for path in allowed if not _is_secret_env_path(path)}


def _text_draft_file_paths(text_record: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for draft in text_record.get("patch_text_drafts", []):
        if not isinstance(draft, dict):
            continue
        for item in _normalize_file_entries(draft.get("target_files", [])):
            if not _is_secret_env_path(item["path"]):
                paths.add(item["path"])
    return paths


def _build_target_files(text_record: dict[str, Any], allowed_paths: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in text_record.get("patch_text_drafts", []):
        if not isinstance(draft, dict):
            continue
        candidate_id = _normalize_text(draft.get("candidate_id"))
        for item in _normalize_file_entries(draft.get("target_files", [])):
            path = item["path"]
            if path in seen or path not in allowed_paths or _is_secret_env_path(path):
                continue
            seen.add(path)
            out.append(
                {
                    "path": path,
                    "candidate_id": candidate_id,
                    "category": item["category"],
                    "reason": item["reason"],
                    "confidence": item["confidence"],
                }
            )
    return out


def _build_executable_edit_units(text_record: dict[str, Any], allowed_paths: set[str]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    sequence = 1
    for draft in text_record.get("patch_text_drafts", []):
        if not isinstance(draft, dict):
            continue
        candidate_id = _normalize_text(draft.get("candidate_id"))
        intent = _normalize_text(draft.get("intent")) or _first_string(draft.get("proposed_edits", []))
        safety_notes = _normalize_string_list(draft.get("safety_notes", []))
        for item in _normalize_file_entries(draft.get("target_files", [])):
            path = item["path"]
            if path not in allowed_paths or _is_secret_env_path(path):
                continue
            units.append(
                {
                    "edit_id": f"{_slugify(candidate_id)}-{sequence:02d}",
                    "candidate_id": candidate_id,
                    "target_file": path,
                    "edit_type": "replace_text",
                    "intent": intent,
                    "anchor_strategy": "full_file_read_required_before_anchor_selection",
                    "old_text": None,
                    "new_text": None,
                    "unified_diff": None,
                    "apply_allowed": False,
                    "sandbox_only_later": True,
                    "requires_full_file_read": True,
                    "safety_notes": _normalize_string_list(
                        [
                            *safety_notes,
                            "Placeholder edit unit only; source text must be read before old_text/new_text can be grounded.",
                            "Patch safety checks and sandbox application are required before any later apply phase.",
                        ]
                    ),
                }
            )
            sequence += 1
    return units


def _build_human_next_steps(edit_units: list[dict[str, Any]], text_record: dict[str, Any]) -> list[str]:
    steps = [
        f"Review {len(edit_units)} placeholder edit unit(s) and confirm the target files still match the approved migration scope.",
        "Read every target file in full before grounding old_text or new_text in a later phase.",
        "Run patch safety checks before any later sandbox apply attempt.",
        "Use a sandbox/temp clone before any validation command is considered.",
    ]
    if text_record.get("open_questions"):
        steps.append("Resolve the open questions from the patch text draft before grounding executable edits.")
    return steps


def _chain_error(
    repo_root: Path,
    source_plan_hash: str,
    approval_path: Path,
    patch_draft_package_path: Path,
    patch_candidates_path: Path,
    patch_text_draft_path: Path,
    migration_goal: str,
    message: str,
    code: str,
) -> dict[str, Any]:
    return _build_error_record(
        repo_root=repo_root,
        source_plan_hash=source_plan_hash,
        approval_path=str(approval_path),
        patch_draft_package_path=str(patch_draft_package_path),
        patch_candidates_path=str(patch_candidates_path),
        patch_text_draft_path=str(patch_text_draft_path),
        migration_goal=migration_goal,
        message=message,
        code=code,
    )


def _build_error_record(
    *,
    repo_root: Path,
    source_plan_hash: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    patch_text_draft_path: str,
    migration_goal: str,
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
        "migration_goal": migration_goal,
        "source_plan_hash": source_plan_hash,
        "approval_path": approval_path,
        "patch_draft_package_path": patch_draft_package_path,
        "patch_candidates_path": patch_candidates_path,
        "patch_text_draft_path": patch_text_draft_path,
        "approval_verified": False,
        "executable_patch_draft_only": True,
        "source_files_mutated": False,
        "real_repo_apply_allowed": False,
        "sandbox_apply_allowed_later": True,
        "validation_execution_allowed": False,
        "requires_patch_safety_before_apply": True,
        "requires_sandbox_before_validation": True,
        "target_files": [],
        "executable_edit_units": [],
        "tests_required_later": [],
        "rollback_notes": [],
        "risks": [],
        "limitations": [
            "The executable patch draft could not be created because the approved artifact chain was not verified.",
            "No patch was generated, applied, validated, or committed.",
        ],
        "human_next_steps": [
            "Fix the reported chain issue and rerun executable patch draft creation.",
        ],
    }


def _load_json_record(path: Path, schema_version: str, label: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_missing",
            "message": f"{label} does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_invalid_json",
            "message": f"{label} is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_unreadable",
            "message": f"{label} could not be read: {path} ({exc})",
        }
    if not isinstance(record, dict) or record.get("schema_version") != schema_version:
        return {
            "status": "error",
            "code": f"{label.replace(' ', '_')}_bad_schema",
            "message": f"{label} has an unexpected schema: {path}",
        }
    return {"status": "ok", "record": record}


def _resolve_artifact_path(repo_root: Path, artifact_path: str, dirname: str) -> Path | None:
    root = (repo_root / ".agent" / "project_evolution" / dirname).resolve()
    candidate = Path(artifact_path).expanduser()
    resolved = candidate if candidate.is_absolute() else (repo_root / candidate)
    resolved = resolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _resolve_candidate_path(repo_root: Path, artifact_path: str) -> Path:
    candidate = Path(artifact_path).expanduser()
    return candidate if candidate.is_absolute() else (repo_root / candidate)


def _resolve_output_root(repo_root: Path) -> Path:
    resolved = (repo_root / ".agent" / "project_evolution" / EXECUTABLE_PATCH_DRAFTS_DIRNAME).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _normalize_file_entries(entries: Any) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            continue
        path = _clean_rel_path(item.get("path", ""))
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(
            {
                "path": path,
                "category": _normalize_text(item.get("category")) or "unknown",
                "reason": _normalize_text(item.get("reason")) or "",
                "confidence": _normalize_confidence(item.get("confidence")),
            }
        )
    return normalized


def _normalize_string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _candidate_ids(candidates: Any) -> list[str]:
    if not isinstance(candidates, list):
        return []
    out: list[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = _normalize_text(item.get("candidate_id"))
        if candidate_id:
            out.append(candidate_id)
    return out


def _render_edit_units(units: list[dict[str, Any]]) -> list[str]:
    if not units:
        return ["- None"]
    lines: list[str] = []
    for unit in units:
        lines.extend(
            [
                f"### {unit.get('edit_id', '')}",
                f"- Candidate ID: `{unit.get('candidate_id', '')}`",
                f"- Target file: `{unit.get('target_file', '')}`",
                f"- Edit type: `{unit.get('edit_type', '')}`",
                f"- Apply allowed: `{unit.get('apply_allowed', False)}`",
                f"- Requires full file read: `{unit.get('requires_full_file_read', False)}`",
                f"- Anchor strategy: `{unit.get('anchor_strategy', '')}`",
                f"- Intent: {unit.get('intent', '')}",
                "- Safety notes:",
                *_render_string_list(unit.get("safety_notes", [])),
                "",
            ]
        )
    return lines


def _render_file_lines(files: list[dict[str, Any]]) -> list[str]:
    if not files:
        return ["- None"]
    lines: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- `{item.get('path', '')}` [{item.get('category', 'unknown')}, "
            f"confidence={item.get('confidence', 0.0)}] {item.get('reason', '')}".rstrip()
        )
    return lines or ["- None"]


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _first_string(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    for item in items:
        text = _normalize_text(item)
        if text:
            return text
    return ""


def _clean_rel_path(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        return ""
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts or ".." in parts:
        return ""
    return Path(*parts).as_posix()


def _is_secret_env_path(path: str) -> bool:
    name = Path(path).name.lower()
    if name == ".env":
        return True
    if name.startswith(".env.") and name not in {".env.example", ".env.sample", ".env.template"}:
        return True
    return False


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(confidence, 1.0))


def _slugify(text: str) -> str:
    slug = []
    last_was_dash = False
    for char in text.lower():
        if char.isalnum():
            slug.append(char)
            last_was_dash = False
        elif not last_was_dash:
            slug.append("-")
            last_was_dash = True
    return "".join(slug).strip("-") or "edit"


def _approval_id_from_path(path: str) -> str:
    return Path(path).stem


def _safe_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
