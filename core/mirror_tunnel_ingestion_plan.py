"""MIRROR.4 - Real Run Trace Ingestion Plan (report-only).

MIRROR.4 defines how future real C.A.T.T.U.S runs should emit usable Mirror
Tunnel frames for MIRROR.1-MIRROR.3. It is a planning/report layer only: no
models, no patch apply, no validation or benchmark execution, no MCP/worker
launch, no Docker/subprocess, no network, no database writes, no route/auth
changes, no execution blocking, and no automatic Mirror tracing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_ingestion_plan"
JSON_NAME = "mirror_tunnel_ingestion_plan.json"
MD_NAME = "mirror_tunnel_ingestion_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "ingestion_plan"

FRAME_TYPES: tuple[str, ...] = (
    "user_intent",
    "goal_brief",
    "mode_decision",
    "control_prompt",
    "worker_assignment",
    "worker_reply",
    "patch_or_diff",
    "validation_evidence",
    "benchmark_evidence",
    "replay_evidence",
    "final_answer",
)

INGESTION_PRIORITIES: dict[str, tuple[str, ...]] = {
    "P0": ("user_intent", "control_prompt", "patch_or_diff", "validation_evidence", "final_answer"),
    "P1": ("goal_brief", "worker_assignment", "benchmark_evidence", "replay_evidence"),
    "P2": ("worker_reply", "mode_decision", "teaching_lesson_cards"),
}

STATUSES: tuple[str, ...] = (
    "ready_for_manual_ingestion",
    "partial_mapping_available",
    "insufficient_sources",
    "blocked",
)

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.4 is report-only.",
    "MIRROR.4 defines future ingestion and emission points only.",
    "MIRROR.4 does not enable automatic Mirror tracing.",
    "MIRROR.4 does not call models.",
    "MIRROR.4 does not apply patches.",
    "MIRROR.4 does not run validation.",
    "MIRROR.4 does not run benchmarks.",
    "MIRROR.4 does not invoke MCP tools.",
    "MIRROR.4 does not launch workers.",
    "MIRROR.4 does not execute Dream actions.",
    "MIRROR.4 does not apply Replay janitor actions.",
    "MIRROR.4 does not use Docker or subprocess.",
    "MIRROR.4 does not contact network services.",
    "MIRROR.4 does not write to a database.",
    "MIRROR.4 does not change route behavior.",
    "MIRROR.4 does not change auth policy.",
    "MIRROR.4 writes plan artifacts only.",
)

SOURCE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "source_id": "raw_query_textarea",
        "target_frame_type": "user_intent",
        "priority": "P0",
        "candidate_paths": ["web/templates/index.html"],
        "required_fields": ["raw_user_text", "submitted_at", "source_surface", "run_id"],
        "notes": "The run entrypoint should persist the raw query textarea before prompt rewriting.",
    },
    {
        "source_id": "goal_brief_json",
        "target_frame_type": "goal_brief",
        "priority": "P1",
        "candidate_paths": [".agent/goal_briefs/**/goal_brief.json", ".agent/ux/goal_brief_4w1h/*.json"],
        "required_fields": ["brief_id", "objective", "constraints", "validation_expectations", "artifact_path"],
        "notes": "Goal Brief artifacts can become structured goal_brief frames when linked to a run id.",
    },
    {
        "source_id": "mixed_mode_router_preview",
        "target_frame_type": "mode_decision",
        "priority": "P2",
        "candidate_paths": [".agent/ux/mixed_mode_intent_router/*.json", ".agent/roadmap/phase_picker_report.json"],
        "required_fields": ["mode", "reason", "confidence", "allowed_next_steps", "forbidden_next_steps"],
        "notes": "Mode preview/driver decision artifacts should record the route chosen for the run.",
    },
    {
        "source_id": "debug_last_control_prompt",
        "target_frame_type": "control_prompt",
        "priority": "P0",
        "candidate_paths": [".agent/debug_last_control_prompt.txt", ".agent/replays/**/prompt*.txt"],
        "required_fields": ["prompt_text", "prompt_hash", "model_or_worker_target", "run_id", "artifact_path"],
        "notes": "Control prompts must be captured as artifacts before dispatch, with secret redaction.",
    },
    {
        "source_id": "worker_assignment_json",
        "target_frame_type": "worker_assignment",
        "priority": "P1",
        "candidate_paths": [".agent/worker_assignments/**/worker_assignment.json"],
        "required_fields": ["worker_id", "objective", "allowed_files", "forbidden_files", "validation_expectations"],
        "notes": "Worker assignment artifacts should preserve objective, file boundaries, and evidence expectations.",
    },
    {
        "source_id": "worker_result_review",
        "target_frame_type": "worker_reply",
        "priority": "P2",
        "candidate_paths": [".agent/workers/**/result*.json", ".agent/**/proposal.md"],
        "required_fields": ["worker_id", "reply_text", "claimed_changes", "evidence_links", "artifact_path"],
        "notes": "Worker replies are not consistently saved in a Mirror-friendly schema today.",
        "current_gap": True,
    },
    {
        "source_id": "patch_proposal_json",
        "target_frame_type": "patch_or_diff",
        "priority": "P0",
        "candidate_paths": [".agent/patches/**/*.json", ".agent/**/patch*.json", ".agent/**/diff*.txt"],
        "required_fields": ["artifact_path", "changed_files", "patched_files", "generated_artifacts", "unexpected_mutations"],
        "notes": "Patch proposals should normalize changed_files, patched_files, generated artifacts, and unexpected mutations.",
    },
    {
        "source_id": "validation_result_json",
        "target_frame_type": "validation_evidence",
        "priority": "P0",
        "candidate_paths": [".agent/validation/**/*.json", ".agent/**/validation*.json", ".agent/harden/**/*.json"],
        "required_fields": ["command", "status", "exit_code", "started_at", "finished_at", "artifact_path"],
        "notes": "Validation evidence should be saved by safe-validation paths, not run by MIRROR.4.",
    },
    {
        "source_id": "benchmark_report_json",
        "target_frame_type": "benchmark_evidence",
        "priority": "P1",
        "candidate_paths": [".agent/benchmarks/benchmark_report_*.json", ".agent/eval/**/*.json"],
        "required_fields": ["benchmark_report_id", "case_count", "status", "failures", "artifact_path"],
        "notes": "Existing benchmark reports can map directly to benchmark_evidence frames.",
    },
    {
        "source_id": "replay_artifacts",
        "target_frame_type": "replay_evidence",
        "priority": "P1",
        "candidate_paths": [".agent/replays/**"],
        "required_fields": ["replay_id", "status", "source_run_id", "artifact_path", "findings"],
        "notes": "Replay artifacts should be linked, never executed, by Mirror ingestion.",
    },
    {
        "source_id": "saved_final_answer",
        "target_frame_type": "final_answer",
        "priority": "P0",
        "candidate_paths": [".agent/answers/**/final_answer.txt", ".agent/runs/**/final_answer.md", ".agent/**/answer*.json"],
        "required_fields": ["answer_text", "claims_summary", "validation_summary", "benchmark_summary", "artifact_path"],
        "notes": "Saved answer/result artifacts are the main current gap; final answers are not consistently persisted.",
        "current_gap": True,
    },
    {
        "source_id": "teaching_lesson_cards",
        "target_frame_type": "teaching_lesson_cards",
        "priority": "P2",
        "candidate_paths": [".agent/lessons/**/*.json", ".agent/model/**/*.json"],
        "required_fields": ["lesson_id", "source_run_id", "claim", "evidence_link", "artifact_path"],
        "notes": "Teaching/lesson cards are useful context but not core Mirror trace frames yet.",
    },
)

FUTURE_INTEGRATION_POINTS: tuple[dict[str, Any], ...] = (
    {
        "integration_id": "persist_raw_user_intent",
        "target_frame_type": "user_intent",
        "priority": "P0",
        "description": "Persist raw query textarea and Goal Brief final prompt with run_id before any route or prompt rewrite.",
    },
    {
        "integration_id": "save_control_prompt_frame",
        "target_frame_type": "control_prompt",
        "priority": "P0",
        "description": "Save redacted control prompt artifact, prompt hash, and dispatch target before worker/model handoff.",
    },
    {
        "integration_id": "emit_patch_diff_frame",
        "target_frame_type": "patch_or_diff",
        "priority": "P0",
        "description": "Normalize patch proposal evidence into changed_files, patched_files, generated_artifacts, and unexpected_mutations.",
    },
    {
        "integration_id": "persist_validation_frame",
        "target_frame_type": "validation_evidence",
        "priority": "P0",
        "description": "Persist validation result JSON from existing safe-validation machinery without MIRROR.4 running validation.",
    },
    {
        "integration_id": "save_final_answer_frame",
        "target_frame_type": "final_answer",
        "priority": "P0",
        "description": "Save final answer/result text and evidence summaries in a run-linked artifact before responding to the operator.",
    },
    {
        "integration_id": "link_worker_assignment_and_reply",
        "target_frame_type": "worker_reply",
        "priority": "P2",
        "description": "Link worker assignment ids to worker replies and proposal artifacts with claims/evidence summaries.",
    },
)

MISSING_GAPS: tuple[dict[str, str], ...] = (
    {
        "gap_id": "final_answer_not_consistently_saved",
        "severity": "high",
        "affected_frame_type": "final_answer",
        "description": "Final answers/results are not consistently persisted as run-linked artifacts.",
    },
    {
        "gap_id": "worker_reply_not_mirror_friendly",
        "severity": "medium",
        "affected_frame_type": "worker_reply",
        "description": "Worker replies/proposals may exist, but claim/evidence fields are not normalized.",
    },
    {
        "gap_id": "real_run_frame_emission_missing",
        "severity": "high",
        "affected_frame_type": "all",
        "description": "Real run paths do not yet emit canonical Mirror Tunnel frame records.",
    },
    {
        "gap_id": "control_prompt_redaction_contract_needed",
        "severity": "medium",
        "affected_frame_type": "control_prompt",
        "description": "Control prompt capture needs explicit redaction and secret-boundary rules before automatic emission.",
    },
)


def build_mirror_tunnel_ingestion_plan(
    *,
    repo_path: str = ".",
    plan_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic report-only MIRROR.4 ingestion plan."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    inventory = [_inventory_item(repo_root, spec) for spec in SOURCE_SPECS]
    mapping = [_mapping_row(frame_type, inventory) for frame_type in FRAME_TYPES]
    status = _status_for_plan(inventory, mapping)
    report = {
        "report_kind": REPORT_KIND,
        "plan_id": plan_id or _default_plan_id(str(repo_root), created_at),
        "created_at": str(created_at or ""),
        "repo_path": str(repo_root),
        "status": status,
        "recommended_next_action": _recommended_next_action(status),
        "recommended_next_phase": "MIRROR.5",
        "current_trace_weakness": _current_trace_weakness(),
        "artifact_source_inventory": inventory,
        "frame_mapping_plan": mapping,
        "ingestion_priority": {key: list(value) for key, value in INGESTION_PRIORITIES.items()},
        "required_fields_per_source": {
            item["source_id"]: list(item["required_fields"]) for item in inventory
        },
        "missing_source_gaps": [dict(item) for item in MISSING_GAPS],
        "future_integration_points": [dict(item) for item in FUTURE_INTEGRATION_POINTS],
        "safety_privacy_boundaries": list(BOUNDARIES),
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }
    return report


def write_mirror_tunnel_ingestion_plan(
    *,
    repo_path: str = ".",
    output_root: str | None = None,
    plan_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Write MIRROR.4 ingestion-plan JSON + Markdown artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    try:
        output_dir = _resolve_output_root(repo_root, output_root)
    except ValueError as exc:
        report = _blocked_report(plan_id=plan_id, created_at=created_at, repo_path=str(repo_root), reason=str(exc))
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_mirror_tunnel_ingestion_markdown(report),
        }

    report = build_mirror_tunnel_ingestion_plan(repo_path=str(repo_root), plan_id=plan_id, created_at=created_at)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_NAME
    md_path = output_dir / MD_NAME
    markdown = render_mirror_tunnel_ingestion_markdown(report)
    json_path.write_text(render_mirror_tunnel_ingestion_json(report), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": report["status"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_mirror_tunnel_ingestion_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_ingestion_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Real Run Trace Ingestion Plan",
        "",
        "## Summary",
        "",
        f"- **Plan id:** `{_md(report.get('plan_id'))}`",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Current Trace Weakness",
        "",
        _bullet_list(_dict_lines(report.get("current_trace_weakness"))),
        "",
        "## Source Artifact Inventory",
        "",
        _source_table(report.get("artifact_source_inventory")),
        "",
        "## Frame Mapping Table",
        "",
        _mapping_table(report.get("frame_mapping_plan")),
        "",
        "## Missing Frame Gaps",
        "",
        _bullet_list(_gap_lines(report.get("missing_source_gaps"))),
        "",
        "## Proposed Future Integration Points",
        "",
        _bullet_list(_integration_lines(report.get("future_integration_points"))),
        "",
        "## Safety / Privacy Boundaries",
        "",
        _bullet_list([_md(item) for item in report.get("safety_privacy_boundaries", [])]),
        "",
        "## Recommended Next Phase",
        "",
        f"`{_md(report.get('recommended_next_phase'))}`",
        "",
    ]
    return "\n".join(lines)


def _inventory_item(repo_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    candidate_paths = list(spec["candidate_paths"])
    existing = _matching_paths(repo_root, candidate_paths)
    item = {
        "source_id": str(spec["source_id"]),
        "target_frame_type": str(spec["target_frame_type"]),
        "priority": str(spec["priority"]),
        "candidate_paths": candidate_paths,
        "required_fields": list(spec["required_fields"]),
        "existing_artifacts_found": existing,
        "availability": "available" if existing else "not_detected",
        "current_gap": bool(spec.get("current_gap", False)),
        "notes": str(spec["notes"]),
    }
    if item["current_gap"] and item["availability"] == "available":
        item["availability"] = "available_but_not_mirror_friendly"
    return item


def _mapping_row(frame_type: str, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    sources = [item for item in inventory if item["target_frame_type"] == frame_type]
    priority = _priority_for_frame(frame_type)
    required_fields: list[str] = []
    candidate_sources: list[str] = []
    source_ids: list[str] = []
    gaps: list[str] = []
    for source in sources:
        source_ids.append(source["source_id"])
        candidate_sources.append(_source_label(source["source_id"]))
        for field in source["required_fields"]:
            if field not in required_fields:
                required_fields.append(field)
        if source["current_gap"]:
            gaps.append(source["source_id"])
    return {
        "frame_type": frame_type,
        "priority": priority,
        "source_ids": source_ids,
        "candidate_sources": candidate_sources,
        "required_fields": required_fields,
        "current_gaps": gaps,
        "ingestion_action": _ingestion_action(frame_type, bool(source_ids), bool(gaps)),
    }


def _matching_paths(repo_root: Path, patterns: list[str]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        if _forbidden_pattern(pattern):
            continue
        try:
            matches = sorted(repo_root.glob(pattern))
        except (OSError, ValueError):
            matches = []
        for match in matches[:5]:
            if _forbidden_path(match):
                continue
            try:
                rel = match.resolve().relative_to(repo_root)
            except (OSError, ValueError):
                continue
            found.append(str(rel).replace("\\", "/"))
    return _dedupe(found)[:8]


def _status_for_plan(inventory: list[dict[str, Any]], mapping: list[dict[str, Any]]) -> str:
    mapped_frames = [row for row in mapping if row["source_ids"]]
    p0_gaps = [row for row in mapping if row["priority"] == "P0" and row["current_gaps"]]
    if len(mapped_frames) < 3:
        return "insufficient_sources"
    if p0_gaps:
        return "partial_mapping_available"
    if any(item["availability"] == "available" for item in inventory):
        return "ready_for_manual_ingestion"
    return "partial_mapping_available"


def _recommended_next_action(status: str) -> str:
    if status == "ready_for_manual_ingestion":
        return "prepare_manual_ingestion_dry_run"
    if status == "partial_mapping_available":
        return "prepare_mirror_frame_emitter_contract"
    if status == "insufficient_sources":
        return "catalog_more_run_artifacts"
    return "resolve_blockers"


def _current_trace_weakness() -> dict[str, Any]:
    return {
        "primary_weakness": "current traces are dominated by unknown_artifact frames",
        "impact": "MIRROR.2 and MIRROR.3 can report insufficient evidence, but cannot yet reconstruct real intent-to-evidence chains reliably.",
        "expected_current_status": "partial_mapping_available",
        "reason": "Some sources already exist, but final_answer, worker_reply, and real run frame emission are not consistently saved in a Mirror-friendly shape.",
    }


def _priority_for_frame(frame_type: str) -> str:
    for priority, frames in INGESTION_PRIORITIES.items():
        if frame_type in frames:
            return priority
    return "P2"


def _ingestion_action(frame_type: str, has_sources: bool, has_gaps: bool) -> str:
    if not has_sources:
        return f"define source contract for {frame_type}"
    if has_gaps:
        return f"normalize and persist {frame_type} source artifacts"
    return f"map existing artifacts into {frame_type} frames"


def _source_label(source_id: str) -> str:
    labels = {
        "raw_query_textarea": "raw query textarea",
        "goal_brief_json": "Goal Brief JSON",
        "mixed_mode_router_preview": "mixed mode router preview / driver decision artifacts",
        "debug_last_control_prompt": "debug last control prompt / replay prompt artifacts",
        "worker_assignment_json": "worker assignment JSON",
        "worker_result_review": "worker result review artifacts / proposal.md",
        "patch_proposal_json": "patch proposal JSON / changed_files / patched_files / generated_artifacts",
        "validation_result_json": "validation result JSON / safe validation metadata",
        "benchmark_report_json": "benchmark report JSON",
        "replay_artifacts": "replay artifacts",
        "saved_final_answer": "saved answer/result artifacts",
        "teaching_lesson_cards": "teaching/lesson cards",
    }
    return labels.get(source_id, source_id)


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "automatic_mirror_tracing_enabled": False,
        "writes_plan_artifacts_only": True,
    }


def _blocked_report(*, plan_id: str | None, created_at: str, repo_path: str, reason: str) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "plan_id": plan_id or _default_plan_id(repo_path, created_at),
        "created_at": str(created_at or ""),
        "repo_path": repo_path,
        "status": "blocked",
        "recommended_next_action": "resolve_blockers",
        "recommended_next_phase": "MIRROR.5",
        "current_trace_weakness": _current_trace_weakness(),
        "artifact_source_inventory": [],
        "frame_mapping_plan": [],
        "ingestion_priority": {key: list(value) for key, value in INGESTION_PRIORITIES.items()},
        "required_fields_per_source": {},
        "missing_source_gaps": [dict(item) for item in MISSING_GAPS],
        "future_integration_points": [dict(item) for item in FUTURE_INTEGRATION_POINTS],
        "safety_privacy_boundaries": list(BOUNDARIES),
        "boundaries": list(BOUNDARIES),
        "blockers": [{"reason": reason}],
        "guardrails": _guardrails(),
    }


def _resolve_output_root(repo_root: Path, raw: str | None) -> Path:
    raw_path = Path(raw or DEFAULT_OUTPUT_ROOT).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"refusing traversal output path: {raw or DEFAULT_OUTPUT_ROOT}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"refusing output path outside repository: {resolved}") from exc
    if _forbidden_path(resolved):
        raise ValueError(f"refusing secret/env/key output path: {resolved}")
    return resolved


def _forbidden_pattern(pattern: str) -> bool:
    low = pattern.lower()
    return any(token in low for token in (".env", "secret", "credential", ".agent/private"))


def _forbidden_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if ".env" in parts or ".agent" in parts and "private" in parts:
        return True
    if any("secret" in part or "credential" in part for part in parts):
        return True
    if name.endswith((".key", ".pem")) or name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
        return True
    return False


def _default_plan_id(repo_path: str, created_at: str) -> str:
    seed = json.dumps({"repo_path": repo_path, "created_at": str(created_at or "")}, sort_keys=True)
    return "mirror-ingestion-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _source_table(value: Any) -> str:
    items = value if isinstance(value, list) else []
    if not items:
        return "_None._"
    lines = [
        "| Source | Frame | Priority | Availability | Candidate paths | Required fields |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {source} | {frame} | {priority} | {availability} | {paths} | {fields} |".format(
                source=_md(item.get("source_id")),
                frame=_md(item.get("target_frame_type")),
                priority=_md(item.get("priority")),
                availability=_md(item.get("availability")),
                paths=_md(", ".join(item.get("candidate_paths") or [])),
                fields=_md(", ".join(item.get("required_fields") or [])),
            )
        )
    return "\n".join(lines)


def _mapping_table(value: Any) -> str:
    items = value if isinstance(value, list) else []
    if not items:
        return "_None._"
    lines = [
        "| Frame | Priority | Candidate sources | Required fields | Current gaps | Action |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        if not isinstance(item, dict):
            continue
        lines.append(
            "| {frame} | {priority} | {sources} | {fields} | {gaps} | {action} |".format(
                frame=_md(item.get("frame_type")),
                priority=_md(item.get("priority")),
                sources=_md(", ".join(item.get("candidate_sources") or [])),
                fields=_md(", ".join(item.get("required_fields") or [])),
                gaps=_md(", ".join(item.get("current_gaps") or [])),
                action=_md(item.get("ingestion_action")),
            )
        )
    return "\n".join(lines)


def _dict_lines(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [f"`{_md(key)}`: {_md(value[key])}" for key in sorted(value)]


def _gap_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{_md(item.get('gap_id'))}` ({_md(item.get('severity'))}, `{_md(item.get('affected_frame_type'))}`): {_md(item.get('description'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _integration_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{_md(item.get('integration_id'))}` ({_md(item.get('priority'))}, `{_md(item.get('target_frame_type'))}`): {_md(item.get('description'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
