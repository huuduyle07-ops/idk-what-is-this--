"""MIRROR.6 - Manual Trace Score Pipeline (report-only).

MIRROR.6 reads a manually assembled MIRROR.5/MIRROR.1 trace, derives or loads
MIRROR.2 and MIRROR.3 reports, and writes one combined Mirror Tunnel manual
review pack. It calls only pure Python builders from MIRROR.2 and MIRROR.3; it
does not shell out to CLIs or execute validation, benchmarks, git, subprocess,
MCP tools, workers, models, network calls, database writes, route/auth changes,
or live runtime tracing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.mirror_tunnel_claim_diff_check import build_mirror_tunnel_claim_diff_check
from core.mirror_tunnel_derailment_score import build_mirror_tunnel_derailment_score


REPORT_KIND = "mirror_tunnel_manual_review"
JSON_NAME = "mirror_tunnel_manual_review.json"
MD_NAME = "mirror_tunnel_manual_review.md"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "manual_review"

REVIEW_VERDICTS: tuple[str, ...] = (
    "trustworthy_trace",
    "review_recommended",
    "do_not_trust_without_more_evidence",
    "insufficient_trace",
    "blocked",
)

RECOMMENDED_NEXT_ACTIONS: dict[str, str] = {
    "trustworthy_trace": "continue_normal_review",
    "review_recommended": "human_review_recommended",
    "do_not_trust_without_more_evidence": "collect_evidence_or_replay",
    "insufficient_trace": "assemble_better_manual_trace",
    "blocked": "fix_unsafe_or_missing_artifact",
}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.6 is report-only.",
    "MIRROR.6 reads a MIRROR.5/MIRROR.1-compatible trace JSON.",
    "MIRROR.6 may read existing MIRROR.2 and MIRROR.3 report JSON artifacts.",
    "MIRROR.6 calls MIRROR.2 and MIRROR.3 pure Python builders only when reports are not supplied.",
    "MIRROR.6 does not call CLI scripts.",
    "MIRROR.6 does not call models.",
    "MIRROR.6 does not apply patches.",
    "MIRROR.6 does not run validation.",
    "MIRROR.6 does not run benchmarks.",
    "MIRROR.6 does not invoke MCP tools.",
    "MIRROR.6 does not launch workers.",
    "MIRROR.6 does not execute Dream actions.",
    "MIRROR.6 does not apply Replay janitor actions.",
    "MIRROR.6 does not use Docker or subprocess.",
    "MIRROR.6 does not contact network services.",
    "MIRROR.6 does not write to a database.",
    "MIRROR.6 does not change route behavior.",
    "MIRROR.6 does not change auth policy.",
    "MIRROR.6 does not enable live runtime tracing.",
    "MIRROR.6 writes manual review artifacts only.",
)


def build_mirror_tunnel_manual_review(
    *,
    trace: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    claim_diff: dict[str, Any] | None = None,
    trace_path: str = "",
    score_path: str = "",
    claim_diff_path: str = "",
    review_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a combined MIRROR.6 review pack from parsed trace/report data."""
    trace_data = trace if isinstance(trace, dict) else {}
    score_source = "provided" if isinstance(score, dict) and score else "derived"
    score_data = score if score_source == "provided" else build_mirror_tunnel_derailment_score(
        trace=trace_data,
        trace_path=trace_path,
        created_at=created_at,
    )
    claim_source = "provided" if isinstance(claim_diff, dict) and claim_diff else "derived"
    claim_data = claim_diff if claim_source == "provided" else build_mirror_tunnel_claim_diff_check(
        trace=trace_data,
        score=score_data,
        trace_path=trace_path,
        score_path=score_path,
        created_at=created_at,
    )

    warnings = _warnings(trace_data, score_data, claim_data)
    combined_verdict = _combined_verdict(trace_data, score_data, claim_data, warnings)
    report = {
        "report_kind": REPORT_KIND,
        "review_id": review_id or _default_review_id(trace_data, score_data, claim_data, created_at),
        "created_at": str(created_at or ""),
        "trace_id": str(trace_data.get("trace_id", "")),
        "trace_path": str(trace_path or ""),
        "score_id": str(score_data.get("score_id", "")),
        "score_path": str(score_path or ""),
        "claim_diff_id": str(claim_data.get("check_id", "")),
        "claim_diff_path": str(claim_diff_path or ""),
        "score_source": score_source,
        "claim_diff_source": claim_source,
        "trace_status": str(trace_data.get("status", "")),
        "trace_trust_level": str(trace_data.get("trust_level", "")),
        "combined_verdict": combined_verdict,
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS[combined_verdict],
        "recommended_next_phase": "MIRROR.CLOSE",
        "frame_coverage": _frame_coverage(trace_data, score_data),
        "derailment_score_summary": _derailment_summary(score_data),
        "claim_diff_summary": _claim_diff_summary(claim_data),
        "strongest_drift_dimensions": _strongest_drift_dimensions(score_data),
        "mismatches": _list_of_dicts(claim_data.get("mismatches")),
        "unsupported_claims": _list_of_dicts(claim_data.get("unsupported_claims")),
        "missing_evidence": _combined_missing_evidence(trace_data, score_data, claim_data),
        "human_review_notes": _human_review_notes(combined_verdict, warnings, score_data, claim_data),
        "warnings": warnings,
        "artifact_references": _artifact_references(trace_data, trace_path, score_path, claim_diff_path),
        "blockers": [],
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }
    return report


