"""UX.LIVE.4 focused tests for truthful multi-stage shadow snapshots."""
from __future__ import annotations

import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_snapshot_loader import LOADED_WITH_WARNINGS, load_run_progress_snapshot
from core.run_progress_snapshot_shadow_writer import (
    ALLOWED_WRITE_ROOT,
    BLOCKED,
    CANONICAL_JSON_NAME,
    ENVIRONMENT_FLAG,
    WRITER_DISABLED,
    WRITTEN,
    WRITTEN_WITH_WARNINGS,
    safe_update_run_progress_snapshot_shadow,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = PROJECT_ROOT / "web" / "runner.py"
WRITER_PATH = PROJECT_ROOT / "core" / "run_progress_snapshot_shadow_writer.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _path(root: Path, run_id: str) -> Path:
    return root / ALLOWED_WRITE_ROOT / run_id / CANONICAL_JSON_NAME


def _read(root: Path, run_id: str) -> dict:
    return json.loads(_path(root, run_id).read_text(encoding="utf-8"))


def test_disabled_multistage_writer_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)

    result = safe_update_run_progress_snapshot_shadow(
        "run-safe", stage_id="request_received", repo_root=tmp_path
    )

    assert result["writer_status"] == WRITER_DISABLED
    assert result["runtime_result_changed"] is False
    assert not (tmp_path / ALLOWED_WRITE_ROOT).exists()


def test_truthful_nonterminal_updates_share_one_run_id_and_are_loader_compatible(tmp_path):
    first = safe_update_run_progress_snapshot_shadow(
        "run-safe", stage_id="request_received", repo_root=tmp_path, enabled=True, mode="reviewer"
    )
    initial = _read(tmp_path, "run-safe")
    second = safe_update_run_progress_snapshot_shadow(
        "run-safe", stage_id="model_response_received", repo_root=tmp_path, enabled=True, mode="reviewer"
    )
    updated = _read(tmp_path, "run-safe")

    assert first["writer_status"] == second["writer_status"] == WRITTEN
    assert first["run_id"] == second["run_id"] == "run-safe"
    assert initial["sequence_number"] == 1
    assert updated["sequence_number"] == 2
    assert updated["created_at"] == initial["created_at"]
    assert updated["updated_at"] >= initial["updated_at"]
    assert updated["terminal"] is False
    assert updated["current_stage_id"] == "model_response_received"
    assert updated["observed_stage_ids"] == ["request_received", "model_response_received"]
    assert updated["completed_stage_ids"] == ["request_received", "model_response_received"]
    assert updated["pending_stage_ids"] == []
    assert updated["live_stream_enabled"] is False
    assert updated["polling_enabled"] is False
    assert updated["runtime_authority"] is False
    assert updated["actions_available"] == []
    assert load_run_progress_snapshot("run-safe", repo_root=tmp_path)["loader_status"] == LOADED_WITH_WARNINGS


def test_terminal_success_and_error_are_truthful_and_terminal(tmp_path):
    safe_update_run_progress_snapshot_shadow("success", stage_id="request_received", repo_root=tmp_path, enabled=True)
    result = safe_update_run_progress_snapshot_shadow("success", stage_id="final_response_ready", repo_root=tmp_path, enabled=True)
    success = _read(tmp_path, "success")

    assert result["writer_status"] == WRITTEN
    assert success["terminal"] is True
    assert success["current_stage_id"] == "final_response_ready"
    assert success["observed_stage_ids"] == ["request_received", "final_response_ready"]
    assert success["completed_stage_ids"] == ["request_received", "final_response_ready"]

    safe_update_run_progress_snapshot_shadow("failure", stage_id="request_received", repo_root=tmp_path, enabled=True)
    safe_update_run_progress_snapshot_shadow("failure", stage_id="error_reported", repo_root=tmp_path, enabled=True, error_category="runtime_error")
    failure = _read(tmp_path, "failure")
    assert failure["terminal"] is True
    assert failure["current_stage_id"] == "error_reported"
    assert failure["error_stage_ids"] == ["error_reported"]
    assert failure["errors"] == ["runtime_error"]


