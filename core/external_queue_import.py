from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "external_queue_import"
SCHEMA_VERSION = "external_queue_import_v1"
EXTERNAL_QUEUE_DIRNAME = "external_queue"

RESULT_MAX_CHARS = 4096
METADATA_MAX_DEPTH = 4
METADATA_MAX_BYTES = 32_768

_KNOWN_SOURCES: frozenset[str] = frozenset({"discord", "n8n", "zalo", "webhook", "manual"})
_KNOWN_KINDS: frozenset[str] = frozenset({
    "research_wishlist",
    "bug_seed",
    "project_evolution_seed",
    "lesson_candidate_seed",
})

_ALLOWED_NEXT_STEPS: list[str] = [
    "review_manually",
    "convert_to_dream_candidate",
    "convert_to_project_evolution_candidate",
    "convert_to_goal_brief_seed",
    "reject",
]
_FORBIDDEN_NEXT_STEPS: list[str] = [
    "auto_dream",
    "auto_patch",
    "apply_patch",
    "modify_real_repo",
    "promote_lesson_without_review",
    "run_subagent_without_approval",
]

# (label, pattern, replacement) — applied in order to query and result
_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    ("api_key_sk", r'sk-[A-Za-z0-9]{16,}', '[REDACTED_SECRET]'),
    ("github_pat", r'ghp_[A-Za-z0-9]{36,}', '[REDACTED_SECRET]'),
    ("aws_access_key", r'AKIA[A-Z2-7]{16}', '[REDACTED_SECRET]'),
    ("bearer_token", r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*', r'\1[REDACTED_SECRET]'),
    ("password_assignment", r'(password\s*[=:])\s*\S+', r'\1[REDACTED_SECRET]'),
    ("secret_assignment", r'(secret\s*[=:])\s*\S+', r'\1[REDACTED_SECRET]'),
    ("token_assignment", r'(token\s*[=:])\s*\S+', r'\1[REDACTED_SECRET]'),
    ("api_key_assignment", r'(api[_-]?key\s*[=:])\s*\S+', r'\1[REDACTED_SECRET]'),
]

_HIGH_RISK_PHRASES: frozenset[str] = frozenset({
    "apply patch",
    "auto patch",
    "auto-patch",
    "apply_patch",
    "push to",
    "commit to",
    "modify repo",
    "mutate repo",
    "server mutation",
    "production deploy",
    "deploy to prod",
    "deploy to production",
    "force push",
})
_HIGH_RISK_WORDS: frozenset[str] = frozenset({
    "credential",
    "credentials",
    "deploy",
    "password",
})
_HIGH_RISK_MIGRATION_APPLY: frozenset[str] = frozenset({
    "apply",
    "patch",
    "push",
    "commit",
    "deploy",
    "mutate",
    "modify",
})
_MEDIUM_RISK_PHRASES: frozenset[str] = frozenset({
    "architecture",
    "broad migration",
    "refactor everything",
    "migrate from",
    "migrate to",
    "big refactor",
})
_FILE_REF_SIGNALS: tuple[str, ...] = (".py", ".ts", ".js", ".go", ".rs", ".java", "/", "\\")


