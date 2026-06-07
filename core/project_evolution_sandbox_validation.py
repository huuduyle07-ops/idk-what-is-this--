from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.failure_taxonomy import classify_benchmark_failure_kind
from core.patch_safety import evaluate_patch_safety
from core import project_evolution_approval as approval_core
from core import sandbox_runner
from core.validation_command import validation_command_safety_issue


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_sandbox_validation_v1"
APPROVAL_SCHEMA_VERSION = "evolution_plan_review_v1"
DRAFT_PACKAGE_SCHEMA_VERSION = "evolution_patch_draft_package_v1"
CANDIDATES_SCHEMA_VERSION = "evolution_patch_candidates_v1"
TEXT_DRAFT_SCHEMA_VERSION = "evolution_patch_text_draft_v1"
SANDBOX_VALIDATION_DIRNAME = "sandbox_validation"
DEFAULT_MAX_TIMEOUT = 300


def build_project_evolution_sandbox_validation(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    patch_text_draft_path: str,
    *,
    backend: str = "temp_clone",
    validation_command: str | None = None,
    max_timeout: int = DEFAULT_MAX_TIMEOUT,
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

    if max_timeout < 1:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path="",
            patch_draft_package_path="",
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message="max_timeout must be at least 1",
            code="invalid_max_timeout",
        )

    approval_resolved = _resolve_artifact_path(repo_root, approval_path, "approvals")
    if approval_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(_resolve_candidate_path(repo_root, approval_path)),
            patch_draft_package_path="",
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message="approval record must live inside .agent/project_evolution/approvals/",
            code="approval_path_outside_approvals",
        )

    draft_resolved = _resolve_artifact_path(repo_root, patch_draft_package_path, "patch_drafts")
    if draft_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(_resolve_candidate_path(repo_root, patch_draft_package_path)),
            patch_candidates_path="",
            patch_text_draft_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message="patch draft package must live inside .agent/project_evolution/patch_drafts/",
            code="draft_path_outside_patch_drafts",
        )

    candidates_resolved = _resolve_artifact_path(repo_root, patch_candidates_path, "patch_candidates")
    if candidates_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(_resolve_candidate_path(repo_root, patch_candidates_path)),
            patch_text_draft_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message="patch candidates must live inside .agent/project_evolution/patch_candidates/",
            code="candidates_path_outside_patch_candidates",
        )

    text_draft_resolved = _resolve_artifact_path(repo_root, patch_text_draft_path, "patch_text_drafts")
    if text_draft_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(_resolve_candidate_path(repo_root, patch_text_draft_path)),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message="patch text draft must live inside .agent/project_evolution/patch_text_drafts/",
            code="text_draft_path_outside_patch_text_drafts",
        )

    approval_load = _load_json_record(approval_resolved, APPROVAL_SCHEMA_VERSION, "approval")
    if approval_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message=approval_load["message"],
            code=approval_load["code"],
        )

    draft_load = _load_json_record(draft_resolved, DRAFT_PACKAGE_SCHEMA_VERSION, "patch draft package")
    if draft_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message=draft_load["message"],
            code=draft_load["code"],
        )

    candidates_load = _load_json_record(candidates_resolved, CANDIDATES_SCHEMA_VERSION, "patch candidates")
    if candidates_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message=candidates_load["message"],
            code=candidates_load["code"],
        )

    text_load = _load_json_record(text_draft_resolved, TEXT_DRAFT_SCHEMA_VERSION, "patch text draft")
    if text_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            message=text_load["message"],
            code=text_load["code"],
        )

    approval_record = approval_load["record"]
    draft_record = draft_load["record"]
    candidates_record = candidates_load["record"]
    text_record = text_load["record"]
    current_hash = current_plan_load["source_plan_hash"]
    current_goal = current_plan_load["source_plan"].get("migration_goal", "")
    approval_id = _approval_id_from_path(approval_resolved.name)

    if approval_record.get("decision") != "approve":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="approval decision must be approve before sandbox validation can begin",
            code="approval_not_approved",
        )

    if str(approval_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="approval source_plan_hash does not match the current normalized migration plan hash",
            code="approval_source_hash_mismatch",
        )

    if str(draft_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch draft package source_plan_hash does not match the current normalized migration plan hash",
            code="draft_source_hash_mismatch",
        )

    if str(candidates_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch candidates source_plan_hash does not match the current normalized migration plan hash",
            code="candidates_source_hash_mismatch",
        )

    if str(text_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft source_plan_hash does not match the current normalized migration plan hash",
            code="text_source_hash_mismatch",
        )

    if str(draft_record.get("approval_hash_or_id") or "") != approval_id:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch draft package approval id does not match the selected approval record",
            code="draft_approval_id_mismatch",
        )

    if str(candidates_record.get("approval_hash_or_id") or "") != approval_id:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch candidates approval id does not match the selected approval record",
            code="candidates_approval_id_mismatch",
        )

    if str(draft_record.get("approval_path") or "") != str(approval_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch draft package was not created from the selected approval record",
            code="draft_approval_mismatch",
        )

    if str(candidates_record.get("approval_path") or "") != str(approval_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch candidates were not created from the selected approval record",
            code="candidates_approval_mismatch",
        )

    if str(text_record.get("approval_path") or "") != str(approval_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft was not created from the selected approval record",
            code="text_approval_mismatch",
        )

    if str(text_record.get("patch_draft_package_path") or "") != str(draft_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft was not created from the selected patch draft package",
            code="text_draft_mismatch",
        )

    if str(text_record.get("patch_candidates_path") or "") != str(candidates_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft was not created from the selected patch candidates package",
            code="text_candidates_mismatch",
        )

    if text_record.get("patch_text_draft_only") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft is not marked as patch_text_draft_only",
            code="text_not_read_only",
        )

    selected_ids = _normalize_string_list(text_record.get("selected_candidate_ids", []))
    candidate_ids = _candidate_ids(candidates_record.get("candidates", []))
    if any(candidate_id not in candidate_ids for candidate_id in selected_ids):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft references candidate ids that are not in the selected candidates package",
            code="text_candidate_mismatch",
        )

    text_candidates = _normalize_text_candidates(text_record.get("selected_candidates", []))
    if [item["candidate_id"] for item in text_candidates] != selected_ids:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            patch_text_draft_path=str(text_draft_resolved),
            migration_goal=current_goal,
            message="patch text draft selected candidates do not match the selected candidate ids",
            code="text_selected_candidates_mismatch",
        )

    validation_command_text = _normalize_text(validation_command)
    validation_command_safety_checked = bool(validation_command_text)
    validation_command_issue = (
        validation_command_safety_issue(validation_command_text)
        if validation_command_safety_checked
        else ""
    )
    if validation_command_issue:
        validation_result = {
            "status": "blocked",
            "reason": validation_command_issue,
            "command": validation_command_text,
            "timeout_sec": max_timeout,
            "output": "",
        }
        apply_result = _not_applicable_apply_result(
            "patch text draft contains no executable diff",
            backend=backend,
        )
        return _finalize_report(
            repo_root=repo_root,
            current_goal=current_goal,
            current_hash=current_hash,
            approval_resolved=approval_resolved,
            draft_resolved=draft_resolved,
            candidates_resolved=candidates_resolved,
            text_draft_resolved=text_draft_resolved,
            approval_record=approval_record,
            draft_record=draft_record,
            candidates_record=candidates_record,
            text_record=text_record,
            backend=backend,
            backend_available=_backend_available(backend),
            patch_safety=evaluate_patch_safety([], project_root=repo_root),
            validation_command_text=validation_command_text,
            validation_command_safety_checked=validation_command_safety_checked,
            validation_command_issue=validation_command_issue,
            apply_result=apply_result,
            validation_result=validation_result,
            failure_message=validation_command_issue,
        )

    backend_available = _backend_available(backend)
    if backend == "docker_ubuntu" and not backend_available:
        block_reason = "docker backend unavailable"
        apply_result = {
            "status": "blocked",
            "reason": block_reason,
            "backend": backend,
            "applied": False,
        }
        validation_result = {
            "status": "not_run",
            "reason": "validation not run because the backend is unavailable",
            "command": validation_command_text,
            "timeout_sec": max_timeout,
            "output": "",
        }
        return _finalize_report(
            repo_root=repo_root,
            current_goal=current_goal,
            current_hash=current_hash,
            approval_resolved=approval_resolved,
            draft_resolved=draft_resolved,
            candidates_resolved=candidates_resolved,
            text_draft_resolved=text_draft_resolved,
            approval_record=approval_record,
            draft_record=draft_record,
            candidates_record=candidates_record,
            text_record=text_record,
            backend=backend,
            backend_available=False,
            patch_safety=evaluate_patch_safety([], project_root=repo_root),
            validation_command_text=validation_command_text,
            validation_command_safety_checked=False,
            validation_command_issue="",
            apply_result=apply_result,
            validation_result=validation_result,
            failure_message=block_reason,
        )

    patch_safety = evaluate_patch_safety([], project_root=repo_root)
    apply_result = _not_applicable_apply_result(
        "patch text draft contains no executable diff",
        backend=backend,
    )
    validation_result = {
        "status": "not_run",
        "reason": (
            "validation command not provided"
            if not validation_command_text
            else "patch text draft contains no executable diff"
        ),
        "command": validation_command_text,
        "timeout_sec": max_timeout,
        "output": "",
    }
    return _finalize_report(
        repo_root=repo_root,
        current_goal=current_goal,
        current_hash=current_hash,
        approval_resolved=approval_resolved,
        draft_resolved=draft_resolved,
        candidates_resolved=candidates_resolved,
        text_draft_resolved=text_draft_resolved,
        approval_record=approval_record,
        draft_record=draft_record,
        candidates_record=candidates_record,
        text_record=text_record,
        backend=backend,
        backend_available=backend_available,
        patch_safety=patch_safety,
        validation_command_text=validation_command_text,
        validation_command_safety_checked=validation_command_safety_checked,
        validation_command_issue="",
        apply_result=apply_result,
        validation_result=validation_result,
        failure_message="",
    )


