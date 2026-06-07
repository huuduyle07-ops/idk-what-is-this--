from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import project_evolution_approval as approval_core


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_patch_candidates_v1"
APPROVAL_SCHEMA_VERSION = "evolution_plan_review_v1"
DRAFT_PACKAGE_SCHEMA_VERSION = "evolution_patch_draft_package_v1"
PATCH_CANDIDATES_DIRNAME = "patch_candidates"
DEFAULT_MAX_CANDIDATES = 8

GROUP_ORDER = (
    "Config/env changes",
    "Provider abstraction changes",
    "Retrieval/indexing changes",
    "Graph/search integration changes",
    "Tests",
    "Documentation",
    "Rollback/compatibility",
)

GROUP_METADATA: dict[str, dict[str, Any]] = {
    "Config/env changes": {
        "change_type": "config",
        "intent": (
            "Draft a candidate work order for configuration, environment, and dependency surfaces "
            "that can affect migration startup and runtime compatibility."
        ),
        "dependencies": [
            "Approved migration plan",
            "Provider abstraction review",
            "Runtime configuration contract review",
        ],
        "risks": [
            "Config drift can silently break provider selection, fallback routing, or secrets handling.",
        ],
        "tests_to_run_later": [
            "Re-run configuration and startup coverage after the later patch phase.",
            "Check that environment parsing still matches the approved runtime contract.",
        ],
    },
    "Provider abstraction changes": {
        "change_type": "code",
        "intent": (
            "Draft a candidate work order for provider abstraction and adapter surfaces that need "
            "compatibility during the migration."
        ),
        "dependencies": [
            "Approved migration plan",
            "Config/env changes",
            "Retrieval/indexing changes",
        ],
        "risks": [
            "Provider wiring can change embedding shape or retrieval behavior even when imports still succeed.",
        ],
        "tests_to_run_later": [
            "Run focused provider abstraction tests once patch text exists.",
            "Check fallback routing and embedding output shape coverage.",
        ],
    },
    "Retrieval/indexing changes": {
        "change_type": "code",
        "intent": (
            "Draft a candidate work order for retrieval and indexing surfaces that can influence "
            "search output or evidence flow."
        ),
        "dependencies": [
            "Approved migration plan",
            "Provider abstraction changes",
        ],
        "risks": [
            "Retrieval or indexer changes can shift search output quality or evidence ordering.",
        ],
        "tests_to_run_later": [
            "Run focused indexing and retrieval regression coverage.",
            "Check any migration-sensitive search output snapshots.",
        ],
    },
    "Graph/search integration changes": {
        "change_type": "code",
        "intent": (
            "Draft a candidate work order for graph and search integration surfaces that may affect "
            "ranking or evidence ordering."
        ),
        "dependencies": [
            "Approved migration plan",
            "Retrieval/indexing changes",
        ],
        "risks": [
            "Graph weight or search integration changes can alter evidence ordering and hotspot interpretation.",
        ],
        "tests_to_run_later": [
            "Run graph-weight and evidence-ordering regression coverage after patch text exists.",
            "Verify any search integration snapshots that depend on ranking.",
        ],
    },
    "Tests": {
        "change_type": "test",
        "intent": (
            "Draft a candidate work order for regression coverage that protects the migration-sensitive surfaces."
        ),
        "dependencies": [
            "Approved migration plan",
            "Any selected code or config candidates",
        ],
        "risks": [
            "Test selection can encode legacy assumptions if the migration changes behavior intentionally.",
        ],
        "tests_to_run_later": [
            "Update or add focused regression tests before any later patch phase.",
            "Run the selected migration-sensitive tests after the later patch phase.",
        ],
    },
    "Documentation": {
        "change_type": "docs",
        "intent": (
            "Draft a candidate work order for docs and migration notes that must stay aligned with the approved plan."
        ),
        "dependencies": [
            "Approved migration plan",
            "Any resolved code, config, or test decisions",
        ],
        "risks": [
            "Docs can drift from the approved operator workflow if the migration story changes midstream.",
        ],
        "tests_to_run_later": [
            "Check docs rendering or markdown lint if the repo enforces it.",
            "Confirm docs match the later patch phase before shipping.",
        ],
    },
    "Rollback/compatibility": {
        "change_type": "compatibility",
        "intent": (
            "Draft a candidate work order for rollback-friendly and compatibility-preserving surfaces."
        ),
        "dependencies": [
            "Approved migration plan",
            "Provider abstraction changes",
            "Config/env changes",
        ],
        "risks": [
            "Rollback or compatibility shims can be fragile if the later patch phase changes too many entry points at once.",
        ],
        "tests_to_run_later": [
            "Verify rollback and compatibility coverage after the later patch phase.",
            "Check any entrypoint or shim behavior that needs to remain stable.",
        ],
    },
}


