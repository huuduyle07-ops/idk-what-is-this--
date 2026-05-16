from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


AUTO_APPROVED = "auto_approved"
NEEDS_HUMAN_REVIEW = "needs_human_review"
BLOCKED = "blocked"

PROMOTIONS = {AUTO_APPROVED, NEEDS_HUMAN_REVIEW, BLOCKED}

MAX_AUTO_DIFF_CHANGED_LINES = 30

_REQUIRED_FIELDS = (
    "validation_ok",
    "touched_forbidden_files",
    "missing_expected_files",
    "patch_kind",
    "rollback_happened",
    "changed_files",
)

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


def evaluate_lesson_candidate(candidate: dict) -> dict:
    """Classify whether a lesson candidate can become active knowledge.

    This is intentionally conservative. Missing or malformed evidence never
    auto-approves a lesson; dangerous evidence blocks it.
    """
    if not isinstance(candidate, dict):
        return {
            "promotion": NEEDS_HUMAN_REVIEW,
            "active_knowledge_allowed": False,
            "score": 0.0,
            "reasons": ["candidate is not a dict"],
        }

    reasons: list[str] = []
    review_reasons: list[str] = []
    block_reasons: list[str] = []

    missing = [field for field in _REQUIRED_FIELDS if field not in candidate]
    if missing:
        review_reasons.append("missing required fields: " + ", ".join(missing))

    validation_ok = candidate.get("validation_ok")
    if "validation_ok" in candidate:
        if validation_ok is True:
            pass
        elif validation_ok is False:
            block_reasons.append("validation_ok is false")
        else:
            review_reasons.append("validation_ok is missing or not boolean")

    rollback_happened = candidate.get("rollback_happened")
    if "rollback_happened" in candidate:
        if rollback_happened is True:
            block_reasons.append("rollback_happened is true")
        elif rollback_happened is not False:
            review_reasons.append("rollback_happened is missing or not boolean")

    forbidden_files = _coerce_path_list(candidate.get("touched_forbidden_files"))
    if "touched_forbidden_files" in candidate:
        if forbidden_files is None:
            review_reasons.append("touched_forbidden_files is not a list")
        elif forbidden_files:
            block_reasons.append(
                "touched_forbidden_files is not empty: "
                + ", ".join(forbidden_files[:5])
            )

    missing_expected = _coerce_path_list(candidate.get("missing_expected_files"))
    if "missing_expected_files" in candidate:
        if missing_expected is None:
            review_reasons.append("missing_expected_files is not a list")
        elif missing_expected:
            review_reasons.append(
                "missing_expected_files is not empty: "
                + ", ".join(missing_expected[:5])
            )

    patch_kind = candidate.get("patch_kind")
    if "patch_kind" in candidate:
        if not isinstance(patch_kind, str) or not patch_kind.strip():
            review_reasons.append("patch_kind is missing or not a string")
        elif patch_kind.strip().lower() == "unknown":
            review_reasons.append("patch_kind is unknown")

    changed_files = _coerce_path_list(candidate.get("changed_files"))
    if "changed_files" in candidate:
        if changed_files is None:
            review_reasons.append("changed_files is not a list")
        else:
            for path in changed_files:
                path_reason = _blocked_changed_path_reason(path)
                if path_reason:
                    block_reasons.append(path_reason)

    diff_stats = _extract_diff_stats(candidate)
    if _has_diff_stats_field(candidate) and diff_stats is None:
        review_reasons.append("diff stats are present but malformed")
    if diff_stats is not None:
        changed_lines = diff_stats["changed_lines"]
        if changed_lines > MAX_AUTO_DIFF_CHANGED_LINES:
            review_reasons.append(
                f"diff is too large for auto approval: {changed_lines} changed lines"
            )

    if block_reasons:
        promotion = BLOCKED
        reasons.extend(_dedupe(block_reasons + review_reasons))
    elif review_reasons:
        promotion = NEEDS_HUMAN_REVIEW
        reasons.extend(_dedupe(review_reasons))
    else:
        promotion = AUTO_APPROVED
        reasons.append("all auto-approval checks passed")

    return {
        "promotion": promotion,
        "active_knowledge_allowed": promotion == AUTO_APPROVED,
        "score": _score_for_reasons(block_reasons, review_reasons),
        "reasons": reasons,
    }


def _coerce_path_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [str(item) for item in value if str(item).strip()]
    return None


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


def _extract_diff_stats(candidate: Mapping[str, Any]) -> dict[str, int] | None:
    structured = _extract_structured_diff_stats(candidate)
    if structured is not None:
        return structured

    for key in ("diff", "patch_diff"):
        value = candidate.get(key)
        if isinstance(value, str) and value:
            return _count_unified_diff_lines(value)

    diffs = candidate.get("diffs")
    if isinstance(diffs, Sequence) and not isinstance(diffs, (bytes, bytearray, str)):
        text = "\n".join(str(item) for item in diffs if item)
        if text:
            return _count_unified_diff_lines(text)

    return None


def _has_diff_stats_field(candidate: Mapping[str, Any]) -> bool:
    return any(
        key in candidate
        for key in (
            "diff_stats",
            "diff_stat",
            "diffstat",
            "changed_lines",
            "diff_changed_lines",
            "diff_line_count",
            "diff_lines",
            "diff_size",
            "added",
            "additions",
            "lines_added",
            "added_lines",
            "removed",
            "deletions",
            "lines_removed",
            "removed_lines",
        )
    )


def _extract_structured_diff_stats(candidate: Mapping[str, Any]) -> dict[str, int] | None:
    stats_value = None
    for key in ("diff_stats", "diff_stat", "diffstat"):
        value = candidate.get(key)
        if isinstance(value, Mapping):
            stats_value = value
            break

    if stats_value is not None:
        added = _first_int(
            stats_value,
            ("added", "additions", "lines_added", "added_lines"),
        )
        removed = _first_int(
            stats_value,
            ("removed", "deletions", "lines_removed", "removed_lines"),
        )
        changed = _first_int(
            stats_value,
            ("changed", "changed_lines", "line_count", "diff_lines", "total"),
        )
        if added is None and removed is None and changed is None:
            return None
        if changed is None:
            changed = (added or 0) + (removed or 0)
        return {"changed_lines": max(0, changed)}

    changed = _first_int(
        candidate,
        (
            "changed_lines",
            "diff_changed_lines",
            "diff_line_count",
            "diff_lines",
            "diff_size",
        ),
    )
    if changed is not None:
        return {"changed_lines": max(0, changed)}

    added = _first_int(candidate, ("added", "additions", "lines_added", "added_lines"))
    removed = _first_int(
        candidate,
        ("removed", "deletions", "lines_removed", "removed_lines"),
    )
    if added is not None or removed is not None:
        return {"changed_lines": max(0, (added or 0) + (removed or 0))}

    return None


def _first_int(data: Mapping[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                continue
    return None


def _count_unified_diff_lines(diff_text: str) -> dict[str, int]:
    changed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed += 1
    return {"changed_lines": changed}


def _score_for_reasons(block_reasons: list[str], review_reasons: list[str]) -> float:
    score = 1.0
    score -= 0.45 * len(block_reasons)
    score -= 0.2 * len(review_reasons)
    return round(max(0.0, min(1.0, score)), 3)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
