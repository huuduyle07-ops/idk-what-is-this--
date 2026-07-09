"""OPS.TEST.3 - Test Suite Split Manifest Plan.

Builds a report-only plan for named test-suite manifests. It records command
templates, gates, timeouts, and failure-reporting rules without moving tests,
skipping tests, weakening coverage, hiding failures, or changing production
behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "test_suite_split_manifest_plan"
THIS_PHASE_ID = "OPS.TEST.3"

STATUS_READY = "test_suite_split_manifest_plan_ready"
STATUS_READY_WITH_WARNINGS = "test_suite_split_manifest_plan_ready_with_warnings"
STATUS_INCOMPLETE = "test_suite_split_manifest_plan_incomplete"
STATUS_BLOCKED = "test_suite_split_manifest_plan_blocked"

JSON_NAME = "test_suite_split_manifest_plan.json"
MD_NAME = "test_suite_split_manifest_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ops" / "test_suite_split_manifest_plan"
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

FULL_TIMEOUT_SECONDS = 30 * 60

REQUIRED_PROFILE_IDS: tuple[str, ...] = (
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
    "phase_id": "OPS.TEST.CLOSE",
    "title": "Test Runtime Operations Branch Checkpoint",
    "reason": "Freeze OPS.TEST.1-OPS.TEST.3 as a complete test-runtime planning branch.",
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "UX.RUN.1",
    "title": "Run Progress / Operator Visibility",
    "reason": "Improve operator visibility for long-running validation gates.",
}

GUARDRAIL_NOTE = (
    "OPS.TEST.3 is report-only and manifest-plan-only. It may define named suite "
    "manifest strategy, command templates, gates, and timeouts, but it must not "
    "move, delete, skip, or weaken tests; hide failures; treat timeout as pass; "
    "change production behavior; execute validation; mutate benchmarks; call "
    "models; launch workers; contact networks; or write databases."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "manifest plan only",
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
    "test_deletion_recommended": "plan recommends deleting tests to make the suite faster",
    "safety_coverage_weakened": "plan weakens safety or guardrail coverage",
    "failures_hidden": "plan hides failed assertions or validation failures",
    "timeout_treated_as_pass": "plan treats timeout as a pass",
    "slow_tests_silently_excluded": "plan silently excludes slow tests from full/nightly profiles",
    "production_behavior_mutated": "plan changes production behavior to satisfy timing policy",
    "benchmark_check_weakened": "plan weakens benchmark check coverage",
    "automatic_test_skipping_added": "plan adds automatic test skipping without an explicit manifest",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm_path(value: str | Path | None) -> str:
    return str(value or "").replace("\\", "/")


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


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


def _manifest_profiles() -> list[dict[str, Any]]:
    return [
        {
            "profile_id": "smoke",
            "purpose": "Fast sanity check for syntax and registry health.",
            "should_include": [
                "compileall",
                "registry validation",
                "phase picker report",
            ],
        },
        {
            "profile_id": "phase",
            "purpose": "Validate the current phase implementation.",
            "should_include": [
                "current phase test file",
                "direct dependency tests",
                "registry/picker tests",
                "benchmark check if phase touches registry, roadmap, or benchmarks",
            ],
        },
        {
            "profile_id": "branch",
            "purpose": "Validate a whole branch chain before branch close.",
            "should_include": [
                "all tests in current branch",
                "adjacent expectation tests",
                "registry/picker tests",
                "benchmark check",
            ],
        },
        {
            "profile_id": "registry_picker",
            "purpose": "Validate roadmap integrity and live recommendation.",
            "should_include": [
                "tests/test_phase_registry.py",
                "tests/test_phase_picker.py",
                "scripts/validate_phase_registry.py",
                "scripts/create_phase_picker_report.py",
            ],
        },
        {
            "profile_id": "benchmark",
            "purpose": "Validate benchmark metadata and benchmark cases.",
            "should_include": ["python benchmarks/run_benchmarks.py --check"],
        },
        {
            "profile_id": "full",
            "purpose": "Full verification gate.",
            "should_include": ["python -m pytest -q"],
        },
        {
            "profile_id": "nightly",
            "purpose": "Long verification and timing collection gate.",
            "should_include": [
                "full pytest",
                "benchmark check",
                "optional pytest duration output",
                "optional slow timing report generation for timing collection",
            ],
        },
        {
            "profile_id": "release_freeze",
            "purpose": "Highest-confidence pre-release/pre-freeze gate.",
            "should_include": [
                "full pytest with long timeout",
                "benchmark check",
                "registry validation",
                "phase picker report",
                "relevant branch checkpoint reports",
            ],
        },
    ]


def _failure_policy() -> dict[str, Any]:
    return {
        "failed_assertions_are_failures": True,
        "timeout_is_pass": False,
        "full_suite_pass_requires_successful_pytest_exit": True,
        "requires_successful_pytest_exit": True,
        "quick_gate_timeout_message": "full suite not completed within quick-gate timeout",
        "partial_output_can_claim_full_suite_health": False,
        "skipped_tests_must_be_reported": True,
        "xfail_tests_remain_visible": True,
    }


def _timeout_policy() -> dict[str, dict[str, Any]]:
    return {
        "smoke": {
            "runtime_class": "very_fast",
            "recommended_timeout_seconds": 300,
            "timeout_policy": "Short timeout; timeout is not a pass.",
        },
        "phase": {
            "runtime_class": "fast",
            "recommended_timeout_seconds": 600,
            "timeout_policy": "Short/medium timeout; timeout is not a pass.",
        },
        "branch": {
            "runtime_class": "medium",
            "recommended_timeout_seconds": 900,
            "timeout_policy": "Medium timeout; timeout is not a pass.",
        },
        "registry_picker": {
            "runtime_class": "very_fast",
            "recommended_timeout_seconds": 300,
            "timeout_policy": "Short timeout; timeout is not a pass.",
        },
        "benchmark": {
            "runtime_class": "medium",
            "recommended_timeout_seconds": 600,
            "timeout_policy": "Medium timeout; timeout is not a pass.",
        },
        "full": {
            "runtime_class": "very_slow",
            "recommended_timeout_seconds": FULL_TIMEOUT_SECONDS,
            "timeout_policy": "At least 30 minutes; timeout is not a pass.",
        },
        "nightly": {
            "runtime_class": "long_running",
            "recommended_timeout_seconds": 3600,
            "timeout_policy": "At least 30 minutes; timeout is not a pass.",
        },
        "release_freeze": {
            "runtime_class": "long_running",
            "recommended_timeout_seconds": 3600,
            "timeout_policy": "At least 30 minutes; timeout is not a pass.",
        },
    }


def _template(
    profile_id: str,
    description: str,
    command_templates: list[str],
    expected_runtime_class: str,
    recommended_timeout_seconds: int,
    *,
    required_before_commit: bool = False,
    required_before_branch_close: bool = False,
    required_before_release: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "description": description,
        "command_templates": command_templates,
        "expected_runtime_class": expected_runtime_class,
        "recommended_timeout_seconds": int(recommended_timeout_seconds),
        "required_before_commit": bool(required_before_commit),
        "required_before_branch_close": bool(required_before_branch_close),
        "required_before_release": bool(required_before_release),
        "failure_policy": _failure_policy(),
        "timeout_policy": _timeout_policy()[profile_id],
        "notes": list(notes or []),
    }


def _profile_command_templates() -> list[dict[str, Any]]:
    timeouts = _timeout_policy()
    return [
        _template(
            "smoke",
            "Fast syntax and roadmap sanity gate.",
            [
                "python -m compileall -q core scripts tests benchmarks web",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
            ],
            timeouts["smoke"]["runtime_class"],
            timeouts["smoke"]["recommended_timeout_seconds"],
            required_before_commit=True,
            required_before_branch_close=True,
            notes=["Use as a quick sanity gate, not as full-suite proof."],
        ),
        _template(
            "phase",
            "Current phase implementation plus direct dependency tests.",
            [
                "python -m pytest tests/test_<current_phase>.py -q",
                "python -m pytest tests/test_<direct_dependency>.py -q",
                "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
            ],
            timeouts["phase"]["runtime_class"],
            timeouts["phase"]["recommended_timeout_seconds"],
            required_before_commit=True,
            required_before_branch_close=True,
            notes=[
                "Replace placeholders with the current phase test file and direct dependency tests.",
                "Include benchmark check when the phase touches registry, roadmap, or benchmark metadata.",
            ],
        ),
        _template(
            "branch",
            "Whole branch chain gate before branch close.",
            [
                "python -m pytest tests/test_<branch_chain_a>.py tests/test_<branch_chain_b>.py -q",
                "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
                "python benchmarks/run_benchmarks.py --check",
            ],
            timeouts["branch"]["runtime_class"],
            timeouts["branch"]["recommended_timeout_seconds"],
            required_before_branch_close=True,
            notes=[
                "Include all tests in the current branch chain and adjacent expectation tests.",
                "Do not remove slow branch-chain tests to satisfy this profile.",
            ],
        ),
        _template(
            "registry_picker",
            "Roadmap integrity and live recommendation gate.",
            [
                "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
            ],
            timeouts["registry_picker"]["runtime_class"],
            timeouts["registry_picker"]["recommended_timeout_seconds"],
            required_before_branch_close=True,
            notes=["Required whenever roadmap or phase recommendation metadata changes."],
        ),
        _template(
            "benchmark",
            "Benchmark metadata and case contract gate.",
            ["python benchmarks/run_benchmarks.py --check"],
            timeouts["benchmark"]["runtime_class"],
            timeouts["benchmark"]["recommended_timeout_seconds"],
            required_before_branch_close=True,
            notes=["Benchmark check must remain visible and cannot be weakened by suite splitting."],
        ),
        _template(
            "full",
            "Full pytest verification gate.",
            ["python -m pytest -q"],
            timeouts["full"]["runtime_class"],
            timeouts["full"]["recommended_timeout_seconds"],
            required_before_release=True,
            notes=[
                "Full-suite pass can only be claimed when pytest exits successfully.",
                "Partial output or quick-gate timeout is not full-suite proof.",
            ],
        ),
        _template(
            "nightly",
            "Long gate with full validation and timing collection concept.",
            [
                "python -m pytest -q",
                "python benchmarks/run_benchmarks.py --check",
                "python -m pytest -q --durations=50",
                "python scripts/create_slow_test_timing_report.py --timing-log <pytest-duration-log> --json",
            ],
            timeouts["nightly"]["runtime_class"],
            timeouts["nightly"]["recommended_timeout_seconds"],
            required_before_release=False,
            notes=[
                "Duration output and slow timing report generation are optional timing collection aids.",
                "Slow tests remain part of full and nightly health.",
            ],
        ),
        _template(
            "release_freeze",
            "Highest-confidence pre-release/pre-freeze gate.",
            [
                "python -m pytest -q",
                "python benchmarks/run_benchmarks.py --check",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_<relevant_branch_checkpoint>.py --json",
            ],
            timeouts["release_freeze"]["runtime_class"],
            timeouts["release_freeze"]["recommended_timeout_seconds"],
            required_before_release=True,
            notes=[
                "Use relevant branch checkpoint reports for the branch being frozen.",
                "Release freeze is a confidence gate, not a mechanism for excluding known failures.",
            ],
        ),
    ]


def _required_gates_by_context() -> dict[str, list[str]]:
    return {
        "before_commit": ["smoke", "phase"],
        "registry_change": ["registry_picker", "benchmark"],
        "before_branch_close": ["smoke", "phase", "branch", "registry_picker", "benchmark"],
        "before_release": ["release_freeze"],
        "nightly_or_scheduled": ["nightly"],
    }


def _suite_split_recommendations() -> list[dict[str, str]]:
    return [
        {
            "profile": "smoke",
            "recommendation": "Keep smoke focused on compileall, registry validation, and phase picker reporting.",
            "reason": "Smoke is a fast sanity gate and must not claim full-suite health.",
        },
        {
            "profile": "phase",
            "recommendation": "Bind phase manifests to the current phase test file, direct dependencies, registry/picker tests, and benchmark check when metadata changes.",
            "reason": "Phase gates should be small, explicit, and traceable to the current implementation boundary.",
        },
        {
            "profile": "branch",
            "recommendation": "Use branch-chain manifests to collect all branch tests and adjacent expectation tests before branch close.",
            "reason": "Branch close requires confidence across the whole branch, not only the last phase.",
        },
        {
            "profile": "full_or_nightly",
            "recommendation": "Keep all tests visible in full and nightly profiles; use timing data for planning, not deletion.",
            "reason": "Slow tests can be tracked and budgeted without disappearing from safety gates.",
        },
    ]


def _no_weakening_policy() -> dict[str, Any]:
    return {
        "deleting_tests_to_make_suite_faster_is_blocked": True,
        "hiding_failed_assertions_is_blocked": True,
        "timeout_is_not_a_pass": True,
        "full_profile_must_include_safety_and_guardrail_tests": True,
        "full_and_nightly_must_not_silently_exclude_slow_tests": True,
        "benchmark_check_must_not_be_weakened": True,
        "production_behavior_must_not_change_for_timing": True,
        "automatic_test_skipping_requires_explicit_manifest": True,
    }


def _policy_blockers(markers: dict[str, Any] | None) -> list[str]:
    values = dict(markers or {})
    return [
        label
        for key, label in POLICY_VIOLATION_LABELS.items()
        if _truthy(values.get(key, False))
    ]


def _guardrails(markers: dict[str, Any] | None = None) -> dict[str, bool]:
    values = dict(markers or {})
    return {
        "report_only": True,
        "manifest_plan_only": True,
        "no_test_deletion": not _truthy(values.get("test_deletion_recommended")),
        "no_test_skipping_behavior": not _truthy(values.get("automatic_test_skipping_added")),
        "no_coverage_weakening": not _truthy(values.get("safety_coverage_weakened")),
        "no_hidden_failures": not _truthy(values.get("failures_hidden")),
        "timeout_is_not_pass": not _truthy(values.get("timeout_treated_as_pass")),
        "no_silent_slow_test_exclusion": not _truthy(values.get("slow_tests_silently_excluded")),
        "no_production_behavior_change": not _truthy(values.get("production_behavior_mutated")),
        "no_route_auth_change": True,
        "no_model_call": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "no_benchmark_mutation": not _truthy(values.get("benchmark_check_weakened")),
        "no_database_write": True,
        "no_network": True,
        "no_automatic_authority_escalation": True,
        "no_executable_test_runner_changes": True,
    }


def _profile_ids(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {str(item.get("profile_id", "")) for item in items if isinstance(item, dict)}


def _incomplete_reasons(
    *,
    manifest_profiles: Any,
    profile_command_templates: Any,
    timeout_policy: Any,
    failure_reporting_policy: Any,
) -> list[str]:
    reasons: list[str] = []
    profile_ids = _profile_ids(manifest_profiles)
    missing_profiles = [item for item in REQUIRED_PROFILE_IDS if item not in profile_ids]
    if missing_profiles:
        reasons.append("Required manifest profiles are missing: " + ", ".join(missing_profiles))

    template_ids = _profile_ids(profile_command_templates)
    missing_templates = [item for item in REQUIRED_PROFILE_IDS if item not in template_ids]
    if missing_templates:
        reasons.append("Command templates are missing: " + ", ".join(missing_templates))
    elif isinstance(profile_command_templates, list):
        empty_commands = [
            str(item.get("profile_id", ""))
            for item in profile_command_templates
            if isinstance(item, dict) and not item.get("command_templates")
        ]
        if empty_commands:
            reasons.append("Command templates are empty: " + ", ".join(empty_commands))

    if not isinstance(timeout_policy, dict) or not timeout_policy:
        reasons.append("Timeout policy is absent.")
    else:
        for profile_id in ("full", "nightly", "release_freeze"):
            entry = timeout_policy.get(profile_id)
            seconds = entry.get("recommended_timeout_seconds") if isinstance(entry, dict) else 0
            if int(seconds or 0) < FULL_TIMEOUT_SECONDS:
                reasons.append(f"Timeout policy for {profile_id} must be at least 1800 seconds.")

    if not isinstance(failure_reporting_policy, dict) or not failure_reporting_policy:
        reasons.append("Failure reporting policy is absent.")
    else:
        if failure_reporting_policy.get("timeout_is_pass") is not False:
            reasons.append("Failure reporting policy must state timeout is not pass.")
        if failure_reporting_policy.get("full_suite_pass_requires_successful_pytest_exit") is not True:
            reasons.append("Failure reporting policy must require successful pytest exit for full-suite pass.")

    return _dedupe(reasons)


def _status(blockers: list[str], incomplete: list[str], warnings: list[str]) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def build_test_suite_split_manifest_plan(
    *,
    repo_root: str | Path = ".",
    plan_id: str = "",
    created_at: str = "",
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
    manifest_profiles: list[dict[str, Any]] | None = None,
    profile_command_templates: list[dict[str, Any]] | None = None,
    timeout_policy: dict[str, Any] | None = None,
    failure_reporting_policy: dict[str, Any] | None = None,
    executable_manifest_boundary_clear: bool = False,
    policy_violation_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic suite split manifest plan record."""
    Path(repo_root or ".")
    profiles = _manifest_profiles() if manifest_profiles is None else list(manifest_profiles)
    templates = _profile_command_templates() if profile_command_templates is None else list(profile_command_templates)
    timeouts = _timeout_policy() if timeout_policy is None else dict(timeout_policy)
    failures = _failure_policy() if failure_reporting_policy is None else dict(failure_reporting_policy)

    warnings: list[str] = []
    if not executable_manifest_boundary_clear:
        warnings.append(
            "Executable manifest files are intentionally not written in OPS.TEST.3; future phases may create them."
        )

    blockers = _dedupe(_policy_blockers(policy_violation_markers))
    incomplete = _incomplete_reasons(
        manifest_profiles=profiles,
        profile_command_templates=templates,
        timeout_policy=timeouts,
        failure_reporting_policy=failures,
    )
    warnings = _dedupe(warnings)
    plan_status = _status(blockers, incomplete, warnings)

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "plan_id": str(plan_id or "ops-test-3-test-suite-split-manifest-plan"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "plan_status": plan_status,
        "source_runtime_profile_audit_path": _norm_path(source_runtime_profile_audit_path),
        "source_slow_timing_report_path": _norm_path(source_slow_timing_report_path),
        "manifest_profiles": profiles,
        "profile_command_templates": templates,
        "required_gates_by_context": _required_gates_by_context(),
        "timeout_policy": timeouts,
        "failure_reporting_policy": failures,
        "suite_split_recommendations": _suite_split_recommendations(),
        "no_weakening_policy": _no_weakening_policy(),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "guardrails": _guardrails(policy_violation_markers),
        "boundaries": list(BOUNDARIES),
        "final_verdict": {
            "status": plan_status,
            "ready_for_next_phase": plan_status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Suite split manifest plan is ready for OPS.TEST.CLOSE."
                if plan_status == STATUS_READY
                else f"Suite split manifest plan status is {plan_status}."
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


def render_test_suite_split_manifest_plan_markdown(plan: dict[str, Any]) -> str:
    """Render a suite split manifest plan as Markdown."""
    lines: list[str] = [
        "# Test Suite Split Manifest Plan",
        "",
        f"> {_md(plan.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Plan status:** `{_md(plan.get('plan_status', ''))}`",
        f"- **Runtime profile audit:** `{_md(plan.get('source_runtime_profile_audit_path', ''))}`",
        f"- **Slow timing report:** `{_md(plan.get('source_slow_timing_report_path', ''))}`",
        f"- **Profiles:** {len(plan.get('manifest_profiles') or [])}",
        "",
        "## Manifest Profiles",
        "",
    ]
    lines.extend(_list_lines(plan.get("manifest_profiles")))
    lines.extend(["", "## Profile Command Templates", ""])
    lines.extend(_list_lines(plan.get("profile_command_templates")))
    lines.extend(["", "## Required Gates By Context", ""])
    lines.extend(_dict_lines(plan.get("required_gates_by_context")))
    lines.extend(["", "## Timeout Policy", ""])
    lines.extend(_dict_lines(plan.get("timeout_policy")))
    lines.extend(["", "## Failure Reporting Policy", ""])
    lines.extend(_dict_lines(plan.get("failure_reporting_policy")))
    lines.extend(["", "## Suite Split Recommendations", ""])
    lines.extend(_list_lines(plan.get("suite_split_recommendations")))
    lines.extend(["", "## No Weakening Policy", ""])
    lines.extend(_dict_lines(plan.get("no_weakening_policy")))
    lines.extend(["", "## Warnings", ""])
    lines.extend(_list_lines(plan.get("warnings")))
    lines.extend(["", "## Blocked Reasons", ""])
    lines.extend(_list_lines(plan.get("blocked_reasons")))
    lines.extend(["", "## Incomplete Reasons", ""])
    lines.extend(_list_lines(plan.get("incomplete_reasons")))

    next_phase = plan.get("recommended_next_phase") if isinstance(plan.get("recommended_next_phase"), dict) else {}
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
    lines.extend(_list_lines(plan.get("boundaries")))
    guardrails = plan.get("guardrails") if isinstance(plan.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: `{str(bool(guardrails[key])).lower()}`")
    lines.append("")
    return "\n".join(lines)


def write_test_suite_split_manifest_plan(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    plan_id: str = "",
    created_at: str = "",
    source_runtime_profile_audit_path: str | Path = DEFAULT_RUNTIME_PROFILE_AUDIT_PATH,
    source_slow_timing_report_path: str | Path = DEFAULT_SLOW_TIMING_REPORT_PATH,
) -> dict[str, Any]:
    """Build and write OPS.TEST.3 JSON/Markdown manifest plan artifacts."""
    plan = build_test_suite_split_manifest_plan(
        repo_root=repo_root,
        plan_id=plan_id,
        created_at=created_at,
        source_runtime_profile_audit_path=source_runtime_profile_audit_path,
        source_slow_timing_report_path=source_slow_timing_report_path,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_test_suite_split_manifest_plan_markdown(plan), encoding="utf-8")
    return {
        "ok": plan["plan_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": plan,
    }