def build_project_evolution_patch_candidates(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    *,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
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
            approval_hash_or_id="",
            patch_draft_package_path="",
            migration_goal="",
            notes=notes,
            message=current_plan_load.get("message", "migration plan is unavailable"),
            code="source_plan_unavailable",
        )

    if max_candidates < 1:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path="",
            approval_hash_or_id="",
            patch_draft_package_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message="max_candidates must be at least 1",
            code="invalid_max_candidates",
        )

    approval_resolved = _resolve_project_evolution_artifact_path(
        repo_root,
        approval_path,
        "approvals",
    )
    if approval_resolved is None:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(_resolve_candidate_path(repo_root, approval_path)),
            approval_hash_or_id=_approval_id_from_path(approval_path),
            patch_draft_package_path="",
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=(
                "approval record must live inside .agent/project_evolution/approvals/"
            ),
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
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            patch_draft_package_path=str(_resolve_candidate_path(repo_root, patch_draft_package_path)),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=(
                "patch draft package must live inside .agent/project_evolution/patch_drafts/"
            ),
            code="draft_path_outside_patch_drafts",
        )

    approval_load = _load_json_record(approval_resolved, APPROVAL_SCHEMA_VERSION, "approval")
    if approval_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_plan_load["source_plan_hash"],
            approval_path=str(approval_resolved),
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            patch_draft_package_path=str(draft_resolved),
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
            approval_hash_or_id=_approval_id_from_path(approval_resolved.name),
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan_load["source_plan"].get("migration_goal", ""),
            notes=notes,
            message=draft_load["message"],
            code=draft_load["code"],
        )

    approval_record = approval_load["record"]
    draft_record = draft_load["record"]
    current_plan = current_plan_load["source_plan"]
    current_hash = current_plan_load["source_plan_hash"]
    approval_id = _approval_id_from_path(approval_resolved.name)

    if approval_record.get("decision") != "approve":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="approval decision must be approve before candidate drafting can begin",
            code="approval_not_approved",
        )

    if approval_record.get("patch_generation_allowed") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="approval record does not allow patch generation",
            code="approval_patch_gate_closed",
        )

    approval_source_hash = str(approval_record.get("source_plan_hash") or "")
    if approval_source_hash != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message=(
                "approval source_plan_hash does not match the current normalized migration plan hash"
            ),
            code="approval_source_hash_mismatch",
        )

    draft_source_hash = str(draft_record.get("source_plan_hash") or "")
    if draft_source_hash != current_hash:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message=(
                "patch draft package source_plan_hash does not match the current normalized migration plan hash"
            ),
            code="draft_source_hash_mismatch",
        )

    draft_approval_path = _resolve_project_evolution_artifact_path(
        repo_root,
        str(draft_record.get("approval_path", "")),
        "approvals",
    )
    if draft_approval_path is None or draft_approval_path != approval_resolved:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package was not created from the selected approval record",
            code="draft_approval_mismatch",
        )

    if str(draft_record.get("approval_hash_or_id") or "") != approval_id:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package approval id does not match the selected approval record",
            code="draft_approval_id_mismatch",
        )

    if draft_record.get("approval_decision") != "approve":
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package must be sourced from an approved draft package",
            code="draft_not_approved",
        )

    if draft_record.get("draft_package_only") is not True:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
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
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
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
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
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
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package must keep validation execution disabled",
            code="draft_validation_gate_open",
        )

    selected_groups = _select_groups(draft_record.get("proposed_change_groups", []), max_candidates=max_candidates)
    candidates = _build_candidates(selected_groups, draft_record, max_candidates=max_candidates)
    if not candidates:
        return _build_error_record(
            repo_root=repo_root,
            source_plan_path=current_plan_load["source_plan_path"],
            source_plan_hash=current_hash,
            approval_path=str(approval_resolved),
            approval_hash_or_id=approval_id,
            patch_draft_package_path=str(draft_resolved),
            migration_goal=current_plan.get("migration_goal", ""),
            notes=notes,
            message="patch draft package does not contain any selectable candidate groups",
            code="draft_no_candidates",
        )

    files_to_read_first = _unique_file_entries(
        [
            *[
                file_item
                for candidate in candidates
                for file_item in candidate["target_files"]
            ],
            *_normalize_file_entries(draft_record.get("files_to_read_first", [])),
        ]
    )
    proposed_change_groups = [
        {
            "title": group["title"],
            "summary": group["summary"],
            "rationale": group["rationale"],
            "files": _normalize_file_entries(group.get("files", [])),
        }
        for group in selected_groups
    ]

    tests_required = _normalize_string_list(draft_record.get("test_requirements", []))
    docs_required = _normalize_string_list(draft_record.get("docs_requirements", []))
    rollback_notes = _normalize_string_list(draft_record.get("rollback_requirements", []))
    risks = _normalize_string_list(draft_record.get("risks", []))
    open_questions = _normalize_string_list(draft_record.get("open_questions", []))
    human_next_steps = _build_human_next_steps(
        draft_record=draft_record,
        candidates=candidates,
    )
    limitations = [
        "This is a candidate draft only. No patch was generated, applied, or validated.",
        "The candidate package uses the approved migration plan and approved patch draft package as its only sources.",
        "Approval remains valid only while the current migration plan hash matches both the approval record and the patch draft package.",
        "No model/API calls, patch generation, patch application, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
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
        "approval_hash_or_id": approval_id,
        "patch_draft_package_path": str(draft_resolved),
        "approval_verified": True,
        "approval_decision": approval_record.get("decision", ""),
        "approval_source_hash_matched": True,
        "patch_draft_package_source_hash_matched": True,
        "patch_draft_package_approval_matched": True,
        "migration_goal": current_plan.get("migration_goal", ""),
        "patch_generation_allowed": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "candidate_draft_only": True,
        "source_files_mutated": False,
        "candidates": candidates,
        "proposed_change_groups": proposed_change_groups,
        "files_to_read_first": files_to_read_first,
        "risks": risks,
        "tests_required": tests_required,
        "docs_required": docs_required,
        "rollback_notes": rollback_notes,
        "open_questions": open_questions,
        "human_next_steps": human_next_steps,
        "limitations": limitations,
    }


