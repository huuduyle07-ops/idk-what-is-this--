from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, request

from web.session_store import load_sessions, save_sessions, list_sessions
from core import benchmarks_view
from core import dream_artifacts

bp = Blueprint("history_routes", __name__)

_CONFIRM_SESSION = "DELETE_SESSION"
_CONFIRM_BENCHMARK = "DELETE_BENCHMARK_REPORT"
_CONFIRM_DREAM = "DELETE_DREAM_RUN"
_BENCH_FILENAME_RE = re.compile(r"^benchmark_report_\d+\.json$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RUN_RE = re.compile(r"^\d{6}-run(-\d+)?$")


def _bool_field(name: str) -> bool:
    return request.form.get(name, "").strip().lower() not in {"0", "false", "no", "off", ""}


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------

@bp.route("/history/sessions", methods=["GET"])
def history_sessions():
    include_archived = request.values.get("include_archived", "").strip() in {"1", "true", "yes"}
    return {"sessions": list_sessions(include_archived=include_archived)}


@bp.route("/history/session/archive", methods=["POST"])
def history_session_archive():
    session_id = request.form.get("session_id", "").strip()
    if not session_id:
        return {"ok": False, "error": "session_id is required"}, 400

    archived = _bool_field("archived")
    sessions = load_sessions()
    for s in sessions:
        if s.get("id") == session_id:
            s["archived"] = archived
            save_sessions(sessions)
            return {"ok": True, "session_id": session_id, "archived": archived}

    return {"ok": False, "error": f"session not found: {session_id}"}, 404


@bp.route("/history/session/delete", methods=["POST"])
def history_session_delete():
    session_id = request.form.get("session_id", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not session_id:
        return {"ok": False, "error": "session_id is required"}, 400
    if confirm != _CONFIRM_SESSION:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_SESSION}"}, 400

    sessions = load_sessions()
    for s in sessions:
        if s.get("id") == session_id:
            s["deleted"] = True
            s["deleted_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            save_sessions(sessions)
            return {"ok": True, "session_id": session_id}

    return {"ok": False, "error": f"session not found: {session_id}"}, 404


# ---------------------------------------------------------------------------
# Benchmark routes
# ---------------------------------------------------------------------------

@bp.route("/history/benchmark/update", methods=["POST"])
def history_benchmark_update():
    repo_path = request.form.get("repo_path", "").strip()
    filename = request.form.get("filename", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not filename:
        return {"ok": False, "error": "filename is required"}, 400
    if not _BENCH_FILENAME_RE.match(filename):
        return {"ok": False, "error": f"invalid filename: {filename}"}, 400

    fields: dict[str, bool] = {}
    if "archived" in request.form:
        fields["archived"] = _bool_field("archived")
    if "pinned" in request.form:
        fields["pinned"] = _bool_field("pinned")
    if not fields:
        return {"ok": False, "error": "at least one of archived or pinned is required"}, 400

    entry = benchmarks_view.update_benchmark_entry(repo_path, filename, **fields)
    return {"ok": True, "filename": filename, "meta": entry}


@bp.route("/history/benchmark/delete", methods=["POST"])
def history_benchmark_delete():
    repo_path = request.form.get("repo_path", "").strip()
    filename = request.form.get("filename", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not filename:
        return {"ok": False, "error": "filename is required"}, 400
    if not _BENCH_FILENAME_RE.match(filename):
        return {"ok": False, "error": f"invalid filename: {filename}"}, 400
    if confirm != _CONFIRM_BENCHMARK:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_BENCHMARK}"}, 400

    meta = benchmarks_view.read_benchmark_meta(repo_path)
    if meta.get(filename, {}).get("pinned"):
        return {"ok": False, "error": "cannot delete a pinned item — unpin first"}, 409

    entry = dict(meta.get(filename, {}))
    entry["deleted"] = True
    meta[filename] = entry
    benchmarks_view.write_benchmark_meta(repo_path, meta)
    return {"ok": True, "filename": filename}


# ---------------------------------------------------------------------------
# Dream routes
# ---------------------------------------------------------------------------

def _run_key(date: str, run: str) -> str:
    return f"{date}/{run}" if run else date


@bp.route("/history/dream/update", methods=["POST"])
def history_dream_update():
    repo_path = request.form.get("repo_path", "").strip()
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not date:
        return {"ok": False, "error": "date is required"}, 400
    if not _DATE_RE.match(date):
        return {"ok": False, "error": f"invalid date format: {date}"}, 400
    if run and not _RUN_RE.match(run):
        return {"ok": False, "error": f"invalid run id: {run}"}, 400

    fields: dict[str, bool] = {}
    if "archived" in request.form:
        fields["archived"] = _bool_field("archived")
    if "pinned" in request.form:
        fields["pinned"] = _bool_field("pinned")
    if not fields:
        return {"ok": False, "error": "at least one of archived or pinned is required"}, 400

    key = _run_key(date, run)
    entry = dream_artifacts.update_dream_entry(repo_path, key, **fields)
    return {"ok": True, "run_key": key, "meta": entry}


@bp.route("/history/dream/delete", methods=["POST"])
def history_dream_delete():
    repo_path = request.form.get("repo_path", "").strip()
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    confirm = request.form.get("confirm", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not date:
        return {"ok": False, "error": "date is required"}, 400
    if not _DATE_RE.match(date):
        return {"ok": False, "error": f"invalid date format: {date}"}, 400
    if run and not _RUN_RE.match(run):
        return {"ok": False, "error": f"invalid run id: {run}"}, 400
    if confirm != _CONFIRM_DREAM:
        return {"ok": False, "error": f"confirm string required: {_CONFIRM_DREAM}"}, 400

    key = _run_key(date, run)
    meta = dream_artifacts.read_dream_meta(repo_path)
    if meta.get(key, {}).get("pinned"):
        return {"ok": False, "error": "cannot delete a pinned item — unpin first"}, 409

    entry = dict(meta.get(key, {}))
    entry["deleted"] = True
    meta[key] = entry
    dream_artifacts.write_dream_meta(repo_path, meta)
    return {"ok": True, "run_key": key}
