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
