"""MIRROR.7 - Shadow Live Trace Writer.

This module writes passive Mirror Tunnel trace artifacts only when explicitly
enabled through ``MIRROR_TUNNEL_SHADOW_TRACE_ENABLED``. The default is off.

It uses only data supplied by an existing caller. It does not call models,
change prompts, apply patches, run validation, run benchmarks, invoke tools,
launch workers, execute Dream or Replay actions, use Docker, contact the
network, write to a database, change route/auth behavior, block execution,
score derailment, or run claim-vs-diff checks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ENV_FLAG = "MIRROR_TUNNEL_SHADOW_TRACE_ENABLED"
REPORT_KIND = "mirror_tunnel_shadow_live_trace"
JSON_NAME = "mirror_tunnel_trace_contract.json"
MD_NAME = "mirror_tunnel_trace_contract.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "live_traces"
DEFAULT_EXCERPT_LIMIT = 1200
RECOMMENDED_NEXT_PHASE = "MIRROR.8"

STATUS_LIVE_TRACE_WRITTEN = "live_trace_written"
STATUS_DISABLED = "disabled"
STATUS_SKIPPED_NO_RUN_ID = "skipped_no_run_id"
STATUS_SKIPPED_INSUFFICIENT_CONTEXT = "skipped_insufficient_context"
STATUS_BLOCKED = "blocked"

LIVE_FRAME_TYPES: tuple[str, ...] = (
    "user_intent",
    "control_prompt",
    "patch_or_diff",
    "validation_evidence",
    "benchmark_evidence",
    "replay_evidence",
    "final_answer",
)

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.7 is default-off.",
    "MIRROR.7 is shadow-only.",
    "MIRROR.7 writes passive trace artifacts only.",
    "MIRROR.7 uses only data already provided by the existing run path.",
    "MIRROR.7 never reads environment files or secrets.",
    "MIRROR.7 caps all excerpts.",
    "MIRROR.7 records unavailable frames as missing evidence.",
    "MIRROR.7 does not call models.",
    "MIRROR.7 does not change prompts.",
    "MIRROR.7 does not apply patches.",
    "MIRROR.7 does not run validation.",
    "MIRROR.7 does not run benchmarks.",
    "MIRROR.7 does not invoke MCP tools.",
    "MIRROR.7 does not launch workers.",
    "MIRROR.7 does not execute Dream actions.",
    "MIRROR.7 does not apply Replay janitor actions.",
    "MIRROR.7 does not use Docker or subprocess.",
    "MIRROR.7 does not contact network services.",
    "MIRROR.7 does not write to a database.",
    "MIRROR.7 does not change route behavior.",
    "MIRROR.7 does not change auth policy.",
    "MIRROR.7 does not block execution.",
    "MIRROR.7 does not score derailment during a run.",
    "MIRROR.7 does not run claim-vs-diff checks during a run.",
)

_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|secret|credential)\b\s*[:=]\s*\S+"
)
_SECRET_KEY_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "auth_token",
    "credential",
    "credentials",
    "password",
    "passwd",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}
_SECRET_PATH_PARTS = {
    ".env",
    ".agent/private",
    "credentials",
    "secrets",
}


def is_shadow_trace_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return true only for explicit truthy flag values.

    This reads the process environment mapping only; it never reads ``.env`` or
    any other file.
    """
    source = env if env is not None else os.environ
    return str(source.get(ENV_FLAG, "")).strip().lower() in _TRUE_VALUES


