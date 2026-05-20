from __future__ import annotations

import hashlib
import json
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

SCHEMA_VERSION = 2


def _stable_json_hash(value: Any) -> str | None:
    try:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _compute_code_dna_hash(repo: Path) -> str | None:
    try:
        from core.code_dna import compute_dna

        return _stable_json_hash(compute_dna(str(repo)))
    except Exception:
        return None


def compute_brain_stamp_id(stamp: dict[str, Any]) -> str:
    """Return a stable stamp id for provenance-sensitive run inputs.

    Timestamps are intentionally excluded so repeated reports over the same
    repo/prompt/DNA state get the same id.
    """
    payload = {
        "schema_version": stamp.get("schema_version", SCHEMA_VERSION),
        "git_sha": stamp.get("git_sha") or "unknown",
        "git_branch": stamp.get("git_branch") or "unknown",
        "git_dirty_summary": stamp.get("git_dirty_summary") or "unknown",
        "prompt_config_hash": stamp.get("prompt_config_hash") or "none",
        "code_dna_hash": stamp.get("code_dna_hash") or "none",
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]


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
    code_dna_hash = _compute_code_dna_hash(repo)

    stamp = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_branch": git_branch,
        "git_dirty": dirty,
        "git_dirty_summary": f"{len(dirty_lines)} dirty file(s)" if dirty else "clean",
        "git_diff_stat_capped": diff_stat_capped,
        "prompt_config_hash": prompt_config["hash"],
        "prompt_config_files": prompt_config["files"],
        "code_dna_hash": code_dna_hash,
    }
    stamp["brain_stamp_id"] = compute_brain_stamp_id(stamp)
    return stamp


def format_brain_stamp_markdown(stamp: dict[str, Any]) -> str:
    lines = [
        "## Brain Stamp",
        "",
        f"- Git SHA: `{stamp.get('git_sha') or 'unknown'}`",
        f"- Branch: `{stamp.get('git_branch') or 'unknown'}`",
        f"- Dirty: `{stamp.get('git_dirty')}` ({stamp.get('git_dirty_summary')})",
        f"- Prompt/config hash: `{stamp.get('prompt_config_hash') or 'none'}`",
    ]
    if stamp.get("brain_stamp_id"):
        lines.append(f"- Brain stamp ID: `{stamp.get('brain_stamp_id')}`")
    if stamp.get("code_dna_hash"):
        lines.append(f"- Code DNA hash: `{stamp.get('code_dna_hash')}`")

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
