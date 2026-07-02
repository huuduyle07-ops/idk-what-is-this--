"""MIRROR.12 - Mirror Tunnel Live Demo Readiness Check.

This module inspects artifacts from one manually controlled Mirror Tunnel demo:
an existing MIRROR.7 live trace, an existing MIRROR.8 preview, and the MIRROR.11
preview-id loading contract. It writes a report-only readiness verdict.

It does not enable tracing, start Flask, start a web run, call the live writer,
generate previews, score anything, mutate trace or preview artifacts, call
models, run validation or benchmarks, invoke MCP tools, launch workers, contact
network services, write to a database, change routes/auth, apply patches, or
block Submit/Apply behavior.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_live_demo_readiness"
JSON_NAME = "mirror_tunnel_live_demo_readiness.json"
MD_NAME = "mirror_tunnel_live_demo_readiness.md"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "live_demo_readiness"
PREVIEW_ROOT = Path(".agent") / "mirror_tunnel" / "live_trace_scoring_preview"
PREVIEW_JSON_NAME = "mirror_tunnel_live_trace_scoring_preview.json"
RECOMMENDED_NEXT_PHASE = "MIRROR.CLOSE3"

DEMO_READY = "demo_ready"
DEMO_READY_WITH_WARNINGS = "demo_ready_with_warnings"
STATUS_INSUFFICIENT_LIVE_TRACE = "insufficient_live_trace"
PREVIEW_MISSING_OR_MISMATCHED = "preview_missing_or_mismatched"
STATUS_BLOCKED = "blocked"

_LIVE_REPORT_KINDS = {"mirror_tunnel_shadow_live_trace", "mirror_tunnel_trace_contract"}
_PREVIEW_STATUSES = {"preview_ready", "preview_with_warnings", "insufficient_trace", "blocked"}
_MIRROR11_PREVIEW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

_INTENT_FRAME_TYPES = {"user_intent", "goal_brief", "control_prompt"}
_ACTION_FRAME_TYPES = {"worker_assignment", "worker_reply", "patch_or_diff"}
_OUTCOME_FRAME_TYPES = {"validation_evidence", "benchmark_evidence", "replay_evidence", "final_answer"}

MANUAL_DEMO_INSTRUCTIONS: tuple[str, ...] = (
    "Set MIRROR_TUNNEL_SHADOW_TRACE_ENABLED=true manually.",
    "Run one controlled existing web run.",
    "Confirm .agent/mirror_tunnel/live_traces/<run_id>/mirror_tunnel_trace_contract.json exists.",
    "Run MIRROR.8 preview CLI manually against that trace.",
    "Load the preview_id in the MIRROR.11 panel.",
    "Run MIRROR.12 readiness checker on the live trace and preview.",
    "Turn MIRROR_TUNNEL_SHADOW_TRACE_ENABLED=false afterward.",
)

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.12 is report-only.",
    "MIRROR.12 is artifact-inspection only.",
    "MIRROR.12 documents readiness for one manually controlled demo run.",
    "MIRROR.12 does not enable MIRROR_TUNNEL_SHADOW_TRACE_ENABLED.",
    "MIRROR.12 does not start Flask.",
    "MIRROR.12 does not start a web run.",
    "MIRROR.12 does not call run_agent_web.",
    "MIRROR.12 does not call the MIRROR.7 writer.",
    "MIRROR.12 does not call the MIRROR.8 preview builder.",
    "MIRROR.12 does not call MIRROR.2 or MIRROR.3 directly.",
    "MIRROR.12 does not mutate live traces.",
    "MIRROR.12 does not mutate previews.",
    "MIRROR.12 does not score anything.",
    "MIRROR.12 does not block Apply or Submit.",
    "MIRROR.12 does not change UI behavior.",
    "MIRROR.12 preserves advisory and non-blocking policy.",
)


def write_mirror_tunnel_live_demo_readiness(
    *,
    repo_path: str | Path = ".",
    live_trace_path: str | Path,
    preview_path: str | Path,
    preview_id: str | None = None,
    output_dir: str | Path | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Inspect existing demo artifacts and write JSON/Markdown readiness reports."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    created = str(created_at or _utc_now())
    report = build_mirror_tunnel_live_demo_readiness(
        repo_path=repo_root,
        live_trace_path=live_trace_path,
        preview_path=preview_path,
        preview_id=preview_id,
        created_at=created,
    )

    out_dir_result = _resolve_output_dir(repo_root, output_dir)
    if not out_dir_result["ok"]:
        report["status"] = STATUS_BLOCKED
        report["blockers"].append(
            {
                "reason": out_dir_result["reason"],
                "message": out_dir_result["message"],
            }
        )
        return _result(False, report, "", "")

    out_dir = Path(str(out_dir_result["path"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    report["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(render_mirror_tunnel_live_demo_readiness_json(report), encoding="utf-8")
    md_path.write_text(render_mirror_tunnel_live_demo_readiness_markdown(report), encoding="utf-8")
    return _result(report["status"] in {DEMO_READY, DEMO_READY_WITH_WARNINGS}, report, str(json_path), str(md_path))


def build_mirror_tunnel_live_demo_readiness(
    *,
    repo_path: str | Path = ".",
    live_trace_path: str | Path,
    preview_path: str | Path,
    preview_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a readiness report from already-written live trace and preview paths."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    created = str(created_at or _utc_now())
    blockers: list[dict[str, str]] = []

    live_res = _resolve_input_path(repo_root, live_trace_path, kind="live_trace")
    preview_res = _resolve_input_path(repo_root, preview_path, kind="preview")
    blockers.extend(live_res["blockers"])
    blockers.extend(preview_res["blockers"])

    live_trace: dict[str, Any] = {}
    preview: dict[str, Any] = {}
    if not blockers and live_res["exists"]:
        live_loaded = _load_json_object(Path(str(live_res["path"])), label="live_trace")
        if live_loaded["ok"]:
            live_trace = live_loaded["data"]
        else:
            blockers.append(live_loaded["blocker"])
    if not blockers and preview_res["exists"]:
        preview_loaded = _load_json_object(Path(str(preview_res["path"])), label="preview")
        if preview_loaded["ok"]:
            preview = preview_loaded["data"]
        else:
            blockers.append(preview_loaded["blocker"])

    live_check = _live_trace_check(live_trace, live_res)
    preview_check = _preview_check(preview, preview_res, live_check)
    loader = _ui_loader_compatibility(repo_root, preview, preview_res, preview_id)
    coverage = _frame_coverage(live_trace, preview)
    missing = _missing_evidence(live_check, preview_check, loader, coverage, live_trace, preview)
    warnings = _warnings(live_check, preview_check, loader, coverage, preview)
    status = _readiness_status(
        blockers=blockers,
        live_check=live_check,
        preview_check=preview_check,
        loader=loader,
        coverage=coverage,
        warnings=warnings,
    )

    trace_id = str(live_trace.get("trace_id") or preview.get("trace_id") or "")
    run_id = str(live_trace.get("run_id") or live_trace.get("source_run_id") or preview.get("run_id") or "")
    effective_preview_id = str(preview_id or preview.get("preview_id") or "")
    return {
        "report_kind": REPORT_KIND,
        "created_at": created,
        "status": status,
        "trace_id": trace_id,
        "run_id": run_id,
        "preview_id": effective_preview_id,
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "summary": {
            "verdict": status,
            "live_trace_ready": bool(live_check.get("schema_compatible") and coverage.get("has_useful_frame_coverage")),
            "preview_ready": bool(preview_check.get("exists") and preview_check.get("trace_id_matches") is not False),
            "ui_loader_compatible": bool(loader.get("loader_compatible")),
            "advisory_non_blocking_policy_preserved": True,
        },
        "demo_inputs": {
            "live_trace_path": str(live_trace_path or ""),
            "preview_path": str(preview_path or ""),
            "preview_id": effective_preview_id,
        },
        "live_trace_check": live_check,
        "preview_check": preview_check,
        "ui_loader_compatibility": loader,
        "frame_coverage": coverage,
        "missing_evidence": missing,
        "warnings": warnings,
        "blockers": blockers,
        "manual_demo_instructions": list(MANUAL_DEMO_INSTRUCTIONS),
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "artifact_paths": {},
    }


def render_mirror_tunnel_live_demo_readiness_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_live_demo_readiness_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Live Demo Readiness Check",
        "",
        "## Summary",
        "",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Run id:** `{_md(report.get('run_id'))}`",
        f"- **Preview id:** `{_md(report.get('preview_id'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Demo Inputs",
        "",
        _dict_block(report.get("demo_inputs")),
        "",
        "## Live Trace Check",
        "",
        _dict_block(report.get("live_trace_check")),
        "",
        "## Preview Check",
        "",
        _dict_block(report.get("preview_check")),
        "",
        "## UI Loader Compatibility",
        "",
        _dict_block(report.get("ui_loader_compatibility")),
        "",
        "## Frame Coverage",
        "",
        _dict_block(report.get("frame_coverage")),
        "",
        "## Missing Evidence",
        "",
        _table(report.get("missing_evidence"), ("source", "reason", "detail")),
        "",
        "## Warnings",
        "",
        _bullet_list(report.get("warnings")),
        "",
        "## Readiness Verdict",
        "",
        f"`{_md(report.get('status'))}`",
        "",
        "## Manual Demo Instructions",
        "",
        _numbered_list(report.get("manual_demo_instructions")),
        "",
        "## Boundaries / Guardrails",
        "",
        _bullet_list(report.get("boundaries")),
        "",
    ]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.extend(["", "## Recommended Next Phase", "", f"`{_md(report.get('recommended_next_phase'))}`", ""])
    return "\n".join(lines)


def _live_trace_check(trace: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    path = Path(str(resolved.get("path") or "")) if resolved.get("path") else None
    kind = str(trace.get("report_kind", ""))
    schema_compatible = bool(trace) and kind in _LIVE_REPORT_KINDS and isinstance(frames, list) and all(isinstance(frame, dict) for frame in frames)
    if not schema_compatible and trace and "trace_id" in trace and isinstance(frames, list):
        schema_compatible = all(isinstance(frame, dict) for frame in frames)
    from_live_dir = _path_has_parts(path, (".agent", "mirror_tunnel", "live_traces")) if path else False
    marked_live = kind == "mirror_tunnel_shadow_live_trace" or bool(trace.get("enabled")) or bool(_dict(trace.get("guardrails")).get("shadow_only"))
    useful_frames = _available_frames(frames)
    useful_types = [str(frame.get("frame_type", "")) for frame in useful_frames]
    return {
        "exists": bool(resolved.get("exists")),
        "path": str(resolved.get("path") or ""),
        "report_kind": kind,
        "status": str(trace.get("status", "not_available") if trace else "not_available"),
        "trace_id": str(trace.get("trace_id", "")),
        "run_id": str(trace.get("run_id") or trace.get("source_run_id") or ""),
        "schema_compatible": bool(schema_compatible),
        "from_live_traces_directory": from_live_dir,
        "explicitly_marked_live_or_shadow": marked_live,
        "origin_acceptable": bool(from_live_dir or marked_live),
        "frame_count": len(frames),
        "useful_frame_count": len(useful_frames),
        "useful_frame_types": useful_types,
        "missing_evidence_count": _count(trace.get("missing_evidence")) + _count(trace.get("missing_frames")),
        "blocked_reason_count": _count(trace.get("blocked_reasons")) + _count(trace.get("blockers")),
    }


def _preview_check(preview: dict[str, Any], resolved: dict[str, Any], live_check: dict[str, Any]) -> dict[str, Any]:
    status = str(preview.get("status", "") if preview else "")
    trace_id = str(preview.get("trace_id", ""))
    live_trace_id = str(live_check.get("trace_id", ""))
    trace_id_matches: bool | None
    if trace_id and live_trace_id:
        trace_id_matches = trace_id == live_trace_id
    else:
        trace_id_matches = None
    live_input = _dict(preview.get("live_trace_input"))
    guardrails = _dict(preview.get("guardrails"))
    return {
        "exists": bool(resolved.get("exists")),
        "path": str(resolved.get("path") or ""),
        "report_kind": str(preview.get("report_kind", "")),
        "preview_id": str(preview.get("preview_id", "")),
        "status": status or "not_available",
        "status_recorded": bool(status),
        "status_known": status in _PREVIEW_STATUSES if status else False,
        "trace_id": trace_id,
        "trace_id_matches": trace_id_matches,
        "generated_separately_from_live_trace_directory": not _path_has_parts(Path(str(resolved.get("path") or "")), (".agent", "mirror_tunnel", "live_traces")),
        "live_trace_artifact_mutated": bool(live_input.get("live_trace_artifact_mutated") or guardrails.get("live_trace_mutated")),
        "preview_mutated_by_readiness_check": False,
        "missing_evidence_count": _count(preview.get("missing_evidence")),
        "warning_count": _count(preview.get("warnings")),
    }


def _ui_loader_compatibility(
    repo_root: Path,
    preview: dict[str, Any],
    resolved: dict[str, Any],
    requested_preview_id: str | None,
) -> dict[str, Any]:
    effective_id = str(requested_preview_id or preview.get("preview_id") or "").strip()
    safe = _is_safe_preview_id(effective_id)
    expected = (repo_root / PREVIEW_ROOT / effective_id / PREVIEW_JSON_NAME).resolve() if safe else None
    actual = Path(str(resolved.get("path") or "")).resolve() if resolved.get("path") else None
    expected_match = bool(expected and actual and expected == actual)
    fields = _panel_display_fields(preview)
    missing_fields = [key for key, available in fields.items() if not available]
    return {
        "preview_id": effective_id,
        "preview_id_safe_for_mirror11": safe,
        "expected_loader_path": str(expected or ""),
        "actual_preview_path": str(actual or ""),
        "loader_path_matches": expected_match,
        "loader_compatible": bool(safe and expected_match and resolved.get("exists") and str(preview.get("report_kind", "")) == "mirror_tunnel_live_trace_scoring_preview"),
        "panel_display_fields": fields,
        "missing_display_fields": missing_fields,
        "display_fields_safely_missing": True,
        "advisory_non_blocking_policy_preserved": True,
    }


def _panel_display_fields(preview: dict[str, Any]) -> dict[str, bool]:
    live_input = _dict(preview.get("live_trace_input"))
    derailment = _dict(preview.get("derailment_score_preview"))
    claim = _dict(preview.get("claim_vs_diff_preview"))
    coverage = _dict(preview.get("frame_coverage"))
    return {
        "status": bool(preview.get("status")),
        "trace_status": bool(live_input.get("trace_status") or preview.get("status")),
        "trace_id": bool(preview.get("trace_id")),
        "run_id": bool(preview.get("run_id")),
        "derailment_verdict": bool(derailment.get("verdict")),
        "derailment_score": derailment.get("overall_derailment_score") is not None,
        "claim_support_verdict": bool(claim.get("overall_claim_support")),
        "missing_evidence_count": isinstance(preview.get("missing_evidence"), list) or coverage.get("missing_evidence_count") is not None,
        "recommended_next_action": bool(preview.get("recommended_next_action")),
    }


def _frame_coverage(trace: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    useful_frames = _available_frames(frames)
    useful_types = {str(frame.get("frame_type", "")) for frame in useful_frames}
    has_useful = (
        len(useful_frames) >= 3
        and bool(useful_types & _INTENT_FRAME_TYPES)
        and bool(useful_types & _ACTION_FRAME_TYPES)
        and bool(useful_types & _OUTCOME_FRAME_TYPES)
    )
    preview_coverage = _dict(preview.get("frame_coverage"))
    return {
        "live_frame_count": len(frames),
        "useful_frame_count": len(useful_frames),
        "useful_frame_types": sorted(item for item in useful_types if item),
        "has_useful_frame_coverage": has_useful,
        "preview_available_frame_count": preview_coverage.get("available_frame_count"),
        "preview_missing_evidence_count": preview_coverage.get("missing_evidence_count"),
    }


def _missing_evidence(
    live_check: dict[str, Any],
    preview_check: dict[str, Any],
    loader: dict[str, Any],
    coverage: dict[str, Any],
    live_trace: dict[str, Any],
    preview: dict[str, Any],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if not live_check.get("exists"):
        entries.append(_evidence("live_trace", "missing_live_trace", "live trace artifact does not exist"))
    if live_check.get("exists") and not live_check.get("schema_compatible"):
        entries.append(_evidence("live_trace", "schema_incompatible", "live trace is not MIRROR.1-compatible"))
    if live_check.get("exists") and not coverage.get("has_useful_frame_coverage"):
        entries.append(_evidence("live_trace", "weak_frame_coverage", "live trace lacks useful end-to-end frame coverage"))
    if not preview_check.get("exists"):
        entries.append(_evidence("preview", "missing_preview", "preview artifact does not exist"))
    if preview_check.get("trace_id_matches") is False:
        entries.append(_evidence("preview", "trace_id_mismatch", "preview trace_id does not match live trace trace_id"))
    if not loader.get("loader_compatible"):
        entries.append(_evidence("ui_loader", "loader_incompatible", "preview cannot be loaded through MIRROR.11 preview_id rules"))
    for item in _missing_items("live_trace", live_trace.get("missing_evidence")):
        entries.append(item)
    for item in _missing_items("preview", preview.get("missing_evidence")):
        entries.append(item)
    return _dedupe_evidence(entries)


def _warnings(
    live_check: dict[str, Any],
    preview_check: dict[str, Any],
    loader: dict[str, Any],
    coverage: dict[str, Any],
    preview: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if live_check.get("exists") and not live_check.get("origin_acceptable"):
        warnings.append("live trace path is not in live_traces and artifact is not explicitly marked live/shadow")
    if live_check.get("blocked_reason_count"):
        warnings.append("live trace reports blocked reasons")
    if live_check.get("missing_evidence_count"):
        warnings.append("live trace has missing evidence")
    if live_check.get("exists") and not coverage.get("has_useful_frame_coverage"):
        warnings.append("live trace has weak frame coverage")
    status = str(preview_check.get("status") or "")
    if preview_check.get("exists") and not preview_check.get("status_recorded"):
        warnings.append("preview status is missing")
    if preview_check.get("exists") and preview_check.get("status_recorded") and not preview_check.get("status_known"):
        warnings.append(f"preview status is not recognized: {status}")
    if status == "insufficient_trace":
        warnings.append("preview status is insufficient_trace")
    elif status == "preview_with_warnings":
        warnings.append("preview status is preview_with_warnings")
    if preview_check.get("live_trace_artifact_mutated"):
        warnings.append("preview reports live trace mutation")
    if loader.get("missing_display_fields"):
        warnings.append("panel display fields are safely missing: " + ", ".join(loader["missing_display_fields"]))
    for item in preview.get("warnings", []) if isinstance(preview.get("warnings"), list) else []:
        text = str(item or "")
        if text:
            warnings.append(text)
    return _dedupe_strings(warnings)


def _readiness_status(
    *,
    blockers: list[dict[str, str]],
    live_check: dict[str, Any],
    preview_check: dict[str, Any],
    loader: dict[str, Any],
    coverage: dict[str, Any],
    warnings: list[str],
) -> str:
    if blockers:
        return STATUS_BLOCKED
    if preview_check.get("status") == "blocked":
        return STATUS_BLOCKED
    if not live_check.get("exists") or not live_check.get("schema_compatible") or not live_check.get("origin_acceptable"):
        return STATUS_INSUFFICIENT_LIVE_TRACE
    if not preview_check.get("exists") or str(preview_check.get("report_kind", "")) != "mirror_tunnel_live_trace_scoring_preview":
        return PREVIEW_MISSING_OR_MISMATCHED
    if preview_check.get("trace_id_matches") is False:
        return PREVIEW_MISSING_OR_MISMATCHED
    if not coverage.get("has_useful_frame_coverage") or preview_check.get("status") == "insufficient_trace":
        return STATUS_INSUFFICIENT_LIVE_TRACE
    if warnings or not loader.get("loader_compatible"):
        return DEMO_READY_WITH_WARNINGS
    return DEMO_READY


def _resolve_input_path(repo_root: Path, raw: str | Path, *, kind: str) -> dict[str, Any]:
    raw_text = str(raw or "").strip()
    blockers: list[dict[str, str]] = []
    if not raw_text:
        blockers.append({"reason": "empty_artifact_path", "message": f"{kind} path is required"})
        return {"path": "", "exists": False, "blockers": blockers}
    raw_path = Path(raw_text).expanduser()
    if _has_traversal(raw_text) or any(part == ".." for part in raw_path.parts):
        blockers.append({"reason": "traversal_attempt", "message": f"refusing traversal path: {raw_text}"})
        return {"path": "", "exists": False, "blockers": blockers}
    if _is_forbidden_path(raw_path):
        blockers.append({"reason": "secret_or_env_path", "message": f"refusing secret/env/key/token path: {raw_text}"})
        return {"path": "", "exists": False, "blockers": blockers}
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        blockers.append({"reason": "forbidden_root", "message": f"{kind} path resolves outside repository: {raw_text}"})
        return {"path": str(resolved), "exists": False, "blockers": blockers}
    if _is_forbidden_path(resolved):
        blockers.append({"reason": "secret_or_env_path", "message": f"refusing secret/env/key/token path: {raw_text}"})
        return {"path": str(resolved), "exists": False, "blockers": blockers}
    if not _path_has_parts(resolved, (".agent", "mirror_tunnel")):
        blockers.append({"reason": "artifact_outside_allowed_mirror_dirs", "message": f"{kind} path must be under .agent/mirror_tunnel"})
        return {"path": str(resolved), "exists": resolved.is_file(), "blockers": blockers}
    if kind == "preview" and _path_has_parts(resolved, (".agent", "mirror_tunnel", "live_traces")):
        blockers.append({"reason": "preview_inside_live_traces", "message": "preview artifact must not be inside live_traces"})
        return {"path": str(resolved), "exists": resolved.is_file(), "blockers": blockers}
    if kind == "preview" and not _path_has_parts(resolved, (".agent", "mirror_tunnel", "live_trace_scoring_preview")):
        blockers.append({"reason": "artifact_outside_allowed_mirror_dirs", "message": "preview path must be under live_trace_scoring_preview"})
        return {"path": str(resolved), "exists": resolved.is_file(), "blockers": blockers}
    return {"path": str(resolved), "exists": resolved.is_file(), "blockers": blockers}


def _resolve_output_dir(repo_root: Path, raw: str | Path | None) -> dict[str, Any]:
    raw_path = Path(str(raw or DEFAULT_OUTPUT_DIR)).expanduser()
    if _has_traversal(str(raw_path)) or any(part == ".." for part in raw_path.parts):
        return {"ok": False, "reason": "traversal_attempt", "message": "refusing traversal output path", "path": ""}
    if _is_forbidden_path(raw_path):
        return {"ok": False, "reason": "secret_or_env_path", "message": "refusing secret/env/key/token output path", "path": ""}
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return {"ok": False, "reason": "forbidden_root", "message": "output path resolves outside repository", "path": str(resolved)}
    if _is_forbidden_path(resolved):
        return {"ok": False, "reason": "secret_or_env_path", "message": "refusing secret/env/key/token output path", "path": str(resolved)}
    return {"ok": True, "path": str(resolved)}


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "data": {},
            "blocker": {"reason": f"malformed_{label}_json", "message": f"{label} JSON could not be parsed: {exc}"},
        }
    except OSError as exc:
        return {
            "ok": False,
            "data": {},
            "blocker": {"reason": "unreadable_artifact", "message": f"{label} artifact could not be read: {exc}"},
        }
    if not isinstance(data, dict):
        return {
            "ok": False,
            "data": {},
            "blocker": {"reason": f"malformed_{label}_json", "message": f"{label} JSON root must be an object"},
        }
    return {"ok": True, "data": data}


def _is_safe_preview_id(value: str) -> bool:
    preview_id = str(value or "").strip()
    if not preview_id or preview_id in {".", ".."}:
        return False
    if ".." in preview_id or "/" in preview_id or "\\" in preview_id or "?" in preview_id:
        return False
    return bool(_MIRROR11_PREVIEW_ID_RE.fullmatch(preview_id))


def _available_frames(frames: list[Any]) -> list[dict[str, Any]]:
    return [
        frame
        for frame in frames
        if isinstance(frame, dict)
        and str(frame.get("availability") or "available") == "available"
        and (str(frame.get("frame_type", "")).strip() or str(frame.get("excerpt", "")).strip())
    ]


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "artifact_inspection_only": True,
        "manual_demo_executed_by_checker": False,
        "env_flag_enabled_by_checker": False,
        "flask_started": False,
        "web_run_started": False,
        "run_agent_web_called": False,
        "mirror7_writer_called": False,
        "mirror8_preview_builder_called": False,
        "mirror2_or_mirror3_called": False,
        "live_trace_mutated": False,
        "preview_mutated": False,
        "preview_generated": False,
        "scoring_performed": False,
        "runtime_scoring_performed": False,
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
        "execution_blocking_performed": False,
        "apply_submit_blocking_performed": False,
    }


def _result(ok: bool, report: dict[str, Any], json_path: str, md_path: str) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "status": str(report.get("status", "")),
        "json_path": json_path,
        "md_path": md_path,
        "report": report,
        "markdown": render_mirror_tunnel_live_demo_readiness_markdown(report),
    }


def _missing_items(source: str, value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        frame_type = str(item.get("frame_type", item.get("category", "")))
        reason = str(item.get("reason", item.get("evidence_status", "missing")))
        items.append(_evidence(source, reason or "missing", frame_type))
    return items


def _evidence(source: str, reason: str, detail: str) -> dict[str, str]:
    return {"source": str(source), "reason": str(reason), "detail": str(detail)}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _path_has_parts(path: Path | None, parts: tuple[str, ...]) -> bool:
    if path is None:
        return False
    actual = [part.lower() for part in path.parts]
    target = [part.lower() for part in parts]
    if not target:
        return False
    for index in range(0, len(actual) - len(target) + 1):
        if actual[index : index + len(target)] == target:
            return True
    return False


def _has_traversal(path: str) -> bool:
    return any(part == ".." for part in str(path).replace("\\", "/").split("/") if part)


def _is_forbidden_path(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if ".git" in parts:
        return True
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


def _dedupe_strings(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "")
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dedupe_evidence(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (str(item.get("source", "")), str(item.get("reason", "")), str(item.get("detail", "")))
        if key not in seen:
            seen.add(key)
            out.append(item)
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


def _numbered_list(value: Any) -> str:
    items = value if isinstance(value, list) else []
    if not items:
        return "_None._"
    return "\n".join(f"{index}. {_md(item)}" for index, item in enumerate(items, start=1))


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
