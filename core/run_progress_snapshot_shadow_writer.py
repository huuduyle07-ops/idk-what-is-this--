"""UX.LIVE.4 default-off, multi-stage run-progress shadow snapshots.

The writer is evidence-only.  It records only explicit observations supplied by
the caller, never starts work, and never controls the run that called it.
"""
from __future__ import annotations

import copy
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

SOURCE_PHASE = "UX.LIVE.4"
RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.LIVE.5",
    "title": "Current Run Snapshot Association",
    "reason": "Associate a current browser/run context with its read-only snapshot without polling or authority.",
}

SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RESERVED_RUN_IDS = {"env", "secrets", "secret", "credentials", "private", "tokens"}
_ALLOWED_METADATA_KEYS = {"mode", "source_component", "result_type", "warning_codes", "error_category"}
_SENSITIVE_MARKERS = (
    "api_key", "apikey", "token", "password", "credential", "authorization", "cookie",
    "secret", ".env", "raw prompt", "user message", "model response", "patch content",
    "database connection", "connection string", "stack trace",
)
_STAGE_DEFINITIONS: dict[str, dict[str, str]] = {
    "request_received": {
        "label": "Request received",
        "message": "The existing run function received the request.",
        "status": "completed",
    },
    "model_response_received": {
        "label": "Model response received",
        "message": "The existing draft pipeline returned a response; response content is intentionally omitted.",
        "status": "completed",
    },
    "final_response_ready": {
        "label": "Final response ready",
        "message": "Final response assembly was observed; this does not imply validation, approval, or success.",
        "status": "completed",
    },
    "error_reported": {
        "label": "Error reported",
        "message": "A terminal error was observed; error details are intentionally omitted.",
        "status": "error",
    },
}
_TERMINAL_STAGE_IDS = {"final_response_ready", "error_reported"}

REQUIRED_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "snapshot_id", "run_id", "source_phase", "writer_mode", "writer_enabled", "snapshot_status",
    "current_stage_id", "observed_stage_ids", "completed_stage_ids", "pending_stage_ids",
    "warning_stage_ids", "error_stage_ids", "stages", "progress_notice", "created_at",
    "updated_at", "sequence_number", "terminal", "simulated_only", "live_stream_enabled",
    "polling_enabled", "runtime_behavior_changed", "runtime_authority", "action_triggered",
    "actions_available", "artifact_refs", "warnings", "errors", "metadata",
    # UX.RUN.2 loader compatibility fields.  They mirror no additional state.
    "source_contract_phase", "blocked_reasons", "recommended_next_phase",
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
    """Missing configuration is disabled; only an explicit truthy value enables it."""
    raw = os.getenv(ENVIRONMENT_FLAG) if value is None else value
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_run_id(run_id: Any) -> str:
    """Validate a single safe run slug; paths and secret roots are never IDs."""
    value = str(run_id or "").strip()
    if not value:
        raise ValueError("run_id_empty")
    if value in {".", ".."} or ".." in value:
        raise ValueError("run_id_path_traversal")
    if any(char in value for char in ("/", "\\", ":", "\x00")) or Path(value).is_absolute():
        raise ValueError("run_id_path_not_allowed")
    if not SAFE_RUN_ID_RE.fullmatch(value):
        raise ValueError("run_id_unsafe_slug")
    if value.lower() in _RESERVED_RUN_IDS:
        raise ValueError("run_id_reserved_secret_path")
    return value


def _contains_sensitive_marker(value: Any) -> bool:
    value_text = str(value or "").lower()
    return any(marker in value_text for marker in _SENSITIVE_MARKERS)


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
        if key_text == "warning_codes":
            if not isinstance(value, (list, tuple)):
                return {}, "metadata_value_not_small_descriptive"
            codes = [str(code) for code in value]
            if len(codes) > 8 or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", code) for code in codes):
                return {}, "metadata_value_not_small_descriptive"
            clean[key_text] = codes
            continue
        text = str(value)
        if len(text) > 160 or "\n" in text or "\r" in text:
            return {}, "metadata_value_not_small_descriptive"
        if key_text == "mode" and text not in {"reviewer", "planner"}:
            return {}, "metadata_mode_not_allowed"
        if key_text == "source_component" and not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", text):
            return {}, "metadata_source_component_not_allowed"
        if key_text == "result_type" and text not in {"shadow_stage_update", "terminal_response", "terminal_error"}:
            return {}, "metadata_result_type_not_allowed"
        if key_text == "error_category" and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", text):
            return {}, "metadata_error_category_not_allowed"
        clean[key_text] = text
    return clean, ""


