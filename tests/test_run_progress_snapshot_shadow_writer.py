"""Focused UX.LIVE.3 shadow-writer tests.

These tests exercise explicit temporary directories only.  Normal disabled
operation never creates a snapshot directory.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_snapshot_loader import LOADED_WITH_WARNINGS, load_run_progress_snapshot
from core.run_progress_snapshot_shadow_writer import (
    ALLOWED_WRITE_ROOT,
    BLOCKED,
    CANONICAL_JSON_NAME,
    ENVIRONMENT_FLAG,
    FAILED_ISOLATED,
    REQUIRED_SNAPSHOT_FIELDS,
    WRITER_DISABLED,
    WRITTEN,
    build_run_progress_snapshot,
    is_run_progress_shadow_writer_enabled,
    normalize_run_id,
    safe_write_run_progress_snapshot,
    validate_snapshot_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WRITER_PATH = PROJECT_ROOT / "core" / "run_progress_snapshot_shadow_writer.py"
RUNNER_PATH = PROJECT_ROOT / "web" / "runner.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _snapshot_path(root: Path, run_id: str) -> Path:
    return root / ALLOWED_WRITE_ROOT / run_id / CANONICAL_JSON_NAME


def test_writer_is_disabled_by_default_and_missing_configuration_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)

    assert is_run_progress_shadow_writer_enabled() is False
    result = safe_write_run_progress_snapshot("safe-run", repo_root=tmp_path)

    assert result["writer_status"] == WRITER_DISABLED
    assert result["writer_enabled"] is False
    assert result["snapshot_written"] is False
    assert result["runtime_result_changed"] is False
    assert not (tmp_path / ALLOWED_WRITE_ROOT).exists()


def test_enabled_writer_writes_one_safe_terminal_success_snapshot_and_loader_reads_it(tmp_path):
    result = safe_write_run_progress_snapshot(
        "safe-run",
        repo_root=tmp_path,
        enabled=True,
        metadata={"mode": "reviewer", "source_component": "test", "result_type": "terminal_response"},
    )
    path = _snapshot_path(tmp_path, "safe-run")

    assert result["writer_status"] == WRITTEN
    assert result["snapshot_written"] is True
    assert result["snapshot_path"] == ".agent/ux/run_progress_snapshots/safe-run/run_progress_snapshot.json"
    assert result["runtime_result_changed"] is False
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert set(REQUIRED_SNAPSHOT_FIELDS) <= set(snapshot)
    assert snapshot["current_stage_id"] == "final_response_ready"
    assert snapshot["observed_stage_ids"] == ["final_response_ready"]
    assert snapshot["completed_stage_ids"] == ["final_response_ready"]
    assert snapshot["pending_stage_ids"] == []
    assert snapshot["error_stage_ids"] == []
    assert snapshot["sequence_number"] == 1
    assert snapshot["terminal"] is True
    assert snapshot["runtime_authority"] is False
    assert snapshot["action_triggered"] is False
    assert snapshot["actions_available"] == []
    assert snapshot["polling_enabled"] is False
    assert snapshot["live_stream_enabled"] is False
    assert snapshot["runtime_behavior_changed"] is False
    assert "prompt_built" not in snapshot["observed_stage_ids"]
    assert "validation_finished" not in snapshot["completed_stage_ids"]

    loaded = load_run_progress_snapshot("safe-run", repo_root=tmp_path)
    assert loaded["loader_status"] == LOADED_WITH_WARNINGS
    assert loaded["blocked_reasons"] == []
    assert loaded["snapshot"]["snapshot_id"] == "safe-run"


def test_enabled_writer_writes_terminal_error_without_raw_error_payload(tmp_path):
    result = safe_write_run_progress_snapshot(
        "failed-run",
        repo_root=tmp_path,
        outcome="error",
        enabled=True,
        metadata={"mode": "reviewer", "source_component": "test", "result_type": "terminal_error", "error_category": "runtime_error"},
    )
    snapshot = json.loads(_snapshot_path(tmp_path, "failed-run").read_text(encoding="utf-8"))

    assert result["writer_status"] == WRITTEN
    assert snapshot["current_stage_id"] == "error_reported"
    assert snapshot["observed_stage_ids"] == ["error_reported"]
    assert snapshot["completed_stage_ids"] == []
    assert snapshot["error_stage_ids"] == ["error_reported"]
    assert snapshot["errors"] == ["runtime_error"]
    assert "details are intentionally omitted" in snapshot["stages"][0]["message"]
    assert "Error:" not in json.dumps(snapshot)


@pytest.mark.parametrize("run_id", ["../escape", "..\\escape", "/absolute", "C:\\drive", "run.json", "", "secrets"])
def test_unsafe_run_ids_are_blocked_without_creating_snapshot_root(tmp_path, run_id):
    result = safe_write_run_progress_snapshot(run_id, repo_root=tmp_path, enabled=True)

    assert result["writer_status"] == BLOCKED
    assert result["snapshot_written"] is False
    assert result["blocked_reason"]
    assert not (tmp_path / ALLOWED_WRITE_ROOT).exists()


def test_normalize_run_id_accepts_only_safe_slug():
    assert normalize_run_id("run_20260710") == "run_20260710"
    with pytest.raises(ValueError):
        normalize_run_id("folder/run")


def test_sensitive_metadata_is_rejected_before_persistence(tmp_path):
    result = safe_write_run_progress_snapshot(
        "safe-run",
        repo_root=tmp_path,
        enabled=True,
        metadata={"api_key": "do-not-store"},
    )

    assert result["writer_status"] == BLOCKED
    assert result["blocked_reason"] == "metadata_key_not_allowed"
    assert not _snapshot_path(tmp_path, "safe-run").exists()


def test_metadata_fields_cannot_be_used_to_store_short_raw_messages(tmp_path):
    result = safe_write_run_progress_snapshot(
        "safe-run",
        repo_root=tmp_path,
        enabled=True,
        metadata={"mode": "please fix the payment page"},
    )

    assert result["writer_status"] == BLOCKED
    assert result["blocked_reason"] == "metadata_mode_not_allowed"


def test_payload_validator_rejects_authority_actions_and_sensitive_metadata():
    snapshot = build_run_progress_snapshot("safe-run", metadata={"mode": "reviewer"})
    assert validate_snapshot_payload(snapshot)["valid"] is True

    snapshot["runtime_authority"] = True
    assert validate_snapshot_payload(snapshot)["valid"] is False
    snapshot["runtime_authority"] = False
    snapshot["actions_available"] = ["rerun"]
    assert validate_snapshot_payload(snapshot)["valid"] is False
    snapshot["actions_available"] = []
    snapshot["metadata"] = {"token": "not-allowed"}
    assert validate_snapshot_payload(snapshot)["valid"] is False


def test_atomic_write_cleans_temporary_file_after_replace_failure(tmp_path, monkeypatch):
    import core.run_progress_snapshot_shadow_writer as writer

    monkeypatch.setattr(writer.os, "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")))
    result = safe_write_run_progress_snapshot("safe-run", repo_root=tmp_path, enabled=True)
    directory = _snapshot_path(tmp_path, "safe-run").parent

    assert result["writer_status"] == FAILED_ISOLATED
    assert result["failure_isolated"] is True
    assert not _snapshot_path(tmp_path, "safe-run").exists()
    assert not list(directory.glob("*.tmp"))


def test_malformed_previous_snapshot_is_preserved_and_not_silently_overwritten(tmp_path):
    path = _snapshot_path(tmp_path, "safe-run")
    path.parent.mkdir(parents=True)
    path.write_text("{malformed", encoding="utf-8")

    result = safe_write_run_progress_snapshot("safe-run", repo_root=tmp_path, enabled=True)

    assert result["writer_status"] == FAILED_ISOLATED
    assert result["failure_isolated"] is True
    assert result["warning"] == "malformed_prior_snapshot_preserved"
    assert path.read_text(encoding="utf-8") == "{malformed"


def test_existing_terminal_snapshot_at_different_boundary_is_preserved(tmp_path):
    safe_write_run_progress_snapshot("safe-run", repo_root=tmp_path, enabled=True, outcome="success")
    path = _snapshot_path(tmp_path, "safe-run")
    before = path.read_text(encoding="utf-8")

    result = safe_write_run_progress_snapshot("safe-run", repo_root=tmp_path, enabled=True, outcome="error")

    assert result["writer_status"] == BLOCKED
    assert result["blocked_reason"] == "terminal_snapshot_update_rejected"
    assert path.read_text(encoding="utf-8") == before


def test_final_boundary_helper_keeps_main_result_identical_and_writes_only_when_enabled(tmp_path, monkeypatch):
    from web import runner

    monkeypatch.setattr(runner, "_RUN_PROGRESS_SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    result = {"answer": "unchanged", "patch": "unchanged"}

    returned = runner._maybe_write_run_progress_snapshot_shadow(
        result=result,
        session_id="runner-final",
        mode="reviewer",
        outcome="success",
    )

    assert returned is result
    assert returned == {"answer": "unchanged", "patch": "unchanged"}
    snapshot = json.loads(_snapshot_path(tmp_path, "runner-final").read_text(encoding="utf-8"))
    assert snapshot["metadata"] == {
        "mode": "reviewer",
        "source_component": "web.runner",
        "result_type": "terminal_response",
    }


def test_final_boundary_helper_isolates_unexpected_writer_failure(monkeypatch):
    from web import runner

    monkeypatch.setattr(runner, "safe_write_run_progress_snapshot", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("writer failure")))
    result = {"answer": "unchanged"}

    returned = runner._maybe_write_run_progress_snapshot_shadow(
        result=result,
        session_id="runner-final",
        mode="reviewer",
        outcome="error",
    )

    assert returned is result
    assert returned["answer"] == "unchanged"


def test_get_only_loader_route_returns_generated_snapshot(tmp_path, monkeypatch):
    from web import app as web_app

    safe_write_run_progress_snapshot("route-run", repo_root=tmp_path, enabled=True)
    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as client:
        response = client.get("/ux/run-progress/snapshot/route-run")

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["result"]["snapshot"]["current_stage_id"] == "final_response_ready"
    assert body["result"]["snapshot"]["actions_available"] == []


def test_runner_integration_is_single_terminal_shadow_observer_without_live_delivery():
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "def _maybe_write_run_progress_snapshot_shadow(" in source
    assert source.count("_maybe_write_run_progress_snapshot_shadow(") == 3
    assert "outcome=\"success\"" in source
    assert "outcome=\"error\"" in source
    for forbidden in ("setInterval", "WebSocket", "EventSource", "threading.Thread", "run_progress_events.jsonl"):
        assert forbidden not in source


def test_writer_source_has_no_network_database_or_execution_expansion():
    source = WRITER_PATH.read_text(encoding="utf-8")
    for forbidden in ("requests", "httpx", "socket", "subprocess", "Popen", "sqlite", "sqlalchemy", "run_draft_pipeline", "run_benchmarks", "apply_patch"):
        assert forbidden not in source


def test_registry_marks_live_3_and_live_4_complete_then_recommends_live_5():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.3"]["status"] == "complete"
    assert by_id["UX.LIVE.3"]["prerequisites"] == ["UX.LIVE.2"]
    assert by_id["UX.LIVE.4"]["status"] == "complete"
    assert by_id["UX.LIVE.4"]["prerequisites"] == ["UX.LIVE.3"]
    assert by_id["UX.LIVE.5"]["status"] == "complete"
    assert by_id["UX.LIVE.5"]["prerequisites"] == ["UX.LIVE.4"]
    assert by_id["UX.LIVE.6"]["status"] == "complete"
    assert by_id["UX.LIVE.6"]["prerequisites"] == ["UX.LIVE.5"]
    assert by_id["UX.LIVE.7"]["status"] == "complete"
    assert by_id["UX.LIVE.7"]["prerequisites"] == ["UX.LIVE.6"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-3", created_at="t")
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.8"
