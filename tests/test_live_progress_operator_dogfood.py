"""DOGFOOD.1A framework tests; all records here are synthetic test fixtures."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from core import live_progress_operator_dogfood as dogfood
from scripts import create_live_progress_operator_dogfood_report as cli


def _observation(observation_id: str = "safe-run-1", *, terminal: str = "response_like", polling: bool = False, synthetic: bool = False) -> dict:
    stages = ["request_received", "model_response_received", "final_response_ready"]
    if terminal == "error":
        stages = ["request_received", "error_reported"]
    mode = "manual_and_bounded_polling" if polling else "manual"
    return {
        "observation_id": observation_id,
        "real_run_confirmed": False if synthetic else True,
        "synthetic_test_fixture": synthetic,
        "evaluation_date": "2026-07-12",
        "task_category": "error_path" if terminal == "error" else "code_analysis",
        "safe_task_summary": "Review a small Python validation issue.",
        "writer_enabled": True,
        "polling_permitted": polling,
        "polling_explicitly_started": polling,
        "refresh_mode": mode,
        "snapshot_associated": True,
        "stages_seen": stages,
        "terminal_state_seen": True,
        "terminal_outcome": terminal,
        "freshness_statuses_seen": ["fresh", "terminal"],
        "polling_stop_reason": "terminal" if polling else "not_applicable",
        "progress_panel_used": True,
        "operator_uncertainty_before": 3,
        "operator_uncertainty_during": 2,
        "operator_uncertainty_after": 1,
        "stage_clarity_rating": 4,
        "freshness_helpfulness_rating": 4,
        "refresh_usability_rating": 4,
        "polling_usefulness_rating": 4 if polling else None,
        "progress_validation_confusion": False,
        "progress_approval_confusion": False,
        "discoverability_rating": 4,
        "stage_coverage_understood": True,
        "freshness_assessment": {
            "labels_seen": ["fresh", "terminal"],
            "advisory_notice_understood": True,
            "stale_mistaken_for_failure": False,
            "terminal_mistaken_for_success": False,
            "possibly_abandoned_mistaken_for_confirmed_crash": False,
        },
        "manual_refresh_assessment": {
            "associated_snapshot_discovered": True,
            "refresh_button_discoverable": True,
            "one_click_one_get": True,
            "loading_state_understandable": True,
            "refresh_result_understandable": True,
            "repeated_clicking_burden_rating": 2,
            "preference_compared_with_polling": "bounded_polling" if polling else "not_applicable",
        },
        "polling_assessment": {
            "explicit_start_confirmed": True,
            "automatic_start_absent": True,
            "request_overlap_observed": False,
            "stop_notice_clarity_rating": 4,
            "polling_distraction_rating": 2,
            "manual_refresh_preferred": False,
            "polling_changed_execution_behavior": False,
        } if polling else None,
        "discoverability_assessment": {
            "writer_enablement_found": True,
            "polling_enablement_found": True,
            "start_progress_updates_found": True,
            "stop_progress_updates_found": True,
            "refresh_progress_found": True,
            "freshness_label_understood": True,
            "advisory_notice_understood": True,
        },
        "operator_notes": "The terminal label was understood as progress only.",
        "problems_observed": [],
        "suggested_improvements": [],
        "sensitive_content_removed": True,
        "evidence_refs": [f"snapshot-{observation_id}"],
    }


def _minimum_set() -> list[dict]:
    return [
        _observation("success-run"),
        _observation("error-run", terminal="error"),
        _observation("polling-run", polling=True),
    ]


def test_valid_observation_is_deterministic_and_not_mutated():
    raw = _observation()
    original = copy.deepcopy(raw)
    assert dogfood.validate_operator_observation(raw)["valid"] is True
    first = dogfood.score_operator_observation(raw)
    second = dogfood.score_operator_observation(raw)
    assert first == second
    assert raw == original
    assert first["uncertainty_reduction"] == 2


def test_synthetic_fixture_never_counts_as_real_evidence():
    report = dogfood.build_live_progress_dogfood_report([_observation(synthetic=True)], created_at="t")
    assert report["real_run_count"] == 0
    assert report["synthetic_test_fixture_count"] == 1
    assert report["aggregate_metrics"]["excluded_observation_count"] == 1
    assert report["decision_recommendation"] == "insufficient_real_evidence"


def test_real_confirmation_and_safe_input_are_required():
    raw = _observation()
    raw["real_run_confirmed"] = False
    assert "real_run_confirmed must be true" in " ".join(dogfood.validate_operator_observation(raw)["errors"])
    raw = _observation()
    raw["raw_prompt"] = "secret user request"
    assert dogfood.validate_operator_observation(raw)["valid"] is False
    raw = _observation()
    raw["operator_notes"] = "C:\\Users\\Admin\\private"
    assert "absolute paths" in " ".join(dogfood.validate_operator_observation(raw)["errors"])


def test_rating_and_uncertainty_boundaries_and_non_applicable_polling():
    raw = _observation()
    raw["stage_clarity_rating"] = 6
    raw["operator_uncertainty_after"] = 5
    assert dogfood.validate_operator_observation(raw)["valid"] is False
    raw = _observation()
    assert raw["polling_usefulness_rating"] is None
    assert dogfood.validate_operator_observation(raw)["valid"] is True


def test_minimum_required_coverage_and_metrics_are_summarized():
    report = dogfood.build_live_progress_dogfood_report(_minimum_set(), created_at="t")
    metrics = report["aggregate_metrics"]
    assert report["evaluation_status"] == "live_progress_operator_dogfood_complete_with_warnings"
    assert report["coverage_summary"]["evidence_status"] == "dogfood_real_evidence_sufficient_with_warnings"
    assert metrics["success_terminal_run_count"] == 2
    assert metrics["error_terminal_run_count"] == 1
    assert metrics["multistage_run_count"] == 3
    assert metrics["manual_refresh_run_count"] == 3
    assert metrics["bounded_polling_run_count"] == 1
    assert metrics["average_polling_usefulness"] == {"value": 4.0, "sample_size": 1}
    assert metrics["average_uncertainty_reduction"] == {"value": 2.0, "sample_size": 3}


def test_missing_or_partial_required_coverage_is_visible():
    assert dogfood.build_live_progress_dogfood_report(_minimum_set()[:2])["coverage_summary"]["evidence_status"] == "dogfood_real_evidence_missing"
    partial = [_observation("one"), _observation("two"), _observation("three")]
    assert dogfood.build_live_progress_dogfood_report(partial)["coverage_summary"]["evidence_status"] == "dogfood_real_evidence_partial"


def test_stage_truthfulness_freshness_and_confusion_findings():
    raw = _observation()
    raw["stages_seen"].append("validation_passed")
    raw["freshness_assessment"]["stale_mistaken_for_failure"] = True
    raw["freshness_assessment"]["terminal_mistaken_for_success"] = True
    raw["progress_validation_confusion"] = True
    result = dogfood.score_operator_observation(raw)
    codes = {item["code"] for item in result["findings"]}
    assert {"unsupported_stage_claim", "stale_mistaken_for_failure", "terminal_mistaken_for_success", "progress_validation_confusion"} <= codes
    assert result["stage_truthfulness"]["terminal_state_is_not_validation"] is True
    assert result["stage_truthfulness"]["terminal_state_is_not_approval"] is True


def test_polling_requires_explicit_start_and_records_safety_blockers():
    raw = _observation(polling=True)
    raw["polling_explicitly_started"] = False
    assert dogfood.validate_operator_observation(raw)["valid"] is False
    raw = _observation(polling=True)
    raw["polling_assessment"]["automatic_start_absent"] = False
    raw["polling_assessment"]["request_overlap_observed"] = True
    report = dogfood.build_live_progress_dogfood_report([raw, _observation("error", terminal="error"), _observation("success")])
    assert report["blockers"]
    assert report["decision_recommendation"] == "larger_ux_rework_needed"


def test_report_is_advisory_only_and_writes_expected_artifacts(tmp_path: Path):
    report = dogfood.build_live_progress_dogfood_report([], created_at="t")
    assert report["phase_id"] == "DOGFOOD.1A"
    assert report["phase_split_status"] == "dogfood_phase_split_complete_with_warnings"
    assert report["framework_status"] == "live_progress_operator_evaluation_framework_ready"
    assert report["artifact_status"] == "live_progress_operator_evaluation_framework_ready_with_warnings"
    assert report["framework_complete"] is True
    assert report["real_evaluation_complete"] is False
    assert report["real_evidence_required"] is True
    assert report["real_run_count"] == 0
    assert report["evaluation_status"] == "insufficient_real_evidence"
    assert {"real_operator_evidence_pending", "zero_confirmed_real_runs", "synthetic_fixtures_do_not_count_as_real_evidence"} <= set(report["warnings"])
    assert report["report_only"] is True
    assert report["runtime_behavior_changed"] is False
    assert report["ui_behavior_changed"] is False
    assert report["runtime_authority"] is False
    assert report["action_triggered"] is False
    assert report["recommended_next_phase"] == "DOGFOOD.1B"
    out = dogfood.write_live_progress_dogfood_report(report, tmp_path)
    saved = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
    assert saved == report
    markdown = Path(out["markdown_path"]).read_text(encoding="utf-8")
    assert "stale is not failure" in markdown
    assert "The evaluation framework is complete, but no real operator evaluation has been completed." in markdown


def test_cli_loads_safe_records_without_running_product(tmp_path: Path):
    inputs = tmp_path / "runs"
    inputs.mkdir()
    (inputs / "safe-run.json").write_text(json.dumps(_observation("safe-cli")), encoding="utf-8")
    output = tmp_path / "out"
    result = cli.run_create_live_progress_operator_dogfood_report(output_root=output, input_root=inputs, created_at="t")
    assert Path(result["json_path"]).name == dogfood.JSON_NAME
    assert result["report"]["real_run_count"] == 1