def render_project_evolution_sandbox_validation_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Sandbox Validation",
        "",
        "## Summary",
        f"- Repo path: `{record.get('repo_path', '')}`",
        f"- Mode: `{record.get('mode', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Backend: `{record.get('backend', '')}`",
        f"- Status: `{record.get('status', '')}`",
        f"- Source plan hash: `{record.get('source_plan_hash', '')}`",
        "- This validation ran in a sandbox/temp clone only. The real repository was not mutated.",
        "",
        "## Approval Verification",
        f"- Approval verified: `{record.get('approval_verified', False)}`",
        f"- Approval path: `{record.get('approval_path', '')}`",
        f"- Patch draft package: `{record.get('patch_draft_package_path', '')}`",
        f"- Patch candidates: `{record.get('patch_candidates_path', '')}`",
        f"- Patch text draft: `{record.get('patch_text_draft_path', '')}`",
        "",
        "## Backend",
        f"- Backend available: `{record.get('backend_available', False)}`",
        f"- Sandbox validation only: `{record.get('sandbox_validation_only', False)}`",
        f"- Real repo apply allowed: `{record.get('real_repo_apply_allowed', False)}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Patch Safety",
        f"- Patch safety checked: `{record.get('patch_safety_checked', False)}`",
        f"- Apply result status: `{record.get('apply_result', {}).get('status', '')}`",
        f"- Apply result reason: {record.get('apply_result', {}).get('reason', '')}",
        "",
        "## Validation Command Safety",
        f"- Validation command safety checked: `{record.get('validation_command_safety_checked', False)}`",
        f"- Validation command: `{record.get('validation_command', '') or 'None'}`",
        "",
        "## Sandbox Apply Result",
        f"- Status: `{record.get('apply_result', {}).get('status', '')}`",
        f"- Reason: {record.get('apply_result', {}).get('reason', '')}",
        "",
        "## Validation Result",
        f"- Status: `{record.get('validation_result', {}).get('status', '')}`",
        f"- Reason: {record.get('validation_result', {}).get('reason', '')}",
        "",
        "## Sandbox File Changes",
        *_render_file_list(record.get("changed_files_in_sandbox", [])),
        "",
        "## Failure Classification",
        f"- Failure kind: `{record.get('failure_kind', '')}`",
        f"- Failure kind display: `{record.get('failure_kind_display', '')}`",
        f"- Failure cause: {record.get('failure_cause', '')}",
        f"- Failure evidence: {record.get('failure_evidence', '')}",
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
    if record.get("status") == "error" and record.get("error"):
        lines.extend(["## Error", f"- {record['error']['message']}", ""])
    return "\n".join(lines)


