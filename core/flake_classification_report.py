"""EVAL.3 - Flake Classification Report (report-only).

Reads existing EVAL.1 ledger artifacts, EVAL.2 comparison artifacts, and benchmark
report artifacts as fallback evidence, then classifies benchmark case stability for
human review.

Core principle: EVAL.3 classifies existing evidence. It does not run benchmarks,
call models, apply patches, edit benchmark cases, run validation, contact network
services, write to a database, launch workers, or merge. It only reads existing
artifact files and writes a triage report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.benchmark_run_ledger import DEFAULT_INPUT_GLOB, build_ledger, load_benchmark_reports


REPORT_KIND = "flake_classification_report"

DEFAULT_LEDGER_PATH = ".agent/eval/benchmark_run_ledger/benchmark_run_ledger.json"
DEFAULT_COMPARE_ROOT = ".agent/eval/benchmark_report_compare"
DEFAULT_OUTPUT_ROOT = ".agent/eval/flake_classification_report"

JSON_NAME = "flake_classification_report.json"
MD_NAME = "flake_classification_report.md"

CLASSIFICATIONS: tuple[str, ...] = (
    "stable",
    "likely_flake",
    "likely_broken",
    "insufficient_history",
    "needs_rerun",
    "no_evidence",
)

ACTION_LABELS: tuple[str, ...] = (
    "no_action",
    "monitor",
    "rerun_single_case",
    "rerun_full_suite",
    "inspect_failure_notes",
    "consider_case_fix_only_after_repeated_failure",
    "do_not_patch_yet",
)

FLAKE_CLASSIFICATION_GUARDRAIL_NOTE = (
    "Flake Classification Report is report-only: it reads existing EVAL.1 ledger "
    "artifacts, EVAL.2 comparison artifacts, and benchmark report artifacts as "
    "fallback evidence, then classifies benchmark stability for human review. It "
    "does not run benchmarks, call models, apply patches, edit benchmark cases, "
    "run validation, contact network services, write to a database, launch workers, "
    "or merge. It only reads artifacts and writes a triage report."
)


def _norm(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve(repo_path: str | Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(repo_path) / path


def _guardrails() -> dict[str, bool]:
    return {
        "benchmark_run_performed": False,
        "model_call_performed": False,
        "patch_applied": False,
        "benchmark_case_modified": False,
        "validation_run": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


def load_ledger_report(repo_path: str | Path, ledger_path: str = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    """Read the optional EVAL.1 ledger; malformed input is a warning."""
    full = _resolve(repo_path, ledger_path)
    out: dict[str, Any] = {
        "loaded": False,
        "present": False,
        "path": _norm(full),
        "data": None,
        "warnings": [],
        "skipped_artifacts": [],
    }
    if not full.exists():
        out["warnings"].append(f"EVAL.1 ledger not found at {_norm(full)}")
        return out
    out["present"] = True
    try:
        data = json.loads(full.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        out["warnings"].append(f"EVAL.1 ledger at {_norm(full)} could not be read (skipped)")
        out["skipped_artifacts"].append({"path": _norm(full), "reason": "malformed_or_unreadable_ledger"})
        return out
    if not isinstance(data, dict):
        out["warnings"].append(f"EVAL.1 ledger at {_norm(full)} is not a JSON object (skipped)")
        out["skipped_artifacts"].append({"path": _norm(full), "reason": "non_object_ledger"})
        return out
    out["loaded"] = True
    out["data"] = data
    return out


def load_compare_reports(repo_path: str | Path, compare_root: str = DEFAULT_COMPARE_ROOT) -> dict[str, Any]:
    """Read EVAL.2 comparison reports under ``compare_root``."""
    root = _resolve(repo_path, compare_root)
    out: dict[str, Any] = {
        "loaded": 0,
        "present": False,
        "root": _norm(root),
        "reports": [],
        "warnings": [],
        "skipped_artifacts": [],
    }
    if not root.exists():
        out["warnings"].append(f"EVAL.2 compare root not found at {_norm(root)}")
        return out
    if not root.is_dir():
        out["warnings"].append(f"EVAL.2 compare root at {_norm(root)} is not a directory")
        out["skipped_artifacts"].append({"path": _norm(root), "reason": "compare_root_not_directory"})
        return out
    out["present"] = True
    paths = sorted(root.glob("*.json"))
    if not paths:
        out["warnings"].append(f"no EVAL.2 compare reports found under {_norm(root)}")
        return out
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out["warnings"].append(f"skipped malformed compare report {_norm(path)}")
            out["skipped_artifacts"].append({"path": _norm(path), "reason": "malformed_compare_report"})
            continue
        if not isinstance(data, dict):
            out["warnings"].append(f"skipped non-object compare report {_norm(path)}")
            out["skipped_artifacts"].append({"path": _norm(path), "reason": "non_object_compare_report"})
            continue
        out["reports"].append(data)
    out["loaded"] = len(out["reports"])
    return out


def _label_list(values: Any) -> list[str]:
    labels: list[str] = []
    if isinstance(values, list):
        for value in values:
            text = str(value or "").strip()
            if text and text not in labels:
                labels.append(text)
    return labels


def _blank_evidence(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "pass_count": 0,
        "fail_count": 0,
        "seen_runs": 0,
        "latest_status": "",
        "latest_run_id": "",
        "latest_scope": "",
        "evidence_labels": [],
        "eval2_classifications": [],
        "sources": [],
    }


def _add_label(evidence: dict[str, Any], label: str) -> None:
    if label and label not in evidence["evidence_labels"]:
        evidence["evidence_labels"].append(label)


def _add_source(evidence: dict[str, Any], source: str) -> None:
    if source and source not in evidence["sources"]:
        evidence["sources"].append(source)


def _ledger_flake_ids(ledger_data: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in ledger_data.get("flake_candidates") or []:
        if isinstance(item, dict):
            case_id = str(item.get("case_id") or "")
            if case_id:
                ids.add(case_id)
    return ids


def _evidence_from_ledger_case(item: dict[str, Any], ledger_data: dict[str, Any], flake_ids: set[str]) -> dict[str, Any]:
    case_id = str(item.get("case_id") or "")
    evidence = _blank_evidence(case_id)
    evidence["pass_count"] = _as_int(item.get("pass_count"), 0)
    evidence["fail_count"] = _as_int(item.get("fail_count"), 0)
    evidence["seen_runs"] = _as_int(item.get("seen_runs"), evidence["pass_count"] + evidence["fail_count"])
    evidence["latest_status"] = str(item.get("latest_status") or "")
    latest_run = ledger_data.get("latest_run_summary") if isinstance(ledger_data.get("latest_run_summary"), dict) else {}
    evidence["latest_run_id"] = str(item.get("latest_run_id") or latest_run.get("run_id") or "")
    evidence["latest_scope"] = str(item.get("latest_scope") or "")
    for label in _label_list(item.get("notes")):
        _add_label(evidence, label)
    if item.get("suspected_flaky") or case_id in flake_ids:
        _add_label(evidence, "ledger_flake_candidate")
    _add_source(evidence, "ledger")
    return evidence


def _iter_compare_cases(report: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons = report.get("comparisons")
    if isinstance(comparisons, list):
        return [item for item in comparisons if isinstance(item, dict)]
    return [report] if str(report.get("case_id") or "") else []


def _evidence_from_compare_case(item: dict[str, Any]) -> dict[str, Any]:
    case_id = str(item.get("case_id") or "")
    evidence = _blank_evidence(case_id)
    counts = item.get("status_counts") if isinstance(item.get("status_counts"), dict) else {}
    timeline = item.get("case_timeline") if isinstance(item.get("case_timeline"), list) else []
    evidence["pass_count"] = _as_int(counts.get("pass"), 0)
    evidence["fail_count"] = _as_int(counts.get("fail"), 0)
    evidence["seen_runs"] = len(timeline) if timeline else evidence["pass_count"] + evidence["fail_count"]
    latest = item.get("latest_observation") if isinstance(item.get("latest_observation"), dict) else {}
    evidence["latest_status"] = str(latest.get("status") or "")
    evidence["latest_run_id"] = str(latest.get("run_id") or "")
    evidence["latest_scope"] = str(latest.get("suite_scope") or latest.get("scope") or "")
    for label in _label_list(item.get("evidence_labels")):
        _add_label(evidence, label)
    classification = str(item.get("classification") or "")
    if classification:
        evidence["eval2_classifications"].append(classification)
    if classification == "likely_flake":
        _add_label(evidence, "eval2_likely_flake")
    elif classification == "likely_broken":
        _add_label(evidence, "eval2_likely_broken")
    elif classification == "single_failure_only":
        _add_label(evidence, "single_failure_observed")
    elif classification == "single_pass_only":
        _add_label(evidence, "single_pass_only")
    ledger_ref = item.get("ledger_reference") if isinstance(item.get("ledger_reference"), dict) else {}
    if ledger_ref.get("case_is_flake_candidate"):
        _add_label(evidence, "ledger_flake_candidate")
    for label in _label_list(ledger_ref.get("ledger_notes")):
        _add_label(evidence, label)
    _add_source(evidence, "compare")
    return evidence


def _merge_evidence(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        merged = dict(incoming)
        merged["evidence_labels"] = list(incoming.get("evidence_labels") or [])
        merged["eval2_classifications"] = list(incoming.get("eval2_classifications") or [])
        merged["sources"] = list(incoming.get("sources") or [])
        return merged

    merged = dict(existing)
    if _as_int(incoming.get("seen_runs"), 0) > _as_int(existing.get("seen_runs"), 0):
        for key in ("pass_count", "fail_count", "seen_runs", "latest_status", "latest_run_id", "latest_scope"):
            merged[key] = incoming.get(key)
    elif not merged.get("latest_run_id") and incoming.get("latest_run_id"):
        for key in ("latest_status", "latest_run_id", "latest_scope"):
            merged[key] = incoming.get(key)

    merged["evidence_labels"] = list(existing.get("evidence_labels") or [])
    for label in incoming.get("evidence_labels") or []:
        if label not in merged["evidence_labels"]:
            merged["evidence_labels"].append(label)
    merged["eval2_classifications"] = list(existing.get("eval2_classifications") or [])
    for classification in incoming.get("eval2_classifications") or []:
        if classification not in merged["eval2_classifications"]:
            merged["eval2_classifications"].append(classification)
    merged["sources"] = list(existing.get("sources") or [])
    for source in incoming.get("sources") or []:
        if source not in merged["sources"]:
            merged["sources"].append(source)
    return merged


def _source_text(sources: list[str]) -> str:
    order = {"ledger": 0, "compare": 1, "benchmark_reports": 2}
    return "+".join(sorted(sources, key=lambda item: (order.get(item, 99), item)))


def _classification_reason(evidence: dict[str, Any], classification: str) -> str:
    pass_count = _as_int(evidence.get("pass_count"), 0)
    fail_count = _as_int(evidence.get("fail_count"), 0)
    seen_runs = _as_int(evidence.get("seen_runs"), 0)
    labels = set(evidence.get("evidence_labels") or [])
    if classification == "stable":
        return "repeated passes and no failures were observed"
    if classification == "likely_flake":
        if "eval2_likely_flake" in labels:
            return "EVAL.2 classifies this case as likely_flake"
        if "within_run_retry_flake" in labels:
            return "within-run retry evidence marks this case as flaky"
        if "recovered_on_later_run" in labels:
            return "a failure recovered on a later run"
        return "mixed pass/fail evidence was observed for this case"
    if classification == "likely_broken":
        return "repeated failures were observed with no pass evidence"
    if classification == "needs_rerun":
        return "a single failure or weak latest failure needs rerun evidence before inspection"
    if classification == "insufficient_history":
        return f"only {seen_runs} usable observation(s) were found"
    return f"no usable pass/fail observations were found (pass={pass_count}, fail={fail_count})"


def _classify(evidence: dict[str, Any]) -> tuple[str, str, str, str]:
    pass_count = _as_int(evidence.get("pass_count"), 0)
    fail_count = _as_int(evidence.get("fail_count"), 0)
    seen_runs = _as_int(evidence.get("seen_runs"), 0)
    labels = set(evidence.get("evidence_labels") or [])
    eval2 = set(evidence.get("eval2_classifications") or [])
    latest_status = str(evidence.get("latest_status") or "")

    if pass_count == 0 and fail_count == 0:
        classification = "no_evidence" if seen_runs == 0 else "insufficient_history"
    elif "likely_flake" in eval2:
        classification = "likely_flake"
    elif labels.intersection({"ledger_flake_candidate", "within_run_retry_flake", "within_run_retry"}):
        classification = "likely_flake"
    elif pass_count > 0 and fail_count > 0:
        classification = "likely_flake"
    elif fail_count >= 2:
        classification = "likely_broken"
    elif fail_count == 1:
        classification = "needs_rerun"
    elif pass_count >= 2:
        classification = "stable"
    else:
        classification = "insufficient_history"

    if pass_count > 0 and fail_count > 0:
        _add_label(evidence, "mixed_pass_fail_history")
    if pass_count >= 2 and fail_count == 0:
        _add_label(evidence, "stable_passing")
    if pass_count == 1 and fail_count == 0:
        _add_label(evidence, "single_pass_only")
    if fail_count == 1 and pass_count == 0:
        _add_label(evidence, "single_failure_observed")
    if fail_count >= 2 and pass_count == 0:
        _add_label(evidence, "repeated_failure_no_pass")
    if latest_status == "fail":
        _add_label(evidence, "latest_is_fail")
    elif latest_status == "pass":
        _add_label(evidence, "latest_is_pass")

    confidence = _confidence(evidence, classification)
    action = _case_action(classification, latest_status)
    reason = _classification_reason(evidence, classification)
    return classification, confidence, action, reason


def _confidence(evidence: dict[str, Any], classification: str) -> str:
    pass_count = _as_int(evidence.get("pass_count"), 0)
    fail_count = _as_int(evidence.get("fail_count"), 0)
    labels = set(evidence.get("evidence_labels") or [])
    if classification == "stable":
        return "high" if pass_count >= 3 else "medium"
    if classification == "likely_flake":
        return "high" if (pass_count > 0 and fail_count > 0) or "eval2_likely_flake" in labels else "medium"
    if classification == "likely_broken":
        return "high" if fail_count >= 3 else "medium"
    return "low"


def _case_action(classification: str, latest_status: str) -> str:
    if classification == "stable":
        return "no_action"
    if classification == "likely_flake":
        return "rerun_single_case" if latest_status == "fail" else "monitor"
    if classification == "likely_broken":
        return "inspect_failure_notes"
    if classification == "needs_rerun":
        return "rerun_single_case"
    return "monitor"


def _triage_case(evidence: dict[str, Any]) -> dict[str, Any]:
    classification, confidence, action, reason = _classify(evidence)
    labels = sorted(set(evidence.get("evidence_labels") or []))
    return {
        "case_id": str(evidence.get("case_id") or ""),
        "classification": classification,
        "confidence": confidence,
        "evidence_labels": labels,
        "pass_count": _as_int(evidence.get("pass_count"), 0),
        "fail_count": _as_int(evidence.get("fail_count"), 0),
        "seen_runs": _as_int(evidence.get("seen_runs"), 0),
        "latest_status": str(evidence.get("latest_status") or ""),
        "latest_run_id": str(evidence.get("latest_run_id") or ""),
        "latest_scope": str(evidence.get("latest_scope") or ""),
        "reason": reason,
        "recommended_action": action,
        "source": _source_text(list(evidence.get("sources") or [])),
    }


def _case_priority(case: dict[str, Any]) -> tuple[int, str]:
    order = {
        "likely_broken": 0,
        "likely_flake": 1,
        "needs_rerun": 2,
        "insufficient_history": 3,
        "no_evidence": 4,
        "stable": 5,
    }
    return (order.get(str(case.get("classification")), 99), str(case.get("case_id") or ""))


def _classification_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in CLASSIFICATIONS}
    for case in cases:
        label = str(case.get("classification") or "")
        if label in counts:
            counts[label] += 1
    return counts


def _bucket(cases: list[dict[str, Any]], classification: str) -> list[dict[str, Any]]:
    return sorted([case for case in cases if case["classification"] == classification], key=lambda c: c["case_id"])


def _recommended_actions(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    def add(action: str, case_ids: list[str], reason: str) -> None:
        if action in ACTION_LABELS:
            actions.append({"action": action, "case_ids": sorted(case_ids), "reason": reason})

    stable = [c["case_id"] for c in cases if c["classification"] == "stable"]
    flakes = [c["case_id"] for c in cases if c["classification"] == "likely_flake"]
    flaky_latest_fail = [
        c["case_id"]
        for c in cases
        if c["classification"] == "likely_flake" and c.get("latest_status") == "fail"
    ]
    broken = [c["case_id"] for c in cases if c["classification"] == "likely_broken"]
    rerun = [c["case_id"] for c in cases if c["classification"] == "needs_rerun"]
    insufficient = [c["case_id"] for c in cases if c["classification"] in ("insufficient_history", "no_evidence")]

    if stable:
        add("no_action", stable, "Repeated passing evidence has no failure signal.")
    if flakes:
        add("monitor", flakes, "Likely flakes need monitoring and more evidence, not code changes.")
    if flaky_latest_fail:
        add("rerun_single_case", flaky_latest_fail, "Latest failing likely flakes should be rerun in isolation.")
    if rerun:
        add("rerun_single_case", rerun, "Single-failure cases need rerun evidence before any fix is considered.")
    if broken:
        add("inspect_failure_notes", broken, "Repeated failures should be inspected by a human.")
        add(
            "consider_case_fix_only_after_repeated_failure",
            broken,
            "Only consider a case fix after repeated failure evidence is reviewed.",
        )
    if insufficient:
        add("monitor", insufficient, "Insufficient-history cases need more observations.")
    if cases and (flakes or rerun or broken or insufficient):
        add("do_not_patch_yet", flakes + rerun + broken + insufficient, "This report never recommends automatic patches.")
    if not cases:
        add("monitor", [], "No cases were loaded; check artifact paths or produce EVAL.1/EVAL.2 evidence.")
    return sorted(actions, key=lambda item: (ACTION_LABELS.index(item["action"]), item["case_ids"]))


def _top_risks(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risky = [
        case
        for case in cases
        if case["classification"] in ("likely_broken", "needs_rerun")
        or (case["classification"] == "likely_flake" and case.get("latest_status") == "fail")
    ]
    out: list[dict[str, Any]] = []
    for case in sorted(risky, key=_case_priority):
        out.append(
            {
                "case_id": case["case_id"],
                "classification": case["classification"],
                "latest_status": case["latest_status"],
                "recommended_action": case["recommended_action"],
                "reason": case["reason"],
            }
        )
    return out


def _default_source_summary(
    ledger_data: Any,
    compare_reports: Any,
    benchmark_ledger_data: Any,
    fallback_used: bool,
) -> dict[str, Any]:
    ledger_cases = ledger_data.get("case_history") if isinstance(ledger_data, dict) else []
    benchmark_runs = benchmark_ledger_data.get("run_count") if isinstance(benchmark_ledger_data, dict) else 0
    return {
        "ledger_loaded": isinstance(ledger_data, dict),
        "ledger_case_count": len(ledger_cases) if isinstance(ledger_cases, list) else 0,
        "compare_reports_loaded": len(compare_reports) if isinstance(compare_reports, list) else 0,
        "benchmark_reports_loaded": _as_int(benchmark_runs, 0) if fallback_used else 0,
        "fallback_used": bool(fallback_used),
        "skipped_artifacts": [],
    }


def build_flake_classification_report(
    *,
    ledger_data: Any = None,
    compare_reports: Any = None,
    benchmark_ledger_data: Any = None,
    report_id: str = "",
    created_at: str = "",
    repo_path: str = "",
    ledger_path: str = DEFAULT_LEDGER_PATH,
    compare_root: str = DEFAULT_COMPARE_ROOT,
    input_glob: str = DEFAULT_INPUT_GLOB,
    source_summary: dict[str, Any] | None = None,
    warnings: Any = (),
    blockers: Any = (),
    limit: Any = None,
) -> dict[str, Any]:
    """Build the deterministic EVAL.3 classification report."""
    report_warnings = list(warnings) if isinstance(warnings, list) else list(warnings or [])
    report_blockers = list(blockers) if isinstance(blockers, list) else list(blockers or [])
    compare_list = [item for item in compare_reports if isinstance(item, dict)] if isinstance(compare_reports, list) else []
    fallback_used = not isinstance(ledger_data, dict) and not compare_list and isinstance(benchmark_ledger_data, dict)
    summary = dict(source_summary) if isinstance(source_summary, dict) else _default_source_summary(
        ledger_data, compare_list, benchmark_ledger_data, fallback_used
    )

    evidence_by_case: dict[str, dict[str, Any]] = {}

    if isinstance(ledger_data, dict):
        flake_ids = _ledger_flake_ids(ledger_data)
        case_history = ledger_data.get("case_history") if isinstance(ledger_data.get("case_history"), list) else []
        for item in case_history:
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("case_id") or "")
            if not case_id:
                continue
            evidence = _evidence_from_ledger_case(item, ledger_data, flake_ids)
            evidence_by_case[case_id] = _merge_evidence(evidence_by_case.get(case_id), evidence)

    for report in compare_list:
        for item in _iter_compare_cases(report):
            case_id = str(item.get("case_id") or "")
            if not case_id:
                continue
            evidence = _evidence_from_compare_case(item)
            evidence_by_case[case_id] = _merge_evidence(evidence_by_case.get(case_id), evidence)

    if not evidence_by_case and isinstance(benchmark_ledger_data, dict):
        case_history = benchmark_ledger_data.get("case_history") if isinstance(benchmark_ledger_data.get("case_history"), list) else []
        flake_ids = _ledger_flake_ids(benchmark_ledger_data)
        for item in case_history:
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("case_id") or "")
            if not case_id:
                continue
            evidence = _evidence_from_ledger_case(item, benchmark_ledger_data, flake_ids)
            evidence["sources"] = ["benchmark_reports"]
            evidence_by_case[case_id] = evidence
        summary["fallback_used"] = True

    cases = [_triage_case(evidence_by_case[case_id]) for case_id in sorted(evidence_by_case)]
    cases.sort(key=lambda item: item["case_id"])
    total_cases = len(cases)
    if isinstance(limit, int) and limit >= 0 and total_cases > limit:
        cases = sorted(cases, key=_case_priority)[:limit]
        cases.sort(key=lambda item: item["case_id"])
        report_warnings.append(f"classification report limited to {limit} of {total_cases} case(s)")

    if not cases:
        report_warnings.append("no flake classification evidence found in ledger, compare reports, or benchmark reports")

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": FLAKE_CLASSIFICATION_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm(repo_path) if repo_path else "",
        "ledger_path": str(ledger_path or ""),
        "compare_root": str(compare_root or ""),
        "input_glob": str(input_glob or ""),
        "source_summary": summary,
        "case_count": len(cases),
        "classification_counts": _classification_counts(cases),
        "stable_cases": _bucket(cases, "stable"),
        "likely_flakes": _bucket(cases, "likely_flake"),
        "likely_broken_cases": _bucket(cases, "likely_broken"),
        "insufficient_history_cases": _bucket(cases, "insufficient_history"),
        "needs_rerun_cases": _bucket(cases, "needs_rerun"),
        "recommended_actions": _recommended_actions(cases),
        "top_risks": _top_risks(cases),
        "warnings": sorted(set(str(item) for item in report_warnings)),
        "blockers": sorted(set(str(item) for item in report_blockers)),
        "guardrails": _guardrails(),
    }


def _fmt(value: Any) -> str:
    return "(none)" if value is None or value == "" else _md(value)


def _render_case_table(lines: list[str], cases: list[dict[str, Any]], empty: str) -> None:
    if not cases:
        lines.append(empty)
        lines.append("")
        return
    lines += [
        "| Case | Confidence | Pass | Fail | Seen | Latest | Action | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        lines.append(
            f"| `{_md(case.get('case_id'))}` | {_md(case.get('confidence'))} | "
            f"{case.get('pass_count')} | {case.get('fail_count')} | {case.get('seen_runs')} | "
            f"`{_md(case.get('latest_status'))}` | `{_md(case.get('recommended_action'))}` | "
            f"{_md(case.get('source'))} |"
        )
    lines.append("")


def render_flake_classification_markdown(report: dict[str, Any]) -> str:
    """Render the report as operator-facing Markdown."""
    summary = report.get("source_summary") if isinstance(report.get("source_summary"), dict) else {}
    counts = report.get("classification_counts") if isinstance(report.get("classification_counts"), dict) else {}
    lines: list[str] = [
        "# Flake Classification Report",
        "",
        f"> {report.get('guardrail_note', FLAKE_CLASSIFICATION_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.3 classifies existing benchmark stability evidence for human review. It runs nothing and changes nothing._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_fmt(report.get('report_id'))}`",
        f"- **Created at:** `{_fmt(report.get('created_at'))}`",
        f"- **Repo path:** `{_fmt(report.get('repo_path'))}`",
        f"- **Case count:** {report.get('case_count', 0)}",
        "",
        "## Source Coverage",
        "",
        f"- **Ledger loaded:** {str(bool(summary.get('ledger_loaded'))).lower()}",
        f"- **Ledger case count:** {summary.get('ledger_case_count', 0)}",
        f"- **Compare reports loaded:** {summary.get('compare_reports_loaded', 0)}",
        f"- **Benchmark reports loaded:** {summary.get('benchmark_reports_loaded', 0)}",
        f"- **Fallback used:** {str(bool(summary.get('fallback_used'))).lower()}",
        f"- **Skipped artifacts:** {len(summary.get('skipped_artifacts') or [])}",
        "",
        "## Classification Counts",
        "",
        "| Classification | Count |",
        "| --- | --- |",
    ]
    for label in CLASSIFICATIONS:
        lines.append(f"| `{label}` | {counts.get(label, 0)} |")
    lines.append("")

    lines += ["## Likely Flakes", ""]
    _render_case_table(lines, report.get("likely_flakes") or [], "_None._")

    lines += ["## Likely Broken Cases", ""]
    _render_case_table(lines, report.get("likely_broken_cases") or [], "_None._")

    lines += ["## Needs Rerun", ""]
    _render_case_table(lines, report.get("needs_rerun_cases") or [], "_None._")

    lines += ["## Stable Cases", ""]
    _render_case_table(lines, report.get("stable_cases") or [], "_None._")

    lines += ["## Recommended Human Actions", ""]
    actions = report.get("recommended_actions") or []
    if actions:
        for action in actions:
            case_ids = ", ".join(action.get("case_ids") or []) or "(none)"
            lines.append(f"- `{_md(action.get('action'))}`: {_md(action.get('reason'))} Cases: {case_ids}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    if blockers:
        for blocker in blockers:
            lines.append(f"- {_md(blocker)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Boundaries", ""]
    lines += [
        "- EVAL.3 does not run benchmarks.",
        "- EVAL.3 does not call models.",
        "- EVAL.3 does not apply patches.",
        "- EVAL.3 does not edit benchmark cases.",
        "- EVAL.3 does not run validation.",
        "- EVAL.3 does not contact network services.",
        "- EVAL.3 does not launch workers.",
        "- EVAL.3 is a report-only triage tool.",
        "",
    ]
    return "\n".join(lines) + "\n"


def write_flake_classification_report(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    compare_root: str = DEFAULT_COMPARE_ROOT,
    input_glob: str = DEFAULT_INPUT_GLOB,
    report_id: str = "",
    created_at: str = "",
    limit: Any = None,
) -> dict[str, Any]:
    """Load existing artifacts and write the EVAL.3 JSON + Markdown report."""
    ledger = load_ledger_report(repo_path, ledger_path)
    compare = load_compare_reports(repo_path, compare_root)

    warnings = list(ledger["warnings"]) + list(compare["warnings"])
    skipped = list(ledger["skipped_artifacts"]) + list(compare["skipped_artifacts"])
    benchmark_ledger_data = None
    benchmark_loaded = 0
    fallback_used = False

    if not ledger["loaded"] and not compare["reports"]:
        loaded = load_benchmark_reports(repo_path, input_glob)
        warnings.extend(loaded["warnings"])
        benchmark_loaded = len(loaded["entries"])
        if loaded["entries"]:
            benchmark_ledger_data = build_ledger(
                loaded["entries"],
                ledger_id="flake-classification-fallback",
                created_at=str(created_at or ""),
                repo_path=str(repo_path),
                input_glob=input_glob,
                scan_warnings=[],
                matched_count=loaded["matched_count"],
            )
            fallback_used = True

    source_summary = {
        "ledger_loaded": bool(ledger["loaded"]),
        "ledger_case_count": len((ledger["data"] or {}).get("case_history") or []) if ledger["loaded"] else 0,
        "compare_reports_loaded": len(compare["reports"]),
        "benchmark_reports_loaded": benchmark_loaded,
        "fallback_used": fallback_used,
        "skipped_artifacts": skipped,
    }

    report = build_flake_classification_report(
        ledger_data=ledger["data"],
        compare_reports=compare["reports"],
        benchmark_ledger_data=benchmark_ledger_data,
        report_id=report_id,
        created_at=created_at,
        repo_path=str(repo_path),
        ledger_path=ledger_path,
        compare_root=compare_root,
        input_glob=input_glob,
        source_summary=source_summary,
        warnings=warnings,
        limit=limit,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_flake_classification_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
