"""Phase 11.b - two-language invariant verification reports.

Evidence-only normalization of already-existing patch/proposal/validation
artifacts. This module does not run validation, benchmarks, models, patching,
lessons, Reverse Dream, mutation oracle, Docker, subprocesses, or network calls.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REPORT_TITLE = "Patch Invariant Verification"
GUARDRAIL_NOTE = (
    "This report is evidence-only. It does not modify patches, prompts, "
    "lessons, benchmarks, or validation behavior."
)

SUPPORTED = "supported"
WEAKLY_SUPPORTED = "weakly_supported"
UNSUPPORTED = "unsupported"
UNKNOWN = "unknown"

_NO_BEHAVIOR_CHANGE_MARKERS = (
    "no behavior change",
    "does not change behavior",
    "doesn't change behavior",
    "behavior unchanged",
    "unchanged behavior",
)
_FIX_MARKERS = ("fix", "bug", "correct", "repair", "resolve")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _get_string(record: dict[str, Any], key: str) -> str:
    value = _clean_string(record.get(key))
    if value is not None:
        return value
    evidence = _as_mapping(record.get("evidence"))
    value = _clean_string(evidence.get(key))
    return value or ""


def _get_any(record: dict[str, Any], key: str) -> Any:
    if key in record:
        return record.get(key)
    evidence = _as_mapping(record.get("evidence"))
    return evidence.get(key)


def _unique_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text and text not in out:
                out.append(text)
    return sorted(out)


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _excerpt(value: str, *, limit: int = 1000) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _first_string(*values: Any) -> str | None:
    for value in values:
        text = _clean_string(value)
        if text is not None:
            return text
    return None


def infer_basic_invariants(record: dict[str, Any]) -> dict[str, str]:
    """Return explicit invariant text when present, else conservative unknowns.

    The helper intentionally does not invent a behavioral claim. It accepts a
    root-level shape and a nested ``invariants`` shape so benchmark, proposal,
    replay, and validation artifacts can all feed the same report builder.
    """
    nested = _as_mapping(record.get("invariants"))
    code = _first_string(
        record.get("code_invariant"),
        nested.get("code"),
        nested.get("code_invariant"),
    )
    plain = _first_string(
        record.get("plain_english_invariant"),
        nested.get("plain_english"),
        nested.get("plain_english_invariant"),
        nested.get("english"),
    )
    return {
        "code_invariant": code or UNKNOWN,
        "plain_english_invariant": plain or UNKNOWN,
    }


def _source_ref(record: dict[str, Any]) -> str:
    return _first_string(
        record.get("source_ref"),
        record.get("filename"),
        record.get("case_file"),
        record.get("path"),
        record.get("name"),
        record.get("id"),
    ) or UNKNOWN


def _evidence(record: dict[str, Any]) -> dict[str, Any]:
    validation_output = _get_string(record, "validation_output")
    if not validation_output:
        validation_output = _get_string(record, "validation_output_excerpt")
    touched_forbidden = _unique_strings(_get_any(record, "touched_forbidden_files"))
    if not touched_forbidden:
        touched_forbidden = _unique_strings(_get_any(record, "forbidden_touched_files"))
    return {
        "changed_files": _unique_strings(_get_any(record, "changed_files")),
        "patched_files": _unique_strings(_get_any(record, "patched_files")),
        "touched_forbidden_files": touched_forbidden,
        "unexpected_mutations": _unique_strings(_get_any(record, "unexpected_mutations")),
        "validation_command": _get_string(record, "validation_command"),
        "validation_ok": _bool_or_none(_get_any(record, "validation_ok")),
        "validation_output_excerpt": _excerpt(validation_output) if validation_output else "",
        "patch_summary": _get_string(record, "patch_summary"),
    }


def _obvious_contradiction(
    code_invariant: str,
    plain_english_invariant: str,
    evidence: dict[str, Any],
) -> bool:
    text = f"{code_invariant}\n{plain_english_invariant}".lower()
    says_no_behavior_change = any(marker in text for marker in _NO_BEHAVIOR_CHANGE_MARKERS)
    if not says_no_behavior_change:
        return False

    patch_summary = str(evidence.get("patch_summary") or "").lower()
    changed_files = bool(evidence.get("changed_files"))
    validation_ok = evidence.get("validation_ok") is True
    summary_says_fix = any(marker in patch_summary for marker in _FIX_MARKERS)
    return changed_files or validation_ok or summary_says_fix


def _verdict_and_reasons(
    code_invariant: str,
    plain_english_invariant: str,
    evidence: dict[str, Any],
) -> tuple[str, list[str]]:
    if code_invariant == UNKNOWN and plain_english_invariant == UNKNOWN:
        return UNKNOWN, ["No explicit invariant was provided."]
    if code_invariant == UNKNOWN or plain_english_invariant == UNKNOWN:
        return UNKNOWN, ["Both code and plain-English invariants are required."]

    reasons: list[str] = []
    if _obvious_contradiction(code_invariant, plain_english_invariant, evidence):
        reasons.append("Invariant text contradicts local evidence about a behavior-changing fix.")

    validation_ok = evidence.get("validation_ok")
    if validation_ok is False:
        reasons.append("validation failed, so the invariant is not supported by the artifact.")

    if evidence.get("touched_forbidden_files"):
        reasons.append("forbidden files were touched in the artifact.")
    if evidence.get("unexpected_mutations"):
        reasons.append("unexpected mutations are present in the artifact.")

    if reasons:
        return UNSUPPORTED, reasons

    if validation_ok is None:
        return UNKNOWN, ["validation status is unknown."]

    weak_reasons: list[str] = []
    if not evidence.get("validation_output_excerpt"):
        weak_reasons.append("validation output is missing.")
    if not evidence.get("changed_files"):
        weak_reasons.append("changed-file evidence is missing.")
    if not evidence.get("patch_summary"):
        weak_reasons.append("patch summary is missing.")

    if weak_reasons:
        return WEAKLY_SUPPORTED, weak_reasons

    return SUPPORTED, [
        "validation succeeded and both invariant forms are backed by local patch evidence."
    ]


def build_invariant_verification(
    record: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic evidence-only invariant verification report."""
    if not isinstance(record, dict):
        record = {}
    invariant_text = infer_basic_invariants(record)
    evidence = _evidence(record)
    verdict, reasons = _verdict_and_reasons(
        invariant_text["code_invariant"],
        invariant_text["plain_english_invariant"],
        evidence,
    )
    return {
        "title": REPORT_TITLE,
        "generated_at": generated_at or _now_iso(),
        "source_ref": _source_ref(record),
        "code_invariant": invariant_text["code_invariant"],
        "plain_english_invariant": invariant_text["plain_english_invariant"],
        "evidence": evidence,
        "verdict": verdict,
        "reasons": reasons,
        "guardrail": GUARDRAIL_NOTE,
    }


