#!/usr/bin/env python
"""Phase 7.1 — run a handoff note's worker command in a temp clone.

Default behavior is DRY RUN: print the would-be command and write a
worker_run.json with `dry_run: true`. The real subprocess only runs when
`--allow-run` is explicitly passed. The real repo is never modified.

CLI:
    python scripts/run_subagent_handoff.py --note <path>
    python scripts/run_subagent_handoff.py --note <path> --allow-run
    python scripts/run_subagent_handoff.py --note <path> --allow-run --timeout-sec 120
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import handoff_notes
from core.handoff_notes import _slug  # type: ignore[attr-defined]


HANDOFF_ROOT = PROJECT_ROOT / ".agent" / "handoffs"
WORKER_RUNS_ROOT = PROJECT_ROOT / ".agent" / "worker_runs"


WORKER_COMMAND_MAP: dict[str, str | None] = {
    "codex":       "codex exec --full-auto",
    "claude-code": "claude --print",
    "gemini":      "gemini --prompt-file HANDOFF.md",
    "other":       None,
}

_ENV_OVERRIDE_FOR_WORKER = {
    "codex":       "HANDOFF_CODEX_CMD",
    "claude-code": "HANDOFF_CLAUDE_CODE_CMD",
    "gemini":      "HANDOFF_GEMINI_CMD",
    "other":       "HANDOFF_OTHER_CMD",
}

_COPY_IGNORE = shutil.ignore_patterns(
    ".git", ".agent", "node_modules", "target",
    ".venv", "venv", "__pycache__", ".pytest_cache",
    "dist", "build",
)

DEFAULT_TIMEOUT_SEC = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_worker_command(worker: str, override: str | None) -> str | None:
    if override:
        return override.strip() or None
    env_var = _ENV_OVERRIDE_FOR_WORKER.get(worker)
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value:
            return env_value
    return WORKER_COMMAND_MAP.get(worker)


def _new_artifact_dir(slug: str) -> Path:
    WORKER_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    base = WORKER_RUNS_ROOT / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}"
    suffix = 1
    target = base
    while target.exists():
        target = WORKER_RUNS_ROOT / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}-{suffix}"
        suffix += 1
    target.mkdir(parents=True)
    return target


def _write_artifacts(
    *,
    artifact_dir: Path,
    handoff_text: str,
    command: str | None,
    record: dict[str, Any],
    raw_output: str,
) -> None:
    (artifact_dir / "handoff.md").write_text(handoff_text, encoding="utf-8")
    (artifact_dir / "worker_command.txt").write_text((command or "") + "\n", encoding="utf-8")
    (artifact_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")
    (artifact_dir / "worker_run.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def run_handoff(
    *,
    note_path: str,
    allow_run: bool = False,
    worker_override: str | None = None,
    worker_command_override: str | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    root = handoff_root if handoff_root is not None else HANDOFF_ROOT
    parsed = handoff_notes.read_handoff_note(note_path, handoff_root=root)
    meta = parsed["meta"]
    handoff_text = parsed["raw"]
    slug = meta.get("slug") or _slug(meta.get("title") or "handoff")
    worker = (worker_override or meta.get("intended_worker") or "other").strip()
    command = _resolve_worker_command(worker, worker_command_override)
    artifact_dir = _new_artifact_dir(slug)

    error: str | None = None
    if not command:
        error = (
            "no worker_command resolved (set HANDOFF_<WORKER>_CMD env var or "
            "pass --worker-command)"
        )

    record: dict[str, Any] = {
        "dry_run": True,
        "started_at": _now_iso(),
        "finished_at": None,
        "duration_sec": 0.0,
        "exit_code": None,
        "timed_out": False,
        "command": command,
        "worker": worker,
        "handoff_path": parsed["path"],
        "artifact_dir": str(artifact_dir),
        "timeout_sec": int(timeout_sec),
        "error": error,
    }

    if not allow_run or error or meta.get("status") == "archived":
        if meta.get("status") == "archived" and not error:
            record["error"] = "handoff status is archived; refusing to run"
        _write_artifacts(
            artifact_dir=artifact_dir,
            handoff_text=handoff_text,
            command=command,
            record=record,
            raw_output="",
        )
        return record

    # --- Real run path -------------------------------------------------
    record["dry_run"] = False
    started = time.time()
    repo_path = meta.get("repo_path") or str(PROJECT_ROOT)
    repo_src = Path(repo_path).resolve()
    if not repo_src.is_dir():
        record["error"] = f"repo_path is not a directory: {repo_src}"
        record["finished_at"] = _now_iso()
        _write_artifacts(
            artifact_dir=artifact_dir,
            handoff_text=handoff_text,
            command=command,
            record=record,
            raw_output="",
        )
        handoff_notes.update_handoff_status(parsed["path"], "failed", handoff_root=root)
        return record

    raw_output = ""
    exit_code: int | None = None
    timed_out = False

    with tempfile.TemporaryDirectory(prefix="handoff-clone-", ignore_cleanup_errors=True) as tmp_dir:
        temp_clone = Path(tmp_dir) / "repo"
        shutil.copytree(repo_src, temp_clone, ignore=_COPY_IGNORE)
        (temp_clone / "HANDOFF.md").write_text(handoff_text, encoding="utf-8")

        try:
            completed = subprocess.run(
                shlex.split(command, posix=(os.name != "nt")),
                cwd=str(temp_clone),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1, int(timeout_sec)),
                check=False,
            )
            exit_code = completed.returncode
            raw_output = (completed.stdout or "") + (completed.stderr or "")
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            raw_output = (stdout or "") + (stderr or "")
            record["error"] = f"subprocess timed out after {timeout_sec}s"
        except FileNotFoundError as exc:
            record["error"] = f"worker executable not found: {exc}"
        except Exception as exc:
            record["error"] = f"subprocess error: {type(exc).__name__}: {exc}"

        # Surface worker-produced artifacts from temp clone root.
        for filename in ("proposal.md", "patch_plan.json"):
            produced = temp_clone / filename
            if produced.is_file():
                shutil.copy2(produced, artifact_dir / filename)

    finished = time.time()
    record.update(
        finished_at=_now_iso(),
        duration_sec=round(finished - started, 3),
        exit_code=exit_code,
        timed_out=timed_out,
    )
    _write_artifacts(
        artifact_dir=artifact_dir,
        handoff_text=handoff_text,
        command=command,
        record=record,
        raw_output=raw_output,
    )

    final_status = "ran" if (exit_code == 0 and not timed_out and not record.get("error")) else "failed"
    handoff_notes.update_handoff_status(parsed["path"], final_status, handoff_root=root)
    return record


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run a handoff note's worker command in a temp clone.",
    )
    p.add_argument("--note", required=True)
    p.add_argument("--allow-run", action="store_true", default=False)
    p.add_argument("--worker", default=None, choices=sorted(handoff_notes.VALID_WORKERS))
    p.add_argument("--worker-command", default=None)
    p.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    args = p.parse_args(argv)

    try:
        result = run_handoff(
            note_path=args.note,
            allow_run=args.allow_run,
            worker_override=args.worker,
            worker_command_override=args.worker_command,
            timeout_sec=args.timeout_sec,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if result.get("dry_run"):
        print("DRY RUN — no subprocess was executed.")
    print(f"command: {result.get('command')}")
    print(f"artifact_dir: {result.get('artifact_dir')}")
    if result.get("error"):
        print(f"error: {result.get('error')}", file=sys.stderr)
        return 2
    return 0 if (result.get("exit_code") in (None, 0) and not result.get("timed_out")) else 1


if __name__ == "__main__":
    raise SystemExit(main())