def _sanitize_artifact_refs(value: Any) -> tuple[list[str], str]:
    if value is None:
        return [], ""
    if not isinstance(value, list):
        return [], "artifact_refs_not_a_list"
    refs = [str(ref) for ref in value]
    if len(refs) > 8:
        return [], "artifact_refs_too_many"
    for ref in refs:
        path = Path(ref)
        if not ref or path.is_absolute() or ".." in ref or "\\" in ref or _contains_sensitive_marker(ref):
            return [], "artifact_ref_not_safe"
        if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", ref):
            return [], "artifact_ref_not_safe"
    return list(dict.fromkeys(refs)), ""


def _timestamp_not_before(now: str, previous: str) -> str:
    return previous if previous and previous > now else now


def _stage_record(stage_id: str, *, timestamp: str, error_category: str = "", artifact_refs: list[str] | None = None) -> dict[str, Any]:
    definition = _STAGE_DEFINITIONS[stage_id]
    is_error = stage_id == "error_reported"
    return {
        "stage_id": stage_id,
        "status": definition["status"],
        "label": definition["label"],
        "message": definition["message"],
        "updated_at": timestamp,
        "artifact_refs": list(artifact_refs or []),
        "warnings": [],
        "errors": [error_category or "runtime_error"] if is_error else [],
        "is_runtime_authority": False,
        "may_trigger_action": False,
        "safe_to_display": True,
    }


def validate_stage_transition(
    stage_id: Any,
    *,
    stage_status: str = "",
    terminal: bool | None = None,
) -> dict[str, Any]:
    """Validate only the small, explicitly instrumented stage vocabulary."""
    stage = str(stage_id or "")
    if stage not in _STAGE_DEFINITIONS:
        return {"valid": False, "blocked_reason": "unknown_stage_id"}
    expected_status = _STAGE_DEFINITIONS[stage]["status"]
    if stage_status and stage_status != expected_status:
        return {"valid": False, "blocked_reason": "stage_status_not_truthful"}
    expected_terminal = stage in _TERMINAL_STAGE_IDS
    if terminal is not None and bool(terminal) is not expected_terminal:
        return {"valid": False, "blocked_reason": "stage_terminal_state_not_truthful"}
    return {"valid": True, "blocked_reason": "", "terminal": expected_terminal, "stage_status": expected_status}


