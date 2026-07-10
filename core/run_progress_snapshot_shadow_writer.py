"""UX.LIVE.3 default-off terminal run-progress snapshot writer.

This module writes one read-only, terminal shadow snapshot only when explicitly
enabled.  It has no polling, streaming, network, database, UI, or runtime
authority behaviour.  The caller must keep its result separate from the main
run result.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENVIRONMENT_FLAG = "RUN_PROGRESS_SHADOW_WRITER_ENABLED"
ALLOWED_WRITE_ROOT = Path(".agent") / "ux" / "run_progress_snapshots"
CANONICAL_JSON_NAME = "run_progress_snapshot.json"

WRITER_DISABLED = "run_progress_writer_disabled"
WRITTEN = "run_progress_snapshot_written"
WRITTEN_WITH_WARNINGS = "run_progress_snapshot_written_with_warnings"
BLOCKED = "run_progress_snapshot_blocked"
FAILED_ISOLATED = "run_progress_snapshot_write_failed_isolated"

SOURCE_PHASE = "UX.LIVE.3"
RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.4",
    "title": "Narrow Multi-Stage Shadow Instrumentation",
    "reason": "Add only a small number of genuinely observed shadow stages while preserving default-off isolation.",
}

SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RESERVED_RUN_IDS = {"env", "secrets", "secret", "credentials", "private", "tokens"}
_ALLOWED_METADATA_KEYS = {
    "mode",
    "source_component",
    "result_type",
    "warning_codes",
    "error_category",
}
_SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "token",
    "password",
    "credential",
    "authorization",
    "cookie",
    "secret",
    ".env",
    "raw prompt",
    "user message",
    "model response",
    "patch content",
    "database connection",
    "connection string",
)

REQUIRED_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id",
    "run_id",
    "source_phase",
    "writer_mode",
    "writer_enabled",
    "snapshot_status",
    "current_stage_id",
    "observed_stage_ids",
    "completed_stage_ids",
    "pending_stage_ids",
    "warning_stage_ids",
    "error_stage_ids",
    "stages",
    "progress_notice",
    "created_at",
    "updated_at",
    "sequence_number",
    "terminal",
    "simulated_only",
    "live_stream_enabled",
    "polling_enabled",
    "runtime_behavior_changed",
    "runtime_authority",
    "action_triggered",
    "actions_available",
    "artifact_refs",
    "warnings",
    "errors",
    "metadata",
    # UX.RUN.2 compatibility fields.  They do not provide a second state model.
    "source_contract_phase",
    "blocked_reasons",
    "recommended_next_phase",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _result(
    status: str,
    *,
    writer_enabled: bool,
    run_id: str = "",
    snapshot_path: str = "",
    snapshot_written: bool = False,
    warning: str = "",
    blocked_reason: str = "",
    failure_isolated: bool = False,
) -> dict[str, Any]:
    return {
        "writer_status": status,
        "writer_enabled": bool(writer_enabled),
        "run_id": str(run_id or ""),
        "snapshot_path": str(snapshot_path or ""),
        "snapshot_written": bool(snapshot_written),
        "warning": str(warning or ""),
        "blocked_reason": str(blocked_reason or ""),
        "failure_isolated": bool(failure_isolated),
        "runtime_result_changed": False,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def is_run_progress_shadow_writer_enabled(value: Any = None) -> bool:
    """Return true only for an explicit truthy setting; missing means disabled."""
    raw = os.getenv(ENVIRONMENT_FLAG) if value is None else value
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_run_id(run_id: Any) -> str:
    """Accept a single safe slug and reject paths, extensions, and secret roots."""
    value = str(run_id or "").strip()
    lowered = value.lower()
    if not value:
        raise ValueError("run_id_empty")
    if value in {".", ".."} or ".." in value:
        raise ValueError("run_id_path_traversal")
    if any(char in value for char in ("/", "\\", ":", "\x00")) or Path(value).is_absolute():
        raise ValueError("run_id_path_not_allowed")
    if not SAFE_RUN_ID_RE.fullmatch(value):
        raise ValueError("run_id_unsafe_slug")
    if lowered in _RESERVED_RUN_IDS:
        raise ValueError("run_id_reserved_secret_path")
    return value


def _contains_sensitive_marker(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in _SENSITIVE_MARKERS)


def _sanitize_metadata(metadata: Any) -> tuple[dict[str, Any], str]:
    if metadata is None:
        return {}, ""
    if not isinstance(metadata, dict):
        return {}, "metadata_not_an_object"
    clean: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if key_text not in _ALLOWED_METADATA_KEYS:
            return {}, "metadata_key_not_allowed"
        if _contains_sensitive_marker(key_text) or _contains_sensitive_marker(value):
            return {}, "sensitive_metadata_rejected"
        if isinstance(value, (dict, list, tuple, set)):
            if key_text != "warning_codes" or not isinstance(value, (list, tuple)):
                return {}, "metadata_value_not_small_descriptive"
            normalized_codes = [str(item) for item in value]
            if any(_contains_sensitive_marker(item) or len(item) > 80 for item in normalized_codes):
                return {}, "sensitive_metadata_rejected"
            clean[key_text] = normalized_codes[:8]
            continue
        text = str(value)
        if len(text) > 160 or "\n" in text or "\r" in text:
            return {}, "metadata_value_not_small_descriptive"
        if key_text == "mode" and text not in {"reviewer", "planner"}:
            return {}, "metadata_mode_not_allowed"
        if key_text == "source_component" and not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", text):
            return {}, "metadata_source_component_not_allowed"
        if key_text == "result_type" and text not in {"terminal_response", "terminal_error"}:
            return {}, "metadata_result_type_not_allowed"
        if key_text == "error_category" and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", text):
            return {}, "metadata_error_category_not_allowed"
        clean[key_text] = text
    return clean, ""


def _stage_record(stage_id: str, *, timestamp: str, outcome: str) -> dict[str, Any]:
    is_error = outcome == "error"
    return {
        "stage_id": stage_id,
        "status": "error" if is_error else "completed",
        "label": "Error reported" if is_error else "Final response ready",
        "message": "A terminal error was observed; error details are intentionally omitted." if is_error else "Final response assembly was observed.",
        "updated_at": timestamp,
        "artifact_refs": [],
        "warnings": [],
        "errors": ["runtime_error"] if is_error else [],
        "is_runtime_authority": False,
        "may_trigger_action": False,
        "safe_to_display": True,
    }


def build_run_progress_snapshot(
    run_id: Any,
    *,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a one-stage terminal snapshot without accepting raw run payloads."""
    safe_run_id = normalize_run_id(run_id)
    if outcome not in {"success", "error"}:
        raise ValueError("snapshot_outcome_not_allowed")
    safe_metadata, metadata_error = _sanitize_metadata(metadata)
    if metadata_error:
        raise ValueError(metadata_error)
    timestamp = created_at or _utc_now()
    stage_id = "error_reported" if outcome == "error" else "final_response_ready"
    stage = _stage_record(stage_id, timestamp=timestamp, outcome=outcome)
    return {
        "snapshot_id": safe_run_id,
        "run_id": safe_run_id,
        "source_phase": SOURCE_PHASE,
        "writer_mode": "shadow",
        "writer_enabled": True,
        "snapshot_status": "terminal_error_observed" if outcome == "error" else "terminal_final_response_observed",
        "current_stage_id": stage_id,
        "observed_stage_ids": [stage_id],
        "completed_stage_ids": [] if outcome == "error" else [stage_id],
        "pending_stage_ids": [],
        "warning_stage_ids": [],
        "error_stage_ids": [stage_id] if outcome == "error" else [],
        "stages": [stage],
        "progress_notice": "This default-off shadow snapshot records only the observed terminal boundary; it does not claim intermediate live progress or success.",
        "created_at": timestamp,
        "updated_at": timestamp,
        "sequence_number": 1,
        "terminal": True,
        "simulated_only": False,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "runtime_authority": False,
        "action_triggered": False,
        "actions_available": [],
        "artifact_refs": [],
        "warnings": [],
        "errors": ["runtime_error"] if outcome == "error" else [],
        "metadata": safe_metadata,
        "source_contract_phase": "UX.RUN.1",
        "blocked_reasons": [],
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def validate_snapshot_payload(snapshot: Any) -> dict[str, Any]:
    """Validate the narrow writer contract before anything reaches disk."""
    if not isinstance(snapshot, dict):
        return {"valid": False, "blocked_reason": "snapshot_not_an_object"}
    missing = [field for field in REQUIRED_SNAPSHOT_FIELDS if field not in snapshot]
    if missing:
        return {"valid": False, "blocked_reason": "snapshot_required_fields_missing:" + ",".join(missing)}
    try:
        safe_run_id = normalize_run_id(snapshot.get("run_id"))
    except ValueError as exc:
        return {"valid": False, "blocked_reason": str(exc)}
    if snapshot.get("snapshot_id") != safe_run_id:
        return {"valid": False, "blocked_reason": "snapshot_id_must_match_run_id"}
    required_values = {
        "source_phase": SOURCE_PHASE,
        "writer_mode": "shadow",
        "writer_enabled": True,
        "sequence_number": 1,
        "terminal": True,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "runtime_authority": False,
        "action_triggered": False,
    }
    for key, expected in required_values.items():
        if snapshot.get(key) is not expected and snapshot.get(key) != expected:
            return {"valid": False, "blocked_reason": f"snapshot_invalid_{key}"}
    if snapshot.get("actions_available") != []:
        return {"valid": False, "blocked_reason": "snapshot_actions_not_allowed"}
    observed = snapshot.get("observed_stage_ids")
    stages = snapshot.get("stages")
    if not isinstance(observed, list) or not isinstance(stages, list) or len(observed) != 1 or len(stages) != 1:
        return {"valid": False, "blocked_reason": "snapshot_must_observe_one_terminal_stage"}
    stage_id = snapshot.get("current_stage_id")
    if stage_id not in {"final_response_ready", "error_reported"} or observed != [stage_id]:
        return {"valid": False, "blocked_reason": "snapshot_terminal_stage_invalid"}
    if stage_id == "final_response_ready" and snapshot.get("completed_stage_ids") != [stage_id]:
        return {"valid": False, "blocked_reason": "snapshot_final_stage_not_completed"}
    if stage_id == "error_reported" and snapshot.get("error_stage_ids") != [stage_id]:
        return {"valid": False, "blocked_reason": "snapshot_error_stage_not_visible"}
    metadata, metadata_error = _sanitize_metadata(snapshot.get("metadata"))
    if metadata_error or metadata != snapshot.get("metadata"):
        return {"valid": False, "blocked_reason": metadata_error or "sensitive_metadata_rejected"}
    return {"valid": True, "blocked_reason": ""}


def _run_directory(repo_root: str | Path, run_id: str) -> tuple[Path, Path]:
    root = Path(repo_root).resolve()
    allowed_root = (root / ALLOWED_WRITE_ROOT).resolve()
    directory = (allowed_root / run_id).resolve()
    try:
        directory.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError("snapshot_path_outside_allowed_root") from exc
    return allowed_root, directory


def _relative_path(path: Path, repo_root: str | Path) -> str:
    try:
        return path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _load_existing_snapshot(path: Path, expected_run_id: str, expected_stage_id: str) -> tuple[bool, str]:
    if not path.exists():
        return True, ""
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "malformed_prior_snapshot_preserved"
    validation = validate_snapshot_payload(prior)
    if not validation["valid"] or prior.get("run_id") != expected_run_id or prior.get("terminal") is not True:
        return False, "invalid_prior_snapshot_preserved"
    if prior.get("current_stage_id") != expected_stage_id:
        return False, "terminal_boundary_changed_snapshot_preserved"
    return True, "existing_terminal_snapshot_overwritten_deterministically"


def _write_json_atomically(target: Path, payload: dict[str, Any]) -> None:
    temp_path = target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        last_error: PermissionError | None = None
        for _attempt in range(2):
            try:
                os.replace(temp_path, target)
                return
            except PermissionError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def write_run_progress_snapshot_shadow(
    run_id: Any,
    *,
    repo_root: str | Path = ".",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    enabled: Any = None,
) -> dict[str, Any]:
    """Write the canonical JSON snapshot, returning a non-authoritative result."""
    writer_enabled = is_run_progress_shadow_writer_enabled(enabled)
    if not writer_enabled:
        return _result(WRITER_DISABLED, writer_enabled=False)
    try:
        snapshot = build_run_progress_snapshot(run_id, outcome=outcome, metadata=metadata)
    except ValueError as exc:
        return _result(BLOCKED, writer_enabled=True, run_id=str(run_id or ""), blocked_reason=str(exc))
    validation = validate_snapshot_payload(snapshot)
    if not validation["valid"]:
        return _result(BLOCKED, writer_enabled=True, run_id=snapshot["run_id"], blocked_reason=validation["blocked_reason"])
    try:
        _allowed_root, directory = _run_directory(repo_root, snapshot["run_id"])
        target = directory / CANONICAL_JSON_NAME
        safe_to_write, prior_warning = _load_existing_snapshot(
            target,
            snapshot["run_id"],
            snapshot["current_stage_id"],
        )
        if not safe_to_write:
            return _result(
                FAILED_ISOLATED,
                writer_enabled=True,
                run_id=snapshot["run_id"],
                snapshot_path=_relative_path(target, repo_root),
                warning=prior_warning,
                failure_isolated=True,
            )
        directory.mkdir(parents=True, exist_ok=True)
        _write_json_atomically(target, snapshot)
        status = WRITTEN_WITH_WARNINGS if prior_warning else WRITTEN
        return _result(
            status,
            writer_enabled=True,
            run_id=snapshot["run_id"],
            snapshot_path=_relative_path(target, repo_root),
            snapshot_written=True,
            warning=prior_warning,
        )
    except (OSError, ValueError) as exc:
        return _result(
            FAILED_ISOLATED,
            writer_enabled=True,
            run_id=snapshot["run_id"],
            warning="snapshot_write_failed_isolated",
            blocked_reason=type(exc).__name__,
            failure_isolated=True,
        )


def safe_write_run_progress_snapshot(
    run_id: Any,
    *,
    repo_root: str | Path = ".",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    enabled: Any = None,
) -> dict[str, Any]:
    """Catch every writer-local failure so callers can preserve their run result."""
    try:
        return write_run_progress_snapshot_shadow(
            run_id,
            repo_root=repo_root,
            outcome=outcome,
            metadata=metadata,
            enabled=enabled,
        )
    except Exception as exc:  # Defensive boundary: never leak writer failures to a run.
        return _result(
            FAILED_ISOLATED,
            writer_enabled=is_run_progress_shadow_writer_enabled(enabled),
            run_id=str(run_id or ""),
            warning="snapshot_write_failed_isolated",
            blocked_reason=type(exc).__name__,
            failure_isolated=True,
        )
