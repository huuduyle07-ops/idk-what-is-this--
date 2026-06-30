"""MIRROR.CLOSE - Mirror Tunnel Branch Checkpoint (report-only).

This checkpoint freezes the manual Mirror Tunnel branch after MIRROR.1 through
MIRROR.6 and before any live runtime instrumentation. It reads the phase
registry, already-written Mirror Tunnel artifacts, and local source text, then
writes JSON and Markdown checkpoint artifacts only.

It does not call models, apply patches, run validation, run benchmarks, invoke
MCP tools, launch workers, execute Dream or Replay janitor actions, use Docker
or subprocess, contact network services, write to a database, change route
behavior, change auth policy, enable live runtime tracing, or block execution.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "mirror_tunnel_branch_checkpoint"
THIS_PHASE_ID = "MIRROR.CLOSE"
REQUIRED_MIRROR_PHASE_IDS: tuple[str, ...] = (
    "MIRROR.1",
    "MIRROR.2",
    "MIRROR.3",
    "MIRROR.4",
    "MIRROR.5",
    "MIRROR.6",
)

STATUS_FROZEN_COMPLETE = "frozen_manual_pipeline_complete"
STATUS_FROZEN_WARNINGS = "frozen_with_manual_review_warnings"
STATUS_NEEDS_MANUAL_EVIDENCE = "needs_more_manual_evidence"
STATUS_BLOCKED = "blocked"

JSON_NAME = "mirror_tunnel_branch_checkpoint.json"
MD_NAME = "mirror_tunnel_branch_checkpoint.md"

DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "branch_checkpoint"
DEFAULT_ARTIFACT_PATHS: dict[str, str] = {
    "trace_contract": ".agent/mirror_tunnel/trace_contract/mirror_tunnel_trace_contract.json",
    "derailment_score": ".agent/mirror_tunnel/derailment_score/mirror_tunnel_derailment_score.json",
    "claim_diff_check": ".agent/mirror_tunnel/claim_diff_check/mirror_tunnel_claim_diff_check.json",
    "ingestion_plan": ".agent/mirror_tunnel/ingestion_plan/mirror_tunnel_ingestion_plan.json",
}

EXPECTED_REPORT_KINDS: dict[str, str] = {
    "trace_contract": "mirror_tunnel_trace_contract",
    "derailment_score": "mirror_tunnel_derailment_score",
    "claim_diff_check": "mirror_tunnel_claim_diff_check",
    "ingestion_plan": "mirror_tunnel_ingestion_plan",
    "manual_trace": "mirror_tunnel_trace_contract",
    "manual_review": "mirror_tunnel_manual_review",
}

CORE_MODULES: tuple[tuple[str, str], ...] = (
    ("MIRROR.1", "core/mirror_tunnel_trace_contract.py"),
    ("MIRROR.2", "core/mirror_tunnel_derailment_score.py"),
    ("MIRROR.3", "core/mirror_tunnel_claim_diff_check.py"),
    ("MIRROR.4", "core/mirror_tunnel_ingestion_plan.py"),
    ("MIRROR.5", "core/mirror_tunnel_manual_trace_assembler.py"),
    ("MIRROR.6", "core/mirror_tunnel_manual_review_pipeline.py"),
    (THIS_PHASE_ID, "core/mirror_tunnel_branch_checkpoint.py"),
)

SCRIPT_MODULES: tuple[str, ...] = (
    "scripts/create_mirror_tunnel_trace_contract.py",
    "scripts/create_mirror_tunnel_derailment_score.py",
    "scripts/create_mirror_tunnel_claim_diff_check.py",
    "scripts/create_mirror_tunnel_ingestion_plan.py",
    "scripts/create_mirror_tunnel_manual_trace.py",
    "scripts/create_mirror_tunnel_manual_review.py",
    "scripts/create_mirror_tunnel_branch_checkpoint.py",
)

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

NEXT_PHASE = "MIRROR.7 - Shadow Live Trace Writer"

GUARDRAIL_NOTE = (
    "MIRROR.CLOSE is report-only. It freezes the manual Mirror Tunnel evidence "
    "loop and allows future live instrumentation only as shadow-only, default-off, "
    "non-blocking work."
)

BOUNDARIES: tuple[str, ...] = (
    "MIRROR.CLOSE is report-only.",
    "MIRROR.CLOSE reads registry, source, and existing Mirror Tunnel artifacts only.",
    "MIRROR.CLOSE writes checkpoint artifacts only.",
    "MIRROR.CLOSE does not call models.",
    "MIRROR.CLOSE does not apply patches.",
    "MIRROR.CLOSE does not run validation.",
    "MIRROR.CLOSE does not run benchmarks.",
    "MIRROR.CLOSE does not invoke MCP tools.",
    "MIRROR.CLOSE does not launch workers.",
    "MIRROR.CLOSE does not execute Dream actions.",
    "MIRROR.CLOSE does not apply Replay janitor actions.",
    "MIRROR.CLOSE does not use Docker or subprocess.",
    "MIRROR.CLOSE does not contact network services.",
    "MIRROR.CLOSE does not write to a database.",
    "MIRROR.CLOSE does not change route behavior.",
    "MIRROR.CLOSE does not change auth policy.",
    "MIRROR.CLOSE does not enable live runtime tracing.",
    "MIRROR.CLOSE does not block execution.",
    "Future live instrumentation is allowed only as shadow-only, default-off, non-blocking work.",
)

_FORBIDDEN_IMPORT_ROOTS: set[str] = {
    "agents",
    "anthropic",
    "benchmarks",
    "database",
    "docker",
    "flask",
    "google",
    "httpx",
    "mcp",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "web",
}

_FORBIDDEN_CALL_NAMES: set[str] = {
    "apply_patch",
    "call",
    "call_model",
    "check_call",
    "check_output",
    "connect",
    "create_dream",
    "execute",
    "get_embedding",
    "invoke_mcp",
    "launch_worker",
    "Popen",
    "post",
    "request",
    "run",
    "run_benchmarks",
    "run_safe_validation_command",
    "run_validation_command",
    "system",
    "urlopen",
}


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/")


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _lower(value: Any) -> str:
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


def _load_json_object(path: Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None:
        return None, "missing artifact path"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read or parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def _repo_path(repo_path: str | Path) -> Path:
    return Path(repo_path or ".").expanduser().resolve()


def _resolve(repo: Path, path: str | Path | None) -> Path | None:
    if path is None or str(path).strip() == "":
        return None
    raw = Path(path).expanduser()
    return raw.resolve() if raw.is_absolute() else (repo / raw).resolve()


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    return {
        str(phase["phase_id"]): phase
        for phase in phases
        if isinstance(phase, dict) and phase.get("phase_id")
    }


def _phase_guardrail_violations(phase: dict[str, Any]) -> list[str]:
    violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase.get(field) is True]
    automation = str(phase.get("automation_level", ""))
    if automation not in {"LOCAL_0_OBSERVE", "LOCAL_1_PREPARE"}:
        violations.append(f"automation_level={automation or '(missing)'}")
    if phase.get("human_approval_required") is not True:
        violations.append("human_approval_required")
    return violations


def _build_phase_status(registry_data: Any) -> dict[str, Any]:
    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_MIRROR_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        complete = present and phase.get("status") == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": _str(phase.get("status")) if present else "(missing)",
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )

    this_phase = phases.get(THIS_PHASE_ID)
    this_registered = this_phase is not None
    this_complete = this_registered and this_phase.get("status") == "complete"
    this_violations = _phase_guardrail_violations(this_phase) if this_registered else []
    return {
        "required_phase_ids": list(REQUIRED_MIRROR_PHASE_IDS),
        "phase_checks": checks,
        "all_required_mirror_phases_complete": all(check["complete"] for check in checks),
        "all_required_mirror_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_registered": this_registered,
        "this_phase_complete": this_complete,
        "this_phase_guardrails_ok": this_registered and not this_violations,
        "this_phase_guardrail_violations": this_violations,
    }


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "live_runtime_tracing_enabled": False,
        "execution_blocking_performed": False,
        "runtime_behavior_changed": False,
    }


def _artifact_guardrail_violations(key: str, report: Any) -> list[str]:
    if not isinstance(report, dict):
        return [f"{key} artifact is missing"]
    guardrails = report.get("guardrails")
    if not isinstance(guardrails, dict):
        return [f"{key} artifact has no guardrails block"]
    violations: list[str] = []
    if guardrails.get("report_only") is not True:
        violations.append(f"{key} guardrail report_only is not true")
    for guardrail_key, value in guardrails.items():
        if guardrail_key == "report_only":
            continue
        if guardrail_key.startswith("writes_") or guardrail_key.startswith("reads_"):
            continue
        if value is not False:
            violations.append(f"{key} guardrail {guardrail_key} is not false")
    return violations


def _artifact_status_value(key: str, report: Any) -> str:
    if not isinstance(report, dict):
        return "(missing)"
    if key in {"trace_contract", "ingestion_plan", "manual_trace"}:
        return _str(report.get("status"))
    if key == "derailment_score":
        return _str(report.get("verdict"))
    if key == "claim_diff_check":
        return _str(report.get("overall_claim_support"))
    if key == "manual_review":
        return _str(report.get("combined_verdict"))
    return ""


def _build_artifact_evidence(
    artifact_reports: dict[str, Any],
    artifact_load_errors: dict[str, str],
    artifact_paths: dict[str, str] | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    guardrail_violations: list[str] = []
    missing_required: list[str] = []
    manual_gaps: list[str] = []
    paths = artifact_paths or {}

    for key, expected_kind in EXPECTED_REPORT_KINDS.items():
        report = artifact_reports.get(key)
        load_error = _str(artifact_load_errors.get(key))
        present = isinstance(report, dict) and not load_error
        kind = _str(report.get("report_kind")) if isinstance(report, dict) else ""
        kind_ok = present and kind == expected_kind
        violations = _artifact_guardrail_violations(key, report) if present else []
        if present and not kind_ok:
            violations.append(f"{key} report_kind {kind or '(missing)'} is not {expected_kind}")
        guardrail_violations.extend(violations)
        if not present:
            message = f"{key} artifact missing or unreadable: {load_error or 'missing'}"
            if key in {"manual_trace", "manual_review"}:
                manual_gaps.append(message)
            else:
                missing_required.append(message)
        checks.append(
            {
                "artifact_key": key,
                "path": _norm_path(paths.get(key, "")),
                "expected_report_kind": expected_kind,
                "report_kind": kind,
                "present": present,
                "load_error": load_error,
                "status": _artifact_status_value(key, report),
                "guardrails_ok": present and kind_ok and not violations,
                "guardrail_violations": violations,
            }
        )

    return {
        "artifact_checks": checks,
        "missing_required_artifacts": missing_required,
        "manual_evidence_gaps": manual_gaps,
        "artifact_guardrail_violations": guardrail_violations,
        "all_required_artifacts_present": not missing_required,
        "all_artifact_guardrails_ok": not guardrail_violations,
    }


def _meaningful_manual_frames(manual_trace: Any) -> list[dict[str, Any]]:
    if not isinstance(manual_trace, dict):
        return []
    frames = manual_trace.get("frames") if isinstance(manual_trace.get("frames"), list) else []
    return [
        frame
        for frame in frames
        if isinstance(frame, dict)
        and _str(frame.get("frame_type"))
        and _str(frame.get("frame_type")) != "unknown_artifact"
    ]


def _build_manual_pipeline_summary(artifact_reports: dict[str, Any], manual_gaps: list[str]) -> dict[str, Any]:
    manual_trace = artifact_reports.get("manual_trace")
    manual_review = artifact_reports.get("manual_review")
    meaningful = _meaningful_manual_frames(manual_trace)
    review_present = isinstance(manual_review, dict)
    review_status = _str(manual_review.get("combined_verdict")) if review_present else "(missing)"
    trace_status = _str(manual_trace.get("status")) if isinstance(manual_trace, dict) else "(missing)"
    extra_gaps = list(manual_gaps)
    if isinstance(manual_trace, dict) and not meaningful:
        extra_gaps.append("manual trace has no meaningful non-unknown frames")
    if review_present and review_status == "blocked":
        extra_gaps.append("manual review artifact is blocked")
    usable = not extra_gaps and bool(meaningful) and review_present
    warnings = list(manual_review.get("warnings") or []) if review_present and isinstance(manual_review.get("warnings"), list) else []
    return {
        "manual_trace_present": isinstance(manual_trace, dict),
        "manual_review_present": review_present,
        "manual_trace_status": trace_status,
        "manual_review_status": review_status,
        "meaningful_manual_frame_count": len(meaningful),
        "meaningful_manual_frame_types": [_str(frame.get("frame_type")) for frame in meaningful],
        "manual_review_warning_count": len(warnings),
        "manual_review_warnings": [str(item) for item in warnings],
        "usable_even_if_real_trace_quality_is_weak": usable,
        "manual_evidence_gaps": _dedupe(extra_gaps),
    }


def _weak_report_warnings(artifact_reports: dict[str, Any], manual_summary: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    weak_values = {
        "insufficient_evidence",
        "insufficient_trace",
        "partial_trace",
        "review_recommended",
        "do_not_trust_without_more_evidence",
    }
    for key in ("trace_contract", "derailment_score", "claim_diff_check", "manual_review"):
        status = _artifact_status_value(key, artifact_reports.get(key))
        if status in weak_values:
            warnings.append(f"{key} generated report status is {status}")
    warnings.extend(_str(item) for item in manual_summary.get("manual_review_warnings") or [])
    return _dedupe(warnings)


def _build_core_module_checks(repo: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for phase_id, rel in CORE_MODULES:
        path = repo / rel
        checks.append(
            {
                "phase_id": phase_id,
                "path": rel,
                "exists": path.is_file(),
                "source_guardrails_ok": path.is_file(),
                "issues": [] if path.is_file() else [f"{rel} is missing"],
            }
        )
    return checks


def _source_files_to_scan(repo: Path) -> list[Path]:
    rels = [rel for _, rel in CORE_MODULES] + list(SCRIPT_MODULES)
    files: list[Path] = []
    for rel in rels:
        path = repo / rel
        if path.is_file():
            files.append(path)
    return files


def _scan_source_guardrails(repo: Path) -> dict[str, Any]:
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    parse_errors: list[str] = []
    files_checked: list[str] = []
    for path in _source_files_to_scan(repo):
        files_checked.append(_norm_path(path.relative_to(repo)))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            parse_errors.append(f"{_norm_path(path)}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in _FORBIDDEN_IMPORT_ROOTS:
                        forbidden_imports.append(f"{_norm_path(path.relative_to(repo))}: {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in _FORBIDDEN_IMPORT_ROOTS:
                    forbidden_imports.append(f"{_norm_path(path.relative_to(repo))}: {root}")
            elif isinstance(node, ast.Call):
                call_name = ""
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                if call_name in _FORBIDDEN_CALL_NAMES:
                    forbidden_calls.append(f"{_norm_path(path.relative_to(repo))}: {call_name}")
    return {
        "ok": not forbidden_imports and not forbidden_calls and not parse_errors,
        "files_checked": files_checked,
        "forbidden_imports": sorted(set(forbidden_imports)),
        "forbidden_calls": sorted(set(forbidden_calls)),
        "parse_errors": parse_errors,
    }


def _excluded_live_scan_path(rel: Path) -> bool:
    norm = _norm_path(rel)
    if norm.startswith(("tests/", "docs/", ".agent/", ".git/")):
        return True
    if norm.startswith("core/mirror_tunnel") and norm.endswith(".py"):
        return True
    if norm.startswith("scripts/create_mirror_tunnel") and norm.endswith(".py"):
        return True
    return False


def _scan_live_instrumentation(repo: Path) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    for root_name in ("core", "scripts", "web", "benchmarks"):
        root = repo / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".js", ".html", ".css"}:
                continue
            try:
                rel = path.relative_to(repo)
            except ValueError:
                continue
            if _excluded_live_scan_path(rel):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "mirror_tunnel" in text or "shadow_live_trace" in text:
                matches.append({"path": _norm_path(rel), "token": "mirror_tunnel/shadow_live_trace"})
    return {
        "live_runtime_instrumentation_added": bool(matches),
        "matches": matches,
    }


def _discover_manual_artifact(repo: Path, pattern: str) -> Path | None:
    matches = sorted(repo.glob(pattern))
    return matches[-1].resolve() if matches else None


def gather_mirror_tunnel_branch_checkpoint_inputs(
    *,
    repo_path: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY,
    trace_contract_path: str | Path | None = None,
    derailment_score_path: str | Path | None = None,
    claim_diff_check_path: str | Path | None = None,
    ingestion_plan_path: str | Path | None = None,
    manual_trace_path: str | Path | None = None,
    manual_review_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read checkpoint inputs without running validation, benchmarks, or tools."""
    repo = _repo_path(repo_path)
    registry_file = _resolve(repo, registry_path)
    registry_data, registry_load_error = _load_json_object(registry_file)

    raw_paths: dict[str, str | Path | None] = {
        "trace_contract": trace_contract_path or DEFAULT_ARTIFACT_PATHS["trace_contract"],
        "derailment_score": derailment_score_path or DEFAULT_ARTIFACT_PATHS["derailment_score"],
        "claim_diff_check": claim_diff_check_path or DEFAULT_ARTIFACT_PATHS["claim_diff_check"],
        "ingestion_plan": ingestion_plan_path or DEFAULT_ARTIFACT_PATHS["ingestion_plan"],
        "manual_trace": manual_trace_path,
        "manual_review": manual_review_path,
    }
    artifact_files: dict[str, Path | None] = {
        key: _resolve(repo, value) for key, value in raw_paths.items() if value
    }
    if "manual_trace" not in artifact_files:
        artifact_files["manual_trace"] = _discover_manual_artifact(
            repo, ".agent/mirror_tunnel/manual_trace/*/mirror_tunnel_trace_contract.json"
        )
    if "manual_review" not in artifact_files:
        artifact_files["manual_review"] = _discover_manual_artifact(
            repo, ".agent/mirror_tunnel/manual_review/*/mirror_tunnel_manual_review.json"
        )

    artifact_reports: dict[str, Any] = {}
    artifact_load_errors: dict[str, str] = {}
    artifact_paths: dict[str, str] = {}
    for key in EXPECTED_REPORT_KINDS:
        path = artifact_files.get(key)
        artifact_paths[key] = _norm_path(path.relative_to(repo)) if path and path.is_relative_to(repo) else _norm_path(path or "")
        report, error = _load_json_object(path)
        artifact_reports[key] = report
        artifact_load_errors[key] = error

    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "artifact_reports": artifact_reports,
        "artifact_load_errors": artifact_load_errors,
        "artifact_paths": artifact_paths,
        "core_module_checks": _build_core_module_checks(repo),
        "source_guardrail_summary": _scan_source_guardrails(repo),
        "live_instrumentation_summary": _scan_live_instrumentation(repo),
        "repo_path": str(repo),
        "registry_path": _norm_path(registry_file or registry_path),
    }


