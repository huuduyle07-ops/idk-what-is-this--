"""Tests for MIRROR.CLOSE3 - Mirror Tunnel Live UI Readiness Checkpoint.

MIRROR.CLOSE3 freezes the MIRROR.7-MIRROR.12 live/UI chain before any capture
quality expansion. It is report-only: it reads registry/source/artifact evidence
and writes checkpoint artifacts only.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.mirror_tunnel_live_ui_readiness_checkpoint import (
    JSON_NAME,
    MD_NAME,
    RECOMMENDED_NEXT_PHASE,
    REPORT_KIND,
    REQUIRED_MIRROR_LIVE_UI_PHASE_IDS,
    STATUS_BLOCKED,
    STATUS_FROZEN,
    STATUS_FROZEN_WITH_WARNINGS,
    STATUS_NEEDS_LIVE_DEMO_EVIDENCE,
    build_mirror_tunnel_live_ui_readiness_checkpoint,
    render_mirror_tunnel_live_ui_readiness_checkpoint_markdown,
    write_mirror_tunnel_live_ui_readiness_checkpoint,
)
import scripts.create_mirror_tunnel_live_ui_readiness_checkpoint as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
CORE_PATH = PROJECT_ROOT / "core" / "mirror_tunnel_live_ui_readiness_checkpoint.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_mirror_tunnel_live_ui_readiness_checkpoint.py"


def _phase(pid: str, *, status: str = "complete", **overrides) -> dict:
    data = {
        "phase_id": pid,
        "title": f"{pid} title",
        "track": "MIRROR",
        "status": status,
        "summary": "Report-only Mirror phase.",
        "automation_level": "LOCAL_0_OBSERVE",
        "budget_tier": "local_only",
        "risk_level": "low",
        "allowed_files": ["core/x.py", "tests/test_x.py"],
        "forbidden_files": [".env", ".git", ".agent/private", "secrets", "credentials"],
        "validation": ["python -m pytest -q"],
        "human_approval_required": True,
        "merge_allowed": False,
        "network_allowed": False,
        "model_calls_allowed": False,
        "writes_real_repo": False,
        "requires_sandbox": False,
        "prerequisites": [],
        "expected_artifacts": [".agent/x.json"],
        "notes": ["Report-only."],
    }
    data.update(overrides)
    return data


def _registry(*, drop=(), status_overrides=None, phase_overrides=None, include_close3=True, include_mirror13=True) -> dict:
    status_overrides = status_overrides or {}
    phase_overrides = phase_overrides or {}
    phases = []
    for pid in REQUIRED_MIRROR_LIVE_UI_PHASE_IDS:
        if pid in drop:
            continue
        phases.append(
            _phase(
                pid,
                status=status_overrides.get(pid, "complete"),
                **phase_overrides.get(pid, {}),
            )
        )
    if include_close3:
        phases.append(_phase("MIRROR.CLOSE3", status="complete", prerequisites=["MIRROR.12"]))
    if include_mirror13:
        phases.append(_phase("MIRROR.13", status="proposed", prerequisites=["MIRROR.CLOSE3"]))
    return {"schema_version": "1.0", "updated_at": "2026-07-02T00:00:00+09:00", "phases": phases}


def _source_texts(**overrides) -> dict[str, str]:
    source = {
        "mirror7": """
ENV_FLAG = "MIRROR_TUNNEL_SHADOW_TRACE_ENABLED"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "mirror_tunnel" / "live_traces"
def is_shadow_trace_enabled(env=None):
    return str((env or {}).get(ENV_FLAG, "")).lower() in {"true", "1", "yes"}
def _guardrails():
    return {
        "default_off": True,
        "writes_trace_artifacts_only": True,
        "scoring_during_run": False,
        "claim_diff_check_during_run": False,
        "execution_blocking_performed": False,
    }
BOUNDARIES = ("MIRROR.7 is default-off.", "MIRROR.7 does not score derailment during a run.")
""",
        "mirror8": """
DEFAULT_OUTPUT_DIR = Path(".agent") / "mirror_tunnel" / "live_trace_scoring_preview"
BOUNDARIES = (
    "MIRROR.8 is report-only.",
    "MIRROR.8 is post-run only.",
    "MIRROR.8 writes preview artifacts only.",
    "MIRROR.8 does not mutate live trace artifacts.",
    "MIRROR.8 does not score during runtime.",
)
def _guardrails():
    return {"post_run_only": True, "writes_preview_artifacts_only": True, "live_trace_mutated": False, "runtime_scoring_performed": False}
