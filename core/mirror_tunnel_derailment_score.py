"""MIRROR.2 - Mirror Tunnel Derailment Score Report (report-only).

MIRROR.2 consumes a MIRROR.1 trace contract and deterministically estimates how
much the multi-agent chain drifted from original intent to final evidence/result.
It scores six dimensions:

* intent_drift
* scope_drift
* evidence_loss
* claim_action_mismatch
* validation_gap
* confidence_inflation

This module is report-only. It uses plain text heuristics only: no models, no
embeddings, no semantic API, no validation/benchmark execution, no workers, no
MCP calls, no Docker/subprocess, no network, no database writes, no route/auth
changes, and no execution blocking. It writes only
``mirror_tunnel_derailment_score.json`` / ``mirror_tunnel_derailment_score.md``
when the writer is called.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_derailment_score"
JSON_NAME = "mirror_tunnel_derailment_score.json"
MD_NAME = "mirror_tunnel_derailment_score.md"
DEFAULT_TRACE_PATH = Path(".agent") / "mirror_tunnel" / "trace_contract" / "mirror_tunnel_trace_contract.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "derailment_score"

SCORE_DIMENSIONS: tuple[str, ...] = (
    "intent_drift",
    "scope_drift",
    "evidence_loss",
    "claim_action_mismatch",
    "validation_gap",
    "confidence_inflation",
)

DIMENSION_WEIGHTS: dict[str, float] = {
    "intent_drift": 0.25,
    "scope_drift": 0.20,
    "evidence_loss": 0.20,
    "claim_action_mismatch": 0.15,
    "validation_gap": 0.10,
    "confidence_inflation": 0.10,
}

VERDICTS: tuple[str, ...] = (
    "aligned",
    "minor_drift",
    "moderate_drift",
    "severe_derailment",
    "insufficient_trace",
)

RECOMMENDED_NEXT_ACTIONS: dict[str, str] = {
    "aligned": "continue_normal_review",
    "minor_drift": "continue_normal_review",
    "moderate_drift": "human_review_recommended",
    "severe_derailment": "do_not_trust_result_without_replay",
    "insufficient_trace": "collect_more_trace_artifacts",
}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.2 is report-only.",
    "MIRROR.2 reads a MIRROR.1 trace contract.",
    "MIRROR.2 uses deterministic heuristics only.",
    "MIRROR.2 does not call models.",
    "MIRROR.2 does not use embeddings or semantic APIs.",
    "MIRROR.2 does not apply patches.",
    "MIRROR.2 does not run validation.",
    "MIRROR.2 does not run benchmarks.",
    "MIRROR.2 does not invoke MCP tools.",
    "MIRROR.2 does not launch workers.",
    "MIRROR.2 does not execute Dream actions.",
    "MIRROR.2 does not apply Replay janitor actions.",
    "MIRROR.2 does not use Docker or subprocess.",
    "MIRROR.2 does not contact network services.",
    "MIRROR.2 does not write to a database.",
    "MIRROR.2 does not change route behavior.",
    "MIRROR.2 does not change auth policy.",
    "MIRROR.2 does not block execution.",
    "MIRROR.2 writes score artifacts only.",
)

_CORE_FRAME_TYPES: tuple[str, ...] = (
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

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "without",
    "this",
    "that",
    "only",
    "fix",
    "fixed",
    "please",
}

_SUCCESS_CLAIM_RE = re.compile(
    r"\b(validated|validation passed|tests? passed|benchmark passed|passed|fixed|complete|done|shipped|resolved)\b",
    re.IGNORECASE,
)
_FAILURE_RE = re.compile(r"\b(fail|failed|failure|error|blocked|timeout|regression)\b", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"\b(confidence|confident|certain|definitely|guaranteed|complete|validated)\b", re.IGNORECASE)
_BROAD_SCOPE_RE = re.compile(r"\b(rewrite|redesign|new feature|refactor all|migration|overhaul|broad)\b", re.IGNORECASE)


def build_mirror_tunnel_derailment_score(
    *,
    trace: dict[str, Any] | None = None,
    trace_path: str = "",
    score_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a deterministic MIRROR.2 score report from a parsed trace dict."""
    trace_data = trace if isinstance(trace, dict) else {}
    frames = _frames(trace_data)
    by_type = _frames_by_type(frames)
    insufficient_reasons = _insufficient_reasons(trace_data, by_type)
    coverage = _frame_coverage(trace_data, frames)

    dimension_scores = {
        "intent_drift": _score_intent_drift(by_type),
        "scope_drift": _score_scope_drift(by_type),
        "evidence_loss": _score_evidence_loss(trace_data, by_type, coverage),
        "claim_action_mismatch": _score_claim_action_mismatch(by_type),
        "validation_gap": _score_validation_gap(by_type),
        "confidence_inflation": _score_confidence_inflation(trace_data, by_type),
    }

    if insufficient_reasons:
        verdict = "insufficient_trace"
        overall: float | None = None
    else:
        overall = _weighted_average(dimension_scores)
        verdict = _verdict(overall)

    report = {
        "report_kind": REPORT_KIND,
        "score_id": score_id or _default_score_id(trace_data, trace_path, created_at),
        "created_at": str(created_at or ""),
        "trace_id": str(trace_data.get("trace_id", "")),
        "trace_path": str(trace_path or ""),
        "source_run_id": str(trace_data.get("source_run_id", "")),
        "trace_status": str(trace_data.get("status", "")),
        "trace_trust_level": str(trace_data.get("trust_level", "")),
        "overall_derailment_score": overall,
        "dimension_scores": dimension_scores,
        "dimension_weights": dict(DIMENSION_WEIGHTS),
        "verdict": verdict,
        "recommended_next_action": RECOMMENDED_NEXT_ACTIONS[verdict],
        "recommended_next_phase": "MIRROR.3",
        "frame_coverage": coverage,
        "detected_drift_points": _drift_points(dimension_scores),
        "evidence_used": _evidence_used(frames),
        "missing_evidence": _missing_evidence(trace_data),
        "claim_action_checks": _claim_action_checks(by_type),
        "validation_gap_checks": _validation_gap_checks(by_type),
        "insufficient_reasons": insufficient_reasons,
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }
    return report


