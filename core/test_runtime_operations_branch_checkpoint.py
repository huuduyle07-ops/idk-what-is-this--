"""OPS.TEST.CLOSE - Test Runtime Operations Branch Checkpoint.

Builds a report-only checkpoint for the completed OPS.TEST.1 through
OPS.TEST.3 planning branch. The checkpoint reads the phase registry and the
three existing OPS.TEST artifacts, then verifies completion, safety policy,
non-execution boundaries, and the next recommended phase.

It does not execute tests, create executable manifests, add runner behavior,
delete or skip tests, weaken coverage, change production behavior, call models,
launch workers, apply patches, contact the network, write a database, or mutate
benchmarks.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "test_runtime_operations_branch_checkpoint"
THIS_PHASE_ID = "OPS.TEST.CLOSE"

STATUS_FROZEN = "test_runtime_operations_branch_frozen"
STATUS_FROZEN_WITH_WARNINGS = "test_runtime_operations_branch_frozen_with_warnings"
STATUS_INCOMPLETE = "test_runtime_operations_branch_incomplete"
STATUS_BLOCKED = "test_runtime_operations_branch_blocked"

JSON_NAME = "test_runtime_operations_branch_checkpoint.json"
MD_NAME = "test_runtime_operations_branch_checkpoint.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ops" / "test_runtime_operations_branch_checkpoint"

DEFAULT_REGISTRY_PATH = Path("docs") / "roadmap" / "phase_registry.json"
DEFAULT_RUNTIME_PROFILE_AUDIT_PATH = (
    Path(".agent")
    / "ops"
    / "test_suite_runtime_profile_audit"
    / "test_suite_runtime_profile_audit.json"
)
DEFAULT_SLOW_TIMING_REPORT_PATH = (
    Path(".agent")
    / "ops"
    / "slow_test_timing_collector"
    / "slow_test_timing_report.json"
)
DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH = (
    Path(".agent")
    / "ops"
    / "test_suite_split_manifest_plan"
    / "test_suite_split_manifest_plan.json"
)

REQUIRED_PHASE_IDS: tuple[str, ...] = ("OPS.TEST.1", "OPS.TEST.2", "OPS.TEST.3")
REQUIRED_RUNTIME_PROFILE_NAMES: tuple[str, ...] = (
    "smoke",
    "phase",
    "branch",
    "registry_picker",
    "benchmark",
    "full",
    "nightly",
)
REQUIRED_MANIFEST_PROFILE_IDS: tuple[str, ...] = (
    "smoke",
    "phase",
    "branch",
    "registry_picker",
    "benchmark",
    "full",
    "nightly",
    "release_freeze",
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "UX.RUN.1",
    "title": "Run Progress / Operator Visibility",
    "reason": (
        "After test-runtime planning is closed, the next practical product "
        "improvement is making C.A.T.T.U.S less silent during runs."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "OPS.TEST.4",
    "title": "Executable Suite Manifest Design",
    "reason": "Continue test operations only when executable suite design is the explicit priority.",
}

GUARDRAIL_NOTE = (
    "OPS.TEST.CLOSE is report-only and checkpoint-only. It verifies the "
    "OPS.TEST.1-OPS.TEST.3 planning branch without deleting tests, skipping "
    "tests, weakening coverage, changing production behavior, adding executable "
    "test runner behavior, calling models, launching workers, applying patches, "
    "mutating benchmarks, writing databases, contacting networks, or escalating "
    "authority."
)

GUARDRAILS: tuple[str, ...] = (
    "report-only",
    "checkpoint only",
    "no test deletion",
    "no test skipping behavior",
    "no coverage weakening",
    "no production behavior change",
    "no route/auth change",
    "no model call",
    "no worker launch",
    "no patch apply",
    "no benchmark mutation",
    "no database write",
    "no network",
    "no automatic authority escalation",
    "no executable test runner changes",
)

POLICY_VIOLATION_LABELS: dict[str, str] = {
    "test_deletion_recommended": "branch recommends deleting tests",
    "safety_coverage_weakened": "branch weakens safety coverage",
    "coverage_weakened": "branch weakens test coverage",
    "test_skipping_behavior_added": "branch adds test skipping behavior",
    "automatic_test_skipping_added": "branch adds automatic test skipping behavior",
    "timeout_treated_as_pass": "branch treats timeout as pass",
    "failures_hidden": "branch hides validation failures",
    "hidden_failure_policy": "branch has a hidden failure policy",
    "slow_tests_silently_excluded": "branch silently excludes slow tests from full/nightly",
    "production_behavior_mutated": "branch changes production behavior",
    "executable_runner_behavior_added": "branch adds executable test runner behavior unexpectedly",
}

PHASE_GUARDRAIL_FIELDS: tuple[str, ...] = (
    "merge_allowed",
    "network_allowed",
    "model_calls_allowed",
    "writes_real_repo",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        text = str(item)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _status_from(report: Any, fields: tuple[str, ...]) -> str:
    data = _as_dict(report)
    for field in fields:
        value = data.get(field)
        if value is not None:
            return str(value)
    return ""


def _source_warnings(report: Any) -> list[str]:
    return [str(item) for item in _as_list(_as_dict(report).get("warnings")) if str(item)]


def _source_blockers(report: Any) -> list[str]:
    return [str(item) for item in _as_list(_as_dict(report).get("blocked_reasons")) if str(item)]


def _source_incomplete(report: Any) -> list[str]:
    return [str(item) for item in _as_list(_as_dict(report).get("incomplete_reasons")) if str(item)]


def _phase_map(registry_data: Any) -> dict[str, dict[str, Any]]:
    phases = _as_list(_as_dict(registry_data).get("phases"))
    out: dict[str, dict[str, Any]] = {}
    for phase in phases:
        if isinstance(phase, dict) and phase.get("phase_id"):
            out[str(phase["phase_id"])] = phase
    return out


def _phase_completion_summary(
    registry_data: Any,
    registry_load_error: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    blockers: list[str] = []
    if registry_load_error:
        incomplete.append(f"phase registry could not be loaded: {registry_load_error}")

    phases = _phase_map(registry_data)
    checks: list[dict[str, Any]] = []
    for phase_id in REQUIRED_PHASE_IDS:
        phase = phases.get(phase_id)
        present = phase is not None
        status = str(phase.get("status", "")) if phase else "(missing)"
        complete = present and status == "complete"
        violations = [field for field in PHASE_GUARDRAIL_FIELDS if phase and phase.get(field) is True]
        guardrails_ok = present and not violations
        if not present:
            incomplete.append(f"{phase_id} is missing from phase registry")
        elif not complete:
            incomplete.append(f"{phase_id} is {status}, expected complete")
        if violations:
            blockers.append(f"{phase_id} has guardrail violation(s): {', '.join(violations)}")
        checks.append(
            {
                "phase_id": phase_id,
                "present": present,
                "status": status,
                "complete": complete,
                "guardrails_ok": guardrails_ok,
                "guardrail_violations": violations,
            }
        )

    checkpoint_phase = phases.get(THIS_PHASE_ID)
    summary = {
        "required_phase_ids": list(REQUIRED_PHASE_IDS),
        "phase_checks": checks,
        "all_required_phases_complete": all(item["complete"] for item in checks),
        "all_required_phase_guardrails_ok": all(item["guardrails_ok"] for item in checks),
        "checkpoint_phase_registered": checkpoint_phase is not None,
        "checkpoint_phase_status": str(checkpoint_phase.get("status", "")) if checkpoint_phase else "(missing)",
        "checkpoint_phase_complete": bool(checkpoint_phase and checkpoint_phase.get("status") == "complete"),
    }
    return summary, incomplete, blockers


def _artifact_check(
    *,
    artifact_id: str,
    path: str | Path,
    report: Any,
    load_error: str,
    expected_phase_id: str,
    expected_report_kind: str,
    status_fields: tuple[str, ...],
) -> tuple[dict[str, Any], list[str], list[str]]:
    incomplete: list[str] = []
    blockers: list[str] = []
    data = _as_dict(report)
    present = bool(data) and not load_error
    status = _status_from(data, status_fields)
    report_kind = str(data.get("report_kind", "")) if data else ""
    phase_id = str(data.get("phase_id", "")) if data else ""
    if not present:
        incomplete.append(f"{artifact_id} artifact is missing or unreadable: {load_error or _norm_path(path)}")
    else:
        if phase_id != expected_phase_id:
            incomplete.append(f"{artifact_id} artifact phase_id is {phase_id or '(missing)'}, expected {expected_phase_id}")
        if report_kind != expected_report_kind:
            incomplete.append(
                f"{artifact_id} artifact report_kind is {report_kind or '(missing)'}, expected {expected_report_kind}"
            )
        if status.endswith("_blocked"):
            blockers.append(f"{artifact_id} artifact is blocked: {status}")
        if status.endswith("_incomplete"):
            incomplete.append(f"{artifact_id} artifact is incomplete: {status}")
        for reason in _source_blockers(data):
            blockers.append(f"{artifact_id} artifact blocked reason: {reason}")
        for reason in _source_incomplete(data):
            incomplete.append(f"{artifact_id} artifact incomplete reason: {reason}")

    return (
        {
            "artifact_id": artifact_id,
            "path": _norm_path(path),
            "present": present,
            "load_error": str(load_error or ""),
            "phase_id": phase_id,
            "report_kind": report_kind,
            "status": status,
        },
        incomplete,
        blockers,
    )


def _artifact_coverage(
    *,
    source_runtime_profile_audit_path: str | Path,
    source_runtime_profile_audit: Any,
    source_runtime_profile_audit_load_error: str,
    source_slow_timing_report_path: str | Path,
    source_slow_timing_report: Any,
    source_slow_timing_report_load_error: str,
    source_suite_split_manifest_plan_path: str | Path,
    source_suite_split_manifest_plan: Any,
    source_suite_split_manifest_plan_load_error: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    incomplete: list[str] = []
    blockers: list[str] = []
    specs = (
        {
            "artifact_id": "runtime_profile_audit",
            "path": source_runtime_profile_audit_path,
            "report": source_runtime_profile_audit,
            "load_error": source_runtime_profile_audit_load_error,
            "expected_phase_id": "OPS.TEST.1",
            "expected_report_kind": "test_suite_runtime_profile_audit",
            "status_fields": ("audit_status",),
        },
        {
            "artifact_id": "slow_timing_report",
            "path": source_slow_timing_report_path,
            "report": source_slow_timing_report,
            "load_error": source_slow_timing_report_load_error,
            "expected_phase_id": "OPS.TEST.2",
            "expected_report_kind": "slow_test_timing_report",
            "status_fields": ("report_status",),
        },
        {
            "artifact_id": "suite_split_manifest_plan",
            "path": source_suite_split_manifest_plan_path,
            "report": source_suite_split_manifest_plan,
            "load_error": source_suite_split_manifest_plan_load_error,
            "expected_phase_id": "OPS.TEST.3",
            "expected_report_kind": "test_suite_split_manifest_plan",
            "status_fields": ("plan_status",),
        },
    )
    for spec in specs:
        check, item_incomplete, item_blockers = _artifact_check(**spec)
        checks.append(check)
        incomplete.extend(item_incomplete)
        blockers.extend(item_blockers)
    return (
        {
            "checks": checks,
            "all_required_artifacts_present": all(item["present"] for item in checks),
            "all_required_artifacts_ready": all(
                item["present"] and not item["status"].endswith("_incomplete") and not item["status"].endswith("_blocked")
                for item in checks
            ),
        },
        incomplete,
        blockers,
    )


def _profile_names(report: Any) -> set[str]:
    return {
        str(item.get("name", ""))
        for item in _as_list(_as_dict(report).get("suite_profiles"))
        if isinstance(item, dict)
    }


def _manifest_profile_ids(report: Any) -> set[str]:
    return {
        str(item.get("profile_id", ""))
        for item in _as_list(_as_dict(report).get("manifest_profiles"))
        if isinstance(item, dict)
    }


def _profile_coverage(runtime_profile_audit: Any, suite_split_manifest_plan: Any) -> tuple[dict[str, Any], list[str]]:
    runtime_names = _profile_names(runtime_profile_audit)
    manifest_ids = _manifest_profile_ids(suite_split_manifest_plan)
    missing_runtime = [name for name in REQUIRED_RUNTIME_PROFILE_NAMES if name not in runtime_names]
    missing_manifest = [name for name in REQUIRED_MANIFEST_PROFILE_IDS if name not in manifest_ids]
    incomplete: list[str] = []
    if missing_runtime:
        incomplete.append("runtime profile artifact is missing required profile(s): " + ", ".join(missing_runtime))
    if missing_manifest:
        incomplete.append("suite manifest plan is missing required profile(s): " + ", ".join(missing_manifest))
    return (
        {
            "required_runtime_profiles": list(REQUIRED_RUNTIME_PROFILE_NAMES),
            "runtime_profiles": sorted(runtime_names),
            "missing_runtime_profiles": missing_runtime,
            "runtime_profiles_exist": not missing_runtime,
            "required_manifest_profiles": list(REQUIRED_MANIFEST_PROFILE_IDS),
            "manifest_profiles": sorted(manifest_ids),
            "missing_manifest_profiles": missing_manifest,
            "manifest_profiles_exist": not missing_manifest,
            "all_required_profiles_present": not missing_runtime and not missing_manifest,
        },
        incomplete,
    )


def _timing_collector_summary(slow_timing_report: Any) -> dict[str, Any]:
    report = _as_dict(slow_timing_report)
    return {
        "slow_timing_collector_exists": bool(report),
        "report_status": _status_from(report, ("report_status",)),
        "timing_source_type": str(report.get("timing_source_type", "")),
        "collected_test_count": int(report.get("collected_test_count") or 0),
        "collected_file_count": int(report.get("collected_file_count") or 0),
        "slowest_file_count": len(_as_list(report.get("slowest_files"))),
        "timeout_interpretation_present": isinstance(report.get("timeout_interpretation"), dict),
        "collector_report_only": bool(_as_dict(report.get("guardrails")).get("report_only")),
        "collector_does_not_execute_pytest": bool(_as_dict(report.get("guardrails")).get("cli_does_not_execute_pytest")),
    }


def _suite_manifest_summary(suite_split_manifest_plan: Any) -> dict[str, Any]:
    plan = _as_dict(suite_split_manifest_plan)
    guardrails = _as_dict(plan.get("guardrails"))
    warnings = _source_warnings(plan)
    executable_future = any("executable manifest" in item.lower() for item in warnings)
    return {
        "suite_manifest_plan_exists": bool(plan),
        "plan_status": _status_from(plan, ("plan_status",)),
        "manifest_profile_count": len(_as_list(plan.get("manifest_profiles"))),
        "command_template_count": len(_as_list(plan.get("profile_command_templates"))),
        "timeout_policy_present": isinstance(plan.get("timeout_policy"), dict) and bool(plan.get("timeout_policy")),
        "failure_reporting_policy_present": isinstance(plan.get("failure_reporting_policy"), dict)
        and bool(plan.get("failure_reporting_policy")),
        "executable_manifest_files_future_work": executable_future,
        "future_boundary_explicit": executable_future or bool(guardrails.get("no_executable_test_runner_changes")),
        "no_executable_runner_added": bool(guardrails.get("no_executable_test_runner_changes")),
    }


def _timeout_policy_summary(
    runtime_profile_audit: Any,
    slow_timing_report: Any,
    suite_split_manifest_plan: Any,
) -> tuple[dict[str, Any], list[str], list[str]]:
    runtime = _as_dict(runtime_profile_audit)
    timing = _as_dict(slow_timing_report)
    manifest = _as_dict(suite_split_manifest_plan)
    runtime_timeout = _as_dict(runtime.get("known_timeout_interpretation"))
    timing_timeout = _as_dict(timing.get("timeout_interpretation"))
    manifest_timeout = _as_dict(manifest.get("timeout_policy"))
    failure_policy = _as_dict(manifest.get("failure_reporting_policy"))

    full_timeout = _as_dict(manifest_timeout.get("full")).get("recommended_timeout_seconds")
    nightly_timeout = _as_dict(manifest_timeout.get("nightly")).get("recommended_timeout_seconds")
    release_timeout = _as_dict(manifest_timeout.get("release_freeze")).get("recommended_timeout_seconds")
    explicit = all(int(value or 0) >= 1800 for value in (full_timeout, nightly_timeout, release_timeout))

    timeout_false_values = [
        runtime_timeout.get("timeout_counts_as_pass"),
        timing_timeout.get("timeout_counts_as_pass"),
        failure_policy.get("timeout_is_pass"),
    ]
    timeout_is_pass_seen = any(value is True for value in timeout_false_values)
    timeout_is_not_pass = all(value is False for value in timeout_false_values)
    full_success_required = (
        runtime_timeout.get("full_suite_health_requires_exit_success") is True
        and timing_timeout.get("full_suite_health_requires_exit_success") is True
        and failure_policy.get("full_suite_pass_requires_successful_pytest_exit") is True
    )
    incomplete: list[str] = []
    blockers: list[str] = []
    if not manifest_timeout:
        incomplete.append("timeout policy is missing from suite manifest plan")
    if not explicit:
        incomplete.append("full/nightly/release timeout policy is not explicit at 1800 seconds or more")
    if not timeout_is_not_pass:
        if timeout_is_pass_seen:
            blockers.append("timeout is treated as pass")
        else:
            incomplete.append("timeout-is-not-pass policy cannot be verified")
    if not full_success_required:
        incomplete.append("full pytest pass policy cannot be verified as requiring successful pytest exit")
    return (
        {
            "quick_timeout_seconds": int(runtime.get("quick_timeout_seconds") or 0),
            "full_timeout_seconds": int(runtime.get("full_timeout_seconds") or 0),
            "manifest_full_timeout_seconds": int(full_timeout or 0),
            "manifest_nightly_timeout_seconds": int(nightly_timeout or 0),
            "manifest_release_freeze_timeout_seconds": int(release_timeout or 0),
            "full_timeout_policy_explicit": explicit,
            "timeout_is_not_pass": timeout_is_not_pass,
            "full_pytest_pass_requires_successful_exit": full_success_required,
            "partial_output_cannot_claim_full_suite_health": failure_policy.get(
                "partial_output_can_claim_full_suite_health"
            )
            is False,
            "timeout_without_final_report": str(
                runtime_timeout.get("timeout_without_final_report")
                or timing_timeout.get("timeout_without_final_report")
                or ""
            ),
        },
        incomplete,
        blockers,
    )


def _failure_reporting_policy_summary(
    runtime_profile_audit: Any,
    suite_split_manifest_plan: Any,
) -> tuple[dict[str, Any], list[str], list[str]]:
    runtime = _as_dict(runtime_profile_audit)
    manifest = _as_dict(suite_split_manifest_plan)
    policy = _as_dict(manifest.get("failure_reporting_policy"))
    validation_policy_text = " ".join(str(item) for item in _as_list(runtime.get("validation_reporting_policy"))).lower()
    guardrails = _as_dict(manifest.get("guardrails"))

    failed_assertions_are_failures = policy.get("failed_assertions_are_failures") is True
    timeout_is_not_pass = policy.get("timeout_is_pass") is False
    full_requires_success = policy.get("full_suite_pass_requires_successful_pytest_exit") is True
    hidden_failure_policy_absent = bool(guardrails.get("no_hidden_failures")) and "hide failures" in validation_policy_text
    partial_output_policy = policy.get("partial_output_can_claim_full_suite_health") is False
    verified = (
        bool(policy)
        and failed_assertions_are_failures
        and timeout_is_not_pass
        and full_requires_success
        and hidden_failure_policy_absent
        and partial_output_policy
    )
    incomplete: list[str] = []
    blockers: list[str] = []
    if not policy:
        incomplete.append("failure reporting policy is missing from suite manifest plan")
    elif not verified:
        if policy.get("timeout_is_pass") is True:
            blockers.append("failure reporting policy treats timeout as pass")
        if policy.get("partial_output_can_claim_full_suite_health") is True:
            blockers.append("failure reporting policy allows partial output to claim full-suite health")
        if guardrails.get("no_hidden_failures") is False:
            blockers.append("failure reporting policy allows hidden failures")
        if not blockers:
            incomplete.append("failure reporting policy cannot be fully verified")
    return (
        {
            "policy_present": bool(policy),
            "failed_assertions_are_failures": failed_assertions_are_failures,
            "timeout_is_not_pass": timeout_is_not_pass,
            "full_pytest_pass_requires_successful_exit": full_requires_success,
            "partial_output_cannot_claim_full_suite_health": partial_output_policy,
            "hidden_failure_policy_absent": hidden_failure_policy_absent,
            "verified": verified,
        },
        incomplete,
        blockers,
    )


def _all_guardrails_true(reports: tuple[Any, ...], keys: tuple[str, ...]) -> bool:
    for report in reports:
        guardrails = _as_dict(_as_dict(report).get("guardrails"))
        for key in keys:
            if guardrails.get(key) is False:
                return False
    return True


def _no_weakening_verification(
    runtime_profile_audit: Any,
    slow_timing_report: Any,
    suite_split_manifest_plan: Any,
    markers: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    reports = (runtime_profile_audit, slow_timing_report, suite_split_manifest_plan)
    no_test_deletion = _all_guardrails_true(reports, ("no_test_deletion",)) and not _truthy(
        markers.get("test_deletion_recommended")
    )
    no_coverage_weakening = (
        _all_guardrails_true((runtime_profile_audit, slow_timing_report), ("no_safety_weakening",))
        and _all_guardrails_true((suite_split_manifest_plan,), ("no_coverage_weakening",))
        and not _truthy(markers.get("safety_coverage_weakened"))
        and not _truthy(markers.get("coverage_weakened"))
    )
    no_hidden_failure_policy = _all_guardrails_true(reports, ("no_hidden_failures",)) and not _truthy(
        markers.get("hidden_failure_policy")
    ) and not _truthy(markers.get("failures_hidden"))
    no_silent_slow_test_exclusion = _all_guardrails_true(
        (suite_split_manifest_plan,), ("no_silent_slow_test_exclusion",)
    ) and not _truthy(markers.get("slow_tests_silently_excluded"))
    no_production_behavior_change = _all_guardrails_true(
        reports, ("no_production_behavior_change",)
    ) and not _truthy(markers.get("production_behavior_mutated"))
    no_test_skipping_behavior = _all_guardrails_true(
        (suite_split_manifest_plan,), ("no_test_skipping_behavior",)
    ) and not _truthy(markers.get("test_skipping_behavior_added")) and not _truthy(
        markers.get("automatic_test_skipping_added")
    )

    checks = {
        "no_test_deletion": no_test_deletion,
        "no_test_skipping_behavior": no_test_skipping_behavior,
        "no_coverage_weakening": no_coverage_weakening,
        "no_hidden_failure_policy": no_hidden_failure_policy,
        "no_silent_slow_test_exclusion": no_silent_slow_test_exclusion,
        "no_production_behavior_change": no_production_behavior_change,
    }
    blockers = [key.replace("_", " ") + " verification failed" for key, value in checks.items() if not value]
    checks["all_clear"] = not blockers
    return checks, blockers


def _non_execution_verification(
    runtime_profile_audit: Any,
    slow_timing_report: Any,
    suite_split_manifest_plan: Any,
    markers: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    reports = (runtime_profile_audit, slow_timing_report, suite_split_manifest_plan)
    report_only = _all_guardrails_true(reports, ("report_only",))
    no_model_call = _all_guardrails_true(reports, ("no_model_call",))
    no_worker_launch = _all_guardrails_true(reports, ("no_worker_launch",))
    no_patch_apply = _all_guardrails_true(reports, ("no_patch_apply",))
    no_benchmark_mutation = _all_guardrails_true(reports, ("no_benchmark_mutation",))
    no_database_write = _all_guardrails_true(reports, ("no_database_write",))
    no_network = _all_guardrails_true(reports, ("no_network",))
    no_authority_escalation = _all_guardrails_true(reports, ("no_automatic_authority_escalation",))
    no_executable_runner = _all_guardrails_true(
        (suite_split_manifest_plan,), ("no_executable_test_runner_changes",)
    ) and not _truthy(markers.get("executable_runner_behavior_added"))

    checks = {
        "report_only": report_only,
        "checkpoint_only": True,
        "no_model_call": no_model_call,
        "no_worker_launch": no_worker_launch,
        "no_patch_apply": no_patch_apply,
        "no_benchmark_mutation": no_benchmark_mutation,
        "no_database_write": no_database_write,
        "no_network": no_network,
        "no_automatic_authority_escalation": no_authority_escalation,
        "no_executable_test_runner_changes": no_executable_runner,
        "no_validation_run": bool(_as_dict(_as_dict(runtime_profile_audit).get("guardrails")).get("no_validation_run", True)),
        "collector_does_not_execute_pytest": bool(
            _as_dict(_as_dict(slow_timing_report).get("guardrails")).get("cli_does_not_execute_pytest", True)
        ),
    }
    blockers = [key.replace("_", " ") + " verification failed" for key, value in checks.items() if not value]
    checks["all_clear"] = not blockers
    return checks, blockers


def _policy_blockers(markers: dict[str, Any]) -> list[str]:
    return [
        label
        for key, label in POLICY_VIOLATION_LABELS.items()
        if _truthy(markers.get(key))
    ]


def _guardrails(
    no_weakening: dict[str, Any],
    non_execution: dict[str, Any],
) -> dict[str, bool]:
    return {
        "report_only": bool(non_execution.get("report_only")),
        "checkpoint_only": True,
        "no_test_deletion": bool(no_weakening.get("no_test_deletion")),
        "no_test_skipping_behavior": bool(no_weakening.get("no_test_skipping_behavior")),
        "no_coverage_weakening": bool(no_weakening.get("no_coverage_weakening")),
        "no_production_behavior_change": bool(no_weakening.get("no_production_behavior_change")),
        "no_route_auth_change": True,
        "no_model_call": bool(non_execution.get("no_model_call")),
        "no_worker_launch": bool(non_execution.get("no_worker_launch")),
        "no_patch_apply": bool(non_execution.get("no_patch_apply")),
        "no_benchmark_mutation": bool(non_execution.get("no_benchmark_mutation")),
        "no_database_write": bool(non_execution.get("no_database_write")),
        "no_network": bool(non_execution.get("no_network")),
        "no_automatic_authority_escalation": bool(non_execution.get("no_automatic_authority_escalation")),
        "no_executable_test_runner_changes": bool(non_execution.get("no_executable_test_runner_changes")),
    }


def _checkpoint_status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_FROZEN_WITH_WARNINGS
    return STATUS_FROZEN


def build_test_runtime_operations_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_data: Any = None,
    registry_load_error: str = "",
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_runtime_profile_audit: Any = None,
    source_runtime_profile_audit_load_error: str = "",
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
    source_slow_timing_report: Any = None,
    source_slow_timing_report_load_error: str = "",
    source_suite_split_manifest_plan_path: str | Path = DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH,
    source_suite_split_manifest_plan: Any = None,
    source_suite_split_manifest_plan_load_error: str = "",
    checkpoint_id: str = "",
    created_at: str = "",
    policy_violation_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the report-only OPS.TEST.CLOSE checkpoint record."""
    Path(repo_root or ".")
    markers = dict(policy_violation_markers or {})

    phase_summary, phase_incomplete, phase_blockers = _phase_completion_summary(
        registry_data, registry_load_error
    )
    artifact_coverage, artifact_incomplete, artifact_blockers = _artifact_coverage(
        source_runtime_profile_audit_path=source_runtime_profile_audit_path,
        source_runtime_profile_audit=source_runtime_profile_audit,
        source_runtime_profile_audit_load_error=source_runtime_profile_audit_load_error,
        source_slow_timing_report_path=source_slow_timing_report_path,
        source_slow_timing_report=source_slow_timing_report,
        source_slow_timing_report_load_error=source_slow_timing_report_load_error,
        source_suite_split_manifest_plan_path=source_suite_split_manifest_plan_path,
        source_suite_split_manifest_plan=source_suite_split_manifest_plan,
        source_suite_split_manifest_plan_load_error=source_suite_split_manifest_plan_load_error,
    )
    profile_coverage, profile_incomplete = _profile_coverage(
        source_runtime_profile_audit, source_suite_split_manifest_plan
    )
    timing_summary = _timing_collector_summary(source_slow_timing_report)
    suite_summary = _suite_manifest_summary(source_suite_split_manifest_plan)
    timeout_summary, timeout_incomplete, timeout_blockers = _timeout_policy_summary(
        source_runtime_profile_audit,
        source_slow_timing_report,
        source_suite_split_manifest_plan,
    )
    failure_summary, failure_incomplete, failure_blockers = _failure_reporting_policy_summary(
        source_runtime_profile_audit,
        source_suite_split_manifest_plan,
    )
    no_weakening, weakening_blockers = _no_weakening_verification(
        source_runtime_profile_audit,
        source_slow_timing_report,
        source_suite_split_manifest_plan,
        markers,
    )
    non_execution, execution_blockers = _non_execution_verification(
        source_runtime_profile_audit,
        source_slow_timing_report,
        source_suite_split_manifest_plan,
        markers,
    )

    warnings = (
        _source_warnings(source_runtime_profile_audit)
        + _source_warnings(source_slow_timing_report)
        + _source_warnings(source_suite_split_manifest_plan)
    )
    if suite_summary["executable_manifest_files_future_work"]:
        warnings.append("Executable suite manifests and runner commands are intentionally future work.")
    warnings = _dedupe(warnings)

    incomplete = _dedupe(
        phase_incomplete
        + artifact_incomplete
        + profile_incomplete
        + timeout_incomplete
        + failure_incomplete
    )
    blockers = _dedupe(
        _policy_blockers(markers)
        + phase_blockers
        + artifact_blockers
        + timeout_blockers
        + failure_blockers
        + weakening_blockers
        + execution_blockers
    )
    status = _checkpoint_status(blockers, incomplete, warnings)

    guardrails = _guardrails(no_weakening, non_execution)
    verdict_message = {
        STATUS_FROZEN: "OPS.TEST.1-OPS.TEST.3 are complete, safe, and frozen.",
        STATUS_FROZEN_WITH_WARNINGS: (
            "OPS.TEST.1-OPS.TEST.3 are complete and safe to freeze with warnings; "
            "executable suite manifests and runner commands remain future work."
        ),
        STATUS_INCOMPLETE: "OPS.TEST.CLOSE cannot freeze the branch until incomplete items are resolved.",
        STATUS_BLOCKED: "OPS.TEST.CLOSE is blocked by unsafe test-runtime policy or unexpected execution behavior.",
    }[status]

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "checkpoint_id": str(checkpoint_id or "ops-test-close-test-runtime-operations-branch-checkpoint"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "checkpoint_status": status,
        "source_runtime_profile_audit_path": _norm_path(source_runtime_profile_audit_path),
        "source_slow_timing_report_path": _norm_path(source_slow_timing_report_path),
        "source_suite_split_manifest_plan_path": _norm_path(source_suite_split_manifest_plan_path),
        "phase_completion_summary": phase_summary,
        "artifact_coverage": artifact_coverage,
        "profile_coverage": profile_coverage,
        "timing_collector_summary": timing_summary,
        "suite_manifest_summary": suite_summary,
        "timeout_policy_summary": timeout_summary,
        "failure_reporting_policy_summary": failure_summary,
        "no_weakening_verification": no_weakening,
        "non_execution_verification": non_execution,
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "guardrails": guardrails,
        "boundaries": list(GUARDRAILS),
        "final_verdict": {
            "status": status,
            "ready_to_freeze": status in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": verdict_message,
        },
    }


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