""",
        "mirror9": """
PANEL_PLAN_READY = "panel_plan_ready"
def _non_blocking_policy():
    return {"is_approval_gate": False, "may_block_run": False, "may_block_patch": False}
def _guardrails():
    return {"report_only": True, "ui_implemented": False, "approval_gate_added": False}
""",
        "template": """
<section id="mirrorTunnelPanel" data-mirror-readonly="true">
  Mirror Tunnel is advisory evidence, not an approval gate.
  <button type="button">Load Mirror preview</button>
  <button type="button">Refresh Mirror summary</button>
  <button type="button">Copy Mirror summary</button>
  <button type="button">Copy artifact paths</button>
</section>
<!-- /mirror-tunnel-panel -->
<div id="primarySubmit">Submit</div>
<div class="actions actions--primary">Apply / Review Patch</div>
// MIRROR.10 read-only operator panel
fetch(`/mirror-tunnel/preview/${encodeURIComponent(previewId)}`)
// /MIRROR.10 read-only operator panel
""",
        "route": """
# MIRROR.11 read-only preview loader
@app.route("/mirror-tunnel/preview/<path:preview_id>", methods=["GET"])
def mirror_tunnel_preview_route(preview_id: str):
    path = _mirror_preview_artifact_path(preview_id)
    preview = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": True, "summary": _mirror_preview_summary(preview, path)}
# /MIRROR.11 read-only preview loader
""",
        "mirror12": """
REPORT_KIND = "mirror_tunnel_live_demo_readiness"
def _guardrails():
    return {
        "report_only": True,
        "artifact_inspection_only": True,
        "manual_demo_executed_by_checker": False,
        "mirror7_writer_called": False,
        "mirror8_preview_builder_called": False,
        "validation_run": False,
        "benchmark_run": False,
    }
