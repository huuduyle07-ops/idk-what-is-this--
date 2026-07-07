"""Tests for EVAL.N7 - Evidence Quality Loader Readiness Check.

EVAL.N7 is report-only. It inspects the EVAL.N5 panel, EVAL.N6 GET-only
loader, and optional existing EVAL.N3 report artifacts. It must not generate
evidence quality reports, run validation or benchmarks, call models, apply
patches, approve/reject anything, mutate reports, or alter Submit/Apply.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.evidence_quality_loader_readiness import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    build_evidence_quality_loader_readiness,
    write_evidence_quality_loader_readiness,
)
from scripts.create_evidence_quality_loader_readiness import (
    run_create_evidence_quality_loader_readiness,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "evidence_quality_loader_readiness.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_evidence_quality_loader_readiness.py"


SAFE_TEMPLATE = """
<section id="ws-evidence-cards">
  <section id="evidenceQualityPanel" data-evidence-quality-readonly="true">
    <strong>Evidence Quality</strong>
    <p>Evidence Quality is advisory evidence, not an approval gate.</p>
    <div id="evidenceQualityEmptyState">No evidence quality report loaded.</div>
    <dl>
      <dt>Evidence quality status</dt>
      <dt>Overall evidence quality</dt>
      <dt>Claim count</dt>
      <dt>Missing evidence count</dt>
      <dt>Contradiction risk count</dt>
      <dt>Confidence alignment warnings</dt>
      <dt>Validation evidence status</dt>
      <dt>Benchmark evidence status</dt>
      <dt>Freshness status</dt>
      <dt>Recommended human checks</dt>
    </dl>
    <button type="button" onclick="loadEvidenceQualityReport()">Load Evidence Quality report</button>
    <button type="button" onclick="renderEvidenceQualityPanel()">Refresh Evidence Quality summary</button>
    <button type="button" onclick="copyEvidenceQualitySummary()">Copy Evidence Quality summary</button>
    <details class="evidence-quality-details">
      <summary>Evidence Quality details</summary>
      <pre id="evidenceQualityRawJson">No raw Evidence Quality JSON loaded.</pre>
    </details>
  </section>
  <!-- /evidence-quality-panel -->
  <script>
  // EVAL.N5/EVAL.N6 read-only Evidence Quality panel
  async function loadEvidenceQualityReport() {
    const encodedReportId = encodeURIComponent(reportId);
    const response = await fetch(`/eval/evidence-quality/report/${encodedReportId}`);
    renderEvidenceQualityPanel(body.report || body.summary);
  }
  // /EVAL.N5/EVAL.N6 read-only Evidence Quality panel
  </script>
  <!-- /ws-evidence-cards -->