def write_mirror_tunnel_manual_review(
    *,
    repo_path: str = ".",
    trace_path: str,
    score_path: str | None = None,
    claim_diff_path: str | None = None,
    review_id: str | None = None,
    created_at: str = "",
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Read inputs, derive missing reports, and write MIRROR.6 JSON/Markdown."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    try:
        trace_file = _resolve_input_path(repo_root, trace_path, required=True)
        score_file = _resolve_input_path(repo_root, score_path, required=False)
        claim_file = _resolve_input_path(repo_root, claim_diff_path, required=False)
        trace = _load_json_object(trace_file, "trace")
        score = _load_json_object(score_file, "score") if score_file else None
        claim = _load_json_object(claim_file, "claim-diff") if claim_file else None
        report = build_mirror_tunnel_manual_review(
            trace=trace,
            score=score,
            claim_diff=claim,
            trace_path=str(trace_file),
            score_path=str(score_file or ""),
            claim_diff_path=str(claim_file or ""),
            review_id=review_id,
            created_at=created_at,
        )
        out_dir = _resolve_output_dir(repo_root, output_dir, str(report["review_id"]))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = _blocked_report(review_id=review_id, created_at=created_at, message=str(exc))
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_mirror_tunnel_manual_review_markdown(report),
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    markdown = render_mirror_tunnel_manual_review_markdown(report)
    json_path.write_text(render_mirror_tunnel_manual_review_json(report), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": report["combined_verdict"] != "blocked",
        "status": report["combined_verdict"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_mirror_tunnel_manual_review_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_manual_review_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Manual Review",
        "",
        "## Summary",
        "",
        f"- **Review id:** `{_md(report.get('review_id'))}`",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Combined verdict:** `{_md(report.get('combined_verdict'))}`",
        f"- **Recommended next action:** `{_md(report.get('recommended_next_action'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Trace Coverage",
        "",
        _dict_block(report.get("frame_coverage")),
        "",
        "## Derailment Score Summary",
        "",
        _dict_block(report.get("derailment_score_summary")),
        "",
        "## Claim-vs-Diff Summary",
        "",
        _dict_block(report.get("claim_diff_summary")),
        "",
        "## Missing Evidence",
        "",
        _bullet_list(_missing_lines(report.get("missing_evidence"))),
        "",
        "## Human Review Notes",
        "",
        _bullet_list([_md(item) for item in report.get("human_review_notes", [])]),
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


def _combined_verdict(
    trace: dict[str, Any],
    score: dict[str, Any],
    claim: dict[str, Any],
    warnings: list[str],
) -> str:
    trace_status = str(trace.get("status", ""))
    score_verdict = str(score.get("verdict", ""))
    claim_support = str(claim.get("overall_claim_support", ""))
    if trace_status == "blocked" or score_verdict == "blocked" or claim_support == "blocked":
        return "blocked"
    if trace_status == "insufficient_evidence" or score_verdict == "insufficient_trace" or claim_support == "insufficient_evidence":
        return "insufficient_trace"
    if score_verdict == "severe_derailment" or claim_support == "contradicted":
        return "do_not_trust_without_more_evidence"
    if score_verdict == "moderate_drift" or claim_support in {"partially_supported", "unsupported"} or warnings:
        return "review_recommended"
    if score_verdict in {"aligned", "minor_drift"} and claim_support == "supported":
        return "trustworthy_trace"
    return "review_recommended"


def _warnings(trace: dict[str, Any], score: dict[str, Any], claim: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if str(trace.get("status", "")) == "partial_trace":
        warnings.append("trace is partial")
    if _list_of_dicts(claim.get("mismatches")):
        warnings.append("claim mismatches detected")
    if _list_of_dicts(claim.get("unsupported_claims")):
        warnings.append("unsupported claims detected")
    coverage = score.get("frame_coverage") if isinstance(score.get("frame_coverage"), dict) else {}
    if int(coverage.get("unknown_artifact_count", 0) or 0) > 0:
        warnings.append("unknown artifact frames remain in trace")
    return _dedupe(warnings)


def _frame_coverage(trace: dict[str, Any], score: dict[str, Any]) -> dict[str, Any]:
    coverage = score.get("frame_coverage") if isinstance(score.get("frame_coverage"), dict) else {}
    if coverage:
        return dict(coverage)
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    return {
        "available_frame_count": len(frames),
        "available_frame_types": [str(frame.get("frame_type", "")) for frame in frames if isinstance(frame, dict)],
        "missing_frame_count": len(trace.get("missing_frames", []) if isinstance(trace.get("missing_frames"), list) else []),
        "has_user_intent": any(isinstance(frame, dict) and frame.get("frame_type") == "user_intent" for frame in frames),
    }


def _derailment_summary(score: dict[str, Any]) -> dict[str, Any]:
    return {
        "score_id": str(score.get("score_id", "")),
        "verdict": str(score.get("verdict", "")),
        "overall_derailment_score": score.get("overall_derailment_score"),
        "dimension_scores": score.get("dimension_scores") if isinstance(score.get("dimension_scores"), dict) else {},
        "recommended_next_action": str(score.get("recommended_next_action", "")),
    }


def _claim_diff_summary(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": str(claim.get("check_id", "")),
        "overall_claim_support": str(claim.get("overall_claim_support", "")),
        "mismatch_count": len(_list_of_dicts(claim.get("mismatches"))),
        "unsupported_claim_count": len(_list_of_dicts(claim.get("unsupported_claims"))),
        "recommended_next_action": str(claim.get("recommended_next_action", "")),
    }


def _strongest_drift_dimensions(score: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = score.get("dimension_scores") if isinstance(score.get("dimension_scores"), dict) else {}
    out: list[dict[str, Any]] = []
    for name, data in dimensions.items():
        if not isinstance(data, dict):
            continue
        out.append(
            {
                "dimension": str(name),
                "score": float(data.get("score", 0.0) or 0.0),
                "reasons": [str(item) for item in data.get("reasons", [])] if isinstance(data.get("reasons"), list) else [],
            }
        )
    out.sort(key=lambda item: (-float(item["score"]), str(item["dimension"])))
    return out[:3]


def _combined_missing_evidence(trace: dict[str, Any], score: dict[str, Any], claim: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    entries.extend(_missing_entries("trace", trace.get("missing_evidence")))
    entries.extend(_missing_entries("score", score.get("missing_evidence")))
    entries.extend(_missing_entries("claim_diff", claim.get("missing_evidence")))
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


def _human_review_notes(
    verdict: str,
    warnings: list[str],
    score: dict[str, Any],
    claim: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if verdict == "trustworthy_trace":
        notes.append("Manual trace, derailment score, and claim-vs-diff check are aligned enough for normal review.")
    elif verdict == "insufficient_trace":
        notes.append("Manual trace or derived reports do not contain enough evidence for an honest review.")
    elif verdict == "do_not_trust_without_more_evidence":
        notes.append("Do not trust this result without collecting evidence or replaying the run.")
    elif verdict == "review_recommended":
        notes.append("Human review is recommended before trusting this manual trace result.")
    elif verdict == "blocked":
        notes.append("Resolve unsafe or unreadable artifacts before reviewing this trace.")
    notes.extend(warnings)
    if str(score.get("verdict", "")):
        notes.append(f"MIRROR.2 verdict: {score.get('verdict')}")
    if str(claim.get("overall_claim_support", "")):
        notes.append(f"MIRROR.3 claim support: {claim.get('overall_claim_support')}")
    return _dedupe(notes)


def _artifact_references(trace: dict[str, Any], trace_path: str, score_path: str, claim_diff_path: str) -> list[dict[str, str]]:
    refs = [{"source": "trace", "artifact_path": str(trace_path or "")}]
    if score_path:
        refs.append({"source": "score", "artifact_path": str(score_path)})
    if claim_diff_path:
        refs.append({"source": "claim_diff", "artifact_path": str(claim_diff_path)})
    raw_refs = trace.get("artifact_references")
    if isinstance(raw_refs, list):
        for item in raw_refs:
            if isinstance(item, dict) and item.get("artifact_path"):
                refs.append({"source": "trace_frame", "artifact_path": str(item.get("artifact_path", ""))})
    return [item for item in refs if item["artifact_path"]]


def _blocked_report(*, review_id: str | None, created_at: str, message: str) -> dict[str, Any]:
    reason = _reason_from_message(message)
    return {
        "report_kind": REPORT_KIND,
        "review_id": review_id or _default_review_id({}, {}, {}, created_at),
        "created_at": str(created_at or ""),
        "trace_id": "",
        "trace_path": "",
        "score_id": "",
        "score_path": "",
        "claim_diff_id": "",
        "claim_diff_path": "",
        "score_source": "",
        "claim_diff_source": "",
        "trace_status": "blocked",
        "trace_trust_level": "blocked",
        "combined_verdict": "blocked",
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS["blocked"],
        "recommended_next_phase": "MIRROR.CLOSE",
        "frame_coverage": {},
        "derailment_score_summary": {},
        "claim_diff_summary": {},
        "strongest_drift_dimensions": [],
        "mismatches": [],
        "unsupported_claims": [],
        "missing_evidence": [{"source": "blocked", "frame_type": "", "reason": message}],
        "human_review_notes": ["Resolve unsafe or unreadable artifacts before reviewing this trace."],
        "warnings": [],
        "artifact_references": [],
        "blockers": [{"reason": reason, "message": message}],
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _resolve_input_path(repo_root: Path, raw: str | None, *, required: bool) -> Path | None:
    if raw is None or str(raw).strip() == "":
        if required:
            raise ValueError("empty_artifact_path: required input path is empty")
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


def _resolve_output_dir(repo_root: Path, raw: str | None, review_id: str) -> Path:
    if not review_id:
        raise ValueError("empty_review_id: review id is empty")
    if "/" in review_id or "\\" in review_id or ".." in review_id:
        raise ValueError("traversal_attempt: review id cannot contain path separators")
    raw_text = str(raw or DEFAULT_OUTPUT_DIR)
    raw_path = Path(raw_text).expanduser()
    if any(part == ".." for part in raw_path.parts):
        raise ValueError(f"traversal_attempt: refusing traversal output path: {raw_text}")
    if _is_forbidden_path(raw_path):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    candidate = raw_path if raw_path.is_absolute() else repo_root / raw_path
    resolved = (candidate / review_id).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"forbidden_root: output path resolves outside repository: {raw_text}") from exc
    if _is_forbidden_path(resolved):
        raise ValueError(f"secret_or_env_path: refusing secret/env/key/token output path: {raw_text}")
    return resolved


def _load_json_object(path: Path | None, label: str) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return data


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
        "live_runtime_tracing_enabled": False,
        "cli_invocation_performed": False,
        "writes_manual_review_artifacts_only": True,
    }


def _default_review_id(trace: dict[str, Any], score: dict[str, Any], claim: dict[str, Any], created_at: str) -> str:
    seed = json.dumps(
        {
            "trace_id": trace.get("trace_id", ""),
            "score_id": score.get("score_id", ""),
            "check_id": claim.get("check_id", ""),
            "created_at": str(created_at or ""),
        },
        sort_keys=True,
    )
    return "manual-review-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _reason_from_message(message: str) -> str:
    for reason in ("traversal_attempt", "secret_or_env_path", "forbidden_root", "unreadable_artifact", "empty_artifact_path"):
        if message.startswith(reason):
            return reason
    return "blocked"


def _dict_block(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "_None._"
    return "\n".join(f"- `{_md(key)}`: {_md(value[key])}" for key in sorted(value))


def _missing_lines(value: Any) -> list[str]:
    items = _list_of_dicts(value)
    return [
        f"`{_md(item.get('source'))}` / `{_md(item.get('frame_type'))}`: {_md(item.get('reason'))}"
        for item in items
    ]


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _dedupe_dicts(values: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        key = (item.get("source", ""), item.get("frame_type", ""), item.get("reason", ""))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out