BOUNDARIES = ("MIRROR.12 is artifact-inspection only.", "MIRROR.12 does not start a web run.")
""",
    }
    source.update(overrides)
    return source


def _demo_readiness(*, status: str = "demo_ready", useful: bool = True) -> dict:
    return {
        "report_kind": "mirror_tunnel_live_demo_readiness",
        "status": status,
        "trace_id": "trace-alpha",
        "preview_id": "preview-1",
        "summary": {
            "live_trace_ready": useful,
            "preview_ready": True,
            "ui_loader_compatible": True,
            "advisory_non_blocking_policy_preserved": True,
        },
        "frame_coverage": {
            "has_useful_frame_coverage": useful,
            "useful_frame_count": 5 if useful else 1,
        },
        "missing_evidence": [] if useful else [{"source": "live_trace", "reason": "weak_frame_coverage"}],
        "warnings": [] if status == "demo_ready" and useful else ["trace quality still needs review"],
        "blockers": [],
        "guardrails": {
            "manual_demo_executed_by_checker": False,
            "mirror7_writer_called": False,
            "mirror8_preview_builder_called": False,
            "runtime_scoring_performed": False,
            "live_trace_mutated": False,
            "preview_generated": False,
        },
    }


def _build(**overrides) -> dict:
    kwargs = {
        "registry_data": _registry(),
        "source_texts": _source_texts(),
        "demo_readiness_artifact": _demo_readiness(),
        "report_id": "close3",
        "created_at": "2026-07-02T00:00:00+09:00",
        "repo_path": ".",
        "registry_path": "docs/roadmap/phase_registry.json",
        "readiness_artifact_path": ".agent/mirror_tunnel/live_demo_readiness/mirror_tunnel_live_demo_readiness.json",
    }
    kwargs.update(overrides)
    return build_mirror_tunnel_live_ui_readiness_checkpoint(**kwargs)


def test_complete_safe_chain_with_real_demo_evidence_freezes():
    report = _build()

    assert report["report_kind"] == REPORT_KIND == "mirror_tunnel_live_ui_readiness_checkpoint"
    assert report["checkpoint_status"] == STATUS_FROZEN == "live_ui_readiness_frozen"
    assert report["blockers"] == []
    assert report["phase_completion"]["all_required_complete"] is True
    assert report["runtime_safety_checks"]["all_clear"] is True
    assert report["ui_safety_checks"]["all_clear"] is True
    assert report["loader_safety_checks"]["all_clear"] is True
    assert report["demo_readiness_evidence"]["real_demo_chain_exists"] is True
    assert report["recommended_next_phase"] == RECOMMENDED_NEXT_PHASE


def test_missing_real_demo_evidence_reports_needs_live_demo_evidence():
    report = _build(demo_readiness_artifact=None, readiness_artifact_path="")

    assert report["checkpoint_status"] == STATUS_NEEDS_LIVE_DEMO_EVIDENCE
    assert report["blockers"] == []
    assert report["demo_readiness_evidence"]["real_demo_chain_exists"] is False
    assert any("MIRROR.12" in item["detail"] for item in report["missing_evidence"])


def test_weak_demo_evidence_freezes_with_warnings():
    report = _build(demo_readiness_artifact=_demo_readiness(status="demo_ready_with_warnings", useful=False))

    assert report["checkpoint_status"] == STATUS_FROZEN_WITH_WARNINGS
    assert report["blockers"] == []
    assert report["warnings"]


def test_missing_or_incomplete_mirror12_blocks():
    for registry in (
        _registry(drop=("MIRROR.12",)),
        _registry(status_overrides={"MIRROR.12": "proposed"}),
    ):
        report = _build(registry_data=registry)
        assert report["checkpoint_status"] == STATUS_BLOCKED
        assert any("MIRROR.12" in blocker for blocker in report["blockers"])


def test_default_off_mirror7_guard_is_required():
    bad_mirror7 = _source_texts()["mirror7"].replace('"default_off": True', '"default_off": False')
    report = _build(source_texts=_source_texts(mirror7=bad_mirror7))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("default-off" in blocker.lower() for blocker in report["blockers"])


def test_runtime_scoring_marker_blocks_checkpoint():
    bad_mirror7 = _source_texts()["mirror7"] + "\nbuild_mirror_tunnel_derailment_score(trace)\n"
    report = _build(source_texts=_source_texts(mirror7=bad_mirror7))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("runtime scoring" in blocker.lower() or "derailment" in blocker.lower() for blocker in report["blockers"])


def test_mutating_loader_route_blocks_checkpoint():
    bad_route = _source_texts()["route"] + "\npath.write_text(json.dumps(preview), encoding='utf-8')\n"
    report = _build(source_texts=_source_texts(route=bad_route))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("loader" in blocker.lower() and "mutat" in blocker.lower() for blocker in report["blockers"])


def test_apply_reject_approve_buttons_inside_mirror_panel_block_checkpoint():
    bad_template = _source_texts()["template"].replace("</section>", "<button>Approve</button></section>")
    report = _build(source_texts=_source_texts(template=bad_template))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("approve" in blocker.lower() for blocker in report["blockers"])


def test_preview_generation_from_loader_blocks_checkpoint():
    bad_route = _source_texts()["route"] + "\nbuild_mirror_tunnel_live_trace_scoring_preview(trace_path='x')\n"
    report = _build(source_texts=_source_texts(route=bad_route))

    assert report["checkpoint_status"] == STATUS_BLOCKED
    assert any("preview generation" in blocker.lower() or "scoring" in blocker.lower() for blocker in report["blockers"])


def test_checkpoint_writes_json_and_markdown_artifacts(tmp_path):
    result = write_mirror_tunnel_live_ui_readiness_checkpoint(
        repo_path=tmp_path,
        registry_path=tmp_path / "missing-registry.json",
        output_dir=tmp_path / "out",
        report_id="write-test",
        created_at="2026-07-02T00:00:00+09:00",
        inputs={
            "registry_data": _registry(),
            "registry_load_error": "",
            "source_texts": _source_texts(),
            "source_load_errors": {},
            "demo_readiness_artifact": None,
            "demo_readiness_load_error": "not found",
            "readiness_artifact_path": "",
        },
    )

    assert result["ok"] is True
    assert Path(result["json_path"]).name == JSON_NAME
    assert Path(result["md_path"]).name == MD_NAME
    data = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert data["report_id"] == "write-test"
    assert data["checkpoint_status"] == STATUS_NEEDS_LIVE_DEMO_EVIDENCE
    md = Path(result["md_path"]).read_text(encoding="utf-8")
    for section in (
        "## Summary",
        "## Phase Completion",
        "## Runtime Safety Checks",
        "## UI Safety Checks",
        "## Loader Safety Checks",
        "## Demo Readiness Evidence",
        "## Missing Evidence",
        "## Warnings",
        "## Final Verdict",
        "## Recommended Next Phase",
        "## Boundaries / Guardrails",
    ):
        assert section in md


def test_cli_writes_json_result_against_real_repo(tmp_path, capsys):
    code = script.main(
        [
            "--repo-path",
            str(PROJECT_ROOT),
            "--registry",
            str(REGISTRY_PATH),
            "--output-dir",
            str(tmp_path / "out"),
            "--report-id",
            "cli",
            "--created-at",
            "2026-07-02T00:00:00+09:00",
            "--json",
            "--allow-needs-evidence",
            "--allow-warnings",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["report_kind"] == REPORT_KIND
    assert printed["checkpoint_status"] in {
        STATUS_FROZEN,
        STATUS_FROZEN_WITH_WARNINGS,
        STATUS_NEEDS_LIVE_DEMO_EVIDENCE,
    }
    assert Path(printed["artifact_paths"]["json"]).is_file()


def test_build_does_not_mutate_inputs():
    registry = _registry()
    source_texts = _source_texts()
    readiness = _demo_readiness(status="demo_ready_with_warnings", useful=False)
    snapshot = copy.deepcopy([registry, source_texts, readiness])

    build_mirror_tunnel_live_ui_readiness_checkpoint(
        registry_data=registry,
        source_texts=source_texts,
        demo_readiness_artifact=readiness,
    )

    assert [registry, source_texts, readiness] == snapshot


def test_markdown_contains_boundaries_and_guardrails():
    md = render_mirror_tunnel_live_ui_readiness_checkpoint_markdown(_build()).lower()

    for phrase in (
        "report-only",
        "checkpoint only",
        "no model call",
        "no patch apply",
        "no validation run",
        "no benchmark run",
        "no mcp invocation",
        "no worker launch",
        "no dream execution",
        "no docker/subprocess",
        "no network",
        "no database write",
        "no route behavior change",
        "no runtime scoring",
        "no live trace mutation",
        "no preview generation",
        "no execution blocking",
    ):
        assert phrase in md


def test_checkpoint_source_is_report_only_and_does_not_import_runtime_builders():
    core_src = CORE_PATH.read_text(encoding="utf-8")
    script_src = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(core_src + "\n" + script_src)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert "core.mirror_tunnel_shadow_live_trace" not in imports
    assert "core.mirror_tunnel_live_trace_scoring_preview" not in imports
    assert "maybe_write_shadow_live_trace" not in calls
    assert "write_shadow_live_trace" not in calls
    assert "build_mirror_tunnel_live_trace_scoring_preview" not in calls
    assert "write_mirror_tunnel_live_trace_scoring_preview" not in calls

    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "flask",
        "google",
        "httpx",
        "mcp",
        "openai",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    assert sorted({item.split(".", 1)[0] for item in imports} & forbidden_import_roots) == []
    forbidden_calls = {
        "apply_patch",
        "call_model",
        "check_call",
        "check_output",
        "connect",
        "create_dream",
        "invoke_mcp",
        "launch_worker",
        "Popen",
        "post",
        "request",
        "run_benchmarks",
        "run_safe_validation_command",
        "run_validation_command",
        "system",
        "urlopen",
    }
    assert sorted(calls & forbidden_calls) == []


def test_registry_marks_close3_complete_and_picker_recommends_cmd_n4():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.12"]["status"] == "complete"
    assert by_id["MIRROR.CLOSE3"]["status"] == "complete"
    assert by_id["MIRROR.CLOSE3"]["prerequisites"] == ["MIRROR.12"]
    assert by_id["MIRROR.13"]["status"] == "proposed"
    assert by_id["MIRROR.13"]["prerequisites"] == ["MIRROR.CLOSE3"]
    assert by_id["CMD.N1"]["status"] == "complete"
    assert by_id["CMD.N1"]["prerequisites"] == ["MIRROR.CLOSE3"]
    assert by_id["CMD.N2"]["status"] == "complete"
    assert by_id["CMD.N2"]["prerequisites"] == ["CMD.N1"]
    assert by_id["CMD.N3"]["status"] == "complete"
    assert by_id["CMD.N3"]["prerequisites"] == ["CMD.N2"]
    assert by_id["CMD.N4"]["status"] == "complete"
    assert by_id["CMD.N4"]["prerequisites"] == ["CMD.N3"]
    assert by_id["CMD.N5"]["status"] == "complete"
    assert by_id["CMD.N5"]["prerequisites"] == ["CMD.N4"]
    assert by_id["CMD.N6"]["status"] == "proposed"
    assert by_id["CMD.N6"]["prerequisites"] == ["CMD.N5"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="mirror-close3",
        created_at="2026-07-02T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "CMD.N6"
