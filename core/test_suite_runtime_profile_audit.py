"""OPS.TEST.1 - Test Suite Runtime Profile Audit.

Defines practical test-suite runtime profiles for C.A.T.T.U.S validation. This
module is report-only: it writes local JSON and Markdown artifacts and never
runs validation, benchmarks, pytest, model calls, network calls, workers, patch
application, database writes, or production behavior changes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "test_suite_runtime_profile_audit"
THIS_PHASE_ID = "OPS.TEST.1"

STATUS_READY = "test_suite_runtime_profile_audit_ready"
STATUS_READY_WITH_WARNINGS = "test_suite_runtime_profile_audit_ready_with_warnings"
STATUS_INCOMPLETE = "test_suite_runtime_profile_audit_incomplete"
STATUS_BLOCKED = "test_suite_runtime_profile_audit_blocked"

JSON_NAME = "test_suite_runtime_profile_audit.json"
MD_NAME = "test_suite_runtime_profile_audit.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ops" / "test_suite_runtime_profile_audit"

QUICK_TIMEOUT_SECONDS = 304
FULL_TIMEOUT_SECONDS = 30 * 60

REQUIRED_PROFILE_NAMES: tuple[str, ...] = (
    "smoke",
    "phase",
    "branch",
    "registry_picker",
    "benchmark",
    "full",
    "nightly",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "OPS.TEST.2",
    "title": "Slow Test Timing Collector",
    "reason": (
        "Collect per-test-file timing data so slowest tests can be identified "
        "without deleting, hiding, or weakening coverage."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "UX.RUN.1",
    "title": "Run Progress / Operator Visibility",
    "reason": "Improve operator visibility for long-running local validation.",
}

GUARDRAIL_NOTE = (
    "OPS.TEST.1 is report-only and test-policy-only. It classifies validation "
    "commands, timeout expectations, and suite profiles without deleting tests, "
    "weakening safety coverage, changing production behavior, mutating benchmark "
    "cases, running validation, or treating a timeout as a pass."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "test policy only",
    "no test deletion",
    "no safety weakening",
    "no production behavior change",
    "no core logic change",
    "no route/auth change",
    "no model call",
    "no worker launch",
    "no patch apply",
    "no validation run",
    "no benchmark mutation",
    "no database write",
    "no network",
    "no automatic authority escalation",
)

POLICY_VIOLATION_LABELS: dict[str, str] = {
    "test_deletion_recommended": "audit recommends deleting tests",
    "safety_coverage_weakened": "audit weakens safety coverage",
    "failed_assertions_ignored": "audit ignores failed assertions",
    "timeout_treated_as_pass": "audit treats a timeout as a pass",
    "slow_tests_marked_unimportant": "audit marks slow tests as unimportant",
    "failures_hidden": "audit hides validation failures",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _default_suite_profiles() -> list[dict[str, Any]]:
    return [
        {
            "name": "smoke",
            "purpose": "Fast sanity check for syntax, registry integrity, and live recommendation reports.",
            "commands": [
                "python -m compileall -q core scripts tests benchmarks web",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
            ],
            "recommended_timeout_seconds": QUICK_TIMEOUT_SECONDS,
        },
        {
            "name": "phase",
            "purpose": "Validate the current phase and direct dependency tests only.",
            "commands": [
                "python -m pytest tests/test_<current_phase>.py -q",
                "python -m pytest tests/test_<direct_dependency>.py -q",
            ],
            "recommended_timeout_seconds": QUICK_TIMEOUT_SECONDS,
        },
        {
            "name": "branch",
            "purpose": "Validate a coherent branch chain before closing that branch.",
            "commands": [
                "python -m pytest tests/test_<branch-chain-a>.py tests/test_<branch-chain-b>.py -q",
                "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
            ],
            "examples": [
                "HARDEN.N1-N4 tests together",
                "HUMAN.N1-CLOSE tests together",
                "MODEL adoption tests together",
            ],
            "recommended_timeout_seconds": 900,
        },
        {
            "name": "registry_picker",
            "purpose": "Validate roadmap integrity and the live phase recommendation.",
            "commands": ["python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q"],
            "recommended_timeout_seconds": QUICK_TIMEOUT_SECONDS,
        },
        {
            "name": "benchmark",
            "purpose": "Validate benchmark metadata and case definitions without mutating benchmark cases.",
            "commands": ["python benchmarks/run_benchmarks.py --check"],
            "recommended_timeout_seconds": 600,
        },
        {
            "name": "full",
            "purpose": "Full verification gate for pytest coverage.",
            "commands": ["python -m pytest -q"],
            "recommended_timeout_seconds": FULL_TIMEOUT_SECONDS,
        },
        {
            "name": "nightly",
            "purpose": "Long verification profile for slow-suite visibility and broad confidence.",
            "commands": [
                "python -m pytest -q",
                "python benchmarks/run_benchmarks.py --check",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
            ],
            "optional_outputs": ["slow-test timing output"],
            "recommended_timeout_seconds": FULL_TIMEOUT_SECONDS,
        },
    ]


def _recommended_phase_gate() -> dict[str, Any]:
    return {
        "purpose": "Small phase commit gate.",
        "commands": [
            "python -m compileall -q core scripts tests benchmarks web",
            "python -m pytest tests/test_<current_phase>.py -q",
            "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
            "python benchmarks/run_benchmarks.py --check",
        ],
        "timeout_policy": "Quick gate; do not use it to claim full-suite health.",
        "full_pytest_required": False,
    }


def _recommended_branch_close_gate() -> dict[str, Any]:
    return {
        "purpose": "Branch close gate.",
        "commands": [
            "python -m pytest tests/test_<branch-chain-a>.py tests/test_<branch-chain-b>.py -q",
            "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
            "python benchmarks/run_benchmarks.py --check",
        ],
        "full_pytest_required": False,
        "full_pytest_note": "Full pytest is optional at branch close if time allows; do not call it passed unless it exits 0.",
    }


def _recommended_release_gate() -> dict[str, Any]:
    return {
        "purpose": "Release or freeze gate.",
        "commands": [
            "python -m pytest -q",
            "python benchmarks/run_benchmarks.py --check",
            "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
            "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
        ],
        "full_pytest_required": True,
        "recommended_timeout_seconds": FULL_TIMEOUT_SECONDS,
    }


def _timeout_interpretation() -> dict[str, Any]:
    return {
        "quick_timeout_seconds": QUICK_TIMEOUT_SECONDS,
        "full_timeout_seconds": FULL_TIMEOUT_SECONDS,
        "quick_timeout_on_full_suite": "full suite not completed within quick gate",
        "timeout_counts_as_pass": False,
        "full_suite_health_requires_exit_success": True,
        "timeout_report_should_include": [
            "timeout duration",
            "whether any partial failure report was produced",
            "final pytest exit status when available",
        ],
        "timeout_without_final_report": "timed out without final report",
        "partial_output_policy": "Do not claim full-suite health from partial output alone.",
    }


def _validation_reporting_policy() -> list[str]:
    return [
        "Report a 5-minute timeout on full pytest as full suite not completed within quick gate.",
        "A full-suite pass may be claimed only when python -m pytest -q exits successfully.",
        "A timeout report must include the timeout duration and whether pytest produced a partial failure report.",
        "If no final pytest report is produced, say timed out without final report.",
        "Do not claim full-suite health from partial output alone.",
        "Do not delete tests, weaken safety coverage, hide failures, or mark slow tests as unimportant.",
    ]


def _slow_suite_notes(exact_collected: bool) -> list[str]:
    notes = [
        "Known validation history indicates the full pytest suite can take about 20-25 minutes.",
        "A 304-second timeout is a quick-gate limit, not evidence that assertions failed.",
        "Exact per-test-file runtime measurements are reserved for OPS.TEST.2.",
    ]
    if exact_collected:
        notes[-1] = "Exact per-test-file runtime measurements have been collected by a later timing pass."
    return notes


def _known_runtime_estimate() -> dict[str, Any]:
    return {
        "display": "20-25 minutes",
        "minimum_minutes": 20,
        "maximum_minutes": 25,
        "source": "recent branch validation history and operator timing notes",
        "exact_per_test_runtime_measurements_collected": False,
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _policy_blockers(markers: dict[str, Any] | None) -> list[str]:
    marker_values = dict(markers or {})
    return [
        label
        for key, label in POLICY_VIOLATION_LABELS.items()
        if _truthy(marker_values.get(key, False))
    ]


def _profile_incomplete_reasons(suite_profiles: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    by_name = {
        str(profile.get("name") or ""): profile
        for profile in suite_profiles
        if isinstance(profile, dict)
    }
    missing = [name for name in REQUIRED_PROFILE_NAMES if name not in by_name]
    if missing:
        reasons.append("missing required suite profile(s): " + ", ".join(missing))

    for name in REQUIRED_PROFILE_NAMES:
        profile = by_name.get(name)
        if not profile:
            continue
        commands = profile.get("commands")
        if not isinstance(commands, list) or not all(isinstance(item, str) and item for item in commands):
            reasons.append(f"{name} profile lacks command text")
        if not str(profile.get("purpose") or "").strip():
            reasons.append(f"{name} profile lacks purpose")

    full = by_name.get("full") or {}
    full_timeout = int(full.get("recommended_timeout_seconds") or 0)
    if full and full_timeout < FULL_TIMEOUT_SECONDS:
        reasons.append("full profile timeout is below 30 minutes")
    return reasons


def _guardrails(policy_violation_markers: dict[str, Any] | None = None) -> dict[str, bool]:
    markers = dict(policy_violation_markers or {})
    return {
        "report_only": True,
        "test_policy_only": True,
        "no_test_deletion": not _truthy(markers.get("test_deletion_recommended")),
        "no_safety_weakening": not _truthy(markers.get("safety_coverage_weakened")),
        "no_failed_assertion_ignoring": not _truthy(markers.get("failed_assertions_ignored")),
        "timeout_is_not_pass": not _truthy(markers.get("timeout_treated_as_pass")),
        "slow_tests_not_marked_unimportant": not _truthy(markers.get("slow_tests_marked_unimportant")),
        "no_hidden_failures": not _truthy(markers.get("failures_hidden")),
        "no_production_behavior_change": True,
        "no_core_logic_change": True,
        "no_route_auth_change": True,
        "no_model_call": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "no_validation_run": True,
        "no_benchmark_mutation": True,
        "no_database_write": True,
        "no_network": True,
        "no_automatic_authority_escalation": True,
    }


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def build_test_suite_runtime_profile_audit(
    *,
    repo_root: str | Path = ".",
    audit_id: str = "",
    created_at: str = "",
    suite_profiles: list[dict[str, Any]] | None = None,
    validation_reporting_policy: list[str] | None = None,
    policy_violation_markers: dict[str, Any] | None = None,
    exact_per_test_runtime_measurements_collected: bool = False,
) -> dict[str, Any]:
    """Build the OPS.TEST.1 report-only runtime profile audit."""
    Path(repo_root or ".")
    profiles = list(suite_profiles) if suite_profiles is not None else _default_suite_profiles()
    policy = (
        list(validation_reporting_policy)
        if validation_reporting_policy is not None
        else _validation_reporting_policy()
    )

    blockers = _policy_blockers(policy_violation_markers)
    incomplete = _profile_incomplete_reasons(profiles)
    if not policy:
        incomplete.append("validation reporting policy is absent")

    warnings: list[str] = []
    if not exact_per_test_runtime_measurements_collected:
        warnings.append("Exact per-test runtime measurements are not yet collected; OPS.TEST.2 should collect them.")

    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    audit_status = _status(blockers, incomplete, warnings)
    estimate = _known_runtime_estimate()
    estimate["exact_per_test_runtime_measurements_collected"] = bool(exact_per_test_runtime_measurements_collected)

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "audit_id": str(audit_id or "ops-test-1-test-suite-runtime-profile-audit"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "audit_status": audit_status,
        "known_full_suite_runtime_estimate": estimate,
        "quick_timeout_seconds": QUICK_TIMEOUT_SECONDS,
        "full_timeout_seconds": FULL_TIMEOUT_SECONDS,
        "suite_profiles": profiles,
        "recommended_phase_gate": _recommended_phase_gate(),
        "recommended_branch_close_gate": _recommended_branch_close_gate(),
        "recommended_release_gate": _recommended_release_gate(),
        "known_timeout_interpretation": _timeout_interpretation(),
        "validation_reporting_policy": policy,
        "slow_suite_notes": _slow_suite_notes(exact_per_test_runtime_measurements_collected),
        "incomplete_reasons": incomplete,
        "blocked_reasons": blockers,
        "warnings": warnings,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "guardrails": _guardrails(policy_violation_markers),
        "boundaries": list(BOUNDARIES),
        "final_verdict": {
            "status": audit_status,
            "ready_for_next_phase": audit_status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Runtime profiles are defined with warnings because exact per-test timing data is not yet collected."
                if audit_status == STATUS_READY_WITH_WARNINGS
                else f"Runtime profile audit status is {audit_status}."
            ),
        },
    }


def _dict_lines(values: Any) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["_None._"]
    lines: list[str] = []
    for key in sorted(values):
        value = values[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{_md(key)}`: {_md(value)}")
    return lines


def _list_lines(values: Any) -> list[str]:
    if not isinstance(values, list) or not values:
        return ["_None._"]
    lines: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        lines.append(f"- {_md(text)}")
    return lines


def _render_gate(lines: list[str], title: str, gate: dict[str, Any]) -> None:
    lines.extend([f"## {title}", ""])
    lines.append(f"- **Purpose:** {_md(gate.get('purpose', ''))}")
    lines.append(f"- **Full pytest required:** `{_bool(gate.get('full_pytest_required'))}`")
    if gate.get("recommended_timeout_seconds"):
        lines.append(f"- **Recommended timeout:** {gate.get('recommended_timeout_seconds')} seconds")
    lines.extend(["", "**Commands:**", ""])
    lines.extend(_list_lines(gate.get("commands")))
    if gate.get("full_pytest_note"):
        lines.extend(["", f"- {_md(gate.get('full_pytest_note'))}"])
    lines.append("")


def render_test_suite_runtime_profile_audit_markdown(report: dict[str, Any]) -> str:
    """Render the OPS.TEST.1 audit report as Markdown."""
    lines: list[str] = [
        "# Test Suite Runtime Profile Audit",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Audit status:** `{_md(report.get('audit_status', ''))}`",
        f"- **Quick timeout:** {report.get('quick_timeout_seconds', 0)} seconds",
        f"- **Full timeout:** {report.get('full_timeout_seconds', 0)} seconds",
        f"- **Known full-suite runtime:** `{_md((report.get('known_full_suite_runtime_estimate') or {}).get('display', ''))}`",
        "",
        "## Suite Profiles",
        "",
    ]
    profiles = report.get("suite_profiles") if isinstance(report.get("suite_profiles"), list) else []
    if profiles:
        lines.extend(["| Profile | Purpose | Timeout | Commands |", "|---|---|---|---|"])
        for profile in profiles:
            commands = "; ".join(profile.get("commands") or [])
            lines.append(
                f"| {_md(profile.get('name'))} | {_md(profile.get('purpose'))} | "
                f"{_md(profile.get('recommended_timeout_seconds', ''))} | {_md(commands)} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    _render_gate(lines, "Phase Gate", report.get("recommended_phase_gate") or {})
    _render_gate(lines, "Branch Close Gate", report.get("recommended_branch_close_gate") or {})
    _render_gate(lines, "Release Gate", report.get("recommended_release_gate") or {})

    timeout = report.get("known_timeout_interpretation") if isinstance(report.get("known_timeout_interpretation"), dict) else {}
    lines.extend(
        [
            "## Timeout Interpretation",
            "",
            "- A 5-minute timeout on full pytest means full suite not completed within quick gate.",
            f"- **Timeout counts as pass:** `{_bool(timeout.get('timeout_counts_as_pass'))}`",
            f"- **Full-suite health requires successful exit:** `{_bool(timeout.get('full_suite_health_requires_exit_success'))}`",
            f"- **No final report wording:** `{_md(timeout.get('timeout_without_final_report', ''))}`",
            f"- **Partial output policy:** {_md(timeout.get('partial_output_policy', ''))}",
            "",
            "## Validation Reporting Policy",
            "",
        ]
    )
    lines.extend(_list_lines(report.get("validation_reporting_policy")))
    lines.extend(["", "## Slow Suite Notes", ""])
    lines.extend(_list_lines(report.get("slow_suite_notes")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(report.get("incomplete_reasons")))

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
            "## Guardrails",
            "",
        ]
    )
    lines.extend(_list_lines(report.get("boundaries")))
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_test_suite_runtime_profile_audit(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    audit_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build and write OPS.TEST.1 JSON/Markdown audit artifacts."""
    report = build_test_suite_runtime_profile_audit(
        repo_root=repo_root,
        audit_id=audit_id,
        created_at=created_at,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_test_suite_runtime_profile_audit_markdown(report), encoding="utf-8")
    return {
        "ok": report["audit_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