def build_external_queue_item(
    *,
    repo_path: str,
    source: str,
    kind: str,
    query: str,
    result: str = "",
    source_url: str = "",
    submitted_by: str = "",
    received_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()

    source_norm = _normalize_source(source)
    kind_norm = _normalize_kind(kind)
    query_norm = str(query).strip() if query is not None else ""

    if not query_norm:
        return _build_error_record(
            message="query must not be empty",
            code="empty_query",
        )

    result_norm = _truncate_result(str(result).strip() if result is not None else "")
    source_url_norm = str(source_url).strip() if source_url else ""
    submitted_by_norm = str(submitted_by).strip() if submitted_by else ""
    received_at_norm = _normalize_timestamp(received_at)
    metadata_norm = _sanitize_metadata(metadata or {})

    # Secret scan and redact
    query_clean, secret_reasons_q = _process_text_for_secrets(query_norm)
    result_clean, secret_reasons_r = _process_text_for_secrets(result_norm)
    secret_reasons = _deduplicate_list(secret_reasons_q + secret_reasons_r)

    generated_at = _utc_now_iso()
    queue_id = _make_queue_id(source_norm, query_clean, generated_at)

    risk_level, risk_reasons = _classify_risk(
        kind=kind_norm,
        query=query_clean,
        result=result_clean,
        secret_reasons=secret_reasons,
    )

    reviewer_checklist = _build_reviewer_checklist(risk_level, secret_reasons)

    return {
        "generated_at": generated_at,
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "queue_id": queue_id,
        "source": source_norm,
        "kind": kind_norm,
        "query": query_clean,
        "result": result_clean,
        "source_url": source_url_norm,
        "submitted_by": submitted_by_norm,
        "received_at": received_at_norm,
        "auto_dream_allowed": False,
        "human_review_required": True,
        "import_status": "pending_review",
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "allowed_next_steps": list(_ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(_FORBIDDEN_NEXT_STEPS),
        "reviewer_checklist": reviewer_checklist,
        "metadata": metadata_norm,
    }


def _classify_risk(
    *,
    kind: str,
    query: str,
    result: str,
    secret_reasons: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    text_lower = (query + " " + result).lower()

    # HIGH: secrets detected
    if secret_reasons:
        reasons.extend(secret_reasons)

    # HIGH: direct mutation/apply phrases
    for phrase in _HIGH_RISK_PHRASES:
        if phrase in text_lower:
            reasons.append(f"mutation/apply keyword: '{phrase}'")
            break

    # HIGH: project evolution + apply keywords
    if kind == "project_evolution_seed":
        if any(word in text_lower for word in _HIGH_RISK_MIGRATION_APPLY):
            reasons.append(
                "project_evolution_seed with apply/patch/deploy action keyword"
            )

    # HIGH: standalone dangerous words
    for word in _HIGH_RISK_WORDS:
        if _word_boundary_match(word, text_lower):
            reasons.append(f"high-risk keyword: '{word}'")
            break

    if reasons:
        return "high", reasons

    # MEDIUM
    med_reasons: list[str] = []
    if kind == "project_evolution_seed":
        med_reasons.append(
            "project_evolution_seed without apply/deploy keywords (planning-only)"
        )
    for phrase in _MEDIUM_RISK_PHRASES:
        if phrase in text_lower:
            med_reasons.append(f"broad/architecture keyword: '{phrase}'")
            break
    if not result:
        med_reasons.append("no result provided")
    if len(query) > 300 and not any(sig in query for sig in _FILE_REF_SIGNALS):
        med_reasons.append("long query without concrete file references")

    if med_reasons:
        return "medium", med_reasons

    return "low", ["narrow research item with no mutation request"]


def _process_text_for_secrets(text: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    for label, pattern, replacement in _SECRET_PATTERNS:
        new_text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
        if count:
            reasons.append(f"possible secret detected: {label}")
            text = new_text
    return text, reasons


def _build_reviewer_checklist(risk_level: str, secret_reasons: list[str]) -> list[str]:
    checklist = [
        "Confirm this item came from an authorized and expected source.",
        "Verify the query is relevant and not a test payload or injection attempt.",
        "Review risk_level and risk_reasons before selecting any next step.",
        "Do not trigger Dream automatically — auto_dream_allowed is false.",
        "Do not apply patches from this artifact — it is review-only.",
        "Select one of the allowed_next_steps or reject the item.",
    ]
    if secret_reasons:
        checklist.append(
            "WARNING: possible secret detected — investigate source before sharing this artifact."
        )
    if risk_level == "high":
        checklist.append(
            "HIGH RISK: do not convert to any active mode without additional human review."
        )
    checklist.append(
        "Remove or archive this item from the review queue after action is taken."
    )
    return checklist


def render_external_queue_item_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# External Queue Item",
        "",
        "## Status",
        f"- Import status: `{record.get('import_status', 'pending_review')}`",
        f"- Human review required: `{record.get('human_review_required', True)}`",
        f"- Auto dream allowed: `{record.get('auto_dream_allowed', False)}`",
        f"- Queue ID: `{record.get('queue_id', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        "",
        "## Source",
        f"- Source: `{record.get('source', '')}`",
        f"- Kind: `{record.get('kind', '')}`",
        f"- Submitted by: `{record.get('submitted_by', '') or '(not provided)'}`",
        f"- Source URL: `{record.get('source_url', '') or '(not provided)'}`",
        f"- Received at: `{record.get('received_at', '') or '(not provided)'}`",
        "",
        "## Query",
        "",
        record.get("query", ""),
        "",
        "## Result Summary",
        "",
    ]
    result = record.get("result", "")
    if result:
        lines.append(result)
    else:
        lines.append("*(no result provided)*")
    lines += [
        "",
        "## Risk",
        f"- Risk level: **{str(record.get('risk_level', 'unknown')).upper()}**",
        "- Risk reasons:",
        *_render_string_list(record.get("risk_reasons", [])),
        "",
        "## Allowed Next Steps",
        *_render_string_list(record.get("allowed_next_steps", [])),
        "",
        "## Forbidden Next Steps",
        *_render_string_list(record.get("forbidden_next_steps", [])),
        "",
        "## Reviewer Checklist",
        *_render_string_list(record.get("reviewer_checklist", [])),
        "",
        "## Guardrails",
        "- This item is review-only.",
        "- It cannot trigger Dream automatically.",
        "- It cannot apply patches.",
        "- It cannot modify the real repository.",
        "- Human review is required before conversion into any stronger mode.",
        "",
    ]
    if record.get("status") == "error" and record.get("error"):
        lines += [
            "## Error",
            f"- {record['error']['message']}",
            "",
        ]
    return "\n".join(lines)


def write_external_queue_item_artifacts(
    *,
    repo_path: str,
    source: str,
    kind: str,
    query: str,
    result: str = "",
    source_url: str = "",
    submitted_by: str = "",
    received_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_external_queue_item(
        repo_path=str(repo_root),
        source=source,
        kind=kind,
        query=query,
        result=result,
        source_url=source_url,
        submitted_by=submitted_by,
        received_at=received_at,
        metadata=metadata,
    )
    if record.get("status") == "error":
        return {"record": record, "json_path": "", "md_path": ""}

    output_dir = _resolve_output_dir(repo_root, record["queue_id"])
    if output_dir is None:
        error = _build_error_record(
            message="could not resolve safe output directory for queue item",
            code="output_dir_unsafe",
        )
        return {"record": error, "json_path": "", "md_path": ""}

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "external_queue_item.json"
    md_path = output_dir / "external_queue_item.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_external_queue_item_markdown(record), encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def load_external_queue_item_from_json(input_path: str) -> dict[str, Any]:
    path = Path(input_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if not path.exists():
        return {
            "status": "error",
            "code": "input_file_missing",
            "message": f"input JSON file does not exist: {path.name}",
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "code": "input_file_invalid_json",
            "message": f"input JSON file is not valid JSON ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "code": "input_file_unreadable",
            "message": f"input JSON file could not be read ({exc})",
        }
    if not isinstance(raw, dict):
        return {
            "status": "error",
            "code": "input_file_not_object",
            "message": "input JSON must be a JSON object",
        }
    return {"status": "ok", "data": raw}


def _normalize_source(value: Any) -> str:
    text = str(value).strip().lower() if value else ""
    return text if text in _KNOWN_SOURCES else "manual"


def _normalize_kind(value: Any) -> str:
    text = str(value).strip().lower() if value else ""
    return text if text in _KNOWN_KINDS else "research_wishlist"


def _truncate_result(text: str) -> str:
    if len(text) <= RESULT_MAX_CHARS:
        return text
    return text[:RESULT_MAX_CHARS] + f"\n... [truncated at {RESULT_MAX_CHARS} chars]"


def _normalize_timestamp(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return text
    except ValueError:
        return ""


def _sanitize_metadata(
    value: Any,
    *,
    _depth: int = 0,
) -> Any:
    if _depth >= METADATA_MAX_DEPTH:
        return "[truncated: max depth exceeded]"
    if isinstance(value, dict):
        return {
            str(k): _sanitize_metadata(v, _depth=_depth + 1)
            for k, v in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_sanitize_metadata(v, _depth=_depth + 1) for v in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _check_metadata_size(metadata: dict[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(metadata, ensure_ascii=False)
    except (TypeError, ValueError):
        return {}
    if len(serialized.encode("utf-8")) > METADATA_MAX_BYTES:
        return {"_truncated": True, "_reason": "metadata exceeded size limit"}
    return metadata


def _make_queue_id(source: str, query: str, generated_at: str) -> str:
    timestamp = _safe_timestamp(generated_at)
    slug = _slugify(f"{source}-{query[:20]}")
    return f"{timestamp}_{slug}" if slug else timestamp


def _resolve_output_dir(repo_root: Path, queue_id: str) -> Path | None:
    safe_id = _slugify(queue_id)
    if not safe_id:
        return None
    root = (repo_root / ".agent" / EXTERNAL_QUEUE_DIRNAME).resolve()
    output_dir = (root / safe_id).resolve()
    try:
        output_dir.relative_to(root)
    except ValueError:
        return None
    return output_dir


def _build_error_record(*, message: str, code: str) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {"code": code, "message": message},
        "queue_id": "",
        "source": "",
        "kind": "",
        "query": "",
        "result": "",
        "source_url": "",
        "submitted_by": "",
        "received_at": "",
        "auto_dream_allowed": False,
        "human_review_required": True,
        "import_status": "pending_review",
        "risk_level": "unknown",
        "risk_reasons": [],
        "allowed_next_steps": list(_ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(_FORBIDDEN_NEXT_STEPS),
        "reviewer_checklist": [],
        "metadata": {},
    }


def _word_boundary_match(word: str, text: str) -> bool:
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text))


def _deduplicate_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _render_string_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _slugify(text: str) -> str:
    slug: list[str] = []
    last_was_dash = False
    for char in text.lower():
        if char.isalnum():
            slug.append(char)
            last_was_dash = False
        elif not last_was_dash and slug:
            slug.append("-")
            last_was_dash = True
    return "".join(slug).strip("-") or "item"


def _safe_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