def _base_snapshot(run_id: str, *, stage_id: str, timestamp: str, metadata: dict[str, Any], artifact_refs: list[str], error_category: str) -> dict[str, Any]:
    terminal = stage_id in _TERMINAL_STAGE_IDS
    is_error = stage_id == "error_reported"
    return {
        "snapshot_id": run_id,
        "run_id": run_id,
        "source_phase": SOURCE_PHASE,
        "writer_mode": "shadow",
        "writer_enabled": True,
        "snapshot_status": "terminal_error_observed" if is_error else ("terminal_final_response_observed" if terminal else "shadow_stage_observed"),
        "current_stage_id": stage_id,
        "observed_stage_ids": [stage_id],
        "completed_stage_ids": [] if is_error else [stage_id],
        "pending_stage_ids": [],
        "warning_stage_ids": [],
        "error_stage_ids": [stage_id] if is_error else [],
        "stages": [_stage_record(stage_id, timestamp=timestamp, error_category=error_category, artifact_refs=artifact_refs)],
        "progress_notice": "This default-off shadow snapshot records only genuinely observed boundaries; progress does not imply validation, approval, or success.",
        "created_at": timestamp,
        "updated_at": timestamp,
        "sequence_number": 1,
        "terminal": terminal,
        "simulated_only": False,
        "live_stream_enabled": False,
        "polling_enabled": False,
        "runtime_behavior_changed": False,
        "runtime_authority": False,
        "action_triggered": False,
        "actions_available": [],
        "artifact_refs": list(artifact_refs),
        "warnings": [],
        "errors": [error_category or "runtime_error"] if is_error else [],
        "metadata": metadata,
        "source_contract_phase": "UX.RUN.1",
        "blocked_reasons": [],
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def merge_observed_stage(
    snapshot: dict[str, Any],
    *,
    stage_id: str,
    timestamp: str,
    metadata: dict[str, Any],
    artifact_refs: list[str],
    error_category: str,
) -> dict[str, Any]:
    """Return a new monotonically updated snapshot for one genuine observation."""
    merged = copy.deepcopy(snapshot)
    observed = list(merged.get("observed_stage_ids") or [])
    if stage_id in observed:
        return merged
    is_error = stage_id == "error_reported"
    terminal = stage_id in _TERMINAL_STAGE_IDS
    observed.append(stage_id)
    completed = list(dict.fromkeys(str(item) for item in merged.get("completed_stage_ids") or []))
    if not is_error:
        completed.append(stage_id)
    errors = list(dict.fromkeys(str(item) for item in merged.get("error_stage_ids") or []))
    if is_error:
        errors.append(stage_id)
    merged["source_phase"] = SOURCE_PHASE
    merged["snapshot_status"] = "terminal_error_observed" if is_error else ("terminal_final_response_observed" if terminal else "shadow_stage_observed")
    merged["current_stage_id"] = stage_id
    merged["observed_stage_ids"] = list(dict.fromkeys(observed))
    merged["completed_stage_ids"] = list(dict.fromkeys(completed))
    merged["pending_stage_ids"] = []
    merged["error_stage_ids"] = list(dict.fromkeys(errors))
    merged["stages"] = list(merged.get("stages") or []) + [
        _stage_record(stage_id, timestamp=timestamp, error_category=error_category, artifact_refs=artifact_refs)
    ]
    merged["updated_at"] = _timestamp_not_before(timestamp, str(merged.get("updated_at") or ""))
    merged["sequence_number"] = int(merged.get("sequence_number", 0)) + 1
    merged["terminal"] = terminal
    merged["errors"] = [error_category or "runtime_error"] if is_error else list(merged.get("errors") or [])
    merged["artifact_refs"] = list(dict.fromkeys([*list(merged.get("artifact_refs") or []), *artifact_refs]))
    merged["metadata"] = metadata
    merged["recommended_next_phase"] = dict(RECOMMENDED_NEXT_PHASE)
    return merged


def build_run_progress_snapshot(
    run_id: Any,
    *,
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build a terminal snapshot for UX.LIVE.3 compatibility callers."""
    stage_id = "error_reported" if outcome == "error" else "final_response_ready"
    transition = validate_stage_transition(stage_id)
    if outcome not in {"success", "error"} or not transition["valid"]:
        raise ValueError("snapshot_outcome_not_allowed")
    safe_run_id = normalize_run_id(run_id)
    safe_metadata, metadata_error = _sanitize_metadata(metadata)
    if metadata_error:
        raise ValueError(metadata_error)
    timestamp = created_at or _utc_now()
    return _base_snapshot(
        safe_run_id,
        stage_id=stage_id,
        timestamp=timestamp,
        metadata=safe_metadata,
        artifact_refs=[],
        error_category="runtime_error" if outcome == "error" else "",
    )


def validate_snapshot_payload(snapshot: Any) -> dict[str, Any]:
    """Validate containment, truthfulness, and loader-compatible field shapes."""
    if not isinstance(snapshot, dict):
        return {"valid": False, "blocked_reason": "snapshot_not_an_object"}
    missing = [field for field in REQUIRED_SNAPSHOT_FIELDS if field not in snapshot]
    if missing:
        return {"valid": False, "blocked_reason": "snapshot_required_fields_missing:" + ",".join(missing)}
    try:
        run_id = normalize_run_id(snapshot.get("run_id"))
    except ValueError as exc:
        return {"valid": False, "blocked_reason": str(exc)}
    if snapshot.get("snapshot_id") != run_id:
        return {"valid": False, "blocked_reason": "snapshot_id_must_match_run_id"}
    for key, expected in {
        "source_phase": SOURCE_PHASE, "writer_mode": "shadow", "writer_enabled": True,
        "simulated_only": False, "live_stream_enabled": False, "polling_enabled": False,
        "runtime_behavior_changed": False, "runtime_authority": False, "action_triggered": False,
    }.items():
        if snapshot.get(key) != expected:
            return {"valid": False, "blocked_reason": f"snapshot_invalid_{key}"}
    if snapshot.get("actions_available") != [] or snapshot.get("pending_stage_ids") != []:
        return {"valid": False, "blocked_reason": "snapshot_actions_or_pending_not_allowed"}
    if not isinstance(snapshot.get("sequence_number"), int) or snapshot["sequence_number"] < 1:
        return {"valid": False, "blocked_reason": "snapshot_sequence_invalid"}
    observed = snapshot.get("observed_stage_ids")
    stages = snapshot.get("stages")
    if not isinstance(observed, list) or not observed or len(observed) != len(set(observed)) or not isinstance(stages, list):
        return {"valid": False, "blocked_reason": "snapshot_observed_stages_invalid"}
    if any(stage not in _STAGE_DEFINITIONS for stage in observed):
        return {"valid": False, "blocked_reason": "snapshot_unknown_stage"}
    if snapshot.get("current_stage_id") != observed[-1]:
        return {"valid": False, "blocked_reason": "snapshot_current_stage_invalid"}
    if [str(item.get("stage_id", "")) for item in stages] != observed:
        return {"valid": False, "blocked_reason": "snapshot_stage_records_invalid"}
    for record in stages:
        stage_id = str(record.get("stage_id") or "")
        definition = _STAGE_DEFINITIONS.get(stage_id, {})
        if record.get("status") != definition.get("status") or record.get("label") != definition.get("label"):
            return {"valid": False, "blocked_reason": "snapshot_stage_record_not_truthful"}
        if record.get("is_runtime_authority") is not False or record.get("may_trigger_action") is not False:
            return {"valid": False, "blocked_reason": "snapshot_stage_authority_not_allowed"}
        refs, refs_error = _sanitize_artifact_refs(record.get("artifact_refs"))
        if refs_error or refs != record.get("artifact_refs"):
            return {"valid": False, "blocked_reason": refs_error or "artifact_ref_not_safe"}
    completed = list(snapshot.get("completed_stage_ids") or [])
    errors = list(snapshot.get("error_stage_ids") or [])
    if len(completed) != len(set(completed)) or len(errors) != len(set(errors)):
        return {"valid": False, "blocked_reason": "snapshot_stage_ids_not_deduplicated"}
    if any(stage not in observed for stage in completed + errors):
        return {"valid": False, "blocked_reason": "snapshot_stage_ids_not_observed"}
    current = snapshot["current_stage_id"]
    if bool(snapshot.get("terminal")) != (current in _TERMINAL_STAGE_IDS):
        return {"valid": False, "blocked_reason": "snapshot_terminal_state_invalid"}
    if current == "final_response_ready" and current not in completed:
        return {"valid": False, "blocked_reason": "snapshot_final_stage_not_completed"}
    if current == "error_reported" and current not in errors:
        return {"valid": False, "blocked_reason": "snapshot_error_stage_not_visible"}
    metadata, metadata_error = _sanitize_metadata(snapshot.get("metadata"))
    refs, refs_error = _sanitize_artifact_refs(snapshot.get("artifact_refs"))
    if metadata_error or metadata != snapshot.get("metadata"):
        return {"valid": False, "blocked_reason": metadata_error or "sensitive_metadata_rejected"}
    if refs_error or refs != snapshot.get("artifact_refs"):
        return {"valid": False, "blocked_reason": refs_error or "artifact_ref_not_safe"}
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


def load_existing_safe_snapshot(path: Path, expected_run_id: str) -> tuple[dict[str, Any] | None, str]:
    """Load a prior canonical snapshot without repairing or replacing malformed data."""
    if not path.exists():
        return None, ""
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "malformed_prior_snapshot_preserved"
    validation = validate_snapshot_payload(snapshot)
    if not validation["valid"] or snapshot.get("run_id") != expected_run_id:
        return None, "invalid_prior_snapshot_preserved"
    return snapshot, ""


def _write_json_atomically(target: Path, payload: dict[str, Any]) -> None:
    temporary = target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        permission_error: PermissionError | None = None
        for _attempt in range(2):
            try:
                os.replace(temporary, target)
                return
            except PermissionError as exc:
                permission_error = exc
        if permission_error is not None:
            raise permission_error
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def _metadata_for_update(
    existing: dict[str, Any] | None,
    *,
    mode: str,
    source_component: str,
    terminal: bool,
    error_category: str,
    warning_codes: Any,
) -> tuple[dict[str, Any], str]:
    metadata = dict(existing or {})
    if mode:
        metadata["mode"] = mode
    metadata["source_component"] = source_component
    metadata["result_type"] = "terminal_error" if error_category else ("terminal_response" if terminal else "shadow_stage_update")
    if warning_codes is not None:
        metadata["warning_codes"] = warning_codes
    if error_category:
        metadata["error_category"] = error_category
    return _sanitize_metadata(metadata)


def update_run_progress_snapshot_shadow(
    run_id: Any,
    *,
    stage_id: str,
    stage_status: str = "",
    terminal: bool | None = None,
    safe_message: str = "",
    warning_codes: Any = None,
    error_category: str = "",
    artifact_refs: Any = None,
    source_component: str = "web.runner",
    mode: str = "",
    repo_root: str | Path = ".",
    enabled: Any = None,
    expected_sequence_number: int | None = None,
) -> dict[str, Any]:
    """Atomically add one truthful observation to one canonical run snapshot.

    ``safe_message`` is deliberately not persisted: canonical stage messages are
    fixed, so callers cannot smuggle prompt, response, or user text into a file.
    """
    del safe_message
    writer_enabled = is_run_progress_shadow_writer_enabled(enabled)
    if not writer_enabled:
        return _result(WRITER_DISABLED, writer_enabled=False)
    try:
        safe_run_id = normalize_run_id(run_id)
    except ValueError as exc:
        return _result(BLOCKED, writer_enabled=True, run_id=str(run_id or ""), blocked_reason=str(exc))
    transition = validate_stage_transition(stage_id, stage_status=stage_status, terminal=terminal)
    if not transition["valid"]:
        return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, blocked_reason=transition["blocked_reason"])
    refs, refs_error = _sanitize_artifact_refs(artifact_refs)
    if refs_error:
        return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, blocked_reason=refs_error)
    if error_category and not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", error_category):
        return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, blocked_reason="error_category_not_safe")
    try:
        _allowed_root, directory = _run_directory(repo_root, safe_run_id)
        target = directory / CANONICAL_JSON_NAME
        prior, load_warning = load_existing_safe_snapshot(target, safe_run_id)
        if load_warning:
            return _result(
                FAILED_ISOLATED,
                writer_enabled=True,
                run_id=safe_run_id,
                snapshot_path=_relative_path(target, repo_root),
                warning=load_warning,
                failure_isolated=True,
            )
        if prior is not None:
            if expected_sequence_number is not None and expected_sequence_number != prior.get("sequence_number"):
                return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, snapshot_path=_relative_path(target, repo_root), blocked_reason="stale_sequence_update_rejected")
            if stage_id in prior.get("observed_stage_ids", []):
                return _result(WRITTEN_WITH_WARNINGS, writer_enabled=True, run_id=safe_run_id, snapshot_path=_relative_path(target, repo_root), warning="duplicate_stage_update_ignored")
            if prior.get("terminal") is True:
                return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, snapshot_path=_relative_path(target, repo_root), blocked_reason="terminal_snapshot_update_rejected")
        safe_metadata, metadata_error = _metadata_for_update(
            prior.get("metadata") if prior else None,
            mode=mode,
            source_component=source_component,
            terminal=bool(transition["terminal"]),
            error_category=error_category if stage_id == "error_reported" else "",
            warning_codes=warning_codes,
        )
        if metadata_error:
            return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, blocked_reason=metadata_error)
        timestamp = _utc_now()
        if prior is None:
            snapshot = _base_snapshot(
                safe_run_id,
                stage_id=stage_id,
                timestamp=timestamp,
                metadata=safe_metadata,
                artifact_refs=refs,
                error_category=error_category,
            )
        else:
            snapshot = merge_observed_stage(
                prior,
                stage_id=stage_id,
                timestamp=timestamp,
                metadata=safe_metadata,
                artifact_refs=refs,
                error_category=error_category,
            )
        validation = validate_snapshot_payload(snapshot)
        if not validation["valid"]:
            return _result(BLOCKED, writer_enabled=True, run_id=safe_run_id, blocked_reason=validation["blocked_reason"])
        directory.mkdir(parents=True, exist_ok=True)
        _write_json_atomically(target, snapshot)
        return _result(
            WRITTEN,
            writer_enabled=True,
            run_id=safe_run_id,
            snapshot_path=_relative_path(target, repo_root),
            snapshot_written=True,
        )
    except (OSError, ValueError) as exc:
        return _result(
            FAILED_ISOLATED,
            writer_enabled=True,
            run_id=safe_run_id,
            warning="snapshot_write_failed_isolated",
            blocked_reason=type(exc).__name__,
            failure_isolated=True,
        )


def safe_update_run_progress_snapshot_shadow(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Contain all writer failures so instrumentation never changes the run."""
    try:
        return update_run_progress_snapshot_shadow(*args, **kwargs)
    except Exception as exc:
        run_id = str(args[0] if args else kwargs.get("run_id", ""))
        return _result(
            FAILED_ISOLATED,
            writer_enabled=is_run_progress_shadow_writer_enabled(kwargs.get("enabled")),
            run_id=run_id,
            warning="snapshot_write_failed_isolated",
            blocked_reason=type(exc).__name__,
            failure_isolated=True,
        )


def write_run_progress_snapshot_shadow(
    run_id: Any,
    *,
    repo_root: str | Path = ".",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    enabled: Any = None,
) -> dict[str, Any]:
    """UX.LIVE.3-compatible terminal wrapper over the multi-stage update path."""
    if outcome not in {"success", "error"}:
        return _result(BLOCKED, writer_enabled=is_run_progress_shadow_writer_enabled(enabled), run_id=str(run_id or ""), blocked_reason="snapshot_outcome_not_allowed")
    data = dict(metadata or {})
    stage_id = "error_reported" if outcome == "error" else "final_response_ready"
    expected_result_type = "terminal_error" if outcome == "error" else "terminal_response"
    provided_result_type = data.pop("result_type", expected_result_type)
    if provided_result_type != expected_result_type:
        return _result(BLOCKED, writer_enabled=is_run_progress_shadow_writer_enabled(enabled), run_id=str(run_id or ""), blocked_reason="metadata_result_type_not_allowed")
    source_component = str(data.pop("source_component", "web.runner"))
    mode = str(data.pop("mode", ""))
    warning_codes = data.pop("warning_codes", None)
    supplied_error_category = str(data.pop("error_category", "runtime_error" if outcome == "error" else ""))
    if outcome != "error" and supplied_error_category:
        return _result(BLOCKED, writer_enabled=is_run_progress_shadow_writer_enabled(enabled), run_id=str(run_id or ""), blocked_reason="metadata_error_category_not_allowed")
    if data:
        return _result(BLOCKED, writer_enabled=is_run_progress_shadow_writer_enabled(enabled), run_id=str(run_id or ""), blocked_reason="metadata_key_not_allowed")
    return update_run_progress_snapshot_shadow(
        run_id,
        stage_id=stage_id,
        terminal=True,
        error_category=supplied_error_category,
        source_component=source_component,
        mode=mode,
        warning_codes=warning_codes,
        repo_root=repo_root,
        enabled=enabled,
    )


def safe_write_run_progress_snapshot(
    run_id: Any,
    *,
    repo_root: str | Path = ".",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    enabled: Any = None,
) -> dict[str, Any]:
    """Terminal safe wrapper retained for the existing final-boundary integration."""
    try:
        return write_run_progress_snapshot_shadow(run_id, repo_root=repo_root, outcome=outcome, metadata=metadata, enabled=enabled)
    except Exception as exc:
        return _result(
            FAILED_ISOLATED,
            writer_enabled=is_run_progress_shadow_writer_enabled(enabled),
            run_id=str(run_id or ""),
            warning="snapshot_write_failed_isolated",
            blocked_reason=type(exc).__name__,
            failure_isolated=True,
        )
