"""Tests for UX.LIVE.1 - Run Progress Instrumentation Plan."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_instrumentation_plan import (
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    EVENT_PAYLOAD_FIELDS,
    INCOMPLETE,
    JSON_NAME,
    MD_NAME,
    READY_WITH_WARNINGS,
    REPORT_KIND,
    REQUIRED_ATTACHMENT_POINT_FIELDS,
    REQUIRED_STAGE_IDS,
    STORAGE_OPTION_IDS,
    THIS_PHASE_ID,
    build_run_progress_instrumentation_plan,
    render_run_progress_instrumentation_plan_markdown,
    write_run_progress_instrumentation_plan,
)
from scripts.create_run_progress_instrumentation_plan import (
    run_create_run_progress_instrumentation_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_instrumentation_plan.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _phase(phase_id: str, status: str = "complete") -> dict:
    return {
        "phase_id": phase_id,
        "title": phase_id,
        "track": "UX",
        "status": status,
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["tests/test_run_progress_instrumentation_plan.py"],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "validation": ["python -m pytest tests/test_run_progress_instrumentation_plan.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [],
    }


def _registry(missing: str = "") -> dict:
    ids = ["UX.RUN.1", "UX.RUN.2", "UX.RUN.3", "UX.RUN.CLOSE", "UX.LIVE.1", "UX.LIVE.2", "MIRROR.13"]
    return {
        "schema_version": "1.0",
        "phases": [
            _phase(phase_id, "proposed" if phase_id in {"UX.LIVE.2", "MIRROR.13"} else "complete")
            for phase_id in ids
            if phase_id != missing
        ],
    }


def _visibility() -> dict:
    return {
        "report_kind": "run_progress_visibility",
        "status": "run_progress_visibility_ready_with_warnings",
        "stage_contract": [{"stage_id": "request_received"}],
        "warnings": ["No live progress stream is implemented yet."],
    }


def _loader() -> dict:
    return {
        "report_kind": "run_progress_snapshot_loader",
        "status": "run_progress_snapshot_loaded_with_warnings",
        "blocked_reasons": [],
    }


def _checkpoint() -> dict:
    return {
        "report_kind": "run_progress_visibility_branch_checkpoint",
        "checkpoint_status": "run_progress_visibility_branch_frozen_with_warnings",
    }


def _build(**kwargs) -> dict:
    defaults = {
        "registry_data": _registry(),
        "visibility_report": _visibility(),
        "snapshot_loader_report": _loader(),
        "branch_checkpoint": _checkpoint(),
        "runner_source": "def run_agent_web():\n    run_draft_pipeline(state)\n    run_review_pipeline(state, draft)\n    return {\"answer\": state.final_answer}\n",
        "app_source": "def route():\n    return run_agent_web()\n",
        "created_at": "2026-07-10T00:00:00+09:00",
    }
    defaults.update(kwargs)
    return build_run_progress_instrumentation_plan(**defaults)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_fake_repo(root: Path) -> None:
    _write_json(root / "docs/roadmap/phase_registry.json", _registry())
    _write_json(root / ".agent/ux/run_progress_visibility/run_progress_visibility_report.json", _visibility())
    _write_json(root / ".agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.json", _loader())
    _write_json(
        root / ".agent/ux/run_progress_visibility_branch_checkpoint/run_progress_visibility_branch_checkpoint.json",
        _checkpoint(),
    )
    runner = root / "web/runner.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text("def run_agent_web():\n    run_draft_pipeline(state)\n    run_review_pipeline(state, draft)\n    return {\"answer\": state.final_answer}\n", encoding="utf-8")
    (root / "web/app.py").write_text("def route():\n    return run_agent_web()\n", encoding="utf-8")


def test_complete_plan_is_ready_with_warnings_and_has_all_required_stages():
    report = _build()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == THIS_PHASE_ID == "UX.LIVE.1"
    assert report["status"] == READY_WITH_WARNINGS
    assert report["recommended_next_phase"]["phase_id"] == "UX.LIVE.2"
    assert [point["stage_id"] for point in report["attachment_points"]] == list(REQUIRED_STAGE_IDS)
    assert report["final_verdict"]["live_instrumentation_implemented"] is False
    assert report["final_verdict"]["safe_to_plan"] is True


def test_every_attachment_point_has_schema_and_remains_non_authoritative():
    report = _build()

    for point in report["attachment_points"]:
        assert set(REQUIRED_ATTACHMENT_POINT_FIELDS) <= set(point)
        assert point["event_payload_fields"] == list(EVENT_PAYLOAD_FIELDS)
        assert point["enforcement_allowed_now"] is False
        assert point["emits_runtime_authority"] is False
        assert point["may_trigger_action"] is False
        assert point["may_block_action"] is False
        assert "future_only" in point["live_stream_candidate"]
        assert "future_only" in point["polling_candidate"]


def test_payload_contract_preserves_distinct_non_authoritative_semantics():
    contract = _build()["event_payload_contract"]

    assert contract["fields"] == list(EVENT_PAYLOAD_FIELDS)
    assert contract["planned_defaults"]["action_triggered"] is False
    assert contract["planned_defaults"]["runtime_authority"] is False
    for key in (
        "progress_implies_success",
        "validation_started_is_validation_passed",
        "validation_finished_is_validation_passed",
        "benchmark_started_is_benchmark_passed",
        "benchmark_finished_is_benchmark_passed",
        "model_call_pending_triggers_model_call",
        "validation_started_triggers_validation",
        "benchmark_started_triggers_benchmark",
        "approval_boundary_checked_enforces_approval",
    ):
        assert contract["semantics"][key] is False
    assert contract["semantics"]["error_reported_remains_visible"] is True


def test_storage_options_are_complete_and_future_only():
    options = _build()["storage_options"]

    assert [option["option_id"] for option in options] == list(STORAGE_OPTION_IDS)
    assert all(option["allowed_now"] is False for option in options)
    assert all(option["future_only"] is True for option in options)


@pytest.mark.parametrize(
    "flag",
    [
        "live_hooks_allowed_now",
        "polling_allowed_now",
        "streaming_allowed_now",
        "runtime_mutation_allowed_now",
        "action_triggering_events_allowed_now",
        "approval_enforcement_allowed_now",
        "model_call_allowed_now",
        "worker_launch_allowed_now",
        "patch_apply_allowed_now",
        "validation_execution_allowed_now",
        "benchmark_execution_allowed_now",
        "progress_as_authority_allowed_now",
    ],
)
def test_forbidden_live_or_runtime_planning_flags_block(flag: str):
    report = _build(safety_context={flag: True})
    assert report["status"] == BLOCKED
    assert report["blocked_reasons"]


def test_action_or_enforcement_attachment_override_blocks():
    for field in ("enforcement_allowed_now", "emits_runtime_authority", "may_trigger_action", "may_block_action"):
        report = _build(attachment_overrides={"request_received": {field: True}})
        assert report["status"] == BLOCKED


@pytest.mark.parametrize(
    "override",
    [
        {"planned_defaults": {"action_triggered": True}},
        {"semantics": {"model_call_pending_triggers_model_call": True}},
        {"semantics": {"validation_started_triggers_validation": True}},
        {"semantics": {"benchmark_started_triggers_benchmark": True}},
        {"semantics": {"approval_boundary_checked_enforces_approval": True}},
        {"semantics": {"progress_implies_success": True}},
        {"semantics": {"error_reported_remains_visible": False}},
    ],
)
def test_invalid_payload_semantics_block(override: dict):
    assert _build(payload_contract_overrides=override)["status"] == BLOCKED


def test_missing_required_stage_or_source_is_incomplete():
    points = _build()["attachment_points"]
    assert _build(attachment_points=points[1:])["status"] == INCOMPLETE
    assert _build(registry_data=_registry(missing="UX.RUN.CLOSE"))["status"] == INCOMPLETE
    assert _build(visibility_report=None, visibility_report_load_error="missing")["status"] == INCOMPLETE


def test_write_and_markdown_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    result = write_run_progress_instrumentation_plan(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        plan_id="plan-test",
        created_at="2026-07-10T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["plan_id"] == "plan-test"
    assert data["status"] == READY_WITH_WARNINGS
    for section in (
        "Summary", "Source Artifacts", "Instrumentation Philosophy", "Proposed Stage Attachment Points",
        "Event Payload Contract", "Storage Options", "Live Streaming / Polling Boundary",
        "Runtime Authority Boundary", "Risks and Mitigations", "Future Implementation Path", "Warnings",
        "Blocked Reasons", "Final Verdict", "Recommended Next Phase", "Guardrails",
    ):
        assert f"## {section}" in markdown


def test_script_writes_plan_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    result = run_create_run_progress_instrumentation_plan(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        plan_id="script-test",
        created_at="2026-07-10T00:00:00+09:00",
    )
    assert result["summary"]["status"] == READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "UX.LIVE.2"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_renderer_is_pure_and_defaults_match_spec():
    report = _build()
    before = json.loads(json.dumps(report, sort_keys=True))
    assert "# Run Progress Instrumentation Plan" in render_run_progress_instrumentation_plan_markdown(report)
    assert report == before
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_instrumentation_plan"


def test_real_registry_marks_live_1_through_live_3_complete_and_recommends_live_4():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert by_id["UX.LIVE.1"]["status"] == "complete"
    assert by_id["UX.LIVE.1"]["prerequisites"] == ["UX.RUN.CLOSE"]
    assert by_id["UX.LIVE.2"]["status"] == "complete"
    assert by_id["UX.LIVE.2"]["prerequisites"] == ["UX.LIVE.1"]
    assert by_id["UX.LIVE.3"]["status"] == "complete"
    assert by_id["UX.LIVE.3"]["prerequisites"] == ["UX.LIVE.2"]
    assert by_id["UX.LIVE.4"]["status"] == "complete"
    assert by_id["UX.LIVE.4"]["prerequisites"] == ["UX.LIVE.3"]
    assert by_id["UX.LIVE.5"]["status"] == "complete"
    assert by_id["UX.LIVE.5"]["prerequisites"] == ["UX.LIVE.4"]
    assert by_id["UX.LIVE.6"]["status"] == "proposed"
    assert by_id["UX.LIVE.6"]["prerequisites"] == ["UX.LIVE.5"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-1", created_at="t")
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.6"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.6", "MIRROR.13"]


def test_plan_source_has_no_runtime_execution_or_network_path():
    source = CORE_PATH.read_text(encoding="utf-8")
    for forbidden in ("import requests", "import subprocess", "os.system(", "run_benchmarks(", "run_validation("):
        assert forbidden not in source