def render_project_evolution_patch_candidates_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Patch Candidates",
        "",
        "## Summary",
        f"- Repo path: `{record.get('repo_path', '')}`",
        f"- Mode: `{record.get('mode', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Candidate count: `{len(record.get('candidates', []))}`",
        f"- Source plan: `{record.get('source_plan_path', '')}`",
        f"- Source plan hash: `{record.get('source_plan_hash', '')}`",
        f"- Approval path: `{record.get('approval_path', '')}`",
        f"- Patch draft package: `{record.get('patch_draft_package_path', '')}`",
        "- This is a candidate draft only. No patch was generated, applied, or validated.",
        "",
        "## Approval Verification",
        f"- Approval verified: `{record.get('approval_verified', False)}`",
        f"- Approval decision: `{record.get('approval_decision', '')}`",
        f"- Approval source hash matched: `{record.get('approval_source_hash_matched', False)}`",
        f"- Draft package source hash matched: `{record.get('patch_draft_package_source_hash_matched', False)}`",
        f"- Draft package approval matched: `{record.get('patch_draft_package_approval_matched', False)}`",
        f"- Patch generation allowed: `{record.get('patch_generation_allowed', False)}`",
        f"- Patch apply allowed: `{record.get('patch_apply_allowed', False)}`",
        f"- Validation execution allowed: `{record.get('validation_execution_allowed', False)}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Candidate Overview",
        *_render_candidate_overview(record.get("candidates", [])),
        "",
        "## Candidates",
        *_render_candidate_sections(record.get("candidates", [])),
        "",
        "## Files To Read First",
        *_render_file_lines(record.get("files_to_read_first", [])),
        "",
        "## Tests Required",
        *_render_string_list(record.get("tests_required", [])),
        "",
        "## Docs Required",
        *_render_string_list(record.get("docs_required", [])),
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


