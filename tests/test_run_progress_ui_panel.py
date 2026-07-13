"""Tests for UX.RUN.3 - Run Progress UI Panel Stub.

The panel may display an existing UX.RUN.2 snapshot through the GET-only loader
and an explicitly activated, default-off bounded browser reader. It remains
read-only: no live run hooks, mutation requests, or execution controls.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _panel(template: str | None = None) -> str:
    return _between(
        template or _template(),
        "<!-- UX.RUN.3 run-progress-panel",
        "<!-- /UX.RUN.3 run-progress-panel -->",
    )


def _panel_js(template: str | None = None) -> str:
    return _between(
        template or _template(),
        "// UX.RUN.3 run-progress-panel",
        "// /UX.RUN.3 run-progress-panel",
    )


def _button_labels(html: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", label).strip()
        for label in re.findall(r"<button\b[^>]*>(.*?)</button>", html, re.S)
    ]


def test_run_progress_panel_exists_in_evidence_area_with_safe_empty_state():
    template = _template()
    panel = _panel(template)
    evidence_area = _between(template, 'id="ws-evidence-cards"', "<!-- /ws-evidence-cards -->")

    assert 'id="runProgressPanel"' in evidence_area
    assert 'data-run-progress-readonly="true"' in panel
    assert "Run Progress Snapshot" in panel
    assert (
        "No live progress stream yet. Load a read-only snapshot to inspect planned progress stages."
        in panel
    )
    assert "GET-only snapshot display." in panel
    assert "Optional progress updates are disabled by default" in panel
    assert "execution, validation, benchmark, worker, model, approval, or token controls" in panel

    assert "runProgressPanel" not in _between(
        template,
        'id="primarySubmit"',
        '<details class="instant-run-controls"',
    )


def test_panel_exposes_every_requested_snapshot_field_without_action_controls():
    panel = _panel()

    for field in (
        "snapshot_id",
        "snapshot_status",
        "current_stage_id",
        "observed_stage_ids",
        "completed_stage_ids",
        "pending_stage_ids",
        "warning_stage_ids",
        "error_stage_ids",
        "updated_at",
        "sequence_number",
        "terminal",
        "progress_notice",
        "simulated_only",
        "live_stream_enabled",
        "polling_enabled",
        "runtime_behavior_changed",
        "warnings",
        "errors",
        "blocked_reasons",
    ):
        assert f">{field}<" in panel

    assert _button_labels(panel) == [
        "Refresh progress",
        "Load associated snapshot",
        "Load snapshot",
        "Start progress updates",
        "Stop progress updates",
    ]
    for forbidden in (
        "Apply",
        "Run",
        "Validate",
        "Benchmark",
        "Worker",
        "Model",
        "Approve",
        "Token",
    ):
        assert forbidden not in _button_labels(panel)


def test_panel_displays_derived_freshness_as_secondary_manual_load_advice():
    panel = _panel()
    js = _panel_js()

    for field in (
        "Freshness",
        "snapshot_age",
        "terminal_outcome",
        "freshness_notice",
        "freshness_warning_codes",
    ):
        assert f">{field}<" in panel
    for element_id in (
        "runProgressFreshnessStatus",
        "runProgressFreshnessAge",
        "runProgressTerminalOutcome",
        "runProgressFreshnessNotice",
        "runProgressFreshnessWarnings",
    ):
        assert f'id="{element_id}"' in panel

    for status in ("fresh", "recent", "terminal", "stale", "possibly_abandoned", "unknown"):
        assert f'{status}:' in js
    assert "const freshness = _runProgressObject(result.freshness);" in js
    assert "renderRunProgressSnapshot({ ...snapshot, freshness });" in js
    assert "Optional progress updates are disabled by default" in panel
    assert "Temporary read-only progress updates" in panel


def test_stage_chips_distinguish_every_visibility_state_and_not_run_is_not_passed():
    panel = _panel()

    for state in (
        "completed",
        "current",
        "pending",
        "warning",
        "error",
        "not-run",
    ):
        assert f"run-progress-stage--{state}" in panel

    assert "Completed" in panel
    assert "Current" in panel
    assert "Pending" in panel
    assert "Warning" in panel
    assert "Error" in panel
    assert "Not run / unavailable" in panel
    assert "not a passed result" in panel


def test_panel_javascript_uses_only_operator_initiated_get_and_renders_error_states():
    js = _panel_js()

    assert "async function loadRunProgressSnapshot(snapshotId, options = {})" in js
    assert "function renderRunProgressSnapshot" in js
    assert 'fetch("/ux/run-progress/snapshot/" + safeId, { method: "GET" })' in js
    assert "encodeURIComponent(requestedId)" in js
    assert "payload.ok !== true" in js
    assert "result.snapshot" in js
    assert "snapshot_not_found" in js
    assert "snapshot_malformed" in js
    assert "snapshot_blocked" in js
    assert "blocked_reasons" in js

    for forbidden in (
        'method: "POST"',
        "method: 'POST'",
        "setInterval",
        "applyPatch(",
        "generatePatch(",
        "runValidation",
        "runBenchmark",
        "launchWorker",
        "routeModel",
        "callModel",
        "invokeMcp",
    ):
        assert forbidden not in js


def test_panel_javascript_renders_stages_as_text_only_chips():
    js = _panel_js()

    assert "document.createElement(\"span\")" in js
    assert "chip.textContent" in js
    assert "container.replaceChildren()" in js
    assert "run-progress-stage--" in js
    assert 'return "error"' in js
    assert 'return "warning"' in js
    assert 'return "current"' in js
    assert 'return "completed"' in js
    assert 'return "pending"' in js
    assert 'return "not-run"' in js
    assert "innerHTML" not in js


def test_panel_has_compact_local_styles_for_panel_and_stage_states():
    css = _styles()

    for selector in (
        ".run-progress-panel",
        ".run-progress-loader",
        ".run-progress-badge",
        ".run-progress-fields",
        ".run-progress-stages",
        ".run-progress-stage",
        ".run-progress-stage--completed",
        ".run-progress-stage--current",
        ".run-progress-stage--pending",
        ".run-progress-stage--warning",
        ".run-progress-stage--error",
        ".run-progress-stage--not-run",
    ):
        assert selector in css


def test_registry_marks_ux_run_3_and_close_complete_then_adds_live_plan():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["UX.RUN.3"]["status"] == "complete"
    assert by_id["UX.RUN.3"]["prerequisites"] == ["UX.RUN.2"]
    assert by_id["UX.RUN.3"]["expected_artifacts"] == []
    assert by_id["UX.RUN.CLOSE"]["status"] == "complete"
    assert by_id["UX.RUN.CLOSE"]["title"] == "Run Progress Visibility Branch Checkpoint"
    assert by_id["UX.RUN.CLOSE"]["prerequisites"] == ["UX.RUN.3"]
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
    assert by_id["UX.LIVE.6"]["status"] == "complete"
    assert by_id["UX.LIVE.6"]["prerequisites"] == ["UX.LIVE.5"]
    assert by_id["UX.LIVE.7"]["status"] == "complete"
    assert by_id["UX.LIVE.7"]["prerequisites"] == ["UX.LIVE.6"]
    assert by_id["UX.LIVE.8"]["status"] == "complete"
    assert by_id["UX.LIVE.8"]["prerequisites"] == ["UX.LIVE.7"]
    assert by_id["UX.LIVE.9"]["status"] == "complete"
    assert by_id["UX.LIVE.9"]["prerequisites"] == ["UX.LIVE.8"]
    assert by_id["UX.LIVE.10"]["status"] == "complete"
    assert by_id["UX.LIVE.10"]["prerequisites"] == ["UX.LIVE.9"]
    assert by_id["UX.LIVE.CLOSE"]["status"] == "complete"
    assert by_id["UX.LIVE.CLOSE"]["prerequisites"] == ["UX.LIVE.10"]
    assert by_id["DOGFOOD.1B"]["status"] == "proposed"

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="ux-run-3",
        created_at="2026-07-10T00:00:00+09:00",
    )
    assert report["registry_valid"] is True, report["errors"]
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
    safe_ids = [phase["phase_id"] for phase in report["safe_to_prepare"]]
    assert safe_ids[:2] == ["DOGFOOD.1B", "VERIFY.TEST.1"]

