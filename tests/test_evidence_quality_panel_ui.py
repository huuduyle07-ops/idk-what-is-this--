"""Tests for EVAL.N5 - Evidence Quality Read-only UI Stub.

The EVAL.N5 panel is an inert UI surface for an already available in-page
Evidence Quality object. It must not add artifact loading, backend routes,
report generation, validation/benchmark execution, scoring gates, approval
actions, or Apply/Submit coupling.
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


def _panel(template: str | None = None) -> str:
    return _between(template or _template(), 'id="evidenceQualityPanel"', "<!-- /evidence-quality-panel -->")


def _panel_js(template: str | None = None) -> str:
    return _between(
        template or _template(),
        "// EVAL.N5 read-only Evidence Quality panel",
        "// /EVAL.N5 read-only Evidence Quality panel",
    )


def _button_labels(html: str) -> list[str]:
    return [re.sub(r"\s+", " ", label).strip() for label in re.findall(r"<button\b[^>]*>(.*?)</button>", html, re.S)]


def test_evidence_quality_panel_exists_with_advisory_empty_state_and_visible_fields():
    panel = _panel()

    assert "<strong>Evidence Quality</strong>" in panel
    assert "Evidence Quality is advisory evidence, not an approval gate." in panel
    assert "No evidence quality report loaded." in panel
    assert 'data-evidence-quality-readonly="true"' in panel

    visible_labels = (
        "Evidence quality status",
        "Overall evidence quality",
        "Claim count",
        "Missing evidence count",
        "Contradiction risk count",
        "Confidence alignment warnings",
        "Validation evidence status",
        "Benchmark evidence status",
        "Freshness status",
        "Recommended human checks",
    )
    for label in visible_labels:
        assert label in panel

    visible_ids = (
        "evidenceQualityStatus",
        "evidenceQualityOverall",
        "evidenceQualityClaimCount",
        "evidenceQualityMissingEvidenceCount",
        "evidenceQualityContradictionRiskCount",
        "evidenceQualityConfidenceAlignmentWarnings",
        "evidenceQualityValidationEvidenceStatus",
        "evidenceQualityBenchmarkEvidenceStatus",
        "evidenceQualityFreshnessStatus",
        "evidenceQualityRecommendedHumanChecks",
    )
    for element_id in visible_ids:
        assert f'id="{element_id}"' in panel


def test_evidence_quality_details_are_collapsed_with_debug_placeholders_and_raw_json():
    panel = _panel()

    details_open = re.search(r"<details\b[^>]*class=\"evidence-quality-details\"[^>]*>", panel)
    assert details_open is not None
    assert " open" not in details_open.group(0)
    assert ">Evidence Quality details<" in panel

    debug_labels = (
        "Artifact inventory",
        "Claim inventory",
        "Evidence inventory",
        "Dimension reviews",
        "Missing evidence list",
        "Contradiction risks",
        "Freshness findings",
        "Confidence alignment findings",
        "Scope alignment findings",
        "Raw JSON",
    )
    for label in debug_labels:
        assert label in panel

    assert 'id="evidenceQualityRawJson"' in panel
    assert "No raw Evidence Quality JSON loaded." in panel


def test_evidence_quality_actions_are_read_only_and_never_approval_execution_or_apply_buttons():
    panel = _panel()
    labels = _button_labels(panel)

    assert labels == ["Refresh Evidence Quality summary", "Copy Evidence Quality summary"]
    for label in labels:
        assert all(word not in label.lower() for word in ("apply", "reject", "approve", "validation", "benchmark", "score", "generate"))

    for forbidden in (
        "Approve",
        "Reject",
        "Apply",
        "Run Validation",
        "Run Benchmark",
        "Score Now",
        "Generate Report",
        "model-call",
        "Call Model",
    ):
        assert forbidden not in panel


def test_evidence_quality_panel_lives_in_evidence_area_not_submit_or_apply_path():
    template = _template()
    evidence = _between(template, 'id="ws-evidence-cards"', "<!-- /ws-evidence-cards -->")
    assert 'id="evidenceQualityPanel"' in evidence
    assert "applyPatch()" not in evidence
    assert "generatePatch()" not in evidence

    primary_submit_area = _between(template, 'id="primarySubmit"', '<details class="instant-run-controls"')
    primary_patch_actions = _between(template, 'class="actions actions--primary"', '<!-- anti-lesson-control-per-run -->')
    assert "evidenceQualityPanel" not in primary_submit_area
    assert "evidenceQualityPanel" not in primary_patch_actions
    assert "Apply / Review Patch" in primary_patch_actions


def test_evidence_quality_javascript_renders_existing_object_only_without_fetch_post_or_routes():
    js = _panel_js()

    assert "function renderEvidenceQualityPanel" in js
    assert "window.evidenceQualityReport" in js
    assert "EVIDENCE_QUALITY_EMPTY_REPORT" in js
    assert "No evidence quality report loaded." in js
    assert "fetch(" not in js
    assert "method: \"POST\"" not in js
    assert "method: 'POST'" not in js
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert ".disabled" not in js

    for forbidden in (
        "/evidence-quality",
        "/evidence_quality",
        "/generate_patch",
        "/apply_patch",
        "/benchmarks/run",
        "/proposals/validate",
        "/worker-runs/import",
        "/dream/run",
        "applyPatch(",
        "generatePatch(",
        "runBenchmark",
        "runValidation",
        "Score Now",
        "scoreNow",
        "generateEvidenceQualityReport",
        "buildEvidenceQualityReport",
        "callModel",
        "launchWorker",
        "invokeMcp",
    ):
        assert forbidden not in js


def test_no_backend_evidence_quality_route_is_added():
    from web.app import app

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert not any("evidence-quality" in rule or "evidence_quality" in rule for rule in rules)

    route_sources = [WEB_APP.read_text(encoding="utf-8")]
    route_sources.extend(path.read_text(encoding="utf-8") for path in WEB_ROUTES.glob("*.py"))
    route_text = "\n".join(route_sources)
    assert '@app.route("/evidence-quality' not in route_text
    assert '@app.route("/evidence_quality' not in route_text


def test_evidence_quality_panel_has_local_styles():
    css = _styles()

    for selector in (
        ".evidence-quality-panel",
        ".evidence-quality-badge",
        ".evidence-quality-fields",
        ".evidence-quality-actions",
        ".evidence-quality-details",
        ".evidence-quality-raw",
    ):
        assert selector in css


def test_registry_marks_eval_n5_complete_and_picker_recommends_eval_n6():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["EVAL.N4"]["status"] == "complete"
    assert by_id["EVAL.N5"]["status"] == "complete"
    assert by_id["EVAL.N5"]["prerequisites"] == ["EVAL.N4"]
    assert by_id["EVAL.N6"]["status"] == "proposed"
    assert by_id["EVAL.N6"]["title"] == "Evidence Quality GET-only Artifact Loader"
    assert by_id["EVAL.N6"]["prerequisites"] == ["EVAL.N5"]

    assert by_id["EVAL.N5"]["network_allowed"] is False
    assert by_id["EVAL.N5"]["model_calls_allowed"] is False
    assert by_id["EVAL.N5"]["writes_real_repo"] is False
    assert by_id["EVAL.N5"]["requires_sandbox"] is False
    assert by_id["EVAL.N5"]["expected_artifacts"] == []

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="eval-n5-ui",
        created_at="2026-07-06T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "EVAL.N6"
