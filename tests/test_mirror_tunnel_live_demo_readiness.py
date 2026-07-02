"""Tests for MIRROR.12 - Mirror Tunnel Live Demo Readiness Check.

MIRROR.12 inspects artifacts from one manually controlled Mirror Tunnel demo:
an existing MIRROR.7 live trace, an existing MIRROR.8 preview, and the
MIRROR.11 preview-id loading contract. It is report-only and must not generate
traces, score previews, start web runs, or mutate input artifacts.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.mirror_tunnel_live_demo_readiness import (
    DEMO_READY,
    DEMO_READY_WITH_WARNINGS,
    JSON_NAME,
    MD_NAME,
    PREVIEW_MISSING_OR_MISMATCHED,
    STATUS_BLOCKED,
    STATUS_INSUFFICIENT_LIVE_TRACE,
    write_mirror_tunnel_live_demo_readiness,
)
import scripts.create_mirror_tunnel_live_demo_readiness as script


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_PATH = PROJECT_ROOT / "core" / "mirror_tunnel_live_demo_readiness.py"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "create_mirror_tunnel_live_demo_readiness.py"
REGISTRY_PATH = PROJECT_ROOT / "docs" / "roadmap" / "phase_registry.json"
PREVIEW_JSON_NAME = "mirror_tunnel_live_trace_scoring_preview.json"


def _frame(frame_type: str, excerpt: str = "evidence") -> dict:
    return {
        "frame_id": frame_type,
        "frame_index": 0,
        "frame_type": frame_type,
        "availability": "available",
        "artifact_path": "",
        "resolved_artifact_path": "",
        "artifact_kind": "in_memory",
        "excerpt": excerpt,
        "excerpt_truncated": False,
        "classification_reason": "test frame",
    }


def _live_trace(*, trace_id: str = "trace-alpha", thin: bool = False) -> dict:
    frames = [_frame("final_answer", "Done.")] if thin else [
        _frame("user_intent", "Fix checkout total."),
        _frame("control_prompt", "Keep the fix narrow."),
        _frame("patch_or_diff", "diff --git a/checkout.py b/checkout.py"),
        _frame("validation_evidence", "pytest passed."),
        _frame("final_answer", "Updated checkout.py."),
    ]
    return {
        "report_kind": "mirror_tunnel_shadow_live_trace",
        "enabled": True,
        "status": "live_trace_written",
        "trace_id": trace_id,
        "run_id": "run-alpha",
        "created_at": "2026-07-02T00:00:00+09:00",
        "frames": frames,
        "missing_evidence": [] if not thin else [
            {"frame_type": "patch_or_diff", "reason": "source value was not available"}
        ],
        "blocked_reasons": [],
        "artifact_paths": {},
        "boundaries": ["MIRROR.7 is shadow-only."],
        "recommended_next_phase": "MIRROR.8",
        "guardrails": {"report_only": True, "model_call_performed": False},
    }


def _preview(*, trace_id: str = "trace-alpha", status: str = "preview_ready", preview_id: str = "preview-1") -> dict:
    return {
        "report_kind": "mirror_tunnel_live_trace_scoring_preview",
        "preview_id": preview_id,
        "created_at": "2026-07-02T00:00:00+09:00",
        "status": status,
        "recommended_next_action": "review_live_trace_evidence",
        "recommended_next_phase": "MIRROR.9",
        "trace_id": trace_id,
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
            "available_frame_types": ["user_intent", "patch_or_diff", "validation_evidence", "final_answer"],
            "missing_evidence_count": 0,
        },
        "derailment_score_preview": {
            "score_id": f"{preview_id}-mirror2",
            "verdict": "aligned",
            "overall_derailment_score": 0.05,
            "dimension_scores": {"scope_drift": 0.0},
            "recommended_next_action": "review_live_trace_evidence",
            "insufficient_reasons": [],
        },
        "claim_vs_diff_preview": {
            "check_id": f"{preview_id}-mirror3",
            "overall_claim_support": "supported",
            "mismatch_count": 0,
            "unsupported_claim_count": 0,
            "recommended_next_action": "review_live_trace_evidence",
        },
        "combined_review_verdict": {
            "review_id": f"{preview_id}-combined",
            "combined_verdict": "trustworthy_trace",
            "recommended_next_action": "review_live_trace_evidence",
            "warning_count": 0,
        },
        "missing_evidence": [],
        "warnings": [],
        "blockers": [],
        "artifact_paths": {
            "json": f".agent/mirror_tunnel/live_trace_scoring_preview/{preview_id}/{PREVIEW_JSON_NAME}",
            "markdown": f".agent/mirror_tunnel/live_trace_scoring_preview/{preview_id}/mirror_tunnel_live_trace_scoring_preview.md",
        },
        "guardrails": {
            "model_call_performed": False,
            "live_trace_artifact_mutated": False,
            "preview_generation_performed": False,
        },
    }


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _live_trace_path(root: Path) -> Path:
    return root / ".agent" / "mirror_tunnel" / "live_traces" / "run-alpha" / "mirror_tunnel_trace_contract.json"


def _preview_path(root: Path, preview_id: str = "preview-1") -> Path:
    return root / ".agent" / "mirror_tunnel" / "live_trace_scoring_preview" / preview_id / PREVIEW_JSON_NAME


def test_ready_live_trace_and_preview_writes_readiness_report(tmp_path):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace())
    preview_path = _write_json(_preview_path(tmp_path), _preview())
    trace_before = trace_path.read_text(encoding="utf-8")
    preview_before = preview_path.read_text(encoding="utf-8")

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(preview_path),
        preview_id="preview-1",
        created_at="2026-07-02T00:00:00+09:00",
    )

    assert result["ok"] is True
    assert result["status"] in {DEMO_READY, DEMO_READY_WITH_WARNINGS}
    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])
    assert json_path.name == JSON_NAME
    assert md_path.name == MD_NAME
    assert json_path.parent == tmp_path / ".agent" / "mirror_tunnel" / "live_demo_readiness"
    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["report_kind"] == "mirror_tunnel_live_demo_readiness"
    assert report["trace_id"] == "trace-alpha"
    assert report["preview_id"] == "preview-1"
    assert report["live_trace_check"]["schema_compatible"] is True
    assert report["preview_check"]["trace_id_matches"] is True
    assert report["ui_loader_compatibility"]["loader_compatible"] is True
    assert report["recommended_next_phase"] == "MIRROR.CLOSE3"
    assert "Manual Demo Instructions" in md_path.read_text(encoding="utf-8")
    assert trace_path.read_text(encoding="utf-8") == trace_before
    assert preview_path.read_text(encoding="utf-8") == preview_before


def test_missing_live_trace_reports_insufficient_safely(tmp_path):
    preview_path = _write_json(_preview_path(tmp_path), _preview())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(_live_trace_path(tmp_path)),
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_INSUFFICIENT_LIVE_TRACE
    assert result["report"]["live_trace_check"]["exists"] is False
    assert result["report"]["missing_evidence"]


def test_missing_preview_returns_preview_missing_or_mismatched(tmp_path):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(_preview_path(tmp_path)),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == PREVIEW_MISSING_OR_MISMATCHED
    assert result["report"]["preview_check"]["exists"] is False


def test_mismatched_trace_id_is_detected(tmp_path):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace(trace_id="trace-alpha"))
    preview_path = _write_json(_preview_path(tmp_path), _preview(trace_id="trace-beta"))

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == PREVIEW_MISSING_OR_MISMATCHED
    assert result["report"]["preview_check"]["trace_id_matches"] is False


def test_unsafe_live_trace_path_is_blocked(tmp_path):
    preview_path = _write_json(_preview_path(tmp_path), _preview())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path="../outside.json",
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert any("traversal" in blocker["reason"] for blocker in result["report"]["blockers"])


def test_unsafe_preview_path_is_blocked(tmp_path):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path="../preview.json",
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert any("traversal" in blocker["reason"] for blocker in result["report"]["blockers"])


def test_malformed_json_is_blocked(tmp_path):
    trace_path = _live_trace_path(tmp_path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("{not-json", encoding="utf-8")
    preview_path = _write_json(_preview_path(tmp_path), _preview())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert any("malformed" in blocker["reason"] for blocker in result["report"]["blockers"])


def test_preview_inside_live_traces_directory_is_rejected(tmp_path):
    live_dir = tmp_path / ".agent" / "mirror_tunnel" / "live_traces" / "run-alpha"
    trace_path = _write_json(live_dir / "mirror_tunnel_trace_contract.json", _live_trace())
    preview_path = _write_json(live_dir / "preview-copy.json", _preview())

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["ok"] is False
    assert result["status"] == STATUS_BLOCKED
    assert any(blocker["reason"] == "preview_inside_live_traces" for blocker in result["report"]["blockers"])


def test_insufficient_preview_status_keeps_readiness_honest(tmp_path):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace(thin=True))
    preview_path = _write_json(_preview_path(tmp_path), _preview(status="insufficient_trace"))

    result = write_mirror_tunnel_live_demo_readiness(
        repo_path=tmp_path,
        live_trace_path=str(trace_path),
        preview_path=str(preview_path),
        preview_id="preview-1",
    )

    assert result["status"] == STATUS_INSUFFICIENT_LIVE_TRACE
    assert any("insufficient_trace" in warning for warning in result["report"]["warnings"])


def test_cli_writes_json_result(tmp_path, capsys):
    trace_path = _write_json(_live_trace_path(tmp_path), _live_trace())
    preview_path = _write_json(_preview_path(tmp_path), _preview())

    code = script.main(
        [
            "--repo-path",
            str(tmp_path),
            "--live-trace",
            str(trace_path),
            "--preview",
            str(preview_path),
            "--preview-id",
            "preview-1",
            "--created-at",
            "2026-07-02T00:00:00+09:00",
            "--json",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] in {DEMO_READY, DEMO_READY_WITH_WARNINGS}
    assert Path(printed["json_path"]).is_file()


def test_source_is_report_only_and_does_not_import_scoring_or_live_writer():
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


def test_registry_picker_recommends_cmd_n3_after_close3_and_cmd_n2():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_id = {phase["phase_id"]: phase for phase in data["phases"]}

    assert by_id["MIRROR.11"]["status"] == "complete"
    assert by_id["MIRROR.12"]["status"] == "complete"
    assert by_id["MIRROR.12"]["prerequisites"] == ["MIRROR.11"]
    assert by_id["MIRROR.CLOSE3"]["status"] == "complete"
    assert by_id["MIRROR.CLOSE3"]["prerequisites"] == ["MIRROR.12"]
    assert by_id["MIRROR.13"]["status"] == "proposed"
    assert by_id["MIRROR.13"]["prerequisites"] == ["MIRROR.CLOSE3"]

    report = summarize_phase_candidates(
        pick_phase_candidates(data),
        report_id="mirror12-readiness",
        created_at="2026-07-02T00:00:00+09:00",
    )
    assert report["top_recommendation"]["phase_id"] == "CMD.N3"