def write_project_evolution_patch_candidate_artifacts(
    repo_path: str,
    approval_path: str,
    patch_draft_package_path: str,
    *,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    notes: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_evolution_patch_candidates(
        str(repo_root),
        approval_path,
        patch_draft_package_path,
        max_candidates=max_candidates,
        notes=notes,
    )
    if record.get("status") != "ok":
        return {"record": record, "json_path": "", "md_path": ""}

    output_root = _resolve_output_root(repo_root)
    timestamp = _safe_timestamp(record["generated_at"])
    prefix = f"{timestamp}_patch_candidates"
    json_path = output_root / f"{prefix}.json"
    md_path = output_root / f"{prefix}.md"
    markdown = render_project_evolution_patch_candidates_markdown(record)
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _build_candidates(
    groups: list[dict[str, Any]],
    draft_record: dict[str, Any],
    *,
    max_candidates: int,
) -> list[dict[str, Any]]:
    likely_files = _normalize_file_entries(draft_record.get("likely_files_to_change", []))
    files_to_read_first = _normalize_file_entries(draft_record.get("files_to_read_first", []))
    allowed_paths = {item["path"] for item in likely_files} | {item["path"] for item in files_to_read_first}

    candidates: list[dict[str, Any]] = []
    for index, group in enumerate(groups[:max_candidates], start=1):
        title = str(group.get("title", "")).strip() or "Unknown"
        meta = GROUP_METADATA.get(title, _fallback_group_metadata(title))
        target_files = _normalize_file_entries(group.get("files", []))
        target_files = [item for item in target_files if item["path"] in allowed_paths]
        if not target_files:
            continue
        candidates.append(
            {
                "candidate_id": f"{_slugify(title)}-{index:02d}",
                "title": title,
                "intent": meta["intent"],
                "target_files": target_files,
                "change_type": meta["change_type"],
                "rationale": str(group.get("rationale", "")) or meta["intent"],
                "dependencies": _normalize_string_list(meta.get("dependencies", [])),
                "risks": _normalize_string_list([*meta.get("risks", []), *draft_record.get("risks", [])]),
                "tests_to_run_later": _normalize_string_list(meta.get("tests_to_run_later", [])),
                "requires_full_file_read": True,
                "patch_content": None,
                "unified_diff": None,
                "apply_allowed": False,
            }
        )
    return candidates


def _build_human_next_steps(
    *,
    draft_record: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[str]:
    steps = [
        "Read the files listed under Files To Read First before any later patch phase.",
        "Confirm the approval hash still matches the current migration plan before drafting patch text.",
        "Use the candidate buckets as a work order, not as an exact diff.",
        "Resolve open questions and compatibility boundaries before any patch generation phase.",
    ]
    if candidates:
        steps.insert(
            1,
            f"Review the {len(candidates)} candidate bucket(s) in deterministic order before any implementation work.",
        )
    if draft_record.get("open_questions"):
        steps.append("Revisit the draft package open questions and close out the ones that affect rollout.")
    return steps


def _build_error_record(
    *,
    repo_root: Path,
    source_plan_path: str,
    source_plan_hash: str,
    approval_path: str,
    approval_hash_or_id: str,
    patch_draft_package_path: str,
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
        "approval_hash_or_id": approval_hash_or_id,
        "patch_draft_package_path": patch_draft_package_path,
        "approval_verified": False,
        "approval_decision": "",
        "approval_source_hash_matched": False,
        "patch_draft_package_source_hash_matched": False,
        "patch_draft_package_approval_matched": False,
        "migration_goal": migration_goal,
        "patch_generation_allowed": False,
        "patch_apply_allowed": False,
        "validation_execution_allowed": False,
        "candidate_draft_only": False,
        "source_files_mutated": False,
        "candidates": [],
        "proposed_change_groups": [],
        "files_to_read_first": [],
        "risks": [],
        "tests_required": [],
        "docs_required": [],
        "rollback_notes": [],
        "open_questions": [],
        "human_next_steps": [],
        "limitations": [
            "This is a candidate draft only. No patch was generated, applied, or validated.",
            "A matching approved migration plan and approved patch draft package are required before any candidate package can be created.",
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
    resolved = (repo_root / ".agent" / "project_evolution" / PATCH_CANDIDATES_DIRNAME).resolve()
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


def _select_groups(groups: Any, *, max_candidates: int) -> list[dict[str, Any]]:
    if not isinstance(groups, list):
        return []
    normalized: list[dict[str, Any]] = []
    known = {title: index for index, title in enumerate(GROUP_ORDER)}
    for group in groups:
        if not isinstance(group, dict):
            continue
        title = str(group.get("title", "")).strip()
        if not title:
            continue
        normalized.append(
            {
                "title": title,
                "summary": _normalize_text(group.get("summary")) or "",
                "rationale": _normalize_text(group.get("rationale")) or "",
                "files": _normalize_file_entries(group.get("files", [])),
            }
        )
    normalized.sort(
        key=lambda item: (
            known.get(item["title"], len(known)),
            item["title"].lower(),
        )
    )
    return normalized[:max_candidates]


def _fallback_group_metadata(title: str) -> dict[str, Any]:
    return {
        "change_type": "unknown",
        "intent": f"Draft a candidate work order for the {title.lower()} bucket.",
        "dependencies": ["Approved migration plan"],
        "risks": [f"{title} may need additional review before patch drafting can begin."],
        "tests_to_run_later": ["Run the most relevant focused regression tests after the later patch phase."],
    }


def _render_candidate_overview(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return ["- No candidates were selected."]
    lines: list[str] = []
    for candidate in candidates:
        lines.append(
            f"- `{candidate['candidate_id']}`: {candidate['title']} "
            f"({candidate['change_type']}, {len(candidate['target_files'])} file(s))"
        )
    return lines


def _render_candidate_sections(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return ["- No candidates were selected."]
    lines: list[str] = []
    for candidate in candidates:
        lines.extend(
            [
                f"### {candidate['title']}",
                f"- Candidate ID: `{candidate['candidate_id']}`",
                f"- Change type: `{candidate['change_type']}`",
                f"- Intent: {candidate['intent']}",
                f"- Requires full file read: `{candidate['requires_full_file_read']}`",
                f"- Apply allowed: `{candidate['apply_allowed']}`",
                "- Target files:",
                *_render_file_lines(candidate.get("target_files", [])),
                "- Dependencies:",
                *_render_string_list(candidate.get("dependencies", [])),
                "- Risks:",
                *_render_string_list(candidate.get("risks", [])),
                "- Tests to run later:",
                *_render_string_list(candidate.get("tests_to_run_later", [])),
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
        lines.append(
            f"- `{path}` [{category}, confidence={confidence}] {reason}".rstrip()
        )
    return lines or ["- None"]


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


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
    return "".join(slug).strip("-") or "candidate"


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
