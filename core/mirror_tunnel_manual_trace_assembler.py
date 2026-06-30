"""MIRROR.5 - Manual Trace Assembler (report-only).

MIRROR.5 takes explicit operator-provided artifact paths and assembles a
MIRROR.1-compatible trace contract with real frame types. It is a manual bridge
only: no live runtime wiring, automatic tracing, model calls, patch apply,
validation or benchmark execution, MCP/worker launch, Docker/subprocess,
network, database writes, route/auth changes, or execution blocking.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.mirror_tunnel_trace_contract import (
    DEFAULT_EXCERPT_LIMIT,
    FRAME_TYPES,
    JSON_NAME,
    MAX_ARTIFACT_CHARS,
    MD_NAME,
    REPORT_KIND,
    render_mirror_tunnel_trace_json,
    render_mirror_tunnel_trace_markdown,
)


DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "manual_trace"

TRACE_STATUSES: tuple[str, ...] = (
    "complete_trace",
    "partial_trace",
    "insufficient_evidence",
    "blocked",
)

MANUAL_TRUST_LEVELS: tuple[str, ...] = (
    "user_provided",
    "generated_artifact",
    "validation_artifact",
    "benchmark_artifact",
    "replay_artifact",
    "unknown",
)

FRAME_INPUTS: tuple[dict[str, str], ...] = (
    {"source_key": "user_intent_file", "frame_type": "user_intent", "trust_level": "user_provided"},
    {"source_key": "goal_brief_json", "frame_type": "goal_brief", "trust_level": "generated_artifact"},
    {"source_key": "mode_decision_json", "frame_type": "mode_decision", "trust_level": "generated_artifact"},
    {"source_key": "control_prompt_file", "frame_type": "control_prompt", "trust_level": "generated_artifact"},
    {"source_key": "worker_assignment_json", "frame_type": "worker_assignment", "trust_level": "generated_artifact"},
    {"source_key": "worker_reply_file", "frame_type": "worker_reply", "trust_level": "generated_artifact"},
    {"source_key": "patch_json", "frame_type": "patch_or_diff", "trust_level": "generated_artifact"},
    {"source_key": "diff_file", "frame_type": "patch_or_diff", "trust_level": "generated_artifact"},
    {"source_key": "validation_json", "frame_type": "validation_evidence", "trust_level": "validation_artifact"},
    {"source_key": "benchmark_json", "frame_type": "benchmark_evidence", "trust_level": "benchmark_artifact"},
    {"source_key": "replay_json", "frame_type": "replay_evidence", "trust_level": "replay_artifact"},
    {"source_key": "final_answer_file", "frame_type": "final_answer", "trust_level": "generated_artifact"},
)

_INPUT_BY_KEY = {item["source_key"]: item for item in FRAME_INPUTS}
_CANONICAL_FRAME_TYPES = tuple(frame_type for frame_type in FRAME_TYPES if frame_type != "unknown_artifact")
_FRAME_RANK = {frame_type: index for index, frame_type in enumerate(FRAME_TYPES)}
_EVIDENCE_TYPES = {"validation_evidence", "benchmark_evidence", "replay_evidence"}
_ACTION_OR_FINAL_TYPES = {"patch_or_diff", "final_answer"}

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.5 Manual Trace Assembler is report-only.",
    "MIRROR.5 reads explicit operator-provided artifact paths only.",
    "MIRROR.5 maps known CLI inputs to real MIRROR.1 frame types.",
    "MIRROR.5 records omitted optional inputs as missing evidence.",
    "MIRROR.5 preserves artifact paths.",
    "MIRROR.5 caps loaded text and JSON excerpts.",
    "MIRROR.5 rejects traversal, secret, environment, key, token, unreadable, and out-of-root paths.",
    "MIRROR.5 does not call models.",
    "MIRROR.5 does not apply patches.",
    "MIRROR.5 does not run validation.",
    "MIRROR.5 does not run benchmarks.",
    "MIRROR.5 does not invoke MCP tools.",
    "MIRROR.5 does not launch workers.",
    "MIRROR.5 does not execute Dream actions.",
    "MIRROR.5 does not apply Replay janitor actions.",
    "MIRROR.5 does not use Docker or subprocess.",
    "MIRROR.5 does not contact network services.",
    "MIRROR.5 does not write to a database.",
    "MIRROR.5 does not change route behavior.",
    "MIRROR.5 does not change auth policy.",
    "MIRROR.5 does not enable automatic live tracing.",
    "MIRROR.5 writes assembled trace artifacts only.",
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
        "source_key",
        "trust_level",
        "excerpt",
        "excerpt_truncated",
        "classification_reason",
    ],
    "availability_values": ["available", "missing"],
    "frame_type_enum": list(FRAME_TYPES),
    "manual_trust_level_enum": list(MANUAL_TRUST_LEVELS),
    "rules": [
        "Read explicit operator-provided artifacts only.",
        "Map known input flags to fixed frame types.",
        "Never infer an omitted optional frame from another artifact.",
        "Record omitted optional inputs under missing_evidence.",
        "Preserve operator-supplied artifact paths.",
        "Cap excerpts and mark truncation.",
        "Block secret, token, environment, traversal, unreadable, and out-of-root paths.",
    ],
}


def build_manual_mirror_tunnel_trace(
    *,
    repo_path: str = ".",
    artifact_paths: dict[str, str | None] | None = None,
    trace_id: str | None = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
) -> dict[str, Any]:
    """Build a MIRROR.1-compatible trace from explicit manual artifact paths."""
    repo_root = Path(repo_path or ".").expanduser().resolve()
    raw_artifacts = dict(artifact_paths or {})
    safe_excerpt_limit = max(0, int(excerpt_limit or 0))
    trace = trace_id or _default_trace_id(raw_artifacts, created_at)

    blockers: list[dict[str, str]] = []
    frames: list[dict[str, Any]] = []
    artifact_references: list[dict[str, Any]] = []

    for input_index, (source_key, raw_path) in enumerate(_provided_artifacts(raw_artifacts)):
        spec = _INPUT_BY_KEY.get(source_key, {"source_key": source_key, "frame_type": "unknown_artifact", "trust_level": "unknown"})
        resolved = _resolve_source_artifact(repo_root, str(raw_path or ""))
        if not resolved["ok"]:
            blocker = {
                "source_key": source_key,
                "artifact_path": str(raw_path or ""),
                "reason": str(resolved["reason"]),
                "message": str(resolved["message"]),
            }
            blockers.append(blocker)
            artifact_references.append(_artifact_reference(input_index, source_key, raw_path, resolved, "blocked", ""))
            continue

        path = Path(str(resolved["resolved_artifact_path"]))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            blocker = {
                "source_key": source_key,
                "artifact_path": str(raw_path or ""),
                "reason": "unreadable_artifact",
                "message": f"artifact could not be read: {exc}",
            }
            blockers.append(blocker)
            resolved = {"ok": False, "reason": "unreadable_artifact", "resolved_artifact_path": str(path)}
            artifact_references.append(_artifact_reference(input_index, source_key, raw_path, resolved, "blocked", ""))
            continue

        frame_type = str(spec["frame_type"])
        trust_level = str(spec["trust_level"])
        excerpt, truncated = _excerpt(text[:MAX_ARTIFACT_CHARS], safe_excerpt_limit)
        frame = {
            "frame_id": _frame_id(trace, source_key, frame_type, input_index),
            "frame_index": input_index,
            "frame_type": frame_type,
            "availability": "available",
            "artifact_path": str(raw_path or ""),
            "resolved_artifact_path": str(path),
            "artifact_kind": _artifact_kind(path),
            "source_key": source_key,
            "trust_level": trust_level,
            "excerpt": excerpt,
            "excerpt_truncated": truncated or len(text) > MAX_ARTIFACT_CHARS,
            "classification_reason": _classification_reason(source_key, frame_type),
            "content_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
            "parsed_json": _looks_like_json(text),
        }
        frames.append(frame)
        artifact_references.append(_artifact_reference(input_index, source_key, raw_path, resolved, "read", frame_type, frame["artifact_kind"]))

    ordered_frames = sorted(frames, key=lambda frame: (_FRAME_RANK.get(str(frame["frame_type"]), 999), frame["frame_index"]))
    for frame_index, frame in enumerate(ordered_frames):
        frame["frame_index"] = frame_index

    available_types = {str(frame["frame_type"]) for frame in ordered_frames}
    missing_frames = [_missing_frame(frame_type) for frame_type in _CANONICAL_FRAME_TYPES if frame_type not in available_types]
    missing_evidence = _missing_evidence(raw_artifacts, missing_frames)
    status = _trace_status(ordered_frames, blockers)
    trust = _trace_trust_level(status)

    return {
        "report_kind": REPORT_KIND,
        "assembly_method": "manual_trace_assembler",
        "trace_id": trace,
        "created_at": str(created_at or ""),
        "repo_path": str(repo_root),
        "source_run_id": "",
        "source_artifact_paths": [str(value or "") for _, value in _provided_artifacts(raw_artifacts)],
        "source_artifacts": artifact_references,
        "status": status,
        "trust_level": trust,
        "frame_schema": FRAME_SCHEMA,
        "frame_type_enum": list(FRAME_TYPES),
        "frame_order": [str(frame["frame_type"]) for frame in ordered_frames],
        "frames": ordered_frames,
        "missing_frames": missing_frames,
        "available_evidence": _available_evidence(ordered_frames),
        "missing_evidence": missing_evidence,
        "reusable_context": _reusable_context(ordered_frames, status, trust),
        "excluded_context": _excluded_context(blockers),
        "artifact_references": artifact_references,
        "blockers": blockers,
        "excerpt_limit": safe_excerpt_limit,
        "recommended_next_phase": "MIRROR.2",
        "boundaries": list(BOUNDARIES),
        "guardrails": _guardrails(),
    }


def write_manual_mirror_tunnel_trace(
    *,
    repo_path: str = ".",
    artifact_paths: dict[str, str | None] | None = None,
    trace_id: str | None = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Build and write manual MIRROR.1-compatible trace JSON + Markdown."""
    report = build_manual_mirror_tunnel_trace(
        repo_path=repo_path,
        artifact_paths=artifact_paths,
        trace_id=trace_id,
        created_at=created_at,
        excerpt_limit=excerpt_limit,
    )
    repo_root = Path(repo_path or ".").expanduser().resolve()
    try:
        out_dir = _resolve_output_dir(repo_root, output_dir, str(report["trace_id"]))
    except ValueError as exc:
        report["status"] = "blocked"
        report["trust_level"] = "blocked"
        report["blockers"].append(
            {
                "source_key": "output_dir",
                "artifact_path": str(output_dir or DEFAULT_OUTPUT_DIR),
                "reason": _block_reason_from_message(str(exc)),
                "message": str(exc),
            }
        )
        return {
            "ok": False,
            "status": "blocked",
            "json_path": "",
            "md_path": "",
            "report": report,
            "markdown": render_manual_mirror_tunnel_trace_markdown(report),
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    markdown = render_manual_mirror_tunnel_trace_markdown(report)
    json_path.write_text(render_manual_mirror_tunnel_trace_json(report), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "ok": report["status"] != "blocked",
        "status": report["status"],
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "markdown": markdown,
    }


def render_manual_mirror_tunnel_trace_json(report: dict[str, Any]) -> str:
    return render_mirror_tunnel_trace_json(report)


def render_manual_mirror_tunnel_trace_markdown(report: dict[str, Any]) -> str:
    return render_mirror_tunnel_trace_markdown(report)


def _provided_artifacts(raw_artifacts: dict[str, str | None]) -> list[tuple[str, str | None]]:
    ordered: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for spec in FRAME_INPUTS:
        source_key = spec["source_key"]
        if raw_artifacts.get(source_key):
            ordered.append((source_key, raw_artifacts[source_key]))
            seen.add(source_key)
    for source_key in sorted(raw_artifacts):
        if source_key not in seen and raw_artifacts.get(source_key):
            ordered.append((source_key, raw_artifacts[source_key]))
    return ordered


def _resolve_source_artifact(repo_root: Path, raw_path: str) -> dict[str, Any]:
    raw = str(raw_path or "").strip()
    if not raw:
        return _blocked("empty_artifact_path", "artifact path is empty")
    if _has_traversal(raw):
        return _blocked("traversal_attempt", "artifact path contains a parent-directory segment")
    if _is_secret_or_env_path(raw):
        return _blocked("secret_or_env_path", "artifact path is a secret, token, credential, environment, key, or private path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    if _is_secret_or_env_path(str(resolved)):
        return _blocked(
            "secret_or_env_path",
            "artifact path resolves to a secret, token, credential, environment, key, or private path",
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


def _resolve_output_dir(repo_root: Path, output_dir: str | None, trace_id: str) -> Path:
    safe_trace_id = _safe_trace_id(trace_id)
    raw = str(output_dir or DEFAULT_OUTPUT_DIR).strip()
    if _has_traversal(raw):
        raise ValueError("traversal_attempt: output directory contains a parent-directory segment")
    if _is_secret_or_env_path(raw):
        raise ValueError("secret_or_env_path: output directory is a secret/env/token/key path")
    base = Path(raw).expanduser()
    if not base.is_absolute():
        base = repo_root / base
    resolved = (base / safe_trace_id).resolve()
    if _is_secret_or_env_path(str(resolved)):
        raise ValueError("secret_or_env_path: output directory resolves to a secret/env/token/key path")
    try:
        resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("forbidden_root: output directory resolves outside the repository root") from exc
    return resolved


def _safe_trace_id(trace_id: str) -> str:
    raw = str(trace_id or "").strip()
    if not raw:
        raise ValueError("empty_trace_id: trace id is empty")
    if _has_traversal(raw) or "/" in raw or "\\" in raw:
        raise ValueError("traversal_attempt: trace id cannot contain path separators")
    if _is_secret_or_env_path(raw):
        raise ValueError("secret_or_env_path: trace id cannot look like a secret/env/token/key path")
    return raw


def _blocked(reason: str, message: str, *, resolved_artifact_path: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "message": message, "resolved_artifact_path": resolved_artifact_path}


def _artifact_reference(
    input_index: int,
    source_key: str,
    raw_path: str | None,
    resolved: dict[str, Any],
    read_status: str,
    frame_type: str,
    artifact_kind: str = "",
) -> dict[str, Any]:
    return {
        "input_index": input_index,
        "source_key": source_key,
        "artifact_path": str(raw_path or ""),
        "resolved_artifact_path": str(resolved.get("resolved_artifact_path", "")),
        "read_status": read_status,
        "block_reason": "" if read_status == "read" else str(resolved.get("reason", "")),
        "frame_type": frame_type,
        "artifact_kind": artifact_kind,
    }


def _missing_frame(frame_type: str) -> dict[str, str]:
    return {
        "frame_type": frame_type,
        "availability": "missing",
        "artifact_path": "",
        "reason": "no explicit manual artifact path was provided for this frame type",
    }


def _missing_evidence(raw_artifacts: dict[str, str | None], missing_frames: list[dict[str, str]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for spec in FRAME_INPUTS:
        source_key = spec["source_key"]
        if not raw_artifacts.get(source_key):
            entries.append(
                {
                    "source_key": source_key,
                    "frame_type": spec["frame_type"],
                    "evidence_status": "missing",
                    "reason": "optional manual artifact path was not provided",
                }
            )
    present_frame_types = {item["frame_type"] for item in entries}
    for frame in missing_frames:
        frame_type = frame["frame_type"]
        if frame_type not in present_frame_types:
            entries.append(
                {
                    "source_key": "",
                    "frame_type": frame_type,
                    "evidence_status": "missing",
                    "reason": frame["reason"],
                }
            )
    return entries


def _available_evidence(frames: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "source_key": str(frame.get("source_key", "")),
            "frame_type": str(frame.get("frame_type", "")),
            "artifact_path": str(frame.get("artifact_path", "")),
            "artifact_kind": str(frame.get("artifact_kind", "")),
            "trust_level": str(frame.get("trust_level", "")),
            "evidence_status": "available",
        }
        for frame in frames
    ]


def _trace_status(frames: list[dict[str, Any]], blockers: list[dict[str, str]]) -> str:
    if blockers:
        return "blocked"
    meaningful_types = {str(frame.get("frame_type", "")) for frame in frames if frame.get("frame_type") != "unknown_artifact"}
    if len(meaningful_types) < 2 or "user_intent" not in meaningful_types:
        return "insufficient_evidence"
    if meaningful_types & _ACTION_OR_FINAL_TYPES and meaningful_types & _EVIDENCE_TYPES:
        return "complete_trace"
    return "partial_trace"


def _trace_trust_level(status: str) -> str:
    if status == "complete_trace":
        return "high"
    if status == "partial_trace":
        return "medium"
    if status == "blocked":
        return "blocked"
    return "low"


def _reusable_context(frames: list[dict[str, Any]], status: str, trust_level: str) -> dict[str, Any]:
    return {
        "policy": "Reusable context is limited to explicit manual frame metadata and capped excerpts.",
        "items": [
            "frame_type",
            "source_key",
            "artifact_path",
            "artifact_kind",
            "trust_level",
            "capped_excerpt",
            "trace_status",
            "available_evidence_summary",
            "missing_evidence_summary",
        ],
        "frame_count": len(frames),
        "trace_status": status,
        "trace_trust_level": trust_level,
    }


def _excluded_context(blockers: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "policy": "Excluded context is never read or reused by the manual assembler.",
        "items": [
            "secrets",
            "API keys",
            "tokens",
            "credentials",
            "environment files",
            "private agent files",
            "key material",
            "raw environment variables",
            "hidden chain-of-thought",
            "unbounded raw artifact text",
            "execution handles",
            "worker state",
            "database state",
            "patch application authority",
            "validation execution authority",
            "automatic live tracing hooks",
        ],
        "blocked_artifact_count": len(blockers),
    }


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
        "automatic_live_tracing_enabled": False,
        "automatic_mirror_tracing_enabled": False,
        "writes_assembled_trace_artifacts_only": True,
    }


def _classification_reason(source_key: str, frame_type: str) -> str:
    if frame_type == "unknown_artifact":
        return f"unknown manual source key {source_key!r}; preserving as unknown_artifact"
    return f"explicit manual source key {source_key!r} maps to {frame_type}"


def _excerpt(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix:
        return suffix
    return "text"


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "[{":
        return False
    try:
        json.loads(text)
    except (TypeError, ValueError):
        return False
    return True


def _frame_id(trace_id: str, source_key: str, frame_type: str, input_index: int) -> str:
    seed = json.dumps(
        {"trace_id": trace_id, "source_key": source_key, "frame_type": frame_type, "input_index": input_index},
        sort_keys=True,
    )
    return "manual-frame-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _default_trace_id(raw_artifacts: dict[str, str | None], created_at: str) -> str:
    seed = json.dumps({"artifact_paths": raw_artifacts, "created_at": str(created_at or "")}, sort_keys=True)
    return "manual-trace-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _has_traversal(raw_path: str) -> bool:
    parts = str(raw_path or "").replace("\\", "/").split("/")
    return any(part == ".." for part in parts)


def _is_secret_or_env_path(raw_path: str) -> bool:
    normal = str(raw_path or "").replace("\\", "/").lower()
    parts = [part for part in normal.split("/") if part]
    name = parts[-1] if parts else ""
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


def _block_reason_from_message(message: str) -> str:
    for reason in ("traversal_attempt", "secret_or_env_path", "forbidden_root", "empty_trace_id"):
        if message.startswith(reason):
            return reason
    return "blocked_output_dir"