def test_duplicate_unknown_stale_and_post_terminal_updates_are_safe(tmp_path):
    safe_update_run_progress_snapshot_shadow("run-safe", stage_id="request_received", repo_root=tmp_path, enabled=True)
    before = _read(tmp_path, "run-safe")
    duplicate = safe_update_run_progress_snapshot_shadow("run-safe", stage_id="request_received", repo_root=tmp_path, enabled=True)
    assert duplicate["writer_status"] == WRITTEN_WITH_WARNINGS
    assert duplicate["warning"] == "duplicate_stage_update_ignored"
    assert _read(tmp_path, "run-safe")["sequence_number"] == before["sequence_number"]

    stale = safe_update_run_progress_snapshot_shadow(
        "run-safe", stage_id="model_response_received", repo_root=tmp_path, enabled=True, expected_sequence_number=0
    )
    unknown = safe_update_run_progress_snapshot_shadow("run-safe", stage_id="validation_finished", repo_root=tmp_path, enabled=True)
    assert stale["writer_status"] == unknown["writer_status"] == BLOCKED
    assert stale["blocked_reason"] == "stale_sequence_update_rejected"
    assert unknown["blocked_reason"] == "unknown_stage_id"

    safe_update_run_progress_snapshot_shadow("run-safe", stage_id="final_response_ready", repo_root=tmp_path, enabled=True)
    terminal = _read(tmp_path, "run-safe")
    post_terminal = safe_update_run_progress_snapshot_shadow("run-safe", stage_id="model_response_received", repo_root=tmp_path, enabled=True)
    assert post_terminal["writer_status"] == BLOCKED
    assert post_terminal["blocked_reason"] == "terminal_snapshot_update_rejected"
    assert _read(tmp_path, "run-safe") == terminal


def test_raw_safe_message_is_not_persisted_and_sensitive_metadata_is_blocked(tmp_path):
    result = safe_update_run_progress_snapshot_shadow(
        "run-safe",
        stage_id="request_received",
        repo_root=tmp_path,
        enabled=True,
        safe_message="user message: do not persist this raw text",
    )
    snapshot_text = _path(tmp_path, "run-safe").read_text(encoding="utf-8")
    assert result["writer_status"] == WRITTEN
    assert "do not persist this raw text" not in snapshot_text

    blocked = safe_update_run_progress_snapshot_shadow(
        "other-safe",
        stage_id="request_received",
        repo_root=tmp_path,
        enabled=True,
        source_component="authorization-header",
    )
    assert blocked["writer_status"] == BLOCKED
    assert blocked["blocked_reason"] == "sensitive_metadata_rejected"
    assert not _path(tmp_path, "other-safe").exists()


def test_get_only_route_loads_nonterminal_snapshot(tmp_path, monkeypatch):
    from web import app as web_app

    safe_update_run_progress_snapshot_shadow("route-run", stage_id="request_received", repo_root=tmp_path, enabled=True)
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as client:
        response = client.get("/ux/run-progress/snapshot/route-run")

    assert response.status_code == 200
    snapshot = response.get_json()["result"]["snapshot"]
    assert snapshot["terminal"] is False
    assert snapshot["current_stage_id"] == "request_received"


def test_runner_helpers_use_same_internal_run_id_without_changing_result(tmp_path, monkeypatch):
    from web import runner

    monkeypatch.setattr(runner, "_RUN_PROGRESS_SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    run_id = runner._new_run_progress_shadow_run_id()
    result = {"answer": "unchanged", "patch": "unchanged"}

    runner._maybe_update_run_progress_snapshot_shadow(run_id=run_id, mode="reviewer", stage_id="request_received")
    runner._maybe_update_run_progress_snapshot_shadow(run_id=run_id, mode="reviewer", stage_id="model_response_received")
    returned = runner._maybe_write_run_progress_snapshot_shadow(
        result=result, session_id=run_id, mode="reviewer", outcome="success"
    )
    snapshot = _read(tmp_path, run_id)

    assert returned is result
    assert returned == {"answer": "unchanged", "patch": "unchanged"}
    assert snapshot["observed_stage_ids"] == ["request_received", "model_response_received", "final_response_ready"]
    assert snapshot["sequence_number"] == 3
    assert snapshot["metadata"]["source_component"] == "web.runner"


def test_runner_source_adds_no_live_delivery_or_execution_controls():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "stage_id=\"request_received\"" in source
    assert "stage_id=\"model_response_received\"" in source
    assert "draft = run_draft_pipeline(state)" in source
    assert source.index('draft = run_draft_pipeline(state)') < source.index('stage_id="model_response_received"')
    for forbidden in ("setInterval", "WebSocket", "EventSource", "threading.Thread", "run_progress_events.jsonl"):
        assert forbidden not in source


def test_writer_source_has_no_network_database_or_runtime_control_paths():
    source = WRITER_PATH.read_text(encoding="utf-8")
    for forbidden in ("requests", "httpx", "socket", "subprocess", "Popen", "sqlite", "sqlalchemy", "run_draft_pipeline", "apply_patch", "run_benchmarks"):
        assert forbidden not in source


def test_registry_marks_live_4_complete_adds_live_5_and_recommends_it():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.4"]["status"] == "complete"
    assert by_id["UX.LIVE.4"]["prerequisites"] == ["UX.LIVE.3"]
    assert by_id["UX.LIVE.5"]["status"] == "proposed"
    assert by_id["UX.LIVE.5"]["prerequisites"] == ["UX.LIVE.4"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-4", created_at="t")
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.5"
