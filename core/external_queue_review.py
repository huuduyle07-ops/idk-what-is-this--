from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "external_queue_review"
SCHEMA_VERSION = "external_queue_review_v1"
IMPORT_SCHEMA_VERSION = "external_queue_import_v1"
EXTERNAL_QUEUE_DIRNAME = "external_queue"

_REQUIRED_ITEM_FIELDS: tuple[str, ...] = (
    "queue_id",
    "mode",
    "schema_version",
    "source",
    "kind",
    "query",
    "import_status",
)

_ALLOWED_NEXT_STEPS: list[str] = [
    "review_manually",
    "reject",
    "create_goal_brief_seed_manually",
    "create_dream_candidate_manually",
    "create_project_evolution_candidate_manually",
]

_FORBIDDEN_NEXT_STEPS: list[str] = [
    "auto_dream",
    "auto_patch",
    "apply_patch",
    "modify_real_repo",
    "promote_lesson_without_review",
    "run_subagent_without_approval",
    "convert_without_human_approval",
]

_GUARDRAIL_LINES: tuple[str, ...] = (
    "This review is advisory only.",
    "No conversion was performed.",
    "No Dream item was created.",
    "No Project Evolution plan was created.",
    "No patch was generated or applied.",
    "Human approval is required before entering any stronger mode.",
)

_REJECT_PHRASES: frozenset[str] = frozenset({
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
    "force-push",
})

_BYPASS_SAFETY_PHRASES: frozenset[str] = frozenset({
    "bypass safety",
    "skip safety",
    "ignore safety",
    "disable safety",
    "override safety",
    "no-verify",
    "--no-verify",
})

_PROJECT_EVOLUTION_PHRASES: frozenset[str] = frozenset({
    "migrate from",
    "migrate to",
    "architecture",
    "broad migration",
    "big refactor",
    "refactor everything",
})

_GOAL_INTENT_PATTERNS: tuple[str, ...] = (
    "i want",
    "we want",
    "we need",
    "i need",
    "can we",
    "how to",
    "how do we",
    "should we",
    "is there a way to",
    "what would it take",
)

_FILE_REF_SIGNALS: tuple[str, ...] = (".py", ".ts", ".js", ".go", ".rs", ".java", "/", "\\")

_SUGGESTED_PROMPTS: dict[str, str] = {
    "reject": (
        "Reject this item. Do not import it into stronger modes."
    ),
    "needs_more_evidence": (
        "Review this item manually. Add more context or a result before deciding on conversion."
    ),
    "convert_to_goal_brief_seed": (
        "Use this external queue item as evidence for a Goal Brief. "
        "Ask clarifying questions before any patch."
    ),
    "convert_to_dream_candidate": (
        "Create a Dream candidate from this reviewed item. Keep auto-apply disabled."
    ),
    "convert_to_project_evolution_candidate": (
        "Create a Project Evolution candidate. Produce a plan only; no patch application."
    ),
}


