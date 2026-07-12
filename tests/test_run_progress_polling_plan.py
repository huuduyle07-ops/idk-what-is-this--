"""Tests for UX.LIVE.9's report-only bounded polling experiment contract."""
from __future__ import annotations

import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_polling_plan import (
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_POLLING_CONFIGURATION,
    INCOMPLETE,
    READY_WITH_WARNINGS,
    REQUIRED_STOP_CONDITIONS,
    REQUIRED_UI_STATUSES,
    build_run_progress_polling_plan,
    render_run_progress_polling_plan_markdown,
    write_run_progress_polling_plan,
)
from scripts.create_run_progress_polling_plan import run_create_run_progress_polling_plan


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_polling_plan.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_run_progress_polling_plan.py"


def _build(**kwargs):
    return build_run_progress_polling_plan(created_at="2026-07-12T00:00:00+00:00", **kwargs)


def test_default_plan_is_report_only_ready_with_warnings_and_has_no_runtime_power():
    plan = _build()

    assert plan["plan_status"] == READY_WITH_WARNINGS
    for key, expected in {
        "report_only": True,
        "polling_implemented": False,
        "polling_enabled_by_default": False,
        "background_requests_enabled": False,
        "automatic_retry_enabled": False,
        "streaming_enabled": False,
        "runtime_behavior_changed": False,
        "snapshot_writer_changed": False,
        "runtime_authority": False,
        "action_triggered": False,
    }.items():
        assert plan[key] is expected
    assert plan["actions_available"] == []
    assert plan["recommended_next_phase"]["phase_id"] == "UX.LIVE.10"
    assert plan["blockers"] == []


def test_configuration_is_default_off_bounded_and_only_affects_read_frequency_and_stop_bounds():
    plan = _build()
    config = plan["configuration_contract"]

    assert set(config["names"].values()) == {
        "RUN_PROGRESS_POLLING_ENABLED",
        "RUN_PROGRESS_POLL_INTERVAL_SECONDS",
        "RUN_PROGRESS_POLL_MAX_DURATION_SECONDS",
        "RUN_PROGRESS_POLL_MAX_REQUESTS",
        "RUN_PROGRESS_POLL_MAX_CONSECUTIVE_ERRORS",
        "RUN_PROGRESS_POLL_HIDDEN_TAB_BEHAVIOR",
    }
    assert config["proposed_defaults"] == DEFAULT_POLLING_CONFIGURATION
    assert config["enabled_by_default"] is False
    assert config["operator_activation_still_required"] is True
    assert config["configuration_never_starts_polling"] is True
    assert "fall back" in config["safe_fallback"]
    assert config["interval_rules"]["minimum_supported_seconds"] == 2
    assert config["interval_rules"]["rapid_one_second_polling_prohibited"] is True
    assert "execution behavior" in config["scope"]


def test_activation_route_and_request_model_require_safe_operator_control_and_a_single_get():
    plan = _build()

    assert plan["explicit_operator_activation_required"] is True
    route = plan["route_contract"]
    assert route["method"] == "GET"
    assert route["path"] == "/ux/run-progress/snapshot/<snapshot_id>"
    assert route["reuse_existing_loader_only"] is True
    assert route["new_backend_route_required"] is False
    activation = plan["operator_activation"]
    assert activation["start_label"] == "Start bounded progress updates"
    assert activation["start_requires_safe_associated_snapshot"] is True
    assert activation["never_enables_snapshot_writer"] is True
    assert activation["never_creates_or_changes_run"] is True
    assert activation["stop_does_not_cancel_underlying_run"] is True
    model = plan["polling_model"]
    assert model["future_sequence"][0] == "operator explicitly starts polling"
    assert "page load -> automatic polling" in model["rejected_implicit_triggers"]
    assert "error -> recursive retry loop" in model["rejected_implicit_triggers"]


def test_budgets_scheduling_hidden_tab_and_all_stop_conditions_are_deterministic():
    plan = _build()

    assert plan["one_request_at_a_time"] is True
    concurrency = plan["request_concurrency"]
    assert concurrency["maximum_concurrent_polling_requests"] == 1
    assert concurrency["no_request_while_previous_in_flight"] is True
    assert concurrency["no_request_queue"] is True
    assert concurrency["next_interval_starts_after_settlement"] is True
    assert concurrency["reuse_ux_live_6_request_guard"] is True
    scheduling = plan["scheduling_model"]
    assert scheduling["kind"] == "chained_one_shot_timeout"
    assert scheduling["fixed_interval_prohibited"] is True
    assert scheduling["implemented_now"] is False
    hidden = plan["hidden_tab_policy"]
    assert hidden["configured_default"] == "pause"
    assert "Remain paused until explicit operator resume" in hidden["on_visible"]
    assert "catch-up request bursts" in hidden["prohibited"]
    assert {item["id"] for item in plan["stop_conditions"]} == set(REQUIRED_STOP_CONDITIONS)
    assert plan["terminal_stop_policy"]["stop_after_render"] is True
    assert plan["association_change_policy"]["stop_old_session"] is True
    assert plan["association_change_policy"]["new_association_starts_automatically"] is False