def build_shadow_live_trace(
    *,
    run_id: str = "",
    user_intent: Any = None,
    control_prompt: Any = None,
    patch_or_diff: Any = None,
    validation_evidence: Any = None,
    benchmark_evidence: Any = None,
    replay_evidence: Any = None,
    final_answer: Any = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
    boundary: str = "web.runner.run_agent_web.final_result",
) -> dict[str, Any]:
    """Build a passive trace object from values already held by the caller."""
    safe_created = str(created_at or _utc_now())
    safe_limit = max(0, int(excerpt_limit or 0))
    safe_run_id, run_id_errors = _validate_run_id(run_id)
    blocked_reasons = list(run_id_errors)

    frame_values = {
        "user_intent": user_intent,
        "control_prompt": control_prompt,
        "patch_or_diff": patch_or_diff,
        "validation_evidence": validation_evidence,
        "benchmark_evidence": benchmark_evidence,
        "replay_evidence": replay_evidence,
        "final_answer": final_answer,
    }

    frames: list[dict[str, Any]] = []
    missing_evidence: list[dict[str, str]] = []
    for frame_index, frame_type in enumerate(LIVE_FRAME_TYPES):
        frame, missing, blockers = _build_frame(
            frame_type=frame_type,
            value=frame_values.get(frame_type),
            frame_index=frame_index,
            run_id=safe_run_id or str(run_id or ""),
            excerpt_limit=safe_limit,
        )
        blocked_reasons.extend(blockers)
        frames.append(frame)
        if missing:
            missing_evidence.append(missing)

    available_frames = [
        frame
        for frame in frames
        if frame.get("availability") == "available"
    ]
    status = _trace_status(
        run_id=str(run_id or ""),
        blocked_reasons=blocked_reasons,
        available_count=len(available_frames),
    )
    trace_id = _trace_id(safe_run_id or str(run_id or ""), safe_created, frames)

    return {
        "report_kind": REPORT_KIND,
        "enabled": True,
        "status": status,
        "trace_id": trace_id,
        "run_id": safe_run_id,
        "created_at": safe_created,
        "frames": frames,
        "missing_evidence": missing_evidence,
        "blocked_reasons": _dedupe(blocked_reasons),
        "artifact_paths": {},
        "boundaries": list(BOUNDARIES),
        "boundary": str(boundary or ""),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "excerpt_limit": safe_limit,
        "guardrails": _guardrails(),
    }


def write_shadow_live_trace(
    *,
    trace: dict[str, Any],
    repo_path: str | Path = ".",
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write JSON and Markdown artifacts for a live shadow trace."""
    report = dict(trace)
    repo = Path(repo_path or ".").expanduser().resolve()
    out_root, output_errors = _resolve_output_root(repo, output_root)
    run_id = str(report.get("run_id") or "")
    safe_run_id, run_id_errors = _validate_run_id(run_id)
    blocked = _dedupe(list(report.get("blocked_reasons") or []) + output_errors + run_id_errors)
    if blocked or out_root is None:
        report["status"] = STATUS_BLOCKED
        report["blocked_reasons"] = blocked or ["trace output root is unavailable"]
        report["artifact_paths"] = {}
        return report

    out_dir = (out_root / safe_run_id).resolve()
    try:
        out_dir.relative_to(out_root.resolve())
    except ValueError:
        report["status"] = STATUS_BLOCKED
        report["blocked_reasons"] = _dedupe(blocked + ["run_id output path escapes live trace root"])
        report["artifact_paths"] = {}
        return report

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    artifact_paths = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    report["status"] = STATUS_LIVE_TRACE_WRITTEN
    report["artifact_paths"] = artifact_paths
    json_path.write_text(_json(report), encoding="utf-8")
    md_path.write_text(render_shadow_live_trace_markdown(report), encoding="utf-8")
    return report


def maybe_write_shadow_live_trace(
    *,
    repo_path: str | Path = ".",
    run_id: str = "",
    user_intent: Any = None,
    control_prompt: Any = None,
    patch_or_diff: Any = None,
    validation_evidence: Any = None,
    benchmark_evidence: Any = None,
    replay_evidence: Any = None,
    final_answer: Any = None,
    output_root: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str = "",
    excerpt_limit: int = DEFAULT_EXCERPT_LIMIT,
    boundary: str = "web.runner.run_agent_web.final_result",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Best-effort live trace writer.

    Ordinary trace failures are converted into skipped/blocked trace results
    and are never raised into the caller's run path.
    """
    if not is_shadow_trace_enabled(env):
        return _attach_metadata(
            metadata,
            _base_result(
                enabled=False,
                status=STATUS_DISABLED,
                run_id=str(run_id or ""),
                boundary=boundary,
            ),
        )

    try:
        trace = build_shadow_live_trace(
            run_id=run_id,
            user_intent=user_intent,
            control_prompt=control_prompt,
            patch_or_diff=patch_or_diff,
            validation_evidence=validation_evidence,
            benchmark_evidence=benchmark_evidence,
            replay_evidence=replay_evidence,
            final_answer=final_answer,
            created_at=created_at,
            excerpt_limit=excerpt_limit,
            boundary=boundary,
        )
        if trace["status"] != STATUS_LIVE_TRACE_WRITTEN:
            return _attach_metadata(metadata, trace)
        written = write_shadow_live_trace(
            trace=trace,
            repo_path=repo_path,
            output_root=output_root,
        )
        return _attach_metadata(metadata, written)
    except Exception as exc:
        return _attach_metadata(
            metadata,
            _base_result(
                enabled=True,
                status=STATUS_BLOCKED,
                run_id=str(run_id or ""),
                boundary=boundary,
                blocked_reasons=[f"trace write failed: {type(exc).__name__}"],
            ),
        )


def render_shadow_live_trace_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Mirror Tunnel Shadow Live Trace",
        "",
        f"- **Trace id:** `{_md(report.get('trace_id'))}`",
        f"- **Run id:** `{_md(report.get('run_id'))}`",
        f"- **Status:** `{_md(report.get('status'))}`",
        f"- **Enabled:** `{str(bool(report.get('enabled'))).lower()}`",
        f"- **Boundary:** `{_md(report.get('boundary'))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase'))}`",
        "",
        "## Frames",
        "",
    ]
    for frame in report.get("frames") or []:
        if not isinstance(frame, dict):
            continue
        lines.append(f"### `{_md(frame.get('frame_type'))}`")
        lines.append(f"- Availability: `{_md(frame.get('availability'))}`")
        lines.append(f"- Source: `{_md(frame.get('source_key'))}`")
        lines.append(f"- Truncated: `{str(bool(frame.get('excerpt_truncated'))).lower()}`")
        excerpt = _md(frame.get("excerpt"))
        lines.append(f"- Excerpt: {excerpt if excerpt else '(empty)'}")
        lines.append("")

    lines.extend(["## Missing Evidence", ""])
    missing = report.get("missing_evidence") if isinstance(report.get("missing_evidence"), list) else []
    if missing:
        for item in missing:
            lines.append(f"- `{_md(item.get('frame_type'))}` - {_md(item.get('reason'))}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Blocked Reasons", ""])
    blocked = report.get("blocked_reasons") if isinstance(report.get("blocked_reasons"), list) else []
    if blocked:
        for reason in blocked:
            lines.append(f"- {_md(reason)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Artifact Paths", ""])
    paths = report.get("artifact_paths") if isinstance(report.get("artifact_paths"), dict) else {}
    if paths:
        for key in sorted(paths):
            lines.append(f"- `{_md(key)}`: `{_md(paths[key])}`")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Boundaries", ""])
    for item in report.get("boundaries") or []:
        lines.append(f"- {_md(item)}")
    lines.append("")
    return "\n".join(lines)


