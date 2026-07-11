"""UX.LIVE.6 tests for one-click, advisory run-progress refreshes only."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _between(text: str, start: str, end: str) -> str:
    beginning = text.index(start)
    return text[beginning:text.index(end, beginning)]


def _panel() -> str:
    return _between(
        INDEX_TEMPLATE.read_text(encoding="utf-8"),
        "<!-- UX.RUN.3 run-progress-panel",
        "<!-- /UX.RUN.3 run-progress-panel -->",
    )


def _panel_js() -> str:
    return _between(
        INDEX_TEMPLATE.read_text(encoding="utf-8"),
        "// UX.RUN.3 run-progress-panel",
        "// /UX.RUN.3 run-progress-panel",
    )


def _refresh_function(js: str | None = None) -> str:
    source = js or _panel_js()
    return _between(
        source,
        "async function refreshAssociatedRunProgressSnapshot()",
        "function _runProgressBadgeClass",
    )


def test_refresh_control_is_a_disabled_read_only_button_without_an_association():
    panel = _panel()

    assert re.search(
        r'<button id="runProgressRefreshButton"[^>]*type="button"[^>]*disabled[^>]*>Refresh progress</button>',
        panel,
    )
    assert "No progress snapshot is associated with the current run." in _panel_js()
    assert 'id="runProgressLoadStatus"' in panel
    assert 'aria-live="polite"' in panel
    assert "run-progress-refresh-button" in STYLE_SHEET.read_text(encoding="utf-8")


def test_refresh_uses_only_the_current_safe_association_and_one_existing_get_loader_call():
    js = _panel_js()
    refresh = _refresh_function(js)

    assert "const snapshotId = currentRunProgressSnapshotId;" in refresh
    assert "currentRunProgressAvailable" in refresh
    assert "RUN_PROGRESS_ASSOCIATION_SAFE_ID_RE.test(snapshotId)" in refresh
    assert refresh.count("loadRunProgressSnapshot(snapshotId") == 1
    assert 'fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" })' in js
    assert "encodeURIComponent(requestedId)" in js
    assert "snapshot_path" not in js
    assert "repo_path" not in js


def test_refresh_prevents_duplicate_requests_and_restores_its_button_state():
    js = _panel_js()
    refresh = _refresh_function(js)

    assert "let runProgressRefreshInFlight = false;" in js
    assert "if (runProgressRefreshInFlight) return;" in refresh
    assert 'setRunProgressRefreshState("refreshing"' in refresh
    assert 'setRunProgressRefreshState("refreshed"' in refresh
    assert 'setRunProgressRefreshState(outcome.status || "refresh_failed"' in refresh
    assert 'refreshButton.disabled = !currentRunProgressAvailable || runProgressRefreshInFlight;' in js
    assert 'refreshButton.textContent = runProgressRefreshInFlight ? "Refreshing…" : "Refresh progress";' in js


def test_refresh_has_safe_failure_messages_and_never_renders_a_stale_association():
    js = _panel_js()

    for status in (
        "snapshot_not_found",
        "snapshot_blocked",
        "snapshot_malformed",
        "refresh_failed",
    ):
        assert status in js
    assert "The associated snapshot is not currently available." in js
    assert "The progress snapshot could not be read safely." in js
    assert "The progress snapshot refresh failed." in js
    assert "_runProgressAssociationIsCurrent(requestedId, options)" in js
    assert "snapshotId === currentRunProgressSnapshotId" in js
    assert "if (outcome.stale)" in _refresh_function(js)
    assert 'setRunProgressRefreshState("idle")' in _refresh_function(js)


def test_refresh_keeps_progress_advisory_and_does_not_add_background_or_execution_behaviour():
    js = _panel_js()
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")

    for field in (
        "observed_stage_ids",
        "completed_stage_ids",
        "updated_at",
        "sequence_number",
        "terminal",
        "warnings",
        "errors",
        "error_stage_ids",
    ):
        assert f">{field}<" in _panel()
    assert "does not imply success, validation, or approval" in js
    assert "not a passed result" in _panel()
    assert "setCurrentRunProgressAssociation(RUN_PROGRESS_ASSOCIATION_FROM_RUN_RESULT);" in template

    for forbidden in (
        "setInterval",
        "setTimeout",
        "requestAnimationFrame",
        "WebSocket",
        "EventSource",
        "visibilitychange",
        "focus",
        'method: "POST"',
        "enableWriter",
        "applyPatch(",
        "runValidation",
        "runBenchmark",
        "launchWorker",
        "routeModel",
        "callModel",
        "localStorage",
        "document.cookie",
    ):
        assert forbidden not in js


def test_registry_completes_live_6_and_recommends_live_7():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.6"]["status"] == "complete"
    assert by_id["UX.LIVE.6"]["prerequisites"] == ["UX.LIVE.5"]
    assert by_id["UX.LIVE.7"]["status"] == "complete"
    assert by_id["UX.LIVE.7"]["prerequisites"] == ["UX.LIVE.6"]
    assert by_id["UX.LIVE.8"]["status"] == "proposed"
    assert by_id["UX.LIVE.8"]["prerequisites"] == ["UX.LIVE.7"]
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-6", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "UX.LIVE.8"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["UX.LIVE.8", "MIRROR.13"]
