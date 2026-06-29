"""HARDEN.CLOSE - Hardening Branch Checkpoint.

This module is report-only. It consolidates existing HARDEN.1, HARDEN.2, and
HARDEN.3 evidence from the phase registry, local source markers, and already
written audit artifacts. It does not call route handlers, invoke MCP tools, call
models, apply patches, run validation, run benchmarks, launch workers, execute
Dream or Replay janitor actions, contact network services, write to a database,
or change route, auth, or UI behavior. It writes only its checkpoint artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "hardening_branch_checkpoint"
THIS_PHASE_ID = "HARDEN.CLOSE"
HARDEN_PHASE_IDS: tuple[str, ...] = ("HARDEN.1", "HARDEN.2", "HARDEN.3")
DOC_PHASE_IDS: tuple[str, ...] = HARDEN_PHASE_IDS + (THIS_PHASE_ID,)

STATUS_FROZEN = "frozen"
STATUS_FROZEN_WARNINGS = "frozen_with_manual_review_warnings"
STATUS_NEEDS_HARDEN4 = "needs_harden_4"
STATUS_BLOCKED = "blocked"

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "model_calls_allowed",
    "network_allowed",
    "merge_allowed",
    "writes_real_repo",
)

JSON_NAME = "hardening_branch_checkpoint.json"
MD_NAME = "hardening_branch_checkpoint.md"

DEFAULT_REGISTRY = "docs/roadmap/phase_registry.json"
DEFAULT_HARDEN2_ARTIFACT = (
    ".agent/harden/web_mutation_surface_audit/web_mutation_surface_audit.json"
)
DEFAULT_HARDEN3_ARTIFACT = (
    ".agent/harden/safe_validation_mcp_approval_audit/"
    "safe_validation_mcp_approval_audit.json"
)

NEXT_PHASE_FREEZE = "MIRROR.1 - Mirror Tunnel Trace Contract"
NEXT_PHASE_HARDEN4 = "HARDEN.4 - Confirmed Bypass Enforcement Fix"
NEXT_PHASE_BLOCKED = "Fix missing evidence / artifact first"

GUARDRAIL_NOTE = (
    "Hardening Branch Checkpoint is report-only: it reads the phase registry, "
    "HARDEN.1 source markers, and already-written HARDEN.2/HARDEN.3 audit "
    "artifacts, then writes JSON and Markdown checkpoint artifacts. It does not "
    "call models, apply patches, run validation, run benchmarks, invoke MCP "
    "tools, launch workers, execute Dream or Replay janitor actions, use Docker "
    "or subprocess, contact network services, write to a database, change route "
    "behavior, change auth policy, change UI behavior, push, merge, open PRs, "
    "or add automation power."
)

BOUNDARIES: tuple[str, ...] = (
    "HARDEN.CLOSE is report-only.",
    "HARDEN.CLOSE does not call models.",
    "HARDEN.CLOSE does not apply patches.",
    "HARDEN.CLOSE does not run validation.",
    "HARDEN.CLOSE does not run benchmarks.",
    "HARDEN.CLOSE does not invoke MCP tools.",
    "HARDEN.CLOSE does not launch workers.",
    "HARDEN.CLOSE does not execute Dream actions.",
    "HARDEN.CLOSE does not apply Replay janitor actions.",
    "HARDEN.CLOSE does not use Docker or subprocess.",
    "HARDEN.CLOSE does not contact network services.",
    "HARDEN.CLOSE does not write to a database.",
    "HARDEN.CLOSE does not change route behavior.",
    "HARDEN.CLOSE does not change auth policy.",
    "HARDEN.CLOSE does not change UI behavior.",
    "HARDEN.CLOSE does not push, merge, or open PRs.",
    "HARDEN.CLOSE writes only its checkpoint artifacts.",
)


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/")


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _lower(value: Any) -> str:
    return str(bool(value)).lower()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except OSError as exc:
        return "", f"could not read {_norm_path(path)}: {exc}"


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    text, read_error = _read_text(path)
    if read_error:
        return None, read_error
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"could not parse {_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    root = registry_data if isinstance(registry_data, dict) else {}
    phases = root.get("phases") if isinstance(root.get("phases"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for phase in phases:
        if isinstance(phase, dict) and phase.get("phase_id"):
            out[str(phase["phase_id"])] = phase
    return out


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
    for pid in HARDEN_PHASE_IDS:
        phase = phases.get(pid)
        present = phase is not None
        complete = present and phase.get("status") == "complete"
        violations = _phase_guardrail_violations(phase) if present else []
        checks.append(
            {
                "phase_id": pid,
                "present": present,
                "status": _str(phase.get("status")) if present else "(missing)",
                "complete": complete,
                "guardrails_ok": present and not violations,
                "guardrail_violations": violations,
            }
        )

    this_phase = phases.get(THIS_PHASE_ID)
    this_present = this_phase is not None
    this_complete = this_present and this_phase.get("status") == "complete"
    this_violations = _phase_guardrail_violations(this_phase) if this_present else []

    return {
        "required_phase_ids": list(HARDEN_PHASE_IDS),
        "phase_checks": checks,
        "all_required_harden_phases_complete": all(check["complete"] for check in checks),
        "all_required_harden_phase_guardrails_ok": all(check["guardrails_ok"] for check in checks),
        "this_phase_id": THIS_PHASE_ID,
        "this_phase_registered": this_present,
        "this_phase_complete": this_complete,
        "this_phase_guardrails_ok": this_present and not this_violations,
        "this_phase_guardrail_violations": this_violations,
    }


def _detect_harden1_gate(repo_path: str | Path) -> dict[str, Any]:
    repo = Path(repo_path)
    auth_path = repo / "web" / "auth_gate.py"
    app_path = repo / "web" / "app.py"
    test_path = repo / "tests" / "test_web_mutation_auth_gate.py"

    auth_text, auth_error = _read_text(auth_path)
    app_text, app_error = _read_text(app_path)

    module_exists = auth_path.is_file() and not auth_error
    gate_function = "def should_allow_mutation" in auth_text
    before_request = "before_request" in app_text and "should_allow_mutation" in app_text
    token_or_loopback = "WEB_AUTH_TOKEN" in auth_text and "loopback" in auth_text.lower()
    test_exists = test_path.is_file()

    evidence: list[str] = []
    if module_exists:
        evidence.append("web/auth_gate.py exists")
    if gate_function:
        evidence.append("should_allow_mutation detected")
    if before_request:
        evidence.append("web/app.py before_request wiring detected")
    if token_or_loopback:
        evidence.append("WEB_AUTH_TOKEN and loopback fallback evidence detected")
    if test_exists:
        evidence.append("tests/test_web_mutation_auth_gate.py exists")

    missing = []
    if not module_exists:
        missing.append("web/auth_gate.py")
    if not gate_function:
        missing.append("should_allow_mutation")
    if not before_request:
        missing.append("before_request wiring")
    if not token_or_loopback:
        missing.append("WEB_AUTH_TOKEN/loopback evidence")
    if not test_exists:
        missing.append("tests/test_web_mutation_auth_gate.py")

    return {
        "auth_gate_module_path": _norm_path(auth_path),
        "app_path": _norm_path(app_path),
        "test_path": _norm_path(test_path),
        "auth_gate_module_exists": module_exists,
        "gate_function_detected": gate_function,
        "before_request_wiring_detected": before_request,
        "token_or_loopback_evidence": token_or_loopback,
        "test_exists": test_exists,
        "status": "present" if not missing else "missing",
        "evidence": evidence,
        "missing": missing,
        "read_errors": [error for error in (auth_error, app_error) if error],
    }


def _harden1_ready(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence.get("auth_gate_module_exists")
        and evidence.get("gate_function_detected")
        and evidence.get("before_request_wiring_detected")
        and evidence.get("token_or_loopback_evidence")
        and evidence.get("test_exists")
    )


def _artifact_guardrail_violations(source: str, report: Any) -> list[str]:
    if not isinstance(report, dict):
        return []
    guardrails = report.get("guardrails")
    if not isinstance(guardrails, dict):
        return [f"{source} artifact has no guardrails block"]
    violations: list[str] = []
    if guardrails.get("report_only") is not True:
        violations.append(f"{source} guardrail report_only is not true")
    for key, value in guardrails.items():
        if key == "report_only":
            continue
        if value is not False:
            violations.append(f"{source} guardrail {key} is not false")
    return violations


def _build_harden2_evidence(report: Any, load_error: str) -> dict[str, Any]:
    present = isinstance(report, dict) and not load_error
    route_counts = report.get("route_counts") if isinstance(report, dict) else {}
    route_counts = route_counts if isinstance(route_counts, dict) else {}
    blockers = list(report.get("blockers") or []) if isinstance(report, dict) else []
    warnings = list(report.get("warnings") or []) if isinstance(report, dict) else []
    return {
        "present": present,
        "load_error": load_error,
        "report_kind": _str(report.get("report_kind")) if isinstance(report, dict) else "",
        "verdict": _str(report.get("verdict")) if isinstance(report, dict) else "",
        "total_routes": int(route_counts.get("total") or 0),
        "mutating_routes": int(route_counts.get("mutating") or 0),
        "covered_mutating_routes": int(route_counts.get("covered_mutating") or 0),
        "uncovered_mutating_routes": int(route_counts.get("uncovered_mutating") or 0),
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "warnings_are_manual_review": bool(warnings) and not blockers,
        "warnings": warnings,
        "blockers": blockers,
        "guardrail_violations": _artifact_guardrail_violations("HARDEN.2", report),
    }


def _build_harden3_evidence(report: Any, load_error: str) -> dict[str, Any]:
    present = isinstance(report, dict) and not load_error
    counts = report.get("surface_counts") if isinstance(report, dict) else {}
    counts = counts if isinstance(counts, dict) else {}
    blockers = list(report.get("blockers") or []) if isinstance(report, dict) else []
    warnings = list(report.get("warnings") or []) if isinstance(report, dict) else []
    return {
        "present": present,
        "load_error": load_error,
        "report_kind": _str(report.get("report_kind")) if isinstance(report, dict) else "",
        "verdict": _str(report.get("verdict")) if isinstance(report, dict) else "",
        "surface_counts": counts,
        "validation_surface_count": int(counts.get("validation") or 0),
        "mcp_surface_count": int(counts.get("mcp") or 0),
        "janitor_or_cleanup_surface_count": int(counts.get("janitor_or_cleanup") or 0),
        "approval_gate_surface_count": int(counts.get("approval_gate") or 0),
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "confirmed_bypass_count": len(blockers),
        "warnings_are_manual_review": bool(warnings) and not blockers,
        "warnings": warnings,
        "blockers": blockers,
        "guardrail_violations": _artifact_guardrail_violations("HARDEN.3", report),
    }


def _warning_inventory(h2: dict[str, Any], h3: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source, evidence in (("HARDEN.2", h2), ("HARDEN.3", h3)):
        for warning in evidence.get("warnings") or []:
            items.append(
                {
                    "source": source,
                    "classification": "manual_review",
                    "message": _str(warning),
                }
            )
    return items


def _blocker_inventory(h2: dict[str, Any], h3: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source, evidence in (("HARDEN.2", h2), ("HARDEN.3", h3)):
        for blocker in evidence.get("blockers") or []:
            items.append(
                {
                    "source": source,
                    "classification": "confirmed_blocker",
                    "message": _str(blocker),
                }
            )
    return items


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "ui_behavior_changed": False,
        "push_performed": False,
        "merge_performed": False,
        "pr_opened": False,
        "automation_power_added": False,
    }


def build_hardening_branch_checkpoint(
    *,
    registry_data: Any = None,
    registry_load_error: str = "",
    harden1_gate_evidence: dict[str, Any] | None = None,
    harden2_report: dict[str, Any] | None = None,
    harden2_load_error: str = "",
    harden3_report: dict[str, Any] | None = None,
    harden3_load_error: str = "",
    report_id: str = "",
    created_at: str = "",
    repo_path: str | Path = "",
    registry_path: str | Path = DEFAULT_REGISTRY,
    harden2_artifact_path: str | Path = DEFAULT_HARDEN2_ARTIFACT,
    harden3_artifact_path: str | Path = DEFAULT_HARDEN3_ARTIFACT,
) -> dict[str, Any]:
    """Build the HARDEN.CLOSE report from already available evidence data."""
    harden1 = harden1_gate_evidence or {}
    phase_status = _build_phase_status(registry_data)
    h2 = _build_harden2_evidence(harden2_report, harden2_load_error)
    h3 = _build_harden3_evidence(harden3_report, harden3_load_error)
    warnings_inventory = _warning_inventory(h2, h3)
    blockers_inventory = _blocker_inventory(h2, h3)

    blocked_reasons: list[str] = []
    h4_reasons: list[str] = []
    phase_guardrail_violations: list[dict[str, str]] = []
    artifact_guardrail_violations: list[str] = []

    if registry_load_error:
        blocked_reasons.append(f"phase registry missing or unreadable: {registry_load_error}")
    if not isinstance(registry_data, dict):
        blocked_reasons.append("phase registry data is missing")

    for check in phase_status["phase_checks"]:
        if not check["present"]:
            blocked_reasons.append(f"{check['phase_id']} is missing from the phase registry")
        elif not check["complete"]:
            blocked_reasons.append(
                f"{check['phase_id']} is not registered complete "
                f"(status={check['status']})"
            )
        for field in check.get("guardrail_violations") or []:
            phase_guardrail_violations.append({"phase_id": check["phase_id"], "field": field})
            blocked_reasons.append(f"{check['phase_id']} adds forbidden power: {field}")

    if phase_status["this_phase_registered"]:
        if not phase_status["this_phase_complete"]:
            blocked_reasons.append(
                f"{THIS_PHASE_ID} is registered but not complete "
                f"(status={_phase_map(registry_data).get(THIS_PHASE_ID, {}).get('status')})"
            )
        for field in phase_status.get("this_phase_guardrail_violations") or []:
            phase_guardrail_violations.append({"phase_id": THIS_PHASE_ID, "field": field})
            blocked_reasons.append(f"{THIS_PHASE_ID} adds forbidden power: {field}")

    if not _harden1_ready(harden1):
        missing = ", ".join(harden1.get("missing") or ["gate evidence"])
        blocked_reasons.append(f"HARDEN.1 auth gate is not detectable: {missing}")

    if not h2["present"]:
        blocked_reasons.append(f"HARDEN.2 artifact missing or unreadable: {h2['load_error']}")
    if not h3["present"]:
        blocked_reasons.append(f"HARDEN.3 artifact missing or unreadable: {h3['load_error']}")

    if h2["uncovered_mutating_routes"] > 0:
        h4_reasons.append(
            "HARDEN.2 reports uncovered mutating routes: "
            f"{h2['uncovered_mutating_routes']}"
        )
    for blocker in h2["blockers"]:
        h4_reasons.append(f"HARDEN.2 blocker: {blocker}")
    for blocker in h3["blockers"]:
        h4_reasons.append(f"HARDEN.3 blocker: {blocker}")
    if h3["confirmed_bypass_count"] > 0:
        h4_reasons.append(
            "HARDEN.3 reports confirmed approval/validation/MCP bypass evidence"
        )

    for violation in h2["guardrail_violations"] + h3["guardrail_violations"]:
        artifact_guardrail_violations.append(violation)
        blocked_reasons.append(violation)

    warnings = [
        f"{item['source']}: {item['message']}" for item in warnings_inventory
    ]
    blockers = _dedupe(blocked_reasons + h4_reasons)

    if blocked_reasons:
        status = STATUS_BLOCKED
        reason = f"{len(_dedupe(blocked_reasons))} blocker(s) prevent the checkpoint"
    elif h4_reasons:
        status = STATUS_NEEDS_HARDEN4
        reason = f"{len(_dedupe(h4_reasons))} confirmed blocker(s) require HARDEN.4"
    elif warnings:
        status = STATUS_FROZEN_WARNINGS
        reason = (
            f"{len(_dedupe(warnings))} manual-review warning(s); "
            "the HARDEN branch can freeze with warnings"
        )
    else:
        status = STATUS_FROZEN
        reason = (
            "HARDEN.1, HARDEN.2, and HARDEN.3 evidence is complete; "
            "no blockers or manual-review warnings remain"
        )

    if status in {STATUS_FROZEN, STATUS_FROZEN_WARNINGS}:
        recommended_next_phase = NEXT_PHASE_FREEZE
        harden4_required = False
    elif status == STATUS_NEEDS_HARDEN4:
        recommended_next_phase = NEXT_PHASE_HARDEN4
        harden4_required = True
    else:
        recommended_next_phase = NEXT_PHASE_BLOCKED
        harden4_required = False

    enforcement = {
        "harden4_required": harden4_required,
        "no_enforcement_phase_justified_without_blocker": not harden4_required,
        "basis": (
            "HARDEN.4 is required only when HARDEN.2 or HARDEN.3 reports a "
            "confirmed blocker or uncovered mutating route."
        ),
        "harden4_reasons": _dedupe(h4_reasons),
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": _str(report_id),
        "created_at": _str(created_at),
        "repo_path": _norm_path(repo_path),
        "registry_path": _norm_path(registry_path),
        "harden2_artifact_path": _norm_path(harden2_artifact_path),
        "harden3_artifact_path": _norm_path(harden3_artifact_path),
        "checkpoint_status": status,
        "checkpoint_reason": reason,
        "phase_status": phase_status,
        "harden1_gate_evidence": harden1,
        "harden2_route_surface_evidence": h2,
        "harden3_validation_mcp_approval_evidence": h3,
        "warning_inventory": warnings_inventory,
        "blocker_inventory": blockers_inventory,
        "freeze_decision": {
            "status": status,
            "reason": reason,
            "can_freeze": status in {STATUS_FROZEN, STATUS_FROZEN_WARNINGS},
            "manual_review_required": status == STATUS_FROZEN_WARNINGS,
        },
        "enforcement_phase_decision": enforcement,
        "harden4_required": harden4_required,
        "recommended_next_phase": recommended_next_phase,
        "warnings": _dedupe(warnings),
        "blockers": blockers,
        "power_guardrail_summary": {
            "phase_guardrail_fields_checked": list(PHASE_GUARDRAIL_FIELDS),
            "phase_guardrail_violations": phase_guardrail_violations,
            "artifact_guardrail_violations": artifact_guardrail_violations,
            "all_clear": not phase_guardrail_violations and not artifact_guardrail_violations,
        },
        "guardrails": _guardrails(),
        "boundaries": list(BOUNDARIES),
    }


def _list_section(lines: list[str], title: str, items: list[Any]) -> None:
    lines.extend([f"## {title}", ""])
    if items:
        for item in items:
            if isinstance(item, dict):
                source = item.get("source") or item.get("phase_id") or ""
                message = item.get("message") or item.get("field") or item
                prefix = f"{source}: " if source else ""
                lines.append(f"- {_md(prefix)}{_md(message)}")
            else:
                lines.append(f"- {_md(item)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_hardening_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the HARDEN.CLOSE checkpoint as operator-readable Markdown."""
    lines: list[str] = [
        "# Hardening Branch Checkpoint",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status') or '(none)')}`",
        f"- **Checkpoint reason:** {_md(report.get('checkpoint_reason') or '(none)')}",
        f"- **HARDEN.4 required:** {_lower(report.get('harden4_required'))}",
        "",
        "## Phase Status",
        "",
    ]
    phase_status = report.get("phase_status") or {}
    lines.append(
        f"- **Required HARDEN phases complete:** "
        f"{_lower(phase_status.get('all_required_harden_phases_complete'))}"
    )
    lines.append(
        f"- **Required HARDEN guardrails ok:** "
        f"{_lower(phase_status.get('all_required_harden_phase_guardrails_ok'))}"
    )
    lines.append(
        f"- **{THIS_PHASE_ID} registered:** "
        f"{_lower(phase_status.get('this_phase_registered'))}"
    )
    lines.append(
        f"- **{THIS_PHASE_ID} complete:** "
        f"{_lower(phase_status.get('this_phase_complete'))}"
    )
    checks = phase_status.get("phase_checks") or []
    if checks:
        lines.extend(
            [
                "",
                "| Phase | Present | Status | Complete | Guardrails OK | Violations |",
                "|---|---|---|---|---|---|",
            ]
        )
        for check in checks:
            violations = ", ".join(check.get("guardrail_violations") or []) or "(none)"
            lines.append(
                f"| {_md(check.get('phase_id'))} | {_lower(check.get('present'))} | "
                f"{_md(check.get('status'))} | {_lower(check.get('complete'))} | "
                f"{_lower(check.get('guardrails_ok'))} | {_md(violations)} |"
            )
    lines.append("")

    lines.extend(["## HARDEN.1 Gate Evidence", ""])
    harden1 = report.get("harden1_gate_evidence") or {}
    lines.append(f"- **Status:** `{_md(harden1.get('status') or '(none)')}`")
    lines.append(f"- **Auth gate module exists:** {_lower(harden1.get('auth_gate_module_exists'))}")
    lines.append(f"- **Gate function detected:** {_lower(harden1.get('gate_function_detected'))}")
    lines.append(
        f"- **before_request wiring detected:** "
        f"{_lower(harden1.get('before_request_wiring_detected'))}"
    )
    lines.append(f"- **Test exists:** {_lower(harden1.get('test_exists'))}")
    if harden1.get("evidence"):
        lines.extend(["", "**Evidence:**", ""])
        lines.extend(f"- {_md(item)}" for item in harden1.get("evidence") or [])
    lines.append("")

    lines.extend(["## HARDEN.2 Route Surface Evidence", ""])
    h2 = report.get("harden2_route_surface_evidence") or {}
    lines.append(f"- **Present:** {_lower(h2.get('present'))}")
    lines.append(f"- **Verdict:** `{_md(h2.get('verdict') or '(none)')}`")
    lines.append(f"- **Mutating routes:** {h2.get('mutating_routes', 0)}")
    lines.append(f"- **Uncovered mutating routes:** {h2.get('uncovered_mutating_routes', 0)}")
    lines.append(f"- **Blockers:** {h2.get('blocker_count', 0)}")
    lines.append(f"- **Warnings:** {h2.get('warning_count', 0)}")
    lines.append("")

    lines.extend(["## HARDEN.3 Validation / MCP / Approval Evidence", ""])
    h3 = report.get("harden3_validation_mcp_approval_evidence") or {}
    lines.append(f"- **Present:** {_lower(h3.get('present'))}")
    lines.append(f"- **Verdict:** `{_md(h3.get('verdict') or '(none)')}`")
    lines.append(f"- **Validation surfaces:** {h3.get('validation_surface_count', 0)}")
    lines.append(f"- **MCP surfaces:** {h3.get('mcp_surface_count', 0)}")
    lines.append(
        f"- **Janitor / cleanup surfaces:** "
        f"{h3.get('janitor_or_cleanup_surface_count', 0)}"
    )
    lines.append(f"- **Approval gate surfaces:** {h3.get('approval_gate_surface_count', 0)}")
    lines.append(f"- **Blockers:** {h3.get('blocker_count', 0)}")
    lines.append(f"- **Warnings:** {h3.get('warning_count', 0)}")
    lines.append("")

    _list_section(lines, "Warning Inventory", list(report.get("warning_inventory") or []))
    _list_section(lines, "Blocker Inventory", list(report.get("blocker_inventory") or []))

    lines.extend(["## Freeze Decision", ""])
    decision = report.get("freeze_decision") or {}
    lines.append(f"- **Status:** `{_md(decision.get('status') or '(none)')}`")
    lines.append(f"- **Can freeze:** {_lower(decision.get('can_freeze'))}")
    lines.append(f"- **Manual review required:** {_lower(decision.get('manual_review_required'))}")
    lines.append(f"- **Reason:** {_md(decision.get('reason') or '(none)')}")
    lines.append("")

    lines.extend(["## Recommended Next Phase", ""])
    lines.append(f"- `{_md(report.get('recommended_next_phase') or '(none)')}`")
    enforcement = report.get("enforcement_phase_decision") or {}
    lines.append(
        f"- **No enforcement phase justified without blocker:** "
        f"{_lower(enforcement.get('no_enforcement_phase_justified_without_blocker'))}"
    )
    lines.append("")

    lines.extend(["## Boundaries / Guardrails", ""])
    for boundary in report.get("boundaries") or list(BOUNDARIES):
        lines.append(f"- {_md(boundary)}")
    lines.append("")
    guardrails = report.get("guardrails") or {}
    if guardrails:
        lines.extend(["| Guardrail | Value |", "|---|---|"])
        for key, value in sorted(guardrails.items()):
            lines.append(f"| `{_md(key)}` | {_lower(value)} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def gather_hardening_branch_checkpoint_inputs(
    *,
    repo_path: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY,
    harden2_artifact_path: str | Path = DEFAULT_HARDEN2_ARTIFACT,
    harden3_artifact_path: str | Path = DEFAULT_HARDEN3_ARTIFACT,
    report_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Read registry/source/artifact evidence without executing audited surfaces."""
    registry_data, registry_load_error = _load_json_object(Path(registry_path))
    harden2_report, harden2_load_error = _load_json_object(Path(harden2_artifact_path))
    harden3_report, harden3_load_error = _load_json_object(Path(harden3_artifact_path))
    return {
        "registry_data": registry_data,
        "registry_load_error": registry_load_error,
        "harden1_gate_evidence": _detect_harden1_gate(repo_path),
        "harden2_report": harden2_report,
        "harden2_load_error": harden2_load_error,
        "harden3_report": harden3_report,
        "harden3_load_error": harden3_load_error,
        "report_id": report_id,
        "created_at": created_at,
        "repo_path": repo_path,
        "registry_path": registry_path,
        "harden2_artifact_path": harden2_artifact_path,
        "harden3_artifact_path": harden3_artifact_path,
    }


def write_hardening_branch_checkpoint(
    *,
    repo_path: str | Path,
    registry_path: str | Path,
    harden2_artifact_path: str | Path,
    harden3_artifact_path: str | Path,
    output_dir: str | Path,
    report_id: str = "",
    created_at: str = "",
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the checkpoint and write JSON/Markdown artifacts."""
    raw_inputs = inputs or gather_hardening_branch_checkpoint_inputs(
        repo_path=repo_path,
        registry_path=registry_path,
        harden2_artifact_path=harden2_artifact_path,
        harden3_artifact_path=harden3_artifact_path,
        report_id=report_id,
        created_at=created_at,
    )
    report = build_hardening_branch_checkpoint(
        registry_data=raw_inputs.get("registry_data"),
        registry_load_error=_str(raw_inputs.get("registry_load_error")),
        harden1_gate_evidence=raw_inputs.get("harden1_gate_evidence") or {},
        harden2_report=raw_inputs.get("harden2_report"),
        harden2_load_error=_str(raw_inputs.get("harden2_load_error")),
        harden3_report=raw_inputs.get("harden3_report"),
        harden3_load_error=_str(raw_inputs.get("harden3_load_error")),
        report_id=report_id,
        created_at=created_at,
        repo_path=repo_path,
        registry_path=registry_path,
        harden2_artifact_path=harden2_artifact_path,
        harden3_artifact_path=harden3_artifact_path,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(render_hardening_branch_checkpoint_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
