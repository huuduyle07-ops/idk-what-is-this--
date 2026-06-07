"""Project Evolution approval review routes.

Read-only panel data and manual approval recording for existing
``migration_plan_dry_run.json`` artifacts. This module never generates or
applies patches, never calls models, and never writes outside
``.agent/project_evolution/approvals/``.
"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, request

from core import project_evolution_approval as pea


bp = Blueprint("project_evolution_approval_routes", __name__)
_APPROVAL_WARNING = "Approval only applies to this exact plan hash."
_PANEL_LIMITATIONS = [
    "This panel is read-only and never generates or applies patches.",
    "Approval buttons create manual approval records only; no automatic B.5 trigger occurs.",
    "No model/API calls, validation execution, benchmark execution, Docker/subprocess behavior, or lesson mutation occurs here.",
]


def _valid_repo(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    path = Path(repo_path).expanduser()
    if not path.is_dir():
        return None
    return path


def _scope_values(payload, key: str) -> list[str] | None:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw).splitlines()
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        for piece in str(item).split(","):
            value = piece.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
    return cleaned


@bp.route("/project-evolution/approval-panel", methods=["GET"])
def project_evolution_approval_panel():
    repo_path = str(request.values.get("repo_path") or "").strip()
    if not repo_path:
        return {
            "ok": False,
            "generated_at": "",
            "repo_path": "",
            "mode": pea.MODE,
            "schema_version": pea.PANEL_SCHEMA_VERSION,
            "status": "error",
            "plan_present": False,
            "source_plan_path": "",
            "source_plan_hash": "",
            "source_plan_generated_at": "",
            "migration_goal": "",
            "patch_generation_allowed": False,
            "human_approval_required": True,
            "approval_warning": _APPROVAL_WARNING,
            "buttons_enabled": False,
            "message": "Set a repo path to load the latest migration plan.",
            "limitations": _PANEL_LIMITATIONS,
        }
    if not _valid_repo(repo_path):
        return {
            "ok": False,
            "generated_at": "",
            "repo_path": repo_path,
            "mode": pea.MODE,
            "schema_version": pea.PANEL_SCHEMA_VERSION,
            "status": "error",
            "plan_present": False,
            "source_plan_path": "",
            "source_plan_hash": "",
            "source_plan_generated_at": "",
            "migration_goal": "",
            "patch_generation_allowed": False,
            "human_approval_required": True,
            "approval_warning": _APPROVAL_WARNING,
            "buttons_enabled": False,
            "message": f"repo_path is not a directory: {repo_path}",
            "limitations": _PANEL_LIMITATIONS,
        }

    panel = pea.build_project_evolution_approval_panel_record(repo_path)
    return {"ok": panel.get("status") == "ok", **panel}


@bp.route("/project-evolution/approval-panel/review", methods=["POST"])
def project_evolution_approval_review():
    payload = request.get_json(silent=True) or request.form
    repo_path = str(payload.get("repo_path") or "").strip()
    decision = str(payload.get("decision") or "").strip()
    reviewer = payload.get("reviewer")
    notes = payload.get("notes")
    expected_hash = str(payload.get("source_plan_hash") or "").strip()
    approved_scope = _scope_values(payload, "approved_scope")
    blocked_scope = _scope_values(payload, "blocked_scope")

    repo = _valid_repo(repo_path)
    if not repo:
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not decision:
        return {"ok": False, "error": "decision is required"}, 400
    if not expected_hash:
        return {"ok": False, "error": "source_plan_hash is required"}, 400

    panel = pea.build_project_evolution_approval_panel_record(repo_path)
    if panel.get("status") != "ok" or not panel.get("plan_present"):
        return {
            "ok": False,
            "error": panel.get("message") or "migration plan is unavailable",
        }, 400

    current_hash = str(panel.get("source_plan_hash") or "")
    if current_hash != expected_hash:
        return {
            "ok": False,
            "error": (
                "source plan hash changed; refresh the panel before approving this plan"
            ),
            "expected_source_plan_hash": expected_hash,
            "current_source_plan_hash": current_hash,
        }, 409

    result = pea.write_project_evolution_approval_artifacts(
        source_plan_path=panel["source_plan_path"],
        decision=decision,
        reviewer=str(reviewer) if reviewer is not None else None,
        notes=str(notes) if notes is not None else None,
        approved_scope=approved_scope,
        blocked_scope=blocked_scope,
    )

    record = result["record"]
    if record.get("status") != "ok":
        return {
            "ok": False,
            "error": record.get("error", {}).get("message", "approval record failed"),
        }, 400

    return {
        "ok": True,
        "decision": record["decision"],
        "approval_record_path": result["json_path"],
        "approval_markdown_path": result["md_path"],
        "approved_source_hash": record["source_plan_hash"],
        "patch_generation_allowed": record["patch_generation_allowed"],
        "message": "No patch was generated.",
        "source_plan_path": record["source_plan_path"],
        "source_plan_hash": record["source_plan_hash"],
        "human_approval_recorded": True,
    }