def load_trace_contract(trace_path: str | Path) -> dict[str, Any]:
    """Read a MIRROR.1 trace contract JSON file."""
    path = Path(trace_path)
    if _is_forbidden_trace_path(path):
        raise ValueError("refusing to read secret/env path as a MIRROR.1 trace contract")
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("trace contract root must be a JSON object")
    return data


def write_mirror_tunnel_derailment_score(
    *,
    trace_path: str | None = None,
    repo_path: str = ".",
    output_root: str | None = None,
    score_id: str | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Read a trace contract and write MIRROR.2 JSON + Markdown artifacts."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    trace_file = _resolve_trace_path(repo_root, trace_path)
    try:
        trace = load_trace_contract(trace_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = _blocked_report(trace_file, score_id=score_id, created_at=created_at, message=str(exc))
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_mirror_tunnel_derailment_markdown(report),
        }

    report = build_mirror_tunnel_derailment_score(
        trace=trace,
        trace_path=str(trace_file),
        score_id=score_id,
        created_at=created_at,
    )
    output_dir = _resolve_output_root(repo_root, output_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / JSON_NAME
    md_path = output_dir / MD_NAME
    markdown = render_mirror_tunnel_derailment_markdown(report)
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": report["verdict"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_mirror_tunnel_derailment_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_mirror_tunnel_derailment_markdown(report: dict[str, Any]) -> str:
    """Render the MIRROR.2 report as operator-readable Markdown."""
    lines: list[str] = [
        "# Mirror Tunnel Derailment Score Report",
        "",
        "## Summary",
        "",
        f"- **Score id:** `{_md(report.get('score_id'))}`",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Verdict:** `{_md(report.get('verdict'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Overall Derailment Score",
        "",
        f"`{_score_text(report.get('overall_derailment_score'))}`",
        "",
        "## Dimension Scores",
        "",
    ]
    dimensions = report.get("dimension_scores") if isinstance(report.get("dimension_scores"), dict) else {}
    for name in SCORE_DIMENSIONS:
        item = dimensions.get(name) if isinstance(dimensions.get(name), dict) else {}
        lines.append(f"- `{name}` = `{_score_text(item.get('score'))}` (weight `{DIMENSION_WEIGHTS[name]}`)")
        for reason in item.get("reasons", []):
            lines.append(f"  - {_md(reason)}")
    lines.append("")

    lines += ["## Frame Coverage", ""]
    coverage = report.get("frame_coverage") if isinstance(report.get("frame_coverage"), dict) else {}
    for key in sorted(coverage):
        lines.append(f"- `{_md(key)}` = `{_md(coverage[key])}`")
    lines.append("")

    lines += ["## Detected Drift Points", ""]
    lines.append(_bullet_list(_point_lines(report.get("detected_drift_points"))))
    lines.append("")

    lines += ["## Evidence Used", ""]
    lines.append(_bullet_list(_evidence_lines(report.get("evidence_used"))))
    lines.append("")

    lines += ["## Missing Evidence", ""]
    lines.append(_bullet_list(_missing_lines(report.get("missing_evidence"))))
    lines.append("")

    lines += ["## Claim / Action Checks", ""]
    lines.append(_bullet_list(_check_lines(report.get("claim_action_checks"))))
    lines.append("")

    lines += ["## Validation Gap Checks", ""]
    lines.append(_bullet_list(_check_lines(report.get("validation_gap_checks"))))
    lines.append("")

    lines += ["## Recommended Next Action", ""]
    lines.append(f"`{_md(report.get('recommended_next_action'))}`")
    lines.append("")

    lines += ["## Boundaries / Guardrails", ""]
    for boundary in report.get("boundaries", []):
        lines.append(f"- {_md(boundary)}")
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def _frames(trace: dict[str, Any]) -> list[dict[str, Any]]:
    raw = trace.get("frames")
    return [frame for frame in raw if isinstance(frame, dict)] if isinstance(raw, list) else []


def _frames_by_type(frames: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        frame_type = str(frame.get("frame_type", "unknown_artifact") or "unknown_artifact")
        out.setdefault(frame_type, []).append(frame)
    return out


def _text_for(by_type: dict[str, list[dict[str, Any]]], frame_types: tuple[str, ...]) -> str:
    parts: list[str] = []
    for frame_type in frame_types:
        for frame in by_type.get(frame_type, []):
            parts.append(str(frame.get("excerpt", "")))
            parts.append(str(frame.get("artifact_path", "")))
    return "\n".join(part for part in parts if part)


def _all_text(by_type: dict[str, list[dict[str, Any]]]) -> str:
    return _text_for(by_type, tuple(by_type.keys()))


def _score_intent_drift(by_type: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    intent = _text_for(by_type, ("user_intent", "goal_brief"))
    later = _text_for(
        by_type,
        ("mode_decision", "control_prompt", "worker_assignment", "worker_reply", "patch_or_diff", "final_answer"),
    )
    reasons: list[str] = []
    if not intent:
        return _dimension(1.0, ["user intent frame is missing"])
    if not later:
        return _dimension(0.7, ["no later action/result frames are available to compare with intent"])
    intent_tokens = _keywords(intent)
    later_tokens = _keywords(later)
    if not intent_tokens:
        return _dimension(0.2, ["user intent has too few comparable keywords"])
    overlap = len(intent_tokens & later_tokens) / max(1, len(intent_tokens))
    if overlap >= 0.5:
        score = 0.0
    elif overlap >= 0.3:
        score = 0.25
        reasons.append("later frames preserve only partial user-intent keywords")
    else:
        score = 0.6
        reasons.append("later frames preserve few user-intent keywords")
    if _BROAD_SCOPE_RE.search(later) and "only" in intent.lower():
        score = max(score, 0.5)
        reasons.append("later frames mention broad work despite narrow/only language in the intent")
    return _dimension(score, reasons)


def _score_scope_drift(by_type: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    source = _text_for(by_type, ("user_intent", "goal_brief", "worker_assignment", "control_prompt"))
    patch_text = _text_for(by_type, ("patch_or_diff",))
    later_text = _text_for(by_type, ("worker_reply", "final_answer", "patch_or_diff"))
    allowed = _allowed_files(source)
    forbidden = _forbidden_files(source)
    touched = _touched_files(patch_text)
    reasons: list[str] = []
    score = 0.0
    out_of_scope = sorted(path for path in touched if allowed and path not in allowed)
    forbidden_touched = sorted(path for path in touched if path in forbidden)
    if out_of_scope:
        score = max(score, 0.75)
        reasons.append("patch/diff touches files outside allowed context: " + ", ".join(out_of_scope))
    if forbidden_touched:
        score = max(score, 0.9)
        reasons.append("patch/diff touches forbidden files: " + ", ".join(forbidden_touched))
    if _BROAD_SCOPE_RE.search(later_text) and re.search(r"\b(only|narrow|single|do not)\b", source, re.IGNORECASE):
        score = max(score, 0.5)
        reasons.append("later frames broaden a narrow task into broader work")
    if touched and not allowed and re.search(r"\ballowed files?\b", source, re.IGNORECASE):
        score = max(score, 0.4)
        reasons.append("allowed-file context was mentioned but no allowed path could be recovered")
    return _dimension(score, reasons)


def _score_evidence_loss(
    trace: dict[str, Any],
    by_type: dict[str, list[dict[str, Any]]],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    score = 0.0
    source = _text_for(by_type, ("user_intent", "goal_brief", "worker_assignment", "control_prompt"))
    later = _text_for(by_type, ("worker_reply", "final_answer", "validation_evidence", "benchmark_evidence", "replay_evidence"))
    if coverage["unknown_artifact_count"] >= 3:
        score = max(score, 0.5)
        reasons.append("many unknown_artifact frames reduce trace readability")
    missing_core = set(coverage.get("missing_core_frame_types", []))
    if {"worker_assignment", "final_answer"} & missing_core and by_type.get("patch_or_diff"):
        score = max(score, 0.3)
        reasons.append("important action/result frames are missing around a patch")
    if "validation" in source.lower() and not by_type.get("validation_evidence"):
        score = max(score, 0.4)
        reasons.append("validation command or constraint appears early but validation evidence is missing")
    allowed = _allowed_files(source)
    if allowed and later and not any(path in later for path in allowed):
        score = max(score, 0.25)
        reasons.append("allowed-file context appears early but disappears from later evidence/result frames")
    trace_missing = trace.get("missing_evidence")
    if isinstance(trace_missing, list) and len(trace_missing) >= 8 and coverage["available_frame_count"] <= 2:
        score = max(score, 0.45)
        reasons.append("trace carries many missing evidence records and few available frames")
    return _dimension(score, reasons)


def _score_claim_action_mismatch(by_type: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    checks = _claim_action_checks(by_type)
    reasons = [check["message"] for check in checks if check["status"] == "mismatch"]
    if not reasons:
        return _dimension(0.0, [])
    severe = any("failure" in reason.lower() or "without validation evidence" in reason.lower() for reason in reasons)
    return _dimension(0.8 if severe else 0.55, reasons)


def _score_validation_gap(by_type: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    checks = _validation_gap_checks(by_type)
    reasons = [check["message"] for check in checks if check["status"] in {"gap", "warning"}]
    if not reasons:
        return _dimension(0.0, [])
    if any("claims validation" in reason.lower() for reason in reasons):
        return _dimension(0.9, reasons)
    if any("patch/diff exists" in reason.lower() for reason in reasons):
        return _dimension(0.8, reasons)
    return _dimension(0.45, reasons)


def _score_confidence_inflation(trace: dict[str, Any], by_type: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    later = _text_for(by_type, ("worker_reply", "final_answer"))
    evidence_present = bool(
        by_type.get("validation_evidence") or by_type.get("benchmark_evidence") or by_type.get("replay_evidence")
    )
    reasons: list[str] = []
    score = 0.0
    if _CONFIDENCE_RE.search(later) and not evidence_present:
        score = max(score, 0.55)
        reasons.append("confident success language appears while evidence frames are weak or missing")
    if str(trace.get("trust_level", "")).lower() == "high" and not evidence_present:
        score = max(score, 0.4)
        reasons.append("trace trust level is high despite missing validation/benchmark/replay evidence")
    return _dimension(score, reasons)


def _claim_action_checks(by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    final_text = _text_for(by_type, ("final_answer",))
    patch_text = _text_for(by_type, ("patch_or_diff",))
    validation_text = _text_for(by_type, ("validation_evidence",))
    benchmark_text = _text_for(by_type, ("benchmark_evidence",))
    replay_text = _text_for(by_type, ("replay_evidence",))
    checks: list[dict[str, str]] = []
    final_claims_success = bool(_SUCCESS_CLAIM_RE.search(final_text))
    evidence_text = "\n".join([validation_text, benchmark_text, replay_text])
    has_evidence = bool(evidence_text.strip())
    if final_claims_success and not has_evidence:
        checks.append(
            {
                "status": "mismatch",
                "message": "final answer claims success or validation without validation/benchmark/replay evidence",
            }
        )
    if final_claims_success and not patch_text and re.search(r"\b(fixed|resolved|patch|changed)\b", final_text, re.IGNORECASE):
        checks.append({"status": "mismatch", "message": "final answer claims a fix but no patch/diff frame exists"})
    if _FAILURE_RE.search(benchmark_text + "\n" + replay_text) and final_claims_success:
        checks.append({"status": "mismatch", "message": "benchmark/replay evidence contains failure while final answer claims success"})
    if not checks:
        checks.append({"status": "ok", "message": "no claim/action mismatch detected by deterministic checks"})
    return checks


def _validation_gap_checks(by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    final_text = _text_for(by_type, ("final_answer",))
    patch_exists = bool(by_type.get("patch_or_diff"))
    validation_exists = bool(by_type.get("validation_evidence"))
    benchmark_exists = bool(by_type.get("benchmark_evidence"))
    replay_exists = bool(by_type.get("replay_evidence"))
    checks: list[dict[str, str]] = []
    if patch_exists and not (validation_exists or benchmark_exists or replay_exists):
        checks.append({"status": "gap", "message": "patch/diff exists but validation, benchmark, and replay evidence are missing"})
    if re.search(r"\b(validated|validation passed|tests? passed|passed)\b", final_text, re.IGNORECASE) and not validation_exists:
        checks.append({"status": "gap", "message": "final answer claims validation passed but validation_evidence frame is missing"})
    if not checks:
        checks.append({"status": "ok", "message": "no validation gap detected by deterministic checks"})
    return checks


def _frame_coverage(trace: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
    frame_types = [str(frame.get("frame_type", "")) for frame in frames]
    missing = [
        str(item.get("frame_type", ""))
        for item in trace.get("missing_frames", [])
        if isinstance(item, dict) and str(item.get("frame_type", ""))
    ]
    return {
        "available_frame_count": len(frames),
        "unknown_artifact_count": frame_types.count("unknown_artifact"),
        "available_frame_types": frame_types,
        "missing_frame_count": len(missing),
        "missing_core_frame_types": [frame_type for frame_type in _CORE_FRAME_TYPES if frame_type in missing],
        "has_user_intent": "user_intent" in frame_types,
        "has_final_answer": "final_answer" in frame_types,
        "has_patch_or_diff": "patch_or_diff" in frame_types,
        "has_validation_evidence": "validation_evidence" in frame_types,
        "has_benchmark_evidence": "benchmark_evidence" in frame_types,
        "has_replay_evidence": "replay_evidence" in frame_types,
    }


def _insufficient_reasons(trace: dict[str, Any], by_type: dict[str, list[dict[str, Any]]]) -> list[str]:
    reasons: list[str] = []
    if not by_type.get("user_intent"):
        reasons.append("missing_user_intent_frame")
    if not by_type.get("final_answer") and not (
        by_type.get("validation_evidence") or by_type.get("benchmark_evidence") or by_type.get("replay_evidence")
    ):
        reasons.append("missing_final_answer_and_evidence_frames")
    if str(trace.get("status", "")) == "blocked":
        reasons.append("source_trace_blocked")
    known_count = sum(len(items) for frame_type, items in by_type.items() if frame_type != "unknown_artifact")
    if known_count <= 1:
        reasons.append("too_few_known_frames")
    return _dedupe(reasons)


def _weighted_average(dimension_scores: dict[str, dict[str, Any]]) -> float:
    total = 0.0
    for name, weight in DIMENSION_WEIGHTS.items():
        total += float(dimension_scores[name]["score"]) * weight
    return round(total, 3)


def _verdict(score: float) -> str:
    if score < 0.20:
        return "aligned"
    if score < 0.40:
        return "minor_drift"
    if score < 0.70:
        return "moderate_drift"
    return "severe_derailment"


def _drift_points(dimension_scores: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for dimension in SCORE_DIMENSIONS:
        data = dimension_scores[dimension]
        if float(data.get("score", 0.0)) <= 0:
            continue
        reasons = [str(reason) for reason in data.get("reasons", [])]
        points.append(
            {
                "dimension": dimension,
                "score": data["score"],
                "evidence": "; ".join(reasons) if reasons else "heuristic score above zero",
            }
        )
    return points


def _evidence_used(frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "frame_type": str(frame.get("frame_type", "")),
            "artifact_path": str(frame.get("artifact_path", "")),
            "excerpt_used": _cap(str(frame.get("excerpt", "")), 240),
        }
        for frame in frames
    ]


def _missing_evidence(trace: dict[str, Any]) -> list[dict[str, str]]:
    raw = trace.get("missing_evidence")
    if not isinstance(raw, list):
        raw = trace.get("missing_frames")
    out: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "frame_type": str(item.get("frame_type", "")),
                    "reason": str(item.get("reason", item.get("evidence_status", "missing"))),
                }
            )
    return out


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
    return {word for word in words if word not in _STOPWORDS and not word.isdigit()}


def _allowed_files(text: str) -> set[str]:
    allowed: set[str] = set()
    for match in re.finditer(r"allowed files?\s*[:=]\s*([^\n.;]+)", text, re.IGNORECASE):
        allowed.update(_file_paths(match.group(1)))
    return allowed


def _forbidden_files(text: str) -> set[str]:
    forbidden: set[str] = set()
    for match in re.finditer(r"forbidden files?\s*[:=]\s*([^\n.;]+)", text, re.IGNORECASE):
        forbidden.update(_file_paths(match.group(1)))
    for match in re.finditer(r"do not touch\s+([A-Za-z0-9_./\\-]+)", text, re.IGNORECASE):
        forbidden.update(_file_paths(match.group(1)))
    return forbidden


def _touched_files(text: str) -> set[str]:
    files: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("+++") or stripped.startswith("---"):
            parts = stripped.split()
            if len(parts) >= 2:
                files.update(_file_paths(parts[1].removeprefix("a/").removeprefix("b/")))
    files.update(_file_paths(text))
    return files


def _file_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for raw in re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text.replace("\\", "/")):
        clean = raw.strip("`'\"),.;:")
        if clean in {"a/dev/null", "b/dev/null"}:
            continue
        clean = clean.removeprefix("a/").removeprefix("b/")
        if "/" in clean and not clean.startswith(".agent/"):
            paths.add(clean)
    return paths


def _dimension(score: float, reasons: list[str]) -> dict[str, Any]:
    clipped = min(1.0, max(0.0, float(score)))
    return {"score": round(clipped, 3), "reasons": _dedupe(reasons)}


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "semantic_api_call_performed": False,
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
        "writes_score_artifacts_only": True,
    }


def _blocked_report(trace_path: Path, *, score_id: str | None, created_at: str, message: str) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "score_id": score_id or _default_score_id({}, str(trace_path), created_at),
        "created_at": str(created_at or ""),
        "trace_id": "",
        "trace_path": str(trace_path),
        "source_run_id": "",
        "trace_status": "unreadable",
        "trace_trust_level": "blocked",
        "overall_derailment_score": None,
        "dimension_scores": {name: _dimension(0.0, []) for name in SCORE_DIMENSIONS},
        "dimension_weights": dict(DIMENSION_WEIGHTS),
        "verdict": "insufficient_trace",
        "recommended_next_action": "collect_more_trace_artifacts",
        "recommended_next_phase": "MIRROR.3",
        "frame_coverage": {"available_frame_count": 0, "unknown_artifact_count": 0},
        "detected_drift_points": [],
        "evidence_used": [],
        "missing_evidence": [],
        "claim_action_checks": [{"status": "blocked", "message": "trace contract could not be read"}],
        "validation_gap_checks": [{"status": "blocked", "message": "trace contract could not be read"}],
        "insufficient_reasons": ["trace_contract_unreadable", message],
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def _resolve_trace_path(repo_root: Path, trace_path: str | None) -> Path:
    candidate = Path(trace_path or DEFAULT_TRACE_PATH).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _resolve_output_root(repo_root: Path, output_root: str | None) -> Path:
    candidate = Path(output_root or DEFAULT_OUTPUT_ROOT).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _is_forbidden_trace_path(path: Path) -> bool:
    normalized = [part.lower() for part in path.parts]
    if any(part in {".env", "secrets", "credentials"} for part in normalized):
        return True
    return ".agent" in normalized and "private" in normalized


def _default_score_id(trace: dict[str, Any], trace_path: str, created_at: str) -> str:
    seed = json.dumps(
        {
            "trace_id": trace.get("trace_id", ""),
            "trace_path": str(trace_path or ""),
            "created_at": str(created_at or ""),
        },
        sort_keys=True,
    )
    return "mirror-score-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 22)] + " [excerpt truncated]"


def _score_text(value: Any) -> str:
    if value is None:
        return "not_scored"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


def _md(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _point_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{item.get('dimension')}` score `{_score_text(item.get('score'))}` - {_md(item.get('evidence'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _evidence_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{item.get('frame_type')}` - `{_md(item.get('artifact_path'))}` - {_md(item.get('excerpt_used'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _missing_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{item.get('frame_type')}` - {_md(item.get('reason'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _check_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        f"`{item.get('status')}` - {_md(item.get('message'))}"
        for item in value
        if isinstance(item, dict)
    ]


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
