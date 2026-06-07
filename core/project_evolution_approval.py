from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "project_evolution"
SCHEMA_VERSION = "evolution_plan_review_v1"
PANEL_SCHEMA_VERSION = "evolution_plan_review_panel_v1"
VALID_DECISIONS = {"approve", "reject", "needs_revision"}
SOURCE_PLAN_SCHEMA_VERSION = "migration_plan_dry_run_v1"


def build_project_evolution_approval_record(
    source_plan_path: str,
    decision: str,
    *,
    reviewer: str | None = None,
    notes: str | None = None,
    approved_scope: list[str] | None = None,
    blocked_scope: list[str] | None = None,
) -> dict[str, Any]:
    decision_text = _normalize_decision(decision)
    if decision_text not in VALID_DECISIONS:
        raise ValueError(
            f"invalid decision: {decision!r}; expected one of {sorted(VALID_DECISIONS)}"
        )

    source_path = _resolve_source_plan_path(source_plan_path)
    repo_root = _infer_repo_root(source_path)
    source_load = _load_source_plan(source_path)
    if source_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            source_path=source_path,
            decision=decision_text,
            reviewer=reviewer,
            notes=notes,
            approved_scope=approved_scope,
            blocked_scope=blocked_scope,
            message=source_load["message"],
        )

    source_plan = source_load["record"]
    source_plan_hash = _hash_source_plan(source_plan)
    reviewer_text = _normalize_text(reviewer)
    notes_text = _normalize_text(notes)
    approved_scope_list = _normalize_scope(approved_scope)
    blocked_scope_list = _normalize_scope(blocked_scope)

    patch_allowed = decision_text == "approve"
    gate_reason = _gate_reason(decision_text, source_plan_hash)

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "source_plan_path": str(source_path),
        "source_plan_hash": source_plan_hash,
        "migration_goal": source_plan.get("migration_goal", ""),
        "decision": decision_text,
        "reviewer": reviewer_text,
        "notes": notes_text,
        "approved_scope": approved_scope_list,
        "blocked_scope": blocked_scope_list,
        "human_approval_recorded": True,
        "patch_generation_allowed": patch_allowed,
        "patch_generation_gate_reason": gate_reason,
        "limitations": [
            "This approval record is read-only and does not generate or apply patches.",
            "Patch generation remains blocked unless the source plan hash exactly matches this approval record and the decision is approve.",
            "No model/API calls, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
        ],
    }


def render_project_evolution_approval_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Evolution Plan Review",
        "",
        "## Decision",
        f"- `{record.get('decision', '')}`",
        "",
        "## Source Plan",
        f"- Path: `{record.get('source_plan_path', '')}`",
        f"- Hash: `{record.get('source_plan_hash', '')}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Reviewer Notes",
        f"- Reviewer: {record.get('reviewer', '') or 'None'}",
        f"- Notes: {record.get('notes', '') or 'None'}",
        "",
        "## Approved Scope",
        *_render_scope(record.get("approved_scope", [])),
        "",
        "## Blocked Scope",
        *_render_scope(record.get("blocked_scope", [])),
        "",
        "## Patch Generation Gate",
        f"- Patch generation allowed: `{record.get('patch_generation_allowed', False)}`",
        f"- Gate reason: {record.get('patch_generation_gate_reason', '')}",
        "",
        "## Limitations",
        *_render_string_list(record.get("limitations", [])),
        "",
    ]
    if record.get("status") != "ok" and record.get("error"):
        lines.extend(
            [
                "## Error",
                f"- {record['error']['message']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_project_evolution_approval_artifacts(
    source_plan_path: str,
    decision: str,
    *,
    reviewer: str | None = None,
    notes: str | None = None,
    approved_scope: list[str] | None = None,
    blocked_scope: list[str] | None = None,
    output_root: str | None = None,
) -> dict[str, Any]:
    source_path = _resolve_source_plan_path(source_plan_path)
    record = build_project_evolution_approval_record(
        str(source_path),
        decision,
        reviewer=reviewer,
        notes=notes,
        approved_scope=approved_scope,
        blocked_scope=blocked_scope,
    )
    markdown = render_project_evolution_approval_markdown(record)
    approvals_root = _resolve_output_root(_infer_repo_root(source_path), output_root)
    timestamp = _safe_timestamp(record.get("generated_at", _utc_now_iso()))
    filename = f"{timestamp}_{record.get('decision', 'unknown')}_approval"
    json_path = approvals_root / f"{filename}.json"
    md_path = approvals_root / f"{filename}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def load_latest_project_evolution_plan(repo_path: str) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    source_path = repo_root / ".agent" / "project_evolution" / "migration_plan_dry_run.json"
    source_load = _load_source_plan(source_path)
    if source_load["status"] != "ok":
        return {
            "status": source_load["status"],
            "repo_path": str(repo_root),
            "source_plan_path": str(source_path),
            "source_plan_hash": "",
            "source_plan": None,
            "plan_present": False,
            "message": source_load["message"],
        }

    source_plan = source_load["record"]
    return {
        "status": "ok",
        "repo_path": str(repo_root),
        "source_plan_path": str(source_path),
        "source_plan_hash": _hash_source_plan(source_plan),
        "source_plan": source_plan,
        "plan_present": True,
        "message": "",
    }


def build_project_evolution_approval_panel_record(repo_path: str) -> dict[str, Any]:
    loaded = load_latest_project_evolution_plan(repo_path)
    repo_root = Path(repo_path).expanduser().resolve()
    base_limitations = [
        "This panel is read-only and never generates or applies patches.",
        "Approval buttons create manual approval records only; no automatic B.5 trigger occurs.",
        "No model/API calls, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
    ]

    if loaded["status"] != "ok" or not loaded.get("source_plan"):
        return {
            "generated_at": _utc_now_iso(),
            "repo_path": str(repo_root),
            "mode": MODE,
            "schema_version": PANEL_SCHEMA_VERSION,
            "status": "error",
            "plan_present": False,
            "source_plan_path": loaded.get("source_plan_path", ""),
            "source_plan_hash": "",
            "source_plan_generated_at": "",
            "migration_goal": "",
            "patch_generation_allowed": False,
            "human_approval_required": True,
            "approval_warning": "Approval only applies to this exact plan hash.",
            "buttons_enabled": False,
            "message": loaded.get("message", "migration plan is unavailable"),
            "limitations": base_limitations + [
                "A readable migration_plan_dry_run.json is required before the review panel can be used.",
            ],
        }

    source_plan = loaded["source_plan"]
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": PANEL_SCHEMA_VERSION,
        "status": "ok",
        "plan_present": True,
        "source_plan_path": loaded["source_plan_path"],
        "source_plan_hash": loaded["source_plan_hash"],
        "source_plan_generated_at": source_plan.get("generated_at", ""),
        "migration_goal": source_plan.get("migration_goal", ""),
        "patch_generation_allowed": bool(source_plan.get("patch_generation_allowed", False)),
        "human_approval_required": bool(source_plan.get("human_approval_required", True)),
        "approval_warning": "Approval only applies to this exact plan hash.",
        "buttons_enabled": True,
        "message": "",
        "limitations": base_limitations,
    }