</section>
<section id="primarySubmit">Submit</section>
<section class="actions actions--primary">Apply / Review Patch</section>
"""

SAFE_APP = '''
from pathlib import Path
import json
import re

_EVIDENCE_QUALITY_REPORT_SUBDIR = Path(".agent") / "eval" / "evidence_quality_report"
_EVIDENCE_QUALITY_REPORT_JSON = "evidence_quality_report.json"
_EVIDENCE_QUALITY_REPORT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

# EVAL.N6 GET-only Evidence Quality artifact loader
@app.route("/eval/evidence-quality/report/<path:report_id>", methods=["GET"])
def evidence_quality_report_route(report_id: str):
    root = PROJECT_ROOT / _EVIDENCE_QUALITY_REPORT_SUBDIR
    if not _is_safe_evidence_quality_report_id(report_id):
        return _evidence_quality_report_error("blocked_unsafe_report_id", "Blocked unsafe Evidence Quality report id.", 400)
    path = root / _EVIDENCE_QUALITY_REPORT_JSON if report_id == "default" else root / report_id / _EVIDENCE_QUALITY_REPORT_JSON
    if not path.resolve().relative_to(root.resolve()):
        raise ValueError("unreachable")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _evidence_quality_report_error("report_not_found", "Select an existing Evidence Quality report.", 404)
    except json.JSONDecodeError:
        return _evidence_quality_report_error("malformed_report", "Malformed Evidence Quality report JSON.", 400)
    if data.get("report_kind") != "evidence_quality_report":
        return _evidence_quality_report_error("malformed_report", "Malformed Evidence Quality report JSON.", 400)
    return jsonify({"ok": True, "report": data})
# /EVAL.N6 GET-only Evidence Quality artifact loader
'''


def _write_fake_repo(root: Path, *, template: str = SAFE_TEMPLATE, app: str = SAFE_APP) -> Path:
    template_path = root / "web" / "templates" / "index.html"
    app_path = root / "web" / "app.py"
    template_path.parent.mkdir(parents=True, exist_ok=True)
    app_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(template, encoding="utf-8")
    app_path.write_text(app, encoding="utf-8")
    return root


def _compatible_report(path: Path, *, status: str = "evidence_quality_ready") -> Path:
    data = {
        "report_kind": "evidence_quality_report",
        "report_id": "evidence-quality-report",
        "evidence_quality_status": status,
        "overall_evidence_quality": "adequate",
        "artifact_inventory": [{"artifact_key": "validation", "read_status": "present"}],
        "claim_inventory": [{"claim_id": "claim-1"}],
        "evidence_inventory": [{"artifact_key": "validation", "evidence_status": "present"}],
        "dimension_reviews": [{"dimension_id": "validation_relevance", "verdict": "supported"}],
        "missing_evidence": [],
        "contradiction_risks": [],
        "freshness_findings": [{"freshness_status": "recent"}],
        "confidence_alignment_findings": [],
        "scope_alignment_findings": [],
        "recommended_human_checks": ["Review evidence manually before apply."],
        "guardrails": {
            "model_call_performed": False,
            "validation_run_performed": False,
            "benchmark_run_performed": False,
            "patch_apply_performed": False,
            "evidence_report_mutated": False,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _statuses(report: dict) -> dict[str, str]:
    return {check["check_id"]: check["status"] for check in report["source_checks"]}


def _reasons(report: dict) -> list[str]:
    return [str(item.get("reason", "")) for item in report.get("blocked_reasons", [])]


def test_safe_eval_n5_n6_setup_produces_ready_with_warnings_without_demo_report(tmp_path):
    repo = _write_fake_repo(tmp_path)

    report = build_evidence_quality_loader_readiness(repo_root=repo, created_at="2026-07-06T00:00:00+09:00")

    assert report["report_kind"] == "evidence_quality_loader_readiness"
    assert report["readiness_status"] == "loader_readiness_ready_with_warnings"
    assert report["summary"]["panel_ready"] is True
    assert report["summary"]["loader_ready"] is True
    assert report["summary"]["compatible_report_loaded"] is False
    assert report["recommended_next_phase"]["phase_id"] == "EVAL.CLOSE"
    assert report["guardrails"]["report_generation_performed"] is False
    assert any("No real loaded-report demo artifact" in warning for warning in report["warnings"])


def test_compatible_eval_n3_report_improves_readiness_to_ready(tmp_path):
    repo = _write_fake_repo(tmp_path)
    report_path = _compatible_report(repo / ".agent" / "eval" / "evidence_quality_report" / "evidence_quality_report.json")

    report = build_evidence_quality_loader_readiness(
        repo_root=repo,
        report_path=report_path,
        created_at="2026-07-06T00:00:00+09:00",
    )

    assert report["readiness_status"] == "loader_readiness_ready"
    assert report["artifact_compatibility"]["compatible"] is True
    assert report["artifact_compatibility"]["report_kind"] == "evidence_quality_report"
    assert report["artifact_compatibility"]["overall_evidence_quality"] == "adequate"
    assert report["warnings"] == []


def test_missing_panel_reports_incomplete(tmp_path):
    repo = _write_fake_repo(tmp_path, template="<section>No panel here</section>")

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_incomplete"
    assert _statuses(report)["panel_exists"] == "missing"
    assert "Evidence Quality panel missing" in report["incomplete_reasons"]


def test_missing_loader_reports_incomplete(tmp_path):
    repo = _write_fake_repo(tmp_path, app="from pathlib import Path\n")

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_incomplete"
    assert _statuses(report)["loader_route_exists"] == "missing"
    assert "EVAL.N6 GET-only loader route missing" in report["incomplete_reasons"]


def test_mutating_loader_route_blocks(tmp_path):
    app = SAFE_APP.replace('methods=["GET"]', 'methods=["GET", "POST"]')
    repo = _write_fake_repo(tmp_path, app=app)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    assert "loader_route_allows_mutating_methods" in _reasons(report)


def test_traversal_allowance_blocks(tmp_path):
    app = SAFE_APP.replace("not _is_safe_evidence_quality_report_id(report_id)", "False")
    app = app.replace('relative_to(root.resolve())', 'is_relative_to(root.resolve())')
    repo = _write_fake_repo(tmp_path, app=app)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    reasons = _reasons(report)
    assert "report_id_sanitization_missing" in reasons
    assert "path_traversal_guard_missing" in reasons


def test_eval_n3_builder_import_or_call_from_loader_blocks(tmp_path):
    app = SAFE_APP.replace(
        "# EVAL.N6 GET-only Evidence Quality artifact loader",
        "# EVAL.N6 GET-only Evidence Quality artifact loader\nfrom core import evidence_quality_report_builder",
    )
    repo = _write_fake_repo(tmp_path, app=app)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    assert "evidence_quality_report_generation_hook" in _reasons(report)


@pytest.mark.parametrize(
    "marker,reason",
    [
        ("run_validation()", "validation_execution_hook"),
        ("run_benchmarks()", "benchmark_execution_hook"),
        ("run_gemini_request()", "model_call_hook"),
    ],
)
def test_validation_benchmark_or_model_execution_marker_blocks(tmp_path, marker, reason):
    app = SAFE_APP.replace("return jsonify", f"{marker}\n    return jsonify")
    repo = _write_fake_repo(tmp_path, app=app)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    assert reason in _reasons(report)


@pytest.mark.parametrize("label", ["Approve", "Reject", "Apply"])
def test_apply_reject_approve_buttons_inside_panel_block(tmp_path, label):
    template = SAFE_TEMPLATE.replace(
        "</section>\n  <!-- /evidence-quality-panel -->",
        f'<button type="button">{label}</button></section>\n  <!-- /evidence-quality-panel -->',
    )
    repo = _write_fake_repo(tmp_path, template=template)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    assert f"forbidden_panel_control:{label}" in _reasons(report)


@pytest.mark.parametrize("label", ["Generate Report", "Run Validation", "Run Benchmark", "Score Now"])
def test_generate_validate_benchmark_score_controls_inside_panel_block(tmp_path, label):
    template = SAFE_TEMPLATE.replace(
        "</section>\n  <!-- /evidence-quality-panel -->",
        f'<button type="button">{label}</button></section>\n  <!-- /evidence-quality-panel -->',
    )
    repo = _write_fake_repo(tmp_path, template=template)

    report = build_evidence_quality_loader_readiness(repo_root=repo)

    assert report["readiness_status"] == "loader_readiness_blocked"
    assert f"forbidden_panel_control:{label}" in _reasons(report)


def test_missing_report_produces_safe_warning(tmp_path):
    repo = _write_fake_repo(tmp_path)
    missing = repo / ".agent" / "eval" / "evidence_quality_report" / "missing.json"

    report = build_evidence_quality_loader_readiness(repo_root=repo, report_path=missing)

    assert report["readiness_status"] == "loader_readiness_ready_with_warnings"
    assert report["artifact_compatibility"]["compatible"] is False
    assert any("could not be read" in warning for warning in report["warnings"])


def test_malformed_report_produces_safe_warning(tmp_path):
    repo = _write_fake_repo(tmp_path)
    report_path = repo / ".agent" / "eval" / "evidence_quality_report" / "evidence_quality_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{not-json", encoding="utf-8")

    report = build_evidence_quality_loader_readiness(repo_root=repo, report_path=report_path)

    assert report["readiness_status"] == "loader_readiness_ready_with_warnings"
    assert report["artifact_compatibility"]["compatible"] is False
    assert any("malformed" in warning.lower() for warning in report["warnings"])


def test_readiness_json_and_markdown_artifacts_are_written(tmp_path):
    repo = _write_fake_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = write_evidence_quality_loader_readiness(repo_root=repo, output_dir=output_dir, created_at="2026-07-06T00:00:00+09:00")

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["readiness_status"] == "loader_readiness_ready_with_warnings"
    assert "# Evidence Quality Loader Readiness Check" in markdown
    assert "## Final Verdict" in markdown
    assert "EVAL.CLOSE" in markdown


def test_cli_writes_summary_json(tmp_path):
    repo = _write_fake_repo(tmp_path)
    output_dir = tmp_path / "cli-out"

    result = run_create_evidence_quality_loader_readiness(
        repo_root=repo,
        output_dir=output_dir,
        created_at="2026-07-06T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["summary"]["readiness_status"] == "loader_readiness_ready_with_warnings"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()
    assert Path(result["json_path"]).parent == output_dir


def test_default_output_root_is_readiness_artifact_directory():
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "eval" / "evidence_quality_loader_readiness"


def test_readiness_checker_and_cli_do_not_import_or_call_execution_primitives():
    for path in (CORE_PATH, SCRIPT_PATH):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: set[str] = set()
        calls: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)

        assert imports.isdisjoint({"subprocess", "socket", "requests", "httpx", "urllib", "openai", "anthropic"})
        assert calls.isdisjoint(
            {
                "run_validation",
                "run_safe_validation",
                "run_benchmarks",
                "run_gemini_request",
                "run_deepseek_review",
                "apply_patch",
                "build_evidence_quality_report",
                "write_evidence_quality_report",
                "launch_worker",
                "invoke_mcp",
            }
        )


def test_registry_keeps_eval_readiness_and_human_history_valid():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["EVAL.N7"]["status"] == "complete"
    assert by_id["EVAL.N7"]["prerequisites"] == ["EVAL.N6"]
    assert by_id["EVAL.N7"]["expected_artifacts"] == [
        ".agent/eval/evidence_quality_loader_readiness/evidence_quality_loader_readiness.json",
        ".agent/eval/evidence_quality_loader_readiness/evidence_quality_loader_readiness.md",
    ]
    assert by_id["EVAL.N7"]["network_allowed"] is False
    assert by_id["EVAL.N7"]["model_calls_allowed"] is False
    assert by_id["EVAL.N7"]["writes_real_repo"] is False
    assert by_id["EVAL.CLOSE"]["status"] == "complete"
    assert by_id["EVAL.CLOSE"]["prerequisites"] == ["EVAL.N7"]
    assert by_id["EVAL.CLOSE"]["title"] == "Evidence Quality Branch Checkpoint"
    assert by_id["HUMAN.N1"]["status"] == "complete"
    assert by_id["HUMAN.N1"]["prerequisites"] == ["EVAL.CLOSE"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="eval-n7-readiness",
        created_at="2026-07-06T00:00:00+09:00",
    )
    assert report["registry_valid"] is True
