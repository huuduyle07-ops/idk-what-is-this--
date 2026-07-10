"""Tests for UX.LIVE.2 - Run Progress Snapshot Writer Plan."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_snapshot_writer_plan import (
    ALLOWED_FUTURE_WRITE_ROOT,
    BLOCKED,
    DEFAULT_OUTPUT_ROOT,
    INCOMPLETE,
    JSON_NAME,
    MD_NAME,
    READY_WITH_WARNINGS,
    REPORT_KIND,
    REQUIRED_SNAPSHOT_FIELDS,
    SAFE_SLUG_RE,
    THIS_PHASE_ID,
    build_run_progress_snapshot_writer_plan,
    render_run_progress_snapshot_writer_plan_markdown,
    write_run_progress_snapshot_writer_plan,
)
from scripts.create_run_progress_snapshot_writer_plan import (
    run_create_run_progress_snapshot_writer_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "run_progress_snapshot_writer_plan.py"
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
        "allowed_files": ["tests/test_run_progress_snapshot_writer_plan.py"],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "validation": ["python -m pytest tests/test_run_progress_snapshot_writer_plan.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [],
    }


def _registry() -> dict:
    ids = ["UX.RUN.1", "UX.RUN.2", "UX.RUN.CLOSE", "UX.LIVE.1", "UX.LIVE.2", "UX.LIVE.3", "MIRROR.13"]
    return {
        "schema_version": "1.0",
        "phases": [_phase(phase_id, "proposed" if phase_id in {"UX.LIVE.3", "MIRROR.13"} else "complete") for phase_id in ids],
    }


def _instrumentation() -> dict:
    return {
        "report_kind": "run_progress_instrumentation_plan",
        "status": "run_progress_instrumentation_plan_ready_with_warnings",
        "attachment_points": [
            {
                "stage_id": "final_response_ready",
                "proposed_source_file": "web/runner.py",
                "proposed_function_or_boundary": "existing final result assembly boundary",
            }
        ],
    }


def _visibility() -> dict:
    return {
        "report_kind": "run_progress_visibility",
        "status": "run_progress_visibility_ready_with_warnings",
        "stage_contract": [{"stage_id": "request_received"}],
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
        "instrumentation_plan": _instrumentation(),
        "visibility_report": _visibility(),
        "snapshot_loader_report": _loader(),
        "branch_checkpoint": _checkpoint(),
        "created_at": "2026-07-10T00:00:00+09:00",
    }
    defaults.update(kwargs)
    return build_run_progress_snapshot_writer_plan(**defaults)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_fake_repo(root: Path) -> None:
    _write_json(root / "docs/roadmap/phase_registry.json", _registry())
    _write_json(root / ".agent/ux/run_progress_instrumentation_plan/run_progress_instrumentation_plan.json", _instrumentation())
    _write_json(root / ".agent/ux/run_progress_visibility/run_progress_visibility_report.json", _visibility())
    _write_json(root / ".agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.json", _loader())
    _write_json(
        root / ".agent/ux/run_progress_visibility_branch_checkpoint/run_progress_visibility_branch_checkpoint.json",
        _checkpoint(),
    )


def test_complete_plan_is_ready_with_warnings_and_writes_no_live_snapshots():
    report = _build()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == THIS_PHASE_ID == "UX.LIVE.2"
    assert report["status"] == READY_WITH_WARNINGS
    assert report["recommended_next_phase"]["phase_id"] == "UX.LIVE.3"
    assert report["writer_purpose"]["implemented_now"] is False
    assert report["final_verdict"]["runtime_hooks_inserted"] is False
    assert report["final_verdict"]["live_snapshots_written"] is False


def test_default_off_configuration_and_allowed_write_root_are_explicit():
    report = _build()
    config = report["default_off_configuration"]
    root = report["allowed_write_root"]

    assert config["environment_variable"] == "RUN_PROGRESS_SHADOW_WRITER_ENABLED"
    assert config["default_value"] is False
    assert config["missing_config_behaves_as_disabled"] is True
    assert config["no_implicit_enablement"] is True
    assert config["disabled_state_writes_nothing"] is True
    assert root["root"] == ALLOWED_FUTURE_WRITE_ROOT.as_posix()
    assert root["per_run_directory_template"] == ".agent/ux/run_progress_snapshots/<run_id>/"
    assert root["writes_outside_root_allowed"] is False


def test_schema_is_safe_non_authoritative_and_keeps_polling_streaming_off():
    report = _build()
    schema = report["snapshot_schema"]
    defaults = schema["planned_defaults"]
    authority = report["runtime_authority_boundary"]

    assert set(REQUIRED_SNAPSHOT_FIELDS) <= set(schema["required_fields"])
    assert defaults["runtime_authority"] is False
    assert defaults["action_triggered"] is False
    assert defaults["actions_available"] == []
    assert defaults["live_stream_enabled"] is False
    assert defaults["polling_enabled"] is False
    assert defaults["runtime_behavior_changed"] is False
    assert authority["progress_updates_may_trigger_actions"] is False
    assert authority["progress_updates_may_block_actions"] is False
    assert authority["progress_updates_may_enforce_approvals"] is False


def test_atomicity_path_safety_failure_concurrency_and_retention_are_defined():
    report = _build()

    assert report["atomic_write_strategy"]["temporary_file_location"] == "same_per_run_directory_as_canonical_target"
    assert report["atomic_write_strategy"]["windows_safe_temporary_filenames"] is True
    assert report["atomic_write_strategy"]["canonical_json_never_partially_written"] is True
    assert report["atomic_write_strategy"]["temporary_file_cleanup_on_failure"] is True
    assert report["path_safety"]["run_id_must_be_safe_slug"] is True
    assert report["path_safety"]["snapshot_id_must_be_safe_slug"] is True
    assert SAFE_SLUG_RE.fullmatch("run_20260710")
    assert SAFE_SLUG_RE.fullmatch("../unsafe") is None
    assert report["failure_isolation"]["writer_failure_fails_main_run"] is False
    assert report["failure_isolation"]["database_fallback"] is False
    assert report["failure_isolation"]["network_fallback"] is False
    assert report["concurrency_strategy"]["sequence_based_last_update_logic"] is True
    assert report["concurrency_strategy"]["stale_sequence_updates_rejected_or_ignored"] is True
    assert report["retention_boundary"]["deletion_performed_now"] is False
    assert report["retention_boundary"]["automatic_janitor_enabled"] is False


def test_sensitive_data_is_forbidden_and_stage_semantics_do_not_claim_success():
    report = _build()
    redaction = report["sensitive_data_redaction"]
    update_policy = report["stage_update_policy"]

    assert redaction["sensitive_data_forbidden"] is True
    assert "raw prompts" in redaction["forbidden_payload_categories"]
    assert update_policy["progress_stage_is_not_success"] is True
    assert update_policy["validation_finished_is_validation_passed"] is False
    assert update_policy["benchmark_finished_is_benchmark_passed"] is False
    assert update_policy["final_response_ready_implies_patch_approval"] is False


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"configuration_overrides": {"default_value": True}}, "writer_enabled_by_default"),
        ({"redaction_policy_overrides": {"sensitive_data_forbidden": False}}, "sensitive_data_permitted"),
        ({"failure_isolation_overrides": {"writer_failure_fails_main_run": True}}, "writer_failure_fails_main_run"),
        ({"allowed_write_root_overrides": {"root": ".agent/other"}}, "writes_outside_allowed_root"),
    ],
)
def test_unsafe_writer_plan_boundaries_block(kwargs: dict, reason: str):
    report = _build(**kwargs)
    assert report["status"] == BLOCKED
    assert any(item["reason"] == reason for item in report["blocked_reasons"])


def test_missing_schema_boundary_is_incomplete():
    report = _build(snapshot_schema_overrides={"required_fields": []})
    assert report["status"] == INCOMPLETE
    assert report["incomplete_reasons"]


def test_writes_json_and_markdown_plan_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    result = write_run_progress_snapshot_writer_plan(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        plan_id="writer-plan-test",
        created_at="2026-07-10T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["plan_id"] == "writer-plan-test"
    assert data["status"] == READY_WITH_WARNINGS
    for section in (
        "Summary", "Source Artifacts", "Writer Philosophy", "Default-Off Configuration",
        "Allowed Write Root", "Snapshot Schema", "Stage Update Policy", "Atomic Write Strategy",
        "Path Safety", "Sensitive Data Redaction", "Failure Isolation", "Concurrency Strategy",
        "Retention Boundary", "Runtime Authority Boundary", "Future Attachment Points", "Warnings",
        "Blocked Reasons", "Final Verdict", "Recommended Next Phase", "Guardrails",
    ):
        assert f"## {section}" in markdown


def test_script_writes_only_plan_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    result = run_create_run_progress_snapshot_writer_plan(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        plan_id="script-test",
        created_at="2026-07-10T00:00:00+09:00",
    )
    assert result["summary"]["status"] == READY_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "UX.LIVE.3"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()
    assert not (tmp_path / ".agent/ux/run_progress_snapshots").exists()


def test_renderer_is_pure_and_default_output_root_matches_spec():
    report = _build()
    before = json.loads(json.dumps(report, sort_keys=True))
    assert "# Run Progress Snapshot Writer Plan" in render_run_progress_snapshot_writer_plan_markdown(report)
    assert report == before
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_snapshot_writer_plan"


def test_real_registry_completes_live_2_adds_live_3_and_recommends_it():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert by_id["UX.LIVE.2"]["status"] == "complete"
    assert by_id["UX.LIVE.3"]["status"] == "proposed"
    assert by_id["UX.LIVE.3"]["prerequisites"] == ["UX.LIVE.2"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-2", created_at="t")
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.3"


def test_plan_source_has_no_runtime_execution_or_network_path():
    source = CORE_PATH.read_text(encoding="utf-8")
    for forbidden in ("import requests", "import subprocess", "os.system(", "run_benchmarks(", "run_validation("):
        assert forbidden not in source
