"""MIRROR.8 - Live Trace Scoring Preview.

This module is a post-run, report-only preview for MIRROR.7 live traces. It
reads an existing live trace or MIRROR.1-compatible trace JSON, derives MIRROR.2
and MIRROR.3 reports through pure core builders, reuses MIRROR.6 aggregation,
and writes only separate preview artifacts.

It does not run during the web run, call models, change prompts, apply patches,
run validation or benchmarks, invoke tools, launch workers, execute Dream or
Replay actions, use Docker/subprocess, contact the network, write to a database,
change route/auth behavior, block runs, score at runtime, or mutate the live
trace artifact.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.mirror_tunnel_claim_diff_check import build_mirror_tunnel_claim_diff_check
from core.mirror_tunnel_derailment_score import build_mirror_tunnel_derailment_score
from core.mirror_tunnel_manual_review_pipeline import build_mirror_tunnel_manual_review


REPORT_KIND = "mirror_tunnel_live_trace_scoring_preview"
JSON_NAME = "mirror_tunnel_live_trace_scoring_preview.json"
MD_NAME = "mirror_tunnel_live_trace_scoring_preview.md"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "live_trace_scoring_preview"
RECOMMENDED_NEXT_PHASE = "MIRROR.9"

PREVIEW_READY = "preview_ready"
PREVIEW_WITH_WARNINGS = "preview_with_warnings"
STATUS_INSUFFICIENT_TRACE = "insufficient_trace"
STATUS_BLOCKED = "blocked"

RECOMMENDED_NEXT_ACTIONS: dict[str, str] = {
    PREVIEW_READY: "review_live_trace_evidence",
    PREVIEW_WITH_WARNINGS: "improve_live_trace_frame_capture",
    STATUS_INSUFFICIENT_TRACE: "collect_richer_live_trace_frames",
    STATUS_BLOCKED: "fix_trace_artifact_or_path",
}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.8 is report-only.",
    "MIRROR.8 is post-run only.",
    "MIRROR.8 reads an existing MIRROR.7 live trace or MIRROR.1-compatible trace JSON.",
    "MIRROR.8 calls MIRROR.2 and MIRROR.3 pure core builders directly.",
    "MIRROR.8 reuses MIRROR.6-style aggregation through the pure core builder.",
    "MIRROR.8 does not call CLI scripts.",
    "MIRROR.8 does not run during the original web run.",
    "MIRROR.8 does not call the MIRROR.7 live writer.",
    "MIRROR.8 does not mutate live trace artifacts.",
    "MIRROR.8 writes preview artifacts only.",
    "MIRROR.8 does not call models.",
    "MIRROR.8 does not apply patches.",
    "MIRROR.8 does not run validation.",
    "MIRROR.8 does not run benchmarks.",
    "MIRROR.8 does not invoke MCP tools.",
    "MIRROR.8 does not launch workers.",
    "MIRROR.8 does not execute Dream actions.",
    "MIRROR.8 does not apply Replay janitor actions.",
    "MIRROR.8 does not use Docker or subprocess.",
    "MIRROR.8 does not contact network services.",
    "MIRROR.8 does not write to a database.",
    "MIRROR.8 does not change route behavior.",
    "MIRROR.8 does not change auth policy.",
    "MIRROR.8 does not block runs.",
    "MIRROR.8 does not score during runtime.",
)

_LIVE_REPORT_KINDS = {"mirror_tunnel_shadow_live_trace"}
_MIRROR1_REPORT_KINDS = {"mirror_tunnel_trace_contract"}


def build_mirror_tunnel_live_trace_scoring_preview(
    *,
    trace: dict[str, Any] | None = None,
    trace_path: str = "",
    preview_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a post-run scoring preview from an already-loaded trace dict."""
    trace_data = trace if isinstance(trace, dict) else {}
    created = str(created_at or _utc_now())
    preview = preview_id or _default_preview_id(trace_data, trace_path, created)
    compatibility, compatibility_errors = _trace_compatibility(trace_data)
    if compatibility_errors:
        return _blocked_report(
            preview_id=preview,
            created_at=created,
            trace_path=trace_path,
            reason="malformed_trace",
            message="; ".join(compatibility_errors),
        )

    score = build_mirror_tunnel_derailment_score(
        trace=trace_data,
        trace_path=trace_path,
        score_id=f"{preview}-mirror2",
        created_at=created,
    )
    claim = build_mirror_tunnel_claim_diff_check(
        trace=trace_data,
        score=score,
        trace_path=trace_path,
        score_path="",
        check_id=f"{preview}-mirror3",
        created_at=created,
    )
    review = build_mirror_tunnel_manual_review(
        trace=trace_data,
        score=score,
        claim_diff=claim,
        trace_path=trace_path,
        review_id=f"{preview}-combined",
        created_at=created,
    )

    warnings = _warnings(trace_data, score, claim, review)
    status = _status(score, claim, review, warnings)
    missing = _combined_missing_evidence(trace_data, score, claim, review)
    frame_coverage = _frame_coverage(trace_data, score, review)
    return {
        "report_kind": REPORT_KIND,
        "preview_id": preview,
        "created_at": created,
        "status": status,
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS[status],
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "trace_id": str(trace_data.get("trace_id", "")),
        "run_id": str(trace_data.get("run_id") or trace_data.get("source_run_id") or ""),
        "live_trace_input": {
            "trace_path": str(trace_path or ""),
            "trace_report_kind": str(trace_data.get("report_kind", "")),
            "trace_status": str(trace_data.get("status", "")),
            "trace_compatibility": compatibility,
            "live_trace_artifact_mutated": False,
        },
        "frame_coverage": frame_coverage,
        "derailment_score_preview": _derailment_summary(score),
        "claim_vs_diff_preview": _claim_summary(claim),
        "combined_review_verdict": _review_summary(review),
        "missing_evidence": missing,
        "warnings": warnings,
        "blockers": [],
        "artifact_paths": {},
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def write_mirror_tunnel_live_trace_scoring_preview(
    *,
    repo_path: str | Path = ".",
    trace_path: str,
    preview_id: str | None = None,
    created_at: str = "",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Read a trace JSON and write MIRROR.8 preview JSON/Markdown artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    created = str(created_at or _utc_now())
    try:
        trace_file = _resolve_input_path(repo_root, trace_path)
        trace = _load_json_object(trace_file)
        report = build_mirror_tunnel_live_trace_scoring_preview(
            trace=trace,
            trace_path=str(trace_file),
            preview_id=preview_id,
            created_at=created,
        )
        if report["status"] == STATUS_BLOCKED:
            return _result(False, report, "", "")
        out_dir = _resolve_output_dir(repo_root, output_dir, str(report["preview_id"]))
        _ensure_not_live_trace_input_dir(out_dir, trace_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = _blocked_report(
            preview_id=preview_id,
            created_at=created,
            trace_path=str(trace_path or ""),
            reason=_reason_from_message(str(exc)),
            message=str(exc),
        )
        return _result(False, report, "", "")

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    report["artifact_paths"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    json_path.write_text(render_mirror_tunnel_live_trace_scoring_preview_json(report), encoding="utf-8")
    md_path.write_text(render_mirror_tunnel_live_trace_scoring_preview_markdown(report), encoding="utf-8")
    return _result(True, report, str(json_path), str(md_path))


def render_mirror_tunnel_live_trace_scoring_preview_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_live_trace_scoring_preview_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Live Trace Scoring Preview",
        "",
        "## Summary",
        "",
        f"- **Preview id:** `{_md(report.get('preview_id'))}`",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Run id:** `{_md(report.get('run_id'))}`",
        f"- **Recommended next action:** `{_md(report.get('recommended_next_action'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Live Trace Input",
        "",
        _dict_block(report.get("live_trace_input")),
        "",
        "## Frame Coverage",
        "",
        _dict_block(report.get("frame_coverage")),
        "",
        "## Derailment Score Preview",
        "",
        _dict_block(report.get("derailment_score_preview")),
        "",
        "## Claim-vs-Diff Preview",
        "",
        _dict_block(report.get("claim_vs_diff_preview")),
        "",
        "## Combined Review Verdict",
        "",
        _dict_block(report.get("combined_review_verdict")),
        "",
        "## Missing Evidence",
        "",
        _bullet_list(_missing_lines(report.get("missing_evidence"))),
        "",
        "## Warnings",
        "",
        _bullet_list([_md(item) for item in report.get("warnings", [])]),
        "",
        "## Recommended Next Action",
        "",
        f"`{_md(report.get('recommended_next_action'))}`",
        "",
        "## Boundaries / Guardrails",
        "",
        _bullet_list([_md(item) for item in report.get("boundaries", [])]),
        "",
    ]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def _status(
    score: dict[str, Any],
    claim: dict[str, Any],
    review: dict[str, Any],
    warnings: list[str],
) -> str:
    if str(score.get("verdict", "")) == "insufficient_trace":
        return STATUS_INSUFFICIENT_TRACE
    if str(claim.get("overall_claim_support", "")) == "insufficient_evidence":
        return STATUS_INSUFFICIENT_TRACE
    if str(review.get("combined_verdict", "")) == "insufficient_trace":
        return STATUS_INSUFFICIENT_TRACE
    if warnings:
        return PREVIEW_WITH_WARNINGS
    return PREVIEW_READY


def _trace_compatibility(trace: dict[str, Any]) -> tuple[str, list[str]]:
    if not isinstance(trace, dict) or not trace:
        return "", ["trace JSON root must be an object"]
    frames = trace.get("frames")
    if not isinstance(frames, list):
        return "", ["trace must contain a frames list"]
    if any(not isinstance(frame, dict) for frame in frames):
        return "", ["trace frames must be objects"]
    kind = str(trace.get("report_kind", ""))
    if kind in _LIVE_REPORT_KINDS:
        return "mirror7_live_trace", []
    if kind in _MIRROR1_REPORT_KINDS:
        return "mirror1_compatible", []
    if "trace_id" in trace and frames:
        return "mirror1_compatible", []
    return "", [f"unsupported trace report_kind: {kind or '(missing)'}"]


def _warnings(
    trace: dict[str, Any],
    score: dict[str, Any],
    claim: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if _missing_entries("trace", trace.get("missing_evidence")):
        warnings.append("live trace has missing evidence frames")
    if _missing_entries("trace", trace.get("missing_frames")):
        warnings.append("trace has missing MIRROR.1 frames")
    if str(score.get("verdict", "")) in {"moderate_drift", "severe_derailment"}:
        warnings.append(f"MIRROR.2 verdict is {score.get('verdict')}")
    if str(claim.get("overall_claim_support", "")) in {"partially_supported", "unsupported", "contradicted"}:
        warnings.append(f"MIRROR.3 claim support is {claim.get('overall_claim_support')}")
    if _list_of_dicts(claim.get("mismatches")):
        warnings.append("claim mismatches detected")
    if _list_of_dicts(claim.get("unsupported_claims")):
        warnings.append("unsupported claims detected")
    if str(review.get("combined_verdict", "")) not in {"trustworthy_trace", ""}:
        warnings.append(f"combined review verdict is {review.get('combined_verdict')}")
    return _dedupe(warnings)


def _frame_coverage(trace: dict[str, Any], score: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    coverage = review.get("frame_coverage") if isinstance(review.get("frame_coverage"), dict) else {}
    if not coverage:
        coverage = score.get("frame_coverage") if isinstance(score.get("frame_coverage"), dict) else {}
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    out = dict(coverage)
    out.setdefault("available_frame_count", len(frames))
    out.setdefault("available_frame_types", [str(frame.get("frame_type", "")) for frame in frames if isinstance(frame, dict)])
    out["missing_evidence_count"] = len(_missing_entries("trace", trace.get("missing_evidence")))
    return out


def _derailment_summary(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "score_id": str(score.get("score_id", "")),
        "verdict": str(score.get("verdict", "")),
        "overall_derailment_score": score.get("overall_derailment_score"),
        "dimension_scores": score.get("dimension_scores") if isinstance(score.get("dimension_scores"), dict) else {},
        "recommended_next_action": str(score.get("recommended_next_action", "")),
        "insufficient_reasons": [str(item) for item in score.get("insufficient_reasons", [])] if isinstance(score.get("insufficient_reasons"), list) else [],
    }


def _claim_summary(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": str(claim.get("check_id", "")),
        "overall_claim_support": str(claim.get("overall_claim_support", "")),
        "mismatch_count": len(_list_of_dicts(claim.get("mismatches"))),
        "unsupported_claim_count": len(_list_of_dicts(claim.get("unsupported_claims"))),
        "recommended_next_action": str(claim.get("recommended_next_action", "")),
    }


def _review_summary(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": str(review.get("review_id", "")),
        "combined_verdict": str(review.get("combined_verdict", "")),
        "recommended_next_action": str(review.get("recommended_next_action", "")),
        "warning_count": len(review.get("warnings", []) if isinstance(review.get("warnings"), list) else []),
    }


def _combined_missing_evidence(
    trace: dict[str, Any],
    score: dict[str, Any],
    claim: dict[str, Any],
    review: dict[str, Any],
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    entries.extend(_missing_entries("trace", trace.get("missing_evidence")))
    entries.extend(_missing_entries("trace", trace.get("missing_frames")))
    entries.extend(_missing_entries("score", score.get("missing_evidence")))
    entries.extend(_missing_entries("claim_diff", claim.get("missing_evidence")))
    entries.extend(_missing_entries("combined_review", review.get("missing_evidence")))
    return _dedupe_dicts(entries)


def _missing_entries(source: str, value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    entries: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        entries.append(
            {
                "source": source,
                "frame_type": str(item.get("frame_type", item.get("category", ""))),
                "reason": str(item.get("reason", item.get("evidence_status", "missing"))),
            }
        )
    return entries


def _resolve_input_path(repo_root: Path, raw: str | Path | None) -> Path:
    if raw is None or str(raw).strip() == "":
        raise ValueError("empty_artifact_path: trace path is required")
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
        raise ValueError(f"unreadable_artifact: trace artifact is missing or not a file: {raw_text}")
    return resolved


def _resolve_output_dir(repo_root: Path, raw: str | Path | None, preview_id: str) -> Path:
    if not preview_id:
        raise ValueError("empty_preview_id: preview id is empty")
    if "/" in preview_id or "\\" in preview_id or ".." in preview_id:
        raise ValueError("traversal_attempt: preview id cannot contain path separators")
    raw_text = str(raw or DEFAULT_OUTPUT_DIR)
    raw_path = Path(raw_text).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"traversal_attempt: refusing traversal output path: {raw_text}")
    if _is_forbidden_path(raw_path):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = (candidate / preview_id).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"forbidden_root: output path resolves outside repository: {raw_text}") from exc
    if _is_forbidden_path(resolved):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    return resolved


def _ensure_not_live_trace_input_dir(output_dir: Path, trace_file: Path) -> None:
    trace_parent = trace_file.parent.resolve()
    if not _is_live_trace_dir(trace_parent):
        return
    try:
        if output_dir.resolve() == trace_parent or output_dir.resolve().is_relative_to(trace_parent):
            raise ValueError("live_trace_mutation: output directory must not be inside the live trace input directory")
    except AttributeError:
        output = output_dir.resolve()
        if output == trace_parent or str(output).startswith(str(trace_parent) + "/"):
            raise ValueError("live_trace_mutation: output directory must not be inside the live trace input directory")


def _is_live_trace_dir(path: Path) -> bool:
    parts = [part.lower() for part in path.parts]
    for index in range(0, max(0, len(parts) - 3)):
        if parts[index : index + 3] == [".agent", "mirror_tunnel", "live_traces"]:
            return True
    return False


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed_trace: trace JSON could not be parsed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("malformed_trace: trace JSON root must be an object")
    return data


def _blocked_report(
    *,
    preview_id: str | None,
    created_at: str,
    trace_path: str,
    reason: str,
    message: str,
) -> dict[str, Any]:
    status = STATUS_BLOCKED
    return {
        "report_kind": REPORT_KIND,
        "preview_id": preview_id or _default_preview_id({}, trace_path, created_at),
        "created_at": str(created_at or ""),
        "status": status,
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS[status],
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "trace_id": "",
        "run_id": "",
        "live_trace_input": {
            "trace_path": str(trace_path or ""),
            "trace_report_kind": "",
            "trace_status": "blocked",
            "trace_compatibility": "",
            "live_trace_artifact_mutated": False,
        },
        "frame_coverage": {},
        "derailment_score_preview": {},
        "claim_vs_diff_preview": {},
        "combined_review_verdict": {},
        "missing_evidence": [],
        "warnings": [],
        "blockers": [{"reason": reason, "message": message}],
        "artifact_paths": {},
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _result(ok: bool, report: dict[str, Any], json_path: str, md_path: str) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "status": str(report.get("status", "")),
        "json_path": json_path,
        "md_path": md_path,
        "report": report,
        "markdown": render_mirror_tunnel_live_trace_scoring_preview_markdown(report),
    }


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "post_run_only": True,
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
        "runtime_scoring_performed": False,
        "live_trace_mutated": False,
        "writes_preview_artifacts_only": True,
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


def _default_preview_id(trace: dict[str, Any], trace_path: str, created_at: str) -> str:
    seed = json.dumps(
        {
            "trace_id": trace.get("trace_id", ""),
            "run_id": trace.get("run_id", ""),
            "trace_path": str(trace_path or ""),
            "created_at": str(created_at or ""),
        },
        sort_keys=True,
    )
    return "live-trace-preview-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _reason_from_message(message: str) -> str:
    for reason in (
        "traversal_attempt",
        "secret_or_env_path",
        "forbidden_root",
        "unreadable_artifact",
        "empty_artifact_path",
        "malformed_trace",
        "live_trace_mutation",
    ):
        if str(message).startswith(reason):
            return reason
    return "blocked"


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "")
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _dedupe_dicts(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("source", "")),
            str(item.get("frame_type", "")),
            str(item.get("reason", "")),
        )
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


def _missing_lines(value: Any) -> list[str]:
    return [
        f"`{_md(item.get('source'))}` / `{_md(item.get('frame_type'))}`: {_md(item.get('reason'))}"
        for item in _list_of_dicts(value)
    ]


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