def _md_list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def _md_bool(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def format_invariant_verification_markdown(report: dict[str, Any]) -> str:
    """Format an invariant verification report as evidence-only Markdown."""
    evidence = _as_mapping(report.get("evidence"))
    reasons = _unique_strings(report.get("reasons"))
    lines = [
        f"# {report.get('title') or REPORT_TITLE}",
        "",
        f"- Generated at: {report.get('generated_at') or UNKNOWN}",
        f"- Source: {report.get('source_ref') or UNKNOWN}",
        f"- Verdict: {report.get('verdict') or UNKNOWN}",
        "",
        "## Code Invariant",
        "",
        str(report.get("code_invariant") or UNKNOWN),
        "",
        "## Plain-English Invariant",
        "",
        str(report.get("plain_english_invariant") or UNKNOWN),
        "",
        "## Reasons",
        "",
    ]
    if reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Changed files: {_md_list(_unique_strings(evidence.get('changed_files')))}",
            f"- Patched files: {_md_list(_unique_strings(evidence.get('patched_files')))}",
            (
                "- Touched forbidden files: "
                f"{_md_list(_unique_strings(evidence.get('touched_forbidden_files')))}"
            ),
            (
                "- Unexpected mutations: "
                f"{_md_list(_unique_strings(evidence.get('unexpected_mutations')))}"
            ),
            f"- Validation command: {evidence.get('validation_command') or 'none'}",
            f"- Validation ok: {_md_bool(evidence.get('validation_ok'))}",
            f"- Patch summary: {evidence.get('patch_summary') or 'none'}",
            "",
            "### Validation Output Excerpt",
            "",
            str(evidence.get("validation_output_excerpt") or "none"),
            "",
            "## Guardrail",
            "",
            str(report.get("guardrail") or GUARDRAIL_NOTE),
        ]
    )
    return "\n".join(lines) + "\n"
