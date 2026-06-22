"""ROAD.1 — Machine-Readable Phase Registry (report-only).

Defines, validates, and summarizes roadmap phase metadata so future phases can be
inspected, filtered, and (later, by a separate phase) selected safely. ROAD.1 is
the metadata layer only: it gives every roadmap phase a structured record with an
automation level, a budget tier, a risk level, an allow/forbid file scope, and a
set of guardrail booleans.

Core principle: ROAD.1 defines and validates roadmap phase metadata. It does not
choose work, execute phases, run validation or a benchmark check, call models,
apply patches, write to the real repo, push, merge, open PRs, or contact a remote
git host / chat service / external automation. Validation commands are stored as
opaque text only; ROAD.1 never runs them.

This module is stdlib-only and pure. ``load_phase_registry`` reads a JSON file and
``write_phase_registry_report`` writes the report artifacts, but the analysis
functions (``validate_phase_registry`` / ``summarize_phase_registry`` /
``render_phase_registry_markdown``) never read, write, mutate, or run anything.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "phase_registry_report"

SCHEMA_VERSION = "1.0"

#: Allowed phase ``status`` values.
STATUSES: tuple[str, ...] = ("proposed", "active", "complete", "parked", "deferred")

#: Statuses that count as live implementation work (subject to the stricter
#: "must declare files and validation" rules).
IMPLEMENTATION_STATUSES: tuple[str, ...] = ("proposed", "active")

#: Statuses that represent shipped history (the only ones that may carry real
#: repo write authority or waive the human-approval gate).
HISTORY_STATUSES: tuple[str, ...] = ("complete",)

#: Allowed automation levels, lowest to highest power.
AUTOMATION_LEVELS: tuple[str, ...] = (
    "LOCAL_0_OBSERVE",
    "LOCAL_1_PREPARE",
    "SANDBOX_2_DRAFT_PATCH",
    "REMOTE_3_DRAFT_PR",
    "AUTO_4_AUTO_MERGE",
)

#: The automation level that ROAD.1 rejects outright for now.
FORBIDDEN_AUTOMATION_LEVEL = "AUTO_4_AUTO_MERGE"

#: Allowed budget tiers.
BUDGET_TIERS: tuple[str, ...] = (
    "local_only",
    "cheap_api_allowed",
    "strong_model_requires_approval",
    "blocked",
)

#: The only budget tier under which a phase may declare it would call a model.
MODEL_BUDGET_TIER = "strong_model_requires_approval"

#: Allowed risk levels.
RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "blocked")

#: Accepted phase-id prefixes (the token before the first dot).
PHASE_ID_PREFIXES: tuple[str, ...] = ("ROAD", "AUTO", "MODEL", "EVAL", "CMD", "A", "GOV", "F", "H")

#: Registry-root fields that must be present.
REQUIRED_ROOT_FIELDS: tuple[str, ...] = ("schema_version", "updated_at", "phases")

#: Per-phase fields that must be present.
REQUIRED_PHASE_FIELDS: tuple[str, ...] = (
    "phase_id",
    "title",
    "track",
    "status",
    "summary",
    "automation_level",
    "budget_tier",
    "risk_level",
    "allowed_files",
    "forbidden_files",
    "validation",
    "human_approval_required",
    "merge_allowed",
    "network_allowed",
    "model_calls_allowed",
    "writes_real_repo",
    "requires_sandbox",
)

#: List-typed phase fields whose entries must all be strings.
_STRING_LIST_FIELDS: tuple[str, ...] = ("allowed_files", "forbidden_files", "validation")

#: Boolean-typed phase fields.
_BOOL_FIELDS: tuple[str, ...] = (
    "human_approval_required",
    "merge_allowed",
    "network_allowed",
    "model_calls_allowed",
    "writes_real_repo",
    "requires_sandbox",
)

#: forbidden_files must always include at least these protected entries.
REQUIRED_FORBIDDEN_FILES: tuple[str, ...] = (".env", ".git", ".agent/private")

#: Report artifact filenames.
JSON_NAME = "phase_registry_report.json"
MD_NAME = "phase_registry_report.md"

PHASE_REGISTRY_GUARDRAIL_NOTE = (
    "Machine-Readable Phase Registry is report-only: it defines, validates, and "
    "summarizes roadmap phase metadata. It does not choose work, execute phases, "
    "run validation or a benchmark check, call models, apply patches, write to the "
    "real repo, push, merge, open PRs, or contact a remote git host, chat app, or "
    "external automation. Validation commands are stored as text only; ROAD.1 never "
    "runs them. Human approval is required before any phase is acted on."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _phase_label(phase: Any, index: int) -> str:
    if isinstance(phase, dict):
        pid = str(phase.get("phase_id", "")).strip()
        if pid:
            return pid
    return f"#{index}"


def _natural_tokens(text: str) -> tuple[tuple[int, int, str], ...]:
    """Split a string into comparable digit / non-digit chunks for natural sort.

    ``"AUTO.10b"`` -> alternating runs so ``A.2`` sorts before ``A.10``. Each run
    becomes ``(is_number, number_value, lowercased_text)`` so numbers and text
    stay comparable across entries.
    """
    tokens: list[tuple[int, int, str]] = []
    run = ""
    run_is_digit: bool | None = None
    for ch in str(text):
        is_digit = ch.isdigit()
        if run_is_digit is None or is_digit == run_is_digit:
            run += ch
            run_is_digit = is_digit
            continue
        tokens.append((1, int(run), "") if run_is_digit else (0, 0, run.lower()))
        run = ch
        run_is_digit = is_digit
    if run:
        tokens.append((1, int(run), "") if run_is_digit else (0, 0, run.lower()))
    return tuple(tokens)


def _phase_sort_key(phase: dict[str, Any]) -> tuple[Any, ...]:
    track = str(phase.get("track", ""))
    phase_id = str(phase.get("phase_id", ""))
    return (track, _natural_tokens(phase_id), phase_id)


def phase_id_prefix(phase_id: Any) -> str:
    """Return the prefix before the first dot of a phase id (or ``""``)."""
    raw = str(phase_id or "")
    return raw.split(".", 1)[0] if "." in raw else ""


def _is_history(status: Any) -> bool:
    return str(status) in HISTORY_STATUSES


# ── Loading ───────────────────────────────────────────────────────────────────

def load_phase_registry(path: str | Path) -> Any:
    """Read and parse a registry JSON file. Returns the parsed object.

    Raises ``OSError`` if the file cannot be read and ``ValueError`` if it is not
    valid JSON. This only reads the file — it never runs or contacts anything.
    """
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


# ── Validation ────────────────────────────────────────────────────────────────

def _validate_phase(
    phase: Any,
    index: int,
    seen_ids: dict[str, int],
    errors: list[str],
    warnings: list[str],
) -> None:
    label = _phase_label(phase, index)
    if not isinstance(phase, dict):
        errors.append(f"phase {label} is not a JSON object")
        return

    # Required fields present.
    for field in REQUIRED_PHASE_FIELDS:
        if field not in phase:
            errors.append(f"phase {label} is missing required field: {field}")

    # Uniqueness.
    pid = str(phase.get("phase_id", "")).strip()
    if pid:
        if pid in seen_ids:
            errors.append(f"phase {label} has a duplicate phase id: {pid}")
        seen_ids[pid] = seen_ids.get(pid, 0) + 1
        prefix = phase_id_prefix(pid)
        if prefix not in PHASE_ID_PREFIXES:
            warnings.append(
                f"phase {pid} has an unrecognized phase-id prefix "
                f"(expected one of {', '.join(PHASE_ID_PREFIXES)})"
            )

    status = phase.get("status")
    # Enum checks (only when the field is present).
    for field, allowed in (
        ("status", STATUSES),
        ("automation_level", AUTOMATION_LEVELS),
        ("budget_tier", BUDGET_TIERS),
        ("risk_level", RISK_LEVELS),
    ):
        if field in phase and phase.get(field) not in allowed:
            errors.append(
                f"phase {label} has an invalid {field}: {phase.get(field)!r} "
                f"(allowed: {', '.join(allowed)})"
            )

    # Type checks for list / boolean fields.
    for field in _STRING_LIST_FIELDS:
        value = phase.get(field)
        if field in phase:
            if not isinstance(value, list):
                errors.append(f"phase {label} field {field} must be a list")
            elif field == "validation" and not all(isinstance(item, str) for item in value):
                errors.append(f"phase {label} validation commands must be text (string) values")
    for field in _BOOL_FIELDS:
        if field in phase and not isinstance(phase.get(field), bool):
            errors.append(f"phase {label} field {field} must be a boolean")

    # Rule: AUTO_4_AUTO_MERGE is rejected for now.
    if phase.get("automation_level") == FORBIDDEN_AUTOMATION_LEVEL:
        errors.append(
            f"phase {label} uses automation_level {FORBIDDEN_AUTOMATION_LEVEL}, "
            "which is not allowed yet"
        )

    # Rule: merge_allowed must be false for now.
    if phase.get("merge_allowed") is True:
        errors.append(f"phase {label} sets merge_allowed=true, which is not allowed yet")

    # Rule: non-complete phases must keep the human-approval gate.
    if phase.get("human_approval_required") is False and not _is_history(status):
        errors.append(
            f"phase {label} sets human_approval_required=false but is not a complete phase"
        )

    # Rule: network access is rejected (strict for ROAD.1).
    if phase.get("network_allowed") is True:
        errors.append(
            f"phase {label} sets network_allowed=true, which is not allowed for "
            "ROAD.1-managed phases"
        )

    # Rule: model calls only under the approval budget tier.
    if phase.get("model_calls_allowed") is True and phase.get("budget_tier") != MODEL_BUDGET_TIER:
        errors.append(
            f"phase {label} sets model_calls_allowed=true but budget_tier is not "
            f"{MODEL_BUDGET_TIER}"
        )

    # Rule: only complete/history phases may carry real repo write authority.
    if phase.get("writes_real_repo") is True and not _is_history(status):
        errors.append(
            f"phase {label} sets writes_real_repo=true but is not a complete phase"
        )

    # Rule: active/proposed implementation phases must declare files + validation.
    if status in IMPLEMENTATION_STATUSES:
        allowed_files = phase.get("allowed_files")
        validation = phase.get("validation")
        if isinstance(allowed_files, list) and not allowed_files:
            errors.append(
                f"phase {label} has empty allowed_files but is an active/proposed phase"
            )
        if isinstance(validation, list) and not validation:
            errors.append(
                f"phase {label} has empty validation but is an active/proposed phase"
            )

    # Rule: forbidden_files must include the protected entries.
    forbidden = phase.get("forbidden_files")
    if isinstance(forbidden, list):
        for required in REQUIRED_FORBIDDEN_FILES:
            if required not in forbidden:
                errors.append(
                    f"phase {label} forbidden_files must include {required}"
                )


def validate_phase_registry(data: Any) -> dict[str, Any]:
    """Validate a parsed registry. Returns ``{errors, warnings, is_valid}``.

    Pure: it reads the data, never mutates it, and never runs anything. Errors
    and warnings are returned sorted for deterministic output.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {"errors": ["registry root must be a JSON object"], "warnings": [], "is_valid": False}

    for field in REQUIRED_ROOT_FIELDS:
        if field not in data:
            errors.append(f"registry is missing required root field: {field}")

    phases = data.get("phases")
    if "phases" in data and not isinstance(phases, list):
        errors.append("registry field 'phases' must be a list")
        phases = None

    known_ids: set[str] = set()
    if isinstance(phases, list):
        for phase in phases:
            if isinstance(phase, dict):
                pid = str(phase.get("phase_id", "")).strip()
                if pid:
                    known_ids.add(pid)

        seen_ids: dict[str, int] = {}
        for index, phase in enumerate(phases):
            _validate_phase(phase, index, seen_ids, errors, warnings)
            if isinstance(phase, dict):
                label = _phase_label(phase, index)
                for prereq in phase.get("prerequisites") or []:
                    if str(prereq) not in known_ids:
                        warnings.append(
                            f"phase {label} lists prerequisite {prereq} which is not in the registry"
                        )

    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    return {"errors": errors, "warnings": warnings, "is_valid": not errors}


