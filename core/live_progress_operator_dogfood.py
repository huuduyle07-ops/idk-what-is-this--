"""DOGFOOD.1A: pure, report-only framework for safe operator observations."""
from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

THIS_PHASE_ID = "DOGFOOD.1A"
REPORT_KIND = "live_progress_operator_evaluation"
JSON_NAME = "live_progress_operator_evaluation.json"
MD_NAME = "live_progress_operator_evaluation.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "dogfood" / "live_progress_operator_evaluation"
APPROVED_STAGES = ("request_received", "model_response_received", "final_response_ready", "error_reported")
TERMINAL_STAGES = ("final_response_ready", "error_reported")
FRESHNESS_STATUSES = ("fresh", "recent", "terminal", "stale", "possibly_abandoned", "unknown")
TASK_CATEGORIES = ("chat_or_explanation", "code_analysis", "patch_generation", "error_path", "project_planning", "other")
REFRESH_MODES = ("manual", "bounded_polling", "manual_and_bounded_polling", "not_used")
TERMINAL_OUTCOMES = ("response_like", "error", "nonterminal", "unknown")
STOP_REASONS = ("terminal", "association_changed", "duration_limit", "request_budget_exhausted", "consecutive_error_limit", "operator_stopped", "not_applicable", "unknown")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_ABSOLUTE_PATH = re.compile(r"(?i)(?:\b[a-z]:[\\/]|(?:^|[\s\"'])/(?:home|users|tmp|var|etc|opt|private|mnt)/|\\\\)")
_REQUIRED = (
    "observation_id", "real_run_confirmed", "evaluation_date", "task_category", "safe_task_summary", "writer_enabled", "polling_permitted", "polling_explicitly_started", "refresh_mode", "snapshot_associated", "stages_seen", "terminal_state_seen", "terminal_outcome", "freshness_statuses_seen", "polling_stop_reason", "progress_panel_used", "operator_uncertainty_before", "operator_uncertainty_during", "operator_uncertainty_after", "stage_clarity_rating", "freshness_helpfulness_rating", "refresh_usability_rating", "polling_usefulness_rating", "progress_validation_confusion", "progress_approval_confusion", "discoverability_rating", "stage_coverage_understood", "freshness_assessment", "manual_refresh_assessment", "polling_assessment", "discoverability_assessment", "operator_notes", "problems_observed", "suggested_improvements", "sensitive_content_removed", "evidence_refs",
)
_OPTIONAL = ("synthetic_test_fixture",)
_FORBIDDEN_KEYS = ("prompt", "model_response", "raw_response", "patch_content", "repository_file", "credential", "secret", "absolute_path")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _manual(data: dict[str, Any]) -> bool:
    return data.get("refresh_mode") in {"manual", "manual_and_bounded_polling"}


def _polling(data: dict[str, Any]) -> bool:
    return data.get("refresh_mode") in {"bounded_polling", "manual_and_bounded_polling"}


def _has_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_ABSOLUTE_PATH.search(value))
    if isinstance(value, dict):
        return any(_has_path(item) for item in value.values())
    return isinstance(value, list) and any(_has_path(item) for item in value)