def write_project_evolution_sandbox_validation_artifacts(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    patch_text_draft_path: str,
    *,
    backend: str = "temp_clone",
    validation_command: str | None = None,
    max_timeout: int = DEFAULT_MAX_TIMEOUT,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_sandbox_validation(
        str(repo_root),
        approval_path,
        patch_draft_package_path,
        patch_candidates_path,
        patch_text_draft_path,
        backend=backend,
        validation_command=validation_command,
        max_timeout=max_timeout,
    )
    if record.get("status") == "error":
        return {"record": record, "json_path": "", "md_path": ""}

    output_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_sandbox_validation"
    json_path = output_root / f"{prefix}.json"
    md_path = output_root / f"{prefix}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_project_evolution_sandbox_validation_markdown(record), encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def _finalize_report(
    *,
    repo_root: Path,
    current_goal: str,
    current_hash: str,
    approval_resolved: Path,
    draft_resolved: Path,
    candidates_resolved: Path,
    text_draft_resolved: Path,
    approval_record: dict[str, Any],
    draft_record: dict[str, Any],
    candidates_record: dict[str, Any],
    text_record: dict[str, Any],
    backend: str,
    backend_available: bool,
    patch_safety: dict[str, Any],
    validation_command_text: str,
    validation_command_safety_checked: bool,
    validation_command_issue: str,
    apply_result: dict[str, Any],
    validation_result: dict[str, Any],
    failure_message: str,
) -> dict[str, Any]:
    changed_files = _normalize_string_list(apply_result.get("changed_files", []))
    generated_artifacts = _normalize_string_list(apply_result.get("generated_artifacts", []))
    unexpected_mutations = _normalize_string_list(apply_result.get("unexpected_mutations", []))
    failure_kind, failure_kind_display, failure_cause, failure_evidence = _failure_fields(
        failure_message or apply_result.get("reason", "") or validation_result.get("reason", "")
    )
    status = "blocked" if apply_result.get("status") in {"blocked", "not_applicable"} or validation_result.get("status") == "blocked" else "ok"
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "block_reason": failure_message or apply_result.get("reason", "") or validation_result.get("reason", ""),
        "migration_goal": current_goal,
        "source_plan_hash": current_hash,
        "approval_path": str(approval_resolved),
        "patch_draft_package_path": str(draft_resolved),
        "patch_candidates_path": str(candidates_resolved),
        "patch_text_draft_path": str(text_draft_resolved),
        "approval_verified": True,
        "sandbox_validation_only": True,
        "real_repo_apply_allowed": False,
        "source_files_mutated": False,
        "backend": backend,
        "backend_available": backend_available,
        "patch_safety_checked": bool(patch_safety),
        "validation_command_safety_checked": validation_command_safety_checked,
        "validation_command": validation_command_text,
        "validation_result": validation_result,
        "apply_result": apply_result,
        "changed_files_in_sandbox": changed_files,
        "generated_artifacts_in_sandbox": generated_artifacts,
        "unexpected_mutations_in_sandbox": unexpected_mutations,
        "failure_kind": failure_kind,
        "failure_kind_display": failure_kind_display,
        "failure_cause": failure_cause,
        "failure_evidence": failure_evidence,
        "risks": _collect_risks(draft_record, candidates_record, text_record),
        "limitations": [
            "This validation ran in a sandbox/temp clone only. The real repository was not mutated.",
            "The current B.7 patch text draft contains no executable diff, so this report is not a real patch application run.",
            "No model/API calls, patch apply, validation execution, benchmark execution, Docker subprocess management, or lesson mutation occurred here.",
        ],
        "human_next_steps": _build_human_next_steps(text_record, validation_result, apply_result),
        "patch_safety": patch_safety,
    }