def test_error_freshness_budget_and_manual_refresh_contracts_remain_advisory():
    plan = _build()

    errors = plan["error_policy"]
    assert errors["immediate_retry"] is False
    assert errors["successful_response_resets_consecutive_errors"] is True
    assert errors["stop_at_configured_consecutive_error_limit"] is True
    assert errors["exponential_backoff_proposed"] is False
    freshness = plan["freshness_relationship"]
    assert freshness["advisory_only"] is True
    assert freshness["stale_increases_frequency"] is False
    assert freshness["possibly_abandoned_triggers_runtime_action"] is False
    assert plan["possibly_abandoned_policy"]["recommended_behavior"] == "Stop polling and ask the operator to decide."
    assert plan["unknown_freshness_policy"]["unknown_alone_stops_polling"] is False
    budget = plan["request_budget"]
    assert budget["duration_and_request_count_both_apply"] is True
    assert budget["first_limit_reached_stops_session"] is True
    assert "localStorage" in budget["not_persisted_in"]
    assert budget["session_token"]["not_runtime_authority"] is True
    manual = plan["manual_refresh_coexistence"]
    assert manual["shared_get_loader"] is True
    assert manual["shared_in_flight_guard"] is True
    assert "stops bounded polling" in manual["policy"]


def test_ui_security_accessibility_resources_and_live_10_boundary_are_complete():
    plan = _build()

    assert {item["status"] for item in plan["ui_statuses"]} == set(REQUIRED_UI_STATUSES)
    notices = {item["status"]: item["notice"] for item in plan["ui_statuses"]}
    assert "No execution action was taken" in notices["stopped_error_limit"]
    assert "No automatic action was taken" in notices["stopped_possibly_abandoned"]
    security = plan["security_boundaries"]
    assert security["server_provided_safe_snapshot_id_only"] is True
    assert security["no_filesystem_path_exposure"] is True
    assert security["no_arbitrary_user_entered_path"] is True
    assert all(plan["accessibility"].values())
    resources = plan["resource_boundaries"]
    assert resources["one_active_polling_session_per_page"] is True
    assert resources["no_unbounded_memory_growth"] is True
    boundary = plan["implementation_boundaries"]
    assert boundary["next_implementation_phase"] == "UX.LIVE.10"
    assert "start polling automatically" in boundary["may_not"]
    assert "add WebSocket/SSE" in boundary["may_not"]
    assert "apply patches" in boundary["may_not"]


def test_status_logic_blocks_unsafe_contracts_and_marks_missing_sections_incomplete():
    blocked = _build(safety_context={"polling_added": True})
    assert blocked["plan_status"] == BLOCKED
    assert "forbidden_behavior_enabled:polling_implemented" in blocked["blockers"]

    overlap = _build(plan_overrides={"one_request_at_a_time": False})
    assert overlap["plan_status"] == BLOCKED
    assert "overlapping_requests_permitted" in overlap["blockers"]

    stale_action = _build(plan_overrides={"freshness_relationship": {"stale_increases_frequency": True}})
    assert stale_action["plan_status"] == BLOCKED
    assert "stale_increases_polling_frequency" in stale_action["blockers"]

    incomplete = _build(plan_overrides={"stop_conditions": []})
    assert incomplete["plan_status"] == INCOMPLETE
    assert "stop_conditions_incomplete" in incomplete["incomplete_reasons"]


def test_artifact_writer_script_and_markdown_are_data_only():
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        root = Path(directory)
        result = write_run_progress_polling_plan(_build(), root / "direct")
        assert result["ok"] is True
        json_path = Path(result["json_path"])
        markdown_path = Path(result["markdown_path"])
        assert json_path.name == "run_progress_polling_plan.json"
        assert markdown_path.name == "run_progress_polling_plan.md"
        assert json.loads(json_path.read_text(encoding="utf-8"))["plan_status"] == READY_WITH_WARNINGS
        markdown = markdown_path.read_text(encoding="utf-8")
        for heading in ("# Bounded Run Progress Polling Experiment Plan", "## Scheduling, Budget, and Stop Conditions", "## UX.LIVE.10 Boundary"):
            assert heading in markdown

        scripted = run_create_run_progress_polling_plan(output_root=root / "script", created_at="t")
        assert scripted["ok"] is True
        assert Path(scripted["json_path"]).is_file()
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_polling_plan"


def test_plan_and_script_do_not_contain_runtime_or_browser_polling_implementation():
    source = CORE_PATH.read_text(encoding="utf-8") + "\n" + SCRIPT_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "import requests", "import httpx", "subprocess", "web.runner", "run_agent_web", "load_run_progress_snapshot",
        "fetch(", "setInterval(", "os.system", "run_benchmarks(", "run_validation(",
    ):
        assert forbidden not in source


def test_registry_completes_live_9_proposes_live_10_and_picker_recommends_live_10():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.9"]["status"] == "complete"
    assert by_id["UX.LIVE.9"]["prerequisites"] == ["UX.LIVE.8"]
    assert by_id["UX.LIVE.10"]["status"] == "proposed"
    assert by_id["UX.LIVE.10"]["prerequisites"] == ["UX.LIVE.9"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-9", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.10"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.10", "MIRROR.13"]
