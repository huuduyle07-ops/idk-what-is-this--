"""Phase 14.6 — deterministic failure_category mapper for benchmark case records.

Adds four display-only metadata fields to a failing case dict:
  failure_category            one of FAILURE_CATEGORIES
  failure_category_confidence "high", "medium", "low", or "none"
  failure_category_rule       rule name that fired (or "no_rule_matched")
  failure_category_reason     human-readable explanation

Does NOT change scoring, pass/fail logic, patch behavior, retrieval,
lessons, anti-lessons, Dream, Project Evolution, model prompts, or routing.
Imports only stdlib modules.
"""
from __future__ import annotations

from typing import Any

FAILURE_CATEGORIES: tuple[str, ...] = (
    "toolchain_environment",
    "security_tool_or_permission",
    "validation_command_gap",
    "wrong_file_or_decoy",
    "forbidden_file_or_scope_violation",
    "missing_import_or_dependency",
    "async_or_lifecycle_bug",
    "state_mutation_or_side_effect",
    "data_validation_or_boundary",
    "root_cause_multifile",
    "false_positive_no_patch",
    "insufficient_evidence",
    "unknown",
)

FAILURE_CATEGORY_GUARDRAIL_NOTE: str = (
    "failure_category is a read-only observational field added after "
    "scoring is settled. It does not affect pass/fail, retries, patch "
    "generation, patch safety, validation, retrieval, lessons, or routing."
)

_BENCH_CATEGORY_TO_FAILURE_CATEGORY: dict[str, str] = {
    "async_error": "async_or_lifecycle_bug",
    "side_effect": "state_mutation_or_side_effect",
    "missing_import": "missing_import_or_dependency",
    "logic_validation": "data_validation_or_boundary",
    "boundary_logic": "data_validation_or_boundary",
    "multi_file_root_cause": "root_cause_multifile",
}

_ACCESS_DENIED_MARKERS: tuple[str, ...] = (
    "access is denied",
    "access denied",
    "permission denied",
)
_ANTIVIRUS_MARKERS: tuple[str, ...] = (
    "antivirus",
    "blocked the execution",
    "quarantined",
)
_TOOLCHAIN_MARKERS: tuple[str, ...] = (
    "command not found",
    "not found in path",
    "no such file or directory",
    "is not recognized as an internal or external command",
    "cannot find the file",
)


def _lower_str(v: Any) -> str:
    return v.lower() if isinstance(v, str) else ""


def _extract_text_signals(case: dict[str, Any]) -> str:
    parts: list[str] = []
    val_out = case.get("validation_output")
    if isinstance(val_out, str):
        parts.append(val_out.lower())
    val_sum = case.get("validation_summary")
    if isinstance(val_sum, dict):
        tail = val_sum.get("agent_validation_tail")
        if isinstance(tail, str):
            parts.append(tail.lower())
    return " ".join(parts)


def _result(
    category: str,
    confidence: str,
    rule: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "failure_category": category,
        "failure_category_confidence": confidence,
        "failure_category_rule": rule,
        "failure_category_reason": reason,
    }


def derive_failure_category(case_record: dict[str, Any]) -> dict[str, Any]:
    """Return failure_category metadata for a failing benchmark case.

    Priority-ordered rules; first match wins. The returned dict contains
    failure_category, failure_category_confidence, failure_category_rule,
    and failure_category_reason.
    """
    failure_kind = _lower_str(case_record.get("failure_kind"))
    bench_cat = _lower_str(case_record.get("category"))
    text_signals = _extract_text_signals(case_record)

    # Rule 1: explicit failure_kind == "security_tool"
    if failure_kind == "security_tool":
        return _result(
            "security_tool_or_permission", "high",
            "failure_kind_security_tool",
            "failure_kind field is security_tool",
        )

    # Rule 2: access-denied or antivirus signal in validation text
    for marker in _ACCESS_DENIED_MARKERS:
        if marker in text_signals:
            return _result(
                "security_tool_or_permission", "high",
                "access_denied_or_antivirus_signal",
                f"validation text contains {marker!r}",
            )
    for marker in _ANTIVIRUS_MARKERS:
        if marker in text_signals:
            return _result(
                "security_tool_or_permission", "high",
                "access_denied_or_antivirus_signal",
                f"validation text contains antivirus marker {marker!r}",
            )

    # Rule 3: toolchain / environment failure_kind
    if failure_kind in ("toolchain", "environment"):
        return _result(
            "toolchain_environment", "medium",
            "failure_kind_toolchain_or_environment",
            f"failure_kind field is {failure_kind!r}",
        )

    # Rule 4: compiler/tool not found in validation text
    for marker in _TOOLCHAIN_MARKERS:
        if marker in text_signals:
            return _result(
                "toolchain_environment", "high",
                "compiler_or_tool_not_found",
                f"validation text contains {marker!r}",
            )

    # Rule 5: no-patch expected flag
    if case_record.get("expects_patch") is False or case_record.get("no_patch_expected") is True:
        return _result(
            "false_positive_no_patch", "high",
            "no_patch_expected_flag",
            "case marked as expects_patch=False or no_patch_expected=True",
        )

    # Rule 6: touched forbidden files
    forbidden = case_record.get("touched_forbidden_files")
    if isinstance(forbidden, list) and len(forbidden) > 0:
        return _result(
            "forbidden_file_or_scope_violation", "high",
            "touched_forbidden_files",
            f"touched {len(forbidden)} forbidden file(s)",
        )

    # Rule 7: changed files disjoint from expected
    changed = case_record.get("changed_files")
    expected = case_record.get("expected_changed_files")
    if (
        isinstance(changed, list)
        and isinstance(expected, list)
        and len(changed) > 0
        and len(expected) > 0
        and not set(changed).intersection(set(expected))
    ):
        return _result(
            "wrong_file_or_decoy", "high",
            "changed_files_disjoint_from_expected",
            "changed_files and expected_changed_files share no files",
        )

    # Rule 8: benchmark category mapping
    if bench_cat in _BENCH_CATEGORY_TO_FAILURE_CATEGORY:
        mapped = _BENCH_CATEGORY_TO_FAILURE_CATEGORY[bench_cat]
        return _result(
            mapped, "high",
            "benchmark_category_mapping",
            f"benchmark category {bench_cat!r} maps to {mapped!r}",
        )

    # Rule 9: failure_kind code_unknown → insufficient evidence
    if failure_kind == "code_unknown":
        return _result(
            "insufficient_evidence", "low",
            "failure_kind_code_unknown",
            "failure_kind is code_unknown; no further signal available",
        )

    # Fallthrough: unknown
    return _result(
        "unknown", "none",
        "no_rule_matched",
        "no classification rule matched",
    )