def build_mirror_tunnel_branch_checkpoint(
    *,
    registry_data: Any = None,
    registry_load_error: str = "",
    artifact_reports: dict[str, Any] | None = None,
    artifact_load_errors: dict[str, str] | None = None,
    artifact_paths: dict[str, str] | None = None,
    core_module_checks: list[dict[str, Any]] | None = None,
    source_guardrail_summary: dict[str, Any] | None = None,
    live_instrumentation_summary: dict[str, Any] | None = None,
    report_id: str = "",
    created_at: str = "",
    repo_path: str | Path = "",
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    """Build the MIRROR.CLOSE report from already-loaded input data."""
    artifact_reports = artifact_reports or {}
    artifact_load_errors = artifact_load_errors or {}
    core_module_checks = core_module_checks or []
    source_guardrail_summary = source_guardrail_summary or {"ok": False, "forbidden_imports": [], "forbidden_calls": []}
    live_instrumentation_summary = live_instrumentation_summary or {
        "live_runtime_instrumentation_added": True,
        "matches": [{"path": "", "token": "missing live instrumentation scan"}],
    }

    phase_status = _build_phase_status(registry_data)
    artifact_evidence = _build_artifact_evidence(artifact_reports, artifact_load_errors, artifact_paths)
    manual_summary = _build_manual_pipeline_summary(
        artifact_reports,
        artifact_evidence["manual_evidence_gaps"],
    )
    weak_warnings = _weak_report_warnings(artifact_reports, manual_summary)

    blocked_reasons: list[str] = []
    if registry_load_error:
        blocked_reasons.append(f"phase registry missing or unreadable: {registry_load_error}")
    if not isinstance(registry_data, dict):
        blocked_reasons.append("phase registry data is missing")

    for check in phase_status["phase_checks"]:
        if not check["present"]:
            blocked_reasons.append(f"{check['phase_id']} is missing from the phase registry")
        elif not check["complete"]:
            blocked_reasons.append(f"{check['phase_id']} is not registered complete (status={check['status']})")
        for field in check.get("guardrail_violations") or []:
            blocked_reasons.append(f"{check['phase_id']} adds forbidden power: {field}")

    if not phase_status["this_phase_registered"]:
        blocked_reasons.append(f"{THIS_PHASE_ID} is missing from the phase registry")
    elif not phase_status["this_phase_complete"]:
        blocked_reasons.append(f"{THIS_PHASE_ID} is not registered complete")
    for field in phase_status.get("this_phase_guardrail_violations") or []:
        blocked_reasons.append(f"{THIS_PHASE_ID} adds forbidden power: {field}")

    for check in core_module_checks:
        if not check.get("exists"):
            blocked_reasons.append(f"{check.get('phase_id', '(unknown)')} core module is missing: {check.get('path', '')}")
        if not check.get("source_guardrails_ok"):
            for issue in check.get("issues") or ["source guardrail failure"]:
                blocked_reasons.append(f"{check.get('phase_id', '(unknown)')} source issue: {issue}")

    blocked_reasons.extend(artifact_evidence["missing_required_artifacts"])
    blocked_reasons.extend(artifact_evidence["artifact_guardrail_violations"])

    if not source_guardrail_summary.get("ok"):
        for item in source_guardrail_summary.get("forbidden_imports") or []:
            blocked_reasons.append(f"Mirror source imports forbidden module: {item}")
        for item in source_guardrail_summary.get("forbidden_calls") or []:
            blocked_reasons.append(f"Mirror source calls forbidden sink: {item}")
        for item in source_guardrail_summary.get("parse_errors") or []:
            blocked_reasons.append(f"Mirror source parse error: {item}")

    if live_instrumentation_summary.get("live_runtime_instrumentation_added"):
        blocked_reasons.append("live runtime instrumentation has already been added")

    manual_evidence_gaps = list(manual_summary["manual_evidence_gaps"])
    warnings = list(weak_warnings)

    if blocked_reasons:
        status = STATUS_BLOCKED
        reason = f"{len(_dedupe(blocked_reasons))} blocker(s) prevent freezing the Mirror Tunnel branch"
    elif manual_evidence_gaps:
        status = STATUS_NEEDS_MANUAL_EVIDENCE
        reason = f"{len(_dedupe(manual_evidence_gaps))} manual evidence gap(s) remain"
    elif warnings:
        status = STATUS_FROZEN_WARNINGS
        reason = "manual pipeline is complete, but current generated reports still require review"
    else:
        status = STATUS_FROZEN_COMPLETE
        reason = "MIRROR.1 through MIRROR.6 are complete and the manual evidence loop is frozen"

    freeze_decision = {
        "status": status,
        "reason": reason,
        "can_freeze_manual_branch": status in {STATUS_FROZEN_COMPLETE, STATUS_FROZEN_WARNINGS},
        "manual_review_required": status == STATUS_FROZEN_WARNINGS,
        "live_instrumentation_allowed_only_as_shadow_default_off_non_blocking": status in {
            STATUS_FROZEN_COMPLETE,
            STATUS_FROZEN_WARNINGS,
        },
    }

    guardrail_summary = {
        "phase_guardrail_fields_checked": list(PHASE_GUARDRAIL_FIELDS),
        "phase_guardrails_ok": phase_status["all_required_mirror_phase_guardrails_ok"] and phase_status["this_phase_guardrails_ok"],
        "artifact_guardrails_ok": artifact_evidence["all_artifact_guardrails_ok"],
        "source_guardrails_ok": bool(source_guardrail_summary.get("ok")),
        "no_live_runtime_instrumentation_added_yet": not live_instrumentation_summary.get("live_runtime_instrumentation_added"),
        "all_clear": not blocked_reasons,
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": _str(report_id),
        "created_at": _str(created_at),
        "repo_path": _norm_path(repo_path),
        "registry_path": _norm_path(registry_path),
        "checkpoint_status": status,
        "checkpoint_reason": reason,
        "phase_status": phase_status,
        "artifact_evidence": artifact_evidence,
        "manual_pipeline_summary": manual_summary,
        "source_guardrail_summary": source_guardrail_summary,
        "live_instrumentation_summary": live_instrumentation_summary,
        "guardrail_summary": guardrail_summary,
        "freeze_decision": freeze_decision,
        "recommended_next_phase": NEXT_PHASE,
        "recommended_next_action": "prepare_shadow_only_default_off_non_blocking_live_trace_writer",
        "manual_evidence_gaps": _dedupe(manual_evidence_gaps),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blocked_reasons),
        "guardrails": _guardrails(),
        "boundaries": list(BOUNDARIES),
    }