def _build_frame(
    *,
    frame_type: str,
    value: Any,
    frame_index: int,
    run_id: str,
    excerpt_limit: int,
) -> tuple[dict[str, Any], dict[str, str] | None, list[str]]:
    blockers = _unsafe_findings(value, frame_type)
    if blockers:
        frame = _missing_frame(
            frame_type=frame_type,
            frame_index=frame_index,
            reason="unsafe source value excluded",
        )
        return frame, {"frame_type": frame_type, "reason": "unsafe source value excluded"}, blockers

    text = _stringify_value(value)
    if not text.strip():
        frame = _missing_frame(
            frame_type=frame_type,
            frame_index=frame_index,
            reason="source value was not available",
        )
        return frame, {"frame_type": frame_type, "reason": "source value was not available"}, []

    excerpt, truncated = _excerpt(text, excerpt_limit)
    frame = {
        "frame_id": _frame_id(run_id, frame_type, frame_index, text),
        "frame_index": frame_index,
        "frame_type": frame_type,
        "availability": "available",
        "source_key": frame_type,
        "artifact_path": "",
        "resolved_artifact_path": "",
        "artifact_kind": "in_memory",
        "excerpt": excerpt,
        "excerpt_truncated": truncated,
        "classification_reason": "value was already present in the existing run context",
        "content_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
    }
    return frame, None, []


def _missing_frame(*, frame_type: str, frame_index: int, reason: str) -> dict[str, Any]:
    return {
        "frame_id": f"missing-{frame_type}",
        "frame_index": frame_index,
        "frame_type": frame_type,
        "availability": "missing",
        "source_key": frame_type,
        "artifact_path": "",
        "resolved_artifact_path": "",
        "artifact_kind": "",
        "excerpt": "",
        "excerpt_truncated": False,
        "classification_reason": "",
        "reason": reason,
    }


def _trace_status(*, run_id: str, blocked_reasons: list[str], available_count: int) -> str:
    if blocked_reasons:
        return STATUS_BLOCKED
    if not str(run_id or "").strip():
        return STATUS_SKIPPED_NO_RUN_ID
    if available_count == 0:
        return STATUS_SKIPPED_INSUFFICIENT_CONTEXT
    return STATUS_LIVE_TRACE_WRITTEN


