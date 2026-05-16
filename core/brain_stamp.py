from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPT_CONFIG_CANDIDATES = [
    "config.py",
    "core/config.py",
    "core/control_engine.py",
    "core/code_dna.py",
    "core/scout.py",
    "core/sleeping_consultant.py",
]


def _run_git(repo: Path, args: list[str], timeout: int = 5) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return None

    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None

    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None

    return h.hexdigest()


def _combined_hash(repo: Path, rel_paths: list[str]) -> dict[str, Any]:
    files: dict[str, str] = {}
    h = hashlib.sha256()

    for rel in rel_paths:
        path = repo / rel
        digest = _sha256_file(path)
        if not digest:
            continue
        files[rel] = digest
        h.update(rel.encode("utf-8"))
        h.update(digest.encode("utf-8"))

    return {
        "hash": h.hexdigest() if files else None,
        "files": files,
    }


def collect_brain_stamp(repo_path: str | Path = ".") -> dict[str, Any]:
    repo = Path(repo_path).resolve()

    git_sha = _run_git(repo, ["rev-parse", "HEAD"])
    git_branch = _run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    status = _run_git(repo, ["status", "--porcelain"]) or ""
    diff_stat = _run_git(repo, ["diff", "--stat", "HEAD"]) or ""

    dirty_lines = [line for line in status.splitlines() if line.strip()]
    dirty = bool(dirty_lines)

    if len(diff_stat) > 500:
        diff_stat_capped = diff_stat[:500] + "\n... [truncated]"
    else:
        diff_stat_capped = diff_stat

    prompt_config = _combined_hash(repo, PROMPT_CONFIG_CANDIDATES)

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_branch": git_branch,
        "git_dirty": dirty,
        "git_dirty_summary": f"{len(dirty_lines)} dirty file(s)" if dirty else "clean",
        "git_diff_stat_capped": diff_stat_capped,
        "prompt_config_hash": prompt_config["hash"],
        "prompt_config_files": prompt_config["files"],
    }


def format_brain_stamp_markdown(stamp: dict[str, Any]) -> str:
    lines = [
        "## Brain Stamp",
        "",
        f"- Git SHA: `{stamp.get('git_sha') or 'unknown'}`",
        f"- Branch: `{stamp.get('git_branch') or 'unknown'}`",
        f"- Dirty: `{stamp.get('git_dirty')}` ({stamp.get('git_dirty_summary')})",
        f"- Prompt/config hash: `{stamp.get('prompt_config_hash') or 'none'}`",
    ]

    diff_stat = stamp.get("git_diff_stat_capped")
    if diff_stat:
        lines.extend([
            "",
            "### Dirty diff stat",
            "",
            "```text",
            diff_stat,
            "```",
        ])

    return "\n".join(lines)