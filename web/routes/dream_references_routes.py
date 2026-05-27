"""Web routes for local Dream research reference imports."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, request

from core import dream_references


bp = Blueprint("dream_references_routes", __name__)


def _valid_repo(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    path = Path(repo_path)
    if not path.is_dir():
        return None
    return path


@bp.route("/dream/references/import", methods=["POST"])
def dream_references_import():
    payload = request.get_json(silent=True) or request.form
    repo_path = str(payload.get("repo_path") or "").strip()
    if not _valid_repo(repo_path):
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}

    # Phase 4.7e-a: accept normalize_loose as either JSON bool or form string.
    raw_flag = payload.get("normalize_loose")
    if isinstance(raw_flag, bool):
        normalize_loose = raw_flag
    elif isinstance(raw_flag, str):
        normalize_loose = raw_flag.strip().lower() in {"1", "true", "yes", "on"}
    else:
        normalize_loose = False

    try:
        result = dream_references.create_dream_reference(
            repo_path=repo_path,
            topic=payload.get("topic"),
            raw_input=payload.get("raw_input"),
            source_type=payload.get("source_type") or "manual_paste",
            sources=payload.get("sources"),
            key_ideas=payload.get("key_ideas"),
            risks_or_weaknesses=payload.get("risks_or_weaknesses"),
            do_not_assume=payload.get("do_not_assume"),
            suggested_dream_trial_input=payload.get("suggested_dream_trial_input") or "",
            normalize_loose=normalize_loose,
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "reference_id": result.reference_id,
        "reference_dir": result.reference_dir,
        "markdown_path": result.markdown_path,
        "json_path": result.json_path,
        "summary": result.summary,
    }


@bp.route("/dream/references/list", methods=["GET"])
def dream_references_list():
    repo_path = str(request.values.get("repo_path") or "").strip()
    if not _valid_repo(repo_path):
        return {"error": f"repo_path is not a directory: {repo_path}"}
    return {"references": dream_references.list_dream_references(repo_path)}


@bp.route("/dream/references/file", methods=["GET"])
def dream_references_file():
    repo_path = str(request.values.get("repo_path") or "").strip()
    reference_id = str(request.values.get("reference_id") or "").strip()
    file_name = str(request.values.get("file") or "").strip()

    if not _valid_repo(repo_path):
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}
    try:
        content = dream_references.read_dream_reference_file(
            repo_path=repo_path,
            reference_id=reference_id,
            file_name=file_name,
        )
    except (FileNotFoundError, ValueError, OSError) as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "reference_id": reference_id,
        "file": file_name,
        "content": content,
    }