def _build_human_next_steps(
    text_record: dict[str, Any],
    validation_result: dict[str, Any],
    apply_result: dict[str, Any],
) -> list[str]:
    steps = [
        "If you want a real sandbox validation later, convert the patch text draft into an executable patch format first.",
        "Keep the current real repository untouched and rerun only after the patch text can be executed safely in a temp clone.",
    ]
    if validation_result.get("status") == "blocked":
        steps.append("Fix the validation command safety issue before attempting a sandbox run.")
    if apply_result.get("status") == "blocked":
        steps.append("Resolve the backend issue before trying the sandbox backend again.")
    if text_record.get("open_questions"):
        steps.append("Review the open questions from the patch text draft before the next phase.")
    return steps


def _collect_risks(
    draft_record: dict[str, Any],
    candidates_record: dict[str, Any],
    text_record: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    for source in (
        draft_record.get("risks", []),
        candidates_record.get("risks", []),
        text_record.get("risks", []),
    ):
        items.extend(_normalize_string_list(source))
    return _dedupe(items)


def _failure_fields(message: str) -> tuple[str, str, str, str]:
    text = _normalize_text(message)
    if not text:
        return "", "", "", ""
    kind = classify_benchmark_failure_kind(validation_output=text)
    return kind["kind"], kind["display"], kind["cause"], kind["evidence"]


def _not_applicable_apply_result(reason: str, *, backend: str) -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "reason": reason,
        "backend": backend,
        "applied": False,
    }


