"""MIRROR.1 - Mirror Tunnel Trace Contract (report-only).

MIRROR.1 reconstructs a bounded, operator-readable trace from existing
artifacts only:

user intent -> Goal Brief / route card -> control prompt -> worker assignment
-> worker reply -> patch/diff/evidence -> validation/benchmark/replay -> final
answer.

The contract records available frames, missing frames, reusable context,
excluded context, trust level, artifact references, and boundaries. It never
infers a missing frame from another artifact and never scores derailment.

This module is stdlib-only. It reads explicit source artifacts and writes only
``mirror_tunnel_trace_contract.json`` / ``mirror_tunnel_trace_contract.md`` when
the writer is called. It does not execute validation, benchmarks, workers, MCP
tools, Docker/subprocess commands, Dream actions, Replay janitor actions,
network calls, database writes, route changes, auth changes, model calls, patch
generation, or patch application.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_trace_contract"
JSON_NAME = "mirror_tunnel_trace_contract.json"
MD_NAME = "mirror_tunnel_trace_contract.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "trace_contract"
DEFAULT_EXCERPT_LIMIT = 1200
MAX_ARTIFACT_CHARS = 65536

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
    "unknown_artifact",
)

TRACE_STATUSES: tuple[str, ...] = (
    "complete_trace",
    "partial_trace",
    "insufficient_evidence",
    "blocked",
)

TRUST_LEVELS: tuple[str, ...] = ("high", "medium", "low", "blocked")

_CANONICAL_MISSING_FRAME_TYPES = FRAME_TYPES[:-1]
_FRAME_RANK = {frame_type: index for index, frame_type in enumerate(FRAME_TYPES)}

_INTENT_FRAMES = {"user_intent", "goal_brief"}
_ACTION_FRAMES = {"worker_assignment", "worker_reply", "patch_or_diff"}
_EVIDENCE_FRAMES = {"validation_evidence", "benchmark_evidence", "replay_evidence"}
_FINAL_FRAMES = {"final_answer"}

_REUSABLE_CONTEXT_ITEMS: tuple[str, ...] = (
    "frame_type",
    "artifact_path",
    "bounded_excerpt",
    "artifact_kind",
    "source_run_id",
    "trace_status",
    "trust_level",
    "available_evidence_summary",
    "missing_evidence_summary",
)

_EXCLUDED_CONTEXT_ITEMS: tuple[str, ...] = (
    "secrets",
    "API keys",
    "tokens",
    "credentials",
    "environment files",
    "raw environment variables",
    "hidden chain-of-thought",
    "unbounded raw artifact text",
    "unreviewed tool outputs beyond capped excerpts",
    "execution handles",
    "worker state",
    "database state",
    "auto-approval state",
    "patch application authority",
    "validation execution authority",
)

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.1 is report-only.",
    "MIRROR.1 reads existing artifacts only.",
    "MIRROR.1 never invents missing frames.",
    "MIRROR.1 records missing frames as missing.",
    "MIRROR.1 preserves artifact paths.",
    "MIRROR.1 caps long text excerpts.",
    "MIRROR.1 does not read secrets or environment files.",
    "MIRROR.1 does not call models.",
    "MIRROR.1 does not apply patches.",
    "MIRROR.1 does not run validation.",
    "MIRROR.1 does not run benchmarks.",
    "MIRROR.1 does not invoke MCP tools.",
    "MIRROR.1 does not launch workers.",
    "MIRROR.1 does not execute Dream actions.",
    "MIRROR.1 does not apply Replay janitor actions.",
    "MIRROR.1 does not use Docker or subprocess.",
    "MIRROR.1 does not contact network services.",
    "MIRROR.1 does not write to a database.",
    "MIRROR.1 does not change route behavior.",
    "MIRROR.1 does not change auth policy.",
    "MIRROR.1 does not score derailment.",
    "MIRROR.1 writes trace artifacts only.",
)

FRAME_SCHEMA: dict[str, Any] = {
    "required_fields": [
        "frame_id",
        "frame_index",
        "frame_type",
        "availability",
        "artifact_path",
        "resolved_artifact_path",
        "artifact_kind",
        "excerpt",
        "excerpt_truncated",
        "classification_reason",
    ],
    "availability_values": ["available", "missing"],
    "frame_type_enum": list(FRAME_TYPES),
    "rules": [
        "Read explicit existing artifacts only.",
        "Never infer a missing frame from another frame.",
        "Record absent canonical frame types under missing_frames.",
        "Preserve operator-supplied artifact paths.",
        "Cap excerpts and mark truncated excerpts.",
        "Block secret, environment, traversal, unreadable, and out-of-root paths.",
    ],
}


def build_mirror_tunnel_trace_contract(
    *,
    repo_path: str = ".",
    source_artifact_paths: list[str] | tuple[str, ...] | None = None,
    source_run_id: str = "",
    trace_id: str | None = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
) -> dict[str, Any]:
    """Build a MIRROR.1 trace contract from explicit existing artifact paths.

    The builder reads files only after path safety checks pass. It performs no
    execution and never searches for extra artifacts.
    """
    repo_root = Path(repo_path or ".").expanduser().resolve()
    raw_paths = [str(path) for path in (source_artifact_paths or [])]
    safe_excerpt_limit = max(0, int(excerpt_limit or 0))

    artifact_references: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []

    for input_index, raw_path in enumerate(raw_paths):
        resolved = _resolve_source_artifact(repo_root, raw_path)
        if not resolved["ok"]:
            blocker = {
                "artifact_path": raw_path,
                "reason": resolved["reason"],
                "message": resolved["message"],
            }
            blockers.append(blocker)
            artifact_references.append(
                {
                    "input_index": input_index,
                    "artifact_path": raw_path,
                    "resolved_artifact_path": resolved.get("resolved_artifact_path", ""),
                    "read_status": "blocked",
                    "block_reason": resolved["reason"],
                    "frame_type": "",
                }
            )
            continue

        path = Path(str(resolved["resolved_artifact_path"]))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            blocker = {
                "artifact_path": raw_path,
                "reason": "unreadable_artifact",
                "message": f"artifact could not be read: {exc}",
            }
            blockers.append(blocker)
            artifact_references.append(
                {
                    "input_index": input_index,
                    "artifact_path": raw_path,
                    "resolved_artifact_path": str(path),
                    "read_status": "blocked",
                    "block_reason": "unreadable_artifact",
                    "frame_type": "",
                }
            )
            continue

        parsed = _parse_json_if_possible(text)
        frame_type, reason = _detect_frame_type(path, parsed)
        excerpt_source = text[:MAX_ARTIFACT_CHARS]
        excerpt, truncated = _excerpt(excerpt_source, safe_excerpt_limit)
        frame = {
            "frame_id": _frame_id(frame_type, raw_path, input_index),
            "frame_index": input_index,
            "frame_type": frame_type,
            "availability": "available",
            "artifact_path": raw_path,
            "resolved_artifact_path": str(path),
            "artifact_kind": _artifact_kind(path),
            "excerpt": excerpt,
            "excerpt_truncated": truncated or len(text) > MAX_ARTIFACT_CHARS,
            "classification_reason": reason,
            "content_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
            "parsed_json": isinstance(parsed, (dict, list)),
        }
        frames.append(frame)
        artifact_references.append(
            {
                "input_index": input_index,
                "artifact_path": raw_path,
                "resolved_artifact_path": str(path),
                "read_status": "read",
                "block_reason": "",
                "frame_type": frame_type,
                "artifact_kind": frame["artifact_kind"],
            }
        )

    ordered_frames = sorted(
        frames,
        key=lambda frame: (_FRAME_RANK.get(str(frame.get("frame_type")), 999), frame["frame_index"]),
    )
    for output_index, frame in enumerate(ordered_frames):
        frame["frame_index"] = output_index

    available_types = {str(frame["frame_type"]) for frame in ordered_frames}
    missing_frames = [
        _missing_frame(frame_type)
        for frame_type in _CANONICAL_MISSING_FRAME_TYPES
        if frame_type not in available_types
    ]
    status = _trace_status(ordered_frames, blockers)
    trust = _trust_level(status)

    report = {
        "report_kind": REPORT_KIND,
        "trace_id": trace_id or _default_trace_id(source_run_id, raw_paths, created_at),
        "created_at": str(created_at or ""),
        "repo_path": str(repo_root),
        "source_run_id": str(source_run_id or ""),
        "source_artifact_paths": list(raw_paths),
        "source_artifacts": artifact_references,
        "status": status,
        "trust_level": trust,
        "frame_schema": FRAME_SCHEMA,
        "frame_type_enum": list(FRAME_TYPES),
        "frame_order": [str(frame["frame_type"]) for frame in ordered_frames],
        "frames": ordered_frames,
        "missing_frames": missing_frames,
        "available_evidence": _available_evidence(ordered_frames),
        "missing_evidence": _missing_evidence(missing_frames),
        "reusable_context": _reusable_context(ordered_frames, status, trust, source_run_id),
        "excluded_context": _excluded_context(blockers),
        "artifact_references": artifact_references,
        "blockers": blockers,
        "excerpt_limit": safe_excerpt_limit,
        "recommended_next_phase": "MIRROR.2",
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }
    return report


def write_mirror_tunnel_trace_contract(
    *,
    repo_path: str = ".",
    source_artifact_paths: list[str] | tuple[str, ...] | None = None,
    source_run_id: str = "",
    trace_id: str | None = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
    output_root: str | None = None,
) -> dict[str, Any]:
    """Build and write the MIRROR.1 JSON + Markdown trace artifacts."""
    report = build_mirror_tunnel_trace_contract(
        repo_path=repo_path,
        source_artifact_paths=source_artifact_paths,
        source_run_id=source_run_id,
        trace_id=trace_id,
        created_at=created_at,
        excerpt_limit=excerpt_limit,
    )
    repo_root = Path(repo_path or ".").expanduser().resolve()
    output = _resolve_output_root(repo_root, output_root)
    if not output["ok"]:
        report["status"] = "blocked"
        report["trust_level"] = "blocked"
        report["blockers"].append(
            {
                "artifact_path": str(output_root or ""),
                "reason": output["reason"],
                "message": output["message"],
            }
        )
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_mirror_tunnel_trace_markdown(report),
        }

    out_dir = Path(str(output["resolved_output_root"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    markdown = render_mirror_tunnel_trace_markdown(report)
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": report["status"] != "blocked",
        "status": report["status"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_mirror_tunnel_trace_markdown(report: dict[str, Any]) -> str:
    """Render a MIRROR.1 trace contract as operator-readable Markdown."""
    lines: list[str] = [
        "# Mirror Tunnel Trace Contract",
        "",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Created at:** `{_md(report.get('created_at'))}`",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Trust level:** `{_md(report.get('trust_level'))}`",
        f"- **Source run id:** `{_md(report.get('source_run_id'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Frame Schema",
        "",
    ]
    schema = report.get("frame_schema") if isinstance(report.get("frame_schema"), dict) else {}
    lines.append("Required fields: " + ", ".join(f"`{_md(field)}`" for field in schema.get("required_fields", [])))
    lines.append("")
    lines.append("Frame type enum: " + ", ".join(f"`{_md(item)}`" for item in report.get("frame_type_enum", [])))
    lines.append("")

    lines.extend(["## Frame Order", ""])
    frame_order = [str(item) for item in report.get("frame_order", [])]
    lines.append(_bullet_list([f"`{item}`" for item in frame_order]) if frame_order else "_None._")
    lines.append("")

    lines.extend(["## Available Frames", ""])
    frames = report.get("frames") if isinstance(report.get("frames"), list) else []
    if frames:
        for frame in frames:
            lines.append(f"### `{_md(frame.get('frame_type'))}`")
            lines.append(f"- Artifact: `{_md(frame.get('artifact_path'))}`")
            lines.append(f"- Kind: `{_md(frame.get('artifact_kind'))}`")
            lines.append(f"- Classification: {_md(frame.get('classification_reason'))}")
            excerpt = _md(frame.get("excerpt"))
            lines.append(f"- Excerpt: {excerpt if excerpt else '(empty)'}")
            lines.append("")
    else:
        lines.append("_None._")
        lines.append("")

    lines.extend(["## Missing Frames", ""])
    missing = report.get("missing_frames") if isinstance(report.get("missing_frames"), list) else []
    lines.append(_bullet_list([f"`{item.get('frame_type')}` - {item.get('reason')}" for item in missing]) if missing else "_None._")
    lines.append("")

    lines.extend(["## Available Evidence", ""])
    lines.append(_bullet_list(_evidence_lines(report.get("available_evidence"))))
    lines.append("")

    lines.extend(["## Missing Evidence", ""])
    lines.append(_bullet_list(_evidence_lines(report.get("missing_evidence"))))
    lines.append("")

    lines.extend(["## Reusable Context", ""])
    reusable = report.get("reusable_context") if isinstance(report.get("reusable_context"), dict) else {}
    lines.append(_md(reusable.get("policy")))
    lines.append("")
    lines.append(_bullet_list([str(item) for item in reusable.get("items", [])]))
    lines.append("")

    lines.extend(["## Excluded Context", ""])
    excluded = report.get("excluded_context") if isinstance(report.get("excluded_context"), dict) else {}
    lines.append(_md(excluded.get("policy")))
    lines.append("")
    lines.append(_bullet_list([str(item) for item in excluded.get("items", [])]))
    lines.append("")

    lines.extend(["## Artifact References", ""])
    refs = report.get("artifact_references") if isinstance(report.get("artifact_references"), list) else []
    if refs:
        for ref in refs:
            status = ref.get("read_status")
            frame_type = ref.get("frame_type") or "(none)"
            lines.append(f"- `{_md(ref.get('artifact_path'))}` - `{_md(status)}` - `{_md(frame_type)}`")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Blockers", ""])
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    if blockers:
        for blocker in blockers:
            lines.append(
                f"- `{_md(blocker.get('artifact_path'))}` - `{_md(blocker.get('reason'))}`: "
                f"{_md(blocker.get('message'))}"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Boundaries", ""])
    lines.append(_bullet_list([str(item) for item in report.get("boundaries", [])]))
    lines.append("")

    lines.extend(["## Guardrails", ""])
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}` = `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def render_mirror_tunnel_trace_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _resolve_source_artifact(repo_root: Path, raw_path: str) -> dict[str, Any]:
    raw = str(raw_path or "").strip()
    if not raw:
        return _blocked("empty_artifact_path", "artifact path is empty")
    if _has_traversal(raw):
        return _blocked("traversal_attempt", "artifact path contains a parent-directory segment")
    if _is_secret_or_env_path(raw):
        return _blocked("secret_or_env_path", "artifact path is a secret, credential, environment, or private path")

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    if _is_secret_or_env_path(str(resolved)):
        return _blocked(
            "secret_or_env_path",
            "artifact path resolves to a secret, credential, environment, or private path",
            resolved_artifact_path=str(resolved),
        )
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return _blocked(
            "forbidden_root",
            "artifact path resolves outside the repository root",
            resolved_artifact_path=str(resolved),
        )
    if not resolved.is_file():
        return _blocked(
            "unreadable_artifact",
            "artifact path does not point to a readable file",
            resolved_artifact_path=str(resolved),
        )
    return {"ok": True, "resolved_artifact_path": str(resolved)}


def _resolve_output_root(repo_root: Path, output_root: str | None) -> dict[str, Any]:
    raw = str(output_root or "").strip()
    candidate = Path(raw).expanduser() if raw else repo_root / DEFAULT_OUTPUT_ROOT
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return {
            "ok": False,
            "reason": "forbidden_output_root",
            "message": "output root must stay inside the repository root",
            "resolved_output_root": str(resolved),
        }
    return {"ok": True, "resolved_output_root": str(resolved)}


def _blocked(reason: str, message: str, *, resolved_artifact_path: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "reason": reason,
        "message": message,
        "resolved_artifact_path": resolved_artifact_path,
    }


def _parse_json_if_possible(text: str) -> Any:
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _detect_frame_type(path: Path, parsed: Any) -> tuple[str, str]:
    lower_path = _lower_path(path)
    name = path.name.lower()
    parts = _parts(str(path))
    keys = _json_keys(parsed)

    if _has_any(lower_path, ("benchmark", "benchmark_report")) or keys & {"benchmark_summary", "benchmark_report", "case_results"}:
        return "benchmark_evidence", "path or JSON keys indicate benchmark evidence"
    if _has_any(lower_path, ("replay", "replay_compare", "replay_recorder")) or keys & {"replay_id", "replay_summary", "replay_evidence"}:
        return "replay_evidence", "path or JSON keys indicate replay evidence"
    if _has_any(lower_path, ("validation", "pytest", "test_report", "safe_validation")) or keys & {
        "validation_command",
        "validation_commands",
        "validation_output",
        "validation_summary",
    }:
        return "validation_evidence", "path or JSON keys indicate validation evidence"
    if path.suffix.lower() in {".diff", ".patch"} or _has_any(name, ("patch", "diff")) or keys & {
        "patch",
        "patch_candidate",
        "patch_plan",
        "diff",
        "patched_snippet",
        "target_snippet",
    }:
        return "patch_or_diff", "path, suffix, or JSON keys indicate a patch/diff"
    if _has_any(lower_path, ("final_answer", "answer_summary", "final_response")) or keys & {
        "final_answer",
        "final_response",
        "answer_summary",
    }:
        return "final_answer", "path or JSON keys indicate a final answer"
    if _has_any(lower_path, ("worker_assignment", "assignment.json")) or {"assignment_id", "worker_role"} <= keys:
        return "worker_assignment", "path or JSON keys indicate a worker assignment"
    if (
        _has_any(lower_path, ("worker_reply", "worker_result", "worker_run", "result_review"))
        or ("workers" in parts and name.startswith("reply"))
        or keys & {
        "worker_reply",
        "worker_result",
        "result_text",
        "reply",
        }
    ):
        return "worker_reply", "path or JSON keys indicate a worker reply"
    if _has_any(lower_path, ("control_prompt", "prompt_payload")) or keys & {"control_prompt", "prompt_text"}:
        return "control_prompt", "path or JSON keys indicate a control prompt"
    if _has_any(lower_path, ("mode_decision", "route_card", "mixed_mode_intent")) or keys & {
        "mode_decision_id",
        "recommended_mode",
        "route_card",
    }:
        return "mode_decision", "path or JSON keys indicate a mode decision or route card"
    if _has_any(lower_path, ("goal_brief", "4w1h")) or keys & {"goal_brief_id", "problem_statement", "why_now"}:
        return "goal_brief", "path or JSON keys indicate a Goal Brief"
    if _has_any(lower_path, ("user_intent", "operator_intent")) or "intent" in parts:
        return "user_intent", "path indicates user/operator intent"
    return "unknown_artifact", "artifact did not match a known MIRROR.1 frame type"


def _trace_status(frames: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> str:
    if blockers:
        return "blocked"
    known_types = {str(frame.get("frame_type")) for frame in frames if frame.get("frame_type") != "unknown_artifact"}
    if not known_types:
        return "insufficient_evidence"
    has_intent = bool(known_types & _INTENT_FRAMES)
    has_action = bool(known_types & _ACTION_FRAMES)
    has_evidence = bool(known_types & _EVIDENCE_FRAMES)
    has_final = bool(known_types & _FINAL_FRAMES)
    if has_intent and has_action and has_evidence and has_final:
        return "complete_trace"
    if len(known_types) <= 1:
        return "insufficient_evidence"
    return "partial_trace"


def _trust_level(status: str) -> str:
    if status == "complete_trace":
        return "high"
    if status == "partial_trace":
        return "medium"
    if status == "blocked":
        return "blocked"
    return "low"


def _available_evidence(frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "frame_type": str(frame.get("frame_type", "")),
            "artifact_path": str(frame.get("artifact_path", "")),
            "artifact_kind": str(frame.get("artifact_kind", "")),
            "evidence_status": "available",
        }
        for frame in frames
    ]


def _missing_evidence(missing_frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "frame_type": str(frame.get("frame_type", "")),
            "evidence_status": "missing",
            "reason": str(frame.get("reason", "")),
        }
        for frame in missing_frames
    ]


def _reusable_context(
    frames: list[dict[str, Any]],
    status: str,
    trust_level: str,
    source_run_id: str,
) -> dict[str, Any]:
    return {
        "policy": "Only bounded excerpts, frame metadata, and safe artifact references are reusable.",
        "items": list(_REUSABLE_CONTEXT_ITEMS),
        "source_run_id": str(source_run_id or ""),
        "status": status,
        "trust_level": trust_level,
        "frame_context": [
            {
                "frame_type": str(frame.get("frame_type", "")),
                "artifact_path": str(frame.get("artifact_path", "")),
                "excerpt": str(frame.get("excerpt", "")),
            }
            for frame in frames
        ],
    }


def _excluded_context(blockers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "policy": "Secrets, hidden reasoning, execution authority, and unbounded raw output are never carried forward.",
        "items": list(_EXCLUDED_CONTEXT_ITEMS),
        "blocked_artifacts": list(blockers),
    }


def _missing_frame(frame_type: str) -> dict[str, Any]:
    return {
        "frame_id": f"missing-{frame_type}",
        "frame_index": _FRAME_RANK.get(frame_type, 0),
        "frame_type": frame_type,
        "availability": "missing",
        "artifact_path": "",
        "resolved_artifact_path": "",
        "artifact_kind": "",
        "excerpt": "",
        "excerpt_truncated": False,
        "classification_reason": "",
        "reason": "no source artifact matched this frame type",
    }


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "reads_existing_artifacts_only": True,
        "writes_trace_artifacts_only": True,
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
        "derailment_scored": False,
    }


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".diff", ".patch"}:
        return "diff"
    if suffix in {".txt", ".log"}:
        return "text"
    return suffix.lstrip(".") or "unknown"


def _excerpt(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) <= limit:
        return normalized, False
    marker = "\n[excerpt truncated]"
    if limit <= len(marker):
        return normalized[:limit], True
    return normalized[: limit - len(marker)] + marker, True


def _frame_id(frame_type: str, raw_path: str, input_index: int) -> str:
    digest = hashlib.sha1(f"{frame_type}:{raw_path}:{input_index}".encode("utf-8")).hexdigest()[:10]
    return f"{frame_type}-{digest}"


def _default_trace_id(source_run_id: str, raw_paths: list[str], created_at: str) -> str:
    seed = json.dumps(
        {"source_run_id": source_run_id, "source_artifact_paths": raw_paths, "created_at": created_at},
        sort_keys=True,
    )
    return "mirror-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _json_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            if isinstance(item, dict):
                keys.update(str(child_key) for child_key in item.keys())
    elif isinstance(value, list):
        for item in value[:5]:
            if isinstance(item, dict):
                keys.update(str(key) for key in item.keys())
    return keys


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_traversal(path: str) -> bool:
    return any(part == ".." for part in _parts(path))


def _is_secret_or_env_path(path: str) -> bool:
    parts = _parts(path)
    lowered = [part.lower() for part in parts]
    for part in lowered:
        if part == ".git":
            return True
        if part == "env" or part == ".env" or part.startswith(".env.") or part.endswith(".env"):
            return True
        if part in {"secret", "secrets", "credential", "credentials"}:
            return True
    for index, part in enumerate(lowered[:-1]):
        if part == ".agent" and lowered[index + 1] == "private":
            return True
    return False


def _parts(path: str) -> list[str]:
    return [
        part
        for part in str(path).replace("\\", "/").split("/")
        if part not in {"", "."} and not part.endswith(":")
    ]


def _lower_path(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def _md(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "_None._"
    return "\n".join(f"- {item}" for item in items)


def _evidence_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        frame_type = item.get("frame_type", "")
        status = item.get("evidence_status", "")
        artifact = item.get("artifact_path", "")
        reason = item.get("reason", "")
        if artifact:
            lines.append(f"`{frame_type}` - `{status}` - `{artifact}`")
        elif reason:
            lines.append(f"`{frame_type}` - `{status}` - {reason}")
        else:
            lines.append(f"`{frame_type}` - `{status}`")
    return lines