def render_test_runtime_operations_branch_checkpoint_markdown(report: dict[str, Any]) -> str:
    """Render the OPS.TEST.CLOSE checkpoint as Markdown."""
    lines: list[str] = [
        "# Test Runtime Operations Branch Checkpoint",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Checkpoint id:** `{_md(report.get('checkpoint_id', ''))}`",
        f"- **Checkpoint status:** `{_md(report.get('checkpoint_status', ''))}`",
        f"- **Runtime profile audit:** `{_md(report.get('source_runtime_profile_audit_path', ''))}`",
        f"- **Slow timing report:** `{_md(report.get('source_slow_timing_report_path', ''))}`",
        f"- **Suite manifest plan:** `{_md(report.get('source_suite_split_manifest_plan_path', ''))}`",
        "",
        "## Phase Completion",
        "",
    ]
    phase = report.get("phase_completion_summary") or {}
    lines.extend(_dict_lines({k: v for k, v in phase.items() if k != "phase_checks"}))
    checks = phase.get("phase_checks") or []
    if checks:
        lines.extend(["", "| Phase | Present | Status | Complete | Guardrails OK |", "|---|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('phase_id'))} | {_bool(check.get('present'))} | "
                f"{_md(check.get('status'))} | {_bool(check.get('complete'))} | "
                f"{_bool(check.get('guardrails_ok'))} |"
            )
    lines.extend(["", "## Artifact Coverage", ""])
    artifact = report.get("artifact_coverage") or {}
    lines.extend(_dict_lines({k: v for k, v in artifact.items() if k != "checks"}))
    checks = artifact.get("checks") or []
    if checks:
        lines.extend(["", "| Artifact | Present | Status | Path |", "|---|---|---|---|"])
        for check in checks:
            lines.append(
                f"| {_md(check.get('artifact_id'))} | {_bool(check.get('present'))} | "
                f"{_md(check.get('status'))} | `{_md(check.get('path'))}` |"
            )

    lines.extend(["", "## Runtime Profile Summary", ""])
    lines.extend(_dict_lines(report.get("profile_coverage")))
    lines.extend(["", "## Timing Collector Summary", ""])
    lines.extend(_dict_lines(report.get("timing_collector_summary")))
    lines.extend(["", "## Suite Manifest Plan Summary", ""])
    lines.extend(_dict_lines(report.get("suite_manifest_summary")))
    lines.extend(["", "## Timeout and Failure Policy", ""])
    lines.extend(["**Timeout policy:**", ""])
    lines.extend(_dict_lines(report.get("timeout_policy_summary")))
    lines.extend(["", "**Failure reporting policy:**", ""])
    lines.extend(_dict_lines(report.get("failure_reporting_policy_summary")))
    lines.extend(["", "## No-Weakening Verification", ""])
    lines.extend(_dict_lines(report.get("no_weakening_verification")))
    lines.extend(["", "## Non-Execution Verification", ""])
    lines.extend(_dict_lines(report.get("non_execution_verification")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(report.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(report.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(report.get("incomplete_reasons")))
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


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{_norm_path(path)}: {exc}"
    if not isinstance(data, dict):
        return None, f"{_norm_path(path)} is not a JSON object"
    return data, ""


def write_test_runtime_operations_branch_checkpoint(
    *,
    repo_root: str | Path = ".",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
    source_suite_split_manifest_plan_path: str | Path = DEFAULT_SUITE_SPLIT_MANIFEST_PLAN_PATH,
    checkpoint_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Read checkpoint inputs and write OPS.TEST.CLOSE JSON/Markdown artifacts."""
    root = Path(repo_root or ".")
    registry_data, registry_error = _load_json_object(_resolve(root, registry_path))
    runtime, runtime_error = _load_json_object(_resolve(root, source_runtime_profile_audit_path))
    timing, timing_error = _load_json_object(_resolve(root, source_slow_timing_report_path))
    manifest, manifest_error = _load_json_object(_resolve(root, source_suite_split_manifest_plan_path))

    report = build_test_runtime_operations_branch_checkpoint(
        repo_root=root,
        registry_data=registry_data,
        registry_load_error=registry_error,
        source_runtime_profile_audit_path=source_runtime_profile_audit_path,
        source_runtime_profile_audit=runtime,
        source_runtime_profile_audit_load_error=runtime_error,
        source_slow_timing_report_path=source_slow_timing_report_path,
        source_slow_timing_report=timing,
        source_slow_timing_report_load_error=timing_error,
        source_suite_split_manifest_plan_path=source_suite_split_manifest_plan_path,
        source_suite_split_manifest_plan=manifest,
        source_suite_split_manifest_plan_load_error=manifest_error,
        checkpoint_id=checkpoint_id,
        created_at=created_at,
    )

    out = Path(output_dir)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_test_runtime_operations_branch_checkpoint_markdown(report), encoding="utf-8")
    return {
        "ok": report["checkpoint_status"] in {STATUS_FROZEN, STATUS_FROZEN_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
