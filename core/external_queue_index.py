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


def load_external_queue_item_detail(
    repo_path: str,
    queue_id: str,
    *,
    include_raw: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    requested_queue_id = _text(queue_id)
    if not requested_queue_id:
        return _detail_error(
            queue_id=requested_queue_id,
            status="not_found",
            code="queue_id_required",
            message="queue id is required",
        )

    items = build_external_queue_index(str(repo_root))
    matches = [
        item
        for item in items
        if item.get("queue_id") == requested_queue_id
        or item.get("artifact_id") == requested_queue_id
    ]
    if not matches:
        return _detail_error(
            queue_id=requested_queue_id,
            status="not_found",
            code="queue_id_not_found",
            message=f"queue id not found: {requested_queue_id}",
        )
    if len(matches) > 1:
        return {
            "found": False,
            "status": "ambiguous",
            "queue_id": requested_queue_id,
            "error": {
                "code": "queue_id_ambiguous",
                "message": f"queue id is ambiguous: {requested_queue_id}",
            },
            "matches": [
                {
                    "queue_id": _text(match.get("queue_id")),
                    "artifact_id": _text(match.get("artifact_id")),
                    "path": _text(match.get("path")),
                    "status": _text(match.get("status")),
                }
                for match in matches
            ],
        }

    index_item = matches[0]
    item_path = Path(str(index_item.get("path", "")))
    item_load = _read_json_object(item_path)
    item, item_error = _loaded_item_or_error(item_load)

    review_path = item_path.parent / REVIEW_FILENAME
    review_load: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    review_error = ""
    if review_path.exists():
        review_load = _read_json_object(review_path)
        review, review_error = _loaded_review_or_error(review_load)

    detail = {
        "found": True,
        "status": _text(index_item.get("status")) or "unknown",
        "identity": _detail_identity(index_item, item, item_path, review_path),
        "content_summary": _detail_content_summary(index_item, item),
        "gate_status": _detail_gate_status(index_item, item, review),
        "risk_safety": _detail_risk_safety(index_item, item, item_error, review_error),
        "linked_artifacts": _detail_linked_artifacts(
            repo_root,
            dict(index_item.get("linked_paths") or {}),
        ),
        "review_details": _detail_review_details(review_path, review, review_error),
    }
    if include_raw:
        detail["raw"] = _detail_raw(item_load, review_load)
    return detail


def render_external_queue_detail_json(detail: dict[str, Any]) -> str:
    return json.dumps(detail, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_external_queue_detail_text(
    detail: dict[str, Any],
    *,
    show_review: bool = False,
    show_linked: bool = False,
    show_redaction_warnings: bool = False,
) -> str:
    if not detail.get("found"):
        error = detail.get("error") if isinstance(detail.get("error"), dict) else {}
        message = _text(error.get("message")) or "queue item was not found"
        lines = [f"External queue item {detail.get('status', 'error')}: {message}"]
        matches = detail.get("matches") if isinstance(detail.get("matches"), list) else []
        for match in matches:
            lines.append(
                "- "
                + " | ".join(
                    part
                    for part in (
                        _text(match.get("queue_id")),
                        _text(match.get("artifact_id")),
                        _text(match.get("path")),
                    )
                    if part
                )
            )
        return "\n".join(lines) + "\n"

    identity = detail.get("identity") if isinstance(detail.get("identity"), dict) else {}
    content = (
        detail.get("content_summary")
        if isinstance(detail.get("content_summary"), dict)
        else {}
    )
    gates = detail.get("gate_status") if isinstance(detail.get("gate_status"), dict) else {}
    risk = detail.get("risk_safety") if isinstance(detail.get("risk_safety"), dict) else {}
    review = (
        detail.get("review_details")
        if isinstance(detail.get("review_details"), dict)
        else {}
    )

    lines = [
        "External Queue Item Detail",
        f"Queue ID: {_text(identity.get('queue_id'))}",
        f"Status: {_text(detail.get('status'))}",
        f"Item path: {_text(identity.get('item_path'))}",
        f"Review path: {_text(identity.get('review_path')) or '(not present)'}",
        f"Source: {_text(identity.get('source_kind')) or 'unknown'}",
        f"Source label: {_text(identity.get('source_label')) or '(not provided)'}",
        f"Source channel: {_text(identity.get('source_channel')) or '(not provided)'}",
        f"Created at: {_text(identity.get('created_at')) or '(unknown)'}",
        f"Modified at: {_text(identity.get('modified_at')) or '(unknown)'}",
        "",
        "Content",
        f"Title: {_text(content.get('title')) or '(untitled)'}",
        f"Summary: {_text(content.get('summary')) or '(not provided)'}",
        f"Source URL: {_text(content.get('source_url')) or '(not provided)'}",
        f"Original message: {_text(content.get('original_message')) or '(not provided)'}",
        f"Tags: {_join_or_none(content.get('tags'))}",
        f"Categories: {_join_or_none(content.get('categories'))}",
        "",
        "Gate Status",
        f"Human review required: {gates.get('human_review_required')}",
        f"Auto dream allowed: {gates.get('auto_dream_allowed')}",
        f"Action performed: {gates.get('action_performed')}",
        f"Import status: {_text(gates.get('import_status')) or 'unknown'}",
        f"Review status: {_text(gates.get('review_status')) or 'unknown'}",
        f"Recommendation: {_text(gates.get('recommendation')) or '(none)'}",
        "",
        "Risk / Safety",
        f"Risk level: {_text(risk.get('risk_level')) or 'unknown'}",
        f"Display safety: {_text(risk.get('display_safety')) or 'unknown'}",
        f"Safe to display: {risk.get('safe_to_display')}",
        f"Validation: {_text(risk.get('validation_error_summary')) or '(none)'}",
    ]

    warning_lines = _render_warning_lines(
        risk,
        force=show_redaction_warnings,
    )
    if warning_lines:
        lines.extend(warning_lines)

    missing_links = risk.get("invalid_or_missing_linked_paths")
    if isinstance(missing_links, list) and missing_links:
        lines.append("Invalid or missing linked paths:")
        lines.extend(f"- {entry}" for entry in missing_links)

    linked = (
        detail.get("linked_artifacts")
        if isinstance(detail.get("linked_artifacts"), list)
        else []
    )
    if linked or show_linked:
        lines.extend(["", "Linked Artifacts"])
        if linked:
            for entry in linked:
                if not isinstance(entry, dict):
                    continue
                marker = "present" if entry.get("exists") else "missing"
                lines.append(
                    f"- {_text(entry.get('label'))}: {_text(entry.get('path'))} [{marker}]"
                )
        else:
            lines.append("- None")

    if review.get("present") or show_review:
        lines.extend(["", "Review Details"])
        lines.append(f"Present: {review.get('present')}")
        lines.append(f"Valid: {review.get('valid')}")
        lines.append(f"Recommendation: {_text(review.get('recommendation')) or '(none)'}")
        lines.append(f"Reason: {_text(review.get('reason')) or '(none)'}")
        lines.append(f"Human approval required: {review.get('human_approval_required')}")
        lines.append(f"Action performed: {review.get('action_performed')}")
        lines.append(f"Created at: {_text(review.get('created_at')) or '(unknown)'}")
        if review.get("error"):
            lines.append(f"Error: {_text(review.get('error'))}")
        if show_review:
            evidence = (
                review.get("evidence_summary")
                if isinstance(review.get("evidence_summary"), dict)
                else {}
            )
            lines.append("Evidence summary:")
            lines.extend(
                f"- reason: {value}"
                for value in _string_list(evidence.get("reasons"))
            )
            missing = _string_list(evidence.get("missing_evidence"))
            if missing:
                lines.append("Missing evidence:")
                lines.extend(f"- {value}" for value in missing)
            prompt = _text(evidence.get("suggested_next_prompt"))
            if prompt:
                lines.append(f"Suggested next prompt: {prompt}")

    if "raw" in detail:
        lines.extend(["", "Raw"])
        lines.append(json.dumps(detail["raw"], indent=2, sort_keys=True, ensure_ascii=False))

    return "\n".join(lines) + "\n"


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


def _detail_error(
    *,
    queue_id: str,
    status: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "found": False,
        "status": status,
        "queue_id": queue_id,
        "error": {
            "code": code,
            "message": message,
        },
        "matches": [],
    }


def _loaded_item_or_error(load_result: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if load_result.get("status") != "ok":
        return None, _text(load_result.get("message"))
    item = load_result.get("data")
    if not isinstance(item, dict):
        return None, "external_queue_item.json must be a JSON object"
    errors = _item_schema_errors(item)
    return item, "; ".join(errors)


def _loaded_review_or_error(load_result: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if load_result.get("status") != "ok":
        return None, _text(load_result.get("message"))
    review = load_result.get("data")
    if not isinstance(review, dict):
        return None, "external_queue_review.json must be a JSON object"
    errors = _review_schema_errors(review)
    if errors:
        return None, "; ".join(errors)
    return review, ""


def _detail_identity(
    index_item: dict[str, Any],
    item: dict[str, Any] | None,
    item_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    metadata = _metadata(item)
    return {
        "queue_id": _text(index_item.get("queue_id")),
        "artifact_id": _text(index_item.get("artifact_id")),
        "item_path": str(item_path),
        "review_path": str(review_path) if review_path.exists() else "",
        "source_kind": _text(index_item.get("source_kind")) or "unknown",
        "source_label": (
            _text((item or {}).get("source_label"))
            or _text(metadata.get("source_label"))
            or _text(index_item.get("source"))
            or _text(index_item.get("source_kind"))
        ),
        "source_channel": (
            _text((item or {}).get("source_channel"))
            or _text(metadata.get("source_channel"))
            or _text(metadata.get("discord_channel"))
            or _text(metadata.get("channel"))
        ),
        "created_at": _text(index_item.get("created_at")),
        "modified_at": _text(index_item.get("modified_at")),
    }


def _detail_content_summary(
    index_item: dict[str, Any],
    item: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = _metadata(item)
    safe_to_display = bool(index_item.get("safe_to_display"))
    return {
        "title": _text(index_item.get("title")),
        "summary": _text(index_item.get("summary")),
        "query": _text((item or {}).get("query")) if safe_to_display else "",
        "result": _text((item or {}).get("result")) if safe_to_display else "",
        "source_url": _text((item or {}).get("source_url")) if safe_to_display else "",
        "original_message": (
            _text((item or {}).get("source_message"))
            or _text((item or {}).get("message"))
            or _text(metadata.get("source_message"))
            or _text(metadata.get("original_message"))
            or _text(metadata.get("message"))
        ) if safe_to_display else "",
        "source_metadata": metadata if safe_to_display else {},
        "tags": _string_list((item or {}).get("tags")) or _string_list(metadata.get("tags")),
        "categories": (
            _string_list((item or {}).get("categories"))
            or _string_list(metadata.get("categories"))
        ),
    }


def _detail_gate_status(
    index_item: dict[str, Any],
    item: dict[str, Any] | None,
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "human_review_required": _bool((item or {}).get("human_review_required"), True),
        "auto_dream_allowed": _bool((item or {}).get("auto_dream_allowed"), False),
        "human_approval_required": _bool(
            (review or {}).get("human_approval_required"),
            True,
        ),
        "action_performed": _bool((review or {}).get("action_performed"), False),
        "import_status": _text(index_item.get("import_status")) or "unknown",
        "review_status": _text(index_item.get("review_status")) or "unknown",
        "recommendation": _text(index_item.get("recommendation")),
    }


def _detail_risk_safety(
    index_item: dict[str, Any],
    item: dict[str, Any] | None,
    item_error: str,
    review_error: str,
) -> dict[str, Any]:
    risk_reasons = _string_list((item or {}).get("risk_reasons"))
    redaction_warnings, secret_warnings, sensitive_warnings = _warning_groups(item)
    validation_messages = [
        _text(index_item.get("validation_error_summary")),
        item_error,
        review_error,
    ]
    safe_to_display = (
        bool(index_item.get("safe_to_display"))
        and not secret_warnings
        and not sensitive_warnings
    )
    return {
        "risk_level": _text(index_item.get("risk_level")) or "unknown",
        "risk_reasons": risk_reasons,
        "redaction_warnings": redaction_warnings,
        "secret_warnings": secret_warnings,
        "sensitive_field_warnings": sensitive_warnings,
        "safe_to_display": safe_to_display,
        "display_safety": "safe" if safe_to_display else "unsafe_or_needs_review",
        "validation_error_summary": "; ".join(_dedupe(validation_messages)),
        "invalid_or_missing_linked_paths": _missing_link_messages(index_item),
    }


def _detail_linked_artifacts(
    repo_root: Path,
    linked_paths: dict[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, value in linked_paths.items():
        path_text = _text(value)
        if not path_text:
            continue
        resolved = _resolve_linked_path(repo_root, path_text)
        out.append({
            "label": label,
            "path": path_text,
            "resolved_path": str(resolved) if resolved else "",
            "exists": bool(resolved and resolved.exists()),
        })
    return out


def _detail_review_details(
    review_path: Path,
    review: dict[str, Any] | None,
    review_error: str,
) -> dict[str, Any]:
    if not review_path.exists():
        return {
            "present": False,
            "valid": False,
            "path": "",
            "recommendation": "",
            "reason": "",
            "evidence_summary": {
                "reasons": [],
                "missing_evidence": [],
                "suggested_next_prompt": "",
            },
            "human_approval_required": True,
            "action_performed": False,
            "created_at": "",
            "error": "",
        }
    if review is None:
        return {
            "present": True,
            "valid": False,
            "path": str(review_path),
            "recommendation": "",
            "reason": "",
            "evidence_summary": {
                "reasons": [],
                "missing_evidence": [],
                "suggested_next_prompt": "",
            },
            "human_approval_required": True,
            "action_performed": False,
            "created_at": "",
            "error": review_error,
        }

    reasons = _string_list(review.get("recommendation_reasons"))
    reason = _text(review.get("reason")) or (reasons[0] if reasons else "")
    return {
        "present": True,
        "valid": True,
        "path": str(review_path),
        "recommendation": _text(review.get("recommendation")),
        "reason": reason,
        "evidence_summary": {
            "reasons": reasons,
            "missing_evidence": _string_list(review.get("missing_evidence")),
            "suggested_next_prompt": _text(review.get("suggested_next_prompt")),
        },
        "human_approval_required": _bool(review.get("human_approval_required"), True),
        "action_performed": _bool(review.get("action_performed"), False),
        "created_at": _first_text(review, ("created_at", "generated_at")),
        "error": "",
    }


def _detail_raw(
    item_load: dict[str, Any],
    review_load: dict[str, Any] | None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    if item_load.get("status") == "ok":
        raw["item"] = item_load.get("data")
    else:
        raw["item_error"] = _text(item_load.get("message"))
    if review_load is not None:
        if review_load.get("status") == "ok":
            raw["review"] = review_load.get("data")
        else:
            raw["review_error"] = _text(review_load.get("message"))
    return raw


def _metadata(item: dict[str, Any] | None) -> dict[str, Any]:
    metadata = (item or {}).get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _warning_groups(
    item: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    candidates: list[str] = []
    if item:
        for key in (
            "risk_reasons",
            "reviewer_checklist",
            "redaction_warnings",
            "redaction_reasons",
            "secret_warnings",
            "secret_reasons",
            "sensitive_field_warnings",
            "sensitive_fields",
        ):
            candidates.extend(_string_list(item.get(key)))

    redaction: list[str] = []
    secrets: list[str] = []
    sensitive: list[str] = []
    for value in candidates:
        lowered = value.lower()
        if "redact" in lowered:
            redaction.append(value)
        if (
            "possible secret" in lowered
            or "secret" in lowered
            or "token" in lowered
            or "password" in lowered
            or "credential" in lowered
            or "api_key" in lowered
            or "api key" in lowered
        ):
            secrets.append(value)
        if "sensitive" in lowered:
            sensitive.append(value)
    return _dedupe(redaction), _dedupe(secrets), _dedupe(sensitive)


def _missing_link_messages(index_item: dict[str, Any]) -> list[str]:
    summary = _text(index_item.get("validation_error_summary"))
    missing: list[str] = []
    for part in summary.split(";"):
        message = part.strip()
        prefix = "linked path missing: "
        if message.startswith(prefix):
            missing.append(message[len(prefix):])
    return missing


def _join_or_none(value: Any) -> str:
    items = _string_list(value)
    return ", ".join(items) if items else "(none)"


def _render_warning_lines(
    risk: dict[str, Any],
    *,
    force: bool,
) -> list[str]:
    lines: list[str] = []
    groups = (
        ("Redaction warnings", risk.get("redaction_warnings")),
        ("Secret warnings", risk.get("secret_warnings")),
        ("Sensitive-field warnings", risk.get("sensitive_field_warnings")),
    )
    for title, values in groups:
        items = _string_list(values)
        if not items and not force:
            continue
        lines.append(f"{title}:")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("- None")
    return lines


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
