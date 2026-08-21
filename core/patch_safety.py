"""Apply-time safety gate for patches.

Pure helper: given a list of changed file paths + optional project root,
decide whether the patch is safe to apply to disk. Used by /apply_patch,
/apply_patch_plan, and their /test_patch siblings before any write.

Single source of truth for forbidden-path constants — `core.lesson_quality`
re-imports from here so lesson promotion and apply-time gating cannot drift.

Rules:
- Traversal: empty, absolute, contains `..`, or resolves outside project_root.
- Protected dirs: `.agent`, `.git`, `node_modules`, `target` anywhere in path.
- Env files: `.env` or `.env.*`.
- Test paths: `test/`, `tests/`, `__test__/`, `spec/`, `specs/` dirs;
  `test.py`/`tests.js` exact names; `test_*.py` prefix; `_test.py` /
  `.test.ts` / `.spec.tsx` etc. suffixes.
- Benchmark validation: under `benchmarks/`, files `case.json` / starting
  with `expected` / containing `validation` or starting with `validate`.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


_PROTECTED_DIRS = {".agent", ".git", "node_modules", "target"}
_TEST_DIRS = {"test", "tests", "__test__", "__tests__", "spec", "specs"}
_TEST_FILE_NAMES = {
    "test.py",
    "tests.py",
    "test.js",
    "tests.js",
    "test.ts",
    "tests.ts",
}
_TEST_SUFFIXES = (
    "_test.py",
    "_tests.py",
    "_test.go",
    "_test.rs",
    "_test.c",
    "_test.cpp",
    "_test.cc",
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
)

# Per-category rationale that ships alongside each blocked path. Keeps the
# default-deny policy from feeling arbitrary: every refusal tells the user
# WHY the rule exists and (where applicable) what an explicit-human-approval
# override would look like in a future iteration.
_CATEGORY_WHY: dict[str, str] = {
    "protected_dir": (
        "Default policy blocks edits inside `.agent` / `.git` / `node_modules` / `target` "
        "because these are agent-owned or build-output directories the patch flow "
        "must not own. Future override: explicit human approval may allow targeted edits."
    ),
    "env": (
        "Default policy blocks `.env*` files because they typically hold secrets "
        "and credentials that should never be rewritten by an automated patch. "
        "Future override: explicit human approval may allow."
    ),
    "test": (
        "Default policy blocks test paths because patches that rewrite tests can "
        "mask the real bug in production code, and the benchmark harness also "
        "treats touched tests as a fail signal. "
        "Future override: explicit human approval may allow test edits when the "
        "test itself is genuinely wrong."
    ),
    "benchmark_validation": (
        "Default policy blocks `case.json` / `expected*` / `validate*` files because "
        "they define the success criteria the benchmark runs against; editing them "
        "would make the harness lie. Use the Add Case UI to change benchmark "
        "expectations instead of patching them."
    ),
    "traversal": (
        "Hard safety boundary: absolute paths, `..` segments, or anything that "
        "resolves outside the repo root is rejected with no override path. "
        "If you need to touch a file outside the repo, open it directly."
    ),
    "other": (
        "Default policy refuses this path. No override path is wired today; "
        "if the rule is wrong, update `core.patch_safety` so lesson promotion "
        "and apply-time gating stay in sync."
    ),
}


def category_why(category: str) -> str:
    """Return the human-readable rationale for a blocked-path category."""
    return _CATEGORY_WHY.get(category, _CATEGORY_WHY["other"])


def evaluate_patch_safety(
    changed_files: Sequence[str],
    project_root: Path | str | None = None,
) -> dict:
    """Return {ok, blocked_paths, reasons}.

    blocked_paths entries: {"path": str, "reason": str, "category": str}
    categories: traversal | protected_dir | env | test | benchmark_validation
    """
    blocked: list[dict] = []
    for raw in changed_files or []:
        traversal = _traversal_reason(raw, project_root)
        if traversal:
            blocked.append({
                "path": str(raw),
                "reason": traversal,
                "category": "traversal",
                "why": _CATEGORY_WHY["traversal"],
            })
            continue
        forbidden = _blocked_changed_path_reason(raw)
        if forbidden:
            category = _category_for_reason(forbidden)
            blocked.append({
                "path": str(raw),
                "reason": forbidden,
                "category": category,
                "why": category_why(category),
            })
    return {
        "ok": not blocked,
        "blocked_paths": blocked,
        "reasons": [b["reason"] for b in blocked],
    }


def attach_direct_context_to_patch_safety(**kwargs):
    """Lazily expose the CTX.APPLY.0 adapter from the safety namespace.

    Keeping this import lazy preserves the established, path-only
    ``evaluate_patch_safety`` import surface and avoids a cycle: the attachment
    calls this module's existing gate as one of its fail-closed checks.
    """

    from core.direct_context_patch_attachment import (
        attach_direct_context_to_patch_safety as _attach,
    )

    return _attach(**kwargs)


def _traversal_reason(raw, project_root) -> str | None:
    if raw is None:
        return "empty path"
    text = str(raw).strip()
    if not text:
        return "empty path"
    try:
        p = Path(text)
    except Exception:
        return f"invalid path: {text}"
    # Catch POSIX-style leading slash on Windows too, where Path().is_absolute()
    # only flags drive-rooted paths.
    if p.is_absolute() or text.startswith("/") or text.startswith("\\"):
        return f"absolute path not allowed: {text}"
    normalized = text.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        return f"path traversal `..` not allowed: {text}"
    if project_root is not None:
        try:
            root = Path(project_root).resolve()
            resolved = (root / text).resolve()
            resolved.relative_to(root)
        except (ValueError, OSError):
            return f"path escapes repo root: {text}"
    return None


def _category_for_reason(reason: str) -> str:
    if "protected path" in reason:
        return "protected_dir"
    if "env file" in reason:
        return "env"
    if "test path" in reason:
        return "test"
    if "benchmark validation" in reason:
        return "benchmark_validation"
    return "other"


def _normalize_path(path: str) -> str:
    text = str(path).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _is_env_path(parts: list[str]) -> bool:
    return any(part == ".env" or part.startswith(".env.") for part in parts)


def _is_test_path(parts: list[str], name: str) -> bool:
    if any(part in _TEST_DIRS for part in parts[:-1]):
        return True
    if name in _TEST_FILE_NAMES:
        return True
    if name.startswith("test_"):
        return True
    return any(name.endswith(suffix) for suffix in _TEST_SUFFIXES)


def _is_benchmark_validation_path(parts: list[str], name: str) -> bool:
    if "benchmarks" not in parts:
        return False
    if name == "case.json":
        return True
    if name.startswith("expected"):
        return True
    return "validation" in name or name.startswith("validate")


def _blocked_changed_path_reason(path: str) -> str | None:
    normalized = _normalize_path(path)
    parts = [part for part in normalized.split("/") if part]
    lowered_parts = [part.lower() for part in parts]
    name = lowered_parts[-1] if lowered_parts else ""

    for part in lowered_parts:
        if part in _PROTECTED_DIRS:
            return f"changed_files touches protected path {part}: {path}"

    if _is_env_path(lowered_parts):
        return f"changed_files touches env file: {path}"

    if _is_test_path(lowered_parts, name):
        return f"changed_files touches test path: {path}"

    if _is_benchmark_validation_path(lowered_parts, name):
        return f"changed_files touches benchmark validation file: {path}"

    return None
