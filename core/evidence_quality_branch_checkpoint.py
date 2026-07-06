"""EVAL.CLOSE - Evidence Quality Branch Checkpoint.

Freezes the EVAL.N1-EVAL.N7 Evidence Quality branch before any further UI
expansion, scoring-gate integration, approval behavior, or automatic evidence
execution is added. This module is report-only: it reads registry metadata,
existing Evidence Quality artifacts, and local UI/loader source markers, then
writes checkpoint artifacts only.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "evidence_quality_branch_checkpoint"
THIS_PHASE_ID = "EVAL.CLOSE"
REQUIRED_EVAL_PHASE_IDS: tuple[str, ...] = (
    "EVAL.N1",
    "EVAL.N2",
    "EVAL.N3",
    "EVAL.N4",
    "EVAL.N5",
    "EVAL.N6",
    "EVAL.N7",
)

STATUS_FROZEN = "evidence_quality_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "evidence_quality_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "evidence_quality_branch_incomplete"
STATUS_BLOCKED = "evidence_quality_branch_blocked"

JSON_NAME = "evidence_quality_branch_checkpoint.json"
MD_NAME = "evidence_quality_branch_checkpoint.md"
DEFAULT_REGISTRY_PATH = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_branch_checkpoint"

ADVISORY_NOTE = "Evidence Quality is advisory evidence, not an approval gate."
EMPTY_STATE = "No evidence quality report loaded."
ALLOWED_REPORT_ROOT = ".agent/eval/evidence_quality_report/"

REQUIRED_ARTIFACTS: dict[str, dict[str, str]] = {
    "evidence_quality_plan": {
        "phase_id": "EVAL.N1",
        "path": ".agent/eval/evidence_quality_plan/evidence_quality_plan.json",
        "report_kind": "evidence_quality_plan",
    },
    "evidence_quality_report_contract": {
        "phase_id": "EVAL.N2",
        "path": ".agent/eval/evidence_quality_report_contract/evidence_quality_report_contract.json",
        "report_kind": "evidence_quality_report_contract",
    },
    "evidence_quality_report": {
        "phase_id": "EVAL.N3",
        "path": ".agent/eval/evidence_quality_report/evidence_quality_report.json",
        "report_kind": "evidence_quality_report",
    },
    "evidence_quality_artifact_loader_plan": {
        "phase_id": "EVAL.N4",
        "path": ".agent/eval/evidence_quality_artifact_loader_plan/evidence_quality_artifact_loader_plan.json",
        "report_kind": "evidence_quality_artifact_loader_plan",
    },
    "evidence_quality_loader_readiness": {
        "phase_id": "EVAL.N7",
        "path": ".agent/eval/evidence_quality_loader_readiness/evidence_quality_loader_readiness.json",
        "report_kind": "evidence_quality_loader_readiness",
    },
}

VISIBLE_PANEL_FIELDS: tuple[str, ...] = (
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
EVIDENCE_MUTATION_MARKERS: tuple[str, ...] = (
    ".write_text(",
    ".mkdir(",
    "apply_patch",
    "generate_patch",
    "request.form",
    "request.values",
    "database",
    "requests.",
)

FALSE_GUARDRAIL_KEYS: tuple[str, ...] = (
    "model_call_performed",
    "patch_apply_performed",
    "patch_applied",
    "validation_run_performed",
    "validation_run",
    "benchmark_run_performed",
    "benchmark_run",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "network_call_performed",
    "database_write_performed",
    "auth_policy_changed",
    "scoring_gate_changed",
    "approval_or_rejection_performed",
    "apply_submit_blocking_performed",
    "evidence_report_mutated",
    "route_behavior_changed",
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
    "checkpoint only",
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
    "writes checkpoint artifacts only",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "HUMAN.N1",
    "title": "Human Review Boundary Map",
    "reason": (
        "After MIRROR/CMD/MODEL/EVAL, map what the system may advise or display "
        "versus what only a human may approve."
    ),
}

GUARDRAIL_NOTE = (
    "EVAL.CLOSE is report-only: it reads existing Evidence Quality artifacts, "
    "registry metadata, and local UI/loader source markers to freeze EVAL.N1-EVAL.N7 "
    "as advisory, read-only where applicable, and non-blocking. It writes checkpoint "
    "artifacts only."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return str(bool(value)).lower()


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _norm_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _resolve(repo: Path, path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else repo / raw


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", str(exc)


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "artifact is not a JSON object"
    return data, ""


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def _block(blocked: list[dict[str, str]], reason: str, message: str) -> None:
    if not any(item.get("reason") == reason for item in blocked):
        blocked.append({"reason": reason, "message": message})


def _between(text: str, start: str, end: str) -> str:
    try:
        start_index = text.index(start)
        end_index = text.index(end, start_index)
    except ValueError:
        return ""
    return text[start_index:end_index]


def _button_labels(panel_source: str) -> list[str]:
    labels: list[str] = []
    for raw in re.findall(r"<button\b[^>]*>(.*?)</button>", panel_source, flags=re.I | re.S):
        label = re.sub(r"<[^>]+>", " ", raw)
        label = re.sub(r"\s+", " ", label).strip()
        if label:
            labels.append(label)
    return labels


def _methods_from_route(route_source: str) -> list[str]:
    match = re.search(r"@app\.route\([^)]*methods\s*=\s*\[([^\]]*)\]", route_source, re.S)
    if not match:
        return []
    return [item.strip("'\" ") for item in match.group(1).split(",") if item.strip("'\" ")]


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    return {
        str(phase["phase_id"]): phase
        for phase in phases
        if isinstance(phase, dict) and phase.get("phase_id")
    }


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for key in ("network_allowed", "model_calls_allowed", "merge_allowed", "writes_real_repo"):
        if phase.get(key) is True:
            violations.append(key)
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _phase_completion(registry_data: Any, registry_error: str, blocked: list[dict[str, str]]) -> dict[str, Any]:
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    if registry_error:
        _block(blocked, "phase_registry_unreadable", f"Phase registry could not be read: {registry_error}")
    if not isinstance(registry_data, dict):
        _block(blocked, "phase_registry_missing", "Phase registry data is missing.")

    for phase_id in REQUIRED_EVAL_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        status = str(phase.get("status", "")) if present else "(missing)"
        complete = present and status == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        if not present:
            _block(blocked, f"required_phase_missing:{phase_id}", f"{phase_id} is missing from the phase registry.")
        elif not complete:
            _block(blocked, f"required_phase_not_complete:{phase_id}", f"{phase_id} is not registered complete.")
        for violation in violations:
            _block(blocked, f"required_phase_guardrail:{phase_id}:{violation}", f"{phase_id} adds forbidden power: {violation}.")
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": status,
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )

    this_phase = phases.get(THIS_PHASE_ID)
    this_present = this_phase is not None
    this_status = str(this_phase.get("status", "")) if this_present else "(missing)"
    this_complete = this_present and this_status == "complete"
    this_violations = _phase_guardrail_violations(this_phase) if this_present else []
    if not this_present:
        _block(blocked, f"required_phase_missing:{THIS_PHASE_ID}", f"{THIS_PHASE_ID} is missing from the phase registry.")
    elif not this_complete:
        _block(blocked, f"required_phase_not_complete:{THIS_PHASE_ID}", f"{THIS_PHASE_ID} is not registered complete.")
    for violation in this_violations:
        _block(blocked, f"required_phase_guardrail:{THIS_PHASE_ID}:{violation}", f"{THIS_PHASE_ID} adds forbidden power: {violation}.")

    return {
        "required_phase_ids": list(REQUIRED_EVAL_PHASE_IDS),
        "phase_checks": checks,
        "all_required_eval_phases_complete": all(check["complete"] for check in checks),
        "all_required_eval_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_present": this_present,
        "this_phase_status": this_status,
        "this_phase_complete": this_complete,
        "this_phase_guardrails_ok": this_present and not this_violations,
        "this_phase_guardrail_violations": this_violations,
    }


def _artifact_guardrail_violations(key: str, artifact: dict[str, Any]) -> list[str]:
    guardrails = artifact.get("guardrails")
    if not isinstance(guardrails, dict):
        return []
    violations: list[str] = []
    for flag in FALSE_GUARDRAIL_KEYS:
        if guardrails.get(flag) is True:
            violations.append(f"{key} guardrail {flag} is true")
    return violations


def _artifact_coverage(
    artifacts: dict[str, dict[str, Any] | None],
    artifact_errors: dict[str, str],
    artifact_paths: dict[str, str],
    blocked: list[dict[str, str]],
    incomplete: list[str],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    guardrail_violations: list[str] = []
    for key, spec in REQUIRED_ARTIFACTS.items():
        artifact = artifacts.get(key)
        load_error = str(artifact_errors.get(key) or "")
        present = isinstance(artifact, dict) and not load_error
        expected_kind = spec["report_kind"]
        report_kind = str(artifact.get("report_kind", "")) if isinstance(artifact, dict) else ""
        kind_ok = present and report_kind == expected_kind
        violations = _artifact_guardrail_violations(key, artifact) if isinstance(artifact, dict) else []
        guardrail_violations.extend(violations)

        if not present:
            incomplete.append(f"{key} artifact missing or unreadable: {load_error or 'missing'}")
        elif not kind_ok:
            incomplete.append(f"{key} artifact report_kind {report_kind or '(missing)'} is not {expected_kind}")
        for violation in violations:
            _block(blocked, f"artifact_guardrail:{key}", violation)

        checks.append(
            {
                "artifact_key": key,
                "phase_id": spec["phase_id"],
                "path": _norm_path(artifact_paths.get(key, spec["path"])),
                "expected_report_kind": expected_kind,
                "report_kind": report_kind,
                "present": present,
                "kind_ok": kind_ok,
                "load_error": load_error,
                "guardrails_ok": present and kind_ok and not violations,
                "guardrail_violations": violations,
            }
        )
    return {
        "artifact_checks": checks,
        "required_artifacts_present": all(check["present"] and check["kind_ok"] for check in checks),
        "artifact_guardrails_ok": not guardrail_violations,
        "artifact_guardrail_violations": guardrail_violations,
    }


def _scan_execution_markers(source: str, blocked: list[dict[str, str]]) -> dict[str, bool]:
    flags = {
        "report_generation_hook": any(marker in source for marker in REPORT_GENERATION_MARKERS),
        "validation_execution_hook": any(marker in source for marker in VALIDATION_MARKERS),
        "benchmark_execution_hook": any(marker in source for marker in BENCHMARK_MARKERS),
        "model_call_hook": any(marker in source for marker in MODEL_MARKERS),
    }
    if flags["report_generation_hook"]:
        _block(blocked, "evidence_quality_report_generation_hook", "Evidence Quality loader/panel must not call or import the EVAL.N3 builder.")
    if flags["validation_execution_hook"]:
        _block(blocked, "validation_execution_hook", "Evidence Quality loader/panel must not run validation.")
    if flags["benchmark_execution_hook"]:
        _block(blocked, "benchmark_execution_hook", "Evidence Quality loader/panel must not run benchmarks.")
    if flags["model_call_hook"]:
        _block(blocked, "model_call_hook", "Evidence Quality loader/panel must not call models.")
    return flags


def _scan_mutation_markers(source: str, blocked: list[dict[str, str]]) -> dict[str, bool]:
    flags = {
        "evidence_report_mutation_hook": any(marker in source for marker in EVIDENCE_MUTATION_MARKERS),
        "apply_submit_blocking_hook": ".disabled" in source,
        "routing_or_mode_change_hook": "window.location" in source or "location.href" in source or "setMode(" in source,
    }
    if flags["evidence_report_mutation_hook"]:
        _block(blocked, "evidence_report_mutation_hook", "Evidence Quality must not mutate evidence reports or repo state.")
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


def _ui_loader_safety(
    template_source: str,
    template_error: str,
    app_source: str,
    app_error: str,
    blocked: list[dict[str, str]],
    incomplete: list[str],
) -> dict[str, Any]:
    panel_source = _between(template_source, 'id="evidenceQualityPanel"', "<!-- /evidence-quality-panel -->")
    route_source = _between(
        app_source,
        "# EVAL.N6 GET-only Evidence Quality artifact loader",
        "# /EVAL.N6 GET-only Evidence Quality artifact loader",
    )
    if template_error:
        incomplete.append(f"Evidence Quality template unreadable: {template_error}")
    if app_error:
        incomplete.append(f"Evidence Quality loader source unreadable: {app_error}")

    ui_stub_present = bool(panel_source)
    if not ui_stub_present:
        incomplete.append("Evidence Quality panel missing")
    get_loader_present = "/eval/evidence-quality/report/<path:report_id>" in route_source
    if not get_loader_present:
        incomplete.append("EVAL.N6 GET-only loader missing")

    advisory_present = ADVISORY_NOTE in panel_source
    empty_state_present = EMPTY_STATE in panel_source
    visible_missing = [field for field in VISIBLE_PANEL_FIELDS if field not in panel_source]
    details_match = re.search(r"<details\b[^>]*class=\"evidence-quality-details\"[^>]*>", panel_source, re.I)
    raw_details_collapsed = bool(details_match and " open" not in details_match.group(0).lower())
    raw_json_placeholder_present = 'id="evidenceQualityRawJson"' in panel_source
    button_labels = _button_labels(panel_source)
    if ui_stub_present and not advisory_present:
        incomplete.append("Evidence Quality advisory warning missing")
    if ui_stub_present and not empty_state_present:
        incomplete.append("Evidence Quality empty state missing")
    if ui_stub_present and visible_missing:
        incomplete.append("Evidence Quality visible placeholder fields missing: " + ", ".join(visible_missing))
    if ui_stub_present and not raw_details_collapsed:
        incomplete.append("Evidence Quality raw/details section is not collapsed")

    for label in button_labels:
        for forbidden in FORBIDDEN_PANEL_CONTROLS:
            if label == forbidden or label.startswith(f"{forbidden} ") or f" {forbidden} " in f" {label} ":
                _block(blocked, f"forbidden_panel_control:{forbidden}", f"Forbidden Evidence Quality panel control found: {label}")

    methods = _methods_from_route(route_source)
    get_only = methods == ["GET"]
    if get_loader_present and not get_only:
        _block(blocked, "loader_route_allows_mutating_methods", f"Loader route methods are {methods!r}; expected GET only.")

    rooted = ".agent" in app_source and "evidence_quality_report" in app_source and "evidence_quality_report.json" in app_source
    if get_loader_present and not rooted:
        _block(blocked, "allowed_report_root_missing", "Loader must only read under .agent/eval/evidence_quality_report/.")
    sanitized = "not _is_safe_evidence_quality_report_id" in route_source and "_EVIDENCE_QUALITY_REPORT_ID_RE" in app_source
    if get_loader_present and not sanitized:
        _block(blocked, "report_id_sanitization_missing", "Evidence Quality report ids must be sanitized.")
    traversal_guarded = ".relative_to(" in route_source and "root" in route_source
    if get_loader_present and not traversal_guarded:
        _block(blocked, "path_traversal_guard_missing", "Loader must block traversal with a resolved root check.")

    panel_js = _panel_js(template_source)
    route_execution = _scan_execution_markers(route_source, blocked)
    panel_execution = _scan_execution_markers(panel_js, blocked)
    route_mutation = _scan_mutation_markers(route_source, blocked)
    panel_mutation = _scan_mutation_markers(panel_js, blocked)
    mutating_fetch = bool(re.search(r"fetch\([^)]*method\s*:\s*['\"]POST['\"]", panel_js, re.I | re.S))
    if mutating_fetch:
        _block(blocked, "panel_post_fetch_hook", "Evidence Quality panel must not POST.")
    auto_refresh = "setInterval" in panel_js or "setTimeout" in panel_js
    if auto_refresh:
        _block(blocked, "panel_auto_refresh_hook", "Evidence Quality panel must not auto-refresh.")

    return {
        "ui_stub_present": ui_stub_present,
        "advisory_note_present": advisory_present,
        "empty_state_present": empty_state_present,
        "visible_fields_present": not visible_missing,
        "missing_visible_fields": visible_missing,
        "raw_details_collapsed": raw_details_collapsed,
        "raw_json_placeholder_present": raw_json_placeholder_present,
        "get_loader_present": get_loader_present,
        "loader_methods": methods,
        "loader_get_only": get_only,
        "loader_rooted_under_allowed_report_root": rooted,
        "loader_allowed_root": ALLOWED_REPORT_ROOT if rooted else "",
        "report_id_sanitized": sanitized,
        "path_traversal_blocked": traversal_guarded,
        "arbitrary_paths_blocked": sanitized and traversal_guarded,
        "button_labels": button_labels,
        "forbidden_controls_absent": not any(str(item.get("reason", "")).startswith("forbidden_panel_control:") for item in blocked),
        "no_report_generation_hook": not (route_execution["report_generation_hook"] or panel_execution["report_generation_hook"]),
        "no_validation_hook": not (route_execution["validation_execution_hook"] or panel_execution["validation_execution_hook"]),
        "no_benchmark_hook": not (route_execution["benchmark_execution_hook"] or panel_execution["benchmark_execution_hook"]),
        "no_model_hook": not (route_execution["model_call_hook"] or panel_execution["model_call_hook"]),
        "no_evidence_report_mutation_hook": not (route_mutation["evidence_report_mutation_hook"] or panel_mutation["evidence_report_mutation_hook"]),
        "no_apply_submit_blocking_hook": not (route_mutation["apply_submit_blocking_hook"] or panel_mutation["apply_submit_blocking_hook"]),
        "no_routing_or_mode_change_hook": not (route_mutation["routing_or_mode_change_hook"] or panel_mutation["routing_or_mode_change_hook"]),
        "no_mutating_fetch": not mutating_fetch,
        "no_auto_refresh": not auto_refresh,
    }


def _warning_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for item in value:
        if isinstance(item, dict):
            texts.append(str(item.get("message") or item.get("warning_id") or json.dumps(item, sort_keys=True)))
        else:
            texts.append(str(item))
    return texts


def _branch_warnings(artifacts: dict[str, dict[str, Any] | None]) -> tuple[list[str], dict[str, Any]]:
    warnings: list[str] = []
    readiness = artifacts.get("evidence_quality_loader_readiness") or {}
    report = artifacts.get("evidence_quality_report") or {}
    readiness_status = str(readiness.get("readiness_status", ""))
    readiness_summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    compatible_loaded = bool(readiness_summary.get("compatible_report_loaded"))
    if readiness_status == "loader_readiness_ready_with_warnings":
        warnings.append("EVAL.N7 readiness artifact is ready with warnings.")
    warnings.extend(_warning_texts(readiness.get("warnings")))
    if not compatible_loaded:
        warnings.append("No real loaded-report demo evidence was supplied to EVAL.N7.")

    evidence_quality_status = str(report.get("evidence_quality_status", ""))
    overall_quality = str(report.get("overall_evidence_quality", ""))
    if evidence_quality_status and evidence_quality_status not in {"evidence_quality_ready", "evidence_quality_ready_with_warnings"}:
        warnings.append(f"EVAL.N3 report status is {evidence_quality_status}.")
    if overall_quality in {"weak", "missing", "contradicted", "blocked"}:
        warnings.append(f"EVAL.N3 overall evidence quality is {overall_quality}.")
    warnings.extend(_warning_texts(report.get("warnings")))

    missing_demo = {
        "real_loaded_report_demo_supplied": compatible_loaded,
        "readiness_status": readiness_status,
        "compatible_report_loaded": compatible_loaded,
        "warning": "" if compatible_loaded else "No real loaded-report demo evidence was supplied to EVAL.N7.",
    }
    return _dedupe(warnings), missing_demo


def _status(blocked: list[dict[str, str]], incomplete: list[str], warnings: list[str]) -> str:
    if blocked:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WITH_WARNINGS
    return STATUS_FROZEN


def _collect_inputs(repo: Path, registry_path: str | Path) -> dict[str, Any]:
    registry_file = _resolve(repo, registry_path)
    registry_data, registry_error = _load_json_object(registry_file)
    artifacts: dict[str, dict[str, Any] | None] = {}
    artifact_errors: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    for key, spec in REQUIRED_ARTIFACTS.items():
        path = _resolve(repo, spec["path"])
        artifact_paths[key] = _norm_path(spec["path"])
        artifacts[key], artifact_errors[key] = _load_json_object(path)
    template_source, template_error = _read_text(repo / "web" / "templates" / "index.html")
    app_source, app_error = _read_text(repo / "web" / "app.py")
    return {
        "registry_data": registry_data,
        "registry_error": registry_error,
        "artifacts": artifacts,
        "artifact_errors": artifact_errors,
        "artifact_paths": artifact_paths,
        "template_source": template_source,
        "template_error": template_error,
        "app_source": app_source,
        "app_error": app_error,
    }


def build_evidence_quality_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build an EVAL.CLOSE checkpoint by reading existing local artifacts/source."""
    repo = Path(repo_root or ".").resolve()
    inputs = _collect_inputs(repo, registry_path)
    blocked: list[dict[str, str]] = []
    incomplete: list[str] = []

    phase_completion = _phase_completion(inputs["registry_data"], str(inputs["registry_error"] or ""), blocked)
    artifact_coverage = _artifact_coverage(
        inputs["artifacts"],
        inputs["artifact_errors"],
        inputs["artifact_paths"],
        blocked,
        incomplete,
    )
    ui_loader_safety = _ui_loader_safety(
        inputs["template_source"],
        str(inputs["template_error"] or ""),
        inputs["app_source"],
        str(inputs["app_error"] or ""),
        blocked,
        incomplete,
    )
    warnings, missing_demo = _branch_warnings(inputs["artifacts"])
    warnings = _dedupe(warnings)
    incomplete = _dedupe(incomplete)
    status = _status(blocked, incomplete, warnings)

    forbidden_control_checks = {
        "button_labels": list(ui_loader_safety["button_labels"]),
        "forbidden_controls_absent": bool(ui_loader_safety["forbidden_controls_absent"]),
    }
    execution_checks = {
        "no_report_generation_hook": bool(ui_loader_safety["no_report_generation_hook"]),
        "no_validation_hook": bool(ui_loader_safety["no_validation_hook"]),
        "no_benchmark_hook": bool(ui_loader_safety["no_benchmark_hook"]),
        "no_model_hook": bool(ui_loader_safety["no_model_hook"]),
        "no_evidence_report_mutation_hook": bool(ui_loader_safety["no_evidence_report_mutation_hook"]),
        "no_apply_submit_blocking_hook": bool(ui_loader_safety["no_apply_submit_blocking_hook"]),
        "no_routing_or_mode_change_hook": bool(ui_loader_safety["no_routing_or_mode_change_hook"]),
        "no_mutating_fetch": bool(ui_loader_safety["no_mutating_fetch"]),
        "no_auto_refresh": bool(ui_loader_safety["no_auto_refresh"]),
    }
    capability_summary = {
        "doctrine_plan_present": bool(inputs["artifacts"].get("evidence_quality_plan")),
        "report_contract_present": bool(inputs["artifacts"].get("evidence_quality_report_contract")),
        "report_artifact_present": bool(inputs["artifacts"].get("evidence_quality_report")),
        "artifact_loader_plan_present": bool(inputs["artifacts"].get("evidence_quality_artifact_loader_plan")),
        "read_only_ui_stub_present": bool(ui_loader_safety["ui_stub_present"]),
        "get_only_loader_present": bool(ui_loader_safety["get_loader_present"] and ui_loader_safety["loader_get_only"]),
        "loader_readiness_artifact_present": bool(inputs["artifacts"].get("evidence_quality_loader_readiness")),
        "advisory_only": True,
        "approval_gate": False,
        "blocking_gate": False,
    }
    human_boundary = {
        "advisory_only": True,
        "approval_gate": False,
        "human_must_approve": True,
        "system_may_display": [
            "Evidence Quality status",
            "artifact evidence summaries",
            "missing evidence and warning counts",
            "recommended human checks",
        ],
        "human_only_authority": [
            "approve work",
            "reject work",
            "apply patches",
            "accept risk",
            "treat evidence as sufficient",
        ],
    }
    summary = {
        "checkpoint_status": status,
        "all_required_eval_phases_complete": bool(phase_completion["all_required_eval_phases_complete"]),
        "required_artifacts_present": bool(artifact_coverage["required_artifacts_present"]),
        "ui_stub_present": bool(ui_loader_safety["ui_stub_present"]),
        "get_loader_present": bool(ui_loader_safety["get_loader_present"]),
        "loader_get_only": bool(ui_loader_safety["loader_get_only"]),
        "blocked_reason_count": len(blocked),
        "incomplete_reason_count": len(incomplete),
        "warning_count": len(warnings),
    }
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or _utc_now()),
        "repo_root": _norm_path(repo),
        "registry_path": _norm_path(registry_path),
        "checkpoint_status": status,
        "summary": summary,
        "phase_completion": phase_completion,
        "artifact_coverage": artifact_coverage,
        "evidence_quality_capability_summary": capability_summary,
        "ui_loader_safety": ui_loader_safety,
        "forbidden_control_checks": forbidden_control_checks,
        "execution_prohibition_checks": execution_checks,
        "human_review_boundary": human_boundary,
        "missing_demo_evidence": missing_demo,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "incomplete_reasons": incomplete,
        "final_verdict": {
            "status": status,
            "branch_frozen": status == STATUS_FROZEN,
            "branch_frozen_with_warnings": status == STATUS_FROZEN_WITH_WARNINGS,
            "ready_for_human_boundary_map": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
        },
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "boundaries_guardrails": list(BOUNDARIES),
        "guardrails": _guardrails(),
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