def _backend_available(backend: str) -> bool:
    if backend == "temp_clone":
        return True
    if backend == "docker_ubuntu":
        available, _ = sandbox_runner._is_docker_available()
        return available
    return False


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
    resolved = (repo_root / ".agent" / "project_evolution" / SANDBOX_VALIDATION_DIRNAME).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


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
        "block_reason": message,
        "error": {
            "code": code,
            "message": message,
        },
        "source_plan_hash": source_plan_hash,
        "approval_path": approval_path,
        "patch_draft_package_path": patch_draft_package_path,
        "patch_candidates_path": patch_candidates_path,
        "patch_text_draft_path": patch_text_draft_path,
        "migration_goal": migration_goal,
        "approval_verified": False,
        "sandbox_validation_only": True,
        "real_repo_apply_allowed": False,
        "source_files_mutated": False,
        "backend": "",
        "backend_available": False,
        "patch_safety_checked": False,
        "validation_command_safety_checked": False,
        "validation_command": "",
        "validation_result": {
            "status": "not_run",
            "reason": message,
        },
        "apply_result": {
            "status": "blocked",
            "reason": message,
            "applied": False,
        },
        "changed_files_in_sandbox": [],
        "generated_artifacts_in_sandbox": [],
        "unexpected_mutations_in_sandbox": [],
        "failure_kind": "",
        "failure_kind_display": "",
        "failure_cause": "",
        "failure_evidence": "",
        "risks": [],
        "limitations": [
            "This validation did not complete because the sandbox approval chain could not be verified.",
            "No patch was generated, applied, or validated.",
        ],
        "human_next_steps": [
            "Fix the reported issue and rerun the sandbox validation with a matching approved chain.",
        ],
        "patch_safety": {},
    }


def _candidate_ids(candidates: Any) -> list[str]:
    if not isinstance(candidates, list):
        return []
    out: list[str] = []
    for item in candidates:
        if isinstance(item, dict):
            candidate_id = _normalize_text(item.get("candidate_id"))
            if candidate_id:
                out.append(candidate_id)
    return _dedupe(out)


def _normalize_text_candidates(candidates: Any) -> list[dict[str, Any]]:
    if not isinstance(candidates, list):
        return []
    out: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = _normalize_text(item.get("candidate_id"))
        title = _normalize_text(item.get("title"))
        if not candidate_id or not title:
            continue
        out.append(
            {
                "candidate_id": candidate_id,
                "title": title,
            }
        )
    return out


def _normalize_string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = _normalize_text(item)
        if text:
            out.append(text)
    return _dedupe(out)


def _render_file_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- `{item}`" for item in items]


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _approval_id_from_path(path: str) -> str:
    return Path(path).stem


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