# ── Summary ───────────────────────────────────────────────────────────────────

def _count_by(phases: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for phase in phases:
        value = phase.get(field)
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _boundaries() -> dict[str, bool]:
    return {
        "chooses_work": False,
        "executes_phases": False,
        "runs_validation_or_benchmarks": False,
        "calls_models": False,
        "applies_patches": False,
        "modifies_real_repo": False,
        "pushes_merges_or_opens_pr": False,
        "contacts_remote_or_chat_or_automation": False,
    }


def _phase_view(phase: dict[str, Any]) -> dict[str, Any]:
    """A read-only, normalized view of a phase for the report (input untouched)."""
    view = dict(phase)
    view["allowed_files_count"] = len(phase.get("allowed_files") or [])
    view["forbidden_files_count"] = len(phase.get("forbidden_files") or [])
    view["validation_count"] = len(phase.get("validation") or [])
    return view


def summarize_phase_registry(
    data: Any,
    *,
    report_id: str = "",
    created_at: str = "",
    registry_path: str = "",
) -> dict[str, Any]:
    """Validate and summarize a registry into a deterministic report record.

    Pure: never mutates ``data`` and never runs anything. Phases are sorted by
    track then natural phase id; counts and validation results are included.
    """
    validation = validate_phase_registry(data)
    root = data if isinstance(data, dict) else {}
    raw_phases = root.get("phases")
    phase_dicts = [p for p in raw_phases if isinstance(p, dict)] if isinstance(raw_phases, list) else []
    ordered = sorted(phase_dicts, key=_phase_sort_key)

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": PHASE_REGISTRY_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "schema_version": str(root.get("schema_version", "")),
        "updated_at": str(root.get("updated_at", "")),
        "registry_path": str(registry_path or ""),
        "phase_count": len(phase_dicts),
        "counts_by_track": _count_by(phase_dicts, "track"),
        "counts_by_status": _count_by(phase_dicts, "status"),
        "counts_by_automation_level": _count_by(phase_dicts, "automation_level"),
        "errors": list(validation["errors"]),
        "warnings": list(validation["warnings"]),
        "is_valid": bool(validation["is_valid"]),
        "phases": [_phase_view(p) for p in ordered],
        "boundaries": _boundaries(),
        # ── ROAD.1 guardrail booleans (this tool does none of these) ──
        "human_approval_required": True,
        "executes_phases": False,
        "runs_validation_or_benchmarks": False,
        "model_call_performed": False,
        "applies_patches": False,
        "writes_real_repo": False,
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def _render_counts(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines += [f"## {title}", ""]
    if counts:
        lines += ["| Key | Count |", "|---|---|"]
        for key in counts:
            lines.append(f"| {_md(key)} | {counts[key]} |")
    else:
        lines.append("_None._")
    lines.append("")


def render_phase_registry_markdown(summary: dict[str, Any]) -> str:
    """Render a summary record as one operator-readable Markdown report."""
    lines: list[str] = [
        "# Machine-Readable Phase Registry Report",
        "",
        f"> {summary.get('guardrail_note', PHASE_REGISTRY_GUARDRAIL_NOTE)}",
        "",
        "_Report only: ROAD.1 defines, validates, and summarizes roadmap phase "
        "metadata. It chooses no work, runs nothing, and changes nothing in the real "
        "repo. Validation commands are stored as text only; ROAD.1 never runs them._",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]
    lines.append(f"- **Report id:** `{_md(summary.get('report_id') or '(none)')}`")
    lines.append(f"- **Created at:** `{_md(summary.get('created_at') or '(none)')}`")
    lines.append(f"- **Schema version:** `{_md(summary.get('schema_version') or '(none)')}`")
    lines.append(f"- **Registry path:** `{_md(summary.get('registry_path') or '(inline)')}`")
    lines.append(f"- **Phase count:** {summary.get('phase_count', 0)}")
    is_valid = bool(summary.get("is_valid"))
    lines.append(f"- **Valid:** {'VALID' if is_valid else 'INVALID'}")
    lines.append("")

    _render_counts(lines, "Counts by track", summary.get("counts_by_track") or {})
    _render_counts(lines, "Counts by status", summary.get("counts_by_status") or {})
    _render_counts(lines, "Counts by automation level", summary.get("counts_by_automation_level") or {})

    # Validation result
    errors = summary.get("errors") or []
    warnings = summary.get("warnings") or []
    lines += ["## Validation result", ""]
    lines.append(f"- **Result:** {'VALID' if is_valid else 'INVALID'}")
    lines.append(f"- **Errors:** {len(errors)}")
    lines.append(f"- **Warnings:** {len(warnings)}")
    lines.append("")

    # Errors
    lines += ["## Errors", ""]
    if errors:
        for error in errors:
            lines.append(f"- {_md(error)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Phase table
    lines += ["## Phase Table", ""]
    phases = summary.get("phases") or []
    if phases:
        lines += [
            "| Phase | Title | Track | Status | Automation level | Budget | Risk | Human approval |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for phase in phases:
            lines.append(
                "| {pid} | {title} | {track} | {status} | {auto} | {budget} | {risk} | {appr} |".format(
                    pid=_md(phase.get("phase_id", "")),
                    title=_md(phase.get("title", "")),
                    track=_md(phase.get("track", "")),
                    status=_md(phase.get("status", "")),
                    auto=_md(phase.get("automation_level", "")),
                    budget=_md(phase.get("budget_tier", "")),
                    risk=_md(phase.get("risk_level", "")),
                    appr=str(phase.get("human_approval_required", "")).lower(),
                )
            )
    else:
        lines.append("_No phases._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- ROAD.1 does not execute phases.",
        "- ROAD.1 does not run validation or benchmarks.",
        "- ROAD.1 does not call models.",
        "- ROAD.1 does not apply patches.",
        "- ROAD.1 does not push, merge, open PRs, or contact GitHub, Telegram, or N8N "
        "/ external automation.",
        "- ROAD.1 only validates and summarizes roadmap metadata.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Report writing ────────────────────────────────────────────────────────────

def write_phase_registry_report(
    data: Any,
    output_dir: str | Path,
    report_id: str = "",
    created_at: str = "",
    *,
    registry_path: str = "",
) -> dict[str, Any]:
    """Summarize the registry and write the JSON + Markdown report artifacts.

    Returns ``{ok, json_path, md_path, report}``. The report content is the same
    deterministic record ``summarize_phase_registry`` returns; nothing is run.
    """
    report = summarize_phase_registry(
        data, report_id=report_id, created_at=created_at, registry_path=registry_path
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_phase_registry_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
