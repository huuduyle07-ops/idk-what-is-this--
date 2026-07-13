"""UX.LIVE.10 tests for explicitly activated, bounded progress polling only."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from web.app import _run_progress_polling_config


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


def test_configuration_is_default_off_and_malformed_values_fall_back_to_bounded_defaults(monkeypatch):
    for name in (
        "RUN_PROGRESS_POLLING_ENABLED",
        "RUN_PROGRESS_POLL_INTERVAL_SECONDS",
        "RUN_PROGRESS_POLL_MAX_DURATION_SECONDS",
        "RUN_PROGRESS_POLL_MAX_REQUESTS",
        "RUN_PROGRESS_POLL_MAX_CONSECUTIVE_ERRORS",
    ):
        monkeypatch.delenv(name, raising=False)
    assert _run_progress_polling_config() == {
        "enabled": False,
        "interval_seconds": 3,
        "maximum_duration_seconds": 300,
        "maximum_requests": 100,
        "maximum_consecutive_errors": 3,
    }

    monkeypatch.setenv("RUN_PROGRESS_POLLING_ENABLED", "true")
    monkeypatch.setenv("RUN_PROGRESS_POLL_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("RUN_PROGRESS_POLL_MAX_DURATION_SECONDS", "infinite")
    monkeypatch.setenv("RUN_PROGRESS_POLL_MAX_REQUESTS", "0")
    monkeypatch.setenv("RUN_PROGRESS_POLL_MAX_CONSECUTIVE_ERRORS", "-1")
    assert _run_progress_polling_config() == {
        "enabled": True,
        "interval_seconds": 3,
        "maximum_duration_seconds": 300,
        "maximum_requests": 100,
        "maximum_consecutive_errors": 3,
    }


def test_controls_are_real_secondary_buttons_with_textual_accessible_status():
    panel = _panel()

    assert re.search(
        r'<button id="runProgressPollingStartButton"[^>]*type="button"[^>]*disabled[^>]*>Start progress updates</button>',
        panel,
    )
    assert re.search(
        r'<button id="runProgressPollingStopButton"[^>]*type="button"[^>]*disabled[^>]*>Stop progress updates</button>',
        panel,
    )
    assert 'id="runProgressPollingStatus"' in panel
    assert 'aria-live="polite"' in panel
    assert "Temporary read-only progress updates" in panel
    css = STYLE_SHEET.read_text(encoding="utf-8")
    assert ".run-progress-polling-controls" in css
    assert ".run-progress-polling-button" in css


def test_polling_is_explicit_default_off_and_never_started_by_association_or_page_load():
    js = _panel_js()
    template = INDEX_TEMPLATE.read_text(encoding="utf-8")
    panel_end = template.index("// /UX.RUN.3 run-progress-panel")
    page_initialization = template[panel_end:template.index("</script>", panel_end)]

    assert "enabled: false" in js
    assert "supplied.enabled === true" in js
    assert "function startRunProgressPolling()" in js
    assert "onclick=\"startRunProgressPolling()\"" in _panel()
    assert "setCurrentRunProgressAssociation(RUN_PROGRESS_ASSOCIATION_FROM_RUN_RESULT);" in page_initialization
    assert "startRunProgressPolling(RUN_PROGRESS_ASSOCIATION_FROM_RUN_RESULT)" not in template
    assert "startRunProgressPolling();" not in page_initialization


def test_one_shot_scheduler_has_finite_bounds_and_no_overlapping_or_queued_gets():
    js = _panel_js()

    for state in (
        "runProgressPollingActive",
        "runProgressPollingPaused",
        "runProgressPollingInFlight",
        "runProgressPollingTimeoutId",
        "runProgressPollingStartedAt",
        "runProgressPollingRequestCount",
        "runProgressPollingConsecutiveErrors",
        "runProgressPollingSnapshotId",
        "runProgressPollingSessionToken",
    ):
        assert f"let {state}" in js
    assert "window.setTimeout" in js
    assert "window.clearTimeout" in js
    assert "setInterval" not in js
    assert "runProgressPollingTimeoutId !== null" in js
    assert "runProgressPollingInFlight || runProgressRefreshInFlight" in js
    assert "runProgressPollingRequestCount >= RUN_PROGRESS_POLLING_CONFIGURATION.maximumRequests" in js
    assert "_runProgressPollingDurationExpired" in js
    assert "runProgressPollingRequestCount += 1" in js


def test_shared_loader_preserves_only_the_existing_safe_get_route_and_manual_override_policy():
    js = _panel_js()

    assert js.count('fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" })') == 1
    assert "encodeURIComponent(requestedId)" in js
    assert "pollingSessionToken: token" in js
    assert "if (runProgressPollingActive || runProgressPollingPaused) stopRunProgressPolling(\"operator\")" in js
    assert "manualRefresh: true" in js
    assert "runProgressRefreshInFlight" in js
    for forbidden in (
        'method: "POST"',
        "WebSocket",
        "EventSource",
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "serviceWorker",
        "snapshot_path",
        "repo_path",
    ):
        assert forbidden not in js


def test_terminal_association_error_and_freshness_stops_are_deterministic_and_advisory():
    js = _panel_js()

    for reason in (
        "operator",
        "terminal",
        "association_changed",
        "association_unavailable",
        "duration_limit",
        "request_limit",
        "error_limit",
        "possibly_abandoned",
        "blocked_snapshot",
        "unsafe_snapshot_id",
        "page_unload",
        "stale_session",
        "configuration_disabled",
    ):
        assert f'"{reason}"' in js
    assert "if (snapshot.terminal === true)" in js
    assert 'stopRunProgressPolling("terminal")' in js
    assert 'freshness.freshness_status === "possibly_abandoned"' in js
    assert 'stopRunProgressPolling("possibly_abandoned")' in js
    assert 'stopRunProgressPolling("association_changed")' in js
    assert "runProgressPollingConsecutiveErrors >= RUN_PROGRESS_POLLING_CONFIGURATION.maximumConsecutiveErrors" in js
    assert "runtime_authority: false" in js
    assert "action_triggered: false" in js
    assert "actions_available: []" in js
    for forbidden in ("enableWriter", "applyPatch(", "runValidation", "runBenchmark", "launchWorker", "routeModel", "callModel"):
        assert forbidden not in js


def test_hidden_tab_pause_resume_and_page_unload_use_one_listener_and_no_burst():
    js = _panel_js()

    assert 'document.addEventListener("visibilitychange", _handleRunProgressPollingVisibilityChange);' in js
    assert 'window.addEventListener("pagehide", () => stopRunProgressPolling("page_unload"));' in js
    assert "if (document.hidden)" in js
    assert "runProgressPollingPaused = true" in js
    assert "_clearRunProgressPollingTimeout();" in js
    assert "_scheduleRunProgressPolling(runProgressPollingSessionToken);" in js
    assert "catch-up" not in js.lower()


def test_registry_completes_live_10_adds_close_and_picker_recommends_close():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.LIVE.10"]["status"] == "complete"
    assert by_id["UX.LIVE.10"]["prerequisites"] == ["UX.LIVE.9"]
    assert by_id["UX.LIVE.CLOSE"]["status"] == "complete"
    assert by_id["UX.LIVE.CLOSE"]["prerequisites"] == ["UX.LIVE.10"]
    assert by_id["DOGFOOD.1A"]["status"] == "complete"
    assert by_id["DOGFOOD.1A"]["prerequisites"] == ["UX.LIVE.CLOSE"]
    assert by_id["DOGFOOD.1B"]["status"] == "proposed"
    assert by_id["DOGFOOD.1B"]["prerequisites"] == ["DOGFOOD.1A", "HARDEN.PROGRESS.1"]
    assert by_id["VERIFY.TEST.1"]["status"] == "proposed"
    report = summarize_phase_candidates(pick_phase_candidates(data), report_id="ux-live-10", created_at="t")
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
    assert [item["phase_id"] for item in report["safe_to_prepare"][:2]] == ["DOGFOOD.1B", "VERIFY.TEST.1"]
