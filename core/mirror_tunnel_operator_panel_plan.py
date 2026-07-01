"""MIRROR.9 - Live Trace Operator Report Panel Plan.

This module builds a report-only operator UX plan for displaying MIRROR.7 live
trace artifacts and MIRROR.8 scoring previews. It defines panel placement,
visible fields, debug fields, advisory copy, status badges, evidence display
rules, and operator actions before any UI is built.

It does not implement UI, call models, apply patches, run validation, run
benchmarks, invoke tools, launch workers, execute Dream or Replay actions, use
Docker/subprocess, contact the network, write to a database, change route/auth
behavior, block runs, mutate traces or previews, or make Mirror Tunnel an
approval gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_operator_panel_plan"
JSON_NAME = "mirror_tunnel_operator_panel_plan.json"
MD_NAME = "mirror_tunnel_operator_panel_plan.md"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "operator_panel_plan"

PANEL_PLAN_READY = "panel_plan_ready"
STATUS_BLOCKED = "blocked"
RECOMMENDED_NEXT_PHASE = "MIRROR.10"
RECOMMENDED_FUTURE_UI_PHASE = "MIRROR.10 - Operator Panel Read-only UI Stub"

WARNING_LANGUAGE: tuple[str, ...] = (
    "Mirror Tunnel is advisory evidence, not an approval gate.",
    "A low derailment score does not prove correctness.",
    "A high derailment score means review the evidence, not automatically reject.",
    "Missing evidence should be shown plainly.",
)


def build_mirror_tunnel_operator_panel_plan(
    *,
    preview: dict[str, Any] | None = None,
    trace: dict[str, Any] | None = None,
    preview_path: str = "",
    trace_path: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build the MIRROR.9 operator panel contract from optional loaded inputs."""
    preview_data = preview if isinstance(preview, dict) else {}
    trace_data = trace if isinstance(trace, dict) else {}
    warnings = _top_warnings(preview_data, trace_data)
    visible = _visible_fields(preview_data, trace_data, warnings)
    return {
        "report_kind": REPORT_KIND,
        "created_at": str(created_at or _utc_now()),
        "status": PANEL_PLAN_READY,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "recommended_future_ui_phase": RECOMMENDED_FUTURE_UI_PHASE,
        "input_summary": {
            "preview": _preview_summary(preview_data, preview_path),
            "trace": _trace_summary(trace_data, trace_path),
        },
        "panel_purpose": _panel_purpose(),
        "panel_placement": _panel_placement(),
        "visible_fields": visible,
        "collapsed_debug_fields": _collapsed_debug_fields(preview_data, trace_data),
        "warning_language": list(WARNING_LANGUAGE),
        "non_blocking_policy": _non_blocking_policy(),
        "operator_actions": _operator_actions(),
        "forbidden_ui_actions": _forbidden_ui_actions(),
        "status_badge_rules": _status_badge_rules(),
        "evidence_display_rules": _evidence_display_rules(),
        "artifact_paths": {},
        "blockers": [],
        "boundaries": _boundaries(),
        "guardrails": _guardrails(),
    }


