from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import project_evolution_approval as approval_core


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_patch_text_draft_v1"
APPROVAL_SCHEMA_VERSION = "evolution_plan_review_v1"
DRAFT_PACKAGE_SCHEMA_VERSION = "evolution_patch_draft_package_v1"
CANDIDATES_SCHEMA_VERSION = "evolution_patch_candidates_v1"
PATCH_TEXT_DRAFTS_DIRNAME = "patch_text_drafts"
DEFAULT_MAX_FILES = 12
DEFAULT_PATCH_FORMAT = "narrative_plan"


def build_project_evolution_patch_text_draft(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    *,
    selected_candidate_ids: list[str] | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    notes: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    current_plan_load = approval_core.load_latest_project_evolution_plan(str(repo_root))
    if current_plan_load["status"] != "ok" or not current_plan_load.get("source_plan"):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load.get("source_plan_path", ""),
            source_plan_hash="",
            approval_path="",
            patch_draft_package_path="",
            patch_candidates_path="",
            migration_goal="",
            notes=notes,
            message=current_plan_load.get("message", "migration plan is unavailable"),
            code="source_plan_unavailable",
        )

    if max_files < 1:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path="",
            patch_draft_package_path="",
            patch_candidates_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message="max_files must be at least 1",
            code="invalid_max_files",
        )

    approval_resolved = _resolve_project_evolution_artifact_path(repo_root, approval_path, "approvals")
    if approval_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(_resolve_candidate_path(repo_root, approval_path)),
            patch_draft_package_path="",
            patch_candidates_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message="approval record must live inside .agent/project_evolution/approvals/",
            code="approval_path_outside_approvals",
        )

    draft_resolved = _resolve_project_evolution_artifact_path(
        repo_root,
        patch_draft_package_path,
        "patch_drafts",
    )
    if draft_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(_resolve_candidate_path(repo_root, patch_draft_package_path)),
            patch_candidates_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message="patch draft package must live inside .agent/project_evolution/patch_drafts/",
            code="draft_path_outside_patch_drafts",
        )

    candidates_resolved = _resolve_project_evolution_artifact_path(
        repo_root,
        patch_candidates_path,
        "patch_candidates",
    )
    if candidates_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(_resolve_candidate_path(repo_root, patch_candidates_path)),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message="patch candidates must live inside .agent/project_evolution/patch_candidates/",
            code="candidates_path_outside_patch_candidates",
        )

    approval_load = _load_json_record(approval_resolved, APPROVAL_SCHEMA_VERSION, "approval")
    if approval_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=approval_load["message"],
            code=approval_load["code"],
        )

    draft_load = _load_json_record(draft_resolved, DRAFT_PACKAGE_SCHEMA_VERSION, "patch draft package")
    if draft_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=draft_load["message"],
            code=draft_load["code"],
        )

    candidates_load = _load_json_record(candidates_resolved, CANDIDATES_SCHEMA_VERSION, "patch candidates")
    if candidates_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=candidates_load["message"],
            code=candidates_load["code"],
        )

    approval_record = approval_load["record"]
    draft_record = draft_load["record"]
    candidates_record = candidates_load["record"]
    current_plan = current_plan_load["source_plan"]
    current_hash = current_plan_load["source_plan_hash"]
    approval_id = _approval_id_from_path(approval_resolved.name)

    if approval_record.get("decision") != "approve":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="approval decision must be approve before patch text drafting can begin",
            code="approval_not_approved",
        )

    if approval_record.get("patch_generation_allowed") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="approval record does not allow patch generation",
            code="approval_patch_gate_closed",
        )

    if str(approval_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="approval source_plan_hash does not match the current normalized migration plan hash",
            code="approval_source_hash_mismatch",
        )

    if str(draft_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package source_plan_hash does not match the current normalized migration plan hash",
            code="draft_source_hash_mismatch",
        )

    if str(candidates_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates source_plan_hash does not match the current normalized migration plan hash",
            code="candidates_source_hash_mismatch",
        )

    if not candidates_record.get("approval_verified"):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates record is missing approval verification",
            code="candidates_not_verified",
        )

    if str(candidates_record.get("approval_path") or "") != str(approval_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates were not created from the selected approval record",
            code="candidates_approval_mismatch",
        )

    if str(candidates_record.get("patch_draft_package_path") or "") != str(draft_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates were not created from the selected patch draft package",
            code="candidates_draft_mismatch",
        )

    if str(candidates_record.get("approval_hash_or_id") or "") != approval_id:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates approval id does not match the selected approval record",
            code="candidates_approval_id_mismatch",
        )

    if draft_record.get("approval_hash_or_id") != approval_id:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package approval id does not match the selected approval record",
            code="draft_approval_id_mismatch",
        )

    if str(draft_record.get("source_plan_hash") or "") != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package source_plan_hash does not match the current normalized migration plan hash",
            code="draft_source_hash_mismatch",
        )

    if draft_record.get("approval_path") != str(approval_resolved):
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package was not created from the selected approval record",
            code="draft_approval_mismatch",
        )

    if draft_record.get("draft_package_only") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package is not marked as draft_package_only",
            code="draft_not_read_only",
        )

    if draft_record.get("patch_generation_allowed") is not False:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package must keep patch generation disabled",
            code="draft_patch_gate_open",
        )

    if draft_record.get("patch_apply_allowed") is not False:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package must keep patch application disabled",
            code="draft_patch_apply_gate_open",
        )

    if draft_record.get("validation_execution_allowed") is not False:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package must keep validation execution disabled",
            code="draft_validation_gate_open",
        )

    selected_candidates = _select_candidates(
        candidates_record.get("candidates", []),
        selected_candidate_ids=selected_candidate_ids,
    )
    if not selected_candidates:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            patch_draft_package_path=str(draft_resolved),
            patch_candidates_path=str(candidates_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch candidates record does not contain any selectable candidates",
            code="selected_candidates_missing",
        )

    selected_ids = {candidate["candidate_id"] for candidate in selected_candidates}
    if selected_candidate_ids:
        missing = [candidate_id for candidate_id in _normalize_string_list(selected_candidate_ids) if candidate_id not in selected_ids]
        if missing:
            return _build_error_record(
                repo_root=repo_root,
                source_plan_path=current_plan_load["source_plan_path"],
                source_plan_hash=current_hash,
                approval_path=str(approval_resolved),
                patch_draft_package_path=str(draft_resolved),
                patch_candidates_path=str(candidates_resolved),
                migration_goal=current_plan.get("migration_goal", ""),
                notes=notes,
                message=f"selected candidate ids were not found: {', '.join(missing)}",
                code="selected_candidate_not_found",
            )

    patch_text_drafts = [
        _build_patch_text_draft(candidate, draft_record, index=index, max_files=max_files)
        for index, candidate in enumerate(selected_candidates, start=1)
    ]

    files_to_read_first = _limit_file_entries(
        _unique_file_entries(
            [
                *draft_record.get("files_to_read_first", []),
                *[
                    item
                    for candidate in selected_candidates
                    for item in candidate.get("target_files", [])
                ],
            ]
        ),
        max_files=max_files,
    )

    selected_candidate_records = [
        {
            "candidate_id": candidate["candidate_id"],
            "title": candidate["title"],
            "change_type": candidate["change_type"],
            "target_files": _limit_file_entries(_normalize_file_entries(candidate.get("target_files", [])), max_files=max_files),
            "requires_full_file_read": bool(candidate.get("requires_full_file_read", True)),
            "rationale": _normalize_text(candidate.get("rationale")) or "",
        }
        for candidate in selected_candidates
    ]

    risks = _normalize_string_list(
        [
            *draft_record.get("risks", []),
            *[risk for candidate in selected_candidates for risk in candidate.get("risks", [])],
        ]
    )
    tests_required_later = _normalize_string_list(
        [
            *draft_record.get("test_requirements", []),
            *[test for candidate in selected_candidates for test in candidate.get("tests_to_run_later", [])],
        ]
    )
    rollback_notes = _normalize_string_list(
        [
            *draft_record.get("rollback_requirements", []),
            "No patch text was applied; keep the candidate text read-only until the next patch phase.",
        ]
    )
    open_questions = _normalize_string_list(
        [
            *draft_record.get("open_questions", []),
            *(
                ["Should the remaining candidate groups be drafted in a later pass?"]
                if len(selected_candidates) < len(candidates_record.get("candidates", []))
                else []
            ),
        ]
    )
    human_next_steps = _build_human_next_steps(
        draft_record=draft_record,
        candidate_ids=[candidate["candidate_id"] for candidate in selected_candidates],
    )

    limitations = [
        "This is a patch text draft only. No patch was applied, validated, or committed.",
        "The patch text draft does not contain executable unified diff content.",
        "The package uses only the approved plan, approval, patch draft package, and patch candidates artifacts as sources.",
        "No model/API calls, patch application, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
    ]

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "notes": _normalize_text(notes),
        "source_plan_path": current_plan_load["source_plan_path"],
        "source_plan_hash": current_hash,
        "approval_path": str(approval_resolved),
        "patch_draft_package_path": str(draft_resolved),
        "patch_candidates_path": str(candidates_resolved),
        "approval_verified": True,
        "approval_decision": approval_record.get("decision", ""),
        "patch_draft_package_source_hash_matched": True,
        "patch_draft_package_approval_matched": True,
        "patch_candidates_source_hash_matched": True,
        "patch_candidates_approval_matched": True,
        "patch_candidates_draft_matched": True,
        "migration_goal": current_plan.get("migration_goal", ""),
        "patch_text_draft_only": True,
        "source_files_mutated": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "sandbox_validation_allowed_later": True,
        "requires_patch_safety_before_sandbox": True,
        "real_repo_apply_allowed": False,
        "selected_candidate_ids": [candidate["candidate_id"] for candidate in selected_candidates],
        "selected_candidates": selected_candidate_records,
        "patch_text_drafts": patch_text_drafts,
        "files_to_read_first": files_to_read_first,
        "risks": risks,
        "tests_required_later": tests_required_later,
        "rollback_notes": rollback_notes,
        "open_questions": open_questions,
        "human_next_steps": human_next_steps,
        "limitations": limitations,
    }


