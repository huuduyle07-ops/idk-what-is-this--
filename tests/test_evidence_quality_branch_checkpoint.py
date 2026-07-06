"""Tests for EVAL.CLOSE - Evidence Quality Branch Checkpoint.

EVAL.CLOSE is report-only. It freezes EVAL.N1-EVAL.N7 before any scoring-gate,
approval, validation, benchmark, model, or automatic evidence execution behavior
is added.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.evidence_quality_branch_checkpoint import (
    DEFAULT_OUTPUT_ROOT,
    JSON_NAME,
    MD_NAME,
    REQUIRED_EVAL_PHASE_IDS,
    REPORT_KIND,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_INCOMPLETE,
    THIS_PHASE_ID,
    build_evidence_quality_branch_checkpoint,
    render_evidence_quality_branch_checkpoint_markdown,
    write_evidence_quality_branch_checkpoint,
)
from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from scripts.create_evidence_quality_branch_checkpoint import (
    run_create_evidence_quality_branch_checkpoint,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_REGISTRY = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "evidence_quality_branch_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_evidence_quality_branch_checkpoint.py"


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


def _phase(phase_id: str, **over) -> dict:
    data = {
        "phase_id": phase_id,
        "title": f"{phase_id} title",
        "track": "EVAL" if phase_id.startswith("EVAL") else "HUMAN",
        "status": "complete",
        "summary": "Report-only phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest tests/test_x.py -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/eval/x.json"],
        "notes": ["Report-only; adds no runtime power."],
    }
    data.update(over)
    return data


def _registry(phases: list[dict] | None = None) -> dict:
    if phases is None:
        phases = [
            *[_phase(phase_id) for phase_id in REQUIRED_EVAL_PHASE_IDS],
            _phase(THIS_PHASE_ID, prerequisites=["EVAL.N7"]),
            _phase("HUMAN.N1", track="HUMAN", status="proposed", prerequisites=[THIS_PHASE_ID]),
        ]
    return {
        "schema_version": "1.0",
        "updated_at": "2026-07-06T00:00:00+00:00",
        "phases": phases,
    }


def _guardrails(**over) -> dict:
    data = {
        "report_only": True,
        "model_call_performed": False,
        "patch_apply_performed": False,
        "validation_run_performed": False,
        "benchmark_run_performed": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "docker_or_subprocess_used": False,
        "network_contacted": False,
        "database_write_performed": False,
        "auth_policy_changed": False,
        "scoring_gate_changed": False,
        "approval_or_rejection_performed": False,
        "apply_submit_blocking_performed": False,
        "evidence_report_mutated": False,
    }
    data.update(over)
    return data


def _artifact(report_kind: str, **over) -> dict:
    data = {
        "report_kind": report_kind,
        "guardrails": _guardrails(),
        "warnings": [],
        "boundaries": ["report-only"],
    }
    data.update(over)
    return data


def _evidence_quality_report(**over) -> dict:
    data = _artifact(
        "evidence_quality_report",
        evidence_quality_status="evidence_quality_ready",
        overall_evidence_quality="adequate",
        claim_inventory=[{"claim_id": "claim-1"}],
        missing_evidence=[],
        contradiction_risks=[],
        warnings=[],
    )
    data.update(over)
    return data


def _loader_readiness(**over) -> dict:
    data = _artifact(
        "evidence_quality_loader_readiness",
        readiness_status="loader_readiness_ready_with_warnings",
        summary={
            "panel_ready": True,
            "loader_ready": True,
            "compatible_report_loaded": False,
            "warning_count": 1,
            "blocked_reason_count": 0,
            "incomplete_reason_count": 0,
        },
        final_verdict={"ready_for_branch_checkpoint": True},
        warnings=["No real loaded-report demo artifact supplied; readiness remains advisory with warnings."],
        blocked_reasons=[],
        incomplete_reasons=[],
    )
    data.update(over)
    return data


def _artifacts(**over) -> dict[str, dict]:
    data = {
        "evidence_quality_plan": _artifact("evidence_quality_plan"),
        "evidence_quality_report_contract": _artifact("evidence_quality_report_contract"),
        "evidence_quality_report": _evidence_quality_report(),
        "evidence_quality_artifact_loader_plan": _artifact("evidence_quality_artifact_loader_plan"),
        "evidence_quality_loader_readiness": _loader_readiness(),
    }
    data.update(over)
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _write_fake_repo(
    root: Path,
    *,
    registry: dict | None = None,
    artifacts: dict[str, dict | None] | None = None,
    template: str = SAFE_TEMPLATE,
    app: str = SAFE_APP,
) -> Path:
    (root / "web" / "templates").mkdir(parents=True, exist_ok=True)
    (root / "web").mkdir(exist_ok=True)
    (root / "web" / "templates" / "index.html").write_text(template, encoding="utf-8")
    (root / "web" / "app.py").write_text(app, encoding="utf-8")
    _write_json(root / "docs" / "roadmap" / "phase_registry.json", registry or _registry())
    artifact_map = artifacts if artifacts is not None else _artifacts()
    paths = {
        "evidence_quality_plan": ".agent/eval/evidence_quality_plan/evidence_quality_plan.json",
        "evidence_quality_report_contract": ".agent/eval/evidence_quality_report_contract/evidence_quality_report_contract.json",
        "evidence_quality_report": ".agent/eval/evidence_quality_report/evidence_quality_report.json",
        "evidence_quality_artifact_loader_plan": ".agent/eval/evidence_quality_artifact_loader_plan/evidence_quality_artifact_loader_plan.json",
        "evidence_quality_loader_readiness": ".agent/eval/evidence_quality_loader_readiness/evidence_quality_loader_readiness.json",
    }
    for key, rel in paths.items():
        if artifact_map.get(key) is not None:
            _write_json(root / rel, artifact_map[key])
    return root


def _build(root: Path, **kwargs) -> dict:
    _write_fake_repo(root, **kwargs)
    return build_evidence_quality_branch_checkpoint(
        repo_root=root,
        registry_path="docs/roadmap/phase_registry.json",
        report_id="test-checkpoint",
        created_at="2026-07-06T00:00:00+00:00",
    )


def _reasons(report: dict) -> list[str]:
    return [str(item.get("reason", item)) for item in report.get("blocked_reasons", [])]


def test_constants_match_spec():
    assert REPORT_KIND == "evidence_quality_branch_checkpoint"
    assert THIS_PHASE_ID == "EVAL.CLOSE"
    assert REQUIRED_EVAL_PHASE_IDS == (
        "EVAL.N1",
        "EVAL.N2",
        "EVAL.N3",
        "EVAL.N4",
        "EVAL.N5",
        "EVAL.N6",
        "EVAL.N7",
    )
    assert STATUS_FROZEN == "evidence_quality_branch_frozen"
    assert STATUS_FROZEN_WITH_WARNINGS == "evidence_quality_branch_frozen_with_warnings"
    assert STATUS_INCOMPLETE == "evidence_quality_branch_incomplete"
    assert STATUS_BLOCKED == "evidence_quality_branch_blocked"
    assert DEFAULT_OUTPUT_ROOT == Path(".agent") / "eval" / "evidence_quality_branch_checkpoint"


def test_warning_ready_branch_freezes_with_warnings(tmp_path):
    report = _build(tmp_path)

    assert report["report_kind"] == REPORT_KIND
    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["summary"]["all_required_eval_phases_complete"] is True
    assert report["summary"]["required_artifacts_present"] is True
    assert report["summary"]["ui_stub_present"] is True
    assert report["summary"]["get_loader_present"] is True
    assert report["recommended_next_phase"]["phase_id"] == "HUMAN.N1"
    assert report["blocked_reasons"] == []
    assert any("loaded-report demo" in warning for warning in report["warnings"])
    assert report["guardrails"]["report_generation_performed"] is False
    assert report["human_review_boundary"]["advisory_only"] is True
    assert report["human_review_boundary"]["approval_gate"] is False


def test_ready_branch_freezes_without_warnings(tmp_path):
    artifacts = _artifacts(
        evidence_quality_loader_readiness=_loader_readiness(
            readiness_status="loader_readiness_ready",
            summary={
                "panel_ready": True,
                "loader_ready": True,
                "compatible_report_loaded": True,
                "warning_count": 0,
                "blocked_reason_count": 0,
                "incomplete_reason_count": 0,
            },
            warnings=[],
        )
    )

    report = _build(tmp_path, artifacts=artifacts)

    assert report["checkpoint_status"] == STATUS_FROZEN
    assert report["warnings"] == []
    assert report["final_verdict"]["branch_frozen"] is True


def test_missing_required_eval_phase_blocks_checkpoint(tmp_path):
    phases = [_phase("EVAL.N1"), _phase("EVAL.N2"), _phase(THIS_PHASE_ID)]

    report = _build(tmp_path, registry=_registry(phases=phases))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("EVAL.N3" in reason and "missing" in reason for reason in _reasons(report))


def test_eval_close_must_be_registered_complete(tmp_path):
    registry = _registry(
        phases=[*[_phase(phase_id) for phase_id in REQUIRED_EVAL_PHASE_IDS], _phase(THIS_PHASE_ID, status="proposed")]
    )

    report = _build(tmp_path, registry=registry)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any(
        THIS_PHASE_ID in item["message"] and "not registered complete" in item["message"]
        for item in report["blocked_reasons"]
    )


def test_missing_required_artifact_reports_incomplete(tmp_path):
    artifacts = _artifacts(evidence_quality_loader_readiness=None)

    report = _build(tmp_path, artifacts=artifacts)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("evidence_quality_loader_readiness" in reason for reason in report["incomplete_reasons"])


def test_missing_eval_n3_report_artifact_reports_incomplete(tmp_path):
    artifacts = _artifacts(evidence_quality_report=None)

    report = _build(tmp_path, artifacts=artifacts)

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert any("evidence_quality_report" in reason for reason in report["incomplete_reasons"])


def test_missing_panel_reports_incomplete(tmp_path):
    report = _build(tmp_path, template="<section>No Evidence Quality panel here</section>")

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert report["ui_loader_safety"]["ui_stub_present"] is False
    assert any("Evidence Quality panel" in reason for reason in report["incomplete_reasons"])


def test_missing_loader_reports_incomplete(tmp_path):
    report = _build(tmp_path, app="from pathlib import Path\n")

    assert report["checkpoint_status"] == STATUS_INCOMPLETE
    assert report["ui_loader_safety"]["get_loader_present"] is False
    assert any("GET-only loader" in reason for reason in report["incomplete_reasons"])


def test_mutating_loader_route_blocks(tmp_path):
    app = SAFE_APP.replace('methods=["GET"]', 'methods=["GET", "POST"]')

    report = _build(tmp_path, app=app)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert "loader_route_allows_mutating_methods" in _reasons(report)


def test_traversal_allowance_blocks(tmp_path):
    app = SAFE_APP.replace("not _is_safe_evidence_quality_report_id(report_id)", "False")
    app = app.replace("relative_to(root.resolve())", "is_relative_to(root.resolve())")

    report = _build(tmp_path, app=app)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    reasons = _reasons(report)
    assert "report_id_sanitization_missing" in reasons
    assert "path_traversal_guard_missing" in reasons


def test_eval_n3_builder_import_or_call_from_loader_blocks(tmp_path):
    app = SAFE_APP.replace(
        "# EVAL.N6 GET-only Evidence Quality artifact loader",
        "# EVAL.N6 GET-only Evidence Quality artifact loader\nfrom core import evidence_quality_report_builder",
    )

    report = _build(tmp_path, app=app)

    assert report["checkpoint_status"] == STATUS_BLOCKED
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

    report = _build(tmp_path, app=app)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert reason in _reasons(report)


@pytest.mark.parametrize("label", ["Approve", "Reject", "Apply"])
def test_approve_reject_apply_buttons_inside_panel_block(tmp_path, label):
    template = SAFE_TEMPLATE.replace(
        "</section>\n  <!-- /evidence-quality-panel -->",
        f'<button type="button">{label}</button></section>\n  <!-- /evidence-quality-panel -->',
    )

    report = _build(tmp_path, template=template)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert f"forbidden_panel_control:{label}" in _reasons(report)


@pytest.mark.parametrize("label", ["Generate Report", "Run Validation", "Run Benchmark", "Score Now"])
def test_execution_buttons_inside_panel_block(tmp_path, label):
    template = SAFE_TEMPLATE.replace(
        "</section>\n  <!-- /evidence-quality-panel -->",
        f'<button type="button">{label}</button></section>\n  <!-- /evidence-quality-panel -->',
    )

    report = _build(tmp_path, template=template)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert f"forbidden_panel_control:{label}" in _reasons(report)


def test_evidence_report_mutation_marker_blocks(tmp_path):
    app = SAFE_APP.replace("return jsonify", "path.write_text('{}')\n    return jsonify")

    report = _build(tmp_path, app=app)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert "evidence_report_mutation_hook" in _reasons(report)


def test_apply_submit_blocking_and_routing_change_markers_block(tmp_path):
    template = SAFE_TEMPLATE.replace(
        "renderEvidenceQualityPanel(body.report || body.summary);",
        "primarySubmit.disabled = true; window.location = '/blocked';",
    )

    report = _build(tmp_path, template=template)

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert "apply_submit_blocking_hook" in _reasons(report)
    assert "routing_or_mode_change_hook" in _reasons(report)


def test_markdown_contains_required_sections(tmp_path):
    md = render_evidence_quality_branch_checkpoint_markdown(_build(tmp_path))
    low = md.lower()
    for section in (
        "## summary",
        "## phase completion",
        "## artifact coverage",
        "## evidence quality capability summary",
        "## ui/loader safety verification",
        "## forbidden control checks",
        "## execution-prohibition checks",
        "## human review boundary",
        "## missing demo evidence",
        "## warnings",
        "## blocked reasons",
        "## final verdict",
        "## recommended next phase",
        "## boundaries / guardrails",
    ):
        assert section in low, section


def test_checkpoint_json_and_markdown_artifacts_are_written(tmp_path):
    _write_fake_repo(tmp_path)
    output_dir = tmp_path / "out"

    result = write_evidence_quality_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=output_dir,
        report_id="write-test",
        created_at="2026-07-06T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert Path(result["json_path"]) == output_dir / JSON_NAME
    assert Path(result["md_path"]) == output_dir / MD_NAME
    saved = json.loads((output_dir / JSON_NAME).read_text(encoding="utf-8"))
    markdown = (output_dir / MD_NAME).read_text(encoding="utf-8")
    assert saved["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert "# Evidence Quality Branch Checkpoint" in markdown
    assert "HUMAN.N1" in markdown


def test_cli_writes_summary_json(tmp_path):
    _write_fake_repo(tmp_path)
    output_dir = tmp_path / "cli-out"

    result = run_create_evidence_quality_branch_checkpoint(
        repo_root=tmp_path,
        registry_path="docs/roadmap/phase_registry.json",
        output_dir=output_dir,
        report_id="cli-test",
        created_at="2026-07-06T00:00:00+00:00",
    )

    assert result["ok"] is True
    assert result["summary"]["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert result["summary"]["recommended_next_phase"] == "HUMAN.N1"
    assert Path(result["json_path"]).exists()
    assert Path(result["md_path"]).exists()


def test_checkpoint_core_and_cli_do_not_import_or_call_execution_primitives():
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


def test_real_registry_marks_eval_close_complete_and_picker_recommends_human_n1():
    data = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["EVAL.CLOSE"]["status"] == "complete"
    assert by_id["EVAL.CLOSE"]["prerequisites"] == ["EVAL.N7"]
    assert by_id["EVAL.CLOSE"]["expected_artifacts"] == [
        ".agent/eval/evidence_quality_branch_checkpoint/evidence_quality_branch_checkpoint.json",
        ".agent/eval/evidence_quality_branch_checkpoint/evidence_quality_branch_checkpoint.md",
    ]
    assert by_id["EVAL.CLOSE"]["network_allowed"] is False
    assert by_id["EVAL.CLOSE"]["model_calls_allowed"] is False
    assert by_id["EVAL.CLOSE"]["writes_real_repo"] is False
    assert by_id["HUMAN.N1"]["status"] == "proposed"
    assert by_id["HUMAN.N1"]["prerequisites"] == ["EVAL.CLOSE"]
    assert by_id["HUMAN.N1"]["title"] == "Human Review Boundary Map"

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="eval-close-checkpoint",
        created_at="2026-07-06T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "HUMAN.N1"
