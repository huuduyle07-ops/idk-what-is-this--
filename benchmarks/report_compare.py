from __future__ import annotations

from typing import Any


def report_success_rate(report: dict[str, Any]) -> float:
    value = report.get("success_rate")
    if isinstance(value, (int, float)):
        return float(value)

    total = int(report.get("total") or 0)
    skipped = int(report.get("skipped") or 0)
    passed = int(report.get("passed") or 0)
    runnable = total - skipped
    return passed / runnable if runnable else 0.0


def runnable_count(report: dict[str, Any]) -> int:
    total = int(report.get("total") or 0)
    skipped = int(report.get("skipped") or 0)
    return max(0, total - skipped)


def regression_comparison(
    old_report: dict[str, Any] | None,
    new_report: dict[str, Any],
    *,
    threshold_pp: float = 5.0,
    min_runnable: int = 5,
    require_same_total: bool = True,
) -> dict[str, Any]:
    if not old_report:
        return {
            "checked": False,
            "reason": "no_previous_report",
            "alert": None,
        }

    old_runnable = runnable_count(old_report)
    new_runnable = runnable_count(new_report)

    base = {
        "old_runnable": old_runnable,
        "new_runnable": new_runnable,
        "threshold_pp": threshold_pp,
        "min_runnable": min_runnable,
        "require_same_total": require_same_total,
    }

    if old_runnable < min_runnable or new_runnable < min_runnable:
        return {
            **base,
            "checked": False,
            "reason": "too_few_cases",
            "alert": None,
        }

    if require_same_total and old_runnable != new_runnable:
        return {
            **base,
            "checked": False,
            "reason": "report_size_mismatch",
            "alert": None,
        }

    old_rate = report_success_rate(old_report)
    new_rate = report_success_rate(new_report)
    drop_pp = (old_rate - new_rate) * 100.0

    alert = None
    if drop_pp > threshold_pp:
        old_stamp = old_report.get("brain_stamp") or {}
        new_stamp = new_report.get("brain_stamp") or {}
        alert = {
            "kind": "regression",
            "drop_pp": round(drop_pp, 2),
            "old_success_rate": round(old_rate * 100.0, 1),
            "new_success_rate": round(new_rate * 100.0, 1),
            "old_total": old_report.get("total"),
            "new_total": new_report.get("total"),
            "old_passed": old_report.get("passed"),
            "new_passed": new_report.get("passed"),
            "old_flaky": old_report.get("flaky", 0),
            "new_flaky": new_report.get("flaky", 0),
            "old_git_sha": old_stamp.get("git_sha"),
            "new_git_sha": new_stamp.get("git_sha"),
            "old_dirty": old_stamp.get("git_dirty"),
            "new_dirty": new_stamp.get("git_dirty"),
            "old_prompt_config_hash": old_stamp.get("prompt_config_hash"),
            "new_prompt_config_hash": new_stamp.get("prompt_config_hash"),
        }

    return {
        **base,
        "checked": True,
        "reason": None,
        "old_success_rate": round(old_rate * 100.0, 1),
        "new_success_rate": round(new_rate * 100.0, 1),
        "drop_pp": round(drop_pp, 2),
        "alert": alert,
    }


def regression_alert(
    old_report: dict[str, Any] | None,
    new_report: dict[str, Any],
    *,
    threshold_pp: float = 5.0,
    min_runnable: int = 5,
    require_same_total: bool = True,
) -> dict[str, Any] | None:
    comparison = regression_comparison(
        old_report,
        new_report,
        threshold_pp=threshold_pp,
        min_runnable=min_runnable,
        require_same_total=require_same_total,
    )
    return comparison.get("alert")