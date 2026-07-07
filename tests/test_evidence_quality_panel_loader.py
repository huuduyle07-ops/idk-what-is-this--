"""Tests for EVAL.N6 - Evidence Quality GET-only Artifact Loader.

EVAL.N6 may load an existing EVAL.N3 Evidence Quality report into the
read-only EVAL.N5 panel. It must not generate reports, run validation or
benchmarks, call models, mutate evidence artifacts, or affect Submit/Apply.
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
REPORT_JSON_NAME = "evidence_quality_report.json"


def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _web_app_source() -> str:
    return WEB_APP.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _panel(template: str | None = None) -> str:
    return _between(template or _template(), 'id="evidenceQualityPanel"', "<!-- /evidence-quality-panel -->")


def _panel_js(template: str | None = None) -> str:
    return _between(
        template or _template(),
        "// EVAL.N5/EVAL.N6 read-only Evidence Quality panel",
        "// /EVAL.N5/EVAL.N6 read-only Evidence Quality panel",
    )


def _loader_route_source() -> str:
    return _between(
        _web_app_source(),
        "# EVAL.N6 GET-only Evidence Quality artifact loader",
        "# /EVAL.N6 GET-only Evidence Quality artifact loader",
    )


def _write_report(root: Path, report_id: str | None, data: dict) -> Path:
    base = root / ".agent" / "eval" / "evidence_quality_report"
    path = base / REPORT_JSON_NAME if report_id is None else base / report_id / REPORT_JSON_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _report(status: str = "evidence_quality_ready_with_warnings") -> dict:
    return {
        "report_kind": "evidence_quality_report",
        "report_id": "evidence-quality-report",
        "created_at": "2026-07-06T00:00:00+09:00",
        "evidence_quality_status": status,
        "overall_evidence_quality": "partial",
        "source_artifacts": [
            {"artifact_key": "final_answer", "path": "answer.txt", "read_status": "present"}
        ],
        "artifact_inventory": [
            {"artifact_key": "validation", "read_status": "present"},
            {"artifact_key": "benchmark", "read_status": "not_supplied"},
        ],
        "claim_inventory": [
            {"claim_id": "claim-1", "claim_type": "tests_passed"},
            {"claim_id": "claim-2", "claim_type": "ready"},
        ],
        "evidence_inventory": [
            {"artifact_key": "validation", "evidence_status": "present"},
            {"artifact_key": "benchmark", "evidence_status": "not_supplied"},
        ],
        "dimension_reviews": [
            {"dimension_id": "validation_relevance", "verdict": "supported"}
        ],
        "missing_evidence": [
            {"missing_id": "missing_benchmark_evidence", "reason": "No benchmark artifact supplied."}
        ],
        "contradiction_risks": [
            {"risk_id": "risk-1", "risk": "final answer mentions benchmarks without evidence"}
        ],
        "freshness_findings": [
            {"finding_id": "freshness-1", "freshness_status": "recent"}
        ],
        "confidence_alignment_findings": [
            {"finding_id": "confidence-1", "severity": "medium"}
        ],
        "scope_alignment_findings": [
            {"finding_id": "scope-1", "verdict": "aligned"}
        ],
        "recommended_human_checks": ["Review missing benchmark evidence."],
        "human_review_boundary": {"advisory_only": True, "approved": False},
        "guardrails": {
            "model_call_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
            "patch_apply_performed": False,
            "report_mutated": False,
        },
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(web_app, "PROJECT_ROOT", tmp_path)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as test_client:
        yield test_client


def test_get_route_loads_default_existing_evidence_quality_report_read_only(client, tmp_path):
    path = _write_report(tmp_path, None, _report())
    before = path.read_text(encoding="utf-8")

    resp = client.get("/eval/evidence-quality/report/default")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["status"] == "evidence_quality_ready_with_warnings"
    assert body["report_id"] == "default"
    assert body["artifact_path"].endswith(".agent/eval/evidence_quality_report/evidence_quality_report.json")
    assert body["report"]["report_kind"] == "evidence_quality_report"
    summary = body["summary"]
    assert summary["evidence_quality_status"] == "evidence_quality_ready_with_warnings"
    assert summary["overall_evidence_quality"] == "partial"
    assert summary["claim_count"] == 2
    assert summary["missing_evidence_count"] == 1
    assert summary["contradiction_risk_count"] == 1
    assert summary["confidence_alignment_warnings"] == 1
    assert summary["validation_evidence_status"] == "present"
    assert summary["benchmark_evidence_status"] == "not_supplied"
    assert summary["freshness_status"] == "recent"
    assert summary["recommended_human_checks"] == ["Review missing benchmark evidence."]
    assert summary["raw_json"]["report_kind"] == "evidence_quality_report"
    assert path.read_text(encoding="utf-8") == before


def test_get_route_loads_report_id_existing_evidence_quality_report_read_only(client, tmp_path):
    path = _write_report(tmp_path, "run-20260706", _report(status="evidence_quality_ready"))

    resp = client.get("/eval/evidence-quality/report/run-20260706")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["status"] == "evidence_quality_ready"
    assert body["report_id"] == "run-20260706"
    assert body["artifact_path"].endswith(
        ".agent/eval/evidence_quality_report/run-20260706/evidence_quality_report.json"
    )
    assert path.read_text(encoding="utf-8").strip().startswith("{")


def test_get_route_missing_report_returns_safe_error(client):
    resp = client.get("/eval/evidence-quality/report/missing-report")

    assert resp.status_code == 404
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "report_not_found"
    assert body["summary"]["evidence_quality_status"] == "report_not_found"
    assert body["summary"]["recommended_human_checks"] == ["Select an existing Evidence Quality report."]


def test_get_route_malformed_report_returns_safe_error(client, tmp_path):
    path = tmp_path / ".agent" / "eval" / "evidence_quality_report" / "bad-json" / REPORT_JSON_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    resp = client.get("/eval/evidence-quality/report/bad-json")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "malformed_report"
    assert "malformed" in body["summary"]["recommended_human_checks"][0].lower()
    assert path.read_text(encoding="utf-8") == "{not-json"


@pytest.mark.parametrize(
    "bad_id",
    ["..%2Fsecret", "..%5Csecret", ".", "..", "bad id", "C:%5Csecret", "bad%3Fx%3D1", "bad%2Fid"],
)
def test_get_route_blocks_unsafe_report_id(client, bad_id):
    resp = client.get(f"/eval/evidence-quality/report/{bad_id}")

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert body["status"] == "blocked_unsafe_report_id"
    assert body["summary"]["evidence_quality_status"] == "blocked_unsafe_report_id"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_loader_route_is_get_only(client, method):
    resp = getattr(client, method)("/eval/evidence-quality/report/default")

    assert resp.status_code == 405


def test_panel_has_get_loader_controls_and_preserves_read_only_display():
    panel = _panel()

    assert "Evidence Quality is advisory evidence, not an approval gate." in panel
    assert 'id="evidenceQualityReportId"' in panel
    assert 'value="default"' in panel
    assert "Load Evidence Quality report" in panel
    assert 'id="evidenceQualityLoadStatus"' in panel
    assert "No evidence quality report loaded." in panel

    for label in (
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
    ):
        assert label in panel


def test_panel_keeps_collapsed_raw_details_and_forbidden_buttons_out_of_panel():
    panel = _panel()
    details_open = re.search(r"<details\b[^>]*class=\"evidence-quality-details\"[^>]*>", panel)

    assert details_open is not None
    assert " open" not in details_open.group(0)
    assert 'id="evidenceQualityRawJson"' in panel

    button_labels = [
        re.sub(r"\s+", " ", label).strip()
        for label in re.findall(r"<button\b[^>]*>(.*?)</button>", panel, re.S)
    ]
    assert button_labels == [
        "Load Evidence Quality report",
        "Refresh Evidence Quality summary",
        "Copy Evidence Quality summary",
    ]
    for forbidden in (
        "Approve",
        "Reject",
        "Apply",
        "Run Validation",
        "Run Benchmark",
        "Score Now",
        "Generate Report",
        "Call Model",
    ):
        assert forbidden not in panel


def test_panel_javascript_fetches_only_get_report_route_and_never_mutates():
    js = _panel_js()

    assert "function loadEvidenceQualityReport" in js
    assert "encodeURIComponent(reportId)" in js
    assert "fetch(`/eval/evidence-quality/report/${encodedReportId}`)" in js
    assert "renderEvidenceQualityPanel(body.report || body.summary" in js
    assert "No report selected." in js
    assert "report_not_found" in js
    assert "malformed_report" in js
    assert "blocked_unsafe_report_id" in js
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
        "generateEvidenceQualityReport",
        "buildEvidenceQualityReport",
        "callModel",
        "launchWorker",
        "invokeMcp",
    ):
        assert forbidden not in js


def test_panel_stays_inside_evidence_area_not_submit_or_apply_path():
    template = _template()
    evidence = _between(template, 'id="ws-evidence-cards"', "<!-- /ws-evidence-cards -->")
    primary_submit_area = _between(template, 'id="primarySubmit"', '<details class="instant-run-controls"')
    primary_patch_actions = _between(template, 'class="actions actions--primary"', '<!-- anti-lesson-control-per-run -->')

    assert 'id="evidenceQualityPanel"' in evidence
    assert "evidenceQualityPanel" not in primary_submit_area
    assert "evidenceQualityPanel" not in primary_patch_actions
    assert "Apply / Review Patch" in primary_patch_actions


def test_loader_route_source_is_read_only_and_does_not_generate_or_execute():
    route = _loader_route_source()

    assert '@app.route("/eval/evidence-quality/report/<path:report_id>", methods=["GET"])' in route
    assert "request.values" not in route
    assert "request.form" not in route
    assert "repo_path" not in route
    assert ".write_text" not in route
    assert ".mkdir" not in route
    for forbidden in (
        "evidence_quality_report_builder",
        "create_evidence_quality_report",
        "build_evidence_quality_report",
        "run_benchmarks",
        "run_safe_validation",
        "run_validation",
        "run_gemini_request",
        "run_deepseek_review",
        "subprocess",
        "invoke_mcp",
        "apply_patch",
        "generate_patch",
        "launch_worker",
        "database",
        "requests.",
        "urllib",
    ):
        assert forbidden not in route


def test_registry_keeps_eval_panel_loader_branch_history_valid():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["EVAL.N5"]["status"] == "complete"
    assert by_id["EVAL.N6"]["status"] == "complete"
    assert by_id["EVAL.N6"]["prerequisites"] == ["EVAL.N5"]
    assert by_id["EVAL.N7"]["status"] == "complete"
    assert by_id["EVAL.N7"]["title"] == "Evidence Quality Loader Readiness Check"
    assert by_id["EVAL.N7"]["prerequisites"] == ["EVAL.N6"]
    assert by_id["EVAL.CLOSE"]["status"] == "complete"
    assert by_id["EVAL.CLOSE"]["prerequisites"] == ["EVAL.N7"]
    assert by_id["HUMAN.N1"]["status"] == "complete"
    assert by_id["HUMAN.N1"]["prerequisites"] == ["EVAL.CLOSE"]
    assert by_id["EVAL.N6"]["network_allowed"] is False
    assert by_id["EVAL.N6"]["model_calls_allowed"] is False
    assert by_id["EVAL.N6"]["writes_real_repo"] is False
    assert by_id["EVAL.N6"]["expected_artifacts"] == []

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="eval-n6-loader",
        created_at="2026-07-06T00:00:00+09:00",
    )
    assert report["registry_valid"] is True
