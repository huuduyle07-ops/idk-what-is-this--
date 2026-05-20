"""Phase 7.1 — bounded handoff notes for external coding agents.

Pure storage + validation. No subprocess, no Flask. Notes are markdown files
with JSON frontmatter under `<AI-project>/.agent/handoffs/`. Run artifacts
live elsewhere (see `scripts/run_subagent_handoff.py`).

Safety policy (enforced here, not at runtime):
  - notes default to proposal-only / do-not-apply / do-not-commit
  - default forbidden_files list always includes .env/.agent/.git/etc.
  - allowed_files entries that overlap defaults are recorded as
    safety_overrides for audit
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HANDOFF_ROOT = PROJECT_ROOT / ".agent" / "handoffs"


VALID_WORKERS: frozenset[str] = frozenset({"codex", "claude-code", "gemini", "other"})
VALID_TASK_TYPES: frozenset[str] = frozenset({
    "proposal_only",
    "review_only",
    "explain_only",
    "benchmark_case",
    "research",
})
VALID_STATUSES: frozenset[str] = frozenset({"draft", "ran", "failed", "archived"})

DEFAULT_SAFETY_RULES: tuple[str, ...] = (
    "proposal only",
    "do not apply patch",
    "do not commit",
    "do not push",
    "do not edit .env/.agent/.git/node_modules/target/tests unless explicitly allowed",
    "return proposal.md and patch_plan.json if possible",
)

DEFAULT_FORBIDDEN_FILES: tuple[str, ...] = (
    ".env",
    ".agent",
    ".git",
    "node_modules",
    "target",
    # blocks external agents from writing or editing test files by default;
    # operators must list specific test paths in allowed_files to override
    "tests",
)


def _slug(text: str, fallback: str = "handoff") -> str:
    out: list[str] = []
    for ch in (text or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    value = "".join(out).strip("-")
    return value[:60] or fallback


_HANDOFF_META_RE = re.compile(
    r"<!--HANDOFF_META\s*(?P<json>\{.*?\})\s*HANDOFF_META-->",
    re.DOTALL,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_rel_path(raw: Any) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    if not text or text.startswith("/"):
        return None
    parts = [p for p in text.split("/") if p]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def _validate_allowed_files(values: list[str] | None) -> list[str]:
    if not values:
        return []
    safe: list[str] = []
    for v in values:
        s = _safe_rel_path(v)
        if s is None:
            raise ValueError(f"allowed_files entry is not a safe relative path: {v!r}")
        if s not in safe:
            safe.append(s)
    return safe


def _validate_forbidden_files(values: list[str] | None) -> list[str]:
    if not values:
        return []
    safe: list[str] = []
    for v in values:
        s = _safe_rel_path(v)
        if s is None:
            # forbidden_files can be path prefixes like ".agent" — preserve raw
            text = str(v).strip().replace("\\", "/")
            if text:
                if text not in safe:
                    safe.append(text)
            continue
        if s not in safe:
            safe.append(s)
    return safe


def _merge_forbidden(
    user_forbidden: list[str], allowed: list[str]
) -> tuple[list[str], list[str]]:
    merged = list(user_forbidden)
    for d in DEFAULT_FORBIDDEN_FILES:
        if d not in merged:
            merged.append(d)
    overrides: list[str] = []
    final: list[str] = []
    for entry in merged:
        if any(a == entry or a.startswith(entry + "/") for a in allowed):
            overrides.append(entry)
            continue
        final.append(entry)
    # Allowed entries that are children of defaults: surface override too
    for a in allowed:
        for d in DEFAULT_FORBIDDEN_FILES:
            if (a == d or a.startswith(d + "/")) and a not in overrides:
                overrides.append(a)
    return final, overrides


def _merge_safety_rules(extra: list[str] | None) -> list[str]:
    rules = list(DEFAULT_SAFETY_RULES)
    for r in extra or []:
        s = str(r).strip()
        if s and s not in rules:
            rules.append(s)
    return rules


def _resolve_repo_path(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    return value


def _try_collect_brain_stamp(repo_path: str | None) -> dict[str, Any]:
    try:
        from core.brain_stamp import collect_brain_stamp

        target = repo_path or str(PROJECT_ROOT)
        return collect_brain_stamp(target) or {}
    except Exception:
        return {}


def _render_note_markdown(meta: dict[str, Any], context_summary: str, expected_output: str) -> str:
    meta_json = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True)
    body_lines = [
        f"<!--HANDOFF_META\n{meta_json}\nHANDOFF_META-->",
        "",
        f"# {meta['title']}",
        "",
        "## Context summary",
        "",
        context_summary.strip() or "_No context summary provided._",
        "",
        "## Expected output",
        "",
        expected_output.strip() or "_No expected output declared._",
        "",
        "## Safety rules (advisory — enforced by the runner script too)",
        "",
    ]
    for rule in meta.get("safety_rules", []):
        body_lines.append(f"- {rule}")
    body_lines += [
        "",
        "## How to run this handoff manually",
        "",
        "Always run inside an isolated temp clone — never against the real repo.",
        "`scripts/run_subagent_handoff.py` does this for you when invoked",
        "with `--allow-run`.",
        "",
    ]
    return "\n".join(body_lines) + "\n"


def _resolve_handoff_root(handoff_root: Path | None) -> Path:
    root = Path(handoff_root) if handoff_root is not None else DEFAULT_HANDOFF_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def create_handoff_note(
    *,
    title: str,
    intended_worker: str,
    task_type: str,
    repo_path: str | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
    validation_command: str | None = None,
    context_summary: str = "",
    expected_output: str = "",
    extra_safety_rules: list[str] | None = None,
    handoff_root: Path | None = None,
) -> dict[str, Any]:
    title_clean = (title or "").strip()
    if not title_clean:
        raise ValueError("title must be a non-empty string")
    if intended_worker not in VALID_WORKERS:
        raise ValueError(
            f"intended_worker must be one of {sorted(VALID_WORKERS)}, got {intended_worker!r}"
        )
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(
            f"task_type must be one of {sorted(VALID_TASK_TYPES)}, got {task_type!r}"
        )

    safe_allowed = _validate_allowed_files(allowed_files)
    user_forbidden = _validate_forbidden_files(forbidden_files)
    final_forbidden, overrides = _merge_forbidden(user_forbidden, safe_allowed)
    safety_rules = _merge_safety_rules(extra_safety_rules)
    repo = _resolve_repo_path(repo_path)
    brain_stamp = _try_collect_brain_stamp(repo)

    now = datetime.now(timezone.utc)
    created_iso = now.isoformat(timespec="seconds")
    slug = _slug(title_clean)
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}.md"

    root = _resolve_handoff_root(handoff_root)
    path = root / filename
    suffix = 1
    while path.exists():
        path = root / f"{now.strftime('%Y%m%d_%H%M%S')}_{slug}-{suffix}.md"
        suffix += 1

    meta: dict[str, Any] = {
        "title": title_clean,
        "created_at": created_iso,
        "owner": "human",
        "intended_worker": intended_worker,
        "task_type": task_type,
        "repo_path": repo,
        "allowed_files": safe_allowed,
        "forbidden_files": final_forbidden,
        "validation_command": (validation_command or "").strip() or None,
        "status": "draft",
        "safety_rules": safety_rules,
        "safety_overrides": overrides,
        "slug": slug,
        "brain_stamp": brain_stamp,
    }
    path.write_text(_render_note_markdown(meta, context_summary, expected_output), encoding="utf-8")

    return {"path": str(path), "meta": meta, "slug": slug}
