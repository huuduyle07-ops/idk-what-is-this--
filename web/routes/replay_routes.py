"""Read-only replay bundle viewer routes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, request

from core.replay_compare import (
    DEFAULT_MAX_CHARS as COMPARE_DEFAULT_MAX_CHARS,
    compare_replay_to_current,
    format_replay_compare_markdown,
)
from core.replay_janitor import (
    apply_replay_cleanup,
    format_replay_janitor_markdown,
    plan_replay_cleanup,
)
from core.replay_recorder import (
    ARTIFACT_NAMES,
    JSON_ARTIFACT_NAMES,
    MANIFEST_NAME,
    list_replay_bundles,
    read_replay_manifest,
)


bp = Blueprint("replay_routes", __name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
PREVIEW_CHAR_LIMIT = 12000
COMPARE_MAX_CHARS = COMPARE_DEFAULT_MAX_CHARS

REPLAY_ARTIFACT_ORDER = [
    "user_query.txt",
    "control_result.json",
    "scout_snippets.json",
    "active_lessons_injected.json",
    "model_prompt.txt",
    "model_raw_response.txt",
    "patch_parsed.json",
    "apply_result.json",
    "validation_output.txt",
    "self_correct_attempts.json",
    "brain_stamp.json",
    "final_status.json",
]


def _repo_from_request() -> Path:
    raw = str(request.values.get("repo_path") or "").strip()
    repo = Path(raw) if raw else PROJECT_ROOT
    if not repo.is_dir():
        raise ValueError(f"repo_path is not a directory: {raw or repo}")
    return repo


def _limit_from_request() -> int:
    try:
        limit = int(str(request.values.get("limit") or "").strip())
    except ValueError:
        return DEFAULT_LIMIT
    if limit <= 0:
        return DEFAULT_LIMIT
    return min(limit, MAX_LIMIT)


def _compare_max_chars_from_request() -> int:
    try:
        max_chars = int(str(request.values.get("max_chars") or "").strip())
    except ValueError:
        return COMPARE_MAX_CHARS
    if max_chars <= 0:
        return COMPARE_MAX_CHARS
    return min(max_chars, COMPARE_MAX_CHARS)


def _safe_replay_id(replay_id: str) -> str:
    if not replay_id or replay_id != Path(replay_id).name:
        raise ValueError(f"invalid replay_id: {replay_id!r}")
    if "/" in replay_id or "\\" in replay_id:
        raise ValueError(f"invalid replay_id: {replay_id!r}")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in replay_id):
        raise ValueError(f"invalid replay_id: {replay_id!r}")
    return replay_id


def _safe_artifact_name(artifact_name: str) -> str:
    if artifact_name not in ARTIFACT_NAMES:
        raise ValueError(f"unsupported replay artifact: {artifact_name!r}")
    if not artifact_name or artifact_name != Path(artifact_name).name:
        raise ValueError(f"invalid replay artifact: {artifact_name!r}")
    if "/" in artifact_name or "\\" in artifact_name:
        raise ValueError(f"invalid replay artifact: {artifact_name!r}")
    return artifact_name


def _artifact_path(repo: Path, replay_id: str, artifact_name: str) -> Path:
    safe_id = _safe_replay_id(replay_id)
    safe_name = _safe_artifact_name(artifact_name)
    replay_dir = (repo.resolve() / ".agent" / "replays" / safe_id).resolve()
    path = (replay_dir / safe_name).resolve()
    try:
        path.relative_to(replay_dir)
    except ValueError as exc:
        raise ValueError(f"replay artifact escapes bundle: {artifact_name!r}") from exc
    return path


def _read_preview(path: Path, artifact_name: str) -> dict[str, Any]:
    size_bytes = path.stat().st_size
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        preview = handle.read(PREVIEW_CHAR_LIMIT + 1)
    truncated = len(preview) > PREVIEW_CHAR_LIMIT
    if truncated:
        preview = preview[:PREVIEW_CHAR_LIMIT]

    content_type = "json" if artifact_name in JSON_ARTIFACT_NAMES else "text"
    if content_type == "json" and not truncated:
        try:
            parsed = json.loads(preview)
            preview = json.dumps(
                parsed,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
        except json.JSONDecodeError:
            content_type = "text"

    return {
        "name": artifact_name,
        "captured": True,
        "content_type": content_type,
        "preview": preview,
        "truncated": truncated,
        "size_bytes": size_bytes,
        "preview_char_limit": PREVIEW_CHAR_LIMIT,
    }


def _artifact_preview(
    repo: Path,
    replay_id: str,
    artifact_name: str,
    files_present: set[str] | None = None,
) -> dict[str, Any]:
    safe_name = _safe_artifact_name(artifact_name)
    if files_present is not None and safe_name not in files_present:
        return {
            "name": safe_name,
            "captured": False,
            "content_type": "json" if safe_name in JSON_ARTIFACT_NAMES else "text",
            "preview": "",
            "truncated": False,
            "size_bytes": 0,
            "preview_char_limit": PREVIEW_CHAR_LIMIT,
        }

    path = _artifact_path(repo, replay_id, safe_name)
    if not path.is_file():
        return {
            "name": safe_name,
            "captured": False,
            "content_type": "json" if safe_name in JSON_ARTIFACT_NAMES else "text",
            "preview": "",
            "truncated": False,
            "size_bytes": 0,
            "preview_char_limit": PREVIEW_CHAR_LIMIT,
        }
    return _read_preview(path, safe_name)


@bp.route("/replays", methods=["GET"])
def replays_list_route():
    try:
        repo = _repo_from_request()
        limit = _limit_from_request()
        replays = list_replay_bundles(repo, limit=limit)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "replays": []}, 400
    except OSError as exc:
        return {"ok": False, "error": str(exc), "replays": []}, 500

    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "replays": replays,
        "count": len(replays),
        "limit": limit,
    }


def _optional_float(name: str) -> float | None:
    raw = str(request.values.get(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name}: {raw!r}") from exc


def _optional_int(name: str) -> int | None:
    raw = str(request.values.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name}: {raw!r}") from exc


def _bool_flag(name: str) -> bool:
    raw = str(request.values.get(name) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _pinned_ids_from_request() -> list[str]:
    raw = str(request.values.get("pinned") or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


@bp.route("/replays/janitor", methods=["GET"])
def replays_janitor_route():
    try:
        repo = _repo_from_request()
        plan = plan_replay_cleanup(
            repo,
            max_age_days=_optional_float("max_age_days"),
            max_keep=_optional_int("max_keep"),
            include_invalid=_bool_flag("include_invalid"),
            pinned_ids=_pinned_ids_from_request(),
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, 500

    if str(request.values.get("format") or "").strip().lower() == "markdown":
        return Response(
            format_replay_janitor_markdown(plan),
            mimetype="text/markdown",
        )

    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "plan": plan.to_dict(),
    }


@bp.route("/replays/janitor/apply", methods=["POST"])
def replays_janitor_apply_route():
    """Confirmation-gated deletion of cleanup_candidate replay bundles.

    GET /replays/janitor stays dry-run only; this POST route is the only path
    that deletes, and only when ``confirm`` equals the exact token.
    """
    try:
        repo = _repo_from_request()
        confirm = str(request.values.get("confirm") or "").strip() or None
        result = apply_replay_cleanup(
            repo,
            confirm=confirm,
            max_age_days=_optional_float("max_age_days"),
            max_keep=_optional_int("max_keep"),
            pinned_ids=_pinned_ids_from_request(),
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, 500

    if not result.confirmed:
        return {
            "ok": False,
            "confirmed": False,
            "error": (
                "confirmation token required: send "
                f"confirm={result.confirm_token_required}"
            ),
            "result": result.to_dict(),
        }, 400

    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "result": result.to_dict(),
    }


@bp.route("/replays/<replay_id>", methods=["GET"])
def replays_detail_route(replay_id: str):
    try:
        repo = _repo_from_request()
        safe_id = _safe_replay_id(replay_id)
        manifest = read_replay_manifest(repo, safe_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, 500

    if manifest is None:
        return {
            "ok": False,
            "error": f"replay not found: {replay_id}",
            "replay_id": replay_id,
        }, 404

    files_present = set(manifest.get("files_present") or [])
    artifacts = {
        name: _artifact_preview(repo, safe_id, name, files_present)
        for name in REPLAY_ARTIFACT_ORDER
    }
    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "replay_id": safe_id,
        "manifest": manifest,
        "artifacts": artifacts,
        "artifact_order": REPLAY_ARTIFACT_ORDER,
        "preview_char_limit": PREVIEW_CHAR_LIMIT,
    }


@bp.route("/replays/<replay_id>/compare", methods=["GET"])
def replays_compare_route(replay_id: str):
    try:
        repo = _repo_from_request()
        safe_id = _safe_replay_id(replay_id)
        max_chars = _compare_max_chars_from_request()
        result = compare_replay_to_current(
            repo,
            safe_id,
            max_chars=max_chars,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "replay_id": replay_id}, 404
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, 500

    if str(request.values.get("format") or "").strip().lower() == "markdown":
        return Response(
            format_replay_compare_markdown(result),
            mimetype="text/markdown",
        )

    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "replay_id": safe_id,
        "compare": result.to_dict(),
        "max_chars": max_chars,
    }


@bp.route("/replays/<replay_id>/artifact/<artifact_name>", methods=["GET"])
def replays_artifact_route(replay_id: str, artifact_name: str):
    try:
        repo = _repo_from_request()
        safe_id = _safe_replay_id(replay_id)
        safe_name = _safe_artifact_name(artifact_name)
        manifest = read_replay_manifest(repo, safe_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}, 400
    except OSError as exc:
        return {"ok": False, "error": str(exc)}, 500

    if manifest is None:
        return {"ok": False, "error": f"replay not found: {replay_id}"}, 404

    preview = _artifact_preview(
        repo,
        safe_id,
        safe_name,
        set(manifest.get("files_present") or []),
    )
    if not preview["captured"]:
        return {
            "ok": False,
            "error": f"artifact not captured: {safe_name}",
            "replay_id": safe_id,
            "artifact_name": safe_name,
        }, 404

    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "replay_id": safe_id,
        "artifact_name": safe_name,
        "artifact": preview,
    }
