"""Tests for UX.RUN.CLOSE - Run Progress Visibility Branch Checkpoint."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_visibility_branch_checkpoint import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    THIS_PHASE_ID,
    build_run_progress_visibility_branch_checkpoint,
    render_run_progress_visibility_branch_checkpoint_markdown,
    write_run_progress_visibility_branch_checkpoint,
)
from scripts.create_run_progress_visibility_branch_checkpoint import (
    run_create_run_progress_visibility_branch_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
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
        "allowed_files": ["tests/test_run_progress_visibility_branch_checkpoint.py"],
        "forbidden_files": [".env", ".git", ".agent/private"],
        "validation": ["python -m pytest tests/test_run_progress_visibility_branch_checkpoint.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [],
    }


def _registry(missing: str = "", status_overrides: dict[str, str] | None = None) -> dict:
    status_overrides = status_overrides or {}
    ids = ["UX.RUN.1", "UX.RUN.2", "UX.RUN.3", "UX.RUN.CLOSE", "UX.LIVE.1", "MIRROR.13"]
    phases = [
        _phase(
            phase_id,
            status_overrides.get(
                phase_id,
                "proposed" if phase_id in {"UX.LIVE.1", "MIRROR.13"} else "complete",
            ),
        )
        for phase_id in ids
        if phase_id != missing
    ]
    return {"schema_version": "1.0", "phases": phases}


def _contract(**overrides) -> dict:
    base = {
        "report_kind": "run_progress_visibility",
        "status": "run_progress_visibility_ready_with_warnings",
        "stage_contract": [
            {"stage_id": "validation_not_run"},
            {"stage_id": "validation_reported"},
            {"stage_id": "benchmark_not_run"},
            {"stage_id": "benchmark_reported"},
        ],
        "progress_semantics": {
            "progress_is_descriptive_only": True,
            "progress_implies_success": False,
        },
        "error_visibility": {"errors_must_be_visible": True},
        "live_stream": {"implemented": False},
        "guardrails": {
            "polling_route_added": False,
            "runtime_execution_changed": False,
            "action_triggering_controls_added": False,
            "patch_apply_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
            "worker_launch_performed": False,
            "model_call_performed": False,
            "model_routing_changed": False,
            "approval_enforcement_changed": False,
            "progress_treated_as_success": False,
        },
        "warnings": ["No live progress stream is implemented yet."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
    }
    base.update(overrides)
    return base


def _loader(**overrides) -> dict:
    base = {
        "report_kind": "run_progress_snapshot_loader",
        "status": "run_progress_snapshot_loaded_with_warnings",
        "read_only_boundaries": ["Loads existing JSON only.", "Does not poll active runs."],
        "warnings": ["No live progress stream yet; UX.RUN.2 only loads existing snapshot artifacts."],
        "blocked_reasons": [],
        "incomplete_reasons": [],
        "loader_result": {
            "loader_status": "run_progress_snapshot_loaded_with_warnings",
            "snapshot": {
                "snapshot_id": "default",
                "snapshot_status": "run_progress_snapshot_from_visibility_report",
                "live_stream_enabled": False,
                "polling_enabled": False,
                "runtime_behavior_changed": False,
                "actions_available": [],
            },
        },
    }
    base.update(overrides)
    return base


def _ui_marker(extra_js: str = "") -> str:
    return """
<!-- UX.RUN.3 run-progress-panel -->
<section id="runProgressPanel" data-run-progress-readonly="true">
  Not run / unavailable is not a passed result.