def build_external_queue_review(
    repo_path: str,
    item_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()

    resolved_item = _resolve_item_path(repo_root, item_path)
    if resolved_item is None:
        return _build_error_record(
            source_item_path=item_path,
            message=(
                "item path must be inside .agent/external_queue/ "
                "and must not use path traversal"
            ),
            code="item_path_outside_external_queue",
        )

    load_result = _load_and_validate_item(resolved_item)
    if load_result["status"] != "ok":
        return _build_error_record(
            source_item_path=str(resolved_item),
            message=load_result["message"],
            code=load_result["code"],
        )

    item = load_result["data"]
    queue_id = item.get("queue_id", "")
    source = item.get("source", "")
    kind = item.get("kind", "")
    query = item.get("query", "")
    result = item.get("result", "")
    import_status = item.get("import_status", "")
    source_risk_level = item.get("risk_level", "unknown")
    risk_reasons = item.get("risk_reasons", [])
    source_url = item.get("source_url", "")

    recommendation, confidence, reasons, missing_evidence = _recommend(
        kind=kind,
        query=query,
        result=result,
        source_risk_level=source_risk_level,
        risk_reasons=risk_reasons,
        source_url=source_url,
    )

    suggested_next_prompt = _SUGGESTED_PROMPTS.get(
        recommendation,
        "Review this item manually before taking any action.",
    )

    return {
        "generated_at": _utc_now_iso(),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "queue_id": queue_id,
        "source_item_path": str(resolved_item),
        "source": source,
        "kind": kind,
        "query": query,
        "import_status": import_status,
        "source_risk_level": source_risk_level,
        "recommendation": recommendation,
        "recommendation_confidence": confidence,
        "recommendation_reasons": reasons,
        "missing_evidence": missing_evidence,
        "suggested_next_prompt": suggested_next_prompt,
        "allowed_next_steps": list(_ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(_FORBIDDEN_NEXT_STEPS),
        "human_approval_required": True,
        "action_performed": False,
        "guardrails": list(_GUARDRAIL_LINES),
    }


def _recommend(
    *,
    kind: str,
    query: str,
    result: str,
    source_risk_level: str,
    risk_reasons: list[str],
    source_url: str,
) -> tuple[str, str, list[str], list[str]]:
    query_lower = query.lower().strip()
    result_lower = result.lower().strip()
    text_lower = (query_lower + " " + result_lower).strip()
    missing: list[str] = []

    # --- REJECT (highest priority) ---
    reject_reasons: list[str] = []

    if not query_lower:
        reject_reasons.append("query is empty or whitespace-only")

    for phrase in _REJECT_PHRASES:
        if phrase in text_lower:
            reject_reasons.append(f"destructive/apply keyword: '{phrase}'")
            break

    for phrase in _BYPASS_SAFETY_PHRASES:
        if phrase in text_lower:
            reject_reasons.append(f"bypass-safety keyword: '{phrase}'")
            break

    secret_reasons = [r for r in risk_reasons if "possible secret detected" in r]
    if secret_reasons:
        reject_reasons.extend(secret_reasons)
        reject_reasons.append("item contains detected secrets — source is untrustworthy")

    if source_risk_level == "high" and not result_lower and not reject_reasons:
        reject_reasons.append(
            "source risk is high and result is empty — poor evidence quality"
        )

    if reject_reasons:
        return "reject", "high", reject_reasons, []

    # --- PROJECT EVOLUTION CANDIDATE ---
    if kind == "project_evolution_seed":
        reasons = ["kind is project_evolution_seed"]
        if not result_lower:
            missing.append("no result provided — add context before creating evolution candidate")
        return "convert_to_project_evolution_candidate", "high", reasons, missing

    for phrase in _PROJECT_EVOLUTION_PHRASES:
        if phrase in text_lower:
            reasons = [f"broad architecture/migration keyword: '{phrase}'"]
            if not result_lower:
                missing.append("no result provided — add research output before conversion")
            return "convert_to_project_evolution_candidate", "medium", reasons, missing

    # --- DREAM CANDIDATE ---
    # bug_seed with any result
    if kind == "bug_seed" and result_lower and len(result_lower) >= 10:
        reasons = ["bug_seed kind with concrete result evidence"]
        return "convert_to_dream_candidate", "medium", reasons, missing

    # research/lesson with substantial specific result
    if result_lower and len(result_lower) >= 20:
        is_specific = (
            any(sig in query for sig in _FILE_REF_SIGNALS)
            or len(query_lower) >= 30
        )
        if is_specific and kind in ("research_wishlist", "lesson_candidate_seed"):
            reasons = ["narrow research item with concrete result and specific query"]
            return "convert_to_dream_candidate", "medium", reasons, missing

    # --- GOAL BRIEF SEED ---
    is_goal_like = any(pattern in query_lower for pattern in _GOAL_INTENT_PATTERNS)
    if is_goal_like:
        reasons = ["query expresses a user goal that needs clarification before action"]
        if not result_lower:
            missing.append(
                "no result provided — add evidence before creating goal brief"
            )
        return "convert_to_goal_brief_seed", "medium", reasons, missing

    # --- NEEDS MORE EVIDENCE (default) ---
    reasons = ["insufficient evidence or specificity for a confident conversion recommendation"]
    if not result_lower:
        missing.append("result is empty — provide context or research output")
    if not source_url and kind == "research_wishlist":
        missing.append(
            "source_url not provided for research item — add link to original source"
        )
    if len(query_lower) < 30:
        missing.append("query is short — add more detail for actionable review")
    return "needs_more_evidence", "low", reasons, missing


def render_external_queue_review_markdown(record: dict[str, Any]) -> str:
    recommendation = record.get("recommendation", "unknown")
    confidence = record.get("recommendation_confidence", "unknown")
    lines = [
        "# External Queue Review",
        "",
        "## Decision",
        f"- Recommendation: **{recommendation}**",
        f"- Confidence: **{confidence}**",
        f"- Queue ID: `{record.get('queue_id', '')}`",
        f"- Generated at: `{record.get('generated_at', '')}`",
        f"- Human approval required: `{record.get('human_approval_required', True)}`",
        f"- Action performed: `{record.get('action_performed', False)}`",
        "",
        "## Source Item",
        f"- Source: `{record.get('source', '')}`",
        f"- Kind: `{record.get('kind', '')}`",
        f"- Import status: `{record.get('import_status', '')}`",
        f"- Source risk level: `{record.get('source_risk_level', '')}`",
        "",
        "## Recommendation",
        "",
        f"**{recommendation}**",
        "",
        record.get("suggested_next_prompt", ""),
        "",
        "## Reasons",
        "",
    ]
    reasons = record.get("recommendation_reasons", [])
    lines.extend(f"- {r}" for r in (reasons or ["None"]))
    lines += [
        "",
        "## Missing Evidence",
        "",
    ]
    missing = record.get("missing_evidence", [])
    lines.extend(f"- {m}" for m in (missing or ["None"]))
    lines += [
        "",
        "## Suggested Next Prompt",
        "",
        record.get("suggested_next_prompt", ""),
        "",
        "## Allowed Next Steps",
        "",
    ]
    lines.extend(f"- {s}" for s in record.get("allowed_next_steps", []))
    lines += [
        "",
        "## Forbidden Next Steps",
        "",
    ]
    lines.extend(f"- {s}" for s in record.get("forbidden_next_steps", []))
    lines += [
        "",
        "## Guardrails",
        "",
    ]
    lines.extend(f"- {g}" for g in _GUARDRAIL_LINES)
    lines.append("")
    if record.get("status") == "error" and record.get("error"):
        lines += [
            "## Error",
            f"- {record['error']['message']}",
            "",
        ]
    return "\n".join(lines)


def write_external_queue_review_artifacts(
    repo_path: str,
    item_path: str,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_external_queue_review(repo_path, item_path)

    if record.get("status") == "error":
        return {"record": record, "json_path": "", "md_path": ""}

    resolved_item = _resolve_item_path(repo_root, item_path)
    if resolved_item is None:
        error = _build_error_record(
            source_item_path=item_path,
            message="could not resolve safe output directory",
            code="output_dir_unsafe",
        )
        return {"record": error, "json_path": "", "md_path": ""}

    output_dir = resolved_item.parent
    json_path = output_dir / "external_queue_review.json"
    md_path = output_dir / "external_queue_review.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_external_queue_review_markdown(record), encoding="utf-8")
    return {"record": record, "json_path": str(json_path), "md_path": str(md_path)}


def _resolve_item_path(repo_root: Path, item_path: str) -> Path | None:
    allowed_root = (repo_root / ".agent" / EXTERNAL_QUEUE_DIRNAME).resolve()
    raw = Path(item_path)
    if not raw.is_absolute():
        raw = (repo_root / raw).resolve()
    else:
        raw = raw.resolve()
    try:
        raw.relative_to(allowed_root)
    except ValueError:
        return None
    return raw


def _load_and_validate_item(item_path: Path) -> dict[str, Any]:
    if not item_path.exists():
        return {
            "status": "error",
            "code": "item_file_missing",
            "message": f"queue item file does not exist: {item_path.name}",
        }
    try:
        raw = json.loads(item_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "code": "item_file_invalid_json",
            "message": f"queue item file is not valid JSON ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "code": "item_file_unreadable",
            "message": f"queue item file could not be read ({exc})",
        }
    if not isinstance(raw, dict):
        return {
            "status": "error",
            "code": "item_file_not_object",
            "message": "queue item file must be a JSON object",
        }
    missing_fields = [f for f in _REQUIRED_ITEM_FIELDS if f not in raw]
    if missing_fields:
        return {
            "status": "error",
            "code": "item_missing_required_fields",
            "message": f"queue item missing required fields: {', '.join(missing_fields)}",
        }
    if raw.get("mode") != "external_queue_import":
        return {
            "status": "error",
            "code": "item_wrong_mode",
            "message": f"expected mode 'external_queue_import', got '{raw.get('mode')}'",
        }
    if raw.get("schema_version") != IMPORT_SCHEMA_VERSION:
        return {
            "status": "error",
            "code": "item_wrong_schema_version",
            "message": (
                f"expected schema_version '{IMPORT_SCHEMA_VERSION}', "
                f"got '{raw.get('schema_version')}'"
            ),
        }
    return {"status": "ok", "data": raw}


def _build_error_record(
    *,
    source_item_path: str,
    message: str,
    code: str,
) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {"code": code, "message": message},
        "queue_id": "",
        "source_item_path": source_item_path,
        "source": "",
        "kind": "",
        "query": "",
        "import_status": "",
        "source_risk_level": "unknown",
        "recommendation": "needs_more_evidence",
        "recommendation_confidence": "low",
        "recommendation_reasons": [],
        "missing_evidence": [],
        "suggested_next_prompt": "",
        "allowed_next_steps": list(_ALLOWED_NEXT_STEPS),
        "forbidden_next_steps": list(_FORBIDDEN_NEXT_STEPS),
        "human_approval_required": True,
        "action_performed": False,
        "guardrails": list(_GUARDRAIL_LINES),
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
