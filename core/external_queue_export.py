from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.external_queue_index import load_external_queue_item_detail


EXPORT_SCHEMA_VERSION = "external_queue_export_draft_v1"
EXPORT_MODE = "external_queue_export_draft"
EXPORT_DIRNAME = "external_queue_exports"

RECOMMENDATION_TARGETS: dict[str, str] = {
    "convert_to_goal_brief_seed": "goal_brief_seed",
    "convert_to_dream_candidate": "dream_candidate_seed",
    "convert_to_project_evolution_candidate": "project_evolution_seed",
}
SUPPORTED_TARGETS: tuple[str, ...] = (
    "goal_brief_seed",
    "dream_candidate_seed",
    "project_evolution_seed",
)


def export_external_queue_item(
    repo_path: str,
    queue_id: str,
    target: str,
    *,
    dry_run: bool = False,
    output_root: str = "",
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    target_value = _text(target)
    queue_id_value = _text(queue_id)
    if target_value not in SUPPORTED_TARGETS:
        return _blocked_result(
            queue_id=queue_id_value,
            target=target_value,
            code="invalid_target",
            message=(
                "target must be one of: "
                + ", ".join(SUPPORTED_TARGETS)
            ),
        )

    detail = load_external_queue_item_detail(
        str(repo_root),
        queue_id_value,
        include_raw=True,
    )
    if not detail.get("found"):
        return {
            "ok": False,
            "status": _text(detail.get("status")) or "not_found",
            "queue_id": queue_id_value,
            "target": target_value,
            "error": detail.get("error", {}),
            "matches": detail.get("matches", []),
            "json_path": "",
            "md_path": "",
        }

    identity = _dict(detail.get("identity"))
    risk = _dict(detail.get("risk_safety"))
    raw = _dict(detail.get("raw"))
    item = _dict(raw.get("item"))
    review = _dict(raw.get("review"))
    item_path = _text(identity.get("item_path"))
    review_path = _text(identity.get("review_path"))

    if _text(detail.get("status")) == "invalid" or not item:
        return {
            "ok": False,
            "status": "invalid",
            "queue_id": _text(identity.get("queue_id")) or queue_id_value,
            "target": target_value,
            "error": {
                "code": "item_invalid",
                "message": (
                    _text(risk.get("validation_error_summary"))
                    or _text(raw.get("item_error"))
                    or "queue item is invalid"
                ),
            },
            "json_path": "",
            "md_path": "",
        }

    review_details = _dict(detail.get("review_details"))
    if not review_details.get("present"):
        return _blocked_result(
            queue_id=_text(identity.get("queue_id")) or queue_id_value,
            target=target_value,
            code="review_missing",
            message="external_queue_review.json is required before export",
        )
    if not review_details.get("valid") or not review:
        return _blocked_result(
            queue_id=_text(identity.get("queue_id")) or queue_id_value,
            target=target_value,
            code="review_invalid",
            message=_text(review_details.get("error")) or "review artifact is invalid",
        )
    if _bool(review_details.get("action_performed"), False):
        return _blocked_result(
            queue_id=_text(identity.get("queue_id")) or queue_id_value,
            target=target_value,
            code="review_action_already_performed",
            message="review action_performed must remain false for export",
        )

    recommendation = _text(review_details.get("recommendation"))
    expected_target = RECOMMENDATION_TARGETS.get(recommendation, "")
    if not expected_target:
        return _blocked_result(
            queue_id=_text(identity.get("queue_id")) or queue_id_value,
            target=target_value,
            code="unsupported_recommendation",
            message=f"review recommendation is not exportable: {recommendation or '(none)'}",
        )
    if target_value != expected_target:
        result = _blocked_result(
            queue_id=_text(identity.get("queue_id")) or queue_id_value,
            target=target_value,
            code="target_mismatch",
            message=(
                f"target {target_value} does not match review recommendation "
                f"{recommendation}; expected {expected_target}"
            ),
        )
        result["expected_target"] = expected_target
        return result

    draft_paths = _draft_paths(
        repo_root,
        _text(identity.get("queue_id")) or queue_id_value,
        target_value,
        output_root=output_root,
    )
    if not dry_run and (draft_paths["json"].exists() or draft_paths["md"].exists()):
        return {
            "ok": False,
            "status": "already_exists",
            "queue_id": _text(identity.get("queue_id")) or queue_id_value,
            "target": target_value,
            "target_recommendation": recommendation,
            "expected_target": expected_target,
            "json_path": str(draft_paths["json"]),
            "md_path": str(draft_paths["md"]),
            "error": {
                "code": "draft_already_exists",
                "message": "export draft already exists; no files were overwritten",
            },
        }

    record = build_external_queue_export_draft(
        detail=detail,
        item=item,
        review=review,
        target=target_value,
        item_path=item_path,
        review_path=review_path,
    )
    markdown = render_external_queue_export_markdown(record)

    if dry_run:
        return {
            "ok": True,
            "status": "dry_run",
            "dry_run": True,
            "queue_id": record["queue_id"],
            "target": target_value,
            "target_recommendation": recommendation,
            "expected_target": expected_target,
            "json_path": str(draft_paths["json"]),
            "md_path": str(draft_paths["md"]),
            "record": record,
            "markdown": markdown,
        }

    draft_paths["dir"].mkdir(parents=True, exist_ok=True)
    draft_paths["json"].write_text(
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    draft_paths["md"].write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "status": "draft_created",
        "dry_run": False,
        "queue_id": record["queue_id"],
        "target": target_value,
        "target_recommendation": recommendation,
        "expected_target": expected_target,
        "json_path": str(draft_paths["json"]),
        "md_path": str(draft_paths["md"]),
        "record": record,
    }


def build_external_queue_export_draft(
    *,
    detail: dict[str, Any],
    item: dict[str, Any],
    review: dict[str, Any],
    target: str,
    item_path: str,
    review_path: str,
) -> dict[str, Any]:
    identity = _dict(detail.get("identity"))
    content = _dict(detail.get("content_summary"))
    risk = _dict(detail.get("risk_safety"))
    review_details = _dict(detail.get("review_details"))
    evidence = _dict(review_details.get("evidence_summary"))
    queue_id = _text(identity.get("queue_id")) or _text(item.get("queue_id"))
    title = (
        _text(content.get("title"))
        or _text(_metadata(item).get("title"))
        or _text(item.get("query"))
        or queue_id
    )
    summary = (
        _text(content.get("summary"))
        or _text(_metadata(item).get("summary"))
        or _truncate(_text(item.get("result")), 240)
    )
    recommendation = _text(review_details.get("recommendation"))
    review_reasons = _string_list(evidence.get("reasons"))
    missing_evidence = _string_list(evidence.get("missing_evidence"))
    risk_notes = _string_list(risk.get("risk_reasons"))
    source_url = _text(item.get("source_url"))
    linked_artifacts = _linked_artifact_paths(detail)
    useful_links = _dedupe([source_url, *linked_artifacts])

    record: dict[str, Any] = {
        "mode": EXPORT_MODE,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "export_id": f"{queue_id}_{target}_draft",
        "queue_id": queue_id,
        "source_item_path": item_path,
        "source_review_path": review_path,
        "target": target,
        "target_recommendation": recommendation,
        "title": title,
        "summary": summary,
        "evidence": {
            "query": _text(item.get("query")),
            "result": _text(item.get("result")),
            "source_url": source_url,
            "review_reasons": review_reasons,
            "missing_evidence": missing_evidence,
            "linked_artifacts": linked_artifacts,
        },
        "useful_links": useful_links,
        "proposed_next_human_action": (
            _text(evidence.get("suggested_next_prompt"))
            or "Review this draft manually before starting any target workflow."
        ),
        "created_at": _utc_now_iso(),
        "export_status": "draft_created",
        "action_performed": False,
        "human_approval_required": True,
        "target_workflow_started": False,
        "model_called": False,
        "webhook_called": False,
        "patch_applied": False,
        "promotion_performed": False,
    }
    record.update(
        _target_fields(
            target=target,
            title=title,
            summary=summary,
            item=item,
            review_reasons=review_reasons,
            missing_evidence=missing_evidence,
            risk_notes=risk_notes,
            useful_links=useful_links,
            linked_artifacts=linked_artifacts,
        )
    )
    return record


def render_external_queue_export_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_external_queue_export_text(result: dict[str, Any]) -> str:
    lines = [
        "External Queue Export Draft",
        f"Status: {_text(result.get('status'))}",
        f"Queue ID: {_text(result.get('queue_id'))}",
        f"Target: {_text(result.get('target'))}",
    ]
    if result.get("expected_target"):
        lines.append(f"Expected target: {_text(result.get('expected_target'))}")
    if result.get("target_recommendation"):
        lines.append(f"Recommendation: {_text(result.get('target_recommendation'))}")
    if result.get("json_path"):
        lines.append(f"JSON path: {_text(result.get('json_path'))}")
    if result.get("md_path"):
        lines.append(f"Markdown path: {_text(result.get('md_path'))}")
    if result.get("dry_run"):
        lines.append("Dry run: True")
    error = _dict(result.get("error"))
    if error:
        lines.append(f"Reason: {_text(error.get('message'))}")
    return "\n".join(lines) + "\n"


def render_external_queue_export_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# External Queue Export Draft",
        "",
        "## Status",
        f"- Export status: `{record.get('export_status', '')}`",
        f"- Queue ID: `{record.get('queue_id', '')}`",
        f"- Target: `{record.get('target', '')}`",
        f"- Recommendation: `{record.get('target_recommendation', '')}`",
        f"- Created at: `{record.get('created_at', '')}`",
        f"- Human approval required: `{record.get('human_approval_required', True)}`",
        f"- Action performed: `{record.get('action_performed', False)}`",
        f"- Target workflow started: `{record.get('target_workflow_started', False)}`",
        "",
        "## Source",
        f"- Item: `{record.get('source_item_path', '')}`",
        f"- Review: `{record.get('source_review_path', '')}`",
        "",
        "## Draft",
        f"- Title: {record.get('title', '')}",
        f"- Summary: {record.get('summary', '')}",
        f"- Proposed next human action: {record.get('proposed_next_human_action', '')}",
        "",
        "## Safety",
        f"- Model called: `{record.get('model_called', False)}`",
        f"- Webhook called: `{record.get('webhook_called', False)}`",
        f"- Patch applied: `{record.get('patch_applied', False)}`",
        f"- Promotion performed: `{record.get('promotion_performed', False)}`",
        "",
        "## Evidence",
    ]
    evidence = _dict(record.get("evidence"))
    for key in ("query", "result", "source_url"):
        value = _text(evidence.get(key))
        if value:
            lines.append(f"- {key}: {value}")
    for reason in _string_list(evidence.get("review_reasons")):
        lines.append(f"- review reason: {reason}")
    for missing in _string_list(evidence.get("missing_evidence")):
        lines.append(f"- missing evidence: {missing}")
    lines.append("")
    return "\n".join(lines)


