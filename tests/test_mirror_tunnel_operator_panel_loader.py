"""Tests for MIRROR.11 - Operator Panel Artifact Loader Preview.

MIRROR.11 may load an existing MIRROR.8 preview artifact into the read-only
Mirror Tunnel panel. It must not generate evidence, score traces, mutate
artifacts, or affect Submit/Apply behavior.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
WEB_APP = PROJECT_ROOT / "web" / "app.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
PREVIEW_JSON_NAME = "mirror_tunnel_live_trace_scoring_preview.json"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _web_app_source() -> str:
    return WEB_APP.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _mirror_panel(template: str | None = None) -> str:
    return _between(template or _template(), 'id="mirrorTunnelPanel"', "<!-- /mirror-tunnel-panel -->")


def _mirror_js(template: str | None = None) -> str:
    return _between(template or _template(), "// MIRROR.10 read-only operator panel", "// /MIRROR.10 read-only operator panel")


def _mirror_route_source() -> str:
    src = _web_app_source()
    return _between(src, "# MIRROR.11 read-only preview loader", "# /MIRROR.11 read-only preview loader")


def _write_preview(root: Path, preview_id: str, data: dict) -> Path:
    path = (
        root
        / ".agent"
        / "mirror_tunnel"
        / "live_trace_scoring_preview"
        / preview_id
        / PREVIEW_JSON_NAME
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _preview(status: str = "preview_with_warnings") -> dict:
    return {
        "report_kind": "mirror_tunnel_live_trace_scoring_preview",
        "preview_id": "preview-1",
        "created_at": "2026-07-02T00:00:00+09:00",
        "status": status,
        "recommended_next_action": "improve_live_trace_frame_capture",
        "recommended_next_phase": "MIRROR.9",
        "trace_id": "trace-alpha",
        "run_id": "run-alpha",
        "live_trace_input": {
            "trace_path": ".agent/mirror_tunnel/live_traces/run-alpha/mirror_tunnel_trace_contract.json",
            "trace_report_kind": "mirror_tunnel_shadow_live_trace",
            "trace_status": "live_trace_written",
            "trace_compatibility": "mirror7_live_trace",
            "live_trace_artifact_mutated": False,
        },
        "frame_coverage": {
            "available_frame_count": 5,
            "available_frame_types": ["user_intent", "patch_or_diff", "final_answer"],
            "missing_evidence_count": 1,
        },
        "derailment_score_preview": {
            "score_id": "preview-1-mirror2",
            "verdict": "minor_drift",
            "overall_derailment_score": 0.22,
            "dimension_scores": {"scope_drift": 0.2},
            "recommended_next_action": "review_minor_drift",
        },
        "claim_vs_diff_preview": {
            "check_id": "preview-1-mirror3",
            "overall_claim_support": "partially_supported",
            "mismatch_count": 1,
            "unsupported_claim_count": 0,
            "recommended_next_action": "review_claim_mismatch",
        },
        "combined_review_verdict": {
            "review_id": "preview-1-combined",
            "combined_verdict": "review_with_caution",
            "recommended_next_action": "review_live_trace_evidence",
            "warning_count": 1,
        },
        "missing_evidence": [
            {"source": "trace", "frame_type": "benchmark_evidence", "reason": "not captured"}
        ],
        "warnings": ["live trace has missing evidence frames"],
        "blockers": [],
        "artifact_paths": {
            "json": ".agent/mirror_tunnel/live_trace_scoring_preview/preview-1/mirror_tunnel_live_trace_scoring_preview.json",
            "markdown": ".agent/mirror_tunnel/live_trace_scoring_preview/preview-1/mirror_tunnel_live_trace_scoring_preview.md",
        },
        "guardrails": {
            "model_call_performed": False,
            "live_trace_artifact_mutated": False,
            "preview_generation_performed": False,
        },
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def test_preview_route_loads_existing_mirror8_json_read_only(client, tmp_path):
    path = _write_preview(tmp_path, "preview-1", _preview())
    before = path.read_text(encoding="utf-8")

    resp = client.get("/mirror-tunnel/preview/preview-1")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["status"] == "preview_with_warnings"
    assert body["preview_id"] == "preview-1"
    assert body["artifact_path"].endswith(
        ".agent/mirror_tunnel/live_trace_scoring_preview/preview-1/"
        "mirror_tunnel_live_trace_scoring_preview.json"
    )
    summary = body["summary"]
    assert summary["status"] == "preview_with_warnings"
    assert summary["trace_status"] == "live_trace_written"
    assert summary["trace_id"] == "trace-alpha"
    assert summary["run_id"] == "run-alpha"
    assert summary["derailment_verdict"] == "minor_drift"
    assert summary["derailment_score"] == 0.22
    assert summary["claim_support_verdict"] == "partially_supported"
    assert summary["missing_evidence_count"] == 1
    assert summary["top_warnings"] == ["live trace has missing evidence frames"]
    assert summary["recommended_next_action"] == "improve_live_trace_frame_capture"
    assert "preview_json" in summary["artifact_paths"]
    assert summary["raw_json"]["report_kind"] == "mirror_tunnel_live_trace_scoring_preview"
    assert path.read_text(encoding="utf-8") == before


def test_preview_route_missing_preview_returns_safe_error(client):
    resp = client.get("/mirror-tunnel/preview/does-not-exist")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "preview_not_found"
    assert body["summary"]["status"] == "preview_not_found"
    assert body["summary"]["recommended_next_action"] == "select_existing_mirror_preview"


def test_preview_route_malformed_preview_returns_safe_error(client, tmp_path):
    path = (
        tmp_path
        / ".agent"
        / "mirror_tunnel"
        / "live_trace_scoring_preview"
        / "bad-json"
        / PREVIEW_JSON_NAME
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    resp = client.get("/mirror-tunnel/preview/bad-json")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "malformed_preview"
    assert "malformed" in body["summary"]["top_warnings"][0].lower()
    assert path.read_text(encoding="utf-8") == "{not-json"


@pytest.mark.parametrize("bad_id", ["..%2Fsecret", "..%5Csecret", ".", "..", "bad id", "bad%3Fx%3D1"])
def test_preview_route_blocks_unsafe_preview_id(client, bad_id):
    resp = client.get(f"/mirror-tunnel/preview/{bad_id}")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "blocked_unsafe_preview_id"
    assert body["summary"]["status"] == "blocked_unsafe_preview_id"


def test_preview_route_is_get_only(client):
    resp = client.post("/mirror-tunnel/preview/preview-1")

    assert resp.status_code == 405


def test_mirror_panel_has_loader_controls_and_required_display_fields():
    panel = _mirror_panel()

    assert "Mirror Tunnel is advisory evidence, not an approval gate." in panel
    assert 'id="mirrorPreviewId"' in panel
    assert "Load Mirror preview" in panel
    for label in (
        "Trace status",
        "Trace ID",
        "Run ID",
        "Derailment verdict",
        "Derailment score",
        "Claim support verdict",
        "Missing evidence count",
        "Recommended next action",
    ):
        assert label in panel
    for element_id in (
        "mirrorTraceStatus",
        "mirrorTraceId",
        "mirrorRunId",
        "mirrorDerailmentVerdict",
        "mirrorDerailmentScore",
        "mirrorClaimSupportVerdict",
        "mirrorMissingEvidenceCount",
        "mirrorRecommendedNextAction",
    ):
        assert f'id="{element_id}"' in panel


def test_mirror_panel_keeps_empty_state_and_collapsed_raw_details():
    panel = _mirror_panel()

    assert "No live trace preview loaded" in panel
    assert "No preview selected" in _mirror_js()
    details_open = re.search(r"<details\b[^>]*class=\"mirror-tunnel-details\"[^>]*>", panel)
    assert details_open is not None
    assert " open" not in details_open.group(0)
    assert 'id="mirrorRawJson"' in panel
    assert "No raw Mirror JSON loaded." in panel


def test_mirror_javascript_fetches_only_get_preview_route_and_never_mutates():
    js = _mirror_js()

    assert "function loadMirrorTunnelPreview" in js
    assert "fetch(`/mirror-tunnel/preview/" in js
    assert "renderMirrorTunnelSummary" in js
    assert "setInterval" not in js
    assert "setTimeout" not in js
    assert ".disabled" not in js
    for forbidden in (
        "method: \"POST\"",
        "method: 'POST'",
        "/generate_patch",
        "/apply_patch",
        "/benchmarks/run",
        "/proposals/validate",
        "/worker-runs/import",
        "/dream/run",
        "runBenchmark",
        "runValidation",
        "Score Now",
        "scoreNow",
        "launchWorker",
        "callModel",
        "maybe_write_shadow_live_trace",
    ):
        assert forbidden not in js


def test_mirror_panel_has_no_approval_execution_or_apply_buttons_and_stays_out_of_submit_apply_area():
    template = _template()
    panel = _mirror_panel(template)
    button_labels = [
        re.sub(r"\s+", " ", label).strip()
        for label in re.findall(r"<button\b[^>]*>(.*?)</button>", panel, re.S)
    ]

    assert button_labels == [
        "Load Mirror preview",
        "Refresh Mirror summary",
        "Copy Mirror summary",
        "Copy artifact paths",
    ]
    for forbidden in (
        "Apply",
        "Reject",
        "Approve",
        "Run Validation",
        "Run Benchmark",
        "Score Now",
        "Launch Worker",
        "Generate Patch",
    ):
        assert forbidden not in panel

    evidence = _between(template, 'id="ws-evidence-cards"', "<!-- /ws-evidence-cards -->")
    assert 'id="mirrorTunnelPanel"' in evidence
    primary_submit_area = _between(template, 'id="primarySubmit"', '<details class="instant-run-controls"')
    primary_patch_actions = _between(template, 'class="actions actions--primary"', '<!-- anti-lesson-control-per-run -->')
    assert "mirrorTunnelPanel" not in primary_submit_area
    assert "mirrorTunnelPanel" not in primary_patch_actions
    assert "Apply / Review Patch" in primary_patch_actions


def test_loader_route_source_is_read_only_and_does_not_import_scoring_or_writer_builders():
    route = _mirror_route_source()

    assert '@app.route("/mirror-tunnel/preview/<path:preview_id>", methods=["GET"])' in route
    assert "request.values" not in route
    assert "request.form" not in route
    assert "repo_path" not in route
    assert ".write_text" not in route
    assert ".mkdir" not in route
    for forbidden in (
        "build_mirror_tunnel_derailment_score",
        "build_mirror_tunnel_claim_diff_check",
        "build_mirror_tunnel_live_trace_scoring_preview",
        "maybe_write_shadow_live_trace",
        "write_shadow_live_trace",
        "subprocess",
        "run_benchmarks",
        "run_safe_validation",
        "run_validation",
        "run_gemini_request",
        "run_deepseek_review",
        "invoke_mcp",
        "apply_patch",
        "generate_patch",
        "launch_worker",
    ):
        assert forbidden not in route


def test_registry_marks_mirror11_complete_and_picker_recommends_cmd_n4():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.10"]["status"] == "complete"
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
        report_id="mirror11-loader",
        created_at="2026-07-02T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "CMD.N6"
