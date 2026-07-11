"""Tests for UX.LIVE.7's report-only freshness and staleness contract."""
from __future__ import annotations

import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_freshness_plan import (
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_THRESHOLDS,
    INCOMPLETE,
    READY_WITH_WARNINGS,
    REQUIRED_CLASSIFICATION_INPUTS,
    REQUIRED_FRESHNESS_STATUSES,
    REQUIRED_RESULT_FIELDS,
    REQUIRED_WARNING_CODES,
    build_run_progress_freshness_plan,
    render_run_progress_freshness_plan_markdown,
    write_run_progress_freshness_plan,
)
from scripts.create_run_progress_freshness_plan import run_create_run_progress_freshness_plan


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_freshness_plan.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_run_progress_freshness_plan.py"


def _build(**kwargs):
    return build_run_progress_freshness_plan(created_at="2026-07-11T00:00:00+00:00", **kwargs)


def test_default_plan_is_report_only_ready_with_warnings_and_has_no_runtime_power():
    plan = _build()

    assert plan["plan_status"] == READY_WITH_WARNINGS
    for key, expected in {
        "report_only": True,
        "runtime_behavior_changed": False,
        "ui_behavior_changed": False,
        "polling_enabled": False,
        "streaming_enabled": False,
        "automatic_retry_enabled": False,
        "cleanup_enabled": False,
        "runtime_authority": False,
        "action_triggered": False,
    }.items():
        assert plan[key] is expected
    assert plan["blockers"] == []
    assert plan["recommended_next_phase"]["phase_id"] == "UX.LIVE.8"


def test_contract_uses_only_approved_metadata_and_documents_excluded_sensitive_or_runtime_inputs():
    plan = _build()
    inputs = plan["classification_inputs"]

    assert tuple(inputs["approved_snapshot_metadata_only"]) == REQUIRED_CLASSIFICATION_INPUTS
    excluded = " ".join(inputs["excluded_inputs"]).lower()
    for forbidden in ("prompt", "response", "repository path", "process inspection", "database", "network probe"):
        assert forbidden in excluded
    boundaries = plan["implementation_boundaries"]
    assert boundaries["process_inspection_required"] is False
    assert boundaries["network_probe_required"] is False
    assert boundaries["database_state_required"] is False
    assert boundaries["raw_content_required"] is False


def test_status_taxonomy_precedence_and_notices_are_deterministic_and_advisory():
    plan = _build()
    statuses = {item["status"]: item for item in plan["freshness_statuses"]}

    assert set(REQUIRED_FRESHNESS_STATUSES) <= set(statuses)
    assert "not a failure declaration" in statuses["stale"]["meaning"]
    assert "must not cancel, restart, retry, clean up" in statuses["possibly_abandoned"]["meaning"]
    assert "cannot calculate a trustworthy age" in statuses["unknown"]["meaning"]
    assert "confirms that the run is healthy" not in statuses["fresh"]["notice"].lower()

    precedence = [item["rule"] for item in plan["status_precedence"]]
    assert "invalid or unsafe snapshot -> invalid" in precedence[0]
    assert "explicit terminal=true -> terminal before age classification" in precedence[2]
    assert precedence[-1].endswith("possibly_abandoned")
    terminal = plan["terminal_precedence"]
    assert terminal["old_terminal_remains_terminal"] is True
    assert terminal["terminal_age_overrides_terminal"] is False
    assert "not validation proof" in terminal["terminal_outcome"]["success"]


def test_time_timestamp_clock_skew_and_negative_age_contracts_are_present():
    plan = _build()

    time_model = plan["time_model"]
    assert "Timezone-aware UTC" in time_model["observed_at"]
    assert "null or max(0" in time_model["age_seconds"]
    assert "never assume local time" in time_model["naive_timestamp_policy"]
    skew = plan["clock_skew_policy"]
    assert skew["negative_age_forbidden"] is True
    assert "unknown" in skew["beyond_tolerance"]
    assert "Do not silently clamp" in skew["large_future_timestamp"]
    malformed = plan["malformed_timestamp_policy"]
    for case in ("missing_updated_at", "missing_created_at", "malformed_or_unsupported", "naive_timestamp", "updated_before_created", "future_created_or_updated"):
        assert case in malformed
        assert "unknown" in malformed[case]