def _target_fields(
    *,
    target: str,
    title: str,
    summary: str,
    item: dict[str, Any],
    review_reasons: list[str],
    missing_evidence: list[str],
    risk_notes: list[str],
    useful_links: list[str],
    linked_artifacts: list[str],
) -> dict[str, Any]:
    base_constraints = [
        "Human approval is required before starting the target workflow.",
        "This export is a draft artifact only.",
    ]
    if target == "goal_brief_seed":
        return {
            "suggested_goal": title or _text(item.get("query")),
            "constraints": base_constraints,
            "likely_mode": "goal_brief_seed",
            "risk_notes": risk_notes,
            "evidence_needed": missing_evidence,
            "suggested_validation": [
                "Review the source item and review artifact.",
                "Confirm the goal is still relevant before creating a real Goal Brief.",
            ],
        }
    if target == "dream_candidate_seed":
        return {
            "dream_seed_title": title,
            "dream_seed_summary": summary,
            "research_sources": useful_links,
            "why_interesting": review_reasons[0] if review_reasons else summary,
            "risk_notes": risk_notes,
            "no_dream_run": True,
        }
    return {
        "evolution_goal": title or _text(item.get("query")),
        "affected_area_guess": _affected_area_guess(item),
        "constraints": base_constraints,
        "risk_notes": risk_notes,
        "suggested_read_first_files": linked_artifacts,
        "no_project_plan_created": True,
    }