def render_project_evolution_patch_text_draft_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Patch Text Draft",
        "",
        "## Summary",
        f"- Repo path: `{record.get('repo_path', '')}`",
        f"- Mode: `{record.get('mode', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Selected candidate count: `{len(record.get('selected_candidates', []))}`",
        f"- Source plan hash: `{record.get('source_plan_hash', '')}`",
        f"- Approval path: `{record.get('approval_path', '')}`",
        f"- Patch draft package: `{record.get('patch_draft_package_path', '')}`",
        f"- Patch candidates: `{record.get('patch_candidates_path', '')}`",
        "- This is a patch text draft only. No patch was applied, validated, or committed.",
        "",
        "## Approval Verification",
        f"- Approval verified: `{record.get('approval_verified', False)}`",
        f"- Approval decision: `{record.get('approval_decision', '')}`",
        f"- Draft package source hash matched: `{record.get('patch_draft_package_source_hash_matched', False)}`",
        f"- Draft package approval matched: `{record.get('patch_draft_package_approval_matched', False)}`",
        f"- Candidates source hash matched: `{record.get('patch_candidates_source_hash_matched', False)}`",
        f"- Candidates approval matched: `{record.get('patch_candidates_approval_matched', False)}`",
        f"- Candidates draft matched: `{record.get('patch_candidates_draft_matched', False)}`",
        f"- Patch apply allowed: `{record.get('patch_apply_allowed', False)}`",
        f"- Validation execution allowed: `{record.get('validation_execution_allowed', False)}`",
        f"- Sandbox validation allowed later: `{record.get('sandbox_validation_allowed_later', False)}`",
        f"- Requires patch safety before sandbox: `{record.get('requires_patch_safety_before_sandbox', False)}`",
        f"- Real repo apply allowed: `{record.get('real_repo_apply_allowed', False)}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Selected Candidates",
        *_render_selected_candidates(record.get("selected_candidates", [])),
        "",
        "## Patch Text Drafts",
        *_render_patch_text_drafts(record.get("patch_text_drafts", [])),
        "",
        "## Files To Read First",
        *_render_file_lines(record.get("files_to_read_first", [])),
        "",
        "## Safety Notes",
        *_render_string_list(_build_safety_notes(record)),
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