</section>
<!-- /UX.RUN.3 run-progress-panel -->
// UX.RUN.3 run-progress-panel
async function loadRunProgressSnapshot() {
  return fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" });
}
""" + extra_js + """
// /UX.RUN.3 run-progress-panel
"""


def _build(**kwargs) -> dict:
    defaults = {
        "registry_data": _registry(),
        "source_visibility_contract": _contract(),
        "source_snapshot_loader_report": _loader(),
        "source_ui_panel_marker": _ui_marker(),
        "created_at": "2026-07-10T00:00:00+09:00",
    }
    defaults.update(kwargs)
    return build_run_progress_visibility_branch_checkpoint(**defaults)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_fake_repo(root: Path) -> None:
    _write_json(root / "docs/roadmap/phase_registry.json", _registry())
    _write_json(root / ".agent/ux/run_progress_visibility/run_progress_visibility_report.json", _contract())
    _write_json(root / ".agent/ux/run_progress_snapshot_loader/run_progress_snapshot_loader_report.json", _loader())
    template = root / "web/templates/index.html"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text(_ui_marker(), encoding="utf-8")


def test_complete_branch_is_frozen_with_warnings_and_has_required_fields():
    report = _build()

    assert report["report_kind"] == REPORT_KIND
    assert report["phase_id"] == THIS_PHASE_ID == "UX.RUN.CLOSE"
    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["final_verdict"]["ready_to_freeze"] is True
    assert report["recommended_next_phase"]["phase_id"] == "UX.LIVE.1"
    assert report["alternative_next_phase"]["phase_id"] == "OPS.TEST.4"
    for key in (
        "checkpoint_id", "source_visibility_contract_path", "source_snapshot_loader_report_path",
        "source_ui_panel_marker", "phase_completion_summary", "artifact_coverage",
        "progress_stage_contract_summary", "snapshot_loader_summary", "ui_panel_summary",
        "read_only_boundary_verification", "non_live_instrumentation_verification",
        "forbidden_runtime_changes", "warnings", "blocked_reasons", "incomplete_reasons",
        "recommended_next_phase", "guardrails",
    ):
        assert key in report
    assert report["phase_completion_summary"]["all_required_phases_complete"] is True
    assert report["read_only_boundary_verification"]["ui_panel_uses_get_only_loader"] is True
    assert report["non_live_instrumentation_verification"]["live_streaming_not_implemented"] is True


def test_missing_run_3_or_artifacts_are_incomplete():
    assert _build(registry_data=_registry(missing="UX.RUN.3"))["checkpoint_status"] == STATUS_INCOMPLETE
    assert _build(source_visibility_contract=None, source_visibility_contract_load_error="missing")["checkpoint_status"] == STATUS_INCOMPLETE
    assert _build(source_snapshot_loader_report=None, source_snapshot_loader_report_load_error="missing")["checkpoint_status"] == STATUS_INCOMPLETE
    assert _build(source_ui_panel_marker="", source_ui_panel_marker_load_error="missing")["checkpoint_status"] == STATUS_INCOMPLETE


@pytest.mark.parametrize("marker", [
    "live_instrumentation_added", "polling_added", "post_action_added", "action_controls_added",
    "runtime_behavior_changed", "patch_apply_controls_added", "validation_controls_added",
    "benchmark_controls_added", "worker_controls_added", "model_controls_added",
    "approval_enforcement_added", "progress_treated_as_authority", "progress_treated_as_success",
])
def test_forbidden_policy_markers_block(marker: str):
    report = _build(policy_violation_markers={marker: True})
    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert report["blocked_reasons"]


@pytest.mark.parametrize("extra_js", ["setInterval(loadRunProgressSnapshot, 1000);", 'fetch("/x", { method: "POST" });', "applyPatch();", "runValidation();", "runBenchmark();", "launchWorker();", "routeModel();"])
def test_ui_runtime_or_action_markers_block(extra_js: str):
    assert _build(source_ui_panel_marker=_ui_marker(extra_js))["checkpoint_status"] == STATUS_BLOCKED


def test_contract_or_loader_authority_changes_block():
    contract = _contract(guardrails={"runtime_execution_changed": True})
    assert _build(source_visibility_contract=contract)["checkpoint_status"] == STATUS_BLOCKED
    loader = _loader()
    loader["loader_result"]["snapshot"]["polling_enabled"] = True
    assert _build(source_snapshot_loader_report=loader)["checkpoint_status"] == STATUS_BLOCKED


def test_write_and_markdown_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    output = tmp_path / "out"
    result = write_run_progress_visibility_branch_checkpoint(
        repo_root=tmp_path,
        output_dir=output,
        checkpoint_id="checkpoint-test",
        created_at="2026-07-10T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(result["md_path"]).read_text(encoding="utf-8")
    assert data["checkpoint_id"] == "checkpoint-test"
    for section in (
        "Summary", "Phase Completion", "Artifact Coverage", "Progress Contract Summary",
        "Snapshot Loader Summary", "UI Panel Summary", "Read-Only Boundary Verification",
        "Non-Live Instrumentation Verification", "Forbidden Runtime Changes", "Warnings",
        "Blocked Reasons", "Incomplete Reasons", "Final Verdict", "Recommended Next Phase", "Guardrails",
    ):
        assert f"## {section}" in markdown


def test_script_writes_checkpoint_artifacts(tmp_path):
    _write_fake_repo(tmp_path)
    result = run_create_run_progress_visibility_branch_checkpoint(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        checkpoint_id="script-test",
        created_at="2026-07-10T00:00:00+09:00",
    )
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "UX.LIVE.1"
    assert Path(result["json_path"]).is_file()
    assert Path(result["md_path"]).is_file()


def test_renderer_is_pure_and_defaults_match_spec():
    report = _build()
    before = json.loads(json.dumps(report, sort_keys=True))
    assert "# Run Progress Visibility Branch Checkpoint" in render_run_progress_visibility_branch_checkpoint_markdown(report)
    assert report == before
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "ux" / "run_progress_visibility_branch_checkpoint"


def test_real_registry_closes_run_progress_branch_and_recommends_live_plan():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}
    assert by_id["UX.RUN.CLOSE"]["status"] == "complete"
    assert by_id["UX.RUN.CLOSE"]["prerequisites"] == ["UX.RUN.3"]
    assert by_id["UX.LIVE.1"]["status"] == "proposed"
    assert by_id["UX.LIVE.1"]["prerequisites"] == ["UX.RUN.CLOSE"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-run-close", created_at="t")
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.1"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.1", "MIRROR.13"]


def test_checkpoint_source_does_not_execute_runtime_work():
    source = (PROJECT_ROOT / "core/run_progress_visibility_branch_checkpoint.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import subprocess", "os.system(", "run_benchmarks(", "run_validation("):
        assert forbidden not in source
