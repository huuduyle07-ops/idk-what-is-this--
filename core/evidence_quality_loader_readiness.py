"""EVAL.N7 - Evidence Quality Loader Readiness Check.

Inspects the EVAL.N5 read-only Evidence Quality panel, the EVAL.N6 GET-only
loader source, and an optional existing EVAL.N3 report artifact. This module is
report-only: it writes readiness artifacts only and does not generate evidence
quality reports, run validation or benchmarks, call models, apply patches,
approve/reject work, mutate reports, or alter Submit/Apply behavior.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "evidence_quality_loader_readiness"
JSON_NAME = "evidence_quality_loader_readiness.json"
MD_NAME = "evidence_quality_loader_readiness.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_loader_readiness"

READY = "loader_readiness_ready"
READY_WITH_WARNINGS = "loader_readiness_ready_with_warnings"
INCOMPLETE = "loader_readiness_incomplete"
BLOCKED = "loader_readiness_blocked"

ADVISORY_NOTE = "Evidence Quality is advisory evidence, not an approval gate."
EMPTY_STATE = "No evidence quality report loaded."
ALLOWED_REPORT_ROOT = ".agent/eval/evidence_quality_report/"

VISIBLE_FIELDS: tuple[str, ...] = (
    "Evidence quality status",
    "Overall evidence quality",
    "Claim count",
    "Missing evidence count",
    "Contradiction risk count",
    "Confidence alignment warnings",
    "Validation evidence status",
    "Benchmark evidence status",
    "Freshness status",
    "Recommended human checks",
)

FORBIDDEN_PANEL_CONTROLS: tuple[str, ...] = (
    "Approve",
    "Reject",
    "Apply",
    "Run Validation",
    "Run Benchmark",
    "Score Now",
    "Generate Report",
)

REPORT_GENERATION_MARKERS: tuple[str, ...] = (
    "evidence_quality_report_builder",
    "create_evidence_quality_report",
    "build_evidence_quality_report",
    "write_evidence_quality_report",
)

VALIDATION_MARKERS: tuple[str, ...] = (
    "run_safe_validation",
    "run_validation",
    "SafeValidationCommand",
    "/proposals/validate",
)

BENCHMARK_MARKERS: tuple[str, ...] = (
    "run_benchmarks",
    "/benchmarks/run",
)

MODEL_MARKERS: tuple[str, ...] = (
    "run_gemini_request",
    "run_deepseek_review",
    "openai",
    "anthropic",
    "litellm",
    "callModel",
)

MUTATION_MARKERS: tuple[str, ...] = (
    ".write_text(",
    ".mkdir(",
    "request.values",
    "request.form",
    "repo_path",
    "apply_patch",
    "generate_patch",
    "database",
    "requests.",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "report_generation_performed",
    "model_call_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "auth_policy_changed",
    "scoring_gate_changed",
    "approval_or_rejection_performed",
    "apply_submit_blocking_performed",
    "evidence_report_mutated",
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "readiness check only",
    "no report generation",
    "no model call",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP invocation",
    "no worker launch",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no auth policy change",
    "no scoring gate change",
    "no approval/rejection",
    "no Apply/Submit blocking",
    "no evidence report mutation",
    "writes readiness artifacts only",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.CLOSE",
    "title": "Evidence Quality Branch Checkpoint",
    "reason": "Freeze the report-only Evidence Quality branch after the UI and loader readiness checkpoint.",
}

GUARDRAIL_NOTE = (
    "Evidence Quality Loader Readiness Check is report-only: it inspects source "
    "and optional existing artifacts to verify the EVAL.N5/EVAL.N6 UI and loader "
    "chain remains safe, read-only, non-blocking, and compatible with EVAL.N3 "
    "reports. It writes readiness artifacts only."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", str(exc)


def _between(text: str, start: str, end: str) -> str:
    try:
        start_index = text.index(start)
        end_index = text.index(end, start_index)
    except ValueError:
        return ""
    return text[start_index:end_index]


def _check(checks: list[dict[str, str]], check_id: str, status: str, message: str) -> None:
    checks.append({"check_id": check_id, "status": status, "message": message})


def _block(blocked: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in blocked):
        blocked.append({"reason": reason, "message": message})


def _button_labels(panel_source: str) -> list[str]:
    labels: list[str] = []
    for raw in re.findall(r"<button\b[^>]*>(.*?)</button>", panel_source, flags=re.I | re.S):
        label = re.sub(r"<[^>]+>", " ", raw)
        label = re.sub(r"\s+", " ", label).strip()
        if label:
            labels.append(label)
    return labels


def _contains_panel(template_source: str, containing_marker: str, closing_marker: str) -> bool:
    segment = _between(template_source, containing_marker, closing_marker)
    return "evidenceQualityPanel" in segment


def _panel_readiness(
    template_source: str,
    template_error: str,
    source_checks: list[dict[str, str]],
    blocked: list[dict[str, str]],
    incomplete: list[str],
) -> dict[str, Any]:
    panel_source = _between(template_source, 'id="evidenceQualityPanel"', "<!-- /evidence-quality-panel -->")
    if template_error:
        _check(source_checks, "panel_source_readable", "missing", f"Template could not be read: {template_error}")
        incomplete.append("Evidence Quality panel source unreadable")
    else:
        _check(source_checks, "panel_source_readable", "present", "Evidence Quality template source is readable.")

    if panel_source:
        _check(source_checks, "panel_exists", "present", "Evidence Quality panel exists.")
    else:
        _check(source_checks, "panel_exists", "missing", "Evidence Quality panel missing.")
        incomplete.append("Evidence Quality panel missing")

    advisory_present = ADVISORY_NOTE in panel_source
    empty_present = EMPTY_STATE in panel_source
    details_match = re.search(r"<details\b[^>]*class=\"evidence-quality-details\"[^>]*>", panel_source, re.I)
    details_collapsed = bool(details_match and " open" not in details_match.group(0).lower())
    raw_placeholder_present = 'id="evidenceQualityRawJson"' in panel_source
    visible_missing = [field for field in VISIBLE_FIELDS if field not in panel_source]
    buttons = _button_labels(panel_source)

    if advisory_present:
        _check(source_checks, "advisory_note", "present", "Advisory warning text is present.")
    else:
        _check(source_checks, "advisory_note", "missing", "Advisory warning text missing.")
        incomplete.append("Evidence Quality advisory warning missing")

    if empty_present:
        _check(source_checks, "empty_state", "present", "Empty state is present.")
    else:
        _check(source_checks, "empty_state", "missing", "Empty state missing.")
        incomplete.append("Evidence Quality empty state missing")

    if details_collapsed and raw_placeholder_present:
        _check(source_checks, "collapsed_raw_details", "present", "Raw/debug details are collapsed.")
    else:
        _check(source_checks, "collapsed_raw_details", "missing", "Collapsed raw/debug details missing.")
        incomplete.append("Evidence Quality collapsed raw/debug details missing")

    for label in buttons:
        for forbidden in FORBIDDEN_PANEL_CONTROLS:
            if label == forbidden or label.startswith(f"{forbidden} ") or f" {forbidden} " in f" {label} ":
                _block(
                    blocked,
                    f"forbidden_panel_control:{forbidden}",
                    f"Forbidden Evidence Quality panel control found: {label}",
                )

    in_primary_submit = _contains_panel(template_source, 'id="primarySubmit"', '<details class="instant-run-controls"')
    in_primary_apply = _contains_panel(template_source, 'class="actions actions--primary"', "<!-- anti-lesson-control-per-run -->")
    if in_primary_submit or in_primary_apply:
        _block(
            blocked,
            "panel_inside_primary_submit_or_apply_area",
            "Evidence Quality panel must not live inside the primary Submit/Apply path.",
        )

    panel_ready = bool(panel_source and advisory_present and empty_present and details_collapsed and raw_placeholder_present and not visible_missing)
    return {
        "panel_exists": bool(panel_source),
        "advisory_note_present": advisory_present,
        "empty_state_present": empty_present,
        "visible_fields_present": not visible_missing,
        "missing_visible_fields": visible_missing,
        "raw_debug_details_collapsed": details_collapsed,
        "raw_json_placeholder_present": raw_placeholder_present,
        "button_labels": buttons,
        "inside_primary_submit_area": in_primary_submit,
        "inside_primary_apply_area": in_primary_apply,
        "panel_ready": panel_ready,
    }


def _methods_from_route(route_source: str) -> list[str]:
    match = re.search(r"@app\.route\([^)]*methods\s*=\s*\[([^\]]*)\]", route_source, re.S)
    if not match:
        return []
    return [item.strip("'\" ") for item in match.group(1).split(",") if item.strip("'\" ")]


def _loader_readiness(
    app_source: str,
    app_error: str,
    source_checks: list[dict[str, str]],
    blocked: list[dict[str, str]],
    incomplete: list[str],
) -> dict[str, Any]:
    route_source = _between(
        app_source,
        "# EVAL.N6 GET-only Evidence Quality artifact loader",
        "# /EVAL.N6 GET-only Evidence Quality artifact loader",
    )
    if app_error:
        _check(source_checks, "loader_source_readable", "missing", f"Web app source could not be read: {app_error}")
        incomplete.append("EVAL.N6 loader source unreadable")
    else:
        _check(source_checks, "loader_source_readable", "present", "Web app source is readable.")

    route_exists = "/eval/evidence-quality/report/<path:report_id>" in route_source
    if route_exists:
        _check(source_checks, "loader_route_exists", "present", "EVAL.N6 GET loader route exists.")
    else:
        _check(source_checks, "loader_route_exists", "missing", "EVAL.N6 GET-only loader route missing.")
        incomplete.append("EVAL.N6 GET-only loader route missing")

    methods = _methods_from_route(route_source)
    get_only = methods == ["GET"]
    if get_only:
        _check(source_checks, "loader_route_get_only", "safe", "Loader route is GET-only.")
    elif route_exists:
        _check(source_checks, "loader_route_get_only", "blocked", f"Loader route methods are {methods!r}.")
        _block(blocked, "loader_route_allows_mutating_methods", "Loader route must allow GET only.")

    rooted = ".agent" in app_source and "evidence_quality_report" in app_source and "evidence_quality_report.json" in app_source
    default_supported = "default" in route_source and (
        "evidence_quality_report.json" in app_source or "_EVIDENCE_QUALITY_REPORT_JSON" in route_source
    )
    sanitized = "not _is_safe_evidence_quality_report_id" in route_source and "_EVIDENCE_QUALITY_REPORT_ID_RE" in app_source
    traversal_guarded = ".relative_to(" in route_source and "root" in route_source

    if rooted:
        _check(source_checks, "loader_allowed_root", "safe", f"Loader is rooted under {ALLOWED_REPORT_ROOT}.")
    elif route_exists:
        _check(source_checks, "loader_allowed_root", "blocked", "Allowed report root marker missing.")
        _block(blocked, "allowed_report_root_missing", "Loader must only read under .agent/eval/evidence_quality_report/.")

    if default_supported:
        _check(source_checks, "default_report_loading", "present", "Default report loading is supported.")
    elif route_exists:
        _check(source_checks, "default_report_loading", "missing", "Default report loading support missing.")
        incomplete.append("Default Evidence Quality report loading support missing")

    if sanitized:
        _check(source_checks, "report_id_sanitized", "safe", "Report id sanitization is present.")
    elif route_exists:
        _check(source_checks, "report_id_sanitized", "blocked", "Report id sanitization missing.")
        _block(blocked, "report_id_sanitization_missing", "Report id must be sanitized.")

    if traversal_guarded:
        _check(source_checks, "path_traversal_blocked", "safe", "Path traversal guard is present.")
        _check(source_checks, "encoded_traversal_blocked", "safe", "Encoded traversal is covered by report id sanitization and path guard.")
        _check(source_checks, "arbitrary_file_paths_blocked", "safe", "Loader does not accept arbitrary file paths.")
    elif route_exists:
        _check(source_checks, "path_traversal_blocked", "blocked", "Path traversal guard missing.")
        _block(blocked, "path_traversal_guard_missing", "Path traversal must be blocked by resolved root checks.")

    _scan_execution_markers(route_source, blocked)
    _scan_mutation_markers(route_source, blocked)

    loader_ready = bool(route_exists and get_only and rooted and default_supported and sanitized and traversal_guarded)
    return {
        "route_exists": route_exists,
        "route_methods": methods,
        "get_only": get_only,
        "allowed_root": ALLOWED_REPORT_ROOT if rooted else "",
        "rooted_under_allowed_report_root": rooted,
        "default_report_loading_supported": default_supported,
        "report_id_sanitized": sanitized,
        "path_traversal_blocked": traversal_guarded,
        "encoded_traversal_blocked": traversal_guarded and sanitized,
        "arbitrary_file_paths_blocked": traversal_guarded and sanitized,
        "loader_ready": loader_ready,
    }


def _scan_execution_markers(source: str, blocked: list[dict[str, str]]) -> dict[str, bool]:
    flags = {
        "report_generation_hook": any(marker in source for marker in REPORT_GENERATION_MARKERS),
        "validation_execution_hook": any(marker in source for marker in VALIDATION_MARKERS),
        "benchmark_execution_hook": any(marker in source for marker in BENCHMARK_MARKERS),
        "model_call_hook": any(marker in source for marker in MODEL_MARKERS),
    }
    if flags["report_generation_hook"]:
        _block(blocked, "evidence_quality_report_generation_hook", "Loader must not call or import the EVAL.N3 builder.")
    if flags["validation_execution_hook"]:
        _block(blocked, "validation_execution_hook", "Loader must not run validation.")
    if flags["benchmark_execution_hook"]:
        _block(blocked, "benchmark_execution_hook", "Loader must not run benchmarks.")
    if flags["model_call_hook"]:
        _block(blocked, "model_call_hook", "Loader must not call models.")
    return flags


def _scan_mutation_markers(source: str, blocked: list[dict[str, str]]) -> dict[str, bool]:
    flags = {
        "evidence_report_mutation_hook": any(marker in source for marker in MUTATION_MARKERS),
        "apply_submit_blocking_hook": ".disabled" in source,
        "routing_or_mode_change_hook": "window.location" in source or "location.href" in source or "setMode(" in source,
    }
    if flags["evidence_report_mutation_hook"]:
        _block(blocked, "evidence_report_mutation_hook", "Loader/panel must not mutate evidence reports or repo state.")
    if flags["apply_submit_blocking_hook"]:
        _block(blocked, "apply_submit_blocking_hook", "Evidence Quality must not disable Apply or Submit.")
    if flags["routing_or_mode_change_hook"]:
        _block(blocked, "routing_or_mode_change_hook", "Evidence Quality must not change routing or mode.")
    return flags


def _panel_js(template_source: str) -> str:
    return _between(
        template_source,
        "// EVAL.N5/EVAL.N6 read-only Evidence Quality panel",
        "// /EVAL.N5/EVAL.N6 read-only Evidence Quality panel",
    )


def _execution_readiness(
    template_source: str,
    app_source: str,
    blocked: list[dict[str, str]],
) -> dict[str, bool]:
    panel_js = _panel_js(template_source)
    execution_flags = _scan_execution_markers(panel_js, blocked)
    mutation_flags = _scan_mutation_markers(panel_js, blocked)
    mutating_fetch = bool(re.search(r"fetch\([^)]*method\s*:\s*['\"]POST['\"]", panel_js, re.I | re.S))
    if mutating_fetch:
        _block(blocked, "panel_post_fetch_hook", "Evidence Quality panel must not POST.")
    auto_refresh = "setInterval" in panel_js or "setTimeout" in panel_js
    if auto_refresh:
        _block(blocked, "panel_auto_refresh_hook", "Evidence Quality panel must not auto-refresh during active runs.")
    return {
        "no_report_generation_hook": not execution_flags["report_generation_hook"],
        "no_validation_hook": not execution_flags["validation_execution_hook"],
        "no_benchmark_hook": not execution_flags["benchmark_execution_hook"],
        "no_model_hook": not execution_flags["model_call_hook"],
        "no_mutating_fetch": not mutating_fetch,
        "no_auto_refresh": not auto_refresh,
        "no_apply_submit_blocking": not mutation_flags["apply_submit_blocking_hook"],
        "no_routing_or_mode_change": not mutation_flags["routing_or_mode_change_hook"],
        "app_source_scanned": bool(app_source),
    }


def _load_report(report_path: str | Path | None) -> tuple[dict[str, Any], list[str]]:
    if report_path is None or str(report_path).strip() == "":
        return {
            "supplied": False,
            "compatible": False,
            "path": "",
            "report_kind": "",
            "evidence_quality_status": "",
            "overall_evidence_quality": "",
            "claim_count": 0,
            "missing_evidence_count": 0,
            "contradiction_risk_count": 0,
        }, ["No real loaded-report demo artifact supplied; readiness remains advisory with warnings."]
    path = Path(report_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "supplied": True,
            "compatible": False,
            "path": str(path),
            "error": str(exc),
        }, [f"Report path could not be read safely: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "supplied": True,
            "compatible": False,
            "path": str(path),
            "error": f"malformed JSON: {exc.msg}",
        }, [f"Report path is malformed JSON: {exc.msg}"]
    if not isinstance(data, dict) or data.get("report_kind") != "evidence_quality_report":
        return {
            "supplied": True,
            "compatible": False,
            "path": str(path),
            "report_kind": data.get("report_kind") if isinstance(data, dict) else "",
        }, ["Report artifact is not a compatible EVAL.N3 evidence_quality_report."]

    warnings: list[str] = []
    status = str(data.get("evidence_quality_status") or "")
    quality = str(data.get("overall_evidence_quality") or "")
    if status not in {"evidence_quality_ready", "evidence_quality_ready_with_warnings"}:
        warnings.append(f"Compatible report status is not ready: {status or 'missing'}.")
    if quality in {"weak", "missing", "contradicted", "blocked"}:
        warnings.append(f"Compatible report quality is weak or blocked: {quality}.")
    return {
        "supplied": True,
        "compatible": True,
        "path": str(path),
        "report_kind": str(data.get("report_kind") or ""),
        "evidence_quality_status": status,
        "overall_evidence_quality": quality,
        "claim_count": len(data.get("claim_inventory") or []),
        "missing_evidence_count": len(data.get("missing_evidence") or []),
        "contradiction_risk_count": len(data.get("contradiction_risks") or []),
    }, warnings


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return BLOCKED
    if incomplete:
        return INCOMPLETE
    if warnings:
        return READY_WITH_WARNINGS
    return READY


def build_evidence_quality_loader_readiness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path | None = None,
    created_at: str = "",
) -> dict[str, Any]:
    """Build an EVAL.N7 readiness report by inspecting source and artifacts."""
    repo = Path(repo_root or ".").resolve()
    created = str(created_at or _utc_now())
    template_source, template_error = _read_text(repo / "web" / "templates" / "index.html")
    app_source, app_error = _read_text(repo / "web" / "app.py")

    source_checks: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    incomplete: list[str] = []

    panel = _panel_readiness(template_source, template_error, source_checks, blocked, incomplete)
    loader = _loader_readiness(app_source, app_error, source_checks, blocked, incomplete)
    execution = _execution_readiness(template_source, app_source, blocked)
    artifact, artifact_warnings = _load_report(report_path)
    warnings = list(artifact_warnings)
    readiness_status = _status(blocked, incomplete, warnings)

    forbidden = {
        "forbidden_controls_absent": not any(str(item.get("reason", "")).startswith("forbidden_panel_control:") for item in blocked),
        "button_labels": panel.get("button_labels", []),
    }
    empty_error = {
        "empty_state_present": bool(panel.get("empty_state_present")),
        "missing_report_safe_warning": not artifact.get("supplied") or "error" in artifact or bool(warnings),
        "malformed_report_safe_warning": any("malformed" in warning.lower() for warning in warnings),
        "raw_debug_details_collapsed": bool(panel.get("raw_debug_details_collapsed")),
    }
    return {
        "report_kind": REPORT_KIND,
        "created_at": created,
        "readiness_status": readiness_status,
        "guardrail_note": GUARDRAIL_NOTE,
        "summary": {
            "panel_ready": bool(panel.get("panel_ready")),
            "loader_ready": bool(loader.get("loader_ready")),
            "compatible_report_loaded": bool(artifact.get("compatible")),
            "blocked_reason_count": len(blocked),
            "incomplete_reason_count": len(incomplete),
            "warning_count": len(warnings),
            "verdict": readiness_status,
        },
        "source_checks": source_checks,
        "ui_panel_readiness": panel,
        "get_loader_readiness": loader,
        "artifact_compatibility": artifact,
        "empty_error_state_readiness": empty_error,
        "forbidden_control_checks": forbidden,
        "execution_prohibition_checks": execution,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "final_verdict": {
            "status": readiness_status,
            "ready_for_branch_checkpoint": readiness_status in {READY, READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
        "boundaries_guardrails": list(BOUNDARIES),
        "guardrails": _guardrails(),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            rendered = str(value)
        lines.append(f"- `{_md(key)}`: {_md(rendered)}")
    return lines


def _list_lines(values: Any, *, key: str = "") -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for item in values:
        if isinstance(item, dict) and key:
            lines.append(f"- {_md(item.get(key, item))}")
        elif isinstance(item, dict):
            lines.append(f"- {_md(json.dumps(item, ensure_ascii=False, sort_keys=True))}")
        else:
            lines.append(f"- {_md(item)}")
    return lines


def render_evidence_quality_loader_readiness_markdown(report: dict[str, Any]) -> str:
    """Render an EVAL.N7 readiness report as Markdown."""
    lines: list[str] = [
        "# Evidence Quality Loader Readiness Check",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))
    lines.extend(["", "## Source Checks", ""])
    lines.extend(_list_lines(report.get("source_checks")))
    lines.extend(["", "## UI Panel Readiness", ""])
    lines.extend(_dict_lines(report.get("ui_panel_readiness")))
    lines.extend(["", "## GET Loader Readiness", ""])
    lines.extend(_dict_lines(report.get("get_loader_readiness")))
    lines.extend(["", "## Artifact Compatibility", ""])
    lines.extend(_dict_lines(report.get("artifact_compatibility")))
    lines.extend(["", "## Empty/Error State Readiness", ""])
    lines.extend(_dict_lines(report.get("empty_error_state_readiness")))
    lines.extend(["", "## Forbidden Control Checks", ""])
    lines.extend(_dict_lines(report.get("forbidden_control_checks")))
    lines.extend(["", "## Execution-Prohibition Checks", ""])
    lines.extend(_dict_lines(report.get("execution_prohibition_checks")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons"), key="reason"))
    lines.extend(["", "## Final Verdict", ""])
    lines.extend(_dict_lines(report.get("final_verdict")))
    lines.extend(["", "## Boundaries / Guardrails", ""])
    lines.extend(_list_lines(report.get("boundaries_guardrails")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines.extend(
        [
            "",
            "## Recommended Next Phase",
            "",
            f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
            f"- **Title:** {_md(next_phase.get('title', ''))}",
            f"- **Reason:** {_md(next_phase.get('reason', ''))}",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence_quality_loader_readiness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    created_at: str = "",
) -> dict[str, Any]:
    """Write EVAL.N7 JSON and Markdown readiness artifacts."""
    report = build_evidence_quality_loader_readiness(
        repo_root=repo_root,
        report_path=report_path,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_evidence_quality_loader_readiness_markdown(report), encoding="utf-8")
    return {
        "ok": report["readiness_status"] in {READY, READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