def write_project_evolution_patch_text_draft_artifacts(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    *,
    selected_candidate_ids: list[str] | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    notes: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_patch_text_draft(
        str(repo_root),
        approval_path,
        patch_draft_package_path,
        patch_candidates_path,
        selected_candidate_ids=selected_candidate_ids,
        max_files=max_files,
        notes=notes,
    )
    if record.get("status") != "ok":
        return {"record": record, "json_path": "", "md_path": ""}

    output_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_patch_text_draft"
    json_path = output_root / f"{prefix}.json"
    md_path = output_root / f"{prefix}.md"
    markdown = render_project_evolution_patch_text_draft_markdown(record)
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def _build_patch_text_draft(
    candidate: dict[str, Any],
    draft_record: dict[str, Any],
    *,
    index: int,
    max_files: int,
) -> dict[str, Any]:
    target_files = _limit_file_entries(_normalize_file_entries(candidate.get("target_files", [])), max_files=max_files)
    candidate_id = str(candidate.get("candidate_id", "")).strip() or f"candidate-{index:02d}"
    title = _normalize_text(candidate.get("title")) or "Unknown"
    intent = _normalize_text(candidate.get("intent")) or ""
    change_type = _normalize_text(candidate.get("change_type")) or "unknown"
    rationale = _normalize_text(candidate.get("rationale")) or intent
    safety_notes = _build_candidate_safety_notes(candidate_id, target_files)
    proposed_edits = _build_proposed_edits(
        candidate_id=candidate_id,
        title=title,
        intent=intent,
        change_type=change_type,
        target_files=target_files,
        draft_record=draft_record,
    )
    return {
        "draft_id": f"{_slugify(candidate_id)}-{index:02d}",
        "candidate_id": candidate_id,
        "title": title,
        "intent": intent,
        "target_files": target_files,
        "change_type": change_type,
        "rationale": rationale,
        "patch_format": DEFAULT_PATCH_FORMAT,
        "proposed_edits": proposed_edits,
        "unified_diff": None,
        "apply_allowed": False,
        "validation_allowed": False,
        "requires_full_file_read": bool(candidate.get("requires_full_file_read", True)),
        "safety_notes": safety_notes,
    }


def _build_proposed_edits(
    *,
    candidate_id: str,
    title: str,
    intent: str,
    change_type: str,
    target_files: list[dict[str, Any]],
    draft_record: dict[str, Any],
) -> list[str]:
    file_lines = [f"Review `{item['path']}` before any later patch phase." for item in target_files]
    if not file_lines:
        file_lines = ["Review the candidate target files before drafting any later patch phase."]
    edits = [
        f"Candidate `{candidate_id}`: {title}.",
        f"Intent: {intent}",
        f"Change type: {change_type}. Keep this as narrative patch text only.",
        f"Keep the change confined to the selected target files and preserve the approved migration goal: {draft_record.get('migration_goal', '')}.",
        *file_lines,
        "Do not convert this text draft into an executable diff yet.",
        "Keep configuration, documentation, test, and compatibility boundaries aligned with the approved candidate package.",
    ]
    return edits


def _build_candidate_safety_notes(candidate_id: str, target_files: list[dict[str, Any]]) -> list[str]:
    file_list = ", ".join(f"`{item['path']}`" for item in target_files) or "the selected files"
    return [
        "No executable unified diff is included in this draft.",
        "No patch is applied or validated in this phase.",
        f"Keep `{candidate_id}` limited to {file_list}.",
        "Read the referenced files before any later patch or sandbox phase.",
    ]


def _build_safety_notes(record: dict[str, Any]) -> list[str]:
    return [
        "This phase is patch text only and does not emit an executable diff.",
        "No patch was applied, validated, or committed.",
        "Keep patch safety checks in place before any later sandbox or patch phase.",
        "Do not treat the patch text draft as a source of truth for code changes without rereading the approved chain.",
    ]


def _build_human_next_steps(*, draft_record: dict[str, Any], candidate_ids: list[str]) -> list[str]:
    steps = [
        "Read the files listed under Files To Read First before any later patch phase.",
        f"Review the selected candidate ids in order: {', '.join(candidate_ids)}.",
        "Keep the patch text draft read-only until the next manual approval step.",
        "Verify patch safety before any later sandbox or patch drafting phase.",
    ]
    if draft_record.get("open_questions"):
        steps.append("Revisit the draft package open questions and close out the ones that affect rollout.")
    return steps


def _build_error_record(
    *,
    repo_root: Path,
    source_plan_path: str,
    source_plan_hash: str,
    approval_path: str,
    patch_draft_package_path: str,
    patch_candidates_path: str,
    migration_goal: str,
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
        "notes": _normalize_text(notes),
        "source_plan_path": source_plan_path,
        "source_plan_hash": source_plan_hash,
        "approval_path": approval_path,
        "patch_draft_package_path": patch_draft_package_path,
        "patch_candidates_path": patch_candidates_path,
        "approval_verified": False,
        "approval_decision": "",
        "patch_draft_package_source_hash_matched": False,
        "patch_draft_package_approval_matched": False,
        "patch_candidates_source_hash_matched": False,
        "patch_candidates_approval_matched": False,
        "patch_candidates_draft_matched": False,
        "migration_goal": migration_goal,
        "patch_text_draft_only": False,
        "source_files_mutated": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "sandbox_validation_allowed_later": True,
        "requires_patch_safety_before_sandbox": True,
        "real_repo_apply_allowed": False,
        "selected_candidate_ids": [],
        "selected_candidates": [],
        "patch_text_drafts": [],
        "files_to_read_first": [],
        "risks": [],
        "tests_required_later": [],
        "rollback_notes": [],
        "open_questions": [],
        "human_next_steps": [],
        "limitations": [
            "This is a patch text draft only. No patch was applied, validated, or committed.",
            "A matching approved migration plan, draft package, and candidate package are required before any patch text draft can be created.",
        ],
    }


def _select_candidates(
    candidates: Any,
    *,
    selected_candidate_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if not isinstance(candidates, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = _normalize_text(item.get("candidate_id"))
        title = _normalize_text(item.get("title"))
        if not candidate_id or not title:
            continue
        normalized.append(
            {
                "candidate_id": candidate_id,
                "title": title,
                "intent": _normalize_text(item.get("intent")) or "",
                "target_files": _normalize_file_entries(item.get("target_files", [])),
                "change_type": _normalize_text(item.get("change_type")) or "unknown",
                "rationale": _normalize_text(item.get("rationale")) or "",
                "dependencies": _normalize_string_list(item.get("dependencies", [])),
                "risks": _normalize_string_list(item.get("risks", [])),
                "tests_to_run_later": _normalize_string_list(item.get("tests_to_run_later", [])),
                "requires_full_file_read": bool(item.get("requires_full_file_read", True)),
            }
        )

    if not selected_candidate_ids:
        return normalized

    requested = _normalize_string_list(selected_candidate_ids)
    selected_by_id = {item["candidate_id"]: item for item in normalized}
    ordered = [selected_by_id[candidate_id] for candidate_id in requested if candidate_id in selected_by_id]
    return ordered


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


def _resolve_project_evolution_artifact_path(repo_root: Path, artifact_path: str, dirname: str) -> Path | None:
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
    resolved = (repo_root / ".agent" / "project_evolution" / PATCH_TEXT_DRAFTS_DIRNAME).resolve()
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


def _unique_file_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _limit_file_entries(entries: list[dict[str, Any]], *, max_files: int) -> list[dict[str, Any]]:
    return entries[:max_files]


def _render_selected_candidates(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return ["- No candidates were selected."]
    lines: list[str] = []
    for candidate in candidates:
        lines.append(
            f"- `{candidate['candidate_id']}`: {candidate['title']} "
            f"({candidate['change_type']}, {len(candidate['target_files'])} file(s))"
        )
    return lines


def _render_patch_text_drafts(drafts: list[dict[str, Any]]) -> list[str]:
    if not drafts:
        return ["- No patch text drafts were selected."]
    lines: list[str] = []
    for draft in drafts:
        lines.extend(
            [
                f"### {draft['title']}",
                f"- Draft ID: `{draft['draft_id']}`",
                f"- Candidate ID: `{draft['candidate_id']}`",
                f"- Change type: `{draft['change_type']}`",
                f"- Patch format: `{draft['patch_format']}`",
                f"- Apply allowed: `{draft['apply_allowed']}`",
                f"- Validation allowed: `{draft['validation_allowed']}`",
                f"- Requires full file read: `{draft['requires_full_file_read']}`",
                "- Target files:",
                *_render_file_lines(draft.get("target_files", [])),
                "- Proposed edits:",
                *_render_string_list(draft.get("proposed_edits", [])),
                "- Safety notes:",
                *_render_string_list(draft.get("safety_notes", [])),
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
        path = item.get("path", "")
        category = item.get("category", "unknown")
        confidence = item.get("confidence", 0.0)
        reason = item.get("reason", "")
        lines.append(f"- `{path}` [{category}, confidence={confidence}] {reason}".rstrip())
    return lines or ["- None"]


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


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


def _normalize_string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


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
    return "".join(slug).strip("-") or "draft"


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