def _list_lines(items: Any) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["_None._"]
    return [f"- {_md(item)}" for item in items]


def render_mirror_tunnel_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render a MIRROR.CLOSE report as operator-readable Markdown."""
    lines: list[str] = [
        "# Mirror Tunnel Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status') or '(none)')}`",
        f"- **Checkpoint reason:** {_md(report.get('checkpoint_reason') or '(none)')}",
        "",
        "## Phase Status",
        "",
    ]
    phase = report.get("phase_status") if isinstance(report.get("phase_status"), dict) else {}
    lines.append(f"- **MIRROR.1-MIRROR.6 complete:** {_lower(phase.get('all_required_mirror_phases_complete'))}")
    lines.append(f"- **{THIS_PHASE_ID} registered:** {_lower(phase.get('this_phase_registered'))}")
    lines.append(f"- **{THIS_PHASE_ID} complete:** {_lower(phase.get('this_phase_complete'))}")
    checks = phase.get("phase_checks") if isinstance(phase.get("phase_checks"), list) else []
    if checks:
        lines.extend(["", "| Phase | Present | Status | Complete | Guardrails OK |", "|---|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('phase_id'))} | {_lower(check.get('present'))} | "
                f"{_md(check.get('status'))} | {_lower(check.get('complete'))} | "
                f"{_lower(check.get('guardrails_ok'))} |"
            )
    lines.append("")

    lines.extend(["## Artifact Evidence", ""])
    artifact = report.get("artifact_evidence") if isinstance(report.get("artifact_evidence"), dict) else {}
    checks = artifact.get("artifact_checks") if isinstance(artifact.get("artifact_checks"), list) else []
    if checks:
        lines.extend(["| Artifact | Present | Status | Guardrails OK | Path |", "|---|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('artifact_key'))} | {_lower(check.get('present'))} | "
                f"{_md(check.get('status'))} | {_lower(check.get('guardrails_ok'))} | "
                f"`{_md(check.get('path'))}` |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Manual Pipeline", ""])
    manual = report.get("manual_pipeline_summary") if isinstance(report.get("manual_pipeline_summary"), dict) else {}
    lines.append(f"- **Manual trace present:** {_lower(manual.get('manual_trace_present'))}")
    lines.append(f"- **Manual review present:** {_lower(manual.get('manual_review_present'))}")
    lines.append(f"- **Meaningful non-unknown frames:** {manual.get('meaningful_manual_frame_count', 0)}")
    lines.append(f"- **Usable with weak real trace quality:** {_lower(manual.get('usable_even_if_real_trace_quality_is_weak'))}")
    lines.append("")

    lines.extend(["## Live Instrumentation", ""])
    live = report.get("live_instrumentation_summary") if isinstance(report.get("live_instrumentation_summary"), dict) else {}
    lines.append(f"- **Live runtime instrumentation added:** {_lower(live.get('live_runtime_instrumentation_added'))}")
    matches = live.get("matches") if isinstance(live.get("matches"), list) else []
    if matches:
        lines.extend(f"- `{_md(item.get('path'))}`: {_md(item.get('token'))}" for item in matches if isinstance(item, dict))
    lines.append("")

    lines.extend(["## Guardrail Summary", ""])
    guardrail = report.get("guardrail_summary") if isinstance(report.get("guardrail_summary"), dict) else {}
    for key in sorted(guardrail):
        lines.append(f"- `{_md(key)}` = `{_lower(guardrail[key])}`")
    lines.append("")

    lines.extend(["## Freeze Decision", ""])
    decision = report.get("freeze_decision") if isinstance(report.get("freeze_decision"), dict) else {}
    lines.append(f"- **Status:** `{_md(decision.get('status') or '(none)')}`")
    lines.append(f"- **Can freeze manual branch:** {_lower(decision.get('can_freeze_manual_branch'))}")
    lines.append(f"- **Manual review required:** {_lower(decision.get('manual_review_required'))}")
    lines.append(
        "- **Shadow-only future work:** "
        f"{_lower(decision.get('live_instrumentation_allowed_only_as_shadow_default_off_non_blocking'))}"
    )
    lines.append("")

    lines.extend(["## Recommended Next Phase", "", f"- `{_md(report.get('recommended_next_phase') or NEXT_PHASE)}`", ""])

    lines.extend(["## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.append("")

    lines.extend(["## Blockers", ""])
    blockers = list(report.get("blockers") or []) + list(report.get("manual_evidence_gaps") or [])
    lines.extend(_list_lines(blockers))
    lines.append("")

    lines.extend(["## Boundaries", ""])
    for boundary in report.get("boundaries") or list(BOUNDARIES):
        lines.append(f"- {_md(boundary)}")
    lines.append("")
    return "\n".join(lines)


def write_mirror_tunnel_branch_checkpoint(
    *,
    repo_path: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    report_id: str = "",
    created_at: str = "",
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and write MIRROR.CLOSE JSON/Markdown artifacts."""
    raw_inputs = inputs or gather_mirror_tunnel_branch_checkpoint_inputs(
        repo_path=repo_path,
        registry_path=registry_path,
    )
    report = build_mirror_tunnel_branch_checkpoint(
        registry_data=raw_inputs.get("registry_data"),
        registry_load_error=_str(raw_inputs.get("registry_load_error")),
        artifact_reports=raw_inputs.get("artifact_reports") or {},
        artifact_load_errors=raw_inputs.get("artifact_load_errors") or {},
        artifact_paths=raw_inputs.get("artifact_paths") or {},
        core_module_checks=raw_inputs.get("core_module_checks") or [],
        source_guardrail_summary=raw_inputs.get("source_guardrail_summary") or {},
        live_instrumentation_summary=raw_inputs.get("live_instrumentation_summary") or {},
        report_id=report_id,
        created_at=created_at,
        repo_path=repo_path,
        registry_path=registry_path,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_mirror_tunnel_branch_checkpoint_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