def _build_error_record(
    *,
    repo_root: Path,
    source_path: Path,
    decision: str,
    reviewer: str | None,
    notes: str | None,
    approved_scope: list[str] | None,
    blocked_scope: list[str] | None,
    message: str,
) -> dict[str, Any]:
    reviewer_text = _normalize_text(reviewer)
    notes_text = _normalize_text(notes)
    approved_scope_list = _normalize_scope(approved_scope)
    blocked_scope_list = _normalize_scope(blocked_scope)
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "error": {
            "code": "source_plan_unavailable",
            "message": message,
        },
        "source_plan_path": str(source_path),
        "source_plan_hash": "",
        "migration_goal": "",
        "decision": decision,
        "reviewer": reviewer_text,
        "notes": notes_text,
        "approved_scope": approved_scope_list,
        "blocked_scope": blocked_scope_list,
        "human_approval_recorded": True,
        "patch_generation_allowed": False,
        "patch_generation_gate_reason": (
            "Patch generation is blocked because the source migration plan could not be loaded."
        ),
        "limitations": [
            "This approval record is an error response and does not authorize patch generation.",
            "A readable migration_plan_dry_run.json is required before approval can be recorded.",
        ],
    }


def _load_source_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "error",
            "message": f"migration plan does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "message": f"migration plan is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "message": f"migration plan could not be read: {path} ({exc})",
        }
    if not isinstance(record, dict) or record.get("schema_version") != SOURCE_PLAN_SCHEMA_VERSION:
        return {
            "status": "error",
            "message": f"migration plan has an unexpected schema: {path}",
        }
    return {"status": "ok", "record": record}


def _hash_source_plan(record: dict[str, Any]) -> str:
    normalized = _normalize_plan_for_hash(record)
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_plan_for_hash(record: dict[str, Any]) -> dict[str, Any]:
    return _remove_generated_at_keys(record)


def _remove_generated_at_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_generated_at_keys(inner)
            for key, inner in value.items()
            if key != "generated_at"
        }
    if isinstance(value, list):
        return [_remove_generated_at_keys(item) for item in value]
    return value


def _gate_reason(decision: str, source_plan_hash: str) -> str:
    if decision == "approve":
        return (
            "Patch generation is allowed only when the active source plan hash exactly matches "
            f"`{source_plan_hash}` and this approval remains the current operator decision."
        )
    if decision == "reject":
        return "Patch generation is blocked because the operator rejected the current migration plan."
    return "Patch generation is blocked because the operator requested revision before any patch work."


def _resolve_source_plan_path(source_plan_path: str) -> Path:
    return Path(source_plan_path).expanduser().resolve()


def _infer_repo_root(source_path: Path) -> Path:
    if len(source_path.parents) >= 3 and source_path.parents[0].name == "project_evolution" and source_path.parents[1].name == ".agent":
        return source_path.parents[2]
    return source_path.parent


def _resolve_output_root(repo_root: Path, output_root: str | None) -> Path:
    if output_root is None:
        resolved = (repo_root / ".agent" / "project_evolution" / "approvals").resolve()
    else:
        candidate = Path(output_root).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _normalize_decision(decision: str) -> str:
    return (decision or "").strip().lower()


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _normalize_scope(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned = [value.strip() for value in values if value and value.strip()]
    seen: set[str] = set()
    scoped: list[str] = []
    for value in cleaned:
        if value in seen:
            continue
        seen.add(value)
        scoped.append(value)
    return scoped


def _render_scope(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]


def _render_string_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]


def _safe_timestamp(value: str) -> str:
    cleaned = value.replace(":", "").replace("-", "").replace("Z", "Z")
    return cleaned or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
