from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXTERNAL_QUEUE_DIRNAME = "external_queue"
ITEM_FILENAME = "external_queue_item.json"
REVIEW_FILENAME = "external_queue_review.json"

IMPORT_SCHEMA_VERSION = "external_queue_import_v1"
IMPORT_MODE = "external_queue_import"
REVIEW_SCHEMA_VERSION = "external_queue_review_v1"
REVIEW_MODE = "external_queue_review"

_SOURCE_KINDS = frozenset({"discord", "n8n", "manual"})
_KNOWN_STATUSES = frozenset({"queued", "reviewed", "rejected", "promoted", "invalid", "unknown"})
_PROMOTABLE_RECOMMENDATIONS = frozenset({
    "convert_to_goal_brief_seed",
    "convert_to_dream_candidate",
    "convert_to_project_evolution_candidate",
})


def build_external_queue_index(
    repo_path: str,
    *,
    status: str = "",
    source: str = "",
    kind: str = "",
    risk: str = "",
    recommendation: str = "",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    repo_root = Path(repo_path).expanduser().resolve()
    queue_root = (repo_root / ".agent" / EXTERNAL_QUEUE_DIRNAME).resolve()
    if not queue_root.exists():
        return []

    item_paths = sorted(
        queue_root.rglob(ITEM_FILENAME),
        key=lambda p: _path_sort_key(queue_root, p),
    )
    items = [_build_index_item(repo_root, queue_root, path) for path in item_paths]
    items = _filter_items(
        items,
        status=status,
        source=source,
        kind=kind,
        risk=risk,
        recommendation=recommendation,
    )
    if limit is not None:
        items = items[: max(0, limit)]
    return items


def render_external_queue_index_json(items: list[dict[str, Any]]) -> str:
    return json.dumps(items, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_external_queue_index_table(items: list[dict[str, Any]]) -> str:
    columns = [
        ("QUEUE ID", "queue_id", 34),
        ("STATUS", "status", 9),
        ("SOURCE", "source_kind", 7),
        ("RISK", "risk_level", 7),
        ("RECOMMENDATION", "recommendation", 34),
        ("MODIFIED", "modified_at", 20),
        ("TITLE", "title", 48),
    ]
    rows = [
        [_truncate(str(item.get(key, "") or ""), max_width) for _, key, max_width in columns]
        for item in items
    ]
    widths = []
    for idx, (header, _key, max_width) in enumerate(columns):
        content_width = max([len(row[idx]) for row in rows] + [len(header)])
        widths.append(min(content_width, max_width))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, (header, _, _) in enumerate(columns))
    divider = "-+-".join("-" * width for width in widths)
    body = [
        " | ".join(row[idx].ljust(widths[idx]) for idx in range(len(columns)))
        for row in rows
    ]
    if not body:
        body = ["(empty)"]
    return "\n".join([header_line, divider, *body]) + "\n"


def _build_index_item(repo_root: Path, queue_root: Path, item_path: Path) -> dict[str, Any]:
    artifact_id = _artifact_id(queue_root, item_path)
    modified_at = _file_mtime_iso(item_path)
    item_load = _read_json_object(item_path)
    if item_load["status"] != "ok":
        return _invalid_index_item(
            artifact_id=artifact_id,
            item_path=item_path,
            modified_at=modified_at,
            validation_error_summary=item_load["message"],
        )

    item = item_load["data"]
    item_errors = _item_schema_errors(item)
    if item_errors:
        return _invalid_index_item(
            artifact_id=str(item.get("queue_id") or artifact_id),
            item_path=item_path,
            modified_at=modified_at,
            validation_error_summary="; ".join(item_errors),
        )

    review_path = item_path.parent / REVIEW_FILENAME
    review: dict[str, Any] | None = None
    invalid_review: dict[str, Any] | None = None
    review_errors: list[str] = []
    if review_path.exists():
        review_load = _read_json_object(review_path)
        if review_load["status"] == "ok":
            candidate_review = review_load["data"]
            review_errors.extend(_review_schema_errors(candidate_review))
            if review_errors:
                invalid_review = candidate_review
            else:
                review = candidate_review
        else:
            review_errors.append(review_load["message"])

    linked_paths, linked_errors = _linked_paths(
        repo_root,
        item_path,
        review_path,
        item,
        review or invalid_review,
    )
    validation_errors = list(review_errors) + linked_errors
    error_summary = _validation_summary(item, review or invalid_review, validation_errors)
    recommendation_value = _text(review.get("recommendation")) if review else ""

    risk_reasons = _string_list(item.get("risk_reasons"))
    safe_to_display = not any("possible secret detected" in reason.lower() for reason in risk_reasons)
    status_value = _derive_status(item, review, recommendation_value)

    return {
        "queue_id": str(item.get("queue_id") or artifact_id),
        "artifact_id": artifact_id,
        "path": str(item_path),
        "title": _title(item),
        "summary": _summary(item),
        "source_kind": _source_kind(item.get("source")),
        "source": _text(item.get("source")) or "unknown",
        "kind": _text(item.get("kind")) or "unknown",
        "created_at": _first_text(item, ("created_at", "generated_at", "received_at")),
        "modified_at": modified_at,
        "status": status_value,
        "import_status": _text(item.get("import_status")) or "unknown",
        "review_status": _text(review.get("status")) if review else ("invalid" if review_errors else "missing"),
        "risk_level": _risk_level(item.get("risk_level")),
        "gate_status": _gate_status(item, review),
        "recommendation": recommendation_value,
        "recommendation_confidence": _text(review.get("recommendation_confidence")) if review else "",
        "linked_paths": linked_paths,
        "validation_error_summary": error_summary,
        "safe_to_display": safe_to_display,
        "executable_or_promotable": (
            status_value == "reviewed"
            and recommendation_value in _PROMOTABLE_RECOMMENDATIONS
            and _bool(review.get("human_approval_required"), True)
            and not _bool(review.get("action_performed"), False)
        ) if review else False,
    }


def _invalid_index_item(
    *,
    artifact_id: str,
    item_path: Path,
    modified_at: str,
    validation_error_summary: str,
) -> dict[str, Any]:
    return {
        "queue_id": artifact_id,
        "artifact_id": artifact_id,
        "path": str(item_path),
        "title": "",
        "summary": "",
        "source_kind": "unknown",
        "source": "unknown",
        "kind": "unknown",
        "created_at": "",
        "modified_at": modified_at,
        "status": "invalid",
        "import_status": "unknown",
        "review_status": "missing",
        "risk_level": "unknown",
        "gate_status": {},
        "recommendation": "",
        "recommendation_confidence": "",
        "linked_paths": {"item": str(item_path)},
        "validation_error_summary": validation_error_summary,
        "safe_to_display": False,
        "executable_or_promotable": False,
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "message": f"{path.name} is not valid JSON ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "message": f"{path.name} could not be read ({exc})",
        }
    if not isinstance(raw, dict):
        return {
            "status": "error",
            "message": f"{path.name} must be a JSON object",
        }
    return {"status": "ok", "data": raw}


def _item_schema_errors(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if item.get("mode") != IMPORT_MODE:
        errors.append(f"expected mode '{IMPORT_MODE}', got '{item.get('mode', '')}'")
    if item.get("schema_version") != IMPORT_SCHEMA_VERSION:
        errors.append(
            f"expected schema_version '{IMPORT_SCHEMA_VERSION}', "
            f"got '{item.get('schema_version', '')}'"
        )
    if item.get("status") == "error":
        errors.append(_error_message(item) or "queue item status is error")
    return errors


def _review_schema_errors(review: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if review.get("mode") != REVIEW_MODE:
        errors.append(f"review expected mode '{REVIEW_MODE}', got '{review.get('mode', '')}'")
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        errors.append(
            f"review expected schema_version '{REVIEW_SCHEMA_VERSION}', "
            f"got '{review.get('schema_version', '')}'"
        )
    if review.get("status") == "error":
        errors.append(_error_message(review) or "review status is error")
    return errors


def _derive_status(
    item: dict[str, Any],
    review: dict[str, Any] | None,
    recommendation: str,
) -> str:
    import_status = _text(item.get("import_status")).lower()
    if import_status in {"promoted", "rejected", "reviewed"}:
        return import_status
    if recommendation == "reject":
        return "rejected"
    if review:
        return "reviewed"
    if import_status in {"pending_review", "queued", ""}:
        return "queued"
    if import_status in _KNOWN_STATUSES:
        return import_status
    return "unknown"


def _gate_status(item: dict[str, Any], review: dict[str, Any] | None) -> dict[str, Any]:
    gates: dict[str, Any] = {}
    for key in ("auto_dream_allowed", "human_review_required", "import_status"):
        if key in item:
            gates[key] = item[key]
    if review:
        for key in ("human_approval_required", "action_performed"):
            if key in review:
                gates[key] = review[key]
    return gates


def _linked_paths(
    repo_root: Path,
    item_path: Path,
    review_path: Path,
    item: dict[str, Any],
    review: dict[str, Any] | None,
) -> tuple[dict[str, str], list[str]]:
    linked = {"item": str(item_path)}
    errors: list[str] = []
    if review_path.exists():
        linked["review"] = str(review_path)

    for source in (item, review or {}):
        for key in (
            "source_item_path",
            "proposal_path",
            "linked_proposal_path",
            "report_path",
            "linked_report_path",
            "validation_report_path",
            "review_json_path",
            "review_md_path",
            "md_path",
        ):
            value = _text(source.get(key))
            if not value:
                continue
            linked[key] = value
            resolved = _resolve_linked_path(repo_root, value)
            if resolved and not resolved.exists():
                errors.append(f"linked path missing: {key}={value}")
    return linked, errors


def _resolve_linked_path(repo_root: Path, value: str) -> Path | None:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        return candidate.expanduser().resolve()
    except OSError:
        return None


def _validation_summary(
    item: dict[str, Any],
    review: dict[str, Any] | None,
    validation_errors: list[str],
) -> str:
    messages = list(validation_errors)
    item_error = _error_message(item)
    if item_error:
        messages.append(item_error)
    if review:
        review_error = _error_message(review)
        if review_error:
            messages.append(review_error)
    return "; ".join(_dedupe(messages))


def _title(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return (
        _text(item.get("title"))
        or _text(metadata.get("title"))
        or _truncate(_text(item.get("query")), 96)
    )


def _summary(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return (
        _text(item.get("summary"))
        or _text(metadata.get("summary"))
        or _truncate(_text(item.get("result")), 180)
    )


def _source_kind(value: Any) -> str:
    source = _text(value).lower()
    return source if source in _SOURCE_KINDS else "unknown"


def _risk_level(value: Any) -> str:
    risk = _text(value).lower()
    return risk if risk in {"low", "medium", "high"} else "unknown"


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float, bool))]


def _error_message(data: dict[str, Any]) -> str:
    error = data.get("error")
    if isinstance(error, dict):
        return _text(error.get("message"))
    return ""


def _filter_items(
    items: list[dict[str, Any]],
    *,
    status: str,
    source: str,
    kind: str,
    risk: str,
    recommendation: str,
) -> list[dict[str, Any]]:
    status_filter = status.strip().lower()
    source_filter = source.strip().lower()
    kind_filter = kind.strip().lower()
    risk_filter = risk.strip().lower()
    recommendation_filter = recommendation.strip().lower()
    return [
        item
        for item in items
        if (not status_filter or item["status"] == status_filter)
        and (not source_filter or item["source_kind"] == source_filter)
        and (not kind_filter or item["kind"].lower() == kind_filter)
        and (not risk_filter or item["risk_level"] == risk_filter)
        and (
            not recommendation_filter
            or item["recommendation"].lower() == recommendation_filter
        )
    ]


def _artifact_id(queue_root: Path, item_path: Path) -> str:
    try:
        relative = item_path.parent.relative_to(queue_root)
    except ValueError:
        return item_path.parent.name or item_path.stem
    text = str(relative).replace("\\", "/").strip("/")
    return text or item_path.stem


def _path_sort_key(queue_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(queue_root)).replace("\\", "/").lower()
    except ValueError:
        return str(path).replace("\\", "/").lower()


def _file_mtime_iso(path: Path) -> str:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip() + "..."


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