def _draft_paths(
    repo_root: Path,
    queue_id: str,
    target: str,
    *,
    output_root: str,
) -> dict[str, Path]:
    root = _output_root(repo_root, output_root)
    safe_queue_id = _safe_segment(queue_id)
    directory = root / safe_queue_id
    return {
        "dir": directory,
        "json": directory / f"{target}_draft.json",
        "md": directory / f"{target}_draft.md",
    }


def _output_root(repo_root: Path, output_root: str) -> Path:
    if output_root:
        root = Path(output_root).expanduser()
        if not root.is_absolute():
            root = repo_root / root
        return root.resolve()
    return (repo_root / ".agent" / EXPORT_DIRNAME).resolve()


def _blocked_result(
    *,
    queue_id: str,
    target: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "blocked",
        "queue_id": queue_id,
        "target": target,
        "error": {
            "code": code,
            "message": message,
        },
        "json_path": "",
        "md_path": "",
    }


def _linked_artifact_paths(detail: dict[str, Any]) -> list[str]:
    linked = detail.get("linked_artifacts")
    if not isinstance(linked, list):
        return []
    out: list[str] = []
    for entry in linked:
        if not isinstance(entry, dict):
            continue
        path = _text(entry.get("path"))
        label = _text(entry.get("label"))
        if path and label not in {"item", "review"}:
            out.append(path)
    return _dedupe(out)


def _affected_area_guess(item: dict[str, Any]) -> str:
    metadata = _metadata(item)
    categories = _string_list(metadata.get("categories"))
    tags = _string_list(metadata.get("tags"))
    if categories:
        return ", ".join(categories)
    if tags:
        return ", ".join(tags)
    return _text(item.get("kind")) or "unknown"


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float, bool))]


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


def _safe_segment(value: str) -> str:
    chars: list[str] = []
    last_dash = False
    for char in value:
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif char in {"-", "_"}:
            chars.append(char)
            last_dash = False
        elif not last_dash and chars:
            chars.append("-")
            last_dash = True
    return "".join(chars).strip("-") or "item"


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3].rstrip() + "..."


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
