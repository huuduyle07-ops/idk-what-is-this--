"""Tests for MIRROR.10 - Operator Panel Read-only UI Stub.

The MIRROR.10 panel is a read-only operator surface for already available
MIRROR.7/MIRROR.8/MIRROR.9 evidence. Later Mirror phases may add GET-only
artifact loading, but the panel must not add execution, scoring, approval, or
blocking behavior.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
WEB_APP = PROJECT_ROOT / "web" / "app.py"
WEB_ROUTES = PROJECT_ROOT / "web" / "routes"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _mirror_panel(template: str | None = None) -> str:
    return _between(template or _template(), 'id="mirrorTunnelPanel"', "<!-- /mirror-tunnel-panel -->")


def _mirror_js(template: str | None = None) -> str:
    return _between(template or _template(), "// MIRROR.10 read-only operator panel", "// /MIRROR.10 read-only operator panel")


def _mirror_route_source() -> str:
    src = WEB_APP.read_text(encoding="utf-8")
    return _between(src, "# MIRROR.11 read-only preview loader", "# /MIRROR.11 read-only preview loader")


def _button_labels(html: str) -> list[str]:
    return [re.sub(r"\s+", " ", label).strip() for label in re.findall(r"<button\b[^>]*>(.*?)</button>", html, re.S)]


def test_mirror_panel_exists_with_required_read_only_empty_state():
    panel = _mirror_panel()

    assert "<strong>Mirror Tunnel</strong>" in panel
    assert "Mirror Tunnel is advisory evidence, not an approval gate." in panel
    assert "No live trace preview loaded" in panel
    for label in (
        "Trace status",
        "Derailment verdict",
        "Claim support verdict",
        "Missing evidence count",
        "Recommended next action",
    ):
        assert label in panel
    for element_id in (
        "mirrorTraceStatus",
        "mirrorDerailmentVerdict",
        "mirrorClaimSupportVerdict",
        "mirrorMissingEvidenceCount",
        "mirrorRecommendedNextAction",
    ):
        assert f'id="{element_id}"' in panel


def test_mirror_panel_actions_are_read_only_and_never_approval_or_execution_buttons():
    panel = _mirror_panel()
    labels = _button_labels(panel)

    assert labels == ["Load Mirror preview", "Refresh Mirror summary", "Copy Mirror summary", "Copy artifact paths"]
    for label in labels:
        assert all(word not in label.lower() for word in ("apply", "reject", "approve", "run"))

    forbidden = (
        "Apply",
        "Reject",
        "Approve",
        "Run Validation",
        "Run Benchmark",
        "Launch Worker",
        "Generate Patch",
        "score now",
        "score-now",
    )
    for token in forbidden:
        assert token not in panel


def test_mirror_panel_lives_in_evidence_cards_not_primary_submit_or_apply_area():
    template = _template()
    evidence = _between(template, 'id="ws-evidence-cards"', "<!-- /ws-evidence-cards -->")
    assert 'id="mirrorTunnelPanel"' in evidence
    assert "applyPatch()" not in evidence
    assert "generatePatch()" not in evidence

    primary_submit_area = _between(template, 'id="primarySubmit"', '<details class="instant-run-controls"')
    assert "mirrorTunnelPanel" not in primary_submit_area

    primary_patch_actions = _between(template, 'class="actions actions--primary"', '<!-- anti-lesson-control-per-run -->')
    assert "mirrorTunnelPanel" not in primary_patch_actions
    assert "Apply / Review Patch" in primary_patch_actions


def test_mirror_details_are_collapsed_and_include_raw_json_placeholder():
    panel = _mirror_panel()

    details_open = re.search(r"<details\b[^>]*class=\"mirror-tunnel-details\"[^>]*>", panel)
    assert details_open is not None
    assert " open" not in details_open.group(0)
    for label in ("Frame coverage", "Top warnings", "Artifact paths", "Raw JSON"):
        assert label in panel
    assert 'id="mirrorRawJson"' in panel
    assert "No raw Mirror JSON loaded." in panel


def test_mirror_javascript_renders_only_existing_data_without_mutating_fetches():
    js = _mirror_js()

    assert "function renderMirrorTunnelSummary" in js
    assert "function loadMirrorTunnelPreview" in js
    assert "window.mirrorTunnelSummary" in js
    assert "MIRROR_TUNNEL_EMPTY_SUMMARY" in js
    assert "fetch(`/mirror-tunnel/preview/" in js
    for forbidden in (
        "method: \"POST\"",
        "method: 'POST'",
        "/generate_patch",
        "/apply_patch",
        "/benchmarks/run",
        "applyPatch(",
        "generatePatch(",
        "runAllBenchmarks(",
        "runBenchmark",
        "runValidation",
        "launchWorker",
        "callModel",
        "maybe_write_shadow_live_trace",
    ):
        assert forbidden not in js


def test_mirror_backend_route_is_get_only_and_read_only_after_loader_phase():
    route_sources = [WEB_APP.read_text(encoding="utf-8")]
    route_sources.extend(path.read_text(encoding="utf-8") for path in WEB_ROUTES.glob("*.py"))
    web_route_text = "\n".join(route_sources)
    route = _mirror_route_source()

    assert '@app.route("/mirror-tunnel/preview/<path:preview_id>", methods=["GET"])' in route
    assert "methods=[\"POST\"]" not in route
    assert ".write_text" not in route
    assert ".mkdir" not in route
    assert "mirror-tunnel" in web_route_text


def test_mirror_panel_has_local_styles():
    styles = _styles()

    for selector in (
        ".mirror-tunnel-panel",
        ".mirror-tunnel-badge",
        ".mirror-tunnel-loader",
        ".mirror-tunnel-fields",
        ".mirror-tunnel-details",
        ".mirror-tunnel-raw",
    ):
        assert selector in styles


def test_registry_marks_mirror10_complete_and_picker_recommends_cmd_n4():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.9"]["status"] == "complete"
    assert by_id["MIRROR.10"]["status"] == "complete"
    assert by_id["MIRROR.10"]["prerequisites"] == ["MIRROR.9"]
    assert by_id["MIRROR.11"]["status"] == "complete"
    assert by_id["MIRROR.11"]["prerequisites"] == ["MIRROR.10"]
    assert by_id["MIRROR.12"]["status"] == "complete"
    assert by_id["MIRROR.12"]["prerequisites"] == ["MIRROR.11"]
    assert by_id["MIRROR.CLOSE3"]["status"] == "complete"
    assert by_id["MIRROR.CLOSE3"]["prerequisites"] == ["MIRROR.12"]
    assert by_id["MIRROR.13"]["status"] == "proposed"
    assert by_id["MIRROR.13"]["prerequisites"] == ["MIRROR.CLOSE3"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="mirror10-ui",
        created_at="2026-07-02T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "CMD.CLOSE"
