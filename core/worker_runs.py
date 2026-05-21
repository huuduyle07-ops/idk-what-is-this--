"""Phase 7.2 — review and import worker-run artifacts.

Reads Phase 7.1 output under `<AI-project>/.agent/worker_runs/<run>/` and,
when the operator chooses, imports a complete run into
`<AI-project>/.agent/proposals/<run>/01-<slug>/` so it can flow through the
existing proposal -> lesson review path.

Pure I/O + validation. No subprocess, no Flask. Never modifies the real
repo or the source worker_runs directory.

Safety policy (enforced here):
  - path-traversal guard on every run dir reference
  - import refuses dry-run worker outputs
  - import refuses incomplete worker outputs
  - imported proposals carry human_approved_for_proposal=false and
    needs_revalidation=true so the proposal queue / lesson promoter
    won't pick them up automatically
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import handoff_notes
from core.handoff_notes import _slug  # type: ignore[attr-defined]
from core.run_lifecycle import run_patch_plan_with_artifacts


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKER_RUNS_ROOT = PROJECT_ROOT / ".agent" / "worker_runs"
DEFAULT_PROPOSALS_ROOT = PROJECT_ROOT / ".agent" / "proposals"

RAW_OUTPUT_PREVIEW_CHARS = 2000
_RAW_OUTPUT_TRUNCATION_MARKER = "\n…[truncated]\n"

REQUIRED_FILES_FOR_IMPORT: tuple[str, ...] = (
    "handoff.md",
    "worker_run.json",
    "proposal.md",
    "patch_plan.json",
)
_OPTIONAL_COPIED_FILES: tuple[str, ...] = ("raw_output.txt",)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_worker_runs_root(root: Path | None) -> Path:
    target = Path(root) if root is not None else DEFAULT_WORKER_RUNS_ROOT
    target.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_proposals_root(root: Path | None) -> Path:
    target = Path(root) if root is not None else DEFAULT_PROPOSALS_ROOT
    target.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_run_dir(path_or_id: str | Path, root: Path) -> Path:
    """Path-traversal guard. Returns a directory strictly under `root`."""
    raw = str(path_or_id).strip()
    if not raw:
        raise ValueError("worker run path/id is empty")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.expanduser().resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"worker run path is outside {root_resolved}: {candidate}"
        ) from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"worker run directory not found: {candidate}")
    return candidate


def _parse_worker_run_json(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "worker_run.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_handoff_title(run_dir: Path) -> str | None:
    handoff_path = run_dir / "handoff.md"
    if not handoff_path.is_file():
        return None
    try:
        text = handoff_path.read_text(encoding="utf-8")
        meta, _body = handoff_notes._parse_meta_and_body(text)  # type: ignore[attr-defined]
        title = meta.get("title")
        return title if isinstance(title, str) and title.strip() else None
    except (OSError, ValueError):
        return None


def _raw_output_preview(run_dir: Path) -> str:
    path = run_dir / "raw_output.txt"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= RAW_OUTPUT_PREVIEW_CHARS:
        return text
    return text[:RAW_OUTPUT_PREVIEW_CHARS] + _RAW_OUTPUT_TRUNCATION_MARKER


def detect_worker_outputs(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
) -> dict[str, Any]:
    root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(run_dir, root)
    presence = {f: (resolved / f).is_file() for f in REQUIRED_FILES_FOR_IMPORT}
    missing = [f for f, present in presence.items() if not present]
    return {
        "has_handoff_md": presence["handoff.md"],
        "has_worker_run_json": presence["worker_run.json"],
        "has_proposal_md": presence["proposal.md"],
        "has_patch_plan_json": presence["patch_plan.json"],
        "missing": missing,
        "complete": not missing,
    }


def _build_run_summary(
    run_dir: Path,
    *,
    include_preview: bool,
) -> dict[str, Any]:
    record = _parse_worker_run_json(run_dir)
    detect = detect_worker_outputs(run_dir, worker_runs_root=run_dir.parent)
    started = record.get("started_at")
    summary: dict[str, Any] = {
        "run_id": run_dir.name,
        "path": str(run_dir),
        # Legacy /worker-runs/list compatibility fields:
        "artifact_dir": str(run_dir),
        "name": run_dir.name,
        # worker_run.json fields:
        "dry_run": record.get("dry_run"),
        "worker": record.get("worker"),
        "command": record.get("command"),
        "exit_code": record.get("exit_code"),
        "timed_out": record.get("timed_out"),
        "duration_sec": record.get("duration_sec"),
        "handoff_path": record.get("handoff_path"),
        "started_at": started,
        "finished_at": record.get("finished_at"),
        "error": record.get("error"),
        "created_at": started,
        # detect_worker_outputs fields:
        "has_proposal_md": detect["has_proposal_md"],
        "has_patch_plan_json": detect["has_patch_plan_json"],
        "has_handoff_md": detect["has_handoff_md"],
        "has_worker_run_json": detect["has_worker_run_json"],
        # parsed:
        "handoff_title": _parse_handoff_title(run_dir),
    }
    if include_preview:
        summary["raw_output_preview"] = _raw_output_preview(run_dir)
    return summary


def list_worker_runs(
    worker_runs_root: Path | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    root = _resolve_worker_runs_root(worker_runs_root)
    if not root.is_dir():
        return []
    try:
        dirs = sorted(
            (d for d in root.iterdir() if d.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for d in dirs:
        if not (d / "worker_run.json").is_file():
            continue
        out.append(_build_run_summary(d, include_preview=False))
        if len(out) >= max(1, limit):
            break
    return out


def read_worker_run(
    path_or_id: str | Path,
    worker_runs_root: Path | None = None,
) -> dict[str, Any]:
    root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(path_or_id, root)
    return _build_run_summary(resolved, include_preview=True)


def _proposal_destination(
    proposals_root: Path,
    slug: str,
) -> Path:
    now = datetime.now(timezone.utc)
    base_run = proposals_root / now.strftime("%Y%m%d_%H%M%S")
    suffix = 0
    run = base_run
    while run.exists():
        suffix += 1
        run = proposals_root / f"{now.strftime('%Y%m%d_%H%M%S')}-{suffix}"
    item_dir = run / f"01-{slug}"
    item_dir.mkdir(parents=True, exist_ok=False)
    return item_dir


def import_worker_run_as_proposal(
    run_dir: str | Path,
    worker_runs_root: Path | None = None,
    proposals_root: Path | None = None,
) -> dict[str, Any]:
    runs_root = _resolve_worker_runs_root(worker_runs_root)
    resolved = _resolve_run_dir(run_dir, runs_root)

    detect = detect_worker_outputs(resolved, worker_runs_root=runs_root)
    if not detect["complete"]:
        raise FileNotFoundError(
            f"worker run is incomplete: missing {', '.join(detect['missing'])}"
        )

    record = _parse_worker_run_json(resolved)
    if record.get("dry_run") is True:
        raise ValueError(
            "cannot import a dry-run worker output as a proposal"
        )

    title = _parse_handoff_title(resolved) or resolved.name
    slug = _slug(title)
    proposals_dst_root = _resolve_proposals_root(proposals_root)
    item_dir = _proposal_destination(proposals_dst_root, slug)

    imported_files: list[str] = []
    for filename in REQUIRED_FILES_FOR_IMPORT:
        shutil.copy2(resolved / filename, item_dir / filename)
        imported_files.append(filename)
    for filename in _OPTIONAL_COPIED_FILES:
        src = resolved / filename
        if src.is_file():
            shutil.copy2(src, item_dir / filename)
            imported_files.append(filename)

    now_iso = _now_iso()
    item = {
        "kind": "worker_run_import",
        "source": "worker_run",
        "source_run_id": resolved.name,
        "source_run_dir": str(resolved),
        "title": title,
        "worker": record.get("worker"),
        "imported_at": now_iso,
        "human_approved_for_proposal": False,
        "needs_revalidation": True,
    }
    source_metadata = {
        "source": "worker_run",
        "source_run_id": resolved.name,
        "source_run_dir": str(resolved),
        "handoff_path": record.get("handoff_path"),
        "worker": record.get("worker"),
        "command": record.get("command"),
        "imported_at": now_iso,
        "imported_files": imported_files,
    }
    (item_dir / "item.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    (item_dir / "source_metadata.json").write_text(
        json.dumps(source_metadata, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "proposal_dir": str(item_dir),
        "source_run_dir": str(resolved),
        "source_run_id": resolved.name,
        "item": item,
        "imported_at": now_iso,
    }


# --- Phase 7.2.1: validate imported worker proposal -------------------------

_VALIDATE_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".agent", "node_modules", "target",
    ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build",
)


def _inferred_validation_command(repo: Path) -> str:
    """Best-effort inference: language from `inspect_repo_inventory`, command
    from `get_default_validation_command`. Returns "" if no command applies.

    Isolated in a thin helper so tests can monkeypatch it without spinning
    up the full language detector for each fixture.
    """
    try:
        from core.repo_librarian import inspect_repo_inventory
        from core.validation_command import get_default_validation_command
        language = inspect_repo_inventory(str(repo)).get(
            "primary_language", "unknown"
        )
        return get_default_validation_command(language, repo) or ""
    except Exception:
        return ""


def _resolve_proposal_dir(
    path_or_id: str | Path, proposals_root: Path
) -> Path:
    """Path-traversal guard. Returns a directory strictly under proposals_root."""
    raw = str(path_or_id).strip()
    if not raw:
        raise ValueError("proposal_dir is empty")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = proposals_root / candidate
    candidate = candidate.expanduser().resolve()
    root_resolved = proposals_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"proposal_dir is outside {root_resolved}: {candidate}"
        ) from exc
    if not candidate.is_dir():
        raise FileNotFoundError(f"proposal_dir not found: {candidate}")
    return candidate


def _read_proposal_title(proposal_dir: Path) -> str:
    item_path = proposal_dir / "item.json"
    if item_path.is_file():
        try:
            data = json.loads(item_path.read_text(encoding="utf-8"))
            title = data.get("title") if isinstance(data, dict) else None
            if isinstance(title, str) and title.strip():
                return title.strip()
        except (OSError, json.JSONDecodeError):
            pass
    return proposal_dir.name


def _update_item_status(proposal_dir: Path, status: str) -> None:
    item_path = proposal_dir / "item.json"
    if not item_path.is_file():
        return
    try:
        item = json.loads(item_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(item, dict):
        return
    item["needs_revalidation"] = False
    item["validation_status"] = status
    item["validation_status_at"] = _now_iso()
    item_path.write_text(
        json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def validate_imported_worker_proposal(
    proposal_dir: str | Path,
    repo_path: str | Path,
    *,
    proposals_root: Path | None = None,
    validation_timeout_sec: int = 60,
) -> dict[str, Any]:
    """Apply the worker proposal's patch_plan.json in a temp clone of
    `repo_path` and run the inferred validation command. Writes
    `apply_result.json`, `validation.json`, `validation_output.txt` into
    proposal_dir. Never modifies the real repo or `repo_path`.

    Returns dict: {ok, proposal_dir, apply_success, validation_ok,
                   message, apply_result_path, validation_path}.
    """
    proposals_dst_root = _resolve_proposals_root(proposals_root)
    resolved = _resolve_proposal_dir(proposal_dir, proposals_dst_root)

    plan_path = resolved / "patch_plan.json"
    if not plan_path.is_file():
        raise FileNotFoundError(
            f"proposal_dir missing patch_plan.json: {resolved}"
        )
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"patch_plan.json is not valid JSON: {exc}") from exc
    if not isinstance(plan, list) or not plan:
        raise ValueError("patch_plan.json must be a non-empty JSON list")

    repo_src = Path(repo_path).expanduser().resolve()
    if not repo_src.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_src}")

    title = _read_proposal_title(resolved)
    apply_result: dict[str, Any] = {}
    validation: dict[str, Any] = {}
    validation_output_text = ""

    with tempfile.TemporaryDirectory(
        prefix="worker-validate-", ignore_cleanup_errors=True
    ) as tmp_dir:
        temp_clone = Path(tmp_dir) / "repo"
        shutil.copytree(repo_src, temp_clone, ignore=_VALIDATE_COPY_IGNORE)

        try:
            apply_result = run_patch_plan_with_artifacts(
                str(temp_clone),
                plan,
                validation_command=None,
                user_query=title,
                control_result={
                    "route": "worker_run_validate",
                    "proposal_dir": str(resolved),
                    "title": title,
                },
                source="worker_run_validate",
            )
        except Exception as exc:
            apply_result = {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "applied_ops": [],
                "diffs": [],
            }

        validation_command = _inferred_validation_command(temp_clone)

        if apply_result.get("success") and validation_command:
            try:
                from scripts.run_patch_proposal_queue import _run_validation_command
                validation = _run_validation_command(
                    validation_command,
                    cwd=temp_clone,
                    timeout_sec=max(1, int(validation_timeout_sec)),
                )
            except Exception as exc:
                validation = {
                    "ok": False,
                    "validation_ok": False,
                    "command": validation_command,
                    "error": f"validation runner error: {type(exc).__name__}: {exc}",
                    "duration_sec": 0.0,
                    "segments": [],
                    "output": "",
                }
        elif not apply_result.get("success"):
            validation = {
                "ok": False,
                "validation_ok": None,
                "command": validation_command,
                "error": "apply did not succeed; validation skipped",
                "duration_sec": 0.0,
                "segments": [],
                "output": "",
            }
        else:
            # apply succeeded but no command could be inferred
            validation = {
                "ok": True,
                "validation_ok": None,
                "command": "",
                "error": "no validation command inferred",
                "duration_sec": 0.0,
                "segments": [],
                "output": "",
            }

        validation_output_text = validation.get("output") or ""

    (resolved / "apply_result.json").write_text(
        json.dumps(apply_result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (resolved / "validation.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (resolved / "validation_output.txt").write_text(
        validation_output_text, encoding="utf-8"
    )

    apply_success = bool(apply_result.get("success"))
    val_ok = validation.get("validation_ok")
    if not apply_success:
        status = "failed"
        message = "Apply failed: " + str(apply_result.get("error") or "(no detail)")
    elif val_ok is True:
        status = "passed"
        message = "Apply and validation passed."
    elif val_ok is False:
        status = "failed"
        message = "Apply succeeded but validation failed."
    else:
        status = "no_command"
        message = "Apply succeeded; no validation command inferred — record only."

    _update_item_status(resolved, status)

    return {
        "ok": True,
        "proposal_dir": str(resolved),
        "apply_success": apply_success,
        "validation_ok": val_ok,
        "message": message,
        "apply_result_path": str(resolved / "apply_result.json"),
        "validation_path": str(resolved / "validation.json"),
    }