def write_mirror_tunnel_operator_panel_plan(
    *,
    repo_path: str | Path = ".",
    preview_path: str | Path | None = None,
    trace_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Read optional inputs and write the MIRROR.9 JSON/Markdown plan artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    created = str(created_at or _utc_now())
    try:
        preview_file = _resolve_optional_input_path(repo_root, preview_path)
        trace_file = _resolve_optional_input_path(repo_root, trace_path)
        preview = _load_json_object(preview_file) if preview_file else {}
        trace = _load_json_object(trace_file) if trace_file else {}
        _validate_preview(preview, preview_file)
        _validate_trace(trace, trace_file)
        out_dir = _resolve_output_dir(repo_root, output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = _blocked_report(
            created_at=created,
            preview_path=str(preview_path or ""),
            trace_path=str(trace_path or ""),
            reason=_reason_from_message(str(exc)),
            message=str(exc),
        )
        return _result(False, report, "", "")

    report = build_mirror_tunnel_operator_panel_plan(
        preview=preview,
        trace=trace,
        preview_path=str(preview_file or ""),
        trace_path=str(trace_file or ""),
        created_at=created,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    report["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(render_mirror_tunnel_operator_panel_plan_json(report), encoding="utf-8")
    md_path.write_text(render_mirror_tunnel_operator_panel_plan_markdown(report), encoding="utf-8")
    return _result(True, report, str(json_path), str(md_path))


def render_mirror_tunnel_operator_panel_plan_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_operator_panel_plan_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Operator Report Panel Plan",
        "",
        "## Summary",
        "",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        f"- **Future UI phase:** `{_md(report.get('recommended_future_ui_phase'))}`",
        "",
        "## Panel Purpose",
        "",
        _dict_block(report.get("panel_purpose")),
        "",
        "## Panel Placement",
        "",
        _dict_block(report.get("panel_placement")),
        "",
        "## Visible Fields",
        "",
        _dict_block(report.get("visible_fields")),
        "",
        "## Collapsed / Debug Fields",
        "",
        _table(report.get("collapsed_debug_fields"), ("field_id", "label", "source")),
        "",
        "## Warning Language",
        "",
        _bullet_list(report.get("warning_language")),
        "",
        "## Non-blocking Policy",
        "",
        _dict_block(report.get("non_blocking_policy")),
        "",
        "## Operator Actions",
        "",
        _table(report.get("operator_actions"), ("action_id", "label", "effect")),
        "",
        "## Forbidden UI Actions",
        "",
        _table(report.get("forbidden_ui_actions"), ("action_id", "reason")),
        "",
        "## Status Badge Rules",
        "",
        _table(report.get("status_badge_rules"), ("status", "color", "label", "note")),
        "",
        "## Evidence Display Rules",
        "",
        _table(report.get("evidence_display_rules"), ("rule_id", "rule")),
        "",
        "## Boundaries / Guardrails",
        "",
        _bullet_list(report.get("boundaries")),
        "",
    ]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def _panel_purpose() -> dict[str, str]:
    return {
        "summary": (
            "Show Mirror Tunnel trace and scoring evidence so an operator can review "
            "what evidence exists, what is missing, and where manual attention is useful."
        ),
        "authority_boundary": "Advisory evidence only; the panel is never an approval gate or trust authority.",
        "implementation_boundary": "MIRROR.9 defines a contract only and does not build the UI.",
    }


def _panel_placement() -> dict[str, Any]:
    return {
        "primary_recommendation": "Evidence Cards / Review area, after result and evidence summaries.",
        "fallback_first_placement": "Advanced/Debug drawer until the read-only UI stub is reviewed.",
        "avoid": "Primary submit area and any location that implies Mirror score controls execution.",
        "never_place_beside_apply_as_gate": True,
    }


def _visible_fields(preview: dict[str, Any], trace: dict[str, Any], top_warnings: list[str]) -> dict[str, Any]:
    coverage = _frame_coverage(preview, trace)
    score = preview.get("derailment_score_preview") if isinstance(preview.get("derailment_score_preview"), dict) else {}
    claim = preview.get("claim_vs_diff_preview") if isinstance(preview.get("claim_vs_diff_preview"), dict) else {}
    return {
        "trace_status": _trace_status(preview, trace),
        "frame_coverage": coverage,
        "derailment_verdict": str(score.get("verdict") or "not_available"),
        "overall_score": score.get("overall_derailment_score"),
        "claim_support_verdict": str(claim.get("overall_claim_support") or "not_available"),
        "missing_evidence_count": _missing_evidence_count(preview, trace, coverage),
        "top_warnings": top_warnings[:3],
        "recommended_next_action": str(preview.get("recommended_next_action") or "review_mirror_evidence_manually"),
    }


def _collapsed_debug_fields(preview: dict[str, Any], trace: dict[str, Any]) -> list[dict[str, Any]]:
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    score = preview.get("derailment_score_preview") if isinstance(preview.get("derailment_score_preview"), dict) else {}
    claim = preview.get("claim_vs_diff_preview") if isinstance(preview.get("claim_vs_diff_preview"), dict) else {}
    return [
        {"field_id": "full_frame_list", "label": "Full frame list", "source": "trace", "count": len(frames)},
        {"field_id": "dimension_scores", "label": "Dimension scores", "source": "preview", "available": isinstance(score.get("dimension_scores"), dict)},
        {"field_id": "claim_list", "label": "Claim list", "source": "preview", "available": bool(claim)},
        {"field_id": "mismatches", "label": "Mismatches", "source": "preview", "count": _count(claim.get("mismatches"))},
        {"field_id": "unsupported_claims", "label": "Unsupported claims", "source": "preview", "count": _count(claim.get("unsupported_claims"))},
        {"field_id": "artifact_paths", "label": "Artifact paths", "source": "trace_and_preview", "available": True},
        {"field_id": "raw_json_links", "label": "Raw JSON links", "source": "trace_and_preview", "available": True},
    ]


def _non_blocking_policy() -> dict[str, bool | str]:
    return {
        "is_approval_gate": False,
        "may_block_run": False,
        "may_block_patch": False,
        "may_hide_apply_button": False,
        "may_change_prompt_or_routing": False,
        "may_start_execution": False,
        "policy": "Mirror Tunnel evidence is advisory and must not change run, patch, prompt, route, or approval behavior.",
    }


def _operator_actions() -> list[dict[str, str]]:
    return [
        {"action_id": "open_trace_artifact", "label": "Open trace artifact", "effect": "Open the MIRROR.7 or MIRROR.1-compatible trace JSON/Markdown."},
        {"action_id": "open_scoring_preview", "label": "Open scoring preview", "effect": "Open the MIRROR.8 scoring preview JSON/Markdown."},
        {"action_id": "copy_mirror_review_summary", "label": "Copy Mirror review summary", "effect": "Copy advisory summary text for human review notes."},
        {"action_id": "rerun_preview_manually", "label": "Rerun preview manually", "effect": "Run MIRROR.8 again after collecting richer evidence."},
        {"action_id": "mark_reviewed_manually_future", "label": "Mark reviewed manually", "effect": "Future phase only; record human review without changing execution."},
    ]


def _forbidden_ui_actions() -> list[dict[str, str]]:
    return [
        {"action_id": "auto_block_run", "reason": "Mirror score must not block execution."},
        {"action_id": "auto_apply_patch", "reason": "Mirror evidence must never apply patches."},
        {"action_id": "auto_reject_patch", "reason": "High drift means review evidence, not automatic rejection."},
        {"action_id": "auto_trust_result", "reason": "Low drift does not prove correctness."},
        {"action_id": "auto_launch_replay_validation_benchmark", "reason": "Panel actions must not launch replay, validation, or benchmarks."},
        {"action_id": "auto_call_model", "reason": "Panel actions must not call models."},
        {"action_id": "hide_apply_button_based_on_mirror_score", "reason": "Mirror score must not change patch controls."},
        {"action_id": "change_prompt_or_routing_based_on_mirror_score", "reason": "Mirror score must not alter prompts or routes."},
    ]


def _status_badge_rules() -> list[dict[str, str]]:
    return [
        {"status": "insufficient_trace", "color": "gray", "label": "Needs more evidence", "note": "Show plainly as missing evidence, never as failure."},
        {"status": "preview_with_warnings", "color": "amber", "label": "Review recommended", "note": "Prompt operator to inspect warnings."},
        {"status": "preview_ready", "color": "blue", "label": "Evidence available", "note": "Evidence can be reviewed, not treated as approved."},
        {"status": "blocked", "color": "red", "label": "Trace blocked", "note": "Input artifact could not be trusted or read."},
    ]


def _evidence_display_rules() -> list[dict[str, str]]:
    return [
        {"rule_id": "show_missing_plainly", "rule": "Missing evidence should be shown plainly with count, frame type, and reason."},
        {"rule_id": "cap_excerpts", "rule": "Frame excerpts should stay capped in the UI and link to raw JSON for deeper inspection."},
        {"rule_id": "separate_summary_from_debug", "rule": "Show visible summary fields first; keep full frames, dimension scores, and raw JSON in collapsed debug."},
        {"rule_id": "do_not_infer_correctness", "rule": "Do not infer correctness, approval, or safety from low score or preview_ready status."},
        {"rule_id": "preserve_artifact_links", "rule": "Artifact paths and raw JSON links should be visible in debug without mutating the artifacts."},
    ]


def _preview_summary(preview: dict[str, Any], path: str) -> dict[str, Any]:
    return {
        "available": bool(preview),
        "path": str(path or ""),
        "report_kind": str(preview.get("report_kind", "")),
        "preview_id": str(preview.get("preview_id", "")),
        "status": str(preview.get("status", "not_available") if preview else "not_available"),
    }


def _trace_summary(trace: dict[str, Any], path: str) -> dict[str, Any]:
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    return {
        "available": bool(trace),
        "path": str(path or ""),
        "report_kind": str(trace.get("report_kind", "")),
        "trace_id": str(trace.get("trace_id", "")),
        "run_id": str(trace.get("run_id", "")),
        "status": str(trace.get("status", "not_available") if trace else "not_available"),
        "frame_count": len(frames),
    }


def _frame_coverage(preview: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    coverage = preview.get("frame_coverage") if isinstance(preview.get("frame_coverage"), dict) else {}
    if coverage:
        return dict(coverage)
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    return {
        "available_frame_count": len(frames),
        "available_frame_types": [str(frame.get("frame_type", "")) for frame in frames if isinstance(frame, dict)],
        "missing_evidence_count": _count(trace.get("missing_evidence")),
    }


def _trace_status(preview: dict[str, Any], trace: dict[str, Any]) -> str:
    if trace:
        return str(trace.get("status") or "not_available")
    live = preview.get("live_trace_input") if isinstance(preview.get("live_trace_input"), dict) else {}
    if live:
        return str(live.get("trace_status") or "not_available")
    return "not_available"


def _missing_evidence_count(preview: dict[str, Any], trace: dict[str, Any], coverage: dict[str, Any]) -> int:
    raw = coverage.get("missing_evidence_count")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return _count(preview.get("missing_evidence")) + _count(trace.get("missing_evidence"))


def _top_warnings(preview: dict[str, Any], trace: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if isinstance(preview.get("warnings"), list):
        warnings.extend(str(item) for item in preview["warnings"] if str(item))
    if _count(trace.get("missing_evidence")):
        warnings.append("trace has missing evidence frames")
    if not warnings:
        warnings.append("Mirror Tunnel is advisory evidence, not an approval gate.")
    return _dedupe(warnings)


def _validate_preview(preview: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    if str(preview.get("report_kind", "")) != "mirror_tunnel_live_trace_scoring_preview":
        raise ValueError("malformed_preview: preview must be a MIRROR.8 live trace scoring preview JSON")


def _validate_trace(trace: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    kind = str(trace.get("report_kind", ""))
    if kind not in {"mirror_tunnel_shadow_live_trace", "mirror_tunnel_trace_contract"}:
        raise ValueError("malformed_trace: trace must be a MIRROR.7 live trace or MIRROR.1-compatible trace JSON")
    if not isinstance(trace.get("frames"), list):
        raise ValueError("malformed_trace: trace must contain a frames list")


def _resolve_optional_input_path(repo_root: Path, raw: str | Path | None) -> Path | None:
    if raw is None or str(raw).strip() == "":
        return None
    raw_text = str(raw)
    raw_path = Path(raw_text).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"traversal_attempt: refusing traversal path: {raw_text}")
    if _is_forbidden_path(raw_path):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token path: {raw_text}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"forbidden_root: input path resolves outside repository: {raw_text}") from exc
    if _is_forbidden_path(resolved):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token path: {raw_text}")
    if not resolved.is_file():
        raise ValueError(f"unreadable_artifact: input artifact is missing or not a file: {raw_text}")
    return resolved


def _resolve_output_dir(repo_root: Path, raw: str | Path | None) -> Path:
    raw_text = str(raw or DEFAULT_OUTPUT_DIR)
    raw_path = Path(raw_text).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"traversal_attempt: refusing traversal output path: {raw_text}")
    if _is_forbidden_path(raw_path):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"forbidden_root: output path resolves outside repository: {raw_text}") from exc
    if _is_forbidden_path(resolved):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed_json: input JSON could not be parsed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("malformed_json: input JSON root must be an object")
    return data


def _blocked_report(*, created_at: str, preview_path: str, trace_path: str, reason: str, message: str) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "created_at": str(created_at or ""),
        "status": STATUS_BLOCKED,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "recommended_future_ui_phase": RECOMMENDED_FUTURE_UI_PHASE,
        "input_summary": {
            "preview": {"available": False, "path": str(preview_path or ""), "status": "blocked"},
            "trace": {"available": False, "path": str(trace_path or ""), "status": "blocked"},
        },
        "panel_purpose": _panel_purpose(),
        "panel_placement": _panel_placement(),
        "visible_fields": {},
        "collapsed_debug_fields": [],
        "warning_language": list(WARNING_LANGUAGE),
        "non_blocking_policy": _non_blocking_policy(),
        "operator_actions": _operator_actions(),
        "forbidden_ui_actions": _forbidden_ui_actions(),
        "status_badge_rules": _status_badge_rules(),
        "evidence_display_rules": _evidence_display_rules(),
        "artifact_paths": {},
        "blockers": [{"reason": reason, "message": message}],
        "boundaries": _boundaries(),
        "guardrails": _guardrails(),
    }


def _result(ok: bool, report: dict[str, Any], json_path: str, md_path: str) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "status": str(report.get("status", "")),
        "json_path": json_path,
        "md_path": md_path,
        "report": report,
        "markdown": render_mirror_tunnel_operator_panel_plan_markdown(report),
    }


def _boundaries() -> list[str]:
    return [
        "MIRROR.9 is report-only.",
        "MIRROR.9 defines an operator panel contract only.",
        "MIRROR.9 does not implement UI.",
        "MIRROR.9 does not change runtime behavior.",
        "MIRROR.9 does not make Mirror Tunnel an approval gate.",
        "MIRROR.9 does not call models.",
        "MIRROR.9 does not apply patches.",
        "MIRROR.9 does not run validation.",
        "MIRROR.9 does not run benchmarks.",
        "MIRROR.9 does not invoke MCP tools.",
        "MIRROR.9 does not launch workers.",
        "MIRROR.9 does not execute Dream actions.",
        "MIRROR.9 does not apply Replay janitor actions.",
        "MIRROR.9 does not use Docker or subprocess.",
        "MIRROR.9 does not contact network services.",
        "MIRROR.9 does not write to a database.",
        "MIRROR.9 does not change route behavior.",
        "MIRROR.9 does not change auth policy.",
        "MIRROR.9 does not block runs.",
        "MIRROR.9 writes operator panel plan artifacts only.",
    ]


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "ui_implemented": False,
        "runtime_behavior_changed": False,
        "approval_gate_added": False,
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
        "run_blocking_performed": False,
        "trace_or_preview_mutated": False,
        "writes_plan_artifacts_only": True,
    }


