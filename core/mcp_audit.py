"""Bounded audit ledger for MCP invocation summaries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import get_agent_dir


AUDIT_DIRNAME = "mcp_audit"
INVOCATIONS_FILENAME = "invocations.jsonl"
MAX_CONTEXT_SUMMARY_CHARS = 500
MAX_AUDIT_STRING_CHARS = 1000


def _audit_path() -> Path:
    return get_agent_dir(None) / AUDIT_DIRNAME / INVOCATIONS_FILENAME


def _truncate_string(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def _sanitize_value(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            _truncate_string(str(item_key), MAX_AUDIT_STRING_CHARS): _sanitize_value(
                item_value,
                key=str(item_key),
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        limit = (
            MAX_CONTEXT_SUMMARY_CHARS
            if key == "context_summary"
            else MAX_AUDIT_STRING_CHARS
        )
        return _truncate_string(value, limit)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _truncate_string(str(value), MAX_AUDIT_STRING_CHARS)


def _sanitize_summary(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return {}
    return _sanitize_value(summary)


def record_mcp_invocation(
    *,
    tool_name: str,
    capability_mode: str,
    allowed: bool,
    input_summary: dict | None = None,
    result_summary: dict | None = None,
    artifacts: list[str] | None = None,
    error: str | None = None,
) -> dict:
    """Append one sanitized MCP invocation event and return it."""
    event = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool_name": _truncate_string(str(tool_name), MAX_AUDIT_STRING_CHARS),
        "capability_mode": _truncate_string(
            str(capability_mode),
            MAX_AUDIT_STRING_CHARS,
        ),
        "allowed": bool(allowed),
        "input_summary": _sanitize_summary(input_summary),
        "result_summary": (
            _sanitize_summary(result_summary)
            if result_summary is not None
            else None
        ),
        "artifacts": _sanitize_value(list(artifacts or [])),
        "error": (
            _truncate_string(str(error), MAX_AUDIT_STRING_CHARS)
            if error is not None
            else None
        ),
    }

    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def list_mcp_invocations(limit: int = 50) -> list[dict]:
    """Return recent valid MCP invocation events, newest first."""
    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError):
        normalized_limit = 50
    if normalized_limit <= 0:
        return []

    path = _audit_path()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except (FileNotFoundError, OSError):
        return []

    events: list[dict] = []
    for line in reversed(lines):
        if len(events) >= normalized_limit:
            break
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events