def test_threshold_contract_is_ordered_and_malformed_values_fall_back_safely():
    plan = _build()
    thresholds = plan["default_thresholds"]

    assert thresholds == DEFAULT_THRESHOLDS
    assert thresholds["fresh_seconds"] < thresholds["recent_seconds"] < thresholds["abandoned_seconds"]
    config = plan["configuration_contract"]
    assert set(config["names"].values()) == {
        "RUN_PROGRESS_FRESH_SECONDS",
        "RUN_PROGRESS_RECENT_SECONDS",
        "RUN_PROGRESS_ABANDONED_SECONDS",
        "RUN_PROGRESS_CLOCK_SKEW_TOLERANCE_SECONDS",
    }
    assert "fall back" in config["fallback"]
    assert "cannot enable polling" in config["boundary"]

    fallback = _build(threshold_overrides={"fresh_seconds": 30, "recent_seconds": 10, "abandoned_seconds": 5})
    assert fallback["default_thresholds"] == DEFAULT_THRESHOLDS
    assert "threshold_configuration_invalid" in fallback["warnings"]


def test_sequence_and_warning_catalog_are_supporting_only_and_complete():
    plan = _build()
    sequence = plan["sequence_policy"]

    assert sequence["does_not_determine_freshness"] is True
    assert sequence["high_sequence_not_fresh"] is True
    assert sequence["sequence_one_may_be_fresh"] is True
    assert sequence["timestamps_required_for_age"] is True
    assert "does not trigger execution decisions" in sequence["decreasing_sequence"]
    assert {item["code"] for item in plan["warning_codes"]} == set(REQUIRED_WARNING_CODES)


def test_future_classifier_schema_and_live_8_boundary_prohibit_actions_and_mutation():
    plan = _build()
    output = plan["proposed_classifier_output"]

    assert set(REQUIRED_RESULT_FIELDS) <= set(output["fields"])
    invariants = " ".join(output["invariants"])
    assert "null or non-negative" in invariants
    assert "Terminal state takes precedence" in invariants
    assert "runtime_authority is always false" in invariants
    assert "action_triggered is always false" in invariants
    boundaries = plan["implementation_boundaries"]
    assert boundaries["next_implementation_phase"] == "UX.LIVE.8"
    prohibited = " ".join(boundaries["prohibited_future_behavior"])
    for forbidden in ("polling", "background requests", "canonical snapshot mutation"):
        assert forbidden in prohibited
    relationship = plan["future_polling_relationship"]
    assert relationship["implemented_now"] is False
    assert relationship["freshness_requires_polling"] is False
    assert relationship["stale_starts_polling"] is False
    assert relationship["possibly_abandoned_triggers_retry_or_cancellation"] is False


def test_status_logic_blocks_runtime_power_and_reports_missing_contract_sections():
    blocked = _build(safety_context={"polling_added": True})
    assert blocked["plan_status"] == BLOCKED
    assert "forbidden_behavior_enabled:polling_enabled" in blocked["blockers"]

    action_blocked = _build(plan_overrides={"future_polling_relationship": {"stale_starts_polling": True}})
    assert action_blocked["plan_status"] == BLOCKED
    assert "stale_starts_polling" in action_blocked["blockers"]

    incomplete = _build(plan_overrides={"freshness_statuses": []})
    assert incomplete["plan_status"] == INCOMPLETE
    assert "freshness_status_taxonomy_missing" in incomplete["incomplete_reasons"]


def test_artifact_writer_and_script_write_json_and_markdown_only(tmp_path):
    result = write_run_progress_freshness_plan(_build(), tmp_path / "direct")

    assert result["ok"] is True
    json_path = Path(result["json_path"])
    md_path = Path(result["markdown_path"])
    assert json_path.name == "run_progress_freshness_plan.json"
    assert md_path.name == "run_progress_freshness_plan.md"
    assert json.loads(json_path.read_text(encoding="utf-8"))["plan_status"] == READY_WITH_WARNINGS
    markdown = md_path.read_text(encoding="utf-8")
    for heading in ("# Run Progress Snapshot Freshness and Staleness Plan", "## Freshness Statuses", "## UX.LIVE.8 Boundary"):
        assert heading in markdown

    scripted = run_create_run_progress_freshness_plan(output_root=tmp_path / "script", created_at="t")
    assert scripted["ok"] is True
    assert Path(scripted["json_path"]).is_file()
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_freshness_plan"


def test_plan_and_script_source_have_no_runtime_ui_or_network_implementation():
    source = CORE_PATH.read_text(encoding="utf-8") + "\n" + SCRIPT_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import requests",
        "import httpx",
        "subprocess",
        "web.runner",
        "run_agent_web",
        "load_run_progress_snapshot",
        "fetch(",
        "setInterval",
        "WebSocket",
        "EventSource",
        "os.system",
        "run_benchmarks(",
        "run_validation(",
    ):
        assert forbidden not in source


def test_registry_completes_live_7_and_recommends_live_8():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.7"]["status"] == "complete"
    assert by_id["UX.LIVE.7"]["prerequisites"] == ["UX.LIVE.6"]
    assert by_id["UX.LIVE.8"]["status"] == "proposed"
    assert by_id["UX.LIVE.8"]["prerequisites"] == ["UX.LIVE.7"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-7", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.8"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.8", "MIRROR.13"]