def _is_forbidden_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if ".agent" in parts and "private" in parts:
        return True
    if any(part == ".env" or part.startswith(".env.") for part in parts):
        return True
    if any("secret" in part or "credential" in part or "token" in part for part in parts):
        return True
    if name.endswith((".key", ".pem", ".token")):
        return True
    if name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
        return True
    return False


def _reason_from_message(message: str) -> str:
    for reason in (
        "traversal_attempt",
        "secret_or_env_path",
        "forbidden_root",
        "unreadable_artifact",
        "malformed_preview",
        "malformed_trace",
        "malformed_json",
    ):
        if str(message).startswith(reason):
            return reason
    return "blocked"


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "")
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dict_block(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "_None._"
    lines: list[str] = []
    for key in sorted(value):
        item = value[key]
        if isinstance(item, (dict, list)):
            item = json.dumps(item, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(item)}")
    return "\n".join(lines)


def _table(value: Any, keys: tuple[str, ...]) -> str:
    rows = value if isinstance(value, list) else []
    if not rows:
        return "_None._"
    lines = ["| " + " | ".join(keys) + " |", "| " + " | ".join("---" for _ in keys) + " |"]
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append("| " + " | ".join(_md(row.get(key)) for key in keys) + " |")
    return "\n".join(lines)


def _bullet_list(value: Any) -> str:
    items = value if isinstance(value, list) else []
    if not items:
        return "_None._"
    return "\n".join(f"- {_md(item)}" for item in items)


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
