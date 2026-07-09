"""OPS.TEST.2 - Slow Test Timing Collector.

Builds a report-only view of test timing data from provided logs, manual maps,
or sample fallback data. It does not execute tests, change coverage, delete
tests, hide failures, mutate application behavior, call models, contact a
network, or modify benchmark cases.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "slow_test_timing_report"
THIS_PHASE_ID = "OPS.TEST.2"

STATUS_READY = "slow_test_timing_report_ready"
STATUS_READY_WITH_WARNINGS = "slow_test_timing_report_ready_with_warnings"
STATUS_INCOMPLETE = "slow_test_timing_report_incomplete"
STATUS_BLOCKED = "slow_test_timing_report_blocked"

JSON_NAME = "slow_test_timing_report.json"
MD_NAME = "slow_test_timing_report.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "ops" / "slow_test_timing_collector"
DEFAULT_PROFILE_AUDIT_PATH = (
    Path(".agent")
    / "ops"
    / "test_suite_runtime_profile_audit"
    / "test_suite_runtime_profile_audit.json"
)

FULL_TIMEOUT_SECONDS = 30 * 60

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "OPS.TEST.3",
    "title": "Suite Split Manifest Plan",
    "reason": (
        "Use collected timing shape to plan named suite manifests for smoke, "
        "phase, branch, full, and nightly gates without changing test behavior."
    ),
}

ALTERNATIVE_NEXT_PHASE = {
    "phase_id": "UX.RUN.1",
    "title": "Run Progress / Operator Visibility",
    "reason": "Improve operator visibility if timing data is not yet useful enough for manifest planning.",
}

GUARDRAIL_NOTE = (
    "OPS.TEST.2 is report-only and timing/reporting-only. It may parse timing "
    "data and recommend suite splitting, but it must not delete tests, weaken "
    "safety coverage, hide failures, treat timeouts as passes, change production "
    "behavior, run tests, or mutate benchmark data."
)

BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "timing/reporting only",
    "no test deletion",
    "no safety weakening",
    "no production behavior change",
    "no route/auth change",
    "no model call",
    "no worker launch",
    "no patch apply",
    "no benchmark mutation",
    "no database write",
    "no network",
    "no automatic authority escalation",
    "collector does not execute pytest",
    "collector does not spawn commands",
)

POLICY_VIOLATION_LABELS: dict[str, str] = {
    "test_deletion_recommended": "collector recommends deleting tests",
    "safety_coverage_weakened": "collector weakens safety coverage",
    "timeout_treated_as_pass": "collector treats a timeout as a pass",
    "failures_hidden": "collector hides validation failures",
    "production_behavior_mutated": "collector mutates production behavior",
    "slow_tests_marked_unimportant": "collector marks slow tests as unimportant",
}

SAMPLE_TIMING_MAP: dict[str, float] = {
    "tests/test_phase_registry.py::test_seed_registry_validates": 1.4,
    "tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets": 1.1,
    "tests/test_test_suite_runtime_profile_audit.py::test_default_audit_is_ready_with_warnings_and_report_only": 0.6,
    "tests/test_benchmark_failure_regressions.py::test_benchmark_case_metadata": 18.5,
    "tests/test_benchmark_run_health_summary.py::test_health_summary_from_reports": 42.0,
}

_DURATION_RE = re.compile(
    r"^\s*(?P<seconds>\d+(?:\.\d+)?)s\s+(?P<phase>call|setup|teardown)\s+(?P<nodeid>\S+)\s*$"
)
_PROGRESS_PREFIX_RE = re.compile(r"^\s*\[(?P<seconds>\d+(?:\.\d+)?)s\]\s+(?P<nodeid>tests/\S+::\S+)")
_PROGRESS_SUFFIX_RE = re.compile(r"(?P<nodeid>tests/\S+::\S+).*?(?P<seconds>\d+(?:\.\d+)?)s\s*$")


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


def _round_seconds(value: float) -> float:
    return round(float(value), 2)


def _file_path(nodeid: str) -> str:
    return str(nodeid).split("::", 1)[0]


def _phase_prefix(file_path: str) -> str:
    name = Path(file_path).name
    if name.startswith("test_"):
        stem = name[len("test_"):]
    else:
        stem = Path(file_path).stem
    return stem.split("_", 1)[0] if stem else ""


def _bucket(seconds: float) -> str:
    if seconds < 1:
        return "very_fast"
    if seconds < 5:
        return "fast"
    if seconds < 30:
        return "medium"
    if seconds < 120:
        return "slow"
    return "very_slow"


def _human_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} minutes"
    return f"{seconds / 3600:.1f} hours"


def _timing_entry(nodeid: str, seconds: float, source: str, phase: str = "call") -> dict[str, Any]:
    file_path = _file_path(nodeid)
    return {
        "nodeid": nodeid,
        "file_path": file_path,
        "phase": phase,
        "seconds": _round_seconds(seconds),
        "phase_prefix": _phase_prefix(file_path),
        "source": source,
    }


def parse_timing_text(text: str) -> dict[str, Any]:
    """Parse pytest duration/progress text into raw timing events.

    Non-timing lines are ignored. Timing-shaped malformed lines become warnings
    so an operator can see parser gaps without losing valid entries.
    """
    duration_entries: list[dict[str, Any]] = []
    progress_entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for line_no, raw in enumerate(str(text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue

        match = _DURATION_RE.match(line)
        if match:
            nodeid = match.group("nodeid")
            if "::" not in nodeid or not nodeid.startswith("tests/"):
                warnings.append(f"ignored malformed timing line {line_no}: {line}")
                continue
            duration_entries.append(
                _timing_entry(
                    nodeid=nodeid,
                    seconds=float(match.group("seconds")),
                    phase=match.group("phase"),
                    source="parsed_pytest_durations",
                )
            )
            continue

        prefix = _PROGRESS_PREFIX_RE.search(line)
        suffix = _PROGRESS_SUFFIX_RE.search(line)
        progress = prefix or suffix
        if progress:
            progress_entries.append(
                _timing_entry(
                    nodeid=progress.group("nodeid"),
                    seconds=float(progress.group("seconds")),
                    source="parsed_pytest_progress_log",
                )
            )
            continue

        if re.match(r"^\s*\d+(?:\.\d+)?s\s+", line) or "tests/" in line and "::" in line and line.endswith("s"):
            warnings.append(f"ignored malformed timing line {line_no}: {line}")

    if duration_entries:
        return {
            "source_type": "parsed_pytest_durations",
            "entries": duration_entries,
            "warnings": warnings,
        }
    if progress_entries:
        return {
            "source_type": "parsed_pytest_progress_log",
            "entries": progress_entries,
            "warnings": warnings,
        }
    return {"source_type": "missing_timing_data", "entries": [], "warnings": warnings}


def _entries_from_manual_map(values: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for nodeid, raw_seconds in sorted((values or {}).items()):
        try:
            seconds = float(raw_seconds)
        except (TypeError, ValueError):
            warnings.append(f"ignored manual timing entry with non-numeric seconds: {nodeid}")
            continue
        if "::" not in str(nodeid) or seconds < 0:
            warnings.append(f"ignored malformed manual timing entry: {nodeid}")
            continue
        entries.append(_timing_entry(str(nodeid), seconds, source="manual_timing_map"))
    return entries, warnings


def _aggregate_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    tests: dict[str, dict[str, Any]] = {}
    files: dict[str, dict[str, Any]] = {}
    for entry in entries:
        nodeid = str(entry["nodeid"])
        file_path = str(entry["file_path"])
        seconds = float(entry["seconds"])

        test_item = tests.setdefault(
            nodeid,
            {
                "nodeid": nodeid,
                "file_path": file_path,
                "phase_prefix": entry.get("phase_prefix", ""),
                "total_seconds": 0.0,
                "events": [],
            },
        )
        test_item["total_seconds"] += seconds
        test_item["events"].append({"phase": entry.get("phase", "call"), "seconds": seconds})

        file_item = files.setdefault(
            file_path,
            {
                "file_path": file_path,
                "phase_prefix": entry.get("phase_prefix", ""),
                "total_seconds": 0.0,
                "test_count": 0,
                "_nodes": set(),
            },
        )
        file_item["total_seconds"] += seconds
        file_item["_nodes"].add(nodeid)

    test_items: list[dict[str, Any]] = []
    for item in tests.values():
        total = _round_seconds(item["total_seconds"])
        test_items.append(
            {
                "nodeid": item["nodeid"],
                "file_path": item["file_path"],
                "phase_prefix": item["phase_prefix"],
                "total_seconds": total,
                "runtime_bucket": _bucket(total),
                "events": item["events"],
            }
        )

    file_items: list[dict[str, Any]] = []
    for item in files.values():
        total = _round_seconds(item["total_seconds"])
        file_items.append(
            {
                "file_path": item["file_path"],
                "phase_prefix": item["phase_prefix"],
                "total_seconds": total,
                "test_count": len(item["_nodes"]),
                "runtime_bucket": _bucket(total),
            }
        )

    test_items.sort(key=lambda item: (-item["total_seconds"], item["nodeid"]))
    file_items.sort(key=lambda item: (-item["total_seconds"], item["file_path"]))

    buckets = {
        name: {"test_count": 0, "total_seconds": 0.0}
        for name in ("very_fast", "fast", "medium", "slow", "very_slow")
    }
    for item in test_items:
        bucket = item["runtime_bucket"]
        buckets[bucket]["test_count"] += 1
        buckets[bucket]["total_seconds"] = _round_seconds(
            buckets[bucket]["total_seconds"] + item["total_seconds"]
        )

    total = _round_seconds(sum(item["total_seconds"] for item in test_items))
    return {
        "total_seconds": total,
        "test_count": len(test_items),
        "file_count": len(file_items),
        "slowest_tests": test_items[:20],
        "slowest_files": file_items[:20],
        "runtime_buckets": buckets,
    }


def _recommended_profiles() -> list[dict[str, Any]]:
    return [
        {
            "name": "smoke",
            "purpose": "Fast syntax and roadmap sanity gate.",
            "commands": [
                "python -m compileall -q core scripts tests benchmarks web",
                "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
                "python scripts/create_phase_picker_report.py --registry docs/roadmap/phase_registry.json --json",
            ],
        },
        {
            "name": "phase",
            "purpose": "Current phase test file plus direct dependency tests.",
            "commands": [
                "python -m pytest tests/test_<current_phase>.py -q",
                "python -m pytest tests/test_<direct_dependency>.py -q",
            ],
        },
        {
            "name": "branch",
            "purpose": "Branch chain tests plus registry/picker and benchmark metadata checks.",
            "commands": [
                "python -m pytest tests/test_<branch-chain-a>.py tests/test_<branch-chain-b>.py -q",
                "python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q",
                "python benchmarks/run_benchmarks.py --check",
            ],
        },
        {
            "name": "full",
            "purpose": "Full pytest verification gate.",
            "commands": ["python -m pytest -q"],
        },
        {
            "name": "nightly",
            "purpose": "Long profile with full tests, benchmark metadata, and duration collection.",
            "commands": [
                "python -m pytest -q",
                "python benchmarks/run_benchmarks.py --check",
                "python -m pytest -q --durations=50",
            ],
        },
    ]


def _recommended_timeouts() -> dict[str, Any]:
    return {
        "smoke_seconds": 304,
        "phase_seconds": 304,
        "branch_seconds": 900,
        "full_seconds": FULL_TIMEOUT_SECONDS,
        "nightly_seconds": 3600,
        "timing_collection": "Use pytest duration output in nightly/full contexts; do not require it for small phase gates.",
    }


def _suite_split_recommendations(slowest_files: list[dict[str, Any]], timing_source_type: str) -> list[dict[str, Any]]:
    recommendations = [
        {
            "profile": "smoke",
            "recommendation": "Keep smoke focused on compileall, registry validation, and picker report generation.",
            "reason": "Smoke should stay independent of slowest test files.",
        },
        {
            "profile": "full",
            "recommendation": "Keep the full profile as python -m pytest -q with at least a 30-minute timeout.",
            "reason": "Full-suite health requires pytest to exit successfully.",
        },
    ]
    if slowest_files:
        top = slowest_files[0]
        recommendations.insert(
            1,
            {
                "profile": "branch_or_nightly",
                "recommendation": f"Track {top['file_path']} explicitly in branch/nightly timing reports.",
                "reason": "The slowest observed files should guide suite split manifest planning, not deletion.",
            },
        )
    if timing_source_type in {"manual_timing_map", "sample_timing_data"}:
        recommendations.append(
            {
                "profile": "ops_test_3_input",
                "recommendation": "Replace sample/manual timings with parsed pytest duration output when available.",
                "reason": "Suite manifests should eventually be based on observed timing data.",
            }
        )
    return recommendations


def _timeout_interpretation() -> dict[str, Any]:
    return {
        "timeout_counts_as_pass": False,
        "full_suite_health_requires_exit_success": True,
        "quick_timeout_meaning": "full suite not completed within quick gate",
        "timeout_without_final_report": "timed out without final report",
        "partial_output_policy": "Do not claim full-suite health from partial timing output alone.",
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


def _guardrails(markers: dict[str, Any] | None = None) -> dict[str, bool]:
    marker_values = dict(markers or {})
    return {
        "report_only": True,
        "timing_reporting_only": True,
        "no_test_deletion": not _truthy(marker_values.get("test_deletion_recommended")),
        "no_safety_weakening": not _truthy(marker_values.get("safety_coverage_weakened")),
        "timeout_is_not_pass": not _truthy(marker_values.get("timeout_treated_as_pass")),
        "no_hidden_failures": not _truthy(marker_values.get("failures_hidden")),
        "no_production_behavior_change": not _truthy(marker_values.get("production_behavior_mutated")),
        "slow_tests_not_marked_unimportant": not _truthy(marker_values.get("slow_tests_marked_unimportant")),
        "no_route_auth_change": True,
        "no_model_call": True,
        "no_worker_launch": True,
        "no_patch_apply": True,
        "no_benchmark_mutation": True,
        "no_database_write": True,
        "no_network": True,
        "no_automatic_authority_escalation": True,
        "cli_does_not_execute_pytest": True,
        "cli_does_not_spawn_commands": True,
    }


def _status(blockers: list[str], incomplete: list[str], timing_source_type: str) -> str:
    if blockers:
        return STATUS_BLOCKED
    if incomplete:
        return STATUS_INCOMPLETE
    if timing_source_type in {"manual_timing_map", "sample_timing_data"}:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY


def _select_entries(
    *,
    timing_text: str | None,
    manual_timing_map: dict[str, Any] | None,
    allow_sample_timing: bool,
) -> tuple[str, list[dict[str, Any]], list[str], list[str]]:
    warnings: list[str] = []
    incomplete: list[str] = []

    if timing_text:
        parsed = parse_timing_text(timing_text)
        warnings.extend(parsed["warnings"])
        if parsed["entries"]:
            return parsed["source_type"], list(parsed["entries"]), warnings, incomplete

    if manual_timing_map:
        entries, manual_warnings = _entries_from_manual_map(manual_timing_map)
        warnings.extend(manual_warnings)
        if entries:
            warnings.append("Manual timing map used; replace with parsed pytest timing output when available.")
            return "manual_timing_map", entries, warnings, incomplete

    if allow_sample_timing:
        entries, sample_warnings = _entries_from_manual_map(SAMPLE_TIMING_MAP)
        warnings.extend(sample_warnings)
        warnings.append("Sample timing data used because no timing log or manual map was provided.")
        return "sample_timing_data", entries, warnings, incomplete

    incomplete.append("No timing data is available and sample/manual fallback is disabled.")
    return "missing_timing_data", [], warnings, incomplete


def build_slow_test_timing_report(
    *,
    repo_root: str | Path = ".",
    report_id: str = "",
    created_at: str = "",
    timing_text: str | None = None,
    manual_timing_map: dict[str, Any] | None = None,
    allow_sample_timing: bool = True,
    source_profile_audit_path: str | Path = DEFAULT_PROFILE_AUDIT_PATH,
    source_timing_log_path: str | Path = "",
    policy_violation_markers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic report from provided timing data."""
    Path(repo_root or ".")
    timing_source_type, entries, warnings, incomplete = _select_entries(
        timing_text=timing_text,
        manual_timing_map=manual_timing_map,
        allow_sample_timing=allow_sample_timing,
    )
    aggregate = _aggregate_entries(entries)
    blockers = _policy_blockers(policy_violation_markers)
    blockers = _dedupe(blockers)
    incomplete = _dedupe(incomplete)
    warnings = _dedupe(warnings)
    report_status = _status(blockers, incomplete, timing_source_type)

    return {
        "report_kind": REPORT_KIND,
        "phase_id": THIS_PHASE_ID,
        "report_id": str(report_id or "ops-test-2-slow-test-timing-report"),
        "created_at": str(created_at or _utc_now()),
        "guardrail_note": GUARDRAIL_NOTE,
        "report_status": report_status,
        "source_profile_audit_path": _norm_path(source_profile_audit_path),
        "source_timing_log_path": _norm_path(source_timing_log_path),
        "timing_source_type": timing_source_type,
        "total_observed_runtime_seconds": aggregate["total_seconds"],
        "total_observed_runtime_human": _human_seconds(aggregate["total_seconds"]),
        "collected_test_count": aggregate["test_count"],
        "collected_file_count": aggregate["file_count"],
        "slowest_tests": aggregate["slowest_tests"],
        "slowest_files": aggregate["slowest_files"],
        "runtime_buckets": aggregate["runtime_buckets"],
        "recommended_profiles": _recommended_profiles(),
        "recommended_timeouts": _recommended_timeouts(),
        "suite_split_recommendations": _suite_split_recommendations(
            aggregate["slowest_files"], timing_source_type
        ),
        "timeout_interpretation": _timeout_interpretation(),
        "warnings": warnings,
        "blocked_reasons": blockers,
        "incomplete_reasons": incomplete,
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "alternative_next_phase": dict(ALTERNATIVE_NEXT_PHASE),
        "guardrails": _guardrails(policy_violation_markers),
        "boundaries": list(BOUNDARIES),
        "final_verdict": {
            "status": report_status,
            "ready_for_next_phase": report_status in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
            "recommended_next_phase": RECOMMENDED_NEXT_PHASE["phase_id"],
            "message": (
                "Timing report is ready for OPS.TEST.3 manifest planning."
                if report_status == STATUS_READY
                else f"Timing report status is {report_status}."
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


def render_slow_test_timing_report_markdown(report: dict[str, Any]) -> str:
    """Render a slow-test timing report as Markdown."""
    lines: list[str] = [
        "# Slow Test Timing Report",
        "",
        f"> {_md(report.get('guardrail_note') or GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report status:** `{_md(report.get('report_status', ''))}`",
        f"- **Timing source:** `{_md(report.get('timing_source_type', ''))}`",
        f"- **Observed runtime:** `{_md(report.get('total_observed_runtime_human', ''))}`",
        f"- **Collected tests:** {report.get('collected_test_count', 0)}",
        f"- **Collected files:** {report.get('collected_file_count', 0)}",
        "",
        "## Slowest Tests",
        "",
    ]
    lines.extend(_list_lines(report.get("slowest_tests")))
    lines.extend(["", "## Slowest Files", ""])
    lines.extend(_list_lines(report.get("slowest_files")))
    lines.extend(["", "## Runtime Buckets", ""])
    lines.extend(_dict_lines(report.get("runtime_buckets")))
    lines.extend(["", "## Recommended Profiles", ""])
    lines.extend(_list_lines(report.get("recommended_profiles")))
    lines.extend(["", "## Recommended Timeouts", ""])
    lines.extend(_dict_lines(report.get("recommended_timeouts")))
    lines.extend(["", "## Suite Split Recommendations", ""])
    lines.extend(_list_lines(report.get("suite_split_recommendations")))
    lines.extend(["", "## Timeout Interpretation", ""])
    lines.extend(_dict_lines(report.get("timeout_interpretation")))
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


def write_slow_test_timing_report(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_ROOT,
    report_id: str = "",
    created_at: str = "",
    timing_text: str | None = None,
    manual_timing_map: dict[str, Any] | None = None,
    allow_sample_timing: bool = True,
    source_profile_audit_path: str | Path = DEFAULT_PROFILE_AUDIT_PATH,
    source_timing_log_path: str | Path = "",
) -> dict[str, Any]:
    """Build and write OPS.TEST.2 JSON/Markdown timing report artifacts."""
    report = build_slow_test_timing_report(
        repo_root=repo_root,
        report_id=report_id,
        created_at=created_at,
        timing_text=timing_text,
        manual_timing_map=manual_timing_map,
        allow_sample_timing=allow_sample_timing,
        source_profile_audit_path=source_profile_audit_path,
        source_timing_log_path=source_timing_log_path,
    )
    out = Path(output_dir)
    if not out.is_absolute():
        out = Path(repo_root or ".") / out
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_slow_test_timing_report_markdown(report), encoding="utf-8")
    return {
        "ok": report["report_status"] in {STATUS_READY, STATUS_READY_WITH_WARNINGS},
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