def render_evidence_quality_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the EVAL.CLOSE checkpoint as operator-readable Markdown."""
    lines: list[str] = [
        "# Evidence Quality Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_dict_lines(report.get("summary")))
    lines.extend(["", "## Phase Completion", ""])
    phase = report.get("phase_completion") if isinstance(report.get("phase_completion"), dict) else {}
    lines.extend(_dict_lines({k: v for k, v in phase.items() if k != "phase_checks"}))
    checks = phase.get("phase_checks") if isinstance(phase.get("phase_checks"), list) else []
    if checks:
        lines.extend(["", "| Phase | Present | Status | Complete | Guardrails OK |", "|---|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('phase_id'))} | {_bool(check.get('present'))} | {_md(check.get('status'))} | "
                f"{_bool(check.get('complete'))} | {_bool(check.get('guardrails_ok'))} |"
            )
    lines.extend(["", "## Artifact Coverage", ""])
    artifact = report.get("artifact_coverage") if isinstance(report.get("artifact_coverage"), dict) else {}
    artifact_checks = artifact.get("artifact_checks") if isinstance(artifact.get("artifact_checks"), list) else []
    if artifact_checks:
        lines.extend(["| Artifact | Present | Kind OK | Path |", "|---|---|---|---|"])
        for check in artifact_checks:
            lines.append(
                f"| {_md(check.get('artifact_key'))} | {_bool(check.get('present'))} | "
                f"{_bool(check.get('kind_ok'))} | `{_md(check.get('path'))}` |"
            )
    else:
        lines.append("_None._")
    lines.extend(["", "## Evidence Quality Capability Summary", ""])
    lines.extend(_dict_lines(report.get("evidence_quality_capability_summary")))
    lines.extend(["", "## UI/Loader Safety Verification", ""])
    lines.extend(_dict_lines(report.get("ui_loader_safety")))
    lines.extend(["", "## Forbidden Control Checks", ""])
    lines.extend(_dict_lines(report.get("forbidden_control_checks")))
    lines.extend(["", "## Execution-Prohibition Checks", ""])
    lines.extend(_dict_lines(report.get("execution_prohibition_checks")))
    lines.extend(["", "## Human Review Boundary", ""])
    lines.extend(_dict_lines(report.get("human_review_boundary")))
    lines.extend(["", "## Missing Demo Evidence", ""])
    lines.extend(_dict_lines(report.get("missing_demo_evidence")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons"), key="reason"))
    lines.extend(["", "## Final Verdict", ""])
    lines.extend(_dict_lines(report.get("final_verdict")))
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
            "## Boundaries / Guardrails",
            "",
        ]
    )
    lines.extend(_list_lines(report.get("boundaries_guardrails")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_evidence_quality_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write EVAL.CLOSE JSON/Markdown checkpoint artifacts."""
    report = build_evidence_quality_branch_checkpoint(
        repo_root=repo_root,
        registry_path=registry_path,
        report_id=report_id,
        created_at=created_at,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_evidence_quality_branch_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
