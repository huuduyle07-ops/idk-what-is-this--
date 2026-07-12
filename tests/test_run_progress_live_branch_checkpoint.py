"""Tests for the UX.LIVE.CLOSE report-only branch checkpoint."""
from __future__ import annotations

import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_live_branch_checkpoint import (
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    FROZEN_WITH_WARNINGS,
    INCOMPLETE,
    OBSERVED_STAGES,
    REQUIRED_PHASE_IDS,
    UNOBSERVED_STAGES,
    build_run_progress_live_branch_checkpoint,
    render_run_progress_live_branch_checkpoint_markdown,
    write_run_progress_live_branch_checkpoint,
)
from scripts.create_run_progress_live_branch_checkpoint import run_create_run_progress_live_branch_checkpoint


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_live_branch_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_run_progress_live_branch_checkpoint.py"


def _build(**kwargs):
    return build_run_progress_live_branch_checkpoint(created_at="2026-07-12T00:00:00+00:00", **kwargs)


def test_checkpoint_freezes_complete_inventory_with_truthful_partial_visibility_only():
    report = _build()

    assert report["checkpoint_status"] == FROZEN_WITH_WARNINGS
    assert report["branch_frozen"] is True
    assert report["report_only"] is True
    assert [item["phase_id"] for item in report["phase_inventory"]] == list(REQUIRED_PHASE_IDS)
    assert all(item["completion_status"] == "complete" for item in report["phase_inventory"])
    assert {item["category"] for item in report["phase_inventory"]} == {"implementation", "plan_only"}
    assert report["truthful_observed_stages"] == list(OBSERVED_STAGES)
    assert set(UNOBSERVED_STAGES) <= set(report["intentionally_unobserved_stages"])
    assert report["truthfulness_statement"] == "The branch provides truthful partial progress visibility, not complete runtime tracing."


def test_configuration_authority_writer_loader_freshness_and_polling_audits_are_advisory_and_complete():
    report = _build()
    configuration = report["configuration_audit"]
    assert configuration["RUN_PROGRESS_SHADOW_WRITER_ENABLED"] is False
    assert configuration["RUN_PROGRESS_POLLING_ENABLED"] is False
    assert all(configuration[key] is True for key in ("missing_flags_disabled", "writer_permission_does_not_enable_polling", "polling_permission_does_not_start_polling", "polling_requires_explicit_operator_activation", "disabled_writer_creates_no_snapshot_root", "no_writer_enable_ui", "no_automatic_polling", "no_page_load_polling", "no_run_start_polling", "no_association_polling", "no_completion_polling"))
    authority = report["authority_audit"]
    assert authority["runtime_authority"] is False
    assert authority["action_triggered"] is False
    assert authority["actions_available"] == []
    assert all(value is False for key, value in authority.items() if key not in {"actions_available"})
    assert all(report["writer_safety_audit"].values())
    assert all(report["loader_safety_audit"].values())
    assert all(report["freshness_audit"].values())
    polling = report["polling_audit"]
    assert all(polling[key] is True for key in ("default_off", "explicit_start_stop", "existing_get_only", "one_request_in_flight", "no_set_interval", "finite_duration", "finite_request_budget", "finite_consecutive_error_budget", "hidden_tab_pause", "no_catch_up_burst", "terminal_stop", "association_change_stop", "stale_callback_rejection", "possibly_abandoned_stop_no_action", "page_local_only", "no_persistent_or_push_transport", "no_local_storage", "no_cookies", "no_database", "no_service_worker", "no_websocket", "no_sse", "no_long_polling"))
    assert all(polling[key] is False for key in ("set_interval", "automatic_polling", "websocket", "sse", "long_polling"))
    assert report["blockers"] == []


def test_status_logic_blocks_unsafe_conditions_and_marks_missing_inventory_incomplete():
    unsafe = _build(checkpoint_overrides={"configuration_audit": {"writer_enabled_by_default": True}})
    assert unsafe["checkpoint_status"] == BLOCKED
    assert "unsafe_default:writer_enabled_by_default" in unsafe["blockers"]
    unsafe_polling = _build(checkpoint_overrides={"polling_audit": {"one_request_in_flight": False}})
    assert unsafe_polling["checkpoint_status"] == BLOCKED
    assert "polling_safety_missing:one_request_in_flight" in unsafe_polling["blockers"]
    incomplete = _build(checkpoint_overrides={"phase_inventory": []})
    assert incomplete["checkpoint_status"] == INCOMPLETE
    assert "phase_inventory_incomplete" in incomplete["incomplete_reasons"]

    inventory = _build()["phase_inventory"]
    inventory[0]["evidence_references"] = []
    incomplete_evidence = _build(checkpoint_overrides={"phase_inventory": inventory})
    assert incomplete_evidence["checkpoint_status"] == INCOMPLETE
    assert "phase_inventory_evidence_incomplete:UX.LIVE.1" in incomplete_evidence["incomplete_reasons"]


def test_warnings_limitations_artifacts_and_script_are_data_only(tmp_path):
    report = _build()
    assert "operator_dogfood_pending" in report["warnings"]
    assert len(report["known_limitations"]) >= 9
    assert report["recommended_next_phase"]["phase_id"] == "DOGFOOD.1"
    assert all((PROJECT_ROOT / item["evidence_references"][1]).is_file() for item in report["phase_inventory"])
    direct = write_run_progress_live_branch_checkpoint(report, tmp_path / "direct")
    assert direct["ok"] is True
    assert json.loads(Path(direct["json_path"]).read_text(encoding="utf-8"))["checkpoint_status"] == FROZEN_WITH_WARNINGS
    markdown = Path(direct["markdown_path"]).read_text(encoding="utf-8")
    for heading in ("# Live Run Progress Branch Checkpoint", "## Truthfulness Boundary", "## Phase Inventory", "## Next Phase"):
        assert heading in markdown
    assert render_run_progress_live_branch_checkpoint_markdown(report) == markdown
    scripted = run_create_run_progress_live_branch_checkpoint(output_root=tmp_path / "script", created_at="t")
    assert scripted["ok"] is True
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_live_branch_checkpoint"


def test_checkpoint_and_script_do_not_contain_runtime_or_polling_implementation_tokens():
    source = CORE_PATH.read_text(encoding="utf-8") + "\n" + SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "subprocess", "web.runner", "fetch(", "setInterval(", "run_benchmarks(", "run_validation("):
        assert forbidden not in source


def test_registry_completes_close_proposes_dogfood_and_picker_recommends_it():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert by_id["UX.LIVE.CLOSE"]["status"] == "complete"
    assert by_id["DOGFOOD.1"]["status"] == "proposed"
    assert by_id["DOGFOOD.1"]["prerequisites"] == ["UX.LIVE.CLOSE"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-close", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["DOGFOOD.1", "MIRROR.13"]