def _mapping(data: Any, field: str, keys: tuple[str, ...], errors: list[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        errors.append(f"{field} must be an object")
        return {}
    missing = [key for key in keys if key not in data]
    extra = sorted(set(data) - set(keys))
    if missing:
        errors.append(f"{field} missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{field} has unsupported fields: {', '.join(extra)}")
    return data


def validate_operator_observation(observation: Any) -> dict[str, Any]:
    """Validate a sanitized observation without changing it or touching product state."""
    if not isinstance(observation, dict):
        return {"valid": False, "errors": ["observation must be an object"], "observation_id": ""}
    data, errors = observation, []
    missing = [field for field in _REQUIRED if field not in data]
    extra = sorted(set(data) - set(_REQUIRED) - set(_OPTIONAL))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    if extra:
        errors.append(f"unsupported observation fields: {', '.join(extra)}")
    for field in data:
        if any(token in field.lower() for token in _FORBIDDEN_KEYS):
            errors.append(f"unsafe raw or sensitive field is not allowed: {field}")
    if not isinstance(data.get("observation_id"), str) or not _ID.fullmatch(data["observation_id"]):
        errors.append("observation_id must be a safe identifier")
    try:
        date.fromisoformat(data.get("evaluation_date", ""))
    except (TypeError, ValueError):
        errors.append("evaluation_date must be an ISO date")
    if data.get("task_category") not in TASK_CATEGORIES:
        errors.append("task_category is not in the safe taxonomy")
    for field in ("safe_task_summary", "operator_notes"):
        if not isinstance(data.get(field), str) or not data[field].strip() or len(data[field]) > (240 if field == "safe_task_summary" else 500):
            errors.append(f"{field} must be a safe non-empty string within its length limit")
    bools = ("real_run_confirmed", "writer_enabled", "polling_permitted", "polling_explicitly_started", "snapshot_associated", "terminal_state_seen", "progress_panel_used", "progress_validation_confusion", "progress_approval_confusion", "stage_coverage_understood", "sensitive_content_removed")
    for field in bools:
        if not isinstance(data.get(field), bool):
            errors.append(f"{field} must be boolean")
    synthetic = data.get("synthetic_test_fixture", False)
    if not isinstance(synthetic, bool):
        errors.append("synthetic_test_fixture must be boolean when present")
    elif synthetic and data.get("real_run_confirmed") is not False:
        errors.append("synthetic_test_fixture must not claim a real run")
    elif not synthetic and data.get("real_run_confirmed") is not True:
        errors.append("real_run_confirmed must be true for real evidence")
    if data.get("sensitive_content_removed") is not True:
        errors.append("sensitive_content_removed must be true")
    if data.get("refresh_mode") not in REFRESH_MODES:
        errors.append("refresh_mode is invalid")
    if data.get("terminal_outcome") not in TERMINAL_OUTCOMES:
        errors.append("terminal_outcome is invalid")
    if data.get("polling_stop_reason") not in STOP_REASONS:
        errors.append("polling_stop_reason is invalid")
    for field in ("stages_seen", "freshness_statuses_seen", "problems_observed", "suggested_improvements", "evidence_refs"):
        if not _strings(data.get(field)):
            errors.append(f"{field} must be a list of strings")
    if isinstance(data.get("freshness_statuses_seen"), list) and set(data["freshness_statuses_seen"]) - set(FRESHNESS_STATUSES):
        errors.append("freshness_statuses_seen has unsupported values")
    if isinstance(data.get("evidence_refs"), list) and any(not _ID.fullmatch(item) for item in data["evidence_refs"]):
        errors.append("evidence_refs must use safe identifiers only")
    for field in ("operator_uncertainty_before", "operator_uncertainty_during", "operator_uncertainty_after"):
        if not _int(data.get(field), 0, 4):
            errors.append(f"{field} must be an integer from 0 to 4")
    for field in ("stage_clarity_rating", "freshness_helpfulness_rating", "refresh_usability_rating", "discoverability_rating"):
        if not _int(data.get(field), 1, 5):
            errors.append(f"{field} must be an integer from 1 to 5")
    if _polling(data):
        if not _int(data.get("polling_usefulness_rating"), 1, 5):
            errors.append("polling_usefulness_rating must be an integer from 1 to 5 when polling is used")
        if data.get("polling_permitted") is not True or data.get("polling_explicitly_started") is not True:
            errors.append("bounded polling requires permitted and explicitly started evidence")
    elif data.get("polling_usefulness_rating") is not None:
        errors.append("polling_usefulness_rating must be null when polling is not used")
    if not _polling(data) and data.get("polling_explicitly_started") is True:
        errors.append("polling_explicitly_started requires bounded polling mode")
    fresh = _mapping(data.get("freshness_assessment"), "freshness_assessment", ("labels_seen", "advisory_notice_understood", "stale_mistaken_for_failure", "terminal_mistaken_for_success", "possibly_abandoned_mistaken_for_confirmed_crash"), errors)
    if not _strings(fresh.get("labels_seen")) or set(fresh.get("labels_seen", [])) - set(FRESHNESS_STATUSES):
        errors.append("freshness_assessment.labels_seen has unsupported values")
    for key in ("advisory_notice_understood", "stale_mistaken_for_failure", "terminal_mistaken_for_success", "possibly_abandoned_mistaken_for_confirmed_crash"):
        if not isinstance(fresh.get(key), bool):
            errors.append(f"freshness_assessment.{key} must be boolean")
    discover = _mapping(data.get("discoverability_assessment"), "discoverability_assessment", ("writer_enablement_found", "polling_enablement_found", "start_progress_updates_found", "stop_progress_updates_found", "refresh_progress_found", "freshness_label_understood", "advisory_notice_understood"), errors)
    if any(not isinstance(value, bool) for value in discover.values()):
        errors.append("discoverability_assessment values must be boolean")
    manual = data.get("manual_refresh_assessment")
    if _manual(data):
        manual = _mapping(manual, "manual_refresh_assessment", ("associated_snapshot_discovered", "refresh_button_discoverable", "one_click_one_get", "loading_state_understandable", "refresh_result_understandable", "repeated_clicking_burden_rating", "preference_compared_with_polling"), errors)
        if any(not isinstance(manual.get(key), bool) for key in ("associated_snapshot_discovered", "refresh_button_discoverable", "one_click_one_get", "loading_state_understandable", "refresh_result_understandable")):
            errors.append("manual_refresh_assessment required flags must be boolean")
        if not _int(manual.get("repeated_clicking_burden_rating"), 1, 5) or manual.get("preference_compared_with_polling") not in {"manual", "bounded_polling", "no_preference", "not_applicable"}:
            errors.append("manual_refresh_assessment rating or preference is invalid")
    elif manual is not None:
        errors.append("manual_refresh_assessment must be null when manual refresh is not used")
    polling = data.get("polling_assessment")
    if _polling(data):
        polling = _mapping(polling, "polling_assessment", ("explicit_start_confirmed", "automatic_start_absent", "request_overlap_observed", "stop_notice_clarity_rating", "polling_distraction_rating", "manual_refresh_preferred", "polling_changed_execution_behavior"), errors)
        if any(not isinstance(polling.get(key), bool) for key in ("explicit_start_confirmed", "automatic_start_absent", "request_overlap_observed", "manual_refresh_preferred", "polling_changed_execution_behavior")):
            errors.append("polling_assessment required flags must be boolean")
        if not _int(polling.get("stop_notice_clarity_rating"), 1, 5) or not _int(polling.get("polling_distraction_rating"), 1, 5):
            errors.append("polling_assessment ratings must be 1 to 5")
        if polling.get("explicit_start_confirmed") is not True:
            errors.append("polling_assessment.explicit_start_confirmed must be true")
    elif polling is not None:
        errors.append("polling_assessment must be null when polling is not used")
    if _has_path(data):
        errors.append("absolute paths are not allowed in operator observations")
    return {"valid": not errors, "errors": sorted(set(errors)), "observation_id": data.get("observation_id", "") if isinstance(data.get("observation_id"), str) else ""}


def normalize_operator_observation(observation: Any) -> dict[str, Any]:
    """Copy and normalize a valid observation; input values are never mutated."""
    result = validate_operator_observation(observation)
    if not result["valid"]:
        raise ValueError("invalid operator observation: " + "; ".join(result["errors"]))
    data = copy.deepcopy(observation)
    for field in ("safe_task_summary", "operator_notes"):
        data[field] = data[field].strip()
    for field in ("stages_seen", "problems_observed", "suggested_improvements", "evidence_refs"):
        data[field] = list(dict.fromkeys(item.strip() for item in data[field] if item.strip()))
    data["freshness_statuses_seen"] = [item for item in FRESHNESS_STATUSES if item in data["freshness_statuses_seen"]]
    data["freshness_assessment"]["labels_seen"] = [item for item in FRESHNESS_STATUSES if item in data["freshness_assessment"]["labels_seen"]]
    data["synthetic_test_fixture"] = bool(data.get("synthetic_test_fixture", False))
    data["manual_refresh_used"] = _manual(data)
    data["bounded_polling_used"] = _polling(data)
    data["uncertainty_reduction"] = data["operator_uncertainty_before"] - data["operator_uncertainty_after"]
    return data


def _finding(code: str, severity: str) -> dict[str, str]:
    return {"code": code, "severity": severity}


def score_operator_observation(observation: Any) -> dict[str, Any]:
    """Score a valid observation with deterministic advisory findings."""
    data = normalize_operator_observation(observation)
    stages, findings = data["stages_seen"], []
    unsupported = [stage for stage in stages if stage not in APPROVED_STAGES]
    rank = {"request_received": 1, "model_response_received": 2, "final_response_ready": 3, "error_reported": 3}
    observed_ranks = [rank[stage] for stage in stages if stage in rank]
    order_bad = any(b < a for a, b in zip(observed_ranks, observed_ranks[1:]))
    terminal_missing = data["terminal_state_seen"] and not any(stage in TERMINAL_STAGES for stage in stages)
    error_visible = data["terminal_outcome"] != "error" or "error_reported" in stages
    if unsupported: findings.append(_finding("unsupported_stage_claim", "moderate"))
    if order_bad: findings.append(_finding("stage_order_inconsistent", "major"))
    if terminal_missing: findings.append(_finding("terminal_stage_missing", "major"))
    if data["terminal_outcome"] == "error" and not error_visible: findings.append(_finding("error_stage_not_visible", "major"))
    findings.append(_finding("partial_coverage_understood" if data["stage_coverage_understood"] and not unsupported else "partial_coverage_confusing", "info" if data["stage_coverage_understood"] and not unsupported else "moderate"))
    if data["progress_validation_confusion"]: findings.append(_finding("progress_validation_confusion", "major"))
    if data["progress_approval_confusion"]: findings.append(_finding("progress_approval_confusion", "major"))
    freshness = data["freshness_assessment"]
    for key in ("stale_mistaken_for_failure", "terminal_mistaken_for_success", "possibly_abandoned_mistaken_for_confirmed_crash"):
        if freshness[key]: findings.append(_finding(key, "moderate"))
    if data["freshness_helpfulness_rating"] <= 2: findings.append(_finding("freshness_helpfulness_low", "moderate"))
    if data["stage_clarity_rating"] <= 2: findings.append(_finding("stage_labels_unclear", "moderate"))
    if data["discoverability_rating"] <= 2: findings.append(_finding("default_off_controls_hard_to_discover", "moderate"))
    manual, polling = data["manual_refresh_assessment"], data["polling_assessment"]
    if manual:
        for key, code in (("refresh_button_discoverable", "refresh_control_hard_to_discover"), ("one_click_one_get", "manual_refresh_request_behavior_unclear"), ("loading_state_understandable", "manual_refresh_loading_unclear"), ("refresh_result_understandable", "manual_refresh_result_unclear")):
            if not manual[key]: findings.append(_finding(code, "moderate"))
    if polling:
        if not polling["automatic_start_absent"]: findings.append(_finding("automatic_polling_observed", "blocker"))
        if polling["request_overlap_observed"]: findings.append(_finding("polling_request_overlap_observed", "blocker"))
        if polling["polling_changed_execution_behavior"]: findings.append(_finding("polling_changed_execution_behavior", "blocker"))
        if polling["stop_notice_clarity_rating"] <= 2: findings.append(_finding("polling_stop_notice_unclear", "moderate"))
        if polling["polling_distraction_rating"] >= 4: findings.append(_finding("polling_distracting", "moderate"))
    return {
        "observation_id": data["observation_id"], "synthetic_test_fixture": data["synthetic_test_fixture"], "included": not data["synthetic_test_fixture"], "uncertainty_reduction": data["uncertainty_reduction"],
        "stage_truthfulness": {"approved_stages_seen": [stage for stage in stages if stage in APPROVED_STAGES], "unsupported_stages": unsupported, "stage_order_inconsistent": order_bad, "terminal_stage_missing": terminal_missing, "error_stage_visible": error_visible, "partial_coverage_understood": data["stage_coverage_understood"], "partial_coverage_confusing": not data["stage_coverage_understood"], "terminal_state_is_not_validation": True, "terminal_state_is_not_approval": True},
        "freshness": {"labels_seen": data["freshness_statuses_seen"], "advisory_notice_understood": freshness["advisory_notice_understood"], "stale_mistaken_for_failure": freshness["stale_mistaken_for_failure"], "terminal_mistaken_for_success": freshness["terminal_mistaken_for_success"], "possibly_abandoned_mistaken_for_confirmed_crash": freshness["possibly_abandoned_mistaken_for_confirmed_crash"]},
        "manual_refresh": copy.deepcopy(manual), "polling": copy.deepcopy(polling), "findings": findings, "normalized_observation": data,
    }


def _average(values: list[int]) -> dict[str, Any]:
    return {"value": round(sum(values) / len(values), 1) if values else None, "sample_size": len(values)}


def _evidence_status(metrics: dict[str, Any]) -> str:
    if metrics["real_run_count"] < 3:
        return "dogfood_real_evidence_missing"
    if not (metrics["success_terminal_run_count"] and metrics["error_terminal_run_count"] and metrics["multistage_run_count"]):
        return "dogfood_real_evidence_partial"
    if metrics["real_run_count"] >= 5 and metrics["manual_refresh_run_count"] and metrics["bounded_polling_run_count"]:
        return "dogfood_real_evidence_sufficient"
    return "dogfood_real_evidence_sufficient_with_warnings"


def summarize_operator_runs(observations: Any) -> dict[str, Any]:
    """Validate, classify, and aggregate records without mutating inputs."""
    values = observations if isinstance(observations, list) else []
    results, included = [], []
    invalid_count = synthetic_count = 0
    for raw in values:
        validation = validate_operator_observation(raw)
        if not validation["valid"]:
            invalid_count += 1
            results.append({"observation_id": validation["observation_id"], "included": False, "status": "invalid", "errors": validation["errors"]})
            continue
        score = score_operator_observation(raw)
        if score["synthetic_test_fixture"]:
            synthetic_count += 1
            results.append({"observation_id": score["observation_id"], "included": False, "status": "synthetic_test_fixture", "errors": [], "score": score})
            continue
        included.append(score)
        results.append({"observation_id": score["observation_id"], "included": True, "status": "valid_real_observation", "errors": [], "score": score})
    normalized = [item["normalized_observation"] for item in included]
    metrics: dict[str, Any] = {
        "real_run_count": len(included), "valid_observation_count": len(included), "synthetic_test_fixture_count": synthetic_count, "invalid_observation_count": invalid_count, "excluded_observation_count": invalid_count + synthetic_count,
        "success_terminal_run_count": sum(item["terminal_outcome"] == "response_like" and "final_response_ready" in item["stages_seen"] for item in normalized),
        "error_terminal_run_count": sum(item["terminal_outcome"] == "error" and "error_reported" in item["stages_seen"] for item in normalized),
        "multistage_run_count": sum(len(item["stages_seen"]) >= 2 and any(stage not in TERMINAL_STAGES for stage in item["stages_seen"]) and any(stage in TERMINAL_STAGES for stage in item["stages_seen"]) for item in normalized),
        "manual_refresh_run_count": sum(item["manual_refresh_used"] for item in normalized), "bounded_polling_run_count": sum(item["bounded_polling_used"] for item in normalized),
        "average_stage_clarity": _average([item["stage_clarity_rating"] for item in normalized]), "average_freshness_helpfulness": _average([item["freshness_helpfulness_rating"] for item in normalized]), "average_refresh_usability": _average([item["refresh_usability_rating"] for item in normalized]), "average_polling_usefulness": _average([item["polling_usefulness_rating"] for item in normalized if item["polling_usefulness_rating"] is not None]), "average_discoverability": _average([item["discoverability_rating"] for item in normalized]), "average_uncertainty_reduction": _average([item["uncertainty_reduction"] for item in normalized]),
        "validation_confusion_count": sum(item["progress_validation_confusion"] for item in normalized), "approval_confusion_count": sum(item["progress_approval_confusion"] for item in normalized), "unsupported_stage_claim_count": sum(len(item["stage_truthfulness"]["unsupported_stages"]) for item in included), "runs_with_operator_problems": sum(bool(item["problems_observed"]) for item in normalized),
        "runs_preferring_manual_refresh": sum((item.get("manual_refresh_assessment") or {}).get("preference_compared_with_polling") == "manual" or (item.get("polling_assessment") or {}).get("manual_refresh_preferred") is True for item in normalized), "runs_preferring_bounded_polling": sum((item.get("manual_refresh_assessment") or {}).get("preference_compared_with_polling") == "bounded_polling" for item in normalized),
    }
    counts: Counter[str] = Counter()
    severities: dict[str, str] = {}
    for score in included:
        for finding in score["findings"]:
            counts[finding["code"]] += 1
            severities[finding["code"]] = finding["severity"]
    metrics["evidence_status"] = _evidence_status(metrics)
    return {"observation_results": results, "included_observations": normalized, "aggregate_metrics": metrics, "finding_counts": dict(sorted(counts.items())), "finding_severities": severities, "evidence_status": metrics["evidence_status"]}


def _recommendation(summary: dict[str, Any]) -> str:
    metrics = summary["aggregate_metrics"]
    if summary["evidence_status"] in {"dogfood_real_evidence_missing", "dogfood_real_evidence_partial"}:
        return "insufficient_real_evidence"
    if "blocker" in summary["finding_severities"].values():
        return "larger_ux_rework_needed"
    total = metrics["real_run_count"]
    if metrics["validation_confusion_count"] >= 2 or metrics["approval_confusion_count"] >= 2 or (total and sum(item["uncertainty_reduction"] <= 0 for item in summary["included_observations"]) * 2 >= total):
        return "larger_ux_rework_needed"
    if any(count >= 2 for count in summary["finding_counts"].values()) or any(metrics[key]["value"] is not None and metrics[key]["value"] < 3 for key in ("average_stage_clarity", "average_freshness_helpfulness", "average_refresh_usability", "average_discoverability")):
        return "small_corrective_phase_needed"
    if metrics["average_discoverability"]["value"] is not None and metrics["average_discoverability"]["value"] < 4:
        return "retain_with_documentation_followup"
    return "retain_without_change"


def _findings(summary: dict[str, Any], predicate: Any) -> list[dict[str, Any]]:
    return [{"code": code, "count": count, "severity": summary["finding_severities"].get(code, "info")} for code, count in summary["finding_counts"].items() if predicate(code)]


def build_live_progress_dogfood_report(observations: Any, *, created_at: str = "") -> dict[str, Any]:
    """Build an advisory report solely from supplied completed observations."""
    summary = summarize_operator_runs(observations)
    metrics = summary["aggregate_metrics"]
    blockers = _findings(summary, lambda code: summary["finding_severities"].get(code) == "blocker")
    warnings = ["single_operator_sample", "small_real_run_sample", "long_term_usage_unproven", "multi_user_discoverability_unproven", "default_off_feature_requires_manual_setup", "real_operator_evidence_pending", "synthetic_fixtures_do_not_count_as_real_evidence"]
    if metrics["real_run_count"] == 0:
        warnings.append("zero_confirmed_real_runs")
    if summary["evidence_status"] in {"dogfood_real_evidence_missing", "dogfood_real_evidence_partial"}:
        warnings.append(summary["evidence_status"])
    real_evaluation_complete = summary["evidence_status"] in {"dogfood_real_evidence_sufficient", "dogfood_real_evidence_sufficient_with_warnings"} and not blockers
    status = "live_progress_operator_dogfood_complete_with_warnings" if real_evaluation_complete else "insufficient_real_evidence"
    problems: Counter[str] = Counter()
    for observation in summary["included_observations"]:
        problems.update(observation["problems_observed"])
    strengths = []
    if metrics["average_uncertainty_reduction"]["value"] is not None and metrics["average_uncertainty_reduction"]["value"] > 0:
        strengths.append("Reported uncertainty decreased on average across included observations.")
    if metrics["real_run_count"] and not metrics["validation_confusion_count"] and not metrics["approval_confusion_count"]:
        strengths.append("No included observation reported validation or approval confusion.")
    return {
        "report_kind": REPORT_KIND, "phase_id": THIS_PHASE_ID, "created_at": created_at or _now(), "evaluation_status": status, "phase_split_status": "dogfood_phase_split_complete_with_warnings", "framework_status": "live_progress_operator_evaluation_framework_ready", "artifact_status": "live_progress_operator_evaluation_framework_ready_with_warnings", "framework_complete": True, "real_evaluation_complete": real_evaluation_complete, "real_evidence_required": True, "framework_statement": "The evaluation framework is complete, but no real operator evaluation has been completed." if not real_evaluation_complete else "The evaluation framework is complete and the supplied real-evidence coverage is sufficient for DOGFOOD.1B review.", "report_only": True,
        "real_run_count": metrics["real_run_count"], "minimum_real_runs_required": 3, "recommended_real_runs": 5,
        "synthetic_test_fixture_count": metrics["synthetic_test_fixture_count"], "invalid_observation_count": metrics["invalid_observation_count"], "excluded_observation_count": metrics["excluded_observation_count"],
        "coverage_summary": {"evidence_status": summary["evidence_status"], "success_terminal_covered": bool(metrics["success_terminal_run_count"]), "error_terminal_covered": bool(metrics["error_terminal_run_count"]), "multistage_covered": bool(metrics["multistage_run_count"]), "manual_refresh_covered": bool(metrics["manual_refresh_run_count"]), "bounded_polling_covered": bool(metrics["bounded_polling_run_count"])},
        "observation_results": summary["observation_results"], "aggregate_metrics": metrics,
        "stage_truthfulness_findings": _findings(summary, lambda code: "stage" in code or "coverage" in code), "freshness_findings": _findings(summary, lambda code: "freshness" in code or "stale" in code or "abandoned" in code), "manual_refresh_findings": _findings(summary, lambda code: "refresh" in code), "polling_findings": _findings(summary, lambda code: "polling" in code or "automatic" in code), "discoverability_findings": _findings(summary, lambda code: "discover" in code), "confusion_findings": _findings(summary, lambda code: "confusion" in code),
        "operator_problems": [{"problem": item, "count": count} for item, count in sorted(problems.items())], "strengths": strengths,
        "limitations": ["single-operator evaluation", "small run sample", "task diversity remains limited", "no long-term repeated-use evidence", "no multi-user usability evidence", "no production deployment evidence", "default-off configuration affects discoverability", "operator is already familiar with the project", "ratings are subjective", "no statistical claim is made"],
        "findings": _findings(summary, lambda _code: True), "decision_recommendation": _recommendation(summary),
        "runtime_behavior_changed": False, "ui_behavior_changed": False, "runtime_authority": False, "action_triggered": False,
        "checkpoint_relationship": {"checkpoint_reference": "UX.LIVE.CLOSE", "ux_live_remains_frozen": True, "dogfood_does_not_reopen_branch": True, "findings_are_evaluation_evidence_only": True, "future_corrective_work_requires_separately_approved_phase": True},
        "blockers": blockers, "warnings": warnings, "recommended_next_phase": "DOGFOOD.1B",
    }


def _md(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_live_progress_dogfood_markdown(report: Any) -> str:
    """Render only report data; terminal/freshness limitations stay explicit."""
    data, metrics, coverage = _dict(report), _dict(_dict(report).get("aggregate_metrics")), _dict(_dict(report).get("coverage_summary"))
    lines = ["# Live Progress Operator Evaluation", "", f"- Framework phase: `{_md(data.get('phase_id'))}`", f"- Framework status: `{_md(data.get('framework_status'))}`", f"- Evaluation status: `{_md(data.get('evaluation_status'))}`", f"- Real observations: `{_md(data.get('real_run_count'))}` / `{_md(data.get('minimum_real_runs_required'))}` minimum", f"- Evidence result: `{_md(coverage.get('evidence_status'))}`", f"- Decision recommendation: `{_md(data.get('decision_recommendation'))}`", "", _md(data.get("framework_statement")), "", "## Coverage", ""]
    for name in ("success_terminal_covered", "error_terminal_covered", "multistage_covered", "manual_refresh_covered", "bounded_polling_covered"):
        lines.append(f"- {_md(name)}: `{str(bool(coverage.get(name))).lower()}`")
    lines += ["", "## Aggregate metrics", "", "| Metric | Value | Sample size |", "|---|---:|---:|"]
    for name in ("average_stage_clarity", "average_freshness_helpfulness", "average_refresh_usability", "average_polling_usefulness", "average_discoverability", "average_uncertainty_reduction"):
        value = _dict(metrics.get(name))
        lines.append(f"| {_md(name)} | {_md(value.get('value'))} | {_md(value.get('sample_size'))} |")
    lines += ["", "## Findings", ""]
    findings = data.get("findings") or []
    lines.extend(f"- `{_md(_dict(item).get('severity'))}` `{_md(_dict(item).get('code'))}`: {_md(_dict(item).get('count'))}" for item in findings) if findings else ["- No included observation findings yet."]
    lines += ["", "## Boundaries", "", "- UX.LIVE remains frozen.", "- Terminal progress is not validation, benchmark success, approval, or patch application.", "- Freshness labels are advisory: stale is not failure and possibly abandoned is not a confirmed crash.", "- Any corrective work requires a separately approved phase.", "", "## Limitations", ""]
    lines.extend(f"- {_md(item)}" for item in data.get("limitations") or [])
    lines += ["", "## Warnings", ""]
    lines.extend(f"- `{_md(item)}`" for item in data.get("warnings") or [])
    return "\n".join(lines) + "\n"


def load_safe_operator_observations(input_root: str | Path) -> list[Any]:
    """Load JSON inputs only; a parse failure is retained as excluded evidence."""
    root = Path(input_root)
    if not root.is_dir():
        return []
    observations = []
    for path in sorted(root.glob("*.json")):
        try:
            observations.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, UnicodeError):
            observations.append({"load_error": f"could not parse observation {path.name}"})
    return observations


def write_live_progress_dogfood_report(report: dict[str, Any], output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Write only the JSON and Markdown report artifacts."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path, markdown_path = root / JSON_NAME, root / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_live_progress_dogfood_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "markdown_path": str(markdown_path), "report": report}
