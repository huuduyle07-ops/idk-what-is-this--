"""UX.LIVE.5 tests for advisory current-run snapshot association only."""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.run_progress_snapshot_shadow_writer import ALLOWED_WRITE_ROOT, ENVIRONMENT_FLAG


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _panel_js() -> str:
    text = INDEX_TEMPLATE.read_text(encoding="utf-8")
    start = text.index("// UX.RUN.3 run-progress-panel")
    end = text.index("// /UX.RUN.3 run-progress-panel", start)
    return text[start:end]


def test_enabled_association_reuses_the_stable_safe_writer_run_id(tmp_path, monkeypatch):
    from web import runner

    monkeypatch.setattr(runner, "_RUN_PROGRESS_SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setenv(ENVIRONMENT_FLAG, "true")
    run_id = runner._new_run_progress_shadow_run_id()
    association = runner.build_current_run_progress_snapshot_association(run_id, writer_enabled=True)
    runner._maybe_update_run_progress_snapshot_shadow(
        run_id=run_id,
        mode="reviewer",
        stage_id="request_received",
    )

    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id)
    assert association["association_status"] == "current_run_snapshot_associated_with_warnings"
    assert association["snapshot_id"] == run_id
    assert association["snapshot_available"] is True
    assert association["writer_enabled"] is True
    assert association["association_mode"] == "advisory"
    assert association["safe_for_loader"] is True
    assert (tmp_path / ALLOWED_WRITE_ROOT / run_id / "run_progress_snapshot.json").is_file()


def test_disabled_association_is_unavailable_and_writes_nothing(tmp_path, monkeypatch):
    from web import runner

    monkeypatch.setattr(runner, "_RUN_PROGRESS_SNAPSHOT_ROOT", tmp_path)
    monkeypatch.delenv(ENVIRONMENT_FLAG, raising=False)
    run_id = runner._new_run_progress_shadow_run_id()
    association = runner.build_current_run_progress_snapshot_association(run_id, writer_enabled=False)
    runner._maybe_update_run_progress_snapshot_shadow(
        run_id=run_id,
        mode="reviewer",
        stage_id="request_received",
    )

    assert run_id == ""
    assert association["association_status"] == "current_run_snapshot_unavailable"
    assert association["snapshot_id"] is None
    assert association["snapshot_available"] is False
    assert association["writer_enabled"] is False
    assert "disabled" in association["notice"]
    assert not (tmp_path / ALLOWED_WRITE_ROOT).exists()


def test_association_metadata_is_advisory_and_preserves_existing_result_payloads():
    from web import runner

    result = {
        "answer": "unchanged answer",
        "patch": "unchanged patch",
        "validation": "unchanged evidence",
        "status": "existing status",
    }
    original = dict(result)
    returned = runner._attach_current_run_progress_snapshot_association(
        result,
        "run_safe_123",
        writer_enabled=True,
    )

    assert returned is result
    for key, value in original.items():
        assert returned[key] == value
    assert returned["run_progress_snapshot_id"] == "run_safe_123"
    assert returned["run_progress_available"] is True
    assert returned["run_progress_writer_enabled"] is True
    assert returned["run_progress_association_mode"] == "advisory"
    assert "does not imply success" in returned["run_progress_notice"]


def test_unsafe_ids_are_not_exposed_or_derived_from_raw_input():
    from web import runner

    raw_input = "../../repo/.env user prompt and model response"
    association = runner.build_current_run_progress_snapshot_association(raw_input, writer_enabled=True)
    serialized = json.dumps(association)

    assert association["association_status"] == "current_run_snapshot_invalid"
    assert association["snapshot_id"] is None
    assert association["snapshot_available"] is False
    assert "unsafe_snapshot_id_rejected" in association["warnings"]
    assert raw_input not in serialized
    source = inspect.getsource(runner.build_current_run_progress_snapshot_association)
    assert "snapshot_path" not in source
    assert "repo_path" not in source


def test_panel_keeps_association_page_local_and_manual_get_only():
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    js = _panel_js()

    for name in (
        "currentRunProgressSnapshotId",
        "currentRunProgressAvailable",
        "currentRunProgressWriterEnabled",
        "setCurrentRunProgressAssociation",
        "loadAssociatedRunProgressSnapshot",
    ):
        assert name in js
    for field in (
        "associated_snapshot_id",
        "snapshot_available",
        "writer_enabled",
        "association_mode",
    ):
        assert f">{field}<" in template
    assert "Load associated snapshot" in template

    assert 'fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" })' in js
    assert "loadRunProgressSnapshot(currentRunProgressSnapshotId)" in js
    assert "Snapshot is associated but not currently available." in js
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "setInterval",
        "setTimeout",
        "WebSocket",
        "EventSource",
        'method: "POST"',
        "enableWriter",
        "applyPatch(",
        "runValidation",
        "runBenchmark",
        "launchWorker",
    ):
        assert forbidden not in js


def test_registry_completes_live_5_and_recommends_live_6():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.5"]["status"] == "complete"
    assert by_id["UX.LIVE.5"]["prerequisites"] == ["UX.LIVE.4"]
    assert by_id["UX.LIVE.6"]["status"] == "complete"
    assert by_id["UX.LIVE.6"]["prerequisites"] == ["UX.LIVE.5"]
    assert by_id["UX.LIVE.7"]["status"] == "complete"
    assert by_id["UX.LIVE.7"]["prerequisites"] == ["UX.LIVE.6"]
    assert by_id["UX.LIVE.8"]["status"] == "proposed"
    assert by_id["UX.LIVE.8"]["prerequisites"] == ["UX.LIVE.7"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-5", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.8"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.8", "MIRROR.13"]
