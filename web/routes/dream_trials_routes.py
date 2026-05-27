"""Phase 4.7c — web routes for structured Dream trial reports.

Three Flask routes back the Dream tab's Structured Trial Reports section:

    POST /dream/trials/create
    GET  /dream/trials/list
    GET  /dream/trials/file

Hard rules for this module:
- No patch executor calls.
- No benchmark runner calls.
- No shell-out (no os-level command execution).
- No model / API clients.
- Read-only file access stays inside the repo's `.agent/dream_trials/` dir.

The creation route delegates to `core.dream_trials.create_structured_dream_trial`,
which is already report-only (Phase 4.7b). The list and file routes are
read-only and reject path traversal + non-whitelisted filenames.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from flask import Blueprint, request

from core import dream_trials


bp = Blueprint("dream_trials_routes", __name__)


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------

# Whitelist of filenames the /dream/trials/file route is allowed to serve.
# Anything not in this set — including extension variants like trial.json.bak,
# any backup or model-raw artifacts a future phase might write, and any name
# containing a path separator — is refused.
_ALLOWED_TRIAL_FILES: frozenset[str] = frozenset({
    "trial.json",
    "01_reference_study.md",
    "02_baseline_answer.md",
    "03_reasoning_chunks.md",
    "04_multi_perspective_evaluation.md",
    "05_refutation.md",
    "06_judge_report.md",
    "07_final_decision.md",
})

# Strict trial_id shape: 8-digit date, dash, 6-digit time, dash, lowercased
# slug of alphanumerics + hyphens. Matches what `_build_trial_id()` produces
# in `core/dream_trials.py`. Anything else (including `..`, `/`, backslashes)
# is rejected before touching the filesystem.
_TRIAL_ID_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9][a-z0-9-]{0,80}$")


def _valid_repo(repo_path: str) -> Path | None:
    if not repo_path:
        return None
    p = Path(repo_path)
    if not p.is_dir():
        return None
    return p


def _resolve_trial_dir(repo_path: str, trial_id: str) -> Path | None:
    """Return the trial directory iff it lives inside the repo's trials root."""
    if not _TRIAL_ID_RE.match(trial_id or ""):
        return None
    trials_root = dream_trials._trials_root(repo_path).resolve()
    candidate = (trials_root / trial_id).resolve()
    try:
        candidate.relative_to(trials_root)
    except ValueError:
        return None
    if not candidate.is_dir():
        return None
    return candidate


def _summarize_trial(trial_path: Path) -> dict | None:
    """Best-effort summary for the list view. Returns None on any parse error."""
    try:
        data = json.loads(trial_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    judge = data.get("judge") if isinstance(data.get("judge"), dict) else {}
    return {
        "trial_id": data.get("trial_id") or trial_path.parent.name,
        "title": data.get("title", ""),
        "dream_type": data.get("dream_type", ""),
        "action_level": data.get("action_level", ""),
        "status": data.get("status", ""),
        "created_at": data.get("created_at", ""),
        "decision": judge.get("decision", ""),
        "risk": judge.get("risk", ""),
        "confidence": judge.get("confidence", ""),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/dream/trials/create", methods=["POST"])
def dream_trials_create():
    """Create a structured trial report. Report-only; delegates to Phase 4.7b."""
    payload = request.get_json(silent=True) or {}

    repo_path = str(payload.get("repo_path") or "").strip()
    if not _valid_repo(repo_path):
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}

    dream_type = str(payload.get("dream_type") or "").strip()
    action_level = str(payload.get("action_level") or "").strip()
    title = str(payload.get("title") or "").strip()
    hint = str(payload.get("hint") or "").strip()
    reference_notes = str(payload.get("reference_notes") or "")

    # markdown_files may arrive as a list (preferred) or comma/newline-
    # separated string (matches the way the queue add route already accepts
    # reference_files). Normalize either shape into a list[str].
    raw_md = payload.get("markdown_files")
    if isinstance(raw_md, list):
        markdown_files = [str(p).strip() for p in raw_md if str(p).strip()]
    elif isinstance(raw_md, str):
        parts: list[str] = []
        for line in raw_md.splitlines():
            for piece in line.split(","):
                piece = piece.strip()
                if piece:
                    parts.append(piece)
        markdown_files = parts
    else:
        markdown_files = []

    try:
        result = dream_trials.create_structured_dream_trial(
            repo_path=repo_path,
            dream_type=dream_type,
            action_level=action_level,
            title=title,
            hint=hint,
            reference_notes=reference_notes,
            markdown_files=markdown_files,
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "trial_id": result.trial_id,
        "status": result.decision,
        "decision": result.decision,
        "artifact_dir": result.trial_dir,
        "files": result.files_written,
        "allowed_actions": result.allowed_actions,
        "blocked_actions": result.blocked_actions,
    }


@bp.route("/dream/trials/list", methods=["GET"])
def dream_trials_list():
    """List trials for the given repo, newest first. Malformed folders are skipped."""
    repo_path = str(request.values.get("repo_path") or "").strip()
    if not _valid_repo(repo_path):
        return {"error": f"repo_path is not a directory: {repo_path}"}

    trials_root = dream_trials._trials_root(repo_path)
    if not trials_root.is_dir():
        return {"trials": []}

    summaries: list[dict] = []
    for sub in trials_root.iterdir():
        if not sub.is_dir():
            continue
        # Defense-in-depth: only accept directories whose name parses as a
        # well-formed trial_id. Skips human-created junk folders silently.
        if not _TRIAL_ID_RE.match(sub.name):
            continue
        trial_path = sub / "trial.json"
        if not trial_path.is_file():
            continue
        summary = _summarize_trial(trial_path)
        if summary is None:
            continue
        summaries.append(summary)

    # Newest first. trial_ids embed `%Y%m%d-%H%M%S`, so plain string sort works.
    summaries.sort(key=lambda s: s.get("trial_id", ""), reverse=True)
    return {"trials": summaries}


@bp.route("/dream/trials/file", methods=["GET"])
def dream_trials_file():
    """Serve one whitelisted file from a trial directory. Read-only."""
    repo_path = str(request.values.get("repo_path") or "").strip()
    trial_id = str(request.values.get("trial_id") or "").strip()
    file_name = str(request.values.get("file") or "").strip()

    if not _valid_repo(repo_path):
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}
    if file_name not in _ALLOWED_TRIAL_FILES:
        return {"ok": False, "error": f"file not allowed: {file_name}"}

    trial_dir = _resolve_trial_dir(repo_path, trial_id)
    if trial_dir is None:
        return {"ok": False, "error": f"trial not found: {trial_id}"}

    target = (trial_dir / file_name).resolve()
    try:
        target.relative_to(trial_dir.resolve())
    except ValueError:
        return {"ok": False, "error": "path escapes trial dir"}
    if not target.is_file():
        return {"ok": False, "error": f"file not found: {file_name}"}

    try:
        content = target.read_text(encoding="utf-8")
    except OSError as e:
        return {"ok": False, "error": f"unreadable: {e}"}

    return {"ok": True, "trial_id": trial_id, "file": file_name, "content": content}