def _base_result(
    *,
    enabled: bool,
    status: str,
    run_id: str,
    boundary: str,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "enabled": bool(enabled),
        "status": status,
        "trace_id": "",
        "run_id": str(run_id or ""),
        "created_at": "",
        "frames": [],
        "missing_evidence": [],
        "blocked_reasons": list(blocked_reasons or []),
        "artifact_paths": {},
        "boundaries": list(BOUNDARIES),
        "boundary": str(boundary or ""),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
        "guardrails": _guardrails(),
    }


def _attach_metadata(metadata: dict[str, Any] | None, trace_result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(metadata, dict):
        metadata["mirror_tunnel_shadow_trace"] = {
            "status": trace_result.get("status"),
            "trace_id": trace_result.get("trace_id"),
            "run_id": trace_result.get("run_id"),
            "artifact_paths": dict(trace_result.get("artifact_paths") or {}),
        }
    return trace_result


def _resolve_output_root(repo: Path, output_root: str | Path | None) -> tuple[Path | None, list[str]]:
    raw = output_root if output_root is not None else DEFAULT_OUTPUT_ROOT
    if _is_secret_or_env_path(str(raw)):
        return None, ["output_root points to a secret or environment path"]
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = repo / candidate
    resolved = candidate.resolve()
    if _is_secret_or_env_path(str(resolved)):
        return None, ["output_root resolves to a secret or environment path"]
    try:
        resolved.relative_to(repo)
    except ValueError:
        return None, ["output_root must stay inside the repository root"]
    return resolved, []


def _validate_run_id(run_id: str) -> tuple[str, list[str]]:
    text = str(run_id or "").strip()
    if not text:
        return "", []
    if ".." in Path(text).parts or "/" in text or "\\" in text or ":" in text:
        return "", ["run_id contains path traversal or path separators"]
    if not _SAFE_RUN_ID_RE.match(text):
        return "", ["run_id contains unsupported characters or is too long"]
    if _is_secret_or_env_path(text):
        return "", ["run_id points to a secret or environment path"]
    return text, []


def _unsafe_findings(value: Any, path: str) -> list[str]:
    findings: list[str] = []
    if value is None:
        return findings
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if _is_secret_key(key_text):
                findings.append(f"{child_path} contains a secret field")
                continue
            findings.extend(_unsafe_findings(item, child_path))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(_unsafe_findings(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        if _SECRET_ASSIGNMENT_RE.search(value):
            findings.append(f"{path} contains credential-like inline text")
        if _is_secret_or_env_path(value):
            findings.append(f"{path} contains a secret or environment path")
    return findings


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(key)).strip("_").lower()
    if normalized in _SECRET_KEY_NAMES:
        return True
    if normalized in {"token_budget", "token_count", "token_limit"}:
        return False
    return (
        normalized.endswith("_api_key")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
        or normalized.endswith("_private_key")
        or normalized.endswith("_token")
    )


def _is_secret_or_env_path(value: str) -> bool:
    normalized = str(value or "").replace("\\", "/").lower()
    if not normalized.strip():
        return False
    parts = [part for part in normalized.split("/") if part]
    if normalized.endswith("/.env") or normalized == ".env" or ".env." in normalized:
        return True
    if ".agent/private" in normalized:
        return True
    return any(part in _SECRET_PATH_PARTS for part in parts)


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple, bool, int, float)):
        try:
            return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _excerpt(text: str, limit: int) -> tuple[str, bool]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if limit <= 0:
        return "", bool(normalized)
    if len(normalized) <= limit:
        return normalized, False
    marker = "\n[excerpt truncated]"
    if limit <= len(marker):
        return normalized[:limit], True
    return normalized[: limit - len(marker)] + marker, True


def _frame_id(run_id: str, frame_type: str, frame_index: int, text: str) -> str:
    seed = f"{run_id}:{frame_type}:{frame_index}:{text[:256]}"
    digest = hashlib.sha1(seed.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"{frame_type}-{digest}"


def _trace_id(run_id: str, created_at: str, frames: list[dict[str, Any]]) -> str:
    seed = json.dumps(
        {
            "run_id": run_id,
            "created_at": created_at,
            "frame_hashes": [frame.get("content_sha256", "") for frame in frames],
        },
        sort_keys=True,
    )
    return "mirror-live-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "shadow_only": True,
        "default_off": True,
        "writes_trace_artifacts_only": True,
        "model_call_performed": False,
        "prompt_changed": False,
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
        "scoring_during_run": False,
        "claim_diff_check_during_run": False,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n"


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "")
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out
